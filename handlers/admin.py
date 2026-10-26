from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db
import reports
from config import ADMIN_IDS, REPORT_CHAT_ID, BOT_TIMEZONE


def is_user_authorized(user_id: int) -> bool:
    """Check if user has admin privileges. If ADMIN_IDS is empty, allow all."""
    if not ADMIN_IDS:
        return True
    return user_id in ADMIN_IDS


async def settarget_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /settarget <STORE> <AMOUNT> command."""
    user = update.effective_user
    if user and not is_user_authorized(user.id):
        await update.message.reply_text("⛔ You are not authorized to change store targets.")
        return

    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_html(
            "⚠️ <b>Usage:</b> <code>/settarget &lt;STORE_CODE&gt; &lt;NEW_AMOUNT&gt;</code>\n"
            "Example: <code>/settarget WWEG 1500</code>\n"
            "Valid Store Codes: <b>WWEG</b>, <b>WW271</b>, <b>WWAE</b>"
        )
        return

    store_code = args[0].upper().strip()
    amount_str = args[1].replace("$", "").replace(",", "").strip()

    try:
        new_target = float(amount_str)
        if new_target <= 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid positive target amount.")
        return

    store = db.get_store(store_code)
    if not store:
        await update.message.reply_text(f"❌ Store code '{store_code}' not found. Please choose from WWEG, WW271, or WWAE.")
        return

    success = db.update_store_target(store_code, new_target)
    if success:
        await update.message.reply_html(
            f"✅ <b>Default Target Updated!</b>\n\n"
            f"🏬 Store: <b>{store_code}</b> ({store['name']})\n"
            f"🎯 New Target: <code>{reports.format_currency(new_target)}</code> / day"
        )
    else:
        await update.message.reply_text("❌ Failed to update store target.")


async def setmanager_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /setmanager <STORE> <@USERNAME> command."""
    user = update.effective_user
    if user and not is_user_authorized(user.id):
        await update.message.reply_text("⛔ You are not authorized to assign store managers.")
        return

    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_html(
            "⚠️ <b>Usage:</b> <code>/setmanager &lt;STORE_CODE&gt; &lt;@USERNAME&gt;</code>\n"
            "Example: <code>/setmanager WWEG @sarah_manager</code>\n"
            "Valid Store Codes: <b>WWEG</b>, <b>WW271</b>, <b>WWAE</b>"
        )
        return

    store_code = args[0].upper().strip()
    manager_username = args[1].strip()

    store = db.get_store(store_code)
    if not store:
        await update.message.reply_text(f"❌ Store code '{store_code}' not found. Please choose from WWEG, WW271, or WWAE.")
        return

    success = db.update_store_manager(store_code, manager_username)
    if success:
        clean_user = manager_username.lstrip("@")
        await update.message.reply_html(
            f"✅ <b>Store Manager Assigned!</b>\n\n"
            f"🏬 Store: <b>{store_code}</b> ({store['name']})\n"
            f"👤 Manager Username: <b>@{clean_user}</b>\n\n"
            f"<i>This manager will now be tagged in follow-up reminders.</i>"
        )
    else:
        await update.message.reply_text("❌ Failed to update store manager.")


async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /remind command - Trigger immediate follow-up alert to pending stores."""
    user = update.effective_user
    if user and not is_user_authorized(user.id):
        await update.message.reply_text("⛔ Only Area Managers can trigger reminders.")
        return

    today_str = datetime.now(BOT_TIMEZONE).strftime("%Y-%m-%d")
    alert_text = reports.format_missing_alert(today_str)

    target_chat = REPORT_CHAT_ID if REPORT_CHAT_ID else update.effective_chat.id
    try:
        await context.bot.send_message(
            chat_id=target_chat,
            text=alert_text,
            parse_mode="HTML"
        )
        if update.effective_chat.id != target_chat:
            await update.message.reply_text(f"✅ Follow-up alert dispatched to target chat: {target_chat}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error sending reminder: {str(e)}")


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send an urgent announcement to the Area Manager channel / group."""
    user = update.effective_user
    if user and not is_user_authorized(user.id):
        await update.message.reply_text("⛔ Only Area Managers can send announcements.")
        return

    if not context.args:
        await update.message.reply_html("⚠️ <b>Usage:</b> <code>/broadcast &lt;Your message here&gt;</code>")
        return

    if not REPORT_CHAT_ID:
        await update.message.reply_text("⚠️ REPORT_CHAT_ID is not configured in .env.")
        return

    broadcast_text = " ".join(context.args)
    full_message = (
        f"📢 <b>AREA MANAGER ANNOUNCEMENT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{broadcast_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Sent by: <i>{user.full_name}</i>"
    )

    try:
        await context.bot.send_message(chat_id=REPORT_CHAT_ID, text=full_message, parse_mode="HTML")
        await update.message.reply_text("✅ Announcement broadcasted successfully!")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to broadcast: {str(e)}")


