"""Autonomous Bluesky presence with shared cross-platform Social OS governance."""
from __future__ import annotations
import json,os,random,re
from datetime import datetime,timezone
from pathlib import Path
from atproto import Client,models
from voice import MARTIN_VOICE
from intelligence import relationship_context,remember_relationship,similarity
from network_intelligence import relationship_profile,discovery_topics
import gdrive_memory as gm
import semantic,policy
HANDLE=os.getenv("BSKY_HANDLE","mraeburn.link");PASSWORD=os.environ["BSKY_APP_PASSWORD"];DRY_RUN=os.getenv("DRY_RUN","true").lower()=="true";STATE_FILE=Path(os.getenv("STATE_FILE","state.json"));MAX_REPLIES=int(os.getenv("MAX_REPLIES_PER_RUN","2"));MAX_FOLLOWS=int(os.getenv("MAX_FOLLOWS_PER_RUN","2"));MAX_LIKES=int(os.getenv("MAX_LIKES_PER_RUN","3"));MAX_INBOUND=int(os.getenv("MAX_INBOUND_REPLIES_PER_RUN","2"));REPLY_LIMIT=int(os.getenv("BSKY_REPLY_CHAR_LIMIT","220"));ECHO_LIMIT=float(os.getenv("BSKY_REPLY_ECHO_LIMIT","0.56"));GENERIC_OPENING=re.compile(r"^(agree(?:d)?|exactly|absolutely|indeed|fair point|good point|great point|spot on|true|yes)\b[\s,.:;!—-]*",re.I)
def state_load():
 try:return json.loads(STATE_FILE.read_text())
 except:return {"seen":[],"followed":[],"liked":[],"replied":[],"inbound_seen":[],"relationships":{}}
def state_save(s):STATE_FILE.parent.mkdir(parents=True,exist_ok=True);STATE_FILE.write_text(json.dumps(s,indent=2,sort_keys=True)+"\n")
def correction_text():return '; '.join(str(r.get('Correct Value') or r.get('Instruction') or '') for r in (gm.corrections() if gm.enabled() else [])[-20:])
def ai_raw(prompt):
 from openai import OpenAI
 r=OpenAI(api_key=os.environ["OPENAI_API_KEY"]).responses.create(model=os.getenv("OPENAI_MODEL","gpt-5-mini"),input=MARTIN_VOICE+"\nHUMAN CORRECTIONS\n"+correction_text()+"\nTASK\n"+prompt);return r.output_text.strip().replace("\r","")
def ai_json(prompt):
 try:return json.loads(re.sub(r"^```(?:json)?\s*|\s*```$","",ai_raw(prompt).strip(),flags=re.I))
 except:return None
def safe_text(t):return re.sub(r"\s+"," ",t or "").strip()[:600]
def opening_sentence(t):
 m=re.search(r"^(.+?[.!?])(?:\s|$)",t);return m.group(1) if m else t
def complete_reply(prompt,source_text=""):
 recent=(gm.recent_lineage_texts(300) if gm.enabled() else [])
 for attempt in range(4):
  suffix=f"\nWrite ONE concise, complete response <= {REPLY_LIMIT} characters. Goal: genuine two-way professional conversation. Start directly with substance; never open with agreement, praise or a restatement. Add a new distinction, mechanism, consequence, constraint, counterpoint or second-order implication. Prefer one educated contribution + one natural question about reasoning, implementation, evidence, incentives, constraints or trade-offs. No sales pitch. Output only reply or NO_REPLY."
  if attempt:suffix+=" Previous attempt failed a style, echo or length check."
  t=re.sub(r"\s+"," ",ai_raw(prompt+suffix).strip())
  if t.upper().startswith("NO_REPLY"):return None
  if GENERIC_OPENING.search(t) or (source_text and similarity(opening_sentence(t),source_text)>ECHO_LIMIT):continue
  ok,reason=policy.gate_generated(t,"\n".join(gm.verified_knowledge()) if gm.enabled() else "")
  if not ok:
   if gm.enabled() and reason=='research_required':gm.research_hold(t,reason,'Bluesky reply')
   continue
  if semantic.duplicate(t,recent,.72):continue
  if len(t)<=REPLY_LIMIT and re.search(r"[.!?][\"')\]]?$",t):return t
 return None
