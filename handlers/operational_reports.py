import logging
import asyncio
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)
import database as db
import reports
from config import BOT_TIMEZONE, REPORT_CHAT_ID, ADMIN_IDS

logger = logging.getLogger(__name__)

# ─── Media-group buffering ────────────────────────────────────────────────────
# Key: media_group_id → {"count": int, "caption": str, "store": dict,
#                         "report_type": str, "type_label": str,
#                         "user_id": int, "user_name": str,
#                         "message": Message, "task": asyncio.Task}
_MEDIA_GROUP_BUFFER: dict = {}
_MEDIA_GROUP_DELAY = 2.0   # seconds to wait before flushing an album
# ─────────────────────────────────────────────────────────────────────────────


async def send_daily_operational_overview(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    thread_id: int | None = None
) -> None:
    """Send clean daily operational overview (no buttons needed, replies accepted)."""
    today_str = datetime.now(BOT_TIMEZONE).strftime("%Y-%m-%d")
    text = reports.format_daily_operational_overview(today_str)

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        message_thread_id=thread_id,
        parse_mode="HTML"
    )


async def link_daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /linkdaily or /settopic daily to bind current topic as Daily Report topic."""
    user = update.effective_user
    if user and ADMIN_IDS and user.id not in ADMIN_IDS:
        await update.effective_message.reply_text("⛔ Only Area Managers can link the Daily Report topic.")
        return

    # Determine thread_id
    explicit_id = None
    if context.args:
        val = context.args[0].strip()
        if val.isdigit():
            explicit_id = int(val)
        elif "/" in val:
            last = val.rstrip("/").split("/")[-1]
            if last.isdigit():
                explicit_id = int(last)

    thread_id = explicit_id or (update.effective_message.message_thread_id if update.effective_message else None)

    if not thread_id:
        await update.effective_message.reply_html(
            "⚠️ <b>របៀបភ្ជាប់ Topic «💡 Daily Report»:</b>\n\n"
            "សូមចូលទៅក្នុង Topic <b>«💡 Daily Report»</b> រួចវាយពាក្យ:\n"
            "<code>/linkdaily</code>\n\n"
            "<i>(ឬវាយ: <code>/linkdaily &lt;Topic_ID&gt;</code>)</i>"
        )
        return

    db.set_daily_report_topic_id(thread_id)
    chat_id = update.effective_chat.id

    await update.effective_message.reply_html(
        f"✅ <b>បានភ្ជាប់ Topic «💡 Daily Report» រួចរាល់!</b>\n"
        f"📌 Thread ID: <code>{thread_id}</code>\n\n"
        f"<i>Bot នឹងតាមដានរាល់ពេល Manager <b>Reply រូបភាព និងចំណាំ</b> លើសាររំលឹក ដើម្បីកត់ត្រាដោយស្វ័យប្រវត្តិ!</i>"
    )

    try:
        await send_daily_operational_overview(context, chat_id=chat_id, thread_id=thread_id)
    except Exception as e:
        logger.error("Error posting initial operational overview: %s", str(e))


async def link_tiktok_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /linktiktok to bind current topic as the official TikTok Video topic."""
    user = update.effective_user
    if user and ADMIN_IDS and user.id not in ADMIN_IDS:
        await update.effective_message.reply_text("⛔ Only Area Managers can link the TikTok topic.")
        return

    explicit_id = None
    if context.args:
        val = context.args[0].strip()
        if val.isdigit():
            explicit_id = int(val)
        elif "/" in val:
            last = val.rstrip("/").split("/")[-1]
            if last.isdigit():
                explicit_id = int(last)

    thread_id = explicit_id or (update.effective_message.message_thread_id if update.effective_message else None)

    if not thread_id:
        await update.effective_message.reply_html(
            "⚠️ <b>របៀបភ្ជាប់ Topic «📱 Tiktok Video»:</b>\n\n"
            "សូមចូលទៅក្នុង Topic <b>«📱 Tiktok Video»</b> រួចវាយពាក្យ:\n"
            "<code>/linktiktok</code>\n\n"
            "<i>(ឬវាយ: <code>/linktiktok &lt;Topic_ID&gt;</code>)</i>"
        )
        return

    db.set_tiktok_topic_id(thread_id)
    chat_id = update.effective_chat.id

    await update.effective_message.reply_html(
        f"✅ <b>បានភ្ជាប់ Topic «📱 Tiktok Video» រួចរាល់!</b>\n"
        f"📌 Thread ID: <code>{thread_id}</code>\n\n"
        f"<i>Bot នឹងតាមដាន និងរំលឹកកាលវិភាគ TikTok (2 វីដេអូ/សប្ដាហ៍) ក្នុង Topic នេះដោយស្វ័យប្រវត្តិ!</i>"
    )

    try:
        overview_text = reports.format_weekly_tiktok_overview()
        await context.bot.send_message(
            chat_id=chat_id,
            text=overview_text,
            message_thread_id=thread_id,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error("Error posting initial tiktok overview: %s", str(e))


def detect_store_from_message(update: Update, text: str) -> dict | None:
    """Detect which store this message belongs to."""
    user = update.effective_user
    username = (user.username or "").strip().lstrip("@").lower()

    # 1. Match by sender's manager username
    if username:
        store = db.get_store_by_manager_username(username)
        if store:
            return store

    # 2. Check if caption or text explicitly mentions store code
    upper_text = text.upper()
    for code in ("WWEG", "WW271", "WWAE", "WWAEON", "WWAEON1", "AEON1"):
        if code in upper_text:
            return db.get_store(code)

    # 3. Check if replying to a bot message that mentions a specific store
    reply_msg = update.effective_message.reply_to_message
    if reply_msg and reply_msg.text:
        reply_upper = reply_msg.text.upper()
        for code in ("WWEG", "WW271", "WWAE", "WWAEON", "WWAEON1"):
            if code in reply_upper:
                return db.get_store(code)

    # 4. Fallback to thread ID if inside a store topic
    thread_id = update.effective_message.message_thread_id if update.effective_message else None
    if thread_id:
        store = db.get_store_by_topic_id(thread_id)
        if store:
            return store

    return None


def extract_date_from_text(text: str) -> str | None:
    """Extract report date from text/caption if explicitly stated by user/manager."""
    if not text:
        return None
    patterns = [
        # YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
        r'(?:Date|ថ្ងៃ)[\s.:=]*([0-9]{4})[-/.]([0-9]{1,2})[-/.]([0-9]{1,2})',
        # DD-MM-YYYY, DD/MM/YYYY, DD.MM.YYYY
        r'(?:Date|ថ្ងៃ)[\s.:=]*([0-9]{1,2})[-/.]([0-9]{1,2})[-/.]([0-9]{4})',
        # DD.MM.YY, DD-MM-YY, DD/MM/YY
        r'(?:Date|ថ្ងៃ)[\s.:=]*([0-9]{1,2})[-/.]([0-9]{1,2})[-/.]([0-9]{2})(?!\d)',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            g1, g2, g3 = m.group(1), m.group(2), m.group(3)
            if len(g1) == 4:
                return f"{g1}-{g2.zfill(2)}-{g3.zfill(2)}"
            elif len(g3) == 4:
                return f"{g3}-{g2.zfill(2)}-{g1.zfill(2)}"
            elif len(g3) == 2:
                year = f"20{g3}"
                return f"{year}-{g2.zfill(2)}-{g1.zfill(2)}"
    return None


def detect_report_type(text: str, store_code: str, target_date: str, message: object = None) -> tuple[str, str]:
    """Detect whether this submission is Briefing, Story & Telegram, or TikTok."""
    lower_text = (text or "").lower()

    # 1. TikTok keywords & links
    tiktok_keywords = ("tiktok", "tik tok", "tik-tok", "vt.tiktok", "vm.tiktok", "tiktok.com", "tt video", "video tiktok", "វីដេអូ tiktok")
    has_video = bool(message and (getattr(message, "video", None) or getattr(message, "video_note", None)))

    if any(k in lower_text for k in tiktok_keywords) or "tiktok.com" in lower_text:
        return "tiktok", "🎬 TikTok Video Report"

    if any(k in lower_text for k in ("briefing", "ប្រជុំ", "meeting", "morning")):
        return "briefing", "🗣️ Briefing Report"

    if any(k in lower_text for k in ("story", "telegram", "channel", "ផុស", "post", "social")):
        return "story_telegram", "📱 Story & Telegram Report"

    if has_video:
        return "tiktok", "🎬 TikTok Video Report"

    # If not explicitly stated in text, check which one is pending for target_date
    status_map = db.get_operational_status_for_date(target_date)
    store_status = status_map.get(store_code, {})

    if not store_status.get("briefing"):
        return "briefing", "🗣️ Briefing Report"
    elif not store_status.get("story_telegram"):
        return "story_telegram", "📱 Story & Telegram Report"
    elif store_status.get("is_tiktok_day") and not store_status.get("tiktok"):
        return "tiktok", "🎬 TikTok Video Report"

    # Fallback based on time of day
    now = datetime.now(BOT_TIMEZONE)
    if now.hour < 12:
        return "briefing", "🗣️ Briefing Report"
    return "story_telegram", "📱 Story & Telegram Report"


async def _flush_media_group(
    mgid: str,
    context: ContextTypes.DEFAULT_TYPE,
    daily_topic_id: int | None,
) -> None:
    """Wait for the album buffer window, then save DB record(s) and one confirmation.

    Standard daily submission = 6 photos: 5 Story + 1 Telegram.
    When count >= 2 the last photo is treated as Telegram, the rest as Story.
    A single photo is saved under the originally detected report type.
    """
    await asyncio.sleep(_MEDIA_GROUP_DELAY)

    buf = _MEDIA_GROUP_BUFFER.pop(mgid, None)
    if not buf:
        return

    photo_count = buf["count"]
    store       = buf["store"]
    user_name   = buf["user_name"]
    user_id     = buf["user_id"]
    caption     = buf["caption"]
    message     = buf["message"]
    today_str   = datetime.now(BOT_TIMEZONE).strftime("%Y-%m-%d")
    report_date = extract_date_from_text(caption) or today_str
    thread_id   = message.message_thread_id

    now_time = datetime.now(BOT_TIMEZONE).strftime("%I:%M %p")

    # ── Split into Story + Telegram when 2+ photos ───────────────────────────
    if photo_count >= 2:
        story_count    = photo_count - 1          # e.g. 5 story
        telegram_count = 1                         # always 1 telegram

        story_note = (
            f"📸 Story ({story_count} សន្លឹក)"
            + (f": {caption}" if caption else "")
        )
        telegram_note = "📸 Telegram (1 សន្លឹក)" + (f": {caption}" if caption else "")

        # Save Story record
        db.save_operational_report(
            store_code=store["code"],
            report_date=report_date,
            report_type="story_telegram",
            notes=story_note,
            user_id=user_id,
            user_name=user_name,
        )
        # Save Telegram record (same type key, distinct note)
        db.save_operational_report(
            store_code=store["code"],
            report_date=report_date,
            report_type="story_telegram",
            notes=telegram_note,
            user_id=user_id,
            user_name=user_name,
        )

        logger.info(
            "Operational report saved (album %s photo(s) → %s story + 1 telegram): store=%s date=%s user=%s",
            photo_count, story_count, store["code"], report_date, user_name,
        )

        photo_line = (
            f"  📷 Story:    {story_count} សន្លឹក\n"
            f"  📲 Telegram: {telegram_count} សន្លឹក"
        )
        type_line = "📱 Story &amp; Telegram Report"

    else:
        # Single photo — use originally detected type
        report_type = buf["report_type"]
        type_label  = buf["type_label"]
        notes_to_save = (
            f"📸 រូបភាព: {caption}" if caption else "📸 បានភ្ជាប់រូបភាពរួចរាល់"
        )
        db.save_operational_report(
            store_code=store["code"],
            report_date=report_date,
            report_type=report_type,
            notes=notes_to_save,
            user_id=user_id,
            user_name=user_name,
        )
        logger.info(
            "Operational report saved (1 photo): store=%s type=%s date=%s user=%s",
            store["code"], report_type, report_date, user_name,
        )
        photo_line = f"  🖼️ {photo_count} សន្លឹក"
        type_line  = type_label

    confirmation_msg = (
        f"✅ <b>បានទទួលរបាយការណ៍ជោគជ័យ! (Already Submitted)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏬 <b>ហាង:</b> {store['code']} ({store['name']})\n"
        f"📅 <b>កាលបរិច្ឆេទ:</b> {report_date}\n"
        f"📋 <b>ប្រភេទ:</b> {type_line}\n"
        f"👤 <b>បញ្ជូនដោយ:</b> {user_name}\n"
        f"🖼️ <b>រូបភាព:</b>\n{photo_line}\n"
        f"🕒 <b>ម៉ោង:</b> {now_time}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🎉 <i>របាយការណ៍ត្រូវបានកត់ត្រាក្នុងប្រព័ន្ធរួចរាល់!</i>"
    )

    try:
        await message.reply_html(confirmation_msg)
    except Exception as e:
        logger.error("Error sending album confirmation: %s", e)

    # Refresh overview in Daily Report topic
    target_chat = REPORT_CHAT_ID if REPORT_CHAT_ID else message.chat_id
    target_thread = daily_topic_id or thread_id
    try:
        await send_daily_operational_overview(context, chat_id=target_chat, thread_id=target_thread)
    except Exception as e:
        logger.error("Error refreshing daily report topic after album: %s", e)


async def handle_operational_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle managers sending pictures (single or album of 5-6) to submit daily reports."""
    message = update.effective_message
    if not message:
        return

    # ── Scope check ───────────────────────────────────────────────────────────
    daily_topic_id = db.get_daily_report_topic_id()
    tiktok_topic_id = db.get_tiktok_topic_id()
    thread_id = message.message_thread_id
    is_daily_topic = bool(daily_topic_id and thread_id == daily_topic_id)
    is_tiktok_topic = bool(tiktok_topic_id and thread_id == tiktok_topic_id)

    reply_to = message.reply_to_message
    is_reply_to_bot = bool(reply_to and reply_to.from_user and reply_to.from_user.is_bot)

    if not (is_daily_topic or is_tiktok_topic or is_reply_to_bot):
        return

    if is_reply_to_bot and not (is_daily_topic or is_tiktok_topic):
        reply_text = (reply_to.text or reply_to.caption or "").lower()
        if not any(k in reply_text for k in ("daily report", "briefing", "story", "telegram", "tiktok", "tik tok", "tt", "ការរំលឹក")):
            return

    # ── Extract content ───────────────────────────────────────────────────────
    caption_or_text = (message.caption or message.text or "").strip()
    has_photo = bool(message.photo)
    has_doc = bool(message.document)
    has_video = bool(message.video or message.video_note)
    has_media = has_photo or has_doc or has_video

    # ── Detect store ──────────────────────────────────────────────────────────
    store = detect_store_from_message(update, caption_or_text)
    if not store:
        if not is_reply_to_bot and not is_tiktok_topic:
            # Manager sent media without replying to the bot's message
            await message.reply_html(
                "⚠️ <b>សូម Reply លើសារ Bot ជាមុនសិន!</b>\n"
                "<i>Please reply on the bot message before submitting.</i>"
            )
        elif is_tiktok_topic:
            await message.reply_html(
                "⚠️ <b>សូមបញ្ជាក់កូដហាង (WWEG, WW271, ឬ WWAE)!</b>\n"
                "<i>Please mention the store code in your message/caption.</i>"
            )
        return

    today_str = datetime.now(BOT_TIMEZONE).strftime("%Y-%m-%d")
    report_date = extract_date_from_text(caption_or_text) or today_str
    if is_tiktok_topic:
        report_type = "tiktok"
        type_label = "🎬 TikTok Video Report"
    else:
        report_type, type_label = detect_report_type(caption_or_text, store["code"], report_date, message=message)
    user = update.effective_user
    user_name = user.full_name if user else "Manager"
    user_id = user.id if user else None

    # ── Media group (album) handling ──────────────────────────────────────────
    mgid = message.media_group_id  # None for single photos / text

    if mgid and has_media:
        if mgid not in _MEDIA_GROUP_BUFFER:
            _MEDIA_GROUP_BUFFER[mgid] = {
                "count": 1,
                "caption": caption_or_text,
                "store": store,
                "report_type": report_type,
                "type_label": type_label,
                "user_id": user_id,
                "user_name": user_name,
                "message": message,
                "task": None,
            }
            task = asyncio.create_task(
                _flush_media_group(mgid, context, daily_topic_id)
            )
            _MEDIA_GROUP_BUFFER[mgid]["task"] = task
        else:
            _MEDIA_GROUP_BUFFER[mgid]["count"] += 1
            if not _MEDIA_GROUP_BUFFER[mgid]["caption"] and caption_or_text:
                _MEDIA_GROUP_BUFFER[mgid]["caption"] = caption_or_text
        return

    # ── Single photo / video / text (no media_group_id) ───────────────────────
    if report_type == "tiktok":
        if has_video:
            notes_to_save = f"🎬 វីដេអូ: {caption_or_text}" if caption_or_text else "🎬 បានភ្ជាប់វីដេអូ TikTok រួចរាល់"
        elif has_media:
            notes_to_save = f"📸 ភស្តុតាង: {caption_or_text}" if caption_or_text else "📸 បានភ្ជាប់ភស្តុតាង TikTok"
        else:
            notes_to_save = caption_or_text or "បានបញ្ជូន Link TikTok"
    else:
        if has_media and caption_or_text:
            notes_to_save = f"📸 រូបភាព: {caption_or_text}"
        elif has_media:
            notes_to_save = "📸 បានភ្ជាប់រូបភាពរួចរាល់"
        else:
            notes_to_save = caption_or_text or "បានបញ្ជូនតាមសារ"

    db.save_operational_report(
        store_code=store["code"],
        report_date=report_date,
        report_type=report_type,
        notes=notes_to_save,
        user_id=user_id,
        user_name=user_name,
    )

    logger.info(
        "Operational report saved: store=%s type=%s date=%s user=%s",
        store["code"], report_type, report_date, user_name,
    )

    now_time = datetime.now(BOT_TIMEZONE).strftime("%I:%M %p")

    if report_type == "tiktok":
        week_count = db.get_tiktok_count_for_week(store["code"], report_date)
        confirmation_msg = (
            f"✅ <b>បានទទួល TikTok Video ជោគជ័យ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🏬 <b>ហាង:</b> {store['code']} ({store['name']})\n"
            f"📅 <b>កាលបរិច្ឆេទ:</b> {report_date}\n"
            f"🎬 <b>ប្រភេទ:</b> 🎬 TikTok Video (គោលដៅ 2 វីដេអូ/សប្ដាហ៍)\n"
            f"👤 <b>បញ្ជូនដោយ:</b> {user_name}\n"
            f"🕒 <b>ម៉ោង:</b> {now_time}\n"
            f"🔗 <b>ចំណាំ/Link:</b> <i>{notes_to_save}</i>\n"
            f"📊 <b>វឌ្ឍនភាពសប្ដាហ៍នេះ:</b> <b>{week_count}/2 វីដេអូ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🎉 <i>TikTok Video ត្រូវបានកត់ត្រាក្នុងប្រព័ន្ធរួចរាល់!</i>"
        )
    else:
        confirmation_msg = (
            f"✅ <b>បានទទួលរបាយការណ៍ជោគជ័យ! (Already Submitted)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🏬 <b>ហាង:</b> {store['code']} ({store['name']})\n"
            f"📅 <b>កាលបរិច្ឆេទ:</b> {report_date}\n"
            f"📋 <b>ប្រភេទ:</b> {type_label}\n"
            f"👤 <b>បញ្ជូនដោយ:</b> {user_name}\n"
            f"🕒 <b>ម៉ោង:</b> {now_time}\n"
            f"📝 <b>ចំណាំ:</b> <i>{notes_to_save}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🎉 <i>របាយការណ៍ត្រូវបានកត់ត្រាក្នុងប្រព័ន្ធរួចរាល់!</i>"
        )

    await message.reply_html(confirmation_msg)

    target_chat = REPORT_CHAT_ID if REPORT_CHAT_ID else update.effective_chat.id
    target_thread = daily_topic_id or thread_id
    try:
        await send_daily_operational_overview(context, chat_id=target_chat, thread_id=target_thread)
    except Exception as e:
        logger.error("Error refreshing daily report topic: %s", str(e))


async def tiktok_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /tiktok command — view weekly TikTok dashboard or log a TikTok submission."""
    message = update.effective_message
    if not message:
        return

    today_str = datetime.now(BOT_TIMEZONE).strftime("%Y-%m-%d")
    args = context.args

    if args:
        full_arg_text = " ".join(args).strip()
        store = detect_store_from_message(update, full_arg_text)
        if not store:
            await message.reply_html(
                "⚠️ <b>មិនស្គាល់ហាង!</b>\n"
                "សូមបញ្ជាក់កូដហាង ឧទាហរណ៍:\n"
                "<code>/tiktok WWEG https://vt.tiktok.com/...</code>"
            )
            return

        user = update.effective_user
        user_name = user.full_name if user else "Manager"
        user_id = user.id if user else None

        db.save_operational_report(
            store_code=store["code"],
            report_date=today_str,
            report_type="tiktok",
            notes=full_arg_text,
            user_id=user_id,
            user_name=user_name,
        )

        week_count = db.get_tiktok_count_for_week(store["code"], today_str)
        now_time = datetime.now(BOT_TIMEZONE).strftime("%I:%M %p")

        confirm_text = (
            f"✅ <b>បានកត់ត្រា TikTok Video ជោគជ័យ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🏬 <b>ហាង:</b> {store['code']} ({store['name']})\n"
            f"📅 <b>កាលបរិច្ឆេទ:</b> {today_str}\n"
            f"🎬 <b>ប្រភេទ:</b> 🎬 TikTok Video Report (2 វីដេអូ/សប្ដាហ៍)\n"
            f"👤 <b>បញ្ជូនដោយ:</b> {user_name}\n"
            f"🕒 <b>ម៉ោង:</b> {now_time}\n"
            f"🔗 <b>Link/Note:</b> <i>{full_arg_text}</i>\n"
            f"📊 <b>វឌ្ឍនភាពសប្ដាហ៍នេះ:</b> <b>{week_count}/2 វីដេអូ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
        await message.reply_html(confirm_text)

        daily_topic_id = db.get_daily_report_topic_id()
        if daily_topic_id:
            try:
                await send_daily_operational_overview(context, chat_id=REPORT_CHAT_ID or message.chat_id, thread_id=daily_topic_id)
            except Exception as e:
                logger.error("Error refreshing daily report topic: %s", e)
        return

    text = reports.format_weekly_tiktok_overview(today_str)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 ធ្វើបច្ចុប្បន្នភាព", callback_data="btn_view_tiktok"),
            InlineKeyboardButton("📋 Daily Report", callback_data="btn_view_today"),
        ],
        [
            InlineKeyboardButton("« ត្រឡប់ទៅមេនុ", callback_data="btn_main_menu"),
        ]
    ])

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message.reply_html(text=text, reply_markup=keyboard)

