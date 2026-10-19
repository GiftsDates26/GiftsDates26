# Address map-check + "I confirm this address is correct" override across all address endpoints (iteration 28)
import os, uuid, time
from datetime import datetime, timezone, timedelta
import pytest, requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env"); load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

MTL = {"address": "2155 av Prudhomme, 16", "city": "Montreal", "postal_code": "H4A 3H3", "country": "Canada"}
FAKE = {"address": "12 Nowhere Fakeway", "city": "Toronto", "postal_code": "M5H 2N2", "country": "Canada"}
WRONG_CITY = {"address": "2155 av Prudhomme", "city": "Toronto", "postal_code": "M5H 2N2", "country": "Canada"}
MISSING = {"address": "12 Nowhere Fakeway", "city": "", "postal_code": "M5H 2N2", "country": "Canada"}

CREATED = {"dates": [], "date_bookings": [], "vip_sched": [], "vip_avail": []}


def login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def h(): return login("testuser@giftsdates.com", "Test@12345")


@pytest.fixture(scope="module")
def ids():
    return db.users.find_one({"email": "testuser@giftsdates.com"})["id"], db.users.find_one({"email": "giftsdates@gmail.com"})["id"]


@pytest.fixture(scope="module", autouse=True)
def state(ids):
    me, ad = ids
    snap = {u: db.users.find_one({"id": u}, {"_id": 0, "coins": 1, "escrow": 1, "withdrawable": 1, "vip_own_place": 1}) for u in (me, ad)}
    db.users.update_one({"id": me}, {"$set": {"coins": 20000}})
    yield
    for u, s in snap.items():
        db.users.update_one({"id": u}, {"$set": {k: s.get(k, 0) for k in ("coins", "escrow", "withdrawable")}})
    if snap[me].get("vip_own_place"):
        db.users.update_one({"id": me}, {"$set": {"vip_own_place": snap[me]["vip_own_place"]}})
    for col, idl in CREATED.items():
        db[col].delete_many({"id": {"$in": idl}})
    db.date_bookings.delete_many({"from_id": me, "venue": {"$regex": "^TEST_"}})
    db.vip_sched.delete_many({"requester_id": me, "venue": {"$regex": "^TEST_"}})


def post(path, body, h, method="post"):
    return requests.request(method, f"{BASE_URL}/api{path}", json=body, headers=h, timeout=45)


def det(r):
    try: return r.json().get("detail")
    except Exception: return r.text


def mk_date(inviter, recipient, status):
    s = (datetime.now(timezone.utc) + timedelta(days=9, hours=3)).replace(microsecond=0)
    did = "TEST_ao_" + uuid.uuid4().hex[:8]; CREATED["dates"].append(did)
    opts = [{"idea_id": "opt1", "name": "Dinner", "order": 1}]
    db.dates.insert_one({"id": did, "seed": True, "inviter_id": inviter, "recipient_id": recipient, "status": status, "options": opts,
                         "chosen_idea": opts[0], "proposed_start": s.isoformat(), "proposed_end": (s + timedelta(hours=3)).isoformat(),
                         "coins": 100, "total_hold": 100,
                         "location": {"venue": "Bar", "address": "100 Queen St W", "city": "Toronto", "scheduled_start": s.isoformat()} if status != "DATE_ACTIVITY_SELECTED" else None,
                         "transportation": {"type": "pickup", "status": "awaiting_address"} if status == "PICKUP_ADDRESS_PENDING" else None,
                         "status_log": [], "created_at": s.isoformat()})
    return did


# ---- /geo/verify ----
class TestGeoVerify:
    def test_montreal_fuzzy_ok(self, h):
        r = post("/geo/verify", MTL, h)
        assert r.status_code == 200, r.text
        d = r.json(); assert d["ok"] is True and d["unverified"] is False
        assert 45.3 < d["lat"] < 45.7 and -73.8 < d["lng"] < -73.4

    def test_fake_not_found(self, h):
        time.sleep(1)
        r = post("/geo/verify", FAKE, h)
        assert r.status_code == 400 and det(r) == "ADDRESS_NOT_FOUND", r.text

    def test_wrong_city_not_found(self, h):
        time.sleep(1)
        r = post("/geo/verify", WRONG_CITY, h)
        assert r.status_code == 400 and det(r) == "ADDRESS_NOT_FOUND", r.text

    def test_missing_fields(self, h):
        r = post("/geo/verify", MISSING, h)
        assert r.status_code == 400 and det(r) == "ADDRESS_FIELDS_REQUIRED"


