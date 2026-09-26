#!/usr/bin/env python3
"""
build_site.py — render HTML statis dari arsip pidato.

Keputusan penting: seluruh transkrip ditulis KE DALAM HTML, bukan diambil lewat
JavaScript. Situsnya harus bisa dibaca scraper, mesin pencari, dan siapa pun
yang mematikan JS. JavaScript hanya penyaring opsional, bukan perender.

Keluaran ke docs/ (siap dipakai Cloudflare Pages / GitHub Pages):
    index.html            daftar semua pidato
    pidato/<slug>.html    satu halaman per pidato + transkrip penuh
    cakupan.html          peta cakupan dan lubangnya
    tentang.html          metode + janji traceability
    404.html
    sitemap.xml, robots.txt
    theme.css, app.js
    data/*.json           versi mesin dari data yang sama
"""

from __future__ import annotations

import html
import json
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
WEB = ROOT / "web"
DOCS = ROOT / "docs"
WIB = timezone(timedelta(hours=7))

SITE_NAME = "Arsip Pidato Presiden Prabowo"
SITE_BASE = "https://pidato-presiden-prabowo.himanusia.com"
SITE_TAGLINE = "Log pidato, sambutan, dan pernyataan resmi — lengkap dengan sumber yang bisa ditelusuri."


def e(text) -> str:
    return html.escape(str(text if text is not None else ""), quote=True)


def fmt_int(n) -> str:
    if n is None:
        return "—"
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def fmt_date(iso: str) -> str:
    try:
        d = datetime.fromisoformat(iso)
    except Exception:
        return iso
    bulan = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
             "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    return f"{d.day} {bulan[d.month]} {d.year}"


def hms(seconds) -> str:
    if not seconds:
        return "—"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def ts_short(seconds) -> str:
    s = int(seconds or 0)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def yt_at(video_id: str, t) -> str:
    return f"https://www.youtube.com/watch?v={video_id}&t={int(t or 0)}s"


# Ikon YouTube untuk tautan video. Manusia butuh ini supaya tahu itu video.
YT_ICON = ('<svg width="15" height="15" viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
           '<path fill="#ff0000" d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.6 12 3.6 12 3.6s-7.5 0-9.4.5'
           'A3 3 0 0 0 .5 6.2 31 31 0 0 0 0 12a31 31 0 0 0 .5 5.8 3 3 0 0 0 2.1 2.1c1.9.5 9.4.5 9.4.5'
           's7.5 0 9.4-.5a3 3 0 0 0 2.1-2.1A31 31 0 0 0 24 12a31 31 0 0 0-.5-5.8z"/>'
           '<path fill="#fff" d="M9.6 15.6 15.8 12 9.6 8.4z"/></svg>')


# Tingkat sumber, diterjemahkan untuk pembaca manusia.
TIER_LABEL = {
    "official": "kanal resmi",
    "media": "kanal media",
    "full_media": "kanal media",
    "resmi_setkab": "transkrip resmi",
}


# Cara pengambilan teks, untuk pembaca manusia.
FETCH_LABEL = {
    "caption_api": "takarir YouTube",
    "transcript_panel": "panel transkrip YouTube",
    "setkab": "transkrip resmi Setkab",
    "setkab_api": "transkrip resmi Setkab",
    "setkab_rest_api": "transkrip resmi Setkab",
}


def _bersih(teks: str) -> str:
    """Judul unggahan tanpa bumbu berita, untuk tabel unggahan."""
    try:
        from rapikan_judul import bersih
        return bersih(teks or "")
    except Exception:
        return teks or ""



def judul(s: dict) -> str:
    """Judul tampilan untuk manusia, bukan judul berita kanal.

    Judul asli tetap utuh di `title` (untuk penelusuran); yang ditampilkan
    adalah versi bersih. `title_tampilan` diisi scripts/rapikan_judul.py;
    kalau belum ada, fungsi bersih() dari modul yang sama dipakai langsung.
    """
    if s.get("title_tampilan"):
        return s["title_tampilan"]
    judul_asli = s.get("title") or ""
    try:
        from rapikan_judul import bersih  # modul sebelah di scripts/
        return bersih(judul_asli)
    except Exception:
        return judul_asli


def _host(u: str) -> str:
    try:
        from urllib.parse import urlparse
        h = urlparse(u).netloc.lower()
        return h[4:] if h.startswith("www.") else (h or u)
    except Exception:
        return u


def _momen_load() -> list[dict]:
    p = DATA / "momen.json"
    if not p.exists():
        return []
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    items = d.get("momen") if isinstance(d, dict) else d
    return [m for m in (items or []) if isinstance(m, dict)]


def _momen_sumber(m: dict) -> str:
    out = []
    for u in (m.get("sumber") or [])[:4]:
        if isinstance(u, str) and u.startswith("http"):
            out.append(f'<a href="{e(u)}" rel="noopener nofollow">{e(_host(u))}</a>')
    return " ".join(out)


def _strip_momen(momen: list[dict]) -> str:
    """Beranda: momen yang ramai dibicarakan, kutipan + sumbernya."""
    if not momen:
        return ""

    def kartu(m: dict) -> str:
        vid = ""
        if m.get("video_url"):
            vid = (f'<a class="yt-link" href="{e(m["video_url"])}" rel="noopener nofollow">'
                   f'{YT_ICON} Tonton</a>')
        elif m.get("pidato_id"):
            vid = f'<a href="pidato/{e(m["pidato_id"])}.html">Buka pidatonya</a>'
        return f"""    <article class="momen">
      <div class="momen__h"><span class="chip chip--accent">{e(m.get('tanggal') or '')}</span>
        <span class="hint">{e((m.get('acara') or '')[:90])}</span></div>
      <blockquote>&ldquo;{e(m.get('kutipan') or '')}&rdquo;</blockquote>
      <p class="momen__k">{e(m.get('konteks') or '')}</p>
      <p class="momen__f">{vid}<span class="momen__src">{_momen_sumber(m)}</span></p>
    </article>"""

    tampil = [kartu(m) for m in momen[:12]]
    sisa = [kartu(m) for m in momen[12:]]
    lain = ""
    if sisa:
        lain = ('    <details class="momen__more">\n'
                f'      <summary>Lihat {len(sisa)} momen lainnya</summary>\n'
                '      <div class="momen__grid">\n'
                + chr(10).join(sisa) + "\n"
                '      </div>\n'
                '    </details>\n')
    return f"""  <section class="blok" id="ramai">
    <h2>Yang ramai dibicarakan</h2>
    <p class="blok__d">Kutipan dari pidato yang jadi pembicaraan publik, lengkap dengan sumber beritanya.</p>
    <div class="momen__grid">
{chr(10).join(tampil)}
    </div>
{lain}  </section>
"""


def _sorotan(momen: list[dict]) -> str:
    """Halaman pidato: momen dari pidato ini yang ramai dibicarakan."""
    if not momen:
        return ""
    items = []
    for m in momen:
        konteks = " ".join(x for x in ((m.get("konteks") or "").strip(),
                                       (m.get("ramai") or "").strip()) if x)
        items.append(f"""    <div class="sorotan">
      <blockquote>&ldquo;{e(m.get('kutipan') or '')}&rdquo;</blockquote>
      <p class="momen__k">{e(konteks)}</p>
      <p class="momen__f">{_momen_sumber(m)}</p>
    </div>""")
    return f"""  <section style="margin-top:1.25rem">
    <h2 style="font-size:var(--step-1)">Yang ramai dibicarakan</h2>
{chr(10).join(items)}
  </section>
"""


