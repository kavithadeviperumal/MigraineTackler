"""One-off migration: fix schema drift in log_entries table.

Changes:
  - Rename alcohol_units -> alcohol_drinks
  - Add missing traditional_medicine TEXT column
"""

import sqlite3

from app.config import settings

conn = sqlite3.connect(settings.db_path)
cursor = conn.cursor()

# Check SQLite version (RENAME COLUMN requires >= 3.25.0)
version = tuple(int(x) for x in sqlite3.sqlite_version.split("."))
print(f"SQLite version: {sqlite3.sqlite_version}")

cols = {row[1] for row in cursor.execute("PRAGMA table_info(log_entries)")}

if "alcohol_units" in cols and "alcohol_drinks" not in cols:
    if version >= (3, 25, 0):
        cursor.execute("ALTER TABLE log_entries RENAME COLUMN alcohol_units TO alcohol_drinks")
        print("Renamed alcohol_units -> alcohol_drinks")
    else:
        print("ERROR: SQLite < 3.25 — cannot rename column in-place. Upgrade SQLite.")
elif "alcohol_drinks" in cols:
    print("alcohol_drinks already present — skipping rename")

if "traditional_medicine" not in cols:
    cursor.execute("ALTER TABLE log_entries ADD COLUMN traditional_medicine TEXT")
    print("Added traditional_medicine column")
else:
    print("traditional_medicine already present — skipping")

tables = {row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")}

if "user_profiles" in tables:
    profile_cols = {row[1] for row in cursor.execute("PRAGMA table_info(user_profiles)")}
    if "typical_hydration_oz" not in profile_cols:
        cursor.execute("ALTER TABLE user_profiles ADD COLUMN typical_hydration_oz REAL")
        print("Added typical_hydration_oz column to user_profiles")
    else:
        print("typical_hydration_oz already present — skipping")
    if "typical_caffeine_level" not in profile_cols:
        cursor.execute("ALTER TABLE user_profiles ADD COLUMN typical_caffeine_level TEXT")
        print("Added typical_caffeine_level column to user_profiles")
    else:
        print("typical_caffeine_level already present — skipping")
else:
    print("user_profiles table not yet created — columns will be added by SQLModel on first run")

conn.commit()
conn.close()
print("Migration complete.")
