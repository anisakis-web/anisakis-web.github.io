#!/usr/bin/env python3
"""Genera la web estática de anisakis.com en la carpeta _site/.

Sin dependencias externas: solo la biblioteca estándar de Python 3.9+.
Uso:  python build.py            → genera _site/
      python build.py --serve    → genera y sirve en http://localhost:8000

Contenido:
  content/noticias/*.md   noticias (cabecera YAML sencilla + texto en Markdown)
  content/paginas/*.html  páginas informativas (cabecera + HTML)
  content/legal/*.html    textos legales (cabecera + HTML)
  static/                 imágenes, CSS, JS e iconos (se copian tal cual)
"""
import html
import json
import os
import re
import shutil
import sys
from datetime import date, datetime, timezone
from email.utils import format_datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, '_site')
SITE = 'https://www.anisakis.com'
NAME = 'Anisakis International Information Site'
SHORT = 'Anisakis IIS'
EMAIL = 'info@anisakis.com'
PER_PAGE = 12
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre']
esc = html.escape


# ------------------------------------------------------------------ lectura de contenido
def read_doc(path):
    """Devuelve (metadatos, cuerpo) de un archivo con cabecera '---' tipo YAML sencillo."""
    text = open(path, encoding='utf-8').read().replace('\r\n', '\n')
    meta, body = {}, text
    m = re.match(r'---\n(.*?)\n---\n?', text, re.S)
    if m:
        body = text[m.end():]
        for line in m.group(1).split('\n'):
            if ':' not in line or line.lstrip().startswith('#'):
                continue
            k, v = line.split(':', 1)
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in '"\'':
                v = v[1:-1].replace('\\"', '"').replace('\\\\', '\\') if v[0] == '"' else v[1:-1].replace("''", "'")
            meta[k.strip()] = v
    return meta, body


def fecha(d):
    return f'{d.day} de {MESES[d.month - 1]} de {d.year}'


def plain(h):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', h))).strip()


# ------------------------------------------------------------------ Markdown (subconjunto)
def md_inline(t):
    t = esc(t, quote=False)
    t = re.sub(r'!\[([^\]]*)\]\(([^)\s]+)\)', lambda m: f'<img src="{m.group(2)}" alt="{m.group(1)}" loading="lazy">', t)

    def link(m):
        label, url = m.group(1), m.group(2).replace('&amp;', '&')
        ext = re.match(r'https?://', url) and not re.match(r'https?://(www\.)?anisakis\.com', url)
        return f'<a href="{esc(url)}"' + (' rel="noopener"' if ext else '') + f'>{label}</a>'
    t = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', link, t)
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])', r'<em>\1</em>', t)
    t = t.replace('  \n', '<br>\n')
    return t


def markdown(src):
    out = []
    for block in re.split(r'\n\s*\n', src.strip()):
        lines = block.split('\n')
        first = lines[0]
        if re.match(r'#{2,4} ', first):
            n = len(first) - len(first.lstrip('#'))
            out.append(f'<h{n}>{md_inline(first[n:].strip())}</h{n}>')
        elif all(re.match(r'[-*] ', l) for l in lines):
            out.append('<ul>' + ''.join(f'<li>{md_inline(l[2:].strip())}</li>' for l in lines) + '</ul>')
        elif all(re.match(r'\d+\. ', l) for l in lines):
            out.append('<ol>' + ''.join(f'<li>{md_inline(l.split(". ", 1)[1].strip())}</li>' for l in lines) + '</ol>')
        elif all(l.startswith('>') for l in lines):
            out.append('<blockquote><p>' + md_inline('\n'.join(l[1:].lstrip() for l in lines)) + '</p></blockquote>')
        elif re.fullmatch(r'!\[[^\]]*\]\([^)\s]+\)', block.strip()):
            out.append('<figure>' + md_inline(block.strip()) + '</figure>')
        else:
            out.append('<p>' + md_inline(block) + '</p>')
    return '\n'.join(out)


# ------------------------------------------------------------------ plantilla
NAV = [('/', 'Inicio'), ('/anisakis/', 'Anisakis'), ('/informacion-cientifica/', 'Información científica'),
       ('/legislacion/', 'Legislación'), ('/noticias/', 'Noticias')]


