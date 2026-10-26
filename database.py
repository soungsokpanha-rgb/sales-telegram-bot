import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import config
from config import DATA_DIR, DEFAULT_STORES

DB_PATH = DATA_DIR / "sales_bot.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize SQLite database tables and seed default stores."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Stores table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stores (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                default_target REAL NOT NULL DEFAULT 1000.0,
                manager_username TEXT DEFAULT '',
                topic_id INTEGER DEFAULT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            )
        """)

        # Migration: ensure manager_username and topic_id columns exist if table was created previously
        cursor.execute("PRAGMA table_info(stores)")
        columns = [row["name"] for row in cursor.fetchall()]
        if "manager_username" not in columns:
            cursor.execute("ALTER TABLE stores ADD COLUMN manager_username TEXT DEFAULT ''")
        if "topic_id" not in columns:
            cursor.execute("ALTER TABLE stores ADD COLUMN topic_id INTEGER DEFAULT NULL")

        # Daily sales table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_code TEXT NOT NULL,
                report_date TEXT NOT NULL,
                actual_sales REAL NOT NULL,
                target_sales REAL NOT NULL,
                transactions INTEGER DEFAULT 0,
                footfall INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                submitted_by_user_id INTEGER,
                submitted_by_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(store_code, report_date),
                FOREIGN KEY (store_code) REFERENCES stores(code)
            )
        """)

        # Users table (Managers & Area Managers)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                assigned_store TEXT DEFAULT '',
                role TEXT DEFAULT 'manager',
                last_seen TEXT
            )
        """)

        # System settings table (for dynamic topic IDs and configs)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Operational reports table (Briefing, Story & Telegram)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS operational_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_code TEXT NOT NULL,
                report_date TEXT NOT NULL,
                report_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'completed',
                notes TEXT DEFAULT '',
                submitted_by_user_id INTEGER,
                submitted_by_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(store_code, report_date, report_type),
                FOREIGN KEY (store_code) REFERENCES stores(code)
            )
        """)

        # Seed stores if not present
        for store in DEFAULT_STORES:
            mgr = store.get("manager_username", "")
            topic_id = store.get("topic_id")
            cursor.execute("""
                INSERT INTO stores (code, name, default_target, manager_username, topic_id)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    name = excluded.name,
                    manager_username = CASE 
                        WHEN excluded.manager_username != '' THEN excluded.manager_username 
                        ELSE stores.manager_username 
                    END,
                    topic_id = CASE 
                        WHEN excluded.topic_id IS NOT NULL THEN excluded.topic_id 
                        ELSE stores.topic_id 
                    END
            """, (store["code"], store["name"], store["default_target"], mgr, topic_id))

        conn.commit()


def get_all_stores(active_only: bool = True) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM stores"
        if active_only:
            query += " WHERE is_active = 1 ORDER BY code ASC"
        else:
            query += " ORDER BY code ASC"
        rows = cursor.execute(query).fetchall()
        return [dict(r) for r in rows]


def get_store(store_code: str) -> Optional[Dict[str, Any]]:
    if not store_code:
        return None
    code = store_code.upper().strip()
    if code in ("WWAEON", "WWAEON1", "WWAE-1", "AEON1"):
        code = "WWAE"
    with get_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute("SELECT * FROM stores WHERE code = ?", (code,)).fetchone()
        return dict(row) if row else None


def update_store_target(store_code: str, new_target: float) -> bool:
    store = get_store(store_code)
    if not store:
        return False
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE stores SET default_target = ? WHERE code = ?", (new_target, store["code"]))
        conn.commit()
        return cursor.rowcount > 0


def update_store_manager(store_code: str, manager_username: str) -> bool:
    """Assign or update manager username for a store."""
    store = get_store(store_code)
    if not store:
        return False
    clean_user = manager_username.strip().lstrip("@")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE stores SET manager_username = ? WHERE code = ?", (clean_user, store["code"]))
        conn.commit()
        return cursor.rowcount > 0


def update_store_topic(store_code: str, topic_id: Optional[int]) -> bool:
    """Set forum topic message_thread_id for a store."""
    store = get_store(store_code)
    if not store:
        return False
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE stores SET topic_id = ? WHERE code = ?", (topic_id, store["code"]))
        conn.commit()
        return cursor.rowcount > 0


def get_store_by_topic_id(topic_id: int) -> Optional[Dict[str, Any]]:
    """Lookup store by Telegram forum topic message_thread_id."""
    if not topic_id:
        return None
    with get_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT * FROM stores WHERE topic_id = ? AND is_active = 1",
            (topic_id,)
        ).fetchone()
        return dict(row) if row else None


