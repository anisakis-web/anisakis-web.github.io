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
    text = clean_text(open(path, encoding='utf-8', errors='replace').read().replace('\r\n', '\n'))
    meta, body = {}, text
    m = re.match(r'---\n(.*?)\n---\n?', text, re.S)
    if m:
        body = text[m.end():]
        lines = m.group(1).split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            i += 1
            if ':' not in line or line.lstrip().startswith('#') or line[:1] in ' \t':
                continue
            k, v = line.split(':', 1)
            v = v.strip()
            if v == '' and i < len(lines) and lines[i].lstrip().startswith('- '):   # lista de elementos clave: valor
                items = []
                while i < len(lines) and (lines[i][:1] in ' \t-' and lines[i].strip()):
                    s_ = lines[i].strip()
                    i += 1
                    if s_.startswith('- '):
                        items.append({})
                        s_ = s_[2:].strip()
                    if items and ':' in s_:
                        kk, vv = s_.split(':', 1)
                        items[-1][kk.strip()] = clean_text(str(yaml_scalar(vv.strip())))
                meta[k.strip()] = items[:MAX_LINKS]
                continue
            if v in ('|', '|-', '>', '>-'):          # bloque multilínea de YAML
                block = []
                while i < len(lines) and (lines[i][:1] in ' \t' or not lines[i].strip()):
                    block.append(lines[i].strip())
                    i += 1
                v = ('\n' if v[0] == '|' else ' ').join(block).strip()
            else:
                v = yaml_scalar(v)
            meta[k.strip()] = clean_text(str(v))
    return meta, body


def yaml_scalar(v):
    """Valor de una línea YAML: entre comillas dobles (escapes como JSON), simples o sin comillas."""
    if len(v) >= 2 and v[0] == v[-1] == '"':
        try:
            return json.loads(v)
        except ValueError:
            return v[1:-1].replace('\\"', '"').replace('\\\\', '\\')
    if len(v) >= 2 and v[0] == v[-1] == "'":
        return v[1:-1].replace("''", "'")
    return v


def clean_text(t):
    """Quita caracteres de control y sustitutos Unicode sueltos (romperían el HTML, el RSS o la compilación)."""
    return re.sub('[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ud800-\udfff\ufdd0-\ufdef\ufffe\uffff]', '', t)


# Lo que llega del panel de noticias se trata como no fiable (ver README, «Panel de noticias»)
SLUG_OK = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
IMG_OK = re.compile(r'/img/noticias/[A-Za-z0-9._-]+\.(?:webp|jpe?g|png|gif|avif)')
IMG_EXT = ('.webp', '.jpg', '.jpeg', '.png', '.gif', '.avif')
MAX_NEWS_BYTES = 200_000                       # una noticia normal ocupa 2–10 KB
MAX_LINKS = 12                                 # «Fuentes y enlaces» por noticia

# Noticias publicadas antes del panel (19/11/2026): conservan sus enlaces dentro del texto tal como están.
# En las nuevas, el texto no admite enlaces: van en el apartado «Fuentes y enlaces» (campo `enlaces`).
LEGACY_NEWS = {
    '2025-01-07-investigacion-chilena-confirma-expresion-de-alergenos-en-parasitos.md',
    '2025-06-23-el-cambio-climatico-y-las-practicas-de-pesca-aceleran-el-ciclo-del.md',
    '2025-09-06-nuevas-recomendaciones-para-prevenir-el-anisakis.md',
    '2025-09-07-falta-de-informacion-sobre-el-anisakis-entre-los-consumidores-el-caso.md',
    '2025-12-02-alerta-por-parasitos-en-una-caballa-saludable-en-espana.md',
    '2025-12-02-primer-caso-confirmado-de-anisakiasis-en-grecia-tras-una-cena-de-sushi.md',
    '2025-12-15-el-anisakis-esta-presente-en-el-100-de-las-merluzas-europeas-y-en-una.md',
    '2026-01-12-alergia-al-anisakis-una-reaccion-que-puede-llegar-a-ser-grave.md',
    '2026-01-12-anisakis-como-causante-de-alergia-a-la-carne.md',
    '2026-01-13-empresa-espanola-crea-tecnologias-contra-el-parasito-anisakis.md',
    '2026-03-26-retirada-preventiva-por-presencia-extraordinaria-de-anisakis.md',
    '2026-04-27-alerta-sanitaria-infestacion-masiva-de-anisakis-en-pescado-azul.md',
    '2026-06-08-el-gobierno-vasco-lanza-la-campana-frescossi-anisakisno-para-impulsar.md',
    '2026-07-22-descodifican-el-genoma-del-anisakis-la-ciencia-avanza-hacia-un-control.md',
    '2026-09-07-mas-alla-del-96-analisis-cientifico-del-estudio-sobre-parasitos-en-el.md',
    '2026-10-05-inactivacion-termica-del-anisakis-lo-que-revela-el-proyecto-heatsakis.md',
    '2026-10-26-control-del-anisakis-el-papel-de-los-veterinarios-desde-la-lonja-hasta.md',
}