# --------------------------------------------------------------------- kerangka

ASSET_V = {"css": "", "js": ""}


def page(title: str, body: str, *, desc: str = "", canonical: str = "",
         jsonld: str = "", active: str = "", rel_root: str = "") -> str:
    return f"""<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc or SITE_TAGLINE)}">
<link rel="canonical" href="{e(SITE_BASE + canonical)}">
<meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{e(SITE_NAME)}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc or SITE_TAGLINE)}">
<meta property="og:url" content="{e(SITE_BASE + canonical)}">
<meta name="twitter:card" content="summary">
<link rel="stylesheet" href="{rel_root}theme.{ASSET_V['css']}.css">
<link rel="alternate" type="application/json" href="{rel_root}data/index.json" title="Indeks JSON">
<link rel="icon" type="image/svg+xml" href="{rel_root}favicon.{ASSET_V['favicon']}.svg">
<script type="application/ld+json">{jsonld}</script>
<script type="speculationrules">
{{"prerender":[{{"where":{{"href_matches":"/*"}},"eagerness":"moderate"}}]}}
</script>
</head>
<body>
<header class="top">
  <div class="wrap top__row">
    <div class="brand">
      <span class="brand__mark">&#9632;</span>
      <span class="brand__name"><a href="{rel_root}index.html" style="color:inherit">{e(SITE_NAME)}</a></span>
    </div>
    <nav class="nav" aria-label="Navigasi utama">
      <button type="button" data-go="{rel_root}index.html" {'aria-current="page"' if active == 'beranda' else ''}>Beranda</button>
      <button type="button" data-go="{rel_root}daftar.html" {'aria-current="page"' if active == 'daftar' else ''}>Daftar</button>
      <button type="button" data-go="{rel_root}cakupan.html" {'aria-current="page"' if active == 'cakupan' else ''}>Cakupan</button>
      <button type="button" data-go="{rel_root}tentang.html" {'aria-current="page"' if active == 'tentang' else ''}>Tentang</button>
      <button type="button" data-theme-toggle title="Ganti tema terang/gelap" aria-label="Ganti tema">&#9681;</button>
    </nav>
  </div>
</header>
<main class="wrap">
{body}
</main>
<footer class="wrap">
  <p>{e(SITE_NAME)} &middot; <a href="{rel_root}data/index.json">data JSON</a></p>
  <p class="hint">Sumber teks: takarir YouTube dan transkrip resmi Sekretariat Kabinet. Periksa video aslinya sebelum mengutip.</p>
</footer>
<script src="{rel_root}vendor/echarts.{ASSET_V['vendor']}.min.js" defer></script>
<script src="{rel_root}charts.{ASSET_V['charts']}.js" defer></script>
<script src="{rel_root}app.{ASSET_V['js']}.js" defer></script>
</body>
</html>
"""


# ------------------------------------------------------------------ bentuk grafik

def _treemap_rects(values):
    """Tata letak treemap sederhana: belah dua berulang, menghasilkan (x,y,w,h) persen."""
    if not values or sum(values) <= 0:
        return []
    out = []

    def bagi(areas, x, y, w, h):
        if not areas:
            return
        if len(areas) == 1:
            out.append((x, y, w, h))
            return
        total = sum(areas)
        acc, i = 0.0, 0
        for i in range(len(areas)):
            acc += areas[i]
            if acc >= total / 2:
                break
        kiri, kanan = areas[:i + 1], areas[i + 1:]
        porsi = sum(kiri) / total
        if w >= h:
            bagi(kiri, x, y, w * porsi, h)
            bagi(kanan, x + w * porsi, y, w * (1 - porsi), h)
        else:
            bagi(kiri, x, y, w, h * porsi)
            bagi(kanan, x, y + h * porsi, w, h * (1 - porsi))

    bagi([v / sum(values) * 100 * 100 for v in values], 0.0, 0.0, 100.0, 100.0)
    return out


def _treemap(items, min_label=6.0):
    """Treemap: luas kotak = besar porsi. Bentuk yang sama sekali beda dari batang."""
    if not items:
        return ""
    rects = _treemap_rects([x["share"] for x in items])
    hi = max(x["share"] for x in items) or 1
    parts = []
    for (x, y, w, h), it in zip(rects, items):
        kuat = 30 + (it["share"] / hi) * 55
        bg = f"color-mix(in srgb, var(--primary) {kuat:.0f}%, var(--card))"
        terang = it["share"] / hi > 0.55
        fg = "color:#fff" if terang else "color:var(--fg)"
        isi = (f'<b>{e(it["label"])}</b><span>{it["share"]:.0f}%</span>'
               if w * h >= min_label * 6 else f'<span>{it["share"]:.0f}%</span>')
        parts.append(
            f'<div class="tmap__c" style="left:{x:.3f}%;top:{y:.3f}%;'
            f'width:{w:.3f}%;height:{h:.3f}%;background:{bg};{fg}" '
            f'title="{e(it["label"])}: {it["share"]:.0f}% pidato">{isi}</div>')
    return f'<div class="tmap">{"".join(parts)}</div>'


def _columns(items, satuan="per 1.000 token"):
    """Kolom vertikal: bentuk lain lagi, menonjolkan perbandingan tinggi."""
    if not items:
        return ""
    hi = max(x["nilai"] for x in items) or 1
    cols = "".join(
        f'<div class="col" title="{e(x["label"])}: {x["nilai"]:.1f} {satuan}">'
        f'<span class="col__v">{x["nilai"]:.1f}</span>'
        f'<span class="col__b" style="height:{max(2.0, x["nilai"] / hi * 100):.1f}%"></span>'
        f'<span class="col__l">{e(x["label"])}</span></div>'
        for x in items)
    return f'<div class="cols">{cols}</div>'


def _donut(items, tengah=""):
    """Donat: busur SVG. Sekali lagi bentuk yang berbeda dari batang."""
    if not items:
        return ""
    total = sum(x["share"] for x in items) or 1
    r, cx, cy, tebal = 52.0, 70.0, 70.0, 20.0
    C = 2 * 3.141592653589793 * r
    off = 0.0
    seg = []
    for x in items:
        frac = x["share"] / total
        dash = frac * C
        kuat = 92 - (x["share"] / items[0]["share"]) * 34
        seg.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
            f'stroke="color-mix(in srgb, var(--primary) {kuat:.0f}%, var(--card))" '
            f'stroke-width="{tebal}" stroke-dasharray="{dash:.2f} {C - dash:.2f}" '
            f'stroke-dashoffset="{-off:.2f}" transform="rotate(-90 {cx} {cy})">'
            f'<title>{e(x["label"])}: {x["share"]:.0f}%</title></circle>')
        off += dash
    tengah_html = (f'<text x="{cx}" y="{cy - 2}" text-anchor="middle" '
                   f'class="donut__n">{e(tengah)}</text>'
                   if tengah else "")
    legend = "".join(
        f'<li><span class="dot" style="background:'
        f'color-mix(in srgb, var(--primary) {92 - (x["share"] / items[0]["share"]) * 34:.0f}%, var(--card))">'
        f'</span>{e(x["label"])}<b>{x["share"]:.0f}%</b></li>'
        for x in items)
    return (f'<div class="donut"><svg viewBox="0 0 140 140" role="img" '
            f'aria-label="Porsi tiap kategori">{tengah_html}{"".join(seg)}</svg>'
            f'<ul class="donut__l">{legend}</ul></div>')


