# 发送 Markdown 文档到 Telegram 频道

- **纯文字**：直接分段发送到频道
- **含图片**：上传图片到私聊获取 Telegram 托管 URL，生成 Telegraph 图文文章，发送链接到频道

发送消息格式：`📄 标题 + (Telegraph链接) + hashtag`

## 用法

```
/tg-send <文件路径> [#tag1 #tag2 ...]
```

hashtag 可从文件 frontmatter `tags:` 字段自动提取，也可在命令行额外追加。

## 执行步骤

用 Bash 工具运行以下 Python 脚本（替换 `$FILEPATH` 和 `$EXTRA_TAGS`）：

```python
import subprocess, time, json, urllib.parse, os, re
from datetime import datetime

# ── 配置区 ──────────────────────────────────────────
TOKEN          = "YOUR_BOT_TOKEN"
CHANNEL_ID     = "YOUR_CHANNEL_ID"        # e.g. -1001234567890
USER_ID        = "YOUR_TELEGRAM_USER_ID"  # 用于图片托管的私聊 ID
ATTACHMENT_DIR = "/path/to/attachments"   # Obsidian attachment 目录
VAULT_ROOT     = "/path/to/vault"         # Markdown 仓库根目录
# ────────────────────────────────────────────────────

filepath = "$FILEPATH"
extra_tags = "$EXTRA_TAGS"

if not filepath.startswith('/'):
    filepath = os.path.join(VAULT_ROOT, filepath)

title = os.path.splitext(os.path.basename(filepath))[0]

with open(filepath, 'r') as f:
    raw = f.read()

# 1. 解析 frontmatter，提取 tags（支持单行和多行列表），去掉 meta 块
frontmatter_tags = []
body = raw
fm_match = re.match(r'^---\n(.*?)\n---\n', raw, re.DOTALL)
if fm_match:
    fm_text = fm_match.group(1)
    in_tags = False
    for line in fm_text.split('\n'):
        if line.startswith('tags:'):
            in_tags = True
            val = line.replace('tags:', '').strip()
            if val:
                frontmatter_tags = [t.strip().lstrip('#') for t in val.split(',') if t.strip()]
                in_tags = False
        elif in_tags:
            m = re.match(r'^\s+-\s+(.*)', line)
            if m:
                frontmatter_tags.append(m.group(1).strip().lstrip('#'))
            elif line and not line.startswith(' '):
                in_tags = False
    body = raw[fm_match.end():]

all_tags = list(frontmatter_tags)
for t in re.findall(r'#(\w+)', extra_tags):
    if t not in all_tags:
        all_tags.append(t)

tag_str = ' '.join(f'#{t}' for t in all_tags)

# 2. 判断是否含有本地图片
IMG_PAT = re.compile(r'!\[.*?\]\((.*?)\)')

def resolve_image(img_ref):
    img_ref = img_ref.replace('%20', ' ')
    img_file = img_ref.replace('attachment/', '') if img_ref.startswith('attachment/') else os.path.basename(img_ref)
    full_path = os.path.join(ATTACHMENT_DIR, img_file)
    return full_path if os.path.exists(full_path) else None

local_images = [resolve_image(m.group(1)) for m in IMG_PAT.finditer(body)]
has_images = any(p for p in local_images if p)

# 3. 发送函数
def send_message(msg):
    data = urllib.parse.urlencode({'chat_id': CHANNEL_ID, 'text': msg}).encode()
    r = subprocess.run(
        ['curl', '-s', '-X', 'POST',
         f'https://api.telegram.org/bot{TOKEN}/sendMessage',
         '-H', 'Content-Type: application/x-www-form-urlencoded',
         '--data', data.decode()],
        capture_output=True, text=True
    )
    return json.loads(r.stdout)

def send_chunked(text):
    chunks, current = [], ""
    for line in text.split('\n'):
        if len(current) + len(line) + 1 > 3800:
            chunks.append(current.strip())
            current = line + '\n'
        else:
            current += line + '\n'
    if current.strip():
        chunks.append(current.strip())
    for chunk in chunks:
        res = send_message(chunk)
        print('文字 ✓' if res.get('ok') else f'文字失败: {res.get("description")}')
        time.sleep(0.5)

if not has_images:
    # ── 纯文字：直接发消息 ──
    print('纯文字模式')
    msg = f'📄 {title}\n\n{body.strip()}'
    if tag_str:
        msg += f'\n\n{tag_str}'
    send_chunked(msg)
    page_url = None

else:
    # ── 图文：Telegraph 流程 ──
    print('图文模式，上传图片中...')

    def upload_get_tg_url(img_path):
        r = subprocess.run(
            ['curl', '-s', '-X', 'POST',
             f'https://api.telegram.org/bot{TOKEN}/sendPhoto',
             '-F', f'chat_id={USER_ID}',
             '-F', f'photo=@{img_path}'],
            capture_output=True, text=True
        )
        data = json.loads(r.stdout)
        if not data.get('ok'):
            print(f'上传失败: {data.get("description")}'); return None
        file_id = max(data['result']['photo'], key=lambda p: p['file_size'])['file_id']
        r2 = subprocess.run(
            ['curl', '-s', f'https://api.telegram.org/bot{TOKEN}/getFile?file_id={file_id}'],
            capture_output=True, text=True
        )
        fp = json.loads(r2.stdout)['result']['file_path']
        return f'https://api.telegram.org/file/bot{TOKEN}/{fp}'

    img_url_map = {}
    for m in IMG_PAT.finditer(body):
        local = resolve_image(m.group(1))
        if local and local not in img_url_map:
            url = upload_get_tg_url(local)
            if url:
                img_url_map[local] = url
                print(f'图片上传 ✓ {os.path.basename(local)}')

    def text_to_nodes(text):
        nodes = []
        for para in re.split(r'\n{2,}', text.strip()):
            para = para.strip()
            if not para: continue
            h = re.match(r'^(#{1,6})\s+(.*)', para)
            if h:
                nodes.append({"tag": 'h3' if len(h.group(1)) <= 2 else 'h4', "children": [h.group(2)]})
            else:
                lines = para.split('\n')
                children = []
                for i, line in enumerate(lines):
                    if line.strip(): children.append(line)
                    if i < len(lines) - 1: children.append({"tag": "br"})
                if children: nodes.append({"tag": "p", "children": children})
        return nodes

    nodes, last_end = [], 0
    for m in IMG_PAT.finditer(body):
        if body[last_end:m.start()].strip():
            nodes.extend(text_to_nodes(body[last_end:m.start()]))
        local = resolve_image(m.group(1))
        url = img_url_map.get(local) if local else None
        if url: nodes.append({"tag": "img", "attrs": {"src": url}})
        last_end = m.end()
    if body[last_end:].strip():
        nodes.extend(text_to_nodes(body[last_end:]))

    r = subprocess.run(
        ['curl', '-s', 'https://api.telegra.ph/createAccount', '--data', 'short_name=TIL&author_name=fulln'],
        capture_output=True, text=True
    )
    tg_token = json.loads(r.stdout)['result']['access_token']

    r = subprocess.run(
        ['curl', '-s', 'https://api.telegra.ph/createPage',
         '--data-urlencode', f'access_token={tg_token}',
         '--data-urlencode', f'title={title}',
         '--data-urlencode', f'content={json.dumps(nodes, ensure_ascii=False)}',
         '--data-urlencode', 'return_content=false'],
        capture_output=True, text=True
    )
    data = json.loads(r.stdout)
    page_url = data['result']['url'] if data.get('ok') else None
    if not page_url:
        print(f'Telegraph 创建失败: {data}'); exit(1)
    print(f'Telegraph ✓ {page_url}')

    msg = f'📄 {title}\n\n{page_url}'
    if tag_str: msg += f'\n\n{tag_str}'
    res = send_message(msg)
    print('发送 ✓' if res.get('ok') else f'发送失败: {res.get("description")}')

# 4. 回写 frontmatter：published.telegram
today = datetime.now().strftime('%Y-%m-%d')
with open(filepath, 'r') as f:
    content_raw = f.read()
fm_match2 = re.match(r'^(---\n)(.*?)(\n---\n)', content_raw, re.DOTALL)
if fm_match2:
    fm_block = fm_match2.group(2)
    rest = content_raw[fm_match2.end():]
    if re.search(r'^published:', fm_block, re.MULTILINE):
        if re.search(r'^\s+telegram:', fm_block, re.MULTILINE):
            fm_block = re.sub(r'(^\s+telegram:).*$', rf'\1 {today}', fm_block, flags=re.MULTILINE)
        else:
            fm_block = re.sub(r'^(published:.*?)(\n(?!\s)|\Z)', rf'\1\n  telegram: {today}\2', fm_block, flags=re.MULTILINE | re.DOTALL)
    else:
        fm_block = fm_block.rstrip() + f'\npublished:\n  telegram: {today}\n'
    if all_tags and re.search(r'^tags:\s*$', fm_block, re.MULTILINE):
        tag_lines = '\n'.join(f'  - {t}' for t in all_tags)
        fm_block = re.sub(r'^tags:\s*$', f'tags:\n{tag_lines}', fm_block, flags=re.MULTILINE)
    with open(filepath, 'w') as f:
        f.write(fm_match2.group(1) + fm_block + fm_match2.group(3) + rest)
    print(f'frontmatter 已更新 ✓  published.telegram: {today}')
else:
    print('未找到 frontmatter，跳过回写')
```

## 安装

将 `tg-send-skill.md` 复制到 Claude Code commands 目录，并重命名：

```bash
cp tg-send-skill.md ~/.claude/commands/tg-send.md
```

然后编辑文件顶部的配置区，填入你自己的 token 和 ID。
