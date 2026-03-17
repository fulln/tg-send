#!/usr/bin/env python3
"""
tg-send: Publish Markdown/Obsidian notes to a Telegram channel.

- Text-only articles → sent directly as Telegram messages
- Articles with images → Telegraph article (images hosted on Telegram CDN)

Usage:
    python3 tg_send.py <file> [#tag1 #tag2 ...]

Config via environment variables:
    TG_BOT_TOKEN        Telegram bot token (from @BotFather)
    TG_CHANNEL_ID       Target channel ID (e.g. -1001234567890)
    TG_USER_ID          Your personal Telegram user ID (for image hosting)
    TG_ATTACHMENT_DIR   Local directory where Obsidian attachments are stored
    TG_VAULT_ROOT       Root directory of your Markdown vault (for relative paths)

Or create a .env file in the same directory (KEY=VALUE, one per line).
"""

import subprocess, time, json, urllib.parse, os, re, sys
from datetime import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

def load_env(path=None):
    env_file = path or Path(__file__).parent / '.env'
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

load_env()

TOKEN          = os.environ.get('TG_BOT_TOKEN', '')
CHANNEL_ID     = os.environ.get('TG_CHANNEL_ID', '')
USER_ID        = os.environ.get('TG_USER_ID', '')
ATTACHMENT_DIR = os.environ.get('TG_ATTACHMENT_DIR', '')
VAULT_ROOT     = os.environ.get('TG_VAULT_ROOT', str(Path.home()))

if not all([TOKEN, CHANNEL_ID, USER_ID]):
    print('Error: TG_BOT_TOKEN, TG_CHANNEL_ID, TG_USER_ID must be set.')
    print('Set them as environment variables or in a .env file.')
    sys.exit(1)

# ── Args ──────────────────────────────────────────────────────────────────────

args = sys.argv[1:]
if not args:
    print('Usage: tg_send.py <file> [#tag1 #tag2 ...]')
    sys.exit(1)

filepath = args[0]
extra_tags_str = ' '.join(args[1:])

if not filepath.startswith('/'):
    filepath = os.path.join(VAULT_ROOT, filepath)

if not os.path.exists(filepath):
    print(f'Error: file not found: {filepath}')
    sys.exit(1)

title = os.path.splitext(os.path.basename(filepath))[0]

with open(filepath, 'r') as f:
    raw = f.read()

# ── Parse frontmatter ─────────────────────────────────────────────────────────

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
            if val:  # inline: tags: a, b
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
for t in re.findall(r'#(\w+)', extra_tags_str):
    if t not in all_tags:
        all_tags.append(t)

tag_str = ' '.join(f'#{t}' for t in all_tags)

# ── Image helpers ─────────────────────────────────────────────────────────────

IMG_PAT = re.compile(r'!\[.*?\]\((.*?)\)')

def resolve_image(img_ref):
    img_ref = img_ref.replace('%20', ' ')
    img_file = (img_ref.replace('attachment/', '')
                if img_ref.startswith('attachment/')
                else os.path.basename(img_ref))
    full_path = os.path.join(ATTACHMENT_DIR, img_file) if ATTACHMENT_DIR else img_ref
    return full_path if os.path.exists(full_path) else None

def upload_get_tg_url(img_path):
    """Upload image to Telegram private chat, return CDN URL via getFile."""
    r = subprocess.run(
        ['curl', '-s', '-X', 'POST',
         f'https://api.telegram.org/bot{TOKEN}/sendPhoto',
         '-F', f'chat_id={USER_ID}',
         '-F', f'photo=@{img_path}'],
        capture_output=True, text=True
    )
    data = json.loads(r.stdout)
    if not data.get('ok'):
        print(f'  Upload failed: {data.get("description")}')
        return None
    file_id = max(data['result']['photo'], key=lambda p: p['file_size'])['file_id']
    r2 = subprocess.run(
        ['curl', '-s', f'https://api.telegram.org/bot{TOKEN}/getFile?file_id={file_id}'],
        capture_output=True, text=True
    )
    fp = json.loads(r2.stdout)['result']['file_path']
    return f'https://api.telegram.org/file/bot{TOKEN}/{fp}'

local_images = [resolve_image(m.group(1)) for m in IMG_PAT.finditer(body)]
has_images = any(p for p in local_images if p)

# ── Telegram send helpers ─────────────────────────────────────────────────────

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

