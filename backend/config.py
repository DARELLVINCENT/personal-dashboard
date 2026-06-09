"""
Application configuration loaded from environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/trackerbaru")
SECRET_KEY = os.getenv("SECRET_KEY", "fallback_secret_key_ganti_ini")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
