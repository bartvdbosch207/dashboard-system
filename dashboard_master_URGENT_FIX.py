import json
import os
import sys
import subprocess
import threading
import time
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
from casa_cara import casa_cara

IS_RENDER = bool(os.environ.get("RENDER")) or bool(os.environ.get("PORT"))

if IS_RENDER:
    BASE_DIR = Path(__file__).resolve().parent
    STATIC_DIR = BASE_DIR / "static"
    DATA_ROOT = BASE_DIR / "data"
    DATA_DIR = DATA_ROOT / "casa_cara"
else:
    BASE_DIR = Path("/Users/bartvandenbosch/Desktop/Dropbox")
    STATIC_DIR = BASE_DIR / "static"
    DATA_ROOT = BASE_DIR
    DATA_DIR = BASE_DIR / "Data" / "Casa Cara"

BAR_FILE = DATA_DIR / "bar_koelingen.json"
GENERAL_FILE = DATA_DIR / "algemeen.json"
STATE_FILE = DATA_DIR / "bar_state.json"
PRODUCT_TYPES_FILE = DATA_DIR / "product_soorten.json"
LOCATIONS_FILE = DATA_DIR / "locaties.json"
OP_FILE = DATA_DIR / "op_list.json"

STATS_FILE = DATA_ROOT / "dashboard_stats.json"
TRASH_FILE = DATA_ROOT / "trash_history.json"
DOWNLOADS_FILE = DATA_ROOT / "downloads_history.json"
KEPT_FILE = DATA_ROOT / "kept_history.json"
ACTIVITY_FILE = DATA_ROOT / "activity_history.json"
PENDING_TRASH_FILE = DATA_ROOT / "pending_trash.json"
LOCK_FILE = DATA_ROOT / "run.lock"

GMAIL_SCRIPT = (BASE_DIR / "System" / "gmail_filter.py") if not IS_RENDER else (BASE_DIR / "gmail_filter.py")
DOCUMENTEN_MAP = BASE_DIR / "Documenten"
LOONSTROKEN_MAP = BASE_DIR / "Loonstroken"
FOTOS_MAP = BASE_DIR / "Foto's"

PYTHON_BIN = sys.executable

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
app.secret_key = os.environ.get("APP_SECRET_KEY", "casa-cara-dashboard-secret-key")
app.register_blueprint(casa_cara)
AUTH_FILE = DATA_ROOT / "auth.json"
GMAIL_AUTH_FILE = DATA_ROOT / "gmail_auth.json"
CASA_AUTH_FILE = Path(__file__).resolve().parent / "data" / "casa_cara" / "casa_auth.json"
MASTER_PASSWORD = "Beeldaliba1*"

DEFAULT_STATS = {
    "last_run": None,
    "last_status": "Nog niet uitgevoerd",
    "emails_scanned": 0,
    "pdfs_downloaded": 0,
    "emails_trashed": 0,
    "protected_kept": 0,
    "important_kept": 0,
    "duplicate_skipped": 0,
    "last_run_mode": "volledig",
    "is_running": False,
    "progress_current": 0,
    "progress_total": 0,
    "run_scanned_delta": 0,
    "run_pdfs_delta": 0,
    "run_trashed_delta": 0,
    "run_protected_delta": 0,
    "run_important_delta": 0,
    "run_duplicate_delta": 0,
    "logs": []
}

DAY_NAMES_NL = {
    0: "Maandag",
    1: "Dinsdag",
    2: "Woensdag",
    3: "Donderdag",
    4: "Vrijdag",
    5: "Zaterdag",
    6: "Zondag",
}


def ensure_files():
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not BAR_FILE.exists():
        BAR_FILE.write_text(json.dumps({
            "koelingen": [
                {
                    "id": "bar",
                    "naam": "Koeling Bar",
                    "producten": [
                        {"id": "cola", "naam": "Cola", "voorraad": 4, "minimum": 6, "soort": "Frisdrank"},
                        {"id": "fanta", "naam": "Fanta", "voorraad": 2, "minimum": 4, "soort": "Frisdrank"},
                        {"id": "heineken", "naam": "Heineken", "voorraad": 8, "minimum": 10, "soort": "Bier"},
                    ]
                }
            ]
        }, indent=2, ensure_ascii=False), encoding="utf-8")

    if not GENERAL_FILE.exists():
        GENERAL_FILE.write_text(json.dumps({
            "fooienpot": 0,
            "diensten": []
        }, indent=2, ensure_ascii=False), encoding="utf-8")

    if not PRODUCT_TYPES_FILE.exists():
        PRODUCT_TYPES_FILE.write_text(json.dumps([
            {"naam": "Frisdrank", "locatie": "Magazijn"},
            {"naam": "Bier", "locatie": "Kelder"},
            {"naam": "Wijn", "locatie": "Wijnrek"},
            {"naam": "Water", "locatie": "Magazijn"},
            {"naam": "Mixers", "locatie": "Bar"},
            {"naam": "Overig", "locatie": "-"}
        ], indent=2, ensure_ascii=False), encoding="utf-8")

    if not LOCATIONS_FILE.exists():
        LOCATIONS_FILE.write_text(json.dumps([
            "Magazijn",
            "Kelder",
            "Wijnrek",
            "Bar",
            "-"
        ], indent=2, ensure_ascii=False), encoding="utf-8")

    if not OP_FILE.exists():
        OP_FILE.write_text(json.dumps({"items": []}, indent=2, ensure_ascii=False), encoding="utf-8")

    if not STATE_FILE.exists():
        STATE_FILE.write_text(json.dumps({"checked_fill_items": []}, indent=2, ensure_ascii=False), encoding="utf-8")

    if not AUTH_FILE.exists():
        AUTH_FILE.write_text(json.dumps({"access_code": ""}, indent=2, ensure_ascii=False), encoding="utf-8")

    if not GMAIL_AUTH_FILE.exists():
        GMAIL_AUTH_FILE.write_text(json.dumps({"access_code": ""}, indent=2, ensure_ascii=False), encoding="utf-8")

    if not CASA_AUTH_FILE.exists():
        CASA_AUTH_FILE.write_text(json.dumps({"users": []}, indent=2, ensure_ascii=False), encoding="utf-8")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def load_auth():
    ensure_files()
    return load_json(AUTH_FILE)

def save_auth(data):
    save_json(AUTH_FILE, data)

def has_access_code():
    data = load_auth()
    return bool((data.get("access_code") or "").strip())

def load_gmail_auth():
    ensure_files()
    return load_json(GMAIL_AUTH_FILE)

def save_gmail_auth(data):
    save_json(GMAIL_AUTH_FILE, data)

def gmail_code_exists():
    data = load_gmail_auth()
    return bool((data.get("access_code") or "").strip())

def gmail_logged_in():
    return bool(session.get("gmail_logged_in"))

def load_casa_auth():
    ensure_files()
    if not CASA_AUTH_FILE.exists():
        save_json(CASA_AUTH_FILE, {"users": []})
    data = load_json_file(CASA_AUTH_FILE, {"users": []})
    if not isinstance(data, dict):
        data = {"users": []}
    users = []
    for item in data.get("users", []):
        if not isinstance(item, dict):
            continue
        pin = str(item.get("pin") or "").strip()
        if not pin:
            continue
        users.append({
            "name": (item.get("name") or item.get("username") or "Gebruiker").strip() or "Gebruiker",
            "pin": pin,
            "role": "admin" if (item.get("role") or "").strip().lower() == "admin" else "medewerker",
            "active": bool(item.get("active", True)),
        })
    data["users"] = users
    return data

def save_casa_auth(data):
    ensure_files()
    clean_users = []
    for item in data.get("users", []):
        if not isinstance(item, dict):
            continue
        pin = str(item.get("pin") or "").strip()
        if not pin:
            continue
        clean_users.append({
            "name": (item.get("name") or "Gebruiker").strip() or "Gebruiker",
            "pin": pin,
            "role": "admin" if (item.get("role") or "").strip().lower() == "admin" else "medewerker",
            "active": bool(item.get("active", True)),
        })
    save_json(CASA_AUTH_FILE, {"users": clean_users})

def casa_users_exist():
    return any(u.get("active", True) for u in load_casa_auth().get("users", []))

def find_casa_user_by_pin(pin: str):
    pin = (pin or "").strip()
    if not pin:
        return None
    for user in load_casa_auth().get("users", []):
        if user.get("active", True) and (user.get("pin") or "") == pin:
            return user
    return None

def is_logged_in():
    return bool(session.get("dashboard_logged_in"))


def is_casa_logged_in():
    return bool(session.get("casa_logged_in"))



