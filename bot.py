import logging
import sys
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

import config
import database as db
from handlers.start import start_command, help_command, myid_command
from handlers.submit_sales import get_submission_handler, handle_sales_reply
from handlers.view_reports import (
    report_today_command,
    report_yesterday_command,
    missing_stores_command,
    mtd_command,
    stores_command,
    export_excel_command,
    manual_remind_button,
    return_to_main_menu,
)
from handlers.admin import (
    settarget_command,
    setmanager_command,
    settopic_command,
    link_topic_callback,
    dropforms_command,
    remind_command,
    broadcast_command,
)
from handlers.operational_reports import (
    link_daily_command,
    link_tiktok_command,
    handle_operational_reply,
    tiktok_command,
)
from scheduler import setup_scheduled_jobs

# Configure logging
logging.basicConfig(
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("SalesBot")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by updates."""
    err_str = str(context.error or "")
    if "Message to be replied not found" in err_str:
        # Ignore attempts to reply to messages that were deleted in Telegram
        return
    logger.error("Exception while handling an update: %s", context.error, exc_info=context.error)


async def unified_reply_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route replies: sales report template first, then operational reports."""
    handled = await handle_sales_reply(update, context)
    if handled:
        return
    await handle_operational_reply(update, context)


def main() -> None:
    # 1. Initialize SQLite Database
    logger.info("Initializing database...")
    db.init_db()

    # 2. Check Bot Token
    token = config.BOT_TOKEN
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("\n" + "=" * 60)
        print("❌ ERROR: TELEGRAM_BOT_TOKEN is not configured!")
        print("Please edit the .env file in:")
        print(f"  {config.BASE_DIR / '.env'}")
        print("Set BOT_TOKEN to your bot token from @BotFather.")
        print("=" * 60 + "\n")
        sys.exit(1)

    logger.info("Building Telegram Application...")
    application = Application.builder().token(token).build()

    # 3. Register Handlers
    # Sales Entry Conversation Handler (Priority 1)
    application.add_handler(get_submission_handler())

    # Unified Auto-Reply (Sales Report template, Daily Report photo/notes & TikTok replies)
    application.add_handler(
        MessageHandler(
            (filters.PHOTO | filters.Document.ALL | filters.TEXT | filters.VIDEO) & ~filters.COMMAND,
            unified_reply_router
        ),
        group=1
    )

    # Core Navigation & Info Commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("myid", myid_command))

    # Daily Report & TikTok Topic Commands
    application.add_handler(CommandHandler("linkdaily", link_daily_command))
    application.add_handler(CommandHandler("daily", link_daily_command))
    application.add_handler(CommandHandler("dailyreport", link_daily_command))
    application.add_handler(CommandHandler("linktiktok", link_tiktok_command))

    # Reporting Commands
    application.add_handler(CommandHandler("today", report_today_command))
    application.add_handler(CommandHandler("report", report_today_command))
    application.add_handler(CommandHandler("yesterday", report_yesterday_command))
    application.add_handler(CommandHandler("missing", missing_stores_command))
    application.add_handler(CommandHandler("mtd", mtd_command))
    application.add_handler(CommandHandler("export", export_excel_command))
    application.add_handler(CommandHandler("stores", stores_command))
    application.add_handler(CommandHandler("tiktok", tiktok_command))
    application.add_handler(CommandHandler("tt", tiktok_command))

    # Admin Commands
    application.add_handler(CommandHandler("settarget", settarget_command))
    application.add_handler(CommandHandler("setmanager", setmanager_command))
    application.add_handler(CommandHandler("settopic", settopic_command))
    application.add_handler(CommandHandler("linktopic", settopic_command))
    application.add_handler(CommandHandler("dropforms", dropforms_command))
    application.add_handler(CommandHandler("dropform", dropforms_command))
    application.add_handler(CommandHandler("remind", remind_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))

    # Inline Keyboard Button Handlers
    application.add_handler(CallbackQueryHandler(link_topic_callback, pattern="^link_topic_"))
    application.add_handler(CallbackQueryHandler(report_today_command, pattern="^btn_view_today$"))
    application.add_handler(CallbackQueryHandler(report_yesterday_command, pattern="^btn_view_yesterday$"))
    application.add_handler(CallbackQueryHandler(missing_stores_command, pattern="^btn_view_missing$"))
    application.add_handler(CallbackQueryHandler(mtd_command, pattern="^btn_view_mtd$"))
    application.add_handler(CallbackQueryHandler(export_excel_command, pattern="^btn_export_excel$"))
    application.add_handler(CallbackQueryHandler(stores_command, pattern="^btn_view_stores$"))
    application.add_handler(CallbackQueryHandler(tiktok_command, pattern="^btn_view_tiktok$"))
    application.add_handler(CallbackQueryHandler(manual_remind_button, pattern="^btn_send_reminder$"))
    application.add_handler(CallbackQueryHandler(return_to_main_menu, pattern="^btn_main_menu$"))

    # Global Error Handler
    application.add_error_handler(error_handler)

    # 4. Setup Automated Daily Reminder & Report Jobs
    setup_scheduled_jobs(application)

    print("\n" + "=" * 60)
    print("🚀 Concept Stores Daily Sales Follow-up Bot is RUNNING!")
    print(f"Tracking Stores: WWEG, WW271, WWAE")
    print(f"Timezone: {config.BOT_TIMEZONE}")
    print(f"Press Ctrl+C to stop.")
    print("=" * 60 + "\n")

    # 5. Start Polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
