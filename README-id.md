# Asset Management untuk Odoo 19

> [Read in English](README.md)

Modul Odoo 19 untuk mengelola aset tetap perusahaan dari awal sampai akhir: register
dengan label QR, serah terima ke karyawan, mutasi antar lokasi, maintenance, stock
opname, disposal, dan penyusutan garis lurus. Setiap langkah punya alur persetujuan
dan empat level akses, mulai dari staf yang hanya melihat aset yang dipegangnya
sampai manager yang menyetujui disposal.

Modul berjalan di **Odoo Community** dan hanya membutuhkan `hr` dan `mail`. Modul
`account_asset` milik Enterprise tidak diperlukan.

## Fitur

| Area | Fungsi |
| --- | --- |
| **Register** | Kode aset dari prefix kategori (`IT-00001`), kategori, lokasi bertingkat (kantor pusat › lantai, toko, gudang), departemen, pemegang, merk/model/serial, kondisi, foto, catatan, chatter. |
| **Label QR** | Setiap aset punya QR berisi kodenya; cetak label tiga per baris dari form atau daftar aset. |
| **Serah terima** | Karyawan meminta aset yang tersedia → atasannya menyetujui → officer menyerahkan → karyawan minta mengembalikan → officer menerima dan mencatat kondisinya. Bisa mencetak berita acara serah terima. |
| **Mutasi** | Memindahkan satu atau beberapa aset ke lokasi lain (dan bila perlu departemen lain) setelah disetujui. |
| **Maintenance** | Staf melaporkan kerusakan (corrective); officer menjadwalkan, mengerjakan dan menutupnya beserta vendor dan biaya, serta merencanakan maintenance preventive berulang yang menjadwalkan dirinya sendiri. Ada tampilan kalender. |
| **Stock opname** | Memuat semua aset yang tercatat di suatu lokasi, menandai tiap aset ditemukan / tidak ditemukan / rusak, lalu validasi untuk memperbarui kondisi (aset yang tidak ditemukan menjadi *Lost*). Hasilnya bisa dicetak. |
| **Disposal** | Menjual, membuang atau menghibahkan aset setelah disetujui manager; nilai buku dibekukan, laba/rugi dihitung, sisa jadwal penyusutan ditutup. |
| **Penyusutan** | Jadwal garis lurus bulanan sampai nilai residu; job harian memposting baris yang sudah jatuh tempo, dan nilai buku mengikutinya. |

## Instalasi

Folder modul harus bernama `odoo_asset_management`. Clone langsung ke folder yang
ada di `addons_path`:

```bash
cd /path/ke/addons
git clone https://github.com/fadjardev/odoo_asset_management.git odoo_asset_management
```

Lalu di Odoo:

1. Aktifkan mode developer (*Settings › Activate the developer mode*).
2. *Apps › Update Apps List*.
3. Cari **Asset Management**, klik **Activate**.

Atau lewat command line:

```bash
odoo -c /etc/odoo/odoo.conf -d <database> -i odoo_asset_management --stop-after-init
```

### Dengan Docker (image resmi `odoo:19.0`)

Mount folder addons ke `/mnt/extra-addons`, clone modul ke dalamnya, lalu instal
lewat proses Odoo kedua. Beri proses itu port sendiri karena server yang sedang
berjalan sudah memakai 8069 dan 8072:

```bash
docker exec odoo-app odoo -c /etc/odoo/odoo.conf -d <database> \
    -i odoo_asset_management --stop-after-init --http-port=8299 --gevent-port=8298
docker restart odoo-app
```

## Konfigurasi

1. **Beri level ke tiap user.** *Settings › Users*, buka user, lalu di bagian
   **Asset Management** pilih User, Approver, Officer atau Manager. Administrator
   otomatis menjadi Manager setelah instalasi.
2. **Hubungkan user dengan karyawan.** Persetujuan mengikuti struktur HR:
   departemen karyawan (dan kepala departemennya) serta atasan langsung karyawan.
   User tanpa data karyawan tidak bisa mengajukan serah terima.
3. **Kategori** (*Assets › Configuration › Categories*): kode kategori menjadi
   prefix kode aset; atur metode penyusutan dan umur ekonomis bawaannya.
4. **Lokasi** (*Assets › Configuration › Locations*): boleh bertingkat sedalam apa
   pun. Pencarian dan stock opname di suatu lokasi ikut mencakup semua sub-lokasinya.

## Level akses

Setiap level mendapat semua hak level di bawahnya.

| Fitur | User | Approver | Officer | Manager |
| --- | --- | --- | --- | --- |
| **Aset**: melihat | yang dipegangnya, plus semua yang *Available* | + aset departemennya dan bawahan langsungnya | semua | semua |
| Aset: mendaftarkan, mengubah | – | – | ✓ | ✓ |
| Aset: menghapus | – | – | – | ✓ |
| Nilai aset (harga, nilai buku, penyusutan) | tersembunyi | tersembunyi | ✓ | ✓ |
| Cetak label QR | ✓ | ✓ | ✓ | ✓ |
| **Serah terima**: meminta untuk diri sendiri, minta mengembalikan | ✓ | ✓ | ✓ | ✓ |
| Serah terima: menyetujui / menolak | – | untuk departemennya dan bawahan langsungnya | semua | semua |
| Serah terima: menyerahkan, menerima pengembalian | – | – | ✓ | ✓ |
| **Mutasi**: melihat | – | yang menyangkut aset departemennya | semua | semua |
| Mutasi: membuat, mengajukan, menandai selesai | – | – | ✓ | ✓ |
| Mutasi: menyetujui | – | untuk aset departemennya | semua | semua |
| **Maintenance**: melaporkan kerusakan | pada aset yang bisa dilihatnya | sama | ✓ | ✓ |
| Maintenance: melihat laporan | miliknya, dan yang menyangkut aset yang dipegangnya | + yang menyangkut aset departemennya | semua | semua |
| Maintenance: menjadwalkan, mengerjakan, menutup; rencana preventive; vendor dan biaya | – | – | ✓ | ✓ |
| **Stock opname** | – | – | ✓ | ✓ |
| **Disposal**: mengajukan, melaksanakan | – | – | ✓ | ✓ |
| Disposal: menyetujui | – | – | – | ✓ |
| **Penyusutan**: melihat jadwal | – | – | ✓ | ✓ |
| Penyusutan: menghitung jadwal | – | – | – | ✓ |
| **Konfigurasi** (kategori, lokasi) | – | – | – | ✓ |

