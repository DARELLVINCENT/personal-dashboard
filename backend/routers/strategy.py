"""
Strategy analytics router.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case, asc
from collections import defaultdict

from database import get_db
from models import Portofolio
from auth import get_current_user, log_activity

router = APIRouter(prefix="/api/strategy", tags=["Strategy"])

STRATEGIES = ["Swing", "Scalping", "Investasi"]
STRAT_COLORS = {"Swing": "#3B82F6", "Scalping": "#F59E0B", "Investasi": "#10B981", "Untagged": "#6B7280"}


@router.get("")
def get_strategy_analytics(db: Session = Depends(get_db), user=Depends(get_current_user)):
    user_id = user.id
    log_activity(db, user_id, user.username, "VIEW_STRATEGY", "Melihat halaman Strategy")

    # KPI per strategy
    rows = (
        db.query(
            func.coalesce(Portofolio.strategy, "Untagged"),
            func.count(),
            func.count(case((Portofolio.profit_loss > 0, 1))),
            func.count(case((Portofolio.profit_loss < 0, 1))),
            func.count(case((Portofolio.profit_loss == 0, 1))),
            func.coalesce(func.sum(Portofolio.profit_loss), 0),
            func.coalesce(func.avg(case((Portofolio.profit_loss > 0, Portofolio.profit_loss))), 0),
            func.coalesce(func.avg(case((Portofolio.profit_loss < 0, Portofolio.profit_loss))), 0),
            func.coalesce(func.max(Portofolio.profit_loss), 0),
            func.coalesce(func.min(Portofolio.profit_loss), 0),
        )
        .filter(Portofolio.jenis_transaksi == "JUAL", Portofolio.user_id == user_id)
        .group_by(func.coalesce(Portofolio.strategy, "Untagged"))
        .order_by(func.sum(Portofolio.profit_loss).desc())
        .all()
    )

    strategy_data = []
    for r in rows:
        strat, trades, wins = r[0], int(r[1]), int(r[2])
        avg_win = float(r[6])
        avg_loss = float(r[7])
        strategy_data.append({
            "name": strat, "trades": trades, "wins": wins,
            "losses": int(r[3]), "even": int(r[4]),
            "total_pnl": round(float(r[5]), 2),
            "avg_win": round(avg_win, 2), "avg_loss": round(avg_loss, 2),
            "win_rate": round((wins / trades * 100) if trades > 0 else 0, 1),
            "rr_ratio": round((avg_win / abs(avg_loss)) if avg_loss != 0 else 0, 2),
            "best": round(float(r[8]), 2), "worst": round(float(r[9]), 2),
        })

    # Cumulative PnL timeline per strategy
    timeline_rows = (
        db.query(
            func.coalesce(Portofolio.strategy, "Untagged"),
            Portofolio.tanggal_beli,
            func.sum(Portofolio.profit_loss),
        )
        .filter(Portofolio.jenis_transaksi == "JUAL", Portofolio.user_id == user_id)
        .group_by(func.coalesce(Portofolio.strategy, "Untagged"), Portofolio.tanggal_beli)
        .order_by(asc(Portofolio.tanggal_beli))
        .all()
    )

    raw_by_strat = defaultdict(list)
    for strat, date, pnl in timeline_rows:
        raw_by_strat[strat].append((str(date), float(pnl)))

    timeline = {}
    for strat, entries in raw_by_strat.items():
        running, points = 0.0, []
        for date, pnl in entries:
            running += pnl
            points.append({"date": date, "pnl": round(running, 2)})
        timeline[strat] = points

    chart_labels = [s["name"] for s in strategy_data]
    chart_pnl = [s["total_pnl"] for s in strategy_data]
    chart_wins = [s["wins"] for s in strategy_data]
    chart_losses = [s["losses"] for s in strategy_data]
    chart_colors = [STRAT_COLORS.get(s["name"], "#8B5CF6") for s in strategy_data]

    return {
        "username": user.username,
        "strategy_data": strategy_data,
        "chart_labels": chart_labels, "chart_pnl": chart_pnl,
        "chart_wins": chart_wins, "chart_losses": chart_losses,
        "chart_colors": chart_colors, "timeline": timeline,
        "strategies": STRATEGIES,
    }