def _area(months):
    """Grafik area: volume pidato per bulan, lengkap dengan sumbu dan garis bantu."""
    if not months:
        return ""
    v = [m["events"] for m in months]
    hi = max(v) or 1
    n = len(v)
    titik = [((i / max(1, n - 1)) * 100.0,
              100.0 - (val / hi) * 92.0) for i, val in enumerate(v)]
    garis = " ".join(f"{'M' if i == 0 else 'L'}{x:.2f},{y:.2f}"
                     for i, (x, y) in enumerate(titik))
    isi = f"{garis} L100.00,100.00 L0,100.00 Z"
    grid = "".join(
        f'<line x1="0" y1="{y:.1f}" x2="100" y2="{y:.1f}" class="area__g"/>'
        for y in (8.0, 54.0, 100.0))
    ymax = f'<span>{hi}</span>'
    ymid = f'<span>{round(hi / 2)}</span>'
    awal, akhir = e(months[0]["month"]), e(months[-1]["month"])
    return (f'<div class="area">'
            f'<div class="area__y">{ymax}{ymid}<span>0</span></div>'
            f'<div class="area__plot">'
            f'<svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" '
            f'aria-label="Volume pidato per bulan, puncak {hi}">'
            f'{grid}<path class="area__f" d="{isi}"/>'
            f'<path class="area__l" d="{garis}"/></svg>'
            f'<div class="area__x"><span>{awal}</span>'
            f'<span>puncak {hi} pidato</span><span>{akhir}</span></div>'
            f'</div></div>')


def _timeline(speeches):
    """Garis waktu: SETIAP pidato jadi satu tanda. Menggantikan daftar di beranda."""
    if not speeches:
        return ""
    urut = sorted(speeches, key=lambda s: s["date"])
    n = len(urut)
    W, H = 100.0, 100.0
    hi = max((s["token_count"] or 0) for s in urut) or 1
    tanda = []
    for i, s in enumerate(urut):
        x = (i / max(1, n - 1)) * W
        tinggi = 12 + (s["token_count"] or 0) / hi * (H - 20)
        y = H - tinggi
        tanda.append(
            f'<a href="pidato/{e(s["id"])}.html"><rect x="{x - 0.32:.3f}" y="{y:.2f}" '
            f'width="0.64" height="{tinggi:.2f}"><title>{e(s["date"])} — {e(s["title"][:70])} '
            f'({fmt_int(s["token_count"])} token)</title></rect></a>')
    isi = "".join(tanda)
    awal, akhir = e(urut[0]["date"]), e(urut[-1]["date"])
    return (f'<div class="tl">'
            f'<svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" '
            f'aria-label="Garis waktu {n} pidato">{isi}</svg>'
            f'<div class="tl__x"><span>{awal}</span>'
            f'<span>tiap tanda = satu pidato &middot; tinggi = panjangnya</span>'
            f'<span>{akhir}</span></div></div>')


# ------------------------------------------------------------------ daftar utama

def _bar(label: str, frac: float, value: str, *, soft: bool = False,
         rank: int | None = None) -> str:
    """Satu batang horizontal.

    `frac` 0-1 menentukan panjang. `rank` memberi intensitas warna bertingkat
    supaya peringkat terbaca sekilas, bukan cuma dari panjangnya.
    """
    w = max(0.008, min(1.0, frac)) * 100
    style = f"width:{w:.1f}%"
    cls = "brow__f"
    if soft:
        cls += " brow__f--soft"
    elif rank is not None:
        # peringkat 1 paling pekat, makin ke bawah makin pudar
        mix = max(48, 100 - rank * 7)
        style += f";background:color-mix(in srgb, var(--primary) {mix}%, var(--border))"
    return (f'<div class="brow"><span class="brow__k">{e(label)}</span>'
            f'<span class="brow__t"><span class="{cls}" style="{style}"></span></span>'
            f'<span class="brow__v">{value}</span></div>')


def _word_cloud(words: list[dict], limit: int = 34) -> str:
    """Awan kata: ukuran huruf mengikuti frekuensi, jadi besar = sering."""
    if not words:
        return '<p class="hint">tidak ada</p>'
    top = words[:limit]
    hi = top[0]["count"] or 1
    lo = top[-1]["count"] or 1
    out = []
    for i, w in enumerate(top):
        # skala akar supaya perbedaan ekstrem tidak mendominasi
        frac = ((w["count"] / hi) ** 0.5 - (lo / hi) ** 0.5) / max(1e-6, 1 - (lo / hi) ** 0.5)
        size = 0.9 + max(0.0, min(1.0, frac)) * 2.6
        tier = "cloud__w--1" if i < 3 else ("cloud__w--2" if i < 10 else "cloud__w--3")
        out.append(f'<span class="cloud__w {tier}" style="font-size:{size:.2f}rem">'
                   f'{e(w["word"])}<b>{fmt_int(w["count"])}</b></span>')
    return f'<div class="cloud">{"".join(out)}</div>'


def _cov_cells(coverage: dict) -> str:
    months = coverage.get("months", [])
    peak = max((m["events"] for m in months), default=1) or 1
    out = []
    for m in months:
        if not m["covered"]:
            out.append(f'<div class="heat__c heat__c--0" title="{e(m["month"])}: kosong">'
                       f'<span class="heat__m">{e(m["month"][:4])}</span>'
                       f'<span class="heat__n">&middot;</span></div>')
            continue
        inten = m["events"] / peak
        bg = f"color-mix(in srgb, var(--primary) {8 + inten * 62:.0f}%, var(--card))"
        fg = "" if inten < 0.5 else "color:#fff"
        out.append(f'<div class="heat__c" style="background:{bg};border-color:transparent;{fg}" '
                   f'title="{e(m["month"])}: {m["events"]} pidato, {fmt_int(m["tokens"])} token">'
                   f'<span class="heat__m">{e(m["month"])}</span>'
                   f'<span class="heat__n">{m["events"]}</span></div>')
    return "".join(out)


def _entries(speeches: list[dict]) -> str:
    rows = []
    for s in speeches:
        unggah = s.get("upload_count") or len(s.get("uploads") or []) or 1
        # Entri berbahasa Inggris ditandai supaya jelas transkripnya bukan
        # bahasa Indonesia (dan tidak ikut statistik kata).
        en = ' <span class="chip">EN</span>' if s.get("transcript_language") == "en" else ""
        # NT = tanpa transkrip. Pidatonya terkonfirmasi ada, teksnya tidak.
        en += ' <span class="chip">NT</span>' if s.get("tanpa_transkrip") else ""
        rows.append(f"""      <li>
        <a class="entry" href="pidato/{e(s['id'])}.html">
          <span class="entry__date">{e(s['date'])}</span>
          <span class="entry__title">{e(judul(s))}{en}
            <span class="entry__meta" style="display:block;font-size:var(--step--1)">
              {e(s.get('channel') or '—')} &middot; {e(s.get('duration_hms') or '—')} &middot;
              {fmt_int(s.get('token_count', 0))} token &middot; {unggah} unggahan
            </span>
          </span>
          <span class="entry__meta">{e(TIER_LABEL.get(s.get('source_tier') or '', s.get('source_tier') or ''))}</span>
        </a>
      </li>""")
    return chr(10).join(rows)


