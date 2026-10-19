"""Iteration 24 — Running Late (both sides) + Cancel refund with taxi coins.

Backend endpoints under test:
- POST /vip/schedule/bookings/{id}/late  { minutes }  -> VIP sets `late`, client sets `client_late`
- POST /vip/schedule/bookings/{id}/cancel             -> refund math including taxi_coins
"""
import os
import datetime as dt
import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"
ADMIN = ("giftsdates@gmail.com", "Admin@GD24!")
VIP = ("testuser@giftsdates.com", "Test@12345")
VIP_ID = "b486a9ec-21a5-46f2-ac7b-4bd42fcb91e6"


def _login(e, p):
    r = requests.post(f"{API}/auth/login", json={"email": e, "password": p}, timeout=20)
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


@pytest.fixture(scope="module")
def admin_id(admin_tok):
    r = requests.get(f"{API}/auth/me", headers=_h(admin_tok), timeout=20)
    r.raise_for_status()
    return r.json()["id"]


def _find_free_slot(admin_tok):
    r = requests.get(f"{API}/vip/schedule/{VIP_ID}/slots", headers=_h(admin_tok), timeout=20)
    r.raise_for_status()
    for d in r.json().get("days", []):
        for s in d.get("slots", []):
            if s.get("state") == "available" and s.get("slot_len", 60) >= 60:
                return d["date"], s
    return None, None


