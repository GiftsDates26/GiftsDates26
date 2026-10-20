"""Iteration 33: stale date_card action_for cleanup + location-reject decline_reason + data.chosen."""
import requests
from test_date_chat_cards import (  # noqa: F401
    API,
    LOC,
    _cards,
    _cid,
    _create_invite,
    _day,
    admin,
    db,
    user,
)
from test_date_chat_cards import TestBookingFlow as _BF
from test_date_chat_cards import TestVipFlow as _VF


def _cancelled(h, did):
    items = requests.get(f"{API}/invites/cancelled", headers=h, timeout=20).json()["items"]
    return next((x for x in items if x["id"] == did), None)


def _to_location(admin, user):  # noqa: F811
    did = _create_invite(admin, user)
    assert requests.post(f"{API}/invites/{did}/choose", headers=user[0], json={"idea_id": "opt3"}, timeout=20).status_code == 200
    assert requests.post(f"{API}/invites/{did}/location", headers=admin[0], json=LOC, timeout=30).status_code == 200
    return did


# (1) taxi request via _log_status clears action_for on location card
class TestTaxiClearsCards:
    def test_taxi_request_clears(self, admin, user, db):  # noqa: F811
        did = _to_location(admin, user)
        cid = _cid(db, admin[1], user[1])
        assert _cards(user[0], cid, did)[-1]["action_for"] == user[1]
        r = requests.post(f"{API}/invites/{did}/taxi/request", headers=user[0], json={"amount": 30}, timeout=20)
        assert r.status_code == 200, r.text
        assert all(c["action_for"] is None for c in _cards(user[0], cid, did))
        requests.post(f"{API}/invites/{did}/cancel", headers=admin[0], timeout=20)


# (4) data.chosen set on original invite card
class TestChosen:
    def test_invite_chosen(self, admin, user, db):  # noqa: F811
        did = _create_invite(admin, user)
        requests.post(f"{API}/invites/{did}/choose", headers=user[0], json={"idea_id": "opt2"}, timeout=20)
        c = _cards(user[0], _cid(db, admin[1], user[1]), did)
        assert c[0]["event"] == "invite" and c[0]["data"]["chosen"] == "TEST_Walk"
        requests.post(f"{API}/invites/{did}/cancel", headers=admin[0], timeout=20)

    def test_booking_chosen(self, admin, user, db):  # noqa: F811
        bid = _BF()._book(admin, user)
        requests.post(f"{API}/dates/respond/{bid}", headers=user[0], params={"accept": "true", "selected_activity": "TEST_C"}, timeout=20)
        c = _cards(user[0], _cid(db, admin[1], user[1]), bid)
        assert c[0]["data"]["chosen"] == "TEST_C"
        requests.post(f"{API}/dates/cancel/{bid}", headers=admin[0], timeout=20)


# (2) cancel booked date / VIP pending clears action_for
class TestCancelClears:
    def test_dates_cancel_clears(self, admin, user, db):  # noqa: F811
        bid = _BF()._book(admin, user)
        cid = _cid(db, admin[1], user[1])
        assert _cards(user[0], cid, bid)[0]["action_for"] == user[1]
        r = requests.post(f"{API}/dates/cancel/{bid}", headers=admin[0], timeout=20)
        assert r.status_code == 200, r.text
        assert all(c["action_for"] is None for c in _cards(user[0], cid, bid))
        # stale approve now fails anyway
        r = requests.post(f"{API}/dates/respond/{bid}", headers=user[0], params={"accept": "true", "selected_activity": "TEST_A"}, timeout=20)
        assert r.status_code == 400

    def test_vip_requester_cancel_clears(self, admin, user, db):  # noqa: F811
        bid = _VF()._book(user, admin, db)
        cid = _cid(db, admin[1], user[1])
        assert _cards(admin[0], cid, bid)[0]["action_for"] == admin[1]
        r = requests.post(f"{API}/vip/schedule/bookings/{bid}/cancel", headers=user[0], timeout=20)
        assert r.status_code == 200, r.text
        assert all(c["action_for"] is None for c in _cards(admin[0], cid, bid))

    def test_failed_cancel_should_not_clear(self, admin, user, db):  # noqa: F811
        """Code review: _close_date_cards runs before validation -> unauthorized/invalid cancel clears buttons."""
        bid = _VF()._book(user, admin, db)
        cid = _cid(db, admin[1], user[1])
        # simulate an invalid cancel: booking in a non-cancellable status
        db.vip_sched.update_one({"id": bid}, {"$set": {"status": "declined_tmp"}})
        r = requests.post(f"{API}/vip/schedule/bookings/{bid}/cancel", headers=user[0], timeout=20)
        db.vip_sched.update_one({"id": bid}, {"$set": {"status": "pending"}})
        assert r.status_code == 400
        still = _cards(admin[0], cid, bid)[0]["action_for"]
        requests.post(f"{API}/vip/schedule/bookings/{bid}/decline", headers=admin[0], timeout=20)
        assert still == admin[1], "action_for cleared although cancel was rejected (400)"


# (3) location reject persists decline_reason/declined_by
class TestLocationReject:
    def test_reject_with_reason(self, admin, user, db):  # noqa: F811
        did = _to_location(admin, user)
        r = requests.post(f"{API}/invites/{did}/location/reject", headers=user[0], params={"reason": "TEST_too far away"}, timeout=20)
        assert r.status_code == 200, r.text
        doc = db.dates.find_one({"id": did})
        assert doc["decline_reason"] == "TEST_too far away" and doc["declined_by"] == user[1]
        it = _cancelled(admin[0], did)
        assert it and it["decline_reason"] == "TEST_too far away" and it["declined_by_me"] is False
        assert _cancelled(user[0], did)["declined_by_me"] is True
        c = _cards(admin[0], _cid(db, admin[1], user[1]), did)
        assert c[-1]["data"]["reason"] == "TEST_too far away"

    def test_reject_default_reason(self, admin, user, db):  # noqa: F811
        did = _to_location(admin, user)
        r = requests.post(f"{API}/invites/{did}/location/reject", headers=user[0], timeout=20)
        assert r.status_code == 200, r.text
        it = _cancelled(admin[0], did)
        assert it and it["decline_reason"] == "Meeting place rejected"
