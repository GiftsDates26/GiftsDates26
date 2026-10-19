"""Stripe payments backend tests for GiftsDates."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://giftsdates21.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def user_token():
    email = f"TEST_pay_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={
        "email": email, "password": "Passw0rd!", "name": "Pay Tester",
        "gender": "male", "birth_date": "1990-01-01",
        "age": 34, "interested_in": "female", "city": "Paris", "country": "France"
    })
    assert r.status_code in (200, 201), r.text
    tok = r.json().get("token") or r.json().get("access_token")
    if not tok:
        r2 = requests.post(f"{API}/auth/login", json={"email": email, "password": "Passw0rd!"})
        tok = r2.json().get("token") or r2.json().get("access_token")
    assert tok, "no token returned"
    return tok


@pytest.fixture
def auth_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


ORIGIN = "https://giftsdates21.preview.emergentagent.com"


@pytest.mark.parametrize("package_id", [
    "small_talk", "starter", "popular", "extra", "vip",
    "premium_monthly", "premium_lite_monthly", "vip_monthly",
])
def test_checkout_returns_url(auth_headers, package_id):
    r = requests.post(f"{API}/payments/checkout", headers=auth_headers,
                      json={"package_id": package_id, "origin_url": ORIGIN})
    assert r.status_code == 200, f"{package_id}: {r.status_code} {r.text}"
    data = r.json()
    assert "checkout_url" in data and data["checkout_url"].startswith("https://")
    assert "session_id" in data


def test_checkout_custom(auth_headers):
    r = requests.post(f"{API}/payments/checkout", headers=auth_headers,
                      json={"package_id": "custom", "origin_url": ORIGIN, "usd_amount": 25})
    assert r.status_code == 200, r.text
    assert r.json().get("checkout_url", "").startswith("https://")


def test_checkout_unknown_package(auth_headers):
    r = requests.post(f"{API}/payments/checkout", headers=auth_headers,
                      json={"package_id": "no_such_pkg", "origin_url": ORIGIN})
    assert r.status_code == 400, r.text


def test_checkout_requires_auth():
    r = requests.post(f"{API}/payments/checkout",
                      json={"package_id": "small_talk", "origin_url": ORIGIN})
    assert r.status_code in (401, 403)


def test_payment_status_pending_for_new_session(auth_headers):
    r = requests.post(f"{API}/payments/checkout", headers=auth_headers,
                      json={"package_id": "small_talk", "origin_url": ORIGIN})
    assert r.status_code == 200
    sid = r.json()["session_id"]
    s = requests.get(f"{API}/payments/status/{sid}")
    assert s.status_code == 200, s.text
    body = s.json()
    assert body["session_id"] == sid
    assert body["payment_status"] in ("pending", "unpaid")


def test_payment_status_unknown_session():
    r = requests.get(f"{API}/payments/status/cs_test_unknown_{uuid.uuid4().hex}")
    assert r.status_code == 404
