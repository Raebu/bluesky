"""Publish a useful original Bluesky post with memory, selective media and safety gates."""
import io, json, os, random, re
from pathlib import Path
from atproto import Client
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
from voice import MARTIN_VOICE
from intelligence import load_knowledge, is_duplicate, content_mix_prompt, reputation_gate_prompt

HANDLE = os.getenv("BSKY_HANDLE", "mraeburn.link")
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
STATE_FILE = Path(os.getenv("STATE_FILE", "state.json"))

SYSTEM = MARTIN_VOICE + r"""
Return ONLY valid JSON:
{"text":"post","hashtags":[],"media":"none|insight_card|process_card|contrast_card","card_title":"","card_points":[],"alt_text":"","thread":[]}
RULES: hashtags optional, 0-2 and only for discovery. Final main post <=300 chars. Media is optional and must add information, never decorative generic AI art. Cards may be an insight list, process/sequence, or contrast depending on the idea. Alt text must describe the information. thread is normally empty; use 2-4 additional posts only when the idea genuinely cannot be expressed clearly in one post. Never invent personal experience, clients, projects, transactions, outcomes, statistics or product use.
"""

def load_state():
    try: return json.loads(STATE_FILE.read_text())
    except Exception: return {}

def save_state(s):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(s, indent=2, sort_keys=True)+"\n")

def clean_tag(tag):
    tag=re.sub(r"[^A-Za-z0-9_]","",str(tag).lstrip("#")); return f"#{tag}" if tag else None

def fit_post(text,tags):
    text=re.sub(r"\s+"," ",text).strip(); cleaned=[]
    for tag in tags[:2]:
        t=clean_tag(tag)
        if t and t.lower() not in {x.lower() for x in cleaned}: cleaned.append(t)
    suffix=(" "+" ".join(cleaned)) if cleaned else ""; limit=300-len(suffix)
    if len(text)>limit: text=text[:limit].rsplit(" ",1)[0].rstrip(" ,;:-")
    return text+suffix

def font(size,bold=False):
    p="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(p,size=size) if os.path.exists(p) else ImageFont.load_default()

def wrap(d,text,fnt,width):
    words=text.split(); lines=[]; line=""
    for w in words:
        t=(line+" "+w).strip()
        if d.textbbox((0,0),t,font=fnt)[2]<=width: line=t
        else:
            if line: lines.append(line)
            line=w
    if line: lines.append(line)
    return lines

def make_card(title,points,kind):
    img=Image.new("RGB",(1200,675),(13,20,31)); d=ImageDraw.Draw(img)
    d.text((70,55),"MARTIN RAEBURN",font=font(22,True),fill=(142,183,255)); y=103
    for line in wrap(d,title,font(46,True),1060)[:2]: d.text((70,y),line,font=font(46,True),fill=(245,248,252)); y+=56
    y+=22
    labels = ["→"]*3 if kind=="process_card" else (["A","B","C"] if kind=="contrast_card" else ["1","2","3"])
    for i,p in enumerate(points[:3]):
        d.rounded_rectangle((70,y,1130,y+112),radius=18,fill=(24,35,51)); d.text((96,y+34),labels[i],font=font(27,True),fill=(142,183,255))
        ty=y+24
        for line in wrap(d,p,font(30),930)[:2]: d.text((150,ty),line,font=font(30),fill=(232,237,244)); ty+=38
        y+=132
    out=io.BytesIO(); img.save(out,format="JPEG",quality=90,optimize=True); return out.getvalue()

def ai_json(ai,prompt):
    r=ai.responses.create(model=os.getenv("OPENAI_MODEL","gpt-5-mini"),input=prompt)
    raw=re.sub(r"^```(?:json)?\s*|\s*```$","",r.output_text.strip(),flags=re.I|re.S)
    return json.loads(raw)

def main():
    ai=OpenAI(api_key=os.environ["OPENAI_API_KEY"]); state=load_state(); knowledge=load_knowledge(); topic=content_mix_prompt(state)
    recent=state.get("original_posts",[])[-20:]
    plan=None; text=""
    for _ in range(3):
        task=f"Create one original post. Content lane: {topic}. Verified knowledge: {json.dumps(knowledge)}. Recent posts to avoid repeating: {json.dumps(recent[-8:])}. Prefer a fresh mechanism, trade-off or useful observation."
        plan=ai_json(ai,SYSTEM+"\n\nTASK\n"+task); text=fit_post(str(plan.get("text","")),list(plan.get("hashtags") or []))
        if text and not is_duplicate(text,recent): break
        plan=None
    if not plan or not text: print("SKIP duplicate/weak post"); return
    gate=ai_json(ai,MARTIN_VOICE+"\n\n"+reputation_gate_prompt(text,knowledge))
    if gate.get("publish") is not True: print("SKIP reputation gate:",gate.get("reason","")); return
    media=plan.get("media","none"); title=str(plan.get("card_title","")).strip(); points=[str(x).strip() for x in plan.get("card_points",[]) if str(x).strip()]; alt=str(plan.get("alt_text","")).strip()
    if media not in {"insight_card","process_card","contrast_card"} or not title or len(points)<2 or not alt: media="none"
    thread=[fit_post(str(x),[]) for x in (plan.get("thread") or []) if str(x).strip()][:4]
    if DRY_RUN: print("DRY RUN TEXT:",text); print("DRY RUN MEDIA:",media); print("DRY RUN THREAD:",thread); return
    b=Client(); b.login(HANDLE,os.environ["BSKY_APP_PASSWORD"])
    result=b.send_image(text=text,image=make_card(title,points,media),image_alt=alt,langs=["en-GB"]) if media!="none" else b.send_post(text=text,langs=["en-GB"])
    # Thread support is intentionally conservative: publish continuations only when requested, each replying to the previous post.
    parent=result
    for continuation in thread:
        ref=__import__('atproto').models.ComAtprotoRepoStrongRef.Main(uri=parent.uri,cid=parent.cid)
        parent=b.send_post(continuation,reply_to=__import__('atproto').models.AppBskyFeedPost.ReplyRef(parent=ref,root=__import__('atproto').models.ComAtprotoRepoStrongRef.Main(uri=result.uri,cid=result.cid)),langs=["en-GB"])
    state.setdefault("original_posts",[]).append(text); state["original_posts"]=state["original_posts"][-100:]
    state.setdefault("content_topics",[]).append(topic); state["content_topics"]=state["content_topics"][-100:]; save_state(state); print(result.uri)

if __name__=="__main__": main()
