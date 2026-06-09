"""
Transaction CRUD router — includes the cycle-based P/L calculation logic.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import asc
from datetime import datetime, time as dt_time

from database import get_db
from models import Portofolio, Saldo
from schemas import TransactionCreate, TransactionUpdate
from auth import get_current_user, log_activity

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])


@router.get("/position/{nama_aset}")
def get_asset_position(nama_aset: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """
    Returns current net position and average buy cost for an asset in the active cycle.
    Used by the frontend to show reference info when creating a JUAL transaction.
    """
    user_id = user.id
    nama_aset = nama_aset.upper()

    all_trx = (
        db.query(Portofolio)
        .filter(Portofolio.nama_aset == nama_aset, Portofolio.user_id == user_id)
        .order_by(asc(Portofolio.tanggal_beli), asc(Portofolio.id))
        .all()
    )

    if not all_trx:
        return {"nama_aset": nama_aset, "posisi_bersih": 0, "avg_cost_per_unit": 0}

    # Find start of current cycle
    net_position = 0.0
    idx_start = 0
    for i, trx in enumerate(all_trx):
        if trx.jenis_transaksi == "BELI":
            net_position += float(trx.jumlah)
        else:
            net_position -= float(trx.jumlah)
        if abs(net_position) < 1e-9:
            idx_start = i + 1

    # Aggregate active cycle
    total_unit_beli = 0.0
    total_modal = 0.0
    total_unit_jual = 0.0

    for trx in all_trx[idx_start:]:
        qty = float(trx.jumlah)
        price = float(trx.harga_beli)
        fee = float(trx.fee)
        if trx.jenis_transaksi == "BELI":
            total_unit_beli += qty
            total_modal += (qty * price) + fee
        else:
            total_unit_jual += qty

    posisi_bersih = total_unit_beli - total_unit_jual
    avg_cost = total_modal / total_unit_beli if total_unit_beli > 0 else 0

    return {
        "nama_aset": nama_aset,
        "posisi_bersih": posisi_bersih,
        "avg_cost_per_unit": round(avg_cost, 2),
    }


def _calculate_sell_pnl(db: Session, user_id: int, nama_aset: str, jumlah: float,
                        harga_jual: float, fee_jual: float) -> float:
    """
    Cycle-based P/L calculation — identical logic to original app.py.
    Finds the last full-close cycle, computes avg cost from active cycle only.
    """
    all_trx = (
        db.query(Portofolio)
        .filter(Portofolio.nama_aset == nama_aset, Portofolio.user_id == user_id)
        .order_by(asc(Portofolio.tanggal_beli), asc(Portofolio.id))
        .all()
    )

    # Find start of current cycle
    net_position = 0.0
    idx_mulai_siklus = 0
    for i, trx in enumerate(all_trx):
        if trx.jenis_transaksi == "BELI":
            net_position += float(trx.jumlah)
        else:
            net_position -= float(trx.jumlah)
        if abs(net_position) < 1e-9:
            idx_mulai_siklus = i + 1

    # Aggregate active cycle
    total_unit_beli = 0.0
    total_modal = 0.0
    total_unit_jual = 0.0

    for trx in all_trx[idx_mulai_siklus:]:
        qty = float(trx.jumlah)
        price = float(trx.harga_beli)
        fee = float(trx.fee)
        if trx.jenis_transaksi == "BELI":
            total_unit_beli += qty
            total_modal += (qty * price) + fee
        else:
            total_unit_jual += qty

    avg_cost = total_modal / total_unit_beli if total_unit_beli > 0 else 0
    cost_of_sold = jumlah * avg_cost
    revenue = (jumlah * harga_jual) - fee_jual
    return revenue - cost_of_sold


@router.post("")
def create_transaction(data: TransactionCreate, request: Request,
                       db: Session = Depends(get_db), user=Depends(get_current_user)):
    user_id = user.id
    nama_aset = data.nama_aset.upper()
    jumlah = data.jumlah
    harga_beli = data.harga_beli
    fee_persen = data.fee_persen
    tanggal_beli = data.tanggal_beli or str(datetime.now().date())
    jenis_transaksi = data.jenis_transaksi
    strategy = data.strategy or None
    kategori = data.kategori

    # Parse waktu_transaksi ("HH:MM" → time object)
    waktu_obj = None
    if data.waktu_transaksi:
        try:
            parts = data.waktu_transaksi.split(":")
            waktu_obj = dt_time(int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            waktu_obj = None

    nilai_bersih = jumlah * harga_beli
    total_fee = nilai_bersih * (fee_persen / 100)
    profit_loss = 0.0

    saldo = db.query(Saldo).filter(Saldo.user_id == user_id).first()
    if not saldo:
        raise HTTPException(status_code=400, detail="Saldo belum diinisialisasi.")
    saldo_saat_ini = float(saldo.total)

    if jenis_transaksi == "BELI":
        total_biaya = nilai_bersih + total_fee
        if saldo_saat_ini < total_biaya:
            raise HTTPException(
                status_code=400,
                detail=f"Modal tidak cukup! Diperlukan Rp {total_biaya:,.2f}, saldo: Rp {saldo_saat_ini:,.2f}",
            )
        sisa_saldo = saldo_saat_ini - total_biaya
    else:
        # Validate position
        all_trx = (
            db.query(Portofolio)
            .filter(Portofolio.nama_aset == nama_aset, Portofolio.user_id == user_id)
            .order_by(asc(Portofolio.tanggal_beli), asc(Portofolio.id))
            .all()
        )
        # Compute net position using cycle logic
        net_pos = 0.0
        idx_start = 0
        for i, trx in enumerate(all_trx):
            if trx.jenis_transaksi == "BELI":
                net_pos += float(trx.jumlah)
            else:
                net_pos -= float(trx.jumlah)
            if abs(net_pos) < 1e-9:
                idx_start = i + 1

        total_buy = sum(float(t.jumlah) for t in all_trx[idx_start:] if t.jenis_transaksi == "BELI")
        total_sell = sum(float(t.jumlah) for t in all_trx[idx_start:] if t.jenis_transaksi == "JUAL")
        posisi_bersih = total_buy - total_sell

        if posisi_bersih < jumlah:
            raise HTTPException(
                status_code=400,
                detail=f"Anda hanya memiliki {posisi_bersih} unit {nama_aset}!",
            )

        profit_loss = _calculate_sell_pnl(db, user_id, nama_aset, jumlah, harga_beli, total_fee)
        total_pendapatan = nilai_bersih - total_fee
        sisa_saldo = saldo_saat_ini + total_pendapatan

    # Update saldo
    saldo.total = sisa_saldo
    # Insert transaction
    new_trx = Portofolio(
        nama_aset=nama_aset, jumlah=jumlah, harga_beli=harga_beli,
        fee=total_fee, tanggal_beli=tanggal_beli, jenis_transaksi=jenis_transaksi,
        profit_loss=profit_loss, user_id=user_id, strategy=strategy, kategori=kategori,
        waktu_transaksi=waktu_obj,
    )
    db.add(new_trx)
    db.commit()
    db.refresh(new_trx)

    log_activity(db, user_id, user.username, "ADD_TRANSACTION",
                 f"{jenis_transaksi} {nama_aset} {jumlah} lot @ Rp {harga_beli:,.2f} | Fee: Rp {total_fee:,.2f} | Kategori: {kategori}",
                 request.client.host)

    msg = f"Transaksi {jenis_transaksi} berhasil."
    if jenis_transaksi == "JUAL":
        status_pnl = "PROFIT" if profit_loss > 0 else "RUGI"
        msg += f" Realized {status_pnl}: Rp {profit_loss:,.2f}"

    return {"message": msg, "transaction_id": new_trx.id, "profit_loss": float(profit_loss)}


@router.put("/{trx_id}")
def update_transaction(trx_id: int, data: TransactionUpdate, request: Request,
                       db: Session = Depends(get_db), user=Depends(get_current_user)):
    user_id = user.id
    old = db.query(Portofolio).filter(Portofolio.id == trx_id, Portofolio.user_id == user_id).first()
    if not old:
        raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan.")

    saldo = db.query(Saldo).filter(Saldo.user_id == user_id).first()
    saldo_saat_ini = float(saldo.total)

    old_jumlah = float(old.jumlah)
    old_harga = float(old.harga_beli)
    old_fee = float(old.fee)
    old_jenis = old.jenis_transaksi

    # Simulate reversal
    if old_jenis == "BELI":
        saldo_simulasi = saldo_saat_ini + (old_jumlah * old_harga) + old_fee
    else:
        saldo_simulasi = saldo_saat_ini - ((old_jumlah * old_harga) - old_fee)

    nilai_bersih_baru = data.jumlah * data.harga_beli
    total_fee_baru = nilai_bersih_baru * (data.fee_persen / 100)

    if data.jenis_transaksi == "BELI":
        total_biaya_baru = nilai_bersih_baru + total_fee_baru
        if saldo_simulasi < total_biaya_baru:
            raise HTTPException(status_code=400, detail="Saldo simulasi tidak mencukupi.")
        saldo_final = saldo_simulasi - total_biaya_baru
    else:
        saldo_final = saldo_simulasi + (nilai_bersih_baru - total_fee_baru)

    saldo.total = saldo_final
    old.nama_aset = data.nama_aset
    old.jumlah = data.jumlah
    old.harga_beli = data.harga_beli
    old.fee = total_fee_baru
    old.tanggal_beli = data.tanggal_beli or str(datetime.now().date())
    old.jenis_transaksi = data.jenis_transaksi
    old.strategy = data.strategy or None
    old.kategori = data.kategori

    # Parse waktu_transaksi
    if data.waktu_transaksi:
        try:
            parts = data.waktu_transaksi.split(":")
            old.waktu_transaksi = dt_time(int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            old.waktu_transaksi = None
    else:
        old.waktu_transaksi = None

    db.commit()

    log_activity(db, user_id, user.username, "EDIT_TRANSACTION",
                 f"Edit transaksi ID#{trx_id}: {data.jenis_transaksi} {data.nama_aset} {data.jumlah} lot @ Rp {data.harga_beli:,.2f}",
                 request.client.host)

    return {"message": "Data transaksi berhasil diperbarui!"}


@router.delete("/{trx_id}")
def delete_transaction(trx_id: int, request: Request,
                       db: Session = Depends(get_db), user=Depends(get_current_user)):
    user_id = user.id
    trx = db.query(Portofolio).filter(Portofolio.id == trx_id, Portofolio.user_id == user_id).first()
    if not trx:
        raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan.")

    saldo = db.query(Saldo).filter(Saldo.user_id == user_id).first()
    jumlah = float(trx.jumlah)
    harga = float(trx.harga_beli)
    fee = float(trx.fee)

    if trx.jenis_transaksi == "BELI":
        saldo.total = float(saldo.total) + (jumlah * harga) + fee
    else:
        saldo.total = float(saldo.total) - ((jumlah * harga) - fee)

    log_activity(db, user_id, user.username, "DELETE_TRANSACTION",
                 f"Hapus transaksi ID#{trx_id}: {trx.jenis_transaksi} {jumlah} lot @ Rp {harga:,.2f}",
                 request.client.host)

    db.delete(trx)
    db.commit()

    return {"message": "Transaksi berhasil dihapus dan saldo disesuaikan!"}
