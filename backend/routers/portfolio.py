"""
Portfolio / Dashboard router — provides data for the main dashboard.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, case, asc, desc
from datetime import datetime, timedelta
from io import StringIO
import csv

from database import get_db
from models import Portofolio, Saldo
from auth import get_current_user, log_activity

router = APIRouter(prefix="/api/portfolio", tags=["Portfolio"])


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db), user=Depends(get_current_user)):
    user_id = user.id

    # Get all transactions
    all_trx = (
        db.query(Portofolio)
        .filter(Portofolio.user_id == user_id)
        .order_by(desc(Portofolio.tanggal_beli), desc(Portofolio.id))
        .all()
    )

    # Build asset-grouped transactions for holding duration calc (ordered by date ASC)
    from collections import defaultdict
    asset_trx_map = defaultdict(list)
    for t in sorted(all_trx, key=lambda x: (x.tanggal_beli, x.id)):
        asset_trx_map[t.nama_aset].append(t)

    def _calc_holding_duration(sell_trx):
        """Calculate holding duration from first BUY in active cycle to this SELL."""
        trxs = asset_trx_map.get(sell_trx.nama_aset, [])
        # Find cycle start (same logic as P/L calculation)
        net_position = 0.0
        idx_start = 0
        for i, trx in enumerate(trxs):
            if trx.id == sell_trx.id:
                break  # Stop before current sell
            if trx.jenis_transaksi == "BELI":
                net_position += float(trx.jumlah)
            else:
                net_position -= float(trx.jumlah)
            if abs(net_position) < 1e-9:
                idx_start = i + 1

        # Find earliest BUY in active cycle
        first_buy = None
        for trx in trxs[idx_start:]:
            if trx.id == sell_trx.id:
                break
            if trx.jenis_transaksi == "BELI":
                first_buy = trx
                break

        if not first_buy:
            return None

        # Build datetime for both
        buy_dt = datetime.combine(first_buy.tanggal_beli,
                                  first_buy.waktu_transaksi or datetime.min.time())
        sell_dt = datetime.combine(sell_trx.tanggal_beli,
                                   sell_trx.waktu_transaksi or datetime.min.time())
        delta = sell_dt - buy_dt
        if delta.total_seconds() < 0:
            return None

        total_seconds = int(delta.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0 and days == 0:
            parts.append(f"{minutes}m")
        return " ".join(parts) if parts else "<1m"

    portofolio = []
    for t in all_trx:
        waktu_str = str(t.waktu_transaksi)[:5] if t.waktu_transaksi else None
        holding_duration = None
        if t.jenis_transaksi == "JUAL":
            holding_duration = _calc_holding_duration(t)

        portofolio.append({
            "id": t.id, "nama_aset": t.nama_aset, "jumlah": float(t.jumlah),
            "harga_beli": float(t.harga_beli), "tanggal_beli": str(t.tanggal_beli),
            "waktu_transaksi": waktu_str,
            "holding_duration": holding_duration,
            "fee": float(t.fee), "jenis_transaksi": t.jenis_transaksi,
            "profit_loss": float(t.profit_loss or 0), "strategy": t.strategy,
            "kategori": t.kategori,
        })

    all_tickers = sorted(set(t["nama_aset"] for t in portofolio))

    # Raw JUAL for client-side chart
    raw_jual_trx = sorted(
        [{"date": t["tanggal_beli"], "ticker": t["nama_aset"], "pnl": t["profit_loss"], "strategy": t["strategy"] or ""}
         for t in portofolio if t["jenis_transaksi"] == "JUAL"],
        key=lambda x: x["date"],
    )

    # Saldo
    saldo_row = db.query(Saldo).filter(Saldo.user_id == user_id).first()
    saldo_data = float(saldo_row.total) if saldo_row else 0
    referensi_data = float(saldo_row.referensi) if saldo_row else 0

    # Chart data: cumulative realized P/L
    chart_query = (
        db.query(Portofolio.tanggal_beli, func.sum(Portofolio.profit_loss))
        .filter(Portofolio.jenis_transaksi == "JUAL", Portofolio.user_id == user_id)
        .group_by(Portofolio.tanggal_beli)
        .order_by(asc(Portofolio.tanggal_beli))
        .all()
    )
    label_tanggal = []
    data_investasi = []
    running_pnl = 0.0
    for row in chart_query:
        label_tanggal.append(str(row[0]))
        running_pnl += float(row[1] or 0)
        data_investasi.append(running_pnl)

    # Total realized P/L
    total_realized_pnl = float(
        db.query(func.coalesce(func.sum(Portofolio.profit_loss), 0))
        .filter(Portofolio.jenis_transaksi == "JUAL", Portofolio.user_id == user_id)
        .scalar()
    )

    # Portfolio growth
    res = db.query(
        func.coalesce(func.sum(case(
            (Portofolio.jenis_transaksi == "BELI", (Portofolio.jumlah * Portofolio.harga_beli) + Portofolio.fee),
            else_=0
        )), 0),
        func.coalesce(func.sum(case(
            (Portofolio.jenis_transaksi == "JUAL", (Portofolio.jumlah * Portofolio.harga_beli) - Portofolio.fee),
            else_=0
        )), 0),
    ).filter(Portofolio.user_id == user_id).first()

    total_beli = float(res[0])
    total_jual = float(res[1])
    modal_disetor = saldo_data + total_beli - total_jual
    pertumbuhan_persen = (total_realized_pnl / modal_disetor * 100) if modal_disetor > 0 else 0

    return {
        "saldo": saldo_data,
        "referensi": referensi_data,
        "total_realized_pnl": total_realized_pnl,
        "modal_disetor": round(modal_disetor, 2),
        "pertumbuhan_persen": round(pertumbuhan_persen, 2),
        "label_tanggal": label_tanggal,
        "data_investasi": data_investasi,
        "portofolio": portofolio,
        "all_tickers": all_tickers,
        "raw_jual_trx": raw_jual_trx,
        "username": user.username,
        "is_admin": user.is_admin or False,
        "today": str(datetime.now().date()),
    }


@router.post("/topup")
def topup_modal(jumlah_tambah: float, request: Request,
                db: Session = Depends(get_db), user=Depends(get_current_user)):
    user_id = user.id
    saldo = db.query(Saldo).filter(Saldo.user_id == user_id).first()
    if not saldo:
        raise HTTPException(status_code=400, detail="Saldo belum diinisialisasi.")

    saldo_saat_ini = float(saldo.total)
    saldo_referensi = float(saldo.referensi)

    if saldo_referensi > 0 and saldo_saat_ini > (0.75 * saldo_referensi):
        batas = 0.75 * saldo_referensi
        raise HTTPException(
            status_code=400,
            detail=f"Saldo belum turun > 25%. Batas top-up: Rp {batas:,.2f}",
        )

    total_baru = saldo_saat_ini + jumlah_tambah
    saldo.total = total_baru
    saldo.referensi = total_baru
    db.commit()

    log_activity(db, user_id, user.username, "ADD_CAPITAL",
                 f"Tambah modal Rp {jumlah_tambah:,.2f} → Total: Rp {total_baru:,.2f}",
                 request.client.host)

    return {"message": f"Modal diperbarui menjadi Rp {total_baru:,.2f}.", "saldo": total_baru}


@router.get("/report/{rentang_waktu}")
def download_report(rentang_waktu: str, request: Request,
                    db: Session = Depends(get_db), user=Depends(get_current_user)):
    user_id = user.id
    hari_ini = datetime.now().date()
    if rentang_waktu == "mingguan":
        tanggal_mulai = hari_ini - timedelta(days=7)
    else:
        tanggal_mulai = hari_ini - timedelta(days=30)

    rows = (
        db.query(Portofolio)
        .filter(Portofolio.tanggal_beli >= tanggal_mulai, Portofolio.user_id == user_id)
        .order_by(desc(Portofolio.tanggal_beli))
        .all()
    )

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["REPORT PERFORMA TRADING", rentang_waktu.upper()])
    cw.writerow(["Tipe", "Nama Aset", "Jumlah", "Harga (Rp)", "Fee (Rp)", "Nilai Bersih (Rp)", "Tanggal"])
    for r in rows:
        nilai = float(r.jumlah) * float(r.harga_beli)
        cw.writerow([r.jenis_transaksi, r.nama_aset, float(r.jumlah), float(r.harga_beli), float(r.fee), nilai, str(r.tanggal_beli)])

    log_activity(db, user_id, user.username, "DOWNLOAD_REPORT",
                 f"Download report {rentang_waktu} ({len(rows)} transaksi)",
                 request.client.host)

    return StreamingResponse(
        iter([si.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=report_{rentang_waktu}.csv"},
    )
