
from flask import Blueprint, render_template_string, jsonify, request, session, redirect
import json
from datetime import datetime, date
from pathlib import Path

casa_cara = Blueprint("casa_cara", __name__)

BASE_DIR = Path(__file__).resolve().parent
IS_RENDER = bool(__import__("os").environ.get("RENDER")) or bool(__import__("os").environ.get("PORT"))
DATA_DIR = (BASE_DIR / "data" / "casa_cara") if IS_RENDER else (BASE_DIR / "Data" / "Casa Cara")

BAR_FILE = DATA_DIR / "bar_koelingen.json"
GENERAL_FILE = DATA_DIR / "algemeen.json"
PRODUCT_TYPES_FILE = DATA_DIR / "product_soorten.json"
LOCATIONS_FILE = DATA_DIR / "locaties.json"
DIENST_TYPES_FILE = DATA_DIR / "dienst_soorten.json"
KITCHEN_FILE = DATA_DIR / "kitchen_tasks.json"
BAR_TASKS_FILE = DATA_DIR / "bar_tasks.json"
RECIPES_FILE = DATA_DIR / "recipes.json"
CASA_AUTH_FILE = DATA_DIR / "casa_auth.json"

def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

DEFAULT_PERMISSIONS = {
    "access_general": True,
    "access_bar": True,
    "access_kitchen": True,
    "manage_diensten": True,
    "manage_tips": True,
    "view_bijvullen": True,
    "view_oplijst": True,
    "adjust_stock": True,
    "view_recipes": True,
    "use_tasklists": True,
    "manage_dienst_types": False,
    "manage_users": False,
    "manage_products": False,
    "manage_types": False,
    "manage_locations": False,
    "manage_recipes": False,
    "manage_tasklists": False,
    "manage_coolers": False,
}


def default_permissions_for_role(role: str):
    role = (role or "").strip().lower()
    if role == "admin":
        return {key: True for key in DEFAULT_PERMISSIONS}
    return dict(DEFAULT_PERMISSIONS)


def normalize_permissions(role: str, permissions=None):
    base = default_permissions_for_role(role)
    if isinstance(permissions, dict):
        for key in base:
            if key in permissions:
                base[key] = bool(permissions.get(key))
    return base


def permission_labels():
    return {
        "access_general": "Algemeen zichtbaar",
        "access_bar": "Bar zichtbaar",
        "access_kitchen": "Keuken zichtbaar",
        "manage_diensten": "Diensten gebruiken",
        "manage_tips": "Fooienpot aanpassen",
        "view_bijvullen": "Bijvuloverzicht gebruiken",
        "view_oplijst": "OP-lijst gebruiken",
        "adjust_stock": "Koelingvoorraad aanpassen",
        "view_recipes": "Recepten openen",
        "use_tasklists": "Takenlijsten openen en afvinken",
        "manage_dienst_types": "Dienstsoorten beheren",
        "manage_users": "Medewerkers beheren",
        "manage_products": "Producten toevoegen en bewerken",
        "manage_types": "Productsoorten beheren",
        "manage_locations": "Locaties beheren",
        "manage_recipes": "Recepten beheren",
        "manage_tasklists": "Takenlijsten beheren",
        "manage_coolers": "Koelingen beheren",
    }


def load_casa_auth_data():
    data = load_json(CASA_AUTH_FILE, {"users": []})
    if not isinstance(data, dict):
        data = {"users": []}
    users = []
    for item in data.get("users", []):
        if not isinstance(item, dict):
            continue
        pin = str(item.get("pin") or "").strip()
        if not pin:
            continue
        role = "admin" if (item.get("role") or "").strip().lower() == "admin" else "medewerker"
        users.append({
            "name": (item.get("name") or item.get("username") or "Gebruiker").strip() or "Gebruiker",
            "pin": pin,
            "role": role,
            "active": bool(item.get("active", True)),
            "permissions": normalize_permissions(role, item.get("permissions")),
        })
    data["users"] = users
    return data


def save_casa_auth_data(data):
    users = []
    for item in data.get("users", []):
        if not isinstance(item, dict):
            continue
        pin = str(item.get("pin") or "").strip()
        if not pin:
            continue
        role = "admin" if (item.get("role") or "").strip().lower() == "admin" else "medewerker"
        users.append({
            "name": (item.get("name") or "Gebruiker").strip() or "Gebruiker",
            "pin": pin,
            "role": role,
            "active": bool(item.get("active", True)),
            "permissions": normalize_permissions(role, item.get("permissions")),
        })
    save_json(CASA_AUTH_FILE, {"users": users})


def get_casa_user_by_pin(pin: str):
    pin = (pin or "").strip()
    for user in load_casa_auth_data().get("users", []):
        if user.get("active", True) and user.get("pin") == pin:
            return user
    return None


def get_current_casa_user():
    pin = session.get("casa_user_pin")
    if not pin:
        return None
    user = get_casa_user_by_pin(pin)
    if user:
        session["casa_user_name"] = user.get("name")
        session["casa_user_role"] = user.get("role")
    return user


def current_permissions():
    user = get_current_casa_user() or {}
    role = user.get("role", "medewerker")
    return normalize_permissions(role, user.get("permissions"))


def has_casa_permission(key: str):
    if is_casa_admin():
        return True
    return bool(current_permissions().get(key))


def is_casa_admin():
    user = get_current_casa_user()
    return bool(user and user.get("role") == "admin")


def get_tip_context():
    user = get_current_casa_user() or {}
    data = get_general_data()
    if user.get("role") == "medewerker":
        user_name = user.get("name", "").strip()
        personal = data.get("fooienpot_per_user", {}) or {}
        amount = float(personal.get(user_name, 0) or 0)
        return {
            "amount": round(amount, 2),
            "label": f"Fooienpot van {user_name}" if user_name else "Jouw fooienpot",
            "is_personal": True,
        }
    amount = float(data.get("fooienpot", 0) or 0)
    return {
        "amount": round(amount, 2),
        "label": "Algemene fooienpot",
        "is_personal": False,
    }

def admin_only_response():
    return jsonify({"ok": False, "message": "Alleen een admin mag dit doen."}), 403


def permission_denied_response(message="Je hebt geen rechten voor deze actie."):
    return jsonify({"ok": False, "message": message}), 403

@casa_cara.before_request
def require_casa_login():
    if request.path.startswith("/api/") or request.path in {"/casa", "/casa-cara"}:
        if not session.get("dashboard_logged_in"):
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "message": "Niet ingelogd."}), 401
            return redirect("/login")
        if not session.get("casa_logged_in"):
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "message": "Log eerst in voor Casa Cara."}), 401
            return redirect("/casa-cara-login")
        if not get_current_casa_user():
            for key in ["casa_logged_in", "casa_last_activity", "casa_user_pin", "casa_user_name", "casa_user_role"]:
                session.pop(key, None)
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "message": "Casa Cara gebruiker niet gevonden."}), 401
            return redirect("/casa-cara-login")

def slugify(text: str) -> str:
    text = (text or "").strip().lower()
    clean = "".join(ch if ch.isalnum() else "_" for ch in text)
    while "__" in clean:
        clean = clean.replace("__", "_")
    return clean.strip("_") or "item"

def get_bar_data():
    data = load_json(BAR_FILE, {"koelingen": []})
    if not isinstance(data, dict):
        data = {"koelingen": []}
    data.setdefault("koelingen", [])
    return data

def save_bar_data(data):
    save_json(BAR_FILE, data)

def get_general_data():
    data = load_json(GENERAL_FILE, {"fooienpot": 0, "fooienpot_per_user": {}, "diensten": []})
    if not isinstance(data, dict):
        data = {"fooienpot": 0, "fooienpot_per_user": {}, "diensten": []}
    data.setdefault("fooienpot", 0)
    data.setdefault("fooienpot_per_user", {})
    if not isinstance(data.get("fooienpot_per_user"), dict):
        data["fooienpot_per_user"] = {}
    data.setdefault("diensten", [])
    return data

def save_general_data(data):
    save_json(GENERAL_FILE, data)

def get_types():
    raw = load_json(PRODUCT_TYPES_FILE, [])
    result = []
    for item in raw:
        if isinstance(item, str):
            result.append({"naam": item, "locatie": "-"})
        elif isinstance(item, dict):
            result.append({
                "naam": item.get("naam", "Overig"),
                "locatie": item.get("locatie", "-"),
            })
    deduped = {}
    for item in result:
        deduped[item["naam"]] = {"naam": item["naam"], "locatie": item["locatie"]}
    return sorted(deduped.values(), key=lambda x: x["naam"].lower())

def save_types(items):
    save_json(PRODUCT_TYPES_FILE, items)

def get_locations():
    raw = load_json(LOCATIONS_FILE, [])
    result = []
    for item in raw:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            result.append(item.get("naam", "-"))
    cleaned = []
    seen = set()
    for item in result:
        item = (item or "").strip()
        if item and item not in seen:
            seen.add(item)
            cleaned.append(item)
    if "-" not in seen:
        cleaned.append("-")
    return sorted(cleaned, key=lambda x: x.lower())

def save_locations(items):
    items = [x for x in items if x]
    if "-" not in items:
        items.append("-")
    save_json(LOCATIONS_FILE, sorted(list(dict.fromkeys(items)), key=lambda x: x.lower()))

def get_dienst_types():
    raw = load_json(DIENST_TYPES_FILE, [
        {"naam": "Keukendienst", "start": "16:00", "einde": "23:00"},
        {"naam": "Bardienst", "start": "16:00", "einde": "23:30"},
    ])
    items = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            items.append({"naam": item.strip(), "start": "", "einde": ""})
        elif isinstance(item, dict):
            name = (item.get("naam") or "").strip()
            if name:
                items.append({
                    "naam": name,
                    "start": (item.get("start") or "").strip(),
                    "einde": (item.get("einde") or "").strip(),
                })
    deduped = {}
    for item in items:
        deduped[item["naam"]] = item
    result = sorted(deduped.values(), key=lambda x: x["naam"].lower())
    if not result:
        result = [
            {"naam": "Keukendienst", "start": "16:00", "einde": "23:00"},
            {"naam": "Bardienst", "start": "16:00", "einde": "23:30"},
        ]
    return result

def save_dienst_types(items):
    cleaned = []
    seen = set()
    for item in items:
        if isinstance(item, str):
            name = item.strip()
            start = ""
            einde = ""
        elif isinstance(item, dict):
            name = (item.get("naam") or "").strip()
            start = (item.get("start") or "").strip()
            einde = (item.get("einde") or "").strip()
        else:
            continue
        if name and name not in seen:
            seen.add(name)
            cleaned.append({"naam": name, "start": start, "einde": einde})
    if not cleaned:
        cleaned = [
            {"naam": "Keukendienst", "start": "16:00", "einde": "23:00"},
            {"naam": "Bardienst", "start": "16:00", "einde": "23:30"},
        ]
    save_json(DIENST_TYPES_FILE, cleaned)


def normalize_tasklist_data(path: Path):
    data = load_json(path, {"lists": []})
    if not isinstance(data, dict):
        data = {"lists": []}
    data.setdefault("lists", [])
    changed = False
    for item in data.get("lists", []):
        item.setdefault("tasks", [])
        for task in item.get("tasks", []):
            if "last_checked_by" not in task:
                task["last_checked_by"] = ""
                changed = True
            if "last_checked_at" not in task:
                task["last_checked_at"] = ""
                changed = True
            if "last_checked" not in task:
                task["last_checked"] = ""
                changed = True
            if "checked" not in task:
                task["checked"] = False
                changed = True
            task.setdefault("subtasks", [])
            for sub in task.get("subtasks", []):
                if "last_checked_by" not in sub:
                    sub["last_checked_by"] = ""
                    changed = True
                if "last_checked_at" not in sub:
                    sub["last_checked_at"] = ""
                    changed = True
                if "last_checked" not in sub:
                    sub["last_checked"] = ""
                    changed = True
                if "checked" not in sub:
                    sub["checked"] = False
                    changed = True
    if changed:
        save_json(path, data)
    return data

def sync_task_with_subtasks(task, today: str, checked_by: str = "", checked_at: str = ""):
    subtasks = [sub for sub in task.get("subtasks", []) if isinstance(sub, dict)]
    if not subtasks:
        return
    all_done_today = all(bool(sub.get("checked")) and sub.get("last_checked") == today for sub in subtasks)
    if all_done_today:
        task["checked"] = True
        task["last_checked"] = today
        task["last_checked_by"] = checked_by or task.get("last_checked_by") or ""
        task["last_checked_at"] = checked_at or task.get("last_checked_at") or ""
    else:
        task["checked"] = False
        task["last_checked"] = ""
        task["last_checked_by"] = ""
        task["last_checked_at"] = ""

def get_kitchen_data():
    return normalize_tasklist_data(KITCHEN_FILE)

def save_kitchen_data(data):
    save_json(KITCHEN_FILE, data)

def get_bar_tasks_data():
    return normalize_tasklist_data(BAR_TASKS_FILE)

def save_bar_tasks_data(data):
    save_json(BAR_TASKS_FILE, data)

def get_recipes_data():
    data = load_json(RECIPES_FILE, {"items": []})
    if not isinstance(data, dict):
        data = {"items": []}
    data.setdefault("items", [])
    return data

def save_recipes_data(data):
    save_json(RECIPES_FILE, data)

def type_location(type_name: str) -> str:
    for item in get_types():
        if item["naam"] == type_name:
            return item["locatie"]
    return "-"

def build_fill_items(bar_data):
    items = []
    for koeling in bar_data.get("koelingen", []):
        for product in koeling.get("producten", []):
            if product.get("op"):
                continue
            voorraad = int(product.get("voorraad", 0) or 0)
            minimum = int(product.get("minimum", 0) or 0)
            if voorraad < minimum:
                soort = product.get("soort", "Overig")
                items.append({
                    "koeling_id": koeling.get("id"),
                    "koeling": koeling.get("naam", "Onbekende koeling"),
                    "product_id": product.get("id"),
                    "product": product.get("naam", "Onbekend product"),
                    "soort": soort,
                    "voorraad": voorraad,
                    "minimum": minimum,
                    "bijvullen": max(minimum - voorraad, 0),
                    "locatie": type_location(soort),
                })
    items.sort(key=lambda x: (
        (x.get("locatie") or "").lower(),
        (x.get("soort") or "").lower(),
        (x.get("koeling") or "").lower(),
        (x.get("product") or "").lower(),
    ))
    return items

def serialize_app_data():
    bar_data = get_bar_data()
    general_data = get_general_data()
    tip_context = get_tip_context()
    general_view = dict(general_data)
    general_view["fooienpot"] = tip_context["amount"]
    general_view["fooienpot_label"] = tip_context["label"]
    general_view["fooienpot_is_personal"] = tip_context["is_personal"]
    user = get_current_casa_user() or {}
    permissions = current_permissions()
    return {
        "bar": {
            "koelingen": bar_data.get("koelingen", []),
            "fill_items": build_fill_items(bar_data),
        },
        "general": general_view,
        "types": get_types(),
        "locations": get_locations(),
        "dienst_types": get_dienst_types(),
        "kitchen": get_kitchen_data(),
        "bar_tasks": get_bar_tasks_data(),
        "recipes": get_recipes_data(),
        "auth": {
            "user_name": user.get("name", ""),
            "role": user.get("role", ""),
            "is_admin": is_casa_admin(),
            "permissions": permissions,
            "permission_labels": permission_labels(),
            "users": load_casa_auth_data().get("users", []) if is_casa_admin() else [],
        },
    }

