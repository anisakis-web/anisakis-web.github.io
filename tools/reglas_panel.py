"""Genera las expresiones del panel (static/admin/config.yml) a partir de las reglas de build.py.

Así el panel y la publicación aplican exactamente las mismas normas: lo que el panel deja guardar es lo que
build.py publica. Ejecutar tras cambiar BODY_RULES o SHORTENERS en build.py:

    python tools/reglas_panel.py          (actualiza config.yml)
    python tools/reglas_panel.py --check  (solo comprueba que están sincronizadas; lo usa la publicación)
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import build  # noqa: E402

CFG = os.path.join(ROOT, 'static', 'admin', 'config.yml')


def ci(rx):
    """Versión sin distinción de mayúsculas para JavaScript (el panel no admite el modificador i)."""
    out, i = [], 0
    while i < len(rx):
        c = rx[i]
        if c == '\\':                       # secuencia de escape: se copia tal cual
            out.append(rx[i:i + 2])
            i += 2
            continue
        if c == '[':                        # clase de caracteres: se copia y se añaden las mayúsculas
            j = i + 1
            while rx[j] != ']' or rx[j - 1] == '\\':
                j += 1
            cls = rx[i:j]
            out.append(cls + ('A-Z' if 'a-z' in cls else '') + ']')
            i = j + 1
            continue
        out.append(f'[{c.lower()}{c.upper()}]' if c.isalpha() and c.isascii() else c)
        i += 1
    return ''.join(out)


def body_pattern():
    alts = '|'.join(ci(r) for r in build.BODY_RULES)
    return f'^(?![\\s\\S]*(?:{alts}))[\\s\\S]*$'


def url_pattern():
    sh = '|'.join(re.escape(s) for s in sorted(build.SHORTENERS))
    return f'^https://(?!(?:[a-zA-Z0-9-]+\\.)*(?:{ci(sh)})(?:[/?#]|$))[^\\s/@:]+\\.[a-zA-Z]{{2,}}(?:[/?#][^\\s]*)?$'


def replace(text, field, pattern):
    rx = re.compile(r"(- name: " + field + r"\n(?:(?: {8,}).*\n)*? {8,}pattern: \[')(.*?)(', )")
    new, n = rx.subn(lambda m: m.group(1) + pattern.replace("'", "''") + m.group(3), text, count=1)
    if n != 1:
        sys.exit(f'No se encontró el pattern del campo {field} en config.yml')
    return new


if __name__ == '__main__':
    text = open(CFG, encoding='utf-8').read()
    new = replace(replace(text, 'body', body_pattern()), 'url', url_pattern())
    if '--check' in sys.argv:
        if new != text:
            sys.exit('ERROR: las reglas del panel (config.yml) no coinciden con build.py: ejecutar tools/reglas_panel.py')
        print('Reglas del panel sincronizadas con build.py')
    else:
        open(CFG, 'w', encoding='utf-8', newline='\n').write(new)
        print('config.yml actualizado')