def get_store_by_manager_username(username: str) -> Optional[Dict[str, Any]]:
    """Lookup store assigned to a specific manager's username."""
    if not username:
        return None
    clean_user = username.strip().lstrip("@").lower()
    with get_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT * FROM stores WHERE LOWER(manager_username) = ? AND is_active = 1",
            (clean_user,)
        ).fetchone()
        return dict(row) if row else None


def save_daily_sale(
    store_code: str,
    report_date: str,
    actual_sales: float,
    target_sales: float,
    transactions: int = 0,
    footfall: int = 0,
    notes: str = "",
    user_id: Optional[int] = None,
    user_name: Optional[str] = None
) -> Dict[str, Any]:
    """Upsert daily sales entry for a given store and date."""
    now_str = datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO daily_sales (
                store_code, report_date, actual_sales, target_sales,
                transactions, footfall, notes, submitted_by_user_id,
                submitted_by_name, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(store_code, report_date) DO UPDATE SET
                actual_sales = excluded.actual_sales,
                target_sales = excluded.target_sales,
                transactions = excluded.transactions,
                footfall = excluded.footfall,
                notes = excluded.notes,
                submitted_by_user_id = excluded.submitted_by_user_id,
                submitted_by_name = excluded.submitted_by_name,
                updated_at = excluded.updated_at
        """, (
            store_code, report_date, actual_sales, target_sales,
            transactions, footfall, notes, user_id, user_name,
            now_str, now_str
        ))
        conn.commit()

        # Retrieve the updated/inserted record
        row = cursor.execute("""
            SELECT s.*, st.name as store_name
            FROM daily_sales s
            JOIN stores st ON s.store_code = st.code
            WHERE s.store_code = ? AND s.report_date = ?
        """, (store_code, report_date)).fetchone()
        return dict(row) if row else {}


def get_daily_sales_by_date(date_str: str) -> List[Dict[str, Any]]:
    """Get all submitted sales records for a specific date (YYYY-MM-DD)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT s.*, st.name as store_name
            FROM daily_sales s
            JOIN stores st ON s.store_code = st.code
            WHERE s.report_date = ?
            ORDER BY s.store_code ASC
        """, (date_str,)).fetchall()
        return [dict(r) for r in rows]


def get_missing_stores(date_str: str) -> List[Dict[str, Any]]:
    """Return stores that have NOT yet submitted sales for the given date."""
    with get_connection() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT st.*
            FROM stores st
            WHERE st.is_active = 1
            AND st.code NOT IN (
                SELECT store_code FROM daily_sales WHERE report_date = ?
            )
            ORDER BY st.code ASC
        """, (date_str,)).fetchall()
        return [dict(r) for r in rows]


def get_sales_records(
    store_code: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Query sales records with optional filters."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT s.*, st.name as store_name
            FROM daily_sales s
            JOIN stores st ON s.store_code = st.code
            WHERE 1=1
        """
        params: List[Any] = []
        if store_code:
            query += " AND s.store_code = ?"
            params.append(store_code)
        if start_date:
            query += " AND s.report_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND s.report_date <= ?"
            params.append(end_date)

        query += " ORDER BY s.report_date DESC, s.store_code ASC LIMIT ?"
        params.append(limit)

        rows = cursor.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_monthly_summary(year_month_str: str) -> Dict[str, Any]:
    """Get aggregated month-to-date summary for year-month (e.g. '2026-10')."""
    with get_connection() as conn:
        cursor = conn.cursor()
        # Per store aggregate
        store_rows = cursor.execute("""
            SELECT
                s.store_code,
                st.name as store_name,
                COUNT(s.id) as days_reported,
                SUM(s.actual_sales) as total_actual,
                SUM(s.target_sales) as total_target,
                SUM(s.transactions) as total_transactions,
                SUM(s.footfall) as total_footfall
            FROM daily_sales s
            JOIN stores st ON s.store_code = st.code
            WHERE s.report_date LIKE ?
            GROUP BY s.store_code
            ORDER BY s.store_code ASC
        """, (f"{year_month_str}%",)).fetchall()

        stores_data = [dict(r) for r in store_rows]

        # Overall aggregate
        total_actual = sum(s["total_actual"] or 0.0 for s in stores_data)
        total_target = sum(s["total_target"] or 0.0 for s in stores_data)
        total_bills = sum(s["total_transactions"] or 0 for s in stores_data)

        return {
            "month": year_month_str,
            "stores": stores_data,
            "total_actual": total_actual,
            "total_target": total_target,
            "total_transactions": total_bills,
            "achievement_rate": (total_actual / total_target * 100.0) if total_target > 0 else 0.0
        }


def record_user_activity(user_id: int, username: Optional[str], full_name: Optional[str]) -> None:
    now_str = datetime.now().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (user_id, username, full_name, last_seen)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                last_seen = excluded.last_seen
        """, (user_id, username or "", full_name or "", now_str))
        conn.commit()


