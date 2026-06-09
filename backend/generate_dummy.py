import random
import sys
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from database import SessionLocal
from models import User, Saldo, Portofolio
from auth import get_password_hash

def generate_dummy_data():
    db = SessionLocal()
    try:
        username = "AKUNTEST"
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"Creating user {username}...")
            user = User(
                username=username,
                password_hash=get_password_hash("testpass"),
                is_admin=False
            )
            db.add(user)
            db.flush()
            saldo = Saldo(total=100000000, referensi=100000000, user_id=user.id)
            db.add(saldo)
            db.commit()
            print(f"User {username} created with ID {user.id}")
        else:
            print(f"User {username} already exists with ID {user.id}")

        print("Generating 200 transactions...")
        assets = ["BBCA", "BBRI", "BMRI", "BBNI", "TLKM", "ASII", "GOTO", "AMMN", "ADRO", "UNVR"]
        strategies = ["Scalping", "Swing", "Investasi", "Day Trading"]
        
        start_date = datetime.now() - timedelta(days=365)
        
        for i in range(200):
            asset = random.choice(assets)
            jumlah = random.randint(10, 1000) * 100  # In lots of 100
            harga_beli = random.randint(100, 10000)
            fee = jumlah * harga_beli * 0.0015
            jenis_transaksi = random.choice(["BELI", "JUAL"])
            
            tanggal_beli = start_date + timedelta(days=random.randint(0, 360))
            
            profit_loss = 0
            if jenis_transaksi == "JUAL":
                profit_loss = random.randint(-500000, 1000000)
                
            porto = Portofolio(
                nama_aset=asset,
                jumlah=jumlah,
                harga_beli=harga_beli,
                tanggal_beli=tanggal_beli.date(),
                fee=fee,
                jenis_transaksi=jenis_transaksi,
                profit_loss=profit_loss,
                user_id=user.id,
                strategy=random.choice(strategies),
                kategori="Saham"
            )
            db.add(porto)
            
        db.commit()
        print("Successfully generated 200 transactions for AKUNTEST.")
        
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    generate_dummy_data()
