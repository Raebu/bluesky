"""Publish one useful original Bluesky post with selective discovery tags and media."""
import base64
import io
import json
import os
import random
import re

from atproto import Client
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont

from voice import MARTIN_VOICE

HANDLE = os.getenv("BSKY_HANDLE", "mraeburn.link")
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

PROMPTS = [
    "Make one specific observation about where AI automation creates real business value versus theatre. Connect the technology to an operational or commercial consequence.",
    "Make one concise observation about building software around a real operational problem. Prefer a concrete mechanism or trade-off to general advice.",
    "Make one thoughtful observation about emerging technology adoption in established organisations, including an implementation or second-order consequence people often overlook.",
    "Make one useful observation for entrepreneurs deciding what to automate and what to keep human. Avoid generic productivity advice.",
    "Make one concise technology-leadership observation from first principles. Do not invent personal experience or imply Martin has used a product unless supplied as verified context.",
    "Identify a fashionable assumption in AI or software that deserves a more nuanced view. Challenge the assumption calmly and explain the mechanism, without rage bait.",
]

SYSTEM = MARTIN_VOICE + r"""

For this task return ONLY valid JSON with these keys:
{
  "text": "the Bluesky post",
  "hashtags": ["#Tag"],
  "media": "none" or "insight_card",
  "card_title": "short title or empty string",
  "card_points": ["point one", "point two", "point three"],
  "alt_text": "accessible description or empty string"
}

DISCOVERY AND MEDIA RULES
- Hashtags are optional. Use 0-2 only when they materially improve topic discovery. Never append generic branding tags or use a fixed hashtag set.
- The final text including hashtags must fit within 300 characters. Prefer useful prose over tags.
- Media is optional. Choose none when an image would merely decorate the post.
- Choose insight_card only when a compact visual can add information: a framework, contrast, sequence, trade-off or 2-3 useful takeaways.
- Never create a generic AI-art illustration simply to make a post visual.
- If using an insight card, card_title should be <= 45 characters and card_points should contain 2-3 concise factual/conceptual points supported by the post itself.
- Alt text must describe the information conveyed by the card, not say merely 'graphic' or 'image'.
"""


def clean_tag(tag: str) -> str | None:
    tag = re.sub(r"[^A-Za-z0-9_]", "", str(tag).lstrip("#"))
    return f"#{tag}" if tag else None


def fit_post(text: str, tags: list[str]) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    cleaned = []
    for tag in tags[:2]:
        t = clean_tag(tag)
        if t and t.lower() not in {x.lower() for x in cleaned}:
            cleaned.append(t)
    suffix = (" " + " ".join(cleaned)) if cleaned else ""
    limit = 300 - len(suffix)
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return text + suffix


def font(size: int, bold: bool = False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def wrap(draw, text, fnt, max_width):
    words, lines, line = text.split(), [], ""
    for word in words:
        trial = (line + " " + word).strip()
        if draw.textbbox((0, 0), trial, font=fnt)[2] <= max_width:
            line = trial
        else:
            if line: lines.append(line)
            line = word
    if line: lines.append(line)
    return lines


def make_card(title: str, points: list[str]) -> bytes:
    # Purposefully informational rather than decorative AI art.
    img = Image.new("RGB", (1200, 675), (13, 20, 31))
    d = ImageDraw.Draw(img)
    title_font, body_font, small_font = font(48, True), font(31), font(22, True)
    d.text((70, 58), "MARTIN RAEBURN", font=small_font, fill=(142, 183, 255))
    y = 105
    for line in wrap(d, title, title_font, 1060)[:2]:
        d.text((70, y), line, font=title_font, fill=(245, 248, 252)); y += 58
    y += 25
    for i, point in enumerate(points[:3], 1):
        d.rounded_rectangle((70, y, 1130, y + 112), radius=18, fill=(24, 35, 51))
        d.text((96, y + 34), str(i), font=font(28, True), fill=(142, 183, 255))
        lines = wrap(d, point, body_font, 930)[:2]
        ty = y + 24
        for line in lines:
            d.text((150, ty), line, font=body_font, fill=(232, 237, 244)); ty += 39
        y += 132
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90, optimize=True)
    return out.getvalue()


def generate_plan(ai: OpenAI) -> dict:
    task = (
        "Create ONE standalone Bluesky post in Martin's voice from this seed. "
        "It must make a worthwhile, specific observation rather than generic thought leadership. "
        "Do not invent anecdotes, facts or company experience. Decide intelligently whether hashtags and an informational insight card add value.\n\nSEED: "
        + random.choice(PROMPTS)
    )
    r = ai.responses.create(model=os.getenv("OPENAI_MODEL", "gpt-5-mini"), input=SYSTEM + "\n\n" + task)
    raw = r.output_text.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.S)
    return json.loads(raw)


def main():
    ai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    plan = generate_plan(ai)
    text = fit_post(str(plan.get("text", "")), list(plan.get("hashtags") or []))
    media = plan.get("media", "none")
    title = str(plan.get("card_title", "")).strip()
    points = [str(x).strip() for x in (plan.get("card_points") or []) if str(x).strip()]
    alt = str(plan.get("alt_text", "")).strip()

    if media != "insight_card" or not title or len(points) < 2 or not alt:
        media = "none"

    if DRY_RUN:
        print("DRY RUN TEXT:", text)
        print("DRY RUN MEDIA:", media)
        if media == "insight_card":
            print("DRY RUN CARD:", title, "|", " | ".join(points))
            print("DRY RUN ALT:", alt)
        return

    b = Client()
    b.login(HANDLE, os.environ["BSKY_APP_PASSWORD"])
    if media == "insight_card":
        image = make_card(title, points)
        result = b.send_image(text=text, image=image, image_alt=alt, langs=["en-GB"])
    else:
        result = b.send_post(text=text, langs=["en-GB"])
    print(result.uri)


if __name__ == "__main__":
    main()
