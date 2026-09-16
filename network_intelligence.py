"""Network, discovery and performance intelligence for the Bluesky agent."""
from __future__ import annotations
import os, re
from collections import Counter
import gdrive_memory as gm

DISCOVERY_TOPICS = [
    "AI economics", "AI implementation", "automation ROI", "enterprise AI adoption",
    "technical debt", "software architecture", "interoperability", "technology governance",
    "organisational design", "technology procurement", "digital transformation failure",
    "productivity technology", "emerging technology", "technology leadership",
    "incentive design", "operational resilience", "enterprise software"
]

def relationship_profile(did):
    interactions=[r for r in gm.rows("Interactions") if str(r.get("DID",""))==did] if gm.enabled() else []
    conversations=[r for r in gm.rows("Conversations") if str(r.get("DID",""))==did] if gm.enabled() else []
    inbound=sum(1 for r in conversations if str(r.get("Direction","")).lower()=="inbound")
    outbound=sum(1 for r in conversations if str(r.get("Direction","")).lower()=="outbound")
    likes=sum(1 for r in interactions if str(r.get("Action","")).lower()=="like")
    follows=sum(1 for r in interactions if str(r.get("Action","")).lower()=="follow")
    score=min(100, inbound*18 + min(outbound,4)*8 + min(likes,4)*3 + (10 if follows else 0))
    stage="established" if inbound>=3 or score>=65 else "recurring" if inbound>=1 or score>=30 else "interacted" if interactions or conversations else "new"
    return {"score":score,"stage":stage,"inbound":inbound,"outbound":outbound,"interactions":len(interactions)}

def discovery_topics(limit=6):
    # Rotate broad concepts so discovery does not collapse onto literal 'AI automation' searches.
    runs=gm.rows("Agent Runs") if gm.enabled() else []
    offset=len(runs)%len(DISCOVERY_TOPICS)
    ordered=DISCOVERY_TOPICS[offset:]+DISCOVERY_TOPICS[:offset]
    return ordered[:limit]

def performance_summary(limit=60):
    if not gm.enabled(): return "No durable performance data yet."
    rows=gm.rows("Performance")[-limit:]
    if not rows:return "No durable performance data yet. Do not infer what performs well."
    by_topic={}
    for r in rows:
        topic=str(r.get("Topic","") or "unknown"); vals=by_topic.setdefault(topic,[0,0,0,0])
        for i,k in enumerate(("Likes","Reposts","Replies")):
            try: vals[i]+=int(r.get(k,0) or 0)
            except: pass
        vals[3]+=1
    ranked=sorted(by_topic.items(),key=lambda kv:(kv[1][2]*3+kv[1][1]*2+kv[1][0])/max(kv[1][3],1),reverse=True)
    return "; ".join(f"{t}: {v[3]} snapshots, {v[0]} likes, {v[1]} reposts, {v[2]} replies" for t,v in ranked[:6])

def series_context():
    if not gm.enabled():return ""
    posts=gm.rows("Posts")[-30:]; topics=Counter(str(r.get("Topic","")).strip() for r in posts if r.get("Topic"))
    return "; ".join(f"{k} ({v} prior posts)" for k,v in topics.most_common(6))

def self_critique_prompt(text):
    return f'''Candidate: {text}\nReturn JSON only: {{"pass":true,"reason":""}}. Pass only if this is specific, educated, human, concise, adds a non-obvious mechanism/trade-off/implication, fits Martin's voice, and is worth saying publicly. Reject mini-essays, generic advice, repetition, performative cleverness, unsupported certainty, or anything that sounds automated.'''
