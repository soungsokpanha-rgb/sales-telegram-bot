from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db
from config import ADMIN_IDS


def get_manager_keyboard() -> InlineKeyboardMarkup:
    """Show ONLY the Submit Sale Report button for Managers in store topics."""
    buttons = [
        [InlineKeyboardButton("📝 បញ្ជូនរបាយការណ៍លក់ប្រចាំថ្ងៃ", callback_data="btn_submit_sales")],
    ]
    return InlineKeyboardMarkup(buttons)


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Full dashboard keyboard for Area Manager (Admin)."""
    buttons = [
        [
            InlineKeyboardButton("📝 បញ្ជូនការលក់", callback_data="btn_submit_sales"),
        ],
        [
            InlineKeyboardButton("📊 របាយការណ៍ថ្ងៃនេះ", callback_data="btn_view_today"),
            InlineKeyboardButton("📅 ម្សិលមិញ", callback_data="btn_view_yesterday"),
        ],
        [
            InlineKeyboardButton("⚠️ ហាងដែលមិនទាន់", callback_data="btn_view_missing"),
            InlineKeyboardButton("📈 MTD ប្រចាំខែ", callback_data="btn_view_mtd"),
        ],
        [
            InlineKeyboardButton("🎬 តាមដាន TikTok", callback_data="btn_view_tiktok"),
            InlineKeyboardButton("📥 Export Excel", callback_data="btn_export_excel"),
        ],
        [
            InlineKeyboardButton("🏬 Concept Stores", callback_data="btn_view_stores"),
            InlineKeyboardButton("🔔 ផ្ញើការរំលឹក", callback_data="btn_send_reminder"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command — role-based menu."""
    user = update.effective_user
    if user:
        db.record_user_activity(user.id, user.username, user.full_name)

    is_admin = user.id in ADMIN_IDS if (user and ADMIN_IDS) else False

    if is_admin:
        greeting = (
            f"👋 <b>សូមស្វាគមន៍, {user.first_name if user else 'Area Manager'}!</b>\n\n"
            f"🏬 <b>Concept Store - បន្ទាប់ការលក់ប្រចាំថ្ងៃ</b>\n"
            f"តាមដាន 3 ហាង:\n"
            f"  1️⃣ <b>WWEG</b>\n"
            f"  2️⃣ <b>WW271</b>\n"
            f"  3️⃣ <b>WWAE</b>\n\n"
            f"ជ្រើសរើសសកម្មភាពខាងក្រោម:"
        )
        keyboard = get_admin_keyboard()
    else:
        name = user.first_name if user else "Manager"
        greeting = (
            f"👋 <b>សូមស្វាគមន៍, {name}!</b>\n\n"
            f"📝 <b>សូមបញ្ជូនរបាយការណ៍លក់ប្រចាំថ្ងៃ</b>\n"
            f"ចុចប៊ូតុងខាងក្រោម ដើម្បីបញ្ចូលការលក់:"
        )
        keyboard = get_manager_keyboard()

    thread_id = update.effective_message.message_thread_id if update.effective_message else None
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=greeting,
        reply_markup=keyboard,
        message_thread_id=thread_id,
        parse_mode="HTML"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command — Khmer guide."""
    user = update.effective_user
    is_admin = user.id in ADMIN_IDS if (user and ADMIN_IDS) else False

    if is_admin:
        help_text = (
            f"📖 <b>ការណែនាំប្រើប្រាស់ BOT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>ការរាយការណ៍ប្រចាំថ្ងៃ:</b>\n"
            f"• /submit - បញ្ជូនការលក់ (WWEG / WW271 / WWAE)\n"
            f"• /today - របាយការណ៍ 3 ហាង ថ្ងៃនេះ\n"
            f"• /yesterday - របាយការណ៍ 3 ហាង ម្សិលមិញ\n"
            f"• /missing - ហាងដែលមិនទាន់បញ្ជូន\n"
            f"• /tiktok - តាមដានការផុស TikTok (2 វីដេអូ/ហាង/សប្ដាហ៍)\n"
            f"• /mtd - ការសង្ខេបលក់ប្រចាំខែ\n"
            f"• /export - ទាញ Excel ដែលមានទិន្នន័យ\n\n"
            f"<b>ការគ្រប់គ្រង:</b>\n"
            f"• /settarget <code>&lt;STORE&gt; &lt;AMOUNT&gt;</code> — ឧ. <code>/settarget WWEG 1500</code>\n"
            f"• /setmanager <code>&lt;STORE&gt; @user</code> — ឧ. <code>/setmanager WWEG @alex</code>\n"
            f"• /remind - ផ្ញើការរំលឹកភ្លាមៗ\n"
            f"• /myid - មើល Telegram ID របស់អ្នក\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
    else:
        help_text = (
            f"📖 <b>ការណែនាំ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• ចុច /submit ឬប៊ូតុង <b>«បញ្ជូនរបាយការណ៍លក់»</b> ដើម្បីបន្ថែមការលក់ប្រចាំថ្ងៃ\n"
            f"• វាយ /tiktok ឬ Reply លើសាររំលឹកជាមួយ Link TikTok / វីដេអូ ដើម្បីបញ្ជូន TikTok\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )

    thread_id = update.effective_message.message_thread_id if update.effective_message else None
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=help_text,
        message_thread_id=thread_id,
        parse_mode="HTML"
    )


async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /myid command."""
    user = update.effective_user
    chat = update.effective_chat
    user_id = user.id if user else "Unknown"
    chat_id = chat.id if chat else "Unknown"
    chat_type = chat.type if chat else "Unknown"

    text = (
        f"🆔 <b>TELEGRAM IDs របស់អ្នក</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
        f"💬 <b>Chat ID:</b> <code>{chat_id}</code>\n"
        f"🏷 <b>Chat Type:</b> <code>{chat_type}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>ចម្លង User ID ដាក់ ADMIN_IDS ក្នុង .env ឬ Chat ID ដាក់ REPORT_CHAT_ID.</i>"
    )
    thread_id = update.effective_message.message_thread_id if update.effective_message else None
    await context.bot.send_message(
        chat_id=chat.id,
        text=text,
        message_thread_id=thread_id,
        parse_mode="HTML"
    )
