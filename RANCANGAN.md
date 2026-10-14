# RANCANGAN — Graph Hacks: Context for AI Agents

Disiapkan 12 Okt 2026 (atas persetujuan Akew, opsi "gas dua-duanya").
Status: FAKTA TERVERIFIKASI dari halaman resmi · PENDAFTARAN BELUM (butuh browser, lihat §5) · BUILD BELUM DIMULAI (sesuai aturan: implementasi FalkorDB utama wajib pekerjaan baru selama event).

---

## 1. Fakta resmi terverifikasi

Sumber: halaman resmi https://www.wemakedevs.org/hackathons/falkordb (dibaca 12 Okt 2026) + halaman Luma resmi acara https://luma.com/graph-hacks (pendukung).

- **Nama persis:** Graph Hacks: Context for AI Agents ("Graph Hacks")
- **Penyelenggara:** WeMakeDevs, powered by **FalkorDB**
  - 🔴 KOREKSI PENTING atas lead awal: ini **BUKAN The Graph Protocol** (bukan subgraph/GraphQL token API). "Graph" di sini = **graph database FalkorDB**. Sponsor & teknologi wajibnya FalkorDB.
- **Format:** Online, worldwide, GRATIS. Solo atau tim maks 4 orang. Tanpa syarat pengalaman graph database. Asisten coding AI DIIZINKAN eksplisit.
- **Jendela event (resmi, FAQ halaman resmi):** Kamis 15 Okt 2026 00:01 IST s.d. Minggu 18 Okt 2026 23:59 IST.
  - = **15 Okt 2026 01:31 WIB** s.d. **deadline submission Senin 19 Okt 2026 01:29 WIB**.
- **Syarat keras proyek:**
  - FalkorDB WAJIB jadi graph database utama dan menopang bagian sentral produk ("the graph has to shape what the agent does, not sit on the side").
  - Submission + implementasi FalkorDB utamanya = pekerjaan BARU yang diselesaikan selama event. Library/template/infrastruktur umum boleh dipakai ulang.
  - Bahasa/framework/platform bebas.
  - Deployment live lebih disukai; bila tidak bisa deploy: instruksi setup lokal lengkap + video demo yang berfungsi.
- **Track (boleh masuk 1, 2, atau ketiganya; tiap track 1 hadiah):**
  1. **Agents That Act on Connected Data** — iPhone 18 Pro. Fokus: multi-hop reasoning, graph query/algorithm sebagai tool agent (termasuk via MCP), aksi berdasarkan isi graph, hasil yang bisa dijelaskan.
  2. **Agent Memory and Coordination** — PS5 + GTA VI. Fokus: memori episodik/semantik/prosedural, riwayat percakapan persisten, shared state & handoff antar-agent, memori terpisah per user/tenant.
  3. **Company Brain** — M6 Mac Mini. Fokus: pengetahuan dari docs/ticket/chat dalam satu graph, siapa pemilik/ahli apa, menelusur keputusan ke sumbernya, jawaban bersumber jelas.
- **Hadiah sampingan:** AirPods 5 untuk blog post proyek terbaik (1 pemenang, per halaman resmi); kaos untuk SETIAP anggota 50 tim teratas (dikirim ke alamat — alamat kirim baru dibutuhkan BILA menang, keputusan Akew saat itu).
- **Total pool:** $20.000 (mayoritas berbentuk barang, bukan uang tunai).
- **Skala kompetisi:** postingan LinkedIn penyelenggara menyebut 5.000+ pendaftar — lapangan sangat ramai; target realistis: top 50 + peluang hadiah blog, bukan janji juara track.
- **Komunitas/support:** Discord FalkorDB terbuka selama event (mencari tim / tanya graph modeling).
- **Pendaftaran:** di situs WeMakeDevs itu sendiri — buat akun gratis / sign in, lalu klik "Register now" di halaman hackathon; tim & submission dikelola dari panel yang sama. Luma HANYA untuk reminder (bukan pendaftaran resmi).

## 2. Ide proyek — "RecallGraph" (nama kerja, bisa diganti)

Satu kalimat: **asisten riset AI yang mengingat semuanya ke dalam graph — dan menunjukkan jalur penalarannya.**