def layout(path, title, body, desc='', image='', kind='website', extra_head=''):
    full_title = f'{title} · {SHORT}' if title else NAME
    desc = (desc or 'Información rigurosa sobre el Anisakis: biología, riesgos para la salud, legislación y noticias.')[:300]
    url = SITE + path
    img = SITE + (image or '/img/portada.webp')
    nav = ''.join(
        f'<li><a href="{h}"' + (' aria-current="page"' if (h == path or (h != '/' and path.startswith(h))) else '') + f'>{t}</a></li>'
        for h, t in NAV)
    return f'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none'">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="{kind}">
<meta property="og:site_name" content="{NAME}">
<meta property="og:title" content="{esc(title or NAME)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{img}">
<meta property="og:locale" content="es_ES">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#263e8b">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" href="/favicon-32.png" type="image/png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="alternate" type="application/rss+xml" title="Noticias · {SHORT}" href="/noticias/feed.xml">
<link rel="stylesheet" href="/css/site.css">
{extra_head}</head>
<body>
<a class="skip" href="#main">Saltar al contenido</a>
<header class="top">
  <div class="wrap top-in">
    <a class="brand" href="/" aria-label="{NAME} — inicio"><img src="/img/logo-sm.webp" alt="{SHORT}" width="140" height="101"></a>
    <nav aria-label="Principal"><ul>{nav}</ul></nav>
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="foot">
  <div class="wrap foot-in">
    <div><img src="/img/logo-sm.webp" alt="" width="110" height="79" loading="lazy"><p>{NAME}</p></div>
    <div><p>Contacto: <a href="mailto:{EMAIL}">{EMAIL}</a></p>
    <p class="legal"><a href="/aviso-legal/">Aviso legal</a> · <a href="/privacidad/">Privacidad</a> · <a href="/cookies/">Cookies</a></p></div>
  </div>
</footer>
<script src="/js/site.js" defer></script>
</body>
</html>
'''


def card(n):
    img = (f'<img src="{n["image"]}" alt="" loading="lazy" width="600" height="340">' if n['image']
           else '<span class="ph" aria-hidden="true"></span>')
    return (f'<article class="card"><a href="{n["url"]}">{img}<div class="card-b">'
            f'<time datetime="{n["date"].isoformat()}">{fecha(n["date"])}</time>'
            f'<h3>{esc(n["title"])}</h3><p>{esc(n["summary"])}</p><span class="more">Leer más</span></div></a></article>')


# ------------------------------------------------------------------ generación
def write(rel, content):
    p = os.path.join(OUT, rel.strip('/').replace('/', os.sep))
    if rel.endswith('/') or rel == '':
        p = os.path.join(p, 'index.html')
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w', encoding='utf-8', newline='\n').write(content)


def load_news():
    d = os.path.join(ROOT, 'content', 'noticias')
    items = []
    for f in sorted(os.listdir(d)):
        if not f.endswith('.md'):
            continue
        meta, body = read_doc(os.path.join(d, f))
        if meta.get('draft', '').lower() in ('true', 'si', 'sí', 'yes'):
            continue
        slug = meta.get('slug') or re.sub(r'^\d{4}-\d{2}-\d{2}-', '', f[:-3])
        dt = date.fromisoformat(str(meta.get('date', f[:10]))[:10])
        h = markdown(body)
        summary = meta.get('summary') or plain(h)[:200]
        items.append({'slug': slug, 'url': f'/noticias/{slug}/', 'title': meta.get('title', slug), 'date': dt,
                      'image': meta.get('image', ''), 'summary': summary, 'html': h})
    items.sort(key=lambda n: (n['date'], n['slug']), reverse=True)
    return items


def build():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(os.path.join(ROOT, 'static'), OUT)
    news = load_news()
    pages = []  # (url, lastmod) para el sitemap

    # portada
    temas = [
        ('/anisakis/', 'La biología del Anisakis y su ciclo vital en el medio marino.'),
        ('/informacion-cientifica/', 'Los riesgos para la salud pública, desde alergias graves hasta cuadros gastrointestinales.'),
        ('/legislacion/', 'La evolución normativa y legal relacionada con su control.'),
        ('/noticias/', 'Las razones de su expansión en caladeros y especies concretas.'),
        ('/noticias/', 'El impacto económico en la pesca y la distribución.'),
        ('/noticias/', 'El seguimiento de su presencia en los medios de comunicación y la opinión pública.'),
        ('/noticias/', 'Posibles soluciones para reducir su presencia en el mar y en los productos pesqueros.'),
    ]
    home = f'''<section class="hero">
  <picture><source media="(max-width: 700px)" srcset="/img/portada-movil.webp"><img class="hero-bg" src="/img/portada.webp" alt="" width="1728" height="919" fetchpriority="high"></picture>
  <div class="wrap hero-in">
    <img class="hero-logo" src="/img/logo.webp" alt="{SHORT}" width="560" height="404">
    <h1>Anisakis International Information Site</h1>
    <p class="lead">Esta web nace con el objetivo de sensibilizar a la sociedad y a los profesionales sobre los riesgos reales asociados al consumo de pescado contaminado, así como sobre las implicaciones ecológicas, sanitarias, comerciales y legales que conlleva su proliferación.</p>
    <p class="cta"><a class="btn" href="#noticias">Últimas noticias</a> <a class="btn btn-o" href="#contacto">Contacto</a></p>
  </div>