# ---- VIP own place ----
class TestOwnPlace:
    def test_own_place_override(self, h, ids):
        r = post("/vip/own-place", FAKE, h, "put")
        assert r.status_code == 400 and det(r) == "ADDRESS_NOT_FOUND", r.text
        r = post("/vip/own-place", {**MISSING, "address_confirmed": True}, h, "put")
        assert r.status_code == 400 and det(r) == "ADDRESS_FIELDS_REQUIRED"
        r = post("/vip/own-place", {**FAKE, "address_confirmed": True, "lat": 1.0, "lng": 2.0}, h, "put")
        assert r.status_code == 200, r.text
        d = r.json(); assert d["unverified"] is True and d["lat"] is None and d["lng"] is None and "address_confirmed" not in d
        g = requests.get(f"{BASE_URL}/api/vip/own-place", headers=h).json()
        assert g["unverified"] is True and g["address"] == FAKE["address"]


# ---- Invite location / pickup ----
class TestInvites:
    def test_location_override(self, h, ids):
        me, ad = ids
        did = mk_date(me, ad, "DATE_ACTIVITY_SELECTED")
        body = {"venue": "TEST_Cafe", **FAKE}
        r = post(f"/invites/{did}/location", body, h)
        assert r.status_code == 400 and det(r) == "ADDRESS_NOT_FOUND", r.text
        r = post(f"/invites/{did}/location", {**body, "venue": ""}, h)
        assert det(r) == "ADDRESS_FIELDS_REQUIRED"
        r = post(f"/invites/{did}/location", {**body, "address_confirmed": True, "lat": 5, "lng": 5}, h)
        assert r.status_code == 200, r.text
        loc = db.dates.find_one({"id": did})["location"]
        assert loc["unverified"] is True and loc["lat"] is None and loc["lng"] is None

    def test_pickup_override(self, h, ids):
        me, ad = ids
        did = mk_date(ad, me, "PICKUP_ADDRESS_PENDING")
        body = {"venue": "TEST_Home", "street": FAKE["address"], "city": FAKE["city"], "postal_code": FAKE["postal_code"], "country": FAKE["country"]}
        r = post(f"/invites/{did}/pickup/address", body, h)
        assert r.status_code == 400 and det(r) == "ADDRESS_NOT_FOUND", r.text
        r = post(f"/invites/{did}/pickup/address", {**body, "address_confirmed": True}, h)
        assert r.status_code == 200, r.text
        t = db.dates.find_one({"id": did})["transportation"]
        assert t["pickup_unverified"] is True and t["pickup_lat"] is None and t["pickup_lng"] is None


