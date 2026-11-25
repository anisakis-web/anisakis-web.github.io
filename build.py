#!/usr/bin/env python3
"""Genera la web estática de anisakis.com en la carpeta _site/.

Sin dependencias externas: solo la biblioteca estándar de Python 3.9+.
Uso:  python build.py            → genera _site/
      python build.py --serve    → genera y sirve en http://localhost:8000

Contenido:
  content/noticias/es/*.md  noticias en español (cabecera YAML sencilla + texto en Markdown)
  content/noticias/en/*.md  su versión en inglés, opcional (unidas por «translationKey»)
  content/paginas/*.html    páginas informativas (cabecera + HTML); en inglés, content/en/paginas/
  content/legal/*.html      textos legales (cabecera + HTML); en inglés, content/en/legal/
  static/                 imágenes, CSS, JS e iconos (se copian tal cual)
"""
import hashlib
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
SITE = 'https://anisakis.com'
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
                # formato estricto: «- clave: valor» y «  clave: valor» con la sangría del primer elemento
                items, ok = [], True
                ind = len(lines[i]) - len(lines[i].lstrip())
                while i < len(lines) and (lines[i][:1] in ' \t-' and lines[i].strip()):
                    raw = lines[i]
                    i += 1
                    lead = len(raw) - len(raw.lstrip())
                    s_ = raw.strip()
                    if s_ in ('-', '- ') or (s_.startswith('- ') and lead != ind):
                        ok = False
                        items.append({'__mal_formado': '1'})   # el elemento entero se descarta
                        continue
                    if s_.startswith('- '):
                        items.append({})
                        s_ = s_[2:].strip()
                    elif lead != ind + 2 or not items or ':' not in s_:
                        ok = False
                        if items:
                            items[-1]['__mal_formado'] = '1'
                        continue
                    kk, vv = s_.split(':', 1)
                    kk = kk.strip()
                    if kk in items[-1]:
                        ok = False                      # clave repetida
                    items[-1][kk] = clean_text(str(yaml_scalar(vv.strip())))
                if not ok:
                    warn(f'{os.path.basename(path)}: «{k.strip()}» con formato no válido; se ignoran sus elementos dudosos')
                if k.strip() not in meta:               # si la clave se repite, vale la primera
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


YAML_ESC = {'0': chr(0), 'a': chr(7), 'b': chr(8), 't': chr(9), 'n': chr(10), 'v': chr(11), 'f': chr(12),
            'r': chr(13), 'e': chr(27), ' ': ' ', '"': '"', '/': '/', '\\': '\\', 'N': chr(0x85),
            '_': chr(0xA0), 'L': chr(0x2028), 'P': chr(0x2029), '\t': chr(9)}


def yaml_dq(inner):
    """Escapes de las cadenas YAML entre comillas dobles (los que escribe el panel: \\_ espacio duro, \\N, \\x…)."""
    def rep(m):
        e = m.group(1)
        if e[0] in 'xuU':
            try:
                c = int(e[1:], 16)
                return '' if 0xD800 <= c <= 0xDFFF or c > 0x10FFFF else chr(c)
            except ValueError:
                return ''
        return YAML_ESC.get(e, '')
    return re.sub(r'\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|[\s\S])', rep, inner)


def yaml_scalar(v):
    """Valor de una línea YAML: entre comillas dobles (con sus escapes), simples o sin comillas."""
    if len(v) >= 2 and v[0] == v[-1] == '"':
        return yaml_dq(v[1:-1])
    if len(v) >= 2 and v[0] == v[-1] == "'":
        return v[1:-1].replace("''", "'")
    return v


def clean_text(t):
    """Quita caracteres de control y sustitutos Unicode sueltos (romperían el HTML, el RSS o la compilación)."""
    return re.sub('[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ud800-\udfff\ufdd0-\ufdef\ufffe\uffff]', '', t)


PROBLEMS = []          # avisos de contenido: si hay alguno, la publicación se detiene (y GitHub avisa por correo)


def warn(msg):
    print('AVISO: ' + msg)
    PROBLEMS.append(msg)


# Lo que llega del panel de noticias se trata como no fiable (ver README, «Panel de noticias»)
SLUG_OK = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
IMG_OK = re.compile(r'/img/noticias/[A-Za-z0-9._-]+\.(?:webp|jpe?g|png|gif|avif)')
IMG_EXT = ('.webp', '.jpg', '.jpeg', '.png', '.gif', '.avif')
MAX_NEWS_BYTES = 200_000                       # una noticia normal ocupa 2–10 KB
MAX_LINKS = 12                                 # «Fuentes y enlaces» por noticia

