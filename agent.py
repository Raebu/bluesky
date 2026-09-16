"""Autonomous Bluesky professional presence with durable Google Sheets memory."""
from __future__ import annotations
import json,os,random,re
from datetime import datetime,timezone
from pathlib import Path
from atproto import Client,models
from voice import MARTIN_VOICE
from intelligence import relationship_context,remember_relationship
import gdrive_memory as gm
HANDLE=os.getenv("BSKY_HANDLE","mraeburn.link");PASSWORD=os.environ["BSKY_APP_PASSWORD"];DRY_RUN=os.getenv("DRY_RUN","true").lower()=="true";STATE_FILE=Path(os.getenv("STATE_FILE","state.json"));TOPICS=[x.strip() for x in os.getenv("TOPICS","artificial intelligence,AI automation,enterprise software,technology leadership,entrepreneurship").split(",") if x.strip()];MAX_REPLIES=int(os.getenv("MAX_REPLIES_PER_RUN","2"));MAX_FOLLOWS=int(os.getenv("MAX_FOLLOWS_PER_RUN","2"));MAX_LIKES=int(os.getenv("MAX_LIKES_PER_RUN","3"));MAX_INBOUND=int(os.getenv("MAX_INBOUND_REPLIES_PER_RUN","2"))
def state_load():
 try:return json.loads(STATE_FILE.read_text())
 except:return {"seen":[],"followed":[],"liked":[],"replied":[],"inbound_seen":[],"relationships":{}}
def state_save(s):STATE_FILE.parent.mkdir(parents=True,exist_ok=True);STATE_FILE.write_text(json.dumps(s,indent=2,sort_keys=True)+"\n")
def ai(prompt,max_chars=290):
 from openai import OpenAI
 r=OpenAI(api_key=os.environ["OPENAI_API_KEY"]).responses.create(model=os.getenv("OPENAI_MODEL","gpt-5-mini"),input=MARTIN_VOICE+"\nTASK\n"+prompt);t=r.output_text.strip().replace("\r","");return None if t.upper().startswith("NO_REPLY") else t[:max_chars].rstrip()
def ai_json(prompt):
 raw=ai(prompt,1200)
 if not raw:return None
 try:return json.loads(re.sub(r"^```(?:json)?\s*|\s*```$","",raw.strip(),flags=re.I))
 except:return None
def safe_text(t):return re.sub(r"\s+"," ",t or "").strip()[:600]
def blocked(block,p):
 vals={p.author.did.lower(),p.author.handle.lower(),"@"+p.author.handle.lower()};return bool(vals&block)
def sheet_history(did):
 if not gm.enabled():return ""
 rs=gm.conversation_for(did);return "\n".join(f"- {r.get('Direction')}: {r.get('Their Text','')} => {r.get('Martin Reply','')}" for r in rs[-6:])
def decision(a,t,topic):return ai_json(f"Topic:{topic}\nAuthor:@{a.handle}\nPost:{t}\nReturn JSON only {{\"like\":false,\"follow\":false,\"reason\":\"\"}}. Conservative professional reputation filter. Like only substantive relevant credible content; follow only worthwhile ongoing professional sources/peers. Reject spam, aggregators, promotion, bait, rage and partisan campaigning. Uncertain=false.")
def process_inbound(c,me,s,block):
 done=set(s.get("inbound_seen",[]));count=0
 try:notes=c.app.bsky.notification.list_notifications({"limit":30}).notifications
 except Exception as e:return print("notifications failed",e)
 for n in notes:
  if count>=MAX_INBOUND:break
  if n.uri in done or n.author.did==me.did or n.reason not in {"reply","mention"}:continue
  if {n.author.did.lower(),n.author.handle.lower(),"@"+n.author.handle.lower()}&block:done.add(n.uri);continue
  done.add(n.uri);txt=safe_text(getattr(n.record,"text",""));history=(sheet_history(n.author.did) or relationship_context(s,n.author.did))
  reply=ai(f"Inbound {n.reason} from @{n.author.handle}: {txt}\nRemembered history:\n{history or '- none'}\nReply only if substantive. Ignore spam, generic praise, hostility, bait and political persuasion. NO_REPLY otherwise. Continue genuine context where relevant; never invent familiarity.")
  if reply:
   print("INBOUND REPLY",n.author.handle,reply)
   if not DRY_RUN:
    parent=models.ComAtprotoRepoStrongRef.Main(uri=n.uri,cid=n.cid);root=getattr(getattr(n.record,"reply",None),"root",None) or parent;c.send_post(reply,reply_to=models.AppBskyFeedPost.ReplyRef(parent=parent,root=root));remember_relationship(s,n.author.did,n.author.handle,"inbound_reply",txt+" => "+reply)
    if gm.enabled():gm.log_interaction("inbound_reply",n.author.did,n.author.handle,n.uri,txt,reply,"");gm.log_conversation(n.author.did,n.author.handle,"inbound",n.uri,txt,reply,history)
   count+=1
 s["inbound_seen"]=list(done)[-1500:];return count