**Siapa menjadi approver untuk apa.** "Departemennya" berarti setiap departemen
yang dikepalai user (*Employees › Departments › Manager*) beserta semua departemen
di bawahnya. Untuk serah terima, approver-nya adalah atasan *karyawan yang
meminta*; untuk mutasi, atasan dari aset yang dipindahkan. Kepala departemen paling
atas menjadi approver untuk seluruh perusahaan, sedangkan team lead yang tidak
mengepalai departemen hanya menyetujui untuk bawahan langsungnya.

Aturan ini ditegakkan di server, bukan sekadar menyembunyikan tombol:

- Record rule membatasi data yang bisa dibaca tiap level.
- Setiap aksi alur kerja memeriksa level sebelum berjalan.
- Field `state` tidak bisa ditulis langsung, termasuk lewat RPC. Status hanya
  berpindah lewat tombol aksi.
- Field nilai memakai group di level field, sehingga staf tidak bisa membacanya
  bahkan lewat API.

## Alur kerja

### Status aset

Status aset hanya berubah lewat dokumen di sekitarnya: serah terima membuatnya
dipakai, order maintenance mengeluarkannya dari layanan lalu mengembalikannya ke
status semula, dan disposal yang disetujui mengeluarkannya dari register.
Diagram memakai istilah status berbahasa Inggris, sama seperti di aplikasi.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/asset-status-dark.svg">
  <img alt="Lifecycle status aset: Draft, Available, In Use, Under Maintenance dan Disposed, beserta dokumen pemicu tiap transisi" src="docs/images/asset-status-light.svg">
</picture>

### Serah terima

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/asset-handover-dark.svg">
  <img alt="Alur serah terima antara karyawan, approver, asset officer dan register aset" src="docs/images/asset-handover-light.svg">
</picture>

### Dokumen lainnya

| Dokumen | Langkah | Siapa yang menjalankan |
| --- | --- | --- |
| Mutasi | Draft → Waiting Approval → Approved → Done, atau Cancelled sebelum Done | officer membuat, mengajukan dan menandai selesai; approver aset terkait (atau officer) menyetujui |
| Maintenance | Requested → Scheduled → In Progress → Done, atau Cancelled | siapa pun melaporkan kerusakan; officer menjadwalkan, memulai dan menutup; preventive yang selesai menjadwalkan kunjungan berikutnya |
| Stock opname | Draft → Counting → Validated, atau Cancelled | officer |
| Disposal | Draft → Waiting Approval → Approved → Done, atau Cancelled | officer mengajukan dan melaksanakan; manager menyetujui |

## Laporan

| Laporan | Dari |
| --- | --- |
| Label QR | Aset (tombol di form, atau *Print* pada pilihan di daftar) |
| Berita Acara Serah Terima | Serah terima, setelah diserahkan |
| Hasil Stock Opname | Stock opname, saat penghitungan atau setelah validasi |

## Scheduled action

| Job | Jadwal | Fungsi |
| --- | --- | --- |
| Assets: post due depreciation | harian | memposting setiap baris jadwal yang bertanggal hari ini atau sebelumnya |
| Assets: schedule next preventive maintenance | harian | membuat jadwal berikutnya untuk maintenance preventive selesai yang belum punya jadwal lanjutan |

## Gambaran teknis

| Model | Fungsi |
| --- | --- |
| `asset.asset` | register aset |
| `asset.category` | prefix kode, bawaan penyusutan |
| `asset.location` | lokasi bertingkat (`parent_path`) |
| `asset.depreciation.line` | jadwal penyusutan bulanan |
| `asset.assignment` | serah terima |
| `asset.transfer` | mutasi |
| `asset.maintenance` | maintenance corrective dan preventive |
| `asset.audit`, `asset.audit.line` | stock opname |
| `asset.disposal` | disposal |
| `asset.workflow.mixin` | mengunci `state` di balik method aksi |

```
odoo_asset_management/
├── data/        sequence, scheduled action
├── docs/        diagram README (images/) dan sumber Archify-nya (diagrams/)
├── models/      model-model di atas
├── report/      label QR, berita acara, hasil opname
├── security/    group, hak akses, record rule
├── static/      ikon aplikasi
├── tests/       test alur kerja dan hak akses
└── views/       view list, form, kanban, kalender, search, dan menu
```

### Menjalankan test

```bash
odoo -c /etc/odoo/odoo.conf -d <database-test> -i odoo_asset_management \
    --test-tags /odoo_asset_management --stop-after-init
```

Ke-20 test mencakup setiap alur kerja dan matriks akses di atas. Test memakai
record-nya sendiri, jadi tetap lulus di database yang sudah berisi data.

## Kebutuhan

- Odoo 19.0 (Community atau Enterprise)
- Modul: `hr`, `mail`
- `wkhtmltopdf` untuk laporan PDF (sudah ada di image Docker resmi Odoo)

## Lisensi

[LGPL-3](LICENSE). Riwayat rilis ada di [CHANGELOG.md](CHANGELOG.md).