# Noticias publicadas antes del panel (hasta el 23/11/2026, con sus enlaces revisados a mano) y sus traducciones al
# inglés (25/11/2026): conservan sus enlaces dentro del texto, pero SOLO si el texto no ha cambiado (huella SHA-256 del
# cuerpo; en las inglesas, también de su translationKey). Si se edita, pasa a regirse como una noticia nueva.
# En las noticias nuevas el texto no puede llevar enlaces: van en «Fuentes y enlaces» (campo `enlaces`).
LEGACY_NEWS = {
    'es/2025-01-07-investigacion-chilena-confirma-expresion-de-alergenos-en-parasitos.md':
        '3fa031cfe801015895cdc75069d8444dffac7cb06e7a24001a47c00250b26574',
    'es/2025-06-23-el-cambio-climatico-y-las-practicas-de-pesca-aceleran-el-ciclo-del.md':
        'fd70bb6cc0d54fdba892ea7e1b720effb1dbddb6ad165bbbfcebbb25eda0b081',
    'es/2025-09-06-nuevas-recomendaciones-para-prevenir-el-anisakis.md':
        'e9c81c410ddaf305846ed89d622a614fe1a4ba8c89fe9cd2cc9f8c94cf116bfb',
    'es/2025-09-07-falta-de-informacion-sobre-el-anisakis-entre-los-consumidores-el-caso.md':
        'ec526eb6922e0a8479dae2c6a10778f9a16e31b8eb718a0b6acd84dec92e6bd8',
    'es/2025-12-02-alerta-por-parasitos-en-una-caballa-saludable-en-espana.md':
        'dbc1faa3f77918a551c6dbdc69c3d95675c08a03f42302bc318114b2f5ed0b13',
    'es/2025-12-02-primer-caso-confirmado-de-anisakiasis-en-grecia-tras-una-cena-de-sushi.md':
        'f9967c51f060ec21e3d6922159b96c452f924f61a3ba59007535db08ead331f5',
    'es/2025-12-15-el-anisakis-esta-presente-en-el-100-de-las-merluzas-europeas-y-en-una.md':
        '9699e2a6cf2e85c5347f1d632845712398653c39b2b69c9ebba3d2ae415217cd',
    'es/2026-01-12-alergia-al-anisakis-una-reaccion-que-puede-llegar-a-ser-grave.md':
        '73e4a72c293e4f17f39154f389268a3d5bb6c419200dfde1c02997d3440fb768',
    'es/2026-01-12-anisakis-como-causante-de-alergia-a-la-carne.md':
        'e190dd327e1d7d489a00c5d1298ab63fb43e5aee885fb2c497060fac50d36097',
    'es/2026-01-13-empresa-espanola-crea-tecnologias-contra-el-parasito-anisakis.md':
        'fe1182e58a7fe2fddf85607798b565c4205cb276d5687e2c1c537d9ea1c7798b',
    'es/2026-03-26-retirada-preventiva-por-presencia-extraordinaria-de-anisakis.md':
        '90e416f8246d69e6906fc983865bfb8cffcae586e92377fb6bfafc135eefbf46',
    'es/2026-04-27-alerta-sanitaria-infestacion-masiva-de-anisakis-en-pescado-azul.md':
        '395af83b14a6165589fbc8c2013e84cbaf1e6eedab8c2af57fafc83cfdea34d7',
    'es/2026-06-08-el-gobierno-vasco-lanza-la-campana-frescossi-anisakisno-para-impulsar.md':
        '7880d96475f4019c8fa02444b9e30574ca3c2a159db7c6f2f7146fdf0513c523',
    'es/2026-07-22-descodifican-el-genoma-del-anisakis-la-ciencia-avanza-hacia-un-control.md':
        '8bcb6454181b88bec5cc97e9b25a40fb363b858a1abad4e2616cc48d32b3b51d',
    'es/2026-09-07-mas-alla-del-96-analisis-cientifico-del-estudio-sobre-parasitos-en-el.md':
        '78e52b2f07ea34f0206b1ee6eceb0199c756a50a4c0fcc7a172881b6752c02ff',
    'es/2026-10-05-inactivacion-termica-del-anisakis-lo-que-revela-el-proyecto-heatsakis.md':
        'b547ca782bc32b730647e80196aee178293880ce140f90e6506fba19c7d11980',
    'es/2026-10-26-control-del-anisakis-el-papel-de-los-veterinarios-desde-la-lonja-hasta.md':
        '79e22733a784b924920e18bedec8184668389cb109d09b6d94bbac2b9897c916',
    'es/2026-11-23-controles-en-frontera-destruido-un-lote-de-pez-sable.md':
        '552fb76e922001897bfbc80f348599d306032ba7cc736f3525f17eecbf498e04',
    'en/2025-01-07-chilean-research-confirms-allergen-expression-in-anisakis-parasites.md':
        '55dfdfbcf810fb09817f03fc6b1f02ef67dba91ec3a48cdb28102a7fc07f1d66',
    'en/2025-06-23-consumption-habits-and-evisceration-at-sea-two-factors-behind-anisakis.md':
        '07b65e50fad07cded1e13dbc665d6a1609924318dfd4f6d4833f3faa0d02461e',
    'en/2025-09-06-new-recommendations-to-prevent-anisakis.md':
        'dd44fd8a0e2d13732be0d5798f5e197cb6a0fc74a7f45678949f3210e31460a5',
    'en/2025-09-07-what-consumers-know-about-anisakis-a-study-in-sicily.md':
        '6ce4262f4c56f558e2abe69cf81b431876d83d4f74b52fc725ab9b3177664aaa',
    'en/2025-12-02-alert-over-parasites-in-a-healthy-mackerel-in-spain.md':
        '39ee44e17360d5e25eca5b6460d0a986bfec987d9cd2cda0df1de37bd619f532',
    'en/2025-12-02-first-confirmed-case-of-anisakiasis-in-greece-after-a-sushi-dinner.md':
        '9de9bf1aa00555989507bd8da58054d50bee53ace1dd689599c5e1dc27243537',
    'en/2025-12-15-anisakis-is-present-in-100-of-european-hake-and-in-one-in-five.md':
        '2a0413bb8ba078f02d19bb4a1d8198b0391e70e6d33673d98fe1641fd87026b2',
    'en/2026-01-12-anisakis-allergy-a-reaction-that-can-become-serious.md':
        'f5f788776ccddebdffaeff3b508cad68bd79514c6b5a16952f69dfebbadf0772',
    'en/2026-01-12-anisakis-as-a-cause-of-meat-allergy.md':
        'ac26f48f36ca73707e29f27604db1d259c0b49ce2dd3d7d3a82da51c078330ff',
    'en/2026-01-13-spanish-company-develops-technologies-against-the-anisakis-parasite.md':
        '0d6e5ca881818602f039923987a7df56da83d35896b85ca07f245ca56d461577',
    'en/2026-03-26-precautionary-recall-due-to-exceptional-presence-of-anisakis.md':
        'b0b1a8d9c01d6d8eabe6a7bd169fca1f893546c141687b85bb682635e3517206',
    'en/2026-04-27-health-alert-massive-anisakis-infestation-in-oily-fish.md':
        '72eb124f4b2c05e7f30ae534d43318ce0c2cd297fcc0c93fc8538907d0a8d0ef',
    'en/2026-06-08-the-basque-government-launches-the-frescossi-anisakisno-campaign.md':
        '6bb82ba67606a708f9b5275628b2d4506adb1105aba94b3db2e6a2bbbb47d723',
    'en/2026-07-22-anisakis-genome-decoded-science-moves-towards-genetic-control.md':
        '95075e48c15262b3b793423e502951f76efdb6d5ffb4870ebe35d0caef7de063',
    'en/2026-09-07-beyond-96-scientific-analysis-of-the-study-on-parasites-in-tuna.md':
        '9e063d7699bbef96ea35a2e828f56811fbc174100a37bba7d5f51324b57e9db4',
    'en/2026-10-05-thermal-inactivation-of-anisakis-what-the-heatsakis-project-reveals.md':
        'ab6d6e97752ec01f66551f0a38ea7a782988285bfa80938615ac99f0df1ca008',
    'en/2026-10-26-anisakis-control-the-role-of-veterinarians-from-the-fish-market.md':
        'ef3184381977547585551ff274cebef60be79edb339209b9454b8db1a69b5946',
    'en/2026-11-23-border-controls-batch-of-imported-scabbardfish-destroyed.md':
        'da74cca04600179d5db65b6d2a1020d88de0422a772424d9857c98e29b9373e7',
}

