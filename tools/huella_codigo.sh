#!/usr/bin/env bash
# Huella del «código» de la web: todo el repositorio MENOS las noticias, sus imágenes y los workflows.
# La publicación (.github/workflows/pages.yml) solo publica si la huella coincide con la que lleva escrita.
# Así, con la clave de un editor solo se pueden cambiar noticias: cualquier otro cambio detiene la publicación.
#
#   bash tools/huella_codigo.sh            → muestra la huella del último commit (HEAD)
#   bash tools/huella_codigo.sh --update   → la escribe en pages.yml (hacer commit de ese cambio después)
#
# Usar SIEMPRE sobre cambios ya guardados (commit): se calcula sobre HEAD, no sobre archivos sin guardar.
set -euo pipefail
cd "$(dirname "$0")/.."
h=$(git ls-tree -r HEAD \
    | grep -vE $'\t(content/noticias/(es|en)/[^/]+\\.md|static/img/noticias/[^/]+\\.(webp|jpe?g|png|gif|avif)|\\.github/workflows/[^/]+)$' \
    | sha256sum | cut -c1-64)
if [ "${1:-}" = "--update" ]; then
  sed -i -E "s/^(\s*CODE_TREE: )[0-9a-f]{64}$/\1$h/" .github/workflows/pages.yml
  grep -q "CODE_TREE: $h" .github/workflows/pages.yml || { echo "No se pudo actualizar pages.yml"; exit 1; }
  echo "pages.yml actualizado: $h"
else
  echo "$h"
fi