def main():
 started=datetime.now(timezone.utc).isoformat();c=Client();c.login(HANDLE,PASSWORD);me=c.get_profile(HANDLE);s=state_load();block=gm.do_not_engage() if gm.enabled() else set();inbound=process_inbound(c,me,s,block) or 0;seen=set(s.get("seen",[]));followed=set(s.get("followed",[]));liked=set(s.get("liked",[]));replied=set(s.get("replied",[]));cands=[]
 for topic in random.sample(TOPICS,min(3,len(TOPICS))):
  try:
   for p in c.app.bsky.feed.search_posts({"q":topic,"limit":15,"sort":"latest"}).posts:
    if p.uri in seen or p.author.did==me.did or blocked(block,p):continue
    txt=safe_text(getattr(p.record,"text",""))
    if len(txt)>=45:cands.append((p,txt,topic))
  except Exception as e:print("search failed",topic,e)
 random.shuffle(cands);replies=follows=likes=0
 for p,txt,topic in cands[:20]:
  seen.add(p.uri);history=sheet_history(p.author.did) or relationship_context(s,p.author.did)
  if replies<MAX_REPLIES and p.uri not in replied:
   reply=ai(f"Topic:{topic}\nPost by @{p.author.handle}: {txt}\nRemembered history:\n{history or '- none'}\nIf no genuinely useful contribution output NO_REPLY. Otherwise add substance in 1-3 sentences. Continue genuine context when relevant. No generic agreement, invented familiarity, partisan persuasion or bait.")
   if reply:
    print("REPLY",p.author.handle,reply)
    if not DRY_RUN:
     parent=models.ComAtprotoRepoStrongRef.Main(uri=p.uri,cid=p.cid);root=getattr(getattr(p.record,"reply",None),"root",None) or parent;c.send_post(reply,reply_to=models.AppBskyFeedPost.ReplyRef(parent=parent,root=root));replied.add(p.uri);remember_relationship(s,p.author.did,p.author.handle,"outbound_reply",txt+" => "+reply)
     if gm.enabled():gm.log_interaction("reply",p.author.did,p.author.handle,p.uri,txt,reply,"");gm.log_conversation(p.author.did,p.author.handle,"outbound",p.uri,txt,reply,history)
    replies+=1
  d=None;nl=likes<MAX_LIKES and p.uri not in liked;nf=follows<MAX_FOLLOWS and p.author.did not in followed
  if nl or nf:d=decision(p.author,txt,topic)
  if nl and d and d.get("like") is True:
   print("LIKE",p.author.handle)
   if not DRY_RUN:
    c.like(p.uri,p.cid);liked.add(p.uri);remember_relationship(s,p.author.did,p.author.handle,"like",txt)
    if gm.enabled():gm.log_interaction("like",p.author.did,p.author.handle,p.uri,txt,"",d.get("reason",""))
   likes+=1
  if nf and d and d.get("follow") is True:
   print("FOLLOW",p.author.handle)
   if not DRY_RUN:
    c.follow(p.author.did);followed.add(p.author.did);remember_relationship(s,p.author.did,p.author.handle,"follow",txt)
    if gm.enabled():gm.log_interaction("follow",p.author.did,p.author.handle,p.uri,txt,"",d.get("reason",""))
   follows+=1
  if replies>=MAX_REPLIES and follows>=MAX_FOLLOWS and likes>=MAX_LIKES:break
 s.update(seen=list(seen)[-1500:],followed=list(followed)[-1000:],liked=list(liked)[-1500:],replied=list(replied)[-1500:],last_run=datetime.now(timezone.utc).isoformat());state_save(s)
 if gm.enabled():gm.log_run(started,"engagement",DRY_RUN,len(cands),replies+inbound,likes,follows,0,"")
if __name__=="__main__":main()
