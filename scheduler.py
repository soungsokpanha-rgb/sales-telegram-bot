import logging
from datetime import datetime, time, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db
import reports
from config import (
    REPORT_CHAT_ID,
    BOT_TIMEZONE,
    FORM_DROP_TIME,
    REMINDER_1,
    REMINDER_2,
    RECAP_TIME,
)

logger = logging.getLogger(__name__)


def parse_time_string(time_str: str, tz=BOT_TIMEZONE) -> time:
    """Parse 'HH:MM' string into datetime.time object with timezone."""
    try:
        parts = time_str.split(":")
        return time(hour=int(parts[0]), minute=int(parts[1]), tzinfo=tz)
    except Exception:
        return time(hour=21, minute=0, tzinfo=tz)


async def send_morning_form_for_store(context: ContextTypes.DEFAULT_TYPE, store: dict) -> bool:
    """Send the 8:00 AM daily sales form to a store's topic (Khmer)."""
    if not REPORT_CHAT_ID:
        return False

    code = store["code"]
    name = store["name"]
    mgr = (store.get("manager_username") or "").strip()
    mgr_tag = f"@{mgr.lstrip('@')}" if mgr else "Manager"
    topic_id = store.get("topic_id")

    now_dt = datetime.now(BOT_TIMEZONE)
    today_display = now_dt.strftime("%d-%m-%Y")
    today_day_khmer = now_dt.strftime("%A, %d %b %Y")

    text = (
        f"📊 <b>របាយការណ៍លក់ប្រចាំថ្ងៃ — DAILY SALE REPORT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏬 <b>ហាង:</b> {code} ({name})\n"
        f"👤 <b>Manager:</b> {mgr_tag}\n"
        f"📅 <b>កាលបរិច្ឆេទ:</b> {today_day_khmer}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 <b>របៀបបញ្ជូនរបាយការណ៍:</b>\n"
        f"1️⃣ ចុចលើប្រអប់ខាងក្រោមដើម្បី <b>Copy ទម្រង់ (Tap to copy)</b>\n"
        f"2️⃣ ចុច <b>Reply (ឆ្លើយតប)</b> លើសារនេះ រួច Paste\n"
        f"3️⃣ បំពេញលេខ <b>Target</b> & <b>Actual</b> រួចផ្ញើមកវិញ!\n\n"
        f"<pre>- Sale Report\n"
        f".Date: {today_display}\n"
        f".Store: {code}\n"
        f".Daily Sale Target: \n"
        f".Actual Sale: \n\n"
        f"Need or Support: </pre>"
    )

    await context.bot.send_message(
        chat_id=REPORT_CHAT_ID,
        text=text,
        message_thread_id=topic_id,
        parse_mode="HTML"
    )
    return True