HTML = r"""
<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8">
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1.0, viewport-fit=cover, maximum-scale=1.0, user-scalable=no"
  >
  <meta name="theme-color" content="#070b12">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <title>Casa Cara</title>
  <link rel="icon" type="image/png" href="/static/casa.png">
  <style>
    :root{
      --bg:#070b12;
      --bg-elev:#0d1420;
      --bg-card:#111a28;
      --bg-card-2:#162235;
      --line:rgba(255,255,255,.08);
      --line-strong:rgba(255,255,255,.16);
      --text:#eef4fb;
      --muted:#9fb0c7;
      --accent:#d4b06a;
      --accent-soft:rgba(212,176,106,.14);
      --danger:#e06b6b;
      --warn:#e7b45d;
      --good:#6fca93;
      --shadow:0 20px 48px rgba(0,0,0,.32);
      --radius-xl:24px;
      --radius-lg:18px;
      --radius-md:14px;
      --app-max:980px;
      --sidebar-w:285px;
    }
    *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
    html,body{
      margin:0;padding:0;min-height:100%;
      background:#070b12 !important;
      color:var(--text);
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,system-ui,sans-serif;
      overscroll-behavior:none;
      color-scheme:dark;
    }
    body{touch-action:manipulation}
    body::before{
      content:"";
      position:fixed;
      inset:0;
      z-index:-3;
      background:#070b12;
    }
    button,input,select{font:inherit}
    a{color:inherit;text-decoration:none}
    .app{
      min-height:100dvh;
      background:
        radial-gradient(circle at top left, rgba(212,176,106,.08), transparent 26%),
        radial-gradient(circle at top right, rgba(112,154,255,.06), transparent 22%),
        linear-gradient(180deg,#070b12,#0b111a 60%,#070b12);
    }

    .topbar{
      position:sticky;top:0;z-index:30;
      display:flex;align-items:center;gap:14px;
      min-height:68px;
      padding:14px 18px calc(14px + env(safe-area-inset-top,0px));
      background:rgba(7,11,18,.88);
      backdrop-filter:blur(18px);
      border-bottom:1px solid var(--line);
    }
    .menu-btn,.icon-btn{
      width:42px;height:42px;border-radius:14px;border:1px solid var(--line);
      background:rgba(255,255,255,.02);color:var(--text);
      display:grid;place-items:center;cursor:pointer;
    }
    .menu-btn span{display:block;width:18px;height:2px;background:var(--text);border-radius:999px;position:relative}
    .menu-btn span::before,.menu-btn span::after{
      content:"";position:absolute;left:0;width:18px;height:2px;background:var(--text);border-radius:999px;
    }
    .menu-btn span::before{top:-6px}
    .menu-btn span::after{top:6px}
    .topbar-text{display:flex;flex-direction:column;min-width:0}
    .eyebrow{font-size:12px;color:var(--muted);line-height:1.1}
    .title{font-size:19px;font-weight:800;letter-spacing:-.02em;color:var(--text)}
    .layout{max-width:var(--app-max);margin:0 auto;padding:18px 16px calc(26px + env(safe-area-inset-bottom,0px))}
    .page{display:none}
    .page.active{display:block}

    .welcome-banner{
      margin-bottom:14px;
      padding:6px 2px 2px;
    }
    .welcome-banner .welcome-kicker{
      color:var(--muted);
      font-size:13px;
      margin-bottom:6px;
      letter-spacing:.08em;
      text-transform:uppercase;
    }
    .welcome-banner h1{
      margin:0;
      font-size:36px;
      line-height:1;
      letter-spacing:-.04em;
      color:var(--text);
    }
    .welcome-banner p{
      margin:10px 0 0;
      color:var(--muted);
      font-size:14px;
      line-height:1.5;
    }

    .hero{
      background:linear-gradient(180deg, rgba(18,27,40,.96), rgba(12,19,30,.96));
      border:1px solid var(--line);
      border-radius:var(--radius-xl);
      padding:18px;
      box-shadow:var(--shadow);
      margin-bottom:16px;
    }
    .hero h1{
      margin:0 0 8px;
      font-size:28px;
      line-height:1.05;
      letter-spacing:-.04em;
      color:var(--text);
    }
    .hero p{margin:0;color:var(--muted);line-height:1.55;font-size:14px}
    .stats-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:16px}
    .stat-card{
      border:1px solid var(--line);
      background:
        radial-gradient(circle at top right, rgba(212,176,106,.08), transparent 30%),
        linear-gradient(180deg, var(--bg-card), var(--bg-card-2));
      border-radius:22px;
      padding:16px;
      box-shadow:var(--shadow);
      cursor:pointer;
      transition:transform .16s ease,border-color .16s ease, box-shadow .16s ease;
      text-align:left;
      color:var(--text);
    }
    .stat-card:hover{border-color:var(--line-strong); box-shadow:0 24px 52px rgba(0,0,0,.36)}
    .stat-card:active{transform:scale(.99)}
    .stat-icon{
      width:38px;height:38px;border-radius:12px;
      display:grid;place-items:center;
      background:rgba(212,176,106,.12);
      border:1px solid rgba(212,176,106,.22);
      color:#f3dfbc;
      margin-bottom:12px;
      font-size:16px;
    }
    .stat-label{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px}
    .stat-value{font-size:26px;font-weight:900;letter-spacing:-.04em;margin-bottom:6px;color:var(--text)}
    .stat-sub{color:var(--muted);font-size:13px;line-height:1.35}

    .section{margin-top:18px}
    .section-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}
    .section-title{font-size:18px;font-weight:800;letter-spacing:-.02em;margin:0;color:var(--text)}
    .section-kicker{color:var(--muted);font-size:13px}
    .stack{display:grid;gap:12px}
    .panel{
      border:1px solid var(--line);
      background:linear-gradient(180deg, rgba(16,25,38,.98), rgba(12,20,31,.98));
      border-radius:20px;
      padding:16px;
      box-shadow:var(--shadow);
    }
    .panel-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px}
    .panel-title{margin:0;font-size:16px;font-weight:800;letter-spacing:-.02em;color:var(--text)}
    .actions{display:flex;flex-wrap:wrap;gap:8px}
    .btn{
      min-height:40px;padding:0 14px;border-radius:14px;border:1px solid var(--line);
      background:rgba(255,255,255,.03);color:var(--text);cursor:pointer;
    }
    .btn.accent{background:rgba(212,176,106,.12);border-color:rgba(212,176,106,.24);color:#f3dfbc}
    .btn.danger{background:rgba(224,107,107,.10);border-color:rgba(224,107,107,.22);color:#ffd7d7}
    .btn.good{background:rgba(111,202,147,.10);border-color:rgba(111,202,147,.22);color:#d8ffe7}

    .badge{
      display:inline-flex;align-items:center;gap:6px;min-height:28px;padding:0 10px;border-radius:999px;
      border:1px solid var(--line);color:var(--muted);background:rgba(255,255,255,.02);font-size:12px;white-space:nowrap;
    }
    .badge.warn{color:#f5d7a6;background:rgba(231,180,93,.10);border-color:rgba(231,180,93,.22)}
    .badge.good{color:#d7ffe6;background:rgba(111,202,147,.10);border-color:rgba(111,202,147,.22)}
    .badge.accent{color:#f5dfb5;background:var(--accent-soft);border-color:rgba(212,176,106,.24)}

    .list{display:grid;gap:10px}
    .list-item{
      border:1px solid var(--line);
      background:rgba(255,255,255,.02);
      border-radius:16px;
      padding:14px;
    }
    .item-top{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:6px}
    .item-title{font-weight:800;letter-spacing:-.01em;font-size:15px;margin:0;color:var(--text)}
    .item-sub{color:var(--muted);font-size:13px;line-height:1.4}
    .meta-row{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
    .meta-chip{
      min-height:28px;display:inline-flex;align-items:center;padding:0 10px;border-radius:999px;
      border:1px solid var(--line);background:rgba(255,255,255,.03);color:var(--muted);font-size:12px;
    }
    .permission-grid{display:grid;grid-template-columns:1fr;gap:10px}.permission-panel{border:1px solid var(--line);border-radius:14px;padding:10px;background:rgba(255,255,255,.02)}.permission-kicker{margin:0 0 8px;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.10em;font-weight:800}.permission-row{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:8px 0;border-top:1px solid rgba(255,255,255,.05)}.permission-row:first-child{border-top:none;padding-top:0}.permission-row:last-child{padding-bottom:0}.permission-inline-label{font-size:13px;line-height:1.25;color:var(--text)}.permission-grid select{width:100%;min-height:42px;border-radius:12px;border:1px solid var(--line);background:rgba(255,255,255,.03);color:var(--text);padding:0 12px;outline:none}.permission-grid input[type='checkbox']{width:16px;height:16px;accent-color:#d4b06a;flex:0 0 auto}
    .perm-item{display:flex;align-items:flex-start;gap:8px;padding:10px;border:1px solid var(--line);border-radius:12px;background:rgba(255,255,255,.02)}
    .perm-item input{margin-top:1px;width:15px;height:15px}
    .perm-label{font-size:12px;color:var(--text);line-height:1.3}
    .overview-grid{display:grid;grid-template-columns:1fr;gap:12px}.overview-card{border:1px solid var(--line);border-radius:18px;padding:15px;background:linear-gradient(180deg, rgba(18,27,40,.96), rgba(12,19,30,.96));box-shadow:0 12px 24px rgba(0,0,0,.14)}.overview-top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:8px}.overview-kicker{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.10em;font-weight:800;margin-bottom:6px}.overview-title{font-size:18px;font-weight:900;letter-spacing:-.02em;color:var(--text);margin:0 0 4px}.overview-sub{font-size:13px;color:var(--muted);line-height:1.45}.overview-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.mini-list{display:grid;gap:8px}.mini-row{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 12px;border:1px solid rgba(255,255,255,.06);border-radius:12px;background:rgba(255,255,255,.02)}.mini-row strong{display:block;font-size:14px;color:var(--text)}.mini-row span{font-size:12px;color:var(--muted);line-height:1.35}.overview-note{padding:12px 14px;border:1px dashed var(--line-strong);border-radius:14px;color:var(--muted);font-size:13px;line-height:1.5;background:rgba(255,255,255,.02)}
    .bot-panel{margin:16px 0 18px;border:1px solid var(--line);background:linear-gradient(180deg, rgba(18,27,40,.98), rgba(12,19,30,.98));border-radius:22px;padding:16px;box-shadow:var(--shadow);display:grid;gap:12px}
    .bot-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
    .bot-title{margin:0;font-size:18px;font-weight:900;letter-spacing:-.02em;color:var(--text)}
    .bot-sub{margin-top:4px;color:var(--muted);font-size:13px;line-height:1.45}
    .bot-shell{border:1px solid rgba(255,255,255,.06);border-radius:18px;background:rgba(255,255,255,.02);overflow:hidden}
    .bot-chat{display:grid;gap:10px;max-height:320px;overflow:auto;padding:14px}
    .bot-chat::-webkit-scrollbar{width:8px}.bot-chat::-webkit-scrollbar-thumb{background:rgba(255,255,255,.10);border-radius:999px}
    .bot-msg{max-width:92%;padding:12px 14px;border-radius:16px;border:1px solid var(--line);font-size:14px;line-height:1.55;word-break:break-word;white-space:pre-wrap}
    .bot-msg.bot{justify-self:start;background:rgba(255,255,255,.025);color:var(--text)}
    .bot-msg.user{justify-self:end;background:rgba(212,176,106,.12);border-color:rgba(212,176,106,.24);color:#f5dfb5}
    .bot-msg.muted{color:var(--muted)}
    .bot-composer{padding:12px 14px 14px;border-top:1px solid rgba(255,255,255,.06);background:linear-gradient(180deg, rgba(10,16,24,.98), rgba(12,19,30,.98));position:sticky;bottom:0}
    .bot-row{display:flex;gap:8px;align-items:center}
    .bot-row input{flex:1;min-height:46px;border-radius:14px;border:1px solid var(--line);background:rgba(255,255,255,.03);color:var(--text);padding:0 14px;outline:none}
    .bot-chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
    .bot-chips.hidden{display:none}
    .bot-chip{min-height:32px;padding:0 12px;border-radius:999px;border:1px solid var(--line);background:rgba(255,255,255,.03);color:var(--text);cursor:pointer;font-size:12px}
    .bot-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
    .bot-action{min-height:34px;padding:0 12px;border-radius:999px;border:1px solid rgba(212,176,106,.22);background:rgba(212,176,106,.10);color:#f5dfb5;cursor:pointer}
    .bot-status{margin-top:10px;color:var(--muted);font-size:13px;display:none}
    .bot-status.visible{display:block}

    .audit-note{margin-top:8px;color:var(--muted);font-size:12px;line-height:1.45}
    .item-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
    .empty{
      padding:18px 14px;border-radius:16px;border:1px dashed var(--line-strong);
      color:var(--muted);text-align:center;font-size:14px;background:rgba(255,255,255,.02);
    }

    .drawer-backdrop{
      position:fixed;inset:0;background:rgba(0,0,0,.45);backdrop-filter:blur(3px);
      opacity:0;pointer-events:none;transition:.18s ease;z-index:39;
    }
    .drawer-backdrop.open{opacity:1;pointer-events:auto}
    .drawer{
      position:fixed;top:0;left:0;bottom:0;z-index:40;width:min(var(--sidebar-w),86vw);
      background:linear-gradient(180deg,#0b121d,#09111a);border-right:1px solid var(--line);
      transform:translateX(-100%);transition:transform .22s ease;
      padding:calc(16px + env(safe-area-inset-top,0px)) 14px calc(20px + env(safe-area-inset-bottom,0px));
      display:flex;flex-direction:column;box-shadow:0 26px 60px rgba(0,0,0,.45)
    }
    .drawer.open{transform:translateX(0)}
    .drawer-brand{padding:8px 8px 14px;border-bottom:1px solid var(--line);margin-bottom:12px}
    .drawer-brand .small{font-size:12px;color:var(--muted);margin-bottom:4px}
    .drawer-brand .big{font-size:22px;font-weight:900;letter-spacing:-.03em;color:var(--text)}
    .nav{display:grid;gap:8px;overflow:auto;padding-right:4px}
    .nav-btn,.sub-btn,.logout-btn,.home-btn{
      width:100%;text-align:left;border:1px solid var(--line);background:rgba(255,255,255,.02);color:var(--text);
      border-radius:16px;min-height:46px;padding:0 14px;display:flex;align-items:center;justify-content:space-between;cursor:pointer;
    }
    .nav-btn.active,.sub-btn.active{border-color:rgba(212,176,106,.30);background:rgba(212,176,106,.10)}
    .nav-left{display:flex;align-items:center;gap:10px;min-width:0}
    .nav-icon{width:24px;height:24px;border-radius:8px;display:grid;place-items:center;background:rgba(255,255,255,.04);color:var(--muted);font-size:13px;flex:0 0 auto}
    .nav-label{font-size:15px;font-weight:700;letter-spacing:-.01em;color:var(--text)}
    .nav-caret{color:var(--muted);transition:transform .18s ease}
    .nav-btn.expanded .nav-caret{transform:rotate(90deg)}
    .sub-list{display:none;gap:8px;padding:4px 0 2px 12px;margin:0 0 4px;border-left:1px solid rgba(255,255,255,.06)}
    .sub-list.open{display:grid}
    .sub-btn{min-height:42px;font-size:14px;border-radius:14px}
    .logout-wrap{margin-top:auto;padding-top:14px;border-top:1px solid var(--line);display:grid;gap:8px}
    .home-btn{justify-content:flex-start;gap:10px;background:rgba(255,255,255,.03)}
    .logout-btn{justify-content:flex-start;gap:10px;color:#ffd9d9;background:rgba(224,107,107,.10);border-color:rgba(224,107,107,.18)}

    .modal-backdrop{
      position:fixed;inset:0;z-index:60;background:rgba(0,0,0,.56);backdrop-filter:blur(4px);
      opacity:0;pointer-events:none;transition:.18s ease;
      display:flex;align-items:flex-end;justify-content:center;
    }
    .modal-backdrop.open{opacity:1;pointer-events:auto}
    .modal{
      width:min(100%, var(--app-max));
      background:linear-gradient(180deg,#101827,#0c1420);
      border-top-left-radius:26px;border-top-right-radius:26px;
      border:1px solid var(--line);
      padding:18px 16px calc(18px + env(safe-area-inset-bottom,0px));
      box-shadow:0 -20px 40px rgba(0,0,0,.36);
      transform:translateY(12px);transition:transform .18s ease;
      max-height:88dvh;overflow:auto;
    }
    .modal-backdrop.open .modal{transform:translateY(0)}
    .modal-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:14px}
    .modal-title{margin:0;font-size:20px;font-weight:900;letter-spacing:-.03em;color:var(--text)}
    .modal-sub{margin-top:4px;color:var(--muted);font-size:13px}
    .modal-close{
      width:38px;height:38px;border-radius:12px;border:1px solid var(--line);
      background:rgba(255,255,255,.03);color:var(--text);cursor:pointer;
    }
    .form-grid{display:grid;gap:12px}
    .field label{display:block;font-size:13px;color:var(--muted);margin-bottom:6px}
    .field input,.field select{
      width:100%;min-height:46px;border-radius:14px;border:1px solid var(--line);
      background:rgba(255,255,255,.03);color:var(--text);padding:0 14px;outline:none;
    }
    .form-actions{display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap;margin-top:14px}

    .toast-wrap{position:fixed;top:16px;right:16px;z-index:80;display:grid;gap:10px}
    .toast{
      min-width:220px;max-width:320px;padding:14px 16px;border-radius:16px;border:1px solid var(--line);
      background:rgba(11,18,29,.96);color:var(--text);box-shadow:0 18px 40px rgba(0,0,0,.32)
    }
    .toast.success{border-color:rgba(111,202,147,.26)}
    .toast.error{border-color:rgba(224,107,107,.26)}

    @media (min-width: 860px){
      .layout{padding-left:24px;padding-right:24px}
      .welcome-banner h1{font-size:46px}
      .hero h1{font-size:32px}
      .stats-grid{grid-template-columns:repeat(4,1fr)}
      .modal-backdrop{align-items:center}
      .modal{
        border-radius:24px;
        transform:translateY(8px) scale(.99);
        max-width:640px;
      }
      .modal-backdrop.open .modal{transform:translateY(0) scale(1)}
    }
  
    .klist-card{
      border:1px solid var(--line);
      background:rgba(255,255,255,.02);
      border-radius:18px;
      padding:14px;
    }
    .kprogress{
      width:100%;
      height:8px;
      border-radius:999px;
      background:rgba(255,255,255,.08);
      overflow:hidden;
      margin-top:10px;
    }
    .kprogress > span{
      display:block;
      height:100%;
      border-radius:999px;
      background:linear-gradient(90deg, rgba(212,176,106,.9), rgba(244,220,170,.95));
    }
    .kmeta{
      display:flex;
      justify-content:space-between;
      align-items:center;
      gap:10px;
      margin-top:10px;
      color:var(--muted);
      font-size:13px;
    }
    .ktask{
      border:1px solid var(--line);
      background:rgba(255,255,255,.02);
      border-radius:16px;
      padding:14px;
    }
    .ktask-row,.ksub-row{
      display:flex;
      align-items:flex-start;
      gap:10px;
      cursor:pointer;
    }
    .kcheck{
      width:28px;height:28px;min-width:28px;
      border-radius:999px;
      border:1px solid rgba(255,255,255,.14);
      background:rgba(255,255,255,.03);
      display:grid;place-items:center;
      color:var(--muted);font-size:13px;
      margin-top:2px;
    }
    .kcheck.done{
      background:rgba(111,202,147,.14);
      border-color:rgba(111,202,147,.28);
      color:#d8ffe7;
    }
    .ksub-wrap{
      margin-top:12px;
      padding-left:12px;
      border-left:1px solid rgba(255,255,255,.08);
      display:grid;
      gap:10px;
    }
    .ksub{
      border:1px solid rgba(255,255,255,.06);
      background:rgba(255,255,255,.014);
      border-radius:12px;
      padding:10px;
    }
    .recipe-card{
      border:1px solid var(--line);
      background:rgba(255,255,255,.02);
      border-radius:18px;
      padding:14px;
    }
    @media (max-width:640px){
      .welcome-banner h1{font-size:30px}
      .item-actions{display:grid;grid-template-columns:1fr;gap:8px}
      .item-actions .btn{width:100%}
      .klist-card,.ktask,.ksub,.recipe-card,.list-item{padding:13px}
    }


    .klist-card{
      border:1px solid var(--line);
      background:linear-gradient(180deg, rgba(18,27,40,.96), rgba(12,19,30,.96));
      border-radius:20px;
      padding:16px;
      box-shadow:var(--shadow);
    }
    .klist-top{
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
      margin-bottom:10px;
    }
    .klist-left{
      display:flex;
      align-items:center;
      gap:12px;
      min-width:0;
    }
    .klist-icon{
      width:38px;
      height:38px;
      min-width:38px;
      border-radius:12px;
      display:grid;
      place-items:center;
      background:rgba(212,176,106,.12);
      border:1px solid rgba(212,176,106,.22);
      color:#f3dfbc;
      font-size:16px;
    }
    .klist-name{
      font-size:16px;
      font-weight:800;
      letter-spacing:-.02em;
      color:var(--text);
    }
    .klist-sub{
      color:var(--muted);
      font-size:13px;
      margin-top:2px;
    }
    .kprogress{
      width:100%;
      height:10px;
      border-radius:999px;
      background:rgba(255,255,255,.08);
      overflow:hidden;
      margin-top:12px;
    }
    .kprogress > span{
      display:block;
      height:100%;
      border-radius:999px;
      background:linear-gradient(90deg, rgba(212,176,106,.92), rgba(244,220,170,.96));
    }
    .kmeta{
      display:flex;
      justify-content:space-between;
      align-items:center;
      gap:10px;
      margin-top:10px;
      color:var(--muted);
      font-size:13px;
    }
    .klist-actions{
      display:grid;
      grid-template-columns:1fr;
      gap:8px;
      margin-top:12px;
    }
    .kheadbar{
      display:flex;
      flex-direction:column;
      gap:12px;
      margin-bottom:14px;
    }
    .khead-top{
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
    }
    .khead-actions{
      display:grid;
      grid-template-columns:1fr;
      gap:8px;
    }
    .task-sections{
      display:grid;
      gap:12px;
    }
    .task-group{
      border:1px solid var(--line);
      border-radius:18px;
      background:rgba(255,255,255,.015);
      overflow:hidden;
      box-shadow:0 10px 24px rgba(0,0,0,.10);
    }
    .task-group summary{
      list-style:none;
      cursor:pointer;
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
      padding:12px 14px;
      background:rgba(255,255,255,.02);
    }
    .task-group summary::-webkit-details-marker{display:none}
    .task-group-body{
      padding:10px;
      display:grid;
      gap:10px;
      border-top:1px solid rgba(255,255,255,.06);
    }
    .task-group-label{
      display:flex;
      flex-direction:column;
      gap:4px;
      min-width:0;
    }
    .task-group-title{
      font-size:14px;
      font-weight:900;
      letter-spacing:-.01em;
      color:var(--text);
    }
    .task-group-sub{
      font-size:12px;
      color:var(--muted);
      line-height:1.35;
    }
    .task-group-right{
      display:flex;
      align-items:center;
      gap:8px;
      flex-shrink:0;
    }
    .group-chevron{
      color:var(--muted);
      font-size:12px;
      transition:transform .18s ease;
    }
    .task-group[open] .group-chevron{transform:rotate(180deg)}
    .task-group.done-group:not([open]){
      opacity:.96;
    }
    .ktask{
      border:1px solid var(--line);
      background:rgba(255,255,255,.018);
      border-radius:16px;
      padding:12px;
      box-shadow:0 8px 20px rgba(0,0,0,.10);
    }
    .ktask-row,.ksub-row{
      display:flex;
      align-items:flex-start;
      gap:10px;
      cursor:pointer;
    }
    .kcheck{
      width:26px;
      height:26px;
      min-width:26px;
      border-radius:999px;
      border:1px solid rgba(255,255,255,.14);
      background:rgba(255,255,255,.03);
      display:grid;
      place-items:center;
      color:var(--muted);
      font-size:14px;
      margin-top:2px;
    }
    .kcheck.done{
      background:rgba(111,202,147,.14);
      border-color:rgba(111,202,147,.28);
      color:#d8ffe7;
    }
    .ktask-title{
      font-size:14px;
      font-weight:800;
      letter-spacing:-.01em;
      color:var(--text);
    }
    .ktask-title.done,
    .ksub-title.done{
      text-decoration:line-through;
      opacity:.6;
    }
    .ktask-meta{
      color:var(--muted);
      font-size:12px;
      margin-top:3px;
      line-height:1.35;
    }
    .ktask-actions{
      display:grid;
      grid-template-columns:1fr;
      gap:8px;
      margin-top:12px;
    }
    .ksub-wrap{
      margin-top:12px;
      padding-left:12px;
      border-left:1px solid rgba(255,255,255,.08);
      display:grid;
      gap:10px;
    }
    .ksub{
      border:1px solid rgba(255,255,255,.06);
      background:rgba(255,255,255,.014);
      border-radius:12px;
      padding:10px;
    }
    .ksub-title{
      font-size:13px;
      font-weight:700;
      color:var(--text);
    }
    .ksub-actions{
      display:grid;
      grid-template-columns:1fr;
      gap:8px;
      margin-top:10px;
    }
    @media (min-width: 700px){
      .klist-actions,
      .khead-actions,
      .ktask-actions,
      .ksub-actions{
        grid-template-columns:repeat(2, minmax(0, 1fr));
      }
    }
    @media (max-width: 640px){
      .klist-card,.ktask,.ksub{padding:11px}
      .klist-icon{width:32px;height:32px;min-width:32px}
      .klist-name{font-size:14px}
      .kprogress{margin-top:8px}
      .badge{font-size:11px;padding:0 8px;min-height:24px}
      .kmeta{font-size:12px;margin-top:8px}
      .ksub-wrap{gap:8px;padding-left:10px}
      .task-group summary{padding:11px 12px}
      .task-group-body{padding:8px}
      .ktask-row,.ksub-row{gap:8px}
      .ktask-meta,.task-group-sub,.audit-note{font-size:11px}
      .ktask-title{font-size:13px}
      .ksub-title{font-size:12px}
      .kcheck{width:24px;height:24px;min-width:24px;font-size:12px}
    }


    html,body{
      background:#070b12 !important;
      overscroll-behavior:none;
    }
    body{
      min-height:100dvh;
      min-height:100svh;
      padding-top:env(safe-area-inset-top,0px);
      padding-bottom:env(safe-area-inset-bottom,0px);
    }
    .app{
      position:relative;
      min-height:100dvh;
      min-height:100svh;
      background:transparent;
      isolation:isolate;
    }
    .app::before{
      content:"";
      position:fixed;
      inset:0;
      z-index:-1;
      background:
        radial-gradient(circle at top left, rgba(212,176,106,.08), transparent 26%),
        radial-gradient(circle at top right, rgba(112,154,255,.06), transparent 22%),
        linear-gradient(180deg,#070b12,#0b111a 60%,#070b12);
    }

</style>
</head>
<body>
<div class="app">
  <div class="drawer-backdrop" id="backdrop" onclick="closeDrawer()"></div>

  <aside class="drawer" id="drawer">
    <div class="drawer-brand">
      <div class="small">Dashboard</div>
      <div class="big">Casa Cara</div>
    </div>

    <nav class="nav">
      <button class="nav-btn active" data-page="dashboard" onclick="openPage('dashboard'); closeDrawer();">
        <span class="nav-left"><span class="nav-icon">⌂</span><span class="nav-label">Dashboard</span></span>
      </button>

      <button class="nav-btn" id="toggle-algemeen" onclick="toggleGroup('algemeen')">
        <span class="nav-left"><span class="nav-icon">A</span><span class="nav-label">Algemeen</span></span>
        <span class="nav-caret">›</span>
      </button>
      <div class="sub-list" id="group-algemeen">
        <button class="sub-btn" data-page="algemeen-dashboard" onclick="openPage('algemeen-dashboard'); closeDrawer();">Overzicht</button>
        <button class="sub-btn" data-page="diensten" onclick="openPage('diensten'); closeDrawer();">Diensten</button>
        <button class="sub-btn admin-only" data-page="dienstsoorten" onclick="openPage('dienstsoorten'); closeDrawer();">Dienstsoorten</button>
        <button class="sub-btn" data-page="fooienpot" onclick="openPage('fooienpot'); closeDrawer();">Fooienpot</button>
        
      </div>

      <button class="nav-btn" id="toggle-keuken" onclick="toggleGroup('keuken')">
        <span class="nav-left"><span class="nav-icon">K</span><span class="nav-label">Keuken</span></span>
        <span class="nav-caret">›</span>
      </button>
      <div class="sub-list" id="group-keuken">
        <button class="sub-btn" data-page="keuken-overzicht" onclick="openPage('keuken-overzicht'); closeDrawer();">Overzicht</button>
        <button class="sub-btn" data-page="keuken-takenlijsten" onclick="openPage('keuken-takenlijsten'); closeDrawer();">Takenlijsten</button>
        <button class="sub-btn" data-page="keuken-recepten" onclick="openPage('keuken-recepten'); closeDrawer();">Recepten</button>
      </div>

      <button class="nav-btn" id="toggle-bar" onclick="toggleGroup('bar')">
        <span class="nav-left"><span class="nav-icon">B</span><span class="nav-label">Bar</span></span>
        <span class="nav-caret">›</span>
      </button>
      <div class="sub-list" id="group-bar">
        <button class="sub-btn" data-page="bar-overzicht" onclick="openPage('bar-overzicht'); closeDrawer();">Overzicht</button>
        <button class="sub-btn" data-page="bar-koelingen" onclick="openPage('bar-koelingen'); closeDrawer();">Koelingen</button>
        <button class="sub-btn" data-page="bar-takenlijsten" onclick="openPage('bar-takenlijsten'); closeDrawer();">Takenlijsten</button>
        <button class="sub-btn admin-only" data-page="bar-productsoorten" onclick="openPage('bar-productsoorten'); closeDrawer();">Productsoorten</button>
        <button class="sub-btn admin-only" data-page="bar-locaties" onclick="openPage('bar-locaties'); closeDrawer();">Locaties</button>
        <button class="sub-btn" data-page="bar-oplijst" onclick="openPage('bar-oplijst'); closeDrawer();">Op / niet op voorraad</button>
        <button class="sub-btn" data-page="bar-bijvullen" onclick="openPage('bar-bijvullen'); closeDrawer();">Bijvuloverzicht</button>
      </div>
    </nav>

    <div class="logout-wrap">
      <button class="home-btn admin-only" onclick="openPage('gebruikers'); closeDrawer();">👥 Medewerkers</button>
      <a class="logout-btn" href="/casa-cara-logout">⎋ Uitloggen</a>
    </div>
  </aside>

  <header class="topbar">
    <button class="menu-btn" onclick="toggleDrawer()" aria-label="Menu openen"><span></span></button>
    <div class="topbar-text">
      <div class="eyebrow" id="topKicker">Dashboard</div>
      <div class="title" id="topTitle">Casa Cara</div>
    </div>
  </header>

  <main class="layout">
    <section class="page active" id="page-dashboard">
      <div class="welcome-banner">
        <div class="welcome-kicker">Casa Cara</div>
        <h1 id="dashboardWelcome">Welkom!</h1>
        <p>Fijn dat je er bent. Hieronder vind je meteen het dashboard voor vandaag.</p>
      </div>


      <div class="bot-panel">
        <div class="bot-head">
          <div>
            <h3 class="bot-title">🤖 Casa Bot</h3>
            <div class="bot-sub">Vraag iets over bijvullen, recepten, takenlijsten, diensten of de fooienpot.</div>
          </div>
          <span class="badge accent">Nieuw</span>
        </div>
        <div class="bot-shell">
          <div class="bot-chat" id="botChat">
            <div class="bot-msg bot muted">Ik help je graag op weg. Stel hieronder een vraag over Casa Cara.</div>
          </div>
          <div class="bot-composer">
            <div class="bot-row">
              <input id="botInput" placeholder="Wat wil je vragen?" onkeydown="if(event.key==='Enter'){event.preventDefault(); askBot();}">
              <button class="btn accent" onclick="askBot()">Vraag</button>
            </div>
            <div class="bot-actions" id="botActions"></div>
            <div class="bot-status" id="botStatus"></div>
          </div>
        </div>
      </div>

      <div class="hero">
        <h1>📊 Dashboard</h1>
        <p>Een rustige startpagina met de belangrijkste info van vandaag. Tik op een blok om direct door te gaan naar de juiste pagina.</p>

        <div class="stats-grid">
          <button class="stat-card" onclick="openPage('bar-bijvullen')">
            <div class="stat-icon">!</div><div class="stat-label">Lage voorraad</div>
            <div class="stat-value" id="statLowStock">0</div>
            <div class="stat-sub">Producten onder minimum</div>
          </button>

          <button class="stat-card" onclick="openPage('bar-koelingen')">
            <div class="stat-icon">❄</div><div class="stat-label">Koelingen</div>
            <div class="stat-value" id="statCoolers">0</div>
            <div class="stat-sub">Actieve bar koelingen</div>
          </button>

          <button class="stat-card" onclick="openPage('fooienpot')">
            <div class="stat-icon">€</div><div class="stat-label">Fooienpot</div>
            <div class="stat-value" id="statTips">€ 0,00</div>
            <div class="stat-sub">Huidige stand</div>
          </button>

          <button class="stat-card" onclick="openPage('diensten')">
            <div class="stat-icon">👥</div><div class="stat-label">Diensten</div>
            <div class="stat-value" id="statShifts">0</div>
            <div class="stat-sub">Ingeplande diensten</div>
          </button>
        </div>
      </div>

      <div class="section">
        <div class="section-head">
          <h2 class="section-title">Snelle ingangen</h2>
          <div class="section-kicker">Direct door naar de juiste plek</div>
        </div>
        <div class="stats-grid" id="dashboardQuickGrid"></div>
      </div>
    </section>

    <section class="page" id="page-algemeen-dashboard">
      <div class="hero">
        <h1>📋 Algemeen overzicht</h1>
        <p>Alles wat niet specifiek bij keuken of bar hoort, op één rustige plek.</p>
      </div>
      <div class="stack">
        <div class="overview-grid" id="generalOverviewGrid"></div>
        <div class="panel">
          <div class="panel-head">
            <h3 class="panel-title">Vandaag in beeld</h3>
            <span class="badge" id="generalTodayBadge">Rustig</span>
          </div>
          <div class="mini-list" id="generalTodayList"></div>
        </div>
      </div>
    </section>

    <section class="page" id="page-diensten">
      <div class="hero">
        <h1>👥 Diensten</h1>
        <p>Overzicht van alle ingeplande diensten uit je huidige data.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Geplande diensten</h3>
          <button class="btn accent" id="newDienstBtn" onclick="openDienstModal()">Nieuwe dienst</button>
        </div>
        <div class="list" id="dienstenList"></div>
      </div>
    </section>

    <section class="page admin-only-page" id="page-dienstsoorten">
      <div class="hero">
        <h1>🗂 Dienstsoorten</h1>
        <p>Beheer hier de soorten diensten die je later via een dropdown kunt kiezen.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <div style="display:flex;align-items:center;gap:10px">
            <div class="stat-icon">☰</div>
            <h3 class="panel-title">Dienstsoorten</h3>
          </div>
          <button class="btn accent admin-only-action" onclick="openDienstTypeModal()">Dienstsoort toevoegen</button>
        </div>
        <div class="list" id="dienstTypesList"></div>
      </div>
    </section>

    <section class="page" id="page-fooienpot">
      <div class="hero">
        <h1>💰 Fooienpot</h1>
        <p id="tipsPageIntro">De huidige stand uit je bestaande Casa Cara data.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h3 class="panel-title" id="tipsPageTitle">Stand</h3>
          <div class="actions">
            <span class="badge accent" id="tipsPageAmount">€ 0,00</span>
            <button class="btn accent" onclick="openTipsModal()">Aanpassen</button>
          </div>
        </div>
        <div class="item-sub" id="tipsPageSub">Deze pagina is nu ook direct bewerkbaar, zonder terug te vallen op de oude alles-in-één pagina.</div>
      </div>
    </section>

    <section class="page admin-only-page" id="page-gebruikers">
      <div class="hero"><h1>👥 Medewerkers</h1><p>Alleen admin kan Casa Cara medewerkers en codes beheren.</p></div>
      <div class="panel"><div class="panel-head"><h3 class="panel-title">Medewerkers</h3><button class="btn accent admin-only-action" onclick="openUserModal()">Medewerker toevoegen</button></div><div class="list" id="usersList"></div></div>
    </section>

    <section class="page" id="page-keuken-overzicht">
      <div class="hero">
        <h1>🍳 Keuken</h1>
        <p>De keuken krijgt dezelfde rustige structuur als Bar. Je takenlijsten en recepten krijgen een eigen vaste plek, zodat alles overzichtelijk blijft.</p>
      </div>
      <div class="stack">
        <div class="overview-grid" id="kitchenOverviewGrid"></div>
        <div class="panel">
          <div class="panel-head">
            <h3 class="panel-title">Laatste activiteit</h3>
            <span class="badge accent" id="kitchenActivityBadge">0 items</span>
          </div>
          <div class="mini-list" id="kitchenActivityList"></div>
        </div>
      </div>
    </section>

    <section class="page" id="page-keuken-takenlijsten">
      <div class="hero">
        <h1>☑ Keuken · Takenlijsten</h1>
        <p>Kies een lijst om hem rustig te openen. Zo blijft dit scherm schoon en overzichtelijk.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Takenlijsten</h3>
          <button class="btn accent admin-only-action" onclick="openKitchenListModal()">Takenlijst toevoegen</button>
        </div>
        <div class="list" id="kitchenLists"></div>
      </div>
    </section>

    <section class="page" id="page-keuken-takenlijst-detail">
      <div class="hero">
        <h1 id="kitchenDetailTitle">☑ Takenlijst</h1>
        <p>Werk deze lijst stap voor stap af. De lijst blijft bestaan, maar de vinkjes resetten per nieuwe dag.</p>
      </div>
      <div class="panel">
        <div id="kitchenDetailSummary"></div>
        <div class="panel-head">
          <h3 class="panel-title">Taken</h3>
          <div class="actions">
            <button class="btn" onclick="openPage('keuken-takenlijsten')">Terug naar lijsten</button>
            <button class="btn accent admin-only-action" onclick="openKitchenManagePage(window.currentKitchenListId)">⚙️ Beheer</button>
          </div>
        </div>
        <div class="list" id="kitchenDetailList"></div>
      </div>
    </section>

    <section class="page admin-only-page" id="page-keuken-takenlijst-beheer">
      <div class="hero">
        <h1 id="kitchenManageTitle">⚙️ Takenlijst beheren</h1>
        <p>Pas hier alleen de inhoud van deze takenlijst aan. De checklist zelf blijft rustig voor gebruik op de werkvloer.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Beheer</h3>
          <div class="actions">
            <button class="btn" onclick="openPage('keuken-takenlijst-detail')">Terug naar checklist</button>
            <button class="btn accent admin-only-action" onclick="openKitchenTaskModal(window.currentKitchenListId)">+ Taak toevoegen</button>
          </div>
        </div>
        <div class="list" id="kitchenManageList"></div>
      </div>
    </section>

    <section class="page" id="page-keuken-recepten">
      <div class="hero">
        <h1>🍝 Keuken · Recepten</h1>
        <p>Bouw je eigen receptenbank op met ingrediënten, vindplaats en stappenplan.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Recepten</h3>
          <button class="btn accent admin-only-action" onclick="openRecipeModal()">Recept toevoegen</button>
        </div>
        <div class="list" id="recipesList"></div>
      </div>
    </section>

    <section class="page" id="page-bar-overzicht">
      <div class="hero">
        <h1>🍸 Bar overzicht</h1>
        <p>De bar-sectie is nu opgesplitst in losse pagina’s met beheeracties op de juiste plek.</p>
      </div>
      <div class="stack">
        <div class="overview-grid" id="barOverviewGrid"></div>
        <div class="panel">
          <div class="panel-head">
            <h3 class="panel-title">Actuele focus</h3>
            <span class="badge warn" id="barFocusBadge">0 acties</span>
          </div>
          <div class="mini-list" id="barFocusList"></div>
        </div>
      </div>
    </section>

    <section class="page" id="page-bar-takenlijsten">
      <div class="hero">
        <h1>☑ Bar · Takenlijsten</h1>
        <p>Kies een lijst voor je barshift. Compact, snel af te vinken en fijn op telefoon.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Takenlijsten</h3>
          <button class="btn accent admin-only-action" onclick="openBarListModal()">Takenlijst toevoegen</button>
        </div>
        <div class="list" id="barTaskLists"></div>
      </div>
    </section>

    <section class="page" id="page-bar-takenlijst-detail">
      <div class="hero">
        <h1 id="barDetailTitle">☑ Bar checklist</h1>
        <p>Werk deze barlijst stap voor stap af. De lijst blijft staan, de vinkjes resetten per nieuwe dag.</p>
      </div>
      <div class="panel">
        <div id="barDetailSummary"></div>
        <div class="panel-head">
          <h3 class="panel-title">Taken</h3>
          <div class="actions">
            <button class="btn" onclick="openPage('bar-takenlijsten')">Terug naar lijsten</button>
            <button class="btn accent admin-only-action" onclick="openBarManagePage(window.currentBarListId)">⚙️ Beheer</button>
          </div>
        </div>
        <div class="list" id="barDetailList"></div>
      </div>
    </section>

    <section class="page admin-only-page" id="page-bar-takenlijst-beheer">
      <div class="hero">
        <h1 id="barManageTitle">⚙️ Bar takenlijst beheren</h1>
        <p>Pas hier alleen de inhoud aan. De checklist op de werkvloer blijft compact en rustig.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Beheer</h3>
          <div class="actions">
            <button class="btn" onclick="openPage('bar-takenlijst-detail')">Terug naar checklist</button>
            <button class="btn accent admin-only-action" onclick="openBarTaskModal(window.currentBarListId)">+ Taak toevoegen</button>
          </div>
        </div>
        <div class="list" id="barManageList"></div>
      </div>
    </section>

    <section class="page" id="page-bar-koelingen">
      <div class="hero">
        <h1>❄️ Bar · Koelingen</h1>
        <p>Los overzicht per koeling, met aantallen, status en beheerknoppen.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Koelingen</h3>
          <button class="btn accent admin-only-action" onclick="openKoelingModal()">Koeling toevoegen</button>
        </div>
        <div class="actions" style="margin-bottom:12px">
          <select id="koelingFilterLocatie" class="btn" onchange="renderCoolers()"></select>
          <select id="koelingFilterSoort" class="btn" onchange="renderCoolers()"></select>
        </div>
        <div class="list" id="coolersList"></div>
      </div>
    </section>

    <section class="page admin-only-page" id="page-bar-productsoorten">
      <div class="hero">
        <h1>🏷️ Bar · Productsoorten</h1>
        <p>Je productsoorten in een vaste volgorde, met de gekoppelde locatie erbij.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Productsoorten</h3>
          <button class="btn accent admin-only-action" onclick="openTypeModal()">Productsoort toevoegen</button>
        </div>
        <div class="list" id="typesList"></div>
      </div>
    </section>

    <section class="page admin-only-page" id="page-bar-locaties">
      <div class="hero">
        <h1>📍 Bar · Locaties</h1>
        <p>Alle locaties overzichtelijk onder elkaar, nu ook direct bewerkbaar.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Locaties</h3>
          <button class="btn accent admin-only-action" onclick="openLocationModal()">Locatie toevoegen</button>
        </div>
        <div class="list" id="locationsList"></div>
      </div>
    </section>

    <section class="page" id="page-bar-oplijst">
      <div class="hero">
        <h1>🚫 Bar · Op / niet op voorraad</h1>
        <p>Snelle lijst van producten die aandacht nodig hebben.</p>
      </div>
      <div class="panel"><div class="list" id="stockAlertsList"></div></div>
    </section>

    <section class="page" id="page-bar-bijvullen">
      <div class="hero">
        <h1>📦 Bar · Bijvuloverzicht</h1>
        <p>Alles wat nu direct onder minimum staat en bijgevuld moet worden.</p>
      </div>
      <div class="panel">
        <div class="actions" style="margin-bottom:12px">
          <select id="fillFilterLocatie" class="btn" onchange="renderFill()"></select>
          <select id="fillFilterSoort" class="btn" onchange="renderFill()"></select>
        </div>
        <div style="margin-bottom:10px">
<button id="refillSwitchBtn" class="btn" onclick="openRefillSelector()">Koeling kiezen</button>
</div>
<div class="list" id="fillList"></div>
      </div>
    </section>
    <section class="page" id="page-bar-koeling-detail">
      <div class="hero">
        <h1 id="koelingDetailTitle">Koeling</h1>
        <p>Bekijk alle producten in deze koeling, pas voorraad snel aan en voeg direct nieuwe producten toe.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Producten</h3>
          <div class="actions">
            <button class="btn" onclick="openPage('bar-koelingen')">Terug naar koelingen</button>
            <button class="btn accent admin-only-action" onclick="openProductModal(window.currentKoelingId)">Product toevoegen</button>
          </div>
        </div>
        <div class="actions" style="margin-bottom:12px">
          <select id="koelingDetailFilterLocatie" class="btn" onchange="renderKoelingDetail()"></select>
          <select id="koelingDetailFilterSoort" class="btn" onchange="renderKoelingDetail()"></select>
        </div>
        <div class="list" id="koelingDetailList"></div>
      </div>
    </section>
  </main>
</div>

<div class="modal-backdrop" id="modalWrap">
  <div class="modal" role="dialog" aria-modal="true">
    <div class="modal-head">
      <div>
        <h3 class="modal-title" id="modalTitle">Bewerken</h3>
        <div class="modal-sub" id="modalSub">Pas hier de gegevens aan.</div>
      </div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div id="modalBody"></div>
  </div>
</div>

<div class="toast-wrap" id="toastWrap"></div>

<script>
  let appData = { bar: { koelingen: [], fill_items: [] }, bar_tasks: { lists: [] }, general: { fooienpot: 0, diensten: [] }, kitchen: { lists: [] }, recipes: { items: [] }, types: [], locations: [] };
  let currentPage = 'dashboard';
  let currentKoelingId = null;
  let currentKitchenListId = null;
  let currentBarListId = null;
  const groupState = { algemeen:false, keuken:false, bar:false };
  window.currentKoelingId = null;
  window.currentKitchenListId = null;
  window.currentBarListId = null;

  function euro(value){
    const num = Number(value || 0);
    return new Intl.NumberFormat('nl-NL', { style: 'currency', currency: 'EUR' }).format(num);
  }

  function setChecked(id, value){
    const el = document.getElementById(id);
    if (el) el.checked = !!value;
  }

  function setText(id, value){
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }
  function pageId(name){ return 'page-' + name; }
  function safeArray(value){ return Array.isArray(value) ? value : []; }
  function currentRole(){ return appData?.auth?.role || ''; }
  function isAdmin(){ return currentRole() === 'admin'; }
  function adminOnly(html){ return isAdmin() ? html : ''; }
  function hasPermission(key){ return isAdmin() ? true : !!(appData?.auth?.permissions || {})[key]; }
  function employeeForbiddenPages(){ return ['dienstsoorten','gebruikers','keuken-takenlijst-beheer','bar-takenlijst-beheer','bar-productsoorten','bar-locaties']; }
  function pageAllowed(page){
    if (isAdmin()) return true;
    const map = {
      'dashboard': true,
      'algemeen-dashboard': hasPermission('access_general'),
      'diensten': hasPermission('access_general') && hasPermission('manage_diensten'),
      'dienstsoorten': hasPermission('manage_dienst_types'),
      'fooienpot': hasPermission('access_general') && hasPermission('manage_tips'),
      'gebruikers': hasPermission('manage_users'),
      'keuken-overzicht': hasPermission('access_kitchen'),
      'keuken-takenlijsten': hasPermission('access_kitchen') && hasPermission('use_tasklists'),
      'keuken-takenlijst-detail': hasPermission('access_kitchen') && hasPermission('use_tasklists'),
      'keuken-takenlijst-beheer': hasPermission('access_kitchen') && hasPermission('manage_tasklists'),
      'keuken-recepten': hasPermission('access_kitchen') && hasPermission('view_recipes'),
      'bar-overzicht': hasPermission('access_bar'),
      'bar-koelingen': hasPermission('access_bar') && (hasPermission('adjust_stock') || hasPermission('manage_products') || hasPermission('manage_coolers')),
      'bar-takenlijsten': hasPermission('access_bar') && hasPermission('use_tasklists'),
      'bar-takenlijst-detail': hasPermission('access_bar') && hasPermission('use_tasklists'),
      'bar-takenlijst-beheer': hasPermission('access_bar') && hasPermission('manage_tasklists'),
      'bar-productsoorten': hasPermission('manage_types'),
      'bar-locaties': hasPermission('manage_locations'),
      'bar-oplijst': hasPermission('access_bar') && hasPermission('view_oplijst'),
      'bar-bijvullen': hasPermission('access_bar') && hasPermission('view_bijvullen'),
      'bar-koeling-detail': hasPermission('access_bar') && (hasPermission('adjust_stock') || hasPermission('manage_products') || hasPermission('manage_coolers')),
    };
    return !!map[page];
  }

  function toast(message, kind='success'){
    const wrap = document.getElementById('toastWrap');
    const div = document.createElement('div');
    div.className = 'toast ' + kind;
    div.textContent = message;
    wrap.appendChild(div);
    setTimeout(() => div.remove(), 2800);
  }

  function closeDrawer(){
    document.getElementById('drawer').classList.remove('open');
    document.getElementById('backdrop').classList.remove('open');
  }
  function openDrawer(){
    document.getElementById('drawer').classList.add('open');
    document.getElementById('backdrop').classList.add('open');
  }
  function toggleDrawer(){
    const drawer = document.getElementById('drawer');
    if (drawer.classList.contains('open')) closeDrawer();
    else openDrawer();
  }

  function setGroupState(group, open){
    const list = document.getElementById('group-' + group);
    const toggle = document.getElementById('toggle-' + group);
    if (!list || !toggle) return;
    const isOpen = !!open;
    groupState[group] = isOpen;
    list.classList.toggle('open', isOpen);
    toggle.classList.toggle('expanded', isOpen);
    list.style.display = isOpen ? 'grid' : '';
  }

  function toggleGroup(group){
    setGroupState(group, !groupState[group]);
  }

  function activateNav(page){
    document.querySelectorAll('.nav-btn[data-page], .sub-btn[data-page]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.page === page);
    });
  }

  function applyPermissions(){
    document.querySelectorAll('.admin-only, .admin-only-page, .admin-only-action').forEach(el => { el.style.display = isAdmin() ? '' : 'none'; });
    document.querySelectorAll('.nav-btn[data-page], .sub-btn[data-page]').forEach(btn => {
      btn.style.display = pageAllowed(btn.dataset.page) ? '' : 'none';
    });
    const sectionVisibility = {
      algemeen: isAdmin() || hasPermission('access_general'),
      keuken: isAdmin() || hasPermission('access_kitchen'),
      bar: isAdmin() || hasPermission('access_bar'),
    };
    Object.entries(sectionVisibility).forEach(([key, visible]) => {
      const toggle = document.getElementById('toggle-' + key);
      const group = document.getElementById('group-' + key);
      if (toggle) toggle.style.display = visible ? '' : 'none';
      if (group) group.style.display = visible ? (groupState[key] ? 'grid' : '') : 'none';
      if (!visible && group) {
        group.classList.remove('open');
        groupState[key] = false;
      }
      if (!visible && toggle) toggle.classList.remove('expanded');
    });
    document.querySelectorAll('.page').forEach(el => {
      const pageName = (el.id || '').replace('page-', '');
      el.style.display = pageAllowed(pageName) ? '' : 'none';
    });
    const employeeBtn = document.querySelector('.home-btn');
    if (employeeBtn) employeeBtn.style.display = hasPermission('manage_users') ? '' : 'none';
    if (!pageAllowed(currentPage)) currentPage = 'dashboard';
  }

  function pageMeta(page){
    const map = {
      'dashboard': ['Dashboard', 'Casa Cara'],
      'algemeen-dashboard': ['Algemeen', 'Overzicht'],
      'diensten': ['Algemeen', 'Diensten'],
      'dienstsoorten': ['Algemeen', 'Dienstsoorten'],
      'fooienpot': ['Algemeen', 'Fooienpot'],
      'gebruikers': ['Casa Cara', 'Medewerkers'],
      'keuken-overzicht': ['Keuken', 'Overzicht'],
      'keuken-takenlijsten': ['Keuken', 'Takenlijsten'],
      'keuken-takenlijst-detail': ['Keuken', 'Takenlijst'],
      'keuken-takenlijst-beheer': ['Keuken', 'Takenlijst beheren'],
      'keuken-recepten': ['Keuken', 'Recepten'],
      'bar-overzicht': ['Bar', 'Overzicht'],
      'bar-koelingen': ['Bar', 'Koelingen'],
      'bar-takenlijsten': ['Bar', 'Takenlijsten'],
      'bar-takenlijst-detail': ['Bar', 'Takenlijst'],
      'bar-takenlijst-beheer': ['Bar', 'Takenlijst beheren'],
      'bar-productsoorten': ['Bar', 'Productsoorten'],
      'bar-locaties': ['Bar', 'Locaties'],
      'bar-oplijst': ['Bar', 'Op / niet op voorraad'],
      'bar-bijvullen': ['Bar', 'Bijvuloverzicht'],
      'bar-koeling-detail': ['Bar', 'Koeling detail'],
    };
    return map[page] || ['Casa Cara', 'Overzicht'];
  }

  function openPage(page){
    if (!isAdmin() && employeeForbiddenPages().includes(page)) page = 'dashboard';
    currentPage = page;
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const el = document.getElementById(pageId(page));
    if (el) el.classList.add('active');
    const [kicker, title] = pageMeta(page);
    setText('topKicker', kicker);
    setText('topTitle', title);
    activateNav(page);
    if (page.startsWith('algemeen')) setGroupState('algemeen', true);
    if (page.startsWith('keuken')) setGroupState('keuken', true);
    if (page.startsWith('bar')) setGroupState('bar', true);
    window.scrollTo({ top: 0, behavior: 'instant' });
    if(page === 'bar-bijvullen' && !window.selectedCooler){
      openRefillSelector();
    }
  }

  function openModal(title, sub, bodyHtml){
    setText('modalTitle', title);
    setText('modalSub', sub || '');
    document.getElementById('modalBody').innerHTML = bodyHtml;
    document.getElementById('modalWrap').classList.add('open');
  }
  function closeModal(){
    document.getElementById('modalWrap').classList.remove('open');
    document.getElementById('modalBody').innerHTML = '';
  }

  async function postJSON(url, data){
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data || {})
    });
    const json = await res.json();
    if (!res.ok || json.ok === false){
      throw new Error(json.message || 'Er ging iets mis.');
    }
    return json;
  }

  function renderList(id, items, renderer, emptyText){
    const wrap = document.getElementById(id);
    if (!wrap) return;
    if (!items.length){
      wrap.innerHTML = `<div class="empty">${emptyText}</div>`;
      return;
    }
    wrap.innerHTML = items.map(renderer).join('');
  }


  function getAllTypeNames(){
    return safeArray(appData.types).map(t => t.naam).filter(Boolean);
  }

  function getAllLocationNames(){
    return safeArray(appData.locations).filter(Boolean);
  }

  function fillSelectOptions(selectId, items, allLabel){
    const el = document.getElementById(selectId);
    if (!el) return;
    const current = el.value || '';
    const options = ['<option value="">' + allLabel + '</option>']
      .concat(items.map(item => `<option value="${item}">${item}</option>`));
    el.innerHTML = options.join('');
    if ([...el.options].some(o => o.value === current)) el.value = current;
  }

  function initFilters(){
    const locations = getAllLocationNames();
    const types = getAllTypeNames();
    fillSelectOptions('koelingFilterLocatie', locations, 'Alle locaties');
    fillSelectOptions('koelingFilterSoort', types, 'Alle productsoorten');
    fillSelectOptions('fillFilterLocatie', locations, 'Alle locaties');
    fillSelectOptions('fillFilterSoort', types, 'Alle productsoorten');
    fillSelectOptions('koelingDetailFilterLocatie', locations, 'Alle locaties');
    fillSelectOptions('koelingDetailFilterSoort', types, 'Alle productsoorten');
  }

  function confirmAction(title, sub, buttonText, actionJs, danger=true){
    openModal(
      title,
      sub,
      `
        <div class="form-grid">
          <div class="item-sub">Controleer even of dit echt is wat je wilt doen.</div>
          <div class="form-actions">
            <button class="btn" onclick="closeModal()">Annuleren</button>
            <button class="btn ${danger ? 'danger' : 'accent'}" onclick="${actionJs}">${buttonText}</button>
          </div>
        </div>
      `
    );
  }

  function doConfirmed(actionName, ...args){
    closeModal();
    return window[actionName](...args);
  }

  function matchesTypeAndLocation(product, typeFilter, locationFilter){
    const soort = product.soort || 'Overig';
    const locatie = appData.types.find(t => t.naam === soort)?.locatie || '-';
    const typeOk = !typeFilter || soort === typeFilter;
    const locOk = !locationFilter || locatie === locationFilter;
    return typeOk && locOk;
  }

  function openKoelingDetail(koelingId){
    currentKoelingId = koelingId;
    window.currentKoelingId = koelingId;
    const koeling = safeArray(appData.bar.koelingen).find(k => k.id === koelingId) || {};
    setText('koelingDetailTitle', koeling.naam || 'Koeling');
    openPage('bar-koeling-detail');
    renderKoelingDetail();
  }

  async function saveQuickStock(koelingId, productId){
    const input = document.getElementById('quick-stock-' + productId);
    const koeling = safeArray(appData.bar.koelingen).find(k => k.id === koelingId) || {};
    const product = safeArray(koeling.producten).find(p => p.id === productId) || {};
    if (!input || !product) return;
    try{
      await postJSON('/api/manage/product-save', {
        koeling_id: koelingId,
        product_id: productId,
        naam: product.naam,
        voorraad: input.value,
        minimum: product.minimum || 0,
        soort: product.soort || 'Overig',
        op: !!product.op
      });
      await loadData();
      toast('Voorraad bijgewerkt');
    }catch(err){ toast(err.message, 'error'); }
  }

  function renderKoelingDetail(){
    const koeling = safeArray(appData.bar.koelingen).find(k => k.id === currentKoelingId) || {};
    const products = safeArray(koeling.producten);
    const typeFilter = document.getElementById('koelingDetailFilterSoort')?.value || '';
    const locationFilter = document.getElementById('koelingDetailFilterLocatie')?.value || '';
    const filtered = products.filter(p => matchesTypeAndLocation(p, typeFilter, locationFilter));

    renderList(
      'koelingDetailList',
      filtered,
      (product) => {
        const soort = product.soort || 'Overig';
        const locatie = appData.types.find(t => t.naam === soort)?.locatie || '-';
        const low = Number(product.voorraad || 0) < Number(product.minimum || 0);
        return `
          <div class="list-item">
            <div class="item-top">
              <div>
                <div class="item-title">${product.naam || 'Product'}</div>
                <div class="item-sub">${soort} · ${locatie}</div>
              </div>
              <span class="badge ${product.op ? 'warn' : (low ? 'warn' : 'good')}">${product.op ? 'OP' : `${product.voorraad || 0} / min ${product.minimum || 0}`}</span>
            </div>
            <div class="meta-row">
              <span class="meta-chip">Minimum: ${product.minimum || 0}</span>
              <span class="meta-chip">Voorraad snel aanpassen</span>
            </div>
            <div class="item-actions">
              <button class="btn" onclick="adjustStock('${koeling.id}','${product.id}',-1)">-1</button>
              <input id="quick-stock-${product.id}" class="btn" type="number" value="${product.voorraad ?? 0}" style="width:90px">
              <button class="btn" onclick="adjustStock('${koeling.id}','${product.id}',1)">+1</button>
              <button class="btn accent" onclick="saveQuickStock('${koeling.id}','${product.id}')">Opslaan</button>
            </div>
            <div class="item-actions">
              <button class="btn" onclick="openProductInfo('${koeling.id}','${product.id}')">Productinfo</button>
              ${adminOnly(`<button class=\"btn accent\" onclick=\"openProductModal('${koeling.id}','${product.id}')\">Bewerken</button><button class=\"btn danger\" onclick=\"confirmAction('Product verwijderen','Weet je zeker dat je dit product wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteProduct','${koeling.id}','${product.id}')&quot;)\">Verwijderen</button>`)}
            </div>
          </div>
        `;
      },
      'Nog geen producten gevonden in deze koeling.'
    );
  }

  async function adjustStock(koelingId, productId, delta){
    const input = document.getElementById('quick-stock-' + productId);
    if (!input) return;
    const current = Number(input.value || 0);
    input.value = Math.max(0, current + delta);
    await saveQuickStock(koelingId, productId);
  }

  function openProductInfo(koelingId, productId){
    const koeling = safeArray(appData.bar.koelingen).find(k => k.id === koelingId) || {};
    const product = safeArray(koeling.producten).find(p => p.id === productId) || {};
    const soort = product.soort || 'Overig';
    const locatie = appData.types.find(t => t.naam === soort)?.locatie || '-';
    const low = Number(product.voorraad || 0) < Number(product.minimum || 0);

    openModal(
      'Productinfo',
      `${product.naam || 'Product'} · ${koeling.naam || 'Koeling'}`,
      `
        <div class="stack">
          <div class="panel">
            <div class="panel-head">
              <h3 class="panel-title">${product.naam || 'Product'}</h3>
              <span class="badge ${product.op ? 'warn' : (low ? 'warn' : 'good')}">${product.op ? 'OP' : (low ? 'Laag' : 'Op voorraad')}</span>
            </div>
            <div class="list">
              <div class="list-item"><div class="item-title">Koeling</div><div class="item-sub">${koeling.naam || '-'}</div></div>
              <div class="list-item"><div class="item-title">Productsoort</div><div class="item-sub">${soort}</div></div>
              <div class="list-item"><div class="item-title">Locatie</div><div class="item-sub">${locatie}</div></div>
              <div class="list-item"><div class="item-title">Voorraad</div><div class="item-sub">${product.voorraad ?? 0}</div></div>
              <div class="list-item"><div class="item-title">Minimum</div><div class="item-sub">${product.minimum ?? 0}</div></div>
            </div>
            <div class="form-actions">
              <button class="btn" onclick="closeModal()">Sluiten</button>
              ${adminOnly(`<button class=\"btn accent\" onclick=\"closeModal(); openProductModal('${koeling.id}','${product.id}')\">Bewerken</button>`)}
            </div>
          </div>
        </div>
      `
    );
  }



  const botState = {
    lastAction: null,
    awaitingChoice: false,
    askedOnce: false,
  };

  function appendBotMessage(text, role='bot', muted=false){
    const chat = document.getElementById('botChat');
    if (!chat) return;
    const el = document.createElement('div');
    el.className = `bot-msg ${role}${muted ? ' muted' : ''}`;
    el.textContent = text;
    chat.appendChild(el);
    requestAnimationFrame(() => { chat.scrollTop = chat.scrollHeight; });
  }

  function hideBotChips(){
    const chips = document.getElementById('botChips');
    if (chips) chips.classList.add('hidden');
  }

  function setBotStatus(text=''){
    const status = document.getElementById('botStatus');
    if (!status) return;
    status.textContent = text || '';
    status.classList.toggle('visible', !!text);
  }

  function renderBotActions(actions=[]){
    const wrap = document.getElementById('botActions');
    if (!wrap) return;
    wrap.innerHTML = '';
    actions.forEach(action => {
      const btn = document.createElement('button');
      btn.className = 'bot-action';
      btn.textContent = action.label || action.value || 'Ga verder';
      btn.onclick = () => {
        if (action.type === 'send_text') {
          askBot(action.value || action.label || 'Ja');
          return;
        }
        if (action.type === 'open_page') {
          if (action.page) openPage(action.page);
          appendBotMessage(action.after_text || 'Ik heb die pagina voor je geopend.', 'bot');
          wrap.innerHTML = '';
        }
      };
      wrap.appendChild(btn);
    });
  }

  async function askBot(prefill){
    const input = document.getElementById('botInput');
    const question = (typeof prefill === 'string' && prefill) ? prefill : (input?.value || '').trim();
    if (!question){
      setBotStatus('Typ eerst iets, bijvoorbeeld: hoi, wat moet ik bijvullen of welke takenlijsten zijn er?');
      input?.focus();
      return;
    }
    if (input) input.value = '';
    botState.askedOnce = true;
    hideBotChips();
    setBotStatus('Casa Bot kijkt even mee…');
    appendBotMessage(question, 'user');
    renderBotActions([]);
    try{
      const res = await fetch('/api/bot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, last_action: botState.lastAction })
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.message || 'Er ging iets mis met Casa Bot.');
      appendBotMessage(data.answer || 'Ik heb nu even geen antwoord gevonden.', 'bot');
      botState.lastAction = data.pending_action || null;
      botState.awaitingChoice = !!data.pending_action;
      renderBotActions(Array.isArray(data.actions) ? data.actions : []);
      setBotStatus(data.hint || '');
      if (data.open_page){
        openPage(data.open_page);
      }
    }catch(err){
      appendBotMessage(err?.message || 'Er ging iets mis met Casa Bot.', 'bot');
      setBotStatus('');
    }
  }


  function renderDashboard(){
    const koelingen = safeArray(appData.bar.koelingen);
    const fill = safeArray(appData.bar.fill_items);
    const diensten = safeArray(appData.general.diensten);
    const types = safeArray(appData.types);
    const locations = safeArray(appData.locations);
    const tips = appData.general.fooienpot || 0;
    const tipLabel = appData.general.fooienpot_label || 'Fooienpot';
    const currentUserName = appData?.auth?.user_name || '';

    setText('dashboardWelcome', currentUserName ? `Welkom ${currentUserName}!` : 'Welkom!');
    setText('statLowStock', String(fill.length));
    setText('statCoolers', String(koelingen.length));
    setText('statTips', euro(tips));
    setText('statShifts', String(diensten.length));

    setText('tipsBadge', euro(tips));
    setText('dienstenBadge', `${diensten.length} gepland`);
    setText('tipsPageAmount', euro(tips));
    setText('tipsPanelTitle', tipLabel);
    setText('tipsPanelSub', isAdmin() ? 'Huidige stand van de algemene fooienpot.' : 'Dit is jouw eigen fooienpot binnen Casa Cara.');
    setText('tipsPageTitle', tipLabel);
    setText('tipsPageIntro', isAdmin() ? 'De huidige stand van de algemene fooienpot.' : 'Hier zie je jouw eigen fooienpot binnen Casa Cara.');
    setText('tipsPageSub', isAdmin() ? 'Deze pagina is nu ook direct bewerkbaar, zonder terug te vallen op de oude alles-in-één pagina.' : 'Pas hier jouw eigen fooienpot aan zonder de rest van het team te beïnvloeden.');

    setText('barOverviewCoolers', String(koelingen.length));
    setText('barOverviewTypes', String(types.length));
    setText('barOverviewLocations', String(locations.length));
    setText('barOverviewFill', String(fill.length));

    const quickCards = [];
    if (pageAllowed('bar-koelingen')) quickCards.push({label:'Bar', title:'Koelingen', sub:'Overzicht per koeling en status', page:'bar-koelingen'});
    if (pageAllowed('bar-productsoorten')) quickCards.push({label:'Bar', title:'Productsoorten', sub:'Geordend per soort en locatie', page:'bar-productsoorten'});
    if (pageAllowed('bar-locaties')) quickCards.push({label:'Bar', title:'Locaties', sub:'Opslagplekken en indeling', page:'bar-locaties'});
    if (pageAllowed('bar-bijvullen')) quickCards.push({label:'Bar', title:'Bijvullen', sub:'Wat direct aandacht nodig heeft', page:'bar-bijvullen'});
    if (pageAllowed('diensten')) quickCards.push({label:'Algemeen', title:'Diensten', sub:'Bekijk en plan je diensten', page:'diensten'});
    if (pageAllowed('fooienpot')) quickCards.push({label:'Algemeen', title:'Fooienpot', sub:'Huidige stand en snelle aanpassing', page:'fooienpot'});
    if (pageAllowed('keuken-takenlijsten')) quickCards.push({label:'Keuken', title:'Takenlijsten', sub:'Open lijsten en vink taken af', page:'keuken-takenlijsten'});
    if (pageAllowed('bar-takenlijsten')) quickCards.push({label:'Bar', title:'Takenlijsten', sub:'Open je bar-opstart en afsluit lijsten', page:'bar-takenlijsten'});
    if (pageAllowed('keuken-recepten')) quickCards.push({label:'Keuken', title:'Recepten', sub:'Open receptkaarten en ingrediënten', page:'keuken-recepten'});
    const quickGrid = document.getElementById('dashboardQuickGrid');
    if (quickGrid){
      quickGrid.innerHTML = quickCards.map(card => `
        <button class="stat-card" onclick="openPage('${card.page}')">
          <div class="stat-label">${card.label}</div>
          <div class="stat-value" style="font-size:22px">${card.title}</div>
          <div class="stat-sub">${card.sub}</div>
        </button>
      `).join('') || '<div class="empty">Er zijn nog geen snelle ingangen voor jouw rechten ingesteld.</div>';
    }
  }

  function renderCoolers(){
    const koelingen = safeArray(appData.bar.koelingen);
    const typeFilter = document.getElementById('koelingFilterSoort')?.value || '';
    const locationFilter = document.getElementById('koelingFilterLocatie')?.value || '';

    const filteredKoelingen = koelingen.filter(koeling => {
      const producten = safeArray(koeling.producten);
      if (!typeFilter && !locationFilter) return true;
      return producten.some(product => matchesTypeAndLocation(product, typeFilter, locationFilter));
    });

    renderList(
      'coolersList',
      filteredKoelingen,
      (koeling) => {
        const producten = safeArray(koeling.producten);
        const matchingProducts = producten.filter(product => matchesTypeAndLocation(product, typeFilter, locationFilter));
        const low = matchingProducts.filter(p => !p.op && Number(p.voorraad || 0) < Number(p.minimum || 0)).length;
        return `
          <div class="list-item">
            <div class="item-top" style="cursor:pointer" onclick="openKoelingDetail('${koeling.id}')">
              <div>
                <div class="item-title">${koeling.naam || 'Onbekende koeling'}</div>
                <div class="item-sub">${matchingProducts.length} zichtbare producten in deze koeling</div>
              </div>
              <span class="badge ${low > 0 ? 'warn' : 'good'}">${low > 0 ? `${low} alert${low === 1 ? '' : 's'}` : 'In orde'}</span>
            </div>            <div class="item-actions">
              <button class="btn accent" onclick="openKoelingDetail('${koeling.id}')">Open koeling</button>
              ${hasPermission('manage_coolers') || hasPermission('manage_products') ? `${hasPermission('manage_coolers') ? `<button class=\"btn accent\" onclick=\"openKoelingModal('${koeling.id}')\">Bewerken</button>` : ''}${hasPermission('manage_products') ? `<button class=\"btn\" onclick=\"openProductModal('${koeling.id}')\">Product toevoegen</button>` : ''}${hasPermission('manage_coolers') ? `<button class=\"btn danger\" onclick=\"confirmAction('Koeling verwijderen','Weet je zeker dat je deze koeling wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteKoeling','${koeling.id}')&quot;)\">Verwijderen</button>` : ''}` : ''}
            </div>
          </div>
        `;
      },
      'Nog geen koelingen gevonden voor deze filter.'
    );
  }

  function renderTypes(){
    const types = safeArray(appData.types);
    renderList(
      'typesList',
      types,
      (type) => `
        <div class="list-item">
          <div class="item-top">
            <div>
              <div class="item-title">${type.naam || 'Onbekende soort'}</div>
              <div class="item-sub">Gekoppelde locatie: ${type.locatie || '-'}</div>
            </div>
            <span class="badge accent">Soort</span>
          </div>
          ${hasPermission('manage_types') ? `<div class="item-actions"><button class="btn accent" onclick="openTypeModal('${encodeURIComponent(type.naam)}')">Bewerken</button><button class="btn danger" onclick="confirmAction('Productsoort verwijderen','Weet je zeker dat je deze productsoort wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteType','${encodeURIComponent(type.naam)}')&quot;)">Verwijderen</button></div>` : ''}
        </div>
      `,
      'Nog geen productsoorten gevonden.'
    );
  }

  function renderLocations(){
    const locations = safeArray(appData.locations);
    renderList(
      'locationsList',
      locations,
      (location) => `
        <div class="list-item">
          <div class="item-top">
            <div>
              <div class="item-title">${location}</div>
              <div class="item-sub">Beschikbare locatie binnen de huidige indeling</div>
            </div>
            <span class="badge">Locatie</span>
          </div>
          ${location === '-' ? '' : `
            ${hasPermission('manage_locations') ? `<div class="item-actions"><button class="btn accent" onclick="openLocationModal('${encodeURIComponent(location)}')">Bewerken</button><button class="btn danger" onclick="confirmAction('Locatie verwijderen','Weet je zeker dat je deze locatie wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteLocation','${encodeURIComponent(location)}')&quot;)">Verwijderen</button></div>` : ''}
          `}
        </div>
      `,
      'Nog geen locaties gevonden.'
    );
  }

  function renderStockAlerts(){
    const koelingen = safeArray(appData.bar.koelingen);
    const alerts = [];
    koelingen.forEach(koeling => {
      safeArray(koeling.producten).forEach(product => {
        if (product.op){
          alerts.push({
            koeling: koeling.naam || 'Onbekende koeling',
            koeling_id: koeling.id,
            id: product.id,
            naam: product.naam || 'Onbekend product',
            voorraad: Number(product.voorraad || 0),
            minimum: Number(product.minimum || 0),
            soort: product.soort || 'Overig'
          });
        }
      });
    });

    renderList(
      'stockAlertsList',
      alerts,
      (item) => `
        <div class="list-item">
          <div class="item-top">
            <div>
              <div class="item-title">${item.naam}</div>
              <div class="item-sub">${item.koeling} · ${item.soort}</div>
            </div>
            <span class="badge warn">OP</span>
          </div>
          <div class="meta-row">
            <span class="meta-chip">Laatste voorraad: ${item.voorraad}</span>
            <span class="meta-chip">Minimum: ${item.minimum}</span>
          </div>
          <div class="item-actions">
            <button class="btn good" onclick="markProductAvailable('${item.koeling_id}','${item.id}')">Weer op voorraad</button>
            ${hasPermission('manage_products') ? `<button class=\"btn accent\" onclick=\"openProductModal('${item.koeling_id}','${item.id}')\">Bewerken</button>` : ''}
          </div>
        </div>
      `,
      'Er zijn nu geen producten als OP gemarkeerd.'
    );
  }

  function renderFill(){
    const typeFilter = document.getElementById('fillFilterSoort')?.value || '';
    const locationFilter = document.getElementById('fillFilterLocatie')?.value || '';
    const selectedCooler = window.selectedCooler || null;

    const fill = safeArray(appData.bar.fill_items).filter(item => {
      if (!selectedCooler) return false;
      if (selectedCooler === 'all') return true;
      return item.koeling_id === selectedCooler;
    }).filter(item => {
      const typeOk = !typeFilter || item.soort === typeFilter;
      const locOk = !locationFilter || item.locatie === locationFilter;
      return typeOk && locOk;
    });

    renderList(
      'fillList',
      fill,
      (item) => `
        <div class="list-item">
          <div class="item-top">
            <div>
              <div class="item-title">${item.product}</div>
              <div class="item-sub">${item.koeling} · ${item.soort} · ${item.locatie}</div>
            </div>
            <span class="badge warn">${item.bijvullen} bijvullen</span>
          </div>
          <div class="meta-row">
            <span class="meta-chip">Nu: ${item.voorraad}</span>
            <span class="meta-chip">Min: ${item.minimum}</span>
          </div>
          <div class="item-actions">
            <button class="btn good" onclick="quickFill('${item.koeling_id}','${item.product_id}', ${item.minimum})">Zet op minimum</button>
            ${hasPermission('manage_products') ? `<button class="btn accent" onclick="openProductModal('${item.koeling_id}','${item.product_id}')">Bewerken</button>` : ''}
            <button class="btn danger" onclick="confirmAction('Product markeren als OP','Weet je zeker dat dit product op is?','Markeer als OP', &quot;doConfirmed('markProductOp','${item.koeling_id}','${item.product_id}')&quot;)">Markeer als OP</button>
          </div>
        </div>
      `,
      'Er is nu niets om bij te vullen voor deze filter.'
    );
  }

  function openRefillSelector(){
    const coolers = safeArray(appData.bar.koelingen);
    openModal(
      'Welke koeling ga je bijvullen?',
      '',
      `
        <div class="form-grid">
          ${coolers.map(c => `
            <button class="btn" onclick="selectRefillCooler('${c.id}','${c.naam}')">${c.naam}</button>
          `).join('')}
          <button class="btn accent" onclick="selectRefillCooler('all','Alle koelingen')">Alle koelingen</button>
        </div>
      `
    );
  }

  function selectRefillCooler(id, name){
    window.selectedCooler = id;
    window.selectedCoolerName = name;
    document.getElementById('refillSwitchBtn') && (document.getElementById('refillSwitchBtn').innerText = 'Koeling: ' + name);
    closeModal();
    renderFill();
  }

  function renderOverviewCards(targetId, cards, emptyText){
    const el = document.getElementById(targetId);
    if (!el) return;
    if (!cards.length){
      el.innerHTML = `<div class="overview-note">${emptyText}</div>`;
      return;
    }
    el.innerHTML = cards.map(card => `
      <div class="overview-card">
        <div class="overview-top">
          <div>
            <div class="overview-kicker">${card.kicker || 'Overzicht'}</div>
            <div class="overview-title">${card.title || '-'}</div>
            <div class="overview-sub">${card.sub || ''}</div>
          </div>
          ${card.badge ? `<span class="badge ${card.badgeClass || ''}">${card.badge}</span>` : ''}
        </div>
        ${card.meta && card.meta.length ? `<div class="meta-row">${card.meta.map(item => `<span class="meta-chip">${item}</span>`).join('')}</div>` : ''}
        <div class="overview-actions">
          ${(card.actions || []).map(action => `<button class="btn ${action.kind || ''}" onclick="${action.onclick}">${action.label}</button>`).join('')}
        </div>
      </div>
    `).join('');
  }

  function renderMiniRows(targetId, rows, emptyText){
    const el = document.getElementById(targetId);
    if (!el) return;
    if (!rows.length){
      el.innerHTML = `<div class="overview-note">${emptyText}</div>`;
      return;
    }
    el.innerHTML = rows.map(row => `
      <div class="mini-row">
        <div>
          <strong>${row.title || '-'}</strong>
          <span>${row.sub || ''}</span>
        </div>
        ${row.badge ? `<span class="badge ${row.badgeClass || ''}">${row.badge}</span>` : ''}
      </div>
    `).join('');
  }

  function renderGeneralOverview(){
    const diensten = safeArray(appData.general?.diensten);
    const cards = [];
    if (pageAllowed('fooienpot')){
      cards.push({
        kicker:'Algemeen',
        title: appData.general?.fooienpot_label || 'Fooienpot',
        sub: isAdmin() ? 'Bekijk en pas de algemene stand direct aan.' : 'Jouw persoonlijke fooienpot binnen Casa Cara.',
        badge: euro(appData.general?.fooienpot || 0),
        badgeClass:'accent',
        meta:[isAdmin() ? 'Teambreed overzicht' : 'Alleen zichtbaar voor jou'],
        actions:[{ label:'Open fooienpot', kind:'accent', onclick:`openPage('fooienpot')` }, { label:'Aanpassen', onclick:'openTipsModal()' }]
      });
    }
    if (pageAllowed('diensten')){
      const upcoming = diensten.slice().sort((a,b)=> String(a.datum||'').localeCompare(String(b.datum||'')) || String(a.tijd||'').localeCompare(String(b.tijd||''))).slice(0,3);
      cards.push({
        kicker:'Algemeen',
        title:'Diensten',
        sub: upcoming.length ? 'Je eerstvolgende diensten staan direct klaar.' : 'Plan hier diensten voor de komende dagen.',
        badge:`${diensten.length} gepland`,
        meta: upcoming.map(item => `${item.datum || 'Geen datum'}${item.tijd ? ' · ' + item.tijd : ''}`),
        actions:[{ label:'Open diensten', kind:'accent', onclick:`openPage('diensten')` }, { label:'Dienst toevoegen', onclick:'openDienstModal()' }]
      });
    }
    renderOverviewCards('generalOverviewGrid', cards, 'Je hebt binnen Algemeen nu alleen toegang tot onderdelen die voor jouw werkdag relevant zijn.');

    const rows = [];
    const sorted = diensten.slice().sort((a,b)=> String(a.datum||'').localeCompare(String(b.datum||'')) || String(a.tijd||'').localeCompare(String(b.tijd||'')));
    sorted.slice(0,4).forEach(item => rows.push({ title:item.naam || item.medewerker || 'Dienst', sub:`${item.datum || 'Geen datum'}${item.tijd ? ' · ' + item.tijd : ''}`, badge:item.rol || 'Dienst' }));
    if (pageAllowed('fooienpot')) rows.unshift({ title: appData.general?.fooienpot_label || 'Fooienpot', sub: isAdmin() ? 'Algemene stand voor het team.' : 'Jouw persoonlijke stand van vandaag.', badge: euro(appData.general?.fooienpot || 0), badgeClass:'accent' });
    setText('generalTodayBadge', rows.length ? `${rows.length} items` : 'Rustig');
    renderMiniRows('generalTodayList', rows.slice(0,4), 'Hier kun je snel diensten en je fooienpot volgen zonder naar losse pagina’s te hoeven springen.');
  }

  function renderKitchenOverview(){
    const lists = safeArray(appData.kitchen?.lists);
    const recipes = safeArray(appData.recipes?.items);
    const tasks = lists.flatMap(list => safeArray(list.tasks));
    const doneToday = tasks.filter(task => kitchenTaskIsChecked(task)).length;
    const cards = [];
    if (pageAllowed('keuken-takenlijsten')){
      cards.push({
        kicker:'Keuken',
        title:'Takenlijsten',
        sub:'Open snel je checklist en zie meteen wat vandaag al gedaan is.',
        badge:`${lists.length} lijsten`,
        badgeClass:'accent',
        meta:[`${doneToday} taken vandaag afgevinkt`, `${tasks.length} taken totaal`],
        actions:[{ label:'Open takenlijsten', kind:'accent', onclick:`openPage('keuken-takenlijsten')` }]
      });
    }
    if (pageAllowed('keuken-recepten')){
      cards.push({
        kicker:'Keuken',
        title:'Recepten',
        sub:'Snel naar receptkaarten, ingrediënten en bereidingsstappen.',
        badge:`${recipes.length} recepten`,
        meta:[recipes[0]?.name ? `Laatste: ${recipes[0].name}` : 'Receptenbank beschikbaar'],
        actions:[{ label:'Open recepten', kind:'accent', onclick:`openPage('keuken-recepten')` }]
      });
    }
    renderOverviewCards('kitchenOverviewGrid', cards, 'Je hebt nu alleen toegang tot de keukendelen die voor jouw rol relevant zijn.');

    const activity = [];
    lists.forEach(list => {
      safeArray(list.tasks).forEach(task => {
        if (task.last_checked_by && task.last_checked_at){
          activity.push({ title: task.title || 'Taak', sub: `${list.name || 'Takenlijst'} · ${formatAuditLine(task)}`, badge:'Taak' });
        }
        safeArray(task.subtasks).forEach(sub => {
          if (sub.last_checked_by && sub.last_checked_at){
            activity.push({ title: sub.title || 'Subtaak', sub: `${list.name || 'Takenlijst'} · ${formatAuditLine(sub)}`, badge:'Subtaak', badgeClass:'accent' });
          }
        });
      });
    });
    activity.sort((a,b)=> (b.sub||'').localeCompare(a.sub||''));
    setText('kitchenActivityBadge', activity.length ? `${activity.length} items` : '0 items');
    renderMiniRows('kitchenActivityList', activity.slice(0,4), 'Zodra er taken worden afgevinkt, zie je hier direct door wie en wanneer.');
  }

  function renderBarOverview(){
    const koelingen = safeArray(appData.bar?.koelingen);
    const fill = safeArray(appData.bar?.fill_items);
    const lists = safeArray(appData.bar_tasks?.lists);
    const tasks = lists.flatMap(list => safeArray(list.tasks));
    const lowCount = koelingen.reduce((total, koeling) => total + safeArray(koeling.producten).filter(product => !product.op && Number(product.voorraad || 0) < Number(product.minimum || 0)).length, 0);
    const opCount = koelingen.reduce((total, koeling) => total + safeArray(koeling.producten).filter(product => !!product.op).length, 0);
    const doneToday = tasks.filter(task => kitchenTaskIsChecked(task)).length;
    const cards = [];
    if (pageAllowed('bar-koelingen')) cards.push({ kicker:'Bar', title:'Koelingen', sub:'Bekijk koelingen en pas voorraad direct aan.', badge:`${koelingen.length} koelingen`, badgeClass:'accent', meta:[`${lowCount} lage voorraad`, `${opCount} producten op`], actions:[{ label:'Open koelingen', kind:'accent', onclick:`openPage('bar-koelingen')` }] });
    if (pageAllowed('bar-takenlijsten')) cards.push({ kicker:'Bar', title:'Takenlijsten', sub:'Werk je bar-opstart of afsluiting rustig af vanaf je telefoon.', badge:`${lists.length} lijsten`, badgeClass:'accent', meta:[`${doneToday} taken vandaag afgevinkt`, `${tasks.length} taken totaal`], actions:[{ label:'Open takenlijsten', kind:'accent', onclick:`openPage('bar-takenlijsten')` }] });
    if (pageAllowed('bar-bijvullen')) cards.push({ kicker:'Bar', title:'Bijvuloverzicht', sub:'Zie meteen wat vandaag aandacht nodig heeft.', badge:`${fill.length} acties`, badgeClass: fill.length ? 'warn' : 'good', meta: fill.slice(0,2).map(item => `${item.product} · ${item.bijvullen} bijvullen`), actions:[{ label:'Open bijvullen', kind:'accent', onclick:`openPage('bar-bijvullen')` }] });
    if (pageAllowed('bar-oplijst')) cards.push({ kicker:'Bar', title:'Op-lijst', sub:'Alles wat op is of weer terug op voorraad moet.', badge:`${opCount} op`, badgeClass: opCount ? 'warn' : 'good', actions:[{ label:'Open op-lijst', kind:'accent', onclick:`openPage('bar-oplijst')` }] });
    if (pageAllowed('bar-productsoorten')) cards.push({ kicker:'Bar', title:'Productsoorten', sub:'Beheer soorten en indeling per locatie.', badge:`${safeArray(appData.types).length} soorten`, actions:[{ label:'Open soorten', kind:'accent', onclick:`openPage('bar-productsoorten')` }] });
    if (pageAllowed('bar-locaties')) cards.push({ kicker:'Bar', title:'Locaties', sub:'Overzicht van opslagplekken en logische looproutes.', badge:`${safeArray(appData.locations).filter(Boolean).length} locaties`, actions:[{ label:'Open locaties', kind:'accent', onclick:`openPage('bar-locaties')` }] });
    renderOverviewCards('barOverviewGrid', cards, 'Je ziet hier alleen de bar-onderdelen waar jij echt iets mee kunt.');

    const rows = [];
    fill.slice(0,3).forEach(item => rows.push({ title:item.product, sub:`${item.koeling} · ${item.locatie || '-'} · nu ${item.voorraad}`, badge:`+${item.bijvullen}`, badgeClass:'warn' }));
    safeArray(lists).forEach(list => {
      safeArray(list.tasks).forEach(task => {
        if (task.last_checked_by && task.last_checked_at && rows.length < 4){
          rows.push({ title: task.name || 'Taak', sub: `${list.name || 'Takenlijst'} · ${formatAuditLine(task)}`, badge:'Checklist', badgeClass:'accent' });
        }
      });
    });
    if (!rows.length && pageAllowed('bar-koelingen')) rows.push({ title:'Bar in beeld', sub:`${koelingen.length} koelingen en ${lists.length} lijsten beschikbaar.`, badge: lowCount ? `${lowCount} alerts` : 'In orde', badgeClass: lowCount ? 'warn' : 'good' });
    setText('barFocusBadge', rows.length ? `${rows.length} items` : '0 items');
    renderMiniRows('barFocusList', rows, 'Geen directe focuspunten. De bar is op dit moment netjes op orde.');
  }


  function getTodayString(){
    return new Date().toISOString().slice(0,10);
  }

  function kitchenTaskIsChecked(task){
    return !!task.checked && task.last_checked === getTodayString();
  }

  function kitchenSubtaskIsChecked(sub){
    return !!sub.checked && sub.last_checked === getTodayString();
  }

  function openKitchenListDetail(listId){
    currentKitchenListId = listId;
    window.currentKitchenListId = listId;
    const list = safeArray(appData.kitchen?.lists).find(item => item.id === listId) || {};
    setText('kitchenDetailTitle', `☑ ${list.name || 'Takenlijst'}`);
    openPage('keuken-takenlijst-detail');
    renderKitchenListDetail();
  }

  function formatAuditLine(item){
    if (!item || !item.last_checked_by || !item.last_checked_at) return '';
    let when = item.last_checked_at;
    try{
      when = new Date(item.last_checked_at).toLocaleString('nl-NL', { day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit' });
    }catch(err){}
    return `Afgevinkt door ${item.last_checked_by} om ${when}`;
  }

  function getTaskStatusMeta(task){
    const audit = formatAuditLine(task);
    return audit || `${safeArray(task.subtasks).length} subtaken`;
  }
  function getTaskProgress(task, taskCheckedFn, subtaskCheckedFn){
    const subtasks = safeArray(task?.subtasks);
    const doneSubs = subtasks.filter(sub => subtaskCheckedFn(sub)).length;
    const totalSubs = subtasks.length;
    const isDone = taskCheckedFn(task);
    const pendingSubs = Math.max(totalSubs - doneSubs, 0);
    let status = 'open';
    if (isDone) status = 'done';
    else if (doneSubs > 0) status = 'progress';
    return { subtasks, doneSubs, totalSubs, pendingSubs, isDone, status };
  }

  function renderTaskGroup(title, subtitle, badgeClass, badgeText, itemsHtml, openByDefault=false, extraClass=''){
    if (!itemsHtml) return '';
    return `
      <details class="task-group ${extraClass}" ${openByDefault ? 'open' : ''}>
        <summary>
          <div class="task-group-label">
            <div class="task-group-title">${title}</div>
            <div class="task-group-sub">${subtitle}</div>
          </div>
          <div class="task-group-right">
            <span class="badge ${badgeClass}">${badgeText}</span>
            <span class="group-chevron">⌄</span>
          </div>
        </summary>
        <div class="task-group-body">${itemsHtml}</div>
      </details>
    `;
  }

  function renderChecklistTaskCard(task, options){
    const progress = getTaskProgress(task, options.taskCheckedFn, options.subtaskCheckedFn);
    const meta = formatAuditLine(task) || (progress.totalSubs ? `${progress.doneSubs}/${progress.totalSubs} subtaken gedaan${progress.pendingSubs ? ` · nog ${progress.pendingSubs} open` : ''}` : 'Losse taak');
    return `
      <div class="ktask">
        <div class="ktask-row" onclick="${options.toggleTaskCall(task)}">
          <div class="kcheck ${progress.isDone ? 'done' : ''}">${progress.isDone ? '✓' : ''}</div>
          <div style="min-width:0;flex:1">
            <div class="ktask-title ${progress.isDone ? 'done' : ''}">${task.name || 'Taak'}</div>
            <div class="ktask-meta">${meta}</div>
          </div>
          <span class="badge ${progress.isDone ? 'good' : progress.status === 'progress' ? 'accent' : 'warn'}">${progress.isDone ? 'Gedaan' : progress.status === 'progress' ? 'Bezig' : 'Open'}</span>
        </div>
        ${progress.totalSubs ? `
          <div class="ksub-wrap">
            ${progress.subtasks.map(sub => `
              <div class="ksub">
                <div class="ksub-row" onclick="${options.toggleSubtaskCall(task, sub)}">
                  <div class="kcheck ${options.subtaskCheckedFn(sub) ? 'done' : ''}" style="width:22px;height:22px;min-width:22px;font-size:11px">${options.subtaskCheckedFn(sub) ? '✓' : ''}</div>
                  <div style="min-width:0;flex:1">
                    <div class="ksub-title ${options.subtaskCheckedFn(sub) ? 'done' : ''}">${sub.name || 'Subtaak'}</div>
                    ${formatAuditLine(sub) ? `<div class="audit-note">${formatAuditLine(sub)}</div>` : ''}
                  </div>
                  <span class="badge ${options.subtaskCheckedFn(sub) ? 'good' : ''}">${options.subtaskCheckedFn(sub) ? 'Gedaan' : 'Open'}</span>
                </div>
              </div>
            `).join('')}
          </div>
        ` : ''}
      </div>
    `;
  }

  function renderChecklistSections(targetId, tasks, options){
    const enriched = safeArray(tasks).map(task => ({ task, progress: getTaskProgress(task, options.taskCheckedFn, options.subtaskCheckedFn) }));
    const openItems = enriched.filter(item => item.progress.status === 'open');
    const progressItems = enriched.filter(item => item.progress.status === 'progress');
    const doneItems = enriched.filter(item => item.progress.status === 'done');
    const html = `
      <div class="task-sections">
        ${renderTaskGroup('Direct doen', openItems.length ? `${openItems.length} taak${openItems.length === 1 ? '' : 'en'} nog volledig open` : 'Alles uit deze groep is gestart', 'warn', String(openItems.length), openItems.map(item => renderChecklistTaskCard(item.task, options)).join(''), true, 'open-group')}
        ${renderTaskGroup('Bijna klaar', progressItems.length ? `${progressItems.length} taak${progressItems.length === 1 ? '' : 'en'} is al deels gedaan` : 'Nog geen taken half afgerond', 'accent', String(progressItems.length), progressItems.map(item => renderChecklistTaskCard(item.task, options)).join(''), true, 'progress-group')}
        ${renderTaskGroup('Klaar', doneItems.length ? `${doneItems.length} taak${doneItems.length === 1 ? '' : 'en'} al afgerond vandaag` : 'Nog niets afgerond vandaag', 'good', String(doneItems.length), doneItems.map(item => renderChecklistTaskCard(item.task, options)).join(''), false, 'done-group')}
      </div>
    `;
    document.getElementById(targetId).innerHTML = (openItems.length || progressItems.length || doneItems.length) ? html : '<div class="empty">Nog geen taken in deze lijst.</div>';
  }

  function renderKitchen(){
    const kitchen = appData.kitchen || { lists: [] };
    const lists = safeArray(kitchen.lists);
    const taskCount = lists.reduce((total, lst) => total + safeArray(lst.tasks).length, 0);
    const canManageTasklists = hasPermission('manage_tasklists');

    setText('kitchenListCount', String(lists.length));
    setText('kitchenTaskCount', String(taskCount));
    setText('recipeCount', String(safeArray(appData.recipes?.items).length));

    renderList(
      'kitchenLists',
      lists,
      (list) => {
        const tasks = safeArray(list.tasks);
        const done = tasks.filter(t => kitchenTaskIsChecked(t)).length;
        const percent = tasks.length ? Math.round((done / tasks.length) * 100) : 0;
        return `
          <div class="klist-card">
            <div class="klist-top">
              <div class="klist-left">
                <div class="klist-icon">☑</div>
                <div>
                  <div class="klist-name">${list.name}</div>
                  <div class="klist-sub">${done} van ${tasks.length} taken gedaan</div>
                </div>
              </div>
              <span class="badge accent">${percent}%</span>
            </div>
            <div class="kprogress"><span style="width:${percent}%"></span></div>
            <div class="kmeta">
              <span>${tasks.length ? 'Klaar om af te werken' : 'Nog geen taken in deze lijst'}</span>
              <span>${tasks.length} taak${tasks.length === 1 ? '' : 'en'}</span>
            </div>
            <div class="klist-actions">
              <button class="btn" onclick="openKitchenListDetail('${list.id}')">Open lijst</button>
              ${canManageTasklists ? `<button class="btn danger" onclick="confirmAction('Takenlijst verwijderen','Weet je zeker dat je deze takenlijst wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteKitchenList','${list.id}')&quot;)">Verwijderen</button>` : ''}
            </div>
          </div>
        `;
      },
      'Nog geen takenlijsten gevonden.'
    );
  }

  function renderKitchenListDetail(){
    const kitchen = appData.kitchen || { lists: [] };
    const list = safeArray(kitchen.lists).find(item => item.id === currentKitchenListId) || { tasks: [], name: 'Takenlijst' };
    const tasks = safeArray(list.tasks);
    const done = tasks.filter(t => kitchenTaskIsChecked(t)).length;
    const percent = tasks.length ? Math.round((done / tasks.length) * 100) : 0;

    const title = document.getElementById('kitchenDetailTitle');
    if (title){
      title.textContent = `☑ Takenlijst · ${list.name || 'Takenlijst'}`;
    }
    const summary = document.getElementById('kitchenDetailSummary');
    if (summary){
      summary.innerHTML = `
        <div class="kheadbar">
          <div class="khead-top">
            <div class="item-sub">${done} van ${tasks.length} taken gedaan</div>
            <span class="badge accent">${percent}%</span>
          </div>
          <div class="kprogress"><span style="width:${percent}%"></span></div>
        </div>
      `;
    }

    renderChecklistSections('kitchenDetailList', tasks, {
      taskCheckedFn: kitchenTaskIsChecked,
      subtaskCheckedFn: kitchenSubtaskIsChecked,
      toggleTaskCall: (task) => `toggleKitchenTask('${list.id}','${task.id}')`,
      toggleSubtaskCall: (task, sub) => `toggleKitchenSubtask('${list.id}','${task.id}','${sub.id}')`
    });
  }

  function recipeIngredientFields(items){
    const data = Array.isArray(items) && items.length ? items : [{naam:'', locatie:''}];
    return data.map((ing, index) => `
      <div class="list-item" style="background:rgba(255,255,255,.015)">
        <div class="field"><label>Ingrediënt</label><input data-ing-name="${index}" value="${ing.naam || ''}" placeholder="Bijv. Pasta"></div>
        <div class="field"><label>Vindplaats</label><input data-ing-location="${index}" value="${ing.locatie || ''}" placeholder="Bijv. Droge opslag"></div>
      </div>
    `).join('');
  }



  function openKitchenManagePage(listId){
    if (!hasPermission('manage_tasklists')) return;
    currentKitchenListId = listId;
    window.currentKitchenListId = listId;
    const list = safeArray(appData.kitchen?.lists).find(item => item.id === listId) || {};
    setText('kitchenManageTitle', `⚙️ Takenlijst beheren · ${list.name || 'Takenlijst'}`);
    openPage('keuken-takenlijst-beheer');
    renderKitchenManagePage();
  }

  function renderKitchenManagePage(){
    const kitchen = appData.kitchen || { lists: [] };
    const list = safeArray(kitchen.lists).find(item => item.id === currentKitchenListId) || { tasks: [], name: 'Takenlijst' };
    const tasks = safeArray(list.tasks);

    renderList(
      'kitchenManageList',
      tasks,
      (task) => `
        <div class="ktask">
          <div class="item-top">
            <div>
              <div class="ktask-title">${task.name || 'Taak'}</div>
              <div class="ktask-meta">${safeArray(task.subtasks).length} subtaken</div>
            </div>
            <span class="badge accent">Taak</span>
          </div>
          <div class="ktask-actions">
            <button class="btn" onclick="openKitchenSubtaskModal('${list.id}','${task.id}')">+ Subtaak toevoegen</button>
            <button class="btn danger" onclick="confirmAction('Taak verwijderen','Weet je zeker dat je deze taak wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteKitchenTask','${list.id}','${task.id}')&quot;)">Verwijderen</button>
          </div>
          ${safeArray(task.subtasks).length ? `
            <div class="ksub-wrap">
              ${safeArray(task.subtasks).map(sub => `
                <div class="ksub">
                  <div class="item-top">
                    <div><div class="ksub-title">${sub.name || 'Subtaak'}</div></div>
                    <span class="badge">Subtaak</span>
                  </div>
                  <div class="ksub-actions">
                    <button class="btn danger" onclick="confirmAction('Subtaak verwijderen','Weet je zeker dat je deze subtaak wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteKitchenSubtask','${list.id}','${task.id}','${sub.id}')&quot;)">Verwijderen</button>
                  </div>
                </div>
              `).join('')}
            </div>
          ` : `<div class="empty" style="margin-top:12px">Nog geen subtaken.</div>`}
        </div>
      `,
      'Nog geen taken in deze lijst.'
    );
  }

  function openKitchenListModal(){
    openModal(
      'Takenlijst toevoegen',
      'Maak een blijvende lijst aan voor je keukenwerkzaamheden.',
      `
        <div class="form-grid">
          <div class="field"><label>Naam takenlijst</label><input id="kitchenListName" placeholder="Bijv. Opening keuken"></div>
          <div class="form-actions">
            <button class="btn" onclick="closeModal()">Annuleren</button>
            <button class="btn accent" onclick="saveKitchenList()">Opslaan</button>
          </div>
        </div>
      `
    );
  }

  async function saveKitchenList(){
    try{
      await postJSON('/api/kitchen/list-save', { name: document.getElementById('kitchenListName').value });
      closeModal();
      await loadData();
      renderKitchen();
      toast('Takenlijst opgeslagen');
    }catch(err){ toast(err.message, 'error'); }
  }

  function openKitchenTaskModal(listId){
    openModal(
      'Taak toevoegen',
      'Voeg een nieuwe taak toe aan deze takenlijst.',
      `
        <div class="form-grid">
          <div class="field"><label>Naam taak</label><input id="kitchenTaskName" placeholder="Bijv. Koeling checken"></div>
          <div class="form-actions">
            <button class="btn" onclick="closeModal()">Annuleren</button>
            <button class="btn accent" onclick="saveKitchenTask('${listId}')">Opslaan</button>
          </div>
        </div>
      `
    );
  }

  async function saveKitchenTask(listId){
    try{
      await postJSON('/api/kitchen/task-save', { list_id: listId, name: document.getElementById('kitchenTaskName').value });
      closeModal();
      await loadData();
      renderKitchen();
      renderKitchenListDetail();
      renderKitchenManagePage();
      toast('Taak opgeslagen');
    }catch(err){ toast(err.message, 'error'); }
  }

  function openKitchenSubtaskModal(listId, taskId){
    openModal(
      'Subtaak toevoegen',
      'Voeg een subtaak toe onder deze taak.',
      `
        <div class="form-grid">
          <div class="field"><label>Naam subtaak</label><input id="kitchenSubtaskName" placeholder="Bijv. Koeling 1 checken"></div>
          <div class="form-actions">
            <button class="btn" onclick="closeModal()">Annuleren</button>
            <button class="btn accent" onclick="saveKitchenSubtask('${listId}','${taskId}')">Opslaan</button>
          </div>
        </div>
      `
    );
  }

  async function saveKitchenSubtask(listId, taskId){
    try{
      await postJSON('/api/kitchen/subtask-save', { list_id: listId, task_id: taskId, name: document.getElementById('kitchenSubtaskName').value });
      closeModal();
      await loadData();
      renderKitchenListDetail();
      renderKitchenManagePage();
      toast('Subtaak opgeslagen');
    }catch(err){ toast(err.message, 'error'); }
  }

  async function toggleKitchenTask(listId, taskId){
    try{
      await postJSON('/api/kitchen/task-toggle', { list_id: listId, task_id: taskId });
      await loadData();
      renderKitchen();
      renderKitchenListDetail();
      renderKitchenManagePage();
      toast('Taak bijgewerkt');
    }catch(err){ toast(err.message, 'error'); }
  }

  async function toggleKitchenSubtask(listId, taskId, subtaskId){
    try{
      await postJSON('/api/kitchen/subtask-toggle', { list_id: listId, task_id: taskId, subtask_id: subtaskId });
      await loadData();
      renderKitchenListDetail();
      renderKitchenManagePage();
      toast('Subtaak bijgewerkt');
    }catch(err){ toast(err.message, 'error'); }
  }

  async function deleteKitchenList(listId){
    try{
      await postJSON('/api/kitchen/list-delete', { list_id: listId });
      await loadData();
      openPage('keuken-takenlijsten');
      renderKitchen();
      toast('Takenlijst verwijderd');
    }catch(err){ toast(err.message, 'error'); }
  }

  async function deleteKitchenTask(listId, taskId){
    try{
      await postJSON('/api/kitchen/task-delete', { list_id: listId, task_id: taskId });
      await loadData();
      renderKitchenListDetail();
      renderKitchenManagePage();
      toast('Taak verwijderd');
    }catch(err){ toast(err.message, 'error'); }
  }

  async function deleteKitchenSubtask(listId, taskId, subtaskId){
    try{
      await postJSON('/api/kitchen/subtask-delete', { list_id: listId, task_id: taskId, subtask_id: subtaskId });
      await loadData();
      renderKitchenListDetail();
      renderKitchenManagePage();
      toast('Subtaak verwijderd');
    }catch(err){ toast(err.message, 'error'); }
  }


  function barTaskIsChecked(task){
    return !!task.checked && task.last_checked === getTodayString();
  }

  function barSubtaskIsChecked(sub){
    return !!sub.checked && sub.last_checked === getTodayString();
  }

  function openBarListDetail(listId){
    currentBarListId = listId;
    window.currentBarListId = listId;
    const list = safeArray(appData.bar_tasks?.lists).find(item => item.id === listId) || {};
    setText('barDetailTitle', `☑ ${list.name || 'Bar checklist'}`);
    openPage('bar-takenlijst-detail');
    renderBarTaskListDetail();
  }

  function renderBarTasks(){
    const data = appData.bar_tasks || { lists: [] };
    const lists = safeArray(data.lists);
    const canManageTasklists = hasPermission('manage_tasklists');
    renderList(
      'barTaskLists',
      lists,
      (list) => {
        const tasks = safeArray(list.tasks);
        const done = tasks.filter(t => barTaskIsChecked(t)).length;
        const percent = tasks.length ? Math.round((done / tasks.length) * 100) : 0;
        return `
          <div class="klist-card">
            <div class="klist-top">
              <div class="klist-left">
                <div class="klist-icon">✓</div>
                <div>
                  <div class="klist-name">${list.name}</div>
                  <div class="klist-sub">${done} van ${tasks.length} taken gedaan</div>
                </div>
              </div>
              <span class="badge accent">${percent}%</span>
            </div>
            <div class="kprogress"><span style="width:${percent}%"></span></div>
            <div class="kmeta">
              <span>${tasks.length ? 'Klaar voor je shift' : 'Nog geen taken in deze lijst'}</span>
              <span>${tasks.length} taak${tasks.length === 1 ? '' : 'en'}</span>
            </div>
            <div class="klist-actions">
              <button class="btn" onclick="openBarListDetail('${list.id}')">Open lijst</button>
              ${canManageTasklists ? `<button class="btn danger" onclick="confirmAction('Takenlijst verwijderen','Weet je zeker dat je deze bartakenlijst wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteBarList','${list.id}')&quot;)">Verwijderen</button>` : ''}
            </div>
          </div>
        `;
      },
      'Nog geen bartakenlijsten gevonden.'
    );
  }

  function renderBarTaskListDetail(){
    const data = appData.bar_tasks || { lists: [] };
    const list = safeArray(data.lists).find(item => item.id === currentBarListId) || { tasks: [], name: 'Bar checklist' };
    const tasks = safeArray(list.tasks);
    const done = tasks.filter(t => barTaskIsChecked(t)).length;
    const percent = tasks.length ? Math.round((done / tasks.length) * 100) : 0;
    setText('barDetailTitle', `☑ Bar checklist · ${list.name || 'Bar checklist'}`);
    const summary = document.getElementById('barDetailSummary');
    if (summary){
      summary.innerHTML = `
        <div class="kheadbar">
          <div class="khead-top">
            <div class="item-sub">${done} van ${tasks.length} taken gedaan</div>
            <span class="badge accent">${percent}%</span>
          </div>
          <div class="kprogress"><span style="width:${percent}%"></span></div>
        </div>
      `;
    }
    renderChecklistSections('barDetailList', tasks, {
      taskCheckedFn: barTaskIsChecked,
      subtaskCheckedFn: barSubtaskIsChecked,
      toggleTaskCall: (task) => `toggleBarTask('${list.id}','${task.id}')`,
      toggleSubtaskCall: (task, sub) => `toggleBarSubtask('${list.id}','${task.id}','${sub.id}')`
    });
  }

  function openBarManagePage(listId){
    if (!hasPermission('manage_tasklists')) return;
    currentBarListId = listId;
    window.currentBarListId = listId;
    const list = safeArray(appData.bar_tasks?.lists).find(item => item.id === listId) || {};
    setText('barManageTitle', `⚙️ Bar takenlijst beheren · ${list.name || 'Bar checklist'}`);
    openPage('bar-takenlijst-beheer');
    renderBarTaskManagePage();
  }

  function renderBarTaskManagePage(){
    const data = appData.bar_tasks || { lists: [] };
    const list = safeArray(data.lists).find(item => item.id === currentBarListId) || { tasks: [], name: 'Bar checklist' };
    const tasks = safeArray(list.tasks);
    renderList(
      'barManageList',
      tasks,
      (task) => `
        <div class="ktask">
          <div class="item-top">
            <div>
              <div class="ktask-title">${task.name || 'Taak'}</div>
              <div class="ktask-meta">${safeArray(task.subtasks).length} subtaken</div>
            </div>
            <span class="badge accent">Taak</span>
          </div>
          <div class="ktask-actions">
            <button class="btn" onclick="openBarSubtaskModal('${list.id}','${task.id}')">+ Subtaak toevoegen</button>
            <button class="btn danger" onclick="confirmAction('Taak verwijderen','Weet je zeker dat je deze bartaak wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteBarTask','${list.id}','${task.id}')&quot;)">Verwijderen</button>
          </div>
          ${safeArray(task.subtasks).length ? `
            <div class="ksub-wrap">
              ${safeArray(task.subtasks).map(sub => `
                <div class="ksub">
                  <div class="item-top">
                    <div><div class="ksub-title">${sub.name || 'Subtaak'}</div></div>
                    <span class="badge">Subtaak</span>
                  </div>
                  <div class="ksub-actions">
                    <button class="btn danger" onclick="confirmAction('Subtaak verwijderen','Weet je zeker dat je deze barsubtaak wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteBarSubtask','${list.id}','${task.id}','${sub.id}')&quot;)">Verwijderen</button>
                  </div>
                </div>
              `).join('')}
            </div>
          ` : `<div class="empty" style="margin-top:12px">Nog geen subtaken.</div>`}
        </div>
      `,
      'Nog geen taken in deze lijst.'
    );
  }

  function openBarListModal(){
    openModal('Bartakenlijst toevoegen','Maak een blijvende lijst aan voor je barwerkzaamheden.',`
      <div class="form-grid">
        <div class="field"><label>Naam takenlijst</label><input id="barListName" placeholder="Bijv. Bar opstart"></div>
        <div class="form-actions">
          <button class="btn" onclick="closeModal()">Annuleren</button>
          <button class="btn accent" onclick="saveBarList()">Opslaan</button>
        </div>
      </div>`);
  }

  async function saveBarList(){
    try{
      await postJSON('/api/bar-tasks/list-save', { name: document.getElementById('barListName').value });
      closeModal();
      await loadData();
      renderBarTasks();
      toast('Bartakenlijst opgeslagen');
    }catch(err){ toast(err.message, 'error'); }
  }

  function openBarTaskModal(listId){
    openModal('Bartaak toevoegen','Voeg een nieuwe taak toe aan deze bartakenlijst.',`
      <div class="form-grid">
        <div class="field"><label>Naam taak</label><input id="barTaskName" placeholder="Bijv. Bar klaarzetten"></div>
        <div class="form-actions">
          <button class="btn" onclick="closeModal()">Annuleren</button>
          <button class="btn accent" onclick="saveBarTask('${listId}')">Opslaan</button>
        </div>
      </div>`);
  }

  async function saveBarTask(listId){
    try{
      await postJSON('/api/bar-tasks/task-save', { list_id: listId, name: document.getElementById('barTaskName').value });
      closeModal();
      await loadData();
      renderBarTasks();
      renderBarTaskListDetail();
      renderBarTaskManagePage();
      toast('Bartaak opgeslagen');
    }catch(err){ toast(err.message, 'error'); }
  }

  function openBarSubtaskModal(listId, taskId){
    openModal('Barsubtaak toevoegen','Voeg een subtaak toe onder deze taak.',`
      <div class="form-grid">
        <div class="field"><label>Naam subtaak</label><input id="barSubtaskName" placeholder="Bijv. IJs aanvullen"></div>
        <div class="form-actions">
          <button class="btn" onclick="closeModal()">Annuleren</button>
          <button class="btn accent" onclick="saveBarSubtask('${listId}','${taskId}')">Opslaan</button>
        </div>
      </div>`);
  }

  async function saveBarSubtask(listId, taskId){
    try{
      await postJSON('/api/bar-tasks/subtask-save', { list_id: listId, task_id: taskId, name: document.getElementById('barSubtaskName').value });
      closeModal();
      await loadData();
      renderBarTaskListDetail();
      renderBarTaskManagePage();
      toast('Barsubtaak opgeslagen');
    }catch(err){ toast(err.message, 'error'); }
  }

  async function toggleBarTask(listId, taskId){
    try{
      await postJSON('/api/bar-tasks/task-toggle', { list_id: listId, task_id: taskId });
      await loadData();
      renderBarTasks();
      renderBarTaskListDetail();
      renderBarTaskManagePage();
      toast('Bartaak bijgewerkt');
    }catch(err){ toast(err.message, 'error'); }
  }

  async function toggleBarSubtask(listId, taskId, subtaskId){
    try{
      await postJSON('/api/bar-tasks/subtask-toggle', { list_id: listId, task_id: taskId, subtask_id: subtaskId });
      await loadData();
      renderBarTaskListDetail();
      renderBarTaskManagePage();
      renderBarOverview();
      toast('Barsubtaak bijgewerkt');
    }catch(err){ toast(err.message, 'error'); }
  }

  async function deleteBarList(listId){
    try{
      await postJSON('/api/bar-tasks/list-delete', { list_id: listId });
      await loadData();
      openPage('bar-takenlijsten');
      renderBarTasks();
      toast('Bartakenlijst verwijderd');
    }catch(err){ toast(err.message, 'error'); }
  }

  async function deleteBarTask(listId, taskId){
    try{
      await postJSON('/api/bar-tasks/task-delete', { list_id: listId, task_id: taskId });
      await loadData();
      renderBarTaskListDetail();
      renderBarTaskManagePage();
      toast('Bartaak verwijderd');
    }catch(err){ toast(err.message, 'error'); }
  }

  async function deleteBarSubtask(listId, taskId, subtaskId){
    try{
      await postJSON('/api/bar-tasks/subtask-delete', { list_id: listId, task_id: taskId, subtask_id: subtaskId });
      await loadData();
      renderBarTaskListDetail();
      renderBarTaskManagePage();
      toast('Barsubtaak verwijderd');
    }catch(err){ toast(err.message, 'error'); }
  }

  function openRecipeModal(index=null){
    const recipe = index !== null ? safeArray(appData.recipes?.items)[index] || {} : {};
    const ingredients = Array.isArray(recipe.ingredients) ? recipe.ingredients : [];
    openModal(
      index === null ? 'Recept toevoegen' : 'Recept bewerken',
      'Voeg ingrediënten, vindplaats en stappenplan toe.',
      `
        <div class="form-grid">
          <div class="field"><label>Naam recept</label><input id="recipeName" value="${recipe.name || ''}" placeholder="Bijv. Pasta Carbonara"></div>
          <div class="field"><label>Ingrediënten</label></div>
          <div class="list" id="recipeIngredientsWrap">${recipeIngredientFields(ingredients)}</div>
          <div class="actions"><button class="btn" onclick="addIngredientField()">Ingrediënt toevoegen</button></div>
          <div class="field"><label>Stappenplan</label><input id="recipeSteps" value="${recipe.steps || ''}" placeholder="Bijv. 1. Koken 2. Bakken 3. Serveren"></div>
          <div class="form-actions">
            <button class="btn" onclick="closeModal()">Annuleren</button>
            <button class="btn accent" onclick="saveRecipe(${index === null ? 'null' : index})">Opslaan</button>
          </div>
        </div>
      `
    );
  }

  function addIngredientField(){
    const wrap = document.getElementById('recipeIngredientsWrap');
    const idx = wrap.querySelectorAll('[data-ing-name]').length;
    wrap.insertAdjacentHTML('beforeend', `
      <div class="list-item" style="background:rgba(255,255,255,.015)">
        <div class="field"><label>Ingrediënt</label><input data-ing-name="${idx}" placeholder="Bijv. Pasta"></div>
        <div class="field"><label>Vindplaats</label><input data-ing-location="${idx}" placeholder="Bijv. Droge opslag"></div>
      </div>
    `);
  }

  function collectIngredients(){
    const names = [...document.querySelectorAll('[data-ing-name]')];
    return names.map((input, idx) => ({
      naam: input.value,
      locatie: document.querySelector(`[data-ing-location="${idx}"]`)?.value || ''
    })).filter(item => item.naam);
  }

  async function saveRecipe(index){
    try{
      await postJSON('/api/recipes/save', {
        index,
        name: document.getElementById('recipeName').value,
        ingredients: collectIngredients(),
        steps: document.getElementById('recipeSteps').value
      });
      closeModal();
      await loadData();
      toast('Recept opgeslagen');
    }catch(err){ toast(err.message, 'error'); }
  }

  async function deleteRecipe(index){
    try{
      await postJSON('/api/recipes/delete', { index });
      await loadData();
      toast('Recept verwijderd');
    }catch(err){ toast(err.message, 'error'); }
  }

  function renderRecipes(){
    const items = safeArray(appData.recipes?.items);
    renderList(
      'recipesList',
      items,
      (recipe, index) => `
        <div class="recipe-card">
          <div class="item-top">
            <div>
              <div class="item-title">${recipe.name || 'Recept'}</div>
              <div class="item-sub">Open het recept om ingrediënten, vindplaatsen en het stappenplan te bekijken.</div>
            </div>
            <span class="badge accent">Recept</span>
          </div>
          <div class="item-actions" style="margin-top:12px">
            <button class="btn" onclick="openRecipeInfo(${index})">Open recept</button>
            ${adminOnly(`<button class=\"btn accent\" onclick=\"openRecipeModal(${index})\">Bewerken</button><button class=\"btn danger\" onclick=\"confirmAction('Recept verwijderen','Weet je zeker dat je dit recept wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteRecipe',${index})&quot;)\">Verwijderen</button>`)}
          </div>
        </div>
      `,
      'Nog geen recepten gevonden.'
    );
  }

  function openRecipeInfo(index){
    const recipe = safeArray(appData.recipes?.items)[index] || {};
    openModal(
      recipe.name || 'Recept',
      'Ingrediënten, vindplaats en stappenplan',
      `
        <div class="stack">
          <div class="panel">
            <div class="panel-head"><h3 class="panel-title">${recipe.name || 'Recept'}</h3><span class="badge accent">Recept</span></div>
            <div class="list">
              ${safeArray(recipe.ingredients).map(ing => `
                <div class="list-item">
                  <div class="item-title">${ing.naam || '-'}</div>
                  <div class="item-sub">${ing.locatie || '-'}</div>
                </div>
              `).join('') || '<div class="empty">Nog geen ingrediënten.</div>'}
            </div>
            <div class="panel" style="margin-top:12px">
              <div class="panel-title">Stappenplan</div>
              <div class="item-sub" style="margin-top:8px">${recipe.steps || 'Nog geen stappenplan toegevoegd.'}</div>
            </div>
            <div class="form-actions">
              <button class="btn" onclick="closeModal()">Sluiten</button>
              ${adminOnly(`<button class=\"btn accent\" onclick=\"closeModal(); openRecipeModal(${index})\">Bewerken</button>`)}
            </div>
          </div>
        </div>
      `
    );
  }

  function renderDienstTypes(){
    const items = safeArray(appData.dienst_types);
    renderList(
      'dienstTypesList',
      items,
      (name) => `
        <div class="list-item">
          <div class="item-top">
            <div>
              <div class="item-title">${name.naam}</div>
              <div class="item-sub">Beschikbaar als keuze bij het toevoegen van een dienst · ${name.start || '--:--'} - ${name.einde || '--:--'}</div>
            </div>
            <span class="badge accent">Dienstsoort</span>
          </div>
          <div class="item-actions">
            <button class="btn accent" onclick="openDienstTypeModal('${name.naam}')">Bewerken</button>
            <button class="btn danger" onclick="confirmAction('Dienstsoort verwijderen','Weet je zeker dat je deze dienstsoort wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteDienstType','${encodeURIComponent(name.naam)}')&quot;)">Verwijderen</button>
          </div>
        </div>
      `,
      'Nog geen dienstsoorten gevonden.'
    );
  }


  function derivePermissionPreset(user){
    if ((user?.role || 'medewerker') === 'admin') return 'admin';
    const p = user?.permissions || {};
    const general = !!p.access_general || !!p.manage_diensten || !!p.manage_tips;
    const bar = !!p.access_bar || !!p.adjust_stock || !!p.view_bijvullen || !!p.view_oplijst;
    const kitchen = !!p.access_kitchen || !!p.view_recipes || !!p.use_tasklists;
    if (bar && !general && !kitchen) return 'bar';
    if (kitchen && !general && !bar) return 'keuken';
    return 'medewerker';
  }

  function basePermissionsForPreset(preset){
    const empty = {
      access_general:false, access_bar:false, access_kitchen:false,
      manage_diensten:false, manage_tips:false, view_bijvullen:false, view_oplijst:false,
      adjust_stock:false, view_recipes:false, use_tasklists:false,
      manage_dienst_types:false, manage_users:false, manage_products:false, manage_types:false,
      manage_locations:false, manage_recipes:false, manage_tasklists:false, manage_coolers:false
    };
    if (preset === 'medewerker'){
      return { ...empty,
        access_general:true, access_bar:true, access_kitchen:true,
        manage_diensten:true, manage_tips:true,
        view_bijvullen:true, view_oplijst:true, adjust_stock:true,
        view_recipes:true, use_tasklists:true
      };
    }
    if (preset === 'bar'){
      return { ...empty,
        access_general:true,
        manage_diensten:true, manage_tips:true,
        access_bar:true,
        view_bijvullen:true, view_oplijst:true, adjust_stock:true
      };
    }
    if (preset === 'keuken'){
      return { ...empty,
        access_general:true,
        manage_diensten:true, manage_tips:true,
        access_kitchen:true,
        view_recipes:true, use_tasklists:true
      };
    }
    return { ...empty };
  }

  function applyVisibilityOverrides(base, general, bar, kitchen){
    const result = { ...base };
    if (general){
      result.access_general = true;
      result.manage_diensten = true;
      result.manage_tips = true;
    } else {
      result.access_general = false;
      result.manage_diensten = false;
      result.manage_tips = false;
    }
    if (bar){
      result.access_bar = true;
      result.view_bijvullen = true;
      result.view_oplijst = true;
      result.adjust_stock = true;
    } else {
      result.access_bar = false;
      result.view_bijvullen = false;
      result.view_oplijst = false;
      result.adjust_stock = false;
    }
    if (kitchen){
      result.access_kitchen = true;
      result.view_recipes = true;
      result.use_tasklists = true;
    } else {
      result.access_kitchen = false;
      result.view_recipes = false;
      result.use_tasklists = false;
    }
    return result;
  }

  function permissionCheckboxes(user){
    const preset = derivePermissionPreset(user);
    const p = user?.permissions || {};
    const general = !!p.access_general || !!p.manage_diensten || !!p.manage_tips;
    const bar = !!p.access_bar || !!p.adjust_stock || !!p.view_bijvullen || !!p.view_oplijst;
    const kitchen = !!p.access_kitchen || !!p.view_recipes || !!p.use_tasklists;
    return `
      <div class="permission-panel">
        <div class="permission-kicker">Snelle rechten</div>
        <div class="field" style="margin-bottom:8px">
          <label>Kies een basisprofiel</label>
          <select id="permissionPreset" onchange="syncPermissionPresetInfo()">
            <option value="medewerker" ${preset === 'medewerker' ? 'selected' : ''}>Medewerker · alles voor dagelijks gebruik</option>
            <option value="bar" ${preset === 'bar' ? 'selected' : ''}>Bar medewerker · alleen bar</option>
            <option value="keuken" ${preset === 'keuken' ? 'selected' : ''}>Keuken medewerker · alleen keuken</option>
          </select>
        </div>
        <div class="permission-kicker" style="margin-top:4px">Zichtbaarheid</div>
        <div class="permission-row"><span class="permission-inline-label">Algemeen</span><input type="checkbox" id="perm_access_general" ${general ? 'checked' : ''}></div>
        <div class="permission-row"><span class="permission-inline-label">Bar</span><input type="checkbox" id="perm_access_bar" ${bar ? 'checked' : ''}></div>
        <div class="permission-row"><span class="permission-inline-label">Keuken</span><input type="checkbox" id="perm_access_kitchen" ${kitchen ? 'checked' : ''}></div>
      </div>
    `;
  }

  function syncPermissionPresetInfo(){
    const preset = document.getElementById('permissionPreset')?.value || 'medewerker';
    if (preset === 'medewerker'){
      setChecked('perm_access_general', true);
      setChecked('perm_access_bar', true);
      setChecked('perm_access_kitchen', true);
    } else if (preset === 'bar'){
      setChecked('perm_access_general', true);
      setChecked('perm_access_bar', true);
      setChecked('perm_access_kitchen', false);
    } else if (preset === 'keuken'){
      setChecked('perm_access_general', true);
      setChecked('perm_access_bar', false);
      setChecked('perm_access_kitchen', true);
    }
  }

  function collectUserPermissions(){
    const preset = document.getElementById('permissionPreset')?.value || 'medewerker';
    const general = !!document.getElementById('perm_access_general')?.checked;
    const bar = !!document.getElementById('perm_access_bar')?.checked;
    const kitchen = !!document.getElementById('perm_access_kitchen')?.checked;
    const base = basePermissionsForPreset(preset);
    return applyVisibilityOverrides(base, general, bar, kitchen);
  }

  function permissionSummary(user){
    const preset = derivePermissionPreset(user);
    const labels = {
      admin: 'Admin',
      medewerker: 'Dagelijks gebruik',
      bar: 'Bar medewerker',
      keuken: 'Keuken medewerker'
    };
    const p = user?.permissions || {};
    const extra = [];
    if ((preset === 'bar' || preset === 'keuken') && (p.access_general || p.manage_diensten || p.manage_tips)) extra.push('Algemeen');
    if (preset === 'keuken' && (p.access_bar || p.adjust_stock || p.view_bijvullen || p.view_oplijst)) extra.push('Bar');
    if (preset === 'bar' && (p.access_kitchen || p.view_recipes || p.use_tasklists)) extra.push('Keuken');
    return extra.length ? `${labels[preset]} · + ${extra.join(' + ')}` : labels[preset];
  }

  function openUserModal(index=null){
    if (!isAdmin()) return;
    const user = index !== null ? safeArray(appData.auth?.users)[index] || {} : { role: 'medewerker', permissions: { access_general:true, access_bar:true, access_kitchen:true, manage_diensten:true, manage_tips:true, view_bijvullen:true, view_oplijst:true, adjust_stock:true, view_recipes:true, use_tasklists:true, manage_dienst_types:false, manage_users:false, manage_products:false, manage_types:false, manage_locations:false, manage_recipes:false, manage_tasklists:false, manage_coolers:false } };
    openModal(index === null ? 'Medewerker toevoegen' : 'Medewerker bewerken', 'Alleen admin kan Casa Cara medewerkers en rechten beheren.', `
      <div class="form-grid">
        <div class="field"><label>Naam</label><input id="userName" value="${user.name || ''}" placeholder="Bijv. Lisa"></div>
        <div class="field"><label>Rol</label><select id="userRole" onchange="togglePermissionFields()"><option value="medewerker" ${user.role === 'medewerker' ? 'selected' : ''}>Medewerker</option><option value="admin" ${user.role === 'admin' ? 'selected' : ''}>Admin</option></select></div>
        <div class="field"><label>Code</label><input id="userPin" value="${user.pin || ''}" inputmode="numeric" placeholder="4 cijfers"></div>
        <div id="userPermissionsWrap" class="field" style="display:${user.role === 'admin' ? 'none' : ''}">
          <label>Rechten medewerker</label>
          <div class="permission-grid">${permissionCheckboxes(user)}</div>
        </div>
        <div class="form-actions"><button class="btn" onclick="closeModal()">Annuleren</button><button class="btn accent" onclick="saveUser(${index === null ? 'null' : index})">Opslaan</button></div>
      </div>`);
  }
  async function saveUser(index){ try{ await postJSON('/api/manage/user-save', { index, name: document.getElementById('userName').value, role: document.getElementById('userRole').value, pin: document.getElementById('userPin').value, permissions: collectUserPermissions() }); closeModal(); await loadData(); toast('Medewerker opgeslagen'); }catch(err){ toast(err.message, 'error'); } }
  async function deleteUser(index){ try{ await postJSON('/api/manage/user-delete', { index }); await loadData(); toast('Medewerker verwijderd'); }catch(err){ toast(err.message, 'error'); } }
  function renderUsers(){ const items = safeArray(appData.auth?.users); renderList('usersList', items, (user, index) => `
    <div class="list-item"><div class="item-top"><div><div class="item-title">${user.name || 'Medewerker'}</div><div class="item-sub">Rol: ${user.role || 'medewerker'}</div></div><span class="badge accent">${user.role || 'medewerker'}</span></div><div class="meta-row"><span class="meta-chip">Code: ${user.pin || '-'}</span><span class="meta-chip">${permissionSummary(user)}</span></div><div class="item-actions"><button class="btn accent" onclick="openUserModal(${index})">Bewerken</button><button class="btn danger" onclick="confirmAction('Medewerker verwijderen','Weet je zeker dat je deze medewerker wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteUser',${index})&quot;)">Verwijderen</button></div></div>`, 'Nog geen gebruikers gevonden.'); }

  function renderDiensten(){
    const diensten = safeArray(appData.general.diensten);
    const canManageDiensten = hasPermission('manage_diensten');
    renderList(
      'dienstenList',
      diensten,
      (item, index) => `
        <div class="list-item">
          <div class="item-top">
            <div>
              <div class="item-title">${item.naam || item.medewerker || 'Dienst'}</div>
              <div class="item-sub">${item.datum || 'Geen datum'}${item.tijd ? ' · ' + item.tijd : ''}</div>
            </div>
            <span class="badge">${item.rol || 'Dienst'}</span>
          </div>
          ${canManageDiensten ? `<div class="item-actions"><button class="btn accent" onclick="openDienstModal(${index})">Bewerken</button><button class="btn danger" onclick="confirmAction('Dienst verwijderen','Weet je zeker dat je deze dienst wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteDienst',${index})&quot;)">Verwijderen</button></div>` : ''}
        </div>
      `,
      'Nog geen diensten gevonden.'
    );
  }
    function renderAll(){
    applyPermissions();
    const newDienstBtn = document.getElementById('newDienstBtn');
    if (newDienstBtn) newDienstBtn.style.display = hasPermission('manage_diensten') ? '' : 'none';
    initFilters();
    renderDashboard();
    renderGeneralOverview();
    renderCoolers();
    renderTypes();
    renderLocations();
    renderStockAlerts();
    renderFill();
    renderDiensten();
    renderDienstTypes();
    renderUsers();
    renderKitchen();
    renderKitchenOverview();
    renderKitchenManagePage();
    renderBarTasks();
    renderBarTaskManagePage();
    renderRecipes();
    renderBarOverview();
    if (currentPage === 'bar-koeling-detail' && currentKoelingId){
      renderKoelingDetail();
    }
    if (currentPage === 'keuken-takenlijst-detail' && currentKitchenListId){
      renderKitchenListDetail();
    }
    if (currentPage === 'bar-takenlijst-detail' && currentBarListId){
      renderBarTaskListDetail();
    }
  }

  async function loadData(){
    const res = await fetch('/api/casa-data');
    if (res.status === 401) { window.location.href = '/casa-cara-login'; return; }
    appData = await res.json();
    renderAll();
  }

  function dienstTypeOptions(selected=''){
    const items = safeArray(appData.dienst_types);
    return items.map(item => `<option value="${item.naam}" ${item.naam === selected ? 'selected' : ''}>${item.naam}</option>`).join('');
  }

  function getDienstTypeByName(name){
    return safeArray(appData.dienst_types).find(item => item.naam === name) || {};
  }

  function updateDienstTimePreview(){
    const name = document.getElementById('dienstNaam')?.value || '';
    const item = getDienstTypeByName(name);
    const text = item.start || item.einde ? `${item.start || '--:--'} - ${item.einde || '--:--'}` : 'Geen tijden ingesteld';
    const el = document.getElementById('dienstTimePreview');
    if (el) el.textContent = text;
  }

  function openDienstTypeModal(name=''){
    const item = safeArray(appData.dienst_types).find(x => x.naam === name) || {};
    openModal(
      name ? 'Dienstsoort bewerken' : 'Dienstsoort toevoegen',
      'Beheer hier de soorten diensten die je later kunt selecteren.',
      `
        <div class="form-grid">
          <div class="field"><label>Naam dienstsoort</label><input id="dienstTypeName" value="${item.naam || name || ''}" placeholder="Bijv. Keukendienst"></div>
          <div class="field"><label>Begintijd</label><input id="dienstTypeStart" type="time" value="${item.start || ''}"></div>
          <div class="field"><label>Eindtijd</label><input id="dienstTypeEinde" type="time" value="${item.einde || ''}"></div>
          <div class="form-actions">
            <button class="btn" onclick="closeModal()">Annuleren</button>
            <button class="btn accent" onclick="saveDienstType('${encodeURIComponent(name || '')}')">Opslaan</button>
          </div>
        </div>
      `
    );
  }

  async function saveDienstType(originalEncoded){
    const original = originalEncoded ? decodeURIComponent(originalEncoded) : '';
    try{
      await postJSON('/api/manage/dienst-type-save', {
        original,
        name: document.getElementById('dienstTypeName').value,
        start: document.getElementById('dienstTypeStart').value,
        einde: document.getElementById('dienstTypeEinde').value
      });
      closeModal();
      await loadData();
      toast('Dienstsoort opgeslagen');
    }catch(err){ toast(err.message, 'error'); }
  }

  async function deleteDienstType(encodedName){
    const name = decodeURIComponent(encodedName);
    try{
      await postJSON('/api/manage/dienst-type-delete', { name });
      await loadData();
      toast('Dienstsoort verwijderd');
    }catch(err){ toast(err.message, 'error'); }
  }

  function openTipsModal(){
    openModal(
      'Fooienpot aanpassen',
      (appData.general.fooienpot_is_personal ? 'Voer een bedrag in voor jouw eigen fooienpot.' : 'Voer een bedrag in en kies of dit erbij of eraf moet.'),
      `
        <div class="form-grid">
          <div class="field">
            <label>Huidige stand</label>
            <input value="${euro(appData.general.fooienpot || 0)}" disabled>
          </div>
          <div class="field">
            <label>Bedrag</label>
            <input id="tipsAmount" type="number" step="0.01" placeholder="Bijv. 12.50">
          </div>
          <div class="form-actions">
            <button class="btn" onclick="closeModal()">Annuleren</button>
            <button class="btn danger" onclick="saveTips('subtract')">Afhalen</button>
            <button class="btn accent" onclick="saveTips('add')">Toevoegen</button>
          </div>
        </div>
      `
    );
  }

  async function saveTips(mode){
    const amount = Number(document.getElementById('tipsAmount').value || 0);
    try{
      await postJSON('/api/manage/tips-adjust', { amount, mode });
      closeModal();
      await loadData();
      toast('Fooienpot bijgewerkt');
    }catch(err){ toast(err.message, 'error'); }
  }

  function openDienstModal(index=null){
    const item = index !== null ? safeArray(appData.general.diensten)[index] || {} : {};
    openModal(
      index === null ? 'Dienst toevoegen' : 'Dienst bewerken',
      'Kies een dienstsoort en vul daarna alleen datum en eventueel een notitie in.',
      `
        <div class="form-grid">
          <div class="field">
            <label>Dienstsoort</label>
            <select id="dienstNaam" onchange="updateDienstTimePreview()">${dienstTypeOptions(item.naam || item.medewerker || '')}</select>
          </div>
          <div class="field">
            <label>Begintijd - eindtijd</label>
            <input id="dienstTimePreview" value="" disabled>
          </div>
          <div class="field"><label>Datum</label><input id="dienstDatum" type="date" value="${item.datum || ''}"></div>
          <div class="field"><label>Notitie</label><input id="dienstRol" value="${item.rol || ''}" placeholder="Bijv. Floor / Extra druk"></div>
          ${hasPermission('manage_dienst_types') ? `<div class="actions"><button class="btn" onclick="openDienstTypeModal()">Dienstsoort toevoegen</button><button class="btn" onclick="openPage('dienstsoorten'); closeModal()">Beheer dienstsoorten</button></div>` : ''}
          <div class="form-actions">
            <button class="btn" onclick="closeModal()">Annuleren</button>
            <button class="btn accent" onclick="saveDienst(${index === null ? 'null' : index})">Opslaan</button>
          </div>
        </div>
      `
    );
    updateDienstTimePreview();
  }

  async function saveDienst(index){
    const dienstNaam = document.getElementById('dienstNaam').value;
    const dienstType = getDienstTypeByName(dienstNaam);
    const payload = {
      index,
      naam: dienstNaam,
      datum: document.getElementById('dienstDatum').value,
      tijd: `${dienstType.start || ''}${dienstType.start || dienstType.einde ? ' - ' : ''}${dienstType.einde || ''}`,
      rol: document.getElementById('dienstRol').value,
    };
    try{
      await postJSON('/api/manage/dienst-save', payload);
      closeModal();
      await loadData();
      toast('Dienst opgeslagen');
    }catch(err){ toast(err.message, 'error'); }
  }

  async function deleteDienst(index){
    try{
      await postJSON('/api/manage/dienst-delete', { index });
      await loadData();
      toast('Dienst verwijderd');
    }catch(err){ toast(err.message, 'error'); }
  }

  function openLocationModal(encodedName=null){
    const name = encodedName ? decodeURIComponent(encodedName) : '';
    openModal(
      name ? 'Locatie bewerken' : 'Locatie toevoegen',
      'Voeg een locatie toe of wijzig een bestaande naam.',
      `
        <div class="form-grid">
          <div class="field"><label>Naam</label><input id="locationName" value="${name}"></div>
          <div class="form-actions">
            <button class="btn" onclick="closeModal()">Annuleren</button>
            <button class="btn accent" onclick="saveLocation('${encodedName || ''}')">Opslaan</button>
          </div>
        </div>
      `
    );
  }

  async function saveLocation(originalEncoded){
    const original = originalEncoded ? decodeURIComponent(originalEncoded) : '';
    try{
      await postJSON('/api/manage/location-save', { original, name: document.getElementById('locationName').value });
      closeModal();
      await loadData();
      toast('Locatie opgeslagen');
    }catch(err){ toast(err.message, 'error'); }
  }

  async function deleteLocation(encodedName){
    const name = decodeURIComponent(encodedName);
    try{
      await postJSON('/api/manage/location-delete', { name });
      await loadData();
      toast('Locatie verwijderd');
    }catch(err){ toast(err.message, 'error'); }
  }

  function typeOptions(selected=''){
    return safeArray(appData.locations).map(loc => `<option value="${loc}" ${loc === selected ? 'selected' : ''}>${loc}</option>`).join('');
  }

  function openTypeModal(encodedName=null){
    const current = encodedName ? safeArray(appData.types).find(t => t.naam === decodeURIComponent(encodedName)) || {} : {};
    openModal(
      current.naam ? 'Productsoort bewerken' : 'Productsoort toevoegen',
      'Koppel een productsoort direct aan een locatie.',
      `
        <div class="form-grid">
          <div class="field"><label>Naam</label><input id="typeName" value="${current.naam || ''}"></div>
          <div class="field">
            <label>Locatie</label>
            <select id="typeLocation">${typeOptions(current.locatie || '-')}</select>
          </div>
          <div class="form-actions">
            <button class="btn" onclick="closeModal()">Annuleren</button>
            <button class="btn accent" onclick="saveType('${encodedName || ''}')">Opslaan</button>
          </div>
        </div>
      `
    );
  }

  async function saveType(originalEncoded){
    const original = originalEncoded ? decodeURIComponent(originalEncoded) : '';
    try{
      await postJSON('/api/manage/type-save', {
        original,
        naam: document.getElementById('typeName').value,
        locatie: document.getElementById('typeLocation').value,
      });
      closeModal();
      await loadData();
      toast('Productsoort opgeslagen');
    }catch(err){ toast(err.message, 'error'); }
  }

  async function deleteType(encodedName){
    const name = decodeURIComponent(encodedName);
    try{
      await postJSON('/api/manage/type-delete', { name });
      await loadData();
      toast('Productsoort verwijderd');
    }catch(err){ toast(err.message, 'error'); }
  }

  function openKoelingModal(id=null){
    const koeling = id ? safeArray(appData.bar.koelingen).find(k => k.id === id) || {} : {};
    openModal(
      id ? 'Koeling bewerken' : 'Koeling toevoegen',
      'Voeg een koeling toe of wijzig de naam.',
      `
        <div class="form-grid">
          <div class="field"><label>Naam</label><input id="koelingNaam" value="${koeling.naam || ''}"></div>
          <div class="form-actions">
            <button class="btn" onclick="closeModal()">Annuleren</button>
            <button class="btn accent" onclick="saveKoeling('${id || ''}')">Opslaan</button>
          </div>
        </div>
      `
    );
  }

  async function saveKoeling(id){
    try{
      await postJSON('/api/manage/koeling-save', { id: id || null, naam: document.getElementById('koelingNaam').value });
      closeModal();
      await loadData();
      toast('Koeling opgeslagen');
    }catch(err){ toast(err.message, 'error'); }
  }

  async function deleteKoeling(id){
    try{
      await postJSON('/api/manage/koeling-delete', { id });
      await loadData();
      toast('Koeling verwijderd');
    }catch(err){ toast(err.message, 'error'); }
  }

  function productTypeOptions(selected=''){
    const items = safeArray(appData.types);
    return items.map(t => `<option value="${t.naam}" ${t.naam === selected ? 'selected' : ''}>${t.naam}</option>`).join('') || '<option value="Overig">Overig</option>';
  }

  function openProductModal(koelingId, productId=null){
    const koeling = safeArray(appData.bar.koelingen).find(k => k.id === koelingId) || {};
    const product = productId ? safeArray(koeling.producten).find(p => p.id === productId) || {} : {};
    openModal(
      productId ? 'Product bewerken' : 'Product toevoegen',
      `Koeling: ${koeling.naam || 'Onbekend'}`,
      `
        <div class="form-grid">
          <div class="field"><label>Naam</label><input id="productNaam" value="${product.naam || ''}"></div>
          <div class="field"><label>Voorraad</label><input id="productVoorraad" type="number" value="${product.voorraad ?? 0}"></div>
          <div class="field"><label>Minimum</label><input id="productMinimum" type="number" value="${product.minimum ?? 0}"></div>
          <div class="field"><label>Soort</label><select id="productSoort">${productTypeOptions(product.soort || 'Overig')}</select></div>
          <div class="form-actions">
            <button class="btn" onclick="closeModal()">Annuleren</button>
            <button class="btn accent" onclick="saveProduct('${koelingId}','${productId || ''}')">Opslaan</button>
          </div>
        </div>
      `
    );
  }

  async function saveProduct(koelingId, productId){
    try{
      await postJSON('/api/manage/product-save', {
        koeling_id: koelingId,
        product_id: productId || null,
        naam: document.getElementById('productNaam').value,
        voorraad: document.getElementById('productVoorraad').value,
        minimum: document.getElementById('productMinimum').value,
        soort: document.getElementById('productSoort').value,
      });
      closeModal();
      await loadData();
      toast('Product opgeslagen');
    }catch(err){ toast(err.message, 'error'); }
  }

  async function deleteProduct(koelingId, productId){
    try{
      await postJSON('/api/manage/product-delete', { koeling_id: koelingId, product_id: productId });
      await loadData();
      toast('Product verwijderd');
    }catch(err){ toast(err.message, 'error'); }
  }

  async function quickFill(koelingId, productId, minimum){
    const koeling = safeArray(appData.bar.koelingen).find(k => k.id === koelingId) || {};
    const product = safeArray(koeling.producten).find(p => p.id === productId) || {};
    try{
      await postJSON('/api/manage/product-save', {
        koeling_id: koelingId,
        product_id: productId,
        naam: product.naam,
        voorraad: minimum,
        minimum: minimum,
        soort: product.soort || 'Overig',
        op: false,
      });
      await loadData();
      toast('Product op minimum gezet');
    }catch(err){ toast(err.message, 'error'); }
  }

  async function markProductOp(koelingId, productId){
    try{
      await postJSON('/api/manage/product-mark-op', { koeling_id: koelingId, product_id: productId });
      await loadData();
      toast('Product staat nu op de OP-lijst');
    }catch(err){ toast(err.message, 'error'); }
  }

  async function markProductAvailable(koelingId, productId){
    try{
      await postJSON('/api/manage/product-mark-available', { koeling_id: koelingId, product_id: productId });
      await loadData();
      toast('Product weer op voorraad gezet');
    }catch(err){ toast(err.message, 'error'); }
  }

  document.addEventListener('dblclick', function(e){ e.preventDefault(); }, { passive:false });
  document.addEventListener('keydown', function(e){ if (e.key === 'Escape') closeDrawer(); });

  openPage('dashboard');
  loadData();
</script>
</body>
</html>
"""

