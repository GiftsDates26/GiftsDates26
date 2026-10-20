"""Seed helper for iteration-32 UI test: creates fresh invite/booking/VIP request admin<->testuser."""
import json, uuid, random, os, requests
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv("/app/backend/.env"); load_dotenv("/app/frontend/.env")
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
def login(e, p):
    t = requests.post(f"{API}/auth/login", json={"email": e, "password": p}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    return h, requests.get(f"{API}/auth/me", headers=h).json()["id"], t
ah, aid, at = login("giftsdates@gmail.com", "Admin@12345")
uh, uid, ut = login("testuser@giftsdates.com", "Test@12345")
db.users.update_one({"id": aid}, {"$set": {"coins": 5000}}); db.users.update_one({"id": uid}, {"$set": {"coins": 5000}})
def day(): return datetime.now(timezone.utc) + timedelta(days=random.randint(200, 900))
def inv():
    d = day().replace(hour=12, minute=0, second=0, microsecond=0)
    r = requests.post(f"{API}/invites", headers=ah, json={"recipient_id": uid, "activity_option_1": "TEST_Coffee", "activity_option_2": "TEST_Walk",
        "activity_option_3": "TEST_Dinner", "scheduled_start": d.isoformat(), "local_day": d.strftime("%Y-%m-%d"), "local_time": "12:00", "coins": 150, "safety_ack": True})
    return r.json()["id"]
inv1, inv2 = inv(), inv()
d = day().replace(hour=14, minute=0, second=0, microsecond=0)
bk = requests.post(f"{API}/dates/book", headers=ah, json={"target_id": uid, "venue": "TEST_Bar", "city": "Paris", "address": "Rue de Rivoli 1", "postal_code": "75001",
    "country": "France", "lat": 48.86, "lng": 2.34, "address_confirmed": True, "scheduled_at": d.isoformat(), "local_day": d.strftime("%Y-%m-%d"), "local_time": "14:00",
    "coins": 200, "activities": ["TEST_A", "TEST_B", "TEST_C"]}).json()["booking_id"]
vd = day().strftime("%Y-%m-%d")
db.vip_avail.insert_one({"id": f"TEST_{uuid.uuid4()}", "vip_id": uid, "date": vd, "start": "09:00", "end": "22:00", "slot_len": 60, "tz": "UTC", "seed": True})
vip = requests.post(f"{API}/vip/schedule/{uid}/book", headers=ah, json={"date": vd, "start": "12:00", "end": "13:00", "length": 1, "tz": "UTC", "place": "other",
    "venue": "TEST_VipSpot", "address": "Rue de Rivoli 1", "city": "Paris", "postal_code": "75001", "country": "France", "lat": 48.86, "lng": 2.34, "address_confirmed": True}).json()
cid = db.conversations.find_one({"users": {"$all": [aid, uid]}})["id"]
cards = {m["ref_id"]: m["id"] for m in db.messages.find({"conversation_id": cid, "type": "date_card", "action_for": {"$ne": None}})}
print(json.dumps({"cid": cid, "inv1": inv1, "inv2": inv2, "bk": bk, "vip": vip.get("booking_id"), "vip_raw": vip,
                  "m_inv1": cards.get(inv1), "m_inv2": cards.get(inv2), "m_bk": cards.get(bk), "m_vip": cards.get(vip.get("booking_id")), "ut": ut, "at": at}))
