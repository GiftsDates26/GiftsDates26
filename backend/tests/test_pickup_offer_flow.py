"""Tests for VIP pick-up offer / address / accept flow (iteration 23).

Flow:
  Step 1 inviter -> POST /vip/schedule/bookings/{id}/pickup/offer (needs taxi.status=pending)
  Step 2 VIP     -> POST /vip/schedule/bookings/{id}/pickup/address (needs pickup.status=offered)
  Step 3a inviter-> POST /vip/schedule/bookings/{id}/pickup/accept (needs pickup.status=address_set)
  Step 3b inviter-> POST /vip/schedule/bookings/{id}/taxi/send -> pickup.status becomes 'taxi_instead'
"""
import os
import datetime
import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"
ADMIN = ("giftsdates@gmail.com", "Admin@GD24!")
VIP = ("testuser@giftsdates.com", "Test@12345")
VIP_ID = "b486a9ec-21a5-46f2-ac7b-4bd42fcb91e6"


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
    r.raise_for_status()
    return r.json()["token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="module")
def admin_tok():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def vip_tok():
    return _login(*VIP)


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(os.environ["MONGO_URL"])
    return c[os.environ["DB_NAME"]]


def _find_free_slot(admin_tok):
    r = requests.get(f"{API}/vip/schedule/{VIP_ID}/slots", headers=_h(admin_tok), timeout=20)
    r.raise_for_status()
    out = []
    for d in r.json().get("days", []):
        for s in d.get("slots", []):
            if s.get("state") == "available" and s.get("slot_len", 60) >= 60:
                out.append((d["date"], s))
    return out


def _create_booking(admin_tok, mongo):
    """Create a fresh VIP booking from admin to VIP; return its id."""
    slots = _find_free_slot(admin_tok)
    if not slots:
        pytest.skip("No available VIP slots")
    date, s = slots[0]
    r = requests.post(
        f"{API}/vip/schedule/{VIP_ID}/book",
        headers=_h(admin_tok),
        json={"date": date, "start": s["start"], "end": s["end"], "length": 1, "place": "own"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["booking_id"]


def _request_taxi(vip_tok, bid, coins=50):
    r = requests.post(f"{API}/vip/schedule/bookings/{bid}/taxi/request", headers=_h(vip_tok), json={"coins": coins}, timeout=20)
    r.raise_for_status()
    return r.json()


@pytest.fixture
def booking_with_taxi(admin_tok, vip_tok, mongo):
    bid = _create_booking(admin_tok, mongo)
    _request_taxi(vip_tok, bid, 50)
    yield bid
    # cleanup
    mongo.vip_sched.delete_one({"id": bid})


# ---------- Step 1: offer ----------
class TestPickupOffer:
    def test_offer_requires_inviter(self, booking_with_taxi, vip_tok):
        r = requests.post(f"{API}/vip/schedule/bookings/{booking_with_taxi}/pickup/offer", headers=_h(vip_tok), timeout=20)
        assert r.status_code == 403, r.text

    def test_offer_requires_pending_taxi(self, admin_tok, vip_tok, mongo):
        bid = _create_booking(admin_tok, mongo)
        try:
            # No taxi requested at all
            r = requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/offer", headers=_h(admin_tok), timeout=20)
            assert r.status_code == 400 and "NO_TAXI_REQUEST" in r.text, r.text
        finally:
            mongo.vip_sched.delete_one({"id": bid})

    def test_offer_ok_and_duplicate(self, booking_with_taxi, admin_tok, mongo, vip_tok):
        bid = booking_with_taxi
        r = requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/offer", headers=_h(admin_tok), timeout=20)
        assert r.status_code == 200, r.text
        p = r.json()["pickup"]
        assert p["status"] == "offered"
        b = mongo.vip_sched.find_one({"id": bid})
        assert b["pickup"]["status"] == "offered"
        # VIP notified
        n = list(mongo.notifications.find({"user_id": VIP_ID, "type": "vs_pickup"}).sort("created_at", -1).limit(3))
        assert any((x.get("data") or {}).get("booking_id") == bid for x in n)
        # Duplicate -> PICKUP_PENDING
        r2 = requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/offer", headers=_h(admin_tok), timeout=20)
        assert r2.status_code == 400 and "PICKUP_PENDING" in r2.text


# ---------- Step 2: address ----------
class TestPickupAddress:
    def test_requires_vip(self, booking_with_taxi, admin_tok):
        bid = booking_with_taxi
        requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/offer", headers=_h(admin_tok), timeout=20).raise_for_status()
        r = requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/address", headers=_h(admin_tok), json={"address": "A"}, timeout=20)
        assert r.status_code == 403

    def test_requires_offer_first(self, booking_with_taxi, vip_tok):
        # No offer called yet
        r = requests.post(f"{API}/vip/schedule/bookings/{booking_with_taxi}/pickup/address", headers=_h(vip_tok), json={"address": "A"}, timeout=20)
        assert r.status_code == 400 and "NO_PICKUP_OFFER" in r.text

    def test_address_required(self, booking_with_taxi, admin_tok, vip_tok):
        bid = booking_with_taxi
        requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/offer", headers=_h(admin_tok), timeout=20).raise_for_status()
        r = requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/address", headers=_h(vip_tok), json={"address": "   "}, timeout=20)
        assert r.status_code == 400 and "ADDRESS_REQUIRED" in r.text

    def test_address_ok_and_editable(self, booking_with_taxi, admin_tok, vip_tok, mongo):
        bid = booking_with_taxi
        requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/offer", headers=_h(admin_tok), timeout=20).raise_for_status()
        payload = {"address": "221B Baker Street", "city": "London", "postal_code": "NW1 6XE",
                   "country": "UK", "lat": 51.5237, "lng": -0.1585, "time": "16:30", "note": "Door bell"}
        r = requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/address", headers=_h(vip_tok), json=payload, timeout=20)
        assert r.status_code == 200, r.text
        p = r.json()["pickup"]
        assert p["status"] == "address_set" and p["address"] == "221B Baker Street" and p["time"] == "16:30" and p["note"] == "Door bell"
        # Inviter notified
        b = mongo.vip_sched.find_one({"id": bid})
        n = list(mongo.notifications.find({"user_id": b["requester_id"], "type": "vs_pickup"}).sort("created_at", -1).limit(3))
        assert any((x.get("data") or {}).get("booking_id") == bid for x in n)
        # Edit (VIP calls again)
        r2 = requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/address", headers=_h(vip_tok),
                           json={"address": "10 Downing", "time": "17:15"}, timeout=20)
        assert r2.status_code == 200
        assert r2.json()["pickup"]["address"] == "10 Downing"


# ---------- Step 3a: accept ----------
class TestPickupAccept:
    def test_accept_requires_inviter(self, booking_with_taxi, admin_tok, vip_tok):
        bid = booking_with_taxi
        requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/offer", headers=_h(admin_tok), timeout=20).raise_for_status()
        requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/address", headers=_h(vip_tok), json={"address": "X"}, timeout=20).raise_for_status()
        r = requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/accept", headers=_h(vip_tok), timeout=20)
        assert r.status_code == 403

    def test_accept_requires_address_set(self, booking_with_taxi, admin_tok):
        # Only offer, no address
        bid = booking_with_taxi
        requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/offer", headers=_h(admin_tok), timeout=20).raise_for_status()
        r = requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/accept", headers=_h(admin_tok), timeout=20)
        assert r.status_code == 400 and "NO_PICKUP_ADDRESS" in r.text

    def test_accept_confirms_booking_and_replaces_taxi(self, booking_with_taxi, admin_tok, vip_tok, mongo):
        bid = booking_with_taxi
        requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/offer", headers=_h(admin_tok), timeout=20).raise_for_status()
        requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/address", headers=_h(vip_tok),
                      json={"address": "Accept St", "time": "17:00"}, timeout=20).raise_for_status()
        r = requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/accept", headers=_h(admin_tok), timeout=20)
        assert r.status_code == 200, r.text
        b = mongo.vip_sched.find_one({"id": bid})
        assert b["status"] == "confirmed"
        assert b["pickup"]["status"] == "accepted"
        assert b["taxi"]["status"] == "replaced"


# ---------- Step 3b: taxi/send instead ----------
class TestTaxiInstead:
    def test_taxi_send_marks_pickup_taxi_instead(self, booking_with_taxi, admin_tok, vip_tok, mongo):
        bid = booking_with_taxi
        requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/offer", headers=_h(admin_tok), timeout=20).raise_for_status()
        requests.post(f"{API}/vip/schedule/bookings/{bid}/pickup/address", headers=_h(vip_tok),
                      json={"address": "Any"}, timeout=20).raise_for_status()
        # Ensure admin has coins to send taxi (top up directly for test, restore after)
        me = requests.get(f"{API}/auth/me", headers=_h(admin_tok), timeout=20).json()
        before = (me.get("coins", 0) or 0) + (me.get("withdrawable", 0) or 0)
        topup = 0
        if before < 50:
            topup = 50 - before
            mongo.users.update_one({"id": me["id"]}, {"$inc": {"coins": topup}})
        try:
            r = requests.post(f"{API}/vip/schedule/bookings/{bid}/taxi/send", headers=_h(admin_tok), timeout=20)
            assert r.status_code == 200, r.text
            b = mongo.vip_sched.find_one({"id": bid})
            assert b["taxi"]["status"] == "sent"
            assert b["pickup"]["status"] == "taxi_instead"
            assert b["status"] == "confirmed"
        finally:
            if topup:
                mongo.users.update_one({"id": me["id"]}, {"$inc": {"coins": -topup}})
