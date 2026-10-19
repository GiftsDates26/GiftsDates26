"""Backend tests for VIP 'Show VIP on my main profile' visibility rule.

Rule: when a member's vip.show_on_main is False, NON-VIP viewers see is_vip=False
on the main feed and profile view, and the member is excluded from vip_only
search for non-VIP viewers. VIP viewers see is_vip=True and still find them.
"""
import os
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

VIP_VIEWER = ("giftsdates@gmail.com", "Admin@12345")
PLAIN_VIEWER = ("plain_viewer@example.com", "Test@12345")
LENA = ("ll_tester@example.com", "Test@12345")
LENA_ID = "0be0c2a0-cbb3-480c-b785-533dff4fb64e"


def _login(email, pwd):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd}, timeout=15)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def tokens():
    return {
        "vip": _login(*VIP_VIEWER),
        "plain": _login(*PLAIN_VIEWER),
        "lena": _login(*LENA),
    }


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _find_lena(resp):
    items = resp.get("items", resp) if isinstance(resp, dict) else resp
    for it in items:
        if it.get("id") == LENA_ID or it.get("name") == "Lena Tester":
            return it
    return None


# --- With show_on_main = False (initial state) ---

def test_vip_search_visible_to_vip_viewer(tokens):
    r = requests.get(f"{BASE_URL}/api/profiles", params={"vip_only": "true", "q": "Lena"}, headers=_h(tokens["vip"]), timeout=15)
    assert r.status_code == 200
    lena = _find_lena(r.json())
    assert lena is not None, "VIP viewer should find Lena in vip_only search"
    assert lena.get("is_vip") is True


def test_vip_search_hidden_from_nonvip(tokens):
    r = requests.get(f"{BASE_URL}/api/profiles", params={"vip_only": "true", "q": "Lena"}, headers=_h(tokens["plain"]), timeout=15)
    assert r.status_code == 200
    assert _find_lena(r.json()) is None, "Non-VIP viewer must NOT see Lena in vip_only search"


def test_main_feed_vip_badge_for_vip_viewer(tokens):
    r = requests.get(f"{BASE_URL}/api/profiles", params={"q": "Lena"}, headers=_h(tokens["vip"]), timeout=15)
    assert r.status_code == 200
    lena = _find_lena(r.json())
    assert lena is not None
    assert lena.get("is_vip") is True


def test_main_feed_vip_hidden_for_nonvip(tokens):
    r = requests.get(f"{BASE_URL}/api/profiles", params={"q": "Lena"}, headers=_h(tokens["plain"]), timeout=15)
    assert r.status_code == 200
    lena = _find_lena(r.json())
    assert lena is not None, "Lena still visible on main feed, just without VIP badge"
    assert lena.get("is_vip") is False, "Non-VIP viewer must not see VIP badge"
    assert lena.get("is_premium") is True, "Non-VIP viewer must see hidden VIP member as Premium"


def test_profile_view_vip_true_for_vip_viewer(tokens):
    r = requests.get(f"{BASE_URL}/api/profiles/{LENA_ID}", headers=_h(tokens["vip"]), timeout=15)
    assert r.status_code == 200
    assert r.json().get("is_vip") is True


def test_profile_view_vip_false_for_nonvip(tokens):
    r = requests.get(f"{BASE_URL}/api/profiles/{LENA_ID}", headers=_h(tokens["plain"]), timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert body.get("is_vip") is False
    assert body.get("is_premium") is True, "Non-VIP viewer must see hidden VIP member as Premium on profile view"


def test_profile_view_vip_true_for_owner(tokens):
    r = requests.get(f"{BASE_URL}/api/profiles/{LENA_ID}", headers=_h(tokens["lena"]), timeout=15)
    assert r.status_code == 200
    assert r.json().get("is_vip") is True


# --- Toggle to True then back ---

def test_toggle_show_on_main_true_makes_her_discoverable(tokens):
    # Flip to true via Lena's own PUT /api/vip/profile
    r = requests.put(f"{BASE_URL}/api/vip/profile", json={"show_on_main": True}, headers=_h(tokens["lena"]), timeout=15)
    assert r.status_code == 200, r.text
    try:
        r2 = requests.get(f"{BASE_URL}/api/profiles", params={"vip_only": "true", "q": "Lena"}, headers=_h(tokens["plain"]), timeout=15)
        assert r2.status_code == 200
        lena = _find_lena(r2.json())
        assert lena is not None, "After flip, non-VIP viewer should find Lena in vip search"
        assert lena.get("is_vip") is True
        # Main feed also shows VIP badge now
        r3 = requests.get(f"{BASE_URL}/api/profiles", params={"q": "Lena"}, headers=_h(tokens["plain"]), timeout=15)
        lena2 = _find_lena(r3.json())
        assert lena2 and lena2.get("is_vip") is True
        # Profile view
        r4 = requests.get(f"{BASE_URL}/api/profiles/{LENA_ID}", headers=_h(tokens["plain"]), timeout=15)
        assert r4.json().get("is_vip") is True
    finally:
        # Restore to False for subsequent testing
        requests.put(f"{BASE_URL}/api/vip/profile", json={"show_on_main": False}, headers=_h(tokens["lena"]), timeout=15)


def test_restored_to_false(tokens):
    r = requests.get(f"{BASE_URL}/api/profiles/{LENA_ID}", headers=_h(tokens["plain"]), timeout=15)
    assert r.status_code == 200
    assert r.json().get("is_vip") is False, "Must be restored to show_on_main=False at end of suite"
