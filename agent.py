"""Autonomous Bluesky presence with durable relationship intelligence."""
from __future__ import annotations
import json,os,random,re
from datetime import datetime,timezone
from pathlib import Path
from atproto import Client,models
from voice import MARTIN_VOICE
from intelligence import relationship_context,remember_relationship,similarity
from network_intelligence import relationship_profile,discovery_topics
import gdrive_memory as gm
HANDLE=os.getenv("BSKY_HANDLE","mraeburn.link");PASSWORD=os.environ["BSKY_APP_PASSWORD"];DRY_RUN=os.getenv("DRY_RUN","true").lower()=="true";STATE_FILE=Path(os.getenv("STATE_FILE","state.json"));MAX_REPLIES=int(os.getenv("MAX_REPLIES_PER_RUN","2"));MAX_FOLLOWS=int(os.getenv("MAX_FOLLOWS_PER_RUN","2"));MAX_LIKES=int(os.getenv("MAX_LIKES_PER_RUN","3"));MAX_INBOUND=int(os.getenv("MAX_INBOUND_REPLIES_PER_RUN","2"));REPLY_LIMIT=int(os.getenv("BSKY_REPLY_CHAR_LIMIT","220"));ECHO_LIMIT=float(os.getenv("BSKY_REPLY_ECHO_LIMIT","0.56"));GENERIC_OPENING=re.compile(r"^(agree(?:d)?|exactly|absolutely|indeed|fair point|good point|great point|spot on|true|yes)\b[\s,.:;!—-]*",re.I)
def state_load():
 try:return json.loads(STATE_FILE.read_text())
 except:return {"seen":[],"followed":[],"liked":[],"replied":[],"inbound_seen":[],"relationships":{}}
def state_save(s):STATE_FILE.parent.mkdir(parents=True,exist_ok=True);STATE_FILE.write_text(json.dumps(s,indent=2,sort_keys=True)+"\n")
def ai_raw(prompt):
 from openai import OpenAI
 r=OpenAI(api_key=os.environ["OPENAI_API_KEY"]).responses.create(model=os.getenv("OPENAI_MODEL","gpt-5-mini"),input=MARTIN_VOICE+"\nTASK\n"+prompt);return r.output_text.strip().replace("\r","")
def ai_json(prompt):
 try:return json.loads(re.sub(r"^```(?:json)?\s*|\s*```$","",ai_raw(prompt).strip(),flags=re.I))
 except:return None
def safe_text(t):return re.sub(r"\s+"," ",t or "").strip()[:600]
def opening_sentence(t):
 m=re.search(r"^(.+?[.!?])(?:\s|$)",t);return m.group(1) if m else t
def complete_reply(prompt,source_text=""):
 for attempt in range(4):
  suffix=f"\nWrite ONE concise, complete response <= {REPLY_LIMIT} characters. Goal: genuine two-way professional conversation. Start directly with substance: NEVER open with Agree, Agreed, Exactly, Absolutely, Indeed, Fair point, Good point, Great point, Spot on, True, Yes, praise, or a restatement/paraphrase of the author's premise or headline. The opening sentence must contribute NEW analytical value: a distinction, mechanism, consequence, constraint, counterpoint or second-order implication not already stated by the author. First address the CENTRAL CLAIM; only then introduce a technical angle if it materially sharpens that claim. Prefer one educated, specific contribution + one natural question about reasoning, implementation, evidence, incentives, constraints or trade-offs. Avoid compressed slogan-like phrases and jargon piles. No generic 'Thoughts?'. 1-2 short sentences; one useful point. End naturally. Output only reply or NO_REPLY."
  if attempt:suffix+=" Previous attempt failed a style, echo or length check. Do not paraphrase the source; add genuinely new analytical information and make it natural."
  t=re.sub(r"\s+"," ",ai_raw(prompt+suffix).strip())
  if t.upper().startswith("NO_REPLY"):return None
  if GENERIC_OPENING.search(t):continue
  if source_text and similarity(opening_sentence(t),source_text)>ECHO_LIMIT:continue
  if len(t)<=REPLY_LIMIT and re.search(r"[.!?][\"')\]]?$",t):return t
 return None
