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
<link rel="stylesheet" href="{rel_root}theme.css?v={ASSET_V['css']}">
<link rel="alternate" type="application/json" href="{rel_root}data/index.json" title="Indeks JSON">
<script type="application/ld+json">{jsonld}</script>
</head>
<body>
<header class="top">
  <div class="wrap top__row">
    <div class="brand">
      <span class="brand__mark">&#9632;</span>
      <span class="brand__name"><a href="{rel_root}index.html" style="color:inherit">{e(SITE_NAME)}</a></span>
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
  <p>{e(SITE_NAME)} &middot; <a href="{rel_root}data/index.json">data JSON</a></p>
  <p class="hint">Transkrip dari caption YouTube (auto-generated). Periksa video aslinya sebelum mengutip.</p>
</footer>
<script src="{rel_root}app.js?v={ASSET_V['js']}" defer></script>
</body>
</html>
"""


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
        mix = max(30, 100 - rank * 9)
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
        size = 0.95 + max(0.0, min(1.0, frac)) * 2.0
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


def render_index(speeches: list[dict], meta: dict, coverage: dict, home: dict) -> str:
    rows = []
    for s in speeches:
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

    L = home.get("length") or {}
    hook = f"""  <div class="hero">
    <div class="hero__i"><span class="hero__n hero__n--accent">{fmt_int(home.get('event_count'))}</span><span class="hero__l">pidato</span></div>
    <div class="hero__i"><span class="hero__n">{fmt_int(home.get('token_count'))}</span><span class="hero__l">token</span></div>
    <div class="hero__i"><span class="hero__n">{fmt_int(home.get('upload_count'))}</span><span class="hero__l">unggahan</span></div>
    <div class="hero__i"><span class="hero__n">{fmt_int(L.get('median'))}</span><span class="hero__l">token median</span></div>
    <div class="hero__i"><span class="hero__n">{fmt_int(L.get('longest'))}</span><span class="hero__l">terpanjang</span></div>
    <div class="hero__i"><span class="hero__n">{e(format_span(coverage))}</span><span class="hero__l">rentang</span></div>
  </div>"""

    # ---- awan kata + batang kata
    tw = home.get("top_words", [])
    wc = _word_cloud(tw, 44)
    top12 = tw[:10]
    hi12 = (top12[0]["count"] if top12 else 1) or 1
    word_bars = "".join(
        _bar(w["word"], w["count"] / hi12, fmt_int(w["count"]), rank=i)
        for i, w in enumerate(top12))

    # ---- program
    prog = home.get("programs", [])[:10]
    prog_bars = "".join(_bar(x["label"], x["share"] / 100, f'{x["share"]:.0f}%', rank=i)
                        for i, x in enumerate(prog))

    # ---- konsep
    conc = home.get("concepts", [])
    conc_bars = "".join(_bar(x["label"], x["share"] / 100, f'{x["share"]:.0f}%', rank=i)
                        for i, x in enumerate(conc))

    # ---- topik
    top = home.get("topics", [])
    hi_t = (top[0]["per_1000"] if top else 1) or 1
    topic_bars = "".join(
        _bar(x["topic"].replace("_", " "), x["per_1000"] / hi_t, f'{x["per_1000"]:.1f}', rank=i)
        for i, x in enumerate(top))

    # ---- framing
    fr = {f["label"]: f for f in home.get("framing", [])}
    ratio = home.get("kita_saya_ratio")
    # urutkan menurut nilainya, jangan hardcode — pernah salah urut
    fr_sorted = sorted(home.get("framing", []), key=lambda x: -x["per_1000"])
    fr_bars = "".join(
        _bar(x["label"], x["per_1000"] / (fr_sorted[0]["per_1000"] or 1),
             f'{x["per_1000"]:.1f}', soft=x["label"] in ("kalian", "kami", "mereka"), rank=i)
        for i, x in enumerate(fr_sorted))
    yr_bars = "".join(
        _bar(y["year"], (y["ratio"] or 0) / 2.0, f'{y["ratio"]}&times;', rank=i)
        for i, y in enumerate(home.get("framing_per_year", [])))

    # ---- histogram panjang
    hist = home.get("length_histogram", [])
    hmax = home.get("length_histogram_max", 1) or 1
    hist_html = "".join(
        f'<div class="hist__c" title="{e(h["label"])} token: {h["count"]} pidato">'
        f'<span class="hist__n">{h["count"]}</span>'
        f'<span class="hist__b{"" if h["count"] else " hist__b--zero"}" '
        f'style="height:{(max(h["count"], 0.4) / hmax * 100):.1f}%"></span>'
        f'<span class="hist__l">{e(h["label"])}</span></div>'
        for h in hist)

    # ---- kata teratas per tahun
    pyw = "".join(
        f'<div style="margin-bottom:.7rem"><div class="card__h" style="border:0;margin:0 0 .35rem;padding:0">'
        f'<h2 style="font-size:var(--step-1)">{e(y["year"])}</h2>'
        f'<span class="unit">{fmt_int(y["tokens"])} token</span></div>'
        + "".join(_bar(w["word"], w["count"] / (y["top"][0]["count"] or 1),
                       fmt_int(w["count"]), rank=i)
                  for i, w in enumerate(y["top"]))
        + "</div>"
        for y in home.get("per_year_words", []))

    body = f"""  <h1>{e(SITE_NAME)}</h1>
  <p class="lede">Seluruh pidato, sambutan, dan pernyataan resmi yang terkumpul —
  diukur, bukan diringkas.</p>

