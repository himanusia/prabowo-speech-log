/* Penyaring dan tema. Keduanya opsional — tanpa JS halaman tetap lengkap. */
(function () {
  'use strict';

  // --- tema terang/gelap -------------------------------------------------
  var saved = null;
  try { saved = localStorage.getItem('theme'); } catch (e) {}
  if (saved === 'light' || saved === 'dark') {
    document.documentElement.dataset.theme = saved;
  }
  document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var cur = document.documentElement.dataset.theme;
      if (!cur) {
        cur = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      }
      var next = cur === 'dark' ? 'light' : 'dark';
      document.documentElement.dataset.theme = next;
      try { localStorage.setItem('theme', next); } catch (e) {}
    });
  });

  // --- navigasi berbasis tombol -----------------------------------------
  document.querySelectorAll('[data-go]').forEach(function (el) {
    el.addEventListener('click', function () { window.location.href = el.dataset.go; });
  });

  // --- penyaring daftar -------------------------------------------------
  var q = document.getElementById('q');
  var list = document.getElementById('list');
  if (!q || !list) return;

  var items = Array.prototype.slice.call(list.querySelectorAll('li'));
  var counter = document.getElementById('count');
  var empty = document.getElementById('empty');
  var total = items.length;
  var indexPromise = null;

  // Indeks teks penuh dimuat sekali, hanya saat pengguna mulai mengetik.
  function loadIndex() {
    if (!indexPromise) {
      indexPromise = fetch('data/search.json', { cache: 'force-cache' })
        .then(function (r) { return r.ok ? r.json() : {}; })
        .catch(function () { return {}; });
    }
    return indexPromise;
  }

  var timer = null;
  function apply() {
    var term = q.value.trim().toLowerCase();
    if (!term) {
      items.forEach(function (li) { li.hidden = false; });
      if (counter) counter.textContent = total + ' pidato';
      if (empty) empty.hidden = true;
      return;
    }
    loadIndex().then(function (idx) {
      var shown = 0;
      items.forEach(function (li) {
        var link = li.querySelector('.entry');
        var id = link ? (link.getAttribute('href') || '').replace(/^pidato\/|\.html$/g, '') : '';
        var hay = (li.textContent || '').toLowerCase();
        var body = (idx[id] || '').toLowerCase();
        var hit = hay.indexOf(term) !== -1 || body.indexOf(term) !== -1;
        li.hidden = !hit;
        if (hit) shown++;
      });
      if (counter) counter.textContent = shown + ' dari ' + total + ' pidato';
      if (empty) empty.hidden = shown !== 0;
    });
  }

  q.addEventListener('input', function () {
    clearTimeout(timer);
    timer = setTimeout(apply, 110);
  });
})();
