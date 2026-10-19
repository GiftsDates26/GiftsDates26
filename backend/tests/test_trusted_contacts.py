"""Tests for Trusted Contacts and SOS public token/contacts_alerted feature."""
import os
import time
import pytest
import requests
from pymongo import MongoClient
from dotenv import dotenv_values

_fe = dotenv_values("/app/frontend/.env")
_be = dotenv_values("/app/backend/.env")
BASE_URL = (_fe.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
MONGO_URL = _be.get("MONGO_URL") or "mongodb://localhost:27017"
DB_NAME = _be.get("DB_NAME") or "test_database"
assert BASE_URL, "REACT_APP_BACKEND_URL not configured"

USER_EMAIL = "ll_tester@example.com"
USER_PASS = "Test@12345"
ADMIN_EMAIL = "giftsdates@gmail.com"
ADMIN_PASS = "Admin@12345"


def _login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def user_headers():
    return {"Authorization": f"Bearer {_login(USER_EMAIL, USER_PASS)}"}


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login(ADMIN_EMAIL, ADMIN_PASS)}"}


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    db = c[DB_NAME]
    yield db
    c.close()


# ---------- Trusted Contacts CRUD ----------

class TestTrustedContactsCRUD:
    def test_get_contacts(self, user_headers):
        r = requests.get(f"{BASE_URL}/api/me/trusted-contacts", headers=user_headers, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert "contacts" in d and "max" in d
        assert d["max"] == 3

    def test_put_valid_and_normalize_phone(self, user_headers):
        payload = {"contacts": [
            {"name": "Mom", "email": "delivered@resend.dev", "phone": "+1 (555) 123-4567"},
            {"name": "Sis", "phone": "555-888-9999"},
        ]}
        r = requests.put(f"{BASE_URL}/api/me/trusted-contacts", json=payload, headers=user_headers, timeout=10)
        assert r.status_code == 200, r.text
        contacts = r.json()["contacts"]
        assert len(contacts) == 2
        assert contacts[0]["phone"] == "+15551234567"
        assert contacts[0]["email"] == "delivered@resend.dev"
        assert contacts[1]["phone"] == "5558889999"
        assert contacts[1]["email"] is None

        # Verify persisted via GET
        g = requests.get(f"{BASE_URL}/api/me/trusted-contacts", headers=user_headers, timeout=10)
        assert g.status_code == 200
        assert len(g.json()["contacts"]) == 2

    def test_reject_more_than_three(self, user_headers):
        payload = {"contacts": [{"name": f"c{i}", "email": "delivered@resend.dev"} for i in range(4)]}
        r = requests.put(f"{BASE_URL}/api/me/trusted-contacts", json=payload, headers=user_headers, timeout=10)
        assert r.status_code == 400

    def test_reject_missing_name(self, user_headers):
        payload = {"contacts": [{"name": "   ", "email": "delivered@resend.dev"}]}
        r = requests.put(f"{BASE_URL}/api/me/trusted-contacts", json=payload, headers=user_headers, timeout=10)
        assert r.status_code == 400

    def test_reject_no_email_no_phone(self, user_headers):
        payload = {"contacts": [{"name": "No Contact"}]}
        r = requests.put(f"{BASE_URL}/api/me/trusted-contacts", json=payload, headers=user_headers, timeout=10)
        assert r.status_code == 400

    def test_reject_bad_phone(self, user_headers):
        payload = {"contacts": [{"name": "BadPhone", "phone": "123"}]}
        r = requests.put(f"{BASE_URL}/api/me/trusted-contacts", json=payload, headers=user_headers, timeout=10)
        assert r.status_code == 400

    def test_restore_single_contact(self, user_headers):
        """Leave user with 1 contact (Mom) so UI tests have the expected seed."""
        payload = {"contacts": [{"name": "Mom", "email": "delivered@resend.dev", "phone": "+15551234567"}]}
        r = requests.put(f"{BASE_URL}/api/me/trusted-contacts", json=payload, headers=user_headers, timeout=10)
        assert r.status_code == 200

    def test_auth_required(self):
        r = requests.get(f"{BASE_URL}/api/me/trusted-contacts", timeout=10)
        assert r.status_code in (401, 403)


# ---------- SOS flow ----------

class TestSosWithTrustedContacts:
    def test_sos_alert_and_public_token(self, user_headers, admin_headers, mongo):
        # Ensure we have a bookable date for ll-test-1; set scheduled_at to now
        booking = mongo.date_bookings.find_one({"id": "ll-test-1"})
        if not booking:
            pytest.skip("ll-test-1 booking seed not present")

        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        mongo.date_bookings.update_one({"id": "ll-test-1"}, {"$set": {"scheduled_at": now_iso, "status": "confirmed"}})

        # Delete prior sos alerts for user to clear 5-min rate limit
        u = mongo.users.find_one({"email": USER_EMAIL})
        assert u, "ll_tester user missing"
        mongo.sos_alerts.delete_many({"user_id": u["id"]})

        # Trigger SOS
        r = requests.post(
            f"{BASE_URL}/api/sos/booking/ll-test-1",
            json={"lat": 40.7128, "lng": -74.0060, "message": "test SOS"},
            headers=user_headers, timeout=20,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert d["contacts_alerted"] >= 1, f"Expected contacts alerted, got {d}"

        sos_id = d["id"]

        # public_token should exist in DB
        rec = mongo.sos_alerts.find_one({"id": sos_id})
        assert rec and rec.get("public_token"), "public_token missing"
        token = rec["public_token"]

        # Second SOS within 5min -> contacts_alerted == 0
        r2 = requests.post(
            f"{BASE_URL}/api/sos/booking/ll-test-1",
            json={"lat": 40.7128, "lng": -74.0060},
            headers=user_headers, timeout=20,
        )
        assert r2.status_code == 200
        assert r2.json()["contacts_alerted"] == 0, "Rate limit should prevent 2nd alert within 5min"

        # Admin SOS listing must NOT expose public_token
        a = requests.get(f"{BASE_URL}/api/admin/sos", headers=admin_headers, timeout=10)
        assert a.status_code == 200
        for item in a.json():
            assert "public_token" not in item, "public_token leaked in admin listing"

        # Public endpoint works without auth
        p = requests.get(f"{BASE_URL}/api/sos/public/{token}", timeout=10)
        assert p.status_code == 200
        pd = p.json()
        assert pd["name"]
        assert pd["lat"] == 40.7128
        assert pd["lng"] == -74.0060
        assert pd["status"] == "open"

    def test_sos_public_invalid_token(self):
        r = requests.get(f"{BASE_URL}/api/sos/public/not-a-real-token-xyz", timeout=10)
        assert r.status_code == 404
