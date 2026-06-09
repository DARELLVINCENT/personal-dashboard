# perlu di taruh di github
"""
SQLAlchemy ORM models — mirrors the existing jurnal_db schema.
"""
from sqlalchemy import Column, Integer, String, Numeric, Date, Time, Boolean, DateTime, ForeignKey, Text, func
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    is_admin = Column(Boolean, default=False)


class Saldo(Base):
    __tablename__ = "saldo"

    id = Column(Integer, primary_key=True, index=True)
    total = Column(Numeric(15, 2), nullable=False, default=0)
    referensi = Column(Numeric(15, 2), nullable=False, default=0)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)


class Portofolio(Base):
    __tablename__ = "portofolio"

    id = Column(Integer, primary_key=True, index=True)
    nama_aset = Column(String(100), nullable=False)
    jumlah = Column(Numeric(10, 2), nullable=False)
    harga_beli = Column(Numeric(15, 2), nullable=False)
    tanggal_beli = Column(Date, server_default=func.current_date())
    fee = Column(Numeric(15, 2), nullable=False, default=0)
    jenis_transaksi = Column(String(10), nullable=False, default="BELI")
    profit_loss = Column(Numeric(15, 2), default=0)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    strategy = Column(String(50), nullable=True)
    kategori = Column(String(50), nullable=False, default="Saham")
    waktu_transaksi = Column(Time, nullable=True)  # jam:menit transaksi


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String(50))
    action = Column(String(50))
    detail = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
