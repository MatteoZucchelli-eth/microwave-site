"""Build the pages: content/*.md -> public/**/index.html. Runs on every Vercel deploy (see vercel.json), so a post
saved from the browser (a commit to content/) goes live with the next build. Locally:  .venv/bin/python tools/build.py

  content/site.json                     name, motto, url, linkedin
  content/pages/<slug>.md               -> /<slug>/     front matter: title, label, object (header image), description
  content/pages/coffee.md               -> top of /coffee/ (the short about), followed by the posts
  content/coffee/YYYY-MM-DD-<slug>.md   -> /coffee/<slug>/   front matter: title, [postit], [label], [description],
                                           [draft: true] (not published), [draft-note] (published with a yellow note)
Also writes /latest.json (the post-it on the door), /feed.xml, /404.html.
Lines with "TODO" render as yellow placeholder notes; the build lists them.
Generated files are gitignored: Vercel builds them.
"""
import json, os, re, html, datetime, glob
import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C, PUB = os.path.join(ROOT, 'content'), os.path.join(ROOT, 'public')
site = json.load(open(os.path.join(C, 'site.json')))
TPL = open(os.path.join(ROOT, 'templates', 'page.html')).read()
todos = []
rel = lambda p: os.path.relpath(p, ROOT)

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

def page(out, title, content, label='', description='', hero='', meta='', kind='page', file='', editable=False):
    vals = dict(site, title=html.escape(title), label=html.escape(label), description=html.escape(description or site['motto']),
                content=content, hero=hero, meta=meta, kind=kind,
                attrs=f' data-file="{html.escape(file)}"' if file else '',
                scripts='<script src="/edit.js" defer></script>' if editable else '')
    doc = re.sub(r'{{(\w+)}}', lambda m: str(vals.get(m.group(1), '')), TPL)
    path = os.path.join(PUB, out); os.makedirs(os.path.dirname(path), exist_ok=True); open(path, 'w').write(doc)

def hero(obj):
    return f'<img class="hero" src="/img/hero_{obj}.webp" alt="" width="320">' if obj and os.path.exists(f'{PUB}/img/hero_{obj}.webp') else ''

# pages (coffee.md is the top of /coffee/, built below)
for p in sorted(glob.glob(f'{C}/pages/*.md')):
    slug = os.path.basename(p)[:-3]
    if slug == 'coffee': continue
    m, txt = front(p)
    page(f'{slug}/index.html', m.get('title', slug), md(txt, f'pages/{slug}.md'), m.get('label', ''), m.get('description', ''), hero(m.get('object')))

# coffee posts
posts, drafts = [], 0
for p in sorted(glob.glob(f'{C}/coffee/*.md'), reverse=True):
    base = os.path.basename(p)[:-3]; date, slug = base[:10], base[11:]; m, txt = front(p)
    if m.get('draft', '').lower() == 'true': drafts += 1; continue
    when = datetime.date.fromisoformat(date).strftime('%d %b %Y').lower()
    note = f'<p class="draft">draft — {html.escape(m["draft-note"])}</p>' if m.get('draft-note') else ''
    if note: todos.append(f' 1  coffee/{base}.md (draft-note)')
    page(f'coffee/{slug}/index.html', m.get('title', slug), note + md(txt, f'coffee/{base}.md'), m.get('label', 'over coffee'),
         m.get('description', ''), meta=f'<p class="meta"><time datetime="{date}">{when}</time> · {cook(txt)}</p>',
         kind='post', file=rel(p), editable=True)
    posts.append(dict(title=m.get('title', slug), postit=m.get('postit', m.get('title', slug)), url=f'/coffee/{slug}/',
                      date=date, when=when, cook=cook(txt)))

cm, ctxt = front(f'{C}/pages/coffee.md')
items = ''.join(f'<li><time datetime="{p["date"]}">{p["when"]}</time><a href="{p["url"]}">{html.escape(p["title"])}</a>'
                f'<span class="cook">{p["cook"]}</span></li>' for p in posts) or '<li class="empty">nothing brewed yet.</li>'
page('coffee/index.html', cm.get('title', 'Coffee'),
     f'<div class="about">{md(ctxt, "pages/coffee.md")}</div><h2>Written over coffee</h2><ul class="posts">{items}</ul>',
     cm.get('label', ''), cm.get('description', ''), hero(cm.get('object')), kind='coffee',
     file=rel(f'{C}/pages/coffee.md'), editable=True)

# the post-it on the microwave door
json.dump({'title': posts[0]['postit'], 'url': posts[0]['url']} if posts else None, open(f'{PUB}/latest.json', 'w'))

# feed
esc = html.escape
rss = ''.join(f'<item><title>{esc(p["title"])}</title><link>{site["url"]}{p["url"]}</link><guid>{site["url"]}{p["url"]}</guid>'
              f'<pubDate>{datetime.date.fromisoformat(p["date"]).strftime("%a, %d %b %Y 00:00:00 +0000")}</pubDate></item>' for p in posts)
open(f'{PUB}/feed.xml', 'w').write(f'<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>{esc(site["name"])}</title>'
                                    f'<link>{site["url"]}</link><description>{esc(site["motto"])}</description>{rss}</channel></rss>')

# 404 (Vercel serves public/404.html)
page('404.html', 'Not in here', '<p>Whatever you were looking for, it is not in the microwave. Maybe check the freezer.</p>'
     '<p><a href="/">← back to the microwave</a></p>', '404')

print(f'built {len(glob.glob(C + "/pages/*.md"))} pages, {len(posts)} posts' + (f', {drafts} drafts (unpublished)' if drafts else ''))
if todos: print('placeholders left:\n' + '\n'.join(todos))
