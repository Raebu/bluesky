"""Autonomous, rate-limited Bluesky professional presence for @mraeburn.link."""
from __future__ import annotations
import json, os, random, re
from datetime import datetime, timezone
from pathlib import Path
from atproto import Client, models
from voice import MARTIN_VOICE
from intelligence import relationship_context, remember_relationship, load_knowledge

HANDLE=os.getenv("BSKY_HANDLE","mraeburn.link"); PASSWORD=os.environ["BSKY_APP_PASSWORD"]; DRY_RUN=os.getenv("DRY_RUN","true").lower()=="true"; STATE_FILE=Path(os.getenv("STATE_FILE","state.json"))
TOPICS=[x.strip() for x in os.getenv("TOPICS","artificial intelligence,AI automation,enterprise software,technology leadership,entrepreneurship").split(",") if x.strip()]
MAX_REPLIES=int(os.getenv("MAX_REPLIES_PER_RUN","2")); MAX_FOLLOWS=int(os.getenv("MAX_FOLLOWS_PER_RUN","2")); MAX_LIKES=int(os.getenv("MAX_LIKES_PER_RUN","3")); MAX_INBOUND=int(os.getenv("MAX_INBOUND_REPLIES_PER_RUN","2"))

def state_load():
    try: return json.loads(STATE_FILE.read_text())
    except Exception: return {"seen":[],"followed":[],"liked":[],"replied":[],"inbound_seen":[],"relationships":{}}
def state_save(s): STATE_FILE.parent.mkdir(parents=True,exist_ok=True); STATE_FILE.write_text(json.dumps(s,indent=2,sort_keys=True)+"\n")
def ai(prompt,max_chars=290):
    from openai import OpenAI
    r=OpenAI(api_key=os.environ["OPENAI_API_KEY"]).responses.create(model=os.getenv("OPENAI_MODEL","gpt-5-mini"),input=MARTIN_VOICE+"\n\nTASK\n"+prompt); text=r.output_text.strip().replace("\r","")
    return None if text.upper().startswith("NO_REPLY") else text[:max_chars].rstrip()
def ai_json(prompt):
    raw=ai(prompt,1200)
    if not raw:return None
    try:return json.loads(re.sub(r"^```(?:json)?\s*|\s*```$","",raw.strip(),flags=re.I))
    except:return None
def safe_text(t):return re.sub(r"\s+"," ",t or "").strip()[:600]
def engagement_decision(author,txt,topic):
    return ai_json(f"Topic: {topic}\nAuthor: @{author.handle}\nDisplay name: {getattr(author,'display_name','') or ''}\nPost: {txt}\nReturn JSON only {{\"like\":false,\"follow\":false,\"reason\":\"\"}}. Be conservative. Like only substantive, relevant, credible professional content. Follow only if this author appears worthwhile as an ongoing professional source/peer. Reject spam, promotional noise, generic news/repost aggregators, engagement bait, suspicious accounts, rage bait and partisan political campaigning. Uncertain=false.")

def process_inbound(client,me,state):
    done=set(state.get("inbound_seen",[])); count=0
    try: notes=client.app.bsky.notification.list_notifications({"limit":30}).notifications
    except Exception as e: print("notifications failed",e); return
    for n in notes:
        if count>=MAX_INBOUND:break
        if n.uri in done or n.author.did==me.did or n.reason not in {"reply","mention"}:continue
        done.add(n.uri); txt=safe_text(getattr(n.record,"text","")); history=relationship_context(state,n.author.did)
        reply=ai(f"Inbound {n.reason} from @{n.author.handle}: {txt}\nPrevious remembered interaction:\n{history or '- none'}\nDecide whether a substantive professional response is warranted. Ignore spam, generic praise, hostility, engagement bait and political persuasion. If no useful response, output NO_REPLY. Otherwise reply naturally in Martin's voice, continuing prior context where relevant. Never invent familiarity or facts.")
        if reply:
            print("INBOUND REPLY",n.author.handle,reply)
            if not DRY_RUN:
                parent=models.ComAtprotoRepoStrongRef.Main(uri=n.uri,cid=n.cid); root_ref=getattr(getattr(n.record,"reply",None),"root",None) or parent
                client.send_post(reply,reply_to=models.AppBskyFeedPost.ReplyRef(parent=parent,root=root_ref)); remember_relationship(state,n.author.did,n.author.handle,"inbound_reply",txt+" => "+reply)
            count+=1
    state["inbound_seen"]=list(done)[-1500:]

def main():
    client=Client(); client.login(HANDLE,PASSWORD); me=client.get_profile(HANDLE); state=state_load(); process_inbound(client,me,state)
    seen=set(state.get("seen",[])); followed=set(state.get("followed",[])); liked=set(state.get("liked",[])); replied=set(state.get("replied",[])); candidates=[]
    for topic in random.sample(TOPICS,min(3,len(TOPICS))):
        try:
            for p in client.app.bsky.feed.search_posts({"q":topic,"limit":15,"sort":"latest"}).posts:
                if p.uri in seen or p.author.did==me.did:continue
                txt=safe_text(getattr(p.record,"text",""))
                if len(txt)>=45:candidates.append((p,txt,topic))
        except Exception as e:print("search failed",topic,e)
    random.shuffle(candidates); replies=follows=likes=0
    for p,txt,topic in candidates[:20]:
        seen.add(p.uri); history=relationship_context(state,p.author.did)
        if replies<MAX_REPLIES and p.uri not in replied:
            reply=ai(f"Topic: {topic}\nPost by @{p.author.handle}: {txt}\nPrevious remembered interaction:\n{history or '- none'}\nIf Martin has no genuinely useful contribution output NO_REPLY. Otherwise write 1-3 natural sentences adding substance. Continue genuine prior context when relevant. No generic agreement, invented familiarity, partisan persuasion or engagement bait.")
            if reply:
                print("REPLY",p.author.handle,reply)
                if not DRY_RUN:
                    parent=models.ComAtprotoRepoStrongRef.Main(uri=p.uri,cid=p.cid); root=getattr(getattr(p.record,"reply",None),"root",None) or parent; client.send_post(reply,reply_to=models.AppBskyFeedPost.ReplyRef(parent=parent,root=root)); replied.add(p.uri); remember_relationship(state,p.author.did,p.author.handle,"outbound_reply",txt+" => "+reply)
                replies+=1
        decision=None; needs_like=likes<MAX_LIKES and p.uri not in liked; needs_follow=follows<MAX_FOLLOWS and p.author.did not in followed
        if needs_like or needs_follow: decision=engagement_decision(p.author,txt,topic)
        if needs_like and decision and decision.get("like") is True:
            print("LIKE",p.author.handle)
            if not DRY_RUN:client.like(p.uri,p.cid); liked.add(p.uri); remember_relationship(state,p.author.did,p.author.handle,"like",txt)
            likes+=1
        if needs_follow and decision and decision.get("follow") is True:
            print("FOLLOW",p.author.handle)
            if not DRY_RUN:client.follow(p.author.did); followed.add(p.author.did); remember_relationship(state,p.author.did,p.author.handle,"follow",txt)
            follows+=1
        if replies>=MAX_REPLIES and follows>=MAX_FOLLOWS and likes>=MAX_LIKES:break
    state.update(seen=list(seen)[-1500:],followed=list(followed)[-1000:],liked=list(liked)[-1500:],replied=list(replied)[-1500:],last_run=datetime.now(timezone.utc).isoformat()); state_save(state)
if __name__=="__main__":main()
