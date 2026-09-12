# Arsip Pidato Presiden Prabowo

Log pidato, sambutan, dan pernyataan resmi Presiden Prabowo Subianto — lengkap dengan
transkrip ber-cap-waktu, daftar semua unggahan, dan sumber yang bisa ditelusuri.

Repositori ini **bukan** mesin analisisnya. Mesinnya ada di
[youtube-speech-corpus](https://github.com/himanusia/youtube-speech-corpus) dan di sini
dipakai sebagai submodule yang terkunci ke satu commit. Repo ini memuat profil Prabowo,
arsip datanya, dan situs statisnya.

## Prinsipnya

Setiap angka di situs ini harus bisa ditelusuri balik ke video dan detiknya.
Kalau tidak bisa, angka itu tidak layak ditampilkan.

Konsekuensi praktisnya:

| Klaim | Cara diperiksa |
|---|---|
| Satu pidato dihitung sekali | Halaman pidato menampilkan **semua** unggahan yang memuatnya |
| Sumber kanonik dipilih dengan alasan | Setiap unggahan ditandai kanonik atau tidak, dengan angka pembandingnya |
| Kutipan itu benar | Cap waktu di transkrip bertaut ke detik yang tepat di YouTube |
| Cakupan tidak dilebih-lebihkan | Halaman cakupan menampilkan bulan yang **kosong**, bukan cuma yang terisi |

## Struktur

```
engine/                 submodule → youtube-speech-corpus (terkunci ke satu commit)
profiles/prabowo.json   konfigurasi domain (kata topik, penanda kebijakan, aturan kanonik)
data/
  speeches/<slug>.json  satu berkas per pidato: metadata + semua unggahan + transkrip penuh
  index.json            daftar ringkas untuk situs
  coverage.json         peta cakupan dan lubangnya
  meta.json             asal-usul build (commit engine, waktu, jumlah)
scripts/
  build_log.py          korpus → arsip per pidato
  build_site.py         arsip → situs HTML statis
docs/                   hasil build — inilah yang di-deploy (Cloudflare Pages)
web/theme.css           sumber tema (disalin ke docs/ saat build)
```

## Menjalankan

Butuh Python 3.10+ dan tidak butuh paket pihak ketiga.

```bash
git clone --recurse-submodules <repo-url>
cd <repo>
python3 scripts/build_log.py     # korpus → data/
python3 scripts/build_site.py    # data/  → docs/
```

`build_log.py` mencari korpus dengan urutan: argumen `--source PATH`, variabel
lingkungan `CORPUS_SOURCE`, working copy `youtube-speech-corpus` di direktori sebelah,
lalu `engine/data/prabowo/`.

```bash
python3 scripts/build_log.py --source /path/ke/data/prabowo
CORPUS_SOURCE=/path/ke/data/prabowo python3 scripts/build_log.py
```

Contoh:

```bash
python3 scripts/build_log.py
# OK  67 pidato
#     128 upload
#     2988 paragraf ber-cap-waktu
#     153,699 token

python3 scripts/build_site.py
# OK  67 halaman pidato + 3 halaman utama
#     70 URL di sitemap
```

Pratinjau lokal:

```bash
python3 -m http.server 8899 --directory docs
```

## Kenapa situsnya HTML statis

Seluruh transkrip ditulis **ke dalam HTML**, bukan diambil lewat JavaScript. Situsnya
harus bisa dibaca mesin pencari, scraper, dan siapa pun yang mematikan JS.

- Tanpa JavaScript: daftar lengkap, semua transkrip, semua tautan — tetap ada.
- Dengan JavaScript: penyaring daftar dan tombol tema terang/gelap.
- Tidak ada server, tidak ada Worker, tidak ada permintaan jaringan saat membaca.

Yang tersedia untuk mesin:

```
sitemap.xml       70 URL
robots.txt        izin penuh + lokasi sitemap
JSON-LD           CollectionPage di daftar, Article di tiap pidato
data/*.json       versi mesin dari data yang sama
```

## Sumber transkrip

Caption YouTube bahasa Indonesia (`language_code = "id"`), **bukan** transkrip dari
audio. Dua jalur dipakai dan ditandai per pidato:

- `caption_api` — `youtube-transcript-api`
- `transcript_panel` — panel transkrip YouTube

Kedua jalur pernah diuji pada video yang sama dan menghasilkan teks identik
(15.621 karakter / 2.362 kata) sebelum dipakai bergantian, jadi pencampuran keduanya
tetap konsisten.

Raw caption dari corpus tidak dipublikasikan di repo mesin; repositori ini tempat
transkrip penuhnya dipublikasikan, dengan atribusi video asal di setiap berkas.

## Batas yang harus dibaca sebelum memakai data ini

1. **Distribusi waktu itu artefak, bukan temuan.** Penemuan lewat pencarian YouTube
   yang condong ke hasil terbaru, jadi periode 2026 lebih padat bukan karena Prabowo
   lebih sering berpidato tahun itu. Halaman cakupan menunjukkan bulan yang kosong.
2. **Semua caption auto-generated.** Aman untuk analisis bentuk bahasa; tidak aman
   untuk angka yang diucapkan (anggaran, target, persentase).
3. **Yang masuk hanya pidato, sambutan, dan pernyataan resmi.** Bukan wawancara,
   konferensi pers pendek, atau potongan klip.
4. **Pidato berbahasa asing tidak masuk** — tidak ada track caption Indonesia.
5. **Kategori topik adalah sinyal leksikal, bukan klasifikasi.** Dihitung dari daftar
   kata, jadi bisa salah baca konteks.
6. **Materi pihak ketiga.** Kutip video aslinya sebagai sumber, bukan situs ini.

## Lisensi dan atribusi

Kode di repo ini bebas dipakai. **Transkrip pidato bukan milik repo ini** — itu
rekaman publik dari kanal YouTube masing-masing, dan haknya ada pada pemiliknya.
