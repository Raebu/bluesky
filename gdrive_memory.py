"""Durable Google Sheets memory for the Bluesky agent.

Credentials: GOOGLE_SERVICE_ACCOUNT_JSON (entire service-account JSON as one GitHub secret)
Sheet: BSKY_MEMORY_SHEET_ID
"""
from __future__ import annotations
import json, os
from datetime import datetime, timezone

SHEET_ID=os.getenv("BSKY_MEMORY_SHEET_ID","")

def _client():
    raw=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw or not SHEET_ID:return None
    import gspread
    from google.oauth2.service_account import Credentials
    info=json.loads(raw)
    creds=Credentials.from_service_account_info(info,scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return gspread.authorize(creds).open_by_key(SHEET_ID)

def enabled(): return bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") and SHEET_ID)
def now(): return datetime.now(timezone.utc).isoformat()
def append(tab,row):
    try:
        sh=_client()
        if sh: sh.worksheet(tab).append_row(["" if x is None else str(x) for x in row],value_input_option="RAW")
    except Exception as e: print("GDRIVE append failed",tab,e)
def rows(tab):
    try:
        sh=_client(); return sh.worksheet(tab).get_all_records() if sh else []
    except Exception as e: print("GDRIVE read failed",tab,e); return []
def do_not_engage():
    blocked=set()
    for r in rows("Do Not Engage"):
        if str(r.get("Active","")).lower() not in {"false","0","no","inactive"}:
            v=str(r.get("DID/Handle/Domain","")).strip().lower()
            if v:blocked.add(v)
    return blocked
def recent_posts(limit=100): return [str(r.get("Text","")) for r in rows("Posts")[-limit:] if r.get("Text")]
def verified_knowledge(): return [str(r.get("Fact","")) for r in rows("Verified Knowledge") if str(r.get("Status","")).upper()=="VERIFIED"]
def conversation_for(did,limit=8):
    rs=[r for r in rows("Conversations") if str(r.get("DID",""))==did]
    return rs[-limit:]
def log_post(uri,text,topic,hashtags,media,thread,status="published"): append("Posts",[now(),uri,text,topic," ".join(hashtags),media,json.dumps(thread),status])
def log_interaction(action,did,handle,uri,post_text,agent_text="",reason=""): append("Interactions",[now(),action,did,handle,uri,post_text,agent_text,reason])
def log_conversation(did,handle,direction,uri,their_text,martin_reply,context=""): append("Conversations",[now(),did,handle,direction,uri,their_text,martin_reply,context])
def log_content(text,topic,fingerprint,outcome,reason=""): append("Content Memory",[now(),text,topic,fingerprint,outcome,reason])
def log_run(started,mode,dry,candidates,replies,likes,follows,posts,notes=""): append("Agent Runs",[started,now(),mode,dry,candidates,replies,likes,follows,posts,notes])
