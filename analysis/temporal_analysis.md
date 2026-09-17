# Perubahan pesan Prabowo sepanjang 24 bulan

> Analisis reproducible atas **388** record teks Indonesia dalam era 2024-10-20–2026-09-16, **404.380** token setelah anotasi panggung dibuang. Q4 2024 dan Q3 2026 parsial.

## Ringkasan eksekutif

- Fokus leksikal tetap nasional/identitas di semua kuartal; puncaknya **34,36/1.000** kata pada Q2 2026 dan **33,65/1.000** pada Q3 2026.
- MBG (set alias: MBG, Makan/Makanan Bergizi, SPPG, BGN, dll.) mencapai **1,82/1.000** kata pada Q1 2026, lalu **0,49/1.000** pada Q3 2026: turun **72,9%** dari puncak.
- Kata persis **bencana** naik dari **0,02/1.000** pada Q4 2024 dan **0,02** pada Q3 2025 menjadi **0,96** pada Q4 2025; turun ke **0,45** pada Q1 2026 dan **0** pada Q2 2026.
- Median panjang record naik dari **433 token** (Q4 2024) ke **1.614 token** (Q3 2026). Ini sinyal memanjang dalam arsip, bukan bukti kausal karena komposisi acara/cakupan kuartal berubah.
- Klaim ‘kami turun 70%’ hanya cocok untuk endpoint **Q1 2025 → Q3 2026** (4,63 → 1,48/1.000; **−67,7%**); dari Q4 2024 ke Q3 2026 penurunannya hanya **−29,2%**. ‘Rakyat naik 39%’ cocok untuk Q4 2024 → Q3 2026 (5,31 → 7,31; **+37,5%**, pembulatan).

## Metode dan rekonsiliasi corpus

- `data/speeches/*.json`: 686 berkas. Filter `speaker_kind` menghasilkan 407 kandidat; dikeluarkan 12 teks Inggris dan 5 tanpa transkrip, sehingga **390 record Indonesia berteks**.
- Dengan regex token yang sama setelah pembersihan, 390 record = **410.321 token**. Dua record bertanggal sebelum pelantikan (20 Okt 2024) dikeluarkan dari analisis 24 bulan: **388 record / 404.380 token**.
- Teks resmi `transkrip_resmi.teks` dipakai bila ada (42 record era); sisanya caption. Regex anotasi panggung yang dibuang sebelum hitung: `\[[^\]]{0,60}\]`; ditemukan 2.967 anotasi pada era.
- Rate = `jumlah kecocokan / token bersih × 1.000`. Topik memakai kosakata pada `profiles/prabowo.json`; ini **sinyal leksikal**, bukan klasifikasi makna. Record tetap dihitung satu per berkas kanonik, termasuk 78 yang diberi `is_fragment`.

## Tabel kuartal × topik

| Kuartal | n | Token | Topik 1 | Topik 2 | Topik 3 |
|---|---:|---:|---|---|---|
| Q4 2024 | 69 | 59.849 | nasional_dan_identitas 29,59 | kesehatan_dan_gizi 4,51 | ekonomi 4,23 |
| Q1 2025 | 56 | 34.548 | nasional_dan_identitas 25,39 | ekonomi 4,78 | kesehatan_dan_gizi 3,76 |
| Q2 2025 | 52 | 18.870 | nasional_dan_identitas 32,17 | kesehatan_dan_gizi 6,52 | pangan 4,56 |
| Q3 2025 | 40 | 43.959 | nasional_dan_identitas 34,15 | ekonomi 8,62 | kesehatan_dan_gizi 5,94 |
| Q4 2025 | 44 | 52.173 | nasional_dan_identitas 20,22 | pendidikan 8,45 | kesehatan_dan_gizi 7,82 |
| Q1 2026 | 48 | 75.138 | nasional_dan_identitas 31,68 | kesehatan_dan_gizi 6,29 | ekonomi 5,58 |
| Q2 2026 | 44 | 50.869 | nasional_dan_identitas 34,36 | ekonomi 8,73 | pangan 5,21 |
| Q3 2026 | 35 | 68.974 | nasional_dan_identitas 33,65 | ekonomi 6,74 | kesehatan_dan_gizi 5,97 |

Angka di setiap sel adalah mention per 1.000 token; angka dalam sel tidak bisa dibandingkan sebagai proporsi record. `nasional_dan_identitas` memang memuat kata luas seperti *Indonesia, negara, rakyat, bangsa* sehingga harus dibaca sebagai intensitas kosakata identitas, bukan klaim bahwa semua isi pidato adalah identitas.

### Pergeseran yang terlihat

