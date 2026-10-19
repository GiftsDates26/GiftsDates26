"""Backend tests for availability ranges / weekly schedule / clock picker validation."""
import os
import requests
import pytest
from datetime import datetime, timedelta, timezone

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        try:
            for line in open("/app/frontend/.env"):
                if line.startswith("REACT_APP_BACKEND_URL="):
                    v = line.split("=", 1)[1].strip(); break
        except Exception: pass
    assert v, "REACT_APP_BACKEND_URL not configured"
    return v.rstrip("/")

BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

OWNER = {"email": "giftsdates@gmail.com", "password": "Admin@12345"}
INVITER = {"email": "avtest_b@example.com", "password": "Test@12345"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login {creds['email']}: {r.status_code} {r.text}"
    return r.json()["token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def owner_token():
    return _login(OWNER)


@pytest.fixture(scope="module")
def inviter_token():
    return _login(INVITER)


@pytest.fixture(scope="module")
def owner_me(owner_token):
    r = requests.get(f"{API}/auth/me", headers=_h(owner_token))
    assert r.status_code == 200
    return r.json()


def _future_day(weekday_target, days_ahead_min=1):
    """Return next YYYY-MM-DD matching the python weekday (Mon=0)."""
    d = datetime.now(timezone.utc).date() + timedelta(days=days_ahead_min)
    while d.weekday() != weekday_target:
        d += timedelta(days=1)
    return d.isoformat()


# --- Availability PATCH ------------------------------------------------------
class TestAvailabilityPatch:
    def test_set_weekly_and_specific(self, owner_token):
        # Monday 18:00-23:00; Friday 22:00-02:00 (overnight)
        weekly = {"0": [{"from": "18:00", "to": "23:00"}], "4": [{"from": "22:00", "to": "02:00"}]}
        specific_day = _future_day(5)  # Saturday
        ranges = {specific_day: [{"from": "12:00", "to": "14:30"}, {"from": "19:00", "to": "23:00"}]}
        r = requests.patch(f"{API}/auth/me", headers=_h(owner_token),
                           json={"availability_weekly": weekly, "availability_ranges": ranges})
        assert r.status_code == 200, r.text
        me = r.json()
        assert me["availability_weekly"]["0"][0]["from"] == "18:00"
        assert me["availability_weekly"]["4"][0]["to"] == "02:00"
        assert me["availability_ranges"][specific_day][0]["from"] == "12:00"
        assert len(me["availability_ranges"][specific_day]) == 2

    def test_invalid_range_rejected(self, owner_token):
        # "to" == "from" should be rejected (filtered out, so day removed)
        r = requests.patch(f"{API}/auth/me", headers=_h(owner_token),
                           json={"availability_ranges": {"2026-11-01": [{"from": "10:00", "to": "10:00"}]}})
        assert r.status_code == 200
        # The day should not appear (filter dropped it)
        assert "2026-11-01" not in (r.json().get("availability_ranges") or {})


# --- /profiles/{id}/availability --------------------------------------------
class TestProfileAvailability:
    def test_day_windows_combine(self, inviter_token, owner_me):
        pid = owner_me["id"]
        r = requests.get(f"{API}/profiles/{pid}/availability", headers=_h(inviter_token))
        assert r.status_code == 200, r.text
        data = r.json()
        assert "day_windows" in data
        assert data.get("restricted") is True
        assert data.get("slot_minutes") == 150
        assert data.get("start_step") == 15
        # weekly Monday should populate at least one future Monday
        today = datetime.now(timezone.utc).date()
        found_mon = any(datetime.fromisoformat(d).weekday() == 0 for d in data["day_windows"])
        assert found_mon, "Weekly Monday schedule not reflected in day_windows"


# --- Invite validation (clock time) -----------------------------------------
class TestInviteTimeValidation:
    def _invite(self, token, pid, day, time_str, coins=400):
        start_iso = f"{day}T{time_str}:00Z"
        return requests.post(f"{API}/invites", headers=_h(token), json={
            "recipient_id": pid, "scheduled_start": start_iso,
            "local_day": day, "local_time": time_str,
            "activity_option_1": "Coffee", "activity_option_2": "Walk", "activity_option_3": "Dinner",
            "coins": coins, "safety_ack": True,
        })

    def test_closed_day_rejected(self, inviter_token, owner_me):
        # Sunday (wd=6) with no weekly entry and no specific-day override should be closed
        day = _future_day(6)  # Sunday
        r = self._invite(inviter_token, owner_me["id"], day, "20:00")
        assert r.status_code == 400
        assert "DAY_UNAVAILABLE" in r.text or "TIME_UNAVAILABLE" in r.text

    def test_time_outside_range_rejected(self, inviter_token, owner_me):
        day = _future_day(0)  # Monday - weekly 18:00-23:00
        r = self._invite(inviter_token, owner_me["id"], day, "10:00")
        assert r.status_code == 400
        assert "TIME_UNAVAILABLE" in r.text

    def test_valid_monday_time_accepted(self, inviter_token, owner_me):
        day = _future_day(0)
        # 18:00 + 2.5h = 20:30 fits inside 18:00-23:00
        r = self._invite(inviter_token, owner_me["id"], day, "18:00")
        assert r.status_code == 200, r.text
        assert r.json().get("status") == "INVITATION_SENT"

    def test_too_late_rejected(self, inviter_token, owner_me):
        day = _future_day(0)
        # 21:00 + 2.5h = 23:30 > 23:00 end -> rejected
        r = self._invite(inviter_token, owner_me["id"], day, "21:00")
        assert r.status_code == 400
        assert "TIME_UNAVAILABLE" in r.text

    def test_overnight_friday_23_accepted(self, inviter_token, owner_me):
        day = _future_day(4)  # Friday - weekly 22:00-02:00 overnight
        # 23:00 + 2.5h = 01:30 next day; fits inside 22:00->02:00(+1d)
        r = self._invite(inviter_token, owner_me["id"], day, "23:00")
        assert r.status_code == 200, r.text

    def test_overnight_friday_midnight_rejected(self, inviter_token, owner_me):
        day = _future_day(4)
        # 00:00 start — _hm_to_min=0, not >=1320(=22:00) & window 22:00-26:00 => fit_start returns None
        r = self._invite(inviter_token, owner_me["id"], day, "00:00")
        assert r.status_code == 400
        assert "TIME_UNAVAILABLE" in r.text