# Comprobación de las direcciones de «Fuentes y enlaces»
LINK_TYPES = {'fuente': ('Fuente', 'Fuentes'), 'video': ('Vídeo relacionado', 'Vídeos relacionados'),
              'enlace': ('Enlace relacionado', 'Enlaces relacionados')}
SHORTENERS = {'bit.ly', 'bitly.com', 't.co', 'tinyurl.com', 'goo.gl', 'ow.ly', 'is.gd', 'buff.ly', 'rebrand.ly',
              'cutt.ly', 'shorturl.at', 'shorturl.fm', 'tiny.cc', 'rb.gy', 's.id', 'v.gd', 'lnkd.in', 'trib.al',
              'dlvr.it', 'shorte.st', 'adf.ly', 'bl.ink', 'short.io', 'qrco.de', 'linktr.ee', 'x.gd', 'urlz.fr'}
# Orientativo: un servidor puede servir un ejecutable en cualquier ruta; esto solo evita los enlaces evidentes.
RISKY_EXT = ('.exe', '.msi', '.bat', '.cmd', '.scr', '.ps1', '.vbs', '.js', '.jar', '.apk', '.dmg',
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
    if host.endswith(WILDCARD_DNS) or host in {d.lstrip('.') for d in WILDCARD_DNS} or re.search(r'(?:^|\.)\d{1,3}(?:[.-]\d{1,3}){3}\.', host):
        return None, 'dominio que apunta a una IP cualquiera (nip.io, sslip.io…)'
    from urllib.parse import unquote, parse_qsl
    path = unquote(unquote(p.path)).lower().rstrip('/;. ')
    if path.endswith(RISKY_EXT) or re.search(r'\.(?:exe|msi|apk|dmg|zip|rar|7z|iso|scr|bat|jar)[;.]', path):
        return None, 'apunta a un archivo descargable o ejecutable'
    for _, v in parse_qsl(p.query + '&' + p.fragment, keep_blank_values=True):
        v = unquote(unquote(v)).lower().strip()
        if re.search(r'(?:https?:|^//|^www\.)', v):
            return None, 'lleva dentro otra dirección (redirección): enlazar directamente al destino'
        if v.rstrip('/;. ').endswith(RISKY_EXT):
            return None, 'apunta a un archivo descargable o ejecutable'
    return u, ''


# Dominios que resuelven a cualquier IP que se ponga en el nombre (sirven para esconder servidores propios)
WILDCARD_DNS = ('.nip.io', '.sslip.io', '.xip.io', '.lvh.me', '.localtest.me', '.traefik.me', '.local.gd')


# Texto de las noticias nuevas: sin enlaces ni imágenes de ningún tipo (van en «Fuentes y enlaces»)
# Las mismas reglas se copian al panel con tools/reglas_panel.py (que la publicación comprueba).
BODY_RULES = [
    r'\]\s*[(\[]',                                   # sintaxis de enlace o imagen [texto](…) / [texto][…]
    r'\[[^\]\n]{0,300}\]:\s*\S',                     # definición de enlace [1]: … (acotado: evita esperas)
    r'\[\s*\.\s*\]|\(\s*\.\s*\)',                    # dominios «desactivados» como evil[.]com
    r'<\s*/?\s*(?:a|img|iframe|script|object|embed)\b',   # etiquetas HTML de enlace, imagen o contenido externo
    r'\b(?:https?|ftp|mailto|javascript|data|file|hxxps?)\s*:',   # direcciones con protocolo
    r'\bwww\s*\.',                                   # www.…
    r'\b[a-z0-9-]{1,63}\.(?:com|es|org|net|eu|info|io|ly|me|gal|cat|co|uk|de|fr|it|pt|gov|edu|tv|biz|app|dev|ru|su|cn'
    r'|xyz|top|site|online|shop|store|club|link|click|live|pro|cc|ws|us|ca|mx|ar|cl|br|nl|be|ch|at|pl|se|no|dk|fi|ie'
    r'|ro|gr|tr|ua|jp|kr|in|au|nz|za|ai|to|gg|zip|mov|vip|win|bid|loc|lat|icu|cfd|sbs|rest|fun|space|website|tech)\b',   # dominio suelto
]
BODY_FORBIDDEN = re.compile('|'.join(BODY_RULES), re.I | re.A)


def body_problem(body):
    """Motivo por el que el texto de una noticia nueva no se puede publicar, o '' si está bien.
    Se normaliza antes (NFKC) para que caracteres «disfrazados» (p. ej. los dos puntos de ancho completo) no se cuelen."""
    import unicodedata
    m = BODY_FORBIDDEN.search(unicodedata.normalize('NFKC', body or ''))
    return f'el texto contiene un enlace o dirección web («{m.group(0).strip()}»): los enlaces van en «Fuentes y enlaces»' if m else ''


def render_links(items, fname):
    """Bloque «Fuente: …» / «Vídeo relacionado: …» al final de la noticia, con direcciones ya comprobadas."""
    groups = {k: [] for k in LINK_TYPES}
    for it in items if isinstance(items, list) else []:
        extra = set(it) - {'tipo', 'nombre', 'url'}
        if extra:
            warn(f'{fname}: enlace descartado (campos no permitidos: {", ".join(sorted(extra))})')
            continue
        kind = it.get('tipo', 'fuente') if it.get('tipo') in LINK_TYPES else 'fuente'
        name = re.sub(r'\s+', ' ', it.get('nombre', '')).strip()[:80]
        url, why = check_external_url(it.get('url', ''))
        if url and body_problem(name):
            url, why = None, 'el nombre visible no puede ser otra dirección web'
        if not url:
            warn(f'{fname}: enlace descartado ({why}): {it.get("url", "")!r}')
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

    if not links:                               # noticias nuevas: el editor escapa caracteres (\* \_ \[ …): se muestran tal cual
        t = re.sub(r'\\(&lt;|&gt;|&amp;|[\\`*_{}\[\]()#+\-.!|~])', lambda m: keep(m.group(1)), t)

    # Las noticias solo llevan una imagen (la principal, en la cabecera): las imágenes dentro del texto se quitan
    t = re.sub(r'!\[([^\[\]\x00]*)\]\(([^()\s\x00]+)\)', '', t)

    def link(m):
        url = None
        if links:                               # solo noticias antiguas sin cambios: internas o https comprobadas
            raw = html.unescape(m.group(2))
            url = safe_url(raw) if raw.startswith(('/', '#')) else check_external_url(raw)[0]
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


# ------------------------------------------------------------------ idiomas
# Español (principal, en la raíz) e inglés (en /en/). Las noticias en inglés son opcionales: si una noticia no
# tiene versión inglesa, la lista inglesa la muestra en español con el aviso ONLY_ES.
LANGS = ('es', 'en')
MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
          'November', 'December']