def render_daftar(speeches: list[dict], meta: dict, coverage: dict) -> str:
    """Halaman daftar. Dipisah dari beranda: beranda untuk analisis, bukan indeks."""
    n_en = sum(1 for s in speeches if s.get("transcript_language") == "en")
    n_nt = sum(1 for s in speeches if s.get("tanpa_transkrip"))
    rinci = ""
    if n_en and n_nt:
        rinci = f" Termasuk {n_en} pidato berbahasa Inggris dan {n_nt} tanpa transkrip."
    elif n_en:
        rinci = f" Termasuk {n_en} pidato berbahasa Inggris."
    elif n_nt:
        rinci = f" Termasuk {n_nt} pidato tanpa transkrip."
    body = f"""  <h1>Semua pidato</h1>
  <p class="lede">{len(speeches)} pidato, {fmt_int(sum((s.get('upload_count') or len(s.get('uploads') or []) or 1) for s in speeches))} unggahan.
  Satu baris = satu acara, bukan satu video. Terbaru di atas.{e(rinci)}</p>

  <div class="searchbar">
    <input id="q" type="search" placeholder="Cari pidato atau isi transkrip…" aria-label="Cari pidato" autocomplete="off">
  </div>
  <p class="hint" id="count">{len(speeches)} pidato</p>
  <ol class="list" id="list">
{_entries(speeches)}
  </ol>
  <p class="empty" id="empty" hidden>Tidak ada yang cocok.</p>
"""
    return page(
        f"Semua pidato — {len(speeches)}",
        body,
        desc=f"Daftar lengkap {len(speeches)} pidato Presiden Prabowo dengan transkrip, "
             f"tautan video, dan cap waktu.",
        canonical="/daftar.html",
        active="daftar",
    )


def _chart(id_: str, judul: str, angka: str, unit: str, tinggi: str = "16rem",
           kelas: str = "c12", bisa_semua: bool = True) -> str:
    """Satu panel: judul, ANGKA (bukan paragraf), satuan, grafik, tombol.

    Tombol `semua` membuka seluruh data. Data dikirim UTUH ke halaman;
    pemotongan hanya soal tampilan dan bisa dibuka pengguna.
    """
    tombol = (f'<button type="button" class="lebih" data-lebih="{id_}" '
              f'aria-expanded="false">semua</button>' if bisa_semua else "")
    return f"""      <section class="card {kelas}">
        <div class="card__h">
          <h3>{e(judul)}</h3>
          <span class="unit">{unit}</span>
        </div>
        <p class="angka">{angka}</p>
        <div class="chart" id="{id_}" style="height:{tinggi}"></div>
        <div class="kaki">{tombol}<span class="kaki__n" data-jumlah="{id_}"></span></div>
      </section>"""


