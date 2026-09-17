from __future__ import annotations
import re
CURRENT=re.compile(r'\b(today|yesterday|breaking|just announced|acquir(?:e|ed|es|ing)|merger|deal value|valued at|raised|funding round|lawsuit|alleg(?:e|ed|ation)|election|candidate|vote|poll)\b',re.I)
POLITICAL=re.compile(r'\b(election|candidate|vote|voting|party|parliament|president|prime minister|ballot|referendum)\b',re.I)
SALES=re.compile(r'\b(dm me|book a call|we can help|contact us|hire us|buy now)\b',re.I)
PERSONAL_DEAL=re.compile(r'\b(i|we)\s+(led|advised|acquired|bought|sold|invested|integrated|closed)\b',re.I)
def gate_generated(text,verified_context=''):
 if not text:return False,'empty'
 if SALES.search(text):return False,'automated sales outreach'
 if PERSONAL_DEAL.search(text) and not verified_context:return False,'unverified personal transaction claim'
 if CURRENT.search(text) and not verified_context:return False,'research_required'
 return True,'ok'
def political(text):return bool(POLITICAL.search(text or ''))
def current_claim(text):return bool(CURRENT.search(text or ''))