def load_json_file(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def load_stats():
    data = DEFAULT_STATS.copy()
    data.update(load_json_file(STATS_FILE, {}))
    return data


def gmail_process_running():
    stats = load_stats()
    return LOCK_FILE.exists() or bool(stats.get("is_running"))


def start_gmail_subprocess(args):
    if not GMAIL_SCRIPT.exists():
        return False

    def _run():
        subprocess.run([PYTHON_BIN, str(GMAIL_SCRIPT), *args], cwd=str(BASE_DIR), check=False)
    threading.Thread(target=_run, daemon=True).start()
    return True


def slugify(text: str) -> str:
    clean = ''.join(ch.lower() if ch.isalnum() else '_' for ch in text.strip())
    while '__' in clean:
        clean = clean.replace('__', '_')
    return clean.strip('_') or "item"


def format_day_label(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return f"{DAY_NAMES_NL[dt.weekday()]} {dt.strftime('%d-%m-%Y')}"
    except Exception:
        return date_str


def get_types():
    raw = load_json(PRODUCT_TYPES_FILE)
    migrated = []
    changed = False
    for item in raw:
        if isinstance(item, str):
            migrated.append({"naam": item, "locatie": "-"})
            changed = True
        elif isinstance(item, dict):
            migrated.append({
                "naam": item.get("naam", "Overig"),
                "locatie": item.get("locatie", "-")
            })
        else:
            changed = True
    deduped = {}
    for item in migrated:
        deduped[item["naam"]] = item
    result = sorted(deduped.values(), key=lambda x: x.get("naam", "").lower())
    if changed or result != raw:
        save_json(PRODUCT_TYPES_FILE, result)
    return result

def get_locations():
    raw = load_json(LOCATIONS_FILE)
    migrated = []
    changed = False
    for item in raw:
        if isinstance(item, str):
            migrated.append(item)
        elif isinstance(item, dict):
            migrated.append(item.get("naam", "-"))
            changed = True
        else:
            changed = True
    result = sorted(list(dict.fromkeys([x for x in migrated if x])), key=lambda x: x.lower())
    if "-" not in result:
        result.append("-")
    if changed or result != raw:
        save_json(LOCATIONS_FILE, result)
    return result


def type_location(type_name: str) -> str:
    for t in get_types():
        if t.get("naam") == type_name:
            return t.get("locatie", "-")
    return "-"


def load_op_items():
    data = load_json(OP_FILE)
    return data.get("items", [])

def save_op_items(items):
    save_json(OP_FILE, {"items": items})


def normalize_bar_data():
    bar_data = load_json(BAR_FILE)
    changed = False
    types = get_types()
    type_names = {t.get("naam") for t in types}

    for cooling in bar_data.get("koelingen", []):
        for product in cooling.get("producten", []):
            if "soort" not in product:
                product["soort"] = "Overig"
                changed = True
            if product.get("soort") not in type_names:
                product["soort"] = "Overig"
                changed = True
    if changed:
        save_json(BAR_FILE, bar_data)


def build_fill_items(bar_data):
    op_pairs = {(x.get("koeling_id"), x.get("product_id")) for x in load_op_items()}
    items = []
    for cooling in bar_data.get("koelingen", []):
        for product in cooling.get("producten", []):
            if (cooling.get("id"), product.get("id")) in op_pairs:
                continue
            voorraad = int(product.get("voorraad", 0))
            minimum = int(product.get("minimum", 0))
            soort = product.get("soort", "Overig")
            locatie = type_location(soort)
            if voorraad < minimum:
                items.append({
                    "koeling_id": cooling.get("id"),
                    "koeling": cooling.get("naam"),
                    "product_id": product.get("id"),
                    "product": product.get("naam"),
                    "soort": soort,
                    "voorraad": voorraad,
                    "minimum": minimum,
                    "bijvullen": max(minimum - voorraad, 0),
                    "locatie": locatie
                })
    items.sort(key=lambda x: (x["locatie"].lower(), x["soort"].lower(), x["koeling"].lower(), x["product"].lower()))
    return items




LOGIN_HTML = """
<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover, maximum-scale=1.0, user-scalable=no">
<meta name="theme-color" content="#08111d">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>Dashboard login</title>
<style>
:root{
  --bg:#08111d; --bg2:#0b1625; --panel:#0f1b2d; --panel2:#0c1522; --text:#eef4fb; --muted:#9fb0c7;
  --line:rgba(159,176,199,.14); --accent:#38bdf8; --accent2:#8be1ff; --shadow:0 24px 64px rgba(0,0,0,.36);
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;min-height:100%;background:#08111d !important;color:var(--text);color-scheme:dark;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif;overscroll-behavior:none}
body{min-height:100dvh;min-height:100svh;display:flex;align-items:center;justify-content:center;padding:24px;padding-top:max(24px, env(safe-area-inset-top,0px));padding-bottom:max(24px, env(safe-area-inset-bottom,0px));background:#08111d !important;position:relative;overflow-x:hidden}
.bg{position:fixed;inset:0;background:radial-gradient(circle at top left, rgba(139,225,255,.11), transparent 28%),radial-gradient(circle at top right, rgba(148,163,184,.08), transparent 24%),radial-gradient(circle at bottom center, rgba(56,189,248,.08), transparent 30%),linear-gradient(180deg, var(--bg), var(--bg2));z-index:-3}body::before{content:"";position:fixed;inset:0;background:#08111d;z-index:-4}.wrap{width:min(430px,100%)}.brand{display:flex;align-items:center;justify-content:center;gap:12px;margin-bottom:18px}.brand-badge{width:46px;height:46px;border-radius:16px;display:grid;place-items:center;background:rgba(255,255,255,.05);border:1px solid var(--line);box-shadow:var(--shadow);font-size:18px}.brand-text{display:flex;flex-direction:column;align-items:flex-start}.brand-kicker{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}.brand-title{font-size:18px;font-weight:900;letter-spacing:-.03em}.card{background:linear-gradient(180deg, rgba(15,27,45,.96), rgba(10,19,31,.94));border:1px solid var(--line);border-radius:32px;padding:24px 22px 20px;box-shadow:var(--shadow);position:relative}.card::after{content:"";position:absolute;inset:0;border-radius:32px;pointer-events:none;box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}.head{text-align:center;margin-bottom:18px}.kicker{display:inline-flex;align-items:center;gap:8px;padding:8px 12px;border-radius:999px;margin-bottom:14px;background:rgba(56,189,248,.10);border:1px solid rgba(139,225,255,.18);color:#cdefff;font-size:12px;font-weight:800;letter-spacing:.1em;text-transform:uppercase}.kicker::before{content:"";width:8px;height:8px;border-radius:999px;background:var(--accent);box-shadow:0 0 0 5px rgba(56,189,248,.12)}h1{margin:0 0 10px;font-size:38px;line-height:1.02;letter-spacing:-.05em}p{margin:0;color:var(--muted);line-height:1.55;font-size:14px}.msg{margin:14px 0 0;padding:12px 14px;border-radius:16px;font-size:14px;text-align:left}.msg.error{background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.22);color:#ffd7d7}.msg.ok{background:rgba(34,197,94,.12);border:1px solid rgba(34,197,94,.22);color:#d4ffe3}.dots{display:flex;justify-content:center;gap:12px;margin:24px 0 20px}.dot{width:16px;height:16px;border-radius:999px;border:1px solid rgba(159,176,199,.25);background:rgba(255,255,255,.04);box-shadow:inset 0 1px 1px rgba(255,255,255,.04)}.dot.filled{background:linear-gradient(180deg,var(--accent2),var(--accent));border-color:rgba(139,225,255,.42)}.pad{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.key{min-height:60px;border:none;border-radius:20px;cursor:pointer;color:var(--text);font-size:22px;font-weight:900;background:linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.025));border:1px solid rgba(159,176,199,.12);box-shadow:0 12px 24px rgba(0,0,0,.18)}.key:active{transform:scale(.985)}.key.small{font-size:14px}.key.action{background:linear-gradient(180deg,#8be1ff,#38bdf8);color:#08263a}.toolbar{display:flex;justify-content:center;align-items:center;margin-top:16px;text-align:center}.help{color:var(--muted);font-size:13px;max-width:260px}.gear{position:absolute;right:14px;bottom:14px;width:42px;height:42px;border-radius:15px;border:1px solid rgba(159,176,199,.12);background:rgba(255,255,255,.04);color:var(--text);cursor:pointer;font-size:18px}.sheet{position:fixed;inset:0;background:rgba(0,0,0,.60);display:none;align-items:flex-end;justify-content:center;padding:14px;z-index:30}.sheet.open{display:flex}.sheet-card{width:min(430px,100%);background:linear-gradient(180deg, rgba(15,27,45,.98), rgba(10,19,31,.96));border:1px solid var(--line);border-radius:28px;padding:18px;box-shadow:var(--shadow)}.sheet-card h2{margin:0 0 8px;font-size:24px;letter-spacing:-.03em}.sheet-card p{margin:0 0 14px}.field{display:grid;gap:6px;margin-bottom:10px}.field label{font-size:13px;color:var(--muted)}.field input{width:100%;min-height:50px;border-radius:15px;border:1px solid rgba(159,176,199,.15);background:rgba(255,255,255,.04);color:var(--text);padding:0 14px;font-size:14px;outline:none}.row{display:flex;gap:10px;justify-content:flex-end;margin-top:8px}.btn{min-height:46px;border:none;border-radius:15px;padding:0 16px;font-weight:900;cursor:pointer}.btn.secondary{background:rgba(255,255,255,.06);color:var(--text);border:1px solid rgba(159,176,199,.12)}.btn.primary{background:linear-gradient(180deg,#8be1ff,#38bdf8);color:#08263a}.hidden{display:none}
@media (max-width:480px){body{padding-left:18px;padding-right:18px}.card{padding:22px 18px 18px}h1{font-size:34px}.key{min-height:56px}}
</style>
</head>
<body>
<div class="bg"></div>
<div class="wrap">
  <div class="brand"><div class="brand-badge">⌂</div><div class="brand-text"><div class="brand-kicker">Beveiligde toegang</div><div class="brand-title">Dashboard</div></div></div>
  <div class="card">
    <div class="head">
      <div class="kicker">Pincode login</div>
      <h1>Welkom terug</h1>
      <p>Voer je code in om door te gaan naar je dashboard en tools.</p>
      {% if message %}<div class="msg {{ 'error' if not success else 'ok' }}">{{ message }}</div>{% endif %}
    </div>
    <form id="loginForm" method="post" action="/login">
      <input id="access_code" class="hidden" type="password" name="access_code" inputmode="numeric" autocomplete="one-time-code">
      <div class="dots" id="dots"><div class="dot"></div><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>
      <div class="pad"><button class="key" type="button" onclick="pressKey('1')">1</button><button class="key" type="button" onclick="pressKey('2')">2</button><button class="key" type="button" onclick="pressKey('3')">3</button><button class="key" type="button" onclick="pressKey('4')">4</button><button class="key" type="button" onclick="pressKey('5')">5</button><button class="key" type="button" onclick="pressKey('6')">6</button><button class="key" type="button" onclick="pressKey('7')">7</button><button class="key" type="button" onclick="pressKey('8')">8</button><button class="key" type="button" onclick="pressKey('9')">9</button><button class="key small" type="button" onclick="backspaceKey()">⌫</button><button class="key" type="button" onclick="pressKey('0')">0</button><button class="key action small" type="submit">Open</button></div>
    </form>
    <div class="toolbar"><div class="help">Na 2 minuten inactiviteit log je automatisch uit.</div></div>
    <button class="gear" type="button" aria-label="Code instellen" onclick="openSheet()">⚙️</button>
  </div>
</div>
<div class="sheet" id="sheet" onclick="if(event.target.id==='sheet')closeSheet()"><div class="sheet-card"><h2>Code instellen</h2><p>Maak of wijzig je toegangscode met het hoofdwachtwoord.</p><form method="post" action="/setup-code"><div class="field"><label>Hoofdwachtwoord</label><input type="password" name="master_password" required></div><div class="field"><label>Nieuwe code</label><input type="password" name="new_access_code" inputmode="numeric" required></div><div class="row"><button class="btn secondary" type="button" onclick="closeSheet()">Sluiten</button><button class="btn primary" type="submit">Opslaan</button></div></form>{% if code_exists %}<div class="msg ok">Er is al een code ingesteld. Je kunt die hier altijd overschrijven.</div>{% else %}<div class="msg ok">Er is nog geen code ingesteld. Maak hier je eerste code aan.</div>{% endif %}</div></div>
<script>const codeInput=document.getElementById('access_code');const dots=Array.from(document.querySelectorAll('.dot'));function renderDots(){const len=(codeInput.value||'').length;dots.forEach((dot,i)=>dot.classList.toggle('filled',i<len));}function pressKey(value){if((codeInput.value||'').length>=4)return;codeInput.value=(codeInput.value||'')+value;renderDots();}function backspaceKey(){codeInput.value=(codeInput.value||'').slice(0,-1);renderDots();}function openSheet(){document.getElementById('sheet').classList.add('open');}function closeSheet(){document.getElementById('sheet').classList.remove('open');}renderDots();</script>
</body>
</html>
"""

CASA_LOGIN_HTML = """
<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover, maximum-scale=1.0, user-scalable=no">
<meta name="theme-color" content="#071120">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>Casa Cara login</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%2064%2064%27%3E%0A%3Cdefs%3E%0A%3ClinearGradient%20id%3D%27g%27%20x1%3D%270%27%20y1%3D%270%27%20x2%3D%271%27%20y2%3D%271%27%3E%0A%3Cstop%20offset%3D%270%25%27%20stop-color%3D%27%23ff8a2a%27/%3E%0A%3Cstop%20offset%3D%2755%25%27%20stop-color%3D%27%23ff5f72%27/%3E%0A%3Cstop%20offset%3D%27100%25%27%20stop-color%3D%27%23915dff%27/%3E%0A%3C/linearGradient%3E%0A%3C/defs%3E%0A%3Crect%20x%3D%274%27%20y%3D%274%27%20width%3D%2756%27%20height%3D%2756%27%20rx%3D%2718%27%20fill%3D%27%230d1422%27/%3E%0A%3Crect%20x%3D%276%27%20y%3D%276%27%20width%3D%2752%27%20height%3D%2752%27%20rx%3D%2716%27%20fill%3D%27url%28%23g%29%27%20opacity%3D%270.98%27/%3E%0A%3Cpath%20d%3D%27M39%2018.5c-1.8-2.3-4.9-3.7-8.3-3.7-5.6%200-10.3%204.3-10.3%209.8s4.7%209.8%2010.3%209.8c3.4%200%206.5-1.4%208.3-3.8%27%20fill%3D%27none%27%20stroke%3D%27white%27%20stroke-width%3D%275%27%20stroke-linecap%3D%27round%27/%3E%0A%3Cpath%20d%3D%27M43%2029.6c-1.5-1.8-3.8-2.9-6.4-2.9-4.7%200-8.5%203.6-8.5%208.1s3.8%208.1%208.5%208.1c2.6%200%204.9-1.1%206.4-2.9%27%20fill%3D%27none%27%20stroke%3D%27white%27%20stroke-width%3D%275%27%20stroke-linecap%3D%27round%27%20opacity%3D%270.96%27/%3E%0A%3C/svg%3E">
<style>
:root{
  --page:#071120;
  --page-2:#0d1729;
  --card:#142238;
  --card-2:#1a2b45;
  --line:rgba(149,170,204,.18);
  --line-strong:rgba(149,170,204,.28);
  --text:#f4f7fb;
  --muted:#8fa0bd;
  --accent:#ff7f2f;
  --accent-2:#ff9f5a;
  --danger:#ff7a7a;
  --shadow:0 28px 70px rgba(0,0,0,.42);
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{
  margin:0;min-height:100%;
  background:#071120!important;color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,system-ui,sans-serif;
  overscroll-behavior:none;
}
body{
  min-height:100dvh;min-height:100svh;overflow:hidden;
  background:
    radial-gradient(circle at 15% 12%, rgba(255,127,47,.14), transparent 24%),
    radial-gradient(circle at 88% 10%, rgba(122,171,255,.12), transparent 22%),
    radial-gradient(circle at 50% 100%, rgba(255,127,47,.08), transparent 30%),
    linear-gradient(180deg, var(--page), var(--page-2))!important;
}
.backdrop-grid{position:fixed;inset:0;pointer-events:none;opacity:.08;background-image:linear-gradient(rgba(255,255,255,.05) 1px, transparent 1px),linear-gradient(90deg, rgba(255,255,255,.05) 1px, transparent 1px);background-size:28px 28px;mask-image:linear-gradient(180deg, rgba(0,0,0,.92), transparent 100%)}
.login-shell{min-height:100dvh;display:flex;align-items:center;justify-content:center;padding:20px 16px calc(22px + env(safe-area-inset-bottom,0px));position:relative}
.card{
  width:min(390px,100%);
  border-radius:28px;
  border:1px solid var(--line);
  background:linear-gradient(180deg, rgba(21,34,54,.96), rgba(16,27,44,.96));
  box-shadow:var(--shadow);
  padding:20px 18px 18px;
  position:relative;
  overflow:hidden;
}
.card::before{content:"";position:absolute;inset:-30% auto auto -14%;width:180px;height:180px;border-radius:999px;background:radial-gradient(circle, rgba(255,127,47,.18), transparent 72%);filter:blur(12px);pointer-events:none}
.card::after{content:"";position:absolute;inset:auto -16% -30% auto;width:180px;height:180px;border-radius:999px;background:radial-gradient(circle, rgba(116,170,255,.12), transparent 72%);filter:blur(12px);pointer-events:none}
.brand{position:relative;z-index:1;text-align:center}
.brand-mark{width:72px;height:72px;margin:0 auto 14px;border-radius:22px;background:linear-gradient(180deg,var(--accent-2),var(--accent));display:grid;place-items:center;box-shadow:0 16px 30px rgba(255,127,47,.25)}
.brand-mark svg{width:42px;height:42px;display:block}
.title{margin:0;font-size:30px;line-height:1;font-weight:800;letter-spacing:-.05em}
.subtitle{margin:8px 0 18px;color:var(--muted);font-size:15px;line-height:1.35}
.prompt{margin:0 0 14px;text-align:center;font-size:15px;font-weight:600;color:#d9e4f5}
.dots{display:flex;justify-content:center;gap:10px;margin:0 0 14px}
.dot{width:52px;height:52px;border-radius:16px;border:2px solid rgba(110,130,163,.42);background:rgba(16,26,42,.78);display:grid;place-items:center;box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}
.dot::after{content:"";width:8px;height:8px;border-radius:999px;background:#6d809f;opacity:.9}
.dot.filled::after{background:#ffffff}
.hidden-input{position:absolute;opacity:0;pointer-events:none}
.pad{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.key{height:64px;border-radius:16px;border:1px solid rgba(116,133,164,.28);background:linear-gradient(180deg,#374761,#31425c);color:#fff;font-size:22px;font-weight:800;cursor:pointer;transition:transform .12s ease,filter .12s ease, border-color .12s ease;box-shadow:0 10px 24px rgba(0,0,0,.14)}
.key:hover{filter:brightness(1.05);border-color:var(--line-strong)}
.key:active{transform:scale(.985)}
.key.small{font-size:16px;color:#ff8f8f}
.key.action{background:linear-gradient(180deg,#b1662f,#9f5b2e);color:#d7dce5}
.key.action svg{width:22px;height:22px;opacity:.9}
.message{margin:0 0 12px;padding:10px 12px;border-radius:14px;border:1px solid rgba(255,255,255,.08);font-size:14px;line-height:1.45}
.message.error{background:rgba(255,122,122,.08);border-color:rgba(255,122,122,.16);color:#ffd0d0}
.message.ok{background:rgba(111,202,147,.10);border-color:rgba(111,202,147,.18);color:#d9ffe7}
.meta{margin-top:12px;text-align:center;color:var(--muted);font-size:12px}
.settings-trigger{
  position:fixed;right:18px;bottom:calc(18px + env(safe-area-inset-bottom,0px));
  width:48px;height:48px;border-radius:16px;border:1px solid var(--line);
  background:rgba(20,34,56,.9);color:var(--text);cursor:pointer;display:grid;place-items:center;
  box-shadow:0 14px 30px rgba(0,0,0,.24);z-index:20;
}
.settings-trigger:hover{border-color:var(--line-strong)}
.settings-trigger svg{width:22px;height:22px;opacity:.88}
.sheet{position:fixed;inset:0;display:none;align-items:center;justify-content:center;padding:20px;background:rgba(4,8,14,.58);backdrop-filter:blur(8px);z-index:40}
.sheet.open{display:flex}
.sheet-card{width:min(390px,100%);border-radius:24px;border:1px solid var(--line);background:linear-gradient(180deg, rgba(20,34,56,.98), rgba(15,27,44,.98));box-shadow:var(--shadow);padding:22px}
.sheet-title{margin:0 0 6px;font-size:24px;font-weight:800;letter-spacing:-.03em}
.sheet-sub{margin:0 0 16px;color:var(--muted);font-size:14px;line-height:1.5}
.field{display:grid;gap:6px;margin-bottom:12px}
.field label{font-size:13px;color:var(--muted)}
.field input{width:100%;min-height:44px;border-radius:14px;border:1px solid rgba(116,133,164,.26);background:rgba(255,255,255,.03);color:var(--text);padding:0 14px;outline:none}
.row{display:flex;justify-content:flex-end;gap:10px;margin-top:6px}
.btn{min-height:42px;padding:0 14px;border-radius:14px;border:none;font-weight:800;cursor:pointer}
.btn.secondary{background:rgba(255,255,255,.04);color:var(--text);border:1px solid rgba(116,133,164,.18)}
.btn.primary{background:linear-gradient(180deg,var(--accent-2),var(--accent));color:#1d130c}
.top-link{position:fixed;top:14px;left:14px;min-height:38px;padding:0 12px;border-radius:999px;border:1px solid var(--line);background:rgba(18,30,48,.72);display:inline-flex;align-items:center;gap:8px;color:var(--text);text-decoration:none;backdrop-filter:blur(16px);z-index:20}
.top-link:hover{border-color:var(--line-strong)}
@media (max-width: 560px){
  .login-shell{padding-top:18px}
  .card{padding:18px 14px 16px;border-radius:22px}
  .brand-mark{width:66px;height:66px;border-radius:20px}
  .brand-mark svg{width:38px;height:38px}
  .title{font-size:28px}
  .subtitle{font-size:14px;margin-bottom:16px}
  .prompt{font-size:14px}
  .dots{gap:8px}
  .dot{width:46px;height:46px;border-radius:14px}
  .pad{gap:8px}
  .key{height:58px;font-size:20px;border-radius:14px}
  .settings-trigger{right:14px;bottom:calc(14px + env(safe-area-inset-bottom,0px))}
}
</style>
</head>
<body>
<div class="backdrop-grid"></div>
<a class="top-link" href="/" aria-label="Terug naar home">← Home</a>
<div class="login-shell">
  <div class="card">
    <div class="brand">
      <div class="brand-mark"><svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>
<defs>
<linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>
<stop offset='0%' stop-color='#ff8a2a'/>
<stop offset='55%' stop-color='#ff5f72'/>
<stop offset='100%' stop-color='#915dff'/>
</linearGradient>
</defs>
<rect x='4' y='4' width='56' height='56' rx='18' fill='#0d1422'/>
<rect x='6' y='6' width='52' height='52' rx='16' fill='url(#g)' opacity='0.98'/>
<path d='M39 18.5c-1.8-2.3-4.9-3.7-8.3-3.7-5.6 0-10.3 4.3-10.3 9.8s4.7 9.8 10.3 9.8c3.4 0 6.5-1.4 8.3-3.8' fill='none' stroke='white' stroke-width='5' stroke-linecap='round'/>
<path d='M43 29.6c-1.5-1.8-3.8-2.9-6.4-2.9-4.7 0-8.5 3.6-8.5 8.1s3.8 8.1 8.5 8.1c2.6 0 4.9-1.1 6.4-2.9' fill='none' stroke='white' stroke-width='5' stroke-linecap='round' opacity='0.96'/>
</svg></div>
      <h1 class="title">Casa Cara</h1>
      <p class="subtitle">Interne werkplek</p>
      {% if message %}<div class="message {'ok' if success else 'error'}">{{ message }}</div>{% endif %}
      <p class="prompt">Voer je 4-cijferige code in</p>
    </div>

    <form id="loginForm" method="post" action="">
      <input id="access_code" class="hidden-input" type="password" name="access_code" inputmode="numeric" autocomplete="one-time-code">
      <div class="dots" id="dots">
        <div class="dot"></div><div class="dot"></div><div class="dot"></div><div class="dot"></div>
      </div>
      <div class="pad">
        <button class="key" type="button" onclick="pressKey('1')">1</button>
        <button class="key" type="button" onclick="pressKey('2')">2</button>
        <button class="key" type="button" onclick="pressKey('3')">3</button>
        <button class="key" type="button" onclick="pressKey('4')">4</button>
        <button class="key" type="button" onclick="pressKey('5')">5</button>
        <button class="key" type="button" onclick="pressKey('6')">6</button>
        <button class="key" type="button" onclick="pressKey('7')">7</button>
        <button class="key" type="button" onclick="pressKey('8')">8</button>
        <button class="key" type="button" onclick="pressKey('9')">9</button>
        <button class="key small" type="button" onclick="backspaceKey()">⌫</button>
        <button class="key" type="button" onclick="pressKey('0')">0</button>
        <button class="key action" type="submit" aria-label="Inloggen">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.2 4.2L19 7"/></svg>
        </button>
      </div>
    </form>
    <div class="meta">Voer je 4-cijferige code in. Na het 4e cijfer log je automatisch in.</div>
  </div>
</div>

<button class="settings-trigger" type="button" aria-label="Casa Cara code instellen" onclick="openSheet()">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.5 2.6 3 .5-.8 2.9 2 2-2 2 .8 2.9-3 .5L12 21l-1.5-2.6-3-.5.8-2.9-2-2 2-2-.8-2.9 3-.5L12 3z"/><circle cx="12" cy="12" r="3.2"/></svg>
</button>

<div class="sheet" id="sheet" onclick="if(event.target.id==='sheet')closeSheet()">
  <div class="sheet-card">
    <h2 class="sheet-title">Casa Cara code instellen</h2>
    <p class="sheet-sub">Maak of wijzig de toegangscode met het hoofdwachtwoord.</p>
    <form method="post" action="/casa-cara-setup">
      <div class="field">
        <label>Hoofdwachtwoord</label>
        <input type="password" name="master_password" required>
      </div>
      {% if 'admin' in '/casa-cara-setup' or 'casa-cara' in '/casa-cara-setup' %}
      <div class="field">
        <label>Admin naam</label>
        <input type="text" name="admin_name" placeholder="Bijvoorbeeld Bart">
      </div>
      {% endif %}
      <div class="field">
        <label>Nieuwe 4-cijferige code</label>
        <input type="password" name="new_access_code" inputmode="numeric" maxlength="4" required>
      </div>
      <div class="row">
        <button class="btn secondary" type="button" onclick="closeSheet()">Sluiten</button>
        <button class="btn primary" type="submit">Opslaan</button>
      </div>
    </form>
    {% if casa_code_exists is defined %}
      {% if casa_code_exists %}<div class="message ok" style="margin-top:14px">Er is al een Casa Cara code ingesteld.</div>{% else %}<div class="message ok" style="margin-top:14px">Er is nog geen Casa Cara code ingesteld.</div>{% endif %}
    {% endif %}
    {% if gmail_code_exists is defined %}
      {% if gmail_code_exists %}<div class="message ok" style="margin-top:14px">Er is al een Gmail Cleaner code ingesteld.</div>{% else %}<div class="message ok" style="margin-top:14px">Er is nog geen Gmail Cleaner code ingesteld.</div>{% endif %}
    {% endif %}
  </div>
</div>

<script>
const codeInput = document.getElementById('access_code');
const dots = Array.from(document.querySelectorAll('.dot'));
const form = document.getElementById('loginForm');
function renderDots(){
  const len = (codeInput.value || '').length;
  dots.forEach((dot, i) => dot.classList.toggle('filled', i < len));
}
function submitIfReady(){
  const value = (codeInput.value || '');
  if(value.length === 4){
    setTimeout(() => form.submit(), 100);
  }
}
function pressKey(value){
  if ((codeInput.value || '').length >= 4) return;
  codeInput.value = (codeInput.value || '') + value;
  renderDots();
  submitIfReady();
}
function backspaceKey(){
  codeInput.value = (codeInput.value || '').slice(0, -1);
  renderDots();
}
function openSheet(){ document.getElementById('sheet').classList.add('open'); }
function closeSheet(){ document.getElementById('sheet').classList.remove('open'); }
renderDots();
</script>
</body>
</html>
"""

GMAIL_LOGIN_HTML = """
<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover, maximum-scale=1.0, user-scalable=no">
<meta name="theme-color" content="#071120">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>Gmail Cleaner login</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%2064%2064%27%3E%0A%3Cdefs%3E%0A%3ClinearGradient%20id%3D%27g%27%20x1%3D%270%27%20y1%3D%270%27%20x2%3D%271%27%20y2%3D%271%27%3E%0A%3Cstop%20offset%3D%270%25%27%20stop-color%3D%27%23ff8a2a%27/%3E%0A%3Cstop%20offset%3D%2755%25%27%20stop-color%3D%27%23ff5f72%27/%3E%0A%3Cstop%20offset%3D%27100%25%27%20stop-color%3D%27%23915dff%27/%3E%0A%3C/linearGradient%3E%0A%3C/defs%3E%0A%3Crect%20x%3D%274%27%20y%3D%274%27%20width%3D%2756%27%20height%3D%2756%27%20rx%3D%2718%27%20fill%3D%27%230d1422%27/%3E%0A%3Crect%20x%3D%276%27%20y%3D%276%27%20width%3D%2752%27%20height%3D%2752%27%20rx%3D%2716%27%20fill%3D%27url%28%23g%29%27%20opacity%3D%270.98%27/%3E%0A%3Cpath%20d%3D%27M39%2018.5c-1.8-2.3-4.9-3.7-8.3-3.7-5.6%200-10.3%204.3-10.3%209.8s4.7%209.8%2010.3%209.8c3.4%200%206.5-1.4%208.3-3.8%27%20fill%3D%27none%27%20stroke%3D%27white%27%20stroke-width%3D%275%27%20stroke-linecap%3D%27round%27/%3E%0A%3Cpath%20d%3D%27M43%2029.6c-1.5-1.8-3.8-2.9-6.4-2.9-4.7%200-8.5%203.6-8.5%208.1s3.8%208.1%208.5%208.1c2.6%200%204.9-1.1%206.4-2.9%27%20fill%3D%27none%27%20stroke%3D%27white%27%20stroke-width%3D%275%27%20stroke-linecap%3D%27round%27%20opacity%3D%270.96%27/%3E%0A%3C/svg%3E">
<style>
:root{
  --page:#071120;
  --page-2:#0d1729;
  --card:#142238;
  --card-2:#1a2b45;
  --line:rgba(149,170,204,.18);
  --line-strong:rgba(149,170,204,.28);
  --text:#f4f7fb;
  --muted:#8fa0bd;
  --accent:#ff7f2f;
  --accent-2:#ff9f5a;
  --danger:#ff7a7a;
  --shadow:0 28px 70px rgba(0,0,0,.42);
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{
  margin:0;min-height:100%;
  background:#071120!important;color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,system-ui,sans-serif;
  overscroll-behavior:none;
}
body{
  min-height:100dvh;min-height:100svh;overflow:hidden;
  background:
    radial-gradient(circle at 15% 12%, rgba(255,127,47,.14), transparent 24%),
    radial-gradient(circle at 88% 10%, rgba(122,171,255,.12), transparent 22%),
    radial-gradient(circle at 50% 100%, rgba(255,127,47,.08), transparent 30%),
    linear-gradient(180deg, var(--page), var(--page-2))!important;
}
.backdrop-grid{position:fixed;inset:0;pointer-events:none;opacity:.08;background-image:linear-gradient(rgba(255,255,255,.05) 1px, transparent 1px),linear-gradient(90deg, rgba(255,255,255,.05) 1px, transparent 1px);background-size:28px 28px;mask-image:linear-gradient(180deg, rgba(0,0,0,.92), transparent 100%)}
.login-shell{min-height:100dvh;display:flex;align-items:center;justify-content:center;padding:20px 16px calc(22px + env(safe-area-inset-bottom,0px));position:relative}
.card{
  width:min(390px,100%);
  border-radius:28px;
  border:1px solid var(--line);
  background:linear-gradient(180deg, rgba(21,34,54,.96), rgba(16,27,44,.96));
  box-shadow:var(--shadow);
  padding:20px 18px 18px;
  position:relative;
  overflow:hidden;
}
.card::before{content:"";position:absolute;inset:-30% auto auto -14%;width:180px;height:180px;border-radius:999px;background:radial-gradient(circle, rgba(255,127,47,.18), transparent 72%);filter:blur(12px);pointer-events:none}
.card::after{content:"";position:absolute;inset:auto -16% -30% auto;width:180px;height:180px;border-radius:999px;background:radial-gradient(circle, rgba(116,170,255,.12), transparent 72%);filter:blur(12px);pointer-events:none}
.brand{position:relative;z-index:1;text-align:center}
.brand-mark{width:72px;height:72px;margin:0 auto 14px;border-radius:22px;background:linear-gradient(180deg,var(--accent-2),var(--accent));display:grid;place-items:center;box-shadow:0 16px 30px rgba(255,127,47,.25)}
.brand-mark svg{width:42px;height:42px;display:block}
.title{margin:0;font-size:30px;line-height:1;font-weight:800;letter-spacing:-.05em}
.subtitle{margin:8px 0 18px;color:var(--muted);font-size:15px;line-height:1.35}
.prompt{margin:0 0 14px;text-align:center;font-size:15px;font-weight:600;color:#d9e4f5}
.dots{display:flex;justify-content:center;gap:10px;margin:0 0 14px}
.dot{width:52px;height:52px;border-radius:16px;border:2px solid rgba(110,130,163,.42);background:rgba(16,26,42,.78);display:grid;place-items:center;box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}
.dot::after{content:"";width:8px;height:8px;border-radius:999px;background:#6d809f;opacity:.9}
.dot.filled::after{background:#ffffff}
.hidden-input{position:absolute;opacity:0;pointer-events:none}
.pad{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.key{height:64px;border-radius:16px;border:1px solid rgba(116,133,164,.28);background:linear-gradient(180deg,#374761,#31425c);color:#fff;font-size:22px;font-weight:800;cursor:pointer;transition:transform .12s ease,filter .12s ease, border-color .12s ease;box-shadow:0 10px 24px rgba(0,0,0,.14)}
.key:hover{filter:brightness(1.05);border-color:var(--line-strong)}
.key:active{transform:scale(.985)}
.key.small{font-size:16px;color:#ff8f8f}
.key.action{background:linear-gradient(180deg,#b1662f,#9f5b2e);color:#d7dce5}
.key.action svg{width:22px;height:22px;opacity:.9}
.message{margin:0 0 12px;padding:10px 12px;border-radius:14px;border:1px solid rgba(255,255,255,.08);font-size:14px;line-height:1.45}
.message.error{background:rgba(255,122,122,.08);border-color:rgba(255,122,122,.16);color:#ffd0d0}
.message.ok{background:rgba(111,202,147,.10);border-color:rgba(111,202,147,.18);color:#d9ffe7}
.meta{margin-top:12px;text-align:center;color:var(--muted);font-size:12px}
.settings-trigger{
  position:fixed;right:18px;bottom:calc(18px + env(safe-area-inset-bottom,0px));
  width:48px;height:48px;border-radius:16px;border:1px solid var(--line);
  background:rgba(20,34,56,.9);color:var(--text);cursor:pointer;display:grid;place-items:center;
  box-shadow:0 14px 30px rgba(0,0,0,.24);z-index:20;
}
.settings-trigger:hover{border-color:var(--line-strong)}
.settings-trigger svg{width:22px;height:22px;opacity:.88}
.sheet{position:fixed;inset:0;display:none;align-items:center;justify-content:center;padding:20px;background:rgba(4,8,14,.58);backdrop-filter:blur(8px);z-index:40}
.sheet.open{display:flex}
.sheet-card{width:min(390px,100%);border-radius:24px;border:1px solid var(--line);background:linear-gradient(180deg, rgba(20,34,56,.98), rgba(15,27,44,.98));box-shadow:var(--shadow);padding:22px}
.sheet-title{margin:0 0 6px;font-size:24px;font-weight:800;letter-spacing:-.03em}
.sheet-sub{margin:0 0 16px;color:var(--muted);font-size:14px;line-height:1.5}
.field{display:grid;gap:6px;margin-bottom:12px}
.field label{font-size:13px;color:var(--muted)}
.field input{width:100%;min-height:44px;border-radius:14px;border:1px solid rgba(116,133,164,.26);background:rgba(255,255,255,.03);color:var(--text);padding:0 14px;outline:none}
.row{display:flex;justify-content:flex-end;gap:10px;margin-top:6px}
.btn{min-height:42px;padding:0 14px;border-radius:14px;border:none;font-weight:800;cursor:pointer}
.btn.secondary{background:rgba(255,255,255,.04);color:var(--text);border:1px solid rgba(116,133,164,.18)}
.btn.primary{background:linear-gradient(180deg,var(--accent-2),var(--accent));color:#1d130c}
.top-link{position:fixed;top:14px;left:14px;min-height:38px;padding:0 12px;border-radius:999px;border:1px solid var(--line);background:rgba(18,30,48,.72);display:inline-flex;align-items:center;gap:8px;color:var(--text);text-decoration:none;backdrop-filter:blur(16px);z-index:20}
.top-link:hover{border-color:var(--line-strong)}
@media (max-width: 560px){
  .login-shell{padding-top:18px}
  .card{padding:18px 14px 16px;border-radius:22px}
  .brand-mark{width:66px;height:66px;border-radius:20px}
  .brand-mark svg{width:38px;height:38px}
  .title{font-size:28px}
  .subtitle{font-size:14px;margin-bottom:16px}
  .prompt{font-size:14px}
  .dots{gap:8px}
  .dot{width:46px;height:46px;border-radius:14px}
  .pad{gap:8px}
  .key{height:58px;font-size:20px;border-radius:14px}
  .settings-trigger{right:14px;bottom:calc(14px + env(safe-area-inset-bottom,0px))}
}
</style>
</head>
<body>
<div class="backdrop-grid"></div>
<a class="top-link" href="/" aria-label="Terug naar home">← Home</a>
<div class="login-shell">
  <div class="card">
    <div class="brand">
      <div class="brand-mark"><svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>
<defs>
<linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>
<stop offset='0%' stop-color='#ff8a2a'/>
<stop offset='55%' stop-color='#ff5f72'/>
<stop offset='100%' stop-color='#915dff'/>
</linearGradient>
</defs>
<rect x='4' y='4' width='56' height='56' rx='18' fill='#0d1422'/>
<rect x='6' y='6' width='52' height='52' rx='16' fill='url(#g)' opacity='0.98'/>
<path d='M39 18.5c-1.8-2.3-4.9-3.7-8.3-3.7-5.6 0-10.3 4.3-10.3 9.8s4.7 9.8 10.3 9.8c3.4 0 6.5-1.4 8.3-3.8' fill='none' stroke='white' stroke-width='5' stroke-linecap='round'/>
<path d='M43 29.6c-1.5-1.8-3.8-2.9-6.4-2.9-4.7 0-8.5 3.6-8.5 8.1s3.8 8.1 8.5 8.1c2.6 0 4.9-1.1 6.4-2.9' fill='none' stroke='white' stroke-width='5' stroke-linecap='round' opacity='0.96'/>
</svg></div>
      <h1 class="title">Gmail Cleaner</h1>
      <p class="subtitle">Interne werkplek</p>
      {% if message %}<div class="message {'ok' if success else 'error'}">{{ message }}</div>{% endif %}
      <p class="prompt">Voer je 4-cijferige code in</p>
    </div>

    <form id="loginForm" method="post" action="">
      <input id="access_code" class="hidden-input" type="password" name="access_code" inputmode="numeric" autocomplete="one-time-code">
      <div class="dots" id="dots">
        <div class="dot"></div><div class="dot"></div><div class="dot"></div><div class="dot"></div>
      </div>
      <div class="pad">
        <button class="key" type="button" onclick="pressKey('1')">1</button>
        <button class="key" type="button" onclick="pressKey('2')">2</button>
        <button class="key" type="button" onclick="pressKey('3')">3</button>
        <button class="key" type="button" onclick="pressKey('4')">4</button>
        <button class="key" type="button" onclick="pressKey('5')">5</button>
        <button class="key" type="button" onclick="pressKey('6')">6</button>
        <button class="key" type="button" onclick="pressKey('7')">7</button>
        <button class="key" type="button" onclick="pressKey('8')">8</button>
        <button class="key" type="button" onclick="pressKey('9')">9</button>
        <button class="key small" type="button" onclick="backspaceKey()">⌫</button>
        <button class="key" type="button" onclick="pressKey('0')">0</button>
        <button class="key action" type="submit" aria-label="Inloggen">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.2 4.2L19 7"/></svg>
        </button>
      </div>
    </form>
    <div class="meta">Voer je 4-cijferige code in. Na het 4e cijfer log je automatisch in.</div>
  </div>
</div>

<button class="settings-trigger" type="button" aria-label="Gmail Cleaner code instellen" onclick="openSheet()">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.5 2.6 3 .5-.8 2.9 2 2-2 2 .8 2.9-3 .5L12 21l-1.5-2.6-3-.5.8-2.9-2-2 2-2-.8-2.9 3-.5L12 3z"/><circle cx="12" cy="12" r="3.2"/></svg>
</button>

<div class="sheet" id="sheet" onclick="if(event.target.id==='sheet')closeSheet()">
  <div class="sheet-card">
    <h2 class="sheet-title">Gmail Cleaner code instellen</h2>
    <p class="sheet-sub">Maak of wijzig de toegangscode met het hoofdwachtwoord.</p>
    <form method="post" action="/gmail-setup">
      <div class="field">
        <label>Hoofdwachtwoord</label>
        <input type="password" name="master_password" required>
      </div>
      {% if 'admin' in '/gmail-setup' or 'casa-cara' in '/gmail-setup' %}
      <div class="field">
        <label>Admin naam</label>
        <input type="text" name="admin_name" placeholder="Bijvoorbeeld Bart">
      </div>
      {% endif %}
      <div class="field">
        <label>Nieuwe 4-cijferige code</label>
        <input type="password" name="new_access_code" inputmode="numeric" maxlength="4" required>
      </div>
      <div class="row">
        <button class="btn secondary" type="button" onclick="closeSheet()">Sluiten</button>
        <button class="btn primary" type="submit">Opslaan</button>
      </div>
    </form>
    {% if casa_code_exists is defined %}
      {% if casa_code_exists %}<div class="message ok" style="margin-top:14px">Er is al een Casa Cara code ingesteld.</div>{% else %}<div class="message ok" style="margin-top:14px">Er is nog geen Casa Cara code ingesteld.</div>{% endif %}
    {% endif %}
    {% if gmail_code_exists is defined %}
      {% if gmail_code_exists %}<div class="message ok" style="margin-top:14px">Er is al een Gmail Cleaner code ingesteld.</div>{% else %}<div class="message ok" style="margin-top:14px">Er is nog geen Gmail Cleaner code ingesteld.</div>{% endif %}
    {% endif %}
  </div>
</div>

<script>
const codeInput = document.getElementById('access_code');
const dots = Array.from(document.querySelectorAll('.dot'));
const form = document.getElementById('loginForm');
function renderDots(){
  const len = (codeInput.value || '').length;
  dots.forEach((dot, i) => dot.classList.toggle('filled', i < len));
}
function submitIfReady(){
  const value = (codeInput.value || '');
  if(value.length === 4){
    setTimeout(() => form.submit(), 100);
  }
}
function pressKey(value){
  if ((codeInput.value || '').length >= 4) return;
  codeInput.value = (codeInput.value || '') + value;
  renderDots();
  submitIfReady();
}
function backspaceKey(){
  codeInput.value = (codeInput.value || '').slice(0, -1);
  renderDots();
}
function openSheet(){ document.getElementById('sheet').classList.add('open'); }
function closeSheet(){ document.getElementById('sheet').classList.remove('open'); }
renderDots();
</script>
</body>
</html>
"""

HOME_HTML = """
<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover, maximum-scale=1.0, user-scalable=no">
<meta name="theme-color" content="#04070d">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>Welkom!</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%2064%2064%27%3E%0A%3Cdefs%3E%0A%3ClinearGradient%20id%3D%27g%27%20x1%3D%270%27%20y1%3D%270%27%20x2%3D%271%27%20y2%3D%271%27%3E%0A%3Cstop%20offset%3D%270%25%27%20stop-color%3D%27%23ff8a2a%27/%3E%0A%3Cstop%20offset%3D%2755%25%27%20stop-color%3D%27%23ff5f72%27/%3E%0A%3Cstop%20offset%3D%27100%25%27%20stop-color%3D%27%23915dff%27/%3E%0A%3C/linearGradient%3E%0A%3C/defs%3E%0A%3Crect%20x%3D%274%27%20y%3D%274%27%20width%3D%2756%27%20height%3D%2756%27%20rx%3D%2718%27%20fill%3D%27%230d1422%27/%3E%0A%3Crect%20x%3D%276%27%20y%3D%276%27%20width%3D%2752%27%20height%3D%2752%27%20rx%3D%2716%27%20fill%3D%27url%28%23g%29%27%20opacity%3D%270.98%27/%3E%0A%3Cpath%20d%3D%27M39%2018.5c-1.8-2.3-4.9-3.7-8.3-3.7-5.6%200-10.3%204.3-10.3%209.8s4.7%209.8%2010.3%209.8c3.4%200%206.5-1.4%208.3-3.8%27%20fill%3D%27none%27%20stroke%3D%27white%27%20stroke-width%3D%275%27%20stroke-linecap%3D%27round%27/%3E%0A%3Cpath%20d%3D%27M43%2029.6c-1.5-1.8-3.8-2.9-6.4-2.9-4.7%200-8.5%203.6-8.5%208.1s3.8%208.1%208.5%208.1c2.6%200%204.9-1.1%206.4-2.9%27%20fill%3D%27none%27%20stroke%3D%27white%27%20stroke-width%3D%275%27%20stroke-linecap%3D%27round%27%20opacity%3D%270.96%27/%3E%0A%3C/svg%3E">
<style>
:root{
  --bg:#04070d; --bg-2:#09111b; --surface:rgba(12,18,29,.66); --surface-2:rgba(16,24,38,.84);
  --line:rgba(255,255,255,.09); --line-strong:rgba(255,255,255,.18);
  --text:#f7f9ff; --muted:#a2b2c9; --cyan:#7ae2ff; --blue:#74a4ff; --pink:#ff6cae; --gold:#ff9a52; --orange:#ff7f2f; --violet:#9d7cff;
  --shadow:0 26px 80px rgba(0,0,0,.4);
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;min-height:100%;background:#04070d!important;color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,system-ui,sans-serif;overscroll-behavior:none;scroll-behavior:smooth}
body{min-height:100dvh;min-height:100svh;overflow-x:clip;background:#04070d!important;width:100%;max-width:100vw}
body::before{content:"";position:fixed;inset:0;z-index:-20;background:
  radial-gradient(circle at 15% 10%, rgba(122,226,255,.16), transparent 23%),
  radial-gradient(circle at 85% 14%, rgba(255,108,174,.13), transparent 19%),
  radial-gradient(circle at 82% 68%, rgba(255,154,82,.12), transparent 22%),
  radial-gradient(circle at 20% 78%, rgba(116,164,255,.14), transparent 20%),
  linear-gradient(180deg, #04070d 0%, #09111b 45%, #04070d 100%);
}
.noise{position:fixed;inset:0;z-index:-19;pointer-events:none;opacity:.05;background-image:radial-gradient(circle at 18% 16%, rgba(255,255,255,.95) .65px, transparent .8px),radial-gradient(circle at 68% 34%, rgba(255,255,255,.9) .65px, transparent .8px),radial-gradient(circle at 44% 80%, rgba(255,255,255,.9) .65px, transparent .8px);background-size:160px 160px,220px 220px,260px 260px}
.grid{position:fixed;inset:0;z-index:-18;pointer-events:none;opacity:.08;background-image:linear-gradient(rgba(255,255,255,.04) 1px, transparent 1px),linear-gradient(90deg, rgba(255,255,255,.04) 1px, transparent 1px);background-size:36px 36px;mask-image:linear-gradient(180deg, rgba(0,0,0,.86), transparent 98%)}
.orb,.orb2,.orb3,.orb4{position:fixed;border-radius:999px;filter:blur(22px);pointer-events:none;z-index:-17;mix-blend-mode:screen;opacity:.4}
.orb{width:300px;height:300px;left:-70px;top:8%;background:radial-gradient(circle, rgba(122,226,255,.38), transparent 72%);animation:float1 22s ease-in-out infinite}
.orb2{width:340px;height:340px;right:-90px;top:22%;background:radial-gradient(circle, rgba(255,108,174,.26), transparent 72%);animation:float2 24s ease-in-out infinite}
.orb3{width:280px;height:280px;left:16%;top:62%;background:radial-gradient(circle, rgba(255,154,82,.22), transparent 72%);animation:float3 20s ease-in-out infinite}
.orb4{width:260px;height:260px;right:12%;bottom:8%;background:radial-gradient(circle, rgba(116,164,255,.22), transparent 72%);animation:float4 21s ease-in-out infinite}
.logo-float{position:fixed;left:20px;top:20px;width:68px;height:68px;border-radius:22px;display:grid;place-items:center;border:1px solid rgba(255,255,255,.12);background:rgba(9,14,22,.7);backdrop-filter:blur(18px);box-shadow:0 16px 40px rgba(0,0,0,.24);z-index:42;transition:transform .28s ease,opacity .28s ease,filter .28s ease}
.logo-float svg{width:42px;height:42px;display:block}
.logo-float.hidden{opacity:0;transform:translateY(-18px) scale(.96);pointer-events:none}
.logo-float.dim{opacity:.2;filter:blur(.5px)}
.nav-shell{position:fixed;left:50%;top:18px;transform:translateX(-50%);z-index:44;transition:transform .32s ease,opacity .32s ease}
.nav-shell.hidden{opacity:0;transform:translate(-50%,-18px)}
.nav-pill{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:999px;border:1px solid rgba(255,255,255,.12);background:rgba(8,13,22,.72);backdrop-filter:blur(18px);box-shadow:0 16px 40px rgba(0,0,0,.28)}
.nav-toggle{width:44px;height:44px;border-radius:14px;border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.04);color:var(--text);display:grid;place-items:center;cursor:pointer;transition:transform .14s ease, background .14s ease}
.nav-toggle:hover{background:rgba(255,255,255,.08)}
.nav-toggle:active{transform:scale(.98)}
.nav-toggle span{display:block;width:18px;height:2px;background:#fff;border-radius:999px;position:relative}
.nav-toggle span::before,.nav-toggle span::after{content:"";position:absolute;left:0;width:18px;height:2px;background:#fff;border-radius:999px}
.nav-toggle span::before{top:-6px} .nav-toggle span::after{top:6px}
.nav-label{font-weight:800;letter-spacing:-.02em;font-size:14px;color:#f6f8fd;white-space:nowrap}
.nav-panel{position:absolute;left:50%;top:64px;transform:translateX(-50%) scale(.98);width:min(420px,calc(100vw - 24px));border-radius:26px;border:1px solid rgba(255,255,255,.12);background:rgba(8,13,22,.86);backdrop-filter:blur(22px);padding:12px;box-shadow:var(--shadow);opacity:0;pointer-events:none;transition:opacity .2s ease, transform .2s ease}
.nav-panel.open{opacity:1;pointer-events:auto;transform:translateX(-50%) scale(1)}
.tool-link{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:14px;border-radius:20px;border:1px solid rgba(255,255,255,.08);background:linear-gradient(180deg, rgba(255,255,255,.05), rgba(255,255,255,.03));text-decoration:none;color:var(--text);transition:transform .14s ease,border-color .14s ease,background .14s ease}
.tool-link + .tool-link{margin-top:10px}
.tool-link:hover{transform:translateY(-1px);border-color:rgba(255,255,255,.16);background:linear-gradient(180deg, rgba(255,255,255,.08), rgba(255,255,255,.04))}
.tool-left{display:flex;align-items:flex-start;gap:12px}
.tool-icon{width:42px;height:42px;border-radius:14px;display:grid;place-items:center;background:rgba(255,255,255,.06);flex:0 0 auto}
.tool-icon svg{width:24px;height:24px;display:block}
.tool-title{font-size:15px;font-weight:800;letter-spacing:-.02em}
.tool-copy{margin-top:3px;font-size:12px;color:var(--muted);line-height:1.4}
.tool-arrow{color:#b8c5da;font-size:18px;line-height:1;margin-top:2px}
.page{position:relative;z-index:1;overflow-x:clip}
.hero{min-height:112vh;display:grid;place-items:center;padding:120px 22px 80px;position:relative;overflow:hidden}
.hero-content{max-width:1040px;width:100%;text-align:center;position:relative}
.eyebrow{display:inline-flex;align-items:center;gap:10px;padding:10px 14px;border-radius:999px;border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.04);backdrop-filter:blur(12px);font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#dfe9fb}
.eyebrow::before{content:"";width:8px;height:8px;border-radius:999px;background:linear-gradient(180deg,var(--gold),var(--pink));box-shadow:0 0 0 6px rgba(255,154,82,.12)}
.hero-title{margin:22px 0 14px;font-size:clamp(66px,14vw,164px);line-height:.88;font-weight:900;letter-spacing:-.08em}
.hero-title .gradient{display:block;background:linear-gradient(120deg,#ffffff 5%,#90dfff 32%,#ff9a52 62%,#ff6cae 88%);-webkit-background-clip:text;background-clip:text;color:transparent}
.hero-copy{max-width:760px;margin:0 auto;color:var(--muted);font-size:clamp(16px,2.2vw,20px);line-height:1.7}
.marquee{margin:34px auto 0;max-width:min(980px,100%);overflow:hidden;border-radius:999px;border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.04);backdrop-filter:blur(14px)}
.marquee-track{display:flex;gap:26px;white-space:nowrap;padding:12px 18px;min-width:max-content;animation:marquee 24s linear infinite}
.marquee-track span{font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#dfe8f7;opacity:.9}
.hero-media{position:relative;max-width:1120px;margin:42px auto 0;height:360px}
.stage{position:absolute;inset:0;border-radius:34px;border:1px solid rgba(255,255,255,.1);background:linear-gradient(180deg, rgba(12,18,29,.56), rgba(12,18,29,.36));box-shadow:var(--shadow);overflow:hidden}
.scanline{position:absolute;inset:-20% 0 auto 0;height:42%;background:linear-gradient(180deg, rgba(255,255,255,0), rgba(255,255,255,.1), rgba(255,255,255,0));transform:translateY(-100%);animation:sweep 7s linear infinite;mix-blend-mode:screen;opacity:.4}
.stage::before{content:"";position:absolute;inset:0;background:radial-gradient(circle at 20% 22%, rgba(122,226,255,.16), transparent 18%),radial-gradient(circle at 82% 28%, rgba(255,108,174,.12), transparent 18%),radial-gradient(circle at 50% 82%, rgba(255,154,82,.12), transparent 20%)}
.float-card{position:absolute;border-radius:24px;border:1px solid rgba(255,255,255,.1);background:rgba(8,13,22,.64);backdrop-filter:blur(16px);box-shadow:0 18px 50px rgba(0,0,0,.28);padding:18px}
.float-card strong{display:block;font-size:14px;letter-spacing:-.02em}
.float-card small{display:block;margin-top:6px;color:var(--muted);line-height:1.5}
.card-mail{left:5%;top:18%;width:290px;animation:float5 8s ease-in-out infinite}
.card-restaurant{right:7%;bottom:14%;width:310px;animation:float6 9s ease-in-out infinite}
.card-pulse{left:34%;top:12%;width:150px;text-align:center;animation:float7 7s ease-in-out infinite}
.card-pulse .number{font-size:44px;font-weight:900;letter-spacing:-.05em;margin-top:10px;background:linear-gradient(120deg,#fff,#9fe5ff 45%,#ff9a52);-webkit-background-clip:text;background-clip:text;color:transparent}
.ribbon{position:absolute;left:-6%;right:-6%;bottom:18px;display:flex;gap:14px;transform:rotate(-2deg)}
.ribbon-track{display:flex;gap:14px;min-width:max-content;animation:marquee2 20s linear infinite}
.ribbon span{padding:12px 16px;border-radius:999px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}
.section{position:relative;padding:88px 22px 120px}
.section-wrap{max-width:1160px;margin:0 auto;display:grid;grid-template-columns:1.02fr .98fr;gap:34px;align-items:center}
.section-badge{display:inline-flex;align-items:center;gap:10px;padding:10px 14px;border-radius:999px;border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.04);font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}
.section-title{margin:18px 0 14px;font-size:clamp(38px,7vw,84px);line-height:.93;letter-spacing:-.07em}
.section-copy{max-width:560px;color:var(--muted);font-size:17px;line-height:1.8}
.feature-list{display:grid;gap:12px;margin-top:22px}
.feature{display:flex;align-items:flex-start;gap:12px;padding:14px 16px;border-radius:20px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.03)}
.feature-dot{width:12px;height:12px;border-radius:999px;background:linear-gradient(180deg,var(--cyan),var(--blue));box-shadow:0 0 0 6px rgba(116,164,255,.12);margin-top:5px;flex:0 0 auto}
.feature strong{font-size:14px;display:block}
.feature span{display:block;margin-top:4px;color:var(--muted);font-size:14px;line-height:1.55}
.visual{position:relative;min-height:540px}
.visual-panel{position:absolute;inset:0;border-radius:34px;border:1px solid rgba(255,255,255,.1);background:linear-gradient(180deg, rgba(10,15,24,.72), rgba(10,15,24,.52));overflow:hidden;box-shadow:var(--shadow)}
.visual-panel.gmail::before{content:"";position:absolute;inset:0;background:radial-gradient(circle at 22% 18%, rgba(122,226,255,.16), transparent 20%),radial-gradient(circle at 80% 30%, rgba(116,164,255,.16), transparent 18%),radial-gradient(circle at 50% 88%, rgba(122,226,255,.08), transparent 22%)}
.visual-panel.restaurant::before{content:"";position:absolute;inset:0;background:radial-gradient(circle at 18% 22%, rgba(255,154,82,.18), transparent 20%),radial-gradient(circle at 82% 28%, rgba(255,108,174,.14), transparent 18%),radial-gradient(circle at 52% 86%, rgba(255,154,82,.08), transparent 24%)}
.mock-window{position:absolute;left:24px;right:24px;top:24px;height:52px;border-radius:18px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);display:flex;align-items:center;gap:10px;padding:0 16px 0 64px;color:#d7e2f4;font-size:13px;position:absolute}
.mock-window::before{content:"";position:absolute;left:18px;top:50%;transform:translateY(-50%);width:9px;height:9px;border-radius:999px;background:#ff6b6b;box-shadow:16px 0 0 #ffcf55,32px 0 0 #54db74}
.mail-list,.ticket-list{position:absolute;left:24px;right:24px;top:92px;display:grid;gap:12px}
.mail{padding:16px 16px 14px;border-radius:22px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.04);box-shadow:0 12px 24px rgba(0,0,0,.12);animation:mailFloat 10s ease-in-out infinite}
.mail:nth-child(2){animation-delay:-2.4s} .mail:nth-child(3){animation-delay:-4.6s}
.mail strong,.ticket strong{display:block;margin-top:2px;font-size:15px;line-height:1.25;letter-spacing:-.02em}
.mail p,.ticket p{margin:8px 0 0;color:var(--muted);line-height:1.55;font-size:13px}
.ticket-list{grid-template-columns:repeat(2,minmax(0,1fr));top:104px}
.ticket{padding:16px;border-radius:24px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.04);min-height:166px;box-shadow:0 12px 24px rgba(0,0,0,.12);animation:ticketFloat 11s ease-in-out infinite}
.ticket:nth-child(2){animation-delay:-2.2s} .ticket:nth-child(3){animation-delay:-3.7s} .ticket:nth-child(4){animation-delay:-5.1s}
.ticket .label{display:inline-flex;padding:7px 10px;border-radius:999px;border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.04);font-size:10px;font-weight:800;letter-spacing:.11em;text-transform:uppercase;margin-bottom:14px}
.ticket .bar{height:8px;border-radius:999px;background:rgba(255,255,255,.06);overflow:hidden;margin-top:14px}
.ticket .bar > span{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,var(--gold),var(--pink))}
.footer-note{padding:0 22px 64px;text-align:center;color:var(--muted);font-size:13px}
@keyframes float1{0%,100%{transform:translate3d(0,0,0)}50%{transform:translate3d(30px,22px,0)}}
@keyframes float2{0%,100%{transform:translate3d(0,0,0)}50%{transform:translate3d(-26px,32px,0)}}
@keyframes float3{0%,100%{transform:translate3d(0,0,0)}50%{transform:translate3d(18px,-24px,0)}}
@keyframes float4{0%,100%{transform:translate3d(0,0,0)}50%{transform:translate3d(-18px,-20px,0)}}
@keyframes float5{0%,100%{transform:translateY(0) rotate(-4deg)}50%{transform:translateY(-14px) rotate(-2deg)}}
@keyframes float6{0%,100%{transform:translateY(0) rotate(3deg)}50%{transform:translateY(-16px) rotate(1deg)}}
@keyframes float7{0%,100%{transform:translateY(0)}50%{transform:translateY(-12px)}}
@keyframes mailFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
@keyframes ticketFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-12px)}}
@keyframes marquee{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
@keyframes marquee2{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
@keyframes sweep{0%{transform:translateY(-120%)}100%{transform:translateY(260%)}}
@media (max-width: 960px){
  .section-wrap{grid-template-columns:1fr;gap:22px}
  .visual{min-height:500px}
  .hero-media{height:420px}
}
@media (max-width: 640px){
  html,body{width:100%;max-width:100%;overflow-x:hidden}
  body{position:relative}
  .page,.hero,.section,.hero-content,.section-wrap,.visual,.visual-panel,.hero-media,.stage,.mail-list,.ticket-list,.mock-window,.feature-list{width:100%;max-width:100%;min-width:0}
  .logo-float{left:14px;top:14px;width:54px;height:54px;border-radius:17px}
  .logo-float svg{width:34px;height:34px}
  .nav-shell{top:14px;left:82px;right:14px;width:auto;max-width:none;transform:none}
  .nav-shell.hidden{transform:translateY(-18px)}
  .nav-pill{padding:8px 12px 8px 10px;justify-content:center;min-height:54px}
  .nav-toggle{width:40px;height:40px;border-radius:12px;flex:0 0 auto}
  .nav-label{font-size:13px;white-space:nowrap}
  .nav-panel{left:0;right:0;top:62px;transform:none;width:auto;max-width:none}
  .nav-panel.open{transform:none}
  .hero{min-height:auto;padding:118px 16px 56px;overflow:hidden}
  .hero-content{padding:0}
  .hero-title{font-size:22vw}
  .hero-copy{font-size:15px;max-width:100%;padding:0 6px;line-height:1.55}
  .marquee{max-width:100%;margin-top:24px;overflow:hidden}
  .marquee-track{gap:18px;padding:12px 16px}
  .marquee-track span{font-size:11px}
  .hero-media{height:560px;margin-top:26px;overflow:hidden}
  .stage{border-radius:28px;overflow:hidden;padding:0}
  .float-card{padding:14px;max-width:none;box-sizing:border-box}
  .card-mail{left:18px;right:18px;top:92px;width:auto;max-width:none;transform:none!important;animation:none!important}
  .card-pulse{left:50%;transform:translateX(-50%);top:166px;width:118px;max-width:calc(100% - 32px);z-index:3;animation:none!important}
  .card-restaurant{left:18px;right:18px;bottom:112px;width:auto;max-width:none;transform:none!important;animation:none!important}
  .ribbon{left:14px;right:14px;bottom:14px;transform:none;overflow:hidden}
  .ribbon-track{gap:10px;animation-duration:24s;padding-left:6px}
  .ribbon span{padding:10px 14px;font-size:10px}
  .section{padding:72px 16px 96px;overflow:hidden}
  .section-wrap{grid-template-columns:1fr;gap:18px}
  .section-title{font-size:clamp(36px,14vw,62px);line-height:.96;max-width:100%;overflow-wrap:anywhere}
  .section-copy{font-size:15px;max-width:100%}
  .visual{min-height:760px;overflow:hidden}
  .visual-panel{border-radius:28px;overflow:hidden}
  .mock-window{left:16px;right:16px;top:16px;height:48px;border-radius:16px;padding:0 14px 0 70px;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .mock-window::before{left:16px;top:50%;transform:translateY(-50%);width:10px;height:10px;box-shadow:18px 0 0 #ffcf55,36px 0 0 #54db74}
  .mail-list,.ticket-list{left:16px;right:16px;top:80px;bottom:16px;display:grid;gap:12px;align-content:start}
  .mail,.ticket{min-width:0;box-sizing:border-box;max-width:100%}
  .mail strong,.ticket strong{font-size:14px}
  .mail p,.ticket p{font-size:13px;line-height:1.45}
  .mail-list{grid-template-columns:1fr}
  .ticket-list{grid-template-columns:1fr;top:84px}
  .mail{padding:14px}
  .ticket{min-height:136px;padding:14px}
  .ticket .label{margin-bottom:12px;max-width:max-content}
  .feature-list{gap:10px}
  .feature{padding:12px 14px}
  .feature strong{font-size:14px}
  .feature span{font-size:13px}
  .footer-note{padding:0 16px 56px}
}
</style>
</head>
<body>
<div class="noise"></div>
<div class="grid"></div>
<div class="orb"></div><div class="orb2"></div><div class="orb3"></div><div class="orb4"></div>

<div class="logo-float" id="floatingLogo" aria-hidden="true"><svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>
<defs>
<linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>
<stop offset='0%' stop-color='#ff8a2a'/>
<stop offset='55%' stop-color='#ff5f72'/>
<stop offset='100%' stop-color='#915dff'/>
</linearGradient>
</defs>
<rect x='4' y='4' width='56' height='56' rx='18' fill='#0d1422'/>
<rect x='6' y='6' width='52' height='52' rx='16' fill='url(#g)' opacity='0.98'/>
<path d='M39 18.5c-1.8-2.3-4.9-3.7-8.3-3.7-5.6 0-10.3 4.3-10.3 9.8s4.7 9.8 10.3 9.8c3.4 0 6.5-1.4 8.3-3.8' fill='none' stroke='white' stroke-width='5' stroke-linecap='round'/>
<path d='M43 29.6c-1.5-1.8-3.8-2.9-6.4-2.9-4.7 0-8.5 3.6-8.5 8.1s3.8 8.1 8.5 8.1c2.6 0 4.9-1.1 6.4-2.9' fill='none' stroke='white' stroke-width='5' stroke-linecap='round' opacity='0.96'/>
</svg></div>

<div class="nav-shell" id="navShell">
  <div class="nav-pill">
    <button class="nav-toggle" id="navToggle" type="button" aria-label="Menu openen"><span></span></button>
    <div class="nav-label">Menu</div>
  </div>
  <div class="nav-panel" id="navPanel">
    <a class="tool-link" href="/casa-cara-login">
      <div class="tool-left">
        <div class="tool-icon"><svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>
<defs>
<linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>
<stop offset='0%' stop-color='#ff8a2a'/>
<stop offset='55%' stop-color='#ff5f72'/>
<stop offset='100%' stop-color='#915dff'/>
</linearGradient>
</defs>
<rect x='4' y='4' width='56' height='56' rx='18' fill='#0d1422'/>
<rect x='6' y='6' width='52' height='52' rx='16' fill='url(#g)' opacity='0.98'/>
<path d='M39 18.5c-1.8-2.3-4.9-3.7-8.3-3.7-5.6 0-10.3 4.3-10.3 9.8s4.7 9.8 10.3 9.8c3.4 0 6.5-1.4 8.3-3.8' fill='none' stroke='white' stroke-width='5' stroke-linecap='round'/>
<path d='M43 29.6c-1.5-1.8-3.8-2.9-6.4-2.9-4.7 0-8.5 3.6-8.5 8.1s3.8 8.1 8.5 8.1c2.6 0 4.9-1.1 6.4-2.9' fill='none' stroke='white' stroke-width='5' stroke-linecap='round' opacity='0.96'/>
</svg></div>
        <div>
          <div class="tool-title">Restaurant-tool</div>
          <div class="tool-copy">Ga naar je eigen gebouwde restaurant tool</div>
        </div>
      </div>
      <div class="tool-arrow">↗</div>
    </a>
    <a class="tool-link" href="/gmail-login">
      <div class="tool-left">
        <div class="tool-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6.6A2.6 2.6 0 0 1 5.6 4h12.8A2.6 2.6 0 0 1 21 6.6v10.8a2.6 2.6 0 0 1-2.6 2.6H5.6A2.6 2.6 0 0 1 3 17.4Z"/><path d="m4 7 8 6 8-6"/></svg>
        </div>
        <div>
          <div class="tool-title">Gmail Cleaner</div>
          <div class="tool-copy">Open je cleaner, statistieken en automatiseringen</div>
        </div>
      </div>
      <div class="tool-arrow">↗</div>
    </a>
  </div>
</div>

<main class="page">
  <section class="hero">
    <div class="hero-content">
      <div class="eyebrow">Nieuwe launch experience</div>
      <h1 class="hero-title"><span class="gradient">Welkom!</span></h1>
      <p class="hero-copy">Eén plek voor je restaurant-tool en je Gmail Cleaner. Donker, snel, levendig en gebouwd om op telefoon net zo hard te werken als op desktop.</p>
      <div class="marquee">
        <div class="marquee-track">
          <span>Restaurant workflow</span><span>Gmail automations</span><span>Live op mobiel</span><span>Eigen toolstack</span><span>Casa Cara</span><span>Cleaner</span><span>Restaurant workflow</span><span>Gmail automations</span><span>Live op mobiel</span><span>Eigen toolstack</span><span>Casa Cara</span><span>Cleaner</span>
        </div>
      </div>

      <div class="hero-media">
        <div class="stage">
          <div class="scanline"></div>
          <div class="float-card card-mail">
            <strong>Inbox in control</strong>
            <small>Statistieken, opruimen en workflows bewegen mee in hetzelfde systeem.</small>
          </div>
          <div class="float-card card-pulse">
            <div style="font-size:12px;color:var(--muted);font-weight:800;letter-spacing:.12em;text-transform:uppercase">Tool status</div>
            <div class="number">2</div>
          </div>
          <div class="float-card card-restaurant">
            <strong>Restaurant flow</strong>
            <small>Koelingen, bijvullen, diensten, fooienpot en taken in één tool die je team snapt.</small>
          </div>
          <div class="ribbon">
            <div class="ribbon-track">
              <span>Premium interface</span><span>Eigen logins</span><span>Mobiel vriendelijk</span><span>Casa Bot</span><span>Realtime workflow</span><span>Premium interface</span><span>Eigen logins</span><span>Mobiel vriendelijk</span><span>Casa Bot</span><span>Realtime workflow</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <section class="section" id="gmail">
    <div class="section-wrap">
      <div>
        <div class="section-badge">Gmail Cleaner</div>
        <h2 class="section-title">Van inbox chaos naar een strakke cleanup flow.</h2>
        <p class="section-copy">Je cleaner draait achter een eigen login en voelt nu als onderdeel van een echte app. De launch page laat meteen zien wat het doet, zonder dat je overal dezelfde knoppen terugziet.</p>
        <div class="feature-list">
          <div class="feature"><div class="feature-dot"></div><div><strong>Eigen toegangspoort</strong><span>Gmail opent pas na een eigen pincode, los van Casa Cara.</span></div></div>
          <div class="feature"><div class="feature-dot"></div><div><strong>Snel naar actie</strong><span>Statistieken, opschonen en downloads zitten achter een rustige, duidelijke flow.</span></div></div>
          <div class="feature"><div class="feature-dot"></div><div><strong>Meer premium gevoel</strong><span>Niet meer een los script, maar een onderdeel van een branded launch experience.</span></div></div>
        </div>
      </div>
      <div class="visual">
        <div class="visual-panel gmail">
          <div class="mock-window">Gmail Cleaner / live layer</div>
          <div class="mail-list">
            <div class="mail"><strong>Nieuwe PDF downloads</strong><p>Documenten automatisch opgepikt en klaar voor verwerking, zonder dat je inbox dichtslibt.</p></div>
            <div class="mail"><strong>Schonere mailbox</strong><p>Overzichtelijk, sneller terug te vinden en minder handwerk voor je dagelijkse flow.</p></div>
            <div class="mail"><strong>Dashboard met ritme</strong><p>Niet meer losse schermen, maar één systeem dat meteen vertrouwen geeft aan wie het opent.</p></div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <section class="section" id="restaurant">
    <div class="section-wrap">
      <div class="visual">
        <div class="visual-panel restaurant">
          <div class="mock-window">Restaurant-tool / Casa Cara</div>
          <div class="ticket-list">
            <div class="ticket"><div class="label">Voorraad</div><strong>Koelingen & bijvullen</strong><p>Snel aanpassen, slim doorsturen en logisch voor medewerker en admin.</p><div class="bar"><span style="width:82%"></span></div></div>
            <div class="ticket"><div class="label">Taken</div><strong>Wie + wanneer</strong><p>Afvinken met logging, zodat je altijd terugziet wie wat gedaan heeft.</p><div class="bar"><span style="width:68%"></span></div></div>
            <div class="ticket"><div class="label">Rechten</div><strong>Per rol afgestemd</strong><p>Iedereen ziet alleen wat relevant is, ook in sidebar en overzichten.</p><div class="bar"><span style="width:74%"></span></div></div>
            <div class="ticket"><div class="label">Bot</div><strong>Chat-achtige hulp</strong><p>Sneller antwoorden, doorsturen naar acties en een betere gebruikersflow.</p><div class="bar"><span style="width:61%"></span></div></div>
          </div>
        </div>
      </div>
      <div>
        <div class="section-badge">Restaurant-tool</div>
        <h2 class="section-title">Gebouwd voor de vloer, maar nu met de uitstraling van een echte app.</h2>
        <p class="section-copy">Je restaurant-tool blijft praktisch, maar de launch page voelt veel groter en spannender. Beweging, diepte en sfeer zonder dat het onrustig of onleesbaar wordt.</p>
        <div class="feature-list">
          <div class="feature"><div class="feature-dot" style="background:linear-gradient(180deg,var(--gold),var(--pink));box-shadow:0 0 0 6px rgba(255,154,82,.12)"></div><div><strong>Eigen loginflow</strong><span>Casa Cara houdt z’n tweede login, maar nu in een veel strakkere visuele laag.</span></div></div>
          <div class="feature"><div class="feature-dot" style="background:linear-gradient(180deg,var(--gold),var(--pink));box-shadow:0 0 0 6px rgba(255,154,82,.12)"></div><div><strong>Nav als toegangspoort</strong><span>De tools leef je niet meer via losse buttons op de page in, maar via de zwevende menu-ervaring.</span></div></div>
          <div class="feature"><div class="feature-dot" style="background:linear-gradient(180deg,var(--gold),var(--pink));box-shadow:0 0 0 6px rgba(255,154,82,.12)"></div><div><strong>Levende backgrounds</strong><span>Meer beweging, meer gelaagdheid en genoeg stijl om het werkgever-proof te maken.</span></div></div>
        </div>
      </div>
    </div>
  </section>

  <div class="footer-note">Open de tools via het floating menu bovenin.</div>
</main>

<script>
const navToggle = document.getElementById('navToggle');
const navPanel = document.getElementById('navPanel');
const navShell = document.getElementById('navShell');
const floatingLogo = document.getElementById('floatingLogo');
let lastScrollY = window.scrollY;
function updateFloatingState(){
  const y = window.scrollY;
  const doc = document.documentElement;
  const nearBottom = y + window.innerHeight > doc.scrollHeight - 180;
  const goingDown = y > lastScrollY && y > 50;
  navShell.classList.toggle('hidden', goingDown || nearBottom);
  floatingLogo.classList.toggle('hidden', goingDown || nearBottom);
  const inReadableZone = y > window.innerHeight * 0.72 && y < window.innerHeight * 1.35;
  floatingLogo.classList.toggle('dim', inReadableZone);
  lastScrollY = y;
}
navToggle.addEventListener('click', (e) => {
  e.stopPropagation();
  navPanel.classList.toggle('open');
});
document.addEventListener('click', (e) => {
  if(!navShell.contains(e.target)) navPanel.classList.remove('open');
});
window.addEventListener('scroll', updateFloatingState, {passive:true});
updateFloatingState();
</script>
</body>
</html>
"""

GMAIL_HTML = """

<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover, maximum-scale=1.0, user-scalable=no">
<title>Gmail Cleaner</title>
<link rel="icon" type="image/png" href="/static/gmail.png">
<style>
:root{
  --bg:#06101c; --bg2:#0b1220; --text:#eff6ff; --muted:#9fb0c7;
  --line:rgba(159,176,199,.14); --line-strong:rgba(159,176,199,.22);
  --accent:#63d5ff; --good:#22c55e; --warn:#f59e0b; --danger:#ef4444;
  --shadow:0 20px 50px rgba(0,0,0,.28); --radius:28px;
}
*{box-sizing:border-box}
body{
  margin:0; color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif;
  background:
    radial-gradient(circle at 10% 0%, rgba(56,189,248,.15), transparent 24%),
    radial-gradient(circle at 90% 0%, rgba(99,213,255,.10), transparent 22%),
    radial-gradient(circle at 50% 100%, rgba(34,197,94,.06), transparent 30%),
    linear-gradient(180deg, var(--bg), var(--bg2));
  min-height:100vh;
}
.wrap{
    background:#0b1a2b;max-width:1380px;margin:0 auto;padding:calc(24px + env(safe-area-inset-top,0px)) 20px calc(44px + env(safe-area-inset-bottom,0px))}
.topbar{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:16px}
.back{
  display:inline-flex;align-items:center;gap:8px;
  text-decoration:none;color:var(--text);
  padding:10px 14px;border-radius:16px;
  background:rgba(16,27,48,.88);
  border:1px solid var(--line);
}
.hero{
  display:grid;
  grid-template-columns:minmax(0,1.25fr) auto;
  gap:22px;
  align-items:start;
  margin-bottom:24px;
}
.hero-main{
  background:linear-gradient(180deg, rgba(15,23,42,.78), rgba(15,23,42,.55));
  border:1px solid var(--line);
  border-radius:32px;
  padding:26px 26px 20px;
  box-shadow:var(--shadow);
}
.eyebrow{
  display:inline-flex;align-items:center;gap:8px;
  font-size:12px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
  color:#bfe9ff;background:rgba(56,189,248,.10);border:1px solid rgba(99,213,255,.18);
  padding:8px 12px;border-radius:999px;margin-bottom:14px;
}
.eyebrow::before{
  content:""; width:8px;height:8px;border-radius:999px;background:var(--accent);
  box-shadow:0 0 0 6px rgba(56,189,248,.12);
}
.hero h1{margin:0 0 10px;font-size:42px;line-height:1.05;letter-spacing:-.03em}
.hero p{margin:0;color:var(--muted);line-height:1.6;max-width:780px;font-size:14px}
.statusrow{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}
.status{
  color:var(--muted);font-size:14px;padding:12px 14px;border-radius:16px;
  background:rgba(15,23,42,.62);border:1px solid var(--line);display:inline-flex;align-items:center;gap:10px;min-height:46px;
}
.dot{width:10px;height:10px;border-radius:999px;background:var(--muted);display:inline-block}
.dot.running{background:var(--accent);box-shadow:0 0 0 6px rgba(56,189,248,.12)}
.dot.ready{background:var(--good);box-shadow:0 0 0 6px rgba(34,197,94,.12)}
.dot.waiting{background:var(--warn);box-shadow:0 0 0 6px rgba(245,158,11,.12)}
.buttons{display:grid;gap:12px;min-width:280px}
button,.linkbtn{
  border:1px solid rgba(159,176,199,.10);border-radius:18px;padding:13px 18px;font-size:14px;font-weight:800;
  cursor:pointer;text-decoration:none;color:white;background:rgba(28,37,56,.92);
  transition:transform .16s ease,opacity .16s ease,background .16s ease,box-shadow .16s ease,border-color .16s ease;
  box-shadow:0 10px 26px rgba(0,0,0,.16);
}
button:hover,.linkbtn:hover{transform:translateY(-2px);opacity:.98;box-shadow:0 16px 34px rgba(0,0,0,.24);border-color:rgba(159,176,199,.20)}
button:disabled{opacity:.58;cursor:not-allowed;transform:none}
.primary{background:linear-gradient(180deg,#8ae3ff,#38bdf8);color:#08263a}
.secondary{background:rgba(28,37,56,.96)}
.danger{background:linear-gradient(180deg,#fca5a5,#ef4444);color:#3b0909}
.progress-shell{margin-top:16px;background:rgba(11,18,32,.66);border-radius:18px;padding:14px 16px;border:1px solid var(--line)}
.progress-head{display:flex;justify-content:space-between;gap:10px;align-items:center}
.progress-line{height:12px;background:rgba(159,176,199,.12);border-radius:999px;overflow:hidden;margin-top:10px}
.progress-fill{height:100%;width:0%;background:linear-gradient(90deg,#7ddfff,#38bdf8);transition:width .25s ease}
.tabs{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0 20px;padding:8px;border-radius:22px;background:rgba(10,18,32,.54);border:1px solid var(--line)}
.tabbtn{background:transparent;color:var(--text);border:1px solid transparent;box-shadow:none}
.tabbtn.active{background:linear-gradient(180deg,#8ae3ff,#38bdf8);color:#08263a;border-color:transparent;box-shadow:0 10px 24px rgba(56,189,248,.24)}
.tabpanel{display:none}.tabpanel.active{display:block}
.section-title{margin:0 0 14px;font-size:20px;letter-spacing:-.02em}
.muted{color:var(--muted);font-size:14px}
.card,.chart-card{background:linear-gradient(180deg, rgba(16,27,48,.86), rgba(12,20,36,.78));border:1px solid var(--line);border-radius:var(--radius);padding:20px;box-shadow:var(--shadow)}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:18px}
.stat .label{color:var(--muted);font-size:13px;margin-bottom:12px}
.stat .value-row{display:flex;align-items:flex-end;gap:10px}
.stat .value{font-size:36px;font-weight:900;line-height:1.05;letter-spacing:-.03em}
.stat .delta{font-size:13px;color:#91d7ff;font-weight:800;background:rgba(56,189,248,.10);padding:6px 9px;border-radius:999px;border:1px solid rgba(56,189,248,.16)}
.searchbar{width:100%;border:1px solid rgba(201,170,112,.16);background:rgba(8,8,8,.92);color:var(--text);border-radius:18px;padding:14px 15px;font-size:14px;margin-bottom:14px;outline:none}
.list{display:grid;gap:10px}
.item{background:rgba(17,27,45,.78);border-radius:18px;padding:15px 16px;cursor:pointer;border:1px solid rgba(159,176,199,.08)}
.item .time{color:var(--muted);font-size:12px;margin-bottom:6px}
.item .title{font-weight:800;line-height:1.35}
.item .meta{color:var(--muted);font-size:13px;margin-top:6px;line-height:1.5}
.foldergrid{display:grid;gap:12px}
.folder{display:flex;justify-content:space-between;align-items:center;background:rgba(17,27,45,.78);border-radius:18px;padding:14px 16px;border:1px solid rgba(159,176,199,.08)}
.chart-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:18px}
.chart{display:flex;align-items:flex-end;gap:12px;min-height:230px;padding-top:10px}
.bar-wrap{flex:1;display:flex;flex-direction:column;align-items:center;min-width:0}
.bar-value{font-size:12px;color:var(--text);margin-bottom:8px;background:rgba(255,255,255,.04);padding:4px 8px;border-radius:999px;border:1px solid rgba(159,176,199,.08)}
.bar{width:100%;max-width:54px;border-radius:16px 16px 8px 8px;min-height:8px;transition:height .4s ease}
.bar-label{font-size:11px;color:var(--muted);margin-top:8px;text-align:center}
.bar.green{background:linear-gradient(180deg,#86efac,#22c55e)}
.bar.orange{background:linear-gradient(180deg,#fcd34d,#f59e0b)}
.empty{padding:18px;background:rgba(17,27,45,.58);border-radius:18px;color:var(--muted);border:1px dashed rgba(159,176,199,.14)}
.pending-card{border-color:rgba(239,68,68,.22);background:radial-gradient(circle at top right, rgba(239,68,68,.10), transparent 28%),linear-gradient(180deg, rgba(32,17,24,.88), rgba(20,14,18,.82))}
.pending-top{display:flex;justify-content:space-between;gap:14px;align-items:start;flex-wrap:wrap}
.pending-badge{font-size:12px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:#fecaca;background:rgba(239,68,68,.12);padding:8px 10px;border-radius:999px;border:1px solid rgba(239,68,68,.20)}
.actionrow{display:flex;gap:12px;flex-wrap:wrap;margin-top:14px}
.modal-backdrop{position:fixed;inset:0;background:rgba(2,6,23,.76);display:none;align-items:center;justify-content:center;z-index:9999}
.modal-backdrop.active{display:flex}
.modal{width:min(760px,calc(100vw - 24px));max-height:84vh;overflow:auto;background:#0d1628;border:1px solid var(--line-strong);border-radius:28px;padding:22px;box-shadow:0 24px 60px rgba(0,0,0,.40)}
.modal h3{margin:0 0 12px;font-size:22px}
.modal .row{margin-bottom:14px}
.modal .key{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.06em}
.modal .val{margin-top:4px;line-height:1.55}
.modal-close{float:right;background:rgba(31,41,55,.9);margin-left:10px}
.toast-wrap{position:fixed;top:18px;right:18px;z-index:10000;display:grid;gap:10px}
.toast{min-width:300px;max-width:390px;background:rgba(9,15,28,.96);border:1px solid rgba(201,170,112,.16);color:var(--text);border-radius:18px;padding:14px 16px;box-shadow:0 18px 40px rgba(0,0,0,.32)}
.toast .title{font-weight:900;margin-bottom:4px}
.toast.success{border-color:rgba(34,197,94,.35)}
.toast.info{border-color:rgba(56,189,248,.35)}
.toast.warning{border-color:rgba(245,158,11,.35)}
.toast.danger{border-color:rgba(239,68,68,.35)}
@media (max-width:1100px){.hero{grid-template-columns:1fr}.buttons{grid-template-columns:repeat(3,minmax(0,1fr));min-width:0}}
@media (max-width:1000px){.grid{grid-template-columns:repeat(2,1fr)}.chart-grid{grid-template-columns:1fr}}
@media (max-width:640px){.wrap{
    background:transparent;padding:18px 14px 34px}.hero-main{padding:20px 18px 18px}.hero h1{font-size:34px}.grid{grid-template-columns:1fr}.buttons{grid-template-columns:1fr}.tabs{padding:6px}}

@media (max-width: 480px){
  body{padding:20px}
  .card{padding:24px 18px 18px}
  .pad{gap:10px}
  .key{min-height:54px;font-size:21px}
  .toolbar{margin-top:14px}
}


.bg-fixed{
  position:fixed;
  inset:0;
  background:
    radial-gradient(circle at 10% 0%, rgba(148,163,184,.08), transparent 24%),
    radial-gradient(circle at 90% 0%, rgba(148,163,184,.05), transparent 22%),
    radial-gradient(circle at 50% 100%, rgba(148,163,184,.04), transparent 30%),
    linear-gradient(180deg, #06101c, #0b1220);
  z-index:-1;
}


html,body{
  margin:0;
  min-height:100%;
  background:#0b1220 !important;
  overscroll-behavior:none;
}
body{
  min-height:100vh;
  min-height:100dvh;
  min-height:100svh;
  padding-top:env(safe-area-inset-top,0px);
  padding-bottom:env(safe-area-inset-bottom,0px);
}
.bg-fixed{
  position:fixed;
  inset:0;
  background:
    radial-gradient(circle at 10% 0%, rgba(56,189,248,.15), transparent 24%),
    radial-gradient(circle at 90% 0%, rgba(99,213,255,.10), transparent 22%),
    radial-gradient(circle at 50% 100%, rgba(34,197,94,.06), transparent 30%),
    linear-gradient(180deg, #06101c, #0b1220);
  z-index:-1;
}
.wrap{
  background:transparent !important;
}

</style>
</head>
<body>
<div class="bg-fixed"></div>
<div class="wrap">
  <div class="topbar">
    <a class="back" href="/">← Terug naar home</a>
    <a class="back" href="/logout">Uitloggen</a>
  </div>
  <div class="hero">
    <div class="hero-main">
      <div class="eyebrow">Gmail automation center</div>
      <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;"><img src="/static/gmail.png" alt="Gmail" onerror="this.style.display='none'" style="width:40px;height:40px;object-fit:contain;border-radius:12px;background:white;padding:6px;"><h1>Gmail Cleaner</h1></div>
      <p>Je centrale overzicht voor Gmail-opruiming, PDF-downloads, goedkeuringen en geschiedenis.</p>
      <div class="statusrow">
        <div class="status" id="statusText"><span class="dot" id="statusDot"></span><span id="statusLabel">Status laden…</span></div>
        <div class="status" id="autoRunText">Auto-run: laden…</div>
      </div>
      <div id="progressShell" class="progress-shell" style="display:none;">
        <div class="progress-head">
          <div id="progressText" class="muted">Bezig...</div>
          <div id="progressPercent" class="muted">0%</div>
        </div>
        <div class="progress-line"><div id="progressFill" class="progress-fill"></div></div>
      </div>
    </div>
    <div class="buttons">
      <button id="btnFull" class="primary" onclick="runGmail('full')">Nu Gmail checken</button>
      <button id="btnCleanup" class="secondary" onclick="runGmail('cleanup')">Alleen cleanup</button>
      <button id="btnPdfs" class="secondary" onclick="runGmail('pdfs')">Alleen PDF's ophalen</button>
    </div>
  </div>

  <div id="pendingApprovalCard" class="card pending-card" style="display:none; margin-bottom:18px;">
    <div class="pending-top">
      <div>
        <div class="pending-badge">Goedkeuring nodig</div>
        <h2 class="section-title" style="margin-top:12px;">Er wachten mails op jouw keuze</h2>
        <div class="muted" id="pendingSummary">Er wachten mails op goedkeuring.</div>
      </div>
    </div>
    <div class="actionrow">
      <button id="approveBtn" class="danger" onclick="approveTrash()">Ja, naar prullenbak</button>
      <button id="rejectBtn" class="secondary" onclick="rejectTrash()">Nee, annuleren</button>
      <button class="secondary" onclick="showPendingModal()">Bekijk lijst</button>
    </div>
  </div>

  <div class="tabs">
    <button class="tabbtn active" onclick="showTab('overzicht', this)">Overzicht</button>
    <button class="tabbtn" onclick="showTab('prullenbak', this)">Naar prullenbak</button>
    <button class="tabbtn" onclick="showTab('pdfs', this)">PDF's gedownload</button>
    <button class="tabbtn" onclick="showTab('bewaard', this)">Bewaarde mails</button>
    <button class="tabbtn" onclick="showTab('activiteit', this)">Activiteit / logs</button>
    <button class="tabbtn" onclick="showTab('shortcuts', this)">Shortcuts</button>
  </div>

  <div id="tab-overzicht" class="tabpanel active">
    <div class="grid">
      <div class="card stat"><div class="label">Laatste run</div><div class="value" id="lastRun">-</div></div>
      <div class="card stat"><div class="label">Mails gescand</div><div class="value-row"><div class="value" id="emailsScanned">0</div><div class="delta" id="emailsScannedDelta"></div></div></div>
      <div class="card stat"><div class="label">PDF's gedownload</div><div class="value-row"><div class="value" id="pdfsDownloaded">0</div><div class="delta" id="pdfsDownloadedDelta"></div></div></div>
      <div class="card stat"><div class="label">Naar prullenbak</div><div class="value-row"><div class="value" id="emailsTrashed">0</div><div class="delta" id="emailsTrashedDelta"></div></div></div>
    </div>
    <div class="grid">
      <div class="card stat"><div class="label">Beschermde mails bewaard</div><div class="value-row"><div class="value" id="protectedKept">0</div><div class="delta" id="protectedKeptDelta"></div></div></div>
      <div class="card stat"><div class="label">Belangrijke mails bewaard</div><div class="value-row"><div class="value" id="importantKept">0</div><div class="delta" id="importantKeptDelta"></div></div></div>
      <div class="card stat"><div class="label">Dubbele downloads overgeslagen</div><div class="value-row"><div class="value" id="duplicateSkipped">0</div><div class="delta" id="duplicateSkippedDelta"></div></div></div>
      <div class="card stat"><div class="label">Laatste status</div><div class="value" id="lastStatus" style="font-size:22px;">-</div></div>
    </div>
    <div class="grid">
      <div class="card stat"><div class="label">Vandaag verwijderd</div><div class="value" id="trashToday">0</div></div>
      <div class="card stat"><div class="label">Afgelopen 7 dagen verwijderd</div><div class="value" id="trashWeek">0</div></div>
      <div class="card stat"><div class="label">Vandaag PDF's</div><div class="value" id="pdfToday">0</div></div>
      <div class="card stat"><div class="label">Afgelopen 7 dagen PDF's</div><div class="value" id="pdfWeek">0</div></div>
    </div>
    <div class="chart-grid">
      <div class="chart-card"><h2 class="section-title">Prullenbak per dag</h2><div class="muted" style="margin-bottom:8px;">Hoeveel mails per dag naar de prullenbak zijn gegaan.</div><div id="trashChart" class="chart"></div></div>
      <div class="chart-card"><h2 class="section-title">PDF-downloads per dag</h2><div class="muted" style="margin-bottom:8px;">Hoeveel PDF's per dag zijn opgeslagen.</div><div id="downloadChart" class="chart"></div></div>
    </div>
    <div class="chart-grid">
      <div class="chart-card"><h2 class="section-title">Afgelopen 30 dagen</h2><div class="muted" style="margin-bottom:8px;">Slim overzicht van trends.</div><div id="thirtyDaySummary" class="list"></div></div>
      <div class="chart-card"><h2 class="section-title">Top afzenders (prullenbak)</h2><div class="muted" style="margin-bottom:8px;">Welke afzenders het vaakst in prullenbak eindigen.</div><div id="topSenders" class="list"></div></div>
    </div>
  </div>

  <div id="tab-prullenbak" class="tabpanel"><div class="card"><h2 class="section-title">Mails naar prullenbak</h2><input id="trashSearch" class="searchbar" placeholder="Zoek op onderwerp of afzender..." oninput="renderTrash()"><div id="trashList" class="list"></div></div></div>
  <div id="tab-pdfs" class="tabpanel"><div class="card"><h2 class="section-title">PDF's gedownload</h2><input id="downloadsSearch" class="searchbar" placeholder="Zoek op bestandsnaam, onderwerp of afzender..." oninput="renderDownloads()"><div id="downloadsList" class="list"></div></div></div>
  <div id="tab-bewaard" class="tabpanel"><div class="card"><h2 class="section-title">Bewaarde mails</h2><input id="keptSearch" class="searchbar" placeholder="Zoek op onderwerp, afzender of type..." oninput="renderKept()"><div id="keptList" class="list"></div></div></div>
  <div id="tab-activiteit" class="tabpanel"><div class="card"><h2 class="section-title">Activiteit / logs</h2><input id="activitySearch" class="searchbar" placeholder="Zoek in activiteiten..." oninput="renderActivity()"><div id="activityList" class="list"></div></div></div>
  <div id="tab-shortcuts" class="tabpanel"><div class="card"><h2 class="section-title">Shortcuts</h2><div class="foldergrid"><div class="folder"><span>Documenten</span><a class="linkbtn" href="/open/documenten">Open</a></div><div class="folder"><span>Loonstroken</span><a class="linkbtn" href="/open/loonstroken">Open</a></div><div class="folder"><span>Foto's</span><a class="linkbtn" href="/open/fotos">Open</a></div><div class="folder"><span>Dropbox map</span><a class="linkbtn" href="/open/base">Open</a></div></div></div></div>
</div>

<div id="modalBackdrop" class="modal-backdrop" onclick="closeModal(event)">
  <div class="modal">
    <button class="modal-close linkbtn" onclick="forceCloseModal()">Sluiten</button>
    <h3 id="modalTitle">Details</h3>
    <div id="modalBody"></div>
  </div>
</div>

<div id="toastWrap" class="toast-wrap"></div>

<script>
let trashData = [];
let downloadsData = [];
let keptData = [];
let activityData = [];
let pendingTrashData = [];
let previousStats = null;
let clientRunPending = false;
let clientActionPending = false;

const esc = v => (v ?? '').toString().replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
const fmt = v => v && v > 0 ? `+${v}` : '';
const set = (id, v) => document.getElementById(id).textContent = v;

function showTab(name, btn){document.querySelectorAll('.tabpanel').forEach(el=>el.classList.remove('active'));document.querySelectorAll('.tabbtn').forEach(el=>el.classList.remove('active'));document.getElementById('tab-'+name).classList.add('active');btn.classList.add('active');}
function openModal(title, rows){document.getElementById('modalTitle').textContent=title;document.getElementById('modalBody').innerHTML=rows.map(r=>`<div class="row"><div class="key">${esc(r.key)}</div><div class="val">${esc(r.value)}</div></div>`).join('');document.getElementById('modalBackdrop').classList.add('active');}
function closeModal(e){if(e.target.id==='modalBackdrop')document.getElementById('modalBackdrop').classList.remove('active')}
function forceCloseModal(){document.getElementById('modalBackdrop').classList.remove('active')}
function showToast(title,message,type='info'){const wrap=document.getElementById('toastWrap');const el=document.createElement('div');el.className=`toast ${type}`;el.innerHTML=`<div class="title">${esc(title)}</div><div>${esc(message)}</div>`;wrap.appendChild(el);setTimeout(()=>{el.style.opacity='0';setTimeout(()=>el.remove(),220)},3600)}
function setRunButtons(disabled){['btnFull','btnCleanup','btnPdfs'].forEach(id=>document.getElementById(id).disabled=disabled)}
function setApprovalButtons(disabled){document.getElementById('approveBtn').disabled=disabled;document.getElementById('rejectBtn').disabled=disabled;}
function updateStatusBadge(statusText,running=false,waiting=false){const dot=document.getElementById('statusDot');const label=document.getElementById('statusLabel');dot.className='dot';if(running)dot.classList.add('running');else if(waiting)dot.classList.add('waiting');else dot.classList.add('ready');label.textContent=statusText;}
function renderItems(id,items,formatter){const c=document.getElementById(id);c.innerHTML='';if(!items||items.length===0){c.innerHTML='<div class="empty">Geen gegevens gevonden.</div>';return;}items.slice().reverse().forEach(item=>{const el=document.createElement('div');el.className='item';el.innerHTML=formatter(item);c.appendChild(el);});}
function filterItems(items,q,keys){if(!q)return items;const s=q.toLowerCase();return items.filter(item=>keys.some(k=>((item[k]||'').toString().toLowerCase()).includes(s)));}
function groupByDay(items,key){const counts={};items.forEach(item=>{const v=(item[key]||'');const d=v.split(' ')[0]||v;if(!d)return;counts[d]=(counts[d]||0)+1;});return counts;}
function renderBarChart(id,counts,color){const c=document.getElementById(id);const entries=Object.entries(counts).slice(-7);if(entries.length===0){c.innerHTML='<div class="empty">Nog geen gegevens voor deze grafiek.</div>';return;}const max=Math.max(...entries.map(e=>e[1]),1);c.innerHTML='';entries.forEach(([label,value])=>{const w=document.createElement('div');w.className='bar-wrap';w.innerHTML=`<div class="bar-value">${value}</div><div class="bar ${color}" style="height:${Math.max((value/max)*160,8)}px"></div><div class="bar-label">${label}</div>`;c.appendChild(w);});}
function wireClicks(id,data,cb){const c=document.getElementById(id);Array.from(c.children).forEach((node,idx)=>{node.onclick=()=>cb(data.slice().reverse()[idx]);});}
function parseDate(v){const [d]=(v||'').split(' ');if(!d)return null;const [day,month,year]=d.split('-').map(Number);if(!day||!month||!year)return null;return new Date(year,month-1,day);}
function countSince(items,key,daysBack){const threshold=new Date();threshold.setHours(0,0,0,0);threshold.setDate(threshold.getDate()-daysBack);return items.filter(item=>{const dt=parseDate(item[key]||'');return dt&&dt>=threshold;}).length;}
function topSenders(items,limit=5){const counts={};items.forEach(item=>{const sender=(item.sender||'Onbekend').trim();counts[sender]=(counts[sender]||0)+1;});return Object.entries(counts).sort((a,b)=>b[1]-a[1]).slice(0,limit);}
function renderOverviewExtras(){set('trashToday',countSince(trashData,'time',0));set('trashWeek',countSince(trashData,'time',6));set('pdfToday',countSince(downloadsData,'time',0));set('pdfWeek',countSince(downloadsData,'time',6));const trash30=countSince(trashData,'time',29),pdf30=countSince(downloadsData,'time',29),kept30=countSince(keptData,'time',29);document.getElementById('thirtyDaySummary').innerHTML=`<div class="item"><div class="title">Laatste 30 dagen</div><div class="meta">Prullenbak: ${trash30}<br>PDF's: ${pdf30}<br>Bewaard: ${kept30}</div></div><div class="item"><div class="title">Trend-indicatie</div><div class="meta">${trash30>pdf30?'Je ruimt meer mails op dan je PDF’s binnenkrijgt.':'Je ontvangt relatief veel belangrijke PDF’s.'}</div></div>`;const senders=topSenders(trashData);document.getElementById('topSenders').innerHTML=senders.length?senders.map(([s,c])=>`<div class="item"><div class="title">${esc(s)}</div><div class="meta">${c} keer in prullenbak</div></div>`).join(''):'<div class="empty">Nog geen afzenders bekend.</div>';renderBarChart('trashChart',groupByDay(trashData,'time'),'orange');renderBarChart('downloadChart',groupByDay(downloadsData,'time'),'green');}
async function loadOverview(){const res=await fetch('/api/stats');const d=await res.json();set('lastRun',d.last_run||'-');set('emailsScanned',d.emails_scanned??0);set('pdfsDownloaded',d.pdfs_downloaded??0);set('emailsTrashed',d.emails_trashed??0);set('protectedKept',d.protected_kept??0);set('importantKept',d.important_kept??0);set('duplicateSkipped',d.duplicate_skipped??0);set('lastStatus',d.last_status||'-');set('autoRunText','Auto-run: elke dag om 09:00 en bij inloggen');set('emailsScannedDelta',fmt(d.run_scanned_delta));set('pdfsDownloadedDelta',fmt(d.run_pdfs_delta));set('emailsTrashedDelta',fmt(d.run_trashed_delta));set('protectedKeptDelta',fmt(d.run_protected_delta));set('importantKeptDelta',fmt(d.run_important_delta));set('duplicateSkippedDelta',fmt(d.run_duplicate_delta));const shell=document.getElementById('progressShell'),fill=document.getElementById('progressFill'),text=document.getElementById('progressText'),percent=document.getElementById('progressPercent');const running=!!d.is_running,current=d.progress_current||0,total=d.progress_total||0,pct=total>0?Math.round((current/total)*100):0;const waitingApproval=(d.last_status||'').toLowerCase().includes('wacht op goedkeuring');shell.style.display=running?'block':'none';fill.style.width=`${pct}%`;text.textContent=running?`Bezig: ${current} van ${total} verwerkt`:'Klaar';percent.textContent=running?`${pct}%`:'100%';updateStatusBadge(`Status: ${d.last_status||'onbekend'}`,running,waitingApproval);if(running)setRunButtons(true);else if(!clientActionPending)setRunButtons(false);if(previousStats&&previousStats.is_running&&!d.is_running)showToast('Run voltooid',d.last_status||'Gmail-check klaar','info');previousStats=d;}
async function loadPendingApproval(){const res=await fetch('/api/pending-trash');const d=await res.json();pendingTrashData=d.items||[];const card=document.getElementById('pendingApprovalCard');const summary=document.getElementById('pendingSummary');if(pendingTrashData.length>0){card.style.display='block';summary.textContent=`${pendingTrashData.length} mail(s) wachten op goedkeuring om naar de prullenbak te gaan.`;}else card.style.display='none';}
function showPendingModal(){if(!pendingTrashData.length)return;openModal('Te goed te keuren mails',pendingTrashData.map((item,idx)=>({key:`Mail ${idx+1}`,value:`${item.subject||'(geen onderwerp)'} — ${item.sender||'-'}`})));}
async function runGmail(mode){if(clientRunPending)return;clientRunPending=true;setRunButtons(true);try{const res=await fetch(`/api/run-gmail?mode=${encodeURIComponent(mode)}`,{method:'POST'});const d=await res.json();showToast('Run gestart',d.message||'Gmail-check gestart','info');setTimeout(refreshAll,1200);}finally{setTimeout(()=>{clientRunPending=false;},1500);}}
async function approveTrash(){if(clientActionPending)return;clientActionPending=true;setApprovalButtons(true);try{const res=await fetch('/api/approve-trash',{method:'POST'});const d=await res.json();showToast('Goedkeuring verstuurd',d.message||'Mails worden naar prullenbak verplaatst','danger');setTimeout(refreshAll,1200)}finally{clientActionPending=false;setApprovalButtons(false);}}
async function rejectTrash(){if(clientActionPending)return;clientActionPending=true;setApprovalButtons(true);try{const res=await fetch('/api/reject-trash',{method:'POST'});const d=await res.json();showToast('Actie geannuleerd',d.message||'Prullenbak-lijst is gewist','info');setTimeout(refreshAll,700)}finally{clientActionPending=false;setApprovalButtons(false);}}
function renderTrash(){const q=document.getElementById('trashSearch').value.trim();const filtered=filterItems(trashData,q,['subject','sender','time']);renderItems('trashList',filtered,item=>`<div class="time">${esc(item.time||'')}</div><div class="title">${esc(item.subject||'(geen onderwerp)')}</div><div class="meta">Van: ${esc(item.sender||'-')}</div>`);wireClicks('trashList',filtered,item=>openModal('Mail naar prullenbak',[{key:'Tijd',value:item.time||'-'},{key:'Onderwerp',value:item.subject||'-'},{key:'Afzender',value:item.sender||'-'},{key:'Message ID',value:item.message_id||'-'}]));}
function renderDownloads(){const q=document.getElementById('downloadsSearch').value.trim();const filtered=filterItems(downloadsData,q,['filename','subject','sender','time']);renderItems('downloadsList',filtered,item=>`<div class="time">${esc(item.time||'')}</div><div class="title">${esc(item.filename||'-')}</div><div class="meta">Van: ${esc(item.sender||'-')}<br>Onderwerp: ${esc(item.subject||'-')}</div>`);wireClicks('downloadsList',filtered,item=>openModal('PDF gedownload',[{key:'Tijd',value:item.time||'-'},{key:'Bestandsnaam',value:item.filename||'-'},{key:'Afzender',value:item.sender||'-'},{key:'Onderwerp',value:item.subject||'-'},{key:'Message ID',value:item.message_id||'-'}]));}
function renderKept(){const q=document.getElementById('keptSearch').value.trim();const filtered=filterItems(keptData,q,['subject','sender','type','time']);renderItems('keptList',filtered,item=>`<div class="time">${esc(item.time||'')}</div><div class="title">${esc(item.subject||'(geen onderwerp)')}</div><div class="meta">Van: ${esc(item.sender||'-')}<br>Type: ${esc(item.type||'-')}</div>`);wireClicks('keptList',filtered,item=>openModal('Mail bewaard',[{key:'Tijd',value:item.time||'-'},{key:'Onderwerp',value:item.subject||'-'},{key:'Afzender',value:item.sender||'-'},{key:'Type',value:item.type||'-'},{key:'Message ID',value:item.message_id||'-'}]));}
function renderActivity(){const q=document.getElementById('activitySearch').value.trim();const filtered=filterItems(activityData,q,['message','time']);renderItems('activityList',filtered,item=>`<div class="time">${esc(item.time||'')}</div><div class="title">${esc(item.message||'')}</div>`);wireClicks('activityList',filtered,item=>openModal('Activiteit',[{key:'Tijd',value:item.time||'-'},{key:'Actie',value:item.message||'-'}]));}
async function loadHistory(){const [trash,downloads,kept,activity]=await Promise.all([fetch('/api/trash').then(r=>r.json()),fetch('/api/downloads').then(r=>r.json()),fetch('/api/kept').then(r=>r.json()),fetch('/api/activity').then(r=>r.json())]);trashData=trash||[];downloadsData=downloads||[];keptData=kept||[];activityData=activity||[];renderTrash();renderDownloads();renderKept();renderActivity();renderOverviewExtras();}
function refreshAll(){loadOverview();loadHistory();loadPendingApproval();}
refreshAll();setInterval(refreshAll,2500);
</script>
</body>
</html>

"""



@app.before_request
def require_login():
    import time
    if request.path.startswith("/static/"):
        return None

    protected_gmail_endpoints = {
        "gmail",
        "api_stats",
        "api_trash",
        "api_downloads",
        "api_kept",
        "api_activity",
        "api_pending_trash",
        "run_gmail",
        "api_approve_trash",
        "api_reject_trash",
    }

    if session.get("casa_logged_in"):
        last_activity = float(session.get("casa_last_activity", 0) or 0)
        now = time.time()
        if last_activity and (now - last_activity) > 120:
            for key in ["casa_logged_in", "casa_last_activity", "casa_user_pin", "casa_user_name", "casa_user_role"]:
                session.pop(key, None)
            session["casa_login_message"] = "Je Casa Cara sessie is verlopen. Log opnieuw in."
            session["casa_login_success"] = False
            if request.path.startswith("/casa-cara"):
                return redirect(url_for("casa_login_page"))
        else:
            session["casa_last_activity"] = now

    if session.get("gmail_logged_in"):
        last_activity = float(session.get("gmail_last_activity", 0) or 0)
        now = time.time()
        if last_activity and (now - last_activity) > 120:
            for key in ["gmail_logged_in", "gmail_last_activity"]:
                session.pop(key, None)
            session["gmail_login_message"] = "Je Gmail Cleaner sessie is verlopen. Log opnieuw in."
            session["gmail_login_success"] = False
            if request.endpoint in protected_gmail_endpoints:
                if request.path.startswith("/api/"):
                    return jsonify({"ok": False, "message": "Gmail Cleaner sessie verlopen. Log opnieuw in."}), 401
                return redirect(url_for("gmail_login_page"))
        else:
            session["gmail_last_activity"] = now

    if request.endpoint in protected_gmail_endpoints and not session.get("gmail_logged_in"):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "message": "Log eerst in bij Gmail Cleaner."}), 401
        return redirect(url_for("gmail_login_page"))

    return None

