"""
Analytics router — KPI scorecard, donut chart, heatmap, top/worst assets.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case, asc, extract
from collections import defaultdict
from datetime import datetime

from database import get_db
from models import Portofolio, Saldo
from auth import get_current_user, log_activity

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

DONUT_COLORS = [
    "#10B981", "#3B82F6", "#F59E0B", "#8B5CF6", "#EF4444",
    "#06B6D4", "#F97316", "#EC4899", "#14B8A6", "#A3E635",
    "#6366F1", "#FB923C", "#2DD4BF", "#FCD34D", "#C084FC",
]


def _compute_active_positions(all_trx):
    """Compute active positions per asset using cycle-reset logic."""
    by_asset = defaultdict(list)
    for t in all_trx:
        by_asset[t.nama_aset].append(t)

    positions = {}
    for nama_aset, trxs in by_asset.items():
        net_position = 0.0
        idx_start = 0
        for i, trx in enumerate(trxs):
            if trx.jenis_transaksi == "BELI":
                net_position += float(trx.jumlah)
            else:
                net_position -= float(trx.jumlah)
            if abs(net_position) < 1e-9:
                idx_start = i + 1

        total_unit_beli = 0.0
        total_modal = 0.0
        total_unit_jual = 0.0
        for trx in trxs[idx_start:]:
            qty = float(trx.jumlah)
            price = float(trx.harga_beli)
            fee = float(trx.fee)
            if trx.jenis_transaksi == "BELI":
                total_unit_beli += qty
                total_modal += (qty * price) + fee
            else:
                total_unit_jual += qty

        net_units = total_unit_beli - total_unit_jual
        if net_units > 1e-9 and total_unit_beli > 0:
            avg_cost = total_modal / total_unit_beli
            positions[nama_aset] = {
                "units": net_units,
                "avg_cost": round(avg_cost, 2),
                "total_value": round(net_units * avg_cost, 2),
            }
    return positions


@router.get("")
def get_analytics(db: Session = Depends(get_db), user=Depends(get_current_user)):
    user_id = user.id
    log_activity(db, user_id, user.username, "VIEW_ANALYTICS", "Melihat halaman Analytics")

    # 1. PORTFOLIO COMPOSITION
    all_trx = (
        db.query(Portofolio).filter(Portofolio.user_id == user_id)
        .order_by(asc(Portofolio.tanggal_beli), asc(Portofolio.id)).all()
    )
    positions = _compute_active_positions(all_trx)

    saldo_row = db.query(Saldo).filter(Saldo.user_id == user_id).first()
    saldo_cash = float(saldo_row.total) if saldo_row else 0.0

    total_invested = sum(p["total_value"] for p in positions.values())
    grand_total = total_invested + saldo_cash

    donut_labels, donut_values, donut_pct = [], [], []
    for nama, pos in sorted(positions.items(), key=lambda x: -x[1]["total_value"]):
        pct = (pos["total_value"] / grand_total * 100) if grand_total > 0 else 0
        donut_labels.append(nama)
        donut_values.append(pos["total_value"])
        donut_pct.append(round(pct, 2))

    if saldo_cash > 0:
        cash_pct = (saldo_cash / grand_total * 100) if grand_total > 0 else 0
        donut_labels.append("💰 Cash")
        donut_values.append(round(saldo_cash, 2))
        donut_pct.append(round(cash_pct, 2))

    donut_colors = [DONUT_COLORS[i % len(DONUT_COLORS)] for i in range(len(donut_labels))]
    if saldo_cash > 0:
        donut_colors[-1] = "#374151"

    # 2. KPI SCORECARD
    kpi_query = db.query(
        func.count(),
        func.count(case((Portofolio.profit_loss > 0, 1))),
        func.count(case((Portofolio.profit_loss < 0, 1))),
        func.count(case((Portofolio.profit_loss == 0, 1))),
        func.coalesce(func.avg(case((Portofolio.profit_loss > 0, Portofolio.profit_loss))), 0),
        func.coalesce(func.avg(case((Portofolio.profit_loss < 0, Portofolio.profit_loss))), 0),
        func.coalesce(func.sum(Portofolio.profit_loss), 0),
        func.coalesce(func.max(Portofolio.profit_loss), 0),
        func.coalesce(func.min(Portofolio.profit_loss), 0),
    ).filter(Portofolio.jenis_transaksi == "JUAL", Portofolio.user_id == user_id).first()

    total_jual = int(kpi_query[0])
    total_win = int(kpi_query[1])
    avg_profit = float(kpi_query[4])
    avg_loss = float(kpi_query[5])

    kpi = {
        "win_rate": round((total_win / total_jual * 100) if total_jual > 0 else 0, 2),
        "total_jual": total_jual,
        "total_win": total_win,
        "total_loss": int(kpi_query[2]),
        "total_even": int(kpi_query[3]),
        "avg_profit": round(avg_profit, 2),
        "avg_loss": round(avg_loss, 2),
        "rr_ratio": round((avg_profit / abs(avg_loss)) if avg_loss != 0 else 0, 2),
        "total_pnl": round(float(kpi_query[6]), 2),
        "best_trade": round(float(kpi_query[7]), 2),
        "worst_trade": round(float(kpi_query[8]), 2),
    }

    # 3. MONTHLY HEATMAP
    monthly_rows = (
        db.query(
            extract("year", Portofolio.tanggal_beli).label("tahun"),
            extract("month", Portofolio.tanggal_beli).label("bulan"),
            func.sum(Portofolio.profit_loss),
        )
        .filter(Portofolio.jenis_transaksi == "JUAL", Portofolio.user_id == user_id)
        .group_by("tahun", "bulan")
        .order_by(asc("tahun"), asc("bulan"))
        .all()
    )

    total_modal = float(
        db.query(func.coalesce(func.sum(
            case((Portofolio.jenis_transaksi == "BELI", (Portofolio.jumlah * Portofolio.harga_beli) + Portofolio.fee), else_=0)
        ), 0)).filter(Portofolio.user_id == user_id).scalar()
    )

    heatmap_data = {}
    years_set = set()
    max_abs_pct = 0.0
    for row in monthly_rows:
        tahun, bulan, pnl = int(row[0]), int(row[1]), float(row[2])
        pct = (pnl / total_modal * 100) if total_modal > 0 else 0
        heatmap_data.setdefault(tahun, {})[bulan] = {"pnl": round(pnl, 2), "pct": round(pct, 2)}
        years_set.add(tahun)
        if abs(pct) > max_abs_pct:
            max_abs_pct = abs(pct)

    if not years_set:
        years_set.add(datetime.now().year)

    # 4. TOP 5 BEST & WORST
    asset_rows = (
        db.query(
            Portofolio.nama_aset,
            func.count().label("total_trades"),
            func.count(case((Portofolio.profit_loss > 0, 1))).label("wins"),
            func.count(case((Portofolio.profit_loss < 0, 1))).label("losses"),
            func.coalesce(func.sum(Portofolio.profit_loss), 0),
            func.coalesce(func.avg(Portofolio.profit_loss), 0),
            func.coalesce(func.max(Portofolio.profit_loss), 0),
            func.coalesce(func.min(Portofolio.profit_loss), 0),
        )
        .filter(Portofolio.jenis_transaksi == "JUAL", Portofolio.user_id == user_id)
        .group_by(Portofolio.nama_aset)
        .order_by(func.sum(Portofolio.profit_loss).desc())
        .all()
    )

    def _build(r):
        trades = int(r[1])
        wins = int(r[2])
        return {
            "name": r[0], "trades": trades, "wins": wins, "losses": int(r[3]),
            "total_pnl": round(float(r[4]), 2), "avg_pnl": round(float(r[5]), 2),
            "best_trade": round(float(r[6]), 2), "worst_trade": round(float(r[7]), 2),
            "win_rate": round((wins / trades * 100) if trades > 0 else 0, 1),
        }

    all_assets = [_build(r) for r in asset_rows]
    top5_best = all_assets[:5]
    top5_worst = list(reversed(all_assets[-5:])) if len(all_assets) >= 5 else list(reversed(all_assets))

    # 5. BENCHMARK TIMELINE
    daily_rows = (
        db.query(Portofolio.tanggal_beli, func.sum(Portofolio.profit_loss))
        .filter(Portofolio.jenis_transaksi == "JUAL", Portofolio.user_id == user_id)
        .group_by(Portofolio.tanggal_beli)
        .order_by(asc(Portofolio.tanggal_beli))
        .all()
    )

    port_labels, port_returns = [], []
    cum_pnl = 0.0
    for row in daily_rows:
        cum_pnl += float(row[1])
        pct = round((cum_pnl / total_modal * 100) if total_modal > 0 else 0, 4)
        port_labels.append(str(row[0]))
        port_returns.append(pct)

    return {
        "username": user.username,
        "donut_labels": donut_labels, "donut_values": donut_values,
        "donut_pct": donut_pct, "donut_colors": donut_colors,
        "total_portfolio_value": round(total_invested, 2),
        "grand_total": round(grand_total, 2), "saldo_cash": round(saldo_cash, 2),
        "positions": positions, "kpi": kpi,
        "heatmap_data": heatmap_data, "heatmap_years": sorted(years_set),
        "month_names": ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"],
        "max_abs_pct": round(max_abs_pct, 2),
        "top5_best": top5_best, "top5_worst": top5_worst,
        "port_bench_labels": port_labels, "port_bench_returns": port_returns,
        "bench_date_from": port_labels[0] if port_labels else "",
        "bench_date_to": port_labels[-1] if port_labels else "",
        "benchmark_options": [
            {"symbol": "^JKSE", "name": "IHSG (Indonesia)"},
            {"symbol": "^GSPC", "name": "S&P 500 (USA)"},
            {"symbol": "^N225", "name": "Nikkei 225 (Japan)"},
            {"symbol": "^HSI", "name": "Hang Seng (HK)"},
            {"symbol": "^FTSE", "name": "FTSE 100 (UK)"},
        ],
    }
