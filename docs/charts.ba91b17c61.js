/* charts.js — grafik interaktif halaman arsip.

   Pustaka: Apache ECharts 5 (vendor/echarts.min.js, lisensi Apache-2.0).
   Data dibaca dari <script id="chart-data" type="application/json"> yang
   ditulis ke dalam HTML oleh build_site.py, jadi perayap bisa membacanya
   tanpa menjalankan JavaScript.

   PRINSIP: setiap tooltip menampilkan SEMUA ukuran yang tersedia untuk
   butir itu (hitungan, per 1.000 token, jumlah pidato, kemunculan,
   rentang tanggal). Grafik tidak menyimpulkan apa pun — pembaca yang
   menilai. Karena itu tidak ada kalimat tafsir di mana pun.

   Warna diambil dari token CSS (--primary, --fg, ...) supaya grafik ikut
   tema terang/gelap tanpa definisi warna terpisah. */
(function () {
  'use strict';

  var host = document.getElementById('chart-data');
  if (!host) return;
  var D;
  try { D = JSON.parse(host.textContent); } catch (e) { return; }
  if (!window.echarts) {
    document.documentElement.setAttribute('data-charts', 'gagal');
    return;
  }
  document.documentElement.setAttribute('data-charts', 'siap');

  var CH = [];
  /* Baris yang tampil saat ringkas. Tombol `semua` membuka seluruh data —
     datanya memang utuh di halaman, ini hanya soal tampilan. */
  var RINGKAS = { 'chart-kata': 14, 'chart-topik': 7, 'chart-sapa': 7, 'chart-masalah': 5 };
  var BUKA = {};

  function v(name, fallback) {
    var x = getComputedStyle(document.documentElement).getPropertyValue(name);
    return (x && x.trim()) || fallback;
  }
  function nf(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.'); }
  function toRGBA(hex, a) {
    var h = (hex || '').trim().replace('#', '');
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    if (h.length !== 6) return hex;
    return 'rgba(' + parseInt(h.slice(0, 2), 16) + ',' + parseInt(h.slice(2, 4), 16)
      + ',' + parseInt(h.slice(4, 6), 16) + ',' + a + ')';
  }
  function theme() {
    return {
      primary: v('--primary', '#b8453f'), fg: v('--fg', '#241f20'),
      muted: v('--muted-fg', '#6b5d5c'), border: v('--border', '#ecdbd9'),
      card: v('--card', '#ffffff'), font: v('--font-sans', 'system-ui, sans-serif'),
      mono: v('--font-mono', 'monospace')
    };
  }
  function base(t) {
    return {
      backgroundColor: 'transparent',
      textStyle: { fontFamily: t.font, color: t.fg, fontSize: 13 },
      animationDuration: 480, animationEasing: 'cubicOut',
      tooltip: {
        backgroundColor: t.card, borderColor: t.border, borderWidth: 1,
        padding: [8, 11], confine: true,
        textStyle: { color: t.fg, fontSize: 13, fontFamily: t.font },
        extraCssText: 'border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,.10);'
      }
    };
  }
  function axisLabel(t) { return { color: t.muted, fontSize: 12, fontFamily: t.font }; }
  function split(t) { return { lineStyle: { color: t.border, type: 'dashed', opacity: 0.6 } }; }

  /* baris fakta di dalam tooltip: label + angka, rata kanan */
  function fakta(rows) {
    return rows.filter(function (r) { return r[1] !== null && r[1] !== undefined && r[1] !== ''; })
      .map(function (r) {
        return '<div style="display:flex;gap:14px;justify-content:space-between">'
          + '<span style="opacity:.65">' + r[0] + '</span>'
          + '<b style="font-variant-numeric:tabular-nums">' + r[1] + '</b></div>';
      }).join('');
  }
  function kepala(x) { return '<div style="margin-bottom:4px;font-weight:700">' + x + '</div>'; }

  function mount(id, opt) {
    var el = document.getElementById(id);
    if (!el) return;
    var c = echarts.init(el, null, { renderer: 'canvas' });
    c.setOption(opt);
    CH.push(c);
  }

  /* ---------------------------------------------------------- 1. kata */
  function kata(t, buka) {
    var n = buka ? D.words.length : (RINGKAS['chart-kata'] || 14);
    var d = D.words.slice(0, n).reverse();
    var hi = d[d.length - 1] ? d[d.length - 1].count : 1;
    return Object.assign(base(t), {
      grid: { left: 10, right: 66, top: 12, bottom: 12, containLabel: true },
      tooltip: Object.assign(base(t).tooltip, {
        trigger: 'item',
        formatter: function (p) {
          var w = D.words.slice(0, n).reverse()[p.dataIndex];
          return kepala(w.name) + fakta([
            ['hitungan', nf(w.count)],
            ['per 1.000 token', w.per1000],
            ['pidato yang memuat', w.speeches + ' dari ' + D.coverage.punya],
            ['porsi pidato', w.share + '%']
          ]);
        }
      }),
      dataZoom: buka && d.length > 22 ? [
        { type: 'inside', yAxisIndex: 0, filterMode: 'none' },
        { type: 'slider', yAxisIndex: 0, width: 11, right: 2, filterMode: 'none',
          borderColor: 'transparent', fillerColor: toRGBA(t.primary, 0.18), showDetail: false }
      ] : [],
      xAxis: { type: 'value', show: false, max: hi * 1.06 },
      yAxis: {
        type: 'category', data: d.map(function (x) { return x.name; }),
        axisLabel: axisLabel(t), axisLine: { show: false }, axisTick: { show: false }
      },
      series: [{
        type: 'bar', barWidth: '60%',
        data: d.map(function (x) { return x.count; }),
        itemStyle: {
          borderRadius: [0, 4, 4, 0],
          color: function (p) { return toRGBA(t.primary, 0.34 + (p.dataIndex / d.length) * 0.66); }
        },
        label: { show: true, position: 'right', color: t.muted, fontSize: 12, fontFamily: t.mono,
                 formatter: function (p) { return nf(p.value); } },
        emphasis: { itemStyle: { color: t.primary } }
      }]
    });
  }

  /* ------------------------------------------------- 2. program (treemap) */
  function program(t) {
    var max = D.programs[0] ? D.programs[0].share : 1;
    return Object.assign(base(t), {
      tooltip: Object.assign(base(t).tooltip, {
        formatter: function (p) {
          var x = D.programs.filter(function (y) { return y.name === p.name; })[0] || {};
          return kepala(x.name + (x.full ? ' <span style="opacity:.6;font-weight:400">(' + x.full + ')</span>' : ''))
            + fakta([
              ['pidato yang membahas', (x.events || 0) + ' dari ' + D.coverage.punya],
              ['porsi pidato', x.share + '%'],
              ['jumlah kemunculan', nf(x.mentions)],
              ['kemunculan per pidato', x.per_event],
              ['pertama disebut', x.first],
              ['terakhir disebut', x.last]
            ]);
        }
      }),
      series: [{
        type: 'treemap', roam: false, nodeClick: false,
        breadcrumb: { show: false }, left: 0, right: 0, top: 0, bottom: 0,
        itemStyle: { borderColor: t.card, borderWidth: 3, gapWidth: 3 },
        label: {
          show: true, position: 'insideBottomLeft', color: '#fff',
          padding: [7, 8], lineHeight: 16,
          formatter: function (p) {
            var cukup = p.value >= max * 0.55;
            return cukup ? '{n|' + p.name + '}\n{v|' + p.value + '%}' : '{v|' + p.value + '%}';
          },
          rich: {
            n: { fontSize: 13, fontWeight: 700, color: '#fff', lineHeight: 17,
                 width: 96, overflow: 'break' },
            v: { fontSize: 12, fontFamily: t.mono, color: 'rgba(255,255,255,.85)',
                 lineHeight: 15, width: 96 }
          }
        },
        levels: [{
          color: D.programs.map(function (x, i) {
            return toRGBA(t.primary, 0.96 - (i / D.programs.length) * 0.5);
          })
        }],
        data: D.programs.map(function (x) { return { name: x.name, value: x.share }; })
      }]
    });
  }

  /* ------------------------------------------------------ 3. topik */
  function topik(t, buka) {
    var n = buka ? D.topics.length : (RINGKAS['chart-topik'] || 7);
    var d = D.topics.slice(0, n).reverse();
    return Object.assign(base(t), {
      grid: { left: 10, right: 66, top: 12, bottom: 12, containLabel: true },
      tooltip: Object.assign(base(t).tooltip, {
        trigger: 'item',
        formatter: function (p) {
          var x = d[p.dataIndex];
          return kepala(x.name) + fakta([
            ['kepadatan', x.per1000 + ' per 1.000 token'],
            ['jumlah kata', nf(x.count)],
            ['pidato yang memuat', (x.speeches || 0) + ' dari ' + D.coverage.punya],
            ['porsi pidato', x.share + '%']
          ]);
        }
      }),
      xAxis: { type: 'value', show: false },
      yAxis: { type: 'category', data: d.map(function (x) { return x.name; }),
               axisLabel: axisLabel(t), axisLine: { show: false }, axisTick: { show: false } },
      series: [{
        type: 'bar', barWidth: '60%',
        data: d.map(function (x) { return x.per1000; }),
        itemStyle: {
          borderRadius: [0, 4, 4, 0],
          color: function (p) { return toRGBA(t.primary, 0.34 + (p.dataIndex / d.length) * 0.66); }
        },
        label: { show: true, position: 'right', color: t.muted, fontSize: 12, fontFamily: t.mono },
        emphasis: { itemStyle: { color: t.primary } }
      }]
    });
  }

  /* ------------------------------------------------- 4. kata ganti */
  function sapa(t, buka) {
    var n = buka ? D.framing.length : (RINGKAS['chart-sapa'] || 7);
    var d = D.framing.slice(0, n);
    return Object.assign(base(t), {
      grid: { left: 0, right: 0, top: 34, bottom: 4, containLabel: true },
      tooltip: Object.assign(base(t).tooltip, {
        trigger: 'item',
        formatter: function (p) {
          var x = d[p.dataIndex];
          return kepala(x.name) + fakta([
            ['per 1.000 token', x.per1000],
            ['hitungan', nf(x.count)],
            ['pidato yang memuat', (x.speeches || 0) + ' dari ' + D.coverage.punya]
          ]);
        }
      }),
      xAxis: { type: 'category', data: d.map(function (x) { return x.name; }),
               axisLabel: axisLabel(t), axisLine: { lineStyle: { color: t.border } },
               axisTick: { show: false } },
      yAxis: { type: 'value', splitLine: split(t),
               axisLabel: Object.assign(axisLabel(t), { fontFamily: t.mono }) },
      series: [{
        type: 'bar', barMaxWidth: 46,
        data: d.map(function (x) { return x.per1000; }),
        itemStyle: {
          borderRadius: [5, 5, 0, 0],
          color: function (p) { return toRGBA(t.primary, 0.34 + (p.dataIndex / d.length) * 0.66); }
        },
        label: { show: true, position: 'top', color: t.fg, fontSize: 12,
                 fontFamily: t.mono, fontWeight: 700 },
        emphasis: { itemStyle: { color: t.primary } }
      }]
    });
  }

  /* ---------------------------------------------- 5. kategori masalah */
  function masalah(t, buka) {
    var n = buka ? D.concepts.length : (RINGKAS['chart-masalah'] || 5);
    var d = D.concepts.slice(0, n);
    return Object.assign(base(t), {
      tooltip: Object.assign(base(t).tooltip, {
        formatter: function (p) {
          var x = d.filter(function (y) { return y.name === p.name; })[0] || {};
          return kepala(x.name)
            + (x.full ? '<div style="opacity:.6;margin-bottom:5px">' + x.full + '</div>' : '')
            + fakta([
              ['pidato yang membahas', (x.events || 0) + ' dari ' + D.coverage.punya],
              ['porsi pidato', x.share + '%'],
              ['jumlah kemunculan', nf(x.mentions)],
              ['kemunculan per pidato', x.per_event],
              ['pertama', x.first], ['terakhir', x.last]
            ]);
        }
      }),
      legend: {
        type: 'scroll', orient: 'vertical', right: 0, top: 'center',
        itemWidth: 10, itemHeight: 10, itemGap: 18,
        textStyle: { color: t.fg, fontSize: 13, fontFamily: t.font },
        formatter: function (name) {
          var f = d.filter(function (x) { return x.name === name; })[0];
          return name + '  ' + (f ? f.share + '%' : '');
        }
      },
      series: [{
        type: 'pie', radius: ['56%', '80%'], center: ['28%', '50%'],
        avoidLabelOverlap: true, label: { show: false }, labelLine: { show: false },
        itemStyle: { borderColor: t.card, borderWidth: 3 },
        emphasis: { scale: true, scaleSize: 6 },
        data: d.map(function (x, i) {
          return { name: x.name, value: x.share,
                   itemStyle: { color: toRGBA(t.primary, 0.95 - i * 0.26) } };
        })
      }]
    });
  }

  /* ------------------------------------------------ 6. panjang pidato */
  function panjang(t) {
    return Object.assign(base(t), {
      grid: { left: 0, right: 0, top: 36, bottom: 4, containLabel: true },
      tooltip: Object.assign(base(t).tooltip, {
        trigger: 'axis', axisPointer: { type: 'shadow' },
        formatter: function (p) {
          return kepala('≤ ' + p[0].name + ' ribu token')
            + fakta([['jumlah pidato', p[0].value]]);
        }
      }),
      xAxis: { type: 'category', data: D.length.labels,
               axisLabel: Object.assign(axisLabel(t), { fontFamily: t.mono }),
               axisLine: { lineStyle: { color: t.border } }, axisTick: { show: false } },
      yAxis: { type: 'value', splitLine: split(t),
               axisLabel: Object.assign(axisLabel(t), { fontFamily: t.mono }) },
      series: [{
        type: 'bar', barMaxWidth: 40, data: D.length.counts,
        itemStyle: { borderRadius: [5, 5, 0, 0], color: toRGBA(t.primary, 0.72) },
        label: { show: true, position: 'top', color: t.fg, fontSize: 12,
                 fontFamily: t.mono, fontWeight: 700 },
        emphasis: { itemStyle: { color: t.primary } }
      }]
    });
  }

  /* ------------------------------------------------- 7. volume bulanan */
  function volume(t) {
    var m = D.months;
    return Object.assign(base(t), {
      grid: { left: 0, right: 12, top: 30, bottom: 4, containLabel: true },
      tooltip: Object.assign(base(t).tooltip, {
        trigger: 'axis',
        formatter: function (p) {
          var x = m[p[0].dataIndex];
          return kepala(x.month) + fakta([
            ['jumlah pidato', x.events], ['token', nf(x.tokens)],
            ['rata-rata token', nf(Math.round(x.tokens / Math.max(1, x.events)))]
          ]);
        }
      }),
      xAxis: { type: 'category', boundaryGap: false,
               data: m.map(function (x) { return x.month; }),
               axisLabel: Object.assign(axisLabel(t), {
                 fontFamily: t.mono, interval: Math.max(0, Math.floor(m.length / 9) - 1) }),
               axisLine: { lineStyle: { color: t.border } }, axisTick: { show: false } },
      yAxis: { type: 'value', splitLine: split(t),
               axisLabel: Object.assign(axisLabel(t), { fontFamily: t.mono }), minInterval: 1 },
      series: [{
        type: 'line', smooth: 0.35, symbol: 'circle', symbolSize: 7,
        data: m.map(function (x) { return x.events; }),
        lineStyle: { width: 2.4, color: t.primary },
        itemStyle: { color: t.primary, borderColor: t.card, borderWidth: 2 },
        emphasis: { scale: 1.7 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: toRGBA(t.primary, 0.30) },
            { offset: 1, color: toRGBA(t.primary, 0.02) }
          ])
        }
      }]
    });
  }

  /* ------------------------------------------- 8. kata ganti per tahun */
  function tahun(t) {
    var y = D.years;
    return Object.assign(base(t), {
      grid: { left: 0, right: 0, top: 44, bottom: 4, containLabel: true },
      tooltip: Object.assign(base(t).tooltip, {
        trigger: 'axis', axisPointer: { type: 'shadow' },
        formatter: function (p) {
          var x = y[p[0].dataIndex];
          return kepala(x.year) + fakta([
            ['jumlah pidato', x.speeches], ['token', nf(x.tokens)],
            ['kita per 1.000', x.kita], ['saya per 1.000', x.saya],
            ['rasio kita : saya', x.ratio]
          ]);
        }
      }),
      legend: { top: 0, itemWidth: 10, itemHeight: 10, itemGap: 14,
                textStyle: { color: t.fg, fontSize: 12, fontFamily: t.font } },
      xAxis: { type: 'category', data: y.map(function (x) { return x.year; }),
               axisLabel: Object.assign(axisLabel(t), { fontFamily: t.mono }),
               axisLine: { lineStyle: { color: t.border } }, axisTick: { show: false } },
      yAxis: { type: 'value', splitLine: split(t),
               axisLabel: Object.assign(axisLabel(t), { fontFamily: t.mono }) },
      series: [
        { name: 'kita', type: 'bar', barMaxWidth: 26,
          data: y.map(function (x) { return x.kita; }),
          itemStyle: { borderRadius: [4, 4, 0, 0], color: toRGBA(t.primary, 0.9) } },
        { name: 'saya', type: 'bar', barMaxWidth: 26,
          data: y.map(function (x) { return x.saya; }),
          itemStyle: { borderRadius: [4, 4, 0, 0], color: toRGBA(t.primary, 0.4) } }
      ]
    });
  }

  /* --------------------------------------------------- 9. garis waktu */
  function waktu(t) {
    var d = D.timeline;
    return Object.assign(base(t), {
      grid: { left: 0, right: 12, top: 24, bottom: 4, containLabel: true },
      tooltip: Object.assign(base(t).tooltip, {
        trigger: 'item',
        formatter: function (p) {
          var x = d[p.dataIndex];
          return kepala(x.date) + '<div style="margin-bottom:5px;max-width:340px;white-space:normal">'
            + x.title + '</div>'
            + fakta([['token', nf(x.tokens)], ['kata unik', nf(x.words)],
                     ['unggahan', x.uploads]]);
        }
      }),
      xAxis: { type: 'time', axisLine: { lineStyle: { color: t.border } },
               axisLabel: Object.assign(axisLabel(t), { fontFamily: t.mono, hideOverlap: true }),
               axisTick: { show: false }, splitLine: { show: false } },
      yAxis: { type: 'value', name: 'token', nameTextStyle: axisLabel(t),
               splitLine: split(t),
               axisLabel: Object.assign(axisLabel(t), { fontFamily: t.mono }) },
      series: [{
        type: 'scatter',
        data: d.map(function (x) { return [x.date, x.tokens, x.title, x.url]; }),
        symbolSize: function (val) { return Math.max(5, Math.min(16, Math.sqrt(val[1]) / 6)); },
        itemStyle: { color: toRGBA(t.primary, 0.6), borderColor: t.primary, borderWidth: 1 },
        emphasis: { itemStyle: { color: t.primary, borderWidth: 2 } }
      }]
    });
  }

  /* ---------------------------------------------- 10. kelengkapan arsip */
  function kelengkapan(t) {
    var c = D.coverage;
    var sisa = Math.max(0, c.era - c.punya);
    return Object.assign(base(t), {
      grid: { left: 0, right: 0, top: 34, bottom: 4, containLabel: true },
      tooltip: Object.assign(base(t).tooltip, {
        trigger: 'item',
        formatter: function (p) { return kepala(p.name) + fakta([['video', nf(p.value)]]); }
      }),
      xAxis: { type: 'value', show: false },
      yAxis: { type: 'category', data: ['arsip'], show: false },
      series: [
        { name: 'sudah masuk arsip', type: 'bar', stack: 'a', barWidth: 34,
          data: [c.punya], itemStyle: { color: t.primary, borderRadius: [4, 0, 0, 4] },
          label: { show: true, position: 'inside', color: '#fff', fontSize: 12,
                   fontWeight: 700, formatter: function (p) { return nf(p.value); } } },
        { name: 'belum ditarik', type: 'bar', stack: 'a', barWidth: 34,
          data: [sisa], itemStyle: { color: toRGBA(t.primary, 0.18), borderRadius: [0, 4, 4, 0] },
          label: { show: true, position: 'inside', color: t.fg, fontSize: 12,
                   fontWeight: 700, formatter: function (p) { return nf(p.value); } } }
      ]
    });
  }

  var BUILDERS = [
    ['chart-program', program], ['chart-kata', kata], ['chart-topik', topik],
    ['chart-sapa', sapa], ['chart-masalah', masalah], ['chart-panjang', panjang],
    ['chart-volume', volume], ['chart-tahun', tahun], ['chart-waktu', waktu],
    ['chart-kelengkapan', kelengkapan]
  ];

  function draw() {
    var t = theme();
    CH.forEach(function (c) { c.dispose(); });
    CH = [];
    BUILDERS.forEach(function (b) {
      if (!document.getElementById(b[0])) return;
      try { mount(b[0], b[1](t, !!BUKA[b[0]])); }
      catch (err) {
        document.getElementById(b[0]).setAttribute('data-chart-error', '1');
        if (window.console) console.warn('grafik gagal:', b[0], err);
      }
    });
    hitung();
  }

  var KUNCI = { 'chart-kata': 'words', 'chart-topik': 'topics', 'chart-sapa': 'framing',
                'chart-masalah': 'concepts', 'chart-program': 'programs' };

  function hitung() {
    /* tombol untuk grafik yang datanya sudah tampil penuh: sembunyikan */
    document.querySelectorAll('[data-lebih]').forEach(function (b) {
      var id = b.getAttribute('data-lebih');
      if (!KUNCI[id]) b.hidden = true;
    });
    Object.keys(KUNCI).forEach(function (id) {
      var total = (D[KUNCI[id]] || []).length;
      var batas = RINGKAS[id] || total;
      var el = document.querySelector('[data-jumlah="' + id + '"]');
      if (el) el.textContent = (BUKA[id] ? total : Math.min(total, batas)) + ' / ' + total;
      var btn = document.querySelector('[data-lebih="' + id + '"]');
      if (btn) {
        btn.hidden = total <= batas;
        btn.textContent = BUKA[id] ? 'ringkas' : 'semua';
        btn.setAttribute('aria-expanded', BUKA[id] ? 'true' : 'false');
      }
    });
  }

  document.addEventListener('click', function (ev) {
    var b = ev.target.closest ? ev.target.closest('[data-lebih]') : null;
    if (!b) return;
    var id = b.getAttribute('data-lebih');
    BUKA[id] = !BUKA[id];
    draw();
  });

  var ro;
  window.addEventListener('resize', function () {
    clearTimeout(ro);
    ro = setTimeout(function () { CH.forEach(function (c) { c.resize(); }); }, 140);
  });

  new MutationObserver(function (m) {
    m.forEach(function (x) { if (x.attributeName === 'data-theme') draw(); });
  }).observe(document.documentElement, { attributes: true });

  draw();
})();
