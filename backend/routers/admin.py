"""
Admin dashboard router.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from datetime import date

from database import get_db
from models import User, Portofolio, Saldo, ActivityLog
from auth import get_current_user

router = APIRouter(prefix="/api/admin", tags=["Admin"])


def format_bytes(size_bytes):
    if not size_bytes:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i, size = 0, float(size_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return f"{size:.2f} {units[i]}"


@router.get("")
def admin_dashboard(
    filter_user: str = "", filter_action: str = "",
    filter_date_from: str = "", filter_date_to: str = "",
    page: int = Query(1, ge=1), per_page: int = 25,
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Akses ditolak!")

    total_users = db.query(func.count(User.id)).scalar()
    activities_today = db.query(func.count(ActivityLog.id)).filter(
        func.date(ActivityLog.created_at) == date.today()).scalar()
    total_db_size = db.execute(text("SELECT pg_database_size(current_database())")).scalar()

    users = db.query(User).order_by(User.id).all()
    user_summary = []
    for u in users:
        lc = db.query(func.count(ActivityLog.id)).filter(ActivityLog.user_id == u.id, ActivityLog.action == "LOGIN").scalar()
        ta = db.query(func.count(ActivityLog.id)).filter(ActivityLog.user_id == u.id).scalar()
        la = db.query(func.max(ActivityLog.created_at)).filter(ActivityLog.user_id == u.id).scalar()
        user_summary.append({"id": u.id, "username": u.username, "created_at": str(u.created_at or ""),
                             "login_count": lc, "total_activity": ta, "last_activity": str(la or "")})

    user_storage = []
    for u in users:
        pr = db.query(func.count(Portofolio.id)).filter(Portofolio.user_id == u.id).scalar()
        ar = db.query(func.count(ActivityLog.id)).filter(ActivityLog.user_id == u.id).scalar()
        sr = db.query(func.count(Saldo.id)).filter(Saldo.user_id == u.id).scalar()
        eb = (pr * 512) + (ar * 256) + (sr * 128)
        user_storage.append({"user_id": u.id, "username": u.username, "portofolio_rows": pr,
                             "activity_rows": ar, "total_rows": pr + ar + sr, "estimated_size": format_bytes(eb)})

    query = db.query(ActivityLog)
    if filter_user: query = query.filter(ActivityLog.username == filter_user)
    if filter_action: query = query.filter(ActivityLog.action == filter_action)
    if filter_date_from: query = query.filter(func.date(ActivityLog.created_at) >= filter_date_from)
    if filter_date_to: query = query.filter(func.date(ActivityLog.created_at) <= filter_date_to)

    total_logs = query.count()
    total_pages = max(1, (total_logs + per_page - 1) // per_page)
    logs = query.order_by(ActivityLog.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    activity_logs = [{"id": l.id, "username": l.username, "action": l.action, "detail": l.detail,
                      "ip_address": l.ip_address, "created_at": str(l.created_at or "")} for l in logs]

    log_users = [r[0] for r in db.query(ActivityLog.username).distinct().order_by(ActivityLog.username).all()]
    log_actions = [r[0] for r in db.query(ActivityLog.action).distinct().order_by(ActivityLog.action).all()]

    return {"total_users": total_users, "activities_today": activities_today, "total_db_size": format_bytes(total_db_size),
            "user_summary": user_summary, "user_storage": user_storage, "activity_logs": activity_logs,
            "total_logs": total_logs, "page": page, "total_pages": total_pages,
            "log_users": log_users, "log_actions": log_actions,
            "all_usernames": [u.username for u in users], "username": user.username, "today": str(date.today())}