{hook}

  <div class="dash" style="margin-top:1rem">

    <section class="card c7">
      <div class="card__h">
        <h2>Kata terbanyak</h2>
        <span class="unit">tanpa kata fungsi &amp; pronomina</span>
      </div>
      {wc}
      <p class="sub">10 teratas, dengan jumlah persisnya</p>
      <div class="bars">{word_bars}</div>
    </section>

    <section class="card c5">
      <div class="card__h">
        <h2>Program yang dibahas</h2>
        <span class="unit">% pidato</span>
      </div>
      <div class="bars">{prog_bars}</div>
      <p class="note-inline">Dihitung dari seluruh cara penyebutannya: akronim, nama panjang,
      maupun badan pelaksananya.</p>
    </section>

    <section class="card c5">
      <div class="card__h">
        <h2>Cara dia menyapa</h2>
        <span class="unit">per 1.000 token</span>
      </div>
      <div class="bars">{fr_bars}</div>
      <p class="note-inline"><strong>kita</strong> {ratio}&times; lebih sering daripada
      <strong>saya</strong>. <strong>kalian</strong> hampir tidak pernah dipakai.</p>
    </section>

    <section class="card c7">
      <div class="card__h">
        <h2>Topik</h2>
        <span class="unit">kepadatan per 1.000 token</span>
      </div>
      <div class="bars">{topic_bars}</div>
      <p class="note-inline">Kepadatan kata, bukan tingkat kepentingan. Kategori
      <em>nasional &amp; identitas</em> memakai banyak kata sekaligus sehingga selalu
      paling tinggi.</p>
    </section>

    <section class="card c6">
      <div class="card__h">
        <h2>Yang disebut masalah</h2>
        <span class="unit">% pidato</span>
      </div>
      <div class="bars">{conc_bars}</div>
      <p class="note-inline">Korupsi jauh di atas hinaan pribadi.</p>
    </section>

    <section class="card c6">
      <div class="card__h">
        <h2>Panjang pidato</h2>
        <span class="unit">jumlah pidato</span>
      </div>
      <div class="hist">{hist_html}</div>
    </section>

    <section class="card c4">
      <div class="card__h">
        <h2>Rasio kita : saya</h2>
        <span class="unit">per tahun</span>
      </div>
      <div class="bars">{yr_bars}</div>
      <p class="note-inline">Stabil di atas 1&times; setiap tahun — dia lebih sering
      memakai kata kolektif daripada kata tunggal.</p>
    </section>

    <section class="card c8">
      <div class="card__h">
        <h2>Sebaran waktu</h2>
        <span class="unit">{len(coverage.get('months_without_events', []))} bulan kosong</span>
      </div>
      <div class="heat">{_cov_cells(coverage)}</div>
      <div class="legend">
        <span>jumlah pidato per bulan</span>
        <span class="legend__s" style="background:color-mix(in srgb, var(--primary) 12%, var(--card))"></span>
        <span>sedikit</span>
        <span class="legend__s" style="background:color-mix(in srgb, var(--primary) 70%, var(--card))"></span>
        <span>banyak</span>
        <span class="legend__s" style="border-style:dashed;background:transparent"></span>
        <span>kosong</span>
      </div>
      <p class="note-inline">Kotak bergaris putus-putus = bulan tanpa pidato sama sekali.
      Sebaran yang condong ke 2026 itu <strong>artefak cara pencarian</strong>, bukan tanda
      Prabowo lebih sering berpidato tahun itu — lihat halaman
      <a href="cakupan.html">cakupan</a>.</p>
    </section>

    <section class="card c12">
      <div class="card__h">
        <h2>Kata teratas per tahun</h2>
        <span class="unit">melihat pergeseran kosakata</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(16rem,1fr));gap:1.5rem">
      {pyw}
      </div>
    </section>

    <section class="card c12">
      <div class="card__h">
        <h2>Semua pidato</h2>
        <span class="unit" id="count">{len(speeches)} pidato</span>
      </div>
      <div class="searchbar">
        <input id="q" type="search" placeholder="Cari pidato atau isi transkrip…" aria-label="Cari pidato" autocomplete="off">
      </div>
      <ol class="list" id="list" style="margin-top:1rem;list-style:none;padding:0">
{chr(10).join(rows)}
      </ol>
      <p class="empty" id="empty" hidden>Tidak ada yang cocok.</p>
    </section>

  </div>
