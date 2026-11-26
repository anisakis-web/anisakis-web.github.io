"""Resumen de lo que se va a publicar, para revisarlo antes de aprobar el despliegue.

Lo ejecuta el workflow de publicación (paso «Resumen para la aprobación») y lo escribe en el resumen de la ejecución
($GITHUB_STEP_SUMMARY), que GitHub muestra en la misma página donde se aprueba. Compara lo que hay ahora en `main`
con lo que está publicado en la web (https://anisakis.com/version.txt, que escribe el propio workflow).

    python3 tools/resumen_cambios.py              → escribe el resumen (o lo muestra si no hay $GITHUB_STEP_SUMMARY)
    python3 tools/resumen_cambios.py --base <sha> → compara con ese commit (para probar en local)

Nunca hace fallar la publicación: si algo va mal, lo dice en el resumen y termina bien.
Los títulos vienen del panel (texto de terceros): se escapan para que no puedan dar formato engañoso al resumen.
"""
import os
import re
import subprocess
import sys
import urllib.request

SITE_VERSION = 'https://anisakis.com/version.txt'
NEWS = re.compile(r'^content/noticias/(es|en)/[^/]+\.md$')
IMG = re.compile(r'^static/img/noticias/[^/]+$')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, encoding='utf-8').stdout


def safe(text, limit=160):
    """Texto plano seguro para Markdown: sin saltos, sin HTML y sin caracteres de formato."""
    text = ' '.join(str(text).split())
    if len(text) > limit:
        text = text[:limit - 1] + '…'
    return re.sub(r'([\\`*_{}\[\]()<>#+!|~&])', r'\\\1', text) or '(sin título)'


def front(sha, path):
    """Título y si es borrador, leídos de la cabecera de la noticia en ese commit."""
    raw = git('show', f'{sha}:{path}')
    m = re.match(r'^---\s*\n(.*?)\n---', raw, re.S)
    head = m.group(1) if m else ''
    t = re.search(r'^title:\s*(.*)$', head, re.M)
    title = t.group(1).strip().strip('"\'') if t else ''
    draft = bool(re.search(r'^draft:\s*true\s*$', head, re.M))
    return title, draft


def base_commit(argv):
    if '--base' in argv:
        return argv[argv.index('--base') + 1], ''
    try:
        with urllib.request.urlopen(SITE_VERSION, timeout=10) as r:
            sha = r.read(100).decode('ascii', 'replace').strip()
        if re.fullmatch(r'[0-9a-f]{40}', sha) and subprocess.run(
                ['git', 'cat-file', '-e', f'{sha}^{{commit}}'], cwd=ROOT).returncode == 0:
            return sha, ''
        why = 'la versión publicada no aparece en el historial'
    except Exception as e:  # sin version.txt todavía, web caída, etc.
        why = f'no se pudo leer la versión publicada ({type(e).__name__})'
    return 'HEAD~1', f'⚠️ {why}: comparo con el commit anterior, puede faltar algún cambio.'


def main(argv):
    base, warn = base_commit(argv)
    out = ['## Qué se va a publicar en anisakis.com', '']
    if warn:
        out += [warn, '']
    commits = [l.split('\t', 2) for l in git('log', '--format=%h\t%an\t%s', f'{base}..HEAD').splitlines() if l]
    changes = [l.split('\t') for l in git('diff', '--name-status', '--no-renames', base, 'HEAD').splitlines() if l]

    news, images, other = [], [], []
    verbs = {'A': 'Nueva', 'M': 'Editada', 'D': 'Borrada'}
    for st, path in ((c[0][0], c[-1]) for c in changes):
        m = NEWS.match(path)
        if m:
            title, draft = front(base if st == 'D' else 'HEAD', path)
            line = f'- **{verbs.get(st, st)}** ({m.group(1).upper()}): {safe(title)}'
            if draft and st != 'D':
                line += ' — *borrador, no se publica*'
            news.append(line)
        elif IMG.match(path):
            images.append(f'- {"Imagen nueva" if st == "A" else "Imagen borrada" if st == "D" else "Imagen cambiada"}: '
                          f'`{safe(path.split("/")[-1], 80)}`')
        else:
            other.append(f'- `{safe(path, 120)}` ({st})')

    out += ['### Noticias', ''] + (news or ['- Sin cambios en las noticias.']) + ['']
    if images:
        out += ['### Imágenes de noticias', ''] + images + ['']
    if other:
        out += ['### ⚠️ Cambios fuera de las noticias', '',
                'El panel no hace estos cambios: solo deberían aparecer si el equipo de la web ha cambiado su código. '
                'Si no te suena, **no apruebes** y revisa el historial.', ''] + other + ['']
    out += ['### Cambios (commits)', '']
    for c in commits:
        h, author, msg = (c + ['', ''])[:3]
        files = [f for f in git('diff-tree', '--no-commit-id', '--name-only', '-r', '-m', h).splitlines() if f]
        only_news = bool(files) and all(NEWS.match(f) or IMG.match(f) for f in files)
        if msg.startswith('Panel:'):
            origin = '🖊️ Panel' if only_news else '⚠️ Dice «Panel» pero toca código'
        else:
            origin = '💻 Código'
        out.append(f'- `{safe(h, 12)}` {origin} — {safe(author, 60)}: {safe(msg, 140)}')
    if not commits:
        out.append('- Ninguno (se vuelve a publicar lo mismo).')
    out += ['', 'Lo marcado como 🖊️ Panel viene del panel de noticias (`/admin/`); 💻 Código, de cambios hechos fuera del panel.']

    text = '\n'.join(out) + '\n'
    dest = os.environ.get('GITHUB_STEP_SUMMARY')
    if dest:
        with open(dest, 'a', encoding='utf-8') as f:
            f.write(text)
    else:
        sys.stdout.write(text)


if __name__ == '__main__':
    try:
        main(sys.argv)
    except Exception as e:  # el resumen nunca debe impedir publicar
        print(f'::warning::No se pudo preparar el resumen de cambios: {type(e).__name__}: {e}')
