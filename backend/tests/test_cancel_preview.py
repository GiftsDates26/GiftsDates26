"""Regression: Cancel Preview on regular dates (/dates/cancel/{bid}) and date invites (/invites/{did}/cancel).

Verifies the backend refund split matches CancelPreviewDialog.cancelSplit:
- Inviter cancels regular date (coins=400, taxi.sent=100): refund=300, comp=100, fee=100.
- Invited person cancels regular date: refund = coins + taxi (full).
- Inviter cancels invite with transportation.taxi confirmed (hold=400, taxi_amount=100):
  r_inv = floor(300/2)+100 = 250 ; r_rec = floor(300/4) = 75 ; fee = 25.
- Recipient cancels invite: full hold back to inviter.
"""
import os, uuid, time
from datetime import datetime, timezone, timedelta
import pytest, requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN = {"email": "giftsdates@gmail.com", "password": "Admin@GD24!"}
USER = {"email": "testuser@giftsdates.com", "password": "Test@12345"}


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def user_token():
    return _login(USER)


@pytest.fixture(scope="module")
def admin_id(db):
    return db.users.find_one({"email": ADMIN["email"]})["id"]


@pytest.fixture(scope="module")
def user_id(db):
    return db.users.find_one({"email": USER["email"]})["id"]


def _coins(db, uid):
    u = db.users.find_one({"id": uid})
    return int(u.get("coins", 0)), float(u.get("escrow", 0) or 0), float(u.get("withdrawable", 0) or 0)