@app.route("/login", methods=["GET"])
def login_page():
    return redirect(url_for("home"))

@app.route("/login", methods=["POST"])
def login_submit():
    return redirect(url_for("home"))

@app.route("/setup-code", methods=["POST"])
def setup_code():
    return redirect(url_for("gmail_login_page"))

@app.route("/casa-cara-login", methods=["GET"])
def casa_login_page():
    message = session.pop("casa_login_message", "")
    success = session.pop("casa_login_success", False)
    return render_template_string(CASA_LOGIN_HTML, message=message, success=success, casa_code_exists=casa_users_exist())

@app.route("/casa-cara-login", methods=["POST"])
def casa_login_submit():
    import time
    access_code = (request.form.get("access_code") or "").strip()
    user = find_casa_user_by_pin(access_code)
    if user:
        session["casa_logged_in"] = True
        session["casa_last_activity"] = time.time()
        session["casa_user_pin"] = user.get("pin")
        session["casa_user_name"] = user.get("name")
        session["casa_user_role"] = user.get("role")
        # Compatibility flags for existing Casa Cara builds that still expect dashboard auth
        session["dashboard_logged_in"] = True
        session["is_logged_in"] = True
        session["last_activity"] = time.time()
        return redirect("/casa-cara")
    session["casa_login_message"] = "Onjuiste Casa Cara code."
    session["casa_login_success"] = False
    return redirect(url_for("casa_login_page"))

