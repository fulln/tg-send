# tg-send — Claude Code Skill

[中文文档](./README_CN.md)

A Claude Code skill (+ standalone Python script) that publishes Obsidian/Markdown documents to a Telegram channel.

- **Text-only articles**: sent directly as Telegram messages
- **Articles with images**: images are uploaded to Telegram (via private chat) to get hosted URLs, then a Telegraph article is created and the link is posted to the channel

Published message format: `📄 Title + (Telegraph link) + #hashtags`

After publishing, the source file's frontmatter is updated with `published.telegram: <date>`.

---

## Why Bot API instead of Telegram Application API?

Telegram offers two ways to send messages programmatically:

| Method | Description |
|---|---|
| **Application API** (MTProto) | Uses `api_id` + `api_hash`, acts as a real user account — most powerful |
| **Bot API** | Uses a Bot Token — simpler, HTTPS-only |

The Application API requires phone number verification on [my.telegram.org](https://my.telegram.org) to obtain `api_id`. This page is **blocked or unreliable for many IP ranges** (especially when behind a VPN/proxy in China), making registration consistently fail.

The Bot API is pure HTTPS against `api.telegram.org` — **it works reliably through any proxy** that can reach that endpoint.

So this tool uses:
1. Bot Token → Bot API to post messages to the channel
2. Images are sent to the bot's private chat with you (`sendPhoto`) to obtain a Telegram-hosted CDN URL — no third-party image hosting needed

---

## Usage

### As a standalone script

```bash
# copy config
cp .env.example .env
# fill in your values, then:

python3 tg_send.py life/ai/my-article.md
python3 tg_send.py life/ai/my-article.md #AI #tools
```

### As a Claude Code skill

Copy the skill file to your commands directory:

```bash
cp tg-send-skill.md ~/.claude/commands/tg-send.md
```

Then in Claude Code:

```
/tg-send life/ai/my-article.md
/tg-send life/ai/my-article.md #AI #tools
```

---

## Config

Set via environment variables or a `.env` file in the same directory as `tg_send.py`:

```ini
TG_BOT_TOKEN=YOUR_BOT_TOKEN
TG_CHANNEL_ID=YOUR_CHANNEL_ID        # e.g. -1001234567890
TG_USER_ID=YOUR_TELEGRAM_USER_ID     # your personal chat ID
TG_ATTACHMENT_DIR=/path/to/attachments
TG_VAULT_ROOT=/path/to/your/vault
```

| Variable | How to get |
|---|---|
| `TG_BOT_TOKEN` | Create a bot via [@BotFather](https://t.me/BotFather) |
| `TG_CHANNEL_ID` | Add bot as admin to channel; get ID via [@userinfobot](https://t.me/userinfobot) |
| `TG_USER_ID` | Message [@userinfobot](https://t.me/userinfobot) |
| `TG_ATTACHMENT_DIR` | Where your Obsidian images are stored |
| `TG_VAULT_ROOT` | Root of your Markdown vault (for relative paths) |

### Bot permissions required

- Channel: **Post Messages** (admin)
- Start a private chat with your bot first (so it can send you photos)

---

## How it works

```
Markdown file
    │
    ├─ no images ──► sendMessage to channel (chunked at 3800 chars)
    │
    └─ has images ──► sendPhoto to private chat → getFile → Telegram CDN URL
                      │
                      └─► Build Telegraph nodes (text + inline images)
                          │
                          └─► createPage on telegra.ph
                              │
                              └─► sendMessage to channel with article link + hashtags
```

---

## Frontmatter support

Tags are auto-extracted from the file's frontmatter (both formats supported):

```yaml
# inline
tags: AI, tools

# YAML list
tags:
  - AI
  - tools
```

After publish, the frontmatter is updated:

```yaml
published:
  telegram: 2026-03-17
```

---

## Requirements

- Python 3 (stdlib only, no pip install needed)
- `curl`
- `sips` for PNG→JPEG conversion (macOS built-in; on Linux use `convert` from ImageMagick)
