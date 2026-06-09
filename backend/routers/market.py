"""
Market data + CSV import router.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import asc
from io import StringIO
from datetime import datetime
import pandas as pd

from database import get_db
from models import Portofolio, Saldo
from auth import get_current_user, log_activity

router = APIRouter(prefix="/api/market", tags=["Market"])


def clean_numeric(val):
    if pd.isna(val) or val == '':
        return 0.0
    val_str = str(val).strip().replace('Rp', '').replace('$', '').replace(' ', '')
    if ',' in val_str and '.' in val_str:
        if val_str.rfind(',') > val_str.rfind('.'):
            val_str = val_str.replace('.', '').replace(',', '.')
        else:
            val_str = val_str.replace(',', '')
    elif ',' in val_str:
        parts = val_str.split(',')
        if len(parts[-1]) == 2:
            val_str = val_str.replace(',', '.')
        else:
            val_str = val_str.replace(',', '')
    try:
        return float(val_str)
    except ValueError:
        return 0.0


def parse_date(date_str):
    date_str = str(date_str).strip()
    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d', '%Y-%m-%d %H:%M:%S']:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return datetime.now().date()


def _calc_pnl(db, user_id, nama_aset, jumlah, harga_jual, fee_jual):
    trxs = db.query(Portofolio).filter(
        Portofolio.nama_aset == nama_aset, Portofolio.user_id == user_id
    ).order_by(asc(Portofolio.tanggal_beli), asc(Portofolio.id)).all()

    net, idx = 0.0, 0
    for i, t in enumerate(trxs):
        net += float(t.jumlah) if t.jenis_transaksi == 'BELI' else -float(t.jumlah)
        if abs(net) < 1e-9:
            idx = i + 1

    cq, cc = 0.0, 0.0
    for t in trxs[idx:]:
        if t.jenis_transaksi == 'BELI':
            cq += float(t.jumlah)
            cc += (float(t.jumlah) * float(t.harga_beli)) + float(t.fee)

    avg = cc / cq if cq > 0 else 0
    return (jumlah * harga_jual) - fee_jual - (jumlah * avg)


@router.post("/download_yfinance")
def download_yfinance(ticker: str = Form(...), timeframe: str = Form(...), period: str = Form(...)):
    import yfinance as yf
    try:
        stock = yf.Ticker(ticker.upper())
        df = stock.history(period=period, interval=timeframe)
        if df.empty:
            raise HTTPException(status_code=404, detail=f"Data tidak ditemukan untuk {ticker}")
        si = StringIO()
        df.to_csv(si)
        return StreamingResponse(
            iter([si.getvalue()]), media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={ticker}_{timeframe}_{period}.csv"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import_csv")
async def import_csv(
    broker: str = Form("standard"), file: UploadFile = File(...),
    request: Request = None, db: Session = Depends(get_db), user=Depends(get_current_user),
):
    user_id = user.id
    content = await file.read()
    stream = StringIO(content.decode('utf-8', errors='ignore'))
    sample = stream.read(2048)
    stream.seek(0)
    delimiter = ';' if ';' in sample else ','
    df = pd.read_csv(stream, sep=delimiter)
    if df.empty:
        raise HTTPException(status_code=400, detail="File CSV kosong.")
    df.columns = [c.strip() for c in df.columns]

    records = []
    for _, row in df.iterrows():
        dc = next((c for c in df.columns if c.lower() in ['tanggal', 'date', 'time']), None)
        tc = next((c for c in df.columns if c.lower() in ['saham', 'ticker', 'symbol', 'asset', 'nama_aset']), None)
        tyc = next((c for c in df.columns if c.lower() in ['tipe', 'type', 'jenis', 'action', 'jenis_transaksi', 'b/s']), None)
        qc = next((c for c in df.columns if c.lower() in ['jumlah', 'qty', 'quantity', 'volume', 'lot', 'vol']), None)
        pc = next((c for c in df.columns if c.lower() in ['harga', 'price', 'harga_beli', 'harga beli']), None)
        fc = next((c for c in df.columns if c.lower() in ['fee', 'total fee', 'biaya', 'commission']), None)

        if not all([dc, tc, tyc, qc, pc]):
            continue

        type_val = str(row[tyc]).upper()
        if any(x in type_val for x in ['BUY', 'BELI', 'B']):
            norm_type = 'BELI'
        elif any(x in type_val for x in ['SELL', 'JUAL', 'S']):
            norm_type = 'JUAL'
        else:
            continue

        ticker_val = str(row[tc]).upper().split('.')[0].strip()
        if not ticker_val:
            continue

        qty = clean_numeric(row[qc])
        if qc and 'lot' in qc.lower():
            qty *= 100.0

        records.append({
            'date': parse_date(row[dc]), 'ticker': ticker_val, 'type': norm_type,
            'qty': qty, 'price': clean_numeric(row[pc]),
            'fee': clean_numeric(row[fc]) if fc else 0.0, 'strategy': None})

    if not records:
        raise HTTPException(status_code=400, detail="Tidak ada transaksi valid.")

    records.sort(key=lambda x: x['date'])
    count = 0
    for rec in records:
        saldo = db.query(Saldo).filter(Saldo.user_id == user_id).first()
        cash = float(saldo.total)
        net = rec['qty'] * rec['price']

        if rec['type'] == 'BELI':
            pnl, new_cash = 0.0, cash - (net + rec['fee'])
        else:
            pnl = _calc_pnl(db, user_id, rec['ticker'], rec['qty'], rec['price'], rec['fee'])
            new_cash = cash + (net - rec['fee'])

        db.add(Portofolio(nama_aset=rec['ticker'], jumlah=rec['qty'], harga_beli=rec['price'],
                          fee=rec['fee'], tanggal_beli=rec['date'], jenis_transaksi=rec['type'],
                          profit_loss=pnl, user_id=user_id, strategy=rec['strategy'], kategori='Saham'))
        saldo.total = new_cash
        db.flush()
        count += 1

    db.commit()
    log_activity(db, user_id, user.username, "IMPORT_CSV",
                 f"Import {count} transaksi dari broker {broker.upper()}", request.client.host if request else None)
    return {"message": f"Berhasil mengimpor {count} transaksi.", "count": count}