@app.route("/casa-cara-setup", methods=["POST"])
def casa_setup_code():
    master_password = (request.form.get("master_password") or "").strip()
    admin_name = (request.form.get("admin_name") or "Admin").strip() or "Admin"
    new_access_code = (request.form.get("new_access_code") or "").strip()
    if casa_users_exist():
        session["casa_login_message"] = "Er bestaat al een Casa Cara admin. Nieuwe medewerkers voeg je in de tool toe."
        session["casa_login_success"] = False
        return redirect(url_for("casa_login_page"))
    if master_password != MASTER_PASSWORD:
        session["casa_login_message"] = "Hoofdwachtwoord onjuist."
        session["casa_login_success"] = False
        return redirect(url_for("casa_login_page"))
    if not new_access_code:
        session["casa_login_message"] = "Vul een nieuwe code in."
        session["casa_login_success"] = False
        return redirect(url_for("casa_login_page"))
    save_casa_auth({"users": [{"name": admin_name, "pin": new_access_code, "role": "admin", "active": True}]})
    session["casa_login_message"] = "Casa Cara admin aangemaakt. Je kunt nu inloggen."
    session["casa_login_success"] = True
    return redirect(url_for("casa_login_page"))

@app.route("/casa-cara-logout")
def casa_logout():
    for key in ["casa_logged_in", "casa_last_activity", "casa_user_pin", "casa_user_name", "casa_user_role", "dashboard_logged_in", "is_logged_in", "last_activity"]:
        session.pop(key, None)
    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/restaurant-tool")
