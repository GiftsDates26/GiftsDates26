"""Backend tests for Stripe checkout endpoints (coins, custom, premium, VIP)."""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://gd24-preview.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "giftsdates@gmail.com"
ADMIN_PASSWORD = "Admin@GD24!"
ORIGIN = BASE_URL


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def auth(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


def _assert_checkout(resp):
    assert resp.status_code == 200, f"{resp.status_code}: {resp.text}"
    data = resp.json()
    assert "checkout_url" in data and data["checkout_url"].startswith("https://checkout.stripe.com"), data
    assert "session_id" in data and data["session_id"].startswith("cs_"), data
    return data


# Coin package checkout
def test_checkout_coin_package_small_talk(auth):
    r = auth.post(f"{BASE_URL}/api/payments/checkout", json={"package_id": "small_talk", "origin_url": ORIGIN})
    _assert_checkout(r)


def test_checkout_coin_package_popular(auth):
    r = auth.post(f"{BASE_URL}/api/payments/checkout", json={"package_id": "popular", "origin_url": ORIGIN})
    _assert_checkout(r)


# Custom amount checkout
def test_checkout_custom_amount_20_usd(auth):
    r = auth.post(f"{BASE_URL}/api/payments/checkout",
                  json={"package_id": "custom", "origin_url": ORIGIN, "usd_amount": 20})
    _assert_checkout(r)


def test_checkout_custom_amount_below_min_rejected(auth):
    r = auth.post(f"{BASE_URL}/api/payments/checkout",
                  json={"package_id": "custom", "origin_url": ORIGIN, "usd_amount": 0})
    assert r.status_code in (400, 422), r.text


# Premium (one-time payment mode)
def test_checkout_premium_monthly(auth):
    r = auth.post(f"{BASE_URL}/api/payments/checkout", json={"package_id": "premium_monthly", "origin_url": ORIGIN})
    _assert_checkout(r)


# VIP (subscription mode)
def test_checkout_vip_monthly_subscription(auth):
    r = auth.post(f"{BASE_URL}/api/payments/checkout", json={"package_id": "vip_monthly", "origin_url": ORIGIN})
    _assert_checkout(r)


# Unknown package
def test_checkout_unknown_package_rejected(auth):
    r = auth.post(f"{BASE_URL}/api/payments/checkout", json={"package_id": "nonexistent_pkg", "origin_url": ORIGIN})
    assert r.status_code == 400, r.text


# Payment status endpoint returns pending for freshly created session
def test_payment_status_pending_for_new_session(auth):
    r = auth.post(f"{BASE_URL}/api/payments/checkout", json={"package_id": "small_talk", "origin_url": ORIGIN})
    data = _assert_checkout(r)
    sid = data["session_id"]
    s = requests.get(f"{BASE_URL}/api/payments/status/{sid}", timeout=20)
    assert s.status_code == 200, s.text
    body = s.json()
    assert body["session_id"] == sid
    assert body["payment_status"] in ("pending", "paid", "unpaid")  # unpaid is also Stripe's label for new sessions


def test_payment_status_unknown_session_404():
    r = requests.get(f"{BASE_URL}/api/payments/status/cs_test_doesnotexist", timeout=20)
    assert r.status_code == 404


# Unauthenticated checkout rejected
def test_checkout_requires_auth():
    r = requests.post(f"{BASE_URL}/api/payments/checkout",
                      json={"package_id": "small_talk", "origin_url": ORIGIN}, timeout=20)
    assert r.status_code in (401, 403), r.text
