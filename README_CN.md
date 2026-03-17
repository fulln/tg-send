# tg-send — Claude Code Skill

将 Obsidian/Markdown 文档发布到 Telegram 频道的 Claude Code skill（同时提供独立 Python 脚本）。

- **纯文字文章**：直接分段发送到频道
- **含图片文章**：图片上传到 Telegram 私聊获取托管 URL，生成 Telegraph 图文文章，发送链接到频道

发送消息格式：`📄 标题 + (Telegraph 链接) + #hashtag`

发布完成后，自动回写源文件 frontmatter：`published.telegram: <日期>`

---

## 使用方式

### 独立脚本

```bash
# 复制配置文件
cp .env.example .env
# 填入你的配置，然后：

python3 tg_send.py life/ai/my-article.md
python3 tg_send.py life/ai/my-article.md #AI #工具
```

### Claude Code skill

将 skill 文件复制到 Claude Code commands 目录：

```bash
cp tg-send-skill.md ~/.claude/commands/tg-send.md
```

然后在 Claude Code 中直接使用：

```
/tg-send life/ai/my-article.md
/tg-send life/ai/my-article.md #AI #工具
```

---

## 配置

通过环境变量或在 `tg_send.py` 同目录下创建 `.env` 文件配置：

```ini
TG_BOT_TOKEN=你的机器人Token
TG_CHANNEL_ID=目标频道ID        # 例如 -1001234567890
TG_USER_ID=你的Telegram用户ID   # 用于图片托管的私聊 ID
TG_ATTACHMENT_DIR=/path/to/attachments
TG_VAULT_ROOT=/path/to/your/vault
```

| 变量 | 获取方式 |
|---|---|
| `TG_BOT_TOKEN` | 通过 [@BotFather](https://t.me/BotFather) 创建机器人获取 |
| `TG_CHANNEL_ID` | 将 bot 设为频道管理员后，通过 [@userinfobot](https://t.me/userinfobot) 转发消息获取 |
| `TG_USER_ID` | 向 [@userinfobot](https://t.me/userinfobot) 发消息获取你的数字 ID |
| `TG_ATTACHMENT_DIR` | Obsidian 附件存储目录 |
| `TG_VAULT_ROOT` | Markdown 仓库根目录（用于解析相对路径） |

### Bot 权限要求

- 频道：需要**发送消息**权限（设为管理员）
- 先与 bot 私聊发一条消息，确保 bot 可以给你发图片

---

## 工作流程

```
Markdown 文件
    │
    ├─ 无图片 ──► sendMessage 发到频道（超长自动分段，每段 3800 字）
    │
    └─ 有图片 ──► sendPhoto 上传到私聊 → getFile → Telegram CDN URL
                  │
                  └─► 构建 Telegraph nodes（文字 + 图片穿插）
                      │
                      └─► createPage 发布到 telegra.ph
                          │
                          └─► sendMessage 发送文章链接 + hashtag 到频道
```

---

## Frontmatter 支持

自动提取文件 frontmatter 中的 tags（两种格式均支持）：

```yaml
# 单行格式
tags: AI, 工具

# 多行列表格式
tags:
  - AI
  - 工具
```

发布后自动更新 frontmatter：

```yaml
published:
  telegram: 2026-03-17
```

---

## 依赖要求

- Python 3（仅用标准库，无需 pip 安装任何包）
- `curl`
- `sips`（macOS 内置，用于 PNG→JPEG 转换；Linux 上可替换为 ImageMagick 的 `convert`）