async def settopic_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Link current forum topic to a specific store."""
    user = update.effective_user
    if user and not is_user_authorized(user.id):
        await update.effective_message.reply_text("⛔ Only Area Managers can link topics.")
        return

    args = context.args

    # Check if thread_id is passed explicitly e.g. /settopic WWEG 123 or /settopic WWEG https://t.me/...
    explicit_id = None
    if args and len(args) >= 2:
        val = args[1].strip()
        if val.isdigit():
            explicit_id = int(val)
        elif "/" in val:
            last = val.rstrip("/").split("/")[-1]
            if last.isdigit():
                explicit_id = int(last)

    thread_id = explicit_id or (update.effective_message.message_thread_id if update.effective_message else None)

    if not thread_id:
        await update.effective_message.reply_html(
            "⚠️ <b>How to link a Store Topic:</b>\n\n"
            "<b>Option 1 (Easiest):</b> Open the store topic tab (e.g. <b>WWEG</b>) and type:\n"
            "<code>/settopic WWEG</code>\n\n"
            "<b>Option 2:</b> Right-click the topic -> Copy Link -> type:\n"
            "<code>/settopic WWEG &lt;paste link&gt;</code>\n\n"
            "<b>Option 3:</b> If you know the Topic ID:\n"
            "<code>/settopic WWEG &lt;ID&gt;</code>"
        )
        return

    # If no store specified, show quick buttons for the 3 stores + Daily Report!
    if not args or (explicit_id and len(args) < 1):
        buttons = [
            [
                InlineKeyboardButton("🏬 Link to WWEG", callback_data=f"link_topic_WWEG_{thread_id}"),
                InlineKeyboardButton("🏬 Link to WW271", callback_data=f"link_topic_WW271_{thread_id}"),
            ],
            [
                InlineKeyboardButton("🏬 Link to WWAEON1", callback_data=f"link_topic_WWAE_{thread_id}"),
                InlineKeyboardButton("💡 Link as Daily Report", callback_data=f"link_topic_DAILY_{thread_id}"),
            ],
            [
                InlineKeyboardButton("📱 Link as Tiktok Video", callback_data=f"link_topic_TIKTOK_{thread_id}"),
            ]
        ]
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"🔗 <b>LINK THIS TOPIC</b> (Topic ID: <code>{thread_id}</code>)\n\nWhich store or function belongs to this topic?",
            reply_markup=InlineKeyboardMarkup(buttons),
            message_thread_id=thread_id,
            parse_mode="HTML"
        )
        return

    first_arg = args[0].upper().strip()
    if first_arg in ("TIKTOK", "TT", "TIKTOK_VIDEO", "TIKTOKVIDEO"):
        db.set_tiktok_topic_id(thread_id)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"✅ <b>TOPIC «📱 TIKTOK VIDEO» LINKED!</b>\n\n"
                f"📌 Topic ID: <code>{thread_id}</code>\n\n"
                f"⏰ Automated follow-ups for <b>TikTok Video</b> (2 videos/store/week) will run right here!"
            ),
            message_thread_id=thread_id,
            parse_mode="HTML"
        )
        overview_text = reports.format_weekly_tiktok_overview()
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=overview_text,
            message_thread_id=thread_id,
            parse_mode="HTML"
        )
        return

    if first_arg in ("DAILY", "DAILY_REPORT", "DAILYREPORT"):
        db.set_daily_report_topic_id(thread_id)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"✅ <b>TOPIC «💡 DAILY REPORT» LINKED!</b>\n\n"
                f"📌 Topic ID: <code>{thread_id}</code>\n\n"
                f"⏰ Automated follow-ups for <b>Briefing</b> and <b>Story & Telegram</b> will run right here!"
            ),
            message_thread_id=thread_id,
            parse_mode="HTML"
        )
        from handlers.operational_reports import send_daily_operational_overview
        await send_daily_operational_overview(context, chat_id=update.effective_chat.id, thread_id=thread_id)
        return

    store_code = first_arg
    store = db.get_store(store_code)
    if not store:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Store code '{store_code}' not found. Choose from <b>WWEG</b>, <b>WW271</b>, <b>WWAEON1</b>, or <b>DAILY</b>.",
            message_thread_id=thread_id,
            parse_mode="HTML"
        )
        return

    db.update_store_topic(store["code"], thread_id)
    store["topic_id"] = thread_id
    mgr = store.get("manager_username", "")
    mgr_str = f"👤 Manager: <b>@{mgr.lstrip('@')}</b>\n" if mgr else ""

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"✅ <b>TOPIC SUCCESSFULLY LINKED!</b>\n\n"
            f"🏬 Store: <b>{store['code']}</b> ({store['name']})\n"
            f"{mgr_str}"
            f"📌 Topic ID: <code>{thread_id}</code>\n\n"
            f"⏰ <b>Every morning at 08:00 AM</b>, the Daily Sales Form will be dropped right here!\n"
            f"👇 <i>Dropping today's form below:</i>"
        ),
        message_thread_id=thread_id,
        parse_mode="HTML"
    )
    from scheduler import send_morning_form_for_store
    await send_morning_form_for_store(context, store)


async def link_topic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button click to link topic."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    store_code = parts[2]
    thread_id = int(parts[3])

    if store_code == "DAILY":
        db.set_daily_report_topic_id(thread_id)
        await query.edit_message_text(
            f"✅ <b>TOPIC «💡 DAILY REPORT» LINKED!</b>\n\n"
            f"📌 Topic ID: <code>{thread_id}</code>\n\n"
            f"⏰ Automated follow-ups for <b>Briefing</b> and <b>Story & Telegram</b> will run right here!",
            parse_mode="HTML"
        )
        from handlers.operational_reports import send_daily_operational_overview
        await send_daily_operational_overview(context, chat_id=update.effective_chat.id, thread_id=thread_id)
        return

    if store_code == "TIKTOK":
        db.set_tiktok_topic_id(thread_id)
        await query.edit_message_text(
            f"✅ <b>TOPIC «📱 TIKTOK VIDEO» LINKED!</b>\n\n"
            f"📌 Topic ID: <code>{thread_id}</code>\n\n"
            f"⏰ Automated follow-ups for <b>TikTok Video</b> (2 videos/store/week) will run right here!",
            parse_mode="HTML"
        )
        overview_text = reports.format_weekly_tiktok_overview()
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=overview_text,
            message_thread_id=thread_id,
            parse_mode="HTML"
        )
        return

    store = db.get_store(store_code)
    if not store:
        await query.edit_message_text(f"❌ Store '{store_code}' not found.")
        return

    db.update_store_topic(store["code"], thread_id)
    store["topic_id"] = thread_id
    mgr = store.get("manager_username", "")
    mgr_str = f"👤 Manager: <b>@{mgr.lstrip('@')}</b>\n" if mgr else ""

    await query.edit_message_text(
        f"✅ <b>TOPIC SUCCESSFULLY LINKED!</b>\n\n"
        f"🏬 Store: <b>{store['code']}</b> ({store['name']})\n"
        f"{mgr_str}"
        f"📌 Topic ID: <code>{thread_id}</code>\n\n"
        f"⏰ <b>Every morning at 08:00 AM</b>, the Daily Sales Form will be dropped right here!\n"
        f"👇 <i>Dropping today's form below:</i>",
        parse_mode="HTML"
    )
    from scheduler import send_morning_form_for_store
    await send_morning_form_for_store(context, store)


async def dropforms_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually drop the morning sales forms into each store topic right now."""
    user = update.effective_user
    if user and not is_user_authorized(user.id):
        await update.effective_message.reply_text("⛔ Only Area Managers can trigger form drops.")
        return

    from scheduler import send_morning_forms
    await send_morning_forms(context, force=True)
    await update.effective_message.reply_html("✅ <b>Morning sales forms dispatched to all store topics!</b>")
