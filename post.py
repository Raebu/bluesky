"""Publish one useful original post. Designed for scheduled GitHub Actions runs."""
import os, random
from atproto import Client
from openai import OpenAI
from voice import MARTIN_VOICE

HANDLE = os.getenv("BSKY_HANDLE", "mraeburn.link")
PROMPTS = [
    "Make one specific observation about where AI automation creates real business value versus theatre. Connect the technology to an operational or commercial consequence.",
    "Make one concise observation about building software around a real operational problem. Prefer a concrete mechanism or trade-off to general advice.",
    "Make one thoughtful observation about emerging technology adoption in established organisations, including an implementation or second-order consequence people often overlook.",
    "Make one useful observation for entrepreneurs deciding what to automate and what to keep human. Avoid generic productivity advice.",
    "Make one concise technology-leadership observation from first principles. Do not invent personal experience or imply Martin has used a product unless supplied as verified context.",
    "Identify a fashionable assumption in AI or software that deserves a more nuanced view. Challenge the assumption calmly and explain the mechanism, without rage bait.",
]


def main():
    ai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    task = (
        "Write ONE standalone Bluesky post in Martin's voice. Maximum 280 characters. "
        "It must contain a worthwhile, specific thought rather than generic thought leadership. "
        "No hashtags by default, no engagement-bait question, no invented anecdote, and no company promotion unless directly necessary.\n\n"
        + random.choice(PROMPTS)
    )
    r = ai.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
        input=MARTIN_VOICE + "\n\nTASK\n" + task,
    )
    text = r.output_text.strip().replace("\r", "")[:280].rstrip()
    if os.getenv("DRY_RUN", "true").lower() == "true":
        print("DRY RUN:", text)
        return
    b = Client()
    b.login(HANDLE, os.environ["BSKY_APP_PASSWORD"])
    result = b.send_post(text=text, langs=["en-GB"])
    print(result.uri)


if __name__ == "__main__": main()
