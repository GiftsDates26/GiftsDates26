"""Iteration-19 backend regression: cancel-preview math + directions destination.

Covers:
- POST /api/vip/schedule/{vip_id}/book + /confirm + /cancel
  * requester cancels confirmed booking -> 50% refund / 25% comp / 25% fee
  * VIP cancels confirmed booking -> 100% refund to requester (requires fresh booking)
- Confirmed booking 59cd396e... exposes location.lat/lng for directions link
"""
import os, time, uuid, requests, pytest
from datetime import datetime, timedelta, timezone

def _base():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        v = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    assert v, "REACT_APP_BACKEND_URL not set"
    return v.rstrip("/")

BASE = _base()
ADMIN = {"email": "giftsdates@gmail.com", "password": "Admin@GD24!"}
VIP = {"email": "testuser@giftsdates.com", "password": "Test@12345"}
VIP_ID = "b486a9ec-21a5-46f2-ac7b-4bd42fcb91e6"
TARGET_BOOKING = "59cd396e-4b32-43b1-87fa-6ef7f11cebdd"


def _login(cred):
    r = requests.post(f"{BASE}/api/auth/login", json=cred, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_tok():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def vip_tok():
    return _login(VIP)


def _hdr(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


# --- helpers to find a free VIP slot a few days ahead -------------------------
def _next_free_slot(admin_tok, min_hours_from_now=2):
    """Walk /api/vip/{vip_id}/schedule and pick a free whole-hour slot in the future."""
    r = requests.get(f"{BASE}/api/vip/schedule/{VIP_ID}/slots", headers=_hdr(admin_tok), timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    now = datetime.now(timezone.utc)
    for day in data.get("days", []):
        for s in day.get("slots", []):
            if s.get("state") != "available":
                continue
            try:
                dt = datetime.fromisoformat(f"{day['date']}T{s['start']}:00+00:00")
            except Exception:
                continue
            if dt > now + timedelta(hours=min_hours_from_now):
                return day["date"], s["start"], s["end"]
    pytest.skip("No free VIP slot available for test")


# --- 1. Cancel-split math (requester) ----------------------------------------
def test_requester_cancel_split_is_50_25_25(admin_tok, vip_tok):
    date, start, end = _next_free_slot(admin_tok)
    # book as admin
    r = requests.post(f"{BASE}/api/vip/schedule/{VIP_ID}/book",
                      headers=_hdr(admin_tok),
                      json={"date": date, "start": start, "end": end, "length": 1, "place": "own"},
                      timeout=30)
    assert r.status_code == 200, r.text
    bid = r.json()["booking_id"]
    # fetch via mine to get coins
    mine = requests.get(f"{BASE}/api/vip/schedule/bookings/mine", headers=_hdr(admin_tok)).json()
    allb = sum([v for v in mine.values() if isinstance(v, list)], [])
    bk = next(b for b in allb if b["id"] == bid)
    coins = int(bk["coins"])

    # VIP confirms
    cr = requests.post(f"{BASE}/api/vip/schedule/bookings/{bid}/confirm", headers=_hdr(vip_tok), timeout=30)
    assert cr.status_code == 200, cr.text

    # Admin cancels (requester) -> 50/25/25
    me0 = requests.get(f"{BASE}/api/auth/me", headers=_hdr(admin_tok)).json()
    bal0 = int(me0.get("coins") or 0)

    xr = requests.post(f"{BASE}/api/vip/schedule/bookings/{bid}/cancel", headers=_hdr(admin_tok), timeout=30)
    assert xr.status_code == 200, xr.text
    body = xr.json()
    exp_refund = round(coins * 0.5)
    exp_comp = round(coins * 0.25)
    exp_fee = coins - exp_refund - exp_comp
    assert body["refunded"] == exp_refund, body
    assert body["compensation"] == exp_comp, body
    assert body["platform_fee"] == exp_fee, body

    me1 = requests.get(f"{BASE}/api/auth/me", headers=_hdr(admin_tok)).json()
    assert int(me1["coins"]) - bal0 == exp_refund, (bal0, me1["coins"])


# --- 2. VIP cancel -> full refund --------------------------------------------
def test_vip_cancel_full_refund(admin_tok, vip_tok):
    date, start, end = _next_free_slot(admin_tok)
    r = requests.post(f"{BASE}/api/vip/schedule/{VIP_ID}/book",
                      headers=_hdr(admin_tok),
                      json={"date": date, "start": start, "end": end, "length": 1, "place": "own"},
                      timeout=30)
    assert r.status_code == 200, r.text
    bid = r.json()["booking_id"]
    mine = requests.get(f"{BASE}/api/vip/schedule/bookings/mine", headers=_hdr(admin_tok)).json()
    allb = sum([v for v in mine.values() if isinstance(v, list)], [])
    bk = next(b for b in allb if b["id"] == bid)
    coins = int(bk["coins"])
    requests.post(f"{BASE}/api/vip/schedule/bookings/{bid}/confirm", headers=_hdr(vip_tok), timeout=30)

    me0 = requests.get(f"{BASE}/api/auth/me", headers=_hdr(admin_tok)).json()
    bal0 = int(me0["coins"])

    xr = requests.post(f"{BASE}/api/vip/schedule/bookings/{bid}/cancel", headers=_hdr(vip_tok), timeout=30)
    assert xr.status_code == 200, xr.text
    body = xr.json()
    assert body["refunded"] == coins, body
    assert body["compensation"] == 0
    assert body["platform_fee"] == 0

    me1 = requests.get(f"{BASE}/api/auth/me", headers=_hdr(admin_tok)).json()
    assert int(me1["coins"]) - bal0 == coins


# --- 3. Target booking has location for directions ---------------------------
def test_target_booking_has_location(admin_tok):
    r = requests.get(f"{BASE}/api/vip/schedule/bookings/mine", headers=_hdr(admin_tok), timeout=30)
    assert r.status_code == 200
    data = r.json()
    # endpoint returns dict with request lists
    all_bookings = []
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list):
                all_bookings.extend(v)
    else:
        all_bookings = data
    tgt = next((b for b in all_bookings if b.get("id") == TARGET_BOOKING), None)
    assert tgt is not None, "Target booking 59cd396e... not found in admin's My Requests"
    assert tgt["status"] == "confirmed", tgt["status"]
    loc = tgt.get("location") or {}
    assert loc.get("address"), f"No address: {loc}"
    assert loc.get("lat") is not None and loc.get("lng") is not None, loc