def send_chunked(text, chunk_size=3800):
    chunks, current = [], ""
    for line in text.split('\n'):
        if len(current) + len(line) + 1 > chunk_size:
            chunks.append(current.strip())
            current = line + '\n'
        else:
            current += line + '\n'
    if current.strip():
        chunks.append(current.strip())
    for chunk in chunks:
        res = send_message(chunk)
        print('  text ✓' if res.get('ok') else f'  text failed: {res.get("description")}')
        time.sleep(0.5)

# ── Telegraph helpers ─────────────────────────────────────────────────────────

def text_to_nodes(text):
    nodes = []
    for para in re.split(r'\n{2,}', text.strip()):
        para = para.strip()
        if not para:
            continue
        h = re.match(r'^(#{1,6})\s+(.*)', para)
        if h:
            nodes.append({"tag": 'h3' if len(h.group(1)) <= 2 else 'h4',
                          "children": [h.group(2)]})
        else:
            lines = para.split('\n')
            children = []
            for i, line in enumerate(lines):
                if line.strip():
                    children.append(line)
                if i < len(lines) - 1:
                    children.append({"tag": "br"})
            if children:
                nodes.append({"tag": "p", "children": children})
    return nodes

def publish_telegraph(title, nodes):
    r = subprocess.run(
        ['curl', '-s', 'https://api.telegra.ph/createAccount',
         '--data', 'short_name=tg-send&author_name=tg-send'],
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
    return data['result']['url'] if data.get('ok') else None

# ── Main flow ─────────────────────────────────────────────────────────────────

print(f'Publishing: {title}')
print(f'Tags: {tag_str or "(none)"}')
print(f'Mode: {"image+text (Telegraph)" if has_images else "text-only"}')

page_url = None

if not has_images:
    msg = f'📄 {title}\n\n{body.strip()}'
    if tag_str:
        msg += f'\n\n{tag_str}'
    send_chunked(msg)

else:
    # Upload images
    img_url_map = {}
    for m in IMG_PAT.finditer(body):
        local = resolve_image(m.group(1))
        if local and local not in img_url_map:
            print(f'  Uploading {os.path.basename(local)}...')
            url = upload_get_tg_url(local)
            if url:
                img_url_map[local] = url
                print(f'  image ✓')

    # Build Telegraph nodes
    nodes, last_end = [], 0
    for m in IMG_PAT.finditer(body):
        if body[last_end:m.start()].strip():
            nodes.extend(text_to_nodes(body[last_end:m.start()]))
        local = resolve_image(m.group(1))
        url = img_url_map.get(local) if local else None
        if url:
            nodes.append({"tag": "img", "attrs": {"src": url}})
        last_end = m.end()
    if body[last_end:].strip():
        nodes.extend(text_to_nodes(body[last_end:]))

    page_url = publish_telegraph(title, nodes)
    if not page_url:
        print('Telegraph publish failed'); sys.exit(1)
    print(f'  Telegraph ✓ {page_url}')

    msg = f'📄 {title}\n\n{page_url}'
    if tag_str:
        msg += f'\n\n{tag_str}'
    res = send_message(msg)
    print('  channel ✓' if res.get('ok') else f'  channel failed: {res.get("description")}')

# ── Update frontmatter ────────────────────────────────────────────────────────

today = datetime.now().strftime('%Y-%m-%d')
with open(filepath, 'r') as f:
    content_raw = f.read()

fm = re.match(r'^(---\n)(.*?)(\n---\n)', content_raw, re.DOTALL)
if fm:
    fb = fm.group(2)
    rest = content_raw[fm.end():]

    if re.search(r'^published:', fb, re.MULTILINE):
        if re.search(r'^\s+telegram:', fb, re.MULTILINE):
            fb = re.sub(r'(^\s+telegram:).*$', rf'\1 {today}', fb, flags=re.MULTILINE)
        else:
            fb = re.sub(r'^(published:.*?)(\n(?!\s)|\Z)',
                        rf'\1\n  telegram: {today}\2', fb, flags=re.MULTILINE | re.DOTALL)
    else:
        fb = fb.rstrip() + f'\npublished:\n  telegram: {today}\n'

    if all_tags and re.search(r'^tags:\s*$', fb, re.MULTILINE):
        tag_lines = '\n'.join(f'  - {t}' for t in all_tags)
        fb = re.sub(r'^tags:\s*$', f'tags:\n{tag_lines}', fb, flags=re.MULTILINE)

    with open(filepath, 'w') as f:
        f.write(fm.group(1) + fb + fm.group(3) + rest)
    print(f'  frontmatter ✓  published.telegram: {today}')

print('Done.')