def blocked(block,p):return bool({p.author.did.lower(),p.author.handle.lower(),"@"+p.author.handle.lower()}&block)
def sheet_history(did):
 if not gm.enabled():return ""
 return "\n".join(f"- {r.get('Direction')}: {r.get('Their Text','')} => {r.get('Martin Reply','')}" for r in gm.conversation_for(did)[-6:])
def quality_decision(a,t,topic,profile):
 if policy.political(t):return {"reply_worthy":False,"like":False,"follow":False,"reason":"political restraint"}
 if policy.current_claim(t) and not (gm.verified_knowledge() if gm.enabled() else []):
  if gm.enabled():gm.research_hold(t,'current claim requires verification','Bluesky discovery')
  return {"reply_worthy":False,"like":False,"follow":False,"reason":"research_required"}
 d=ai_json(f"Topic:{topic}\nAuthor:@{a.handle}\nDisplay name:{getattr(a,'display_name','') or ''}\nRelationship:{json.dumps(profile)}\nPost:{t}\nReturn JSON only {{\"reply_worthy\":false,\"like\":false,\"follow\":false,\"reason\":\"\"}}. Strict professional reputation filter. Prefer substantive dialogue and, all else equal, recurring/established relationships. Seek CEOs/founders, operators, M&A/corp-dev, investors, strategists, technology leaders and strong independent experts. Existing relationship never overrides poor content. Reject spam, aggregators, bait, low-information posts, rage bait and partisan campaigning. like only credible relevant substance; follow only durable professional value. Uncertain=all false.")
 if gm.enabled():gm.replay('decision',{'handle':a.handle,'topic':topic,'post':t},(d or {}).get('reason','no decision'),.7)
 return d
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
  reply=complete_reply(f"Inbound {n.reason} from @{n.author.handle}: {txt}\nRelationship stage:{profile['stage']} score:{profile['score']}\nHistory:\n{history or '- none'}\nContinue the actual conversation. Address what they are principally saying without echoing it. For recurring/established contacts, build on prior reasoning rather than resetting context.",txt)
  if reply:
   print("INBOUND REPLY",n.author.handle,profile,reply)
   if not DRY_RUN and gm.control('Growth Enabled',True) and gm.control('Comments Enabled',True):
    parent=models.ComAtprotoRepoStrongRef.Main(uri=n.uri,cid=n.cid);root=getattr(getattr(n.record,"reply",None),"root",None) or parent;c.send_post(reply,reply_to=models.AppBskyFeedPost.ReplyRef(parent=parent,root=root));remember_relationship(s,n.author.did,n.author.handle,"inbound_reply",txt+" => "+reply)
    if gm.enabled():gm.log_interaction("inbound_reply",n.author.did,n.author.handle,n.uri,txt,reply,q.get("reason",""));gm.log_conversation(n.author.did,n.author.handle,"inbound",n.uri,txt,reply,f"{profile} {history}")
   count+=1
 s["inbound_seen"]=list(done)[-1500:];return count
