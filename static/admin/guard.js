/* Guardia del panel de noticias de anisakis.com (código propio; se carga antes que Sveltia CMS).
 *  1. Si alguien mete el panel dentro de otra web (iframe), no se carga: evita engaños de «clickjacking».
 *  2. Solo admite claves de GitHub de tipo «fine-grained» (empiezan por github_pat_): si se pega una clave clásica o con
 *     más permisos, se borra al instante del navegador y se avisa. El panel solo debe usarse con claves limitadas a
 *     este repositorio. */
(function () {
  'use strict';
  var KEY = 'sveltia-cms.user';

  if (window.top !== window.self) {
    document.body.textContent = 'Por seguridad, el panel de noticias solo se puede abrir directamente en www.anisakis.com/admin/.';
    return;
  }

  function badToken() {
    try {
      var u = JSON.parse(localStorage.getItem(KEY) || 'null');
      return !!(u && u.token && !/^github_pat_[A-Za-z0-9_]{20,}$/.test(u.token));
    } catch (e) {
      return false;
    }
  }

  function check() {
    if (!badToken()) return;
    try { localStorage.removeItem(KEY); } catch (e) { /* nada */ }
    alert('Esa clave no es válida para este panel.\n\nUsa una clave «fine-grained» de GitHub (empieza por github_pat_), ' +
          'limitada solo al repositorio de la web y con permiso «Contents: Read and write». La clave se ha borrado de este navegador.');
    location.reload();
  }

  check();
  setInterval(check, 1000);

  var s = document.createElement('script');
  s.src = '/admin/sveltia-cms.js';
  document.body.appendChild(s);
})();
