from flask import Flask, render_template, request, redirect, flash, make_response, session, url_for
import psycopg2
from datetime import datetime, timedelta
import csv
from io import StringIO
import json
import os
from functools import wraps
from werkzeug.security import check_password_hash
from dotenv import load_dotenv
from market_routes import market_bp

load_dotenv()  # Baca variabel dari file .env

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback_key_ganti_ini')
app.register_blueprint(market_bp)

def get_db_connection():
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'jurnal_db'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '')
    )
    return conn

# === Decorator: Login Required ===
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Silakan login terlebih dahulu.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# === Route: Login ===
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username'].upper()
        password = request.form['password']
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT id, username, password_hash FROM users WHERE username = %s;', (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            flash(f'Selamat datang, {user[1]}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('User ID atau Password salah!', 'error')
            return redirect(url_for('login'))
    
    return render_template('login.html')

# === Route: Logout ===
@app.route('/logout')
def logout():
    session.clear()
    flash('Berhasil logout.', 'success')
    return redirect(url_for('login'))

# === Route: Dashboard Utama ===
@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    conn = get_db_connection()
    cur = conn.cursor()
    user_id = session['user_id']

    if request.method == 'POST':
        nama_aset = request.form['nama_aset'].upper() # Format uppercase agar seragam
        jumlah = float(request.form['jumlah'])
        harga_beli = float(request.form['harga_beli'])
        fee_persen = float(request.form['fee_persen'])
        tanggal_beli = request.form['tanggal_beli']
        jenis_transaksi = request.form['jenis_transaksi'] 
        
        if not tanggal_beli:
            tanggal_beli = str(datetime.now().date())
        
        nilai_bersih = jumlah * harga_beli
        total_fee = nilai_bersih * (fee_persen / 100)
        profit_loss = 0 # Default 0 untuk transaksi BELI
        
        cur.execute('SELECT total FROM saldo WHERE user_id = %s;', (user_id,))
        saldo_saat_ini = float(cur.fetchone()[0])
        
        if jenis_transaksi == 'BELI':
            total_biaya = nilai_bersih + total_fee
            if saldo_saat_ini < total_biaya:
                flash(f'Transaksi Gagal: Modal tidak cukup! Diperlukan Rp {total_biaya:,.2f}', 'error')
                return redirect('/')
            sisa_saldo = saldo_saat_ini - total_biaya
            
        else: # Logika untuk JUAL (Hitung Profit/Rugi dengan Reset After Full Close)
            # 1. Ambil semua transaksi untuk aset ini secara kronologis
            cur.execute('''
                SELECT jumlah, harga_beli, fee, jenis_transaksi 
                FROM portofolio 
                WHERE nama_aset = %s AND user_id = %s
                ORDER BY tanggal_beli ASC, id ASC
            ''', (nama_aset, user_id))
            semua_transaksi = cur.fetchall()
            
            # 2. Cari siklus trading terakhir (setelah posisi terakhir kali = 0)
            #    Setiap kali net position kembali ke 0, siklus baru dimulai
            net_position = 0
            idx_mulai_siklus = 0
            
            for i, trx in enumerate(semua_transaksi):
                trx_jumlah = float(trx[0])
                trx_jenis = trx[3]
                
                if trx_jenis == 'BELI':
                    net_position += trx_jumlah
                else:
                    net_position -= trx_jumlah
                
                # Jika posisi kembali ke 0, siklus berikutnya dimulai setelah ini
                if abs(net_position) < 1e-9:
                    idx_mulai_siklus = i + 1
            
            # 3. Hitung total unit dan modal hanya dari siklus aktif (setelah reset terakhir)
            total_unit_siklus = 0
            total_modal_siklus = 0
            total_unit_jual_siklus = 0
            
            for trx in semua_transaksi[idx_mulai_siklus:]:
                trx_jumlah = float(trx[0])
                trx_harga = float(trx[1])
                trx_fee = float(trx[2])
                trx_jenis = trx[3]
                
                if trx_jenis == 'BELI':
                    total_unit_siklus += trx_jumlah
                    total_modal_siklus += (trx_jumlah * trx_harga) + trx_fee
                else:
                    total_unit_jual_siklus += trx_jumlah
            
            # 4. Net position saat ini dalam siklus
            posisi_bersih = total_unit_siklus - total_unit_jual_siklus
            
            # Validasi jika mencoba menjual barang yang belum dibeli/kurang
            if posisi_bersih < jumlah:
                flash(f'Transaksi Gagal: Anda hanya memiliki {posisi_bersih} unit {nama_aset}!', 'error')
                return redirect('/')
            
            # 5. Hitung harga modal rata-rata (Average Cost Per Unit) dari siklus aktif
            avg_cost = total_modal_siklus / total_unit_siklus if total_unit_siklus > 0 else 0
            modal_untuk_dijual = jumlah * avg_cost # Modal khusus untuk lot yang dijual ini
            
            # 6. Hitung Profit/Loss
            total_pendapatan = nilai_bersih - total_fee
            profit_loss = total_pendapatan - modal_untuk_dijual
            
            sisa_saldo = saldo_saat_ini + total_pendapatan
            
        cur.execute('UPDATE saldo SET total = %s WHERE user_id = %s;', (sisa_saldo, user_id))
        # Menyertakan kolom profit_loss (indeks terakhir)
        cur.execute('''
            INSERT INTO portofolio (nama_aset, jumlah, harga_beli, fee, tanggal_beli, jenis_transaksi, profit_loss, user_id) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (nama_aset, jumlah, harga_beli, total_fee, tanggal_beli, jenis_transaksi, profit_loss, user_id))
        conn.commit()
        
        pesan_sukses = f'Transaksi {jenis_transaksi} berhasil.'
        if jenis_transaksi == 'JUAL':
            status = "PROFIT" if profit_loss > 0 else "RUGI"
            pesan_sukses += f' Realized {status}: Rp {profit_loss:,.2f}'
            
        flash(pesan_sukses, 'success')
        return redirect('/')

    # Ambil Data Portofolio (Pastikan menambahkan profit_loss di query SELECT)
    cur.execute('SELECT id, nama_aset, jumlah, harga_beli, tanggal_beli, fee, jenis_transaksi, profit_loss FROM portofolio WHERE user_id = %s ORDER BY tanggal_beli DESC, id DESC;', (user_id,))
    data_portofolio = cur.fetchall()

    # Ambil Saldo
    cur.execute('SELECT total, referensi FROM saldo WHERE user_id = %s;', (user_id,))
    saldo_row = cur.fetchone()
    saldo_data, referensi_data = float(saldo_row[0]), float(saldo_row[1])

    # LOGIKA GRAFIK: Akumulasi Profit/Loss Realized - hanya dari transaksi JUAL
    cur.execute('''
        SELECT tanggal_beli, SUM(profit_loss) as daily_pnl
        FROM portofolio 
        WHERE jenis_transaksi = 'JUAL' AND user_id = %s
        GROUP BY tanggal_beli 
        ORDER BY tanggal_beli ASC;
    ''', (user_id,))
    data_grafik_mentah = cur.fetchall()
    
    label_tanggal = []
    data_investasi = []
    running_pnl = 0
    
    for row in data_grafik_mentah:
        label_tanggal.append(str(row[0]))
        # Mengakumulasikan profit realized dari waktu ke waktu
        running_pnl += float(row[1] or 0)
        data_investasi.append(running_pnl)

    # Hitung Total Realized Profit/Loss dari semua transaksi JUAL
    cur.execute('''
        SELECT COALESCE(SUM(profit_loss), 0)
        FROM portofolio
        WHERE jenis_transaksi = 'JUAL' AND user_id = %s
    ''', (user_id,))
    total_realized_pnl = float(cur.fetchone()[0])
    
    # Hitung Pertumbuhan Portofolio
    cur.execute('''
        SELECT 
            COALESCE(SUM(CASE WHEN jenis_transaksi = 'BELI' THEN (jumlah * harga_beli) + fee ELSE 0 END), 0) as total_beli,
            COALESCE(SUM(CASE WHEN jenis_transaksi = 'JUAL' THEN (jumlah * harga_beli) - fee ELSE 0 END), 0) as total_jual
        FROM portofolio
        WHERE user_id = %s
    ''', (user_id,))
    res_modal = cur.fetchone()
    total_beli = float(res_modal[0])
    total_jual = float(res_modal[1])
    
    # Total Modal Disertakan (Initial Capital) = Saldo Cash + Total Uang Masuk Aset - Total Uang Keluar dari Aset
    modal_disetor = saldo_data + total_beli - total_jual
    
    if modal_disetor > 0:
        pertumbuhan_persen = (total_realized_pnl / modal_disetor) * 100
    else:
        pertumbuhan_persen = 0
    
    cur.close()
    conn.close()
    
    return render_template('index.html', 
                           portofolio=data_portofolio, 
                           saldo=saldo_data,
                           referensi=referensi_data,
                           label_tanggal=label_tanggal,
                           data_investasi=data_investasi,
                           total_realized_pnl=total_realized_pnl,
                           modal_disetor=modal_disetor,
                           pertumbuhan_persen=pertumbuhan_persen,
                           today=str(datetime.now().date()),
                           username=session['username'])

@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_transaksi(id):
    conn = get_db_connection()
    cur = conn.cursor()
    user_id = session['user_id']
    
    cur.execute('SELECT jumlah, harga_beli, fee, jenis_transaksi FROM portofolio WHERE id = %s AND user_id = %s;', (id, user_id))
    transaksi = cur.fetchone()
    
    if transaksi:
        jumlah, harga, fee, jenis = float(transaksi[0]), float(transaksi[1]), float(transaksi[2]), transaksi[3]
        
        # Logika pembatalan efek saldo
        if jenis == 'BELI':
            total_refund = (jumlah * harga) + fee
            cur.execute('UPDATE saldo SET total = total + %s WHERE user_id = %s;', (total_refund, user_id))
        else: # JUAL
            total_deduct = (jumlah * harga) - fee
            cur.execute('UPDATE saldo SET total = total - %s WHERE user_id = %s;', (total_deduct, user_id))
            
        cur.execute('DELETE FROM portofolio WHERE id = %s AND user_id = %s;', (id, user_id))
        conn.commit()
        flash('Transaksi berhasil dihapus dan saldo disesuaikan!', 'success')
    
    cur.close()
    conn.close()
    return redirect('/')

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_transaksi(id):
    conn = get_db_connection()
    cur = conn.cursor()
    user_id = session['user_id']
    
    if request.method == 'POST':
        nama_aset = request.form['nama_aset']
        jumlah = float(request.form['jumlah'])
        harga_beli = float(request.form['harga_beli'])
        fee_persen = float(request.form['fee_persen'])
        tanggal_beli = request.form['tanggal_beli']
        jenis_transaksi = request.form['jenis_transaksi']
        
        nilai_bersih_baru = jumlah * harga_beli
        total_fee_baru = nilai_bersih_baru * (fee_persen / 100)
        
        # 1. Ambil data lama & saldo asli
        cur.execute('SELECT jumlah, harga_beli, fee, jenis_transaksi FROM portofolio WHERE id = %s AND user_id = %s;', (id, user_id))
        old = cur.fetchone()
        cur.execute('SELECT total FROM saldo WHERE user_id = %s;', (user_id,))
        saldo_saat_ini = float(cur.fetchone()[0])
        
        if old:
            old_jumlah, old_harga, old_fee, old_jenis = float(old[0]), float(old[1]), float(old[2]), old[3]
            
            # 2. Kembalikan saldo ke kondisi SEBELUM transaksi lama terjadi (Simulasi)
            if old_jenis == 'BELI':
                saldo_simulasi = saldo_saat_ini + ((old_jumlah * old_harga) + old_fee)
            else:
                saldo_simulasi = saldo_saat_ini - ((old_jumlah * old_harga) - old_fee)
                
            # 3. Hitung efek dari data transaksi yang baru dimasukkan
            if jenis_transaksi == 'BELI':
                total_biaya_baru = nilai_bersih_baru + total_fee_baru
                if saldo_simulasi < total_biaya_baru:
                    flash('Update Gagal! Saldo simulasi tidak mencukupi untuk tipe BELI baru.', 'error')
                    return redirect('/')
                saldo_final = saldo_simulasi - total_biaya_baru
            else:
                saldo_final = saldo_simulasi + (nilai_bersih_baru - total_fee_baru)
                
            # 4. Simpan ke database
            cur.execute('UPDATE saldo SET total = %s WHERE user_id = %s;', (saldo_final, user_id))
            cur.execute('''
                UPDATE portofolio 
                SET nama_aset = %s, jumlah = %s, harga_beli = %s, fee = %s, tanggal_beli = %s, jenis_transaksi = %s
                WHERE id = %s AND user_id = %s;
            ''', (nama_aset, jumlah, harga_beli, total_fee_baru, tanggal_beli, jenis_transaksi, id, user_id))
            conn.commit()
            flash('Data transaksi berhasil diperbarui!', 'success')
            
        cur.close()
        conn.close()
        return redirect('/')
        
    cur.execute('SELECT id, nama_aset, jumlah, harga_beli, tanggal_beli, fee, jenis_transaksi FROM portofolio WHERE id = %s AND user_id = %s;', (id, user_id))
    item = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('edit.html', item=item)

@app.route('/tambah_modal', methods=['POST'])
@login_required
def tambah_modal():
    tambahan = float(request.form['jumlah_tambah'])
    conn = get_db_connection()
    cur = conn.cursor()
    user_id = session['user_id']
    cur.execute('SELECT total, referensi FROM saldo WHERE user_id = %s;', (user_id,))
    res = cur.fetchone()
    saldo_saat_ini = float(res[0])
    saldo_referensi = float(res[1])
    if saldo_referensi > 0 and saldo_saat_ini > (0.75 * saldo_referensi):
        batas_maksimal_saldo = 0.75 * saldo_referensi
        flash(f'Request Gagal! Saldo belum turun > 25%. Batas top-up: Rp {batas_maksimal_saldo:,.2f}', 'error')
    else:
        total_baru = saldo_saat_ini + tambahan
        cur.execute('UPDATE saldo SET total = %s, referensi = %s WHERE user_id = %s;', (total_baru, total_baru, user_id))
        conn.commit()
        flash(f'Modal diperbarui menjadi Rp {total_baru:,.2f}.', 'success')
    cur.close()
    conn.close()
    return redirect('/')

@app.route('/download_report/<rentang_waktu>')
@login_required
def download_report(rentang_waktu):
    conn = get_db_connection()
    cur = conn.cursor()
    user_id = session['user_id']
    hari_ini = datetime.now().date()
    if rentang_waktu == 'mingguan':
        tanggal_mulai = hari_ini - timedelta(days=7)
    else:
        tanggal_mulai = hari_ini - timedelta(days=30)
        
    cur.execute('''
        SELECT jenis_transaksi, nama_aset, jumlah, harga_beli, fee, 
               (jumlah * harga_beli) AS nilai_bersih, tanggal_beli 
        FROM portofolio 
        WHERE tanggal_beli >= %s AND user_id = %s
        ORDER BY tanggal_beli DESC;
    ''', (tanggal_mulai, user_id))
    rows = cur.fetchall()
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['REPORT PERFORMA TRADING', rentang_waktu.upper()])
    cw.writerow(['Tipe', 'Nama Aset', 'Jumlah', 'Harga (Rp)', 'Fee (Rp)', 'Nilai Bersih (Rp)', 'Tanggal'])
    for row in rows:
        cw.writerow([row[0], row[1], row[2], float(row[3]), float(row[4]), float(row[5]), row[6]])
    cur.close()
    conn.close()
    response = make_response(si.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=report_{rentang_waktu}.csv"
    response.headers["Content-type"] = "text/csv"
    return response

if __name__ == '__main__':
    app.run(debug=True)