"""Publish a useful original Bluesky post with durable Google Sheets memory."""
import io,json,os,re,hashlib
from pathlib import Path
from atproto import Client,models
from openai import OpenAI
from PIL import Image,ImageDraw,ImageFont
from voice import MARTIN_VOICE
from intelligence import load_knowledge,is_duplicate,content_mix_prompt,reputation_gate_prompt
import gdrive_memory as gm
HANDLE=os.getenv("BSKY_HANDLE","mraeburn.link"); DRY_RUN=os.getenv("DRY_RUN","true").lower()=="true"; STATE_FILE=Path(os.getenv("STATE_FILE","state.json"))
SYSTEM=MARTIN_VOICE+r'''\nReturn ONLY valid JSON: {"text":"post","hashtags":[],"media":"none|insight_card|process_card|contrast_card","card_title":"","card_points":[],"alt_text":"","thread":[]}\nRULES: hashtags optional, 0-2 and only for discovery. Final main post <=300 chars. Media must add information, never generic decoration. thread normally empty; use 2-4 continuations only when genuinely useful. Never invent personal experience, clients, projects, transactions, outcomes, statistics or product use.'''
def load_state():
 try:return json.loads(STATE_FILE.read_text())
 except:return {}
def save_state(s):STATE_FILE.parent.mkdir(parents=True,exist_ok=True);STATE_FILE.write_text(json.dumps(s,indent=2,sort_keys=True)+"\n")
def clean_tag(t):
 t=re.sub(r"[^A-Za-z0-9_]","",str(t).lstrip("#"));return f"#{t}" if t else None
def fit_post(text,tags):
 text=re.sub(r"\s+"," ",text).strip();clean=[]
 for x in tags[:2]:
  t=clean_tag(x)
  if t and t.lower() not in {z.lower() for z in clean}:clean.append(t)
 suffix=(" "+" ".join(clean)) if clean else "";limit=300-len(suffix)
 if len(text)>limit:text=text[:limit].rsplit(" ",1)[0].rstrip(" ,;:-")
 return text+suffix
def font(size,bold=False):
 p="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf";return ImageFont.truetype(p,size) if os.path.exists(p) else ImageFont.load_default()
def wrap(d,text,f,w):
 lines=[];line=""
 for word in text.split():
  test=(line+" "+word).strip()
  if d.textbbox((0,0),test,font=f)[2]<=w:line=test
  else:
   if line:lines.append(line)
   line=word
 if line:lines.append(line)
 return lines
def make_card(title,points,kind):
 img=Image.new("RGB",(1200,675),(13,20,31));d=ImageDraw.Draw(img);d.text((70,55),"MARTIN RAEBURN",font=font(22,True),fill=(142,183,255));y=103
 for line in wrap(d,title,font(46,True),1060)[:2]:d.text((70,y),line,font=font(46,True),fill=(245,248,252));y+=56
 y+=22;labels=["→"]*3 if kind=="process_card" else (["A","B","C"] if kind=="contrast_card" else ["1","2","3"])
 for i,p in enumerate(points[:3]):
  d.rounded_rectangle((70,y,1130,y+112),radius=18,fill=(24,35,51));d.text((96,y+34),labels[i],font=font(27,True),fill=(142,183,255));ty=y+24
  for line in wrap(d,p,font(30),930)[:2]:d.text((150,ty),line,font=font(30),fill=(232,237,244));ty+=38
  y+=132
 out=io.BytesIO();img.save(out,format="JPEG",quality=90,optimize=True);return out.getvalue()
def ai_json(ai,prompt):
 r=ai.responses.create(model=os.getenv("OPENAI_MODEL","gpt-5-mini"),input=prompt);raw=re.sub(r"^```(?:json)?\s*|\s*```$","",r.output_text.strip(),flags=re.I|re.S);return json.loads(raw)
def main():
 ai=OpenAI(api_key=os.environ["OPENAI_API_KEY"]);state=load_state();local=load_knowledge();sheetfacts=gm.verified_knowledge() if gm.enabled() else [];knowledge={"repository":local,"google_sheet_verified_facts":sheetfacts};topic=content_mix_prompt(state)
 recent=list(dict.fromkeys((gm.recent_posts(100) if gm.enabled() else [])+state.get("original_posts",[])))[-100:];plan=None;text=""
 for _ in range(3):
  plan=ai_json(ai,SYSTEM+f"\nTASK\nCreate one original post. Content lane: {topic}. Verified knowledge: {json.dumps(knowledge)}. Recent posts to avoid repeating: {json.dumps(recent[-20:])}. Prefer a fresh mechanism, trade-off or useful observation.");text=fit_post(str(plan.get("text","")),list(plan.get("hashtags") or []))
  if text and not is_duplicate(text,recent):break
  if gm.enabled() and text:gm.log_content(text,topic,hashlib.sha256(text.lower().encode()).hexdigest()[:16],"rejected","semantic duplicate")
  plan=None
 if not plan or not text:return print("SKIP duplicate/weak post")
 gate=ai_json(ai,MARTIN_VOICE+"\n"+reputation_gate_prompt(text,knowledge))
 if gate.get("publish") is not True:
  if gm.enabled():gm.log_content(text,topic,hashlib.sha256(text.lower().encode()).hexdigest()[:16],"rejected",gate.get("reason","reputation gate"))
  return print("SKIP reputation gate:",gate.get("reason",""))
 tags=[clean_tag(x) for x in plan.get("hashtags",[]) if clean_tag(x)];media=plan.get("media","none");title=str(plan.get("card_title","")).strip();points=[str(x).strip() for x in plan.get("card_points",[]) if str(x).strip()];alt=str(plan.get("alt_text","")).strip()
 if media not in {"insight_card","process_card","contrast_card"} or not title or len(points)<2 or not alt:media="none"
 thread=[fit_post(str(x),[]) for x in (plan.get("thread") or []) if str(x).strip()][:4]
 if DRY_RUN:return print("DRY RUN TEXT:",text,"\nDRY RUN MEDIA:",media,"\nDRY RUN THREAD:",thread)
 b=Client();b.login(HANDLE,os.environ["BSKY_APP_PASSWORD"]);result=b.send_image(text=text,image=make_card(title,points,media),image_alt=alt,langs=["en-GB"]) if media!="none" else b.send_post(text=text,langs=["en-GB"]);parent=result
 for c in thread:
  pref=models.ComAtprotoRepoStrongRef.Main(uri=parent.uri,cid=parent.cid);root=models.ComAtprotoRepoStrongRef.Main(uri=result.uri,cid=result.cid);parent=b.send_post(c,reply_to=models.AppBskyFeedPost.ReplyRef(parent=pref,root=root),langs=["en-GB"])
 state.setdefault("original_posts",[]).append(text);state["original_posts"]=state["original_posts"][-100:];state.setdefault("content_topics",[]).append(topic);state["content_topics"]=state["content_topics"][-100:];save_state(state)
 if gm.enabled():gm.log_post(result.uri,text,topic,tags,media,thread);gm.log_content(text,topic,hashlib.sha256(text.lower().encode()).hexdigest()[:16],"published","")
 print(result.uri)
if __name__=="__main__":main()
