"""Shared intelligence, memory and reputation controls for the Bluesky agent."""
from __future__ import annotations
import json,math,re
from collections import Counter
from pathlib import Path
KNOWLEDGE_FILE=Path(__file__).with_name("knowledge.json")
def load_knowledge():
 try:return json.loads(KNOWLEDGE_FILE.read_text())
 except:return {}
def normalise(text):return re.sub(r"[^a-z0-9 ]+"," ",(text or "").lower())
def tokens(text):return [x for x in normalise(text).split() if len(x)>2]
def similarity(a,b):
 ca,cb=Counter(tokens(a)),Counter(tokens(b))
 if not ca or not cb:return 0.0
 dot=sum(ca[k]*cb.get(k,0) for k in ca);return dot/math.sqrt(sum(v*v for v in ca.values())*sum(v*v for v in cb.values()))
def is_duplicate(candidate,previous,threshold=.68):return any(similarity(candidate,old)>=threshold for old in previous[-100:] if old)
def relationship_context(state,did):
 rel=state.get("relationships",{}).get(did,{});return "\n".join(f"- {x.get('kind')}: {x.get('text','')[:240]}" for x in rel.get("history",[])[-6:])
def remember_relationship(state,did,handle,kind,text):
 rel=state.setdefault("relationships",{}).setdefault(did,{"handle":handle,"interactions":0,"history":[]});rel["handle"]=handle;rel["interactions"]=int(rel.get("interactions",0))+1;rel.setdefault("history",[]).append({"kind":kind,"text":text[:500]});rel["history"]=rel["history"][-20:]
def content_mix_prompt(state):
 recent=state.get("content_topics",[])[-16:];counts=Counter(recent);choices=["AI implementation economics","software architecture and technical debt","organisational design and incentives","technology governance and risk","enterprise adoption friction","procurement and interoperability","technology leadership","automation and human judgement","productivity and operational design","emerging technology commercialisation","market structure and technology","measured contrarian technology view"]
 choices.sort(key=lambda x:counts[x]);return choices[0]
def reputation_gate_prompt(text,knowledge):
 return f'''Final pre-publication reputation and factuality review.\nCandidate: {text}\nVerified knowledge: {json.dumps(knowledge,ensure_ascii=False)}\nReturn JSON only: {{"publish":true,"reason":"..."}}. Set publish=false for invented personal/company/client/project experience, unsupported factual claims presented as certain, confidential-looking material, aggressive or abusive language, spam, engagement bait, dubious calls to action, partisan political persuasion, election advocacy/predictions, or content too generic to justify publishing. When uncertain, reject.'''
