"""Autonomous, rate-limited Bluesky professional presence for @mraeburn.link."""
from __future__ import annotations

import json, os, random, re
from datetime import datetime, timezone
from pathlib import Path

from atproto import Client, models
from voice import MARTIN_VOICE

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


def state_load():
    if not STATE_FILE.exists(): return {"seen": [], "followed": [], "liked": [], "replied": [], "posts": []}
    try: return json.loads(STATE_FILE.read_text())
    except Exception: return {"seen": [], "followed": [], "liked": [], "replied": [], "posts": []}


def state_save(s):
    STATE_FILE.write_text(json.dumps(s, indent=2, sort_keys=True) + "\n")


def ai(prompt: str, max_chars=290):
    key = os.getenv("OPENAI_API_KEY")
    if not key: return None
    from openai import OpenAI
    c = OpenAI(api_key=key)
    r = c.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
        input=MARTIN_VOICE + "\n\nTASK\n" + prompt,
    )
    text = r.output_text.strip().replace("\r", "")
    if text.upper().startswith("NO_REPLY"):
        return None
    return text[:max_chars].rstrip()


def ai_json(prompt: str):
    raw = ai(prompt, max_chars=1200)
    if not raw: return None
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I)
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def safe_text(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:600]


def engagement_decision(author, txt, topic):
    return ai_json(
        f"Topic discovered via search: {topic}\n"
        f"Author: @{author.handle}\n"
        f"Display name: {getattr(author, 'display_name', '') or ''}\n"
        f"Post: {txt}\n\n"
        "Act as a conservative reputation filter for Martin Raeburn's professional Bluesky account. "
        "Return JSON only with booleans like and follow plus a short reason. "
        "LIKE only when this individual post is genuinely relevant, substantive, credible-looking, and something Martin could reasonably signal approval/interest in. "
        "FOLLOW only when the author appears to be a worthwhile ongoing professional source or peer in AI, automation, software, technology leadership or entrepreneurship. "
        "Do not follow merely because one post is relevant. Reject spam, engagement bait, promotional noise, generic news/repost aggregators, low-information posts, suspicious accounts, partisan political campaigning, outrage/rage bait, and content where context is too weak to make a sound decision. "
        "When uncertain, set the action false. Do not infer facts about the author that are not present. "
        'Schema: {"like": false, "follow": false, "reason": "brief reason"}'
    )


def main():
    client = Client()
    client.login(HANDLE, PASSWORD)
    me = client.get_profile(HANDLE)
    state = state_load()
    seen = set(state.get("seen", []))
    followed = set(state.get("followed", []))
    liked = set(state.get("liked", []))
    replied = set(state.get("replied", []))

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

        if replies < MAX_REPLIES and p.uri not in replied:
            reply = ai(
                f"Topic discovered via search: {topic}\n"
                f"Post by @{p.author.handle}: {txt}\n\n"
                "Decide first whether Martin has a genuinely useful contribution. "
                "If not, output exactly NO_REPLY. If yes, write one natural Bluesky reply only. "
                "It should normally be 1-3 sentences and must add substance rather than generic agreement. "
                "Avoid partisan political persuasion and do not mention automation or explain your decision."
            )
            if reply:
                print("REPLY", p.author.handle, reply)
                if not DRY_RUN:
                    parent = models.ComAtprotoRepoStrongRef.Main(uri=p.uri, cid=p.cid)
                    root_uri = getattr(getattr(p.record, "reply", None), "root", None)
                    root = root_uri if root_uri else parent
                    client.send_post(reply, reply_to=models.AppBskyFeedPost.ReplyRef(parent=parent, root=root))
                    replied.add(p.uri)
                replies += 1

        decision = None
        needs_like = likes < MAX_LIKES and p.uri not in liked
        needs_follow = follows < MAX_FOLLOWS and p.author.did not in followed
        if needs_like or needs_follow:
            decision = engagement_decision(p.author, txt, topic)
            if decision:
                print("FILTER", p.author.handle, decision.get("reason", ""))

        if needs_like and decision and decision.get("like") is True:
            print("LIKE", p.author.handle)
            if not DRY_RUN:
                client.like(p.uri, p.cid)
                liked.add(p.uri)
            likes += 1

        if needs_follow and decision and decision.get("follow") is True:
            print("FOLLOW", p.author.handle)
            if not DRY_RUN:
                client.follow(p.author.did)
                followed.add(p.author.did)
            follows += 1

        if replies >= MAX_REPLIES and follows >= MAX_FOLLOWS and likes >= MAX_LIKES: break

    state["seen"] = list(seen)[-1500:]
    state["followed"] = list(followed)[-1000:]
    state["liked"] = list(liked)[-1500:]
    state["replied"] = list(replied)[-1500:]
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    state_save(state)


if __name__ == "__main__": main()