def render_index(speeches: list[dict], meta: dict, coverage: dict, home: dict,
                 momen: list[dict] | None = None) -> str:
    """Halaman utama: angka korpus dari banyak sudut, plus momen yang
    ramai dibicarakan."""
    L = home.get("length") or {}
    prog = home.get("programs", [])
    tw = home.get("top_words", [])
    top = home.get("topics", [])
    fr = sorted(home.get("framing", []), key=lambda x: -x["per_1000"])
    conc = home.get("concepts", [])
    hist = home.get("length_histogram", [])
    bln = [m for m in coverage.get("months", []) if m.get("covered")]

    n = home.get("event_count") or 1            # pidato bertranskrip Indonesia
    n_semua = len(speeches)                     # seluruh arsip yang terbit
    tot_token = sum(int(s.get("token_count") or 0) for s in speeches)
    tot_unggah = sum((s.get("upload_count") or len(s.get("uploads") or []) or 1)
                     for s in speeches)
    mbg = next((x for x in prog if "mbg" in x["label"].lower()), None)
    kor = next((x for x in conc if "korupsi" in x["label"].lower()), None)
    kita = next((x for x in fr if x["label"] == "kita"), None)
    saya = next((x for x in fr if x["label"] == "saya"), None)
    rasio = home.get("kita_saya_ratio")
    t0 = top[0] if top else None
    t1 = top[1] if len(top) > 1 else None

    hero = f"""  <div class="hero">
    <div class="hero__i"><span class="hero__n hero__n--accent">{fmt_int(n_semua)}</span><span class="hero__l">pidato</span></div>
    <div class="hero__i"><span class="hero__n">{fmt_int(tot_token)}</span><span class="hero__l">token</span></div>
    <div class="hero__i"><span class="hero__n">{fmt_int(tot_unggah)}</span><span class="hero__l">unggahan</span></div>
    <div class="hero__i"><span class="hero__n">{fmt_int(L.get('median'))}</span><span class="hero__l">token median</span></div>
    <div class="hero__i"><span class="hero__n">{fmt_int(L.get('longest'))}</span><span class="hero__l">terpanjang</span></div>
    <div class="hero__i"><span class="hero__n hero__n--kecil">{e(format_span(coverage))}</span><span class="hero__l">rentang</span></div>
  </div>"""

    chart_data = {
        "insight": json.loads((DATA / "insight.json").read_text(encoding="utf-8"))
                   if (DATA / "insight.json").exists() else {},
        # UTUH dan multi-metrik. Tiap butir membawa beberapa ukuran
        # sekaligus supaya pembaca bisa menilai sendiri dari sudut berbeda,
        # bukan disuguhi satu angka yang sudah ditafsirkan.
        "words": [{"name": w["word"], "count": w["count"], "per1000": w["per_1000"],
                   "speeches": w.get("speeches"), "share": w.get("share")} for w in tw],
        "programs": [{"name": x["label"], "full": x.get("full"), "share": round(x["share"]),
                      "events": x.get("events"), "mentions": x.get("mentions"),
                      "per_event": x.get("per_event"), "first": x.get("first"),
                      "last": x.get("last")} for x in prog],
        "topics": [{"name": x["topic"].replace("_", " "), "per1000": round(x["per_1000"], 1),
                    "count": x.get("count"), "speeches": x.get("speeches"),
                    "share": x.get("share")} for x in top],
        "framing": [{"name": x["label"], "per1000": round(x["per_1000"], 1),
                     "count": x.get("count"), "speeches": x.get("speeches")} for x in fr],
        "concepts": [{"name": x["label"], "full": x.get("full"), "share": round(x["share"]),
                      "events": x.get("events"), "mentions": x.get("mentions"),
                      "per_event": x.get("per_event"), "first": x.get("first"),
                      "last": x.get("last")} for x in conc],
        "length": {"labels": [x["label"] for x in hist],
                   "counts": [x["count"] for x in hist]},
        "months": [{"month": m["month"], "events": m["events"], "tokens": m["tokens"]}
                   for m in bln],
        "timeline": [{"date": s["date"], "title": judul(s),
                      "tokens": s["token_count"] or 0,
                      "words": s.get("unique_word_count"),
                      "uploads": s.get("upload_count"),
                      "url": f"pidato/{s['id']}.html"} for s in speeches],
        "years": [{"year": y["year"], "speeches": y["speeches"], "tokens": y["tokens"],
                   "kita": y.get("kita_per_1000"), "saya": y.get("saya_per_1000"),
                   "ratio": y.get("ratio")} for y in home.get("framing_per_year", [])],
        "coverage": {"punya": len(speeches), "era": meta.get("era_videos") or 894,
                     "kosong": len(coverage.get("months_without_events", []))},
    }
    payload = json.dumps(chart_data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    def pct(x):
        return f"{x:.0f}%" if x is not None else "—"

    body = f"""  <h1>{e(SITE_NAME)}</h1>
  <p class="lede">{fmt_int(n_semua)} pidato sejak 20 Oktober 2024 &middot; {fmt_int(tot_token)} token</p>

{hero}

{_strip_momen(momen or [])}
  <div class="dash">
{_chart('chart-program', 'Program yang dibahas', f"{len(prog)} program", 'luas kotak = % pidato', '17rem', 'c5')}
{_chart('chart-kata', 'Kata yang paling sering', 'tanpa kata fungsi', 'hitungan &middot; per 1.000 token &middot; jumlah pidato', '17rem', 'c7')}
{_chart('chart-topik', 'Topik', f"{len(top)} kategori", 'kepadatan per 1.000 token &middot; jumlah pidato', '15rem', 'c7')}
{_chart('chart-sapa', 'Kata ganti', f"{len(fr)} kata", 'per 1.000 token', '15rem', 'c5')}
{_chart('chart-masalah', 'Kategori masalah', f"{len(conc)} kategori", 'porsi pidato &middot; kemunculan', '14rem', 'c5')}
{_chart('chart-panjang', 'Panjang pidato', f"median {fmt_int(L.get('median'))} token", 'ribu token &middot; jumlah pidato', '14rem', 'c7')}
{_chart('chart-volume', 'Volume per bulan', f"{len(bln)} bulan terisi", 'jumlah pidato &middot; token', '15rem', 'c7')}
{_chart('chart-tahun', 'Kata ganti per tahun', f"{len(home.get('framing_per_year', []))} tahun", 'per 1.000 token', '14rem', 'c5')}
{_chart('chart-siklus', 'Perhatian program per kuartal', 'porsi pidato', 'korupsi · MBG · bencana', '16rem', 'c12')}
    <section class="card c12">
      <div class="card__h">
        <h3>Sebaran waktu</h3>
        <span class="unit">{len(coverage.get('months_without_events', []))} bulan tanpa pidato</span>
      </div>
      <div class="heat">{_cov_cells(coverage)}</div>
      <div class="legend">
        <span class="legend__s" style="background:color-mix(in srgb, var(--primary) 12%, var(--card))"></span>
        <span>sedikit</span>
        <span class="legend__s" style="background:color-mix(in srgb, var(--primary) 70%, var(--card))"></span>
        <span>banyak</span>
        <span class="legend__s" style="border-style:dashed;background:transparent"></span>
        <span>kosong</span>
      </div>
    </section>
{_chart('chart-waktu', 'Garis waktu', f'{fmt_int(n_semua)} pidato', 'tinggi = panjang &middot; klik untuk membuka', '17rem', 'c12')}
{_chart('chart-kelengkapan', 'Kelengkapan arsip', f"{fmt_int(len(speeches))} dari {fmt_int(meta.get('era_videos') or 894)} video era kepresidenan", 'per bulan', '13rem', 'c12', False)}
  </div>

  <script id="chart-data" type="application/json">{payload}</script>
"""
    return page(
        f"{SITE_NAME} — {len(speeches)} pidato",
        body,
        desc=f"Cara Prabowo berpidato, diukur dari {n_semua} pidato: program yang paling dibahas, "
             f"kata yang paling sering diucapkan, dan batas kepercayaan datanya.",
        canonical="/",
        jsonld=json.dumps({
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": SITE_NAME,
            "description": SITE_TAGLINE,
            "url": SITE_BASE + "/",
            "hasPart": [{
                "@type": "CreativeWork",
                "name": judul(s),
                "datePublished": s["date"],
                "url": f"{SITE_BASE}/pidato/{s['id']}.html",
            } for s in speeches],
        }, ensure_ascii=False),
        active="beranda",
    )


def format_span(coverage: dict) -> str:
    a, b = coverage.get("date_first"), coverage.get("date_last")
    if not a or not b:
        return "—"
    return f"{a[:4]}–{b[:4]}"


# ------------------------------------------------------------------ detail pidato

def render_speech(s: dict, prev: dict | None, nxt: dict | None,
                  momen: list[dict] | None = None) -> str:
    vid = s["video_id"]

    paras = []
    for p in s["transcript"]:
        tcell = (f'<a href="{e(yt_at(vid, p["t"]))}" title="Buka di YouTube pada detik ini" '
                 f'rel="noopener">{ts_short(p["t"])}</a>') if vid else ""
        paras.append(f"""    <div class="para" id="t{p['t']}">
      <div class="para__t">{tcell}</div>
      <div class="para__text">{e(p['text'])}</div>
    </div>""")

    up_rows = []
    for u in s["uploads"]:
        mark = '<span class="chip chip--ok">utama</span>' if u.get("canonical") else ""
        fetch = FETCH_LABEL.get(u.get("fetch_method") or "", u.get("fetch_method") or "—")
        up_rows.append(f"""        <tr>
          <td>{mark}</td>
          <td><a href="{e(u['url'])}" rel="noopener nofollow">{e(u['video_id'])}</a>
              <div class="hint">{e(_bersih(u.get('title') or '')[:80])}</div></td>
          <td>{e(u.get('channel') or '—')}</td>
          <td class="mono">{e(u.get('upload_date') or '—')}</td>
          <td class="num">{fmt_int(u.get('token_count'))}</td>
          <td>{e(fetch)}</td>
          <td>{e(u.get('status') or '—')}</td>
        </tr>""")

    topics = s.get("topics") or {}
    topic_chips = " ".join(
        f'<span class="chip">{e(k.replace("_", " "))} {v}</span>'
        for k, v in sorted(topics.items(), key=lambda kv: -kv[1]) if v
    )

    nav = []
    if prev:
        nav.append(f'<a href="{e(prev["id"])}.html">&larr; {e(fmt_date(prev["date"]))}</a>')
    if nxt:
        nav.append(f'<a href="{e(nxt["id"])}.html">{e(fmt_date(nxt["date"]))} &rarr;</a>')
    nav_html = f'<p class="crumb" style="margin-top:1.5rem">{" &middot; ".join(nav)}</p>' if nav else ""

    prov = s.get("provenance") or {}
    # Label bahasa untuk pembaca. Nilai mentah metadata takarir (mis.
    # "Indonesian (auto-generated)") tidak pernah ditampilkan apa adanya.
    bhs = (prov.get("language") or "").strip()
    if s.get("transcript_language") == "en" or bhs.lower().startswith("english"):
        bahasa = "Inggris"
    elif s.get("tanpa_transkrip"):
        bahasa = "—"
    elif not bhs or "indonesian" in bhs.lower() or bhs.lower() == "id":
        bahasa = "Indonesia"
    else:
        bahasa = bhs
    ambil = FETCH_LABEL.get(s.get("fetch_method") or "", s.get("fetch_method") or "—")
    tier = TIER_LABEL.get(s.get("source_tier") or "", s.get("source_tier") or "—")

    if s.get("youtube_url"):
        sumber_dd = (f'<dt>Video</dt><dd><a class="yt-link" href="{e(s["youtube_url"])}" '
                     f'rel="noopener nofollow">{YT_ICON} YouTube</a></dd>')
    else:
        lk = (s.get("provenance") or {}).get("link") or ""
        isi = (f'<a href="{e(lk)}" rel="noopener nofollow">transkrip resmi Sekretariat Kabinet</a>'
               if lk else "—")
        sumber_dd = f'<dt>Sumber teks</dt><dd>{isi}</dd>'

    transkrip_hint = ("Cap waktu di kiri bertaut ke detik yang tepat di YouTube." if vid
                      else "Transkrip resmi, tanpa cap waktu.")

    body = f"""  <p class="crumb"><a href="../daftar.html">Semua pidato</a> / {e(fmt_date(s['date']))}</p>
  <h1>{e(judul(s))}</h1>

  <div class="chips" style="margin:.5rem 0 1rem">
    <span class="chip chip--accent">{e(fmt_date(s['date']))}</span>
    <span class="chip">{e(s['channel'])}</span>
    <span class="chip">{e(s['duration_hms'] or '—')}</span>
    <span class="chip">{e(tier)}</span>
    <span class="chip">{e(ambil)}</span>
    <span class="chip">{len(s['uploads'])} unggahan</span>
  </div>

  <section class="panel">
    <h2 style="font-size:var(--step-1)">Sumber</h2>
    <dl class="dl">
      {sumber_dd}
      <dt>Durasi</dt><dd class="mono">{e(s['duration_hms'] or '—')} ({fmt_int(s['duration_s'])} detik)</dd>
      <dt>Jumlah kata</dt><dd class="mono">{fmt_int(s['token_count'])}</dd>
      <dt>Kata unik</dt><dd class="mono">{fmt_int(s['unique_word_count'])}</dd>
      <dt>Bahasa</dt><dd>{e(bahasa)}</dd>
      <dt>Cara ambil teks</dt><dd>{e(ambil)}</dd>
    </dl>
  </section>

  <section style="margin-top:1.25rem">
    <h2 style="font-size:var(--step-1)">Semua unggahan pidato ini</h2>
    <div style="overflow-x:auto">
    <table class="tbl">
      <thead><tr><th></th><th>Video</th><th>Kanal</th><th>Diunggah</th><th class="num">Kata</th><th>Diambil via</th><th>Status</th></tr></thead>
      <tbody>
{chr(10).join(up_rows)}
      </tbody>
    </table>
    </div>
  </section>

{_sorotan(momen or [])}

  <section style="margin-top:1.25rem">
    <h2 style="font-size:var(--step-1)">Topik</h2>
    <div class="chips">{topic_chips or '<span class="hint">tidak ada</span>'}</div>
  </section>

  <section style="margin-top:1.75rem">
    <h2 style="font-size:var(--step-1)">Transkrip</h2>
    <p class="hint" style="margin:0 0 .5rem">{transkrip_hint}</p>
    <div class="transcript">
{chr(10).join(paras)}
    </div>
  </section>
{nav_html}
"""
    return page(
        f"{judul(s)} — {fmt_date(s['date'])}",
        body,
        desc=f"Transkrip lengkap pidato Prabowo, {fmt_date(s['date'])} di {s['channel']}. "
             f"{fmt_int(s['token_count'])} kata, {len(s['uploads'])} unggahan tercatat.",
        canonical=f"/pidato/{s['id']}.html",
        jsonld=json.dumps({
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": judul(s),
            "datePublished": s["date"],
            "inLanguage": "id",
            "url": f"{SITE_BASE}/pidato/{s['id']}.html",
            "isBasedOn": s["youtube_url"],
            "publisher": {"@type": "Organization", "name": SITE_NAME},
            "about": [k.replace("_", " ") for k, v in (s.get("topics") or {}).items() if v],
        }, ensure_ascii=False),
        rel_root="../",
    )


# ---------------------------------------------------------------------- cakupan

def render_coverage(coverage: dict, meta: dict, speeches: list[dict]) -> str:
    cells = []
    for m in coverage["months"]:
        cls = "cov__cell" + ("" if m["covered"] else " cov__cell--empty")
        cells.append(
            f'<div class="{cls}" title="{e(m["month"])}: {m["events"]} pidato, '
            f'{fmt_int(m["tokens"])} token"><span class="cov__m">{e(m["month"][2:])}</span>'
            f'<span class="cov__n">{m["events"] if m["covered"] else "·"}</span></div>'
        )

    years = []
    for y in coverage["per_year"]:
        years.append(f"""        <tr>
          <td class="mono">{e(y['year'])}</td>
          <td class="num">{y['events']}</td>
          <td class="num">{fmt_int(y['tokens'])}</td>
          <td class="num">{y['event_share']}%</td>
        </tr>""")

    gaps = coverage.get("months_without_events") or []
    gap_html = ", ".join(f"<code>{e(g)}</code>" for g in gaps) if gaps else "tidak ada"

    tiers = " ".join(f'<span class="chip">{e(k)} {v}</span>'
                     for k, v in sorted((coverage.get("source_tiers") or {}).items(), key=lambda kv: -kv[1]))
    komposisi = " ".join(
        f'<span class="chip">{v} {k}</span>' for k, v in (
            ("bertranskrip Indonesia", coverage.get("dengan_transkrip_id")),
            ("berbahasa Inggris", coverage.get("berbahasa_inggris")),
            ("tanpa transkrip", coverage.get("tanpa_transkrip")),
        ) if v
    ) or '<span class="hint">—</span>' 
    methods = " ".join(f'<span class="chip">{e(k)} {v}</span>'
                       for k, v in sorted((coverage.get("fetch_methods") or {}).items(), key=lambda kv: -kv[1]))

    body = f"""  <h1>Seberapa lengkap arsip ini</h1>
  <p class="lede">Halaman ini menunjukkan apa yang <strong>tidak</strong> ada, bukan cuma apa yang ada.</p>

  <div class="stat-row">
    <div class="stat"><span class="stat__n">{fmt_int(coverage.get('span_days'))}</span><span class="stat__l">hari rentang</span></div>
    <div class="stat"><span class="stat__n">{fmt_int(meta.get('event_count'))}</span><span class="stat__l">pidato</span></div>
    <div class="stat"><span class="stat__n">{len(gaps)}</span><span class="stat__l">bulan kosong</span></div>
    <div class="stat"><span class="stat__n">{e(coverage.get('date_first') or '—')}</span><span class="stat__l">pidato pertama</span></div>
  </div>

  <section style="margin-top:1.5rem">
    <h2 style="font-size:var(--step-1)">Pidato per bulan</h2>
    <p class="hint" style="margin:0 0 .5rem">Kotak bergaris putus-putus = bulan tanpa pidato.</p>
    <div class="cov">
{chr(10).join("      " + c for c in cells)}
    </div>
  </section>

  <section style="margin-top:1.5rem">
    <h2 style="font-size:var(--step-1)">Per tahun</h2>
    <table class="tbl">
      <thead><tr><th>Tahun</th><th class="num">Pidato</th><th class="num">Token</th><th class="num">Porsi pidato</th></tr></thead>
      <tbody>
{chr(10).join(years)}
      </tbody>
    </table>
  </section>

  <section style="margin-top:1.5rem">
    <h2 style="font-size:var(--step-1)">Bulan tanpa pidato</h2>
    <p>{gap_html}</p>
  </section>

  <section style="margin-top:1.5rem">
    <h2 style="font-size:var(--step-1)">Komposisi sumber</h2>
    <p class="hint" style="margin:0 0 .4rem">Tingkat sumber</p>
    <div class="chips">{tiers}</div>
    <p class="hint" style="margin:.9rem 0 .4rem">Cara pengambilan transkrip</p>
    <div class="chips">{methods}</div>
    <p class="hint" style="margin:.9rem 0 .4rem">Komposisi arsip</p>
    <div class="chips">{komposisi}</div>
  </section>

  <section class="note" style="margin-top:1.75rem">
    <h3>Batas yang harus dibaca sebelum memakai data ini</h3>
    <ul>
{chr(10).join(f"      <li>{e(x)}</li>" for x in coverage.get("known_limits", []))}
      <li><strong>Distribusi waktu itu artefak, bukan temuan.</strong> Penemuan lewat pencarian
      YouTube yang condong ke hasil terbaru, jadi 2026 lebih padat bukan karena Prabowo
      lebih sering berpidato tahun itu.</li>
    </ul>
  </section>
"""
    return page(
        "Cakupan arsip — apa yang ada dan apa yang bolong",
        body,
        desc="Peta cakupan arsip pidato: jumlah per bulan, bulan yang kosong, komposisi sumber, "
             "dan batas-batas yang perlu diketahui sebelum memakai datanya.",
        canonical="/cakupan.html",
        active="cakupan",
    )


# ---------------------------------------------------------------------- tentang

def render_about(meta: dict, coverage: dict) -> str:
    body = f"""  <h1>Metode</h1>
  <p class="lede">Setiap angka di situs ini bisa ditelusuri balik sampai ke video dan detiknya.</p>

  <section class="panel">
    <h2 style="font-size:var(--step-1)">Satu pidato, satu halaman</h2>
    <p style="margin:.3rem 0">Pidato yang sama sering diunggah puluhan kanal. Aturannya:</p>
    <ul style="margin:.3rem 0;padding-left:1.2rem">
      <li>Satu peristiwa pidato dihitung <strong>sekali</strong>, walau diunggah banyak kanal.</li>
      <li>Satu unggahan dipilih sebagai <strong>rekaman utama</strong> — yang dipakai untuk transkrip dan kutipan.</li>
      <li>Pemilihannya bukan sekadar yang terpanjang. Livestream sering terpadding
      pembawa acara, jadi unggahan yang pembukanya jauh dari pola pembuka pidato justru dibuang.</li>
      <li><strong>Semua unggahan lain tetap dicatat</strong> dan ditampilkan di halaman pidato,
      termasuk yang dibuang. Yang dibuang tidak disembunyikan.</li>
    </ul>
  </section>

  <section class="panel">
    <h2 style="font-size:var(--step-1)">Asal transkrip</h2>
    <p>Tiga sumber teks dipakai, dan jenisnya selalu ditandai di halaman pidato:</p>
    <div class="chips">
      <span class="chip">takarir YouTube bahasa Indonesia</span>
      <span class="chip">takarir asli berbahasa Inggris</span>
      <span class="chip">transkrip resmi Sekretariat Kabinet</span>
    </div>
    <p class="hint" style="margin:.6rem 0 0">Takarir YouTube diambil dua kali dengan
    cara berbeda pada video yang sama untuk memastikan teksnya sama, lalu dipakai
    bergantian. Transkrip resmi tidak punya cap waktu.</p>
  </section>

  <section class="panel">
    <h2 style="font-size:var(--step-1)">Kutipan selalu bertaut ke detiknya</h2>
    <p>Setiap paragraf transkrip punya cap waktu yang menuju YouTube pada detik itu.
    Jadi pembaca bisa memeriksa sendiri apakah kutipannya benar, tanpa mempercayai situs ini.</p>
  </section>

  <section class="panel">
    <h2 style="font-size:var(--step-1)">Data mentah</h2>
    <p>Versi JSON dari data yang sama, untuk yang mau mengolahnya sendiri:</p>
    <ul style="margin:.3rem 0;padding-left:1.2rem">
      <li><a href="data/index.json">data/index.json</a> — daftar semua pidato</li>
      <li><a href="data/coverage.json">data/coverage.json</a> — peta cakupan</li>
      <li><a href="data/meta.json">data/meta.json</a> — asal-usul data</li>
      <li><code>data/speeches/&lt;slug&gt;.json</code> — satu berkas per pidato, termasuk transkrip penuh</li>
    </ul>
  </section>

  <section class="note" style="margin-top:1.25rem">
    <h3>Batas</h3>
    <ul>
{chr(10).join(f"      <li>{e(x)}</li>" for x in coverage.get("known_limits", []))}
      <li>Semua teks di sini adalah materi pihak ketiga dari YouTube. Kutip video aslinya
      sebagai sumber, bukan situs ini.</li>
    </ul>
  </section>

  <section class="panel" style="margin-top:1.25rem">
    <h2 style="font-size:var(--step-1)">Asal-usul data</h2>
    <dl class="dl">
      <dt>Dibangun</dt><dd class="mono">{e(meta.get('built_at') or '—')}</dd>
      <dt>Perangkat</dt><dd><a href="https://github.com/himanusia/youtube-speech-corpus" rel="noopener">youtube-speech-corpus</a></dd>
      <dt>Pidato</dt><dd class="mono">{fmt_int(meta.get('event_count'))}</dd>
      <dt>Unggahan</dt><dd class="mono">{fmt_int(meta.get('upload_count'))}</dd>
      <dt>Token</dt><dd class="mono">{fmt_int(meta.get('token_count'))}</dd>
    </dl>
  </section>
"""
    return page(
        "Tentang — metode dan janji penelusuran",
        body,
        desc="Bagaimana arsip ini dibangun: aturan deduplikasi per peristiwa pidato, asal transkrip, "
             "dan cara setiap kutipan ditautkan ke detik di video aslinya.",
        canonical="/tentang.html",
        active="tentang",
    )


# ------------------------------------------------------------------------ 404

def render_404() -> str:
    return page(
        "Tidak ditemukan",
        """  <p class="eyebrow">404</p>
  <h1>Halaman tidak ada</h1>
  <p class="lede">Alamat ini tidak menunjuk ke pidato mana pun.
  Coba mulai dari <a href="index.html">daftar pidato</a>.</p>
""",
        canonical="/404.html",
        rel_root="/",
    )


APP_JS = r"""/* Penyaring dan tema. Keduanya opsional — tanpa JS halaman tetap lengkap. */
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
"""


# ------------------------------------------------------------------------ main

def main() -> int:
    semua = [json.loads(p.read_text(encoding="utf-8"))
             for p in sorted((DATA / "speeches").glob("*.json"))]
    # Arsip ini soal PIDATO PRABOWO. Entri hasil impor panel yang ternyata
    # keterangan pers pejabat lain, kunjungan, atau potongan sangat pendek
    # TIDAK diterbitkan — kalau ikut, judul situsnya jadi tidak jujur.
    def terbit(d):
        # Pra-era (sebelum 20 Okt 2024) bukan pidato kepresidenan: tidak
        # diterbitkan. Dulu dua entri seperti ini ikut tampil di daftar dan
        # membuat klaim "arsip sejak 20 Oktober 2024" tidak konsisten.
        if d.get("pra_era"):
            return False
        k = d.get("speaker_kind")
        if k is None:
            return True                      # 67 entri awal, sudah terkurasi
        return k in ("pidato_prabowo", "prabowo_bicara")
    # Catatan: entri berbahasa Inggris IKUT diterbitkan (arsipnya harus utuh)
    # tapi ditandai `transcript_language` supaya pembaca tahu transkripnya
    # bukan bahasa Indonesia dan tidak ikut statistik kata.
    speeches = [d for d in semua if terbit(d)]
    speeches.sort(key=lambda d: (d.get("date") or "", d.get("id") or ""))
    disaring = len(semua) - len(speeches)
    index = json.loads((DATA / "index.json").read_text(encoding="utf-8"))
    coverage = json.loads((DATA / "coverage.json").read_text(encoding="utf-8"))
    meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))
    home_path = DATA / "home.json"
    home = json.loads(home_path.read_text(encoding="utf-8")) if home_path.exists() else {}
    momen = _momen_load()

    if not speeches:
        print("Tidak ada pidato. Jalankan build_log.py dulu.")
        return 1

    # Versi aset = potongan hash isi berkasnya. Karena nama berkasnya tidak
    # pernah berubah, tanpa ini browser bisa terus menyajikan CSS lama dan
    # perubahan tidak pernah terlihat walau deploy-nya sudah benar.
    import hashlib
    def asset_version(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:10]

    ASSET_V["css"] = asset_version(WEB / "theme.css")
    ASSET_V["js"] = hashlib.sha256(APP_JS.encode("utf-8")).hexdigest()[:10]
    ASSET_V["vendor"] = asset_version(WEB / "vendor" / "echarts.min.js")
    ASSET_V["charts"] = asset_version(WEB / "charts.js")
    ASSET_V["figure"] = asset_version(WEB / "prabowo.svg")
    ASSET_V["favicon"] = asset_version(WEB / "favicon.svg")
    print(f"versi aset: css={ASSET_V['css']} js={ASSET_V['js']}")

    # Bersihkan keluaran lama supaya tidak ada sisa halaman yatim.
    if DOCS.exists():
        shutil.rmtree(DOCS)
    (DOCS / "pidato").mkdir(parents=True)
    (DOCS / "data" / "speeches").mkdir(parents=True)

    # Data grafik ditanam ke HTML, bukan diambil lewat fetch, supaya perayap
    # dan pembaca tanpa JavaScript tetap mendapat angka yang sama.
    # Momen riset hanya ditautkan ke entri yang benar-benar ada di arsip.
    ids = {s["id"] for s in speeches}
    for m in momen:
        if m.get("pidato_id") and m["pidato_id"] not in ids:
            m["pidato_id"] = None
    (DOCS / "index.html").write_text(
        render_index(speeches, meta, coverage, home, momen), encoding="utf-8")
    # PENTING: daftar memakai ARSIP lengkap, bukan index.json. index.json
    # berasal dari korpus engine dan hanya memuat 67 acara; memakainya membuat
    # halaman "semua pidato" menampilkan 67 dari 329 tanpa penjelasan.
    urut = list(reversed(speeches))          # terbaru di atas
    (DOCS / "daftar.html").write_text(render_daftar(urut, meta, coverage), encoding="utf-8")
    (DOCS / "cakupan.html").write_text(render_coverage(coverage, meta, speeches), encoding="utf-8")
    (DOCS / "tentang.html").write_text(render_about(meta, coverage), encoding="utf-8")
    (DOCS / "404.html").write_text(render_404(), encoding="utf-8")

    momen_by_id: dict[str, list[dict]] = {}
    for m in momen:
        if m.get("pidato_id"):
            momen_by_id.setdefault(m["pidato_id"], []).append(m)
    for i, s in enumerate(speeches):
        prev = speeches[i - 1] if i > 0 else None
        nxt = speeches[i + 1] if i + 1 < len(speeches) else None
        (DOCS / "pidato" / f"{s['id']}.html").write_text(
            render_speech(s, prev, nxt, momen_by_id.get(s["id"]) or []), encoding="utf-8")

    # aset
    # Versi di NAMA BERKAS, bukan di query string.
    # Cloudflare Pages men-cache berdasarkan path dan MENGABAIKAN query,
    # jadi theme.css?v=baru tetap menyajikan theme.css lama — inilah sebab
    # perubahan tidak pernah terlihat di browser. Dengan nama berversi,
    # path-nya benar-benar berubah sehingga cache tidak bisa menyajikan
    # berkas lama.
    # CSS ditulis, bukan disalin: rujukan gambar latar diganti ke nama
    # berversi, supaya gambarnya juga tidak bisa tersangkut di cache.
    css = (WEB / "theme.css").read_text(encoding="utf-8")
    css = css.replace('url("prabowo.svg")',
                      f'url("prabowo.{ASSET_V["figure"]}.svg")')
    (DOCS / f"theme.{ASSET_V['css']}.css").write_text(css, encoding="utf-8")
    (DOCS / f"app.{ASSET_V['js']}.js").write_text(APP_JS, encoding="utf-8")
    shutil.copy2(WEB / "charts.js", DOCS / f"charts.{ASSET_V['charts']}.js")
    shutil.copy2(WEB / "prabowo.svg", DOCS / f"prabowo.{ASSET_V['figure']}.svg")
    shutil.copy2(WEB / "favicon.svg", DOCS / f"favicon.{ASSET_V['favicon']}.svg")
    (DOCS / "vendor").mkdir(exist_ok=True)
    shutil.copy2(WEB / "vendor" / "echarts.min.js",
                 DOCS / "vendor" / f"echarts.{ASSET_V['vendor']}.min.js")

    # data mesin
    for name in ("index.json", "coverage.json", "meta.json", "momen.json"):
        shutil.copy2(DATA / name, DOCS / "data" / name)
    for p in (DATA / "speeches").glob("*.json"):
        shutil.copy2(p, DOCS / "data" / "speeches" / p.name)

    # indeks pencarian: satu string teks penuh per pidato
    search = {
        s["id"]: (judul(s) + " " + s["channel"] + " " + s["date"] + " "
                  + " ".join(p["text"] for p in s["transcript"]))[:400000]
        for s in speeches
    }
    (DOCS / "data" / "search.json").write_text(
        json.dumps(search, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    urls = [f"{SITE_BASE}/", f"{SITE_BASE}/daftar.html",
            f"{SITE_BASE}/cakupan.html", f"{SITE_BASE}/tentang.html"]
    urls += [f"{SITE_BASE}/pidato/{s['id']}.html" for s in speeches]
    today = datetime.now(WIB).date().isoformat()
    (DOCS / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(f'  <url><loc>{u}</loc><lastmod>{today}</lastmod></url>' for u in urls)
        + "\n</urlset>\n", encoding="utf-8")

    (DOCS / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE_BASE}/sitemap.xml\n", encoding="utf-8")

    (DOCS / ".nojekyll").write_text("", encoding="utf-8")

    # Kebijakan cache eksplisit. Tanpa ini Cloudflare tidak mengirim
    # Cache-Control sama sekali, dan browser menebak sendiri kapan CSS basi —
    # itulah sebabnya perubahan tidak terlihat walau deploy-nya sudah benar.
    # Aset boleh di-cache lama karena URL-nya sudah berversi hash;
    # HTML harus selalu diperiksa ulang supaya perubahan langsung terlihat.
    (DOCS / "_headers").write_text(
        # Aset sudah berversi DI NAMA BERKAS, jadi aman di-cache selamanya:
        # kalau isinya berubah, namanya ikut berubah dan browser mengambil
        # URL yang benar-benar baru. HTML sebaliknya: harus selalu
        # divalidasi ulang, kalau tidak perubahan tidak akan pernah terlihat.
        "/*\n"
        "  X-Content-Type-Options: nosniff\n"
        "  Cache-Control: public, max-age=0, must-revalidate\n"
        "\n"
        "/*.css\n"
        "  Cache-Control: public, max-age=31536000, immutable\n"
        "\n"
        "/*.js\n"
        "  Cache-Control: public, max-age=31536000, immutable\n"
        "\n"
        "/*.png\n"
        "  Cache-Control: public, max-age=31536000, immutable\n"
        "\n"
        "/*.svg\n"
        "  Cache-Control: public, max-age=31536000, immutable\n"
        "\n"
        "/data/*\n"
        "  Cache-Control: public, max-age=3600\n",
        encoding="utf-8")

    total_bytes = sum(f.stat().st_size for f in DOCS.rglob("*") if f.is_file())
    print(f"OK  {len(speeches)} halaman pidato + 3 halaman utama")
    print(f"    {len(urls)} URL di sitemap")
    print(f"    {total_bytes/1024/1024:.2f} MB total di docs/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
