/* charts.js — grafik interaktif halaman arsip.

   Pustaka: Apache ECharts 5 (vendor/echarts.min.js, lisensi Apache-2.0).
   Data dibaca dari <script id="chart-data" type="application/json"> yang
   ditulis ke dalam HTML oleh build_site.py. Datanya ada di HTML, jadi
   perayap tetap bisa membacanya tanpa menjalankan JavaScript.

   Warna diambil dari token CSS (--primary, --fg, ...) supaya grafik ikut
   tema terang/gelap tanpa perlu definisi warna terpisah. */
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

  function v(name, fallback) {
    var x = getComputedStyle(document.documentElement).getPropertyValue(name);
    return (x && x.trim()) || fallback;
  }

  /* rupiah bukan, tapi format ribuan Indonesia tetap perlu titik */
  function nf(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.'); }

  function toRGBA(hex, a) {
    var h = (hex || '').trim().replace('#', '');
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    if (h.length !== 6) return hex;
    var r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
    return 'rgba(' + r + ',' + g + ',' + b + ',' + a + ')';
  }

  function theme() {
    return {
      primary: v('--primary', '#b8453f'),
      fg: v('--fg', '#241f20'),
      muted: v('--muted-fg', '#7a6b6a'),
      border: v('--border', '#ecdbd9'),
      card: v('--card', '#ffffff'),
      font: v('--font-sans', 'system-ui, sans-serif'),
      mono: v('--font-mono', 'monospace')
    };
  }

  function base(t) {
    return {
      backgroundColor: 'transparent',
      textStyle: { fontFamily: t.font, color: t.fg, fontSize: 12 },
      animationDuration: 520,
      animationEasing: 'cubicOut',
      tooltip: {
        backgroundColor: t.card,
        borderColor: t.border,
        borderWidth: 1,
        padding: [7, 10],
        textStyle: { color: t.fg, fontSize: 12, fontFamily: t.font },
        extraCssText: 'border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,.10);'
      }
    };
  }

  function axisLabel(t) {
    return { color: t.muted, fontSize: 11, fontFamily: t.font };
  }

  /* garis pisah vertikal antar label, supaya tidak terlihat menempel */
  function split(t) {
    return { lineStyle: { color: t.border, type: 'dashed', opacity: 0.65 } };
  }

  function mount(id, opt) {
    var el = document.getElementById(id);
    if (!el) return;
    var c = echarts.init(el, null, { renderer: 'canvas' });
    c.setOption(opt);
    CH.push(c);
  }

  /* ---------------------------------------------------------- 1. kata */
  function kata(t) {
    var d = D.words.slice(0, 14).reverse();
    return Object.assign(base(t), {
      grid: { left: 10, right: 74, top: 14, bottom: 14, containLabel: true },
      tooltip: Object.assign(base(t).tooltip, {
        trigger: 'axis', axisPointer: { type: 'shadow' },
        formatter: function (p) { return p[0].name + ': <b>' + nf(p[0].value) + '</b> kemunculan'; }
      }),
      xAxis: { type: 'value', show: false, max: d[d.length - 1] ? d[d.length - 1].value * 1.06 : null },
      yAxis: {
        type: 'category',
        data: d.map(function (x) { return x.name; }),
        axisLabel: axisLabel(t),
        axisLine: { show: false },
        axisTick: { show: false }
      },
      series: [{
        type: 'bar',
        data: d.map(function (x) { return x.value; }),
        barWidth: '58%',
        itemStyle: {
          borderRadius: [0, 4, 4, 0],
          color: function (p) { return toRGBA(t.primary, 0.42 + (p.dataIndex / d.length) * 0.58); }
        },
        label: {
          show: true, position: 'right', color: t.muted, fontSize: 11,
          fontFamily: t.mono,
          formatter: function (p) { return nf(p.value); }
        },
        emphasis: { itemStyle: { color: t.primary } }
      }]
    });
  }

  /* ------------------------------------------------- 2. program (treemap) */
  function program(t) {
    return Object.assign(base(t), {
      tooltip: Object.assign(base(t).tooltip, {
        formatter: function (p) { return p.name + ': <b>' + p.value + '%</b> pidato'; }
      }),
      series: [{
        type: 'treemap',
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        left: 0, right: 0, top: 0, bottom: 0,
        itemStyle: { borderColor: t.card, borderWidth: 3, gapWidth: 3 },
        label: {
          show: true, position: 'insideBottomLeft', color: '#fff',
          padding: [6, 7], lineHeight: 15,
          formatter: function (p) {
            var all = D.programs;
            var cukup = p.value >= all[Math.min(2, all.length - 1)].value * 0.55;
            return cukup ? '{n|' + p.name + '}\n{v|' + p.value + '%}' : '{v|' + p.value + '%}';
          },
          rich: {
            /* overflow break + width: kalau tidak, ECharts memotongnya
               jadi "Koper…" pada kotak yang sempit */
            n: { fontSize: 12, fontWeight: 700, color: '#fff', lineHeight: 16,
                 width: 92, overflow: 'break' },
            v: { fontSize: 11, fontFamily: t.mono, color: 'rgba(255,255,255,.85)',
                 lineHeight: 14, width: 92 }
          }
        },
        levels: [{
          color: D.programs.map(function (x, i) {
            return toRGBA(t.primary, 0.96 - (i / D.programs.length) * 0.52);
          })
        }],
        data: D.programs.map(function (x) { return { name: x.name, value: x.value }; })
      }]
    });
  }

  /* ------------------------------------------------------ 3. topik */
  function topik(t) {
    var d = D.topics.slice().reverse();
    return Object.assign(base(t), {
      grid: { left: 10, right: 74, top: 14, bottom: 14, containLabel: true },
      tooltip: Object.assign(base(t).tooltip, {
        trigger: 'axis', axisPointer: { type: 'shadow' },
        formatter: function (p) { return p[0].name + ': <b>' + p[0].value + '</b> per 1.000 token'; }
      }),
      xAxis: { type: 'value', show: false },
      yAxis: {
        type: 'category', data: d.map(function (x) { return x.name; }),
        axisLabel: axisLabel(t), axisLine: { show: false }, axisTick: { show: false }
      },
      series: [{
        type: 'bar', barWidth: '58%',
        data: d.map(function (x) { return x.value; }),
        itemStyle: {
          borderRadius: [0, 4, 4, 0],
          color: function (p) { return toRGBA(t.primary, 0.42 + (p.dataIndex / d.length) * 0.58); }
        },
        label: { show: true, position: 'right', color: t.muted, fontSize: 11, fontFamily: t.mono },
        emphasis: { itemStyle: { color: t.primary } }
      }]
    });
  }

  /* ------------------------------------------------- 4. cara menyapa */
  function sapa(t) {
    var d = D.framing;
    return Object.assign(base(t), {
      grid: { left: 0, right: 0, top: 34, bottom: 6, containLabel: true },
      tooltip: Object.assign(base(t).tooltip, {
        trigger: 'axis', axisPointer: { type: 'shadow' },
        formatter: function (p) { return p[0].name + ': <b>' + p[0].value + '</b> per 1.000 token'; }
      }),
      xAxis: {
        type: 'category', data: d.map(function (x) { return x.name; }),
        axisLabel: axisLabel(t), axisLine: { lineStyle: { color: t.border } }, axisTick: { show: false },
        splitLine: split(t) && undefined
      },
      yAxis: {
        type: 'value', splitLine: split(t),
        axisLabel: Object.assign(axisLabel(t), { fontFamily: t.mono })
      },
      series: [{
        type: 'bar', barMaxWidth: 46,
        data: d.map(function (x) { return x.value; }),
        itemStyle: {
          borderRadius: [5, 5, 0, 0],
          color: function (p) { return toRGBA(t.primary, 0.42 + (p.dataIndex / d.length) * 0.58); }
        },
        label: {
          show: true, position: 'top', color: t.fg, fontSize: 11,
          fontFamily: t.mono, fontWeight: 700
        },
        emphasis: { itemStyle: { color: t.primary } }
      }]
    });
  }

  /* ---------------------------------------------- 5. masalah (donat) */
  function masalah(t) {
    return Object.assign(base(t), {
      tooltip: Object.assign(base(t).tooltip, {
        formatter: function (p) { return p.name + ': <b>' + p.value + '%</b> pidato'; }
      }),
      legend: {
        type: 'scroll', orient: 'vertical', right: 0, top: 'center',
        itemWidth: 10, itemHeight: 10, itemGap: 18,
        textStyle: { color: t.fg, fontSize: 12, fontFamily: t.font },
        formatter: function (name) {
          var f = D.concepts.filter(function (x) { return x.name === name; })[0];
          return name + '  ' + (f ? f.value + '%' : '');
        }
      },
      series: [{
        type: 'pie', radius: ['58%', '82%'], center: ['30%', '50%'],
        avoidLabelOverlap: true,
        label: { show: false }, labelLine: { show: false },
        itemStyle: { borderColor: t.card, borderWidth: 3 },
        emphasis: { scale: true, scaleSize: 6 },
        data: D.concepts.map(function (x, i) {
          return { name: x.name, value: x.value, itemStyle: { color: toRGBA(t.primary, 0.95 - i * 0.26) } };
        })
      }]
    });
  }

  /* ------------------------------------------------ 6. panjang pidato */
  function panjang(t) {
    return Object.assign(base(t), {
      grid: { left: 0, right: 0, top: 36, bottom: 6, containLabel: true },
      tooltip: Object.assign(base(t).tooltip, {
        trigger: 'axis', axisPointer: { type: 'shadow' },
        formatter: function (p) {
          return '≤ ' + p[0].name + ' ribu token: <b>' + p[0].value + '</b> pidato';
        }
      }),
      xAxis: {
        type: 'category', data: D.length.labels,
        axisLabel: Object.assign(axisLabel(t), { fontFamily: t.mono }),
        axisLine: { lineStyle: { color: t.border } }, axisTick: { show: false }
      },
      yAxis: { type: 'value', splitLine: split(t), axisLabel: Object.assign(axisLabel(t), { fontFamily: t.mono }) },
      series: [{
        type: 'bar', barMaxWidth: 40,
        data: D.length.counts,
        itemStyle: { borderRadius: [5, 5, 0, 0], color: toRGBA(t.primary, 0.72) },
        label: { show: true, position: 'top', color: t.fg, fontSize: 11, fontFamily: t.mono, fontWeight: 700 },
        emphasis: { itemStyle: { color: t.primary } }
      }]
    });
  }

  /* ------------------------------------------------- 7. volume bulanan */
  function volume(t) {
    var m = D.months;
    return Object.assign(base(t), {
      grid: { left: 0, right: 14, top: 28, bottom: 6, containLabel: true },
      tooltip: Object.assign(base(t).tooltip, {
        trigger: 'axis',
        formatter: function (p) {
          var i = p[0].dataIndex;
          return m[i].month + '<br/><b>' + m[i].events + '</b> pidato<br/>'
            + nf(m[i].tokens) + ' token';
        }
      }),
      xAxis: {
        type: 'category', boundaryGap: false,
        data: m.map(function (x) { return x.month; }),
        axisLabel: Object.assign(axisLabel(t), {
          fontFamily: t.mono, interval: Math.max(0, Math.floor(m.length / 9) - 1)
        }),
        axisLine: { lineStyle: { color: t.border } }, axisTick: { show: false }
      },
      yAxis: {
        type: 'value', splitLine: split(t),
        axisLabel: Object.assign(axisLabel(t), { fontFamily: t.mono }),
        minInterval: 1
      },
      series: [{
        type: 'line', smooth: 0.35, symbol: 'circle', symbolSize: 7,
        data: m.map(function (x) { return x.events; }),
        lineStyle: { width: 2.4, color: t.primary },
        itemStyle: { color: t.primary, borderColor: t.card, borderWidth: 2 },
        emphasis: { scale: 1.6 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: toRGBA(t.primary, 0.30) },
            { offset: 1, color: toRGBA(t.primary, 0.02) }
          ])
        }
      }]
    });
  }

  /* --------------------------------------------------- 8. garis waktu */
  function waktu(t) {
    var d = D.timeline;
    return Object.assign(base(t), {
      grid: { left: 0, right: 14, top: 26, bottom: 6, containLabel: true },
      tooltip: Object.assign(base(t).tooltip, {
        trigger: 'item',
        formatter: function (p) {
          var x = d[p.dataIndex];
          return '<b>' + x.date + '</b><br/>' + x.title.slice(0, 90)
            + '<br/>' + nf(x.tokens) + ' token';
        }
      }),
      xAxis: {
        type: 'time', axisLine: { lineStyle: { color: t.border } },
        axisLabel: Object.assign(axisLabel(t), { fontFamily: t.mono, hideOverlap: true }),
        axisTick: { show: false }, splitLine: { show: false }
      },
      yAxis: {
        type: 'value', name: 'token', nameTextStyle: axisLabel(t),
        splitLine: split(t), axisLabel: Object.assign(axisLabel(t), { fontFamily: t.mono })
      },
      series: [{
        type: 'scatter',
        data: d.map(function (x) { return [x.date, x.tokens, x.title, x.url]; }),
        symbolSize: function (val) { return Math.max(5, Math.min(15, Math.sqrt(val[1]) / 6)); },
        itemStyle: { color: toRGBA(t.primary, 0.62), borderColor: t.primary, borderWidth: 1 },
        emphasis: { itemStyle: { color: t.primary, borderWidth: 2 } }
      }]
    });
  }

  var BUILDERS = [
    ['chart-kata', kata], ['chart-program', program], ['chart-topik', topik],
    ['chart-sapa', sapa], ['chart-masalah', masalah], ['chart-panjang', panjang],
    ['chart-volume', volume], ['chart-waktu', waktu]
  ];

  function draw() {
    var t = theme();
    CH.forEach(function (c) { c.dispose(); });
    CH = [];
    BUILDERS.forEach(function (b) {
      var el = document.getElementById(b[0]);
      if (!el) return;
      try { mount(b[0], b[1](t)); }
      catch (err) {
        el.setAttribute('data-chart-error', '1');
        if (window.console) console.warn('grafik gagal:', b[0], err);
      }
    });
  }

  var ro;
  window.addEventListener('resize', function () {
    clearTimeout(ro);
    ro = setTimeout(function () { CH.forEach(function (c) { c.resize(); }); }, 140);
  });

  /* ikut berubah saat tema diganti */
  new MutationObserver(function (m) {
    m.forEach(function (x) { if (x.attributeName === 'data-theme') draw(); });
  }).observe(document.documentElement, { attributes: true });

  draw();
})();
