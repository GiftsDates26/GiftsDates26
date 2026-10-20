"""Seed for iteration-33 UI: invite with LOCATION_PROPOSED (location card) + invite with chosen option."""
import json, random, os, requests
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
def inv():
    d = (datetime.now(timezone.utc) + timedelta(days=random.randint(200, 900))).replace(hour=12, minute=0, second=0, microsecond=0)
    return requests.post(f"{API}/invites", headers=ah, json={"recipient_id": uid, "activity_option_1": "TEST_Coffee", "activity_option_2": "TEST_Walk",
        "activity_option_3": "TEST_Dinner", "scheduled_start": d.isoformat(), "local_day": d.strftime("%Y-%m-%d"), "local_time": "12:00", "coins": 150, "safety_ack": True}).json()["id"]
LOC = {"venue": "TEST_UICafe", "address": "Rue de Rivoli 1", "city": "Paris", "postal_code": "75001", "country": "France", "lat": 48.86, "lng": 2.34, "address_confirmed": True}
i1 = inv()
requests.post(f"{API}/invites/{i1}/choose", headers=uh, json={"idea_id": "opt2"})
requests.post(f"{API}/invites/{i1}/location", headers=ah, json=LOC)
cid = db.conversations.find_one({"users": {"$all": [aid, uid]}})["id"]
cards = {m["event"]: m["id"] for m in db.messages.find({"ref_id": i1, "type": "date_card"})}
print(json.dumps({"cid": cid, "inv": i1, "m_invite": cards.get("invite"), "m_location": cards.get("location"), "ut": ut, "at": at}))