async def send_morning_forms(context: ContextTypes.DEFAULT_TYPE, force: bool = False) -> None:
    """Scheduled job (08:00 AM): Drop daily sales form into each store topic."""
    if not REPORT_CHAT_ID:
        logger.warning("REPORT_CHAT_ID not configured; cannot send morning forms.")
        return

    today_str = datetime.now(BOT_TIMEZONE).strftime("%Y-%m-%d")
    last_drop = db.get_setting("last_morning_drop_date")
    if not force and last_drop == today_str:
        logger.info("Morning forms have already been dropped today (%s). Skipping duplicate drop.", today_str)
        return

    stores = db.get_all_stores(active_only=True)
    for st in stores:
        try:
            await send_morning_form_for_store(context, st)
            logger.info("Sent morning form for store %s to topic_id %s", st["code"], st.get("topic_id"))
        except Exception as e:
            logger.error("Failed to send morning form for %s (topic %s): %s", st["code"], st.get("topic_id"), str(e))

    db.set_setting("last_morning_drop_date", today_str)

    # TikTok morning prompt for store(s) scheduled today
    today_dt = datetime.now(BOT_TIMEZONE)
    today_weekday = today_dt.weekday()
    for st in stores:
        code = st["code"]
        if today_weekday in config.TIKTOK_SCHEDULE.get(code, []):
            topic_id = st.get("topic_id")
            mgr = (st.get("manager_username") or "").strip()
            mgr_tag = f"@{mgr.lstrip('@')}" if mgr else "Manager"
            wday_kh = config.WEEKDAY_NAMES_KH[today_weekday]

            tiktok_notice = (
                f"🎬 <b>កាតព្វកិច្ច TIKTOK ថ្ងៃនេះ — {code}!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏬 <b>ហាង:</b> {code} ({st['name']})\n"
                f"👤 <b>Manager:</b> {mgr_tag}\n"
                f"📅 <b>កាលវិភាគ:</b> ថ្ងៃ{wday_kh} ({today_dt.strftime('%d-%m-%Y')})\n\n"
                f"📌 <b>កិច្ចការ:</b> ថ្ងៃនេះជាវេនរបស់ហាង <b>{code}</b> ក្នុងការផុស TikTok Video!\n"
                f"🎯 <b>គោលដៅ:</b> 2 វីដេអូ / ហាង / សប្ដាហ៍\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👉 <i>សូម Manager <b>Reply (ឆ្លើយតប)</b> លើសារនេះ ជាមួយ <b>Link TikTok</b> ឬ <b>វីដេអូ</b> នៅពេលផុសរួចរាល់!</i>"
            )

            if topic_id:
                try:
                    await context.bot.send_message(
                        chat_id=REPORT_CHAT_ID,
                        text=tiktok_notice,
                        message_thread_id=topic_id,
                        parse_mode="HTML"
                    )
                    logger.info("Sent morning TikTok prompt for %s (topic %s)", code, topic_id)
                except Exception as e:
                    logger.error("Failed to send morning TikTok prompt for %s: %s", code, str(e))

    # Also drop Daily Operational Overview into "Daily Report" topic if linked
    daily_topic_id = db.get_daily_report_topic_id()
    last_op_drop = db.get_setting("last_operational_drop_date")
    if daily_topic_id and (force or last_op_drop != today_str):
        try:
            from handlers.operational_reports import send_daily_operational_overview
            await send_daily_operational_overview(context, chat_id=REPORT_CHAT_ID, thread_id=daily_topic_id)
            db.set_setting("last_operational_drop_date", today_str)
            logger.info("Sent daily operational report overview to topic %s", daily_topic_id)
        except Exception as e:
            logger.error("Failed to send operational overview to topic %s: %s", daily_topic_id, str(e))

    # Also drop weekly TikTok dashboard into "📱 Tiktok Video" topic if linked
    tiktok_topic_id = db.get_tiktok_topic_id()
    if tiktok_topic_id:
        try:
            tt_overview = reports.format_weekly_tiktok_overview()
            await context.bot.send_message(
                chat_id=REPORT_CHAT_ID,
                text=tt_overview,
                message_thread_id=tiktok_topic_id,
                parse_mode="HTML"
            )
            logger.info("Sent weekly TikTok dashboard to topic %s", tiktok_topic_id)
        except Exception as e:
            logger.error("Failed to send weekly TikTok dashboard to topic %s: %s", tiktok_topic_id, str(e))


