"""Backend tests for Live Location sharing (to_date / to_support) and admin endpoint."""
import os
import pytest
import requests
from datetime import datetime, timezone

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://repo-site-restore.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

ADMIN = ("giftsdates@gmail.com", "Admin@12345")
USER = ("ll_tester@example.com", "Test@12345")
BID = "ll-test-1"


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def user_token():
    return _login(*USER)


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _reset_schedule_now():
    # Make sure booking is within live window
    from pymongo import MongoClient
    c = MongoClient("mongodb://localhost:27017")
    c["test_database"].date_bookings.update_one(
        {"id": BID},
        {"$set": {"scheduled_at": datetime.now(timezone.utc).isoformat(), "status": "confirmed"},
         "$unset": {"live_location": ""}},
    )
    c.close()


def test_a_window_setup():
    _reset_schedule_now()


def test_share_with_date_only_hidden_from_other_via_support(user_token, admin_token):
    _reset_schedule_now()
    # user shares to date only
    r = requests.post(f"{API}/live-location/booking/{BID}",
                      headers=_h(user_token),
                      json={"lat": 43.65, "lng": -79.38, "sharing": True, "to_date": True, "to_support": False},
                      timeout=20)
    assert r.status_code == 200, r.text
    assert r.json()["sharing"] is True

    # admin (the other party) GETs - should see other
    r = requests.get(f"{API}/live-location/booking/{BID}", headers=_h(admin_token), timeout=20)
    assert r.status_code == 200
    assert r.json()["other"] is not None
    assert r.json()["other"]["lat"] == 43.65

    # admin list of support locations should NOT include this entry
    r = requests.get(f"{API}/admin/live-locations", headers=_h(admin_token), timeout=20)
    assert r.status_code == 200
    assert not any(x["date_id"] == BID for x in r.json())


def test_share_with_support_only_hidden_from_date(user_token, admin_token):
    _reset_schedule_now()
    r = requests.post(f"{API}/live-location/booking/{BID}",
                      headers=_h(user_token),
                      json={"lat": 44.0, "lng": -80.0, "sharing": True, "to_date": False, "to_support": True},
                      timeout=20)
    assert r.status_code == 200
    # other party (admin) sees other=None since to_date=false
    r = requests.get(f"{API}/live-location/booking/{BID}", headers=_h(admin_token), timeout=20)
    assert r.status_code == 200
    assert r.json()["other"] is None

    # admin list includes the entry
    r = requests.get(f"{API}/admin/live-locations", headers=_h(admin_token), timeout=20)
    assert r.status_code == 200
    rows = r.json()
    match = [x for x in rows if x["date_id"] == BID]
    assert len(match) == 1
    assert match[0]["to_date"] is False
    assert match[0]["lat"] == 44.0


def test_both_flags_false_removes_entry(user_token, admin_token):
    _reset_schedule_now()
    # First share
    requests.post(f"{API}/live-location/booking/{BID}", headers=_h(user_token),
                  json={"lat": 44.1, "lng": -80.1, "sharing": True, "to_date": True, "to_support": True}, timeout=20)
    # Then stop with both flags false
    r = requests.post(f"{API}/live-location/booking/{BID}", headers=_h(user_token),
                      json={"lat": 44.1, "lng": -80.1, "sharing": True, "to_date": False, "to_support": False}, timeout=20)
    assert r.status_code == 200
    assert r.json()["sharing"] is False

    r = requests.get(f"{API}/live-location/booking/{BID}", headers=_h(admin_token), timeout=20)
    assert r.status_code == 200
    assert r.json()["other"] is None
    # me from user's view
    rme = requests.get(f"{API}/live-location/booking/{BID}", headers=_h(user_token), timeout=20)
    assert rme.json()["me"] is None


def test_non_admin_forbidden_on_admin_endpoint(user_token):
    r = requests.get(f"{API}/admin/live-locations", headers=_h(user_token), timeout=20)
    assert r.status_code == 403