# Comprobación de las direcciones de «Fuentes y enlaces»
LINK_TYPES = {'fuente': ('Fuente', 'Fuentes'), 'video': ('Vídeo relacionado', 'Vídeos relacionados'),
              'enlace': ('Enlace relacionado', 'Enlaces relacionados')}
SHORTENERS = {'bit.ly', 'bitly.com', 't.co', 'tinyurl.com', 'goo.gl', 'ow.ly', 'is.gd', 'buff.ly', 'rebrand.ly',
              'cutt.ly', 'shorturl.at', 'shorturl.fm', 'tiny.cc', 'rb.gy', 's.id', 'v.gd', 'lnkd.in', 'trib.al',
              'dlvr.it', 'shorte.st', 'adf.ly', 'bl.ink', 'short.io', 'qrco.de', 'linktr.ee', 'x.gd', 'urlz.fr'}
RISKY_EXT = ('.exe', '.msi', '.bat', '.cmd', '.com', '.scr', '.ps1', '.vbs', '.js', '.jar', '.apk', '.dmg',
             '.pkg', '.app', '.deb', '.rpm', '.sh', '.zip', '.rar', '.7z', '.gz', '.tgz', '.iso', '.img',
             '.svg', '.hta', '.lnk', '.reg', '.docm', '.xlsm', '.pptm')


def check_external_url(url):
    """Devuelve (url, '') si la dirección es aceptable o (None, motivo) si no. Solo https a un dominio público."""
    from urllib.parse import urlsplit
    u = (url or '').strip()
    if not u or len(u) > 500:
        return None, 'vacía o demasiado larga'
    if not re.fullmatch(r'https://[!#$%&()*+,\-./0-9:;=?@A-Z_a-z~\[\]]+', u):
        return None, 'debe empezar por https:// y no llevar espacios ni caracteres raros'
    try:
        p = urlsplit(u)
        host = (p.hostname or '').lower().rstrip('.')
        port = p.port
    except ValueError:
        return None, 'dirección mal formada'
    if '@' in p.netloc:
        return None, 'lleva usuario o contraseña'
    if port not in (None, 443):
        return None, 'usa un puerto no estándar'
    if not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}', host):
        return None, 'el servidor debe ser un dominio (no una IP ni un nombre interno)'
    if 'xn--' in host:
        return None, 'dominio con caracteres internacionales (posible imitación de otro)'
    if host.endswith(('.local', '.internal', '.localhost', '.test', '.example', '.invalid')):
        return None, 'dominio interno o de pruebas'
    if host in SHORTENERS or any(host.endswith('.' + s) for s in SHORTENERS):
        return None, 'acortador de enlaces (oculta el destino real)'
    if p.path.lower().rstrip('/').endswith(RISKY_EXT):
        return None, 'apunta a un archivo descargable o ejecutable'
    return u, ''


