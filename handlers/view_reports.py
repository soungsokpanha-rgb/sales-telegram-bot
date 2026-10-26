from datetime import datetime, timedelta
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db
import reports
from export_excel import generate_sales_excel
from config import BOT_TIMEZONE, CURRENCY_SYMBOL, ADMIN_IDS, REPORT_CHAT_ID


async def report_today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show today's consolidated report (Khmer)."""
    today_str = datetime.now(BOT_TIMEZONE).strftime("%Y-%m-%d")
    text = reports.format_daily_summary(today_str)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 ធ្វើបច្ចុប្បន្នភាព", callback_data="btn_view_today"),
         InlineKeyboardButton("📥 Export Excel", callback_data="btn_export_excel")],
        [InlineKeyboardButton("« ត្រឡប់ទៅមេនុ", callback_data="btn_main_menu")]
    ])
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await update.message.reply_html(text=text, reply_markup=keyboard)


async def report_yesterday_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show yesterday's consolidated report (Khmer)."""
    yesterday_str = (datetime.now(BOT_TIMEZONE) - timedelta(days=1)).strftime("%Y-%m-%d")
    text = reports.format_daily_summary(yesterday_str)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 ធ្វើបច្ចុប្បន្នភាព", callback_data="btn_view_yesterday"),
         InlineKeyboardButton("« ត្រឡប់ទៅមេនុ", callback_data="btn_main_menu")]
    ])
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await update.message.reply_html(text=text, reply_markup=keyboard)


async def missing_stores_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show pending stores follow-up list (Khmer)."""
    today_str = datetime.now(BOT_TIMEZONE).strftime("%Y-%m-%d")
    text = reports.format_missing_alert(today_str)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 បញ្ជូនការលក់ឥឡូវ", callback_data="btn_submit_sales")],
        [InlineKeyboardButton("🔄 ពិនិត្យម្ដងទៀត", callback_data="btn_view_missing"),
         InlineKeyboardButton("« ត្រឡប់ទៅមេនុ", callback_data="btn_main_menu")]
    ])
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await update.message.reply_html(text=text, reply_markup=keyboard)


async def mtd_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show Month-To-Date summary (Khmer)."""
    current_month_str = datetime.now(BOT_TIMEZONE).strftime("%Y-%m")
    text = reports.format_monthly_summary(current_month_str)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Export Excel", callback_data="btn_export_excel"),
         InlineKeyboardButton("« ត្រឡប់ទៅមេនុ", callback_data="btn_main_menu")]
    ])
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await update.message.reply_html(text=text, reply_markup=keyboard)


async def stores_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of concept stores and their targets (Khmer)."""
    stores = db.get_all_stores(active_only=False)
    lines = [
        "🏬 <b>បញ្ជី CONCEPT STORES</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]
    for st in stores:
        status = "សកម្ម" if st["is_active"] else "អសកម្ម"
        mgr = (st.get("manager_username") or "").strip()
        mgr_display = f"@{mgr.lstrip('@')}" if mgr else "<i>មិនទាន់ប្រគល់</i>"
        lines.append(f"• <b>{st['code']}</b> - {st['name']}")
        lines.append(f"   👤 Manager: <b>{mgr_display}</b>")
        lines.append(f"   🎯 គោលដៅ: <code>{reports.format_currency(st['default_target'])}</code> ({status})")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(
        "💡 <i>ការគ្រប់គ្រង:</i>\n"
        "• ផ្លាស់ Manager: <code>/setmanager &lt;STORE&gt; &lt;@USER&gt;</code>\n"
        "• ផ្លាស់គោលដៅ: <code>/settarget &lt;STORE&gt; &lt;AMOUNT&gt;</code>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« ត្រឡប់ទៅមេនុ", callback_data="btn_main_menu")]
    ])

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text="\n".join(lines), reply_markup=keyboard, parse_mode="HTML")
    else:
        await update.message.reply_html(text="\n".join(lines), reply_markup=keyboard)


async def export_excel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate Excel report and upload to Telegram chat (Khmer status)."""
    status_msg = None
    if update.callback_query:
        await update.callback_query.answer()
        status_msg = await update.callback_query.message.reply_text("⏳ កំពុងបង្កើតរបាយការណ៍ Excel...")
    else:
        status_msg = await update.message.reply_text("⏳ កំពុងបង្កើតរបាយការណ៍ Excel...")

    try:
        excel_path = generate_sales_excel()
        with open(excel_path, "rb") as f:
            caption = (
                f"📊 <b>Concept Stores - ទិន្នន័យការលក់</b>\n"
                f"ហាង: WWEG, WW271, WWAE\n"
                f"បង្កើតនៅ: {datetime.now(BOT_TIMEZONE).strftime('%Y-%m-%d %H:%M')}"
            )
            chat_id = update.effective_chat.id
            await context.bot.send_document(
                chat_id=chat_id,
                document=f,
                filename=excel_path.name,
                caption=caption,
                parse_mode="HTML"
            )
        if status_msg:
            await status_msg.delete()
    except Exception as e:
        if status_msg:
            await status_msg.edit_text(f"❌ មិនអាចបង្កើត Excel: {str(e)}")


async def manual_remind_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually trigger missing reminder to target group/channel (Khmer)."""
    query = update.callback_query
    await query.answer()

    today_str = datetime.now(BOT_TIMEZONE).strftime("%Y-%m-%d")
    alert_text = reports.format_missing_alert(today_str)

    target_chat = REPORT_CHAT_ID if REPORT_CHAT_ID else query.message.chat.id
    try:
        await context.bot.send_message(
            chat_id=target_chat,
            text=alert_text,
            parse_mode="HTML"
        )
        await query.message.reply_text(f"✅ ការរំលឹកត្រូវបានផ្ញើទៅ Chat ID: {target_chat}!")
    except Exception as e:
        await query.message.reply_text(f"❌ មិនអាចផ្ញើការរំលឹកទៅ {target_chat}: {str(e)}")


async def return_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return to role-based main menu (Khmer)."""
    from handlers.start import get_admin_keyboard, get_manager_keyboard
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    is_admin = user.id in ADMIN_IDS if (user and ADMIN_IDS) else False

    if is_admin:
        greeting = (
            f"🏬 <b>Concept Store - បន្ទាប់ការលក់ប្រចាំថ្ងៃ</b>\n"
            f"ហាង: <b>WWEG | WW271 | WWAE</b>\n\n"
            f"ជ្រើសរើសសកម្មភាព:"
        )
        keyboard = get_admin_keyboard()
    else:
        name = user.first_name if user else "Manager"
        greeting = (
            f"👋 <b>សូមស្វាគមន៍, {name}!</b>\n\n"
            f"📝 <b>សូមបញ្ជូនរបាយការណ៍លក់ប្រចាំថ្ងៃ</b>"
        )
        keyboard = get_manager_keyboard()

    await query.edit_message_text(
        text=greeting,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