@casa_cara.route("/casa")
@casa_cara.route("/casa-cara")
def casa():
    return render_template_string(HTML)


@casa_cara.route("/api/bot", methods=["POST"])
def casa_bot():
    data = request.get_json(silent=True) or {}
    question_raw = (data.get("question") or "").strip()
    if not question_raw:
        return jsonify({"ok": False, "message": "Stel eerst een vraag."}), 400

    question = question_raw.lower().strip()
    user = get_current_casa_user() or {}
    user_name = (user.get("name") or "").strip()
    first_name = user_name.split()[0] if user_name else ""
    bar_data = get_bar_data()
    general_data = get_general_data()
    kitchen_data = get_kitchen_data()
    recipes_data = get_recipes_data()
    fill_items = build_fill_items(bar_data)
    tip_context = get_tip_context()

    affirmatives = {"ja", "ja graag", "graag", "isgoed", "is goed", "zeker", "ok", "oke", "prima", "doe maar", "top", "yes", "yess", "helemaal goed"}
    negatives = {"nee", "nee hoor", "laat maar", "hoeft niet", "niet nodig", "nu even niet"}
    pending = session.get("casa_bot_pending") or {}

    def contains(*terms):
        return any(term in question for term in terms)

    def contains_all(*terms):
        return all(term in question for term in terms)

    def normalize_compact(value: str):
        return ''.join(ch for ch in value.lower() if ch.isalnum())

    compact_question = normalize_compact(question)

    def compact_contains(*terms):
        return any(normalize_compact(term) in compact_question for term in terms)

    def tip_amount_text():
        amount = float(tip_context.get("amount", 0) or 0)
        return f"€ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    if pending:
        intent = pending.get("intent")
        if question in affirmatives or contains("ja", "zeker", "is goed", "open maar", "graag", "prima", "doe maar"):
            session.pop("casa_bot_pending", None)
            if intent == "open_bijvuloverzicht":
                return jsonify({
                    "ok": True,
                    "answer": "Top, ik open meteen het bijvuloverzicht voor je.",
                    "open_page": "bar-bijvullen",
                    "actions": []
                })
            if intent == "open_takenlijsten":
                return jsonify({
                    "ok": True,
                    "answer": "Helemaal goed, ik stuur je door naar de takenlijsten.",
                    "open_page": "keuken-takenlijsten",
                    "actions": []
                })
            if intent == "open_diensten":
                return jsonify({
                    "ok": True,
                    "answer": "Komt voor elkaar, ik open de dienstenpagina.",
                    "open_page": "diensten",
                    "actions": []
                })
        if question in negatives or contains("nee", "laat maar", "hoeft niet", "nu even niet"):
            session.pop("casa_bot_pending", None)
            return jsonify({
                "ok": True,
                "answer": "Is goed 😄 Dan blijf je gewoon hier. Vraag maar raak als je iets anders wilt weten.",
                "actions": []
            })

    if contains("hoi", "hallo", "hey", "hee", "goedemorgen", "goedemiddag", "goedenavond") or compact_contains("hi", "hii", "heyy"):
        name_part = f" {first_name}" if first_name else ""
        return jsonify({
            "ok": True,
            "answer": f"Hoi{name_part}! 😄 Waar kan ik je mee helpen? Je kunt me bijvoorbeeld iets vragen over bijvullen, takenlijsten, recepten, diensten of de fooienpot.",
            "actions": []
        })

    if (
        contains("bijvullen", "lage voorraad", "wat moet ik vullen", "bijvul", "is er iets om bij te vullen", "moet er iets bijgevuld worden", "moet ik iets bijvullen")
        or contains_all("bij", "vullen")
        or compact_contains("bijtevullen", "bijte vullen", "bijvullen", "bijgevuld", "navullen", "aanvullen")
        or (contains("voorraad") and contains("vullen", "aanvullen", "bijvullen"))
    ):
        if not fill_items:
            session.pop("casa_bot_pending", None)
            return jsonify({
                "ok": True,
                "answer": "Er staat nu niets open om bijgevuld te worden 👍",
                "actions": []
            })
        total = len(fill_items)
        first = fill_items[0]
        focus = first.get("product") or "een product"
        session["casa_bot_pending"] = {"intent": "open_bijvuloverzicht"}
        return jsonify({
            "ok": True,
            "answer": f"Ja, er moeten zeker wat producten worden bijgevuld. Ik zie nu {total} producten die aandacht vragen. {focus} springt er in ieder geval uit. Wil je dat ik je naar het bijvuloverzicht stuur?",
            "pending_action": "open_bijvuloverzicht",
            "actions": [
                {"type": "send_text", "label": "Ja graag", "value": "Ja graag"},
                {"type": "send_text", "label": "Nee", "value": "Nee"}
            ],
            "hint": "Typ ook gerust ja, is goed, zeker of nee."
        })

    if contains("fooien", "fooienpot", "tips", "tipjar", "fooi"):
        label = tip_context.get("label", "Fooienpot")
        owner = f" van {user_name}" if user_name and tip_context.get("is_personal") else ""
        return jsonify({
            "ok": True,
            "answer": f"{label}{owner} staat nu op {tip_amount_text()}.",
            "actions": []
        })

    if contains("dienst", "diensten", "rooster") or compact_contains("wanneerwerkik", "mijndiensten"):
        diensten = general_data.get("diensten", []) or []
        if not diensten:
            session.pop("casa_bot_pending", None)
            return jsonify({"ok": True, "answer": "Er staan nu nog geen diensten in Casa Cara.", "actions": []})
        first = diensten[0]
        naam = (first.get("naam") or first.get("medewerker") or first.get("persoon") or "Dienst").strip()
        datum = (first.get("datum") or first.get("date") or "onbekende datum").strip()
        session["casa_bot_pending"] = {"intent": "open_diensten"}
        return jsonify({
            "ok": True,
            "answer": f"Er staan op dit moment {len(diensten)} diensten in het systeem. De eerstvolgende die ik zie is {naam} op {datum}. Wil je dat ik de dienstenpagina voor je open?",
            "pending_action": "open_diensten",
            "actions": [
                {"type": "send_text", "label": "Ja", "value": "Ja"},
                {"type": "send_text", "label": "Nee", "value": "Nee"}
            ]
        })

    if contains("taken", "takenlijst", "takenlijsten", "afgevinkt") or compact_contains("watmoetikdoen", "welketaken"):
        lists = kitchen_data.get("lists", []) or []
        if not lists:
            session.pop("casa_bot_pending", None)
            return jsonify({"ok": True, "answer": "Er zijn nog geen takenlijsten beschikbaar.", "actions": []})
        open_count = 0
        for lst in lists:
            tasks = lst.get("tasks", []) or []
            if any(not t.get("done") for t in tasks):
                open_count += 1
        session["casa_bot_pending"] = {"intent": "open_takenlijsten"}
        return jsonify({
            "ok": True,
            "answer": f"Je hebt nu {len(lists)} takenlijsten. Daarvan hebben er {open_count} nog openstaande taken. Wil je dat ik de takenlijsten voor je open?",
            "pending_action": "open_takenlijsten",
            "actions": [
                {"type": "send_text", "label": "Zeker", "value": "Zeker"},
                {"type": "send_text", "label": "Nee", "value": "Nee"}
            ]
        })

    if contains("recept", "cocktail", "maken", "ingrediënten", "ingredienten") or compact_contains("hoemaakik", "hoemaakje", "hoemaak", "hoemaakik"):
        items = recipes_data.get("items", []) or []
        if not items:
            return jsonify({"ok": True, "answer": "Er staan nog geen recepten in Casa Cara.", "actions": []})
        for recipe in items:
            name = (recipe.get("naam") or "").strip()
            if name and name.lower() in question:
                ingrediënten = recipe.get("ingredienten") or recipe.get("ingredients") or []
                if isinstance(ingrediënten, list):
                    ingrediënten_text = ", ".join(str(x) for x in ingrediënten[:5] if str(x).strip())
                else:
                    ingrediënten_text = str(ingrediënten).strip()
                return jsonify({
                    "ok": True,
                    "answer": f"Ik heb het recept voor {name} gevonden." + (f" De belangrijkste ingrediënten zijn: {ingrediënten_text}." if ingrediënten_text else ""),
                    "actions": []
                })
        matches = [r.get("naam") for r in items if (r.get("naam") or "").strip()]
        suggesties = ", ".join(matches[:4]) if matches else "geen"
        return jsonify({
            "ok": True,
            "answer": f"Ik kon dat recept niet exact vinden. Probeer bijvoorbeeld: {suggesties}.",
            "actions": []
        })

    session.pop("casa_bot_pending", None)
    return jsonify({
        "ok": True,
        "answer": "Ik help je graag met bijvullen, fooienpot, diensten, takenlijsten en recepten. Begin bijvoorbeeld met: hoi, is er iets om bij te vullen, of hoe staat de fooienpot ervoor?",
        "actions": []
    })


