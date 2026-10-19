# Verified address (geocoding) tests: /geo/verify, invite location (inviter), pickup address (recipient)
import os, uuid, time
from datetime import datetime, timezone, timedelta
import pytest, requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env"); load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

REAL = {"address": "100 Queen St W", "city": "Toronto", "postal_code": "M5H 2N2", "country": "Canada"}
FAKE = {"address": "999 Zzqxwplorian Blvd", "city": "Toronto", "postal_code": "M5H 2N2", "country": "Canada"}
NONUM = {"address": "Queen St W", "city": "Toronto", "postal_code": "M5H 2N2", "country": "Canada"}


def login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def user_h(): return login("testuser@giftsdates.com", "Test@12345")


@pytest.fixture(scope="module")
def admin_h(): return login("giftsdates@gmail.com", "Admin@12345")


@pytest.fixture(scope="module")
def ids():
    me = db.users.find_one({"email": "testuser@giftsdates.com"})["id"]
    ad = db.users.find_one({"email": "giftsdates@gmail.com"})["id"]
    return me, ad


CREATED = []


def mk_date(inviter, recipient, status, days):
    now = datetime.now(timezone.utc)
    s = (now + timedelta(days=days, hours=3)).replace(microsecond=0)
    did = "TEST_va_" + uuid.uuid4().hex[:8]
    CREATED.append(did)
    opts = [{"idea_id": "opt1", "name": "Dinner", "order": 1}]
    db.dates.insert_one({"id": did, "seed": True, "test_va": True, "inviter_id": inviter, "recipient_id": recipient,
                         "status": status, "options": opts, "chosen_idea": opts[0], "proposed_start": s.isoformat(),
                         "proposed_end": (s + timedelta(hours=3)).isoformat(), "coins": 100, "total_hold": 100,
                         "location": {"venue": "Bar", "address": "100 Queen St W", "city": "Toronto", "scheduled_start": s.isoformat()} if status != "DATE_ACTIVITY_SELECTED" else None,
                         "transportation": {"type": "pickup", "status": "pending"} if status == "PICKUP_ADDRESS_PENDING" else None,
                         "status_log": [], "created_at": now.isoformat()})
    return did


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    db.dates.delete_many({"id": {"$in": CREATED}})


# ---- /geo/verify ----
class TestGeoVerify:
    def test_real_address_ok(self, user_h):
        r = requests.post(f"{BASE_URL}/api/geo/verify", json=REAL, headers=user_h, timeout=40)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True and isinstance(d["lat"], float) and isinstance(d["lng"], float)
        assert 43.5 < d["lat"] < 43.8 and -79.6 < d["lng"] < -79.2
        assert "Toronto" in d.get("display_name", "")

    def test_fake_street_not_found(self, user_h):
        time.sleep(1.2)
        r = requests.post(f"{BASE_URL}/api/geo/verify", json=FAKE, headers=user_h, timeout=40)
        assert r.status_code == 400 and r.json()["detail"] == "ADDRESS_NOT_FOUND", r.text

    def test_no_number(self, user_h):
        r = requests.post(f"{BASE_URL}/api/geo/verify", json=NONUM, headers=user_h)
        assert r.status_code == 400 and r.json()["detail"] == "ADDRESS_NUMBER_REQUIRED"

    @pytest.mark.parametrize("field", ["address", "city", "postal_code", "country"])
    def test_missing_field(self, user_h, field):
        r = requests.post(f"{BASE_URL}/api/geo/verify", json={**REAL, field: "  "}, headers=user_h)
        assert r.status_code == 400 and r.json()["detail"] == "ADDRESS_FIELDS_REQUIRED"

    def test_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/geo/verify", json=REAL)
        assert r.status_code in (401, 403)


