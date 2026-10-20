"""Iteration 32: date_card chat messages (invites / bookings / VIP) + decline_reason on cards."""
import os
import random
import uuid
import pytest
import requests
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = ("giftsdates@gmail.com", "Admin@12345")
USER = ("testuser@giftsdates.com", "Test@12345")


@pytest.fixture(scope="session")
def db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _login(e, p):
    r = requests.post(f"{API}/auth/login", json={"email": e, "password": p}, timeout=20)
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=20).json()
    return {"Authorization": f"Bearer {tok}"}, me["id"]


@pytest.fixture(scope="session")
def admin(db):
    h, uid = _login(*ADMIN)
    db.users.update_one({"id": uid}, {"$set": {"coins": 5000}})
    return h, uid


@pytest.fixture(scope="session")
def user(db):
    h, uid = _login(*USER)
    db.users.update_one({"id": uid}, {"$set": {"coins": 5000}})
    return h, uid


@pytest.fixture(scope="session")
def conv(admin, user, db):
    c = db.conversations.find_one({"users": {"$all": [admin[1], user[1]]}}, {"_id": 0, "id": 1})
    return c["id"] if c else None


def _cards(h, cid, ref):
    r = requests.get(f"{API}/conversations/{cid}/messages", headers=h, timeout=20)
    assert r.status_code == 200
    return [m for m in r.json() if m.get("type") == "date_card" and m.get("ref_id") == ref]


def _cid(db, a, b):
    return db.conversations.find_one({"users": {"$all": [a, b]}})["id"]


def _day():
    return datetime.now(timezone.utc) + timedelta(days=random.randint(200, 900))