# Páginas fijas: nombre del archivo en español → dirección de la versión inglesa
EN_SLUGS = {'anisakis': 'anisakis', 'informacion-cientifica': 'scientific-information', 'legislacion': 'legislation',
            'aviso-legal': 'legal-notice', 'privacidad': 'privacy', 'cookies': 'cookies'}
T = {
    'es': dict(home='/', news='/noticias/', feed='/noticias/feed.xml', n_home='Inicio', n_news='Noticias',
               more='Leer más', skip='Saltar al contenido', main_nav='Principal', contact='Contacto',
               legal=('Aviso legal', 'Privacidad', 'Cookies'), locale='es_ES', home_word='inicio',
               desc='Información rigurosa sobre el Anisakis: biología, riesgos para la salud, legislación y noticias.',
               news_desc='Actualidad sobre el Anisakis: salud, investigación, pesca y legislación.',
               feed_desc='Actualidad sobre el Anisakis', newer='← Más recientes', older='Anteriores →',
               page_of='Página {} de {}', pages='Páginas', news_page='Noticias (página {})', lang_nav='Idioma',
               nf_title='Página no encontrada', nf_text='La dirección que buscas no existe o ha cambiado.',
               nf_home='Ir al inicio', nf_news='Ver noticias'),
    'en': dict(home='/en/', news='/en/news/', feed='/en/news/feed.xml', n_home='Home', n_news='News',
               more='Read more', skip='Skip to content', main_nav='Main', contact='Contact',
               legal=('Legal notice', 'Privacy', 'Cookies'), locale='en_GB', home_word='home',
               desc='Rigorous information about Anisakis: biology, health risks, legislation and news.',
               news_desc='News about Anisakis: health, research, fisheries and legislation.',
               feed_desc='News about Anisakis', newer='← Newer', older='Older →',
               page_of='Page {} of {}', pages='Pages', news_page='News (page {})', lang_nav='Language',
               nf_title='Page not found', nf_text='The page you are looking for does not exist or has moved.',
               nf_home='Go to the home page', nf_news='See the news'),
}
ONLY_ES = 'Only available in Spanish'
LINK_LABELS = {
    'es': LINK_TYPES,
    'en': {'fuente': ('Source', 'Sources'), 'video': ('Related video', 'Related videos'),
           'enlace': ('Related link', 'Related links')},
}


def page_url(slug, lang):
    """Dirección de una página fija (por el nombre de su archivo en español) en cada idioma."""
    return f'/{slug}/' if lang == 'es' else f'/en/{EN_SLUGS[slug]}/'


def fecha_l(d, lang):
    return fecha(d) if lang == 'es' else f'{d.day} {MONTHS[d.month - 1]} {d.year}'


def nav_items(lang):
    t = T[lang]
    return [(t['home'], t['n_home'])] + \
        [(page_url(s, lang), n) for s, n in (('anisakis', 'Anisakis'),
                                             ('informacion-cientifica', 'Información científica' if lang == 'es' else 'Scientific information'),
                                             ('legislacion', 'Legislación' if lang == 'es' else 'Legislation'))] + \
        [(t['news'], t['n_news'])]


def localize_links(h, url_map):
    """En el contenido inglés, las rutas internas de la web española pasan a su versión inglesa (si existe)."""
    def rep(m):
        return m.group(1) + url_map.get(m.group(2), m.group(2)) + m.group(3)
    return re.sub(r'(href=")(/[^"#?]*)([#?][^"]*)?(?=")', lambda m: rep(m) if m.group(3) else
                  m.group(1) + url_map.get(m.group(2), m.group(2)), h)


