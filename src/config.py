# ==========================
# DVR Configuration Manager (AES-256 Encrypted Storage)
# ==========================

import os
import sys
import json
import shutil
from cryptography.fernet import Fernet


def get_project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_config_dir():
    project_root = get_project_root()
    candidates = [project_root]

    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        cwd = os.getcwd()
        candidates.extend([exe_dir, cwd, os.path.dirname(exe_dir)])
    else:
        cwd = os.getcwd()
        candidates.extend([cwd, os.path.dirname(os.path.abspath(__file__))])

    for candidate in candidates:
        dvrs_path = os.path.join(candidate, "dvrs.json")
        key_path = os.path.join(candidate, ".secret.key")
        telegram_path = os.path.join(candidate, "telegram_config.json")
        if os.path.exists(dvrs_path) or os.path.exists(key_path) or os.path.exists(telegram_path):
            return candidate

    return project_root

CONFIG_DIR = get_config_dir()
DVRS_FILE = os.path.join(CONFIG_DIR, "dvrs.json")
KEY_FILE = os.path.join(CONFIG_DIR, ".secret.key")
TELEGRAM_FILE = os.path.join(CONFIG_DIR, "telegram_config.json")
REFRESH_TIME = 10




def get_or_create_cipher():
    """Gets or generates secret encryption key for AES-256 password protection."""
    if os.path.exists(KEY_FILE):
        try:
            with open(KEY_FILE, "rb") as f:
                key = f.read().strip()
                if key:
                    return Fernet(key)
        except Exception:
            pass
    
    # Generate new key
    key = Fernet.generate_key()
    try:
        with open(KEY_FILE, "wb") as f:
            f.write(key)
    except Exception as e:
        print(f"[Crypto Error] Could not write secret key: {e}")
    return Fernet(key)


cipher = get_or_create_cipher()


def encrypt_password(plain_password):
    """Encrypts a plaintext password."""
    if not plain_password:
        return ""
    if plain_password.startswith("ENC:"):
        return plain_password # Already encrypted
    try:
        token = cipher.encrypt(plain_password.encode("utf-8")).decode("utf-8")
        return f"ENC:{token}"
    except Exception as e:
        print(f"[Crypto Error] Encryption failed: {e}")
        return plain_password


def decrypt_password(encrypted_password):
    """Decrypts an encrypted password."""
    if not encrypted_password:
        return ""
    if not encrypted_password.startswith("ENC:"):
        return encrypted_password # Plaintext fallback
    try:
        raw_token = encrypted_password[4:].encode("utf-8")
        return cipher.decrypt(raw_token).decode("utf-8")
    except Exception as e:
        print(f"[Crypto Error] Decryption failed: {e}")
        return encrypted_password


# Default initial DVR list if dvrs.json doesn't exist
DEFAULT_DVRS = [
    {
        "site": "Test DVR",
        "ip": "10.64.2.253",
        "username": "admin",
        "password": "test@125"
    }
]


