"""Publish one useful original post. Designed for scheduled GitHub Actions runs."""
import os, random
from atproto import Client
from openai import OpenAI

HANDLE = os.getenv("BSKY_HANDLE", "mraeburn.link")
PROMPTS = [
    "Share one practical observation about where AI automation creates real business value versus theatre.",
    "Share one concise lesson about building software products around a real operational problem.",
    "Share a thoughtful observation about emerging technology adoption in established organisations.",
    "Share one useful principle for entrepreneurs deciding what to automate and what to keep human.",
    "Share one concise technology leadership insight based on first principles; do not invent personal anecdotes."
]
VOICE = """Write as Martin Raeburn, Group Managing Director of The Raeburn Group. British English.
Professional but human. AI, automation, software, emerging technology and entrepreneurship. Maximum 280 characters.
No invented facts or personal anecdotes, politics, hype, engagement bait, generic motivational language, or unnecessary hashtags."""

def main():
    ai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    r = ai.responses.create(model=os.getenv("OPENAI_MODEL", "gpt-5-mini"), input=VOICE + "\n\n" + random.choice(PROMPTS))
    text = r.output_text.strip()[:280].rstrip()
    if os.getenv("DRY_RUN", "true").lower() == "true":
        print("DRY RUN:", text); return
    b = Client(); b.login(HANDLE, os.environ["BSKY_APP_PASSWORD"])
    result = b.send_post(text=text, langs=["en-GB"])
    print(result.uri)

if __name__ == "__main__": main()