# ------------------------------------------------------------------ plantilla
def layout(path, title, body, desc='', image='', kind='website', extra_head='', lang='es', alt=None, fallback=None):
    """alt: dirección de la misma página en el otro idioma. Si no existe (None), el selector de idioma lleva a
    `fallback` o, si no se indica, a la portada del otro idioma."""
    t = T[lang]
    other = 'en' if lang == 'es' else 'es'
    full_title = f'{title} · {SHORT}' if title else NAME
    desc = (desc or t['desc'])[:300]
    url = SITE + path
    img = SITE + (image or '/img/portada.webp')
    nav = ''.join(
        f'<li><a href="{h}"' + (' aria-current="page"' if (h == path or (h != t['home'] and path.startswith(h))) else '') + f'>{n}</a></li>'
        for h, n in nav_items(lang))
    paths = {lang: path, other: alt}
    alternates = ''
    if alt:
        alternates = ''.join(f'<link rel="alternate" hreflang="{l}" href="{SITE}{paths[l]}">\n' for l in LANGS) + \
            f'<link rel="alternate" hreflang="x-default" href="{SITE}{paths["es"]}">\n'
    switch = ''.join(
        (f'<a href="{esc(path if path != "/404.html" else T[l]["home"])}" hreflang="{l}" lang="{l}" aria-current="true">{l.upper()}</a>' if l == lang else
         f'<a href="{esc(alt or fallback or T[l]["home"])}" hreflang="{l}" lang="{l}">{l.upper()}</a>') for l in LANGS)
    lt = t['legal']
    return f'''<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none'">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
{alternates}<meta property="og:type" content="{kind}">
<meta property="og:site_name" content="{NAME}">
<meta property="og:title" content="{esc(title or NAME)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{img}">
<meta property="og:locale" content="{t['locale']}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#263e8b">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" href="/favicon-32.png" type="image/png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="alternate" type="application/rss+xml" title="{t['n_news']} · {SHORT}" href="{t['feed']}">
<link rel="stylesheet" href="/css/site.css">
{extra_head}</head>
<body>
<a class="skip" href="#main">{t['skip']}</a>
<header class="top">
  <div class="wrap top-in">
    <a class="brand" href="{t['home']}" aria-label="{NAME} — {t['home_word']}"><img src="/img/logo-sm.webp" alt="{SHORT}" width="140" height="101"></a>
    <nav aria-label="{t['main_nav']}"><ul>{nav}</ul></nav>
    <nav class="lang" aria-label="{t['lang_nav']}">{switch}</nav>
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="foot">
  <div class="wrap foot-in">
    <div><img src="/img/logo-sm.webp" alt="" width="110" height="79" loading="lazy"><p>{NAME}</p></div>
    <div><p>{t['contact']}: <a href="mailto:{EMAIL}">{EMAIL}</a></p>
    <p class="legal"><a href="{page_url('aviso-legal', lang)}">{lt[0]}</a> · <a href="{page_url('privacidad', lang)}">{lt[1]}</a> · <a href="{page_url('cookies', lang)}">{lt[2]}</a></p></div>
  </div>
</footer>
<script src="/js/site.js" defer></script>
</body>
</html>
'''


def card(n, lang='es', notice=''):
    """Tarjeta de la lista. notice: aviso «solo en español» (lista inglesa, noticia sin versión inglesa)."""
    img = (f'<img src="{n["image"]}" alt="" loading="lazy" width="600" height="340">' if n['image']
           else '<span class="ph" aria-hidden="true"></span>')
    tl = ' lang="es"' if notice else ''
    note = f'<span class="only-es">{notice}</span>' if notice else ''
    return (f'<article class="card"><a href="{n["url"]}">{img}<div class="card-b">'
            f'<time datetime="{n["date"].isoformat()}">{fecha_l(n["date"], lang)}</time>{note}'
            f'<h3{tl}>{esc(n["title"])}</h3><p{tl}>{esc(n["summary"])}</p><span class="more">{T[lang]["more"]}</span></div></a></article>')


# ------------------------------------------------------------------ generación
def write(rel, content):
    p = os.path.join(OUT, rel.strip('/').replace('/', os.sep))
    if rel.endswith('/') or rel == '':
        p = os.path.join(p, 'index.html')
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w', encoding='utf-8', newline='\n').write(content)


def render_links_lang(items, fname, lang):
    """Como render_links, con los rótulos («Fuente», «Source»…) en el idioma de la noticia."""
    global LINK_TYPES
    saved, LINK_TYPES = LINK_TYPES, LINK_LABELS[lang]
    try:
        return render_links(items, fname)
    finally:
        LINK_TYPES = saved


def legacy_hash(lang, key, body):
    """Huella de una noticia de confianza: su texto; en las traducciones, también la clave que la une a la española
    (así no se puede «reutilizar» una traducción revisada cambiándole solo la clave)."""
    data = (key + '\n' if lang == 'en' else '') + body.strip()
    return hashlib.sha256(data.encode('utf-8', 'replace')).hexdigest()