def load_dvrs():
    """
    Loads DVR list from dvrs.json and decrypts passwords in memory.
    Automatically migrates any legacy plaintext passwords to encrypted format on disk.
    """
    dvrs_to_load = []
    if os.path.exists(DVRS_FILE):
        try:
            with open(DVRS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    dvrs_to_load = data
        except Exception as e:
            print(f"[Config] Error loading dvrs.json: {e}")

    if not dvrs_to_load:
        dvrs_to_load = DEFAULT_DVRS
        save_dvrs(dvrs_to_load)

    # Auto-encrypt any plaintext passwords found on disk
    needs_re_save = False
    memory_dvrs = []
    for item in dvrs_to_load:
        pwd = item.get("password", "")
        if not pwd.startswith("ENC:"):
            needs_re_save = True
        
        # In memory, we provide the decrypted password for monitor.py
        decrypted_item = dict(item)
        decrypted_item["password"] = decrypt_password(pwd)
        memory_dvrs.append(decrypted_item)

    if needs_re_save:
        save_dvrs(memory_dvrs)

    return memory_dvrs


def save_dvrs(dvrs):
    """Saves DVR list to dvrs.json with passwords AES-256 encrypted."""
    global DVRS, DVR
    disk_dvrs = []
    for item in dvrs:
        disk_item = dict(item)
        disk_item["password"] = encrypt_password(item.get("password", ""))
        disk_dvrs.append(disk_item)

    try:
        with open(DVRS_FILE, "w", encoding="utf-8") as f:
            json.dump(disk_dvrs, f, indent=4, ensure_ascii=False)
        
        # Keep decrypted in memory
        DVRS = dvrs
        if DVRS:
            DVR = DVRS[0]
        return True
    except Exception as e:
        print(f"[Config] Error saving dvrs.json: {e}")
        return False


def get_dvrs():
    """Returns the current list of DVRs (decrypted in memory)."""
    return load_dvrs()


def add_dvr(site, ip, username="admin", password="test@125"):
    """Adds or updates a single DVR entry."""
    site = site.strip() if site else f"DVR-{ip}"
    ip = ip.strip()
    username = username.strip() if username else "admin"
    password = password.strip() if password else "test@125"

    dvrs = load_dvrs()

    updated = False
    for item in dvrs:
        if item.get("ip") == ip:
            item["site"] = site
            item["username"] = username
            item["password"] = password
            updated = True
            break
    
    if not updated:
        dvrs.append({
            "site": site,
            "ip": ip,
            "username": username,
            "password": password
        })
    
    save_dvrs(dvrs)
    return dvrs


def bulk_import_dvrs(text_data, default_user="admin", default_pass="test@125"):
    """
    Parses multi-line text or CSV input.
    Formats supported per line:
      - Site Name, IP, Username, Password
      - Site Name, IP
      - IP
    """
    added_count = 0
    lines = text_data.strip().splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if len(parts) >= 4:
            site, ip, user, pwd = parts[0], parts[1], parts[2], parts[3]
        elif len(parts) == 3:
            site, ip, user, pwd = parts[0], parts[1], parts[2], default_pass
        elif len(parts) == 2:
            site, ip, user, pwd = parts[0], parts[1], default_user, default_pass
        elif len(parts) == 1:
            ip = parts[0]
            site = f"DVR-{ip}"
            user, pwd = default_user, default_pass
        else:
            continue
        
        if "." in ip:
            add_dvr(site, ip, user, pwd)
            added_count += 1
            
    return added_count


def remove_dvr(ip_or_site):
    """Removes a DVR by IP or Site Name."""
    target = ip_or_site.strip()
    dvrs = load_dvrs()
    new_dvrs = [d for d in dvrs if d.get("ip") != target and d.get("site") != target]
    save_dvrs(new_dvrs)
    return new_dvrs


DEFAULT_TELEGRAM_CONFIG = {
    "enabled": False,
    "bot_token": "",
    "chat_id": "",
    "notify_offline": True,
    "notify_hdd": True,
    "notify_summary": True,
    "summary_interval_minutes": 60
}


def load_telegram_config():
    """Loads Telegram notification configuration."""
    if os.path.exists(TELEGRAM_FILE):
        try:
            with open(TELEGRAM_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    merged = dict(DEFAULT_TELEGRAM_CONFIG)
                    merged.update(data)
                    return merged
        except Exception as e:
            print(f"[Config] Error loading telegram_config.json: {e}")
    return dict(DEFAULT_TELEGRAM_CONFIG)


def save_telegram_config(config_dict):
    """Saves Telegram notification configuration."""
    current = load_telegram_config()
    current.update(config_dict)
    try:
        with open(TELEGRAM_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[Config] Error saving telegram_config.json: {e}")
        return False


# Initialize global variables
DVRS = load_dvrs()
DVR = DVRS[0] if DVRS else DEFAULT_DVRS[0]