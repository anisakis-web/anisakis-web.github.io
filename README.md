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

- **Acceso:** cuenta de GitHub con verificación en dos pasos y permiso de escritura en este repositorio (nada más).
  Se entra con «Iniciar sesión con un token de acceso»: un *fine-grained token* con acceso **solo a este
  repositorio**, permiso *Contents: Read and write* y caducidad. El navegador lo recuerda. El botón «Iniciar sesión
  con GitHub» no se usa (necesitaría un servidor de autenticación que no tenemos).
- **Seguridad:** el panel funciona entero en el navegador (sin servidor propio ni servicios de terceros con acceso).
  `static/admin/index.html` lleva una política de seguridad (CSP) que solo deja cargar código desde esta web y solo
  hablar con la API de GitHub; excepciones acotadas, que no son código: tipografías (`cdn.jsdelivr.net/fontsource/`)
  y textos de idioma de la versión fijada (`unpkg.com/@sveltia/cms@VERSIÓN/locales/`). `build.py` trata todo lo que
  llega del panel como no fiable: solo enlaces `https://`, `mailto:` o internos; imagen principal solo de
  `/img/noticias/`; dirección (slug) solo `a-z0-9-`; texto escapado.
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
