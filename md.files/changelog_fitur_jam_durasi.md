# Changelog — Fitur Pilih Jam Transaksi & Durasi Holding

**Tanggal:** 4 Juni 2026  
**Deskripsi:** Menambahkan fitur input waktu (jam:menit) pada form transaksi BELI/JUAL dan menghitung durasi holding aset (berapa lama aset dipegang dari pertama kali beli hingga dijual).

---

## File Baru (NEW)

| # | File | Deskripsi |
|---|------|-----------|
| 1 | `backend/migrate_add_waktu.py` | Script migrasi database untuk menambahkan kolom `waktu_transaksi` (TIME) ke tabel `portofolio`. Bersifat idempotent — cek apakah kolom sudah ada sebelum ALTER TABLE. |

---

## File Diubah (MODIFIED)

### Backend

| # | File | Perubahan |
|---|------|-----------|
| 1 | `backend/models.py` | - Tambah import `Time` dari SQLAlchemy<br>- Tambah kolom `waktu_transaksi = Column(Time, nullable=True)` pada model `Portofolio` |
| 2 | `backend/schemas.py` | - Tambah field `waktu_transaksi: Optional[str] = None` pada `TransactionCreate`<br>- Tambah field `waktu_transaksi: Optional[str] = None` pada `TransactionUpdate`<br>- Tambah field `waktu_transaksi: Optional[str]` pada `TransactionOut` |
| 3 | `backend/routers/transactions.py` | - Tambah import `time as dt_time` dari `datetime`<br>- Fungsi `create_transaction`: parse `waktu_transaksi` (string "HH:MM" → `time` object) dan simpan ke database<br>- Fungsi `update_transaction`: parse dan update `waktu_transaksi` pada transaksi yang diedit |
| 4 | `backend/routers/portfolio.py` | - Tambah import `defaultdict`<br>- Tambah fungsi `_calc_holding_duration()`: menghitung durasi holding dari BELI pertama di siklus aktif hingga JUAL<br>- Dashboard response sekarang menyertakan `waktu_transaksi` dan `holding_duration` per transaksi<br>- Format durasi: "3d 5h", "2h 30m", "<1m" |

### Frontend

| # | File | Perubahan |
|---|------|-----------|
| 5 | `frontend/src/app/page.js` | - Tambah field `waktu_transaksi` pada state `form` (default: waktu saat ini HH:MM)<br>- Tambah input `<input type="time">` pada form modal transaksi (label: "Jam Transaksi")<br>- Tambah 2 kolom baru pada tabel riwayat: **Jam** dan **Durasi**<br>- Kolom Jam: tampilkan format "HH:MM" atau "—" jika kosong<br>- Kolom Durasi: tampilkan badge ungu "⏱ 3d 5h" atau "—" jika bukan transaksi JUAL<br>- Update `handleEdit`: load waktu_transaksi yang tersimpan<br>- Update `colSpan` empty state: 10 → 12 |

---

## Database

| Perubahan | Detail |
|-----------|--------|
| Tabel `portofolio` | Kolom baru: `waktu_transaksi TIME NULL` |
| Migrasi | Dijalankan via `python migrate_add_waktu.py` |
| Backward Compatibility | Data lama tetap valid — kolom baru nullable, ditampilkan sebagai "—" |

---

## Logika Perhitungan Durasi Holding

```
1. Saat transaksi JUAL, ambil semua transaksi aset yang sama
2. Cari siklus aktif (reset saat net position = 0)
3. Temukan tanggal + waktu BELI pertama di siklus aktif
4. Durasi = (tanggal_jual + waktu_jual) - (tanggal_beli_pertama + waktu_beli_pertama)
5. Format output: "Xd Yh" (hari + jam), "Xh Ym" (jika < 1 hari), "<1m" (jika sangat singkat)
6. Jika waktu tidak tersedia → gunakan 00:00 sebagai default
```

---

## Cara Penggunaan

1. **Jalankan migrasi** (sekali saja):
   ```bash
   cd backend
   python migrate_add_waktu.py
   ```

2. **Jalankan backend**:
   ```bash
   uvicorn main:app --reload
   ```

3. **Buka dashboard** → klik "Tambah Transaksi" → isi tanggal & **jam transaksi**

4. **Durasi holding** akan otomatis dihitung dan ditampilkan pada transaksi JUAL