Kenapa ide ini:
- Nempel persis ke brief resmi: "remember across sessions", "share state between agents", "show the path behind an answer" — tiga frasa itu adalah fitur inti, bukan tempelan.
- Masuk **Track 02 (utama)** + **Track 01 (kedua)**: agent tidak cuma menjawab, tapi menyusun rencana aksi dari traversal graph.
- Data demo fiktif mini-company (orang–proyek–keputusan) memberi rasa Track 03 tanpa menambah scope.
- Bisa dibangun solo oleh Muse dalam 4 hari dengan pola yang sudah terbukti di proyek sebelumnya (Python stdlib, LLM lokal, test suite).

### Alur inti
1. **Ingest** — user memasukkan catatan/teks chat/dokumen kecil → extractor mengekstrak entitas (Person, Project, Topic, Decision, Task, Source) + relasinya → ditulis ke FalkorDB. Satu graph per user (multigraph FalkorDB).
2. **Ingat** — tiap sesi percakapan jadi node `Episode` yang terhubung ke entitas; fakta yang berubah ditandai relasi `SUPERSEDES` bertimestamp (fakta lama tidak dihapus, tapi tidak lagi dianggap berlaku).
3. **Recall & bertindak** — pertanyaan dijawab dari traversal Cypher multi-hop di atas subgraph yang relevan saja. Jawaban WAJIB menyertakan **jalur graph** yang dipakai (node→relasi→node), dirender sebagai rantai yang bisa dibaca manusia. Dari jalur yang sama, agent menyusun daftar aksi ("siapa mengerjakan apa, berdasarkan keputusan mana").
4. **Koordinasi dua agent, satu graph bersama:**
   - **Librarian** — menulis & merapikan memori (ingest, dedupe, supersede).
   - **Scout** — membaca memori dan menyusun brief ("yang berubah sejak kemarin + 3 aksi yang disarankan") lewat node `Task` berstatus sebagai mekanisme handoff.

### Skenario demo (3 babak, semua data fiktif)
1. Sesi 1: ajari agent soal mini-company fiktif (6 orang, 3 proyek, 4 keputusan) lewat ingest beberapa catatan.
2. Restart aplikasi (membuktikan persistensi), lalu tanya: "Siapa yang harus me-review perubahan payments API, dan kenapa?" → jawaban + jalur 3-hop (orang → pernah mengerjakan → sistem ← bergantung — keputusan).
3. Scout menyusun brief pagi dari memori yang sama tanpa diajari ulang.

## 3. Arsitektur (sederhana, realistis 4 hari)

Pola stdlib-first seperti ClauseWise/RestockRadar yang sudah terbukti di VM ini:

```
graph-hacks/
  app.py               # UI web stdlib http.server: chat, ingest, tampilan jalur graph (SVG dirender server)
  graphmem/
    store.py           # wrapper client FalkorDB (pip: falkordb) — semua Cypher di sini
    extract.py         # extractor pluggable (lihat di bawah)
    agents.py          # Librarian (tulis) + Scout (baca/brief)
    demo_data.py       # data fiktif mini-company untuk demo
  tests/               # pytest: persistensi lintas restart, recall multi-hop, supersede, isolasi per-user
  README.md            # setup lokal lengkap (syarat bila tidak deploy)
  LICENSE              # MIT
  SUBMISSION-DRAFT.md  # draf teks submission panel WeMakeDevs (diisi saat build)
```

- **Extractor pluggable:** (a) utama: LLM lokal Qwen2.5-3B GGUF via llama-cpp-python (sudah terpasang untuk InvoicePilot) dengan prompt JSON-ketat; (b) fallback deterministik (pencocokan nama/entitas dari daftar + relasi ko-okurensi) — demo TIDAK pernah bergantung penuh pada kualitas model 3B.
- **Tanpa dependensi berat:** selain `falkordb` client + `llama-cpp-python` yang sudah ada.
- **UI:** satu halaman — kolom ingest, kolom tanya, panel "jalur penalaran" (rantai node bergaya breadcrumb + daftar aksi Scout). Cukup untuk video demo <3 menit.

