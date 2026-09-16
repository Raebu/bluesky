"""Autonomous, rate-limited Bluesky professional presence for @mraeburn.link."""
from __future__ import annotations

import json, os, random, re
from datetime import datetime, timezone
from pathlib import Path

from atproto import Client, models

HANDLE = os.getenv("BSKY_HANDLE", "mraeburn.link")
PASSWORD = os.environ["BSKY_APP_PASSWORD"]
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
STATE_FILE = Path(os.getenv("STATE_FILE", "state.json"))
TOPICS = [x.strip() for x in os.getenv(
    "TOPICS", "artificial intelligence,AI automation,enterprise software,technology leadership,entrepreneurship"
).split(",") if x.strip()]
MAX_REPLIES = int(os.getenv("MAX_REPLIES_PER_RUN", "2"))
MAX_FOLLOWS = int(os.getenv("MAX_FOLLOWS_PER_RUN", "2"))
MAX_LIKES = int(os.getenv("MAX_LIKES_PER_RUN", "3"))

VOICE = """You write as Martin Raeburn, Group Managing Director of The Raeburn Group.
Focus: AI, automation, software, emerging technology, entrepreneurship and practical business building.
British English. Clear, thoughtful, useful and concise. No hype, fake familiarity, engagement bait,
political persuasion, invented claims, generic praise, hashtags-by-default, or pretending you read material
that was not supplied. Replies must add a concrete observation or useful question."""


def state_load():
    if not STATE_FILE.exists(): return {"seen": [], "followed": [], "posts": []}
    try: return json.loads(STATE_FILE.read_text())
    except Exception: return {"seen": [], "followed": [], "posts": []}


def state_save(s):
    STATE_FILE.write_text(json.dumps(s, indent=2, sort_keys=True) + "\n")


def ai(prompt: str, max_chars=290):
    key = os.getenv("OPENAI_API_KEY")
    if not key: return None
    from openai import OpenAI
    c = OpenAI(api_key=key)
    r = c.responses.create(model=os.getenv("OPENAI_MODEL", "gpt-5-mini"), input=VOICE + "\n\n" + prompt)
    text = r.output_text.strip().replace("\r", "")
    return text[:max_chars].rstrip()


def safe_text(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:600]


def main():
    client = Client()
    client.login(HANDLE, PASSWORD)
    me = client.get_profile(HANDLE)
    state = state_load()
    seen = set(state.get("seen", []))

    candidates = []
    for topic in random.sample(TOPICS, min(3, len(TOPICS))):
        try:
            result = client.app.bsky.feed.search_posts({"q": topic, "limit": 15, "sort": "latest"})
            for p in result.posts:
                if p.uri in seen or p.author.did == me.did: continue
                txt = safe_text(getattr(p.record, "text", ""))
                if len(txt) < 45: continue
                candidates.append((p, txt, topic))
        except Exception as exc:
            print("search failed", topic, exc)

    random.shuffle(candidates)
    replies = follows = likes = 0
    for p, txt, topic in candidates[:20]:
        seen.add(p.uri)
        if replies < MAX_REPLIES:
            reply = ai(f"Topic: {topic}\nPost by @{p.author.handle}: {txt}\nWrite one natural Bluesky reply. Do not mention automation.")
            if reply:
                print("REPLY", p.author.handle, reply)
                if not DRY_RUN:
                    parent = models.ComAtprotoRepoStrongRef.Main(uri=p.uri, cid=p.cid)
                    root_uri = getattr(getattr(p.record, "reply", None), "root", None)
                    root = root_uri if root_uri else parent
                    client.send_post(reply, reply_to=models.AppBskyFeedPost.ReplyRef(parent=parent, root=root))
                replies += 1
        if likes < MAX_LIKES and len(txt) > 80:
            print("LIKE", p.author.handle)
            if not DRY_RUN: client.like(p.uri, p.cid)
            likes += 1
        if follows < MAX_FOLLOWS and p.author.did not in state.get("followed", []):
            print("FOLLOW", p.author.handle)
            if not DRY_RUN: client.follow(p.author.did)
            state.setdefault("followed", []).append(p.author.did)
            follows += 1
        if replies >= MAX_REPLIES and follows >= MAX_FOLLOWS and likes >= MAX_LIKES: break

    state["seen"] = list(seen)[-1500:]
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    state_save(state)


if __name__ == "__main__": main()