def restaurant_tool():
    if session.get("casa_logged_in"):
        return redirect("/casa-cara")
    return redirect(url_for("casa_login_page"))

@app.route("/")
def home():
    ensure_files()
    normalize_bar_data()
    return render_template_string(HOME_HTML)

@app.route("/gmail-login", methods=["GET"])
def gmail_login_page():
    message = session.pop("gmail_login_message", "")
    success = session.pop("gmail_login_success", False)
    return render_template_string(GMAIL_LOGIN_HTML, message=message, success=success, gmail_code_exists=gmail_code_exists())

@app.route("/gmail-login", methods=["POST"])
def gmail_login_submit():
    import time
    access_code = (request.form.get("access_code") or "").strip()
    auth = load_gmail_auth()
    stored = (auth.get("access_code") or "").strip()
    if stored and access_code == stored:
        session["gmail_logged_in"] = True
        session["gmail_last_activity"] = time.time()
        return redirect(url_for("gmail"))
    session["gmail_login_message"] = "Onjuiste Gmail Cleaner code."
    session["gmail_login_success"] = False
    return redirect(url_for("gmail_login_page"))

@app.route("/gmail-setup", methods=["POST"])
def gmail_setup_code():
    master_password = (request.form.get("master_password") or "").strip()
    new_access_code = (request.form.get("new_access_code") or "").strip()
    if master_password != MASTER_PASSWORD:
        session["gmail_login_message"] = "Hoofdwachtwoord onjuist."
        session["gmail_login_success"] = False
        return redirect(url_for("gmail_login_page"))
    if not new_access_code or len(new_access_code) != 4 or not new_access_code.isdigit():
        session["gmail_login_message"] = "Voer een 4-cijferige code in."
        session["gmail_login_success"] = False
        return redirect(url_for("gmail_login_page"))
    save_gmail_auth({"access_code": new_access_code})
    session["gmail_login_message"] = "Nieuwe Gmail Cleaner code opgeslagen."
    session["gmail_login_success"] = True
    return redirect(url_for("gmail_login_page"))