### 🔴 Keputusan infrastruktur FalkorDB (harus beres SEBELUM 15 Okt)
Docker **TIDAK terpasang** di VM ini (terverifikasi 12 Okt: `docker: command not found`), jadi jalur dokumentasi resmi (`docker pull falkordb/falkordb`) belum bisa jalan. Urutan percobaan:
1. Install Docker (`apt install docker.io` + jalankan dockerd) — uji cepat 13–14 Okt; bila VM tidak bisa menjalankan dockerd, langsung tinggalkan.
2. **FalkorDB Cloud free tier** — signup butuh browser (agen utama; stop-and-report bila CAPTCHA) — client Python konek via protokol Redis dari VM.
3. Build FalkorDB dari source sebagai modul Redis — berat (Rust/C), HANYA jalan terakhir.

Catatan kepatuhan: menyiapkan infrastruktur & scaffold repo (README kerangka, lisensi, struktur folder) sebelum 15 Okt adalah persiapan umum yang diizinkan aturan ("libraries, templates, and infrastructure" boleh dipakai ulang) — **implementasi FalkorDB pada proyek ini ditulis selama 15–18 Okt**.

## 4. Rencana hari per hari

- **13–14 Okt (persiapan):** pendaftaran diselesaikan agen utama (lihat §5); keputusan runtime FalkorDB + smoke test koneksi (script sekali-pakai di luar repo proyek); scaffold repo publik GitHub `airrdrrop1` (README kerangka + LICENSE + struktur folder).
- **15 Okt:** `store.py` + `extract.py` + pipeline ingest; test persistensi lintas restart lolos.
- **16 Okt:** recall multi-hop + penjelasan jalur + UI dasar; skenario demo babak 1–2 jalan end-to-end.
- **17 Okt:** agent Scout + brief; data demo final; rekam draf video demo; mulai draf blog post DEV (untuk hadiah sampingan AirPods).
- **18 Okt:** test penuh, README final, video final, **submit di panel WeMakeDevs target ≤ 20:00 WIB** (buffer ±5,5 jam sebelum deadline 19 Okt 01:29 WIB); blog post diterbitkan setelah submission terkunci.

Deliverable submission: repo GitHub publik + README setup + demo (live bila hosting memungkinkan; jika tidak: video <3 menit + instruksi lokal lengkap) + teks submission di panel.

## 5. Pendaftaran — yang dibutuhkan (stop-and-report)

Pendaftaran BELUM dilakukan. Formulirnya dirender JavaScript di situs WeMakeDevs (fetch teks hanya memuat "Loading…") dan subagen ini tidak bisa mengoperasikan browser live. Yang perlu dijalankan agen utama sebagai SATU browser task:

1. Buka https://www.wemakedevs.org/hackathons/falkordb → buat akun WeMakeDevs gratis / sign in. Identitas: email farming **airrdrrop1@gmail.com** (dan GitHub `airrdrrop1` bila ditawarkan sebagai opsi sign-in). JANGAN memasukkan data pribadi Akew.
2. Klik **Register now** di halaman itu, mode **SOLO** (tim bisa diubah dari panel yang sama nanti).
3. Bila ada kode verifikasi email: ambil dari Gmail farming via konektor (pola yang sudah berjalan). Bila mentok CAPTCHA/login wall: berhenti & laporkan persis tampilannya (pola stop-and-report hackathon sebelumnya).
4. Luma (https://luma.com/graph-hacks) OPSIONAL — hanya reminder; boleh dilewati.
5. Bukti yang diminta kembali: tangkapan status "Registered" / panel tim tampil di akun.

Setelah terdaftar, tidak ada langkah lain sampai kickoff 15 Okt 01:31 WIB selain persiapan §4.

## 6. Risiko & catatan jujur

- 5.000+ pendaftar: peluang juara track kecil; nilai realistis = top-50 (kaos), peluang blog prize, dan portofolio. Biaya kita hanya waktu build 4 hari.
- Hadiah berbentuk barang (iPhone/PS5/Mac Mini/AirPods/kaos) — bukan uang; pencatatan ke tracker penghasilan sebagai nilai barang bila menang.
- Kualitas ekstraksi LLM lokal 3B terbatas → fallback deterministik menjaga demo tetap jujur dan berfungsi.
- Bila runtime FalkorDB gagal total di VM maupun cloud sebelum 15 Okt: proyek tidak bisa memenuhi syarat keras — laporkan ke Akew sebelum membakar waktu build.
