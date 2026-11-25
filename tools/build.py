"""Build the pages: content/*.md -> public/**/index.html (committed; Vercel serves public/ as-is, no build there).

  .venv/bin/python tools/build.py

  content/site.json          name, motto, url, linkedin
  content/pages/<slug>.md    -> /<slug>/        front matter: title, label, object (hero image), description
  content/posts/YYYY-MM-DD-<slug>.md -> /blog/<slug>/   front matter: title, [label], [description], [draft-note]
Also writes /blog/ (index), /latest.json (the post-it on the door), /feed.xml, /404.html.
Lines starting with "TODO" (or inline "TODO: ...") render as yellow placeholder notes; the build lists them.
"""
import json, os, re, html, datetime, glob
import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C, PUB = os.path.join(ROOT, 'content'), os.path.join(ROOT, 'public')
site = json.load(open(os.path.join(C, 'site.json')))
TPL = open(os.path.join(ROOT, 'templates', 'page.html')).read()
todos = []

def front(path):
    txt = open(path).read(); meta = {}
    if txt.startswith('---\n'):
        head, txt = txt[4:].split('\n---\n', 1)
        for line in head.splitlines():
            k, _, v = line.partition(':'); meta[k.strip()] = v.strip()
    return meta, txt

def md(txt, name):
    n = len(re.findall(r'TODO', txt))
    if n: todos.append(f'{n:2d}  {name}')
    out = markdown.markdown(txt, extensions=['fenced_code', 'tables', 'sane_lists'])
    # highlight placeholders in text only (between tags), never inside an attribute like href="TODO-url"
    return re.sub(r'>([^<]*?)(TODO[^<]*)', lambda m: f'>{m.group(1)}<span class="todo">{m.group(2)}</span>', out)

def cook(txt):  # reading time, microwave style
    m = max(1, round(len(re.findall(r'\w+', txt)) / 220)); return f'cook time {m} min'

def page(out, title, content, label='', description='', hero='', meta='', kind='page'):
    vals = dict(site, title=html.escape(title), label=html.escape(label), description=html.escape(description or site['motto']),
                content=content, hero=hero, meta=meta, kind=kind)
    doc = re.sub(r'{{(\w+)}}', lambda m: str(vals.get(m.group(1), '')), TPL)
    path = os.path.join(PUB, out); os.makedirs(os.path.dirname(path), exist_ok=True); open(path, 'w').write(doc)

def hero(obj):
    return f'<img class="hero" src="/img/hero_{obj}.webp" alt="" width="320">' if obj and os.path.exists(f'{PUB}/img/hero_{obj}.webp') else ''

# pages
for p in sorted(glob.glob(f'{C}/pages/*.md')):
    slug = os.path.basename(p)[:-3]; m, txt = front(p)
    page(f'{slug}/index.html', m.get('title', slug), md(txt, f'pages/{slug}.md'), m.get('label', ''), m.get('description', ''), hero(m.get('object')))

# posts
posts = []
for p in sorted(glob.glob(f'{C}/posts/*.md'), reverse=True):
    base = os.path.basename(p)[:-3]; date, slug = base[:10], base[11:]; m, txt = front(p)
    d = datetime.date.fromisoformat(date); when = d.strftime('%d %b %Y').lower()
    note = f'<p class="draft">draft — {html.escape(m["draft-note"])}</p>' if m.get('draft-note') else ''
    if note: todos.append(f' 1  posts/{base}.md (draft-note)')
    page(f'blog/{slug}/index.html', m['title'], note + md(txt, f'posts/{base}.md'), m.get('label', 'from the blog'),
         m.get('description', ''), meta=f'<p class="meta"><time datetime="{date}">{when}</time> · {cook(txt)}</p>', kind='post')
    posts.append(dict(title=m['title'], url=f'/blog/{slug}/', date=date, when=when, cook=cook(txt)))

items = ''.join(f'<li><time datetime="{p["date"]}">{p["when"]}</time><a href="{p["url"]}">{html.escape(p["title"])}</a>'
                f'<span class="cook">{p["cook"]}</span></li>' for p in posts) or '<li>nothing cooked yet.</li>'
page('blog/index.html', 'Blog', f'<ul class="posts">{items}</ul>', 'reheated thoughts', 'Notes from Matteo.', kind='blog')

# the post-it on the microwave door
json.dump({'title': posts[0]['title'], 'url': posts[0]['url']} if posts else None, open(f'{PUB}/latest.json', 'w'))

# feed
esc = html.escape
rss = ''.join(f'<item><title>{esc(p["title"])}</title><link>{site["url"]}{p["url"]}</link><guid>{site["url"]}{p["url"]}</guid>'
              f'<pubDate>{datetime.date.fromisoformat(p["date"]).strftime("%a, %d %b %Y 00:00:00 +0000")}</pubDate></item>' for p in posts)
open(f'{PUB}/feed.xml', 'w').write(f'<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>{esc(site["name"])}</title>'
                                    f'<link>{site["url"]}</link><description>{esc(site["motto"])}</description>{rss}</channel></rss>')

# 404 (Vercel serves public/404.html)
page('404.html', 'Not in here', '<p>Whatever you were looking for, it is not in the microwave. Maybe check the freezer.</p>'
     '<p><a href="/">← back to the microwave</a></p>', '404', kind='page')

print(f'built {len(glob.glob(C + "/pages/*.md"))} pages, {len(posts)} posts')
if todos: print('placeholders left:\n' + '\n'.join(todos))