def load_news():
    """Lee content/noticias/es/*.md (obligatorio) y content/noticias/en/*.md (opcional), unidas por translationKey.
    Devuelve [{'key', 'es': {...}, 'en': {...} o None}] de la más reciente a la más antigua."""
    base = os.path.join(ROOT, 'content', 'noticias')
    for f in sorted(os.listdir(base)):
        if f not in LANGS:
            warn(f'content/noticias/{f}: solo se admiten las carpetas es/ y en/ (no se publica)')
    found = {'es': {}, 'en': {}}
    seen = {'es': set(), 'en': set()}
    for lang in LANGS:
        d = os.path.join(base, lang)
        if not os.path.isdir(d) or os.path.islink(d):
            continue
        # las noticias antiguas primero: una nueva nunca puede quitarles su dirección
        for f in sorted(os.listdir(d), key=lambda f: (f'{lang}/{f}' not in LEGACY_NEWS, f)):
            rel = f'{lang}/{f}'
            p = os.path.join(d, f)
            if not f.endswith('.md'):
                warn(f'{rel}: archivo no permitido en las noticias')
                continue
            if not os.path.isfile(p) or os.path.islink(p):
                warn(f'{rel} se omite (no es un archivo normal)')
                continue
            if os.path.getsize(p) > MAX_NEWS_BYTES:
                warn(f'{rel} se omite (más de {MAX_NEWS_BYTES // 1000} KB)')
                continue
            meta, body = read_doc(p)
            # cada campo con su tipo: solo «enlaces» es una lista; el resto, texto
            meta = {k: (v if (k == 'enlaces') == isinstance(v, list) else ([] if k == 'enlaces' else ''))
                    for k, v in meta.items()}
            if meta.get('draft', '').lower() in ('true', 'si', 'sí', 'yes'):
                continue
            stem = f[:-3]
            slug = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', stem)      # la dirección sale del nombre del archivo
            if not SLUG_OK.fullmatch(slug) or len(slug) > 120:
                warn(f'{rel} se omite (dirección no válida: {slug!r})')
                continue
            key = meta.get('translationKey', '') or (stem if lang == 'es' else '')
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*', key or ''):
                warn(f'{rel} se omite (falta la clave que une los dos idiomas)')
                continue
            if key in found[lang]:
                warn(f'{rel}: ya hay otra noticia con la misma clave ({key}); no se publica')
                continue
            b, n = slug, 2
            while slug in seen[lang]:               # dos noticias con el mismo título: -2, -3…
                slug, n = f'{b}-{n}', n + 1
            seen[lang].add(slug)
            try:
                dt = date.fromisoformat(str(meta.get('date', f[:10]))[:10])
            except ValueError:
                warn(f'{rel} se omite (fecha no válida: {meta.get("date")!r})')
                continue
            image = meta.get('image', '').strip()
            if image and not IMG_OK.fullmatch(image):
                warn(f'{rel}: imagen no válida, se publica sin imagen ({image!r})')
                image = ''
            legacy = LEGACY_NEWS.get(rel) == legacy_hash(lang, key, body)
            why = '' if legacy else (body_problem(body) or next((f'«{k}»: ' + body_problem(meta.get(k, ''))
                                                                for k in ('title', 'summary', 'description')
                                                                if body_problem(meta.get(k, ''))), ''))
            if why:
                warn(f'{rel} NO se publica: {why}')
                continue
            h = markdown(body, links=legacy)
            title = re.sub(r'\s+', ' ', meta.get('title', '')).strip()[:200] or slug
            summary = re.sub(r'\s+', ' ', meta.get('summary', '')).strip()[:300] or plain(h)[:200]
            links_html = render_links_lang(meta.get('enlaces', []), rel, lang)
            if links_html:
                h = h + '\n' + links_html
            found[lang][key] = {'slug': slug, 'url': T[lang]['news'] + slug + '/', 'title': title, 'date': dt,
                                'image': image, 'summary': summary, 'html': h}
    for key in sorted(set(found['en']) - set(found['es'])):
        warn(f'en: versión inglesa sin la española ({key}); no se publica')
    news = [{'key': k, 'es': v, 'en': found['en'].get(k)} for k, v in found['es'].items()]
    news.sort(key=lambda n: (n['es']['date'], n['es']['slug']), reverse=True)
    return news


HOME = {
    'es': dict(
        temas=[('/anisakis/', 'La biología del Anisakis y su ciclo vital en el medio marino.'),
               ('/informacion-cientifica/', 'Los riesgos para la salud pública, desde alergias graves hasta cuadros gastrointestinales.'),
               ('/legislacion/', 'La evolución normativa y legal relacionada con su control.'),
               ('/noticias/', 'Las razones de su expansión en caladeros y especies concretas.'),
               ('/noticias/', 'El impacto económico en la pesca y la distribución.'),
               ('/noticias/', 'El seguimiento de su presencia en los medios de comunicación y la opinión pública.'),
               ('/noticias/', 'Posibles soluciones para reducir su presencia en el mar y en los productos pesqueros.')],
        lead='Esta web nace con el objetivo de sensibilizar a la sociedad y a los profesionales sobre los riesgos reales asociados al consumo de pescado contaminado, así como sobre las implicaciones ecológicas, sanitarias, comerciales y legales que conlleva su proliferación.',
        b_news='Últimas noticias', b_contact='Contacto', eyebrow='Qué encontrarás',
        h2='Mantengamos el pescado más saludable librándolo del Anisakis',
        intro='En esta página web, a través de contenidos actualizados y contrastados, abordaremos temas como:',
        all_news='Ver todas las noticias',
        contact_text='El Anisakis no es un problema menor. Su proliferación está cambiando nuestros hábitos culinarios y afectando a toda la cadena alimentaria del pescado. Aquí encontrarás contenidos actualizados con información relevante, veraz y accesible para todos.',
        contact_mail='Puedes ponerte en contacto con nosotros a través de'),
    'en': dict(
        temas=[('/en/anisakis/', 'The biology of Anisakis and its life cycle in the marine environment.'),
               ('/en/scientific-information/', 'The risks to public health, from severe allergies to gastrointestinal disorders.'),
               ('/en/legislation/', 'The development of regulations and legislation related to its control.'),
               ('/en/news/', 'The reasons for its spread in specific fishing grounds and species.'),
               ('/en/news/', 'The economic impact on fisheries and distribution.'),
               ('/en/news/', 'Monitoring its presence in the media and in public opinion.'),
               ('/en/news/', 'Possible solutions to reduce its presence in the sea and in fishery products.')],
        lead='This website was created to raise awareness among the public and professionals of the real risks associated with eating contaminated fish, and of the ecological, health, commercial and legal implications of its proliferation.',
        b_news='Latest news', b_contact='Contact', eyebrow='What you will find',
        h2='Let’s keep fish healthier by ridding it of Anisakis',
        intro='On this website, through up-to-date and verified content, we will cover topics such as:',
        all_news='See all the news',
        contact_text='Anisakis is not a minor problem. Its proliferation is changing our eating habits and affecting the entire fish food chain. Here you will find up-to-date content with relevant, accurate information that is accessible to everyone.',
        contact_mail='You can contact us at'),
}


