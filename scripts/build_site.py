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


# --------------------------------------------------------------------- kerangka

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
<link rel="stylesheet" href="{rel_root}theme.css">
<link rel="alternate" type="application/json" href="{rel_root}data/index.json" title="Indeks JSON">
<script type="application/ld+json">{jsonld}</script>
</head>
<body>
<header class="top">
  <div class="wrap top__row">
    <div class="brand">
      <span class="brand__mark">&#9632;</span>
      <span class="brand__name"><a href="{rel_root}index.html" style="color:inherit">{e(SITE_NAME)}</a></span>
      <span class="brand__sub">arsip yang bisa ditelusuri</span>
    </div>
    <nav class="nav" aria-label="Navigasi utama">
      <button type="button" data-go="{rel_root}index.html" {'aria-current="page"' if active == 'daftar' else ''}>Daftar</button>
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
  <p>{e(SITE_NAME)} &middot; sumber: rekaman publik YouTube &middot;
  setiap kutipan bertaut ke video dan detik asalnya &middot;
  <a href="{rel_root}data/index.json">data JSON</a> &middot;
  <a href="{rel_root}sitemap.xml">sitemap</a></p>
  <p class="hint">Transkrip berasal dari caption YouTube (auto-generated). Bukan transkrip dari audio,
  dan bukan sumber resmi. Selalu periksa video aslinya sebelum mengutip.</p>
</footer>
<script src="{rel_root}app.js" defer></script>
</body>
</html>
"""


# ------------------------------------------------------------------ daftar utama

def render_index(speeches: list[dict], meta: dict, coverage: dict) -> str:
    rows = []
    for s in speeches:
        t = s["topics"] or {}
        top_topic = max(
            ((k, v) for k, v in t.items() if k != "mbg"),
            key=lambda kv: kv[1], default=("", 0),
        )
        rows.append(f"""      <li>
        <a class="entry" href="pidato/{e(s['id'])}.html">
          <span class="entry__date">{e(s['date'])}</span>
          <span class="entry__title">{e(s['title'])}
            <span class="entry__meta" style="display:block;font-size:var(--step--1)">
              {e(s['channel'])} &middot; {e(s['duration_hms'] or '—')} &middot;
              {fmt_int(s['token_count'])} token &middot; {s['upload_count']} unggahan
            </span>
          </span>
          <span class="entry__meta">{e(s['source_tier'] or '')}</span>
        </a>
      </li>""")

    stats = f"""    <div class="stat-row">
      <div class="stat"><span class="stat__n">{fmt_int(meta.get('event_count'))}</span><span class="stat__l">pidato</span></div>
      <div class="stat"><span class="stat__n">{fmt_int(meta.get('upload_count'))}</span><span class="stat__l">unggahan tercatat</span></div>
      <div class="stat"><span class="stat__n">{fmt_int(meta.get('token_count'))}</span><span class="stat__l">token</span></div>
      <div class="stat"><span class="stat__n">{e(format_span(coverage))}</span><span class="stat__l">rentang</span></div>
    </div>"""

    body = f"""  <p class="eyebrow">Daftar</p>
  <h1>{e(SITE_NAME)}</h1>
  <p class="lede">{e(SITE_TAGLINE)} Tiap halaman memuat transkrip penuh dengan cap waktu,
  daftar semua unggahan yang memuat pidato yang sama, dan alasan pemilihan sumbernya.</p>

{stats}

  <section style="margin-top:1.5rem">
    <div class="searchbar">
      <input id="q" type="search" placeholder="Saring pidato — judul, kanal, tanggal, kata di transkrip…" aria-label="Saring pidato" autocomplete="off">
      <span class="count" id="count">{len(speeches)} pidato</span>
    </div>
    <p class="hint" style="margin:.4rem 0 0">Penyaring ini berjalan di browser.
    Tanpa JavaScript, seluruh daftar di bawah tetap lengkap dan bisa dibaca.</p>
  </section>

  <ol class="list" id="list" style="margin-top:1rem;list-style:none;padding:0">
{chr(10).join(rows)}
  </ol>
  <p class="empty" id="empty" hidden>Tidak ada yang cocok.</p>

  <section class="note" style="margin-top:2rem">
    <h3>Yang perlu diketahui sebelum membaca angka di halaman ini</h3>
    <ul>
{chr(10).join(f"      <li>{e(x)}</li>" for x in coverage.get("known_limits", []))}
    </ul>
  </section>