- Q4 2024–Q1 2025: identitas/nasional tetap nomor satu; ekonomi dan kesehatan/gizi mengisi posisi berikutnya.
- Q2–Q3 2025: kesehatan/gizi dan ekonomi menguat; Q3 2025 ekonomi mencapai **8,62/1.000**, tertinggi dalam tabel. Ini beriringan dengan kemunculan lebih seringnya istilah MBG, Sekolah Rakyat, dan partai dalam korpus, tetapi tabel tidak membuktikan sebab.
- Q4 2025: posisi kedua bergeser ke pendidikan (**8,45/1.000**) dan kesehatan/gizi (**7,82/1.000**); ini kuartal yang memuat respons bencana Sumatra/Aceh.
- Q1–Q3 2026: ekonomi kembali tinggi (5,58; 8,73; 6,74), pangan berada 4,47–5,21, sementara MBG turun setelah puncak Q1.

## Program dan istilah yang berubah

| Kuartal | Bencana persis | Bencana set alias | MBG set alias | Danantara | Kami | Rakyat |
|---|---:|---:|---:|---:|---:|---:|
| Q4 2024 | 0,02 | 0,05 | 0,43 | 0,03 | 2,09 | 5,31 |
| Q1 2025 | 0,06 | 0,32 | 0,78 | 0,64 | 4,63 | 4,60 |
| Q2 2025 | 0,00 | 0,05 | 0,74 | 0,21 | 5,46 | 4,45 |
| Q3 2025 | 0,02 | 0,04 | 1,23 | 0,41 | 5,44 | 7,26 |
| Q4 2025 | 0,96 | 1,69 | 0,88 | 0,29 | 4,45 | 4,03 |
| Q1 2026 | 0,45 | 0,60 | 1,82 | 0,27 | 2,12 | 5,50 |
| Q2 2026 | 0,00 | 0,06 | 0,73 | 0,29 | 1,87 | 5,41 |
| Q3 2026 | 0,25 | 0,32 | 0,49 | 0,48 | 1,48 | 7,31 |

- **Bencana:** angka awal 0,02 → 0,96/1.000 (Q3 2025 → Q4 2025) adalah kenaikan **41,6×** (selisih +0,935/1.000). Setelah itu kata persisnya 0,45 pada Q1 2026 dan 0 pada Q2 2026; Q3 2026 kembali 0,25. Set alias lebih luas memberi 1,69 pada Q4 2025 karena juga menangkap BNPB/BMKG/banjir/longsor, jadi definisi harus disebut.
- **MBG:** set alias naik dari 0,43 (Q4 2024) ke puncak 1,82 (Q1 2026), lalu 0,73 (Q2) dan 0,49 (Q3). Penurunan puncak→Q3 = **−72,9%**. Ini tidak berarti program berhenti: Q3 masih muncul di 13 dari 35 record (lihat JSON).
- **Danantara:** mulai 0,03 (Q4 2024), melonjak 0,64 (Q1 2025), dan masih 0,48 (Q3 2026); tidak memenuhi definisi ‘muncul lalu hilang’.

## Topik yang muncul lalu tidak muncul lagi

Definisi operasional: istilah punya ≥2 mention, mention terakhir paling lambat Juni 2026, dan tidak muncul pada ≥3 bulan pengamatan berikutnya sampai 16 Sep 2026. Ini berarti “tidak muncul lagi dalam corpus sampai batas observasi”, bukan bukti metafisik bahwa topik tidak pernah dibahas di luar corpus.

| Istilah | Pertama | Terakhir | Total mention | Bulan aktif | Bulan kosong setelah terakhir | Kekuatan |
|---|---|---|---:|---:|---:|---|
| Freeport | 2024-11 | 2025-03 | 3 | 2 | 18 | sinyal lemah–menengah (volume kecil / definisi korpus) |
| BRICS | 2024-11 | 2025-08 | 11 | 3 | 13 | sinyal lemah–menengah (volume kecil / definisi korpus) |

- **Freeport** berhenti setelah 3 mention (November 2024 dan Maret 2025) dan tidak muncul lagi pada 18 bulan observasi berikutnya. Karena hanya 3 mention, ini sinyal, bukan temuan kuat tentang agenda.
- **BRICS** terakhir muncul Agustus 2025 (11 mention total; 5 record aktif) dan tidak muncul dalam teks Indonesia sampai September 2026. Namun ada record **KTT BRICS 2026 India** berbahasa Inggris yang dikeluarkan dari denominator; jadi klaim yang sah hanya “menghilang dari teks Indonesia yang dianalisis”, bukan “Prabowo berhenti membahas BRICS”.

## Apakah pidato makin panjang?

