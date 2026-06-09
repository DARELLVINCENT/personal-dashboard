"""
Database migration: Add waktu_transaksi column to portofolio table.
Run: python migrate_add_waktu.py
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from database import engine
import sqlalchemy


def migrate():
    print("[MIGRATION] Adding 'waktu_transaksi' column to 'portofolio'...")

    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(
            sqlalchemy.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'portofolio' AND column_name = 'waktu_transaksi'"
            )
        )
        if result.fetchone():
            print("[INFO] Column 'waktu_transaksi' already exists. Skipping.")
            return

        conn.execute(
            sqlalchemy.text(
                "ALTER TABLE portofolio ADD COLUMN waktu_transaksi TIME;"
            )
        )
        conn.commit()
        print("[OK] Migration complete! Column 'waktu_transaksi' added successfully.")


if __name__ == "__main__":
    migrate()