def home_html(lang, cards_html):
    h = HOME[lang]
    t = T[lang]
    return f'''<section class="hero">
  <picture><source media="(max-width: 700px)" srcset="/img/portada-movil.webp"><img class="hero-bg" src="/img/portada.webp" alt="" width="1728" height="919" fetchpriority="high"></picture>
  <div class="wrap hero-in">
    <img class="hero-logo" src="/img/logo.webp" alt="{SHORT}" width="560" height="404">
    <h1>Anisakis International Information Site</h1>
    <p class="lead">{h['lead']}</p>
    <p class="cta"><a class="btn" href="#noticias">{h['b_news']}</a> <a class="btn btn-o" href="#contacto">{h['b_contact']}</a></p>
  </div>
</section>
<section class="band">
  <div class="wrap temas">
    <div class="temas-intro">
      <p class="eyebrow">{h['eyebrow']}</p>
      <h2>{h['h2']}</h2>
      <p>{h['intro']}</p>
    </div>
    <ol class="topics">{''.join(f'<li><a href="{u}"><span class="num" aria-hidden="true">{i:02d}</span><span class="txt">{esc(x)}</span><span class="arr" aria-hidden="true">→</span></a></li>' for i, (u, x) in enumerate(h['temas'], 1))}</ol>
  </div>
</section>
<section class="wrap" id="noticias">
  <h2>{h['b_news']}</h2>
  <div class="cards">{cards_html}</div>
  <p class="center"><a class="btn" href="{t['news']}">{h['all_news']}</a></p>
</section>
<section class="band band-dark" id="contacto">
  <div class="wrap narrow center">
    <h2>{h['b_contact']}</h2>
    <p>{h['contact_text']}</p>
    <p>{h['contact_mail']} <a href="mailto:{EMAIL}">{EMAIL}</a></p>
  </div>
</section>'''


def list_cards(items, lang):
    """Tarjetas de la lista de un idioma: en inglés, las noticias sin traducir salen en español con aviso."""
    out = []
    for n in items:
        if n[lang]:
            out.append(card(n[lang], lang))
        else:
            out.append(card(n['es'], lang, ONLY_ES))
    return ''.join(out)


