"""Backend tests for VIP schedule 1h/2h/3h booking rules.
Covers:
- GET /api/vip/schedule/{vip_id}/slots → durations, windows, taken with lock buffer
- POST /api/vip/schedule/{vip_id}/book → BAD_DURATION / TIME_UNAVAILABLE / SLOT_TAKEN / success
- POST /api/vip/schedule/bookings/{bid}/reschedule → same rules
- Cross-check normal date_bookings as blocking source for VIP booking
"""
import os
import asyncio
import uuid
import requests
import pytest
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "https://repo-site-restore.preview.emergentagent.com"
# Fallback: try reading frontend .env
if "preview" not in BASE_URL and "https" not in BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

LENA_ID = "0be0c2a0-cbb3-480c-b785-533dff4fb64e"
DAY = "2026-10-15"
ADMIN_EMAIL = "giftsdates@gmail.com"
ADMIN_PASS = "Admin@12345"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"admin login: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, f"no token in {r.json()}"
    return tok


@pytest.fixture(scope="module")
def H(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def db():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return cli[os.environ["DB_NAME"]]


# cleanup: track IDs we create so we can wipe after module
CREATED_SCHED = []
CREATED_DBOOK = []


@pytest.fixture(scope="module", autouse=True)
def _cleanup(db):
    yield
    async def go():
        if CREATED_SCHED:
            await db.vip_sched.delete_many({"id": {"$in": CREATED_SCHED}})
        if CREATED_DBOOK:
            await db.date_bookings.delete_many({"id": {"$in": CREATED_DBOOK}})
    asyncio.get_event_loop().run_until_complete(go()) if not asyncio.get_event_loop().is_closed() else asyncio.run(go())


# --- Public slots endpoint ---
class TestSlotsEndpoint:
    def test_durations_windows_and_locks(self, H):
        r = requests.get(f"{BASE_URL}/api/vip/schedule/{LENA_ID}/slots", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("durations") == [60, 120, 180], data
        assert data.get("buffer") == 15
        days = {d["date"]: d for d in data.get("days", [])}
        assert DAY in days, f"missing {DAY}: {list(days)}"
        d = days[DAY]
        assert {"from": "18:00", "to": "23:00"} in d["windows"], d["windows"]
        taken = d["taken"]
        pend = [t for t in taken if t["from"] == "19:00" and t["to"] == "20:00"]
        assert pend, f"pending booking missing in taken: {taken}"
        assert pend[0]["lock_from"] == "18:45"
        assert pend[0]["lock_to"] == "20:15"


# --- Book endpoint rule checks ---
class TestBook:
    def _book(self, H, start, end, coins=300):
        return requests.post(
            f"{BASE_URL}/api/vip/schedule/{LENA_ID}/book", headers=H,
            json={"date": DAY, "start": start, "end": end, "coins": coins,
                  "tz": "America/Toronto"}, timeout=30)

    def test_overlap_buffer_rejected(self, H):
        # 20:00-21:00 overlaps lock 18:45-20:15 → SLOT_TAKEN
        r = self._book(H, "20:00", "21:00")
        assert r.status_code == 409, f"expected 409 got {r.status_code}: {r.text}"
        assert "SLOT_TAKEN" in r.text

    def test_bad_duration_30min(self, H):
        r = self._book(H, "18:00", "18:30")
        assert r.status_code == 400
        assert "BAD_DURATION" in r.text

    def test_bad_duration_90min(self, H):
        # 20:15-21:45 = 90min, inside window & buffer OK → BAD_DURATION
        r = self._book(H, "20:15", "21:45")
        assert r.status_code in (400, 409)
        assert "BAD_DURATION" in r.text or "SLOT_TAKEN" in r.text

    def test_time_unavailable_outside_window(self, H):
        r = self._book(H, "17:30", "18:30")
        assert r.status_code == 400
        assert "TIME_UNAVAILABLE" in r.text

    def test_valid_booking_after_buffer(self, H):
        # 20:15-22:15 = 120 min, respects 15-min buffer after 19:00-20:00 (ends 20:15)
        r = self._book(H, "20:15", "22:15")
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        bid = r.json().get("id") or r.json().get("booking_id")
        if bid:
            CREATED_SCHED.append(bid)


# --- Reschedule endpoint ---
class TestReschedule:
    @pytest.fixture(scope="class")
    def booking_id(self, H):
        # Reuse the booking created by TestBook (20:15-22:15) if present; else create one.
        if CREATED_SCHED:
            return CREATED_SCHED[-1]
        r = requests.post(
            f"{BASE_URL}/api/vip/schedule/{LENA_ID}/book", headers=H,
            json={"date": DAY, "start": "20:15", "end": "22:15", "coins": 200,
                  "tz": "America/Toronto"}, timeout=30)
        assert r.status_code == 200, r.text
        bid = r.json().get("id") or r.json().get("booking_id")
        assert bid
        CREATED_SCHED.append(bid)
        return bid

    def test_reschedule_bad_duration(self, H, booking_id):
        r = requests.post(
            f"{BASE_URL}/api/vip/schedule/bookings/{booking_id}/reschedule", headers=H,
            json={"date": DAY, "start": "20:15", "end": "21:45"}, timeout=30)
        assert r.status_code in (400, 409)
        assert "BAD_DURATION" in r.text or "SLOT_TAKEN" in r.text

    def test_reschedule_time_unavailable(self, H, booking_id):
        r = requests.post(
            f"{BASE_URL}/api/vip/schedule/bookings/{booking_id}/reschedule", headers=H,
            json={"date": DAY, "start": "17:30", "end": "18:30"}, timeout=30)
        assert r.status_code == 400
        assert "TIME_UNAVAILABLE" in r.text


# --- Normal date_bookings cross-check ---
class TestNormalDateBlocksVip:
    def test_normal_date_booking_blocks_vip_booking(self, H, db):
        """Insert accepted date_bookings for Lena at 21:00 local → VIP booking that overlaps lock must fail."""
        async def seed():
            doc = {
                "id": f"TEST_date_{uuid.uuid4()}", "from_id": "x-admin",
                "to_id": LENA_ID, "status": "accepted",
                "scheduled_at": f"{DAY}T21:00:00",
                "local_time": "21:00", "local_day": DAY,
                "slot_from": "21:00", "slot_to": "23:30",
                "coins": 100, "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.date_bookings.insert_one(doc)
            return doc["id"]
        did = asyncio.get_event_loop().run_until_complete(seed())
        CREATED_DBOOK.append(did)

        # slots endpoint should list this as 'date' with lock 20:45-23:45
        r = requests.get(f"{BASE_URL}/api/vip/schedule/{LENA_ID}/slots", headers=H, timeout=30)
        assert r.status_code == 200
        d = {x["date"]: x for x in r.json()["days"]}[DAY]
        date_blocks = [t for t in d["taken"] if t.get("status") == "date"]
        assert date_blocks, f"no 'date' blocks in taken: {d['taken']}"
        found = [t for t in date_blocks if t["from"] == "21:00"]
        assert found, date_blocks
        assert found[0]["lock_from"] == "20:45"
        assert found[0]["lock_to"] == "23:45"

        # Booking overlapping the lock must be rejected
        r = requests.post(
            f"{BASE_URL}/api/vip/schedule/{LENA_ID}/book", headers=H,
            json={"date": DAY, "start": "20:45", "end": "22:45", "coins": 200,
                  "tz": "America/Toronto"}, timeout=30)
        assert r.status_code == 409, f"expected 409 got {r.status_code}: {r.text}"
        assert "SLOT_TAKEN" in r.text