def blocked(block,p):return bool({p.author.did.lower(),p.author.handle.lower(),"@"+p.author.handle.lower()}&block)
def sheet_history(did):
 if not gm.enabled():return ""
 return "\n".join(f"- {r.get('Direction')}: {r.get('Their Text','')} => {r.get('Martin Reply','')}" for r in gm.conversation_for(did)[-6:])
def quality_decision(a,t,topic,profile):
 return ai_json(f"Topic:{topic}\nAuthor:@{a.handle}\nDisplay name:{getattr(a,'display_name','') or ''}\nRelationship:{json.dumps(profile)}\nPost:{t}\nReturn JSON only {{\"reply_worthy\":false,\"like\":false,\"follow\":false,\"reason\":\"\"}}. Strict professional reputation filter. Prefer substantive two-way dialogue and, all else equal, recurring/established relationships over strangers. Existing relationship never overrides poor content. A reply is worthy only when Martin can engage the post's central claim directly AND add something analytically new rather than restating its premise/headline. Reject promotional bundles/courses, affiliate content, spam, aggregators, bait, low-information posts, suspicious accounts, rage bait and partisan political campaigning. like only credible relevant substance; follow only worthwhile ongoing sources/peers. Uncertain=all false.")
def process_inbound(c,me,s,block):
 done=set(s.get("inbound_seen",[]));count=0
 try:notes=c.app.bsky.notification.list_notifications({"limit":30}).notifications
 except Exception as e:return print("notifications failed",e)
 for n in notes:
  if count>=MAX_INBOUND:break
  if n.uri in done or n.author.did==me.did or n.reason not in {"reply","mention"}:continue
  if {n.author.did.lower(),n.author.handle.lower(),"@"+n.author.handle.lower()}&block:done.add(n.uri);continue
  done.add(n.uri);txt=safe_text(getattr(n.record,"text",""));profile=relationship_profile(n.author.did);history=sheet_history(n.author.did) or relationship_context(s,n.author.did);q=quality_decision(n.author,txt,"inbound",profile)
  if not q or q.get("reply_worthy") is not True:continue
  reply=complete_reply(f"Inbound {n.reason} from @{n.author.handle}: {txt}\nRelationship stage:{profile['stage']} score:{profile['score']}\nHistory:\n{history or '- none'}\nContinue the actual conversation. Address what they are principally saying, but do not echo or paraphrase it. Add a new distinction, mechanism, implication or counterpoint. For recurring/established contacts, build on prior reasoning rather than resetting context. Ask one informed follow-up where useful.",txt)
  if reply:
   print("INBOUND REPLY",n.author.handle,profile,reply)
   if not DRY_RUN:
    parent=models.ComAtprotoRepoStrongRef.Main(uri=n.uri,cid=n.cid);root=getattr(getattr(n.record,"reply",None),"root",None) or parent;c.send_post(reply,reply_to=models.AppBskyFeedPost.ReplyRef(parent=parent,root=root));remember_relationship(s,n.author.did,n.author.handle,"inbound_reply",txt+" => "+reply)
    if gm.enabled():gm.log_interaction("inbound_reply",n.author.did,n.author.handle,n.uri,txt,reply,q.get("reason",""));gm.log_conversation(n.author.did,n.author.handle,"inbound",n.uri,txt,reply,f"{profile} {history}")
   count+=1
 s["inbound_seen"]=list(done)[-1500:];return count
