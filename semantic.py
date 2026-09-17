from __future__ import annotations
import re,math
from collections import Counter
def tokens(s):return re.findall(r'[a-z0-9]{3,}',(s or '').lower())
def similarity(a,b):
 x,y=Counter(tokens(a)),Counter(tokens(b));common=set(x)&set(y)
 num=sum(x[k]*y[k] for k in common);dx=math.sqrt(sum(v*v for v in x.values()));dy=math.sqrt(sum(v*v for v in y.values()))
 return num/(dx*dy) if dx and dy else 0.0
def duplicate(text,recent,threshold=.72):return any(similarity(text,x)>=threshold for x in recent if x)