async def send_scheduled_missing_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled job (Remind 2x daily): Send Khmer follow-up reminder to pending store topics."""
    if not REPORT_CHAT_ID:
        logger.warning("REPORT_CHAT_ID not configured; skipping scheduled missing reminder.")
        return

    today_str = datetime.now(BOT_TIMEZONE).strftime("%Y-%m-%d")
    missing = db.get_missing_stores(today_str)

    if missing:
        # 1. Post reminder directly into each missing store's topic
        for st in missing:
            code = st["code"]
            name = st["name"]
            topic_id = st.get("topic_id")
            mgr = (st.get("manager_username") or "").strip()
            mgr_tag = f"@{mgr.lstrip('@')}" if mgr else "Manager"

            now_dt = datetime.now(BOT_TIMEZONE)
            today_display = now_dt.strftime("%d-%m-%Y")

            topic_reminder = (
                f"⚠️ <b>ការរំលឹក — ការលក់ប្រចាំថ្ងៃ</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏬 <b>ហាង:</b> {code} ({name})\n"
                f"👤 <b>Manager:</b> {mgr_tag}\n\n"
                f"🚨 <b>ការប្រាស្រ័យ:</b> របាយការណ៍លក់ថ្ងៃនេះ <b>មិនទាន់បានទទួលនៅឡើយ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📋 <b>របៀបបញ្ជូនរបាយការណ៍:</b>\n"
                f"1️⃣ ចុចលើប្រអប់ខាងក្រោមដើម្បី <b>Copy ទម្រង់ (Tap to copy)</b>\n"
                f"2️⃣ ចុច <b>Reply (ឆ្លើយតប)</b> លើសារនេះ រួច Paste\n"
                f"3️⃣ បំពេញលេខ <b>Target</b> & <b>Actual</b> រួចផ្ញើមកវិញ!\n\n"
                f"<pre>- Sale Report\n"
                f".Date: {today_display}\n"
                f".Store: {code}\n"
                f".Daily Sale Target: \n"
                f".Actual Sale: \n\n"
                f"Need or Support: </pre>"
            )

            if topic_id:
                try:
                    await context.bot.send_message(
                        chat_id=REPORT_CHAT_ID,
                        text=topic_reminder,
                        message_thread_id=topic_id,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error("Error sending topic reminder for %s: %s", code, str(e))

        # 2. Send overall missing summary to Area Manager (main group)
        alert_text = reports.format_missing_alert(today_str)
        try:
            await context.bot.send_message(
                chat_id=REPORT_CHAT_ID,
                text=alert_text,
                parse_mode="HTML"
            )
            logger.info("Dispatched overall missing reminder for %d stores", len(missing))
        except Exception as e:
            logger.error("Error sending general missing reminder: %s", str(e))

    # 3. Check and remind missing operational reports in "Daily Report" topic
    daily_topic_id = db.get_daily_report_topic_id()
    if daily_topic_id:
        try:
            op_alert = reports.format_missing_operational_reminder(today_str)
            if op_alert:
                await context.bot.send_message(
                    chat_id=REPORT_CHAT_ID,
                    text=op_alert,
                    message_thread_id=daily_topic_id,
                    parse_mode="HTML"
                )
                logger.info("Dispatched missing operational reminder to topic %s", daily_topic_id)
        except Exception as e:
            logger.error("Error sending operational reminder to topic %s: %s", daily_topic_id, str(e))

    # 4. Check if today's scheduled TikTok stores haven't submitted yet, remind in store topic
    op_status = db.get_operational_status_for_date(today_str)
    for code, info in op_status.items():
        if info.get("is_tiktok_day") and not info.get("tiktok"):
            st = db.get_store(code)
            topic_id = st.get("topic_id") if st else None
            if topic_id:
                mgr = (info.get("manager_username") or "").strip()
                mgr_tag = f"@{mgr.lstrip('@')}" if mgr else "Manager"
                tt_remind = (
                    f"⚠️ <b>ការរំលឹក — 🎬 TIKTOK VIDEO នៅខ្វះ!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🏬 <b>ហាង:</b> {code} ({info['store_name']})\n"
                    f"👤 <b>Manager:</b> {mgr_tag}\n\n"
                    f"🚨 <b>កាលវិភាគថ្ងៃនេះ:</b> វីដេអូ TikTok របស់ហាង <b>មិនទាន់បានទទួលនៅឡើយ!</b>\n"
                    f"🎯 <b>គោលដៅ:</b> 2 វីដេអូ / សប្ដាហ៍\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👉 <i>សូម Manager <b>Reply (ឆ្លើយតប)</b> លើសារនេះ ជាមួយ <b>Link TikTok</b> ឬ <b>វីដេអូ</b>!</i>"
                )
                try:
                    await context.bot.send_message(
                        chat_id=REPORT_CHAT_ID,
                        text=tt_remind,
                        message_thread_id=topic_id,
                        parse_mode="HTML"
                    )
                    logger.info("Sent TikTok missing reminder to topic for %s", code)
                except Exception as e:
                    logger.error("Error sending TikTok missing reminder for %s: %s", code, str(e))

    # 5. Also send missing reminder directly to "📱 Tiktok Video" topic if linked
    tiktok_topic_id = db.get_tiktok_topic_id()
    if tiktok_topic_id:
        missing_stores_today = [
            f"• <b>{c}</b> ({inf['store_name']})"
            for c, inf in op_status.items()
            if inf.get("is_tiktok_day") and not inf.get("tiktok")
        ]
        if missing_stores_today:
            tt_topic_alert = (
                f"⚠️ <b>ការរំលឹក — 🎬 TIKTOK VIDEO នៅខ្វះថ្ងៃនេះ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"ហាងខាងក្រោមមានកាតព្វកិច្ចផុស TikTok ថ្ងៃនេះ ប៉ុន្តែមិនទាន់បានទទួលនៅឡើយ:\n\n"
                + "\n".join(missing_stores_today) + "\n\n"
                f"👉 <i>សូម Manager <b>ផ្ញើ Link TikTok ឬ វីដេអូ</b> ក្នុង Topic នេះដើម្បីបញ្ជូន!</i>"
            )
            try:
                await context.bot.send_message(
                    chat_id=REPORT_CHAT_ID,
                    text=tt_topic_alert,
                    message_thread_id=tiktok_topic_id,
                    parse_mode="HTML"
                )
                logger.info("Sent TikTok reminder to TikTok topic %s", tiktok_topic_id)
            except Exception as e:
                logger.error("Error sending TikTok reminder to TikTok topic: %s", str(e))


async def send_scheduled_daily_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled job (00:00 midnight): Send Khmer consolidated closing recap."""
    if not REPORT_CHAT_ID:
        logger.warning("REPORT_CHAT_ID not configured; skipping midnight recap.")
        return

    now = datetime.now(BOT_TIMEZONE)
    if now.hour < 3:
        report_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        report_date = now.strftime("%Y-%m-%d")

    report_text = reports.format_daily_summary(report_date)

    try:
        await context.bot.send_message(
            chat_id=REPORT_CHAT_ID,
            text=f"🌙 <b>សង្ខេបការបិទហាង — ម៉ោង 12:00 យប់</b>\n\n{report_text}",
            parse_mode="HTML"
        )
        logger.info("Dispatched midnight closing recap for date %s", report_date)
    except Exception as e:
        logger.error("Error sending midnight closing report: %s", str(e))