| Kuartal | n | Mean token | Median | P25–P75 | Min–maks |
|---|---:|---:|---:|---:|---:|
| Q4 2024 | 69 | 867 | 433 | 230–850 | 78–6.113 |
| Q1 2025 | 56 | 616 | 423 | 171–912 | 26–3.523 |
| Q2 2025 | 52 | 362 | 160 | 122–392 | 60–2.660 |
| Q3 2025 | 40 | 1.099 | 476 | 168–791 | 74–5.855 |
| Q4 2025 | 44 | 1.185 | 300 | 192–1.479 | 52–9.835 |
| Q1 2026 | 48 | 1.565 | 869 | 220–1.973 | 70–8.244 |
| Q2 2026 | 44 | 1.156 | 303 | 118–2.068 | 36–7.610 |
| Q3 2026 | 35 | 1.970 | 1.614 | 427–2.675 | 10–7.655 |

Median kuartal berkorelasi positif dengan indeks waktu (**r=0.598**, slope 114.53 token/kuartal); mean lebih sensitif terhadap pidato panjang (**r=0.808**, slope 168.017). Median dua kuartal awal = 433, dua kuartal akhir = 1.067, perubahan **146.4%**. Ini bukti deskriptif yang cukup konsisten, tetapi README corpus sendiri memperingatkan distribusi waktu dipengaruhi artefak penemuan/cakupan.

## Tiga record sebelum vs tiga record sesudah peristiwa

Jendela dibuat deterministik: tiga record terakhir dengan tanggal `< anchor`, lalu tiga record pertama dengan tanggal `>= anchor`, diurutkan `(date, title, id)`. Karena respons hari-H masuk sisi “sesudah”, interpretasi yang aman adalah perubahan pada **reaksi awal**, bukan efek kausal.

### Demo Agustus 2025 — anchor 2025-08-29

tanggal pertama arsip memuat Pernyataan Presiden Prabowo (29 Agustus 2025); sisi sesudah mengambil 3 entri pertama pada/ setelah tanggal anchor

**Sebelum:**
- 2025-08-26 — 96 token — Keterangan Pers Presiden Prabowo usai Resmikan Gedung Layanan Terpadu dan INN RSPON, 26 Agustus 2025
- 2025-08-26 — 284 token — Presiden Prabowo Tinjau Fasilitas Modern RSPON Mahar Mardjono Disambut Positif, 26 Agustus 2025
- 2025-08-28 — 179 token — Presiden Prabowo Resmi Buka APKASI Otonomi Expo 2025, Tangerang, 28 Agustus 2025

**Sesudah/reaksi awal:**
- 2025-08-29 — 358 token — Pernyataan Presiden Prabowo, 29 Agustus 2025
- 2025-08-31 — 739 token — Pernyataan Presiden Prabowo Menyikapi Aksi Demo
- 2025-09-01 — 655 token — Keterangan Pers Presiden Prabowo Usai Jenguk Polisi dan Masyarakat Korban Demo, 1 September 2025

| Istilah | Sebelum /1.000 | Sesudah /1.000 | Δ /1.000 | Δ% |
|---|---:|---:|---:|---:|
| kita | 7,16 | 25,11 | 17,96 | 251.0% |
| rakyat | 0,00 | 11,42 | 11,42 | — |
| negara | 0,00 | 11,42 | 11,42 | — |
| kami | 10,73 | 2,85 | -7,88 | -73.4% |
| hukum | 0,00 | 4,00 | 4,00 | — |
| polisi/polri | 0,00 | 3,42 | 3,42 | — |
| damai | 0,00 | 2,85 | 2,85 | — |
| keamanan | 0,00 | 2,28 | 2,28 | — |


### Banjir Sumatra Desember 2025 — anchor 2025-12-01

tanggal pertama arsip memuat kunjungan langsung ke wilayah terdampak di Sumatra/Aceh; sisi sesudah mengambil 3 entri pertama pada/ setelah tanggal anchor

**Sebelum:**
- 2025-11-28 — 1404 token — LIVE Pidato Presiden Prabowo di Pertemuan Tahunan Bank Indonesia Tahun 2025
- 2025-11-28 — 642 token — Presiden Prabowo Perintahkan Pengiriman Bantuan Cepat ke Tiga Provinsi Terdampak Bencana,28 Nov 2025
- 2025-11-28 — 2279 token — [FULL] Pidato Prabowo Di Puncak Peringatan Hari Guru Nasional #beritasatu

**Sesudah/reaksi awal:**
- 2025-12-01 — 306 token — Keterangan Pers Presiden Prabowo Usai Kunjungi Lokasi Bencana di Tapanuli Tengah, 1 Desember 2025
- 2025-12-01 — 210 token — Presiden Prabowo Kunjungi Wilayah Terdampak Bencana di Tapanuli Tengah, 1 Desember 2025
- 2025-12-01 — 196 token — Presiden Prabowo Tinjau Langsung Daerah Terdampak Bencana di Sumatra Utara, Aceh, dan Sumatra Barat

