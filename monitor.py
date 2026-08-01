import os
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from requests.auth import HTTPDigestAuth, HTTPBasicAuth
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import get_dvrs, REFRESH_TIME

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"


def log(text):
    try:
        with open("log.txt", "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception as e:
        print(f"[Log Error] {e}")


def get_dvr_status(dvr):
    """
    Checks system status of a single DVR.
    Detects if DVR is ONLINE even if auth credentials need adjustment.
    """
    ip = dvr.get("ip")
    username = dvr.get("username", "admin")
    password = dvr.get("password", "")
    url = f"http://{ip}/ISAPI/System/status"

    start_time = time.time()
    try:
        # Try HTTPDigestAuth first
        r = requests.get(
            url,
            auth=HTTPDigestAuth(username, password),
            timeout=5,
        )
        latency = round((time.time() - start_time) * 1000)

        # Fallback to HTTPBasicAuth if HTTP 401
        if r.status_code == 401:
            try:
                r_basic = requests.get(
                    url,
                    auth=HTTPBasicAuth(username, password),
                    timeout=3,
                )
                if r_basic.status_code == 200:
                    r = r_basic
            except Exception:
                pass

        if r.status_code == 200:
            ns = {"hik": "http://www.hikvision.com/ver20/XMLSchema"}
            root = ET.fromstring(r.text)

            info = {}
            device_time = root.find("hik:currentDeviceTime", ns)
            uptime = root.find("hik:deviceUpTime", ns)
            memory = root.find(".//hik:memoryUsage", ns)

            if device_time is not None and device_time.text:
                info["device_time"] = device_time.text
            if uptime is not None and uptime.text:
                info["uptime"] = uptime.text
            if memory is not None and memory.text:
                info["memory"] = memory.text

            return True, latency, info, "OK"

        # If HTTP 401 or 403, device is physically ONLINE on network
        if r.status_code in (401, 403):
            return True, latency, {"auth_error": True}, f"AUTH_REQUIRED ({r.status_code})"

        return False, latency, None, f"HTTP_{r.status_code}"
    except Exception:
        latency = round((time.time() - start_time) * 1000)
        # Check HTTP root endpoint to confirm if device is reachable
        try:
            r_root = requests.get(f"http://{ip}/", timeout=3)
            if r_root.status_code in (200, 401, 403):
                return True, latency, {"auth_error": True}, "REACHABLE"
        except Exception:
            pass
        return False, latency, None, "OFFLINE"


def get_hdd_status(dvr):
    """
    Checks HDD status of a single DVR.
    """
    ip = dvr.get("ip")
    username = dvr.get("username", "admin")
    password = dvr.get("password", "")

    apis = [
        "/ISAPI/ContentMgmt/Storage",
        "/ISAPI/ContentMgmt/Storage/hdd",
        "/ISAPI/ContentMgmt/Storage/hdds",
        "/ISAPI/ContentMgmt/Storage/disks",
        "/ISAPI/ContentMgmt/Storage/volume",
    ]

    for api in apis:
        try:
            url = f"http://{ip}{api}"
            r = requests.get(
                url,
                auth=HTTPDigestAuth(username, password),
                timeout=5,
            )
            if r.status_code == 200:
                try:
                    ns = {"hik": "http://www.hikvision.com/ver20/XMLSchema"}
                    root = ET.fromstring(r.text)
                    work_mode = root.find("hik:workMode", ns)
                    hdd_nodes = root.findall(".//hik:hdd", ns)

                    if hdd_nodes:
                        details = []
                        for hdd in hdd_nodes:
                            name = hdd.find("hik:name", ns)
                            status = hdd.find("hik:status", ns)
                            capacity = hdd.find("hik:capacity", ns)
                            detail_parts = []
                            if name is not None and name.text:
                                detail_parts.append(f"name={name.text}")
                            if status is not None and status.text:
                                detail_parts.append(f"status={status.text}")
                            if capacity is not None and capacity.text:
                                detail_parts.append(f"capacity={capacity.text}")
                            if detail_parts:
                                details.append(" | ".join(detail_parts))

                        return {
                            "status": "HDD OK",
                            "message": f"Found {len(hdd_nodes)} HDD(s)",
                            "count": len(hdd_nodes),
                            "work_mode": work_mode.text if work_mode is not None and work_mode.text else "Normal",
                            "details": details,
                        }

                    return {
                        "status": "NO HDD DATA",
                        "message": "No HDD entries returned",
                        "count": 0,
                        "work_mode": work_mode.text if work_mode is not None and work_mode.text else "Unknown",
                        "details": [],
                    }
                except ET.ParseError:
                    return {
                        "status": "XML ERROR",
                        "message": "Storage XML parse error",
                        "count": 0,
                        "work_mode": "Unknown",
                        "details": [],
                    }
            elif r.status_code in (401, 403):
                return {
                    "status": "AUTH REQUIRED",
                    "message": "Correct username/password required for HDD info",
                    "count": 0,
                    "work_mode": "Protected",
                    "details": [],
                }
        except Exception:
            pass

    return {
        "status": "STORAGE UNREACHABLE",
        "message": "No storage endpoint responded",
        "count": 0,
        "work_mode": "Unknown",
        "details": [],
    }


def check_single_dvr(dvr):
    """
    Performs full health check for a single DVR object.
    Returns structured dict with results.
    """
    site = dvr.get("site", "Unknown")
    ip = dvr.get("ip", "0.0.0.0")
    
    online, latency, info, code = get_dvr_status(dvr)
    last_check_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if online:
        auth_error = info.get("auth_error", False) if info else False
        if not auth_error:
            storage_info = get_hdd_status(dvr)
            log(f"{last_check_str} [{site} - {ip}] ONLINE (Latency: {latency}ms)")
            return {
                "site": site,
                "ip": ip,
                "username": dvr.get("username", "admin"),
                "password": dvr.get("password", ""),
                "online": True,
                "latency_ms": latency,
                "device_time": info.get("device_time", "N/A"),
                "uptime": info.get("uptime", "N/A"),
                "memory": info.get("memory", "N/A"),
                "hdd_status": storage_info["status"],
                "hdd_message": storage_info["message"],
                "hdd_count": storage_info["count"],
                "work_mode": storage_info["work_mode"],
                "hdd_details": storage_info["details"],
                "last_checked": last_check_str,
            }
        else:
            log(f"{last_check_str} [{site} - {ip}] ONLINE (Auth Error)")
            return {
                "site": site,
                "ip": ip,
                "username": dvr.get("username", "admin"),
                "password": dvr.get("password", ""),
                "online": True,
                "latency_ms": latency,
                "device_time": "Auth Required",
                "uptime": "N/A",
                "memory": "N/A",
                "hdd_status": "AUTH REQUIRED",
                "hdd_message": "DVR is online on network, but ISAPI credentials returned 401 Unauthorized",
                "hdd_count": 0,
                "work_mode": "Auth Lock",
                "hdd_details": ["Check username/password in dvrs.json or DVR ISAPI permissions"],
                "last_checked": last_check_str,
            }
    else:
        log(f"{last_check_str} [{site} - {ip}] OFFLINE")
        return {
            "site": site,
            "ip": ip,
            "username": dvr.get("username", "admin"),
            "password": dvr.get("password", ""),
            "online": False,
            "latency_ms": latency,
            "device_time": "N/A",
            "uptime": "N/A",
            "memory": "N/A",
            "hdd_status": "OFFLINE",
            "hdd_message": "DVR connection failed",
            "hdd_count": 0,
            "work_mode": "Offline",
            "hdd_details": [],
            "last_checked": last_check_str,
        }


def check_all_dvrs_concurrently(dvrs_list=None, max_workers=30):
    """
    Checks status for all configured DVRs concurrently.
    """
    if dvrs_list is None:
        dvrs_list = get_dvrs()

    if not dvrs_list:
        return []

    results = []
    actual_workers = min(max_workers, max(1, len(dvrs_list)))
    with ThreadPoolExecutor(max_workers=actual_workers) as executor:
        future_to_dvr = {executor.submit(check_single_dvr, dvr): dvr for dvr in dvrs_list}
        for future in as_completed(future_to_dvr):
            try:
                res = future.result()
                results.append(res)
            except Exception as e:
                dvr = future_to_dvr[future]
                results.append({
                    "site": dvr.get("site", "Unknown"),
                    "ip": dvr.get("ip", "0.0.0.0"),
                    "online": False,
                    "latency_ms": 0,
                    "device_time": "N/A",
                    "uptime": "N/A",
                    "memory": "N/A",
                    "hdd_status": "ERROR",
                    "hdd_message": str(e),
                    "hdd_count": 0,
                    "work_mode": "Error",
                    "hdd_details": [],
                    "last_checked": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
    
    results.sort(key=lambda x: (x.get("site", ""), x.get("ip", "")))
    return results


def main():
    """
    CLI Loop for run.bat
    """
    while True:
        clear_cmd = "cls" if os.name == "nt" else "clear"
        os.system(clear_cmd)

        dvrs = get_dvrs()
        total_count = len(dvrs)

        print(CYAN)
        print("=" * 80)
        print(f"        HIKVISION DVR HEALTH MONITOR (Total DVRs: {total_count})")
        print("=" * 80)
        print(RESET)

        print(f"Scanning {total_count} DVR(s) concurrently across Intranet...\n")
        start_scan = time.time()
        results = check_all_dvrs_concurrently(dvrs)
        scan_duration = round(time.time() - start_scan, 2)

        online_count = sum(1 for r in results if r["online"])
        offline_count = total_count - online_count
        hdd_ok_count = sum(1 for r in results if r["online"] and r["hdd_count"] > 0)

        print(f"Summary: {GREEN}Online: {online_count}{RESET} | {RED}Offline: {offline_count}{RESET} | HDD OK: {hdd_ok_count} | Scan Time: {scan_duration}s")
        print("-" * 80)

        header = f"{'SITE NAME':<22} | {'IP ADDRESS':<16} | {'STATUS':<10} | {'LATENCY':<8} | {'HDDs':<6} | {'UPTIME'}"
        print(header)
        print("-" * 80)

        for res in results:
            site = (res['site'][:20] + '..') if len(res['site']) > 22 else res['site']
            ip = res['ip']
            if res['online']:
                status_str = f"{GREEN}ONLINE{RESET}"
                latency_str = f"{res['latency_ms']}ms"
                hdd_str = str(res['hdd_count'])
                uptime_str = f"{res['uptime']} min" if res['uptime'] != 'N/A' else "-"
            else:
                status_str = f"{RED}OFFLINE{RESET}"
                latency_str = "TIMEOUT"
                hdd_str = "0"
                uptime_str = "-"

            print(f"{site:<22} | {ip:<16} | {status_str:<19} | {latency_str:<8} | {hdd_str:<6} | {uptime_str}")

        print("\n" + "=" * 80)
        print(f"Checking again in {REFRESH_TIME} seconds... (Press Ctrl+C to stop)")

        try:
            time.sleep(REFRESH_TIME)
        except KeyboardInterrupt:
            print("\nMonitoring stopped.")
            break


if __name__ == "__main__":
    main()