async def on_startup_check(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Autonomous startup check (runs 3s after bot launch).
    Safely verifies if the scheduled 08:00 AM morning drop was missed due to bot downtime.
    Prevents duplicate drops upon bot restarts or crashes.
    """
    if not REPORT_CHAT_ID:
        return

    now = datetime.now(BOT_TIMEZONE)
    today_str = now.strftime("%Y-%m-%d")
    morning_time = parse_time_string(FORM_DROP_TIME)

    # 1. If starting BEFORE morning drop time (e.g. before 08:00 AM),
    # do NOT drop forms yet — the scheduled daily job will fire at 08:00 AM.
    if now.time() < morning_time:
        logger.info("Startup before %s: scheduled morning drop will run on schedule.", FORM_DROP_TIME)
        return

    # 2. If already dropped today, skip completely to prevent restart duplicate drops
    last_drop = db.get_setting("last_morning_drop_date")
    if last_drop == today_str:
        logger.info("Morning forms were already dropped today (%s). Skipping startup drop.", today_str)
        return

    # 3. If bot was offline during 08:00 AM and started during morning hours (before 12:00 PM),
    # catch up by dropping the morning forms once.
    if now.hour < 12:
        logger.info("Startup catch-up: Missed morning form drop during downtime. Dispatching for %s...", today_str)
        await send_morning_forms(context, force=False)
    else:
        logger.info("Bot started after 12:00 PM; skipping morning form catch-up for %s.", today_str)


def setup_scheduled_jobs(application) -> None:
    """Register all recurring daily jobs in the bot's JobQueue."""
    job_queue = application.job_queue
    if not job_queue:
        logger.warning("JobQueue is not available in Application.")
        return

    # 0. Autonomous Startup Check (Runs 3 seconds after bot launch)
    job_queue.run_once(on_startup_check, when=3, name="startup_auto_dispatch")
    logger.info("Autonomous startup check scheduled (3s after launch).")

    # 1. Morning Form Drop (08:00 AM)
    morning_time = parse_time_string(FORM_DROP_TIME)
    job_queue.run_daily(
        send_morning_forms,
        time=morning_time,
        days=(0, 1, 2, 3, 4, 5, 6),
        name="morning_sales_forms_drop"
    )
    logger.info("Scheduled morning form drop at %s %s", FORM_DROP_TIME, BOT_TIMEZONE)

    # 2. Reminder 1: Afternoon follow-up (14:00 / 2:00 PM)
    remind1_time = parse_time_string(REMINDER_1)
    job_queue.run_daily(
        send_scheduled_missing_reminder,
        time=remind1_time,
        days=(0, 1, 2, 3, 4, 5, 6),
        name="afternoon_missing_reminder_1"
    )
    logger.info("Scheduled 1st reminder at %s %s", REMINDER_1, BOT_TIMEZONE)

    # 3. Reminder 2: Evening pre-closing follow-up (21:00 / 9:00 PM)
    remind2_time = parse_time_string(REMINDER_2)
    job_queue.run_daily(
        send_scheduled_missing_reminder,
        time=remind2_time,
        days=(0, 1, 2, 3, 4, 5, 6),
        name="evening_closing_reminder_2"
    )
    logger.info("Scheduled 2nd reminder at %s %s", REMINDER_2, BOT_TIMEZONE)

    # 4. Nightly Consolidated Recap at 12:00 AM Midnight (00:00)
    recap_time = parse_time_string(RECAP_TIME)
    job_queue.run_daily(
        send_scheduled_daily_report,
        time=recap_time,
        days=(0, 1, 2, 3, 4, 5, 6),
        name="midnight_consolidated_recap"
    )
    logger.info("Scheduled 12:00 AM midnight recap at %s %s", RECAP_TIME, BOT_TIMEZONE)