def render_links(items, fname):
    """Bloque «Fuente: …» / «Vídeo relacionado: …» al final de la noticia, con direcciones ya comprobadas."""
    groups = {k: [] for k in LINK_TYPES}
    for it in items if isinstance(items, list) else []:
        kind = it.get('tipo', 'fuente') if it.get('tipo') in LINK_TYPES else 'fuente'
        name = re.sub(r'\s+', ' ', it.get('nombre', '')).strip()[:80]
        url, why = check_external_url(it.get('url', ''))
        if not url:
            print(f'AVISO: {fname}: enlace descartado ({why}): {it.get("url", "")!r}')
            continue
        name = name or (urlsplit_host(url))
        groups[kind].append(f'<a href="{esc(url)}" rel="nofollow noopener noreferrer">{esc(name)}</a>')
    out = []
    for kind, (one, many) in LINK_TYPES.items():
        if groups[kind]:
            out.append(f'<p class="fuentes">{one if len(groups[kind]) == 1 else many}: {", ".join(groups[kind])}</p>')
    return '\n'.join(out)


def urlsplit_host(url):
    from urllib.parse import urlsplit
    return (urlsplit(url).hostname or url).removeprefix('www.')


def safe_url(url):
    """Solo enlaces web (http/https), de correo, o rutas internas de la web. Cualquier otra cosa → None."""
    u = url.strip()
    if re.match(r'(?i)https?://[^\s<>"]+$', u) or re.match(r'(?i)mailto:[^\s<>"]+$', u):
        return u
    if re.match(r'/(?![/\\])[^\s<>"\\]*$', u) or re.match(r'#[\w-]*$', u):
        return u
    return None


def fecha(d):
    return f'{d.day} de {MESES[d.month - 1]} de {d.year}'


def plain(h):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', h))).strip()