@app.route("/gmail-logout")
def gmail_logout():
    for key in ["gmail_logged_in", "gmail_last_activity"]:
        session.pop(key, None)
    return redirect(url_for("home"))

@app.route("/gmail")
def gmail():
    session["gmail_last_activity"] = time.time()
    return render_template_string(GMAIL_HTML)



@app.route("/api/stats")
def api_stats():
    return jsonify(load_stats())


@app.route("/api/trash")
def api_trash():
    return jsonify(load_json_file(TRASH_FILE, []))


@app.route("/api/downloads")
def api_downloads():
    return jsonify(load_json_file(DOWNLOADS_FILE, []))


@app.route("/api/kept")
def api_kept():
    return jsonify(load_json_file(KEPT_FILE, []))


@app.route("/api/activity")
def api_activity():
    return jsonify(load_json_file(ACTIVITY_FILE, []))


@app.route("/api/pending-trash")
def api_pending_trash():
    return jsonify({"items": load_json_file(PENDING_TRASH_FILE, [])})


@app.route("/api/run-gmail", methods=["POST"])
def run_gmail():
    mode = request.args.get("mode", "full").strip().lower()
    if mode not in {"full", "cleanup", "pdfs"}:
        mode = "full"
    if gmail_process_running():
        return jsonify({"ok": False, "message": "Er draait al een Gmail-check. Wacht tot deze klaar is."}), 409
    if not start_gmail_subprocess([f"--mode={mode}"]):
        return jsonify({"ok": False, "message": "Gmail script niet gevonden op deze omgeving."}), 503
    messages = {
        "full": "Volledige Gmail-check gestart.",
        "cleanup": "Alleen cleanup gestart.",
        "pdfs": "Alleen PDF-downloadcontrole gestart.",
    }
    return jsonify({"ok": True, "message": messages[mode]})