def set_setting(key: str, value: str) -> None:
    """Set a key-value setting in system_settings."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO system_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, str(value)))
        conn.commit()


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Retrieve a setting by key."""
    with get_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute("SELECT value FROM system_settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def get_daily_report_topic_id() -> Optional[int]:
    """Get the thread/topic ID for the 'Daily Report' topic."""
    import os
    val = get_setting("daily_report_topic_id")
    if val and val.strip().isdigit():
        return int(val.strip())
    env_val = os.getenv("TOPIC_DAILY_REPORT", "")
    return int(env_val.strip()) if env_val.strip().isdigit() else None


def set_daily_report_topic_id(topic_id: int) -> None:
    """Save the thread ID for the 'Daily Report' topic."""
    set_setting("daily_report_topic_id", str(topic_id))


def get_tiktok_topic_id() -> Optional[int]:
    """Get the thread/topic ID for the '📱 Tiktok Video' topic."""
    import os
    val = get_setting("tiktok_topic_id")
    if val and val.strip().isdigit():
        return int(val.strip())
    env_val = os.getenv("TOPIC_TIKTOK", os.getenv("TIKTOK_TOPIC_ID", ""))
    return int(env_val.strip()) if env_val.strip().isdigit() else None


def set_tiktok_topic_id(topic_id: int) -> None:
    """Save the thread ID for the '📱 Tiktok Video' topic."""
    set_setting("tiktok_topic_id", str(topic_id))


def save_operational_report(
    store_code: str,
    report_date: str,
    report_type: str,
    notes: str = "",
    user_id: Optional[int] = None,
    user_name: Optional[str] = None
) -> bool:
    """Record briefing or story_telegram report submission."""
    now_str = datetime.now().isoformat()
    store = get_store(store_code)
    code = store["code"] if store else store_code.upper()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO operational_reports (
                store_code, report_date, report_type, status, notes,
                submitted_by_user_id, submitted_by_name, created_at, updated_at
            ) VALUES (?, ?, ?, 'completed', ?, ?, ?, ?, ?)
            ON CONFLICT(store_code, report_date, report_type) DO UPDATE SET
                status = 'completed',
                notes = excluded.notes,
                submitted_by_user_id = excluded.submitted_by_user_id,
                submitted_by_name = excluded.submitted_by_name,
                updated_at = excluded.updated_at
        """, (code, report_date, report_type, notes, user_id, user_name or "Manager", now_str, now_str))
        conn.commit()
        return True


def get_operational_status_for_date(report_date: str) -> Dict[str, Dict[str, Any]]:
    """Return status for all active stores for a specific date (Briefing, Story/Telegram, and TikTok)."""
    stores = get_all_stores(active_only=True)
    try:
        dt = datetime.strptime(report_date, "%Y-%m-%d")
        weekday = dt.weekday()
    except Exception:
        weekday = -1

    status_map = {
        s["code"]: {
            "store_name": s["name"],
            "manager_username": s.get("manager_username", ""),
            "briefing": False,
            "briefing_notes": "",
            "briefing_time": "",
            "story_telegram": False,
            "story_telegram_notes": "",
            "story_telegram_time": "",
            "tiktok": False,
            "tiktok_notes": "",
            "tiktok_time": "",
            "is_tiktok_day": (weekday in config.TIKTOK_SCHEDULE.get(s["code"], [])),
            "week_tiktok_count": 0,
        }
        for s in stores
    }

    with get_connection() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT store_code, report_type, notes, updated_at
            FROM operational_reports
            WHERE report_date = ?
        """, (report_date,)).fetchall()

        for r in rows:
            c = r["store_code"]
            if c in status_map:
                rtype = r["report_type"]
                if rtype == "briefing":
                    status_map[c]["briefing"] = True
                    status_map[c]["briefing_notes"] = r["notes"] or ""
                    status_map[c]["briefing_time"] = r["updated_at"]
                elif rtype in ("story", "story_telegram"):
                    status_map[c]["story_telegram"] = True
                    status_map[c]["story_telegram_notes"] = r["notes"] or ""
                    status_map[c]["story_telegram_time"] = r["updated_at"]
                elif rtype == "tiktok":
                    status_map[c]["tiktok"] = True
                    status_map[c]["tiktok_notes"] = r["notes"] or ""
                    status_map[c]["tiktok_time"] = r["updated_at"]

    # Calculate weekly count for each store
    for code in status_map:
        status_map[code]["week_tiktok_count"] = get_tiktok_count_for_week(code, report_date)

    return status_map


