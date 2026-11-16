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

## Probar en local

Solo hace falta Python 3.9 o superior, sin dependencias:

```
python build.py --serve
```

y abrir http://localhost:8000
