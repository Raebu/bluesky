"""Produce a compact weekly review from persistent agent state."""
import json, os
from pathlib import Path
from datetime import datetime, timezone

STATE = Path(os.getenv("STATE_FILE", "state.json"))
OUT = Path(os.getenv("REVIEW_FILE", "weekly-review.md"))


def main():
    try: s = json.loads(STATE.read_text())
    except Exception: s = {}
    relationships = s.get("relationships", {})
    top = sorted(relationships.values(), key=lambda x: x.get("interactions", 0), reverse=True)[:10]
    lines = [
        "# Bluesky weekly review",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Original posts remembered: {len(s.get('original_posts', []))}",
        f"Posts seen: {len(s.get('seen', []))}",
        f"Posts liked: {len(s.get('liked', []))}",
        f"Posts replied to: {len(s.get('replied', []))}",
        f"Accounts followed: {len(s.get('followed', []))}",
        f"Relationships remembered: {len(relationships)}",
        "",
        "## Most active relationships",
    ]
    lines += [f"- @{x.get('handle','unknown')}: {x.get('interactions',0)} remembered interactions" for x in top] or ["- None yet"]
    lines += ["", "## Recent content mix"]
    lines += [f"- {x}" for x in s.get("content_topics", [])[-12:]] or ["- None yet"]
    OUT.write_text("\n".join(lines) + "\n")
    print(OUT.read_text())

if __name__ == "__main__": main()