def _seed_regular_booking(db, inviter_id, invited_id, coins=400, taxi_coins=100, taxi_status="sent"):
    bid = str(uuid.uuid4())
    sched = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    doc = {
        "id": bid, "from_id": inviter_id, "to_id": invited_id,
        "venue": "TEST_Venue_CP", "city": "TEST_City",
        "address": "Test street 1", "country": "ES", "postal_code": "08001",
        "scheduled_at": sched, "coins": coins,
        "status": "confirmed", "auto_confirmed": True,
        "taxi": {"coins": taxi_coins, "status": taxi_status} if taxi_coins else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.date_bookings.insert_one(doc)
    # keep recipient's escrow/withdrawable consistent
    db.users.update_one({"id": invited_id}, {"$inc": {"escrow": coins, "withdrawable": taxi_coins}})
    return bid


def _cleanup_booking(db, bid):
    db.date_bookings.delete_one({"id": bid})


def test_inviter_cancels_regular_date_split(db, admin_token, admin_id, user_id):
    """Inviter cancel: refund=200+100=300, comp=100, fee=100 (coins=400 taxi=100)."""
    bid = _seed_regular_booking(db, admin_id, user_id, coins=400, taxi_coins=100)
    try:
        inv_before, _, _ = _coins(db, admin_id)
        rec_before = _coins(db, user_id)
        r = requests.post(f"{BASE_URL}/api/dates/cancel/{bid}", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "cancelled"
        assert data["refund"] == 300, data
        assert data["compensation"] == 100, data
        assert data["platform_fee"] == 100, data
        inv_after, _, _ = _coins(db, admin_id)
        assert inv_after - inv_before == 300
        # recipient escrow -= 400 ; withdrawable += (comp - taxi) = 100 - 100 = 0
        _, eb, wb = rec_before
        _, ea, wa = _coins(db, user_id)
        assert eb - ea == 400
        assert round(wa - wb, 2) == 0.0
    finally:
        _cleanup_booking(db, bid)


def test_inviter_cancels_regular_date_no_taxi(db, admin_token, admin_id, user_id):
    """No taxi: refund=200, comp=100, fee=100 (coins=400)."""
    bid = _seed_regular_booking(db, admin_id, user_id, coins=400, taxi_coins=0)
    try:
        inv_before, _, _ = _coins(db, admin_id)
        r = requests.post(f"{BASE_URL}/api/dates/cancel/{bid}", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert (data["refund"], data["compensation"], data["platform_fee"]) == (200, 100, 100)
        inv_after, _, _ = _coins(db, admin_id)
        assert inv_after - inv_before == 200
    finally:
        _cleanup_booking(db, bid)


def test_invited_cancels_regular_date_full_refund(db, user_token, admin_id, user_id):
    """Invited person cancels: full base refund = 400 + 100 = 500 to inviter."""
    bid = _seed_regular_booking(db, admin_id, user_id, coins=400, taxi_coins=100)
    try:
        inv_before, _, _ = _coins(db, admin_id)
        r = requests.post(f"{BASE_URL}/api/dates/cancel/{bid}", headers={"Authorization": f"Bearer {user_token}"}, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["refund"] == 500, data
        assert data["compensation"] == 0
        inv_after, _, _ = _coins(db, admin_id)
        assert inv_after - inv_before == 500
    finally:
        _cleanup_booking(db, bid)


# ---- Invite date (dates collection) ----

def _seed_invite(db, inviter_id, recipient_id, total_hold=400, taxi_amount=100, taxi_confirmed=True):
    did = str(uuid.uuid4())
    start = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    doc = {
        "id": did, "inviter_id": inviter_id, "recipient_id": recipient_id,
        "status": "DATE_CONFIRMED", "total_hold": total_hold, "coins": total_hold,
        "options": [{"idea_id": "idea1", "name": "Dinner"}],
        "chosen_idea": {"idea_id": "idea1", "name": "Dinner"},
        "selected_activity": "Dinner",
        "location": {"venue": "TEST_InvVenue", "address": "x", "city": "TEST", "country": "ES",
                     "scheduled_start": start, "scheduled_end": (datetime.fromisoformat(start) + timedelta(minutes=150)).isoformat()},
        "transportation": {"type": "taxi", "status": "confirmed", "taxi_amount": taxi_amount} if taxi_confirmed and taxi_amount else {},
        "refunded": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.dates.insert_one(doc)
    return did


def _cleanup_invite(db, did):
    db.dates.delete_one({"id": did})


def test_inviter_cancels_invite_split(db, admin_token, admin_id, user_id):
    """hold=400, taxi=100 confirmed: inviter gets floor(300/2)+100=250, recipient 75, fee=25."""
    did = _seed_invite(db, admin_id, user_id, total_hold=400, taxi_amount=100, taxi_confirmed=True)
    try:
        inv_before, _, _ = _coins(db, admin_id)
        _, _, w_before = _coins(db, user_id)
        r = requests.post(f"{BASE_URL}/api/invites/{did}/cancel", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("status") == "CANCELLED"
        inv_after, _, _ = _coins(db, admin_id)
        _, _, w_after = _coins(db, user_id)
        assert inv_after - inv_before == 250, (inv_before, inv_after)
        assert round(w_after - w_before, 2) == 75.0
    finally:
        _cleanup_invite(db, did)


def test_inviter_cancels_invite_no_taxi(db, admin_token, admin_id, user_id):
    """hold=400, no taxi: inviter gets 200, recipient 100, fee=100."""
    did = _seed_invite(db, admin_id, user_id, total_hold=400, taxi_amount=0, taxi_confirmed=False)
    try:
        inv_before, _, _ = _coins(db, admin_id)
        _, _, w_before = _coins(db, user_id)
        r = requests.post(f"{BASE_URL}/api/invites/{did}/cancel", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
        assert r.status_code == 200, r.text
        inv_after, _, _ = _coins(db, admin_id)
        _, _, w_after = _coins(db, user_id)
        assert inv_after - inv_before == 200
        assert round(w_after - w_before, 2) == 100.0
    finally:
        _cleanup_invite(db, did)


def test_recipient_cancels_invite_full_refund(db, user_token, admin_id, user_id):
    """Recipient cancels: inviter gets full hold back (400)."""
    did = _seed_invite(db, admin_id, user_id, total_hold=400, taxi_amount=100, taxi_confirmed=True)
    try:
        inv_before, _, _ = _coins(db, admin_id)
        r = requests.post(f"{BASE_URL}/api/invites/{did}/cancel", headers={"Authorization": f"Bearer {user_token}"}, timeout=15)
        assert r.status_code == 200, r.text
        inv_after, _, _ = _coins(db, admin_id)
        assert inv_after - inv_before == 400
    finally:
        # also remove locked_slots entry pushed by recipient cancel
        db.users.update_one({"id": user_id}, {"$pull": {"locked_slots": {"date_id": did}}})
        _cleanup_invite(db, did)