</section>
<section class="band">
  <div class="wrap temas">
    <div class="temas-intro">
      <p class="eyebrow">Qué encontrarás</p>
      <h2>Mantengamos el pescado más saludable librándolo del Anisakis</h2>
      <p>En esta página web, a través de contenidos actualizados y contrastados, abordaremos temas como:</p>
    </div>
    <ol class="topics">{''.join(f'<li><a href="{h}"><span class="num" aria-hidden="true">{i:02d}</span><span class="txt">{esc(t)}</span><span class="arr" aria-hidden="true">→</span></a></li>' for i, (h, t) in enumerate(temas, 1))}</ol>
  </div>
</section>
<section class="wrap" id="noticias">
  <h2>Últimas noticias</h2>
  <div class="cards">{''.join(card(n) for n in news[:6])}</div>
  <p class="center"><a class="btn" href="/noticias/">Ver todas las noticias</a></p>
</section>
<section class="band band-dark" id="contacto">
  <div class="wrap narrow center">
    <h2>Contacto</h2>
    <p>El Anisakis no es un problema menor. Su proliferación está cambiando nuestros hábitos culinarios y afectando a toda la cadena alimentaria del pescado. Aquí encontrarás contenidos actualizados con información relevante, veraz y accesible para todos.</p>
    <p>Puede ponerse en contacto con nosotros a través de <a href="mailto:{EMAIL}">{EMAIL}</a></p>
  </div>