"""
    return page(
        f"{SITE_NAME} — daftar {len(speeches)} pidato",
        body,
        desc=f"Daftar {len(speeches)} pidato, sambutan, dan pernyataan resmi Presiden Prabowo, "
             f"masing-masing dengan transkrip ber-cap-waktu dan tautan ke video asalnya.",
        canonical="/",
        jsonld=json.dumps({
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": SITE_NAME,
            "description": SITE_TAGLINE,
            "url": SITE_BASE + "/",
            "hasPart": [{
                "@type": "CreativeWork",
                "name": s["title"],
                "datePublished": s["date"],
                "url": f"{SITE_BASE}/pidato/{s['id']}.html",
            } for s in speeches],
        }, ensure_ascii=False),
        active="daftar",
    )


def format_span(coverage: dict) -> str:
    a, b = coverage.get("date_first"), coverage.get("date_last")
    if not a or not b:
        return "—"
    return f"{a[:4]}–{b[:4]}"


# ------------------------------------------------------------------ detail pidato

def render_speech(s: dict, prev: dict | None, nxt: dict | None) -> str:
    vid = s["video_id"]

    paras = []
    for p in s["transcript"]:
        link = yt_at(vid, p["t"])
        paras.append(f"""    <div class="para" id="t{p['t']}">
      <div class="para__t"><a href="{e(link)}" title="Buka di YouTube pada detik ini" rel="noopener">{ts_short(p['t'])}</a></div>
      <div class="para__text">{e(p['text'])}</div>
    </div>""")

    up_rows = []
    for u in s["uploads"]:
        mark = '<span class="chip chip--ok">kanonik</span>' if u["canonical"] else ""
        fetch = {"caption_api": "caption API", "transcript_panel": "panel transkrip"}.get(
            u.get("fetch_method") or "", u.get("fetch_method") or "—")
        up_rows.append(f"""        <tr>
          <td>{mark}</td>
          <td><a href="{e(u['url'])}" rel="noopener nofollow">{e(u['video_id'])}</a>
              <div class="hint">{e((u.get('title') or '')[:80])}</div></td>
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

    sig = s.get("policy_signals") or {}
    sig_block = ""
    if sig:
        ev = sig.get("evidence") or []
        ev_html = ""
        if ev:
            items = []
            for item in ev[:6]:
                if isinstance(item, dict):
                    txt = item.get("text") or item.get("snippet") or ""
                    t = item.get("start", item.get("t"))
                else:
                    txt, t = str(item), None
                if t is not None:
                    items.append(f'<li><a href="{e(yt_at(vid, t))}" rel="noopener">{ts_short(t)}</a> — {e(txt)}</li>')
                else:
                    items.append(f"<li>{e(txt)}</li>")
            ev_html = '<ul style="margin:.4rem 0 0;padding-left:1.1rem">' + "".join(items) + "</ul>"
        sig_block = f"""  <section class="panel" style="margin-top:1rem">
    <h2 style="font-size:var(--step-1)">Sinyal kebijakan: {e(sig.get('label','—'))}</h2>
    <p class="hint" style="margin:0">Sinyal total {fmt_int(sig.get('policy_signal_count'))} &middot;
    token eksak {fmt_int(sig.get('exact_token_count'))} &middot;
    frasa penuh {fmt_int(sig.get('full_phrase_count'))} &middot;
    ambigu {fmt_int(sig.get('ambiguous_count'))}</p>
    {ev_html}
  </section>"""

    nav = []
    if prev:
        nav.append(f'<a href="{e(prev["id"])}.html">&larr; {e(fmt_date(prev["date"]))}</a>')
    if nxt:
        nav.append(f'<a href="{e(nxt["id"])}.html">{e(fmt_date(nxt["date"]))} &rarr;</a>')
    nav_html = f'<p class="crumb" style="margin-top:1.5rem">{" &middot; ".join(nav)}</p>' if nav else ""

    body = f"""  <p class="crumb"><a href="../index.html">Daftar</a> / {e(s['date'])}</p>
  <h1>{e(s['title'])}</h1>

  <div class="chips" style="margin:.5rem 0 1rem">
    <span class="chip chip--accent">{e(fmt_date(s['date']))}</span>
    <span class="chip">{e(s['channel'])}</span>
    <span class="chip">{e(s['duration_hms'] or '—')}</span>
    <span class="chip">{e(s['source_tier'] or '—')}</span>
    <span class="chip">{e(s['fetch_method'] or '—')}</span>
    <span class="chip">{len(s['uploads'])} unggahan</span>
  </div>

  <section class="panel">
    <h2 style="font-size:var(--step-1)">Sumber</h2>
    <dl class="dl">
      <dt>Video kanonik</dt><dd><a href="{e(s['youtube_url'])}" rel="noopener nofollow">{e(vid)}</a></dd>
      <dt>Transkrip dari</dt><dd class="mono">engine/data/prabowo/raw/{e(vid)}.json</dd>
      <dt>Jumlah token</dt><dd class="mono">{fmt_int(s['token_count'])}</dd>
      <dt>Kata unik</dt><dd class="mono">{fmt_int(s['unique_word_count'])}</dd>
      <dt>Durasi</dt><dd class="mono">{e(s['duration_hms'] or '—')} ({fmt_int(s['duration_s'])} detik)</dd>
      <dt>Bahasa</dt><dd class="mono">{e(s['provenance'].get('language') or '—')}</dd>
      <dt>Metode</dt><dd class="mono">{e(s['provenance'].get('fetched_via') or '—')}</dd>
      <dt>Commit engine</dt><dd class="mono">{e((s['provenance'].get('engine_commit') or '—')[:12])}</dd>
    </dl>
  </section>

  <section style="margin-top:1.25rem">
    <h2 style="font-size:var(--step-1)">Semua unggahan pidato ini</h2>
    <p class="hint" style="margin:0 0 .5rem">Pidato yang sama sering diunggah banyak kanal.
    Hanya satu yang dipakai untuk hitungan; sisanya tetap dicatat supaya bisa diperiksa —
    termasuk unggahan yang panjangnya tidak wajar karena terpadding pembawa acara.</p>
    <div style="overflow-x:auto">
    <table class="tbl">
      <thead><tr><th></th><th>Video</th><th>Kanal</th><th>Diunggah</th><th class="num">Token</th><th>Diambil via</th><th>Status</th></tr></thead>
      <tbody>
{chr(10).join(up_rows)}
      </tbody>
    </table>
    </div>
  </section>

{sig_block}

  <section style="margin-top:1.25rem">
    <h2 style="font-size:var(--step-1)">Topik yang terdeteksi</h2>
    <div class="chips">{topic_chips or '<span class="hint">tidak ada</span>'}</div>
    <p class="hint" style="margin:.5rem 0 0">Ini sinyal leksikal, bukan klasifikasi.
    Kategori dihitung dari daftar kata di profil, jadi bisa salah baca konteks.</p>
  </section>

  <section style="margin-top:1.75rem">
    <h2 style="font-size:var(--step-1)">Transkrip</h2>
    <p class="hint" style="margin:0 0 .5rem">Cap waktu di kiri bertaut ke detik yang tepat di YouTube.
    Teks di bawah ini ada di dalam HTML halaman — bukan diambil lewat JavaScript.</p>
    <div class="transcript">
{chr(10).join(paras)}
    </div>
  </section>
{nav_html}
"""
    return page(
        f"{s['title']} — {fmt_date(s['date'])}",
        body,
        desc=f"Transkrip lengkap pidato Prabowo, {fmt_date(s['date'])} di {s['channel']}. "
             f"{fmt_int(s['token_count'])} token, {len(s['uploads'])} unggahan tercatat.",
        canonical=f"/pidato/{s['id']}.html",
        jsonld=json.dumps({
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": s["title"],
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
    methods = " ".join(f'<span class="chip">{e(k)} {v}</span>'
                       for k, v in sorted((coverage.get("fetch_methods") or {}).items(), key=lambda kv: -kv[1]))

    body = f"""  <p class="eyebrow">Cakupan</p>
  <h1>Seberapa lengkap arsip ini</h1>
  <p class="lede">Halaman ini menunjukkan apa yang <strong>tidak</strong> ada, bukan cuma apa yang ada.
  Arsip yang mengklaim lengkap tanpa menunjukkan lubangnya tidak bisa dipercaya.</p>

  <div class="stat-row">
    <div class="stat"><span class="stat__n">{fmt_int(coverage.get('span_days'))}</span><span class="stat__l">hari rentang</span></div>
    <div class="stat"><span class="stat__n">{fmt_int(meta.get('event_count'))}</span><span class="stat__l">pidato</span></div>
    <div class="stat"><span class="stat__n">{len(gaps)}</span><span class="stat__l">bulan kosong</span></div>
    <div class="stat"><span class="stat__n">{e(coverage.get('date_first') or '—')}</span><span class="stat__l">pidato pertama</span></div>
  </div>

  <section style="margin-top:1.5rem">
    <h2 style="font-size:var(--step-1)">Pidato per bulan</h2>
    <p class="hint" style="margin:0 0 .5rem">Kotak bergaris putus-putus = bulan tanpa pidato sama sekali.
    Angka di dalam kotak = jumlah pidato bulan itu.</p>
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
    body = f"""  <p class="eyebrow">Tentang</p>
  <h1>Metode dan janji penelusuran</h1>
  <p class="lede">Setiap angka di situs ini harus bisa ditelusuri balik sampai ke video dan detiknya.
  Kalau tidak bisa, angka itu tidak layak ditampilkan.</p>

  <section class="panel">
    <h2 style="font-size:var(--step-1)">Satu pidato, satu halaman</h2>
    <p style="margin:.3rem 0">Pidato yang sama sering diunggah puluhan kanal. Aturannya:</p>
    <ul style="margin:.3rem 0;padding-left:1.2rem">
      <li>Satu peristiwa pidato dihitung <strong>sekali</strong>, walau diunggah banyak kanal.</li>
      <li>Satu unggahan dipilih jadi <strong>kanonik</strong> — yang dipakai untuk hitungan token.</li>
      <li>Pemilihannya bukan sekadar yang terpanjang. Livestream sering terpadding
      pembawa acara, jadi unggahan yang pembukanya jauh dari pola pembuka pidato justru dibuang.</li>
      <li><strong>Semua unggahan lain tetap dicatat</strong> dan ditampilkan di halaman pidato,
      termasuk yang dibuang. Yang dibuang tidak disembunyikan.</li>
    </ul>
  </section>

  <section class="panel">
    <h2 style="font-size:var(--step-1)">Asal transkrip</h2>
    <p>Sumbernya caption YouTube bahasa Indonesia, bukan transkrip dari audio.
    Dua jalur dipakai, dan keduanya ditandai per pidato:</p>
    <div class="chips">
      <span class="chip">caption API</span>
      <span class="chip">panel transkrip YouTube</span>
    </div>
    <p class="hint" style="margin:.6rem 0 0">Kedua jalur pernah diuji pada video yang sama dan
    menghasilkan teks identik (15.621 karakter, 2.362 kata) sebelum dipakai bergantian.</p>
  </section>

  <section class="panel">
    <h2 style="font-size:var(--step-1)">Kutipan selalu bertaut ke detiknya</h2>
    <p>Setiap paragraf transkrip punya cap waktu yang menuju YouTube pada detik itu.
    Jadi pembaca bisa memeriksa sendiri apakah kutipannya benar, tanpa mempercayai situs ini.</p>
  </section>

  <section class="panel">
    <h2 style="font-size:var(--step-1)">Data mesin</h2>
    <p>Versi JSON dari data yang sama, untuk yang mau mengolahnya sendiri:</p>
    <ul style="margin:.3rem 0;padding-left:1.2rem">
      <li><a href="data/index.json">data/index.json</a> — daftar semua pidato</li>
      <li><a href="data/coverage.json">data/coverage.json</a> — peta cakupan</li>
      <li><a href="data/meta.json">data/meta.json</a> — asal-usul build</li>
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
    <h2 style="font-size:var(--step-1)">Asal-usul build</h2>
    <dl class="dl">
      <dt>Dibangun</dt><dd class="mono">{e(meta.get('built_at') or '—')}</dd>
      <dt>Mesin</dt><dd><a href="https://github.com/himanusia/youtube-speech-corpus" rel="noopener">youtube-speech-corpus</a>
        <span class="mono hint">@ {(meta.get('engine_commit') or '—')[:12]}</span></dd>
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
    speeches = [json.loads(p.read_text(encoding="utf-8"))
                for p in sorted((DATA / "speeches").glob("*.json"))]
    index = json.loads((DATA / "index.json").read_text(encoding="utf-8"))
    coverage = json.loads((DATA / "coverage.json").read_text(encoding="utf-8"))
    meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))

    if not speeches:
        print("Tidak ada pidato. Jalankan build_log.py dulu.")
        return 1

    # Bersihkan keluaran lama supaya tidak ada sisa halaman yatim.
    if DOCS.exists():
        shutil.rmtree(DOCS)
    (DOCS / "pidato").mkdir(parents=True)
    (DOCS / "data" / "speeches").mkdir(parents=True)

    (DOCS / "index.html").write_text(render_index(index, meta, coverage), encoding="utf-8")
    (DOCS / "cakupan.html").write_text(render_coverage(coverage, meta, speeches), encoding="utf-8")
    (DOCS / "tentang.html").write_text(render_about(meta, coverage), encoding="utf-8")
    (DOCS / "404.html").write_text(render_404(), encoding="utf-8")

    for i, s in enumerate(speeches):
        prev = speeches[i - 1] if i > 0 else None
        nxt = speeches[i + 1] if i + 1 < len(speeches) else None
        (DOCS / "pidato" / f"{s['id']}.html").write_text(
            render_speech(s, prev, nxt), encoding="utf-8")

    # aset
    shutil.copy2(WEB / "theme.css", DOCS / "theme.css")
    (DOCS / "app.js").write_text(APP_JS, encoding="utf-8")

    # data mesin
    for name in ("index.json", "coverage.json", "meta.json"):
        shutil.copy2(DATA / name, DOCS / "data" / name)
    for p in (DATA / "speeches").glob("*.json"):
        shutil.copy2(p, DOCS / "data" / "speeches" / p.name)

    # indeks pencarian: satu string teks penuh per pidato
    search = {
        s["id"]: (s["title"] + " " + s["channel"] + " " + s["date"] + " "
                  + " ".join(p["text"] for p in s["transcript"]))[:400000]
        for s in speeches
    }
    (DOCS / "data" / "search.json").write_text(
        json.dumps(search, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    urls = [f"{SITE_BASE}/", f"{SITE_BASE}/cakupan.html", f"{SITE_BASE}/tentang.html"]
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

    total_bytes = sum(f.stat().st_size for f in DOCS.rglob("*") if f.is_file())
    print(f"OK  {len(speeches)} halaman pidato + 3 halaman utama")
    print(f"    {len(urls)} URL di sitemap")
    print(f"    {total_bytes/1024/1024:.2f} MB total di docs/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
