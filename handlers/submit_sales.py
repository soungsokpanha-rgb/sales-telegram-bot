import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
import database as db
import reports
from config import BOT_TIMEZONE, CURRENCY_SYMBOL, REPORT_CHAT_ID, ADMIN_IDS


def get_store_for_topic(update: Update) -> dict | None:
    """Return the store linked to the current message thread, or None if not a store topic."""
    thread_id = update.effective_message.message_thread_id if update.effective_message else None
    if not thread_id:
        return None
    return db.get_store_by_topic_id(thread_id)


async def reject_outside_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a Khmer message telling the user to use the correct store topic."""
    stores = db.get_all_stores(active_only=True)
    store_list = ", ".join(f"<b>{s['code']}</b>" for s in stores)
    msg = (
        f"🚫 <b>សូមមកបញ្ជូនការលក់នៅក្នុង Topic ហាងត្រឹមត្រូវ!</b>\n\n"
        f"📌 Topics ត្រឹមត្រូវ: {store_list}\n\n"
        f"<i>សូមចូលទៅ Topic ហាងរបស់អ្នក រួចចុចប៊ូតុង «បញ្ជូនរបាយការណ៍លក់» ។</i>"
    )
    if update.callback_query:
        await update.callback_query.answer("⛔ Topic ខុស!", show_alert=True)
    elif update.message:
        await update.message.reply_html(msg)

# Conversation states
STATE_SELECT_STORE = 1
STATE_SELECT_DATE = 2
STATE_ENTER_SALES = 3
STATE_ENTER_TARGET = 4
STATE_ENTER_TXNS = 5
STATE_ENTER_NOTES = 6
STATE_CONFIRM = 7


def clean_currency_input(text: str) -> float:
    """Clean string like '$1,250.50' or '1250.50' into float."""
    cleaned = re.sub(r"[^\d.]", "", text.strip())
    return float(cleaned)


def parse_sales_template(text: str) -> dict | None:
    """Parse text formatted as sales report template."""
    pattern_target = r'(?:Daily\s*Sale\s*Target|Target|គោលដៅ)[\s.:=]*[\$]?([0-9,]+(?:\.[0-9]+)?)'
    pattern_actual = r'(?:Actual\s*Sale|Actual|ជាក់ស្ដែង)[\s.:=]*[\$]?([0-9,]+(?:\.[0-9]+)?)'
    pattern_date = r'(?:Date|ថ្ងៃ)[\s.:=]*([0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{4}|[0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2})'
    pattern_store = r'(?:Store|ហាង)[\s.:=]*(WWEG|WW271|WWAE(?:ON1)?|[A-Za-z0-9]+)'
    pattern_support = r'(?:Need\s*or\s*Support|Support|Need|ជំនួយ)[\s.:=]*(.*)'

    t_m = re.search(pattern_target, text, re.IGNORECASE)
    a_m = re.search(pattern_actual, text, re.IGNORECASE)

    # Must contain at least Target or Actual
    if not (t_m or a_m):
        return None

    target = float(t_m.group(1).replace(",", "")) if t_m else 0.0
    actual = float(a_m.group(1).replace(",", "")) if a_m else 0.0

    d_m = re.search(pattern_date, text, re.IGNORECASE)
    date_str = None
    if d_m:
        raw_date = d_m.group(1).replace("/", "-")
        parts = raw_date.split("-")
        if len(parts[0]) == 4:
            date_str = raw_date
        elif len(parts[2]) == 4:
            date_str = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"

    s_m = re.search(pattern_store, text, re.IGNORECASE)
    store_code = s_m.group(1).upper() if s_m else None

    sup_m = re.search(pattern_support, text, re.IGNORECASE | re.DOTALL)
    support = sup_m.group(1).strip() if sup_m else ""

    return {
        "target": target,
        "actual": actual,
        "date": date_str,
        "store_code": store_code,
        "support": support,
    }


async def handle_sales_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle text reply to daily sales template (no buttons needed)."""
    message = update.effective_message
    if not message:
        return False

    raw_text = (message.text or message.caption or "").strip()
    if not raw_text:
        return False

    parsed = parse_sales_template(raw_text)
    if not parsed:
        return False

    # 1. Store detection
    store = None
    if parsed.get("store_code"):
        store = db.get_store(parsed["store_code"])

    if not store:
        thread_id = message.message_thread_id
        if thread_id:
            store = db.get_store_by_topic_id(thread_id)

    if not store:
        user = update.effective_user
        username = (user.username or "").strip().lstrip("@").lower()
        if username:
            store = db.get_store_by_manager_username(username)

    if not store:
        await message.reply_html(
            "⚠️ <b>សូមបញ្ជាក់ឈ្មោះហាងរបស់អ្នក!</b>\n"
            "ឧទាហរណ៍៖ បញ្ចូល <code>.Store: WWEG</code>, <code>WW271</code>, ឬ <code>WWAE</code>"
        )
        return True

    now_dt = datetime.now(BOT_TIMEZONE)
    report_date = parsed.get("date") or now_dt.strftime("%Y-%m-%d")
    target = parsed["target"]
    if target <= 0:
        target = float(store.get("default_target", 1000.0))
    actual = parsed["actual"]
    support = parsed.get("support", "")

    user = update.effective_user
    user_id = user.id if user else None
    user_name = user.full_name if user else "Manager"

    # Save to daily_sales
    db.save_daily_sale(
        store_code=store["code"],
        report_date=report_date,
        actual_sales=actual,
        target_sales=target,
        transactions=0,
        footfall=0,
        notes=support,
        user_id=user_id,
        user_name=user_name,
    )

    variance = actual - target
    ratio = (actual / target * 100.0) if target > 0 else 0.0
    badge = reports.get_status_badge(actual, target)
    sign = "+" if variance >= 0 else "-"
    var_str = f"{sign}{reports.format_currency(abs(variance))}"

    display_date = report_date
    try:
        dt = datetime.strptime(report_date, "%Y-%m-%d")
        display_date = dt.strftime("%d-%m-%Y")
    except Exception:
        pass

    support_line = f"📝 <b>Need or Support:</b> <i>{support}</i>\n" if support else ""

    confirm_card = (
        f"✅ <b>បានកត់ត្រារបាយការណ៍លក់ជោគជ័យ!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏬 <b>ហាង:</b> {store['code']} ({store['name']})\n"
        f"📅 <b>ថ្ងៃ:</b> {display_date}\n"
        f"👤 <b>បញ្ជូនដោយ:</b> {user_name}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💵 <b>ការលក់ជាក់ស្ដែង:</b> <code>{reports.format_currency(actual)}</code>\n"
        f"🎯 <b>គោលដៅ:</b> <code>{reports.format_currency(target)}</code>\n"
        f"{badge} <b>សម្រេចបាន:</b> <b>{ratio:.1f}%</b> ({var_str})\n"
        f"{support_line}"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🎉 <i>អរគុណច្រើន! របាយការណ៍ត្រូវបានរក្សាទុករួចរាល់។</i>"
    )

    await message.reply_html(confirm_card)

    # Broadcast summary to Area Manager in main group if outside main group
    thread_id = message.message_thread_id
    if REPORT_CHAT_ID and thread_id:
        try:
            await context.bot.send_message(
                chat_id=REPORT_CHAT_ID,
                text=confirm_card,
                parse_mode="HTML"
            )
        except Exception as e:
            pass

    return True