# ---- inviter location ----
class TestInviteLocation:
    def test_location_validation_and_success(self, user_h, admin_h, ids):
        me, ad = ids
        did = mk_date(me, ad, "DATE_ACTIVITY_SELECTED", 30)
        url = f"{BASE_URL}/api/invites/{did}/location"
        # missing venue
        r = requests.post(url, json={**REAL, "venue": " "}, headers=user_h)
        assert r.status_code == 400 and r.json()["detail"] == "ADDRESS_FIELDS_REQUIRED", r.text
        for f in ["address", "city", "postal_code", "country"]:
            r = requests.post(url, json={**REAL, "venue": "Cafe", f: ""}, headers=user_h)
            assert r.status_code == 400 and r.json()["detail"] == "ADDRESS_FIELDS_REQUIRED", (f, r.text)
        # unknown address
        r = requests.post(url, json={**FAKE, "venue": "Cafe"}, headers=user_h, timeout=40)
        assert r.status_code == 400 and r.json()["detail"] == "ADDRESS_NOT_FOUND", r.text
        # recipient may not set location
        r = requests.post(url, json={**REAL, "venue": "Cafe"}, headers=admin_h)
        assert r.status_code == 403
        assert db.dates.find_one({"id": did})["status"] == "DATE_ACTIVITY_SELECTED"
        # success; client lat/lng must be ignored
        r = requests.post(url, json={**REAL, "venue": "TEST Cafe", "lat": 1.0, "lng": 2.0}, headers=user_h, timeout=40)
        assert r.status_code == 200 and r.json()["status"] == "LOCATION_PROPOSED", r.text
        d = db.dates.find_one({"id": did})
        loc = d["location"]
        assert d["status"] == "LOCATION_PROPOSED"
        assert loc["venue"] == "TEST Cafe" and loc["postal_code"] == "M5H 2N2" and loc["country"] == "Canada"
        assert 43.5 < loc["lat"] < 43.8 and -79.6 < loc["lng"] < -79.2

    def test_location_missing_venue_key_422(self, user_h, ids):
        me, ad = ids
        did = mk_date(me, ad, "DATE_ACTIVITY_SELECTED", 31)
        r = requests.post(f"{BASE_URL}/api/invites/{did}/location", json=REAL, headers=user_h)
        assert r.status_code in (400, 422)


# ---- recipient pickup address ----
class TestPickupAddress:
    def test_pickup_validation_and_success(self, user_h, admin_h, ids):
        me, ad = ids
        did = mk_date(ad, me, "PICKUP_ADDRESS_PENDING", 32)
        url = f"{BASE_URL}/api/invites/{did}/pickup/address"
        base = {"pickup_address": "x", "venue": "Home", "street": REAL["address"], "city": "Toronto", "postal_code": "M5H 2N2", "country": "Canada"}
        for f in ["venue", "street", "city", "postal_code", "country"]:
            r = requests.post(url, json={**base, f: ""}, headers=user_h)
            assert r.status_code == 400 and r.json()["detail"] == "ADDRESS_FIELDS_REQUIRED", (f, r.text)
        r = requests.post(url, json={**base, "street": "Queen St W"}, headers=user_h)
        assert r.status_code == 400 and r.json()["detail"] == "ADDRESS_NUMBER_REQUIRED"
        r = requests.post(url, json={**base, "street": FAKE["address"]}, headers=user_h, timeout=40)
        assert r.status_code == 400 and r.json()["detail"] == "ADDRESS_NOT_FOUND", r.text
        r = requests.post(url, json=base, headers=admin_h)
        assert r.status_code == 403
        r = requests.post(url, json={**base, "lat": 0, "lng": 0}, headers=user_h, timeout=40)
        assert r.status_code == 200 and r.json()["status"] == "PICKUP_ADDRESS_SELECTED", r.text
        d = db.dates.find_one({"id": did})
        t = d["transportation"]
        assert d["status"] == "PICKUP_ADDRESS_SELECTED"
        assert t["pickup_venue"] == "Home" and t["pickup_street"] == "100 Queen St W" and t["pickup_postal_code"] == "M5H 2N2"
        assert 43.5 < t["pickup_lat"] < 43.8
        assert "Home" in t["pickup_address"] and "Canada" in t["pickup_address"]

    def test_pickup_wrong_status(self, user_h, ids):
        me, ad = ids
        did = mk_date(ad, me, "LOCATION_PROPOSED", 33)
        r = requests.post(f"{BASE_URL}/api/invites/{did}/pickup/address",
                          json={"pickup_address": "x", "venue": "Home", "street": "100 Queen St W", "city": "Toronto", "postal_code": "M5H 2N2", "country": "Canada"}, headers=user_h)
        assert r.status_code == 400

    def test_pickup_without_pickup_address_field(self, user_h, ids):
        # pickup_address is a required pydantic str; frontend always sends it but API clients may not
        me, ad = ids
        did = mk_date(ad, me, "PICKUP_ADDRESS_PENDING", 34)
        r = requests.post(f"{BASE_URL}/api/invites/{did}/pickup/address",
                          json={"venue": "Home", "street": "100 Queen St W", "city": "Toronto", "postal_code": "M5H 2N2", "country": "Canada"}, headers=user_h, timeout=40)
        print("no pickup_address ->", r.status_code, r.text[:200])
        assert r.status_code in (200, 422)