def json_ld(d):
    return ('<script type="application/ld+json">'
            + json.dumps(d, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
            + '</script>\n')


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
            warn(f'static/img/noticias/{n} no se publica (solo se admiten imágenes {", ".join(IMG_EXT)})')
        return bad
    shutil.copytree(os.path.join(ROOT, 'static'), OUT, ignore=only_images)
    news = load_news()
    pages = []  # (url, lastmod, {idioma: url de cada versión}) para el sitemap

    # Correspondencia de rutas españolas → inglesas (para los enlaces internos del contenido inglés)
    url_map = {'/': '/en/', '/noticias/': '/en/news/'}
    url_map.update({page_url(s, 'es'): page_url(s, 'en') for s in EN_SLUGS})
    url_map.update({n['es']['url']: n['en']['url'] for n in news if n['en']})

    # portadas
    for lang in LANGS:
        top = news[:6]
        cards_html = list_cards(top, lang)
        alt = T['en' if lang == 'es' else 'es']['home']
        write(T[lang]['home'], layout(T[lang]['home'], '', home_html(lang, cards_html), lang=lang, alt=alt))
    pages.append(('/', news[0]['es']['date'] if news else None, {'es': '/', 'en': '/en/'}))

    # páginas informativas y textos legales (la versión inglesa está en content/en/, con el mismo nombre de archivo)
    for folder, cls in (('paginas', 'page'), ('legal', 'page legal-text')):
        for f in sorted(os.listdir(os.path.join(ROOT, 'content', folder))):
            if not f.endswith('.html'):
                continue
            slug = f.rsplit('.', 1)[0]
            if slug not in EN_SLUGS:
                warn(f'content/{folder}/{f}: página sin dirección inglesa en EN_SLUGS')
                continue
            versions = {}
            for lang in LANGS:
                p = os.path.join(ROOT, 'content', folder, f) if lang == 'es' else os.path.join(ROOT, 'content', 'en', folder, f)
                if os.path.isfile(p):
                    versions[lang] = read_doc(p)
            for lang, (meta, body) in versions.items():
                url = page_url(slug, lang)
                alt = page_url(slug, 'en' if lang == 'es' else 'es') if len(versions) == 2 else None
                if lang == 'en':
                    body = localize_links(body, url_map)
                desc = meta.get('description') or (plain(body)[:180] if folder == 'paginas' else '')
                write(url, layout(url, meta['title'], f'<article class="wrap narrow {cls}"><h1>{esc(meta["title"])}</h1>\n{body}</article>',
                                  desc, lang=lang, alt=alt))
            pages.append((page_url(slug, 'es'), None, {l: page_url(slug, l) for l in versions}))

    # noticias: listas
    for lang in LANGS:
        t = T[lang]
        total = max(1, -(-len(news) // PER_PAGE))
        page_word = 'pagina' if lang == 'es' else 'page'
        for i in range(total):
            chunk = news[i * PER_PAGE:(i + 1) * PER_PAGE]
            url = t['news'] if i == 0 else f'{t["news"]}{page_word}/{i + 1}/'
            pager = ''
            if total > 1:
                prev_url = t['news'] if i == 1 else f"{t['news']}{page_word}/{i}/"
                prev = '' if i == 0 else f'<a href="{prev_url}" rel="prev">{t["newer"]}</a>'
                nxt = '' if i == total - 1 else f'<a href="{t["news"]}{page_word}/{i + 2}/" rel="next">{t["older"]}</a>'
                pager = f'<nav class="pager" aria-label="{t["pages"]}">{prev}<span>{t["page_of"].format(i + 1, total)}</span>{nxt}</nav>'
            body = f'<section class="wrap"><h1>{t["n_news"]}</h1><div class="cards">{list_cards(chunk, lang)}</div>{pager}</section>'
            other = T['en' if lang == 'es' else 'es']
            alt = other['news'] if i == 0 else f'{other["news"]}{"page" if lang == "es" else "pagina"}/{i + 1}/'
            write(url, layout(url, t['n_news'] if i == 0 else t['news_page'].format(i + 1), body, t['news_desc'], lang=lang, alt=alt))
            if lang == 'es':
                pages.append((url, chunk[0]['es']['date'] if chunk else None,
                              {'es': url, 'en': '/en/news/' if i == 0 else f'/en/news/page/{i + 1}/'}))

    # noticias: una página por noticia y idioma
    for lang in LANGS:
        t = T[lang]
        mine = [n for n in news if n[lang]]
        for idx, n in enumerate(mine):
            v = n[lang]
            newer = mine[idx - 1][lang] if idx > 0 else None
            older = mine[idx + 1][lang] if idx + 1 < len(mine) else None
            img = f'<figure class="lead-img"><img src="{v["image"]}" alt="" width="1200" height="680"></figure>' if v['image'] else ''
            ld = {'@context': 'https://schema.org', '@type': 'NewsArticle', 'headline': v['title'][:110],
                  'datePublished': v['date'].isoformat(), 'inLanguage': lang, 'mainEntityOfPage': SITE + v['url'],
                  'publisher': {'@type': 'Organization', 'name': NAME, 'logo': {'@type': 'ImageObject', 'url': SITE + '/img/logo.png'}}}
            if v['image']:
                ld['image'] = SITE + v['image']
            nav = '<nav class="pager">' + (f'<a href="{newer["url"]}" rel="prev">← {esc(newer["title"])}</a>' if newer else '<span></span>') + \
                  (f'<a href="{older["url"]}" rel="next">{esc(older["title"])} →</a>' if older else '<span></span>') + '</nav>'
            h = localize_links(v['html'], url_map) if lang == 'en' else v['html']
            body = (f'<article class="wrap narrow page news"><p class="meta"><a href="{t["news"]}">{t["n_news"]}</a> · '
                    f'<time datetime="{v["date"].isoformat()}">{fecha_l(v["date"], lang)}</time></p>'
                    f'<h1>{esc(v["title"])}</h1>{img}\n{h}\n{nav}</article>')
            other = n['en' if lang == 'es' else 'es']
            write(v['url'], layout(v['url'], v['title'], body, v['summary'], v['image'], 'article', json_ld(ld),
                                   lang=lang, alt=other['url'] if other else None,
                                   fallback=T['en' if lang == 'es' else 'es']['news']))
            if lang == 'es':
                pages.append((v['url'], v['date'], {l: n[l]['url'] for l in LANGS if n[l]}))

    # 404 (una sola para toda la web: en los dos idiomas), sitemap, robots, RSS, CNAME
    nf = ''.join(f'<section class="wrap narrow page center" lang="{l}"><h1>{T[l]["nf_title"]}</h1><p>{T[l]["nf_text"]}</p>'
                 f'<p><a class="btn" href="{T[l]["home"]}">{T[l]["nf_home"]}</a> <a class="btn btn-o" href="{T[l]["news"]}">{T[l]["nf_news"]}</a></p></section>'
                 for l in LANGS)
    write('404.html', layout('/404.html', 'Página no encontrada · Page not found', nf))
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for _, lm, versions in pages:
        alts = ''.join(f'<xhtml:link rel="alternate" hreflang="{l}" href="{SITE}{u}"/>' for l, u in versions.items()) \
            if len(versions) > 1 else ''
        for l, u in versions.items():
            sm.append(f'<url><loc>{SITE}{u}</loc>' + (f'<lastmod>{lm.isoformat()}</lastmod>' if lm else '') + alts + '</url>')
    sm.append('</urlset>')
    write('sitemap.xml', '\n'.join(sm) + '\n')
    write('robots.txt', f'User-agent: *\nAllow: /\nDisallow: /admin/\n\nSitemap: {SITE}/sitemap.xml\n')
    for lang in LANGS:
        t = T[lang]
        items = []
        for n in [n for n in news if n[lang]][:20]:
            v = n[lang]
            dt = datetime(v['date'].year, v['date'].month, v['date'].day, 9, 0, tzinfo=timezone.utc)
            items.append(f'<item><title>{esc(v["title"])}</title><link>{SITE}{v["url"]}</link><guid>{SITE}{v["url"]}</guid>'
                         f'<pubDate>{format_datetime(dt)}</pubDate><description>{esc(v["summary"])}</description></item>')
        write(t['feed'].lstrip('/'), f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>{t["n_news"]} · {NAME}</title>'
              f'<link>{SITE}{t["news"]}</link><description>{t["feed_desc"]}</description><language>{lang}</language>'
              + ''.join(items) + '</channel></rss>\n')
    write('CNAME', SITE.split('//', 1)[1] + '\n')
    write('.nojekyll', '')
    n_en = sum(1 for n in news if n['en'])
    print(f'OK: {len(news)} noticias ({n_en} en inglés), {sum(len(v) for _, _, v in pages)} direcciones en el sitemap → {OUT}')
    if PROBLEMS:
        for m in PROBLEMS:
            print(f'::error::{m}')
        print(f'ERROR: {len(PROBLEMS)} problema(s) en el contenido: NO se publica (la web sigue como estaba).')
        sys.exit(1)


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