async def start_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /submit or inline button — ONLY works inside a registered store topic."""
    user = update.effective_user
    is_admin = user.id in ADMIN_IDS if (user and ADMIN_IDS) else False

    # Must be inside a recognised store topic
    store = get_store_for_topic(update)
    if not store:
        # Admins get a silent ignore; managers get a helpful redirect
        if not is_admin:
            await reject_outside_topic(update, context)
        return ConversationHandler.END

    return await prompt_date_for_store(store, update, context)


async def start_submission_for_store(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Triggered from store topic morning form button — validates correct topic."""
    query = update.callback_query
    store_code = query.data.replace("btn_fill_", "")
    store = db.get_store(store_code)

    if not store:
        await query.answer("❌ រកមិនឃើញហាង!", show_alert=True)
        return ConversationHandler.END

    # If tapped inside a different store's registered topic, notify manager
    thread_store = get_store_for_topic(update)
    if thread_store and thread_store["code"] != store_code:
        await query.answer("⛔ Topic ខុស! សូមចុចក្នុង Topic ហាងរបស់អ្នក។", show_alert=True)
        return ConversationHandler.END

    await query.answer()
    return await prompt_date_for_store(store, update, context)


async def prompt_date_for_store(store: dict, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt manager to select date for a specific store."""
    context.user_data["sub_store_code"] = store["code"]
    context.user_data["sub_store_name"] = store["name"]
    context.user_data["sub_default_target"] = store["default_target"]

    now = datetime.now(BOT_TIMEZONE)
    today_str = now.strftime("%Y-%m-%d")
    yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    buttons = [
        [InlineKeyboardButton(f"📅 ថ្ងៃនេះ ({today_str})", callback_data=f"sub_date_{today_str}")],
        [InlineKeyboardButton(f"📆 ម្សិលមិញ ({yesterday_str})", callback_data=f"sub_date_{yesterday_str}")],
        [InlineKeyboardButton("✍️ បញ្ចូលថ្ងៃផ្ទាល់ (YYYY-MM-DD)", callback_data="sub_date_custom")],
        [InlineKeyboardButton("❌ បោះបង់", callback_data="sub_cancel")],
    ]

    prompt_text = (
        f"🏬 <b>ហាង:</b> <b>{store['code']}</b> ({store['name']})\n\n"
        f"ជំហានទី 2/5: ជ្រើសរើស <b>ថ្ងៃលក់</b>:"
    )

    thread_id = update.effective_message.message_thread_id if update.effective_message else None
    target_thread = thread_id or store.get("topic_id")

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=prompt_text,
        reply_markup=InlineKeyboardMarkup(buttons),
        message_thread_id=target_thread,
        parse_mode="HTML"
    )

    return STATE_SELECT_DATE


async def store_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store selected, now choose date."""
    query = update.callback_query
    await query.answer()

    store_code = query.data.replace("sub_store_", "")
    store = db.get_store(store_code)
    if not store:
        await query.edit_message_text("❌ រកមិនឃើញហាង។ សូមចាប់ផ្ដើមម្ដងទៀត /submit")
        return ConversationHandler.END

    context.user_data["sub_store_code"] = store_code
    context.user_data["sub_store_name"] = store["name"]
    context.user_data["sub_default_target"] = store["default_target"]

    now = datetime.now(BOT_TIMEZONE)
    today_str = now.strftime("%Y-%m-%d")
    yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    buttons = [
        [InlineKeyboardButton(f"📅 ថ្ងៃនេះ ({today_str})", callback_data=f"sub_date_{today_str}")],
        [InlineKeyboardButton(f"📆 ម្សិលមិញ ({yesterday_str})", callback_data=f"sub_date_{yesterday_str}")],
        [InlineKeyboardButton("✍️ បញ្ចូលថ្ងៃផ្ទាល់ (YYYY-MM-DD)", callback_data="sub_date_custom")],
        [InlineKeyboardButton("❌ បោះបង់", callback_data="sub_cancel")],
    ]

    await query.edit_message_text(
        text=(
            f"🏬 <b>ហាង:</b> <b>{store_code}</b> ({store['name']})\n\n"
            f"ជំហានទី 2/5: ជ្រើសរើស <b>ថ្ងៃលក់</b>:"
        ),
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML"
    )
    return STATE_SELECT_DATE


async def date_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Pre-set date selected from inline button."""
    query = update.callback_query
    await query.answer()

    selected_date = query.data.replace("sub_date_", "")
    if selected_date == "custom":
        await query.edit_message_text(
            "✍️ សូមបញ្ចូលថ្ងៃក្នុងទម្រង់ <code>YYYY-MM-DD</code> (ឧ. <code>2026-10-24</code>):",
            parse_mode="HTML"
        )
        return STATE_SELECT_DATE

    context.user_data["sub_date"] = selected_date
    return await prompt_sales_amount(query.message.edit_text, context)


async def date_custom_typed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User typed custom date."""
    text = update.message.text.strip()
    try:
        dt = datetime.strptime(text, "%Y-%m-%d")
        context.user_data["sub_date"] = dt.strftime("%Y-%m-%d")
        return await prompt_sales_amount(update.message.reply_html, context)
    except ValueError:
        await update.message.reply_html(
            "⚠️ ទម្រង់ថ្ងៃខុស! សូមបញ្ចូលជា <code>YYYY-MM-DD</code> (ឧ. <code>2026-10-24</code>):"
        )
        return STATE_SELECT_DATE


async def prompt_sales_amount(reply_func, context: ContextTypes.DEFAULT_TYPE) -> int:
    store_code = context.user_data.get("sub_store_code")
    date_str = context.user_data.get("sub_date")

    prompt = (
        f"🏬 <b>ហាង:</b> {store_code}\n"
        f"📅 <b>ថ្ងៃ:</b> {date_str}\n\n"
        f"ជំហានទី 3/5: បញ្ចូល <b>ចំនួនលក់ជាក់ស្ដែង</b> (Actual Sales):\n"
        f"<i>(ឧ. <code>1250</code>, <code>1450.75</code>, ឬ <code>$1500</code>)</i>"
    )
    buttons = [[InlineKeyboardButton("❌ បោះបង់", callback_data="sub_cancel")]]
    await reply_func(text=prompt, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
    return STATE_ENTER_SALES


async def sales_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process actual sales input."""
    text = update.message.text.strip()
    try:
        sales_val = clean_currency_input(text)
        if sales_val < 0:
            raise ValueError()
        context.user_data["sub_actual_sales"] = sales_val
    except Exception:
        await update.message.reply_html(
            "⚠️ សូមបញ្ចូលចំនួនត្រឹមត្រូវ (ឧ. <code>1250.00</code>):"
        )
        return STATE_ENTER_SALES

    buttons = [
        [InlineKeyboardButton("❌ បោះបង់", callback_data="sub_cancel")]
    ]

    await update.message.reply_html(
        text=(
            f"💵 <b>ការលក់ជាក់ស្ដែង:</b> <code>{reports.format_currency(sales_val)}</code>\n\n"
            f"🎯 <b>ជំហានទី 4/5: បញ្ចូលគោលដៅលក់ (Set Daily Target)</b>:\n"
            f"👉 <i>សូមវាយបញ្ចូលចំនួនទឹកប្រាក់គោលដៅដែលអ្នកបានកំណត់សម្រាប់ថ្ងៃនេះ</i>\n"
            f"<i>(ឧ. <code>1200</code>, <code>1500</code>, ឬ <code>$1500</code>):</i>"
        ),
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return STATE_ENTER_TARGET


async def target_default_clicked(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User tapped Use Default Target."""
    query = update.callback_query
    await query.answer()
    default_target = context.user_data.get("sub_default_target", 1000.0)
    context.user_data["sub_target_sales"] = default_target
    return await prompt_txns(query.message.edit_text, context)


async def target_custom_typed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User typed custom target."""
    text = update.message.text.strip()
    try:
        target_val = clean_currency_input(text)
        if target_val <= 0:
            raise ValueError()
        context.user_data["sub_target_sales"] = target_val
        return await prompt_txns(update.message.reply_html, context)
    except Exception:
        await update.message.reply_html(
            "⚠️ សូមបញ្ចូលចំនួនគោលដៅត្រឹមត្រូវ (ឧ. <code>1500.00</code>):"
        )
        return STATE_ENTER_TARGET


async def prompt_txns(reply_func, context: ContextTypes.DEFAULT_TYPE) -> int:
    buttons = [
        [InlineKeyboardButton("⏭ រំលង (0 bill)", callback_data="sub_txns_skip")],
        [InlineKeyboardButton("❌ បោះបង់", callback_data="sub_cancel")]
    ]
    await reply_func(
        text=(
            f"🎯 <b>គោលដៅ:</b> <code>{reports.format_currency(context.user_data['sub_target_sales'])}</code>\n\n"
            f"ជំហានទី 5/6: បញ្ចូល <b>ចំនួន Bills (ប្រតិបត្តិការ)</b>:\n"
            f"<i>(ឧ. <code>38</code> bills) ឬចុច រំលង:</i>"
        ),
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML"
    )
    return STATE_ENTER_TXNS


async def txns_skip_clicked(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["sub_txns"] = 0
    return await prompt_notes(query.message.edit_text, context)


async def txns_typed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_html("⚠️ សូមបញ្ចូលចំនួនគត់ (ឧ. <code>42</code>):")
        return STATE_ENTER_TXNS

    context.user_data["sub_txns"] = int(text)
    return await prompt_notes(update.message.reply_html, context)


async def prompt_notes(reply_func, context: ContextTypes.DEFAULT_TYPE) -> int:
    buttons = [
        [InlineKeyboardButton("⏭ គ្មានចំណាំ (បញ្ជូនឥឡូវ)", callback_data="sub_notes_skip")],
        [InlineKeyboardButton("❌ បោះបង់", callback_data="sub_cancel")]
    ]
    await reply_func(
        text=(
            f"🧾 <b>ចំនួន Bills:</b> <code>{context.user_data.get('sub_txns', 0)}</code>\n\n"
            f"ជំហានទី 6/6: បន្ថែម <b>ចំណាំ</b> (ឧ. Footfall, ភ្លៀង, ព្រឹត្តិការណ៍):\n"
            f"<i>បញ្ចូលចំណាំ ឬចុច 'គ្មានចំណាំ':</i>"
        ),
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML"
    )
    return STATE_ENTER_NOTES


async def notes_skip_clicked(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["sub_notes"] = ""
    return await show_confirmation(query.message.edit_text, context)


async def notes_typed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["sub_notes"] = update.message.text.strip()
    return await show_confirmation(update.message.reply_html, context)


async def show_confirmation(reply_func, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data
    store_code = user_data["sub_store_code"]
    store_name = user_data["sub_store_name"]
    date_str = user_data["sub_date"]
    actual = user_data["sub_actual_sales"]
    target = user_data["sub_target_sales"]
    txns = user_data.get("sub_txns", 0)
    notes = user_data.get("sub_notes", "")

    mock_sale = {
        "store_code": store_code,
        "store_name": store_name,
        "report_date": date_str,
        "submitted_by_name": "Preview",
        "actual_sales": actual,
        "target_sales": target,
        "transactions": txns,
        "footfall": 0,
        "notes": notes,
    }

    preview_card = reports.format_single_submission_card(mock_sale)

    buttons = [
        [InlineKeyboardButton("✅ បញ្ជាក់ & រក្សាទុក", callback_data="sub_confirm_yes")],
        [InlineKeyboardButton("❌ លុបចោល & បោះបង់", callback_data="sub_cancel")]
    ]

    await reply_func(
        text=f"{preview_card}\n\n🔍 <i>សូមពិនិត្យព័ត៌មានខាងលើ មុននឹងបញ្ជូន។</i>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML"
    )
    return STATE_CONFIRM


async def confirm_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save record to database and broadcast to group/Area Manager if configured."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    user_id = user.id if user else None
    user_name = user.full_name if user else "Manager"

    data = context.user_data
    store_code = data["sub_store_code"]
    date_str = data["sub_date"]
    actual = data["sub_actual_sales"]
    target = data["sub_target_sales"]
    txns = data.get("sub_txns", 0)
    notes = data.get("sub_notes", "")

    # Save to database
    record = db.save_daily_sale(
        store_code=store_code,
        report_date=date_str,
        actual_sales=actual,
        target_sales=target,
        transactions=txns,
        notes=notes,
        user_id=user_id,
        user_name=user_name
    )

    card_text = reports.format_single_submission_card(record)

    await query.edit_message_text(
        text=f"{card_text}\n🎉 <b>របាយការណ៍ត្រូវបានរក្សាទុករួចរាល់!</b>",
        parse_mode="HTML"
    )

    # Broadcast to Area Manager / Group Chat
    if REPORT_CHAT_ID and query.message.chat.id != REPORT_CHAT_ID:
        try:
            broadcast_msg = f"📢 <b>ការបញ្ជូនការលក់ថ្មី</b>\n\n{card_text}"
            await context.bot.send_message(
                chat_id=REPORT_CHAT_ID,
                text=broadcast_msg,
                parse_mode="HTML"
            )
        except Exception:
            pass

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel submission."""
    context.user_data.clear()
    msg = "❌ ការបញ្ជូនការលក់ត្រូវបានបោះបង់។"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(msg)
    else:
        await update.message.reply_text(msg)
    return ConversationHandler.END


def get_submission_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("submit", start_submission),
            CallbackQueryHandler(start_submission, pattern="^btn_submit_sales$"),
            CallbackQueryHandler(start_submission_for_store, pattern="^btn_fill_"),
        ],
        states={
            STATE_SELECT_STORE: [
                CallbackQueryHandler(store_selected, pattern="^sub_store_"),
                CallbackQueryHandler(cancel_submission, pattern="^sub_cancel$"),
            ],
            STATE_SELECT_DATE: [
                CallbackQueryHandler(date_selected, pattern="^sub_date_"),
                CallbackQueryHandler(cancel_submission, pattern="^sub_cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, date_custom_typed),
            ],
            STATE_ENTER_SALES: [
                CallbackQueryHandler(cancel_submission, pattern="^sub_cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sales_entered),
            ],
            STATE_ENTER_TARGET: [
                CallbackQueryHandler(target_default_clicked, pattern="^sub_target_default$"),
                CallbackQueryHandler(cancel_submission, pattern="^sub_cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, target_custom_typed),
            ],
            STATE_ENTER_TXNS: [
                CallbackQueryHandler(txns_skip_clicked, pattern="^sub_txns_skip$"),
                CallbackQueryHandler(cancel_submission, pattern="^sub_cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, txns_typed),
            ],
            STATE_ENTER_NOTES: [
                CallbackQueryHandler(notes_skip_clicked, pattern="^sub_notes_skip$"),
                CallbackQueryHandler(cancel_submission, pattern="^sub_cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, notes_typed),
            ],
            STATE_CONFIRM: [
                CallbackQueryHandler(confirm_yes, pattern="^sub_confirm_yes$"),
                CallbackQueryHandler(cancel_submission, pattern="^sub_cancel$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_submission),
            CallbackQueryHandler(cancel_submission, pattern="^sub_cancel$"),
        ],
        allow_reentry=True,
        per_message=False,
    )
