import sqlite3
import json
import time
from pathlib import Path

DB_PATH = Path("chatbot_global.db")


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_plan_table():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        profile_json TEXT,
        calories_json TEXT,
        diet_json TEXT,
        workout_json TEXT,
        created_at INTEGER
    )
    """)

    conn.commit()
    conn.close()


def save_plan(user_id, profile, calories, diet, workout):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO plans (
        user_id,
        profile_json,
        calories_json,
        diet_json,
        workout_json,
        created_at
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        json.dumps(profile),
        json.dumps(calories),
        json.dumps(diet),
        json.dumps(workout),
        int(time.time())
    ))

    conn.commit()
    conn.close()


def get_latest_plan(user_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT profile_json, calories_json, diet_json, workout_json, created_at
    FROM plans
    WHERE user_id = ?
    ORDER BY created_at DESC
    LIMIT 1
    """, (user_id,))

    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "profile": json.loads(row[0]),
        "calories": json.loads(row[1]),
        "diet": json.loads(row[2]),
        "workout": json.loads(row[3]),
        "created_at": row[4]
    }


def get_plan_history(user_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT profile_json, calories_json, diet_json, workout_json, created_at
    FROM plans
    WHERE user_id = ?
    ORDER BY created_at DESC
    """, (user_id,))

    rows = cur.fetchall()
    conn.close()

    history = []

    for r in rows:
        history.append({
            "profile": json.loads(r[0]),
            "calories": json.loads(r[1]),
            "diet": json.loads(r[2]),
            "workout": json.loads(r[3]),
            "created_at": r[4]
        })

    return history