</section>'''
    ld = {'@context': 'https://schema.org', '@type': 'WebSite', 'name': NAME, 'url': SITE + '/', 'inLanguage': 'es'}
    write('/', layout('/', '', home, extra_head=''))
    pages.append(('/', news[0]['date'] if news else None))

    # páginas informativas
    for f in sorted(os.listdir(os.path.join(ROOT, 'content', 'paginas'))):
        meta, body = read_doc(os.path.join(ROOT, 'content', 'paginas', f))
        slug = f.rsplit('.', 1)[0]
        url = f'/{slug}/'
        desc = meta.get('description') or plain(body)[:180]
        write(url, layout(url, meta['title'], f'<article class="wrap narrow page"><h1>{esc(meta["title"])}</h1>\n{body}</article>', desc))
        pages.append((url, None))

    # textos legales
    for f in sorted(os.listdir(os.path.join(ROOT, 'content', 'legal'))):
        meta, body = read_doc(os.path.join(ROOT, 'content', 'legal', f))
        slug = f.rsplit('.', 1)[0]
        url = f'/{slug}/'
        write(url, layout(url, meta['title'], f'<article class="wrap narrow page legal-text"><h1>{esc(meta["title"])}</h1>\n{body}</article>', meta.get('description', '')))
        pages.append((url, None))

    # noticias
    total = max(1, -(-len(news) // PER_PAGE))
    for i in range(total):
        chunk = news[i * PER_PAGE:(i + 1) * PER_PAGE]
        url = '/noticias/' if i == 0 else f'/noticias/pagina/{i + 1}/'
        pager = ''
        if total > 1:
            prev = '' if i == 0 else f'<a href="{"/noticias/" if i == 1 else f"/noticias/pagina/{i}/"}" rel="prev">← Más recientes</a>'
            nxt = '' if i == total - 1 else f'<a href="/noticias/pagina/{i + 2}/" rel="next">Anteriores →</a>'
            pager = f'<nav class="pager" aria-label="Páginas">{prev}<span>Página {i + 1} de {total}</span>{nxt}</nav>'
        body = f'<section class="wrap"><h1>Noticias</h1><div class="cards">{"".join(card(n) for n in chunk)}</div>{pager}</section>'
        write(url, layout(url, 'Noticias' if i == 0 else f'Noticias (página {i + 1})', body,
                          'Actualidad sobre el Anisakis: salud, investigación, pesca y legislación.'))
        pages.append((url, chunk[0]['date'] if chunk else None))
    for idx, n in enumerate(news):
        newer = news[idx - 1] if idx > 0 else None
        older = news[idx + 1] if idx + 1 < len(news) else None
        img = f'<figure class="lead-img"><img src="{n["image"]}" alt="" width="1200" height="680"></figure>' if n['image'] else ''
        ld = {'@context': 'https://schema.org', '@type': 'NewsArticle', 'headline': n['title'][:110],
              'datePublished': n['date'].isoformat(), 'inLanguage': 'es', 'mainEntityOfPage': SITE + n['url'],
              'publisher': {'@type': 'Organization', 'name': NAME, 'logo': {'@type': 'ImageObject', 'url': SITE + '/img/logo.png'}}}
        if n['image']:
            ld['image'] = SITE + n['image']
        nav = '<nav class="pager">' + (f'<a href="{newer["url"]}" rel="prev">← {esc(newer["title"])}</a>' if newer else '<span></span>') + \
              (f'<a href="{older["url"]}" rel="next">{esc(older["title"])} →</a>' if older else '<span></span>') + '</nav>'
        body = (f'<article class="wrap narrow page news"><p class="meta"><a href="/noticias/">Noticias</a> · '
                f'<time datetime="{n["date"].isoformat()}">{fecha(n["date"])}</time></p>'
                f'<h1>{esc(n["title"])}</h1>{img}\n{n["html"]}\n{nav}</article>')
        write(n['url'], layout(n['url'], n['title'], body, n['summary'], n['image'], 'article',
                               f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>\n'.replace('<script type="application/ld+json">', '<script type="application/ld+json">')))
        pages.append((n['url'], n['date']))

    # 404, sitemap, robots, RSS, CNAME
    write('404.html', layout('/404.html', 'Página no encontrada',
                             '<section class="wrap narrow page center"><h1>Página no encontrada</h1>'
                             '<p>La dirección que buscas no existe o ha cambiado.</p>'
                             '<p><a class="btn" href="/">Ir al inicio</a> <a class="btn btn-o" href="/noticias/">Ver noticias</a></p></section>'))
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url, lm in pages:
        sm.append(f'<url><loc>{SITE}{url}</loc>' + (f'<lastmod>{lm.isoformat()}</lastmod>' if lm else '') + '</url>')
    sm.append('</urlset>')
    write('sitemap.xml', '\n'.join(sm) + '\n')
    write('robots.txt', f'User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n')
    items = []
    for n in news[:20]:
        dt = datetime(n['date'].year, n['date'].month, n['date'].day, 9, 0, tzinfo=timezone.utc)
        items.append(f'<item><title>{esc(n["title"])}</title><link>{SITE}{n["url"]}</link><guid>{SITE}{n["url"]}</guid>'
                     f'<pubDate>{format_datetime(dt)}</pubDate><description>{esc(n["summary"])}</description></item>')
    write('noticias/feed.xml', f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>Noticias · {NAME}</title>'
          f'<link>{SITE}/noticias/</link><description>Actualidad sobre el Anisakis</description><language>es</language>'
          + ''.join(items) + '</channel></rss>\n')
    write('CNAME', 'www.anisakis.com\n')
    write('.nojekyll', '')
    print(f'OK: {len(news)} noticias, {len(pages)} páginas en el sitemap → {OUT}')


def serve():
    import http.server
    import functools
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=OUT)
    print('http://localhost:8000  (Ctrl+C para parar)')
    http.server.ThreadingHTTPServer(('127.0.0.1', 8000), h).serve_forever()


if __name__ == '__main__':
    build()
    if '--serve' in sys.argv:
        serve()
