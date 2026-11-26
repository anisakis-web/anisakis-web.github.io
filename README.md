# anisakis.com

Código de **Anisakis International Information Site** — [anisakis.com](https://anisakis.com), web informativa sobre el
anisakis, en español e inglés.

Es una web estática: un pequeño script de Python genera las páginas a partir de los textos y las noticias, y GitHub Pages
la publica. No hay servidor, base de datos ni formularios que guarden datos.

## Contenido

- `content/noticias/` — las noticias, una por archivo (español en `es/`, inglés en `en/`).
- `content/paginas/` y `content/legal/` — páginas informativas y textos legales.
- `static/` — imágenes, estilos e iconos. Los créditos de las imágenes que lo requieren están en
  [`IMAGENES.md`](IMAGENES.md).
- `build.py` — genera la web.

## Verla en local

Con Python 3.9 o superior, sin dependencias:

```
python build.py --serve
```

y abrir http://localhost:8000

## Contribuciones y seguridad

Este repositorio lo mantiene el equipo de la web; no se aceptan cambios externos.
Si crees haber encontrado un problema de seguridad, **no abras una incidencia pública**: escríbenos a
info@anisakis.com.

Los textos, imágenes y marcas pertenecen a sus titulares. Todos los derechos reservados.
