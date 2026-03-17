# tg-send — Claude Code Skill

A Claude Code skill that publishes Obsidian/Markdown documents to a Telegram channel.

- **Text-only articles**: sent directly as Telegram messages
- **Articles with images**: images are uploaded to Telegram (via private chat) to get hosted URLs, then a Telegraph article is created and the link is posted to the channel

Published message format: `📄 Title + (Telegraph link) + #hashtags`

Hashtags are auto-extracted from the file's frontmatter `tags:` field (both inline and YAML list formats supported), and can also be appended via command line.

After publishing, the source file's frontmatter is updated with `published.telegram: <date>`.

## Usage

```
/tg-send <file-path> [#tag1 #tag2 ...]
```

Examples:

```
/tg-send life/ai/my-article.md
/tg-send life/ai/my-article.md #AI #tools
```

## Setup

Copy `tg-send.md` to your Claude Code commands directory:

```bash
cp tg-send.md ~/.claude/commands/tg-send.md
```

Then edit the config section at the top of the script inside `tg-send.md`:

```python
TOKEN       = "YOUR_BOT_TOKEN"         # BotFather token
CHANNEL_ID  = "YOUR_CHANNEL_ID"        # e.g. -1001234567890
USER_ID     = "YOUR_TELEGRAM_USER_ID"  # your personal chat ID (for image hosting)
ATTACHMENT_DIR = "/path/to/your/attachments"  # local image directory
VAULT_ROOT  = "/path/to/your/vault"    # markdown vault root
```

### Getting the values

| Variable | How to get |
|---|---|
| `TOKEN` | Create a bot via [@BotFather](https://t.me/BotFather), copy the token |
| `CHANNEL_ID` | Add your bot as admin to the channel; use `getUpdates` or forward a message to [@userinfobot](https://t.me/userinfobot) |
| `USER_ID` | Message [@userinfobot](https://t.me/userinfobot) to get your numeric ID |
| `ATTACHMENT_DIR` | Path where your Obsidian attachments are stored |

### Bot permissions required

- Channel: **Post Messages** (admin)
- Private chat: bot must be able to send you messages (start the bot first)

## How it works

```
Markdown file
    │
    ├─ no images? ──► sendMessage to channel (chunked at 3800 chars)
    │
    └─ has images? ──► sendPhoto to your private chat → getFile → Telegram CDN URL
                       │
                       └─► Build Telegraph nodes (text + inline images)
                           │
                           └─► createPage on telegra.ph
                               │
                               └─► sendMessage to channel with article link
```

## Frontmatter support

Input file example:

```yaml
---
created: 2026-03-10
tags:
  - AI
  - tools
author: you
published:
  telegram: 2026-03-17   ← written automatically after publish
---
```

## Requirements

- `curl` (pre-installed on macOS/Linux)
- `sips` for image conversion (macOS only; remove that line on Linux)
- Python 3 standard library only (no `pip install` needed)