@app.route("/api/approve-trash", methods=["POST"])
def api_approve_trash():
    if gmail_process_running():
        return jsonify({"ok": False, "message": "Er draait al een Gmail-check. Wacht tot deze klaar is."}), 409
    if not start_gmail_subprocess(["--approve-trash"]):
        return jsonify({"ok": False, "message": "Gmail script niet gevonden op deze omgeving."}), 503
    return jsonify({"ok": True, "message": "Goedkeuring verwerkt. Mails gaan nu naar de prullenbak."})


@app.route("/api/reject-trash", methods=["POST"])
def api_reject_trash():
    if gmail_process_running():
        return jsonify({"ok": False, "message": "Er draait al een Gmail-check. Wacht tot deze klaar is."}), 409
    if not start_gmail_subprocess(["--reject-trash"]):
        return jsonify({"ok": False, "message": "Gmail script niet gevonden op deze omgeving."}), 503
    return jsonify({"ok": True, "message": "De wachtrij voor prullenbak is geannuleerd."})


@app.route("/open/<target>")
def open_target(target):
    if IS_RENDER:
        return jsonify({"ok": False, "message": "Bestanden openen werkt alleen lokaal."}), 400

    mapping = {
        "documenten": DOCUMENTEN_MAP,
        "loonstroken": LOONSTROKEN_MAP,
        "fotos": FOTOS_MAP,
        "base": BASE_DIR,
    }
    subprocess.run(["open", str(mapping.get(target, BASE_DIR))], check=False)
    return ("", 204)



if __name__ == "__main__":
    ensure_files()
    normalize_bar_data()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False)
