"""
FastAPI main application — registers all routers and CORS.
"""
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from config import FRONTEND_URL
from database import get_db
from models import User
from schemas import LoginRequest, TokenResponse
from auth import verify_password, create_access_token, log_activity

from routers import transactions, portfolio, analytics, strategy, admin, market, benchmark, forecast, sentiment, screening

app = FastAPI(title="Portfolio Tracker API", version="2.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(transactions.router)
app.include_router(portfolio.router)
app.include_router(analytics.router)
app.include_router(strategy.router)
app.include_router(admin.router)
app.include_router(market.router)
app.include_router(benchmark.router)
app.include_router(forecast.router)
app.include_router(sentiment.router)
app.include_router(screening.router)


@app.get("/")
def root():
    return {"message": "Portfolio Tracker API v2.0 — FastAPI", "status": "running"}


@app.post("/api/auth/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    username = data.username.upper()
    user = db.query(User).filter(User.username == username).first()

    if not user or not verify_password(data.password, user.password_hash):
        # Log failed attempt
        log_activity(db, None, username, "LOGIN_FAILED",
                     f"Percobaan login gagal untuk user {username}",
                     request.client.host, str(request.headers.get("user-agent", "")))
        raise HTTPException(status_code=401, detail="User ID atau Password salah!")

    token = create_access_token(data={"sub": str(user.id)})
    log_activity(db, user.id, user.username, "LOGIN",
                 f"User {user.username} berhasil login",
                 request.client.host, str(request.headers.get("user-agent", "")))

    return TokenResponse(
        access_token=token, username=user.username,
        user_id=user.id, is_admin=user.is_admin or False,
    )


@app.get("/api/auth/me")
def get_me(db: Session = Depends(get_db)):
    from auth import get_current_user, security
    # This is handled via dependency injection in protected routes
    return {"detail": "Use Authorization header with Bearer token"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
