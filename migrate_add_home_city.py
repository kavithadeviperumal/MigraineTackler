"""Migration: add home_city column to user_profiles table."""

from sqlalchemy import text

from app.database import engine

with engine.connect() as conn:
    result = conn.execute(
        text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'user_profiles' AND column_name = 'home_city'
    """)
    )
    if result.fetchone():
        print("home_city already present — skipping")
    else:
        conn.execute(text("ALTER TABLE user_profiles ADD COLUMN home_city TEXT"))
        conn.commit()
        print("Added home_city column to user_profiles")

print("Migration complete.")
