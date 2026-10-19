"""Backend tests for busy/locked slot validation on invites and date bookings.

Covers the spec: GET /api/profiles/{pid}/availability returns busy_slots per local day
(booked + cancelled), locked_days contains only cancelled blocks, each block exposes
from/to/lock_from/lock_to (15-min buffer). POST /api/invites and POST /api/dates/book
reject past times (TIME_PASSED), overlap with cancelled (SLOT_LOCKED:HH:MM-HH:MM) and
overlap with other active dates (SLOT_BUSY:HH:MM-HH:MM); valid free slot succeeds.
"""
import os
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0]).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_ID = "fc5b1d5f-3966-428d-b13c-04911f9f38f3"
INVITER = {"email": "avtest_b@example.com", "password": "Test@12345"}


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def inviter_token():
    r = requests.post(f"{API}/auth/login", json=INVITER, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def avail(inviter_token):
    r = requests.get(f"{API}/profiles/{ADMIN_ID}/availability", headers=_h(inviter_token), timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


# ----------------------------------------------------------------------------
# Availability payload
# ----------------------------------------------------------------------------
class TestAvailabilityPayload:
    def test_structure(self, avail):
        for k in ("busy_slots", "locked_days", "day_windows", "start_step", "slot_minutes", "buffer"):
            assert k in avail, f"missing {k}"
        assert avail["slot_minutes"] == 150
        assert avail["buffer"] == 15
        assert avail["start_step"] == 15

    def test_cancelled_block_on_2026_10_24(self, avail):
        blocks = avail["busy_slots"].get("2026-10-24") or []
        cancelled = [b for b in blocks if b["reason"] == "cancelled"]
        assert cancelled, "Expected cancelled block on 2026-10-24 from cxl-test-1"
        c = cancelled[0]
        assert c["from"] == "19:00" and c["to"] == "21:30"
        # 15-min buffer around
        assert c["lock_from"] == "18:45" and c["lock_to"] == "21:45"

    def test_locked_days_contains_only_cancelled(self, avail):
        # locked_days must only contain cancelled blocks and not include fully-booked days
        locked = avail["locked_days"]
        assert "2026-10-24" in locked
        for d, lst in locked.items():
            for b in lst:
                assert b["reason"] == "cancelled", f"locked_days should only hold cancelled blocks, got {b}"

    def test_booked_block_on_2026_10_17(self, avail):
        blocks = avail["busy_slots"].get("2026-10-17") or []
        booked = [b for b in blocks if b["from"] == "12:00" and b["reason"] == "booked"]
        assert booked, "Accepted booking on 2026-10-17 12:00 missing"
        assert booked[0]["lock_from"] == "11:45" and booked[0]["lock_to"] == "14:45"

    def test_pending_invites_on_2026_10_16(self, avail):
        blocks = avail["busy_slots"].get("2026-10-16") or []
        froms = sorted(b["from"] for b in blocks if b["reason"] == "booked")
        assert "22:00" in froms and "23:00" in froms

    def test_2026_10_16_fully_booked(self, avail):
        # Sat window 22:00-02:00 with pending invites at 22:00 and 23:00 → fully blocked
        assert "2026-10-16" in avail["busy_days"]


# ----------------------------------------------------------------------------
# POST /api/invites validation
# ----------------------------------------------------------------------------
def _invite_payload(day, time_str, coins=160):
    return {
        "recipient_id": ADMIN_ID,
        "scheduled_start": f"{day}T{time_str}:00Z",
        "local_day": day, "local_time": time_str,
        "activity_option_1": "Coffee", "activity_option_2": "Walk", "activity_option_3": "Dinner",
        "coins": coins, "safety_ack": True,
    }


class TestInviteValidation:
    def test_time_passed(self, inviter_token):
        # 2026-10-10 is a Saturday (in admin weekly schedule) in the past → TIME_PASSED
        r = requests.post(f"{API}/invites", headers=_h(inviter_token),
                          json=_invite_payload("2026-10-10", "19:00"), timeout=30)
        assert r.status_code == 400, r.text
        assert "TIME_PASSED" in r.text, r.text

    def test_slot_locked_overlap_cancelled(self, inviter_token):
        # 2026-10-24 19:00 overlaps cancelled 19:00-21:30
        r = requests.post(f"{API}/invites", headers=_h(inviter_token),
                          json=_invite_payload("2026-10-24", "19:00"), timeout=30)
        assert r.status_code == 400, r.text
        assert "SLOT_LOCKED:19:00-21:30" in r.text, r.text

    def test_slot_busy_overlap_active(self, inviter_token):
        # 2026-10-16 22:00 overlaps active invite at 22:00 → SLOT_BUSY
        r = requests.post(f"{API}/invites", headers=_h(inviter_token),
                          json=_invite_payload("2026-10-16", "22:00"), timeout=30)
        assert r.status_code == 400, r.text
        assert "SLOT_BUSY:" in r.text, r.text

    def test_valid_slot_success_and_cleanup(self, inviter_token):
        # 2026-10-24 00:00 → free (window 00:00-03:00, no overlap with cancelled 18:45-21:45)
        day, time_str = "2026-10-24", "00:00"
        r = requests.post(f"{API}/invites", headers=_h(inviter_token),
                          json=_invite_payload(day, time_str), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("status") == "INVITATION_SENT"
        invite_id = data.get("id") or data.get("date_id") or data.get("invite_id")
        assert invite_id, data
        # Verify persisted local_day/local_time via /api/dates
        drsp = requests.get(f"{API}/dates", headers=_h(inviter_token), timeout=30)
        if drsp.status_code == 200:
            match = [x for x in (drsp.json() if isinstance(drsp.json(), list) else drsp.json().get("dates", [])) if x.get("id") == invite_id]
            if match:
                assert match[0].get("local_day") == day
                assert match[0].get("local_time") == time_str
        # cleanup — delete the created invite doc entirely so we don't leave a lingering
        # cancelled block (which would also be seen by the next test run / UI).
        try:
            from pymongo import MongoClient
            MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")].dates.delete_one({"id": invite_id})
        except Exception:
            cr = requests.post(f"{API}/invites/{invite_id}/cancel", headers=_h(inviter_token), timeout=30)
            assert cr.status_code in (200, 204), cr.text


# ----------------------------------------------------------------------------
# POST /api/dates/book validation
# ----------------------------------------------------------------------------
def _book_payload(day, time_str, coins=300):
    return {
        "target_id": ADMIN_ID, "venue": "TEST_Cafe", "city": "London",
        "scheduled_at": f"{day}T{time_str}:00Z", "local_day": day, "local_time": time_str,
        "coins": coins, "activities": ["Coffee", "Walk", "Dinner"],
    }


class TestBookDateValidation:
    def test_time_passed(self, inviter_token):
        r = requests.post(f"{API}/dates/book", headers=_h(inviter_token),
                          json=_book_payload("2026-10-10", "19:00"), timeout=30)
        assert r.status_code == 400, r.text
        assert "TIME_PASSED" in r.text, r.text

    def test_slot_locked_overlap_cancelled(self, inviter_token):
        r = requests.post(f"{API}/dates/book", headers=_h(inviter_token),
                          json=_book_payload("2026-10-24", "19:00"), timeout=30)
        assert r.status_code == 400, r.text
        assert "SLOT_LOCKED:19:00-21:30" in r.text, r.text

    def test_slot_busy_overlap_active(self, inviter_token):
        r = requests.post(f"{API}/dates/book", headers=_h(inviter_token),
                          json=_book_payload("2026-10-16", "22:00"), timeout=30)
        assert r.status_code == 400, r.text
        assert "SLOT_BUSY:" in r.text, r.text