def _create_booking(admin_tok):
    date, s = _find_free_slot(admin_tok)
    if not date:
        pytest.skip("No available VIP slots")
    r = requests.post(
        f"{API}/vip/schedule/{VIP_ID}/book",
        headers=_h(admin_tok),
        json={"date": date, "start": s["start"], "end": s["end"], "length": 1, "place": "own"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["booking_id"]


def _set_now_window(mongo, bid, confirmed=True, taxi_coins=0):
    """Shift booking to today, start = now-30min, end = now+30min (UTC); set status."""
    now = dt.datetime.now(dt.timezone.utc)
    start = (now - dt.timedelta(minutes=30)).replace(second=0, microsecond=0)
    end = start + dt.timedelta(hours=1)
    sets = {
        "date": start.strftime("%Y-%m-%d"),
        "start": start.strftime("%H:%M"),
        "end": end.strftime("%H:%M"),
        "status": "confirmed" if confirmed else "pending",
    }
    if taxi_coins:
        sets["taxi_coins"] = taxi_coins
        sets["coins"] = (sets.get("coins") or 0)
    mongo.vip_sched.update_one({"id": bid}, {"$set": sets})


@pytest.fixture
def booking(admin_tok, mongo):
    bid = _create_booking(admin_tok)
    yield bid
    mongo.vip_sched.delete_one({"id": bid})


# -------- Running late --------
class TestRunningLate:
    def test_vip_notifies_client(self, booking, admin_tok, vip_tok, mongo, admin_id):
        _set_now_window(mongo, booking)
        r = requests.post(f"{API}/vip/schedule/bookings/{booking}/late", headers=_h(vip_tok), json={"minutes": 15}, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["late"]["minutes"] == 15
        b = mongo.vip_sched.find_one({"id": booking})
        assert b["late"]["minutes"] == 15
        assert "client_late" not in b or not b.get("client_late")
        n = list(mongo.notifications.find({"user_id": admin_id, "type": "vs_late"}).sort("created_at", -1).limit(3))
        assert any((x.get("data") or {}).get("booking_id") == booking and (x.get("data") or {}).get("minutes") == 15 for x in n)

    def test_client_notifies_vip(self, booking, admin_tok, mongo):
        _set_now_window(mongo, booking)
        r = requests.post(f"{API}/vip/schedule/bookings/{booking}/late", headers=_h(admin_tok), json={"minutes": 20}, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["client_late"]["minutes"] == 20
        b = mongo.vip_sched.find_one({"id": booking})
        assert b["client_late"]["minutes"] == 20
        n = list(mongo.notifications.find({"user_id": VIP_ID, "type": "vs_late"}).sort("created_at", -1).limit(3))
        assert any((x.get("data") or {}).get("booking_id") == booking and (x.get("data") or {}).get("minutes") == 20 for x in n)

    def test_third_party_403(self, booking, mongo):
        _set_now_window(mongo, booking)
        # Try with an unrelated user token: create a disposable user
        email = f"test_late_{os.urandom(3).hex()}@giftsdates.com"
        pw = "Pass@1234!"
        reg = requests.post(f"{API}/auth/register", json={
            "email": email, "password": pw, "name": "T", "gender": "male", "age": 30,
            "interested_in": "women", "city": "Paris", "country": "France",
        }, timeout=20)
        assert reg.status_code in (200, 201), reg.text
        tok = _login(email, pw)
        r = requests.post(f"{API}/vip/schedule/bookings/{booking}/late", headers=_h(tok), json={"minutes": 10}, timeout=20)
        assert r.status_code == 403

    def test_bad_minutes(self, booking, vip_tok, mongo):
        _set_now_window(mongo, booking)
        r = requests.post(f"{API}/vip/schedule/bookings/{booking}/late", headers=_h(vip_tok), json={"minutes": 7}, timeout=20)
        assert r.status_code == 400
        assert "BAD_MINUTES" in r.text

    def test_not_confirmed_window(self, booking, vip_tok, mongo):
        _set_now_window(mongo, booking, confirmed=False)
        r = requests.post(f"{API}/vip/schedule/bookings/{booking}/late", headers=_h(vip_tok), json={"minutes": 10}, timeout=20)
        assert r.status_code == 400
        assert "NOT_DATE_TIME" in r.text

    def test_outside_window(self, booking, vip_tok, mongo):
        # Set start 5h in the future -> outside the 3h window
        now = dt.datetime.now(dt.timezone.utc)
        start = now + dt.timedelta(hours=5)
        end = start + dt.timedelta(hours=1)
        mongo.vip_sched.update_one({"id": booking}, {"$set": {
            "date": start.strftime("%Y-%m-%d"), "start": start.strftime("%H:%M"),
            "end": end.strftime("%H:%M"), "status": "confirmed",
        }})
        r = requests.post(f"{API}/vip/schedule/bookings/{booking}/late", headers=_h(vip_tok), json={"minutes": 10}, timeout=20)
        assert r.status_code == 400
        assert "NOT_DATE_TIME" in r.text


# -------- Cancel refund math with taxi coins --------
# Per server.py:
#   base = coins - taxi_coins
#   refund_to_client = round(base*0.5) + taxi_coins
#   comp_to_vip      = round(base*0.25)
#   platform_fee     = base - refund_nontaxi - comp
class TestCancelRefundWithTaxi:
    def test_client_cancels_with_taxi(self, booking, admin_tok, mongo):
        # Craft a confirmed booking with coins + taxi coins
        mongo.vip_sched.update_one({"id": booking}, {"$set": {
            "status": "confirmed", "coins": 300, "taxi_coins": 100,
        }})
        r = requests.post(f"{API}/vip/schedule/bookings/{booking}/cancel", headers=_h(admin_tok), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        # base = 200 -> refund = 100 + 100(taxi) = 200, comp = 50, fee = 50
        assert d["refunded"] == 200
        assert d["compensation"] == 50
        assert d["platform_fee"] == 50

    def test_vip_cancels_with_taxi_full_refund(self, booking, admin_tok, vip_tok, mongo):
        mongo.vip_sched.update_one({"id": booking}, {"$set": {
            "status": "confirmed", "coins": 300, "taxi_coins": 100,
        }})
        r = requests.post(f"{API}/vip/schedule/bookings/{booking}/cancel", headers=_h(vip_tok), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["refunded"] == 300  # full refund incl taxi
        assert d["compensation"] == 0
        assert d["platform_fee"] == 0

    def test_client_cancel_without_taxi(self, booking, admin_tok, mongo):
        mongo.vip_sched.update_one({"id": booking}, {"$set": {
            "status": "confirmed", "coins": 200, "taxi_coins": 0,
        }})
        r = requests.post(f"{API}/vip/schedule/bookings/{booking}/cancel", headers=_h(admin_tok), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        # base=200 -> refund=100 comp=50 fee=50
        assert d["refunded"] == 100
        assert d["compensation"] == 50
        assert d["platform_fee"] == 50
