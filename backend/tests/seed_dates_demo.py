import os,uuid
from datetime import datetime,timezone,timedelta
from pymongo import MongoClient
from dotenv import load_dotenv; load_dotenv("/app/backend/.env")
db=MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
me=db.users.find_one({"email":"testuser@giftsdates.com"})["id"]; ad=db.users.find_one({"email":"giftsdates@gmail.com"})["id"]
now=datetime.now(timezone.utc)
opts=[{"idea_id":"i1","name":"Wine bar"},{"idea_id":"i2","name":"Dinner"},{"idea_id":"i3","name":"Museum"}]
rows=[("INVITATION_SENT",ad,me,3),("INVITATION_SENT",me,ad,4),("DATE_CONFIRMED",ad,me,2),("CANCELLED",me,ad,-1),("COMPLETED",ad,me,-5)]
db.dates.delete_many({"seed":True})
for st,inv,rec,days in rows:
    s=(now+timedelta(days=days)).isoformat()
    db.dates.insert_one({"id":str(uuid.uuid4()),"seed":True,"inviter_id":inv,"recipient_id":rec,"status":st,"options":opts,
      "chosen_idea":opts[0] if st!="INVITATION_SENT" else None,"proposed_start":s,"coins":200,"total_hold":200,
      "location":{"venue":"Bar Raval","city":"Toronto","scheduled_start":s} if st!="INVITATION_SENT" else {},
      "created_at":(now-timedelta(hours=days+10)).isoformat()})
print("ok")
