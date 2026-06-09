# Panduan Menjalankan Aplikasi Portfolio Tracker

Aplikasi ini terdiri dari dua bagian utama:
1. **Backend**: FastAPI (Python)
2. **Frontend**: Next.js (React / Node.js)

Berikut adalah panduan langkah demi langkah untuk menjalankan aplikasi ini secara lokal di Windows (PowerShell/Command Prompt).

> [!IMPORTANT]
> Pastikan Anda menjalankan perintah-perintah ini dari root folder proyek (`d:\Project Python\integrasiapp`).

---

## 1. Menjalankan Backend (FastAPI)

Backend aplikasi menggunakan Python dan FastAPI. Anda perlu mengaktifkan virtual environment terlebih dahulu.

1. Buka terminal (PowerShell atau Command Prompt).
2. Arahkan ke folder proyek:
   ```bash
   cd "d:\Project Python\integrasiapp"
   ```
3. Aktifkan virtual environment:
   ```bash
   .\env\Scripts\activate
   ```
   *(Setelah diaktifkan, biasanya akan muncul teks `(env)` di sebelah kiri prompt Anda).*
4. Pindah ke direktori backend:
   ```bash
   cd backend
   ```
5. *(Opsional)* Jika baru pertama kali dan database belum diinisialisasi, jalankan:
   ```bash
   python init_db.py
   ```
6. Jalankan server FastAPI:
   ```bash
   python main.py
   ```
   Server backend akan berjalan di `http://localhost:8000`.

---

## 2. Menjalankan Frontend (Next.js)

Frontend aplikasi dibangun dengan Next.js. Sebaiknya buka **terminal / jendela PowerShell baru** agar backend tetap berjalan.

1. Buka terminal baru.
2. Arahkan ke folder proyek dan masuk ke direktori frontend:
   ```bash
   cd "d:\Project Python\integrasiapp\frontend"
   ```
3. *(Opsional)* Jika Anda baru pertama kali menjalankan proyek di mesin baru atau belum menginstal dependensi (package node_modules), jalankan:
   ```bash
   npm install
   ```
4. Jalankan server pengembangan Next.js:
   ```bash
   npm run dev
   ```
   Server frontend akan berjalan di `http://localhost:3000`.

---

## 3. Mengakses Aplikasi

Setelah kedua server (Backend dan Frontend) berjalan tanpa error, buka browser Anda dan kunjungi:

**[http://localhost:3000](http://localhost:3000)**

> [!TIP]
> Anda dapat login menggunakan akun yang sudah tersedia:
> - **Username**: `DRV1` / `DRV2` / `DRV3` / `CAPITAL1` / `AKUNTEST`
> - **Password**: Sesuai dengan yang terdaftar (contoh: `drv1pass` atau `testpass` untuk `AKUNTEST`)

### Referensi Endpoint
- **Aplikasi Web**: [http://localhost:3000](http://localhost:3000)
- **API Documentation (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Endpoint Utama**: `http://localhost:8000/api/`
