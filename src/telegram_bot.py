import requests
import json
import logging

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

def send_telegram_message(bot_token, chat_id, text, parse_mode="HTML"):
    """
    Sends a message to a Telegram chat using Telegram Bot API.
    """
    if not bot_token or not chat_id:
        return False, "Bot token or Chat ID missing"

    url = TELEGRAM_API_URL.format(token=bot_token)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }

    try:
        response = requests.post(url, json=payload, timeout=8)
        data = response.json()
        if response.status_code == 200 and data.get("ok"):
            return True, "Message sent successfully"
        else:
            description = data.get("description", "Unknown error")
            return False, f"Telegram API Error: {description}"
    except Exception as e:
        return False, f"Network Error: {str(e)}"


def test_telegram_connection(bot_token, chat_id):
    """
    Tests Telegram credentials by sending a test message.
    """
    test_msg = (
        "<b>🟢 DVR Monitoring System</b>\n\n"
        "✅ Telegram Bot integration successfully connected!\n"
        "You will receive real-time DVR updates and alerts here."
    )
    return send_telegram_message(bot_token, chat_id, test_msg)


def auto_detect_chat_id(bot_token):
    """
    Queries Telegram getUpdates to automatically find Chat ID of recent group message.
    """
    if not bot_token:
        return False, "Bot Token is missing", None

    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    try:
        response = requests.get(url, timeout=8)
        data = response.json()
        if response.status_code == 200 and data.get("ok"):
            updates = data.get("result", [])
            for update in reversed(updates):
                msg = update.get("message") or update.get("channel_post") or update.get("my_chat_member")
                if msg:
                    chat = msg.get("chat", {})
                    chat_id = chat.get("id")
                    chat_title = chat.get("title") or chat.get("username") or chat.get("first_name") or "Telegram Chat"
                    if chat_id:
                        return True, f"Found chat: '{chat_title}' (ID: {chat_id})", str(chat_id)
            return False, "No recent group messages found. Please add the bot to your group and send a message (e.g. 'hello') in the group first!", None
        else:
            description = data.get("description", "Unknown error")
            return False, f"Telegram API Error: {description}", None
    except Exception as e:
        return False, f"Network Error: {str(e)}", None



def format_offline_alert(dvr):
    return (
        f"🔴 <b>ALERT: DVR OFFLINE</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Site Name:</b> {dvr.get('site', 'N/A')}\n"
        f"<b>IP Address:</b> <code>{dvr.get('ip', 'N/A')}</code>\n"
        f"<b>Time:</b> {dvr.get('last_checked', 'N/A')}\n"
        f"<b>Status:</b> Offline / Unreachable"
    )


def format_recovery_alert(dvr):
    return (
        f"🟢 <b>RECOVERED: DVR ONLINE</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Site Name:</b> {dvr.get('site', 'N/A')}\n"
        f"<b>IP Address:</b> <code>{dvr.get('ip', 'N/A')}</code>\n"
        f"<b>Latency:</b> {dvr.get('latency_ms', 0)}ms\n"
        f"<b>HDDs:</b> {dvr.get('hdd_count', 0)}\n"
        f"<b>Time:</b> {dvr.get('last_checked', 'N/A')}"
    )


def format_hdd_alert(dvr):
    return (
        f"⚠️ <b>WARNING: DVR HDD ISSUE</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Site Name:</b> {dvr.get('site', 'N/A')}\n"
        f"<b>IP Address:</b> <code>{dvr.get('ip', 'N/A')}</code>\n"
        f"<b>HDD Status:</b> {dvr.get('hdd_status', 'N/A')}\n"
        f"<b>HDD Message:</b> {dvr.get('hdd_message', 'N/A')}\n"
        f"<b>Time:</b> {dvr.get('last_checked', 'N/A')}"
    )


def format_summary_report(results, last_updated):
    total = len(results)
    online = sum(1 for r in results if r.get("online"))
    offline = total - online
    hdd_alerts = sum(1 for r in results if r.get("online") and (r.get("hdd_count", 0) == 0 or "ERROR" in str(r.get("hdd_status", ""))))

    msg_lines = [
        "📊 <b>DVR HEALTH MONITOR SUMMARY</b>",
        f"🕒 <i>Updated: {last_updated}</i>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"Total DVRs: <b>{total}</b>",
        f"🟢 Online: <b>{online}</b>",
        f"🔴 Offline: <b>{offline}</b>",
        f"⚠️ HDD Warnings: <b>{hdd_alerts}</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "<b>DVR Details:</b>"
    ]

    for r in results:
        site = r.get('site', 'N/A')
        ip = r.get('ip', 'N/A')
        if r.get('online'):
            hdd_cnt = r.get('hdd_count', 0)
            hdd_icon = "💾" if hdd_cnt > 0 else "⚠️"
            msg_lines.append(f"🟢 <b>{site}</b> (<code>{ip}</code>) | Latency: {r.get('latency_ms', 0)}ms | {hdd_icon} HDDs: {hdd_cnt}")
        else:
            msg_lines.append(f"🔴 <b>{site}</b> (<code>{ip}</code>) | OFFLINE")

    return "\n".join(msg_lines)


def format_scheduled_alert_report(results, last_updated):
    msg_lines = [
        "🕘 <b>SCHEDULED DVR ALERT REPORT</b>",
        f"🕒 <i>Updated: {last_updated}</i>",
        "━━━━━━━━━━━━━━━━━━━━",
        "<b>Only offline DVRs and HDD issues are included:</b>"
    ]

    for r in results:
        site = r.get('site', 'N/A')
        ip = r.get('ip', 'N/A')
        if not r.get('online', False):
            msg_lines.append(f"🔴 <b>{site}</b> (<code>{ip}</code>) | OFFLINE")
        else:
            msg_lines.append(f"⚠️ <b>{site}</b> (<code>{ip}</code>) | HDD Issue: {r.get('hdd_status', 'N/A')}")

    if len(results) == 0:
        msg_lines.append("✅ No offline DVRs or HDD issues detected.")

    return "\n".join(msg_lines)