# ---- date_bookings meet location ----
class TestMeetLocation:
    def test_meet_override(self, h, ids):
        me, ad = ids
        bid = "TEST_ml_" + uuid.uuid4().hex[:8]; CREATED["date_bookings"].append(bid)
        db.date_bookings.insert_one({"id": bid, "from_id": ad, "to_id": me, "venue": "TEST_VIP", "city": "Toronto", "status": "accepted", "coins": 10,
                                     "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(), "created_at": datetime.now(timezone.utc).isoformat()})
        r = post(f"/dates/meet-location/{bid}", FAKE, h)
        assert r.status_code == 400 and det(r) == "ADDRESS_NOT_FOUND", r.text
        r = post(f"/dates/meet-location/{bid}", {**FAKE, "address_confirmed": True}, h)
        assert r.status_code == 200, r.text
        m = db.date_bookings.find_one({"id": bid})["meet"]
        assert m["unverified"] is True and m["lat"] is None


# ---- VIP schedule pickup address ----
class TestVsPickup:
    def test_vs_pickup_override(self, h, ids):
        me, ad = ids
        bid = "TEST_vp_" + uuid.uuid4().hex[:8]; CREATED["vip_sched"].append(bid)
        day = (datetime.now(timezone.utc) + timedelta(days=6)).strftime("%Y-%m-%d")
        db.vip_sched.insert_one({"id": bid, "vip_id": me, "requester_id": ad, "date": day, "start": "18:00", "end": "19:00", "status": "pending",
                                 "venue": "TEST_x", "taxi": {"status": "pending", "amount": 10}, "pickup": {"status": "offered"}, "coins": 10, "tz": "UTC"})
        r = post(f"/vip/schedule/bookings/{bid}/pickup/address", FAKE, h)
        assert r.status_code == 400 and det(r) == "ADDRESS_NOT_FOUND", r.text
        r = post(f"/vip/schedule/bookings/{bid}/pickup/address", {**FAKE, "address_confirmed": True}, h)
        assert r.status_code == 200, r.text
        p = db.vip_sched.find_one({"id": bid})["pickup"]
        assert p["unverified"] is True and p["lat"] is None and p["status"] == "address_set"


# ---- Booking creation endpoints ----
class TestBookings:
    def test_dates_book_override(self, h, ids):
        me, ad = ids
        when = (datetime.now(timezone.utc) + timedelta(days=11)).replace(hour=18, minute=0, second=0, microsecond=0)
        body = {"target_id": ad, "venue": "TEST_Bar", **FAKE, "scheduled_at": when.isoformat(), "coins": 500, "activities": ["a", "b", "c"]}
        r = post("/dates/book", body, h)
        assert r.status_code == 400 and det(r) == "ADDRESS_NOT_FOUND", r.text
        r = post("/dates/book", {**body, "address_confirmed": True, "lat": 9, "lng": 9}, h)
        assert r.status_code == 200, r.text
        b = db.date_bookings.find_one({"id": r.json()["booking_id"]}); CREATED["date_bookings"].append(b["id"])
        assert b["lat"] is None and b["lng"] is None
        assert b.get("unverified") is True, "booking doc has no unverified flag"

    @pytest.mark.parametrize("place", ["your", "other"])
    def test_vip_book_override(self, h, ids, place):
        me, ad = ids
        when = (datetime.now(timezone.utc) + timedelta(days=12)).strftime("%Y-%m-%dT19:00")
        body = {"target_id": ad, "venue": "TEST_VipBar", **FAKE, "scheduled_at": when, "coins": 1, "place": place, "vip_length": 1}
        r = post("/vip/book", body, h)
        assert r.status_code == 400 and det(r) == "ADDRESS_NOT_FOUND", r.text
        r = post("/vip/book", {**body, "address_confirmed": True}, h)
        assert r.status_code == 200, r.text
        b = db.date_bookings.find_one({"id": r.json()["booking_id"]}); CREATED["date_bookings"].append(b["id"])
        assert b["lat"] is None
        assert b.get("unverified") is True, "VIP booking doc has no unverified flag"

    @pytest.mark.parametrize("place,start", [("your", "10:00"), ("other", "14:00")])
    def test_vs_book_override(self, h, ids, place, start):
        me, ad = ids
        day = (datetime.now(timezone.utc) + timedelta(days=13)).strftime("%Y-%m-%d")
        aid = "TEST_av_" + place; CREATED["vip_avail"].append(aid)
        db.vip_avail.delete_many({"id": aid})
        db.vip_avail.insert_one({"id": aid, "vip_id": ad, "date": day, "start": "09:00", "end": "22:00", "slot_len": 60, "tz": "UTC"})
        end = f"{int(start[:2]) + 1:02d}:00"
        body = {"date": day, "start": start, "end": end, "length": 1, "venue": "TEST_vs", "place": place, "tz": "UTC", **FAKE}
        r = post(f"/vip/schedule/{ad}/book", body, h)
        assert r.status_code == 400 and det(r) == "ADDRESS_NOT_FOUND", r.text
        r = post(f"/vip/schedule/{ad}/book", {**body, "address_confirmed": True}, h)
        assert r.status_code == 200, r.text
        b = db.vip_sched.find_one({"requester_id": me, "date": day, "start": start, "vip_id": ad}, sort=[("created_at", -1)])
        CREATED["vip_sched"].append(b["id"])
        assert b["location"]["lat"] is None
        assert b["location"].get("unverified") is True, "vip_sched location has no unverified flag"


# ---- iteration 29: verified address -> unverified False, own place flag carried, vs pickup excludes address_confirmed ----
QUEEN = {"address": "100 Queen St W", "city": "Toronto", "postal_code": "M5H 2N2", "country": "Canada"}


@pytest.fixture
def admin_own_place(ids):
    me, ad = ids
    old = db.users.find_one({"id": ad}, {"_id": 0, "vip_own_place": 1}).get("vip_own_place")
    yield lambda loc: db.users.update_one({"id": ad}, {"$set": {"vip_own_place": loc}})
    if old is None: db.users.update_one({"id": ad}, {"$unset": {"vip_own_place": ""}})
    else: db.users.update_one({"id": ad}, {"$set": {"vip_own_place": old}})


class TestIter29:
    def test_dates_book_verified(self, h, ids):
        me, ad = ids
        when = (datetime.now(timezone.utc) + timedelta(days=14)).replace(hour=18, minute=0, second=0, microsecond=0)
        r = post("/dates/book", {"target_id": ad, "venue": "TEST_Bar", **QUEEN, "scheduled_at": when.isoformat(), "coins": 500,
                                 "activities": ["a", "b", "c"], "address_confirmed": True, "unverified": True}, h)
        assert r.status_code == 200, r.text
        b = db.date_bookings.find_one({"id": r.json()["booking_id"]}); CREATED["date_bookings"].append(b["id"])
        assert b["unverified"] is False and abs(b["lat"] - 43.6536) < 0.01

    def test_vip_book_verified(self, h, ids):
        me, ad = ids
        when = (datetime.now(timezone.utc) + timedelta(days=15)).strftime("%Y-%m-%dT19:00")
        r = post("/vip/book", {"target_id": ad, "venue": "TEST_VipBar", **QUEEN, "scheduled_at": when, "coins": 1, "place": "your",
                               "vip_length": 1, "unverified": True}, h)
        assert r.status_code == 200, r.text
        b = db.date_bookings.find_one({"id": r.json()["booking_id"]}); CREATED["date_bookings"].append(b["id"])
        assert b["unverified"] is False and b["lat"] is not None

    @pytest.mark.parametrize("unv", [True, False])
    def test_vip_book_own(self, h, ids, admin_own_place, unv):
        me, ad = ids
        admin_own_place({**(FAKE if unv else QUEEN), "lat": None if unv else 43.65, "lng": None if unv else -79.38, "unverified": unv})
        when = (datetime.now(timezone.utc) + timedelta(days=16 + int(unv))).strftime("%Y-%m-%dT19:00")
        r = post("/vip/book", {"target_id": ad, "venue": "TEST_VipOwn", "city": "", "scheduled_at": when, "coins": 1, "place": "own",
                               "vip_length": 1, "unverified": not unv}, h)
        assert r.status_code == 200, r.text
        b = db.date_bookings.find_one({"id": r.json()["booking_id"]}); CREATED["date_bookings"].append(b["id"])
        assert b["unverified"] is unv and b["address"] == (FAKE if unv else QUEEN)["address"]

    @pytest.mark.parametrize("place,start,unv", [("own", "16:00", True), ("own", "18:00", False), ("your", "20:00", False)])
    def test_vs_book_flags(self, h, ids, admin_own_place, place, start, unv):
        me, ad = ids
        day = (datetime.now(timezone.utc) + timedelta(days=13)).strftime("%Y-%m-%d")
        aid = "TEST_av29"; CREATED["vip_avail"].append(aid)
        if not db.vip_avail.find_one({"id": aid}):
            db.vip_avail.insert_one({"id": aid, "vip_id": ad, "date": day, "start": "09:00", "end": "23:00", "slot_len": 60, "tz": "UTC"})
        admin_own_place({**(FAKE if unv else QUEEN), "lat": None if unv else 43.65, "lng": None if unv else -79.38, "unverified": unv})
        end = f"{int(start[:2]) + 1:02d}:00"
        body = {"date": day, "start": start, "end": end, "length": 1, "venue": "TEST_vs29", "place": place, "tz": "UTC", "unverified": True}
        if place != "own": body.update(QUEEN)
        r = post(f"/vip/schedule/{ad}/book", body, h)
        assert r.status_code == 200, r.text
        b = db.vip_sched.find_one({"requester_id": me, "date": day, "start": start, "vip_id": ad}, sort=[("created_at", -1)])
        CREATED["vip_sched"].append(b["id"])
        assert b["location"]["unverified"] is unv, b["location"]

    def test_vs_pickup_no_address_confirmed(self, h, ids):
        me, ad = ids
        bid = "TEST_vp29_" + uuid.uuid4().hex[:8]; CREATED["vip_sched"].append(bid)
        day = (datetime.now(timezone.utc) + timedelta(days=6)).strftime("%Y-%m-%d")
        db.vip_sched.insert_one({"id": bid, "vip_id": me, "requester_id": ad, "date": day, "start": "18:00", "end": "19:00", "status": "pending",
                                 "venue": "TEST_x", "taxi": {"status": "pending", "amount": 10}, "pickup": {"status": "offered"}, "coins": 10, "tz": "UTC"})
        r = post(f"/vip/schedule/bookings/{bid}/pickup/address", {**QUEEN, "address_confirmed": True}, h)
        assert r.status_code == 200, r.text
        p = db.vip_sched.find_one({"id": bid})["pickup"]
        assert "address_confirmed" not in p and p["unverified"] is False and p["lat"] is not None
