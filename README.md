# Martin Raeburn — Bluesky Agent

Autonomous, deliberately rate-limited professional Bluesky presence for **@mraeburn.link**.

It uses Bluesky/AT Protocol APIs rather than browser automation. The agent can discover relevant public posts, draft contextual AI replies, like selectively, follow relevant authors, and publish original professional posts. It keeps per-run limits low to avoid spammy behaviour.

## Required GitHub Actions secrets

Create repository secrets:

- `BSKY_APP_PASSWORD` — a Bluesky **app password**, not your main account password.
- `OPENAI_API_KEY` — used to write original posts and contextual replies.

`BSKY_HANDLE` is already configured as `mraeburn.link`.

## Safety defaults

- Manual workflow runs default to `DRY_RUN=true`.
- Scheduled runs are live once both secrets exist.
- Per engagement run: max 2 replies, 2 follows and 3 likes.
- No automated DMs.
- Prompt explicitly blocks invented personal claims, generic engagement bait and political persuasion.
- Replies are based on the text of the actual candidate post.

## Schedule

GitHub Actions checks at 08:17, 13:17 and 18:17 UTC. The middle run publishes one original post; the other scheduled runs perform restrained discovery/engagement. GitHub scheduled workflows can start later than the exact cron time.

## Test first

Actions → **Bluesky Agent** → Run workflow → choose `engagement` or `post`, leave **Perform live Bluesky writes** off. Review the log. When satisfied, run once with live enabled.

## Configuration

Environment variables include `TOPICS`, `MAX_REPLIES_PER_RUN`, `MAX_FOLLOWS_PER_RUN`, `MAX_LIKES_PER_RUN`, `OPENAI_MODEL` and `DRY_RUN`.

## Notes

This is an initial production-minded baseline. A durable deployment should persist the action register outside the ephemeral Actions filesystem (for example a database or committed state via a dedicated mechanism) before materially increasing activity volumes.