| Istilah | Sebelum /1.000 | Sesudah /1.000 | Δ /1.000 | Δ% |
|---|---:|---:|---:|---:|
| bantuan | 1,39 | 11,24 | 9,85 | 710.1% |
| kita | 35,84 | 43,54 | 7,70 | 21.5% |
| kami | 4,39 | 8,43 | 4,03 | 91.8% |
| rakyat | 4,86 | 2,81 | -2,05 | -42.1% |
| negara | 3,24 | 1,40 | -1,83 | -56.6% |
| bencana | 1,39 | 2,81 | 1,42 | 102.5% |
| korupsi | 1,39 | 0,00 | -1,39 | -100.0% |
| polisi/polri | 0,69 | 1,40 | 0,71 | 102.3% |

Interpretasi berbasis hitungan:
- Demo: tiga sebelum = 559 token; tiga pada/setelah anchor = 1.752 token. `demo` 0,00 → 1,71/1.000; `polisi/polri` 0,00 → 3,42; `hukum` 0,00 → 4,00; `kita` 7,16 → 25,11. `kami` 10,73 → 2,85/1.000. Ini perubahan kosakata yang jelas pada jendela, tetapi n kecil dan genre berubah dari kunjungan/eksposisi ke pernyataan/kunjungan korban.
- Bencana Sumatra: tiga sebelum = 4.325 token; tiga kunjungan 1 Desember = 712 token. `bencana` 1,39 → 2,81/1.000 dan `bantuan` 1,39 → 11,24; `kita` 35,84 → 43,54. Pemendekan mean/median terjadi karena tiga record sesudah adalah laporan/kunjungan pendek; jangan baca sebagai perubahan umum panjang pidato.

## Jenis acara dan periode

Indikator dihitung dari judul arsip, bukan klasifikasi manual isi. `sidang kabinet/ratas` mencari “sidang kabinet”, “rapat kabinet”, “ratas”, atau “rapat terbatas”. `panggung partai (sempit)` mencari nama/kata partai. Karena indikator judul dapat salah klasifikasi dan hit-nya sedikit, korelasi diberi label sinyal lemah.

| Kuartal | Sidang kabinet/ratas | Panggung partai (sempit) |
|---|---:|---:|
| Q4 2024 | 5/69 (7.2%) | 0/69 (0.0%) |
| Q1 2025 | 5/56 (8.9%) | 3/56 (5.4%) |
| Q2 2025 | 0/52 (0.0%) | 0/52 (0.0%) |
| Q3 2025 | 0/40 (0.0%) | 3/40 (7.5%) |
| Q4 2025 | 3/44 (6.8%) | 1/44 (2.3%) |
| Q1 2026 | 0/48 (0.0%) | 0/48 (0.0%) |
| Q2 2026 | 0/44 (0.0%) | 0/44 (0.0%) |
| Q3 2026 | 1/35 (2.9%) | 3/35 (8.6%) |

- Sidang kabinet/ratas: 5/69 (7,2%) pada Q4 2024, 5/56 (8,9%) Q1 2025, nol pada Q2–Q3 2025, 3/44 (6,8%) Q4 2025, nol Q1–Q2 2026, 1/35 (2,9%) Q3 2026; r terhadap indeks kuartal = **-0.5167**. Ada penurunan indikatif, bukan tren monoton.
- Panggung partai sempit: 0, 3, 0, 3, 1, 0, 0, 3 record per kuartal; r = **0.223**. Tidak mendukung klaim ‘makin jarang’ secara kuat; pada Q3 2026 justru 3/35 (8,6%).
- Kesimpulan jenis acara: ada sinyal sidang kabinet/ratas lebih jarang setelah awal masa jabatan, tetapi bukti lemah karena hanya 14 judul match dan arsip bukan panel acara yang lengkap. Panggung partai tidak menunjukkan penurunan yang stabil.

## Batas interpretasi

- Caption otomatis dan transkrip resmi tidak identik; angka kata adalah ukuran bahasa, bukan validasi angka faktual yang diucapkan.
- Kategori topik overlap dan generic (mis. `anak`, `rumah`, `Indonesia`); jangan menyamakan rate dengan porsi makna pidato.
- Semua klaim absence dibatasi pada corpus, bahasa, dan tanggal pengamatan. Record tanpa transkrip/berbahasa Inggris tidak boleh dihitung sebagai nol mention.
- Event-window n=3 per sisi adalah deskriptif. Perbedaan panjang/genre dan record yang berdekatan tanggal dapat mengubah rate; tidak ada uji kausal.

## Reproduksi

```bash
cd /Users/mac/.hermes/workspace/prabowo-speech-log
python3 analysis/prabowo_temporal_analysis.py
```

Script menghasilkan `analysis/temporal_analysis.json` (angka dan record window) serta file laporan ini.

