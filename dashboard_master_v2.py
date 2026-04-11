import json
import os
import sys
import subprocess
import threading
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for

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
AUTH_FILE = DATA_ROOT / "auth.json"
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

def is_logged_in():
    return bool(session.get("is_logged_in"))





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
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Inloggen</title>
<style>
:root{
  --bg:#06101c; --bg2:#0b1220; --text:#eff6ff; --muted:#9fb0c7;
  --line:rgba(159,176,199,.14); --accent:#38bdf8; --danger:#ef4444; --shadow:0 20px 50px rgba(0,0,0,.28);
}
*{box-sizing:border-box}
body{
  margin:0; min-height:100vh; color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif;
  background:
    radial-gradient(circle at 10% 0%, rgba(148,163,184,.08), transparent 24%),
    radial-gradient(circle at 90% 0%, rgba(148,163,184,.05), transparent 22%),
    linear-gradient(180deg, var(--bg), var(--bg2));
  display:flex; align-items:center; justify-content:center;
}
.wrap{width:min(960px,calc(100vw - 28px));display:grid;grid-template-columns:1fr 1fr;gap:18px}
.card{
  background:linear-gradient(180deg, rgba(16,27,48,.88), rgba(12,20,36,.80));
  border:1px solid var(--line); border-radius:30px; padding:26px; box-shadow:var(--shadow);
}
h1,h2{margin:0 0 10px}
p{margin:0;color:var(--muted);line-height:1.6}
.form{margin-top:16px;display:grid;gap:12px}
input{
  width:100%;border:1px solid rgba(201,170,112,.16);background:rgba(8,8,8,.92);color:var(--text);
  border-radius:14px;padding:14px 14px;font-size:15px;outline:none;
}
button{
  border:none;border-radius:14px;padding:14px 16px;font-size:14px;font-weight:800;cursor:pointer;
  background:linear-gradient(180deg,#8ae3ff,#38bdf8);color:#08263a;
}
.msg{margin-top:12px;padding:12px 14px;border-radius:14px;font-size:14px}
.msg.error{background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.22);color:#ffd7d7}
.msg.ok{background:rgba(34,197,94,.12);border:1px solid rgba(34,197,94,.22);color:#d4ffe3}
.logo{width:56px;height:56px;object-fit:contain;border-radius:14px;background:white;padding:8px;margin-bottom:14px}
@media (max-width:800px){.wrap{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <h1>Inloggen</h1>
    <p>Voer je code in om naar het dashboard te gaan.</p>
    {% if message %}
      <div class="msg {{ 'error' if not success else 'ok' }}">{{ message }}</div>
    {% endif %}
    <form class="form" method="post" action="/login">
      <input type="password" name="access_code" placeholder="Jouw code" required>
      <button type="submit">Inloggen</button>
    </form>
  </div>

  <div class="card">
    <h2>Nieuwe code maken</h2>
    <p>Heb je nog geen code? Maak er een aan met het hoofdwachtwoord.</p>
    <form class="form" method="post" action="/setup-code">
      <input type="password" name="master_password" placeholder="Hoofdwachtwoord" required>
      <input type="password" name="new_access_code" placeholder="Nieuwe code" required>
      <button type="submit">Code opslaan</button>
    </form>
    {% if code_exists %}
      <div class="msg ok">Er is al een code ingesteld. Je kunt die altijd overschrijven met het hoofdwachtwoord.</div>
    {% else %}
      <div class="msg ok">Er is nog geen code ingesteld. Maak hier je eerste code aan.</div>
    {% endif %}
  </div>
</div>
</body>
</html>
"""

HOME_HTML = """

<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard</title>
<link rel="icon" type="image/png" href="/static/gmail.png">
<style>
:root{
  --bg:#06101c;
  --bg2:#0b1220;
  --text:#eff6ff;
  --muted:#9fb0c7;
  --line:rgba(159,176,199,.14);
  --accent:#334155;
  --shadow:0 20px 50px rgba(0,0,0,.28);
}
*{box-sizing:border-box}
body{
  margin:0;
  min-height:100vh;
  color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif;
  background:
    radial-gradient(circle at 10% 0%, rgba(148,163,184,.08), transparent 24%),
    radial-gradient(circle at 90% 0%, rgba(148,163,184,.05), transparent 22%),
    radial-gradient(circle at 50% 100%, rgba(148,163,184,.04), transparent 30%),
    linear-gradient(180deg, var(--bg), var(--bg2));
  display:flex;
  align-items:center;
  justify-content:center;
}
.wrap{max-width:1200px;width:100%;padding:36px 20px 44px}
.hero{
  background:linear-gradient(180deg, rgba(15,23,42,.82), rgba(15,23,42,.58));
  border:1px solid var(--line);
  border-radius:34px;
  padding:42px 30px 30px;
  box-shadow:var(--shadow);
  backdrop-filter:blur(16px);
  text-align:center;
}
.eyebrow{
  display:inline-flex;align-items:center;gap:8px;
  font-size:12px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
  color:#bfe9ff;background:rgba(56,189,248,.10);border:1px solid rgba(99,213,255,.18);
  padding:8px 12px;border-radius:999px;margin-bottom:16px;
}
.eyebrow::before{
  content:"";
  width:8px;height:8px;border-radius:999px;background:var(--accent);
  box-shadow:0 0 0 6px rgba(56,189,248,.12);
}
h1{margin:0 0 12px;font-size:82px;letter-spacing:-.05em;line-height:1}
p{margin:0 auto;color:var(--muted);line-height:1.65;max-width:760px;font-size:16px}
.grid{
  margin-top:34px;
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:18px;
}
.card{
  display:block;
  text-decoration:none;
  color:inherit;
  background:linear-gradient(180deg, rgba(22,22,22,.96), rgba(12,12,12,.94));
  border:1px solid var(--line);
  border-radius:30px;
  padding:24px;
  box-shadow:var(--shadow);
  transition:transform .16s ease, border-color .16s ease, box-shadow .16s ease;
  text-align:left;
}
.card:hover{
  transform:translateY(-4px);
  border-color:rgba(99,213,255,.30);
  box-shadow:0 28px 60px rgba(0,0,0,.32);
}
.icon{
  width:62px;
  height:62px;
  border-radius:18px;
  display:flex;
  align-items:center;
  justify-content:center;
  background:white;
  border:1px solid rgba(99,213,255,.18);
  margin-bottom:16px;
  overflow:hidden;
}
.icon img{
  max-width:42px;
  max-height:42px;
  object-fit:contain;
  display:block;
}
.card h2{margin:0 0 10px;font-size:28px;letter-spacing:-.02em}
.card p{font-size:15px;max-width:none;margin:0}
.tag{
  display:inline-block;
  margin-top:16px;
  padding:8px 12px;
  border-radius:999px;
  font-size:12px;
  font-weight:800;
  letter-spacing:.08em;
  text-transform:uppercase;
  background:rgba(255,255,255,.04);
  border:1px solid rgba(159,176,199,.12);
  color:#d7e8fb;
}
@media (max-width:800px){
  h1{font-size:52px}
  .grid{grid-template-columns:1fr}
  .hero{padding:30px 20px}
}
</style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
    <div style="display:flex;justify-content:flex-end;margin-bottom:10px;"><a href="/logout" style="display:inline-flex;align-items:center;gap:8px;text-decoration:none;color:var(--text);padding:10px 14px;border-radius:16px;background:rgba(16,27,48,.88);border:1px solid var(--line)">Uitloggen</a></div>
      <div class="eyebrow">Welkom</div>
      <h1>Welkom</h1>
      <p>Kies welke tool je wilt openen. Zo blijven je Gmail automation en Casa Cara netjes van elkaar gescheiden en overzichtelijk.</p>

      <div class="grid">
        <a class="card" href="/gmail">
          <div class="icon">
            <img src="/static/gmail.png" alt="Gmail logo" onerror="this.style.display='none'; this.parentNode.innerHTML='📧'; this.parentNode.style.fontSize='30px';">
          </div>
          <h2>Gmail Cleaner</h2>
          <p>Je Gmail cleaner met opruimen, PDF-downloads, statistieken, goedkeuringen en geschiedenis.</p>
          <div class="tag">Bestaande tool</div>
        </a>

        <a class="card casa-card" href="/casa-cara">
          <div class="icon">
            <img src="/static/casa.png" alt="Casa Cara logo" onerror="this.style.display='none'; this.parentNode.innerHTML='🍽️'; this.parentNode.style.fontSize='30px';">
          </div>
          <h2>Casa Cara</h2>
          <p>Je restaurant-tool voor koelingen, voorraden en straks een slim bijvuloverzicht voor op je telefoon.</p>
          <div class="tag">Nieuwe tool</div>
        </a>
      </div>
    </div>
  </div>
</body>
</html>

"""

CASA_HTML = """
<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Casa Cara</title>
<link rel="icon" type="image/png" href="/static/casa.png">
<style>
:root{
  --bg:#000000; --bg2:#050505; --text:#f6f1e7; --muted:#b4ab9a;
  --line:rgba(201,170,112,.16); --accent:#d4b06a; --good:#d4b06a; --danger:#b84f4f;
  --shadow:0 20px 50px rgba(0,0,0,.28);
}
*{box-sizing:border-box}
body{
  margin:0; min-height:100vh; color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif;
  background:
    radial-gradient(circle at 10% 0%, rgba(212,176,106,.04), transparent 22%),
    radial-gradient(circle at 90% 0%, rgba(196,153,72,.03), transparent 20%),
    linear-gradient(180deg, var(--bg), var(--bg2));
}
.wrap{max-width:1260px;margin:0 auto;padding:24px 18px 42px}
.topbar{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:16px}
.back{
  display:inline-flex;align-items:center;gap:8px;text-decoration:none;color:var(--text);
  padding:10px 14px;border-radius:16px;background:rgba(18,18,18,.95);border:1px solid var(--line)
}
.hero,.card{
  background:linear-gradient(180deg, rgba(22,22,22,.96), rgba(12,12,12,.94));
  border:1px solid var(--line); border-radius:28px; padding:20px; box-shadow:var(--shadow);
}
.hero h1{margin:0 0 8px;font-size:40px;letter-spacing:-.03em}
.hero p{margin:0;color:var(--muted);line-height:1.6}
.tabs{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0 20px;padding:8px;border-radius:22px;background:rgba(14,14,14,.88);border:1px solid var(--line)}
.tabbtn{
  border:none;border-radius:16px;padding:12px 16px;font-size:14px;font-weight:800;cursor:pointer;
  color:var(--text);background:transparent;
}
.tabbtn.active{background:linear-gradient(180deg,#f3e2bf,#d4b06a);color:#3a2a10}
.tabpanel{display:none}.tabpanel.active{display:block}
.section-title{margin:0 0 12px;font-size:20px}
.muted{color:var(--muted);font-size:14px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.form-row{display:grid;grid-template-columns:1fr 1fr 1fr auto;gap:10px;margin-top:12px}
.form-row.type-row{grid-template-columns:1fr 1fr auto}
.form-row.locations{grid-template-columns:1fr auto}
.form-row.products{grid-template-columns:1.2fr .8fr 1fr auto}
.form-row input,.form-row select{
  width:100%;border:1px solid rgba(201,170,112,.16);background:rgba(8,8,8,.92);color:var(--text);
  border-radius:14px;padding:12px 13px;font-size:14px;outline:none;
}
.btn{
  border:none;border-radius:14px;padding:12px 16px;font-size:14px;font-weight:800;cursor:pointer;
  background:rgba(212,176,106,.16);color:#f5e7c8;border:1px solid rgba(212,176,106,.28);
}
.btn.danger{background:linear-gradient(180deg,#df8a8a,#b84f4f);color:#fff4f4;border-color:rgba(184,79,79,.30)}
.btn.good{background:linear-gradient(180deg,#f3dfb2,#d4b06a);color:#1b1307;border-color:rgba(212,176,106,.28)}
.btn.small{padding:8px 12px;font-size:13px}
.koeling-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.koeling{
  background:rgba(20,20,20,.96);border:1px solid var(--line);border-radius:22px;padding:16px;cursor:pointer;
}
.koeling .title{font-weight:800;margin-bottom:6px}
.koeling .meta{font-size:13px;color:var(--muted);line-height:1.45}
.fill-list,.line-list{display:grid;gap:10px}
.fill-item,.line{
  background:rgba(18,18,18,.95);border:1px solid var(--line);border-radius:20px;padding:14px;
}
.fill-item.urgent{border-color:rgba(239,68,68,.28);background:rgba(239,68,68,.06)}
.line-top,.fill-top{display:flex;justify-content:space-between;gap:12px;align-items:start}
.line .name,.fill-item .title{font-weight:800}
.line .meta,.fill-item .meta{font-size:13px;color:var(--muted);margin-top:5px;line-height:1.45}
.qty{display:flex;align-items:center;gap:8px;margin-top:12px;flex-wrap:wrap}
.qty button{
  min-width:42px;height:38px;border:none;border-radius:12px;cursor:pointer;font-size:18px;font-weight:900;
  background:rgba(212,176,106,.14);color:#f5e7c8;border:1px solid rgba(212,176,106,.28);
}
.qty input{
  max-width:110px;border:1px solid rgba(201,170,112,.16);background:rgba(8,8,8,.92);color:var(--text);
  border-radius:12px;padding:10px 12px;font-size:14px;
}
.pill-list{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.pill{
  display:inline-flex;align-items:center;gap:8px;
  padding:8px 12px;border-radius:999px;background:rgba(20,20,20,.98);border:1px solid var(--line);font-size:13px
}
.empty{padding:16px;border-radius:18px;background:rgba(255,255,255,.03);border:1px dashed var(--line);color:var(--muted)}
.modal-backdrop{position:fixed;inset:0;background:rgba(2,6,23,.76);display:none;align-items:center;justify-content:center;z-index:9999}
.modal-backdrop.active{display:flex}
.modal{width:min(460px,calc(100vw - 24px));background:#0d1628;border:1px solid rgba(159,176,199,.22);border-radius:24px;padding:22px;box-shadow:0 24px 60px rgba(0,0,0,.40)}
.modal h3{margin:0 0 8px;font-size:24px}
.modal p{margin:0;color:var(--muted);line-height:1.6}
.modal .field{margin-top:12px}
.modal .field label{display:block;font-size:13px;color:var(--muted);margin-bottom:6px}
.modal input,.modal select{
  width:100%;border:1px solid rgba(201,170,112,.16);background:rgba(8,8,8,.92);color:var(--text);
  border-radius:14px;padding:12px 13px;font-size:14px;outline:none;
}
.modal-actions{display:flex;gap:10px;justify-content:flex-end;margin-top:18px;flex-wrap:wrap}
.toast-wrap{position:fixed;top:18px;right:18px;z-index:10000;display:grid;gap:10px}
.toast{
  min-width:280px;max-width:380px;background:rgba(9,15,28,.96);border:1px solid rgba(201,170,112,.16);
  color:var(--text);border-radius:18px;padding:14px 16px;box-shadow:0 18px 40px rgba(0,0,0,.32)
}
.toast .title{font-weight:900;margin-bottom:4px}
.toast.success{border-color:rgba(34,197,94,.35)}
.toast.info{border-color:rgba(56,189,248,.35)}
@media (max-width:980px){
  .grid,.form-row,.koeling-grid{grid-template-columns:1fr}
  .form-row.products,.form-row.type-row{grid-template-columns:1fr}
}
@media (max-width:640px){
  .wrap{padding:16px 12px 28px}
  .hero,.card{padding:16px}
  .hero h1{font-size:32px}
  .tabs{gap:8px;padding:6px}
  .tabbtn{width:100%;text-align:center}
  .line-top,.fill-top{flex-direction:column;align-items:stretch}
  .qty{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));}
  .qty input{grid-column:1 / -1;max-width:none}
  .btn{width:100%}
  .pill{width:100%;justify-content:space-between}
}
</style>
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <div style="display:flex;gap:10px;flex-wrap:wrap;"><a class="back" href="/">← Terug naar home</a><a class="back" href="/logout">Uitloggen</a></div>
  </div>

  <div class="hero">
    <div style="display:flex;align-items:center;gap:14px;justify-content:center;margin-bottom:8px;"><img src="/static/casa.png" alt="Casa Cara" onerror="this.style.display='none'" style="width:54px;height:54px;object-fit:contain;border-radius:14px;background:rgba(255,255,255,.04);padding:6px;"><h1 style="margin:0;">Casa Cara</h1></div>
    <p>Casa Cara in eigen stijl, met warme kleuren en dezelfde slimme workflow.</p>
  </div>

  <div class="tabs">
    <button class="tabbtn active" onclick="showTab('algemeen', this)">Algemeen</button>
    <button class="tabbtn" onclick="showTab('keuken', this)">Keuken</button>
    <button class="tabbtn" onclick="showTab('bar', this)">Bar</button>
  </div>

  <div id="tab-algemeen" class="tabpanel active">
    <div class="grid">
      <div class="card">
        <h2 class="section-title">Fooienpot</h2>
        <div class="muted">Houd voor jezelf bij hoeveel fooi je hebt opgespaard.</div>
        <div style="font-size:42px;font-weight:900;margin:14px 0;" id="fooiTotaal">€ 0,00</div>
        <div class="form-row" style="grid-template-columns:1fr auto auto;">
          <input id="fooiBedrag" type="number" step="0.01" placeholder="Bedrag">
          <button class="btn good" onclick="adjustTips('add')">Toevoegen</button>
          <button class="btn danger" onclick="adjustTips('subtract')">Afhalen</button>
        </div>
      </div>

      <div class="card">
        <h2 class="section-title">Diensten</h2>
        <div class="muted">Datum wordt automatisch als dag weergegeven in je overzicht.</div>
        <div id="dienstenList" class="line-list" style="margin-top:12px;"></div>
        <div class="form-row">
          <input id="dienstDatum" type="date">
          <input id="dienstTijd" placeholder="Tijd, bijv. 12:00 - 21:00">
          <input id="dienstNotitie" placeholder="Notitie">
          <button type="button" class="btn" onclick="addDienst()">Toevoegen</button>
        </div>
      </div>
    </div>
  </div>

  <div id="tab-keuken" class="tabpanel">
    <div class="card">
      <h2 class="section-title">Keuken</h2>
      <div class="empty">Deze pagina bewaren we nog even voor later.</div>
    </div>
  </div>

  <div id="tab-bar" class="tabpanel">
    <div id="barHome">
      <div class="grid">
        <div class="card">
          <h2 class="section-title">Koelingen</h2>
          <div class="muted">Klik op een koeling om producten te bekijken en aan te passen.</div>
          <div id="koelingGrid" class="koeling-grid" style="margin-top:12px;"></div>
          <div class="form-row locations">
            <input id="newCoolingName" placeholder="Nieuwe koeling naam">
            <button type="button" class="btn" onclick="addCooling()">Koeling toevoegen</button>
          </div>
        </div>

        <div class="card">
          <h2 class="section-title">Bijvuloverzicht</h2>
          <div class="muted">Gesorteerd op locatie zodat je minder hoeft te lopen.</div>
          <div id="fillSummaryCard" class="line-list" style="margin-top:12px;"></div>
          <div style="margin-top:12px;">
            <button id="fillOverviewBtn" class="btn good" onclick="openFillOverview()">Naar bijvuloverzicht</button>
          </div>
        </div>
      </div>

      <div class="grid" style="margin-top:18px;">

        <div class="card">
          <h2 class="section-title">Locaties</h2>
          <div class="muted">Beheer hier de locaties die je koppelt aan productsoorten.</div>
          <div id="locationsList" class="pill-list"></div>
          <div class="form-row locations">
            <input id="newLocationName" placeholder="Nieuwe locatie">
            <button class="btn" onclick="addLocation()">Locatie toevoegen</button>
          </div>
        </div>
        <div class="card">
          <h2 class="section-title">Productsoorten</h2>
          <div class="muted">Elke productsoort heeft nu een vaste locatie. Nieuwe producten nemen die automatisch over.</div>
          <div id="typesList" class="pill-list"></div>
          <div class="form-row type-row">
            <input id="newTypeName" placeholder="Nieuwe productsoort">
            <select id="newTypeLocation"></select>
            <button type="button" class="btn" onclick="addProductType()">Toevoegen</button>
          </div>
        </div>

        <div class="card">
          <h2 class="section-title">Op / niet op voorraad</h2>
          <div class="muted">Items die je niet kon bijvullen blijven hier zichtbaar totdat ze weer beschikbaar zijn.</div>
          <div id="opList" class="line-list" style="margin-top:12px;"></div>
        </div>
      </div>

      <div class="card" style="margin-top:18px;">
        <h2 class="section-title">Bar overzicht</h2>
        <div class="muted">Snel overzicht van koelingen, producten, open bijvulitems en producten die op zijn.</div>
        <div id="barSummary" class="line-list" style="margin-top:12px;"></div>
      </div>
    </div>

    <div id="fillOverview" style="display:none;">
      <div class="card">
        <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;">
          <div>
            <h2 class="section-title">Bijvuloverzicht</h2>
            <div class="muted">Gesorteerd op locatie zodat je sneller kunt lopen en overzicht houdt.</div>
          </div>
          <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;">
            <select class="styled-select" id="fillSortMode" class="styled-select" onchange="renderFillOverviewOnly()" style="min-width:180px;">
              <option value="locatie">Sorteren op locatie</option>
              <option value="soort">Sorteren op productsoort</option>
            </select>
            <button class="btn" onclick="backToBarHomeFromFill()">← Terug</button>
            <button class="btn good" onclick="markAllFilled()">Alles bijgevuld 🥳</button>
          </div>
        </div>
        <div id="fillList" class="fill-list" style="margin-top:16px;"></div>
      </div>
    </div>

    <div id="coolingDetail" style="display:none;">
      <div class="card">
        <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;">
          <div>
            <h2 class="section-title" id="detailTitle">Koeling</h2>
            <div class="muted">Nieuw product toevoegen staat bovenaan. Vul hier direct in tot welk aantal je wilt aanvullen.</div>
          </div>
          <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;">
            <select class="styled-select" id="coolingSortMode" class="styled-select" onchange="renderCoolingDetail()" style="min-width:220px;">
              <option value="soort">Sorteren op productsoort</option>
              <option value="locatie">Sorteren op locatie</option>
            </select>
            <button class="btn" onclick="backToBarHome()">← Terug</button>
            <button class="btn danger" onclick="deleteCurrentCooling()">Koeling verwijderen</button>
          </div>
        </div>

        <h3 style="margin:18px 0 8px;">Nieuw product toevoegen</h3>
        <div class="form-row products">
          <input id="newProductName" placeholder="Productnaam">
          <input id="newProductMinimum" type="number" placeholder="Aanvullen tot">
          <select id="newProductType"></select>
          <button type="button" class="btn" onclick="addProduct()">Toevoegen</button>
        </div>

        <div id="productList" class="line-list" style="margin-top:16px;"></div>
      </div>
    </div>
  </div>
</div>

<div id="confirmBackdrop" class="modal-backdrop">
  <div class="modal">
    <h3>Weet je het zeker?</h3>
    <p id="confirmText">Deze actie kan niet ongedaan worden gemaakt.</p>
    <div class="modal-actions">
      <button class="btn" onclick="closeConfirm()">Annuleren</button>
      <button class="btn danger" onclick="runConfirm()">Verwijderen</button>
    </div>
  </div>
</div>

<div id="editBackdrop" class="modal-backdrop">
  <div class="modal">
    <h3 id="editTitle">Aanpassen</h3>
    <div id="editBody"></div>
    <div class="modal-actions">
      <button class="btn" onclick="closeEdit()">Annuleren</button>
      <button class="btn good" onclick="runEditSave()">Opslaan</button>
    </div>
  </div>
</div>

<div id="productBackdrop" class="modal-backdrop">
  <div class="modal">
    <h3 id="productModalTitle">Productinfo</h3>
    <div id="productModalBody"></div>
    <div class="modal-actions">
      <button class="btn" onclick="closeProductModal()">Sluiten</button>
    </div>
  </div>
</div>

<div id="toastWrap" class="toast-wrap"></div>

<script>
let generalData = null;
let barData = null;
let productTypesData = [];
let locationsData = [];
let opData = [];
let selectedCoolingId = null;
let confirmAction = null;
let editSaveAction = null;
let activeProductModal = null;

const esc = v => (v ?? '').toString().replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');

function showToast(title, message, type='info'){
  const wrap = document.getElementById('toastWrap');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<div class="title">${esc(title)}</div><div>${esc(message)}</div>`;
  wrap.appendChild(el);
  setTimeout(() => { el.style.opacity='0'; setTimeout(()=>el.remove(), 220); }, 2800);
}

function showTab(name, btn){
  document.querySelectorAll('.tabpanel').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tabbtn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  btn.classList.add('active');
}

function openConfirm(text){
  document.getElementById('confirmText').textContent = text;
  document.getElementById('confirmBackdrop').classList.add('active');
}
function closeConfirm(){
  document.getElementById('confirmBackdrop').classList.remove('active');
  confirmAction = null;
}
function runConfirm(){
  if(confirmAction){ confirmAction(); }
  closeConfirm();
}
function openEdit(title, html, onSave){
  document.getElementById('editTitle').textContent = title;
  document.getElementById('editBody').innerHTML = html;
  editSaveAction = onSave;
  document.getElementById('editBackdrop').classList.add('active');
}
function closeEdit(){
  document.getElementById('editBackdrop').classList.remove('active');
  editSaveAction = null;
}
function runEditSave(){
  if(editSaveAction){ editSaveAction(); }
}

function openProductModal(coolingId, productId){
  const cooling = (barData.koelingen || []).find(k => k.id === coolingId);
  const product = (cooling?.producten || []).find(p => p.id === productId);
  if(!product) return;

  const locatie = productTypesData.find(t => t.naam === (product.soort || 'Overig'))?.locatie || '-';
  document.getElementById('productModalTitle').textContent = product.naam;
  document.getElementById('productModalBody').innerHTML = `
    <div class="field"><label>Productsoort</label><div class="muted">${esc(product.soort || 'Overig')}</div></div>
    <div class="field"><label>Locatie</label><div class="muted">${esc(locatie)}</div></div>
    <div class="field"><label>Aanvullen tot</label><div class="muted">${esc(product.minimum)}</div></div>
    <div class="field"><label>Moet bijgevuld worden</label><div class="muted">${esc(product.voorraad || 0)}</div></div>
  `;
  document.getElementById('productBackdrop').classList.add('active');
}
function closeProductModal(){
  document.getElementById('productBackdrop').classList.remove('active');
  activeProductModal = null;
}


function confirmDeleteDienst(id){
  confirmAction = () => deleteDienst(id);
  openConfirm('Weet je zeker dat je deze dienst wilt verwijderen?');
}

async function loadAll(){
  await Promise.all([loadGeneral(), loadBar(), loadProductTypes(), loadLocations(), loadOpItems()]);
  renderGeneral();
  renderBarHome();
  if(selectedCoolingId){ renderCoolingDetail(); }
}

async function loadGeneral(){
  const res = await fetch('/api/general');
  generalData = await res.json();
}

async function loadBar(){
  const res = await fetch('/api/bar');
  barData = await res.json();
}

async function loadProductTypes(){
  const res = await fetch('/api/product-types');
  productTypesData = await res.json();
}
async function loadLocations(){
  const res = await fetch('/api/locations');
  locationsData = await res.json();
}
async function loadOpItems(){
  const res = await fetch('/api/op-items');
  opData = await res.json();
}

function renderGeneral(){
  document.getElementById('fooiTotaal').textContent = new Intl.NumberFormat('nl-NL', {style:'currency', currency:'EUR'}).format(Number(generalData.fooienpot || 0));
  const list = document.getElementById('dienstenList');
  list.innerHTML = '';
  const diensten = generalData.diensten || [];
  if(!diensten.length){
    list.innerHTML = '<div class="empty">Nog geen diensten toegevoegd.</div>';
  } else {
    diensten.forEach(item => {
      const el = document.createElement('div');
      el.className = 'line';
      el.innerHTML = `
        <div class="line-top">
          <div>
            <div class="name">${esc(item.day_label || item.date)}</div>
            <div class="meta">${esc(item.time || '-')}<br>${esc(item.note || '')}</div>
          </div>
          <button class="btn danger small" onclick="confirmDeleteDienst('${item.id}')">Verwijderen</button>
        </div>
      `;
      list.appendChild(el);
    });
  }
}

async function adjustTips(mode){
  const input = document.getElementById('fooiBedrag');
  const amount = Number(input.value || 0);
  if(!amount){ showToast('Fooienpot', 'Vul eerst een bedrag in.'); return; }
  const res = await fetch('/api/tips', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({mode, amount})
  });
  generalData = await res.json();
  input.value = '';
  renderGeneral();
  showToast('Diensten', 'Dienst verwijderd.', 'success');
}

async function addDienst(){
  const date = document.getElementById('dienstDatum').value;
  const time = document.getElementById('dienstTijd').value.trim();
  const note = document.getElementById('dienstNotitie').value.trim();
  if(!date || !time){ showToast('Diensten', 'Vul een datum en tijd in.'); return; }
  const res = await fetch('/api/dienst', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({date, time, note})
  });
  generalData = await res.json();
  document.getElementById('dienstDatum').value = '';
  document.getElementById('dienstTijd').value = '';
  document.getElementById('dienstNotitie').value = '';
  renderGeneral();
}

async function deleteDienst(id){
  const res = await fetch('/api/dienst-delete', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({id})
  });
  generalData = await res.json();
  renderGeneral();
}

function renderBarHome(){
  const koelingen = barData.koelingen || [];
  const grid = document.getElementById('koelingGrid');
  grid.innerHTML = '';
  if(!koelingen.length){
    grid.innerHTML = '<div class="empty">Nog geen koelingen toegevoegd.</div>';
  } else {
    koelingen.forEach(cooling => {
      const low = cooling.producten.filter(p => Number(p.voorraad) < Number(p.minimum)).length;
      const el = document.createElement('div');
      el.className = 'koeling';
      el.onclick = () => openCooling(cooling.id);
      el.innerHTML = `<div class="title">${esc(cooling.naam)}</div><div class="meta">${cooling.producten.length} producten<br>${low} item(s) onder minimum</div>`;
      grid.appendChild(el);
    });
  }
  renderLocations();
  renderProductTypes();
  renderFillSummary();
  renderOpList();
  renderBarSummary();
}

function renderFillOverviewOnly(){
  const fillItems = barData.fill_items || [];
  const fillList = document.getElementById('fillList');
  const mode = document.getElementById('fillSortMode')?.value || 'locatie';
  fillList.innerHTML = '';

  if(!fillItems.length){
    fillList.innerHTML = '<div class="empty">Alles ziet er goed uit. Er hoeft nu niets bijgevuld te worden.</div>';
    return;
  }

  groupedItems(fillItems, mode).forEach(([groupName, items]) => {
    const header = document.createElement('div');
    header.className = 'line';
    header.innerHTML = `<div class="name">${esc(mode === 'soort' ? 'Productsoort' : 'Locatie')}: ${esc(groupName)}</div><div class="meta">${items.length} item(s)</div>`;
    fillList.appendChild(header);

    items.forEach(item => {
      const urgent = Number(item.voorraad) === 0 || Number(item.voorraad) < Math.ceil(Number(item.minimum) / 2);
      const el = document.createElement('div');
      el.className = 'fill-item' + (urgent ? ' urgent' : '');
      el.innerHTML = `
        <div class="fill-top">
          <div>
            <div class="title">${esc(item.product)}</div>
            <div class="meta">
              Locatie: ${esc(item.locatie)} · Soort: ${esc(item.soort)} · ${esc(item.koeling)}<br>
              Aanvullen tot: ${item.minimum}<br>
              <strong style="font-size:18px;color:#f5deb0;">Moet bijgevuld worden: ${item.bijvullen}</strong>
            </div>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <button class="btn small good" onclick="markFilled('${item.koeling_id}', '${item.product_id}')">Gepakt</button>
            <button class="btn small danger" onclick="markOutOfStock('${item.koeling_id}', '${item.product_id}')">Op</button>
          </div>
        </div>
      `;
      fillList.appendChild(el);
    });
  });
}

function renderProductTypes(){
  const list = document.getElementById('typesList');
  const select = document.getElementById('newProductType');
  const typeLocationSelect = document.getElementById('newTypeLocation');
  list.innerHTML = '';
  select.innerHTML = '';
  typeLocationSelect.innerHTML = '';
  if(!productTypesData.length){
    list.innerHTML = '<div class="empty">Nog geen productsoorten toegevoegd.</div>';
  } else {
    productTypesData.forEach(type => {
      const pill = document.createElement('div');
      pill.className = 'pill';
      pill.innerHTML = `${esc(type.naam)} · ${esc(type.locatie)} <button class="btn small" onclick="renameProductType('${type.naam.replaceAll("'", "\\'")}')">Wijzig</button> <button class="btn danger small" onclick="deleteProductType('${type.naam.replaceAll("'", "\\'")}')">×</button>`;
      list.appendChild(pill);

      const opt = document.createElement('option');
      opt.value = type.naam;
      opt.textContent = `${type.naam} · ${type.locatie}`;
      select.appendChild(opt);
    });
  }

  if(!locationsData.length){
    const opt = document.createElement('option');
    opt.value = '-';
    opt.textContent = '-';
    typeLocationSelect.appendChild(opt);
  } else {
    locationsData.forEach(loc => {
      const opt = document.createElement('option');
      opt.value = loc;
      opt.textContent = loc;
      typeLocationSelect.appendChild(opt);
    });
  }
}



function groupedItems(items, mode){
  const map = {};
  items.forEach(item => {
    let key = mode === 'soort' ? (item.soort || 'Overig') : (item.locatie || '-');
    if(!map[key]) map[key] = [];
    map[key].push(item);
  });
  return Object.keys(map).sort((a,b)=>a.localeCompare(b, 'nl')).map(key => [key, map[key]]);
}

function renderFillSummary(){
  const target = document.getElementById('fillSummaryCard');
  const btn = document.getElementById('fillOverviewBtn');
  if(!target || !btn) return;
  const openItems = (barData.fill_items || []).length;

  if(openItems === 0){
    target.innerHTML = `
      <div class="line">
        <div class="name">Alles is bijgevuld</div>
        <div class="meta">Er zijn nu geen open bijvulitems. Je hoeft het overzicht niet te openen.</div>
      </div>
    `;
    btn.disabled = true;
    btn.style.opacity = '0.55';
    btn.style.cursor = 'not-allowed';
  } else {
    target.innerHTML = `
      <div class="line">
        <div class="name">${openItems} open bijvulitem(s)</div>
        <div class="meta">Er moet nog bijgevuld worden. Open het overzicht voor de volledige lijst, gesorteerd op locatie of productsoort.</div>
      </div>
    `;
    btn.disabled = false;
    btn.style.opacity = '1';
    btn.style.cursor = 'pointer';
  }
}

function renderLocations(){
  const list = document.getElementById('locationsList');
  const typeLocationSelect = document.getElementById('newTypeLocation');
  if(!list || !typeLocationSelect) return;
  list.innerHTML = '';
  typeLocationSelect.innerHTML = '';

  if(!locationsData.length){
    list.innerHTML = '<div class="empty">Nog geen locaties toegevoegd.</div>';
    const opt = document.createElement('option');
    opt.value = '-';
    opt.textContent = '-';
    typeLocationSelect.appendChild(opt);
    return;
  }

  locationsData.forEach(loc => {
    const pill = document.createElement('div');
    pill.className = 'pill';
    pill.innerHTML = `${esc(loc)} <button class="btn small" onclick="renameLocation('${loc.replaceAll("'", "\\'")}')">Wijzig</button> <button class="btn danger small" onclick="deleteLocation('${loc.replaceAll("'", "\\'")}')">×</button>`;
    list.appendChild(pill);

    const opt = document.createElement('option');
    opt.value = loc;
    opt.textContent = loc;
    typeLocationSelect.appendChild(opt);
  });
}

function renderOpList(){
  const target = document.getElementById('opList');
  if(!target) return;
  target.innerHTML = '';
  if(!opData.length){
    target.innerHTML = '<div class="empty">Er staan nu geen producten op de op-lijst.</div>';
    return;
  }
  opData.forEach(item => {
    const el = document.createElement('div');
    el.className = 'line';
    el.innerHTML = `
      <div class="line-top">
        <div>
          <div class="name">${esc(item.product)} · ${esc(item.koeling)}</div>
          <div class="meta">Soort: ${esc(item.soort)} · Locatie: ${esc(item.locatie)}</div>
        </div>
        <button class="btn small good" onclick="markAvailable('${item.koeling_id}', '${item.product_id}')">Weer beschikbaar</button>
      </div>
    `;
    target.appendChild(el);
  });
}

function renderBarSummary(){
  const target = document.getElementById('barSummary');
  const koelingen = barData.koelingen || [];
  const products = koelingen.reduce((sum, k) => sum + k.producten.length, 0);
  const low = (barData.fill_items || []).length;
  target.innerHTML = `<div class="line"><div class="name">${koelingen.length} koeling(en)</div><div class="meta">${products} producten totaal<br>${low} open item(s) in je bijvullijst<br>${opData.length} item(s) op de op-lijst<br>${productTypesData.length} productsoort(en)</div></div>`;
}

async function addCooling(){
  const name = document.getElementById('newCoolingName').value.trim();
  if(!name){ showToast('Bar', 'Vul eerst een naam voor de koeling in.'); return; }
  const res = await fetch('/api/cooling', {
    method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name})
  });
  barData = await res.json();
  document.getElementById('newCoolingName').value = '';
  renderBarHome();
  showToast('Bar', 'Koeling toegevoegd.', 'success');
}

function openCooling(id){
  selectedCoolingId = id;
  document.getElementById('barHome').style.display = 'none';
  document.getElementById('fillOverview').style.display = 'none';
  document.getElementById('coolingDetail').style.display = 'block';
  renderCoolingDetail();
}
function openFillOverview(){
  document.getElementById('barHome').style.display = 'none';
  document.getElementById('coolingDetail').style.display = 'none';
  document.getElementById('fillOverview').style.display = 'block';
  renderFillOverviewOnly();
}
function backToBarHome(){
  document.getElementById('barHome').style.display = 'block';
  document.getElementById('coolingDetail').style.display = 'none';
  document.getElementById('fillOverview').style.display = 'none';
}
function backToBarHomeFromFill(){
  document.getElementById('barHome').style.display = 'block';
  document.getElementById('coolingDetail').style.display = 'none';
  document.getElementById('fillOverview').style.display = 'none';
}

function renderCoolingDetail(){
  const cooling = (barData.koelingen || []).find(k => k.id === selectedCoolingId);
  const title = document.getElementById('detailTitle');
  const list = document.getElementById('productList');
  const sortMode = document.getElementById('coolingSortMode')?.value || 'soort';

  if(!cooling){
    title.textContent = 'Koeling niet gevonden';
    list.innerHTML = '<div class="empty">Deze koeling bestaat niet meer.</div>';
    return;
  }

  title.textContent = cooling.naam;
  list.innerHTML = '';

  if(!cooling.producten.length){
    list.innerHTML = '<div class="empty">Nog geen producten in deze koeling.</div>';
    return;
  }

  const normalized = cooling.producten.map(product => {
    const locatie = productTypesData.find(t => t.naam === (product.soort || 'Overig'))?.locatie || '-';
    return {...product, locatie};
  });

  groupedItems(normalized, sortMode).forEach(([groupName, products]) => {
    const header = document.createElement('div');
    header.className = 'line';
    header.innerHTML = `<div class="name">${esc(sortMode === 'soort' ? 'Productsoort' : 'Locatie')}: ${esc(groupName)}</div><div class="meta">${products.length} product(en)</div>`;
    list.appendChild(header);

    products.forEach(product => {
      const refillAmount = Number(product.voorraad || 0);
      const el = document.createElement('div');
      el.className = 'line';
      el.innerHTML = `
        <div class="line-top">
          <div>
            <div class="name">${esc(product.naam)}</div>
            <div class="meta">Soort: ${esc(product.soort || 'Overig')} · Locatie: ${esc(product.locatie)} · Aanvullen tot: ${product.minimum}</div>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <button class="btn small" onclick="openProductModal('${selectedCoolingId}', '${product.id}')">Bekijk productinfo</button>
            <button class="btn small" onclick="editProduct('${product.id}')">Aanpassen</button>
            <button class="btn danger small" onclick="confirmDeleteProduct('${product.id}')">Verwijderen</button>
          </div>
        </div>
        <div class="qty">
          <button onclick="adjustProduct('${product.id}', -5)">-5</button>
          <button onclick="adjustProduct('${product.id}', -1)">−</button>
          <input type="number" value="${refillAmount}" oninput="queueProductRefillSave('${product.id}', this.value)" onchange="setProductRefill('${product.id}', this.value)" onkeydown="if(event.key==='Enter'){ event.preventDefault(); setProductRefill('${product.id}', this.value); this.blur(); }">
          <button onclick="adjustProduct('${product.id}', 1)">+</button>
          <button onclick="adjustProduct('${product.id}', 5)">+5</button>
        </div>
      `;
      list.appendChild(el);
    });
  });
}

async function addProduct(){
  const name = document.getElementById('newProductName').value.trim();
  const minimum = Number(document.getElementById('newProductMinimum').value || 0);
  const soort = document.getElementById('newProductType').value;

  if(!name){
    showToast('Bar', 'Vul eerst een productnaam in.');
    return;
  }

  try{
    const res = await fetch('/api/product-add', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({cooling_id: selectedCoolingId, name, minimum, soort})
    });

    const data = await res.json();
    barData = data;

    document.getElementById('newProductName').value = '';
    document.getElementById('newProductMinimum').value = '';
    if(document.getElementById('newProductType').options.length){
      document.getElementById('newProductType').selectedIndex = 0;
    }

    renderBarHome();
    renderCoolingDetail();
    showToast('Bar', 'Product toegevoegd.', 'success');
  } catch(e){
    showToast('Bar', 'Toevoegen lukte niet.', 'info');
  }
}

let productRefillTimers = {};

async function adjustProduct(productId, delta){
  const cooling = (barData.koelingen || []).find(k => k.id === selectedCoolingId);
  const product = (cooling?.producten || []).find(p => p.id === productId);
  const currentRefill = Number(product?.voorraad || 0);
  const refill = Math.max(currentRefill + delta, 0);
  await saveProductRefill(productId, refill, false);
}

function queueProductRefillSave(productId, value){
  if(productRefillTimers[productId]){
    clearTimeout(productRefillTimers[productId]);
  }
  productRefillTimers[productId] = setTimeout(() => {
    setProductRefill(productId, value);
  }, 300);
}

async function setProductRefill(productId, value){
  const refill = Math.max(Number(value || 0), 0);
  await saveProductRefill(productId, refill, true);
}

async function saveProductRefill(productId, refill, showMessage){
  try{
    const res = await fetch('/api/product-set-refill', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({cooling_id: selectedCoolingId, product_id: productId, refill})
    });

    const data = await res.json();
    barData = data;
    renderBarHome();
    renderCoolingDetail();

    if(showMessage){
      showToast('Bar', 'Aantal aangepast.', 'success');
    }
  } catch(e){
    showToast('Bar', 'Aantal aanpassen lukte niet.', 'info');
  }
}

function editProduct(productId){
  const cooling = (barData.koelingen || []).find(k => k.id === selectedCoolingId);
  const product = (cooling.producten || []).find(p => p.id === productId);
  if(!product) return;

  const typeOptions = productTypesData.map(t => `<option value="${esc(t.naam)}" ${t.naam === (product.soort || 'Overig') ? 'selected' : ''}>${esc(t.naam)} · ${esc(t.locatie)}</option>`).join('');
  openEdit('Product aanpassen', `
    <div class="field"><label>Naam</label><input id="editProductName" value="${esc(product.naam)}"></div>
    <div class="field"><label>Aanvullen tot</label><input id="editProductMinimum" type="number" value="${product.minimum}"></div>
    <div class="field"><label>Productsoort</label><select id="editProductType">${typeOptions}</select></div>
  `, async () => {
    const res = await fetch('/api/product-edit', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        cooling_id: selectedCoolingId,
        product_id: productId,
        name: document.getElementById('editProductName').value.trim(),
        minimum: Number(document.getElementById('editProductMinimum').value || 0),
        soort: document.getElementById('editProductType').value
      })
    });
    barData = await res.json();
    renderBarHome();
    renderCoolingDetail();
    closeEdit();
    showToast('Bar', 'Product aangepast.', 'success');
  });
}

async function doDeleteProduct(productId){
  const res = await fetch('/api/product-delete', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({cooling_id: selectedCoolingId, product_id: productId})
  });
  barData = await res.json();
  renderBarHome();
  renderCoolingDetail();
  showToast('Bar', 'Product verwijderd.', 'success');
}
function confirmDeleteProduct(productId){
  confirmAction = () => doDeleteProduct(productId);
  openConfirm('Weet je zeker dat je dit product wilt verwijderen?');
}

async function doDeleteCurrentCooling(){
  const res = await fetch('/api/cooling-delete', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({cooling_id: selectedCoolingId})
  });
  barData = await res.json();
  selectedCoolingId = null;
  backToBarHome();
  renderBarHome();
  showToast('Bar', 'Koeling verwijderd.', 'success');
}
async function deleteCurrentCooling(){
  confirmAction = () => doDeleteCurrentCooling();
  openConfirm('Weet je zeker dat je deze koeling wilt verwijderen?');
}

async function markFilled(coolingId, productId){
  const res = await fetch('/api/fill-mark-product', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({cooling_id: coolingId, product_id: productId})
  });
  barData = await res.json();
  await loadOpItems();
  renderBarHome();
  renderFillOverviewOnly();
  if(selectedCoolingId){ renderCoolingDetail(); }
}

async function markOutOfStock(coolingId, productId){
  const res = await fetch('/api/fill-mark-out', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({cooling_id: coolingId, product_id: productId})
  });
  const data = await res.json();
  barData = data.bar;
  opData = data.op_items;
  renderBarHome();
  renderFillOverviewOnly();
  if(selectedCoolingId){ renderCoolingDetail(); }
  showToast('Bijvullen', 'Toegevoegd aan op-lijst.', 'info');
}

async function markAvailable(coolingId, productId){
  const res = await fetch('/api/op-mark-available', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({cooling_id: coolingId, product_id: productId})
  });
  const data = await res.json();
  barData = data.bar;
  opData = data.op_items;
  renderBarHome();
  if(document.getElementById('fillOverview').style.display === 'block'){ renderFillOverviewOnly(); }
  if(selectedCoolingId){ renderCoolingDetail(); }
}

async function markAllFilled(){
  const res = await fetch('/api/fill-mark-all', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({})
  });
  barData = await res.json();
  await loadOpItems();
  renderBarHome();
  renderFillOverviewOnly();
  if(selectedCoolingId){ renderCoolingDetail(); }
  showToast('Bijvullen', 'Alles is bijgevuld.', 'success');
}

async function addLocation(){
  const name = document.getElementById('newLocationName').value.trim();
  if(!name){ showToast('Locaties', 'Vul eerst een locatie in.'); return; }
  const res = await fetch('/api/location-add', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name})
  });
  const data = await res.json();
  locationsData = data.locations;
  productTypesData = data.types;
  document.getElementById('newLocationName').value = '';
  renderLocations();
  renderProductTypes();
  showToast('Locaties', 'Locatie toegevoegd.', 'success');
}
async function doDeleteLocation(name){
  const res = await fetch('/api/location-delete', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name})
  });
  const data = await res.json();
  locationsData = data.locations;
  productTypesData = data.types;
  renderLocations();
  renderProductTypes();
  renderBarHome();
  if(selectedCoolingId){ renderCoolingDetail(); }
  showToast('Productsoorten', 'Productsoort verwijderd.', 'success');
}
function deleteLocation(name){
  confirmAction = () => doDeleteLocation(name);
  openConfirm('Weet je zeker dat je deze locatie wilt verwijderen?');
}
function renameLocation(oldName){
  openEdit('Locatie aanpassen', `
    <div class="field"><label>Nieuwe naam voor locatie</label><input id="editLocationName" value="${esc(oldName)}"></div>
  `, async () => {
    const newName = document.getElementById('editLocationName').value.trim();
    if(!newName || newName === oldName){
      closeEdit();
      return;
    }
    const res = await fetch('/api/location-rename', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({old_name: oldName, new_name: newName})
    });
    const data = await res.json();
    locationsData = data.locations;
    productTypesData = data.types;
    renderLocations();
    renderProductTypes();
    renderBarHome();
    if(selectedCoolingId){ renderCoolingDetail(); }
    closeEdit();
    showToast('Locaties', 'Locatie aangepast.', 'success');
  });
}

async function addProductType(){
  const name = document.getElementById('newTypeName').value.trim();
  const locatie = document.getElementById('newTypeLocation').value.trim();
  if(!name){ showToast('Productsoorten', 'Vul eerst een productsoort in.'); return; }
  const res = await fetch('/api/product-type-add', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name, locatie})
  });
  productTypesData = await res.json();
  document.getElementById('newTypeName').value = '';
  document.getElementById('newTypeLocation').selectedIndex = 0;
  renderLocations();
  renderProductTypes();
  renderFillSummary();
  renderOpList();
  renderBarSummary();
}
async function doDeleteProductType(name){
  const res = await fetch('/api/product-type-delete', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name})
  });
  const data = await res.json();
  productTypesData = data.types;
  barData = data.bar;
  renderProductTypes();
  renderBarHome();
  if(selectedCoolingId){ renderCoolingDetail(); }
}
async function deleteProductType(name){
  confirmAction = () => doDeleteProductType(name);
  openConfirm('Weet je zeker dat je deze productsoort wilt verwijderen?');
}
function renameProductType(oldName){
  const existing = productTypesData.find(t => t.naam === oldName);
  const locationOptions = locationsData.map(loc => `<option value="${esc(loc)}" ${loc === (existing?.locatie || '-') ? 'selected' : ''}>${esc(loc)}</option>`).join('');
  openEdit('Productsoort aanpassen', `
    <div class="field"><label>Naam</label><input id="editTypeName" value="${esc(oldName)}"></div>
    <div class="field"><label>Vaste locatie</label><select id="editTypeLocation">${locationOptions}</select></div>
  `, async () => {
    const res = await fetch('/api/product-type-rename', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        old_name: oldName,
        new_name: document.getElementById('editTypeName').value.trim(),
        new_location: document.getElementById('editTypeLocation').value
      })
    });
    const data = await res.json();
    productTypesData = data.types;
    barData = data.bar;
    renderProductTypes();
    renderBarHome();
    if(selectedCoolingId){ renderCoolingDetail(); }
    closeEdit();
    showToast('Productsoorten', 'Productsoort aangepast.', 'success');
  });
}

loadAll();
</script>
</body>
</html>
"""

GMAIL_HTML = """

<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
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
.wrap{max-width:1380px;margin:0 auto;padding:24px 20px 44px}
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
.hero p{margin:0;color:var(--muted);line-height:1.6;max-width:780px;font-size:15px}
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
.progress-shell{margin-top:16px;background:rgba(11,18,32,.66);border-radius:20px;padding:14px 16px;border:1px solid var(--line)}
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
.item{background:rgba(17,27,45,.78);border-radius:20px;padding:15px 16px;cursor:pointer;border:1px solid rgba(159,176,199,.08)}
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
.modal h3{margin:0 0 12px;font-size:24px}
.modal .row{margin-bottom:14px}
.modal .key{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.06em}
.modal .val{margin-top:4px;line-height:1.55}
.modal-close{float:right;background:rgba(31,41,55,.9);margin-left:10px}
.toast-wrap{position:fixed;top:18px;right:18px;z-index:10000;display:grid;gap:10px}
.toast{min-width:300px;max-width:390px;background:rgba(9,15,28,.96);border:1px solid rgba(201,170,112,.16);color:var(--text);border-radius:20px;padding:14px 16px;box-shadow:0 18px 40px rgba(0,0,0,.32)}
.toast .title{font-weight:900;margin-bottom:4px}
.toast.success{border-color:rgba(34,197,94,.35)}
.toast.info{border-color:rgba(56,189,248,.35)}
.toast.warning{border-color:rgba(245,158,11,.35)}
.toast.danger{border-color:rgba(239,68,68,.35)}
@media (max-width:1100px){.hero{grid-template-columns:1fr}.buttons{grid-template-columns:repeat(3,minmax(0,1fr));min-width:0}}
@media (max-width:1000px){.grid{grid-template-columns:repeat(2,1fr)}.chart-grid{grid-template-columns:1fr}}
@media (max-width:640px){.wrap{padding:18px 14px 34px}.hero-main{padding:20px 18px 18px}.hero h1{font-size:34px}.grid{grid-template-columns:1fr}.buttons{grid-template-columns:1fr}.tabs{padding:6px}}
</style>
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <a class="back" href="/">← Terug naar home</a>
    <a class="back" href="/logout">Uitloggen</a>
  </div>
  <div class="hero">
    <div class="hero-main">
      <div class="eyebrow">Gmail automation center</div>
      <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;"><img src="/static/gmail.png" alt="Gmail" onerror="this.style.display='none'" style="width:42px;height:42px;object-fit:contain;border-radius:12px;background:white;padding:6px;"><h1>Gmail Cleaner</h1></div>
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
    allowed_paths = {"/login", "/setup-code", "/logout"}
    if request.path.startswith("/static/"):
        return None
    if request.path in allowed_paths:
        return None
    if is_logged_in():
        return None
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "message": "Niet ingelogd."}), 401
    return redirect(url_for("login_page"))


@app.route("/login", methods=["GET"])
def login_page():
    message = session.pop("login_message", "")
    success = session.pop("login_success", False)
    return render_template_string(LOGIN_HTML, message=message, success=success, code_exists=has_access_code())

@app.route("/login", methods=["POST"])
def login_submit():
    access_code = (request.form.get("access_code") or "").strip()
    auth = load_auth()
    if access_code and access_code == (auth.get("access_code") or "").strip():
        session["is_logged_in"] = True
        return redirect(url_for("home"))
    session["login_message"] = "Onjuiste code."
    session["login_success"] = False
    return redirect(url_for("login_page"))

@app.route("/setup-code", methods=["POST"])
def setup_code():
    master_password = (request.form.get("master_password") or "").strip()
    new_access_code = (request.form.get("new_access_code") or "").strip()
    if master_password != MASTER_PASSWORD:
        session["login_message"] = "Hoofdwachtwoord onjuist."
        session["login_success"] = False
        return redirect(url_for("login_page"))
    if not new_access_code:
        session["login_message"] = "Vul een nieuwe code in."
        session["login_success"] = False
        return redirect(url_for("login_page"))
    save_auth({"access_code": new_access_code})
    session["login_message"] = "Nieuwe code opgeslagen. Je kunt nu inloggen."
    session["login_success"] = True
    return redirect(url_for("login_page"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

@app.route("/")
def home():
    ensure_files()
    normalize_bar_data()
    return render_template_string(HOME_HTML)


@app.route("/casa")
@app.route("/casa-cara")
def casa():
    ensure_files()
    normalize_bar_data()
    return render_template_string(CASA_HTML)


@app.route("/gmail")
def gmail():
    return render_template_string(GMAIL_HTML)


@app.route("/api/general")
def api_general():
    ensure_files()
    return jsonify(load_json(GENERAL_FILE))


@app.route("/api/bar")
def api_bar():
    ensure_files()
    normalize_bar_data()
    bar_data = load_json(BAR_FILE)
    return jsonify({
        "koelingen": bar_data.get("koelingen", []),
        "fill_items": build_fill_items(bar_data)
    })


@app.route("/api/product-types")
def api_product_types():
    ensure_files()
    return jsonify(get_types())

@app.route("/api/locations")
def api_locations():
    ensure_files()
    return jsonify(get_locations())

@app.route("/api/location-add", methods=["POST"])
def api_location_add():
    ensure_files()
    payload = request.json or {}
    name = payload.get("name", "").strip()
    locations = get_locations()
    if name and name not in locations:
        locations.append(name)
        locations = sorted(list(dict.fromkeys([x for x in locations if x])), key=lambda x: x.lower())
        if "-" not in locations:
            locations.append("-")
        save_json(LOCATIONS_FILE, locations)
    return jsonify({"locations": locations, "types": get_types()})

@app.route("/api/location-delete", methods=["POST"])
def api_location_delete():
    ensure_files()
    payload = request.json or {}
    name = payload.get("name", "").strip()
    locations = [x for x in get_locations() if x != name]
    if "-" not in locations:
        locations.append("-")
    save_json(LOCATIONS_FILE, locations)

    types = get_types()
    changed = False
    for t in types:
        if t.get("locatie") == name:
            t["locatie"] = "-"
            changed = True
    if changed:
        save_json(PRODUCT_TYPES_FILE, types)
    return jsonify({"locations": locations, "types": types})

@app.route("/api/location-rename", methods=["POST"])
def api_location_rename():
    ensure_files()
    payload = request.json or {}
    old_name = payload.get("old_name", "").strip()
    new_name = payload.get("new_name", "").strip()
    locations = []
    for loc in get_locations():
        if loc == old_name:
            locations.append(new_name)
        else:
            locations.append(loc)
    locations = sorted(list(dict.fromkeys([x for x in locations if x])), key=lambda x: x.lower())
    if "-" not in locations:
        locations.append("-")
    save_json(LOCATIONS_FILE, locations)

    types = get_types()
    for t in types:
        if t.get("locatie") == old_name:
            t["locatie"] = new_name
    save_json(PRODUCT_TYPES_FILE, types)
    return jsonify({"locations": locations, "types": types})

@app.route("/api/product-type-locations")
def api_product_type_locations():
    ensure_files()
    types = get_types()
    locs = sorted(list(dict.fromkeys([t.get("locatie", "-") for t in types if t.get("locatie")])))
    return jsonify(locs)


@app.route("/api/tips", methods=["POST"])
def api_tips():
    ensure_files()
    data = load_json(GENERAL_FILE)
    amount = float(request.json.get("amount", 0) or 0)
    mode = request.json.get("mode", "add")
    if mode == "subtract":
        data["fooienpot"] = round(float(data.get("fooienpot", 0)) - amount, 2)
    else:
        data["fooienpot"] = round(float(data.get("fooienpot", 0)) + amount, 2)
    save_json(GENERAL_FILE, data)
    return jsonify(data)


@app.route("/api/dienst", methods=["POST"])
def api_dienst():
    ensure_files()
    payload = request.json or {}
    data = load_json(GENERAL_FILE)
    diensten = data.get("diensten", [])
    diensten.append({
        "id": f"dienst_{len(diensten)+1}_{slugify(payload.get('date', ''))}",
        "date": payload.get("date", ""),
        "day_label": format_day_label(payload.get("date", "")),
        "time": payload.get("time", ""),
        "note": payload.get("note", "")
    })
    data["diensten"] = diensten
    save_json(GENERAL_FILE, data)
    return jsonify(data)


@app.route("/api/dienst-delete", methods=["POST"])
def api_dienst_delete():
    ensure_files()
    payload = request.json or {}
    data = load_json(GENERAL_FILE)
    data["diensten"] = [d for d in data.get("diensten", []) if d.get("id") != payload.get("id")]
    save_json(GENERAL_FILE, data)
    return jsonify(data)


@app.route("/api/cooling", methods=["POST"])
def api_cooling_add():
    ensure_files()
    payload = request.json or {}
    bar_data = load_json(BAR_FILE)
    koelingen = bar_data.get("koelingen", [])
    koelingen.append({
        "id": f"cool_{slugify(payload.get('name', ''))}_{len(koelingen)+1}",
        "naam": payload.get("name", "").strip(),
        "producten": []
    })
    bar_data["koelingen"] = koelingen
    save_json(BAR_FILE, bar_data)
    return jsonify({"koelingen": koelingen, "fill_items": build_fill_items(bar_data)})


@app.route("/api/cooling-delete", methods=["POST"])
def api_cooling_delete():
    ensure_files()
    payload = request.json or {}
    cooling_id = payload.get("cooling_id")
    bar_data = load_json(BAR_FILE)
    bar_data["koelingen"] = [k for k in bar_data.get("koelingen", []) if k.get("id") != cooling_id]
    save_json(BAR_FILE, bar_data)
    save_op_items([x for x in load_op_items() if x.get("koeling_id") != cooling_id])
    return jsonify({"koelingen": bar_data.get("koelingen", []), "fill_items": build_fill_items(bar_data)})


@app.route("/api/product-add", methods=["POST"])
def api_product_add():
    ensure_files()
    payload = request.json or {}
    bar_data = load_json(BAR_FILE)
    added = False
    for cooling in bar_data.get("koelingen", []):
        if cooling.get("id") == payload.get("cooling_id"):
            products = cooling.get("producten", [])
            products.append({
                "id": f"prod_{slugify(payload.get('name', ''))}_{len(products)+1}",
                "naam": payload.get("name", "").strip(),
                "voorraad": 0,
                "minimum": int(payload.get("minimum", 0) or 0),
                "soort": payload.get("soort", "Overig")
            })
            cooling["producten"] = products
            added = True
            break
    if added:
        save_json(BAR_FILE, bar_data)
    return jsonify({"koelingen": bar_data.get("koelingen", []), "fill_items": build_fill_items(bar_data)})

@app.route("/api/product-delete", methods=["POST"])
def api_product_delete():
    ensure_files()
    payload = request.json or {}
    cooling_id = payload.get("cooling_id")
    product_id = payload.get("product_id")
    bar_data = load_json(BAR_FILE)
    for cooling in bar_data.get("koelingen", []):
        if cooling.get("id") == cooling_id:
            cooling["producten"] = [p for p in cooling.get("producten", []) if p.get("id") != product_id]
            break
    save_json(BAR_FILE, bar_data)
    return jsonify({"koelingen": bar_data.get("koelingen", []), "fill_items": build_fill_items(bar_data)})


@app.route("/api/product-set-refill", methods=["POST"])
def api_product_set_refill():
    ensure_files()
    payload = request.json or {}
    cooling_id = payload.get("cooling_id")
    product_id = payload.get("product_id")
    refill = max(int(payload.get("refill", 0) or 0), 0)

    bar_data = load_json(BAR_FILE)
    updated = False

    for cooling in bar_data.get("koelingen", []):
        if cooling.get("id") == cooling_id:
            for product in cooling.get("producten", []):
                if product.get("id") == product_id:
                    product["voorraad"] = refill
                    updated = True
                    break
            break

    if updated:
        save_json(BAR_FILE, bar_data)

    return jsonify({
        "ok": updated,
        "koelingen": bar_data.get("koelingen", []),
        "fill_items": build_fill_items(bar_data)
    })

@app.route("/api/product-edit", methods=["POST"])
def api_product_edit():
    ensure_files()
    payload = request.json or {}
    cooling_id = payload.get("cooling_id")
    product_id = payload.get("product_id")
    bar_data = load_json(BAR_FILE)
    for cooling in bar_data.get("koelingen", []):
        if cooling.get("id") == cooling_id:
            for product in cooling.get("producten", []):
                if product.get("id") == product_id:
                    product["naam"] = payload.get("name", product.get("naam"))
                    product["minimum"] = int(payload.get("minimum", product.get("minimum", 0)) or 0)
                    product["soort"] = payload.get("soort", product.get("soort", "Overig"))
                    break
            break
    save_json(BAR_FILE, bar_data)
    return jsonify({"koelingen": bar_data.get("koelingen", []), "fill_items": build_fill_items(bar_data)})


@app.route("/api/fill-mark-product", methods=["POST"])
def api_fill_mark_product():
    ensure_files()
    payload = request.json or {}
    cooling_id = payload.get("cooling_id")
    product_id = payload.get("product_id")
    bar_data = load_json(BAR_FILE)
    for cooling in bar_data.get("koelingen", []):
        if cooling.get("id") == cooling_id:
            for product in cooling.get("producten", []):
                if product.get("id") == product_id:
                    product["voorraad"] = int(product.get("minimum", 0))
                    break
            break
    save_json(BAR_FILE, bar_data)
    save_op_items([x for x in load_op_items() if not (x.get("koeling_id")==cooling_id and x.get("product_id")==product_id)])
    return jsonify({"koelingen": bar_data.get("koelingen", []), "fill_items": build_fill_items(bar_data)})


@app.route("/api/fill-mark-all", methods=["POST"])
def api_fill_mark_all():
    ensure_files()
    op_pairs = {(x.get("koeling_id"), x.get("product_id")) for x in load_op_items()}
    bar_data = load_json(BAR_FILE)
    for cooling in bar_data.get("koelingen", []):
        for product in cooling.get("producten", []):
            if (cooling.get("id"), product.get("id")) in op_pairs:
                continue
            if int(product.get("voorraad", 0)) < int(product.get("minimum", 0)):
                product["voorraad"] = int(product.get("minimum", 0))
    save_json(BAR_FILE, bar_data)
    return jsonify({"koelingen": bar_data.get("koelingen", []), "fill_items": build_fill_items(bar_data)})



@app.route("/api/op-items")
def api_op_items():
    ensure_files()
    return jsonify(load_op_items())


@app.route("/api/fill-mark-out", methods=["POST"])
def api_fill_mark_out():
    ensure_files()
    payload = request.json or {}
    cooling_id = payload.get("cooling_id")
    product_id = payload.get("product_id")
    bar_data = load_json(BAR_FILE)
    item = None
    for cooling in bar_data.get("koelingen", []):
        if cooling.get("id") == cooling_id:
            for product in cooling.get("producten", []):
                if product.get("id") == product_id:
                    item = {
                        "koeling_id": cooling_id,
                        "koeling": cooling.get("naam"),
                        "product_id": product_id,
                        "product": product.get("naam"),
                        "soort": product.get("soort", "Overig"),
                        "locatie": type_location(product.get("soort", "Overig"))
                    }
                    break
            break
    if item:
        op_items = [x for x in load_op_items() if not (x.get("koeling_id")==cooling_id and x.get("product_id")==product_id)]
        op_items.append(item)
        save_op_items(op_items)
    return jsonify({"bar": {"koelingen": bar_data.get("koelingen", []), "fill_items": build_fill_items(bar_data)}, "op_items": load_op_items()})


@app.route("/api/op-mark-available", methods=["POST"])
def api_op_mark_available():
    ensure_files()
    payload = request.json or {}
    cooling_id = payload.get("cooling_id")
    product_id = payload.get("product_id")
    save_op_items([x for x in load_op_items() if not (x.get("koeling_id")==cooling_id and x.get("product_id")==product_id)])
    bar_data = load_json(BAR_FILE)
    return jsonify({"bar": {"koelingen": bar_data.get("koelingen", []), "fill_items": build_fill_items(bar_data)}, "op_items": load_op_items()})


@app.route("/api/locations-add", methods=["POST"])
def api_locations_add():
    ensure_files()
    payload = request.json or {}
    name = payload.get("name", "").strip()
    locations = get_locations()
    if name and name not in locations:
        locations.append(name)
        locations = sorted(list(dict.fromkeys(locations)), key=lambda x: x.lower())
        save_json(LOCATIONS_FILE, locations)
    return jsonify(locations)

@app.route("/api/locations-delete", methods=["POST"])
def api_locations_delete():
    ensure_files()
    payload = request.json or {}
    name = payload.get("name", "").strip()
    locations = [x for x in get_locations() if x != name]
    if "-" not in locations:
        locations.append("-")
    save_json(LOCATIONS_FILE, sorted(list(dict.fromkeys(locations)), key=lambda x: x.lower()))
    types = get_types()
    changed = False
    for t in types:
        if t.get("locatie") == name:
            t["locatie"] = "-"
            changed = True
    if changed:
        save_json(PRODUCT_TYPES_FILE, types)
    bar_data = load_json(BAR_FILE)
    return jsonify({"locations": get_locations(), "types": get_types(), "bar": {"koelingen": bar_data.get("koelingen", []), "fill_items": build_fill_items(bar_data), "op_items": load_json(OP_FILE)}})

@app.route("/api/locations-rename", methods=["POST"])
def api_locations_rename():
    ensure_files()
    payload = request.json or {}
    old_name = payload.get("old_name", "").strip()
    new_name = payload.get("new_name", "").strip()
    locations = [new_name if x == old_name else x for x in get_locations()]
    save_json(LOCATIONS_FILE, sorted(list(dict.fromkeys([x for x in locations if x])), key=lambda x: x.lower()))
    types = get_types()
    changed = False
    for t in types:
        if t.get("locatie") == old_name:
            t["locatie"] = new_name
            changed = True
    if changed:
        save_json(PRODUCT_TYPES_FILE, types)
    bar_data = load_json(BAR_FILE)
    return jsonify({"locations": get_locations(), "types": get_types(), "bar": {"koelingen": bar_data.get("koelingen", []), "fill_items": build_fill_items(bar_data), "op_items": load_json(OP_FILE)}})

@app.route("/api/product-type-add", methods=["POST"])
def api_product_type_add():
    ensure_files()
    payload = request.json or {}
    name = payload.get("name", "").strip()
    locatie = payload.get("locatie", "").strip() or "-"
    types = get_types()
    if name and not any(t.get("naam") == name for t in types):
        types.append({"naam": name, "locatie": locatie})
        types.sort(key=lambda x: x.get("naam", "").lower())
        save_json(PRODUCT_TYPES_FILE, types)
    return jsonify(types)


@app.route("/api/product-type-delete", methods=["POST"])
def api_product_type_delete():
    ensure_files()
    payload = request.json or {}
    name = payload.get("name", "").strip()
    types = [t for t in get_types() if t.get("naam") != name]
    save_json(PRODUCT_TYPES_FILE, types)

    bar_data = load_json(BAR_FILE)
    for cooling in bar_data.get("koelingen", []):
        for product in cooling.get("producten", []):
            if product.get("soort") == name:
                product["soort"] = "Overig"
    save_json(BAR_FILE, bar_data)
    return jsonify({"types": types, "bar": {"koelingen": bar_data.get("koelingen", []), "fill_items": build_fill_items(bar_data)}})


@app.route("/api/product-type-rename", methods=["POST"])
def api_product_type_rename():
    ensure_files()
    payload = request.json or {}
    old_name = payload.get("old_name", "").strip()
    new_name = payload.get("new_name", "").strip()
    new_location = payload.get("new_location", "").strip() or "-"

    types = get_types()
    for t in types:
        if t.get("naam") == old_name:
            t["naam"] = new_name
            t["locatie"] = new_location
    types.sort(key=lambda x: x.get("naam", "").lower())
    save_json(PRODUCT_TYPES_FILE, types)

    bar_data = load_json(BAR_FILE)
    for cooling in bar_data.get("koelingen", []):
        for product in cooling.get("producten", []):
            if product.get("soort") == old_name:
                product["soort"] = new_name
    save_json(BAR_FILE, bar_data)
    return jsonify({"types": types, "bar": {"koelingen": bar_data.get("koelingen", []), "fill_items": build_fill_items(bar_data)}})


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