"""
    return page(
        f"{SITE_NAME} — {len(speeches)} pidato",
        body,
        desc=f"Arsip {len(speeches)} pidato Presiden Prabowo dengan transkrip ber-cap-waktu: "
             f"kata terbanyak, program yang paling dibahas, topik, dan tautan ke video asalnya.",
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
    <p class="hint" style="margin:0 0 .5rem">Hanya satu yang dipakai untuk hitungan. Sisanya tetap dicatat.</p>
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
    <p class="hint" style="margin:.5rem 0 0">Sinyal leksikal, bukan klasifikasi.</p>
  </section>

  <section style="margin-top:1.75rem">
    <h2 style="font-size:var(--step-1)">Transkrip</h2>
    <p class="hint" style="margin:0 0 .5rem">Cap waktu di kiri bertaut ke detik yang tepat di YouTube.</p>
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
    home_path = DATA / "home.json"
    home = json.loads(home_path.read_text(encoding="utf-8")) if home_path.exists() else {}

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
    print(f"versi aset: css={ASSET_V['css']} js={ASSET_V['js']}")

    # Bersihkan keluaran lama supaya tidak ada sisa halaman yatim.
    if DOCS.exists():
        shutil.rmtree(DOCS)
    (DOCS / "pidato").mkdir(parents=True)
    (DOCS / "data" / "speeches").mkdir(parents=True)

    (DOCS / "index.html").write_text(
        render_index(index, meta, coverage, home), encoding="utf-8")
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

    # Kebijakan cache eksplisit. Tanpa ini Cloudflare tidak mengirim
    # Cache-Control sama sekali, dan browser menebak sendiri kapan CSS basi —
    # itulah sebabnya perubahan tidak terlihat walau deploy-nya sudah benar.
    # Aset boleh di-cache lama karena URL-nya sudah berversi hash;
    # HTML harus selalu diperiksa ulang supaya perubahan langsung terlihat.
    (DOCS / "_headers").write_text(
        "/*\n"
        "  X-Content-Type-Options: nosniff\n"
        "\n"
        "/theme.css\n"
        "  Cache-Control: public, max-age=31536000, immutable\n"
        "\n"
        "/app.js\n"
        "  Cache-Control: public, max-age=31536000, immutable\n"
        "\n"
        "/index.html\n"
        "  Cache-Control: public, max-age=0, must-revalidate\n"
        "\n"
        "/cakupan.html\n"
        "  Cache-Control: public, max-age=0, must-revalidate\n"
        "\n"
        "/tentang.html\n"
        "  Cache-Control: public, max-age=0, must-revalidate\n"
        "\n"
        "/pidato/*\n"
        "  Cache-Control: public, max-age=300\n"
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
