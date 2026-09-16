"""Collect public engagement metrics for Martin's recent Bluesky posts into Google Sheets."""
import os
from datetime import datetime,timezone
from atproto import Client
import gdrive_memory as gm
HANDLE=os.getenv("BSKY_HANDLE","mraeburn.link")
def main():
 if not gm.enabled():return print("Google memory disabled")
 c=Client();c.login(HANDLE,os.environ["BSKY_APP_PASSWORD"]);feed=c.get_author_feed(actor=HANDLE,limit=30).feed;posts={r.get("URI"):r for r in gm.rows("Posts") if r.get("URI")};n=0
 for item in feed:
  p=item.post
  if p.uri not in posts:continue
  meta=posts[p.uri];gm.append("Performance",[datetime.now(timezone.utc).isoformat(),p.uri,getattr(p,"like_count",0) or 0,getattr(p,"repost_count",0) or 0,getattr(p,"reply_count",0) or 0,getattr(p,"quote_count",0) or 0,meta.get("Topic",""),meta.get("Media Type","")]);n+=1
 print("performance snapshots",n)
if __name__=="__main__":main()
