# anisakis.com

Web estática de *Anisakis International Information Site*.

## Cómo funciona

- `content/noticias/` — una noticia por archivo Markdown (`AAAA-MM-DD-titulo.md`) con una cabecera:
  ```
  ---
  title: "Título de la noticia"
  date: 2026-11-16
  image: "/img/noticias/nombre.webp"
  summary: "Resumen corto para el listado."
  ---
  Texto en Markdown. **Negrita**, *cursiva*, [enlace](https://…), listas con "- ".
  ```
  Para dejar una noticia sin publicar, añade `draft: true` a la cabecera.
- `content/paginas/` — páginas informativas (HTML).
- `content/legal/` — aviso legal, privacidad y cookies.
- `static/` — imágenes, estilos e iconos.

Cada cambio en la rama `main` regenera y publica la web automáticamente (GitHub Actions → GitHub Pages).

## Panel de noticias

En `https://www.anisakis.com/admin/` hay un panel (Sveltia CMS) para **crear, editar y borrar noticias** sin tocar
código. Solo gestiona `content/noticias/` y las imágenes de `static/img/noticias/`; el resto de la web se cambia
editando el repositorio.

- **Acceso:** cuenta de GitHub con verificación en dos pasos y permiso de escritura en este repositorio (que, por sí
  solo, permitiría cambiar todo: por eso existe el control de integridad de abajo). Se entra con «Iniciar sesión con
  un token de acceso»: un *fine-grained token* (`github_pat_…`) con acceso **solo a este repositorio**, permiso
  *Contents: Read and write* (nunca *Workflows*) y caducidad ≤ 90 días; la organización exige aprobarlo y bloquea los
  tokens clásicos. El navegador lo recuerda (mejor un perfil de navegador solo para el panel, sin extensiones).
- **Guardia (`static/admin/guard.js`, código propio):** se carga antes de Sveltia; no deja abrir el panel dentro de
  otra web (iframe) y borra al momento cualquier token que no sea *fine-grained*.
- **Control de integridad (en `.github/workflows/pages.yml`):** solo se publica si todo lo que no son noticias
  (`content/noticias/*.md`, `static/img/noticias/*.{webp,jpg,png,gif,avif}`) coincide con la huella `CODE_TREE`. Con un
  token de editor solo se pueden cambiar noticias. **Tras cambiar código:** commit, `bash tools/huella_codigo.sh
  --update` y commit de `pages.yml`. Cualquier problema de contenido también detiene la publicación (`::error::`) y
  GitHub avisa por correo (avisos@anisakis.com).
- **Reglas compartidas:** las normas del texto (`BODY_RULES`) y los acortadores (`SHORTENERS`) están en `build.py`;
  `python tools/reglas_panel.py` las copia a los patrones de `config.yml` y la publicación comprueba que coinciden.
- **Seguridad:** el panel funciona entero en el navegador (sin servidor propio ni servicios de terceros con acceso).
  `static/admin/index.html` lleva una política de seguridad (CSP) que solo deja cargar código desde esta web y solo
  hablar con la API de GitHub; excepciones acotadas, que no son código: tipografías (`cdn.jsdelivr.net/fontsource/`)
  y textos de idioma de la versión fijada (`unpkg.com/@sveltia/cms@VERSIÓN/locales/`). `build.py` trata todo lo que
  llega del panel como no fiable: solo enlaces `https://`, `mailto:` o internos; imagen principal solo de
  `/img/noticias/`; dirección (slug) solo `a-z0-9-`; texto escapado.
- **Enlaces:** en las noticias nuevas el texto **no admite enlaces ni direcciones web**: el panel no deja guardarlo y,
  si llegara por otra vía, la noticia no se publica. Las fuentes, vídeos y
  enlaces relacionados van en el apartado **«Fuentes y enlaces»** (campo `enlaces`: `tipo`, `nombre`, `url`) y se
  muestran al final («Fuente: …», «Vídeo relacionado: …»). `build.py` comprueba cada dirección
  (`check_external_url`): solo `https://` a un dominio público, sin usuario/contraseña, IP, puerto raro, dominios
  `xn--`, acortadores, redirecciones (otra dirección dentro), dominios comodín de IP (nip.io…) ni archivos
  ejecutables o comprimidos; las que no pasan detienen la publicación. Las mismas normas del texto se aplican al título,
  al resumen y al nombre visible de cada enlace. Las 17
  noticias anteriores al panel (`LEGACY_NEWS`, por huella SHA-256 de su texto) conservan sus enlaces dentro del texto
  mientras no se edite ese texto.
- **Aspecto:** nombre y logo de anisakis.com (`app_title`, `logo` en `config.yml`) y colores de la web en `static/admin/panel.css`, que también oculta el pie de Sveltia y los botones de acceso que no se usan.
- **Copia fija:** `static/admin/sveltia-cms.js` y `static/admin/chunks/` son Sveltia CMS **0.258.1** (npm
  `@sveltia/cms`, integridad sha512 y certificado de origen comprobados: compilado por GitHub Actions desde
  `sveltia/sveltia-cms`, etiqueta `v0.258.1`). SHA-256 de `sveltia-cms.js`:
  `7b4add3ae688e7b1604c235b5aac1d007c0a414bdeee49d0ceca7c80c5549c8a`.

### Actualizar Sveltia (solo si hace falta)

1. Elegir una versión publicada hace **al menos dos semanas**; leer sus notas de versión.
2. Descargar el paquete de npm en una carpeta vacía, comprobar la integridad (sha512 del registro) y el certificado de
   origen (`/-/npm/v1/attestations/@sveltia%2fcms@VERSIÓN`: repositorio `sveltia/sveltia-cms`, etiqueta `vVERSIÓN`).
3. Copiar `dist/sveltia-cms.js` y `dist/chunks/` (sin los `.map`), cambiar la versión en la CSP de
   `static/admin/index.html` y en este README (con el nuevo SHA-256).
4. Probar en local (abrir `/admin/`, revisar la consola: solo deben bloquearse servicios externos), revisión
   independiente y pruebas de ataque, PR con visto bueno y comprobación en la web publicada.
5. Si algo falla, volver al commit anterior.

## Probar en local

Solo hace falta Python 3.9 o superior, sin dependencias:

```
python build.py --serve
```

y abrir http://localhost:8000
