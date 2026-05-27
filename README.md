# 📈 Portofolio Tracker

Aplikasi web untuk mencatat dan melacak jurnal trading saham/aset, dibangun dengan **Flask** dan **PostgreSQL**.

## ✨ Fitur

- 🔐 **Multi-User Login** — Setiap akun memiliki data portofolio yang terisolasi
- 📊 **Dashboard Animasi** — Tampilan modern dengan animasi fade-in, counter, dan shimmer
- 💰 **Tracking Saldo Real-time** — Saldo otomatis berkurang/bertambah setiap transaksi
- 📉 **Kalkulasi P/L Realized** — Profit/Loss dihitung otomatis menggunakan rata-rata biaya (Average Cost)
- 📈 **Grafik Akumulasi PnL** — Visualisasi performa trading dari waktu ke waktu
- 📋 **CRUD Transaksi** — Tambah, edit, hapus riwayat transaksi
- ⬇️ **Export CSV** — Download report mingguan/bulanan
- 📡 **Data Pasar** — Cari dan download data historis OHLC via YFinance

## 🚀 Cara Menjalankan

### 1. Clone repository

```bash
git clone https://github.com/username/portofoliotracker.git
cd portofoliotracker
```

### 2. Buat virtual environment & install dependencies

```bash
python -m venv env
env\Scripts\activate       # Windows
# source env/bin/activate  # Linux/Mac

pip install -r requirements.txt
```

### 3. Konfigurasi environment

Salin file `.env.example` menjadi `.env` dan isi nilainya:

```bash
copy .env.example .env
```

Edit `.env`:

```env
SECRET_KEY=buat_secret_key_panjang_dan_acak
DB_HOST=localhost
DB_NAME=nama_database_anda
DB_USER=username_postgres
DB_PASSWORD=password_postgres
```

### 4. Setup Database PostgreSQL

Pastikan PostgreSQL sudah berjalan, lalu jalankan migration:

```bash
python migrate_multiuser.py
```

### 5. Jalankan aplikasi

```bash
python app.py
```

Buka browser: [http://127.0.0.1:5000](http://127.0.0.1:5000)

## 🛠️ Tech Stack

| Layer | Teknologi |
|-------|-----------|
| Backend | Python, Flask |
| Database | PostgreSQL (psycopg2) |
| Frontend | HTML, CSS, JavaScript |
| Charts | Chart.js |
| Market Data | yfinance |
| Auth | Werkzeug (password hashing) |

## ⚠️ Catatan Keamanan

- Jangan pernah commit file `.env` ke repository
- Ganti `SECRET_KEY` dengan string acak yang panjang sebelum deploy ke production
- File `.env` sudah terdaftar di `.gitignore`
