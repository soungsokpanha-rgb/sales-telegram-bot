import os
from pathlib import Path
from dotenv import load_dotenv
import pytz

# Base directory
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
EXPORTS_DIR = BASE_DIR / "exports"

DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Load environment variables
load_dotenv(BASE_DIR / ".env")

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Area Manager & Authorized Admin IDs (comma-separated integers)
ADMIN_IDS = [
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
]

# Primary Chat or Group ID to send automated reminders and consolidated reports
REPORT_CHAT_ID = os.getenv("REPORT_CHAT_ID", "").strip()
if REPORT_CHAT_ID.lstrip("-").isdigit():
    REPORT_CHAT_ID = int(REPORT_CHAT_ID)
else:
    REPORT_CHAT_ID = None

# Timezone settings (Default: GMT+7 Cambodia / Thailand / Indochina)
TIMEZONE_NAME = os.getenv("TIMEZONE", "Asia/Phnom_Penh")
try:
    BOT_TIMEZONE = pytz.timezone(TIMEZONE_NAME)
except Exception:
    BOT_TIMEZONE = pytz.timezone("Asia/Bangkok")

# Currency symbol
CURRENCY_SYMBOL = os.getenv("CURRENCY_SYMBOL", "$")

# Store Definitions
DEFAULT_STORES = [
    {
        "code": "WWEG",
        "name": "WWEG Concept Store",
        "default_target": float(os.getenv("TARGET_WWEG", "1000.0").strip() or "1000.0"),
        "manager_username": os.getenv("MANAGER_WWEG", "").strip().lstrip("@"),
        "topic_id": int(os.getenv("TOPIC_WWEG")) if os.getenv("TOPIC_WWEG", "").strip().isdigit() else None,
    },
    {
        "code": "WW271",
        "name": "WW271 Concept Store",
        "default_target": float(os.getenv("TARGET_WW271", "1000.0").strip() or "1000.0"),
        "manager_username": os.getenv("MANAGER_WW271", "").strip().lstrip("@"),
        "topic_id": int(os.getenv("TOPIC_WW271")) if os.getenv("TOPIC_WW271", "").strip().isdigit() else None,
    },
    {
        "code": "WWAE",
        "name": "WWAEON1 Concept Store",
        "default_target": float(os.getenv("TARGET_WWAE", "1000.0").strip() or "1000.0"),
        "manager_username": os.getenv("MANAGER_WWAE", "").strip().lstrip("@"),
        "topic_id": int(os.getenv("TOPIC_WWAE", os.getenv("TOPIC_WWAEON1", ""))) if (os.getenv("TOPIC_WWAE", "").strip().isdigit() or os.getenv("TOPIC_WWAEON1", "").strip().isdigit()) else None,
    },
]

# Automated Schedule Times (HH:MM in 24-hour format)
FORM_DROP_TIME = os.getenv("FORM_DROP_TIME", "08:00")
REMINDER_1 = os.getenv("REMINDER_1", os.getenv("REMINDER_AFTERNOON", "14:00"))
REMINDER_2 = os.getenv("REMINDER_2", os.getenv("REMINDER_EVENING", "21:00"))
RECAP_TIME = os.getenv("RECAP_TIME", "00:00")  # 12:00 AM Midnight

# TikTok Weekly Follow-up Schedule (2 videos / week per store)
# Weekdays: 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday
TIKTOK_SCHEDULE = {
    "WWEG": [0, 3],   # Monday and Thursday
    "WW271": [1, 4],  # Tuesday and Friday
    "WWAE": [2, 5],   # Wednesday and Saturday (WWAEON1)
}

WEEKDAY_NAMES_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAY_NAMES_KH = ["ចន្ទ", "អង្គារ", "ពុធ", "ព្រហស្បតិ៍", "សុក្រ", "សៅរ៍", "អាទិត្យ"]


def normalize_store_code(store_code: str) -> str:
    """Normalize store aliases to primary code (e.g. WWAEON, WWAEON1 -> WWAE)."""
    if not store_code:
        return ""
    code = store_code.upper().strip()
    if code in ("WWAEON", "WWAEON1", "WWAE-1", "AEON1"):
        return "WWAE"
    return code


def get_store_tiktok_days(store_code: str) -> list[int]:
    """Return scheduled weekdays (0=Mon..6=Sun) for given store."""
    code = normalize_store_code(store_code)
    return TIKTOK_SCHEDULE.get(code, [])
