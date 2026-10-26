# 🏬 Concept Stores Daily Sales Follow-up Telegram Bot

A Telegram bot designed for Area Managers to track and follow up daily sales performance across 3 Concept Stores:
1. **WWEG** (WWEG Concept Store)
2. **WW271** (WW271 Concept Store)
3. **WWAE** (WWAE Concept Store)

---

## ✨ Key Features

- **Interactive Guided Submission Wizard (`/submit`)**:
  Store managers can submit daily sales in seconds using Telegram buttons:
  1. Select Store (WWEG, WW271, WWAE)
  2. Select Date (Today, Yesterday, or custom date)
  3. Enter Actual Sales ($)
  4. Daily Target ($) with 1-tap default button
  5. Number of transactions/bills & ATV (Average Ticket Value) calculation
  6. Optional notes (e.g., promotions, weather, footfall)
- **Real-Time Consolidated Reports (`/today`, `/yesterday`)**:
  - Live performance breakdown per store with status badges (🟢 Hit >=100%, 🟡 Close 80-99%, 🔴 Under <80%, ⏳ Pending)
  - Combined Total Sales, Target, Variance (+/-), Overall %, and Group ATV
- **Follow-up Reminders for Missing Stores (`/missing`)**:
  - Checks which stores haven't reported yet for today.
  - Manual trigger button or automatic scheduled reminders.
- **Month-to-Date (MTD) Analytics (`/mtd`)**:
  - Aggregates monthly performance and achievement rate.
- **One-Click Excel Export (`/export`)**:
  - Generates `.xlsx` spreadsheet with formatted currency, formulas, and multi-store breakdown and sends it directly in Telegram chat.
- **Automated Background Scheduler**:
  - **14:00 (Afternoon):** Early follow-up check.
  - **21:00 (Closing):** Alert sent to group highlighting pending stores.
  - **22:00 (Nightly):** Automated consolidated daily closing recap posted to the Area Manager channel/group.

---

## 🚀 Setup Instructions (3 Steps)

### Step 1: Create Your Telegram Bot
1. Open Telegram and search for **[@BotFather](https://t.me/BotFather)**.
2. Send `/newbot`.
3. Choose a name (e.g., `Concept Store Sales Follow-up Bot`) and username (e.g., `ConceptStoreSalesBot`).
4. BotFather will provide an **API Token** (e.g. `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`).

### Step 2: Configure Environment Variables
Open the `.env` file in this folder:
```env
# Paste your BotFather token here
BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ

# Area Manager Telegram User ID (Optional - send /myid to bot to get your ID)
ADMIN_IDS=123456789

# Target Chat or Group ID for automated alerts and daily recap
# Add your bot to the managers group, then send /myid to get the group ID
REPORT_CHAT_ID=-1001234567890

# Timezone & Currency
TIMEZONE=Asia/Phnom_Penh
CURRENCY_SYMBOL=$

# Daily targets for each Concept Store
TARGET_WWEG=1000.0
TARGET_WW271=1000.0
TARGET_WWAE=1000.0

# Store Managers Telegram Usernames (e.g. @username)
# Bot will tag managers in reminders & automatically recognize them in /submit
MANAGER_WWEG=@manager_wweg
MANAGER_WW271=@manager_ww271
MANAGER_WWAE=@manager_wwae

# Schedule times (24-hour format)
REMINDER_AFTERNOON=14:00
REMINDER_EVENING=21:00
AUTO_REPORT_TIME=22:00
```

### Step 3: Run the Bot
- Simply double-click **`run_bot.bat`**
- Or run in terminal:
  ```powershell
  python bot.py
  ```

---

## 📱 Bot Command Reference

| Command | Description |
|---|---|
| `/start` | Open the interactive dashboard with inline buttons |
| `/submit` | Guided wizard to submit daily sales for WWEG, WW271, or WWAE |
| `/today` or `/report` | Consolidated report for all 3 stores for today |
| `/yesterday` | Consolidated report for yesterday |
| `/missing` | View which stores have NOT yet submitted today (with manager tags) |
| `/mtd` | Month-to-date sales and achievement breakdown |
| `/export` | Download full database in Excel `.xlsx` format |
| `/stores` | View store directory, managers, and configured daily targets |
| `/myid` | Get your Telegram User ID & current Chat ID |
| `/settarget <STORE> <AMOUNT>` | *(Admin)* Update default target (e.g. `/settarget WWEG 1500`) |
| `/setmanager <STORE> <@USER>` | *(Admin)* Assign manager username (e.g. `/setmanager WWEG @alex`) |
| `/remind` | *(Admin)* Trigger immediate follow-up alert to pending stores |
| `/broadcast <MSG>` | *(Admin)* Send urgent announcement to the reporting group |

---

## 📂 Project Structure

```
d:\Concept Store - Area Manager\12. BOT IT\
├── .env                # Active configuration (Bot token, chat IDs, targets)
├── .env.example        # Reference environment template
├── bot.py              # Main bot entry point and router
├── config.py           # Settings and configuration loader
├── database.py         # SQLite database models & query operations
├── export_excel.py     # Excel generator using openpyxl
├── reports.py          # Message formatting for reports, cards, and alerts
├── scheduler.py        # Automated daily reminders and recap jobs
├── run_bot.bat         # 1-click Windows startup script
├── requirements.txt    # Python dependencies
├── data/               # SQLite database storage (sales_bot.db)
├── exports/            # Generated Excel reports (.xlsx)
└── handlers/
    ├── start.py        # /start, /help, /myid and interactive menu
    ├── submit_sales.py # Guided sales submission conversation handler
    ├── view_reports.py # Report viewers, callbacks, and excel trigger
    └── admin.py        # Area Manager commands (targets, broadcast, remind)
```