def get_tiktok_count_for_week(store_code: str, reference_date: Optional[str] = None) -> int:
    """Return number of TikTok videos submitted by a store during the week of reference_date."""
    if not reference_date:
        ref_dt = datetime.now()
    else:
        try:
            ref_dt = datetime.strptime(reference_date, "%Y-%m-%d")
        except Exception:
            ref_dt = datetime.now()

    monday_dt = ref_dt - timedelta(days=ref_dt.weekday())
    sunday_dt = monday_dt + timedelta(days=6)
    start_of_week = monday_dt.strftime("%Y-%m-%d")
    end_of_week = sunday_dt.strftime("%Y-%m-%d")

    store = get_store(store_code)
    code = store["code"] if store else store_code.upper()

    with get_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute("""
            SELECT COUNT(*) as cnt
            FROM operational_reports
            WHERE store_code = ?
              AND report_type = 'tiktok'
              AND report_date >= ?
              AND report_date <= ?
        """, (code, start_of_week, end_of_week)).fetchone()
        return int(row["cnt"]) if row else 0


def get_weekly_tiktok_report(reference_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Get detailed weekly TikTok follow-up status for all 3 stores.
    Tracks 2 videos / week per store:
      WWEG: Monday & Thursday
      WW271: Tuesday & Friday
      WWAE: Wednesday & Saturday
    """
    if not reference_date:
        ref_dt = datetime.now()
    else:
        try:
            ref_dt = datetime.strptime(reference_date, "%Y-%m-%d")
        except Exception:
            ref_dt = datetime.now()

    monday_dt = ref_dt - timedelta(days=ref_dt.weekday())
    sunday_dt = monday_dt + timedelta(days=6)
    start_date = monday_dt.strftime("%Y-%m-%d")
    end_date = sunday_dt.strftime("%Y-%m-%d")

    stores = get_all_stores(active_only=True)
    today_str = datetime.now().strftime("%Y-%m-%d")

    result: Dict[str, Any] = {
        "start_date": start_date,
        "end_date": end_date,
        "stores": {},
        "total_completed": 0,
        "total_target": len(stores) * 2,
    }

    with get_connection() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("""
            SELECT store_code, report_date, notes, submitted_by_name, updated_at
            FROM operational_reports
            WHERE report_type = 'tiktok'
              AND report_date >= ?
              AND report_date <= ?
            ORDER BY report_date ASC
        """, (start_date, end_date)).fetchall()

    submissions_by_store: Dict[str, List[Dict[str, Any]]] = {s["code"]: [] for s in stores}
    for r in rows:
        c = r["store_code"]
        if c in submissions_by_store:
            submissions_by_store[c].append(dict(r))

    for st in stores:
        code = st["code"]
        assigned_weekdays = config.TIKTOK_SCHEDULE.get(code, [])
        store_submissions = submissions_by_store.get(code, [])
        completed_count = len(store_submissions)

        days_info = []
        for wday in assigned_weekdays:
            target_date_dt = monday_dt + timedelta(days=wday)
            target_date_str = target_date_dt.strftime("%Y-%m-%d")
            day_name_en = config.WEEKDAY_NAMES_EN[wday]
            day_name_kh = config.WEEKDAY_NAMES_KH[wday]

            matching = [s for s in store_submissions if s["report_date"] == target_date_str]
            is_submitted = len(matching) > 0
            submission_data = matching[0] if is_submitted else None

            if target_date_str < today_str:
                state = "done" if is_submitted else "missed"
            elif target_date_str == today_str:
                state = "today_done" if is_submitted else "today_pending"
            else:
                state = "done" if is_submitted else "upcoming"

            days_info.append({
                "weekday": wday,
                "date": target_date_str,
                "day_name_en": day_name_en,
                "day_name_kh": day_name_kh,
                "is_submitted": is_submitted,
                "state": state,
                "submission": submission_data,
            })

        result["stores"][code] = {
            "name": st["name"],
            "manager_username": st.get("manager_username", ""),
            "target": 2,
            "completed": completed_count,
            "submissions": store_submissions,
            "days": days_info,
        }
        result["total_completed"] += completed_count

    return result


def get_missing_operational_stores(report_date: str) -> List[Dict[str, Any]]:
    """Return list of stores that are missing briefing, story_telegram, or scheduled tiktok for today."""
    status_map = get_operational_status_for_date(report_date)
    missing = []
    for code, info in status_map.items():
        missing_types = []
        if not info["briefing"]:
            missing_types.append("Briefing")
        if not info["story_telegram"]:
            missing_types.append("Story & Telegram")
        if info.get("is_tiktok_day") and not info["tiktok"]:
            missing_types.append("🎬 TikTok Video")
        if missing_types:
            missing.append({
                "code": code,
                "name": info["store_name"],
                "manager_username": info["manager_username"],
                "missing_types": missing_types,
            })
    return missing