def main():
 started=datetime.now(timezone.utc).isoformat();c=Client();c.login(HANDLE,PASSWORD);me=c.get_profile(HANDLE);s=state_load();block=gm.do_not_engage() if gm.enabled() else set();inbound=process_inbound(c,me,s,block) or 0;seen=set(s.get("seen",[]));followed=set(s.get("followed",[]));liked=set(s.get("liked",[]));replied=set(s.get("replied",[]));cands=[];recent_cross=(gm.recent_lineage_texts(300) if gm.enabled() else [])
 topics=discovery_topics(8)+["M&A","corporate strategy","private equity","corporate development","investment","operating model"]
 for topic in list(dict.fromkeys(topics)):
  try:
   for p in c.app.bsky.feed.search_posts({"q":topic,"limit":10,"sort":"latest"}).posts:
    if p.uri in seen or p.author.did==me.did or blocked(block,p):continue
    txt=safe_text(getattr(p.record,"text",""))
    if len(txt)>=45 and not semantic.duplicate(txt,recent_cross,.80):
     profile=relationship_profile(p.author.did);cands.append((profile["score"],random.random(),p,txt,topic,profile))
  except Exception as e:print("search failed",topic,e)
 cands.sort(key=lambda x:(x[0],x[1]),reverse=True);replies=follows=likes=0
 for _,__,p,txt,topic,profile in cands[:30]:
  seen.add(p.uri);history=sheet_history(p.author.did) or relationship_context(s,p.author.did);d=quality_decision(p.author,txt,topic,profile)
  if not d:continue
  print("FILTER",p.author.handle,profile,d.get("reason",""))
  if replies<MAX_REPLIES and p.uri not in replied and d.get("reply_worthy") is True:
   reply=complete_reply(f"Topic:{topic}\nPost by @{p.author.handle}: {txt}\nRelationship:{profile}\nHistory:\n{history or '- none'}\nEnter as a conversation, not a mini-essay. Engage the central claim without repeating its framing. Add a new distinction, mechanism, consequence, constraint, counterpoint or second-order implication; then normally ask one concrete informed question. For M&A/investment, use relevant lenses such as rationale, diligence, valuation assumptions, technology debt, integration and incentives without claiming personal deal experience.",txt)
   if reply:
    print("REPLY",p.author.handle,reply)
    if not DRY_RUN and gm.control('Growth Enabled',True) and gm.control('Comments Enabled',True):
     parent=models.ComAtprotoRepoStrongRef.Main(uri=p.uri,cid=p.cid);root=getattr(getattr(p.record,"reply",None),"root",None) or parent;c.send_post(reply,reply_to=models.AppBskyFeedPost.ReplyRef(parent=parent,root=root));replied.add(p.uri);remember_relationship(s,p.author.did,p.author.handle,"outbound_reply",txt+" => "+reply)
     if gm.enabled():gm.log_interaction("reply",p.author.did,p.author.handle,p.uri,txt,reply,d.get("reason",""));gm.log_conversation(p.author.did,p.author.handle,"outbound",p.uri,txt,reply,f"{profile} {history}")
    replies+=1
  if likes<MAX_LIKES and p.uri not in liked and d.get("like") is True:
   print("LIKE",p.author.handle)
   if not DRY_RUN and gm.control('Growth Enabled',True) and gm.control('Reactions Enabled',True):
    c.like(p.uri,p.cid);liked.add(p.uri);remember_relationship(s,p.author.did,p.author.handle,"like",txt)
    if gm.enabled():gm.log_interaction("like",p.author.did,p.author.handle,p.uri,txt,"",d.get("reason",""))
   likes+=1
  if follows<MAX_FOLLOWS and p.author.did not in followed and d.get("follow") is True:
   print("FOLLOW",p.author.handle)
   if not DRY_RUN and gm.control('Growth Enabled',True):
    c.follow(p.author.did);followed.add(p.author.did);remember_relationship(s,p.author.did,p.author.handle,"follow",txt)
    if gm.enabled():gm.log_interaction("follow",p.author.did,p.author.handle,p.uri,txt,"",d.get("reason",""))
   follows+=1
 s.update(seen=list(seen)[-1500:],followed=list(followed)[-1000:],liked=list(liked)[-1500:],replied=list(replied)[-1500:],last_run=datetime.now(timezone.utc).isoformat());state_save(s)
 if gm.enabled():gm.log_run(started,"engagement",DRY_RUN,len(cands),replies+inbound,likes,follows,0,"topics="+",".join(topics))
if __name__=="__main__":main()
