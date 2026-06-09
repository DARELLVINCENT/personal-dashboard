"""
Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel
from typing import Optional
from datetime import date


# ── Auth ──────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    user_id: int
    is_admin: bool

class UserInfo(BaseModel):
    id: int
    username: str
    is_admin: bool


# ── Transactions ──────────────────────────────────────────────────────────────
class TransactionCreate(BaseModel):
    nama_aset: str
    jumlah: float
    harga_beli: float
    fee_persen: float
    tanggal_beli: Optional[str] = None
    waktu_transaksi: Optional[str] = None  # format "HH:MM"
    jenis_transaksi: str  # BELI or JUAL
    strategy: Optional[str] = None
    kategori: str = "Saham"

class TransactionUpdate(BaseModel):
    nama_aset: str
    jumlah: float
    harga_beli: float
    fee_persen: float
    tanggal_beli: Optional[str] = None
    waktu_transaksi: Optional[str] = None  # format "HH:MM"
    jenis_transaksi: str
    strategy: Optional[str] = None
    kategori: str = "Saham"

class TransactionOut(BaseModel):
    id: int
    nama_aset: str
    jumlah: float
    harga_beli: float
    tanggal_beli: str
    waktu_transaksi: Optional[str]
    fee: float
    jenis_transaksi: str
    profit_loss: float
    strategy: Optional[str]
    kategori: str

    class Config:
        from_attributes = True


# ── Portfolio / Dashboard ─────────────────────────────────────────────────────
class TopUpRequest(BaseModel):
    jumlah_tambah: float

class DashboardResponse(BaseModel):
    saldo: float
    referensi: float
    total_realized_pnl: float
    modal_disetor: float
    pertumbuhan_persen: float
    label_tanggal: list
    data_investasi: list
    portofolio: list
    all_tickers: list
    raw_jual_trx: list
    username: str
    is_admin: bool
    today: str
