import threading
import time
from datetime import datetime
import os
import sys
import webbrowser

from flask import Flask, render_template, jsonify, request
import config
import monitor

if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    app = Flask(__name__, template_folder=template_folder)
else:
    app = Flask(__name__)

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


if __name__ == "__main__":
    print("\n========================================================")
    print("      HIKVISION DVR MONITOR WEB DASHBOARD STARTED")
    print("      Opening Browser: http://127.0.0.1:5000")
    print("========================================================\n")
    threading.Thread(target=lambda: (time.sleep(1.2), webbrowser.open("http://127.0.0.1:5000")), daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False)