# ------------------------------------------------------------------ Markdown (subconjunto)
def md_inline(t, links=True):
    """links=False: los enlaces se publican como texto (noticias nuevas: los enlaces van en «Fuentes y enlaces»)."""
    t = esc(t.replace('\x00', ''), quote=False)
    hold = []                                  # etiquetas ya generadas: no se vuelven a procesar

    def keep(tag):
        hold.append(tag)
        return f'\x00{len(hold) - 1}\x00'

    # Las noticias solo llevan una imagen (la principal, en la cabecera): las imágenes dentro del texto se quitan
    t = re.sub(r'!\[([^\[\]\x00]*)\]\(([^()\s\x00]+)\)', '', t)

    def link(m):
        url = safe_url(html.unescape(m.group(2))) if links else None
        if not url:
            return m.group(1)
        ext = re.match(r'https?://', url) and not re.match(r'https?://(www\.)?anisakis\.com(?=[/:?#]|$)', url)
        return keep(f'<a href="{esc(url)}"' + (' rel="noopener"' if ext else '') + '>') + m.group(1) + keep('</a>')
    t = re.sub(r'\[([^\[\]\x00]+)\]\(([^()\s\x00]+)\)', link, t)
    t = re.sub(r'\*\*((?:[^*\n]|\*(?!\*))+?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'(?<![\w*])\*(?![\s*])([^*\n]+?)(?<!\s)\*(?![\w*])', r'<em>\1</em>', t)
    t = t.replace('  \n', '<br>\n')
    return re.sub(r'\x00(\d+)\x00', lambda m: hold[int(m.group(1))], t)


def markdown(src, links=True):
    out = []
    il = lambda x: md_inline(x, links)
    src = re.sub(r'(?m)^(#{2,4} .*)$', r'\n\1\n', src)      # cada subtítulo, en su propio bloque
    for block in re.split(r'\n\s*\n', src.strip()):
        lines = block.split('\n')
        first = lines[0]
        if re.match(r'#{2,4} ', first):
            n = len(first) - len(first.lstrip('#'))
            out.append(f'<h{n}>{il(first[n:].strip())}</h{n}>')
        elif all(re.match(r'[-*] ', l) for l in lines):
            out.append('<ul>' + ''.join(f'<li>{il(l[2:].strip())}</li>' for l in lines) + '</ul>')
        elif all(re.match(r'\d+\. ', l) for l in lines):
            out.append('<ol>' + ''.join(f'<li>{il(l.split(". ", 1)[1].strip())}</li>' for l in lines) + '</ol>')
        elif all(l.startswith('>') for l in lines):
            out.append('<blockquote><p>' + il('\n'.join(l[1:].lstrip() for l in lines)) + '</p></blockquote>')
        elif re.fullmatch(r'!\[[^\]]*\]\([^)\s]+\)', block.strip()):
            continue                                # imagen suelta en el texto: no se publica (ver md_inline)
        else:
            out.append('<p>' + il(block) + '</p>')
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
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none'; upgrade-insecure-requests">
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
    items, seen = [], set()
    for f in sorted(os.listdir(d)):
        if not f.endswith('.md'):
            continue
        p = os.path.join(d, f)
        if not os.path.isfile(p) or os.path.islink(p):
            print(f'AVISO: {f} se omite (no es un archivo normal)')
            continue
        if os.path.getsize(p) > MAX_NEWS_BYTES:
            print(f'AVISO: {f} se omite (más de {MAX_NEWS_BYTES // 1000} KB)')
            continue
        meta, body = read_doc(os.path.join(d, f))
        # cada campo con su tipo: solo «enlaces» es una lista; el resto, texto
        meta = {k: (v if (k == 'enlaces') == isinstance(v, list) else ([] if k == 'enlaces' else ''))
                for k, v in meta.items()}
        if meta.get('draft', '').lower() in ('true', 'si', 'sí', 'yes'):
            continue
        slug = meta.get('slug') or re.sub(r'^\d{4}-\d{2}-\d{2}-', '', f[:-3])
        if not SLUG_OK.fullmatch(slug) or len(slug) > 120:
            print(f'AVISO: {f} se omite (dirección no válida: {slug!r})')
            continue
        base, n = slug, 2
        while slug in seen:                     # dos noticias con el mismo título: -2, -3…
            slug, n = f'{base}-{n}', n + 1
        seen.add(slug)
        try:
            dt = date.fromisoformat(str(meta.get('date', f[:10]))[:10])
        except ValueError:
            print(f'AVISO: {f} se omite (fecha no válida: {meta.get("date")!r})')
            continue
        image = meta.get('image', '').strip()
        if image and not IMG_OK.fullmatch(image):
            print(f'AVISO: {f}: imagen no válida, se publica sin imagen ({image!r})')
            image = ''
        legacy = f in LEGACY_NEWS
        h = markdown(body, links=legacy)
        links_html = render_links(meta.get('enlaces', []), f)
        if links_html:
            h = h + '\n' + links_html
        title = re.sub(r'\s+', ' ', meta.get('title', '')).strip()[:200] or slug
        summary = re.sub(r'\s+', ' ', meta.get('summary', '')).strip()[:300] or plain(h)[:200]
        items.append({'slug': slug, 'url': f'/noticias/{slug}/', 'title': title, 'date': dt,
                      'image': image, 'summary': summary, 'html': h})
    items.sort(key=lambda n: (n['date'], n['slug']), reverse=True)
    return items


def build():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    news_img = os.path.normcase(os.path.join(ROOT, 'static', 'img', 'noticias'))

    def only_images(folder, names):
        """En la carpeta de imágenes de noticias (la que escribe el panel) solo se publican imágenes:
        un .svg o .html subido ahí podría ejecutar código en el dominio de la web."""
        f = os.path.normcase(folder)
        if f != news_img and not f.startswith(news_img + os.sep):
            return []

        def ok(n):
            p = os.path.join(folder, n)
            return n.lower().endswith(IMG_EXT) and os.path.isfile(p) and not os.path.islink(p)
        bad = [n for n in names if not ok(n)]   # ni carpetas ni enlaces simbólicos, aunque se llamen .webp
        for n in bad:
            print(f'AVISO: static/img/noticias/{n} no se publica (solo se admiten imágenes {", ".join(IMG_EXT)})')
        return bad
    shutil.copytree(os.path.join(ROOT, 'static'), OUT, ignore=only_images)
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
                               '<script type="application/ld+json">'
                               + json.dumps(ld, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
                               + '</script>\n'))
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