def _create_invite(admin, user):
    d = _day().replace(hour=12, minute=0, second=0, microsecond=0)
    r = requests.post(f"{API}/invites", headers=admin[0], json={
        "recipient_id": user[1], "activity_option_1": "TEST_Coffee", "activity_option_2": "TEST_Walk", "activity_option_3": "TEST_Dinner",
        "scheduled_start": d.isoformat(), "local_day": d.strftime("%Y-%m-%d"), "local_time": "12:00", "coins": 150, "safety_ack": True}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["id"]


LOC = {"venue": "TEST_Cafe", "address": "Rue de Rivoli 1", "city": "Paris", "postal_code": "75001", "country": "France",
       "lat": 48.86, "lng": 2.34, "address_confirmed": True}


# Invite: invite -> choose -> location -> confirm, with action_for transitions
class TestInviteFlow:
    def test_full_happy_flow(self, admin, user, db):
        did = _create_invite(admin, user)
        cid = _cid(db, admin[1], user[1])
        cards = _cards(user[0], cid, did)
        assert len(cards) == 1
        c = cards[0]
        assert c["event"] == "invite" and c["kind"] == "invite" and c["action_for"] == user[1]
        assert [o["name"] for o in c["data"]["options"]] == ["TEST_Coffee", "TEST_Walk", "TEST_Dinner"]
        assert c["data"]["options"][0]["id"] == "opt1"
        assert c["data"]["coins"] == 150 and c["data"]["when"]
        # inviter sees the same card
        assert len(_cards(admin[0], cid, did)) == 1

        r = requests.post(f"{API}/invites/{did}/choose", headers=user[0], json={"idea_id": "opt2"}, timeout=20)
        assert r.status_code == 200, r.text
        cards = _cards(user[0], cid, did)
        assert [x["event"] for x in cards] == ["invite", "accepted"]
        assert cards[0]["action_for"] is None and cards[1]["action_for"] is None
        assert cards[1]["data"]["option"] == "TEST_Walk"

        r = requests.post(f"{API}/invites/{did}/location", headers=admin[0], json=LOC, timeout=30)
        assert r.status_code == 200, r.text
        cards = _cards(user[0], cid, did)
        loc = cards[-1]
        assert loc["event"] == "location" and loc["action_for"] == user[1]
        for k in ("venue", "address", "city", "postal_code", "country", "lat", "lng"):
            assert k in loc["data"]["location"]
        assert loc["data"]["location"]["venue"] == "TEST_Cafe"

        r = requests.post(f"{API}/invites/{did}/location/confirm", headers=user[0], timeout=20)
        assert r.status_code == 200, r.text
        cards = _cards(user[0], cid, did)
        assert cards[-1]["event"] == "confirmed"
        assert all(x["action_for"] is None for x in cards)
        # cleanup: inviter cancels (allowed, far future)
        requests.post(f"{API}/invites/{did}/cancel", headers=admin[0], timeout=20)

    def test_location_reject_card(self, admin, user, db):
        did = _create_invite(admin, user)
        requests.post(f"{API}/invites/{did}/choose", headers=user[0], json={"idea_id": "opt1"}, timeout=20)
        assert requests.post(f"{API}/invites/{did}/location", headers=admin[0], json=LOC, timeout=30).status_code == 200
        r = requests.post(f"{API}/invites/{did}/location/reject", headers=user[0], timeout=20)
        assert r.status_code == 200, r.text
        cards = _cards(admin[0], _cid(db, admin[1], user[1]), did)
        assert cards[-1]["event"] == "declined" and cards[-1]["data"]["reason"] == "Meeting place rejected"
        assert all(x["action_for"] is None for x in cards)

    def test_decline_with_reason_and_invites_list(self, admin, user, db):
        did = _create_invite(admin, user)
        r = requests.post(f"{API}/invites/{did}/cancel", headers=user[0], params={"reason": "TEST_busy that day"}, timeout=20)
        assert r.status_code == 200, r.text
        cards = _cards(admin[0], _cid(db, admin[1], user[1]), did)
        assert cards[-1]["event"] == "declined" and cards[-1]["data"]["reason"] == "TEST_busy that day"
        assert cards[0]["action_for"] is None
        # inviter cancelled list shows reason, declined_by_me false
        lst = requests.get(f"{API}/invites/cancelled", headers=admin[0], timeout=20).json()
        items = lst if isinstance(lst, list) else (lst.get("items") or lst.get("dates") or [])
        it = next((x for x in items if x["id"] == did), None)
        assert it is not None, "declined invite missing from /invites/cancelled"
        assert it["decline_reason"] == "TEST_busy that day" and it["declined_by_me"] is False
        # recipient view -> declined_by_me true
        lst2 = requests.get(f"{API}/invites/cancelled", headers=user[0], timeout=20).json()
        items2 = lst2 if isinstance(lst2, list) else (lst2.get("items") or lst2.get("dates") or [])
        it2 = next((x for x in items2 if x["id"] == did), None)
        assert it2 and it2["declined_by_me"] is True
        # GET /invites also exposes the fields
        r = requests.get(f"{API}/invites", headers=admin[0], timeout=20)
        assert r.status_code == 200
        body = r.json()
        flat = body if isinstance(body, list) else [x for v in body.values() if isinstance(v, list) for x in v]
        if flat:
            assert "decline_reason" in flat[0] and "declined_by_me" in flat[0]


# Booked dates: /dates/book -> respond accept / decline with reason
class TestBookingFlow:
    def _book(self, admin, user):
        d = _day().replace(hour=14, minute=0, second=0, microsecond=0)
        r = requests.post(f"{API}/dates/book", headers=admin[0], json={
            "target_id": user[1], "venue": "TEST_Bar", "city": "Paris", "address": "Rue de Rivoli 1", "postal_code": "75001",
            "country": "France", "lat": 48.86, "lng": 2.34, "address_confirmed": True, "scheduled_at": d.isoformat(),
            "local_day": d.strftime("%Y-%m-%d"), "local_time": "14:00", "coins": 200, "activities": ["TEST_A", "TEST_B", "TEST_C"]}, timeout=30)
        assert r.status_code == 200, r.text
        return r.json()["booking_id"]

    def test_book_accept(self, admin, user, db):
        bid = self._book(admin, user)
        cid = _cid(db, admin[1], user[1])
        c = _cards(user[0], cid, bid)
        assert len(c) == 1 and c[0]["kind"] == "booking" and c[0]["action_for"] == user[1]
        assert c[0]["data"]["options"] == ["TEST_A", "TEST_B", "TEST_C"]
        assert c[0]["data"]["location"]["venue"] == "TEST_Bar"
        r = requests.post(f"{API}/dates/respond/{bid}", headers=user[0], params={"accept": "true", "selected_activity": "TEST_B"}, timeout=20)
        assert r.status_code == 200, r.text
        c = _cards(user[0], cid, bid)
        assert c[-1]["event"] == "accepted" and c[-1]["data"]["option"] == "TEST_B" and c[0]["action_for"] is None

    def test_book_decline_reason(self, admin, user, db):
        bid = self._book(admin, user)
        r = requests.post(f"{API}/dates/respond/{bid}", headers=user[0], params={"accept": "false", "reason": "TEST_too far"}, timeout=20)
        assert r.status_code == 200, r.text
        c = _cards(admin[0], _cid(db, admin[1], user[1]), bid)
        assert c[-1]["event"] == "declined" and c[-1]["data"]["reason"] == "TEST_too far" and c[-1]["data"]["refunded"] == 200
        assert db.date_bookings.find_one({"id": bid})["decline_reason"] == "TEST_too far"
        r = requests.get(f"{API}/dates", headers=admin[0], timeout=20)
        assert r.status_code == 200
        body = r.json()
        flat = body if isinstance(body, list) else [x for v in body.values() if isinstance(v, list) for x in v]
        row = next((x for x in flat if x.get("id") == bid), None)
        assert row is not None and row.get("decline_reason") == "TEST_too far"


# VIP calendar booking -> confirm / decline(reason)
class TestVipFlow:
    def _book(self, user, admin, db):
        day = _day().strftime("%Y-%m-%d")
        db.vip_avail.insert_one({"id": f"TEST_{uuid.uuid4()}", "vip_id": admin[1], "date": day, "start": "09:00", "end": "22:00", "slot_len": 60, "tz": "UTC", "seed": True})
        r = requests.post(f"{API}/vip/schedule/{admin[1]}/book", headers=user[0], json={
            "date": day, "start": "12:00", "end": "13:00", "length": 1, "tz": "UTC", "place": "other", "venue": "TEST_VipSpot",
            "address": "Rue de Rivoli 1", "city": "Paris", "postal_code": "75001", "country": "France", "lat": 48.86, "lng": 2.34,
            "address_confirmed": True}, timeout=30)
        assert r.status_code == 200, r.text
        return r.json()["booking_id"]

    def test_vip_confirm(self, user, admin, db):
        bid = self._book(user, admin, db)
        cid = _cid(db, admin[1], user[1])
        c = _cards(admin[0], cid, bid)
        assert len(c) == 1 and c[0]["kind"] == "vip" and c[0]["action_for"] == admin[1]
        assert c[0]["data"]["location"].get("city") == "Paris"
        r = requests.post(f"{API}/vip/schedule/bookings/{bid}/confirm", headers=admin[0], timeout=20)
        assert r.status_code == 200, r.text
        c = _cards(admin[0], cid, bid)
        assert c[-1]["event"] == "accepted" and c[0]["action_for"] is None
        requests.post(f"{API}/vip/schedule/bookings/{bid}/decline", headers=admin[0], timeout=20)

    def test_vip_decline_reason(self, user, admin, db):
        bid = self._book(user, admin, db)
        r = requests.post(f"{API}/vip/schedule/bookings/{bid}/decline", headers=admin[0], params={"reason": "TEST_not free"}, timeout=20)
        assert r.status_code == 200, r.text
        c = _cards(user[0], _cid(db, admin[1], user[1]), bid)
        assert c[-1]["event"] == "declined" and c[-1]["data"]["reason"] == "TEST_not free"
        r = requests.get(f"{API}/vip/schedule/bookings/mine", headers=user[0], timeout=20)
        assert r.status_code == 200
        body = r.json()
        flat = body if isinstance(body, list) else [x for v in body.values() if isinstance(v, list) for x in v]
        row = next((x for x in flat if x.get("id") == bid), None)
        assert row is not None and row.get("decline_reason") == "TEST_not free"

    def test_no_date_card_access_for_outsider(self, admin, user, db):
        cid = _cid(db, admin[1], user[1])
        r = requests.get(f"{API}/conversations/{cid}/messages", timeout=20)
        assert r.status_code in (401, 403)
