"""Durable Google Sheets memory with shared Social OS schema."""
from __future__ import annotations
import json,os,time
from datetime import datetime,timezone
SHEET_ID=os.getenv("SOCIAL_MEMORY_SHEET_ID") or os.getenv("BSKY_MEMORY_SHEET_ID","");_BOOK=None;_CACHE={};CACHE_SECONDS=int(os.getenv("GDRIVE_CACHE_SECONDS","300"))
TABS={"Social Entity Graph":["At","Entity ID","Platform","Handle","Type","Relation","Evidence"],"Social Knowledge":["Claim","Status","Source","Verified At","Expires At","Confidence"],"Social Outcomes":["At","Platform","Account","Content ID","Outcome","Value"],"Social Research Queue":["At","Question","Reason","Source","Priority","Status","Findings","Evidence"],"Social Content Lineage":["At","Content ID","Idea","Evidence","Conversations","Platform","Text"],"Social Decision Replay":["At","Decision ID","Platform","Action","Input JSON","Reason","Confidence","Policy","Voice","Model","Schema"],"Social Human Corrections":["At","Entity","Field","Correct Value","Reason","Active"],"Social Controls":["Control","Value","Updated","Notes"],"Social Usage":["At","OpenAI Calls","LinkedIn Calls","Sheets Calls","Estimated Cost","Notes"]}
def _client():
 global _BOOK
 if _BOOK is not None:return _BOOK
 raw=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
 if not raw or not SHEET_ID:return None
 import gspread
 from google.oauth2.service_account import Credentials
 creds=Credentials.from_service_account_info(json.loads(raw),scopes=["https://www.googleapis.com/auth/spreadsheets"]);_BOOK=gspread.authorize(creds).open_by_key(SHEET_ID);return _BOOK
def enabled():return bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") and SHEET_ID)
def now():return datetime.now(timezone.utc).isoformat()
def ensure_tabs():
 sh=_client()
 if not sh:return
 existing={w.title:w for w in sh.worksheets()}
 for name,headers in TABS.items():
  if name not in existing:
   w=sh.add_worksheet(title=name,rows=1000,cols=max(12,len(headers)));w.append_row(headers,value_input_option="RAW")
  else:
   w=existing[name];cur=w.row_values(1)
   if not cur:w.append_row(headers,value_input_option="RAW")
   elif not all(h in cur for h in headers):w.update(range_name="A1",values=[cur+[h for h in headers if h not in cur]])
def append(tab,row):
 try:
  ensure_tabs();sh=_client()
  if sh:sh.worksheet(tab).append_row(["" if x is None else str(x) for x in row],value_input_option="RAW");_CACHE.pop(tab,None)
 except Exception as e:print("GDRIVE append failed",tab,e)
def rows(tab,refresh=False):
 try:
  ts,data=_CACHE.get(tab,(0,None))
  if not refresh and data is not None and time.monotonic()-ts<CACHE_SECONDS:return data
  ensure_tabs();sh=_client();data=sh.worksheet(tab).get_all_records() if sh else [];_CACHE[tab]=(time.monotonic(),data);return data
 except Exception as e:print("GDRIVE read failed",tab,e);return _CACHE.get(tab,(0,[]))[1] or []
def preload(*tabs):
 for tab in tabs:rows(tab)
def control(name,default=True):
 for r in rows("Social Controls"):
  if str(r.get("Control","")).strip().lower()==name.lower():return str(r.get("Value","")).lower() in {"true","1","yes","on","enabled"}
 return default
def do_not_engage():
 blocked=set()
 for r in rows("Do Not Engage"):
  if str(r.get("Active","")).lower() not in {"false","0","no","inactive"}:
   v=str(r.get("DID/Handle/Domain","")).strip().lower()
   if v:blocked.add(v)
 return blocked
def recent_posts(limit=100):return [str(r.get("Text","")) for r in rows("Posts")[-limit:] if r.get("Text")]
def recent_lineage_texts(limit=300):return [str(r.get("Text","")) for r in rows("Social Content Lineage")[-limit:] if r.get("Text")]
def verified_knowledge():return [str(r.get("Fact","")) for r in rows("Verified Knowledge") if str(r.get("Status","")).upper()=="VERIFIED"]
def conversation_for(did,limit=8):return [r for r in rows("Conversations") if str(r.get("DID",""))==did][-limit:]
def log_post(uri,text,topic,hashtags,media,thread,status="published"):append("Posts",[now(),uri,text,topic," ".join(hashtags),media,json.dumps(thread),status]);append("Social Content Lineage",[now(),uri,topic,"","","Bluesky",text])
def log_interaction(action,did,handle,uri,post_text,agent_text="",reason=""):append("Interactions",[now(),action,did,handle,uri,post_text,agent_text,reason]);append("Social Entity Graph",[now(),did,"Bluesky",handle,"person/account",action,reason])
def log_conversation(did,handle,direction,uri,their_text,martin_reply,context=""):append("Conversations",[now(),did,handle,direction,uri,their_text,martin_reply,context])
def log_content(text,topic,fingerprint,outcome,reason=""):append("Content Memory",[now(),text,topic,fingerprint,outcome,reason]);append("Social Content Lineage",[now(),fingerprint,topic,reason,"","Bluesky",text])
def log_run(started,mode,dry,candidates,replies,likes,follows,posts,notes=""):append("Agent Runs",[started,now(),mode,dry,candidates,replies,likes,follows,posts,notes]);append("Social Usage",[now(),"", "", "", "",f"Bluesky candidates={candidates}; replies={replies}; likes={likes}; follows={follows}"])
def replay(action,input_json,reason,confidence=.7):append("Social Decision Replay",[now(),"","Bluesky",action,json.dumps(input_json,default=str),reason,confidence,"growth-v3","martin-canonical","","2.2"])
def research_hold(question,reason,source=""):append("Social Research Queue",[now(),question,reason,source,"NORMAL","QUEUED","",""])
def corrections():return [r for r in rows("Social Human Corrections") if str(r.get("Active","")).lower() not in {"false","0","no","inactive"}]