@casa_cara.route("/api/casa-data")
def api_casa_data():
    return jsonify(serialize_app_data())

@casa_cara.route("/api/bar")
def api_bar():
    bar_data = get_bar_data()
    return jsonify({
        "koelingen": bar_data.get("koelingen", []),
        "fill_items": build_fill_items(bar_data),
    })

@casa_cara.route("/api/general")
def api_general():
    return jsonify(get_general_data())

@casa_cara.route("/api/product-types")
def api_product_types():
    return jsonify(get_types())

@casa_cara.route("/api/locations")
def api_locations():
    return jsonify(get_locations())

@casa_cara.route("/api/manage/tips-adjust", methods=["POST"])
def manage_tips_adjust():
    if not has_casa_permission("manage_tips"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    amount = payload.get("amount", 0)
    mode = (payload.get("mode") or "add").strip()
    try:
        amount = float(amount)
    except Exception:
        return jsonify({"ok": False, "message": "Ongeldig bedrag."}), 400
    if amount < 0:
        return jsonify({"ok": False, "message": "Gebruik een positief bedrag."}), 400

    data = get_general_data()
    user = get_current_casa_user() or {}

    if user.get("role") == "medewerker":
        name = (user.get("name") or "").strip()
        per_user = data.get("fooienpot_per_user", {}) or {}
        current = float(per_user.get(name, 0) or 0)
        if mode == "subtract":
            current -= amount
        else:
            current += amount
        per_user[name] = round(current, 2)
        data["fooienpot_per_user"] = per_user
    else:
        current = float(data.get("fooienpot", 0) or 0)
        if mode == "subtract":
            current -= amount
        else:
            current += amount
        data["fooienpot"] = round(current, 2)

    save_general_data(data)
    return jsonify({"ok": True})

@casa_cara.route("/api/manage/dienst-save", methods=["POST"])
def manage_dienst_save():
    if not has_casa_permission("manage_diensten"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    naam = (payload.get("naam") or "").strip()
    datum = (payload.get("datum") or "").strip()
    tijd = (payload.get("tijd") or "").strip()
    rol = (payload.get("rol") or "").strip()
    if not naam:
        return jsonify({"ok": False, "message": "Vul een naam in."}), 400

    data = get_general_data()
    diensten = data.get("diensten", [])
    item = {"naam": naam, "datum": datum, "tijd": tijd, "rol": rol}
    index = payload.get("index", None)
    if index is None:
        diensten.append(item)
    else:
        try:
            index = int(index)
            diensten[index] = item
        except Exception:
            return jsonify({"ok": False, "message": "Ongeldige dienst."}), 400
    data["diensten"] = diensten
    save_general_data(data)
    return jsonify({"ok": True})

@casa_cara.route("/api/manage/dienst-delete", methods=["POST"])
def manage_dienst_delete():
    if not has_casa_permission("manage_diensten"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    try:
        index = int(payload.get("index"))
    except Exception:
        return jsonify({"ok": False, "message": "Ongeldige dienst."}), 400
    data = get_general_data()
    diensten = data.get("diensten", [])
    if index < 0 or index >= len(diensten):
        return jsonify({"ok": False, "message": "Dienst niet gevonden."}), 404
    diensten.pop(index)
    data["diensten"] = diensten
    save_general_data(data)
    return jsonify({"ok": True})

@casa_cara.route("/api/manage/location-save", methods=["POST"])
def manage_location_save():
    if not has_casa_permission("manage_locations"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    original = (payload.get("original") or "").strip()
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "message": "Vul een locatienaam in."}), 400

    locations = get_locations()
    if original and original in locations:
        locations = [name if x == original else x for x in locations]
    else:
        locations.append(name)
    save_locations(locations)

    types = get_types()
    changed = False
    for item in types:
        if item.get("locatie") == original:
            item["locatie"] = name
            changed = True
    if changed:
        save_types(types)
    return jsonify({"ok": True})

@casa_cara.route("/api/manage/location-delete", methods=["POST"])
def manage_location_delete():
    if not has_casa_permission("manage_locations"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "message": "Locatie ontbreekt."}), 400
    locations = [x for x in get_locations() if x != name]
    save_locations(locations)

    types = get_types()
    changed = False
    for item in types:
        if item.get("locatie") == name:
            item["locatie"] = "-"
            changed = True
    if changed:
        save_types(types)
    return jsonify({"ok": True})

@casa_cara.route("/api/manage/type-save", methods=["POST"])
def manage_type_save():
    if not has_casa_permission("manage_types"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    original = (payload.get("original") or "").strip()
    naam = (payload.get("naam") or "").strip()
    locatie = (payload.get("locatie") or "-").strip() or "-"
    if not naam:
        return jsonify({"ok": False, "message": "Vul een productsoort in."}), 400

    types = get_types()
    replaced = False
    for item in types:
      if item["naam"] == original and original:
        item["naam"] = naam
        item["locatie"] = locatie
        replaced = True
        break
    if not replaced:
        types.append({"naam": naam, "locatie": locatie})
    deduped = {}
    for item in types:
        deduped[item["naam"]] = {"naam": item["naam"], "locatie": item["locatie"]}
    save_types(sorted(deduped.values(), key=lambda x: x["naam"].lower()))

    bar = get_bar_data()
    if original and original != naam:
        for koeling in bar.get("koelingen", []):
            for product in koeling.get("producten", []):
                if product.get("soort") == original:
                    product["soort"] = naam
        save_bar_data(bar)
    return jsonify({"ok": True})

@casa_cara.route("/api/manage/type-delete", methods=["POST"])
def manage_type_delete():
    if not has_casa_permission("manage_types"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "message": "Productsoort ontbreekt."}), 400
    types = [x for x in get_types() if x["naam"] != name]
    save_types(types)

    bar = get_bar_data()
    for koeling in bar.get("koelingen", []):
        for product in koeling.get("producten", []):
            if product.get("soort") == name:
                product["soort"] = "Overig"
    save_bar_data(bar)
    return jsonify({"ok": True})

@casa_cara.route("/api/manage/koeling-save", methods=["POST"])
def manage_koeling_save():
    if not has_casa_permission("manage_coolers"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    koeling_id = payload.get("id")
    naam = (payload.get("naam") or "").strip()
    if not naam:
        return jsonify({"ok": False, "message": "Vul een naam in."}), 400

    bar = get_bar_data()
    koelingen = bar.get("koelingen", [])
    if koeling_id:
        for koeling in koelingen:
            if koeling.get("id") == koeling_id:
                koeling["naam"] = naam
                save_bar_data(bar)
                return jsonify({"ok": True})
        return jsonify({"ok": False, "message": "Koeling niet gevonden."}), 404

    new_id = slugify(naam)
    existing = {k.get("id") for k in koelingen}
    base = new_id
    count = 2
    while new_id in existing:
        new_id = f"{base}_{count}"
        count += 1
    koelingen.append({"id": new_id, "naam": naam, "producten": []})
    save_bar_data(bar)
    return jsonify({"ok": True})

@casa_cara.route("/api/manage/koeling-delete", methods=["POST"])
def manage_koeling_delete():
    if not has_casa_permission("manage_coolers"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    koeling_id = payload.get("id")
    if not koeling_id:
        return jsonify({"ok": False, "message": "Koeling ontbreekt."}), 400
    bar = get_bar_data()
    before = len(bar.get("koelingen", []))
    bar["koelingen"] = [k for k in bar.get("koelingen", []) if k.get("id") != koeling_id]
    if len(bar["koelingen"]) == before:
        return jsonify({"ok": False, "message": "Koeling niet gevonden."}), 404
    save_bar_data(bar)
    return jsonify({"ok": True})

@casa_cara.route("/api/manage/product-save", methods=["POST"])
def manage_product_save():
    payload = request.get_json(silent=True) or {}
    koeling_id = payload.get("koeling_id")
    product_id = payload.get("product_id")
    naam = (payload.get("naam") or "").strip()
    soort = (payload.get("soort") or "Overig").strip() or "Overig"
    try:
        voorraad = int(payload.get("voorraad", 0) or 0)
        minimum = int(payload.get("minimum", 0) or 0)
    except Exception:
        return jsonify({"ok": False, "message": "Voorraad of minimum is ongeldig."}), 400

    if not koeling_id or not naam:
        return jsonify({"ok": False, "message": "Koeling en productnaam zijn verplicht."}), 400

    if not is_casa_admin() and not product_id and not has_casa_permission("manage_products"):
        return permission_denied_response()

    bar = get_bar_data()
    koeling = next((k for k in bar.get("koelingen", []) if k.get("id") == koeling_id), None)
    if not koeling:
        return jsonify({"ok": False, "message": "Koeling niet gevonden."}), 404

    koeling.setdefault("producten", [])
    if product_id:
        for product in koeling["producten"]:
            if product.get("id") == product_id:
                if not is_casa_admin():
                    immutable_changed = (product.get("naam") != naam) or ((product.get("soort") or "Overig") != soort) or int(product.get("minimum", 0) or 0) != minimum
                    if immutable_changed and not has_casa_permission("manage_products"):
                        return permission_denied_response()
                    if not has_casa_permission("adjust_stock"):
                        return permission_denied_response("Je mag alleen voorraad aanpassen als je daar rechten voor hebt.")
                product["naam"] = naam
                product["voorraad"] = voorraad
                product["minimum"] = minimum
                product["soort"] = soort
                if "op" in payload:
                    product["op"] = bool(payload.get("op"))
                else:
                    product["op"] = bool(product.get("op"))
                save_bar_data(bar)
                return jsonify({"ok": True})
        return jsonify({"ok": False, "message": "Product niet gevonden."}), 404

    if not has_casa_permission("manage_products"):
        return permission_denied_response()
    new_id = slugify(naam)
    existing = {p.get("id") for p in koeling.get("producten", [])}
    base = new_id
    count = 2
    while new_id in existing:
        new_id = f"{base}_{count}"
        count += 1
    koeling["producten"].append({
        "id": new_id,
        "naam": naam,
        "voorraad": voorraad,
        "minimum": minimum,
        "soort": soort,
        "op": bool(payload.get("op", False)),
    })
    save_bar_data(bar)
    return jsonify({"ok": True})

@casa_cara.route("/api/manage/product-delete", methods=["POST"])
def manage_product_delete():
    if not has_casa_permission("manage_products"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    koeling_id = payload.get("koeling_id")
    product_id = payload.get("product_id")
    if not koeling_id or not product_id:
        return jsonify({"ok": False, "message": "Koeling of product ontbreekt."}), 400

    bar = get_bar_data()
    koeling = next((k for k in bar.get("koelingen", []) if k.get("id") == koeling_id), None)
    if not koeling:
        return jsonify({"ok": False, "message": "Koeling niet gevonden."}), 404

    before = len(koeling.get("producten", []))
    koeling["producten"] = [p for p in koeling.get("producten", []) if p.get("id") != product_id]
    if len(koeling["producten"]) == before:
        return jsonify({"ok": False, "message": "Product niet gevonden."}), 404

    save_bar_data(bar)
    return jsonify({"ok": True})


@casa_cara.route("/api/manage/product-mark-op", methods=["POST"])
def manage_product_mark_op():
    if not has_casa_permission("adjust_stock"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    koeling_id = payload.get("koeling_id")
    product_id = payload.get("product_id")
    if not koeling_id or not product_id:
        return jsonify({"ok": False, "message": "Koeling of product ontbreekt."}), 400

    bar = get_bar_data()
    koeling = next((k for k in bar.get("koelingen", []) if k.get("id") == koeling_id), None)
    if not koeling:
        return jsonify({"ok": False, "message": "Koeling niet gevonden."}), 404

    for product in koeling.get("producten", []):
        if product.get("id") == product_id:
            product["op"] = True
            save_bar_data(bar)
            return jsonify({"ok": True})

    return jsonify({"ok": False, "message": "Product niet gevonden."}), 404


@casa_cara.route("/api/manage/product-mark-available", methods=["POST"])
def manage_product_mark_available():
    if not has_casa_permission("adjust_stock"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    koeling_id = payload.get("koeling_id")
    product_id = payload.get("product_id")
    if not koeling_id or not product_id:
        return jsonify({"ok": False, "message": "Koeling of product ontbreekt."}), 400

    bar = get_bar_data()
    koeling = next((k for k in bar.get("koelingen", []) if k.get("id") == koeling_id), None)
    if not koeling:
        return jsonify({"ok": False, "message": "Koeling niet gevonden."}), 404

    for product in koeling.get("producten", []):
        if product.get("id") == product_id:
            product["op"] = False
            save_bar_data(bar)
            return jsonify({"ok": True})

    return jsonify({"ok": False, "message": "Product niet gevonden."}), 404


@casa_cara.route("/api/manage/dienst-type-save", methods=["POST"])
def manage_dienst_type_save():
    if not is_casa_admin():
        return admin_only_response()
    payload = request.get_json(silent=True) or {}
    original = (payload.get("original") or "").strip()
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "message": "Vul een dienstsoort in."}), 400

    start = (payload.get("start") or "").strip()
    einde = (payload.get("einde") or "").strip()

    items = get_dienst_types()
    replaced = False
    for item in items:
        if original and item.get("naam") == original:
            item["naam"] = name
            item["start"] = start
            item["einde"] = einde
            replaced = True
            break
    if not replaced:
        items.append({"naam": name, "start": start, "einde": einde})
    save_dienst_types(items)

    data = get_general_data()
    changed = False
    for item in data.get("diensten", []):
        if item.get("naam") == original:
            item["naam"] = name
            item["tijd"] = f"{start}{' - ' if (start or einde) else ''}{einde}"
            changed = True
    if changed:
        save_general_data(data)
    return jsonify({"ok": True})


@casa_cara.route("/api/manage/dienst-type-delete", methods=["POST"])
def manage_dienst_type_delete():
    if not is_casa_admin():
        return admin_only_response()
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "message": "Dienstsoort ontbreekt."}), 400

    items = [x for x in get_dienst_types() if (x.get("naam") if isinstance(x, dict) else x) != name]
    save_dienst_types(items)
    return jsonify({"ok": True})


@casa_cara.route("/api/kitchen")
def api_kitchen():
    data = get_kitchen_data()
    today = date.today().isoformat()
    changed = False
    for item in data.get("lists", []):
        for task in item.get("tasks", []):
            if task.get("last_checked") != today and task.get("checked"):
                task["checked"] = False
                task["last_checked"] = ""
                changed = True
            for sub in task.get("subtasks", []):
                if sub.get("last_checked") != today and sub.get("checked"):
                    sub["checked"] = False
                    sub["last_checked"] = ""
                    changed = True
            before = (task.get("checked"), task.get("last_checked"), task.get("last_checked_by"), task.get("last_checked_at"))
            sync_task_with_subtasks(task, today, task.get("last_checked_by", ""), task.get("last_checked_at", ""))
            after = (task.get("checked"), task.get("last_checked"), task.get("last_checked_by"), task.get("last_checked_at"))
            if before != after:
                changed = True
    if changed:
        save_kitchen_data(data)
    return jsonify(data)

@casa_cara.route("/api/kitchen/list-save", methods=["POST"])
def kitchen_list_save():
    if not has_casa_permission("manage_tasklists"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "message": "Vul een naam in voor de takenlijst."}), 400

    data = get_kitchen_data()
    existing = {item.get("id") for item in data.get("lists", [])}
    new_id = slugify(name)
    base = new_id
    count = 2
    while new_id in existing:
        new_id = f"{base}_{count}"
        count += 1

    data["lists"].append({
        "id": new_id,
        "name": name,
        "tasks": []
    })
    save_kitchen_data(data)
    return jsonify({"ok": True})

@casa_cara.route("/api/kitchen/list-delete", methods=["POST"])
def kitchen_list_delete():
    if not has_casa_permission("manage_tasklists"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    data = get_kitchen_data()
    before = len(data.get("lists", []))
    data["lists"] = [item for item in data.get("lists", []) if item.get("id") != list_id]
    if len(data["lists"]) == before:
        return jsonify({"ok": False, "message": "Takenlijst niet gevonden."}), 404
    save_kitchen_data(data)
    return jsonify({"ok": True})

@casa_cara.route("/api/kitchen/task-save", methods=["POST"])
def kitchen_task_save():
    if not has_casa_permission("manage_tasklists"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    name = (payload.get("name") or "").strip()
    if not list_id or not name:
        return jsonify({"ok": False, "message": "Lijst of taak ontbreekt."}), 400

    data = get_kitchen_data()
    for item in data.get("lists", []):
        if item.get("id") == list_id:
            existing = {task.get("id") for task in item.get("tasks", [])}
            new_id = slugify(name)
            base = new_id
            count = 2
            while new_id in existing:
                new_id = f"{base}_{count}"
                count += 1
            item.setdefault("tasks", []).append({
                "id": new_id,
                "name": name,
                "checked": False,
                "last_checked": "",
                "last_checked_by": "",
                "last_checked_at": "",
                "subtasks": []
            })
            save_kitchen_data(data)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Takenlijst niet gevonden."}), 404

@casa_cara.route("/api/kitchen/task-delete", methods=["POST"])
def kitchen_task_delete():
    if not has_casa_permission("manage_tasklists"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    task_id = payload.get("task_id")
    data = get_kitchen_data()
    for item in data.get("lists", []):
        if item.get("id") == list_id:
            before = len(item.get("tasks", []))
            item["tasks"] = [task for task in item.get("tasks", []) if task.get("id") != task_id]
            if len(item["tasks"]) == before:
                return jsonify({"ok": False, "message": "Taak niet gevonden."}), 404
            save_kitchen_data(data)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Takenlijst niet gevonden."}), 404

@casa_cara.route("/api/kitchen/task-toggle", methods=["POST"])
def kitchen_task_toggle():
    if not has_casa_permission("use_tasklists"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    task_id = payload.get("task_id")
    today = date.today().isoformat()
    checked_by = (get_current_casa_user() or {}).get("name", "Onbekend")
    checked_at = datetime.now().isoformat(timespec="minutes")
    data = get_kitchen_data()
    for item in data.get("lists", []):
        if item.get("id") == list_id:
            for task in item.get("tasks", []):
                if task.get("id") == task_id:
                    is_checked = bool(task.get("checked")) and task.get("last_checked") == today
                    task["checked"] = not is_checked
                    task["last_checked"] = today if not is_checked else ""
                    task["last_checked_by"] = checked_by if not is_checked else ""
                    task["last_checked_at"] = checked_at if not is_checked else ""
                    for sub in task.get("subtasks", []):
                        sub["checked"] = not is_checked
                        sub["last_checked"] = today if not is_checked else ""
                        sub["last_checked_by"] = checked_by if not is_checked else ""
                        sub["last_checked_at"] = checked_at if not is_checked else ""
                    save_kitchen_data(data)
                    return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Taak niet gevonden."}), 404

@casa_cara.route("/api/kitchen/subtask-save", methods=["POST"])
def kitchen_subtask_save():
    if not has_casa_permission("manage_tasklists"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    task_id = payload.get("task_id")
    name = (payload.get("name") or "").strip()
    if not list_id or not task_id or not name:
        return jsonify({"ok": False, "message": "Subtaak gegevens ontbreken."}), 400

    data = get_kitchen_data()
    for item in data.get("lists", []):
        if item.get("id") == list_id:
            for task in item.get("tasks", []):
                if task.get("id") == task_id:
                    existing = {sub.get("id") for sub in task.get("subtasks", [])}
                    new_id = slugify(name)
                    base = new_id
                    count = 2
                    while new_id in existing:
                        new_id = f"{base}_{count}"
                        count += 1
                    task.setdefault("subtasks", []).append({
                        "id": new_id,
                        "name": name,
                        "checked": False,
                        "last_checked": "",
                        "last_checked_by": "",
                        "last_checked_at": ""
                    })
                    save_kitchen_data(data)
                    return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Taak niet gevonden."}), 404

@casa_cara.route("/api/kitchen/subtask-delete", methods=["POST"])
def kitchen_subtask_delete():
    if not has_casa_permission("manage_tasklists"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    task_id = payload.get("task_id")
    subtask_id = payload.get("subtask_id")
    data = get_kitchen_data()
    for item in data.get("lists", []):
        if item.get("id") == list_id:
            for task in item.get("tasks", []):
                if task.get("id") == task_id:
                    before = len(task.get("subtasks", []))
                    task["subtasks"] = [sub for sub in task.get("subtasks", []) if sub.get("id") != subtask_id]
                    if len(task["subtasks"]) == before:
                        return jsonify({"ok": False, "message": "Subtaak niet gevonden."}), 404
                    sync_task_with_subtasks(task, date.today().isoformat())
                    save_kitchen_data(data)
                    return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Taak niet gevonden."}), 404

@casa_cara.route("/api/kitchen/subtask-toggle", methods=["POST"])
def kitchen_subtask_toggle():
    if not has_casa_permission("use_tasklists"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    task_id = payload.get("task_id")
    subtask_id = payload.get("subtask_id")
    today = date.today().isoformat()
    checked_by = (get_current_casa_user() or {}).get("name", "Onbekend")
    checked_at = datetime.now().isoformat(timespec="minutes")
    data = get_kitchen_data()
    for item in data.get("lists", []):
        if item.get("id") == list_id:
            for task in item.get("tasks", []):
                if task.get("id") == task_id:
                    for sub in task.get("subtasks", []):
                        if sub.get("id") == subtask_id:
                            is_checked = bool(sub.get("checked")) and sub.get("last_checked") == today
                            sub["checked"] = not is_checked
                            sub["last_checked"] = today if not is_checked else ""
                            sub["last_checked_by"] = checked_by if not is_checked else ""
                            sub["last_checked_at"] = checked_at if not is_checked else ""
                            sync_task_with_subtasks(task, today, checked_by if not is_checked else "", checked_at if not is_checked else "")
                            save_kitchen_data(data)
                            return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Subtaak niet gevonden."}), 404



@casa_cara.route("/api/bar-tasks")
def api_bar_tasks():
    data = get_bar_tasks_data()
    today = date.today().isoformat()
    changed = False
    for item in data.get("lists", []):
        for task in item.get("tasks", []):
            if task.get("last_checked") != today and task.get("checked"):
                task["checked"] = False
                task["last_checked"] = ""
                changed = True
            for sub in task.get("subtasks", []):
                if sub.get("last_checked") != today and sub.get("checked"):
                    sub["checked"] = False
                    sub["last_checked"] = ""
                    changed = True
            before = (task.get("checked"), task.get("last_checked"), task.get("last_checked_by"), task.get("last_checked_at"))
            sync_task_with_subtasks(task, today, task.get("last_checked_by", ""), task.get("last_checked_at", ""))
            after = (task.get("checked"), task.get("last_checked"), task.get("last_checked_by"), task.get("last_checked_at"))
            if before != after:
                changed = True
    if changed:
        save_bar_tasks_data(data)
    return jsonify(data)

@casa_cara.route("/api/bar-tasks/list-save", methods=["POST"])
def bar_list_save():
    if not has_casa_permission("manage_tasklists"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "message": "Vul een naam in voor de takenlijst."}), 400
    data = get_bar_tasks_data()
    existing = {item.get("id") for item in data.get("lists", [])}
    new_id = slugify(name)
    base = new_id
    count = 2
    while new_id in existing:
        new_id = f"{base}_{count}"
        count += 1
    data["lists"].append({"id": new_id, "name": name, "tasks": []})
    save_bar_tasks_data(data)
    return jsonify({"ok": True})

@casa_cara.route("/api/bar-tasks/list-delete", methods=["POST"])
def bar_list_delete():
    if not has_casa_permission("manage_tasklists"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    data = get_bar_tasks_data()
    before = len(data.get("lists", []))
    data["lists"] = [item for item in data.get("lists", []) if item.get("id") != list_id]
    if len(data["lists"]) == before:
        return jsonify({"ok": False, "message": "Takenlijst niet gevonden."}), 404
    save_bar_tasks_data(data)
    return jsonify({"ok": True})

@casa_cara.route("/api/bar-tasks/task-save", methods=["POST"])
def bar_task_save():
    if not has_casa_permission("manage_tasklists"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    name = (payload.get("name") or "").strip()
    if not list_id or not name:
        return jsonify({"ok": False, "message": "Lijst of taak ontbreekt."}), 400
    data = get_bar_tasks_data()
    for item in data.get("lists", []):
        if item.get("id") == list_id:
            existing = {task.get("id") for task in item.get("tasks", [])}
            new_id = slugify(name)
            base = new_id
            count = 2
            while new_id in existing:
                new_id = f"{base}_{count}"
                count += 1
            item.setdefault("tasks", []).append({
                "id": new_id,
                "name": name,
                "checked": False,
                "last_checked": "",
                "last_checked_by": "",
                "last_checked_at": "",
                "subtasks": []
            })
            save_bar_tasks_data(data)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Takenlijst niet gevonden."}), 404

@casa_cara.route("/api/bar-tasks/task-delete", methods=["POST"])
def bar_task_delete():
    if not has_casa_permission("manage_tasklists"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    task_id = payload.get("task_id")
    data = get_bar_tasks_data()
    for item in data.get("lists", []):
        if item.get("id") == list_id:
            before = len(item.get("tasks", []))
            item["tasks"] = [task for task in item.get("tasks", []) if task.get("id") != task_id]
            if len(item["tasks"]) == before:
                return jsonify({"ok": False, "message": "Taak niet gevonden."}), 404
            save_bar_tasks_data(data)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Takenlijst niet gevonden."}), 404

@casa_cara.route("/api/bar-tasks/task-toggle", methods=["POST"])
def bar_task_toggle():
    if not has_casa_permission("use_tasklists"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    task_id = payload.get("task_id")
    today = date.today().isoformat()
    checked_by = (get_current_casa_user() or {}).get("name", "Onbekend")
    checked_at = datetime.now().isoformat(timespec="minutes")
    data = get_bar_tasks_data()
    for item in data.get("lists", []):
        if item.get("id") == list_id:
            for task in item.get("tasks", []):
                if task.get("id") == task_id:
                    is_checked = bool(task.get("checked")) and task.get("last_checked") == today
                    task["checked"] = not is_checked
                    task["last_checked"] = today if not is_checked else ""
                    task["last_checked_by"] = checked_by if not is_checked else ""
                    task["last_checked_at"] = checked_at if not is_checked else ""
                    for sub in task.get("subtasks", []):
                        sub["checked"] = not is_checked
                        sub["last_checked"] = today if not is_checked else ""
                        sub["last_checked_by"] = checked_by if not is_checked else ""
                        sub["last_checked_at"] = checked_at if not is_checked else ""
                    save_bar_tasks_data(data)
                    return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Taak niet gevonden."}), 404

@casa_cara.route("/api/bar-tasks/subtask-save", methods=["POST"])
def bar_subtask_save():
    if not has_casa_permission("manage_tasklists"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    task_id = payload.get("task_id")
    name = (payload.get("name") or "").strip()
    if not list_id or not task_id or not name:
        return jsonify({"ok": False, "message": "Subtaak gegevens ontbreken."}), 400
    data = get_bar_tasks_data()
    for item in data.get("lists", []):
        if item.get("id") == list_id:
            for task in item.get("tasks", []):
                if task.get("id") == task_id:
                    existing = {sub.get("id") for sub in task.get("subtasks", [])}
                    new_id = slugify(name)
                    base = new_id
                    count = 2
                    while new_id in existing:
                        new_id = f"{base}_{count}"
                        count += 1
                    task.setdefault("subtasks", []).append({
                        "id": new_id,
                        "name": name,
                        "checked": False,
                        "last_checked": "",
                        "last_checked_by": "",
                        "last_checked_at": ""
                    })
                    save_bar_tasks_data(data)
                    return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Taak niet gevonden."}), 404

@casa_cara.route("/api/bar-tasks/subtask-delete", methods=["POST"])
def bar_subtask_delete():
    if not has_casa_permission("manage_tasklists"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    task_id = payload.get("task_id")
    subtask_id = payload.get("subtask_id")
    data = get_bar_tasks_data()
    for item in data.get("lists", []):
        if item.get("id") == list_id:
            for task in item.get("tasks", []):
                if task.get("id") == task_id:
                    before = len(task.get("subtasks", []))
                    task["subtasks"] = [sub for sub in task.get("subtasks", []) if sub.get("id") != subtask_id]
                    if len(task["subtasks"]) == before:
                        return jsonify({"ok": False, "message": "Subtaak niet gevonden."}), 404
                    sync_task_with_subtasks(task, date.today().isoformat())
                    save_bar_tasks_data(data)
                    return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Taak niet gevonden."}), 404

@casa_cara.route("/api/bar-tasks/subtask-toggle", methods=["POST"])
def bar_subtask_toggle():
    if not has_casa_permission("use_tasklists"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    task_id = payload.get("task_id")
    subtask_id = payload.get("subtask_id")
    today = date.today().isoformat()
    checked_by = (get_current_casa_user() or {}).get("name", "Onbekend")
    checked_at = datetime.now().isoformat(timespec="minutes")
    data = get_bar_tasks_data()
    for item in data.get("lists", []):
        if item.get("id") == list_id:
            for task in item.get("tasks", []):
                if task.get("id") == task_id:
                    for sub in task.get("subtasks", []):
                        if sub.get("id") == subtask_id:
                            is_checked = bool(sub.get("checked")) and sub.get("last_checked") == today
                            sub["checked"] = not is_checked
                            sub["last_checked"] = today if not is_checked else ""
                            sub["last_checked_by"] = checked_by if not is_checked else ""
                            sub["last_checked_at"] = checked_at if not is_checked else ""
                            sync_task_with_subtasks(task, today, checked_by if not is_checked else "", checked_at if not is_checked else "")
                            save_bar_tasks_data(data)
                            return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Subtaak niet gevonden."}), 404


@casa_cara.route("/api/manage/user-save", methods=["POST"])
def manage_user_save():
    if not has_casa_permission("manage_users"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    pin = "".join(ch for ch in str(payload.get("pin") or "") if ch.isdigit())
    role = "admin" if (payload.get("role") or "").strip().lower() == "admin" else "medewerker"
    permissions = normalize_permissions(role, payload.get("permissions"))

    if not name:
        return jsonify({"ok": False, "message": "Vul een naam in."}), 400
    if len(pin) != 4:
        return jsonify({"ok": False, "message": "Code moet uit 4 cijfers bestaan."}), 400

    data = load_casa_auth_data()
    users = data.get("users", [])

    try:
        raw_index = payload.get("index", None)
        index = None if raw_index in (None, "", "null") else int(raw_index)
    except Exception:
        return jsonify({"ok": False, "message": "Ongeldige gebruiker."}), 400

    for i, user in enumerate(users):
        if i == index:
            continue
        if (user.get("pin") or "") == pin and user.get("active", True):
            return jsonify({"ok": False, "message": "Deze code is al in gebruik."}), 400

    user_record = {
        "name": name,
        "pin": pin,
        "role": role,
        "active": True,
        "permissions": permissions,
    }

    if index is None:
        users.append(user_record)
    else:
        if index < 0 or index >= len(users):
            return jsonify({"ok": False, "message": "Gebruiker niet gevonden."}), 404
        current = users[index]
        user_record["active"] = bool(current.get("active", True))
        users[index] = user_record

    save_casa_auth_data({"users": users})

    current_user = get_current_casa_user()
    if current_user and current_user.get("pin") == pin:
        session["casa_user_name"] = name
        session["casa_user_role"] = role

    return jsonify({"ok": True})


@casa_cara.route("/api/manage/user-delete", methods=["POST"])
def manage_user_delete():
    if not has_casa_permission("manage_users"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}

    try:
        index = int(payload.get("index"))
    except Exception:
        return jsonify({"ok": False, "message": "Gebruiker niet gevonden."}), 400

    data = load_casa_auth_data()
    users = data.get("users", [])

    if index < 0 or index >= len(users):
        return jsonify({"ok": False, "message": "Gebruiker niet gevonden."}), 404

    target = users[index]
    active_users = [u for u in users if u.get("active", True)]
    active_admins = [u for u in active_users if (u.get("role") or "").strip().lower() == "admin"]

    if len(active_users) <= 1:
        return jsonify({"ok": False, "message": "Je kunt niet de laatste gebruiker verwijderen."}), 400

    if (target.get("role") or "").strip().lower() == "admin" and len(active_admins) <= 1:
        return jsonify({"ok": False, "message": "Je kunt niet de laatste admin verwijderen."}), 400

    current_pin = session.get("casa_user_pin")
    if current_pin and (target.get("pin") or "") == current_pin:
        return jsonify({"ok": False, "message": "Je kunt je eigen account niet verwijderen terwijl je bent ingelogd."}), 400

    users.pop(index)
    save_casa_auth_data({"users": users})
    return jsonify({"ok": True})


@casa_cara.route("/api/recipes/save", methods=["POST"])
def recipe_save():
    if not has_casa_permission("manage_recipes"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "message": "Vul een receptnaam in."}), 400

    ingredients = payload.get("ingredients") or []
    steps = (payload.get("steps") or "").strip()

    data = get_recipes_data()
    items = data.get("items", [])
    index = payload.get("index", None)
    recipe = {
        "name": name,
        "ingredients": ingredients,
        "steps": steps
    }
    if index is None:
        items.append(recipe)
    else:
        try:
            idx = int(index)
            items[idx] = recipe
        except Exception:
            return jsonify({"ok": False, "message": "Recept niet gevonden."}), 404
    data["items"] = items
    save_recipes_data(data)
    return jsonify({"ok": True})

@casa_cara.route("/api/recipes/delete", methods=["POST"])
def recipe_delete():
    if not has_casa_permission("manage_recipes"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    data = get_recipes_data()
    items = data.get("items", [])
    try:
        idx = int(payload.get("index"))
    except Exception:
        return jsonify({"ok": False, "message": "Recept niet gevonden."}), 404
    if idx < 0 or idx >= len(items):
        return jsonify({"ok": False, "message": "Recept niet gevonden."}), 404
    items.pop(idx)
    data["items"] = items
    save_recipes_data(data)
    return jsonify({"ok": True})
