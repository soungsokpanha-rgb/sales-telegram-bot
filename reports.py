from datetime import datetime
from typing import Dict, Any, List
import config
from config import CURRENCY_SYMBOL, BOT_TIMEZONE
import database as db


def format_currency(amount: float) -> str:
    """Format float into nice currency string e.g. $1,250.50"""
    return f"{CURRENCY_SYMBOL}{amount:,.2f}"


def get_status_badge(actual: float, target: float) -> str:
    """Return status emoji based on target achievement."""
    if target <= 0:
        return "⚪"
    ratio = (actual / target) * 100.0
    if ratio >= 100.0:
        return "🟢"
    elif ratio >= 80.0:
        return "🟡"
    else:
        return "🔴"


def format_single_submission_card(sale: Dict[str, Any]) -> str:
    """Format single store submission confirmation card (Khmer)."""
    actual = sale.get("actual_sales", 0.0)
    target = sale.get("target_sales", 0.0)
    variance = actual - target
    ratio = (actual / target * 100.0) if target > 0 else 0.0
    transactions = sale.get("transactions", 0)
    atv = (actual / transactions) if transactions > 0 else 0.0
    footfall = sale.get("footfall", 0)
    notes = sale.get("notes", "").strip()
    badge = get_status_badge(actual, target)

    sign = "+" if variance >= 0 else "-"
    var_str = f"{sign}{format_currency(abs(variance))}"

    lines = [
        f"✅ <b>ការលក់ប្រចាំថ្ងៃត្រូវបានរក្សាទុក!</b>",
        f"━━━━━━━━━━━━━━━━━━━",
        f"🏬 <b>ហាង:</b> {sale.get('store_code')} - {sale.get('store_name', '')}",
        f"📅 <b>ថ្ងៃ:</b> {sale.get('report_date')}",
        f"👤 <b>បញ្ជូនដោយ:</b> {sale.get('submitted_by_name', 'Manager')}",
        f"━━━━━━━━━━━━━━━━━━━",
        f"💵 <b>ការលក់ជាក់ស្ដែង:</b> <code>{format_currency(actual)}</code>",
        f"🎯 <b>គោលដៅ:</b> <code>{format_currency(target)}</code>",
        f"{badge} <b>សម្រេចបាន:</b> <b>{ratio:.1f}%</b> ({var_str})",
        f"🧾 <b>ចំនួន Bills:</b> <code>{transactions}</code>",
        f"🎟 <b>ATV (មធ្យម/Bill):</b> <code>{format_currency(atv)}</code>",
    ]

    if footfall > 0:
        lines.append(f"👥 <b>Footfall:</b> <code>{footfall} នាក់</code>")

    if notes:
        lines.append(f"📝 <b>ចំណាំ:</b> <i>{notes}</i>")

    lines.append(f"━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def format_daily_summary(date_str: str) -> str:
    """Format consolidated Daily Sales Report for all 3 Concept Stores (Khmer)."""
    stores = db.get_all_stores(active_only=True)
    sales = db.get_daily_sales_by_date(date_str)
    sales_by_code = {s["store_code"]: s for s in sales}

    try:
        dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
        formatted_date = dt_obj.strftime("%A, %d %b %Y")
    except Exception:
        formatted_date = date_str

    now_local = datetime.now(BOT_TIMEZONE).strftime("%H:%M")

    lines = [
        f"📊 <b>CONCEPT STORES - របាយការណ៍លក់ប្រចាំថ្ងៃ</b>",
        f"📅 <b>{formatted_date}</b> | ⏰ <i>ធ្វើបច្ចុប្បន្នភាពនៅ {now_local}</i>",
        f"━━━━━━━━━━━━━━━━━━━━━━",
    ]

    total_actual = 0.0
    total_target = 0.0
    total_bills = 0
    reported_count = 0

    for store in stores:
        code = store["code"]
        name = store["name"]
        mgr = (store.get("manager_username") or "").strip()
        mgr_str = f" | 👤 @{mgr.lstrip('@')}" if mgr else ""

        if code in sales_by_code:
            reported_count += 1
            s = sales_by_code[code]
            actual = s["actual_sales"]
            target = s["target_sales"]
            txns = s.get("transactions", 0)
            notes = s.get("notes", "").strip()

            total_actual += actual
            total_target += target
            total_bills += txns

            var = actual - target
            ratio = (actual / target * 100.0) if target > 0 else 0.0
            badge = get_status_badge(actual, target)
            sign = "+" if var >= 0 else "-"
            atv = (actual / txns) if txns > 0 else 0.0

            lines.append(f"{badge} <b>{code}</b> ({name}){mgr_str}")
            lines.append(f"  • ការលក់: <b>{format_currency(actual)}</b> / គោលដៅ: {format_currency(target)}")
            lines.append(f"  • សម្រេចបាន: <b>{ratio:.1f}%</b> ({sign}{format_currency(abs(var))})")
            lines.append(f"  • Bills: {txns} | ATV: {format_currency(atv)}")
            if notes:
                lines.append(f"  • ចំណាំ: <i>{notes}</i>")
            lines.append("")
        else:
            def_target = store["default_target"]
            total_target += def_target
            lines.append(f"⏳ <b>{code}</b> ({name}){mgr_str}")
            lines.append(f"  • ⚠️ <i>រង់ចាំការបញ្ជូន</i> (គោលដៅ: {format_currency(def_target)})")
            lines.append("")

    # Summary section
    total_var = total_actual - total_target
    total_ratio = (total_actual / total_target * 100.0) if total_target > 0 else 0.0
    total_badge = get_status_badge(total_actual, total_target)
    total_sign = "+" if total_var >= 0 else "-"
    total_atv = (total_actual / total_bills) if total_bills > 0 else 0.0

    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🏆 <b>សរុបរួម CONCEPT STORES</b> ({reported_count}/{len(stores)} ហាងបានបញ្ជូន)")
    lines.append(f"💵 <b>ការលក់សរុប:</b> <code>{format_currency(total_actual)}</code>")
    lines.append(f"🎯 <b>គោលដៅសរុប:</b> <code>{format_currency(total_target)}</code>")
    lines.append(f"{total_badge} <b>សម្រេចបានសរុប:</b> <b>{total_ratio:.1f}%</b> ({total_sign}{format_currency(abs(total_var))})")
    lines.append(f"🧾 <b>Bills សរុប:</b> <code>{total_bills}</code> | <b>ATV:</b> <code>{format_currency(total_atv)}</code>")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


def format_missing_alert(date_str: str) -> str:
    """Format reminder alert for stores that haven't submitted yet (Khmer)."""
    missing = db.get_missing_stores(date_str)
    if not missing:
        return (
            f"🎉 <b>អស្ចារ្យណាស់!</b> ហាងទាំង 3 (WWEG, WW271, WWAE) "
            f"បានបញ្ជូនការលក់ប្រចាំថ្ងៃ <b>{date_str}</b> រួចរាល់!"
        )

    store_lines = []
    for st in missing:
        mgr = (st.get("manager_username") or "").strip()
        mgr_str = f" — 👤 @{mgr.lstrip('@')}" if mgr else ""
        store_lines.append(f"• <b>{st['code']}</b> ({st['name']}){mgr_str}")

    store_list_str = "\n".join(store_lines)

    lines = [
        f"⚠️ <b>ការរំលឹក — ការបញ្ជូនការលក់ប្រចាំថ្ងៃ</b>",
        f"📅 ថ្ងៃ: <b>{date_str}</b>",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"ហាងខាងក្រោម <b>មិនទាន់</b> បញ្ជូនការលក់ប្រចាំថ្ងៃ:",
        f"",
        store_list_str,
        f"",
        f"👉 <i>សូម Manager ចុច /submit ឬប៊ូតុង «បញ្ជូនរបាយការណ៍» ឥឡូវ!</i>",
        f"━━━━━━━━━━━━━━━━━━━━━━",
    ]
    return "\n".join(lines)


def format_monthly_summary(year_month_str: str) -> str:
    """Format Month-To-Date summary (Khmer)."""
    data = db.get_monthly_summary(year_month_str)
    stores = data.get("stores", [])

    lines = [
        f"📈 <b>ការសង្ខេបលក់ប្រចាំខែ (MTD)</b>",
        f"🗓 <b>ខែ:</b> {year_month_str}",
        f"━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if not stores:
        lines.append(f"<i>មិនមានទិន្នន័យសម្រាប់ខែ {year_month_str}.</i>")
        lines.append(f"━━━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)

    for s in stores:
        actual = s["total_actual"] or 0.0
        target = s["total_target"] or 0.0
        ratio = (actual / target * 100.0) if target > 0 else 0.0
        badge = get_status_badge(actual, target)
        days = s["days_reported"]
        txns = s["total_transactions"] or 0

        lines.append(f"{badge} <b>{s['store_code']}</b> - {s['store_name']}")
        lines.append(f"  • ការលក់ MTD: <b>{format_currency(actual)}</b> (គោលដៅ: {format_currency(target)})")
        lines.append(f"  • សម្រេចបាន: <b>{ratio:.1f}%</b> ក្នុង {days} ថ្ងៃ ({txns} bills)")
        lines.append("")

    total_actual = data["total_actual"]
    total_target = data["total_target"]
    ratio = data["achievement_rate"]
    total_badge = get_status_badge(total_actual, total_target)
    total_txns = data["total_transactions"]

    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🏆 <b>CONCEPT STORES MTD សរុប</b>")
    lines.append(f"💵 <b>ការលក់សរុប:</b> <code>{format_currency(total_actual)}</code>")
    lines.append(f"🎯 <b>គោលដៅសរុប:</b> <code>{format_currency(total_target)}</code>")
    lines.append(f"{total_badge} <b>សម្រេចបាន MTD:</b> <b>{ratio:.1f}%</b>")
    lines.append(f"🧾 <b>Bills សរុប:</b> <code>{total_txns}</code>")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


def format_daily_operational_overview(date_str: str) -> str:
    """Format daily operational report checklist (Briefing, Story/Telegram, and TikTok) in Khmer."""
    status_map = db.get_operational_status_for_date(date_str)

    lines = [
        f"💡 <b>របាយការណ៍ប្រចាំថ្ងៃ — DAILY REPORT</b>",
        f"📅 ថ្ងៃ: <b>{date_str}</b>",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"1️⃣ 🗣️ <b>Briefing Report</b> (ប្រជុំព្រឹក)",
        f"2️⃣ 📱 <b>Story & Telegram Report</b> (ផុស Social/Telegram)",
        f"3️⃣ 🎬 <b>TikTok Follow-up</b> (2 វីដេអូ/ហាង/សប្ដាហ៍)",
        f"━━━━━━━━━━━━━━━━━━━━━━",
    ]

    all_done = True
    for code, info in status_map.items():
        mgr = (info["manager_username"] or "").strip().lstrip("@")
        mgr_str = f" (@{mgr})" if mgr else ""
        b_icon = "✅" if info["briefing"] else "❌"
        s_icon = "✅" if info["story_telegram"] else "❌"

        store_complete = info["briefing"] and info["story_telegram"]
        if info.get("is_tiktok_day") and not info["tiktok"]:
            store_complete = False

        if not store_complete:
            all_done = False

        week_cnt = info.get("week_tiktok_count", 0)
        lines.append(f"🏬 <b>{code}</b> ({info['store_name']}){mgr_str}")
        lines.append(f"  • {b_icon} Briefing: {'រួចរាល់' if info['briefing'] else '<b>មិនទាន់បញ្ជូន</b>'}")
        if info["briefing_notes"]:
            lines.append(f"    <i>({info['briefing_notes']})</i>")
        lines.append(f"  • {s_icon} Story & Telegram: {'រួចរាល់' if info['story_telegram'] else '<b>មិនទាន់បញ្ជូន</b>'}")
        if info["story_telegram_notes"]:
            lines.append(f"    <i>({info['story_telegram_notes']})</i>")

        # TikTok line
        if info.get("is_tiktok_day"):
            t_icon = "✅" if info["tiktok"] else "❌"
            t_status = 'រួចរាល់' if info['tiktok'] else '<b>កាតព្វកិច្ចថ្ងៃនេះ (មិនទាន់បញ្ជូន)</b>'
            lines.append(f"  • {t_icon} 🎬 TikTok: {t_status} <i>(សប្ដាហ៍នេះ: {week_cnt}/2)</i>")
            if info.get("tiktok_notes"):
                lines.append(f"    <i>({info['tiktok_notes']})</i>")
        else:
            sched_indices = config.TIKTOK_SCHEDULE.get(code, [])
            if len(sched_indices) >= 2:
                sched_kh = f"{config.WEEKDAY_NAMES_KH[sched_indices[0]]} & {config.WEEKDAY_NAMES_KH[sched_indices[1]]}"
            else:
                sched_kh = "តាមកាលវិភាគ"
            lines.append(f"  • 🎬 TikTok: កាលវិភាគ ({sched_kh}) <i>(សប្ដាហ៍នេះ: {week_cnt}/2)</i>")

        lines.append("")

    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━")
    if all_done:
        lines.append(f"🎉 <b>អបអរសាទរ! គ្រប់ហាងទាំងអស់បានបញ្ជូនរបាយការណ៍រួចរាល់!</b>")
    else:
        lines.append(f"👉 <i>សូម Manager <b>Reply (ឆ្លើយតប) លើសារនេះ</b> ជាមួយរូបភាព, Link TikTok ឬ វីដេអូ ដើម្បីបញ្ជូន!</i>")

    return "\n".join(lines)


def format_missing_operational_reminder(date_str: str) -> str:
    """Format reminder for stores missing Briefing, Story/Telegram, or scheduled TikTok."""
    missing = db.get_missing_operational_stores(date_str)
    if not missing:
        return ""

    lines = [
        f"⚠️ <b>ការរំលឹក — DAILY REPORT នៅខ្វះ!</b>",
        f"📅 ថ្ងៃ: <b>{date_str}</b>",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"ហាងខាងក្រោមមិនទាន់បានបញ្ជូនរបាយការណ៍គ្រប់គ្រាន់នៅឡើយ:",
        f"",
    ]

    for st in missing:
        mgr = (st.get("manager_username") or "").strip().lstrip("@")
        mgr_str = f" — 👤 @{mgr}" if mgr else ""
        missing_items = " & ".join(st["missing_types"])
        lines.append(f"• <b>{st['code']}</b>{mgr_str}: ខ្វះ <b>{missing_items}</b>")

    lines.append(f"")
    lines.append(f"👉 <i>សូម Manager <b>Reply (ឆ្លើយតប) លើសារនេះ</b> ជាមួយរូបភាព, Link TikTok ឬ វីដេអូ ដើម្បីបញ្ជូនបង្គ្រប់!</i>")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def format_weekly_tiktok_overview(reference_date: str = None) -> str:
    """Format weekly TikTok follow-up dashboard across WWEG, WW271, and WWAE."""
    report = db.get_weekly_tiktok_report(reference_date)
    start_dt = report["start_date"]
    end_dt = report["end_date"]
    total_completed = report["total_completed"]
    total_target = report["total_target"]

    lines = [
        f"🎬 <b>CONCEPT STORES — តាមដាន TIKTOK ប្រចាំសប្ដាហ៍</b>",
        f"📅 សប្ដាហ៍: <b>{start_dt}</b> ដល់ <b>{end_dt}</b>",
        f"🎯 <b>គោលដៅ:</b> <code>2 វីដេអូ / ហាង / សប្ដាហ៍</code> (សរុប {total_target} វីដេអូ)",
        f"━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for code, info in report["stores"].items():
        mgr = (info["manager_username"] or "").strip().lstrip("@")
        mgr_str = f" — 👤 @{mgr}" if mgr else ""
        completed = info["completed"]
        ratio = (completed / 2.0) * 100.0 if info["target"] > 0 else 0.0
        badge = "🟢" if completed >= 2 else ("🟡" if completed == 1 else "🔴")

        lines.append(f"🏬 <b>{code}</b> ({info['name']}){mgr_str}")
        lines.append(f"  {badge} <b>វឌ្ឍនភាព:</b> <b>{completed}/2 វីដេអូ</b> ({ratio:.0f}%)")

        for idx, d in enumerate(info["days"], start=1):
            day_name = f"{d['day_name_kh']} ({d['date']})"
            if d["is_submitted"]:
                sub = d["submission"]
                note = f": <i>{sub['notes']}</i>" if sub and sub.get("notes") else ""
                lines.append(f"  • វីដេអូ {idx} ({day_name}): ✅ <b>រួចរាល់</b>{note}")
            elif d["state"] == "today_pending":
                lines.append(f"  • វីដេអូ {idx} ({day_name}): 🚨 <b>កាតព្វកិច្ចថ្ងៃនេះ! (មិនទាន់បញ្ជូន)</b>")
            elif d["state"] == "missed":
                lines.append(f"  • វីដេអូ {idx} ({day_name}): ❌ <b>មិនទាន់បានផុស (ខកខាន)</b>")
            else:
                lines.append(f"  • វីដេអូ {idx} ({day_name}): ⏳ <i>រង់ចាំតាមកាលវិភាគ</i>")

        # Extra submissions in this week
        extra = [s for s in info["submissions"] if s["report_date"] not in [d["date"] for d in info["days"]]]
        if extra:
            for ex in extra:
                lines.append(f"  • វីដេអូបន្ថែម ({ex['report_date']}): ✅ <i>{ex['notes']}</i>")

        lines.append("")

    total_ratio = (total_completed / total_target * 100.0) if total_target > 0 else 0.0
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🏆 <b>សរុបរួមសប្ដាហ៍នេះ:</b> <b>{total_completed}/{total_target} វីដេអូ</b> ({total_ratio:.0f}%)")
    lines.append(f"📌 <b>កាលវិភាគប្រចាំសប្ដាហ៍:</b>")
    lines.append(f"  • <b>WWEG:</b> ថ្ងៃចន្ទ & ថ្ងៃព្រហស្បតិ៍")
    lines.append(f"  • <b>WW271:</b> ថ្ងៃអង្គារ & ថ្ងៃសុក្រ")
    lines.append(f"  • <b>WWAEON:</b> ថ្ងៃពុធ & ថ្ងៃសៅរ៍")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"👉 <i>ដើម្បីបញ្ជូន TikTok: សូម Reply លើសារនេះ ជាមួយ <b>Link TikTok</b> ឬ <b>វីដេអូ</b>!</i>")

    return "\n".join(lines)

