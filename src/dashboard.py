import threading
import time
from datetime import datetime
import os
import sys
import webbrowser

from flask import Flask, render_template, jsonify, request
import config
import monitor
import telegram_bot


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "templates")

if getattr(sys, 'frozen', False):
    frozen_template_folder = os.path.join(sys._MEIPASS, 'templates')
    if os.path.exists(frozen_template_folder):
        TEMPLATES_DIR = frozen_template_folder
    else:
        TEMPLATES_DIR = os.path.join(os.path.dirname(sys.executable), 'templates')

app = Flask(__name__, template_folder=TEMPLATES_DIR)

# Global cache for status results
cached_results = []
last_updated_time = None
is_scanning = False
scan_lock = threading.Lock()


def run_scan():
    """Performs a background scan of all DVRs and updates cache."""
    global cached_results, last_updated_time, is_scanning
    with scan_lock:
        is_scanning = True
        try:
            dvrs = config.get_dvrs()
            results = monitor.check_all_dvrs_concurrently(dvrs)
            cached_results = results
            last_updated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            print(f"[Dashboard Background Scan Error] {e}")
        finally:
            is_scanning = False


def background_poller():
    """Periodic background thread to update DVR health stats."""
    while True:
        run_scan()
        time.sleep(config.REFRESH_TIME)


# Start background polling thread on server boot
poller_thread = threading.Thread(target=background_poller, daemon=True)
poller_thread.start()


@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/status", methods=["GET"])
def get_status():
    total = len(cached_results)
    online = sum(1 for r in cached_results if r.get("online"))
    offline = total - online
    # HDD Alert if online but hdd_count == 0 or status contains error
    hdd_alerts = sum(1 for r in cached_results if r.get("online") and r.get("hdd_count", 0) == 0)

    return jsonify({
        "status": "success",
        "is_scanning": is_scanning,
        "last_updated": last_updated_time or "Never",
        "summary": {
            "total": total,
            "online": online,
            "offline": offline,
            "hdd_alerts": hdd_alerts
        },
        "dvrs": cached_results
    })


@app.route("/api/scan", methods=["POST"])
def trigger_scan():
    # Run scan synchronously or in thread
    thread = threading.Thread(target=run_scan)
    thread.start()
    thread.join(timeout=10) # wait up to 10s
    return jsonify({"status": "success", "message": "Scan triggered", "is_scanning": is_scanning})


@app.route("/api/dvr/add", methods=["POST"])
def api_add_dvr():
    data = request.json or {}
    site = data.get("site", "")
    ip = data.get("ip", "")
    username = data.get("username", "admin")
    password = data.get("password", "test@125")

    if not ip or "." not in ip:
        return jsonify({"status": "error", "message": "Valid IP address is required"}), 400

    config.add_dvr(site, ip, username, password)
    # Trigger quick background update
    threading.Thread(target=run_scan, daemon=True).start()
    return jsonify({"status": "success", "message": f"DVR {ip} added successfully"})


@app.route("/api/dvr/bulk-import", methods=["POST"])
def api_bulk_import():
    data = request.json or {}
    text_data = data.get("text", "")
    default_user = data.get("username", "admin")
    default_pass = data.get("password", "test@125")

    if not text_data.strip():
        return jsonify({"status": "error", "message": "No input text provided"}), 400

    count = config.bulk_import_dvrs(text_data, default_user, default_pass)
    # Trigger background scan update
    threading.Thread(target=run_scan, daemon=True).start()
    return jsonify({"status": "success", "message": f"Successfully imported {count} DVR(s)"})


@app.route("/api/dvr/delete", methods=["POST"])
def api_delete_dvr():
    data = request.json or {}
    ip = data.get("ip", "")
    if not ip:
        return jsonify({"status": "error", "message": "IP address is required"}), 400

    config.remove_dvr(ip)
    # Trigger background scan update
    threading.Thread(target=run_scan, daemon=True).start()
    return jsonify({"status": "success", "message": f"DVR {ip} removed successfully"})


@app.route("/api/telegram/config", methods=["GET", "POST"])
def api_telegram_config():
    if request.method == "GET":
        tg_cfg = config.load_telegram_config()
        return jsonify({"status": "success", "config": tg_cfg})
    else:
        data = request.json or {}
        config.save_telegram_config(data)
        return jsonify({"status": "success", "message": "Telegram configuration saved successfully"})


@app.route("/api/telegram/test", methods=["POST"])
def api_telegram_test():
    data = request.json or {}
    bot_token = data.get("bot_token") or config.load_telegram_config().get("bot_token")
    chat_id = data.get("chat_id") or config.load_telegram_config().get("chat_id")

    if not bot_token or not chat_id:
        return jsonify({"status": "error", "message": "Both Bot Token and Chat ID are required"}), 400

    ok, msg = telegram_bot.test_telegram_connection(bot_token, chat_id)
    if ok:
        return jsonify({"status": "success", "message": msg})
    else:
        return jsonify({"status": "error", "message": msg}), 400


@app.route("/api/telegram/summary", methods=["POST"])
def api_telegram_summary():
    tg_cfg = config.load_telegram_config()
    bot_token = tg_cfg.get("bot_token")
    chat_id = tg_cfg.get("chat_id")

    if not bot_token or not chat_id:
        return jsonify({"status": "error", "message": "Telegram Bot Token and Chat ID must be configured first"}), 400

    last_update_str = last_updated_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary_msg = telegram_bot.format_summary_report(cached_results, last_update_str)
    ok, msg = telegram_bot.send_telegram_message(bot_token, chat_id, summary_msg)

    if ok:
        return jsonify({"status": "success", "message": "Summary report sent to Telegram successfully!"})
    else:
        return jsonify({"status": "error", "message": msg}), 400


@app.route("/api/telegram/auto-detect", methods=["POST"])
def api_telegram_auto_detect():
    data = request.json or {}
    bot_token = data.get("bot_token") or config.load_telegram_config().get("bot_token")

    if not bot_token:
        return jsonify({"status": "error", "message": "Bot Token is required"}), 400

    ok, msg, chat_id = telegram_bot.auto_detect_chat_id(bot_token)
    if ok and chat_id:
        # Save detected chat_id automatically
        config.save_telegram_config({"chat_id": chat_id})
        return jsonify({"status": "success", "message": msg, "chat_id": chat_id})
    else:
        return jsonify({"status": "error", "message": msg}), 400




if __name__ == "__main__":
    print("\n========================================================")
    print("      HIKVISION DVR MONITOR WEB DASHBOARD STARTED")
    print("      Opening Browser: http://127.0.0.1:5000")
    print("========================================================\n")
    threading.Thread(target=lambda: (time.sleep(1.2), webbrowser.open("http://127.0.0.1:5000")), daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False)
