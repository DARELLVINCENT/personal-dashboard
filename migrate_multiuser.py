"""
Script migrasi database untuk menambahkan dukungan multi-user.
- Membuat tabel 'users'
- Menambah kolom 'user_id' ke tabel 'portofolio' dan 'saldo'
- Insert user DRV1 dan DRV2
- Assign data existing ke DRV1
- Buat saldo untuk DRV2 (kosong)

Jalankan sekali saja: python migrate_multiuser.py
"""

import psycopg2
from werkzeug.security import generate_password_hash

def migrate():
    conn = psycopg2.connect(
        host="localhost",
        database="jurnal_db",
        user="postgres",
        password="postgres"
    )
    cur = conn.cursor()
    
    print("=== Migrasi Multi-User Dimulai ===\n")
    
    # 1. Buat tabel users
    print("[1/6] Membuat tabel 'users'...")
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(256) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()
    print("      [OK] Tabel 'users' berhasil dibuat.")
    
    # 2. Insert users DRV1 dan DRV2
    print("[2/6] Menambahkan user DRV1 dan DRV2...")
    cur.execute("SELECT COUNT(*) FROM users WHERE username = 'DRV1';")
    if cur.fetchone()[0] == 0:
        hash_pw = generate_password_hash('1404')
        cur.execute("INSERT INTO users (id, username, password_hash) VALUES (1, 'DRV1', %s);", (hash_pw,))
        print("      [OK] User DRV1 ditambahkan.")
    else:
        print("      [SKIP]  User DRV1 sudah ada, skip.")
    
    cur.execute("SELECT COUNT(*) FROM users WHERE username = 'DRV2';")
    if cur.fetchone()[0] == 0:
        hash_pw = generate_password_hash('1404')
        cur.execute("INSERT INTO users (id, username, password_hash) VALUES (2, 'DRV2', %s);", (hash_pw,))
        print("      [OK] User DRV2 ditambahkan.")
    else:
        print("      [SKIP]  User DRV2 sudah ada, skip.")
    conn.commit()
    
    # 3. Tambah kolom user_id ke tabel portofolio
    print("[3/6] Menambah kolom 'user_id' ke tabel 'portofolio'...")
    cur.execute('''
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'portofolio' AND column_name = 'user_id';
    ''')
    if cur.fetchone() is None:
        cur.execute('ALTER TABLE portofolio ADD COLUMN user_id INTEGER REFERENCES users(id);')
        # Set semua data existing ke user DRV1 (id=1)
        cur.execute('UPDATE portofolio SET user_id = 1 WHERE user_id IS NULL;')
        # Set NOT NULL setelah data di-update
        cur.execute('ALTER TABLE portofolio ALTER COLUMN user_id SET NOT NULL;')
        conn.commit()
        print("      [OK] Kolom 'user_id' ditambahkan ke 'portofolio'. Data existing -> DRV1.")
    else:
        print("      [SKIP]  Kolom 'user_id' sudah ada di 'portofolio', skip.")
    
    # 4. Tambah kolom user_id ke tabel saldo
    print("[4/6] Menambah kolom 'user_id' ke tabel 'saldo'...")
    cur.execute('''
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'saldo' AND column_name = 'user_id';
    ''')
    if cur.fetchone() is None:
        cur.execute('ALTER TABLE saldo ADD COLUMN user_id INTEGER REFERENCES users(id);')
        # Set saldo existing ke DRV1
        cur.execute('UPDATE saldo SET user_id = 1 WHERE user_id IS NULL;')
        cur.execute('ALTER TABLE saldo ALTER COLUMN user_id SET NOT NULL;')
        conn.commit()
        print("      [OK] Kolom 'user_id' ditambahkan ke 'saldo'. Data existing -> DRV1.")
    else:
        print("      [SKIP]  Kolom 'user_id' sudah ada di 'saldo', skip.")
    
    # 5. Buat saldo untuk DRV2 (akun kosong)
    print("[5/6] Membuat saldo awal untuk DRV2...")
    cur.execute("SELECT COUNT(*) FROM saldo WHERE user_id = 2;")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO saldo (total, referensi, user_id) VALUES (0, 0, 2);")
        conn.commit()
        print("      [OK] Saldo DRV2 dibuat (Rp 0).")
    else:
        print("      [SKIP]  Saldo DRV2 sudah ada, skip.")
    
    # 6. Buat index untuk performa query
    print("[6/6] Membuat index pada kolom user_id...")
    cur.execute('''
        SELECT indexname FROM pg_indexes 
        WHERE tablename = 'portofolio' AND indexname = 'idx_portofolio_user_id';
    ''')
    if cur.fetchone() is None:
        cur.execute('CREATE INDEX idx_portofolio_user_id ON portofolio(user_id);')
        conn.commit()
        print("      [OK] Index dibuat.")
    else:
        print("      [SKIP]  Index sudah ada, skip.")
    
    cur.close()
    conn.close()
    print("\n=== [OK] Migrasi Selesai! ===")
    print("User DRV1 -> data portofolio existing")
    print("User DRV2 -> akun kosong (saldo Rp 0)")

if __name__ == '__main__':
    migrate()