def main():
 started=datetime.now(timezone.utc).isoformat();c=Client();c.login(HANDLE,PASSWORD);me=c.get_profile(HANDLE);s=state_load();block=gm.do_not_engage() if gm.enabled() else set();inbound=process_inbound(c,me,s,block) or 0;seen=set(s.get("seen",[]));followed=set(s.get("followed",[]));liked=set(s.get("liked",[]));replied=set(s.get("replied",[]));cands=[]
 topics=discovery_topics(6)
 for topic in topics:
  try:
   for p in c.app.bsky.feed.search_posts({"q":topic,"limit":12,"sort":"latest"}).posts:
    if p.uri in seen or p.author.did==me.did or blocked(block,p):continue
    txt=safe_text(getattr(p.record,"text",""))
    if len(txt)>=45:
     profile=relationship_profile(p.author.did);cands.append((profile["score"],random.random(),p,txt,topic,profile))
  except Exception as e:print("search failed",topic,e)
 cands.sort(key=lambda x:(x[0],x[1]),reverse=True);replies=follows=likes=0
 for _,__,p,txt,topic,profile in cands[:30]:
  seen.add(p.uri);history=sheet_history(p.author.did) or relationship_context(s,p.author.did);d=quality_decision(p.author,txt,topic,profile)
  if not d:continue
  print("FILTER",p.author.handle,profile,d.get("reason",""))
  if replies<MAX_REPLIES and p.uri not in replied and d.get("reply_worthy") is True:
   reply=complete_reply(f"Topic:{topic}\nPost by @{p.author.handle}: {txt}\nRelationship:{profile}\nHistory:\n{history or '- none'}\nEnter as a conversation, not a mini-essay. Engage the central claim without repeating its framing. The first sentence must earn the reply by adding a new distinction, mechanism, consequence, constraint, counterpoint or second-order implication; then normally ask one concrete, informed question. Do not pivot to an adjacent technical topic merely because Martin knows about it. If recurring/established, continue the relationship's existing thread of thought.",txt)
   if reply:
    print("REPLY",p.author.handle,reply)
    if not DRY_RUN:
     parent=models.ComAtprotoRepoStrongRef.Main(uri=p.uri,cid=p.cid);root=getattr(getattr(p.record,"reply",None),"root",None) or parent;c.send_post(reply,reply_to=models.AppBskyFeedPost.ReplyRef(parent=parent,root=root));replied.add(p.uri);remember_relationship(s,p.author.did,p.author.handle,"outbound_reply",txt+" => "+reply)
     if gm.enabled():gm.log_interaction("reply",p.author.did,p.author.handle,p.uri,txt,reply,d.get("reason",""));gm.log_conversation(p.author.did,p.author.handle,"outbound",p.uri,txt,reply,f"{profile} {history}")
    replies+=1
  if likes<MAX_LIKES and p.uri not in liked and d.get("like") is True:
   print("LIKE",p.author.handle)
   if not DRY_RUN:
    c.like(p.uri,p.cid);liked.add(p.uri);remember_relationship(s,p.author.did,p.author.handle,"like",txt)
    if gm.enabled():gm.log_interaction("like",p.author.did,p.author.handle,p.uri,txt,"",d.get("reason",""))
   likes+=1
  if follows<MAX_FOLLOWS and p.author.did not in followed and d.get("follow") is True:
   print("FOLLOW",p.author.handle)
   if not DRY_RUN:
    c.follow(p.author.did);followed.add(p.author.did);remember_relationship(s,p.author.did,p.author.handle,"follow",txt)
    if gm.enabled():gm.log_interaction("follow",p.author.did,p.author.handle,p.uri,txt,"",d.get("reason",""))
   follows+=1
 s.update(seen=list(seen)[-1500:],followed=list(followed)[-1000:],liked=list(liked)[-1500:],replied=list(replied)[-1500:],last_run=datetime.now(timezone.utc).isoformat());state_save(s)
 if gm.enabled():gm.log_run(started,"engagement",DRY_RUN,len(cands),replies+inbound,likes,follows,0,"topics="+",".join(topics))
if __name__=="__main__":main()
