"""
Database initialization script.
Creates all tables and seeds 4 default user accounts + saldo.
Run: python init_db.py
"""
from database import engine, Base, SessionLocal
from models import User, Saldo, ActivityLog, Portofolio
from auth import get_password_hash


def init():
    print("📦 Creating all tables in 'trackerbaru'...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created successfully!")

    db = SessionLocal()
    try:
        # Check if users already exist
        existing = db.query(User).count()
        if existing > 0:
            print(f"ℹ️  {existing} users already exist. Skipping seed.")
            return

        # Default accounts: DRV1, DRV2, DRV3, Capital1
        accounts = [
            {"username": "DRV1", "password": "drv1pass", "is_admin": True},
            {"username": "DRV2", "password": "drv2pass", "is_admin": False},
            {"username": "DRV3", "password": "drv3pass", "is_admin": False},
            {"username": "CAPITAL1", "password": "capital1pass", "is_admin": False},
        ]

        for acc in accounts:
            user = User(
                username=acc["username"],
                password_hash=get_password_hash(acc["password"]),
                is_admin=acc["is_admin"],
            )
            db.add(user)
            db.flush()  # Get the user ID

            # Create initial saldo (0) for each user
            saldo = Saldo(total=0, referensi=0, user_id=user.id)
            db.add(saldo)
            print(f"  👤 Created user: {acc['username']} (admin={acc['is_admin']})")

        db.commit()
        print("\n🎉 Database initialized successfully!")
        print("\n📋 Default accounts:")
        print("  ┌──────────────┬──────────────┬─────────┐")
        print("  │   Username   │   Password   │  Admin  │")
        print("  ├──────────────┼──────────────┼─────────┤")
        for acc in accounts:
            admin_str = "  ✅  " if acc["is_admin"] else "  ❌  "
            print(f"  │ {acc['username']:<12} │ {acc['password']:<12} │{admin_str}│")
        print("  └──────────────┴──────────────┴─────────┘")

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    init()
