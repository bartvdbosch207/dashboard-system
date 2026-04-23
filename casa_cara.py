
from flask import Blueprint, render_template_string, jsonify, request, session, redirect, Response, Response
import json
import secrets
import base64
import calendar
from io import BytesIO
from datetime import datetime, date
from zoneinfo import ZoneInfo
from pathlib import Path
from PIL import Image

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
BAR_LAYOUTS_FILE = DATA_DIR / "bar_indelingen.json"
RECIPES_FILE = DATA_DIR / "recipes.json"
CASA_AUTH_FILE = DATA_DIR / "casa_auth.json"
CASA_AUTH_CANDIDATES = []
for _candidate in [
    CASA_AUTH_FILE,
    Path(__file__).resolve().parent / "data" / "casa_cara" / "casa_auth.json",
    Path(__file__).resolve().parent / "Data" / "Casa Cara" / "casa_auth.json",
]:
    if _candidate not in CASA_AUTH_CANDIDATES:
        CASA_AUTH_CANDIDATES.append(_candidate)

def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

AMSTERDAM_TZ = ZoneInfo("Europe/Amsterdam")
TASKLIST_DAYS = ["altijd", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]

def get_local_now():
    return datetime.now(AMSTERDAM_TZ)

def get_today_iso():
    return get_local_now().date().isoformat()

def get_now_iso_minutes():
    return get_local_now().replace(second=0, microsecond=0).isoformat(timespec="minutes")

def get_current_task_day_label():
    weekday = get_local_now().weekday()
    mapping = {2: "woensdag", 3: "donderdag", 4: "vrijdag", 5: "zaterdag", 6: "zondag"}
    return mapping.get(weekday, "altijd")

def normalize_task_day(value):
    value = (value or "").strip().lower()
    return value if value in TASKLIST_DAYS else "altijd"

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
    "use_kitchen_tasklists": True,
    "use_bar_tasklists": True,
    "manage_dienst_types": False,
    "manage_users": False,
    "manage_products": False,
    "manage_types": False,
    "manage_locations": False,
    "manage_recipes": False,
    "manage_tasklists": False,
    "manage_kitchen_tasklists": False,
    "manage_bar_tasklists": False,
    "manage_coolers": False,
    "manage_bar_layouts": False}


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

        legacy_use = permissions.get("use_tasklists") if "use_tasklists" in permissions else None
        legacy_manage = permissions.get("manage_tasklists") if "manage_tasklists" in permissions else None

        if "use_kitchen_tasklists" in permissions:
            base["use_kitchen_tasklists"] = bool(permissions.get("use_kitchen_tasklists"))
        elif legacy_use is not None:
            base["use_kitchen_tasklists"] = bool(legacy_use)

        if "use_bar_tasklists" in permissions:
            base["use_bar_tasklists"] = bool(permissions.get("use_bar_tasklists"))
        elif legacy_use is not None:
            base["use_bar_tasklists"] = bool(legacy_use)

        if "manage_kitchen_tasklists" in permissions:
            base["manage_kitchen_tasklists"] = bool(permissions.get("manage_kitchen_tasklists"))
        elif legacy_manage is not None:
            base["manage_kitchen_tasklists"] = bool(legacy_manage)

        if "manage_bar_tasklists" in permissions:
            base["manage_bar_tasklists"] = bool(permissions.get("manage_bar_tasklists"))
        elif legacy_manage is not None:
            base["manage_bar_tasklists"] = bool(legacy_manage)

        base["use_tasklists"] = bool(base.get("use_kitchen_tasklists") or base.get("use_bar_tasklists") or base.get("use_tasklists"))
        base["manage_tasklists"] = bool(base.get("manage_kitchen_tasklists") or base.get("manage_bar_tasklists") or base.get("manage_tasklists"))
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
        "use_kitchen_tasklists": "Keuken takenlijsten openen",
        "use_bar_tasklists": "Bar takenlijsten openen",
        "manage_dienst_types": "Dienstsoorten beheren",
        "manage_users": "Medewerkers beheren",
        "manage_products": "Producten toevoegen en bewerken",
        "manage_types": "Productsoorten beheren",
        "manage_locations": "Locaties beheren",
        "manage_recipes": "Recepten beheren",
        "manage_tasklists": "Takenlijsten beheren",
        "manage_kitchen_tasklists": "Keuken takenlijsten beheren",
        "manage_bar_tasklists": "Bar takenlijsten beheren",
        "manage_coolers": "Koelingen beheren",
        "manage_bar_layouts": "Bar indelingen beheren"}


def load_casa_auth_data():
    merged_users = []
    seen_pins = set()
    for auth_path in CASA_AUTH_CANDIDATES:
        data = load_json(auth_path, {"users": []})
        if not isinstance(data, dict):
            continue
        for item in data.get("users", []):
            if not isinstance(item, dict):
                continue
            pin = str(item.get("pin") or item.get("code") or "").strip()
            pin = "".join(ch for ch in pin if ch.isdigit())
            if len(pin) != 4 or pin in seen_pins:
                continue
            role = "admin" if (item.get("role") or "").strip().lower() == "admin" else "medewerker"
            merged_users.append({
                "name": (item.get("name") or item.get("username") or "Gebruiker").strip() or "Gebruiker",
                "username": (item.get("username") or item.get("name") or "Gebruiker").strip() or "Gebruiker",
                "pin": pin,
                "code": pin,
                "role": role,
                "active": bool(item.get("active", True)),
                "calendar_token": str(item.get("calendar_token") or item.get("agenda_token") or "").strip(),
                "permissions": normalize_permissions(role, item.get("permissions"))})
            seen_pins.add(pin)
    return {"users": merged_users}


def save_casa_auth_data(data):
    users = []
    for item in data.get("users", []):
        if not isinstance(item, dict):
            continue
        pin = str(item.get("pin") or item.get("code") or "").strip()
        role = "admin" if (item.get("role") or "").strip().lower() == "admin" else "medewerker"
        clean_pin = "".join(ch for ch in pin if ch.isdigit())
        if len(clean_pin) != 4:
            continue
        clean_name = (item.get("name") or item.get("username") or "Gebruiker").strip() or "Gebruiker"
        users.append({
            "name": clean_name,
            "username": clean_name,
            "pin": clean_pin,
            "code": clean_pin,
            "role": role,
            "active": bool(item.get("active", True)),
            "calendar_token": str(item.get("calendar_token") or "").strip(),
            "permissions": normalize_permissions(role, item.get("permissions"))})
    payload = {"users": users}
    for auth_path in CASA_AUTH_CANDIDATES:
        try:
            save_json(auth_path, payload)
        except Exception:
            pass


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



def ensure_calendar_token_for_current_user():
    user = get_current_casa_user()
    if not user:
        return ""
    pin = str(user.get("pin") or session.get("casa_user_pin") or "").strip()
    data = load_casa_auth_data()
    changed = False
    token = ""
    for item in data.get("users", []):
        if str(item.get("pin") or "") == pin:
            token = str(item.get("calendar_token") or "").strip()
            if not token:
                token = secrets.token_urlsafe(24)
                item["calendar_token"] = token
                changed = True
            break
    if changed:
        save_casa_auth_data(data)
    return token


def get_casa_user_by_calendar_token(token: str):
    token = str(token or "").strip()
    if not token:
        return None
    for user in load_casa_auth_data().get("users", []):
        if user.get("active", True) and str(user.get("calendar_token") or "").strip() == token:
            return user
    return None


def calendar_feed_url_for_current_user():
    token = ensure_calendar_token_for_current_user()
    if not token:
        return ""
    base = request.host_url.rstrip("/")
    return f"{base}/casa-cara-calendar/{token}.ics"


def current_permissions():
    user = get_current_casa_user() or {}
    role = user.get("role", "medewerker")
    return normalize_permissions(role, user.get("permissions"))


def has_casa_permission(key: str):
    if is_casa_admin():
        return True
    return bool(current_permissions().get(key))


def has_tasklist_access(section: str, manage: bool = False):
    if is_casa_admin():
        return True
    section = (section or "").strip().lower()
    permissions = current_permissions()
    if section == "bar":
        return bool(permissions.get("manage_bar_tasklists" if manage else "use_bar_tasklists"))
    if section == "kitchen":
        return bool(permissions.get("manage_kitchen_tasklists" if manage else "use_kitchen_tasklists"))
    return bool(permissions.get("manage_tasklists" if manage else "use_tasklists"))


def has_layout_manage_permission():
    return has_casa_permission("manage_bar_layouts")


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
            "is_personal": True}
    amount = float(data.get("fooienpot", 0) or 0)
    return {
        "amount": round(amount, 2),
        "label": "Algemene fooienpot",
        "is_personal": False}

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
    data["diensten"] = normalize_diensten(data.get("diensten", []))
    return data

def save_general_data(data):
    save_json(GENERAL_FILE, data)


def normalize_dienst_status(value):
    value = (value or "").strip().lower()
    allowed = {"ingepland", "bevestigd", "gewijzigd", "vervallen"}
    return value if value in allowed else "ingepland"


def normalize_dienst_time_value(value):
    value = (value or "").strip()
    if not value:
        return ""
    parts = value.split(":")
    if len(parts) != 2:
        return ""
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except Exception:
        return ""
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return ""
    return f"{hour:02d}:{minute:02d}"


def build_dienst_time_label(start: str = "", einde: str = "") -> str:
    start = normalize_dienst_time_value(start)
    einde = normalize_dienst_time_value(einde)
    if start and einde:
        return f"{start} - {einde}"
    if start:
        return f"{start}"
    if einde:
        return f"tot {einde}"
    return ""


def extract_dienst_times(start: str = "", einde: str = "", tijd: str = ""):
    start = normalize_dienst_time_value(start)
    einde = normalize_dienst_time_value(einde)
    tijd = (tijd or "").strip().replace("–", "-").replace("—", "-")
    if not (start or einde) and tijd:
        import re
        matches = re.findall(r"(\d{1,2}:\d{2})", tijd)
        if matches:
            start = normalize_dienst_time_value(matches[0])
            if len(matches) > 1:
                einde = normalize_dienst_time_value(matches[1])
    return start, einde, build_dienst_time_label(start, einde)


def month_grid_for_import(year: int, month: int):
    cal = calendar.Calendar(firstweekday=0)
    return cal.monthdayscalendar(year, month)


def decode_image_from_data_url(data_url: str):
    data_url = (data_url or "").strip()
    if not data_url:
        raise ValueError("Geen afbeelding ontvangen.")
    encoded = data_url.split(",", 1)[1] if "," in data_url else data_url
    raw = base64.b64decode(encoded)
    return Image.open(BytesIO(raw)).convert("RGB")


def _find_calendar_panel_bounds(image: Image.Image):
    width, height = image.size
    pixels = image.load()

    def is_light(x, y):
        r, g, b = pixels[x, y]
        return r > 228 and g > 228 and b > 228

    crop_x1 = int(width * 0.04)
    crop_x2 = int(width * 0.96)
    crop_y1 = int(height * 0.18)
    crop_y2 = int(height * 0.58)
    scan_step_y = max(2, int(height / 260))
    rows = []
    for y in range(crop_y1, crop_y2, scan_step_y):
        total = 0
        light_count = 0
        for x in range(crop_x1, crop_x2, 4):
            total += 1
            if is_light(x, y):
                light_count += 1
        rows.append((y, light_count / max(total, 1)))

    segments = []
    start = None
    values = []
    for y, ratio in rows:
        if ratio > 0.72:
            if start is None:
                start = y
                values = [ratio]
            else:
                values.append(ratio)
        elif start is not None:
            segments.append((start, y, sum(values) / len(values)))
            start = None
            values = []
    if start is not None:
        segments.append((start, rows[-1][0], sum(values) / len(values)))

    best = None
    best_score = 0
    for top, bottom, avg in segments:
        h = bottom - top
        if h < height * 0.09:
            continue
        mid_y = int((top + bottom) / 2)
        cols = []
        for x in range(crop_x1, crop_x2, 4):
            total = 0
            light_count = 0
            for yy in range(max(top, mid_y - 8), min(bottom, mid_y + 8), 2):
                total += 1
                if is_light(x, yy):
                    light_count += 1
            cols.append((x, light_count / max(total, 1)))

        cx1 = None
        cx2 = None
        run = None
        for x, ratio in cols:
            if ratio > 0.72 and run is None:
                run = x
            elif ratio <= 0.72 and run is not None:
                if x - run > width * 0.45:
                    cx1, cx2 = run, x
                    break
                run = None
        if cx1 is None and run is not None:
            cx1, cx2 = run, cols[-1][0]

        if cx1 is None or cx2 is None:
            continue

        area = max(0, (cx2 - cx1) * h)
        score = area * avg
        if score > best_score:
            best_score = score
            best = (cx1, top, cx2, bottom)

    if best:
        return best

    return (
        int(width * 0.05),
        int(height * 0.26),
        int(width * 0.95),
        int(height * 0.48),
    )



def _fixed_dish_calendar_panel_bounds(image: Image.Image):
    width, height = image.size
    return (
        int(width * 0.04),
        int(height * 0.24),
        int(width * 0.95),
        int(height * 0.615),
    )


def detect_dish_calendar_days(image: Image.Image, year: int, month: int, include_colors=None):
    # v5: alleen volledig blauwe DISH-dagen herkennen.
    # Groen wordt genegeerd en omcirkelde blauwe dagen vallen buiten de detectie.
    width, height = image.size
    pixels = image.load()

    x1, y1, x2, y2 = _fixed_dish_calendar_panel_bounds(image)
    x1 = max(0, min(width - 1, x1))
    x2 = max(x1 + 1, min(width, x2))
    y1 = max(0, min(height - 1, y1))
    y2 = max(y1 + 1, min(height, y2))

    panel_w = max(1, x2 - x1)
    panel_h = max(1, y2 - y1)

    weeks = month_grid_for_import(year, month)
    rows = max(1, len(weeks))
    cols = 7

    # Deze verhoudingen zijn afgestemd op het DISH maandrooster uit de app:
    # alleen het raster met dagen wordt geanalyseerd.
    grid_x1 = int(x1 + panel_w * 0.158)
    grid_x2 = int(x1 + panel_w * 0.952)
    grid_y1 = int(y1 + panel_h * 0.336)
    grid_y2 = int(y1 + panel_h * 0.975)

    grid_x1 = max(0, min(width - 1, grid_x1))
    grid_x2 = max(grid_x1 + 1, min(width, grid_x2))
    grid_y1 = max(0, min(height - 1, grid_y1))
    grid_y2 = max(grid_y1 + 1, min(height, grid_y2))

    cell_w = (grid_x2 - grid_x1) / cols
    cell_h = (grid_y2 - grid_y1) / rows

    def is_full_blue(r, g, b):
        # Relaxte blauwe detectie voor DISH, maar wel duidelijk gevuld blauw.
        return (
            b >= 145
            and g >= 120
            and r <= 165
            and (b - r) >= 18
            and (g - r) >= 6
        )

    # Bouw masker alleen binnen het kalendergrid.
    mask_w = max(1, grid_x2 - grid_x1)
    mask_h = max(1, grid_y2 - grid_y1)
    mask = [[False] * mask_w for _ in range(mask_h)]
    for yy in range(mask_h):
        py = grid_y1 + yy
        for xx in range(mask_w):
            px = grid_x1 + xx
            r, g, b = pixels[px, py]
            if is_full_blue(r, g, b):
                mask[yy][xx] = True

    # Vind blauwe componenten.
    components = []
    visited = [[False] * mask_w for _ in range(mask_h)]
    for sy in range(mask_h):
        for sx in range(mask_w):
            if not mask[sy][sx] or visited[sy][sx]:
                continue
            stack = [(sx, sy)]
            visited[sy][sx] = True
            area = 0
            min_x = max_x = sx
            min_y = max_y = sy
            while stack:
                cx, cy = stack.pop()
                area += 1
                if cx < min_x:
                    min_x = cx
                if cx > max_x:
                    max_x = cx
                if cy < min_y:
                    min_y = cy
                if cy > max_y:
                    max_y = cy
                if cx > 0 and mask[cy][cx - 1] and not visited[cy][cx - 1]:
                    visited[cy][cx - 1] = True
                    stack.append((cx - 1, cy))
                if cx + 1 < mask_w and mask[cy][cx + 1] and not visited[cy][cx + 1]:
                    visited[cy][cx + 1] = True
                    stack.append((cx + 1, cy))
                if cy > 0 and mask[cy - 1][cx] and not visited[cy - 1][cx]:
                    visited[cy - 1][cx] = True
                    stack.append((cx, cy - 1))
                if cy + 1 < mask_h and mask[cy + 1][cx] and not visited[cy + 1][cx]:
                    visited[cy + 1][cx] = True
                    stack.append((cx, cy + 1))

            bbox_w = max_x - min_x + 1
            bbox_h = max_y - min_y + 1
            fill_ratio = area / max(1, bbox_w * bbox_h)

            # Alleen echt gevulde blauwe vormen:
            # - kleine dunne ringen (zoals omcirkeld blauw) vallen hier af
            # - grote blauwe balken en gevulde bollen blijven over
            if area < 900:
                continue
            if fill_ratio < 0.18:
                continue

            components.append({
                "x1": grid_x1 + min_x,
                "y1": grid_y1 + min_y,
                "x2": grid_x1 + max_x + 1,
                "y2": grid_y1 + max_y + 1,
                "area": area,
                "fill_ratio": fill_ratio})

    results = []
    for row in range(rows):
        for col in range(cols):
            day = weeks[row][col]
            if not day:
                continue

            cell_x1 = int(grid_x1 + col * cell_w)
            cell_x2 = int(grid_x1 + (col + 1) * cell_w)
            cell_y1 = int(grid_y1 + row * cell_h)
            cell_y2 = int(grid_y1 + (row + 1) * cell_h)

            # Gebruik een kernvlak per dagcel; daardoor is de match stabieler.
            core_x1 = int(cell_x1 + cell_w * 0.12)
            core_x2 = int(cell_x2 - cell_w * 0.12)
            core_y1 = int(cell_y1 + cell_h * 0.08)
            core_y2 = int(cell_y2 - cell_h * 0.10)
            core_area = max(1, (core_x2 - core_x1) * (core_y2 - core_y1))

            matched = False
            for comp in components:
                ix1 = max(core_x1, comp["x1"])
                iy1 = max(core_y1, comp["y1"])
                ix2 = min(core_x2, comp["x2"])
                iy2 = min(core_y2, comp["y2"])
                inter_area = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                if inter_area >= min(700, int(core_area * 0.09)):
                    matched = True
                    break

            if matched:
                results.append({
                    "color": "blue",
                    "date": f"{year:04d}-{month:02d}-{day:02d}",
                    "day": day})

    deduped = []
    seen = set()
    for item in sorted(results, key=lambda x: x["date"]):
        key = item["date"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def build_dish_import_preview(image_data: str, year: int, month: int, color_map=None, include_colors=None):
    color_map = color_map or {}
    image = decode_image_from_data_url(image_data)
    detected = detect_dish_calendar_days(image, year, month, include_colors=include_colors)
    dienst_types = {item.get("naam"): item for item in get_dienst_types()}
    preview = []
    for item in detected:
        mapped_name = (color_map.get(item["color"]) or "").strip()
        dienst_type = dienst_types.get(mapped_name, {}) if mapped_name else {}
        start = normalize_dienst_time_value(dienst_type.get("start") or "")
        einde = normalize_dienst_time_value(dienst_type.get("einde") or "")
        preview.append({
            "naam": mapped_name,
            "suggested_name": mapped_name,
            "datum": item["date"],
            "color": item["color"],
            "start": start,
            "einde": einde,
            "tijd": build_dienst_time_label(start, einde),
            "status": "ingepland",
            "source": "dish_screenshot"})
    return preview



def normalize_dienst_item(item):
    item = item if isinstance(item, dict) else {}
    naam = (item.get("naam") or item.get("medewerker") or item.get("persoon") or "").strip()
    datum = (item.get("datum") or item.get("date") or "").strip()
    start, einde, tijd = extract_dienst_times(
        item.get("start") or item.get("starttijd") or "",
        item.get("einde") or item.get("eindtijd") or "",
        item.get("tijd") or "",
    )
    rol = str(item.get("rol") or "").strip()
    notitie = str(item.get("notitie") or "").strip()
    locatie = (item.get("locatie") or item.get("afdeling") or "").strip()
    source = (item.get("source") or "manual").strip() or "manual"
    return {
        **item,
        "naam": naam,
        "datum": datum,
        "start": start,
        "einde": einde,
        "tijd": tijd,
        "rol": rol,
        "notitie": notitie,
        "locatie": locatie,
        "status": normalize_dienst_status(item.get("status")),
        "source": source,
        "owner_name": str(item.get("owner_name") or item.get("eigenaar") or item.get("user_name") or "").strip(),
        "external_id": str(item.get("external_id") or "").strip(),
        "calendar_event_id": str(item.get("calendar_event_id") or "").strip(),
        "last_synced_at": str(item.get("last_synced_at") or "").strip(),
        "created_at": str(item.get("created_at") or "").strip(),
        "updated_at": str(item.get("updated_at") or "").strip()}


def normalize_diensten(items):
    cleaned = []
    for item in items if isinstance(items, list) else []:
        normalized = normalize_dienst_item(item)
        if normalized.get("naam") or normalized.get("datum") or normalized.get("tijd"):
            cleaned.append(normalized)
    return cleaned


def current_casa_owner_name():
    user = get_current_casa_user() or {}
    return str(user.get("name") or "").strip()


def dienst_is_visible_for_current_user(item):
    if is_casa_admin():
        return True
    owner = str((item or {}).get("owner_name") or "").strip().lower()
    current = current_casa_owner_name().lower()
    return bool(owner and current and owner == current)


def dienst_can_current_user_modify(item):
    if is_casa_admin():
        return True
    return dienst_is_visible_for_current_user(item)


def diensten_for_current_user_with_indices(diensten):
    result = []
    current = current_casa_owner_name().lower()
    for index, item in enumerate(diensten or []):
        normalized = normalize_dienst_item(item)
        if is_casa_admin() or (str(normalized.get("owner_name") or "").strip().lower() == current):
            visible_item = dict(normalized)
            visible_item["_global_index"] = index
            result.append(visible_item)
    return result


def get_types():
    raw = load_json(PRODUCT_TYPES_FILE, [])
    result = []
    for item in raw:
        if isinstance(item, str):
            result.append({"naam": item, "locatie": "-"})
        elif isinstance(item, dict):
            result.append({
                "naam": item.get("naam", "Overig"),
                "locatie": item.get("locatie", "-")})
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
                    "einde": (item.get("einde") or "").strip()})
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
        raw_days = item.get("days")
        if isinstance(raw_days, list):
            days = []
            for day_value in raw_days:
                normalized = normalize_task_day(day_value)
                if normalized not in days:
                    days.append(normalized)
            if not days:
                days = [normalize_task_day(item.get("day"))]
        else:
            days = [normalize_task_day(item.get("day"))]
        item["days"] = days
        item["day"] = days[0] if days else "altijd"
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

def default_layout_slot(index: int):
    return {
        "id": f"slot_{index}",
        "label": f"Vak {index}",
        "product_id": "",
        "product_name": "",
        "image_url": "",
        "note": ""}


def default_layout_shelf(index: int, slots_per_shelf: int = 9, *, name: str = "", height: str = "medium", is_floor: bool = False):
    slots_per_shelf = max(1, min(int(slots_per_shelf or 9), 9))
    height = (height or "medium").strip().lower()
    if height not in {"low", "medium", "high", "wine"}:
        height = "medium"
    return {
        "id": f"shelf_{index}",
        "name": (name or ("Bodem" if is_floor else f"Plank {index}")).strip() or ("Bodem" if is_floor else f"Plank {index}"),
        "facings": slots_per_shelf,
        "height": height,
        "is_floor": bool(is_floor),
        "slots": [default_layout_slot(i + 1) for i in range(slots_per_shelf)]}


def default_layout_cooler(index: int, cooler_name: str = ""):
    return {
        "id": f"cooler_{index}",
        "name": cooler_name or f"Koelkast {index}",
        "shelves": [
            default_layout_shelf(1, name="Plank 1"),
            default_layout_shelf(2, name="Plank 2"),
            default_layout_shelf(3, name="Plank 3"),
            default_layout_shelf(4, slots_per_shelf=9, name="Bodem", height="low", is_floor=True),
        ]}


def default_layout_unit(index: int):
    return {
        "id": f"unit_{index}",
        "name": f"GB{index}",
        "coolers": [default_layout_cooler(i + 1) for i in range(3)]}


def default_bar_layout_structure():
    return [default_layout_unit(i + 1) for i in range(4)]


def normalize_layout_slot(item, index: int):
    item = item if isinstance(item, dict) else {}
    product_name = (item.get("product_name") or item.get("product") or item.get("name") or "").strip()
    return {
        "id": (item.get("id") or f"slot_{index}").strip() or f"slot_{index}",
        "label": (item.get("label") or f"Vak {index}").strip() or f"Vak {index}",
        "product_id": str(item.get("product_id") or item.get("productId") or "").strip(),
        "product_name": product_name,
        "image_url": str(item.get("image_url") or item.get("image") or item.get("photo") or item.get("thumb") or "").strip(),
        "note": str(item.get("note") or "").strip()}


def normalize_layout_shelf(item, index: int):
    item = item if isinstance(item, dict) else {}
    facings = max(1, min(int(item.get("facings") or item.get("slots_per_shelf") or item.get("slot_count") or 9), 9))
    inferred_name = str(item.get("name") or "").strip().lower()
    is_floor = bool(item.get("is_floor") or item.get("isFloor") or inferred_name == "bodem")
    default_height = "low" if is_floor else "medium"
    height = str(item.get("height") or item.get("shelf_height") or item.get("height_level") or default_height).strip().lower()
    if height not in {"low", "medium", "high", "wine"}:
        height = default_height
    raw_slots = item.get("slots") if isinstance(item.get("slots"), list) else []
    slots = [normalize_layout_slot(slot, i + 1) for i, slot in enumerate(raw_slots[:facings])]
    while len(slots) < facings:
        slots.append(default_layout_slot(len(slots) + 1))
    return {
        "id": (item.get("id") or f"shelf_{index}").strip() or f"shelf_{index}",
        "name": (item.get("name") or ("Bodem" if is_floor else f"Plank {index}")).strip() or ("Bodem" if is_floor else f"Plank {index}"),
        "facings": facings,
        "height": height,
        "is_floor": is_floor,
        "slots": slots}


def normalize_layout_cooler(item, index: int):
    item = item if isinstance(item, dict) else {}
    raw_shelves = item.get("shelves") if isinstance(item.get("shelves"), list) else []
    shelves = [normalize_layout_shelf(shelf, i + 1) for i, shelf in enumerate(raw_shelves)]
    if not shelves:
        shelves = [
            default_layout_shelf(1, name="Plank 1"),
            default_layout_shelf(2, name="Plank 2"),
            default_layout_shelf(3, name="Plank 3"),
            default_layout_shelf(4, slots_per_shelf=9, name="Bodem", height="low", is_floor=True),
        ]
    if not any(bool(shelf.get("is_floor")) for shelf in shelves):
        shelves.append(default_layout_shelf(len(shelves) + 1, slots_per_shelf=9, name="Bodem", height="low", is_floor=True))
    return {
        "id": (item.get("id") or f"cooler_{index}").strip() or f"cooler_{index}",
        "name": (item.get("name") or f"Koelkast {index}").strip() or f"Koelkast {index}",
        "shelves": shelves}


def normalize_layout_unit(item, index: int):
    item = item if isinstance(item, dict) else {}
    raw_coolers = item.get("coolers") if isinstance(item.get("coolers"), list) else []
    coolers = [normalize_layout_cooler(cooler, i + 1) for i, cooler in enumerate(raw_coolers[:3])]
    while len(coolers) < 3:
        coolers.append(default_layout_cooler(len(coolers) + 1))
    return {
        "id": (item.get("id") or f"unit_{index}").strip() or f"unit_{index}",
        "name": (item.get("name") or f"GB{index}").strip() or f"GB{index}",
        "coolers": coolers[:3]}


def normalize_layout_units(raw_units):
    units = [normalize_layout_unit(unit, i + 1) for i, unit in enumerate(raw_units or [])]
    if not units:
        units = default_bar_layout_structure()
    return units[:8]


def get_bar_layouts_data():
    data = load_json(BAR_LAYOUTS_FILE, {"items": [], "active_id": ""})
    if not isinstance(data, dict):
        data = {"items": [], "active_id": ""}
    items = []
    for item in data.get("items", []):
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        if not name:
            continue
        items.append({
            "id": (item.get("id") or slugify(name)).strip() or slugify(name),
            "name": name,
            "note": (item.get("note") or "").strip(),
            "created_at": (item.get("created_at") or "").strip(),
            "units": normalize_layout_units(item.get("units"))})
    data["items"] = items
    data["active_id"] = str(data.get("active_id") or "").strip()
    if data["active_id"] and not any(item["id"] == data["active_id"] for item in items):
        data["active_id"] = ""
    return data


def save_bar_layouts_data(data):
    clean = {"items": [], "active_id": str(data.get("active_id") or "").strip()}
    seen = set()
    for item in data.get("items", []):
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        if not name:
            continue
        item_id = (item.get("id") or slugify(name)).strip() or slugify(name)
        if item_id in seen:
            continue
        seen.add(item_id)
        clean["items"].append({
            "id": item_id,
            "name": name,
            "note": (item.get("note") or "").strip(),
            "created_at": (item.get("created_at") or "").strip(),
            "units": normalize_layout_units(item.get("units"))})
    if clean["active_id"] and not any(item["id"] == clean["active_id"] for item in clean["items"]):
        clean["active_id"] = ""
    save_json(BAR_LAYOUTS_FILE, clean)

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
                    "locatie": type_location(soort)})
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
    general_view["diensten"] = diensten_for_current_user_with_indices(general_data.get("diensten", []))
    general_view["diensten_personal_view"] = not is_casa_admin()
    general_view["fooienpot"] = tip_context["amount"]
    general_view["fooienpot_label"] = tip_context["label"]
    general_view["fooienpot_is_personal"] = tip_context["is_personal"]
    user = get_current_casa_user() or {}
    permissions = current_permissions()
    return {
        "bar": {
            "koelingen": bar_data.get("koelingen", []),
            "fill_items": build_fill_items(bar_data)},
        "general": general_view,
        "types": get_types(),
        "locations": get_locations(),
        "dienst_types": get_dienst_types(),
        "kitchen": get_kitchen_data(),
        "bar_tasks": get_bar_tasks_data(),
        "bar_layouts": get_bar_layouts_data(),
        "recipes": get_recipes_data(),
        "auth": {
            "user_name": user.get("name", ""),
            "role": user.get("role", ""),
            "is_admin": is_casa_admin(),
            "permissions": permissions,
            "permission_labels": permission_labels(),
            "users": load_casa_auth_data().get("users", []) if is_casa_admin() else [],
            "calendar_url": calendar_feed_url_for_current_user()}}


def ics_escape(value):
    value = str(value or "")
    value = value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    value = value.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
    return value


def parse_ics_datetime(datum, time_value, *, fallback_hour=9, fallback_minute=0):
    try:
        day = date.fromisoformat(str(datum or "")[:10])
    except Exception:
        return None
    hour = fallback_hour
    minute = fallback_minute
    raw = str(time_value or "").strip()
    if ":" in raw:
        try:
            parts = raw.split(":")
            hour = int(parts[0])
            minute = int(parts[1])
        except Exception:
            pass
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=AMSTERDAM_TZ)


def calendar_diensten_for_user(user):
    owner_name = str((user or {}).get("name") or "").strip()
    owner_key = owner_name.lower()
    diensten = []
    for raw in get_general_data().get("diensten", []):
        item = normalize_dienst_item(raw)
        if str(item.get("owner_name") or "").strip().lower() == owner_key:
            if normalize_dienst_status(item.get("status")) == "vervallen":
                continue
            diensten.append(item)
    diensten.sort(key=lambda item: ((item.get("datum") or "9999-99-99"), normalize_dienst_time_value(item.get("start") or "23:59"), (item.get("naam") or "").lower()))
    return diensten


def build_calendar_feed_for_user(user):
    from datetime import timedelta
    owner_name = str((user or {}).get("name") or "").strip()
    owner_key = owner_name.lower()
    diensten = calendar_diensten_for_user(user)

    now_stamp = datetime.now(AMSTERDAM_TZ).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Casa Cara//Diensten//NL",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:Casa Cara diensten - {ics_escape(owner_name)}",
        "X-WR-TIMEZONE:Europe/Amsterdam",
        "BEGIN:VTIMEZONE",
        "TZID:Europe/Amsterdam",
        "X-LIC-LOCATION:Europe/Amsterdam",
        "BEGIN:DAYLIGHT",
        "TZOFFSETFROM:+0100",
        "TZOFFSETTO:+0200",
        "TZNAME:CEST",
        "DTSTART:19700329T020000",
        "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
        "END:DAYLIGHT",
        "BEGIN:STANDARD",
        "TZOFFSETFROM:+0200",
        "TZOFFSETTO:+0100",
        "TZNAME:CET",
        "DTSTART:19701025T030000",
        "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]

    for index, item in enumerate(diensten):
        start_dt = parse_ics_datetime(item.get("datum"), item.get("start"), fallback_hour=9)
        end_dt = parse_ics_datetime(item.get("datum"), item.get("einde"), fallback_hour=10)
        if not start_dt:
            continue
        if not end_dt:
            end_dt = start_dt + timedelta(hours=1)
        if end_dt <= start_dt:
            end_dt = end_dt + timedelta(days=1)
        if end_dt <= start_dt:
            end_dt = start_dt + timedelta(hours=1)

        uid_base = f"{owner_key}-{item.get('datum')}-{item.get('start')}-{item.get('einde')}-{item.get('naam')}-{index}"
        title = item.get("naam") or "Dienst"
        location = item.get("locatie") or ""
        description_parts = []
        if item.get("rol"):
            description_parts.append(f"Rol: {item.get('rol')}")
        if item.get("notitie"):
            description_parts.append(f"Notitie: {item.get('notitie')}")
        if item.get("source"):
            description_parts.append(f"Bron: {item.get('source')}")
        description = "\\n".join(description_parts)

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{ics_escape(uid_base)}@casa-cara",
            f"DTSTAMP:{now_stamp}",
            f"DTSTART;TZID=Europe/Amsterdam:{start_dt.strftime('%Y%m%dT%H%M%S')}",
            f"DTEND;TZID=Europe/Amsterdam:{end_dt.strftime('%Y%m%dT%H%M%S')}",
            f"SUMMARY:{ics_escape(title)}",
        ])
        if location:
            lines.append(f"LOCATION:{ics_escape(location)}")
        if description:
            lines.append(f"DESCRIPTION:{ics_escape(description)}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


@casa_cara.route("/casa-cara-calendar/<token>.ics")
def casa_cara_calendar_feed(token):
    user = get_casa_user_by_calendar_token(token)
    if not user:
        return Response("Agenda feed niet gevonden.", status=404, mimetype="text/plain")
    ics = build_calendar_feed_for_user(user)
    response = Response(ics, mimetype="text/calendar; charset=utf-8")
    response.headers["Content-Disposition"] = "inline; filename=casa-cara-diensten.ics"
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@casa_cara.route("/api/casa/calendar-link")
def casa_cara_calendar_link():
    url = calendar_feed_url_for_current_user()
    if not url:
        return jsonify({"ok": False, "message": "Geen ingelogde gebruiker gevonden."}), 401
    user = get_current_casa_user() or {}
    diensten = calendar_diensten_for_user(user)
    return jsonify({"ok": True, "url": url, "count": len(diensten), "first": diensten[0] if diensten else None})


@casa_cara.route("/api/casa/calendar-status")
def casa_cara_calendar_status():
    user = get_current_casa_user() or {}
    url = calendar_feed_url_for_current_user()
    diensten = calendar_diensten_for_user(user)
    return jsonify({
        "ok": True,
        "url": url,
        "count": len(diensten),
        "items": diensten[:10],
        "user": user.get("name", "")
    })



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
      --accent:#ff7a00;
      --accent-soft:rgba(255,122,0,.14);
      --danger:#e06b6b;
      --warn:#ff9a3d;
      --accent-strong:#ff8f1f;
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
        radial-gradient(circle at top left, rgba(255,122,0,.08), transparent 26%),
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
        radial-gradient(circle at top right, rgba(255,122,0,.08), transparent 30%),
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
      background:rgba(255,122,0,.12);
      border:1px solid rgba(255,122,0,.22);
      color:#ffd9bf;
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
      min-height:36px;padding:0 12px;border-radius:12px;border:1px solid rgba(255,255,255,.10);
      background:rgba(255,255,255,.025);color:var(--text);cursor:pointer;font-size:13px;font-weight:700;
    }
    .btn.accent{background:rgba(255,122,0,.10);border-color:rgba(255,122,0,.18);color:#ffd9bf}
    .btn.danger{background:rgba(224,107,107,.08);border-color:rgba(224,107,107,.18);color:#ffd7d7}
    .btn.good{background:rgba(111,202,147,.08);border-color:rgba(111,202,147,.18);color:#d8ffe7}
    .hero{position:relative}
    .hero-tools{position:absolute;right:16px;top:16px;display:flex;gap:8px}
    .icon-gear-btn{width:38px;height:38px;border-radius:12px;border:1px solid rgba(255,255,255,.10);background:rgba(255,255,255,.025);color:var(--text);display:grid;place-items:center;cursor:pointer;font-size:16px;box-shadow:0 8px 18px rgba(0,0,0,.16)}
    .icon-gear-btn:hover{border-color:rgba(255,122,0,.24);background:rgba(255,122,0,.08);color:#ffd9bf}
    .panel-title-row{display:flex;align-items:center;justify-content:space-between;gap:10px}
    .sidebar-kicker{padding:0 4px 8px;color:var(--muted);font-size:11px;letter-spacing:.12em;text-transform:uppercase;font-weight:800;opacity:.88}
    .nav{gap:6px}
    .nav-btn,.sub-btn,.logout-btn,.home-btn{min-height:42px;border-radius:14px;background:rgba(255,255,255,.018);border-color:rgba(255,255,255,.07)}
    .nav-btn:hover,.sub-btn:hover,.home-btn:hover{border-color:rgba(255,255,255,.13);background:rgba(255,255,255,.03)}
    .nav-label{font-size:14px;font-weight:750}
    .sub-btn{min-height:38px;font-size:13px;padding:0 12px}
    .drawer-brand .big{font-size:20px}
    .drawer{background:linear-gradient(180deg,#0a111a,#091019)}
    @media (max-width:640px){
      .hero-tools{right:12px;top:12px}
      .icon-gear-btn{width:34px;height:34px;border-radius:10px}
      .btn{min-height:34px;padding:0 11px;font-size:12px}
    }

    .badge{font-size:11px;padding:2px 6px;
      display:inline-flex;align-items:center;gap:6px;min-height:28px;padding:0 10px;border-radius:999px;
      border:1px solid var(--line);color:var(--muted);background:rgba(255,255,255,.02);font-size:12px;white-space:nowrap;
    }
    .badge.warn{color:#ffd9bf;background:rgba(231,180,93,.10);border-color:rgba(231,180,93,.22)}
    .badge.good{color:#d7ffe6;background:rgba(111,202,147,.10);border-color:rgba(111,202,147,.22)}
    .badge.accent{color:#ffd9bf;background:var(--accent-soft);border-color:rgba(255,122,0,.24)}

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
    .permission-grid{display:grid;grid-template-columns:1fr;gap:10px}.permission-grid.compact{gap:12px}.permission-sections{display:grid;grid-template-columns:1fr;gap:10px}.permission-panel{border:1px solid var(--line);border-radius:14px;padding:10px;background:rgba(255,255,255,.02)}.permission-kicker{margin:0 0 8px;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.10em;font-weight:800}.permission-actions{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}.permission-chip{min-height:30px;padding:0 10px;border-radius:999px;border:1px solid var(--line);background:rgba(255,255,255,.03);color:var(--text);font-size:12px;font-weight:700;cursor:pointer}.permission-chip:hover{border-color:rgba(255,122,0,.24);background:rgba(255,122,0,.08);color:#ffd9bf}.permission-row{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:8px 0;border-top:1px solid rgba(255,255,255,.05)}.permission-row:first-child{border-top:none;padding-top:0}.permission-row:last-child{padding-bottom:0}.permission-inline-label{font-size:13px;line-height:1.25;color:var(--text)}.permission-help{font-size:12px;color:var(--muted);line-height:1.4;margin-top:-2px;margin-bottom:6px}.permission-grid select{width:100%;min-height:42px;border-radius:12px;border:1px solid var(--line);background:rgba(255,255,255,.03);color:var(--text);padding:0 12px;outline:none}.permission-grid input[type='checkbox']{width:16px;height:16px;accent-color:#ff7a00;flex:0 0 auto}@media (min-width:760px){.permission-sections{grid-template-columns:repeat(2,minmax(0,1fr))}}
    .perm-item{display:flex;align-items:flex-start;gap:8px;padding:10px;border:1px solid var(--line);border-radius:12px;background:rgba(255,255,255,.02)}
    .perm-item input{margin-top:1px;width:15px;height:15px}
    .perm-label{font-size:12px;color:var(--text);line-height:1.3}
    .overview-grid{display:grid;grid-template-columns:1fr;gap:12px}.overview-card{border:1px solid var(--line);border-radius:18px;padding:15px;background:linear-gradient(180deg, rgba(18,27,40,.96), rgba(12,19,30,.96));box-shadow:0 12px 24px rgba(0,0,0,.14)}.overview-top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:8px}.overview-kicker{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.10em;font-weight:800;margin-bottom:6px}.overview-title{font-size:18px;font-weight:900;letter-spacing:-.02em;color:var(--text);margin:0 0 4px}.overview-sub{font-size:13px;color:var(--muted);line-height:1.45}.overview-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.mini-list{display:grid;gap:8px}.mini-row{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 12px;border:1px solid rgba(255,255,255,.06);border-radius:12px;background:rgba(255,255,255,.02)}.mini-row strong{display:block;font-size:14px;color:var(--text)}.mini-row span{font-size:12px;color:var(--muted);line-height:1.35}.overview-note{padding:12px 14px;border:1px dashed var(--line-strong);border-radius:14px;color:var(--muted);font-size:13px;line-height:1.5;background:rgba(255,255,255,.02)}
        .dashboard-compact-shell{display:grid;gap:10px}
    .dashboard-next-hero{
      border:1px solid rgba(255,122,0,.18);
      background:
        radial-gradient(circle at top right, rgba(255,122,0,.14), transparent 34%),
        linear-gradient(180deg, rgba(18,27,40,.98), rgba(12,19,30,.98));
      border-radius:22px;
      padding:16px;
      box-shadow:var(--shadow);
    }
    .dashboard-next-hero-top{
      display:flex;
      align-items:flex-start;
      justify-content:space-between;
      gap:12px;
    }
    .dashboard-next-hero-title{
      font-size:24px;
      font-weight:900;
      letter-spacing:-.04em;
      color:var(--text);
      line-height:1.02;
      margin-top:4px;
    }
    .dashboard-next-hero-sub{
      font-size:14px;
      color:var(--muted);
      line-height:1.45;
      margin-top:8px;
      max-width:36rem;
    }
    .dashboard-next-hero-meta{
      display:flex;
      flex-wrap:wrap;
      align-items:center;
      gap:10px;
      margin-top:14px;
    }
    .dashboard-next-hero-time{
      font-size:28px;
      font-weight:900;
      letter-spacing:-.04em;
      color:var(--text);
    }
    .dashboard-next-hero-countdown{
      min-height:30px;
      display:inline-flex;
      align-items:center;
      padding:0 12px;
      border-radius:999px;
      border:1px solid rgba(255,122,0,.18);
      background:rgba(255,122,0,.10);
      color:#ffd9bf;
      font-size:13px;
      font-weight:800;
    }
    .dashboard-compact-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
    .dashboard-mini-card{
    .dashboard-mini-card.salary-card{
      background:
        radial-gradient(circle at top right, rgba(255,122,0,.12), transparent 40%),
        linear-gradient(180deg, rgba(18,27,40,.96), rgba(12,19,30,.96));
      border:1px solid rgba(255,122,0,.15);
    }
    #dashboardSalaryTitle{
      font-size:20px;
      font-weight:900;
      letter-spacing:-0.03em;
    }
    #dashboardSalarySub{
      font-size:12px;
      color:var(--muted);
    }
    #dashboardSalaryBadge{
      background:rgba(255,122,0,.12);
      border:1px solid rgba(255,122,0,.2);
      color:#ffd9bf;
    }
    
      border:1px solid var(--line);
      border-radius:16px;
      padding:13px;
      background:linear-gradient(180deg, rgba(18,27,40,.96), rgba(12,19,30,.96));
      box-shadow:0 10px 22px rgba(0,0,0,.12);
      min-width:0;
    }
    .dashboard-mini-kicker{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.10em;font-weight:800;margin-bottom:6px}
    .dashboard-mini-title{font-size:16px;font-weight:900;letter-spacing:-.02em;color:var(--text);line-height:1.15}
    .dashboard-mini-sub{font-size:12px;color:var(--muted);line-height:1.4;margin:6px 0 10px}
    .dashboard-chip-row{display:flex;flex-wrap:wrap;gap:8px}
    .dashboard-chip-btn{
      min-height:34px;
      padding:0 12px;
      border-radius:999px;
      border:1px solid var(--line);
      background:rgba(255,255,255,.03);
      color:var(--text);
      cursor:pointer;
      font-size:12px;
      font-weight:700;
    }
    .dashboard-chip-btn:hover{border-color:rgba(255,122,0,.24);background:rgba(255,122,0,.08);color:#ffd9bf}
    @media (min-width:860px){
      .dashboard-compact-grid{grid-template-columns:repeat(4,minmax(0,1fr))}
    }
    @media (max-width:640px){
      .dashboard-compact-grid{grid-template-columns:1fr}
      .dashboard-mini-card{padding:12px}
      .dashboard-mini-title{font-size:15px}
    }

    .bot-panel{margin:16px 0 18px;border:1px solid var(--line);background:linear-gradient(180deg, rgba(18,27,40,.98), rgba(12,19,30,.98));border-radius:22px;padding:16px;box-shadow:var(--shadow);display:grid;gap:12px}
    .bot-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
    .bot-title{margin:0;font-size:18px;font-weight:900;letter-spacing:-.02em;color:var(--text)}
    .bot-sub{margin-top:4px;color:var(--muted);font-size:13px;line-height:1.45}
    .bot-shell{border:1px solid rgba(255,255,255,.06);border-radius:18px;background:rgba(255,255,255,.02);overflow:hidden}
    .bot-chat{display:grid;gap:10px;max-height:320px;overflow:auto;padding:14px}
    .bot-chat::-webkit-scrollbar{width:8px}.bot-chat::-webkit-scrollbar-thumb{background:rgba(255,255,255,.10);border-radius:999px}
    .bot-msg{max-width:92%;padding:12px 14px;border-radius:16px;border:1px solid var(--line);font-size:14px;line-height:1.55;word-break:break-word;white-space:pre-wrap}
    .bot-msg.bot{justify-self:start;background:rgba(255,255,255,.025);color:var(--text)}
    .bot-msg.user{justify-self:end;background:rgba(255,122,0,.12);border-color:rgba(255,122,0,.24);color:#ffd9bf}
    .bot-msg.muted{color:var(--muted)}
    .bot-composer{padding:12px 14px 14px;border-top:1px solid rgba(255,255,255,.06);background:linear-gradient(180deg, rgba(10,16,24,.98), rgba(12,19,30,.98));position:sticky;bottom:0}
    .bot-row{display:flex;gap:8px;align-items:center}
    .bot-row input{flex:1;min-height:46px;border-radius:14px;border:1px solid var(--line);background:rgba(255,255,255,.03);color:var(--text);padding:0 14px;outline:none}
    .bot-chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
    .bot-chips.hidden{display:none}
    .bot-chip{min-height:32px;padding:0 12px;border-radius:999px;border:1px solid var(--line);background:rgba(255,255,255,.03);color:var(--text);cursor:pointer;font-size:12px}
    .bot-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
    .bot-action{min-height:34px;padding:0 12px;border-radius:999px;border:1px solid rgba(255,122,0,.22);background:rgba(255,122,0,.10);color:#ffd9bf;cursor:pointer}
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
    .nav-btn.active,.sub-btn.active{border-color:rgba(255,122,0,.30);background:rgba(255,122,0,.10)}
    .nav-left{display:flex;align-items:center;gap:10px;min-width:0}
    .nav-icon{width:24px;height:24px;border-radius:8px;display:grid;place-items:center;background:rgba(255,255,255,.04);color:var(--muted);font-size:13px;flex:0 0 auto}
    .nav-label{font-size:15px;font-weight:700;letter-spacing:-.01em;color:var(--text)}
    .nav-caret{color:var(--muted);transition:transform .18s ease}
    .nav-btn.expanded .nav-caret{transform:rotate(90deg)}
    .sub-list{display:none;gap:8px;padding:4px 0 2px 12px;margin:0 0 4px;border-left:1px solid rgba(255,255,255,.06)}
    .sub-list.open{display:grid}
    .sub-btn{min-height:42px;font-size:14px;border-radius:14px}
    .sub-section-label{
      margin:8px 2px 2px;
      font-size:11px;
      line-height:1;
      font-weight:800;
      letter-spacing:.12em;
      text-transform:uppercase;
      color:var(--muted);
      opacity:.9;
    }
    .sub-section-label:first-child{margin-top:2px}
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
      background:linear-gradient(90deg, rgba(255,122,0,.9), rgba(255,143,31,.95));
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
      background:rgba(255,122,0,.12);
      border:1px solid rgba(255,122,0,.22);
      color:#ffd9bf;
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
      background:linear-gradient(90deg, rgba(255,122,0,.92), rgba(255,143,31,.96));
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
    .task-switcher{margin-top:2px;padding-top:2px}
    .task-switcher-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.09em;font-weight:800;margin-bottom:8px}
    .task-switcher-row{display:flex;gap:8px;overflow:auto;padding-bottom:2px;scrollbar-width:none}
    .task-switcher-row::-webkit-scrollbar{display:none}
    .diensten-day-switcher{margin-bottom:12px}
    .task-switcher-btn{border:1px solid var(--line);background:rgba(255,255,255,.03);color:var(--text);border-radius:999px;min-height:34px;padding:0 12px;white-space:nowrap;cursor:pointer}
    .task-switcher-btn.active{background:rgba(255,122,0,.12);border-color:rgba(255,122,0,.24);color:#ffd9bf}
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
    .dienst-week-compact{margin-top:8px;
      border:1px solid var(--line);
      border-radius:18px;
      background:rgba(255,255,255,.02);
      margin-top:12px;
      overflow:hidden;
      box-shadow:0 10px 22px rgba(0,0,0,.10);
    }
    .dienst-week-summary{
      list-style:none;
      cursor:pointer;
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:8px;
      padding:10px 12px;
      background:linear-gradient(180deg, rgba(18,27,40,.94), rgba(12,19,30,.94));
    }
    .dienst-week-summary::-webkit-details-marker{display:none}
    .dienst-week-summary-left{min-width:0}
    .dienst-week-summary-title{font-size:14px;font-weight:800;letter-spacing:-.02em;color:var(--text)}
    .dienst-week-summary-sub{font-size:11px;color:var(--muted);margin-top:4px}
    .dienst-week-summary-right{display:flex;align-items:center;gap:10px;flex-shrink:0}
    .dienst-week-compact .group-chevron{transition:transform .18s ease;color:var(--muted)}
    .dienst-week-compact[open] .group-chevron{transform:rotate(180deg)}
    .dienst-week-compact-body{padding:6px;display:grid;gap:10px;border-top:1px solid rgba(255,255,255,.06)}
    .dienst-day-compact{padding:6px 7px !important;
      border:1px solid rgba(255,255,255,.06);
      background:rgba(255,255,255,.018);
      border-radius:10px;
      padding:8px;
    }
    .dienst-day-compact-head{gap:6px;
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:10px;
      margin-bottom:8px;
    }
    .dienst-day-compact-title{font-size:14px;font-weight:800;color:var(--text)}
    .dienst-day-compact.is-today{
      border-color:rgba(255,122,0,.22);
      background:
        radial-gradient(circle at top right, rgba(255,122,0,.08), transparent 38%),
        rgba(255,255,255,.025);
      box-shadow:0 12px 24px rgba(0,0,0,.12);
    }
    .dienst-day-compact-head-left{
      display:flex;
      align-items:center;
      gap:8px;
      min-width:0;
    }
    .dienst-card-item-compact.is-today{
      border-color:rgba(255,122,0,.22);
      background:
        linear-gradient(180deg, rgba(255,122,0,.08), rgba(255,255,255,.02));
    }

    .dienst-cards-compact{
      display:grid;
      gap:4px;
    }
    .dienst-card-item-compact{
      padding:6px 8px !important;
      border-radius:8px !important;
      min-height:0;
    }
    .dienst-card-item-compact .dienst-card-top{
      display:grid;
      grid-template-columns:minmax(74px,88px) minmax(0,1fr) auto;
      align-items:center;
      gap:8px;
      margin:0;
    }
    .dienst-card-item-compact .dienst-card-time{
      font-size:12px !important;
      font-weight:900 !important;
      letter-spacing:-.01em;
      white-space:nowrap;
      margin:0;
    }
    .dienst-card-item-compact .dienst-card-title{
      font-size:13px !important;
      font-weight:800 !important;
      line-height:1.15;
      margin:0;
    }
    .dienst-card-item-compact .dienst-card-sub{
      font-size:11px !important;
      line-height:1.2;
      margin-top:1px;
      opacity:.82;
    }
    .dienst-card-main{
      min-width:0;
    }
    .dienst-card-side{
      display:flex;
      align-items:center;
      gap:6px;
      justify-self:end;
      flex-wrap:nowrap;
    }
    .dienst-inline-actions{
      display:flex;
      align-items:center;
      gap:4px;
      margin:0;
    }
    .dienst-inline-btn{
      min-height:26px;
      height:26px;
      padding:0 8px;
      border-radius:8px;
      border:1px solid rgba(255,255,255,.09);
      background:rgba(255,255,255,.03);
      color:var(--text);
      cursor:pointer;
      font-size:11px;
      font-weight:700;
      line-height:1;
      white-space:nowrap;
    }
    .dienst-inline-btn.accent{
      background:rgba(255,122,0,.10);
      border-color:rgba(255,122,0,.18);
      color:#ffd9bf;
    }
    .dienst-inline-btn.danger{
      background:rgba(224,107,107,.08);
      border-color:rgba(224,107,107,.18);
      color:#ffd7d7;
    }
    .dienst-card-item-compact .meta-row{
      display:none !important;
    }
    .dienst-card-item-compact .item-actions{
      display:none !important;
    }
    @media (max-width:700px){
      .dienst-card-item-compact{
        padding:6px 7px !important;
      }
      .dienst-card-item-compact .dienst-card-top{
        grid-template-columns:70px minmax(0,1fr);
        align-items:start;
      }
      .dienst-card-side{
        grid-column:1 / -1;
        justify-self:start;
        padding-left:70px;
        margin-top:4px;
      }
      .dienst-inline-btn{
        min-height:24px;
        height:24px;
        padding:0 7px;
        font-size:10px;
      }
    }
    .dienst-cards-compact{gap:4px}
    .dienst-card-item-compact{padding:6px;border-radius:8px}
    .dienst-card-item-compact .item-actions{margin-top:6px}
    .dienst-card-item-compact .meta-row{margin-top:4px}

    .task-group.done-group:not([open]){
      opacity:.96;
    }
    .diensten-top-grid{display:grid;grid-template-columns:1fr;gap:12px}
    .diensten-quick-actions{display:grid;grid-template-columns:1fr 1fr;gap:10px}
    .diensten-quick-card{min-height:118px;justify-content:flex-start;align-items:flex-start;padding:14px;text-align:left}
    .diensten-quick-card .stat-value{font-size:24px;margin-top:4px}
    .diensten-quick-note{margin-top:12px;color:var(--muted);font-size:13px;line-height:1.45}
    .diensten-list-head{align-items:flex-start}
    .diensten-groups{display:grid;gap:12px}
    .dienst-group-card{border:1px solid var(--line);border-radius:20px;background:linear-gradient(180deg, rgba(18,27,40,.96), rgba(12,19,30,.96));padding:14px;box-shadow:var(--shadow)}
    .dienst-group-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:12px}
    .dienst-group-kicker{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.10em;font-weight:800;margin-bottom:5px}
    .dienst-group-title{margin:0;font-size:19px;font-weight:900;letter-spacing:-.02em;color:var(--text)}
    .dienst-cards{display:grid;gap:10px}
    .dienst-card-item{border:1px solid rgba(255,255,255,.07);border-radius:16px;background:rgba(255,255,255,.03);padding:14px}
    .dienst-card-item.is-changed{border-color:rgba(255,154,61,.28);background:rgba(255,154,61,.06)}
    .dienst-card-top{gap:6px;display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:10px}
    .dienst-card-time{font-size:12px;font-weight:800;font-size:22px;font-weight:900;letter-spacing:-.03em;color:var(--text);margin-bottom:6px}
    .dienst-card-title{font-size:13px;font-weight:700;font-size:15px;font-weight:800;letter-spacing:-.01em;color:var(--text)}
    .dienst-card-sub{font-size:11px;opacity:.8;font-size:13px;color:var(--muted);margin-top:3px;line-height:1.4}
    @media (min-width:860px){.diensten-top-grid{grid-template-columns:1.2fr .8fr}.diensten-quick-actions{grid-template-columns:1fr 1fr}.dienst-cards{grid-template-columns:1fr 1fr}}
    @media (max-width:640px){.diensten-quick-actions{grid-template-columns:1fr}.dienst-group-title{font-size:17px}.dienst-card-time{font-size:12px;font-weight:800;font-size:19px}}
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
      .badge{font-size:11px;padding:2px 6px;font-size:11px;padding:0 8px;min-height:24px}
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
        radial-gradient(circle at top left, rgba(255,122,0,.08), transparent 26%),
        radial-gradient(circle at top right, rgba(112,154,255,.06), transparent 22%),
        linear-gradient(180deg,#070b12,#0b111a 60%,#070b12);
    }


    .layout-shell{display:grid;gap:16px}
    .layout-editor-wrap{display:grid;gap:14px}
    .layout-editor-empty{padding:18px;border:1px dashed var(--line-strong);border-radius:18px;color:var(--muted);background:rgba(255,255,255,.02)}
    .layout-tools{display:flex;flex-wrap:wrap;gap:8px}
    .layout-note{font-size:13px;color:var(--muted);line-height:1.45}
    .layout-unit-card{border:1px solid var(--line);border-radius:22px;padding:14px;background:linear-gradient(180deg, rgba(18,27,40,.96), rgba(12,19,30,.96));box-shadow:0 16px 34px rgba(0,0,0,.2)}
    .layout-unit-top{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}
    .layout-unit-main{display:flex;align-items:center;gap:10px;min-width:0;flex:1}
    .layout-unit-main input,.layout-cooler-name{width:100%;min-height:40px;border-radius:12px;border:1px solid var(--line);background:rgba(255,255,255,.03);color:var(--text);padding:0 12px;outline:none}
    .layout-unit-label{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;font-weight:800}
    .layout-orientation-hint{display:none;padding:10px 12px;border-radius:14px;border:1px solid rgba(255,122,0,.24);background:rgba(255,122,0,.10);color:#ffd9bf;font-size:12px;line-height:1.4}
    .layout-plan-wrap{overflow-x:auto;padding-bottom:6px}
    .layout-plan-wrap::-webkit-scrollbar{height:8px}.layout-plan-wrap::-webkit-scrollbar-thumb{background:rgba(255,255,255,.10);border-radius:999px}
    .layout-plan{display:grid;grid-template-columns:repeat(3,minmax(240px,1fr));gap:14px;min-width:780px}
    .layout-cooler{position:relative;border:1px solid rgba(255,255,255,.10);border-radius:18px;padding:10px;background:linear-gradient(180deg, rgba(8,13,22,.98), rgba(12,19,30,.98));box-shadow:inset 0 1px 0 rgba(255,255,255,.04), 0 14px 28px rgba(0,0,0,.18)}
    .layout-cooler::after{content:'';position:absolute;inset:10px;pointer-events:none;border-radius:12px;border:1px solid rgba(255,255,255,.05)}
    .layout-cooler-top{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:10px}
    .layout-cooler-heading{display:grid;gap:4px;min-width:0;flex:1}
    .layout-cooler-meta{font-size:12px;color:var(--muted)}
    .layout-cooler-window{position:relative;border-radius:14px;padding:12px 10px 10px;background:linear-gradient(180deg, rgba(230,236,244,.18), rgba(210,219,232,.08) 22%, rgba(193,206,222,.10) 48%, rgba(230,236,244,.14) 100%);border:1px solid rgba(255,255,255,.10);overflow:hidden;min-height:560px}
    .layout-cooler-window::before{content:'';position:absolute;left:10px;right:10px;top:8px;height:14px;border-radius:999px;background:linear-gradient(180deg, rgba(255,255,255,.20), rgba(255,255,255,.02));opacity:.55}
    .layout-door-handle{position:absolute;top:46px;right:10px;width:8px;height:132px;border-radius:999px;background:linear-gradient(180deg, rgba(10,14,20,.98), rgba(24,28,36,.92));box-shadow:inset 0 1px 0 rgba(255,255,255,.12), 0 6px 12px rgba(0,0,0,.25);z-index:2}
    .layout-shelves{display:grid;gap:12px;position:relative;z-index:1;padding-right:18px;padding-top:18px}
    .layout-shelf{position:relative;padding-top:6px}
    .layout-shelf::before{content:'';position:absolute;left:0;right:0;top:0;height:3px;border-radius:999px;background:linear-gradient(180deg, rgba(110,120,132,.95), rgba(185,197,212,.55));box-shadow:0 1px 0 rgba(255,255,255,.24)}
    .layout-shelf:first-child{padding-top:0}.layout-shelf:first-child::before{display:none}
    .layout-shelf-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px}
    .layout-shelf-title{font-size:12px;font-weight:900;color:#dce7f5;letter-spacing:.06em;text-transform:uppercase}
    .layout-slots{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
    .layout-slot{position:relative;min-height:112px;border-radius:12px;border:1px solid rgba(8,12,18,.25);background:linear-gradient(180deg, rgba(255,255,255,.78), rgba(240,244,248,.62));padding:8px;display:flex;flex-direction:column;justify-content:space-between;overflow:hidden;cursor:pointer;box-shadow:0 10px 18px rgba(4,8,12,.14)}
    .layout-slot.has-image{background-size:cover;background-position:center}
    .layout-slot.has-image::before{content:'';position:absolute;inset:0;background:linear-gradient(180deg, rgba(8,12,18,.18), rgba(8,12,18,.58));}
    .layout-slot > *{position:relative;z-index:1}
    .layout-slot-label{font-size:10px;color:rgba(31,43,58,.72);text-transform:uppercase;letter-spacing:.08em;font-weight:800}
    .layout-slot.has-image .layout-slot-label,.layout-slot.has-image .layout-slot-name,.layout-slot.has-image .layout-slot-note{color:#fff}
    .layout-slot-name{font-size:13px;font-weight:900;color:#17212d;line-height:1.15}
    .layout-slot-note{font-size:11px;color:#5a6777;line-height:1.25}
    .layout-slot-thumb{width:38px;height:38px;border-radius:10px;border:1px solid rgba(255,122,0,.22);background:rgba(255,122,0,.12);display:grid;place-items:center;font-size:12px;font-weight:900;color:#b37515;margin-bottom:6px;overflow:hidden}
    .layout-slot-thumb img{width:100%;height:100%;object-fit:cover;display:block}
    .layout-slot-empty{color:#6d7886;font-size:12px;font-weight:700}
    .layout-cooler-footer{display:flex;justify-content:center;gap:8px;margin-top:10px}

    .layout.fullscreen-editor-mode{max-width:none;padding:0}
    .topbar.fullscreen-editor-mode,.drawer.fullscreen-editor-mode,.drawer-backdrop.fullscreen-editor-mode{display:none !important}
    .fridge-editor-page{padding:0;max-width:none;width:100%;margin:0;background:#0b1220}
    .fridge-editor-shell{min-height:100dvh;display:grid;grid-template-rows:auto 1fr;background:radial-gradient(circle at top left, rgba(255,122,17,.10), transparent 18%),radial-gradient(circle at top right, rgba(97,165,255,.10), transparent 20%),linear-gradient(180deg,#0b1220,#0f1727 72%,#0a111d)}
    .fridge-editor-shell,.fridge-editor-stage,.fridge-editor-canvas,.layout-readonly-shell,.layout-readonly-stage{max-width:100%;overflow-x:hidden}
    .fridge-editor-topbar{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:16px 22px;border-bottom:1px solid rgba(255,255,255,.08);background:rgba(9,14,24,.82);backdrop-filter:blur(16px);position:sticky;top:0;z-index:20}
    .fridge-editor-kicker{font-size:11px;font-weight:800;letter-spacing:.16em;text-transform:uppercase;color:#7d8ca3;margin-bottom:6px}
    .fridge-editor-title{font-size:34px;font-weight:900;letter-spacing:-.04em;color:#f5f7fb;margin:0}
    .fridge-editor-sub{font-size:14px;color:#8d9bb0;margin-top:6px;line-height:1.5}
    .fridge-editor-headcopy{min-width:0;flex:1 1 auto}
    .fridge-editor-actions{display:flex;flex-wrap:wrap;gap:10px;justify-content:flex-end;flex:0 0 auto}
    .fridge-editor-btn{min-height:46px;padding:0 18px;border-radius:14px;border:1px solid rgba(255,255,255,.10);background:rgba(255,255,255,.04);color:#f5f7fb;cursor:pointer;font-weight:800;box-shadow:0 8px 24px rgba(0,0,0,.14)}
    .fridge-editor-btn.primary{background:#ff7a11;border-color:#ff7a11;color:#fff}
    .fridge-editor-body{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:12px;padding:10px;align-items:start;min-height:calc(100dvh - 76px)}
    .fridge-editor-body.single-canvas{grid-template-columns:minmax(0,1fr)}
    .readonly-mode-shell .fridge-editor-canvas{max-width:none}
    .fridge-editor-panel{position:sticky;top:10px}
    .fridge-editor-canvas{border:1px solid rgba(255,255,255,.08);border-radius:22px;padding:8px;background:linear-gradient(180deg,#0f1727,#101a2b);box-shadow:0 20px 48px rgba(0,0,0,.22)}
    .fridge-editor-toolbar{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px;padding:4px 2px}
    .fridge-editor-toolbar-left{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
    .fridge-editor-select,.fridge-editor-input,.fridge-editor-panel select,.fridge-editor-panel input{min-height:44px;border-radius:12px;border:1px solid rgba(255,255,255,.10);background:#121d30;color:#f5f7fb;padding:0 12px;outline:none}
    .fridge-editor-select option,.fridge-editor-panel select option{background:#121d30;color:#f5f7fb}
    .fridge-editor-stage{overflow:auto;padding-bottom:8px}
    .fridge-editor-stage::-webkit-scrollbar{height:10px;width:10px}.fridge-editor-stage::-webkit-scrollbar-thumb{background:rgba(255,255,255,.16);border-radius:999px}
    .layout-readonly-shell{border:1px solid rgba(255,255,255,.08);border-radius:22px;padding:8px;background:linear-gradient(180deg,#0f1727,#101a2b);box-shadow:0 20px 48px rgba(0,0,0,.16)}
    .layout-readonly-toolbar{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px;padding:4px 2px;flex-wrap:wrap}
    .layout-readonly-toolbar-left{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
    .layout-readonly-stage .fridge-item{cursor:default}
    .layout-readonly-stage .fridge-shelf{cursor:default}
    .layout-readonly-stage .fridge-shelf.active{box-shadow:none;border-color:rgba(255,255,255,.08)}
    
    .fridge-unit{width:100%;min-width:0;border-radius:22px;padding:10px 10px 12px;background:linear-gradient(180deg,#111a2b,#0e1624);box-shadow:inset 0 1px 0 rgba(255,255,255,.03),0 22px 50px rgba(0,0,0,.26);border:1px solid rgba(255,255,255,.07)}
    .fridge-unit-top{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:2px 4px 8px}
    .fridge-unit-name{font-size:17px;font-weight:900;letter-spacing:-.03em;color:#f6f8fb}
    .fridge-unit-note{font-size:12px;color:#94a3b8}
    .fridge-bank{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;position:relative}
    .fridge-door{position:relative;border-radius:20px;padding:8px;background:linear-gradient(180deg,#0d1421,#131d2d);border:1px solid rgba(255,255,255,.08);min-height:520px;display:grid;grid-template-rows:auto 1fr auto;overflow:hidden}
    .fridge-door::before{content:'';position:absolute;inset:8px;border-radius:16px;border:1px solid rgba(255,255,255,.04);pointer-events:none}
    .fridge-door-frame{position:relative;border-radius:16px;padding:10px 10px 8px;background:linear-gradient(180deg,#182336,#101827)}
    .fridge-door-window{position:relative;min-height:410px;border-radius:14px;padding:12px 8px 10px;background:linear-gradient(180deg,rgba(242,247,252,.96),rgba(233,239,246,.93) 28%,rgba(228,235,244,.91) 60%,rgba(244,248,252,.95) 100%);border:2px solid rgba(255,255,255,.34);overflow:hidden;box-shadow:inset 0 0 0 1px rgba(0,0,0,.08), inset 0 20px 28px rgba(255,255,255,.10);display:flex;flex-direction:column}
    .fridge-door-window::before{content:'';position:absolute;left:12px;right:12px;top:8px;height:22px;border-radius:999px;background:linear-gradient(180deg, rgba(255,255,255,.68), rgba(255,255,255,.08));opacity:.58}
    .fridge-handle{position:absolute;top:62px;right:1px;width:10px;height:138px;border-radius:999px;background:linear-gradient(180deg,#1c2735,#404c5d);box-shadow:inset 0 1px 0 rgba(255,255,255,.10),0 8px 16px rgba(0,0,0,.22)}
    .fridge-door-header{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:6px}
    .fridge-door-title{font-size:12px;font-weight:900;color:#f5f7fa}
    .fridge-door-shelves{display:flex;flex-direction:column;justify-content:flex-end;gap:8px;position:relative;padding-top:10px;min-height:100%;height:100%;flex:1}
    .fridge-shelf{position:relative;padding:0 0 14px 0;cursor:pointer}.fridge-shelf.floor{margin-top:auto}.fridge-shelf.floor .fridge-shelf-track{align-self:end}
    .fridge-shelf.active .fridge-shelf-name{color:#ff7a11}
    .fridge-shelf.active .fridge-shelf-track{box-shadow:0 0 0 3px rgba(255,122,17,.20),0 10px 18px rgba(0,0,0,.10)}
    .fridge-shelf.active .fridge-shelf-beam{box-shadow:0 0 0 2px rgba(255,122,17,.24), 0 8px 16px rgba(0,0,0,.14);border-color:rgba(255,122,17,.42)}
    .fridge-shelf-name{margin-bottom:4px;font-size:9px;font-weight:900;letter-spacing:.08em;text-transform:uppercase;color:#617185}
    .fridge-shelf-track{position:relative;min-height:var(--shelf-height,92px);border-radius:14px;padding:8px 4px 12px;background:linear-gradient(180deg,rgba(255,255,255,.24),rgba(255,255,255,.10));border:1px solid rgba(132,148,166,.22);display:flex;align-items:flex-end}
    .fridge-shelf-track::before{content:'';position:absolute;left:8px;right:8px;top:6px;height:12px;border-radius:999px;background:linear-gradient(180deg,rgba(255,255,255,.24),rgba(255,255,255,0));opacity:.55}
    .fridge-shelf-products{display:grid;grid-template-columns:repeat(var(--slot-count,9),minmax(0,1fr));gap:2px;align-items:end;height:100%;width:100%}
    .fridge-item{min-height:0;height:100%;align-self:end;border-radius:8px;padding:0 1px 0;background:transparent;border:none;display:flex;align-items:flex-end;justify-content:center;box-shadow:none;overflow:visible;position:relative}
    .fridge-item.selected{outline:2px solid rgba(255,122,17,.85);outline-offset:-2px;box-shadow:0 0 0 3px rgba(255,122,17,.18),0 8px 14px rgba(31,41,55,.12)}
    .fridge-item-thumb{width:100%;height:100%;min-height:0;border-radius:8px 8px 4px 4px;display:flex;align-items:flex-end;justify-content:center;overflow:hidden;background:transparent;position:relative}
    .fridge-item-thumb img{width:100%;height:100%;max-width:none;max-height:none;object-fit:contain;object-position:center bottom;background:transparent;display:block;align-self:flex-end;transform:translateY(4px) scale(1.18);transform-origin:center bottom;filter:drop-shadow(0 2px 2px rgba(0,0,0,.12))}
    .fridge-item-pill{display:inline-flex;align-items:center;justify-content:center;min-width:34px;height:34px;padding:0 8px;border-radius:999px;background:linear-gradient(180deg,#e9eef5,#dbe3ec);color:#1d2937;font-size:10px;font-weight:900}
    .fridge-item-label{display:none}
    .fridge-item.empty{min-height:44px;height:100%;background:transparent;border:1px dashed rgba(98,114,130,.12);box-shadow:none;border-radius:8px}
    .fridge-item.empty .fridge-item-thumb{background:transparent;border:1px dashed rgba(98,114,130,.12)}
    .fridge-item.empty .fridge-item-label{color:#8b97a6}
    .fridge-shelf-beam{position:absolute;left:-1px;right:-1px;bottom:5px;height:8px;border-radius:999px;border:1px solid rgba(120,128,140,.42);background:linear-gradient(180deg,#c5ced8,#7f8b9b 36%,#cbd4de 100%);box-shadow:0 3px 8px rgba(0,0,0,.10)}
    .fridge-base{margin-top:6px;height:58px;border-radius:0 0 18px 18px;background:linear-gradient(180deg,#121720,#0d1118);border-top:1px solid rgba(255,255,255,.06);position:relative}
    .fridge-base::before{content:'';position:absolute;left:50%;transform:translateX(-50%);bottom:14px;width:82px;height:18px;border-radius:6px;background:linear-gradient(180deg,#444b55,#21262f);box-shadow:inset 0 1px 0 rgba(255,255,255,.12)}
    .fridge-editor-panel{border:1px solid rgba(255,255,255,.08);border-radius:22px;padding:14px;background:linear-gradient(180deg,#111a2b,#0e1625);box-shadow:0 16px 40px rgba(0,0,0,.18);position:sticky;top:78px;color:#f5f7fb}
    .fridge-editor-panel h3{margin:0 0 4px;font-size:21px;color:#f5f7fb}
    .fridge-editor-panel p{margin:0 0 14px;color:#8d9bb0;font-size:13px;line-height:1.5}
    .fridge-panel-block{display:grid;gap:10px;margin-bottom:16px}
    .fridge-panel-section{border:1px solid rgba(255,255,255,.08);border-radius:18px;padding:12px;background:#121d30;margin-bottom:14px}
    .fridge-panel-section-top{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px}
    .fridge-panel-section-title{font-size:13px;font-weight:900;letter-spacing:.08em;text-transform:uppercase;color:#d8e0ec}
    .fridge-panel-collapse{min-height:34px;padding:0 12px;border-radius:10px;border:1px solid rgba(255,255,255,.10);background:rgba(255,255,255,.04);color:#f5f7fb;font-weight:800;cursor:pointer}
    .fridge-panel-save{min-height:40px;padding:0 14px;border-radius:12px;border:1px solid rgba(255,122,17,.22);background:rgba(255,122,17,.14);color:#ffd6b3;font-weight:900;cursor:pointer}
    .fridge-panel-grid{display:grid;gap:10px}
    .fridge-panel-label{font-size:11px;font-weight:900;letter-spacing:.14em;text-transform:uppercase;color:#718198}
    .fridge-facing-grid{display:grid;grid-template-columns:repeat(9,1fr);gap:8px}
    .fridge-facing-btn{min-height:42px;border-radius:12px;border:1px solid rgba(255,255,255,.10);background:#162236;color:#f5f7fb;cursor:pointer;font-weight:900}
    .fridge-facing-btn.active{background:#ff7a11;border-color:#ff7a11;color:#fff}
    .fridge-product-preview{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
    .fridge-preview-card{border:1px solid rgba(255,255,255,.08);border-radius:14px;padding:8px;background:#121d30;display:grid;gap:6px;cursor:pointer;color:#f5f7fb;min-width:0}
    .fridge-preview-card.active{border-color:#ff7a11;box-shadow:0 0 0 2px rgba(255,122,17,.18)}
    .fridge-preview-thumb{height:86px;border-radius:10px;background:linear-gradient(180deg,#233149,#182338);display:flex;align-items:center;justify-content:center;overflow:hidden;color:#d9e2ef;font-weight:800;padding:4px}
    .fridge-preview-thumb img{width:100%;height:100%;object-fit:contain;object-position:center bottom;background:#fff;border-radius:8px;transform:scale(1.14)}
    .fridge-image-lock{display:block}
    .fridge-image-lock-thumb{height:120px;border-radius:14px;background:linear-gradient(180deg,#233149,#182338);display:flex;align-items:flex-end;justify-content:center;overflow:hidden;padding:6px}
    .fridge-image-lock-thumb img{width:100%;height:100%;object-fit:contain;object-position:center bottom;background:transparent}
    .fridge-image-lock-empty{min-height:64px;border-radius:12px;border:1px dashed rgba(255,255,255,.14);display:grid;place-items:center;color:#8d9bb0;background:rgba(255,255,255,.03);font-size:13px;text-align:center;padding:10px}
    .fridge-editor-mini-note{font-size:12px;color:#8d9bb0;line-height:1.45}
    .fridge-preview-name{display:none}
    .fridge-editor-note{padding:12px 14px;border-radius:16px;background:#121d30;border:1px solid rgba(255,255,255,.08);font-size:12px;color:#8d9bb0;line-height:1.5}
    .fridge-editor-empty{padding:20px;border-radius:18px;border:1px dashed rgba(255,255,255,.16);color:#8d9bb0;background:#111a2b}
    .fridge-rotate-hint{display:none;margin-bottom:14px;padding:12px 14px;border-radius:16px;background:rgba(255,122,17,.10);border:1px solid rgba(255,122,17,.22);color:#ffbf8a;font-size:13px;line-height:1.45}.fridge-panel-inline-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.fridge-inline-neutral,.fridge-inline-accent,.fridge-inline-danger{min-height:38px;padding:0 12px;border-radius:10px;font-weight:800;cursor:pointer}.fridge-inline-neutral{border:1px solid var(--line);background:rgba(255,255,255,.04);color:var(--text)}.fridge-inline-accent{border:1px solid rgba(255,122,0,.26);background:rgba(255,122,0,.14);color:#ffd9bf}.fridge-inline-danger{border:1px solid rgba(224,107,107,.28);background:rgba(224,107,107,.12);color:#ffd7d7}
    .fridge-door-badge{display:inline-flex;align-items:center;min-height:30px;padding:0 12px;border-radius:999px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);font-size:12px;color:#c5cdd8}
    @media (max-width: 1280px){.fridge-editor-body{grid-template-columns:1fr}.fridge-editor-panel{position:relative;top:auto}.fridge-unit{min-width:980px}}
    @media (max-width: 900px){.fridge-editor-title{font-size:28px}.fridge-rotate-hint{display:block}.fridge-editor-body{grid-template-columns:1fr;padding:8px}.fridge-editor-panel{position:static}.fridge-editor-topbar{padding:14px 12px}.fridge-unit{min-width:0;width:100%;max-width:100%}.fridge-editor-shell{min-height:100dvh;overflow-x:hidden}}

    @media (min-width: 901px){.fridge-editor-stage{overflow-x:hidden}.fridge-bank{overflow:hidden}}


    .layout-mini-btn{min-height:32px;padding:0 10px;border-radius:10px;border:1px solid var(--line);background:rgba(255,255,255,.03);color:var(--text);font-size:12px;cursor:pointer}
    .layout-mini-btn.danger{background:rgba(224,107,107,.10);border-color:rgba(224,107,107,.20);color:#ffd7d7}
    @media (max-width: 820px){.layout-orientation-hint{display:block}.layout-unit-top{align-items:flex-start;flex-direction:column}.layout-plan{min-width:760px}}
    @media (max-width: 560px){.layout-slot{min-height:100px}.layout-cooler-window{min-height:520px}}

  
    .fridge-editor-mobile-tip{display:none}
    .mobile-sheet-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.56);backdrop-filter:blur(3px);opacity:0;pointer-events:none;transition:.2s ease;z-index:72}
    .mobile-sheet-backdrop.open{opacity:1;pointer-events:auto}
    .mobile-sheet{position:fixed;left:0;right:0;bottom:0;z-index:73;transform:translateY(104%);transition:transform .24s ease;pointer-events:none;padding:0 8px}
    .mobile-sheet.open{transform:translateY(0);pointer-events:auto}
    .mobile-sheet-card{background:linear-gradient(180deg,#111a28,#0d1420);border-top-left-radius:24px;border-top-right-radius:24px;border:1px solid rgba(255,255,255,.08);box-shadow:0 -20px 40px rgba(0,0,0,.36);max-height:min(86dvh,820px);overflow:hidden;overscroll-behavior:contain;-webkit-overflow-scrolling:touch;padding:12px 14px 0;display:flex;flex-direction:column}
    .mobile-sheet-grab{width:56px;height:5px;border-radius:999px;background:rgba(255,255,255,.20);margin:0 auto 10px}
    .mobile-sheet-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:10px}
    .mobile-sheet-kicker{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:800;margin-bottom:4px}
    .mobile-sheet-title{font-size:18px;font-weight:900;letter-spacing:-.03em;color:#f5f7fb}
    .mobile-sheet-sub{font-size:13px;color:#97a6bb;line-height:1.45;margin-top:2px}
    .mobile-sheet-close{width:38px;height:38px;border-radius:12px;border:1px solid rgba(255,255,255,.10);background:rgba(255,255,255,.03);color:#fff;display:grid;place-items:center}
    #barLayoutShelfMobileBody{padding:0 0 132px;overflow:auto;-webkit-overflow-scrolling:touch;min-height:0}
    .mobile-sheet-actions{display:none;position:sticky;bottom:0;z-index:4;gap:10px;justify-content:flex-end;padding:12px 14px calc(12px + env(safe-area-inset-bottom,0px));margin:0 -14px 0;border-top:1px solid rgba(255,255,255,.08);background:linear-gradient(180deg, rgba(13,20,32,.18), rgba(13,20,32,.96) 26%, #0d1420 100%);box-shadow:0 -12px 32px rgba(0,0,0,.30)}
    .mobile-sheet-actions .fridge-editor-btn{flex:1 1 0;justify-content:center}
    .mobile-sheet-actions .fridge-editor-btn.primary{box-shadow:0 10px 26px rgba(255,122,17,.22)}
    @media (max-width: 900px){
      .fridge-editor-topbar{padding:14px 14px 12px;align-items:stretch;flex-direction:column;justify-content:flex-start}
      .fridge-editor-title{font-size:24px;line-height:1.02;max-width:100%}
      .fridge-editor-sub{font-size:13px;max-width:100%;padding-right:0}
      .fridge-editor-actions{width:100%;justify-content:stretch;flex-wrap:nowrap;display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}
      .fridge-editor-actions .fridge-editor-btn{width:100%}
      .fridge-editor-btn{min-height:40px;padding:0 14px;border-radius:12px;font-size:13px}
      .fridge-editor-body{grid-template-columns:1fr;padding:8px}
      .fridge-editor-panel{display:none !important}
      .fridge-editor-canvas{padding:10px;overflow-x:hidden;overflow-y:visible;width:100%;max-width:100%}
      .fridge-editor-toolbar{flex-direction:column;align-items:stretch;gap:10px;margin-bottom:8px}
      .fridge-editor-toolbar-left{display:flex;flex-direction:column;align-items:stretch;gap:8px;min-width:0}
      .fridge-editor-toolbar-left > *{min-width:0}
      .fridge-editor-toolbar .badge{font-size:11px;padding:2px 6px;display:block;width:100%;white-space:normal;line-height:1.35}
      .fridge-editor-toolbar .actions{display:none}
      .fridge-editor-select{min-height:42px;width:100%}
      .fridge-editor-stage{overflow-x:hidden;overflow-y:visible;padding-bottom:0;width:100%;max-width:100%}
      .mobile-sheet-actions{display:flex}
      .fridge-unit{padding:8px;border-radius:18px}
      .fridge-unit-top{padding:0 2px 6px}
      .fridge-unit-name{font-size:16px}
      .fridge-unit-note{font-size:11px;line-height:1.35}
      .fridge-door-badge{display:none}
      .fridge-bank{display:grid;grid-template-columns:minmax(0,1fr);gap:8px;overflow:visible;padding-bottom:0;width:100%;max-width:100%;min-width:0}
      .fridge-door{min-height:0;padding:6px;border-radius:16px;width:100%;max-width:100%;min-width:0;overflow:hidden}
      .fridge-door-frame{padding:6px 6px 5px;border-radius:13px;width:100%;max-width:100%;min-width:0;overflow:hidden}
      .fridge-door-window{min-height:0;padding:8px 5px 6px;border-radius:11px;width:100%;max-width:100%;min-width:0;overflow:hidden}
      .fridge-handle{top:46px;right:0;width:8px;height:96px}
      .fridge-door-title{font-size:10px}
      .fridge-door-header{margin-bottom:3px}
      .fridge-door-shelves{gap:5px;padding-top:6px}
      .fridge-shelf{padding-bottom:9px}
      .fridge-shelf-name{font-size:8px;margin-bottom:3px}
      .fridge-shelf-track{padding:6px 2px 8px;border-radius:10px;width:100%;max-width:100%;min-width:0}
      .fridge-shelf-track::before{left:6px;right:6px;top:5px;height:10px}
      .fridge-shelf-products{gap:3px;width:100%;max-width:100%;min-width:0}
      .fridge-shelf-beam{bottom:4px;height:6px}
      .fridge-item{min-width:0;border-radius:8px}
      .fridge-item-thumb{padding:1px}
      .fridge-item-thumb img{max-height:44px;transform:translateY(2px) scale(1.02)}
      .fridge-item.empty{min-height:32px}
      .fridge-base{margin-top:4px;height:40px;border-radius:0 0 14px 14px}
      .fridge-base::before{bottom:10px;width:64px;height:12px}
      .fridge-rotate-hint{display:none !important}
      .fridge-editor-mobile-tip{display:block;margin-bottom:10px;padding:10px 12px;border-radius:14px;border:1px solid rgba(255,122,0,.24);background:rgba(255,122,0,.10);color:#ffd9bf;font-size:12px;line-height:1.45}
      .fridge-panel-section,.fridge-panel-block{margin-bottom:12px}
      .fridge-panel-grid{grid-template-columns:1fr !important}
      .fridge-facing-grid{grid-template-columns:repeat(4,minmax(0,1fr)) !important}
      .fridge-product-preview{grid-template-columns:repeat(2,minmax(0,1fr)) !important}
      .fridge-preview-card{min-height:96px}
      .fridge-preview-name{font-size:11px}
      .fridge-bank.single-cooler-mobile,.fridge-bank.single-cooler-mobile .fridge-door{width:100%;max-width:100%;min-width:0}
      .fridge-editor-shell,.layout-readonly-shell,.layout-readonly-stage,.fridge-unit,.fridge-bank,.fridge-door,.fridge-door-frame,.fridge-door-window{overflow-x:hidden;max-width:100%}
      .mobile-sheet .fridge-panel-inline-actions--simple{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
      .mobile-sheet .fridge-panel-inline-actions--simple .fridge-inline-accent,
      .mobile-sheet .fridge-panel-inline-actions--simple .fridge-inline-danger{width:100%;justify-content:center}
      .mobile-sheet .fridge-panel-inline-actions--simple .fridge-panel-save{display:none}
      .mobile-sheet .fridge-panel-inline-actions:not(.fridge-panel-inline-actions--simple){display:flex;flex-direction:column}
      .mobile-sheet .fridge-panel-inline-actions:not(.fridge-panel-inline-actions--simple) > *{width:100%}
    }
    @media (max-width: 520px){
      .fridge-editor-topbar{padding:12px 12px 10px}
      .fridge-editor-title{font-size:22px}
      .fridge-editor-canvas{padding:8px}
      .fridge-unit{padding:7px}
      .fridge-unit-top{padding:0 1px 5px}
      .fridge-unit-name{font-size:15px}
      .fridge-unit-note{font-size:10px}
      .fridge-bank{gap:7px}
      .fridge-door{padding:5px;border-radius:14px}
      .fridge-door-frame{padding:5px 5px 4px;border-radius:12px}
      .fridge-door-window{padding:7px 4px 5px;border-radius:10px}
      .fridge-door-window::before{left:8px;right:8px;top:6px;height:16px}
      .fridge-handle{top:42px;height:82px;width:7px}
      .fridge-door-title{font-size:9px}
      .fridge-door-shelves{gap:4px;padding-top:5px}
      .fridge-shelf{padding-bottom:8px}
      .fridge-shelf-name{font-size:7px;margin-bottom:2px}
      .fridge-shelf-track{padding:5px 2px 7px;border-radius:9px}
      .fridge-shelf-track::before{left:5px;right:5px;top:4px;height:8px}
      .fridge-shelf-beam{bottom:3px;height:5px}
      .fridge-item-thumb img{max-height:38px;transform:translateY(1px) scale(1.04)}
      .fridge-item.empty{min-height:26px}
      .fridge-base{height:32px}
      .fridge-base::before{bottom:8px;width:52px;height:10px}
    }


    .checklists-shell{display:grid;gap:16px}
    .checklists-top{display:grid;gap:12px}
    .checklists-filter-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
    .check-filter{border:1px solid var(--line-strong);background:rgba(255,255,255,.03);color:var(--text);padding:7px 11px;border-radius:999px;font-weight:800;cursor:pointer;font-size:12px;line-height:1}
    .check-filter.active{background:linear-gradient(180deg,#ff9a52,#ff7a1a);color:#1d1409;border-color:transparent;box-shadow:0 12px 24px rgba(255,122,26,.20)}
    .check-settings-btn{margin-left:auto;width:34px;height:34px;border-radius:10px;border:1px solid var(--line-strong);background:rgba(255,255,255,.03);color:var(--text);display:grid;place-items:center;cursor:pointer;font-size:15px}
    .check-datebar{display:flex;align-items:center;gap:8px;padding:9px 11px;border-radius:16px;background:linear-gradient(180deg,rgba(255,255,255,.04),rgba(255,255,255,.02));border:1px solid var(--line)}
    .check-date-btn{width:30px;height:30px;border-radius:10px;border:1px solid var(--line);background:rgba(255,255,255,.02);color:var(--text);display:grid;place-items:center;cursor:pointer;font-size:14px}
    .check-date-main{min-width:0;flex:1;display:flex;flex-direction:column;gap:3px}
    .check-date-label{font-size:18px;font-weight:900;letter-spacing:-.03em}
    .check-date-sub{font-size:13px;color:var(--muted)}
    .check-today-btn{border:none;background:none;color:#ff9a52;font-weight:900;cursor:pointer;padding:0 2px;white-space:nowrap;font-size:13px}
    .check-progress-card{padding:20px;border-radius:24px;background:linear-gradient(180deg,rgba(18,26,40,.96),rgba(12,19,31,.94));border:1px solid var(--line);box-shadow:var(--shadow)}
    .check-progress-top{display:flex;gap:12px;justify-content:space-between;align-items:flex-start}
    .check-progress-title{font-size:15px;color:var(--muted);font-weight:800;letter-spacing:.04em;text-transform:uppercase}
    .check-progress-count{font-size:34px;font-weight:900;letter-spacing:-.05em}
    .check-progress-meta{font-size:15px;color:var(--muted);margin-top:4px}
    .check-progress-percent{font-size:42px;font-weight:900;letter-spacing:-.06em;color:#ff9a52;line-height:1}
    .check-progress-bar{height:10px;border-radius:999px;background:rgba(255,255,255,.06);overflow:hidden;margin-top:14px}
    .check-progress-bar span{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#ff9a52,#ff7a1a)}
    .checklists-sections{display:grid;gap:16px}
    .check-zone{padding:15px;border-radius:22px;background:linear-gradient(180deg,rgba(18,26,40,.96),rgba(12,19,31,.94));border:1px solid var(--line);box-shadow:var(--shadow)}
    .check-zone-head{display:flex;gap:12px;justify-content:space-between;align-items:flex-start;margin-bottom:12px}
    .check-zone-title{font-size:28px;font-weight:900;letter-spacing:-.05em}
    .check-zone-sub{font-size:14px;color:var(--muted);margin-top:4px}
    .check-zone-right{display:flex;align-items:center;gap:12px}
    .check-zone-count{font-size:15px;color:var(--muted);font-weight:800}
    .check-zone-progress{height:8px;border-radius:999px;background:rgba(255,255,255,.06);overflow:hidden;margin-bottom:14px}
    .check-zone-progress span{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#ffb770,#ff7a1a)}
    .check-list-card{border:1px solid var(--line);border-radius:22px;background:rgba(255,255,255,.025);overflow:hidden}
    .check-list-card + .check-list-card{margin-top:12px}
    .check-list-head{display:flex;gap:10px;justify-content:space-between;align-items:center;padding:13px 14px;cursor:pointer}
    .check-list-main{min-width:0;flex:1}
    .check-list-name{font-size:18px;font-weight:900;letter-spacing:-.03em}
    .check-list-meta{font-size:14px;color:var(--muted);margin-top:4px}
    .check-list-right{display:flex;align-items:center;gap:10px}
    .check-list-toggle{width:32px;height:32px;border-radius:999px;border:1px solid var(--line);display:grid;place-items:center;color:var(--muted);font-size:16px}
    .check-list-card.open .check-list-toggle{transform:rotate(180deg);color:var(--text)}
    .check-list-body{display:none;padding:0 0 2px}
    .check-list-card.open .check-list-body{display:block}
    .check-task{border-top:1px solid rgba(255,255,255,.05)}
    .check-task-head{display:flex;align-items:flex-start;gap:10px;padding:12px 14px;cursor:pointer}
    .check-circle{width:22px;height:22px;min-width:22px;border-radius:999px;border:2px solid rgba(255,255,255,.16);display:grid;place-items:center;font-weight:900;font-size:11px;color:#07111d;background:rgba(255,255,255,.03)}
    .check-circle.done{background:linear-gradient(180deg,#7adfa2,#57c97f);border-color:transparent;color:#062214}
    .check-task-title{font-size:16px;font-weight:900;letter-spacing:-.02em}
    .check-task-title.done,.check-subtask-title.done{text-decoration:line-through;color:var(--muted)}
    .check-task-sub{font-size:12px;color:var(--muted);margin-top:3px}
    .check-task-right{display:flex;align-items:center;gap:8px;margin-left:auto}
    .check-subtasks{display:grid;gap:0;padding:0 14px 10px 46px}
    .check-subtask{display:flex;gap:9px;align-items:flex-start;padding:8px 0;border-top:1px dashed rgba(255,255,255,.06)}
    .check-subtask:first-child{border-top:none}
    .check-subcircle{width:18px;height:18px;min-width:18px;border-radius:999px;border:2px solid rgba(255,255,255,.18);display:grid;place-items:center;font-size:10px;font-weight:900;background:rgba(255,255,255,.03)}
    .check-subcircle.done{background:linear-gradient(180deg,#7adfa2,#57c97f);border-color:transparent;color:#062214}
    .check-subtask-title{font-size:14px;font-weight:800;line-height:1.3}
    .check-subtask-meta{font-size:12px;color:var(--muted);margin-top:2px}
    .check-empty{padding:22px;border-radius:22px;border:1px dashed rgba(255,255,255,.10);background:rgba(255,255,255,.02);color:var(--muted)}
    .check-tip{font-size:13px;color:var(--muted);padding:0 4px}
    .check-readonly{font-size:13px;color:#ffb770;padding:0 2px}
    .check-manage-links{display:flex;gap:10px;flex-wrap:wrap;margin-top:4px}
    .check-mini-btn{border:1px solid var(--line);background:rgba(255,255,255,.03);color:var(--text);padding:6px 10px;border-radius:999px;font-weight:700;cursor:pointer;font-size:11px;line-height:1.05}
    .check-mini-btn.danger{border-color:rgba(224,107,107,.28);color:#ffd8d8;background:rgba(224,107,107,.08)}
    .check-admin-wrap{display:grid;gap:14px}
    .check-admin-note{font-size:13px;color:var(--muted);line-height:1.5}
    .check-admin-section{display:grid;gap:12px;padding:14px;border-radius:18px;border:1px solid var(--line);background:rgba(255,255,255,.025)}
    .check-admin-section-head,.check-admin-list-head,.check-admin-task-head,.check-admin-subtask{display:flex;gap:10px;justify-content:space-between;align-items:flex-start}
    .check-admin-title{font-size:18px;font-weight:900;letter-spacing:-.03em}
    .check-admin-sub,.check-admin-list-meta,.check-admin-task-meta,.check-admin-subtask-meta{font-size:12px;color:var(--muted);margin-top:3px}
    .check-admin-lists,.check-admin-tasks,.check-admin-subtasks{display:grid;gap:10px}
    .check-admin-list,.check-admin-task{display:grid;gap:10px;padding:12px;border-radius:16px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.02)}
    .check-admin-list-name,.check-admin-task-name,.check-admin-subtask-name{font-size:14px;font-weight:800;line-height:1.25}
    .check-admin-page{display:grid;gap:14px}
    .check-admin-toolbar{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
    .check-admin-editor{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);border-radius:18px;padding:16px}
    .check-admin-editor-title{font-size:16px;font-weight:900;margin-bottom:6px}
    .check-admin-editor-sub{font-size:13px;color:var(--muted);margin-bottom:12px}
    .check-admin-layout{display:grid;gap:14px}
    .check-admin-actions{display:flex;gap:8px;flex-wrap:wrap}
    .check-admin-actions{display:flex;gap:7px;flex-wrap:wrap;justify-content:flex-end}
    .check-admin-empty{font-size:12px;color:var(--muted);padding:8px 0 2px}
    .check-zone-pill{padding:6px 10px;border-radius:999px;background:rgba(255,154,82,.14);color:#ffb770;font-size:13px;font-weight:800}

    @media (max-width: 720px){
      .checklists-shell{gap:12px}
      .checklists-top{gap:10px}
      .checklists-filter-row{gap:7px}
      .check-filter{padding:5px 9px;font-size:10px}
      .check-settings-btn{width:30px;height:30px;font-size:13px;border-radius:9px}
      .check-datebar{padding:8px 10px;gap:7px;border-radius:14px}
      .check-date-btn{width:26px;height:26px;font-size:12px;border-radius:8px}
      .check-date-label{font-size:16px}
      .check-date-sub{font-size:11px}
      .check-today-btn{font-size:11px}
      .check-progress-card{padding:14px 14px 13px;border-radius:18px}
      .check-progress-count{font-size:24px}
      .check-progress-percent{font-size:32px}
      .check-zone{padding:12px 11px;border-radius:16px}
      .check-zone-title{font-size:20px}
      .check-list-head{padding:11px 11px}
      .check-list-name{font-size:15px}
      .check-task-head{padding:13px 13px;gap:11px}
      .check-circle{width:30px;height:30px;min-width:30px;font-size:13px}
      .check-task-title{font-size:16px}
      .check-task-sub{font-size:12px}
      .check-subtasks{padding:0 13px 11px 54px}
      .check-subcircle{width:18px;height:18px;min-width:18px;font-size:10px}
      .check-subtask-title{font-size:14px}
      .check-admin-editor{padding:14px}
      .check-mini-btn{padding:6px 10px;font-size:11px}
    }



    /* === Global Casa Cara makeover: checklist theme across the app === */
    :root{
      --bg:#070b12;
      --bg-elev:#0d1420;
      --bg-card:#111a28;
      --bg-card-2:#18263a;
      --bg-soft:rgba(255,255,255,.026);
      --line:rgba(236,223,197,.09);
      --line-strong:rgba(236,223,197,.18);
      --text:#f4f7fb;
      --muted:#a9b8cb;
      --accent:#d7a85a;
      --accent-2:#f0c980;
      --accent-soft:rgba(215,168,90,.14);
      --accent-glow:rgba(215,168,90,.24);
      --danger:#ee8d8d;
      --warn:#ff9a33;
      --good:#81d2a1;
      --shadow:0 24px 56px rgba(0,0,0,.34);
      --shadow-soft:0 14px 34px rgba(0,0,0,.24);
      --radius-xl:26px;
      --radius-lg:19px;
      --radius-md:15px;
      --radius-sm:12px;
    }

    body, .app{
      background:
        radial-gradient(circle at top left, rgba(215,168,90,.10), transparent 24%),
        radial-gradient(circle at top right, rgba(240,201,128,.05), transparent 18%),
        linear-gradient(180deg,#070b12 0%,#0b121c 52%,#070b12 100%) !important;
    }

    .topbar,
    .drawer,
    .sheet-card,
    .modal-card,
    .panel,
    .hero,
    .overview-card,
    .stat-card,
    .list-item,
    .mini-row,
    .permission-panel,
    .admin-shell,
    .admin-overview-card,
    .admin-detail-card,
    .admin-task-card,
    .admin-subtask-card,
    .editor-shell,
    .editor-card,
    .checklist-card,
    .tasklist-card,
    .recipe-card,
    .cooler-card,
    .home-card,
    .card{
      border-color:var(--line) !important;
      box-shadow:var(--shadow-soft);
    }

    .topbar{
      background:linear-gradient(180deg, rgba(10,15,23,.96), rgba(9,15,23,.88)) !important;
      border-bottom:1px solid var(--line);
      box-shadow:0 10px 26px rgba(0,0,0,.18);
    }
    .title{font-size:20px;font-weight:900;letter-spacing:-.03em}
    .eyebrow{color:#ccb288;font-weight:700;letter-spacing:.1em;text-transform:uppercase}

    .drawer{
      background:
        radial-gradient(circle at top left, rgba(215,168,90,.09), transparent 26%),
        linear-gradient(180deg, #0b121c, #091019) !important;
      border-right:1px solid var(--line);
      box-shadow:24px 0 48px rgba(0,0,0,.28);
    }

    .hero,
    .panel,
    .overview-card,
    .stat-card,
    .list-item,
    .sheet-card,
    .modal-card,
    .permission-panel,
    .mini-row,
    .admin-overview-card,
    .admin-detail-card,
    .admin-task-card,
    .admin-subtask-card,
    .card{
      background:
        radial-gradient(circle at top right, rgba(215,168,90,.08), transparent 34%),
        linear-gradient(180deg, rgba(20,29,42,.98), rgba(12,19,30,.98)) !important;
      backdrop-filter:blur(12px);
    }

    .hero,
    .panel,
    .overview-card,
    .stat-card,
    .sheet-card,
    .modal-card,
    .checklist-card,
    .tasklist-card,
    .card{
      border-radius:22px !important;
    }

    .section-title,
    .panel-title,
    .overview-title,
    .item-title,
    .hero h1,
    .welcome-banner h1,
    .admin-title,
    .drawer-brand .big{
      color:var(--text);
      letter-spacing:-.03em;
    }

    .section-kicker,
    .overview-kicker,
    .stat-label,
    .sidebar-kicker,
    .permission-kicker{
      color:#c9ab79 !important;
    }

    .menu-btn,.icon-btn,.icon-gear-btn,
    .btn,
    .nav-btn,.sub-btn,.logout-btn,.home-btn,
    .chip,
    .admin-chip,
    .filter-chip,
    .day-chip,
    .section-chip,
    .meta-chip,
    .badge,
    button{
      transition:transform .14s ease, box-shadow .14s ease, border-color .14s ease, background .14s ease, color .14s ease;
    }
    .menu-btn,.icon-btn,.icon-gear-btn{
      background:linear-gradient(180deg, rgba(255,255,255,.04), rgba(255,255,255,.02)) !important;
      border:1px solid var(--line) !important;
      box-shadow:0 10px 20px rgba(0,0,0,.16);
    }

    .btn,
    .nav-btn,.sub-btn,.logout-btn,.home-btn,
    .chip,
    .admin-chip,
    .filter-chip,
    .day-chip,
    .section-chip,
    .meta-chip{
      background:linear-gradient(180deg, rgba(255,255,255,.045), rgba(255,255,255,.02)) !important;
      border:1px solid var(--line) !important;
      color:var(--text) !important;
      box-shadow:0 6px 16px rgba(0,0,0,.12);
    }
    .btn:hover,
    .nav-btn:hover,.sub-btn:hover,.logout-btn:hover,.home-btn:hover,
    .chip:hover,
    .admin-chip:hover,
    .filter-chip:hover,
    .day-chip:hover,
    .section-chip:hover,
    .meta-chip:hover,
    .menu-btn:hover,.icon-btn:hover,.icon-gear-btn:hover{
      border-color:rgba(215,168,90,.32) !important;
      background:linear-gradient(180deg, rgba(215,168,90,.16), rgba(215,168,90,.08)) !important;
      color:#ffe7be !important;
      box-shadow:0 0 0 1px rgba(215,168,90,.08), 0 14px 24px rgba(0,0,0,.18);
    }
    .btn:active,
    .nav-btn:active,.sub-btn:active,.logout-btn:active,.home-btn:active,
    .chip:active,
    .admin-chip:active,
    .filter-chip:active,
    .day-chip:active,
    .section-chip:active,
    .menu-btn:active,.icon-btn:active,.icon-gear-btn:active{
      transform:scale(.98);
    }
    .btn.accent,.badge.accent,.chip.active,.admin-chip.active,.filter-chip.active,.day-chip.active,.section-chip.active,
    .nav-btn.active,.sub-btn.active,.home-btn.active,
    .btn.primary,.btn.good-accent{
      background:linear-gradient(180deg, var(--accent-2), var(--accent)) !important;
      color:#251707 !important;
      border-color:rgba(255,219,164,.32) !important;
      box-shadow:0 10px 22px rgba(215,168,90,.24);
    }
    .btn.danger{background:linear-gradient(180deg, rgba(238,141,141,.16), rgba(238,141,141,.08)) !important;border-color:rgba(238,141,141,.24) !important}
    .btn.good,.badge.good{background:linear-gradient(180deg, rgba(129,210,161,.16), rgba(129,210,161,.08)) !important;border-color:rgba(129,210,161,.22) !important;color:#e2ffec !important}
    .badge.warn{background:linear-gradient(180deg, rgba(255,122,0,.16), rgba(255,122,0,.08)) !important;border-color:rgba(255,122,0,.24) !important}

    input,select,textarea,
    .field input,.field select,.field textarea,
    .search-input,
    .admin-input,
    .admin-select,
    .sheet-card input,.sheet-card select,.sheet-card textarea,
    .modal-card input,.modal-card select,.modal-card textarea{
      width:100%;
      border-radius:14px !important;
      border:1px solid var(--line) !important;
      background:linear-gradient(180deg, rgba(255,255,255,.04), rgba(255,255,255,.025)) !important;
      color:var(--text) !important;
      box-shadow:inset 0 1px 0 rgba(255,255,255,.03);
    }
    input:focus,select:focus,textarea:focus,
    .field input:focus,.field select:focus,.field textarea:focus,
    .sheet-card input:focus,.sheet-card select:focus,.sheet-card textarea:focus,
    .modal-card input:focus,.modal-card select:focus,.modal-card textarea:focus{
      outline:none;
      border-color:rgba(215,168,90,.46) !important;
      box-shadow:0 0 0 4px rgba(215,168,90,.10), inset 0 1px 0 rgba(255,255,255,.03);
    }
    input::placeholder,textarea::placeholder{color:#8ea1b8}

    .badge,.meta-chip{
      background:rgba(255,255,255,.03) !important;
      border-color:var(--line) !important;
      color:var(--muted) !important;
    }

    .nav-btn,.sub-btn,.logout-btn,.home-btn{
      min-height:44px !important;
      border-radius:15px !important;
    }
    .nav-label{font-weight:800;letter-spacing:-.01em}

    .list-item,
    .mini-row,
    .perm-item,
    .task-row,
    .admin-list-row,
    .checklist-row,
    .subtask-row{
      border-color:var(--line) !important;
      background:rgba(255,255,255,.024) !important;
      border-radius:15px !important;
    }

    .sheet,
    .modal,
    .modal-backdrop{
      background:rgba(2,4,8,.62) !important;
      backdrop-filter:blur(8px);
    }

    .progress,
    .progress-track,
    .bar,
    .mini-progress{
      background:rgba(255,255,255,.06) !important;
      border-radius:999px;
      overflow:hidden;
    }
    .progress > span,
    .progress-fill,
    .bar > span,
    .mini-progress > span{
      background:linear-gradient(90deg, var(--accent), var(--accent-2)) !important;
      box-shadow:0 0 18px rgba(215,168,90,.20);
    }

    input[type='checkbox'], input[type='radio']{accent-color:var(--accent)}

    .item-sub,.stat-sub,.overview-sub,.perm-label,.meta-chip,.badge,.item-meta,.welcome-banner p,p,.muted,.help,.permission-help{color:var(--muted)}

    .admin-header,
    .panel-head,
    .section-head,
    .overview-top,
    .item-top{
      gap:12px;
    }

    .topbar,.panel,.hero,.overview-card,.stat-card,.sheet-card,.modal-card,.list-item{position:relative;overflow:hidden}
    .topbar::after,.panel::after,.hero::after,.overview-card::after,.stat-card::after,.sheet-card::after,.modal-card::after,.list-item::after{
      content:"";
      position:absolute;
      inset:0;
      pointer-events:none;
      border-radius:inherit;
      box-shadow:inset 0 1px 0 rgba(255,255,255,.04);
    }

    @media (max-width:640px){
      .topbar{padding-left:14px;padding-right:14px}
      .layout{padding-left:12px;padding-right:12px}
      .panel,.hero,.overview-card,.stat-card,.sheet-card,.modal-card,.list-item{border-radius:18px !important}
      .btn,.nav-btn,.sub-btn,.logout-btn,.home-btn{min-height:40px !important}
    }


    .btn.primary,.btn.good,.btn.accent,.primary-btn,.save-btn,.checklists-filter-btn.active,.day-chip.active,.chip.active,.check-btn.checked,.task-check.checked,.subtask-check.checked,.progress-fill,.progress-bar-fill{
      background:linear-gradient(180deg,#ff8f1f,#ff7a00) !important;
      border-color:rgba(255,122,0,.28) !important;
      color:#1a0f00 !important;
      box-shadow:0 10px 24px rgba(255,122,0,.18);
    }
    .btn.accent,.icon-gear-btn:hover,.sidebar-link.active,.nav-item.active,.tab-btn.active,.seg-btn.active{
      background:rgba(255,122,0,.12) !important;
      border-color:rgba(255,122,0,.24) !important;
      color:#ffd9bf !important;
    }
    input[type='checkbox'], .permission-grid input[type='checkbox']{accent-color:#ff7a00 !important;}

  
    /* === TRUE ORANGE GLOBAL OVERRIDE === */
    :root{
      --accent:#ff7a00 !important;
      --accent-strong:#ff8f1f !important;
      --accent-soft:rgba(255,122,0,.16) !important;
      --accent-glow:rgba(255,122,0,.34) !important;
      --warn:#ff7a00 !important;
    }
    .topbar,
    .drawer,
    .sheet-card,
    .modal-card,
    .card,
    .section-card,
    .stat-card,
    .panel,
    .overview-card,
    .dashboard-card{
      box-shadow:0 18px 40px rgba(0,0,0,.28);
    }
    .btn-primary,
    .btn.primary,
    button.primary,
    .cta-btn,
    .save-btn.primary,
    .quick-action.primary{
      background:linear-gradient(180deg,#ff9a33,#ff7a00) !important;
      border-color:rgba(255,122,0,.34) !important;
      color:#1a0f00 !important;
      box-shadow:0 10px 24px rgba(255,122,0,.22) !important;
    }
    .btn.accent,
    .icon-gear-btn:hover,
    .badge.accent,
    .bot-msg.user,
    .bot-action,
    .nav-btn.active,
    .sub-btn.active,
    .task-switcher-btn.active,
    .layout-orientation-hint,
    .fridge-editor-mobile-tip,
    .layout-slot-thumb,
    .drawer-link.active,
    .drawer-link:hover,
    .page-tab.active,
    .filter-chip.active,
    .selector-chip.active{
      background:rgba(255,122,0,.12) !important;
      border-color:rgba(255,122,0,.28) !important;
      color:#ffd9bf !important;
    }
    .badge.warn,
    .status-warn,
    .summary-badge.warn,
    .metric-badge.warn{
      background:rgba(255,122,0,.12) !important;
      border-color:rgba(255,122,0,.28) !important;
      color:#ffd9bf !important;
    }
    .badge.good{
      background:rgba(111,202,147,.12) !important;
      border-color:rgba(111,202,147,.24) !important;
    }
    .active-badge,
    .is-active,
    .current-badge,
    [data-state="active"] .badge,
    .layout-item.active .badge,
    .layout-active-badge{
      background:rgba(255,122,0,.12) !important;
      border-color:rgba(255,122,0,.28) !important;
      color:#ffd9bf !important;
    }
    .money-card .amount,
    .tips-card .amount,
    .tip-amount,
    .amount-badge,
    .amount-pill,
    .metric-value.accent,
    .value-accent{
      color:#ff9a33 !important;
    }
    .progress-fill,
    .progress-bar-fill,
    .progress > span,
    .mini-progress-fill,
    .checklists-progress-fill{
      background:linear-gradient(90deg,#ff9a33,#ff7a00) !important;
    }
    .chip.active,
    .seg-btn.active,
    .toggle-btn.active,
    .day-chip.active,
    .section-chip.active{
      background:linear-gradient(180deg,#ff9a33,#ff7a00) !important;
      border-color:rgba(255,122,0,.34) !important;
      color:#1a0f00 !important;
      box-shadow:0 8px 18px rgba(255,122,0,.18) !important;
    }
    input:focus,
    select:focus,
    textarea:focus,
    .field input:focus,
    .field select:focus,
    .field textarea:focus{
      border-color:rgba(255,122,0,.34) !important;
      box-shadow:0 0 0 4px rgba(255,122,0,.12) !important;
    }
    .checkbox.checked,
    .check.checked,
    .task-check.checked,
    .subtask-check.checked{
      background:linear-gradient(180deg,#ff9a33,#ff7a00) !important;
      border-color:rgba(255,122,0,.34) !important;
      color:#1a0f00 !important;
      box-shadow:0 6px 14px rgba(255,122,0,.18) !important;
    }
    .sidebar .badge,
    .drawer .badge,
    .sidebar .pill,
    .drawer .pill{
      background:rgba(255,122,0,.12) !important;
      border-color:rgba(255,122,0,.26) !important;
      color:#ffd9bf !important;
    }
    .summary-card .value,
    .stats-card .value,
    .highlight-number,
    .accent-text,
    .text-accent{
      color:#ff9a33 !important;
    }
    .soft-accent,
    .accent-panel,
    .highlight-panel{
      background:rgba(255,122,0,.10) !important;
      border-color:rgba(255,122,0,.24) !important;
    }
    .nav-btn.active svg,
    .sub-btn.active svg,
    .drawer-link.active svg,
    .icon-btn.active svg{
      color:#ff9a33 !important;
      stroke:#ff9a33 !important;
    }



    /* Final typography cleanup: remove leftover gold/beige text so orange stays for actions only */
    .section-title,
    .nav-label,
    .sidebar-title,
    .card-title,
    .panel-title,
    .module-title,
    .dashboard-title,
    .overview-title,
    .topbar .eyebrow,
    .topbar-text .eyebrow,
    .drawer-section-title,
    .drawer-title,
    .page-title,
    .metric-title,
    .summary-title,
    .group-title,
    .list-title,
    .tile-title,
    .stat-title,
    .title-accent,
    .accent-heading,
    h1,h2,h3,h4,h5,h6,
    strong.title,
    .page-tab,
    .drawer-link,
    .sidebar-link,
    .nav-btn,
    .sub-btn{
      color:var(--text) !important;
    }
    .eyebrow,
    .muted,
    .subtle,
    .helper,
    .hint,
    .meta,
    .small-text,
    .subtitle,
    .card-subtitle,
    .section-subtitle,
    .metric-label,
    .summary-label,
    .drawer-subtitle,
    .soft-text{
      color:var(--muted) !important;
    }
    .drawer-link.active,
    .sidebar-link.active,
    .nav-btn.active,
    .sub-btn.active,
    .page-tab.active{
      color:#ff9a33 !important;
    }
    .drawer-link.active .label,
    .sidebar-link.active .label,
    .nav-btn.active .label,
    .sub-btn.active .label,
    .page-tab.active .label,
    .page-tab.active span,
    .drawer-link.active span,
    .sidebar-link.active span{
      color:#ff9a33 !important;
    }
    .badge.warn,
    .status-warn,
    .summary-badge.warn,
    .metric-badge.warn,
    .active-badge,
    .is-active,
    .current-badge,
    [data-state="active"] .badge,
    .layout-item.active .badge,
    .layout-active-badge,
    .money-card .amount,
    .tips-card .amount,
    .tip-amount,
    .amount-badge,
    .amount-pill,
    .metric-value.accent,
    .value-accent,
    .summary-card .value,
    .stats-card .value,
    .highlight-number,
    .accent-text,
    .text-accent,
    .sidebar .badge,
    .drawer .badge,
    .sidebar .pill,
    .drawer .pill{
      color:#ff9a33 !important;
    }


    /* === FINAL ORANGE UNIFICATION PATCH === */
    :root{
      --line:rgba(255,255,255,.08) !important;
      --line-strong:rgba(255,255,255,.16) !important;
      --text:#eef4fb !important;
      --muted:#9fb0c7 !important;
      --accent:#ff7a00 !important;
      --accent-2:#ff8f1f !important;
      --accent-soft:rgba(255,122,0,.14) !important;
      --accent-glow:rgba(255,122,0,.24) !important;
      --warn:#ff9a33 !important;
    }

    body, .app{
      background:
        radial-gradient(circle at top left, rgba(255,122,0,.10), transparent 24%),
        radial-gradient(circle at top right, rgba(255,143,31,.05), transparent 18%),
        linear-gradient(180deg,#070b12 0%,#0b121c 52%,#070b12 100%) !important;
    }

    .drawer{
      background:
        radial-gradient(circle at top left, rgba(255,122,0,.09), transparent 26%),
        linear-gradient(180deg,#0a111a,#091019) !important;
    }

    .eyebrow,
    .sidebar-kicker,
    .sub-section-label,
    .section-kicker,
    .overview-kicker,
    .stat-label,
    .metric-label,
    .summary-label,
    .drawer-brand .small,
    .task-switcher-label{
      color:var(--muted) !important;
    }

    .section-title,
    .panel-title,
    .overview-title,
    .nav-label,
    .drawer-brand .big,
    .title,
    .item-title,
    .task-group-title,
    .klist-name,
    .ktask-title,
    .ksub-title,
    .mini-row strong{
      color:var(--text) !important;
    }

    .home-btn,
    .nav-btn,
    .sub-btn,
    .home-btn *,
    .nav-btn *,
    .sub-btn *,
    .overview-actions .btn,
    .item-actions .btn{
      color:var(--text) !important;
    }

    .nav-btn.active,
    .sub-btn.active,
    .task-switcher-btn.active,
    .selector-chip.active,
    .chip.active,
    .seg-btn.active,
    .toggle-btn.active,
    .day-chip.active,
    .section-chip.active{
      background:linear-gradient(180deg,#ff9a33,#ff7a00) !important;
      border-color:rgba(255,122,0,.34) !important;
      color:#1a0f00 !important;
      box-shadow:0 8px 18px rgba(255,122,0,.18) !important;
    }
    .nav-btn.active *,
    .sub-btn.active *,
    .task-switcher-btn.active *{
      color:#1a0f00 !important;
    }
    .nav-btn.active .nav-icon,
    .sub-btn.active .nav-icon{
      background:rgba(26,15,0,.12) !important;
      color:#1a0f00 !important;
    }

    .btn.accent,
    button.accent,
    .bot-action,
    .permission-chip:hover{
      background:linear-gradient(180deg,#ff9a33,#ff7a00) !important;
      border-color:rgba(255,122,0,.34) !important;
      color:#1a0f00 !important;
    }

    .badge.warn,
    .badge.accent,
    .status-warn,
    .summary-badge.warn,
    .metric-badge.warn,
    .active-badge,
    .is-active,
    .current-badge,
    [data-state="active"] .badge,
    .layout-item.active .badge,
    .layout-active-badge,
    .amount-badge,
    .amount-pill,
    .pill,
    .fridge-inline-accent{
      background:rgba(255,122,0,.12) !important;
      border-color:rgba(255,122,0,.28) !important;
      color:#ffb36b !important;
    }

    .money-card .amount,
    .tips-card .amount,
    .tip-amount,
    .metric-value.accent,
    .value-accent,
    .fooienpot-amount,
    .tip-card-amount{
      color:#ff9a33 !important;
    }

    .progress-fill,
    .progress-bar-fill,
    .progress > span,
    .mini-progress-fill,
    .checklists-progress-fill,
    .kprogress > span{
      background:linear-gradient(90deg,#ff9a33,#ff7a00) !important;
    }

    [style*="#d7a85a"],
    [style*="#f0c980"],
    [style*="#ccb288"],
    [style*="color: gold"],
    [style*="color:#d4b06a"],
    [style*="color:#c9a35d"],
    [style*="color:#e0b96a"]{
      color:var(--text) !important;
    }


.day-chip input[type="checkbox"]{
  width:16px !important;
  height:16px !important;
  transform:scale(1) !important;
  margin:0;
}
.day-chip{
  padding:4px 8px !important;
  min-height:auto !important;
  font-size:13px !important;
}


    .drawer-brand{
      background:rgba(255,255,255,.02);
      border:1px solid rgba(255,255,255,.06);
      border-radius:18px;
      padding:12px 12px 14px;
      margin-bottom:12px;
    }
    .sidebar-kicker{
      margin:10px 4px 4px;
      color:var(--muted);
      font-size:10px;
      letter-spacing:.13em;
      text-transform:uppercase;
      font-weight:900;
      opacity:.85;
    }
    .nav-btn[data-page="diensten"]{
      border-color:rgba(255,122,0,.20);
      background:rgba(255,122,0,.06);
    }
    .nav-btn,.sub-btn{
      min-height:40px;
    }
    .sub-list{
      gap:5px;
      padding:4px 0 4px 12px;
      margin-bottom:2px;
    }
    .sub-btn{
      min-height:34px;
      border-radius:12px;
      font-size:13px;
      padding:0 12px;
    }
    .nav-icon{
      font-size:14px;
    }


    .nav-icon{
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-weight:900;
      font-size:13px;
      color:#ffd9bf;
      background:rgba(255,122,0,.08);
      border:1px solid rgba(255,122,0,.12);
    }
    .nav-btn:not(.active) .nav-icon{
      color:var(--muted);
      background:rgba(255,255,255,.035);
      border-color:rgba(255,255,255,.06);
    }
    .nav-btn[data-page="diensten"] .nav-icon{
      color:#ffd9bf;
      background:rgba(255,122,0,.10);
      border-color:rgba(255,122,0,.18);
    }


    .overview-hero{
      display:flex;
      justify-content:space-between;
      align-items:flex-start;
      gap:16px;
      overflow:hidden;
    }
    .overview-hero-metric{
      min-width:92px;
      border:1px solid rgba(255,122,0,.18);
      background:rgba(255,122,0,.10);
      border-radius:18px;
      padding:12px;
      text-align:center;
      color:#ffd9bf;
      box-shadow:0 14px 28px rgba(0,0,0,.14);
    }
    .overview-hero-metric span{
      display:block;
      font-size:28px;
      font-weight:900;
      letter-spacing:-.04em;
      line-height:1;
    }
    .overview-hero-metric small{
      display:block;
      margin-top:5px;
      color:var(--muted);
      font-size:11px;
      font-weight:800;
      text-transform:uppercase;
      letter-spacing:.08em;
    }
    .overview-hub-grid{
      display:grid;
      grid-template-columns:repeat(2,minmax(0,1fr));
      gap:10px;
    }
    .overview-hub-card{
      border:1px solid var(--line);
      border-radius:18px;
      padding:14px;
      background:
        radial-gradient(circle at top right, rgba(255,122,0,.08), transparent 34%),
        linear-gradient(180deg, rgba(18,27,40,.96), rgba(12,19,30,.96));
      box-shadow:0 12px 24px rgba(0,0,0,.12);
      min-height:112px;
      display:flex;
      flex-direction:column;
      justify-content:space-between;
      gap:10px;
    }
    .overview-hub-top{
      display:flex;
      justify-content:space-between;
      gap:10px;
      align-items:flex-start;
    }
    .overview-hub-kicker{
      color:var(--muted);
      font-size:10px;
      font-weight:900;
      letter-spacing:.12em;
      text-transform:uppercase;
      margin-bottom:5px;
    }
    .overview-hub-title{
      font-size:17px;
      font-weight:900;
      letter-spacing:-.03em;
      color:var(--text);
      line-height:1.05;
    }
    .overview-hub-sub{
      margin-top:5px;
      color:var(--muted);
      font-size:12px;
      line-height:1.35;
    }
    .overview-hub-actions{
      display:flex;
      flex-wrap:wrap;
      gap:6px;
    }
    .overview-hub-actions .btn{
      min-height:30px;
      font-size:12px;
      border-radius:10px;
      padding:0 10px;
    }
    .overview-focus-panel{padding:14px}
    .compact-mini-list .mini-row{padding:9px 10px;border-radius:11px}
    .compact-mini-list .mini-row strong{font-size:13px}
    .compact-mini-list .mini-row span{font-size:11px}
    @media (max-width:700px){
      .overview-hero{align-items:stretch}
      .overview-hero-metric{min-width:80px;padding:10px}
      .overview-hero-metric span{font-size:24px}
      .overview-hub-grid{grid-template-columns:1fr}
      .overview-hub-card{min-height:auto}
    }


    .calendar-link-card{
      display:grid;
      gap:14px;
    }
    .calendar-link-status{
      display:flex;
      align-items:flex-start;
      justify-content:space-between;
      gap:12px;
      border:1px solid rgba(255,122,0,.16);
      background:
        radial-gradient(circle at top right, rgba(255,122,0,.10), transparent 36%),
        rgba(255,255,255,.025);
      border-radius:16px;
      padding:14px;
    }
    .calendar-link-kicker{
      color:var(--muted);
      font-size:10px;
      font-weight:900;
      letter-spacing:.12em;
      text-transform:uppercase;
      margin-bottom:5px;
    }
    .calendar-link-title{
      color:var(--text);
      font-size:17px;
      line-height:1.15;
      font-weight:900;
      letter-spacing:-.03em;
    }
    .calendar-link-sub{
      color:var(--muted);
      font-size:12px;
      line-height:1.4;
      margin-top:6px;
    }
    .calendar-link-actions{
      display:grid;
      grid-template-columns:1fr;
      gap:8px;
    }
    .calendar-main-action{
      width:100%;
      min-height:44px;
      font-size:14px;
    }
    .calendar-secondary-action{
      width:100%;
      min-height:40px;
      display:flex;
      align-items:center;
      justify-content:center;
      color:var(--text);
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
      <div class="sidebar-kicker">Hoofdmenu</div>
      <button class="nav-btn active" data-page="dashboard" onclick="openPage('dashboard'); closeDrawer();">
        <span class="nav-left"><span class="nav-icon">⌂</span><span class="nav-label">Dashboard</span></span>
      </button>
      <button class="nav-btn" data-page="diensten" onclick="openPage('diensten'); closeDrawer();">
        <span class="nav-left"><span class="nav-icon">◷</span><span class="nav-label">Diensten</span></span>
      </button>
      <button class="nav-btn" data-page="checklists" onclick="openPage('checklists'); closeDrawer();">
        <span class="nav-left"><span class="nav-icon">✓</span><span class="nav-label">Checklists</span></span>
      </button>

      <div class="sidebar-kicker">Werkvloer</div>
      <button class="nav-btn" id="toggle-bar" onclick="toggleGroup('bar')">
        <span class="nav-left"><span class="nav-icon">▦</span><span class="nav-label">Bar</span></span>
        <span class="nav-caret">›</span>
      </button>
      <div class="sub-list" id="group-bar">
        <button class="sub-btn" data-page="bar-overzicht" onclick="openPage('bar-overzicht'); closeDrawer();">Overzicht</button>
        <button class="sub-btn" data-page="bar-indeling" onclick="openPage('bar-indeling'); closeDrawer();">Indeling</button>
        <button class="sub-btn" data-page="bar-koelingen" onclick="openPage('bar-koelingen'); closeDrawer();">Koelingen</button>
        <button class="sub-btn" data-page="bar-bijvullen" onclick="openPage('bar-bijvullen'); closeDrawer();">Bijvuloverzicht</button>
        <button class="sub-btn" data-page="bar-oplijst" onclick="openPage('bar-oplijst'); closeDrawer();">Op / niet op voorraad</button>
      </div>

      <button class="nav-btn" data-page="keuken-recepten" onclick="openPage('keuken-recepten'); closeDrawer();">
        <span class="nav-left"><span class="nav-icon">□</span><span class="nav-label">Recepten</span></span>
      </button>

      <div class="sidebar-kicker">Algemeen</div>
      <button class="nav-btn" data-page="fooienpot" onclick="openPage('fooienpot'); closeDrawer();">
        <span class="nav-left"><span class="nav-icon">€</span><span class="nav-label">Fooienpot</span></span>
      </button>
      <button class="nav-btn" data-page="algemeen-dashboard" onclick="openPage('algemeen-dashboard'); closeDrawer();">
        <span class="nav-left"><span class="nav-icon">⋯</span><span class="nav-label">Overzicht</span></span>
      </button>

      <div class="sidebar-kicker admin-only">Beheer</div>
      <button class="nav-btn admin-only" id="toggle-beheer" onclick="toggleGroup('beheer')">
        <span class="nav-left"><span class="nav-icon">⚙</span><span class="nav-label">Beheer</span></span>
        <span class="nav-caret">›</span>
      </button>
      <div class="sub-list" id="group-beheer">
        <button class="sub-btn admin-only" data-page="gebruikers" onclick="openPage('gebruikers'); closeDrawer();">Medewerkers</button>
        <button class="sub-btn admin-only" data-page="dienstsoorten" onclick="openPage('dienstsoorten'); closeDrawer();">Dienstsoorten</button>
        <button class="sub-btn admin-only" data-page="bar-productsoorten" onclick="openPage('bar-productsoorten'); closeDrawer();">Productsoorten</button>
        <button class="sub-btn admin-only" data-page="bar-locaties" onclick="openPage('bar-locaties'); closeDrawer();">Locaties</button>
      </div>
    </nav>

    <div class="logout-wrap">
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
          <h2 class="section-title">Diensten in beeld</h2>
          <div class="section-kicker">Compact overzicht</div>
        </div>
        <div class="dashboard-compact-shell">
          <div class="dashboard-next-hero">
            <div class="dashboard-next-hero-top">
              <div>
                <div class="dashboard-mini-kicker">Eerstvolgende dienst</div>
                <div class="dashboard-next-hero-title" id="dashboardHeroNextTitle">Nog geen dienst gepland</div>
                <div class="dashboard-next-hero-sub" id="dashboardHeroNextSub">Zodra er iets gepland staat, zie je hier direct wanneer je weer aan de beurt bent.</div>
              </div>
              <span class="badge accent" id="dashboardHeroNextBadge">Planning</span>
            </div>
            <div class="dashboard-next-hero-meta">
              <span class="dashboard-next-hero-time" id="dashboardHeroNextTime">—</span>
              <span class="dashboard-next-hero-countdown" id="dashboardHeroNextCountdown">Nog niets gepland</span>
            </div>
          </div>
          <div class="dashboard-compact-grid">
            <div class="dashboard-mini-card salary-card">
              <div class="dashboard-mini-kicker">Vandaag</div>
              <div class="dashboard-mini-title" id="dashboardTodayTitle">0 diensten</div>
              <div class="dashboard-mini-sub" id="dashboardTodaySub">Je planning van vandaag.</div>
              <span class="badge" id="dashboardTodayBadge">Vandaag</span>
            </div>
            <div class="dashboard-mini-card">
              <div class="dashboard-mini-kicker">Deze week</div>
              <div class="dashboard-mini-title" id="dashboardWeekTitle">0 diensten</div>
              <div class="dashboard-mini-sub" id="dashboardWeekSub">Compact overzicht van deze week.</div>
              <span class="badge good" id="dashboardWeekBadge">Week</span>
            </div>
            <div class="dashboard-mini-card">
              <div class="dashboard-mini-kicker">💰 Salaris</div>
              <div class="dashboard-mini-title" id="dashboardSalaryTitle">Uurloon instellen</div>
              <div class="dashboard-mini-sub" id="dashboardSalarySub">Stel je uurloon in voor een maandindicatie.</div>
              <span class="badge accent" id="dashboardSalaryBadge">Instellen</span>
              <div style="margin-top:8px">
                <button class="dienst-inline-btn accent" onclick="openHourlyRateModal()">Uurloon</button>
              </div>
            </div>
            <div class="dashboard-mini-card">
              <div class="dashboard-mini-kicker">Uren</div>
              <div class="dashboard-mini-title" id="dashboardHoursTitle">0,0 uur</div>
              <div class="dashboard-mini-sub" id="dashboardHoursSub">Deze week op basis van je planning.</div>
              <span class="badge good" id="dashboardHoursBadge">Deze maand 0,0u</span>
            </div>
          </div>
          <div class="dashboard-chip-row" id="dashboardActionChips"></div>
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

    <section class="page" id="page-checklists">
      <div class="hero">
        <h1>☑ Checklists</h1>
        <p>Één rustige checklistpagina voor de werkvloer. Kies een dag, filter op wat nog open staat en vink direct af.</p>
      </div>
      <div class="checklists-shell">
        <div class="checklists-top">
          <div class="checklists-filter-row">
            <button class="check-filter active" id="checkFilter-all" onclick="setChecklistFilter('all')">Alle</button>
            <button class="check-filter" id="checkFilter-todo" onclick="setChecklistFilter('todo')">Te doen</button>
            <button class="check-filter" id="checkFilter-done" onclick="setChecklistFilter('done')">Klaar</button>
            <button type="button" class="check-settings-btn checklist-manage-action" onclick="openChecklistManagerPage(); return false;" title="Checklist instellingen">⚙️</button>
          </div>
          <div class="check-datebar">
            <button class="check-date-btn" onclick="shiftChecklistDate(-1)" aria-label="Vorige dag">‹</button>
            <div class="check-date-main">
              <div class="check-date-label" id="checklistDateLabel">Vandaag</div>
              <div class="check-date-sub" id="checklistDateSub">Kies welke dag je wilt zien</div>
            </div>
            <button class="check-today-btn" onclick="goChecklistToday()">Vandaag</button>
            <button class="check-date-btn" onclick="shiftChecklistDate(1)" aria-label="Volgende dag">›</button>
          </div>
          <div class="check-progress-card" id="checklistProgressCard"></div>
        </div>
        <div class="checklists-sections" id="checklistSections"></div>
      </div>
    </section>

    <section class="page checklist-manage-page" id="page-checklists-beheer">
      <div class="hero">
        <h1>⚙️ Checklist beheer</h1>
        <p>Beheer hier centraal je checklists, dagen, taken en subtaken zonder popup-gedoe.</p>
      </div>
      <div class="check-admin-page" id="checklistManagerPage"></div>
    </section>

    <section class="page" id="page-algemeen-dashboard">
      <div class="hero overview-hero">
        <div>
          <div class="overview-kicker">Algemeen</div>
          <h1>Overzicht</h1>
          <p>Je persoonlijke planning, fooienpot en snelle acties compact bij elkaar.</p>
        </div>
        <div class="overview-hero-metric">
          <span id="generalHeroMetric">0</span>
          <small>deze week</small>
        </div>
      </div>
      <div class="stack">
        <div class="overview-hub-grid" id="generalOverviewGrid"></div>
        <div class="panel overview-focus-panel">
          <div class="panel-head">
            <div>
              <h3 class="panel-title">Vandaag in beeld</h3>
              <div class="section-kicker">Alleen de belangrijkste punten</div>
            </div>
            <span class="badge" id="generalTodayBadge">Rustig</span>
          </div>
          <div class="mini-list compact-mini-list" id="generalTodayList"></div>
        </div>
      </div>
    </section>
    <section class="page" id="page-diensten">
      <div class="hero">
        <h1>👥 Diensten</h1>
        <p>Een rustige dienstenpagina met snelle inzichten, handige acties en een overzicht per dag.</p>
      </div>
      <div class="stack">
        <div class="diensten-top-grid">
          <div class="panel diensten-focus-panel">
            <div class="panel-head">
              <h3 class="panel-title">Snel in beeld</h3>
              <span class="badge accent" id="dienstenWeekBadge">0 diensten</span>
            </div>
            <div class="mini-list" id="dienstenWeekList"></div>
          </div>
          <div class="panel diensten-quick-panel">
            <div class="panel-head">
              <h3 class="panel-title">Snelle acties</h3>
              <span class="badge" id="dienstenQuickBadge">Planning</span>
            </div>
            <div class="diensten-quick-actions" id="dienstenQuickActions"></div>
            <div class="diensten-quick-note" id="dienstenQuickNote">Gebruik deze knoppen om snel naar de juiste weergave te springen.</div>
          </div>
        </div>
        <div class="panel" id="dienstenListPanel">
          <div class="panel-head diensten-list-head">
            <div>
              <h3 class="panel-title">Geplande diensten</h3>
              <div class="section-kicker" id="dienstenListIntro">Rustig overzicht per dag, zonder lange onoverzichtelijke lijst.</div>
            </div>
            <div class="actions">
              <button class="btn" id="dienstenFilterAllBtn" onclick="setDienstenView('all')">Alles</button>
              <button class="btn" id="dienstenFilterWeekBtn" onclick="setDienstenView('week')">Alleen deze week</button>
              
              <button class="btn accent" id="newDienstBtn" onclick="openDienstModal()">Nieuwe dienst</button>
            </div>
          </div>
          <div class="task-switcher diensten-day-switcher">
            <div class="task-switcher-label">Filter op dag</div>
            <div class="task-switcher-row" id="dienstenDayFilterRow"></div>
          </div>
          <div class="diensten-groups" id="dienstenList"></div>
        </div>
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
      <div class="hero"><div class="hero-tools"><button class="icon-gear-btn admin-only-action" onclick="openUserModal()" title="Medewerker toevoegen">⚙️</button></div><h1>👥 Medewerkers</h1><p>Alleen admin kan Casa Cara medewerkers en codes beheren.</p></div>
      <div class="panel"><div class="panel-head"><h3 class="panel-title">Medewerkers</h3></div><div class="list" id="usersList"></div></div>
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
        <div class="hero-tools"><button class="icon-gear-btn admin-only-action" onclick="openKitchenListModal()" title="Takenlijst toevoegen">⚙️</button></div>
        <h1>☑ Keuken · Takenlijsten</h1>
        <p>Kies een lijst om hem rustig te openen. Zo blijft dit scherm schoon en overzichtelijk.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Takenlijsten</h3>
        </div>
        <div id="kitchenDaySwitcher"></div>
        <div class="list" id="kitchenLists"></div>
      </div>
    </section>

    <section class="page" id="page-keuken-takenlijst-detail">
      <div class="hero">
        <div class="hero-tools"><button class="icon-gear-btn admin-only-action" onclick="openKitchenManagePage(window.currentKitchenListId)" title="Takenlijst beheren">⚙️</button></div>
        <h1 id="kitchenDetailTitle">☑ Takenlijst</h1>
        <p>Werk deze lijst stap voor stap af. De lijst blijft bestaan, maar de vinkjes resetten per nieuwe dag.</p>
      </div>
      <div class="panel">
        <div id="kitchenDetailSummary"></div>
        <div class="panel-head">
          <h3 class="panel-title">Taken</h3>
          <div class="actions">
            <button class="btn" onclick="openPage('keuken-takenlijsten')">Terug naar lijsten</button>
          </div>
        </div>
        <div class="list" id="kitchenDetailList"></div>
      </div>
    </section>

    <section class="page admin-only-page" id="page-keuken-takenlijst-beheer">
      <div class="hero">
        <div class="hero-tools"><button class="icon-gear-btn admin-only-action" onclick="openKitchenTaskModal(window.currentKitchenListId)" title="Taak toevoegen">⚙️</button></div>
        <h1 id="kitchenManageTitle">⚙️ Takenlijst beheren</h1>
        <p>Pas hier alleen de inhoud van deze takenlijst aan. De checklist zelf blijft rustig voor gebruik op de werkvloer.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Beheer</h3>
          <div class="actions">
            <button class="btn" onclick="openPage('keuken-takenlijst-detail')">Terug naar checklist</button>
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
      <div class="hero overview-hero">
        <div>
          <div class="overview-kicker">Bar</div>
          <h1>Overzicht</h1>
          <p>Voorraad, bijvullen en bar-indeling in één rustig controlepaneel.</p>
        </div>
        <div class="overview-hero-metric">
          <span id="barHeroMetric">0</span>
          <small>acties</small>
        </div>
      </div>
      <div class="stack">
        <div class="overview-hub-grid" id="barOverviewGrid"></div>
        <div class="panel overview-focus-panel">
          <div class="panel-head">
            <div>
              <h3 class="panel-title">Actuele focus</h3>
              <div class="section-kicker">Wat nu aandacht nodig heeft</div>
            </div>
            <span class="badge warn" id="barFocusBadge">0 acties</span>
          </div>
          <div class="mini-list compact-mini-list" id="barFocusList"></div>
        </div>
      </div>
    </section>

    <section class="page" id="page-bar-indeling">
      <div class="hero">
        <div class="hero-tools"><button class="icon-gear-btn layout-manage-action" onclick="openBarLayoutModal()" title="Nieuwe indeling">⚙️</button></div>
        <h1>🧊 Bar · Indeling</h1>
        <p>Werk hier per event met duidelijke presets. Kies een indeling, bekijk hem op de vloer en open de editor alleen als je echt iets wilt aanpassen.</p>
      </div>
      <div class="stack">
        <div class="panel">
          <div class="panel-head">
            <div>
              <h3 class="panel-title">Indelingen</h3>
              <div class="section-kicker">Overzichtelijk overzicht voor presets, actieve indeling en snelle acties</div>
            </div>

          </div>
          <div class="overview-note" id="barLayoutInfo">Kies hieronder een indeling. Daarna kun je hem bekijken op een aparte pagina of openen in de editor.</div>
          <div class="list" id="barLayoutsList"></div>
        </div>
        <div class="panel">
          <div class="panel-head">
            <div>
              <h3 class="panel-title">Info</h3>
              <div class="section-kicker">Snelle samenvatting van wat je hier kunt doen</div>
            </div>
            <button class="btn" onclick="scrollToBarLayouts()">Bekijk alle indelingen</button>
          </div>
          <div class="mini-list">
            <div class="mini-row">
              <div>
                <strong id="barLayoutSelectedBadge">Geen indeling gekozen</strong>
                <span>Geselecteerde indeling voor kijken of bewerken</span>
              </div>
              <span class="badge accent" id="barLayoutInfoCount">0 presets</span>
            </div>
            <div class="mini-row">
              <div>
                <strong>Kijkmodus</strong>
                <span>Gebruik Bekijken tijdens het ombouwen op de vloer</span>
              </div>
              <button class="btn" onclick="openBarLayoutView()">Bekijken</button>
            </div>
            <div class="mini-row layout-manage-action">
              <div>
                <strong>Bewerkmodus</strong>
                <span>Pas units, koelkastjes, planken en producten aan in de editor</span>
              </div>
              <button class="btn accent" id="barLayoutOpenEditorBtn" onclick="openBarLayoutEditor()">Bewerken</button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="page fridge-editor-page" id="page-bar-indeling-view">
      <div class="fridge-editor-shell readonly-mode-shell">
        <div class="fridge-editor-topbar">
          <div class="fridge-editor-headcopy">
            <div class="fridge-editor-kicker">Bar · Indeling · Kijkmodus</div>
            <h1 class="fridge-editor-title" id="barLayoutViewTitle">Indeling bekijken</h1>
            <div class="fridge-editor-sub">Gebruik deze pagina op de vloer om snel te zien hoe een unit opgebouwd moet worden. Geen knoppen om per ongeluk iets te wijzigen.</div>
          </div>
          <div class="fridge-editor-actions">
            <button class="fridge-editor-btn" onclick="openPage('bar-indeling')">Terug</button>
            <button class="fridge-editor-btn primary layout-manage-action" onclick="openBarLayoutEditor()">Bewerken</button>
          </div>
        </div>
        <div class="fridge-editor-body single-canvas">
          <div class="fridge-editor-canvas">
            <div class="fridge-rotate-hint">Voor het beste overzicht gebruik je deze kijkmodus op telefoon in liggende stand.</div>
            <div class="fridge-editor-toolbar">
              <div class="fridge-editor-toolbar-left">
                <select id="barLayoutReadonlyUnitSelect" class="fridge-editor-select" onchange="changeBarLayoutReadonlyUnit(this.value)"></select>
                <span class="badge accent" id="barLayoutReadonlyBadge">3 koelkastjes · kijkmodus</span>
              </div>
              <div class="actions">
                <button class="btn" onclick="openPage('bar-indeling')">Overzicht</button>
                <button class="btn accent layout-manage-action" onclick="openBarLayoutEditor()">Open editor</button>
              </div>
            </div>
            <div class="fridge-editor-stage layout-readonly-stage" id="barLayoutReadonlyStage"></div>
          </div>
        </div>
      </div>
    </section>

    <section class="page fridge-editor-page" id="page-bar-indeling-editor">
      <div class="fridge-editor-shell">
        <div class="fridge-editor-topbar">
          <div class="fridge-editor-headcopy">
            <div class="fridge-editor-kicker">Bar · Indeling · Full editor</div>
            <h1 class="fridge-editor-title" id="fridgeEditorTitle">Indeling editor</h1>
            <div class="fridge-editor-sub">Werk per unit met 3 brede koelkastjes naast elkaar. Klik op een plank en stel rechts het product, de facings en het beeld van die hele rij in.</div>
          </div>
          <div class="fridge-editor-actions">
            <button class="fridge-editor-btn" onclick="openPage('bar-indeling')">Terug</button>
            <button class="fridge-editor-btn primary layout-manage-action" onclick="saveCurrentBarLayoutStructure()">Opslaan</button>
          </div>
        </div>
        <div class="fridge-editor-body">
          <div class="fridge-editor-canvas">
            <div class="fridge-editor-mobile-tip">Op telefoon scroll je nu alleen verticaal door de 3 koelkastjes. Tik op een plank om direct de mobiele editor met product, facings en plankinstellingen te openen.</div>
            <div class="fridge-rotate-hint">Voor het beste overzicht gebruik je deze editor op telefoon in liggende stand.</div>
            <div class="fridge-editor-toolbar">
              <div class="fridge-editor-toolbar-left">
                <select id="fridgeEditorUnitSelect" class="fridge-editor-select" onchange="changeBarLayoutEditorUnit(this.value)"></select>
                <span class="badge accent" id="fridgeEditorActiveBadge">3 koelkastjes · 9 facings per plank</span>
              </div>
              <div class="actions">
                <button class="btn" onclick="openPage('bar-indeling')">Overzicht indelingen</button>
                <button class="btn danger layout-manage-action" onclick="requestRemoveBarLayoutUnit()">Unit verwijderen</button>
              </div>
            </div>
            <div class="fridge-editor-stage" id="barLayoutFridgeStage"></div>
          </div>
          <aside class="fridge-editor-panel" id="barLayoutShelfPanel"></aside>
        </div>
        <div class="mobile-sheet-backdrop" id="barLayoutShelfMobileBackdrop" onclick="closeBarLayoutMobileSheet()"></div>
        <div class="mobile-sheet" id="barLayoutShelfMobile">
          <div class="mobile-sheet-card">
            <div class="mobile-sheet-grab"></div>
            <div class="mobile-sheet-head">
              <div>
                <div class="mobile-sheet-kicker">Indeling editor</div>
                <div class="mobile-sheet-title" id="barLayoutShelfMobileTitle">Plank aanpassen</div>
                <div class="mobile-sheet-sub" id="barLayoutShelfMobileSub">Tik op een plank om hem op telefoon te bewerken.</div>
              </div>
              <button class="mobile-sheet-close" type="button" onclick="closeBarLayoutMobileSheet()">✕</button>
            </div>
            <div id="barLayoutShelfMobileBody"></div>
            <div class="mobile-sheet-actions">
              <button class="fridge-editor-btn" type="button" onclick="closeBarLayoutMobileSheet()">Sluiten</button>
              <button class="fridge-editor-btn primary layout-manage-action" id="barLayoutMobileSaveBtn" type="button" onclick="saveCurrentBarLayoutMobileSelection()">Plank opslaan</button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="page" id="page-bar-takenlijsten">
      <div class="hero">
        <div class="hero-tools"><button class="icon-gear-btn admin-only-action" onclick="openBarListModal()" title="Takenlijst toevoegen">⚙️</button></div>
        <h1>☑ Bar · Takenlijsten</h1>
        <p>Kies een lijst voor je barshift. Compact, snel af te vinken en fijn op telefoon.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Takenlijsten</h3>
        </div>
        <div id="barDaySwitcher"></div>
        <div class="list" id="barTaskLists"></div>
      </div>
    </section>

    <section class="page" id="page-bar-takenlijst-detail">
      <div class="hero">
        <div class="hero-tools"><button class="icon-gear-btn admin-only-action" onclick="openBarManagePage(window.currentBarListId)" title="Bar takenlijst beheren">⚙️</button></div>
        <h1 id="barDetailTitle">☑ Bar checklist</h1>
        <p>Werk deze barlijst stap voor stap af. De lijst blijft staan, de vinkjes resetten per nieuwe dag.</p>
      </div>
      <div class="panel">
        <div id="barDetailSummary"></div>
        <div class="panel-head">
          <h3 class="panel-title">Taken</h3>
          <div class="actions">
            <button class="btn" onclick="openPage('bar-takenlijsten')">Terug naar lijsten</button>
          </div>
        </div>
        <div class="list" id="barDetailList"></div>
      </div>
    </section>

    <section class="page admin-only-page" id="page-bar-takenlijst-beheer">
      <div class="hero">
        <div class="hero-tools"><button class="icon-gear-btn admin-only-action" onclick="openBarTaskModal(window.currentBarListId)" title="Taak toevoegen">⚙️</button></div>
        <h1 id="barManageTitle">⚙️ Bar takenlijst beheren</h1>
        <p>Pas hier alleen de inhoud aan. De checklist op de werkvloer blijft compact en rustig.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Beheer</h3>
          <div class="actions">
            <button class="btn" onclick="openPage('bar-takenlijst-detail')">Terug naar checklist</button>
          </div>
        </div>
        <div class="list" id="barManageList"></div>
      </div>
    </section>

    <section class="page" id="page-bar-koelingen">
      <div class="hero">
        <div class="hero-tools"><button class="icon-gear-btn admin-only-action" onclick="openKoelingModal()" title="Koeling toevoegen">⚙️</button></div>
        <h1>❄️ Bar · Koelingen</h1>
        <p>Los overzicht per koeling, met aantallen, status en beheerknoppen.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Koelingen</h3>
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
        <div class="hero-tools"><button class="icon-gear-btn admin-only-action" onclick="openTypeModal()" title="Productsoort toevoegen">⚙️</button></div>
        <h1>🏷️ Bar · Productsoorten</h1>
        <p>Je productsoorten in een vaste volgorde, met de gekoppelde locatie erbij.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Productsoorten</h3>
        </div>
        <div class="list" id="typesList"></div>
      </div>
    </section>

    <section class="page admin-only-page" id="page-bar-locaties">
      <div class="hero">
        <div class="hero-tools"><button class="icon-gear-btn admin-only-action" onclick="openLocationModal()" title="Locatie toevoegen">⚙️</button></div>
        <h1>📍 Bar · Locaties</h1>
        <p>Alle locaties overzichtelijk onder elkaar, nu ook direct bewerkbaar.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Locaties</h3>
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
<button class="icon-gear-btn admin-only-action" onclick="openProductModal(window.currentKoelingId)" title="Product toevoegen">⚙️</button>
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
  let appData = { bar: { koelingen: [], fill_items: [] }, bar_tasks: { lists: [] }, bar_layouts: { items: [], active_id: '' }, general: { fooienpot: 0, diensten: [] }, kitchen: { lists: [] }, recipes: { items: [] }, types: [], locations: [] };
  let currentPage = 'dashboard';
  let currentKoelingId = null;
  let currentKitchenListId = null;
  let currentBarListId = null;
  let currentKitchenTaskDay = 'altijd';
  let currentBarTaskDay = 'altijd';
  let currentBarLayoutId = null;
  let currentBarLayoutReadonlyUnitIndex = 0;
  let currentChecklistFilter = 'all';
  let currentChecklistDateISO = null;
  let currentDienstView = 'all';
  let currentDienstDayFilter = 'all';
  let currentChecklistAdminEditor = { mode:'overview', section:'', listId:'', taskId:'', subtaskId:'' };
  const groupState = { algemeen:false, keuken:false, bar:false };
  window.currentKoelingId = null;
  window.currentKitchenListId = null;
  window.currentBarListId = null;
  currentKitchenTaskDay = getAmsterdamDayLabel();
  currentBarTaskDay = getAmsterdamDayLabel();
  currentChecklistDateISO = getTodayString();
  window.currentBarLayoutId = null;
  window.currentBarLayoutReadonlyUnitIndex = 0;

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
  function toDateInputValue(value){
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    const offset = date.getTimezoneOffset();
    const local = new Date(date.getTime() - offset * 60000);
    return local.toISOString().slice(0, 10);
  }
  function getTodayString(){ return toDateInputValue(new Date()); }
  function pad2(value){ return String(value || '').padStart(2, '0'); }
  function parseDienstDate(value){
    if (!value) return null;
    const text = String(value).trim();
    if (!text) return null;
    const parts = text.split('-');
    if (parts.length !== 3) return null;
    const year = Number(parts[0]);
    const month = Number(parts[1]);
    const day = Number(parts[2]);
    if (!year || !month || !day) return null;
    const date = new Date(year, month - 1, day);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  function parseTimeValue(value){
    const text = String(value || '').trim();
    if (!text) return 9999;
    const match = text.match(/^(\d{1,2}):(\d{2})$/);
    if (!match) return 9999;
    return Number(match[1]) * 60 + Number(match[2]);
  }
  function normalizeDienstStatus(value){
    const text = String(value || '').trim().toLowerCase();
    return ['ingepland','bevestigd','gewijzigd','vervallen'].includes(text) ? text : 'ingepland';
  }
  function dienstStatusLabel(value){
    const map = { ingepland:'Ingepland', bevestigd:'Bevestigd', gewijzigd:'Gewijzigd', vervallen:'Vervallen' };
    return map[normalizeDienstStatus(value)] || 'Ingepland';
  }
  function dienstStatusBadgeClass(value){
    const map = { ingepland:'', bevestigd:'good', gewijzigd:'warn', vervallen:'danger' };
    return map[normalizeDienstStatus(value)] || '';
  }
  function getDienstStart(item){
    return String(item?.start || item?.starttijd || '').trim();
  }
  function getDienstEnd(item){
    return String(item?.einde || item?.eindtijd || '').trim();
  }
  function normalizeDienstTimeValue(value){
    const text = String(value || '').trim();
    const match = text.match(/^(\d{1,2}):(\d{2})$/);
    if (!match) return '';
    const hour = Number(match[1]);
    const minute = Number(match[2]);
    if (Number.isNaN(hour) || Number.isNaN(minute) || hour < 0 || hour > 23 || minute < 0 || minute > 59) return '';
    return `${String(hour).padStart(2,'0')}:${String(minute).padStart(2,'0')}`;
  }
  function buildDienstTimeLabel(start='', end=''){
    const normalizedStart = normalizeDienstTimeValue(start);
    const normalizedEnd = normalizeDienstTimeValue(end);
    if (normalizedStart && normalizedEnd) return `${normalizedStart} - ${normalizedEnd}`;
    if (normalizedStart) return normalizedStart;
    if (normalizedEnd) return `tot ${normalizedEnd}`;
    return '';
  }
  function getDienstTimeLabel(item){
    const start = getDienstStart(item);
    const end = getDienstEnd(item);
    const direct = buildDienstTimeLabel(start, end);
    if (direct) return direct;
    const fallback = String(item?.tijd || '').trim().replace(/[–—]/g, '-');
    const matches = fallback.match(/\d{1,2}:\d{2}/g) || [];
    if (matches.length) return buildDienstTimeLabel(matches[0], matches[1] || '');
    return fallback;
  }
  function setDienstenView(view='all', options={}){
    currentDienstView = view === 'week' ? 'week' : 'all';
    if (currentDienstView === 'week' && !options.keepDayFilter && currentDienstDayFilter === 'all'){
      currentDienstDayFilter = String(new Date().getDay());
    }
    if (options.render !== false) renderDiensten();
    if (options.scroll !== false) document.getElementById('dienstenListPanel')?.scrollIntoView({behavior:'smooth', block:'start'});
  }
  function getDienstDisplayName(item){
    return item?.naam || item?.medewerker || item?.persoon || 'Dienst';
  }
  function getDienstNote(item){
    return String(item?.notitie || item?.rol || '').trim();
  }
  function getDienstLocation(item){
    return String(item?.locatie || item?.afdeling || '').trim();
  }
  function formatDienstDate(value){
    const date = parseDienstDate(value);
    if (!date) return value || 'Geen datum';
    return new Intl.DateTimeFormat('nl-NL', { weekday:'short', day:'numeric', month:'short' }).format(date);
  }
  function isoWeekKey(date){
    const current = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const dayNr = (current.getDay() + 6) % 7;
    current.setDate(current.getDate() - dayNr + 3);
    const firstThursday = new Date(current.getFullYear(), 0, 4);
    const firstDayNr = (firstThursday.getDay() + 6) % 7;
    firstThursday.setDate(firstThursday.getDate() - firstDayNr + 3);
    const week = 1 + Math.round((current - firstThursday) / 604800000);
    return `${current.getFullYear()}-W${pad2(week)}`;
  }
  function getCurrentWeekKey(){
    return isoWeekKey(new Date());
  }
  function weekLabelFromKey(key){
    const match = String(key || '').match(/^(\d{4})-W(\d{2})$/);
    if (!match) return key || 'Week';
    return `Week ${Number(match[2])} · ${match[1]}`;
  }
  function isDienstThisWeek(item){
    const date = parseDienstDate(item?.datum);
    return !!date && isoWeekKey(date) === getCurrentWeekKey();
  }
  function getDienstWeekday(item){
    const date = parseDienstDate(item?.datum);
    return date ? String(date.getDay()) : '';
  }
  function isDienstOnSelectedDay(item){
    if (currentDienstDayFilter === 'all') return true;
    return getDienstWeekday(item) === currentDienstDayFilter;
  }
  function setDienstDayFilter(value='all', options={}){
    const nextValue = String(value);
    if (options.toggle !== false && currentDienstDayFilter === nextValue && nextValue !== 'all'){
      currentDienstDayFilter = 'all';
    } else {
      currentDienstDayFilter = nextValue;
    }
    if (options.render !== false) renderDiensten();
    if (options.scroll !== false) document.getElementById('dienstenListPanel')?.scrollIntoView({behavior:'smooth', block:'start'});
  }
  function dienstDayLabel(day){
    const map = {'1':'Ma','2':'Di','3':'Woe','4':'Do','5':'Vrij','6':'Zat','0':'Zo'};
    return map[String(day)] || '?';
  }
  function sortDiensten(items){
    return safeArray(items).slice().sort((a,b) => {
      const dateA = String(a?.datum || '9999-99-99');
      const dateB = String(b?.datum || '9999-99-99');
      if (dateA !== dateB) return dateA.localeCompare(dateB);
      const startA = parseTimeValue(getDienstStart(a) || String(a?.tijd || '').split(' - ')[0]);
      const startB = parseTimeValue(getDienstStart(b) || String(b?.tijd || '').split(' - ')[0]);
      if (startA !== startB) return startA - startB;
      return getDienstDisplayName(a).localeCompare(getDienstDisplayName(b));
    });
  }
  function collectDienstStats(){
    const diensten = sortDiensten(appData.general?.diensten);
    const todayIso = getTodayString();
    const today = diensten.filter(item => String(item?.datum || '') === todayIso && normalizeDienstStatus(item?.status) !== 'vervallen');
    const thisWeek = diensten.filter(item => isDienstThisWeek(item));
    const upcoming = diensten.filter(item => String(item?.datum || '') >= todayIso && normalizeDienstStatus(item?.status) !== 'vervallen');
    const changed = diensten.filter(item => normalizeDienstStatus(item?.status) === 'gewijzigd');
    return { diensten, thisWeek, upcoming, changed, today, todayIso };
  }
  function dashboardRelativeDienstLabel(item){
    if (!item || !item.datum) return '';
    const today = parseDienstDate(getTodayString());
    const date = parseDienstDate(item.datum);
    if (!today || !date) return formatDienstDate(item.datum);
    const diff = Math.round((date - today) / 86400000);
    if (diff === 0) return 'Vandaag';
    if (diff === 1) return 'Morgen';
    if (diff > 1 && diff < 7) return `Over ${diff} dagen`;
    return formatDienstDate(item.datum);
  }

  function dashboardCountdownLabel(item){
    if (!item || !item.datum) return 'Nog niets gepland';
    const timeValue = String(item.start || '').trim();
    const targetDate = parseDienstDate(item.datum);
    if (!targetDate) return formatDienstDate(item.datum);
    let target = new Date(targetDate.getFullYear(), targetDate.getMonth(), targetDate.getDate(), 9, 0, 0, 0);
    const timeMatch = timeValue.match(/^(\d{1,2}):(\d{2})$/);
    if (timeMatch){
      target.setHours(Number(timeMatch[1] || 0), Number(timeMatch[2] || 0), 0, 0);
    }
    const now = new Date();
    const diffMs = target.getTime() - now.getTime();
    const diffMin = Math.round(diffMs / 60000);
    if (diffMin <= -180) return 'Al begonnen of voorbij';
    if (diffMin < 0) return 'Begint zo';
    if (diffMin < 60) return `Over ${diffMin} min`;
    if (diffMin < 24 * 60){
      const hours = Math.floor(diffMin / 60);
      const mins = diffMin % 60;
      return mins ? `Over ${hours}u ${mins}m` : `Over ${hours} uur`;
    }
    const days = Math.floor(diffMin / (24 * 60));
    return days <= 1 ? 'Morgen' : `Over ${days} dagen`;
  }

  function dashboardDienstRows(stats){
    const rows = [];
    if (stats.today[0]){
      rows.push({
        title: `Vandaag · ${getDienstDisplayName(stats.today[0])}`,
        sub: `${getDienstTimeLabel(stats.today[0]) || 'Tijd volgt'}${getDienstLocation(stats.today[0]) ? ' · ' + getDienstLocation(stats.today[0]) : ''}`,
        badge: dienstStatusLabel(stats.today[0].status),
        badgeClass: dienstStatusBadgeClass(stats.today[0].status)
      });
    }
    const nextUpcoming = stats.upcoming.find(item => String(item?.datum || '') >= stats.todayIso);
    if (nextUpcoming){
      rows.push({
        title: `Volgende · ${getDienstDisplayName(nextUpcoming)}`,
        sub: `${dashboardRelativeDienstLabel(nextUpcoming)}${getDienstTimeLabel(nextUpcoming) ? ' · ' + getDienstTimeLabel(nextUpcoming) : ''}`,
        badge: getDienstLocation(nextUpcoming) || 'Gepland',
        badgeClass: getDienstLocation(nextUpcoming) ? 'accent' : ''
      });
    }
    if (stats.thisWeek[0]){
      rows.push({
        title: `Deze week · ${stats.thisWeek.length} ${stats.thisWeek.length === 1 ? 'dienst' : 'diensten'}`,
        sub: stats.thisWeek.slice(0,2).map(item => `${formatDienstDate(item.datum)}${getDienstTimeLabel(item) ? ' · ' + getDienstTimeLabel(item) : ''}`).join(' • '),
        badge: stats.changed.length ? `${stats.changed.length} gewijzigd` : 'Op schema',
        badgeClass: stats.changed.length ? 'warn' : 'good'
      });
    }
    return rows;
  }
  function dashboardActionRows(stats){
    const rows = [];
    rows.push({
      title: 'Diensten openen',
      sub: 'Ga direct naar je compacte weekoverzicht.',
      badge: 'Open',
      badgeClass: 'accent'
    });
    rows.push({
      title: 'DISH import',
      sub: 'Importeer nieuwe blauwe dagen vanuit DISH.',
      badge: 'Import',
      badgeClass: 'accent'
    });
    if (pageAllowed('dienstsoorten')){
      rows.push({
        title: 'Dienstsoorten',
        sub: `${safeArray(appData.dienst_types).length} soorten beschikbaar voor snelle planning.`,
        badge: 'Beheer'
      });
    }
    if (stats.changed.length){
      rows.push({
        title: 'Gewijzigde diensten',
        sub: 'Loop even door je planning om wijzigingen te checken.',
        badge: `${stats.changed.length}`,
        badgeClass: 'warn'
      });
    }
    return rows;
  }
  function currentRole(){ return appData?.auth?.role || ''; }
  function isAdmin(){ return currentRole() === 'admin'; }
  function adminOnly(html){ return isAdmin() ? html : ''; }
  function hasPermission(key){ return isAdmin() ? true : !!(appData?.auth?.permissions || {})[key]; }
  function canManageBarLayouts(){ return hasPermission('manage_bar_layouts'); }
  function employeeForbiddenPages(){ return ['dienstsoorten','gebruikers','keuken-takenlijst-beheer','bar-takenlijst-beheer','bar-productsoorten','bar-locaties']; }
  function pageAllowed(page){
    if (isAdmin()) return true;
    const map = {
      'dashboard': true,
      'algemeen-dashboard': hasPermission('access_general'),
      'diensten': hasPermission('access_general') && hasPermission('manage_diensten'),
      'checklists': hasPermission('use_bar_tasklists') || hasPermission('use_kitchen_tasklists'),
      'checklists-beheer': (hasPermission('access_bar') && hasPermission('manage_bar_tasklists')) || (hasPermission('access_kitchen') && hasPermission('manage_kitchen_tasklists')),
      'dienstsoorten': hasPermission('manage_dienst_types'),
      'fooienpot': hasPermission('access_general') && hasPermission('manage_tips'),
      'gebruikers': hasPermission('manage_users'),
      'keuken-overzicht': hasPermission('access_kitchen'),
      'keuken-takenlijsten': hasPermission('access_kitchen') && hasPermission('use_kitchen_tasklists'),
      'keuken-takenlijst-detail': hasPermission('access_kitchen') && hasPermission('use_kitchen_tasklists'),
      'keuken-takenlijst-beheer': hasPermission('access_kitchen') && hasPermission('manage_kitchen_tasklists'),
      'keuken-recepten': hasPermission('access_kitchen') && hasPermission('view_recipes'),
      'bar-overzicht': hasPermission('access_bar'),
      'bar-koelingen': hasPermission('access_bar') && (hasPermission('adjust_stock') || hasPermission('manage_products') || hasPermission('manage_coolers')),
      'bar-takenlijsten': hasPermission('access_bar') && hasPermission('use_bar_tasklists'),
      'bar-takenlijst-detail': hasPermission('access_bar') && hasPermission('use_bar_tasklists'),
      'bar-takenlijst-beheer': hasPermission('access_bar') && hasPermission('manage_bar_tasklists'),
      'bar-indeling': hasPermission('access_bar'),
      'bar-indeling-view': hasPermission('access_bar'),
      'bar-indeling-editor': hasPermission('access_bar') && canManageBarLayouts(),
      'bar-productsoorten': hasPermission('manage_types'),
      'bar-locaties': hasPermission('manage_locations'),
      'bar-oplijst': hasPermission('access_bar') && hasPermission('view_oplijst'),
      'bar-bijvullen': hasPermission('access_bar') && hasPermission('view_bijvullen'),
      'bar-koeling-detail': hasPermission('access_bar') && (hasPermission('adjust_stock') || hasPermission('manage_products') || hasPermission('manage_coolers'))};
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
    document.querySelectorAll('.checklist-manage-action, .checklist-manage-page').forEach(el => { el.style.display = pageAllowed('checklists-beheer') ? '' : 'none'; });
    document.querySelectorAll('.layout-manage-action').forEach(el => { el.style.display = canManageBarLayouts() ? '' : 'none'; });
    document.querySelectorAll('.nav-btn[data-page], .sub-btn[data-page]').forEach(btn => {
      btn.style.display = pageAllowed(btn.dataset.page) ? '' : 'none';
    });
    const sectionVisibility = {
      algemeen: isAdmin() || hasPermission('access_general'),
      keuken: isAdmin() || hasPermission('access_kitchen'),
      bar: isAdmin() || hasPermission('access_bar')};
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
      'checklists': ['Werkvloer', 'Checklists'],
      'checklists-beheer': ['Werkvloer', 'Checklist beheer'],
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
      'bar-indeling': ['Bar', 'Indeling'],
      'bar-indeling-editor': ['Bar', 'Indeling editor'],
      'bar-productsoorten': ['Bar', 'Productsoorten'],
      'bar-locaties': ['Bar', 'Locaties'],
      'bar-oplijst': ['Bar', 'Op / niet op voorraad'],
      'bar-bijvullen': ['Bar', 'Bijvuloverzicht'],
      'bar-koeling-detail': ['Bar', 'Koeling detail']};
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
    const layoutWrap = document.querySelector('.layout');
    const topbar = document.querySelector('.topbar');
    const fullscreenEditor = page === 'bar-indeling-editor';
    if (layoutWrap) layoutWrap.classList.toggle('fullscreen-editor-mode', fullscreenEditor);
    if (topbar) topbar.classList.toggle('fullscreen-editor-mode', fullscreenEditor);
    window.scrollTo({ top: 0, behavior: 'instant' });
    if(page === 'bar-bijvullen' && !window.selectedCooler){
      openRefillSelector();
    }
    if(page === 'checklists-beheer'){
      renderChecklistManagerPage();
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
    const raw = await res.text();
    let json = null;
    try {
      json = raw ? JSON.parse(raw) : {};
    } catch (err) {
      throw new Error('De server gaf geen geldige JSON terug. Probeer de pagina te verversen.');
    }
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
    askedOnce: false};

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


  

  function hourlyRateStorageKey(){
    const userName = String(appData?.auth?.user_name || 'gebruiker').trim().toLowerCase();
    const safeName = userName.replace(/[^a-z0-9_-]+/g, '_') || 'gebruiker';
    return `hourlyRate:${safeName}`;
  }

  function getHourlyRate(){
    const personalKey = hourlyRateStorageKey();
    const raw = localStorage.getItem(personalKey) || '';
    const normalized = String(raw).replace(',', '.').trim();
    const value = Number(normalized);
    return Number.isFinite(value) && value > 0 ? value : 0;
  }

  function openHourlyRateModal(){
    const current = getHourlyRate();
    const userName = String(appData?.auth?.user_name || 'jouw account').trim() || 'jouw account';
    openModal(
      'Uurloon instellen',
      `Dit uurloon geldt alleen voor ${userName}. Andere medewerkers zien of wijzigen dit niet.`,
      `<div class="form-grid">
        <div class="field">
          <label>Uurloon in euro</label>
          <input id="hourlyRateInput" type="number" step="0.01" min="0" value="${current ? current : ''}" placeholder="Bijv. 18.50">
        </div>
        <div class="overview-note">De app rekent hiermee alleen een persoonlijke indicatie uit. Het houdt nog geen rekening met pauzes, toeslagen, belasting of correcties.</div>
        <div class="form-actions">
          <button class="btn" onclick="closeModal()">Annuleren</button>
          <button class="btn danger" onclick="clearHourlyRate()">Wissen</button>
          <button class="btn accent" onclick="saveHourlyRate()">Opslaan</button>
        </div>
      </div>`
    );
  }

  function saveHourlyRate(){
    const input = document.getElementById('hourlyRateInput');
    const value = Number(String(input?.value || '').replace(',', '.'));
    if (!Number.isFinite(value) || value <= 0){
      toast('Vul een geldig uurloon in.', 'error');
      return;
    }
    localStorage.setItem(hourlyRateStorageKey(), String(value));
    closeModal();
    renderDashboard();
    toast('Persoonlijk uurloon opgeslagen.');
  }

  function clearHourlyRate(){
    localStorage.removeItem(hourlyRateStorageKey());
    closeModal();
    renderDashboard();
    toast('Persoonlijk uurloon gewist.');
  }

  function calcDienstHours(item){
    if(!item || !item.start || !item.einde) return 0;
    const [sh, sm] = item.start.split(':').map(Number);
    const [eh, em] = item.einde.split(':').map(Number);
    let start = sh*60+sm;
    let end = eh*60+em;
    if(end < start) end += 24*60;
    return (end-start)/60;
  }

  function calcHoursStats(){
    const stats = collectDienstStats();
    const all = stats.diensten;
    const week = stats.thisWeek;
    const now = new Date();
    const month = all.filter(d=>{
      const dt = parseDienstDate(d.datum);
      return dt && dt.getMonth()===now.getMonth() && dt.getFullYear()===now.getFullYear();
    });

    const sum = arr => arr.reduce((t,i)=>t+calcDienstHours(i),0);

    return {
      weekHours: sum(week),
      monthHours: sum(month)
    };
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
    const dienstStats = collectDienstStats();

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

    const nextUpcoming = dienstStats.upcoming.find(item => String(item?.datum || '') >= dienstStats.todayIso);
    const nextTimeLabel = nextUpcoming ? getDienstTimeLabel(nextUpcoming) : '';
    const nextCountdown = nextUpcoming ? dashboardCountdownLabel(nextUpcoming) : 'Nog niets gepland';
    setText('dashboardHeroNextTitle', nextUpcoming ? getDienstDisplayName(nextUpcoming) : 'Nog geen dienst gepland');
    setText('dashboardHeroNextSub', nextUpcoming
      ? `${dashboardRelativeDienstLabel(nextUpcoming)}${getDienstLocation(nextUpcoming) ? ' · ' + getDienstLocation(nextUpcoming) : ''}${getDienstNote(nextUpcoming) ? ' · ' + getDienstNote(nextUpcoming) : ''}`
      : 'Zodra er iets gepland staat, zie je hier direct wanneer je weer aan de beurt bent.');
    setText('dashboardHeroNextBadge', nextUpcoming ? dienstStatusLabel(nextUpcoming.status) : 'Planning');
    setText('dashboardHeroNextTime', nextTimeLabel || 'Tijd volgt');
    setText('dashboardHeroNextCountdown', nextCountdown);

    setText('dashboardNextTitle', nextUpcoming ? getDienstDisplayName(nextUpcoming) : 'Nog geen dienst');
    setText('dashboardNextSub', nextUpcoming
      ? `${dashboardRelativeDienstLabel(nextUpcoming)}${nextTimeLabel ? ' · ' + nextTimeLabel : ''}${getDienstLocation(nextUpcoming) ? ' · ' + getDienstLocation(nextUpcoming) : ''}`
      : 'Zodra er iets gepland staat, zie je het hier direct.');
    setText('dashboardNextBadge', nextUpcoming ? dienstStatusLabel(nextUpcoming.status) : 'Planning');

    setText('dashboardTodayTitle', `${dienstStats.today.length} ${dienstStats.today.length === 1 ? 'dienst' : 'diensten'}`);
    setText('dashboardTodaySub', dienstStats.today.length
      ? dienstStats.today.slice(0,2).map(item => `${getDienstDisplayName(item)}${getDienstTimeLabel(item) ? ' · ' + getDienstTimeLabel(item) : ''}`).join(' • ')
      : 'Geen diensten voor vandaag ingepland.');
    setText('dashboardTodayBadge', 'Vandaag');

    setText('dashboardWeekTitle', `${dienstStats.thisWeek.length} ${dienstStats.thisWeek.length === 1 ? 'dienst' : 'diensten'}`);
    setText('dashboardWeekSub', dienstStats.thisWeek.length
      ? dienstStats.thisWeek.slice(0,2).map(item => `${formatDienstDate(item.datum)}${getDienstTimeLabel(item) ? ' · ' + getDienstTimeLabel(item) : ''}`).join(' • ')
      : 'Nog geen diensten in deze week.');
    setText('dashboardWeekBadge', dienstStats.changed.length ? `${dienstStats.changed.length} gewijzigd` : 'Op schema');
    const hours = calcHoursStats();
    const hourlyRate = getHourlyRate();
    const weekHours = Number(hours.weekHours || 0);
    const monthHours = Number(hours.monthHours || 0);
    const weekHoursLabel = `${weekHours.toFixed(1).replace('.', ',')} uur`;
    const monthHoursLabel = `${monthHours.toFixed(1).replace('.', ',')}u`;
    const monthSalary = hourlyRate ? monthHours * hourlyRate : 0;
    const monthSalaryFull = monthSalary ? `± €${monthSalary.toFixed(2).replace('.', ',')}` : 'Uurloon instellen';
    const monthSalaryShort = monthSalary ? `± €${monthSalary.toFixed(0).replace('.', ',')}` : 'Instellen';

    setText('dashboardSalaryTitle', monthSalaryFull);
    setText('dashboardSalarySub', hourlyRate
      ? `${monthHoursLabel} deze maand · €${hourlyRate.toFixed(2).replace('.', ',')} per uur.`
      : 'Stel je uurloon in voor je maandindicatie.');
    setText('dashboardSalaryBadge', monthSalaryShort);

    setText('dashboardHoursTitle', weekHoursLabel);
    setText('dashboardHoursSub', `Deze week ingepland. Maand: ${monthHoursLabel}.`);
    setText('dashboardHoursBadge', `Deze maand ${monthHoursLabel}`);

    const actionChips = [];
    if (pageAllowed('diensten')) actionChips.push(`<button class="dashboard-chip-btn" onclick="openPage('diensten')">Open diensten</button>`);
    if (pageAllowed('diensten')) actionChips.push(`<button class="dashboard-chip-btn" onclick="openPage('diensten'); setDienstenView('week', { keepDayFilter: false });">Deze week</button>`);
    if (pageAllowed('dienstsoorten')) actionChips.push(`<button class="dashboard-chip-btn" onclick="openPage('dienstsoorten')">Dienstsoorten</button>`);
    if (pageAllowed('diensten')) actionChips.push(`<button class="dashboard-chip-btn" onclick="openDishImportModal()">DISH import</button>`);
    const actionChipEl = document.getElementById('dashboardActionChips');
    if (actionChipEl) actionChipEl.innerHTML = actionChips.join('');

    

    const quickCards = [];
    if (pageAllowed('bar-koelingen')) quickCards.push({label:'Bar', title:'Koelingen', sub:'Overzicht per koeling en status', page:'bar-koelingen'});
    if (pageAllowed('bar-productsoorten')) quickCards.push({label:'Bar', title:'Productsoorten', sub:'Geordend per soort en locatie', page:'bar-productsoorten'});
    if (pageAllowed('bar-locaties')) quickCards.push({label:'Bar', title:'Locaties', sub:'Opslagplekken en indeling', page:'bar-locaties'});
    if (pageAllowed('bar-bijvullen')) quickCards.push({label:'Bar', title:'Bijvullen', sub:'Wat direct aandacht nodig heeft', page:'bar-bijvullen'});
    if (pageAllowed('diensten')) quickCards.push({label:'Algemeen', title:'Diensten', sub:'Bekijk en plan je diensten', page:'diensten'});
    if (pageAllowed('fooienpot')) quickCards.push({label:'Algemeen', title:'Fooienpot', sub:'Huidige stand en snelle aanpassing', page:'fooienpot'});
    if (pageAllowed('checklists')) quickCards.push({label:'Werkvloer', title:'Checklists', sub:'Alle bar- en keukentaken op één centrale plek', page:'checklists'});
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


  function renderHubCards(targetId, cards, emptyText){
    const el = document.getElementById(targetId);
    if (!el) return;
    if (!cards.length){
      el.innerHTML = `<div class="overview-note">${emptyText}</div>`;
      return;
    }
    el.innerHTML = cards.map(card => `
      <div class="overview-hub-card">
        <div class="overview-hub-top">
          <div>
            <div class="overview-hub-kicker">${card.kicker || 'Overzicht'}</div>
            <div class="overview-hub-title">${card.title}</div>
            <div class="overview-hub-sub">${card.sub || ''}</div>
          </div>
          ${card.badge ? `<span class="badge ${card.badgeClass || ''}">${card.badge}</span>` : ''}
        </div>
        ${card.meta && card.meta.length ? `<div class="meta-row">${card.meta.slice(0,2).map(x => `<span class="meta-chip">${x}</span>`).join('')}</div>` : ''}
        <div class="overview-hub-actions">
          ${(card.actions || []).slice(0,2).map(action => `<button class="btn ${action.kind || ''}" onclick="${action.onclick}">${action.label}</button>`).join('')}
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
    const { diensten, upcoming, thisWeek, changed } = collectDienstStats();
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
      cards.push({
        kicker:'Algemeen',
        title:'Jouw diensten',
        sub: upcoming.length ? 'Je eerstvolgende diensten staan direct klaar.' : 'Plan of importeer je komende diensten.',
        badge:`${diensten.length} gepland`,
        meta:[
          `Deze week: ${thisWeek.length}`,
          `Wijzigingen: ${changed.length}`,
          upcoming[0] ? `Volgende: ${formatDienstDate(upcoming[0].datum)}${getDienstTimeLabel(upcoming[0]) ? ' · ' + getDienstTimeLabel(upcoming[0]) : ''}` : 'Nog niets gepland'
        ],
        actions:[{ label:'Open diensten', kind:'accent', onclick:`openPage('diensten')` }, { label:'DISH import', onclick:'openPage(\'diensten\'); setTimeout(openDishImportModal, 80)' }]
      });
    }
    renderHubCards('generalOverviewGrid', cards, 'Je hebt binnen Algemeen nu alleen toegang tot onderdelen die voor jouw werkdag relevant zijn.');
    setText('generalHeroMetric', String(thisWeek.length));

    const rows = [];
    upcoming.slice(0,4).forEach(item => rows.push({
      title:getDienstDisplayName(item),
      sub:`${formatDienstDate(item.datum)}${getDienstTimeLabel(item) ? ' · ' + getDienstTimeLabel(item) : ''}${getDienstLocation(item) ? ' · ' + getDienstLocation(item) : ''}`,
      badge:dienstStatusLabel(item.status),
      badgeClass:dienstStatusBadgeClass(item.status)
    }));
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
    if (pageAllowed('bar-bijvullen')) cards.push({ kicker:'Bar', title:'Bijvuloverzicht', sub:'Zie meteen wat vandaag aandacht nodig heeft.', badge:`${fill.length} acties`, badgeClass: fill.length ? 'warn' : 'good', meta: fill.slice(0,2).map(item => `${item.product} · ${item.bijvullen} bijvullen`), actions:[{ label:'Open bijvullen', kind:'accent', onclick:`openPage('bar-bijvullen')` }] });
    if (pageAllowed('bar-oplijst')) cards.push({ kicker:'Bar', title:'Op-lijst', sub:'Alles wat op is of weer terug op voorraad moet.', badge:`${opCount} op`, badgeClass: opCount ? 'warn' : 'good', actions:[{ label:'Open op-lijst', kind:'accent', onclick:`openPage('bar-oplijst')` }] });
    if (pageAllowed('bar-productsoorten')) cards.push({ kicker:'Bar', title:'Productsoorten', sub:'Beheer soorten en indeling per locatie.', badge:`${safeArray(appData.types).length} soorten`, actions:[{ label:'Open soorten', kind:'accent', onclick:`openPage('bar-productsoorten')` }] });
    if (pageAllowed('bar-locaties')) cards.push({ kicker:'Bar', title:'Locaties', sub:'Overzicht van opslagplekken en logische looproutes.', badge:`${safeArray(appData.locations).filter(Boolean).length} locaties`, actions:[{ label:'Open locaties', kind:'accent', onclick:`openPage('bar-locaties')` }] });
    renderHubCards('barOverviewGrid', cards, 'Je ziet hier alleen de bar-onderdelen waar jij echt iets mee kunt.');
    setText('barHeroMetric', String(fill.length));

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
    try{
      const parts = new Intl.DateTimeFormat('sv-SE', { timeZone:'Europe/Amsterdam', year:'numeric', month:'2-digit', day:'2-digit' }).formatToParts(new Date());
      const get = type => (parts.find(p => p.type === type) || {}).value || '';
      return `${get('year')}-${get('month')}-${get('day')}`;
    }catch(err){
      return new Date().toISOString().slice(0,10);
    }
  }

  function getAmsterdamDayLabel(){
    try{
      const day = new Intl.DateTimeFormat('en-GB', { timeZone:'Europe/Amsterdam', weekday:'long' }).format(new Date()).toLowerCase();
      const mapping = { wednesday:'woensdag', thursday:'donderdag', friday:'vrijdag', saturday:'zaterdag', sunday:'zondag' };
      return mapping[day] || 'altijd';
    }catch(err){
      return 'altijd';
    }
  }

  function getTaskDayOptions(){
    return ['altijd','woensdag','donderdag','vrijdag','zaterdag','zondag'];
  }

  function formatTaskDayLabel(day){
    const labels = { altijd:'Altijd', woensdag:'Woensdag', donderdag:'Donderdag', vrijdag:'Vrijdag', zaterdag:'Zaterdag', zondag:'Zondag' };
    return labels[day] || 'Altijd';
  }

  function taskListMatchesDay(list, selectedDay){
    const day = ((list && list.day) || 'altijd').toLowerCase();
    return day === 'altijd' || day === selectedDay;
  }

  function renderTaskDaySwitcher(targetId, selectedDay, changeFnName){
    const html = `
      <div class="task-switcher">
        <div class="task-switcher-label">Dag</div>
        <div class="task-switcher-row">
          ${getTaskDayOptions().map(day => `<button class="task-switcher-btn ${day === selectedDay ? 'active' : ''}" onclick="${changeFnName}('${day}')">${formatTaskDayLabel(day)}</button>`).join('')}
        </div>
      </div>
    `;
    const target = document.getElementById(targetId);
    if (target) target.innerHTML = html;
  }

  function getChecklistDate(){
    const base = currentChecklistDateISO || getTodayString();
    const date = new Date(`${base}T12:00:00`);
    return Number.isNaN(date.getTime()) ? new Date() : date;
  }

  function getChecklistSelectedDateIso(){
    if (!currentChecklistDateISO) currentChecklistDateISO = getTodayString();
    return currentChecklistDateISO;
  }

  function isChecklistToday(){
    return getChecklistSelectedDateIso() === getTodayString();
  }

  function getChecklistDayLabel(){
    const date = getChecklistDate();
    try{
      const weekday = new Intl.DateTimeFormat('en-GB', { timeZone:'Europe/Amsterdam', weekday:'long' }).format(date).toLowerCase();
      const mapping = { wednesday:'woensdag', thursday:'donderdag', friday:'vrijdag', saturday:'zaterdag', sunday:'zondag' };
      return mapping[weekday] || 'altijd';
    }catch(err){
      return getAmsterdamDayLabel();
    }
  }

  function formatChecklistDateLabel(){
    const date = getChecklistDate();
    try{
      return new Intl.DateTimeFormat('nl-NL', { weekday:'long', day:'numeric', month:'long', timeZone:'Europe/Amsterdam' }).format(date);
    }catch(err){
      return formatTaskDayLabel(getChecklistDayLabel());
    }
  }

  function shiftChecklistDate(delta){
    const date = getChecklistDate();
    date.setDate(date.getDate() + Number(delta || 0));
    currentChecklistDateISO = date.toISOString().slice(0,10);
    renderChecklistsPage();
  }

  function goChecklistToday(){
    currentChecklistDateISO = getTodayString();
    renderChecklistsPage();
  }

  function setChecklistFilter(filter){
    currentChecklistFilter = filter || 'all';
    renderChecklistsPage();
  }


  function getChecklistListDays(list){
    const raw = Array.isArray(list?.days) && list.days.length ? list.days : [list?.day || 'altijd'];
    const cleaned = [];
    raw.forEach(day => {
      const value = String(day || 'altijd').toLowerCase();
      if (getTaskDayOptions().includes(value) && !cleaned.includes(value)) cleaned.push(value);
    });
    return cleaned.length ? cleaned : ['altijd'];
  }

  function formatTaskDaysLabel(list){
    return getChecklistListDays(list).map(day => formatTaskDayLabel(day)).join(' + ');
  }

  function checklistManageSections(){
    const sections = [];
    if (hasPermission('access_bar') && hasPermission('manage_bar_tasklists')) {
      sections.push({ key:'bar', title:'Bar', lists:safeArray(appData.bar_tasks?.lists) });
    }
    if (hasPermission('access_kitchen') && hasPermission('manage_kitchen_tasklists')) {
      sections.push({ key:'kitchen', title:'Keuken', lists:safeArray(appData.kitchen?.lists) });
    }
    return sections;
  }

  function renderChecklistManagerBody(){
    const sections = checklistManageSections();
    const state = currentChecklistAdminEditor || { mode:'overview' };
    if (!sections.length){
      return `<div class="check-admin-editor"><div class="check-admin-editor-title">Geen toegang</div><div class="check-admin-editor-sub">Je hebt geen beheerrechten voor checklists.</div></div>`;
    }
    if (state.mode === 'manage-list'){
      const section = sections.find(item => item.key === state.section);
      const list = getChecklistList(state.section, state.listId);
      if (!section || !list){
        currentChecklistAdminEditor = { mode:'overview', section:'', listId:'', taskId:'', subtaskId:'' };
        return renderChecklistManagerBody();
      }
      return `
        <div class="check-admin-layout">
          <div class="check-admin-toolbar">
            <div class="check-admin-note">${section.title} · ${escapeHtml(list.name || 'Checklist')} · ${formatTaskDaysLabel(list)}</div>
            <div class="check-admin-actions">
              <button class="btn" onclick="setChecklistAdminEditor('overview')">← Terug</button>
              <button class="btn accent" onclick="openChecklistTaskModal('${section.key}','${list.id}')">+ Taak</button>
              <button class="btn" onclick="openChecklistListEditModal('${section.key}','${list.id}')">Checklist wijzigen</button>
            </div>
          </div>
          <div class="check-admin-section">
            <div class="check-admin-section-head">
              <div>
                <div class="check-admin-title">${escapeHtml(list.name || 'Checklist')}</div>
                <div class="check-admin-sub">${safeArray(list.tasks).length} taken · ${formatTaskDaysLabel(list)}</div>
              </div>
            </div>
            <div class="check-admin-tasks">
              ${safeArray(list.tasks).length ? safeArray(list.tasks).map(task => `
                <div class="check-admin-task">
                  <div class="check-admin-task-head">
                    <div>
                      <div class="check-admin-task-name">${escapeHtml(task.name || 'Taak')}</div>
                      <div class="check-admin-task-meta">${safeArray(task.subtasks).length} subtaken</div>
                    </div>
                    <div class="check-admin-actions">
                      <button class="check-mini-btn" onclick="openChecklistTaskEditModal('${section.key}','${list.id}','${task.id}')">Wijzig</button>
                      <button class="check-mini-btn" onclick="openChecklistSubtaskModal('${section.key}','${list.id}','${task.id}')">+ Subtaak</button>
                      <button class="check-mini-btn danger" onclick="confirmChecklistDelete('${section.key}','task','${list.id}','${task.id}')">Verwijder</button>
                    </div>
                  </div>
                  ${safeArray(task.subtasks).length ? `
                    <div class="check-admin-subtasks">
                      ${safeArray(task.subtasks).map(sub => `
                        <div class="check-admin-subtask">
                          <div>
                            <div class="check-admin-subtask-name">${escapeHtml(sub.name || 'Subtaak')}</div>
                            ${formatAuditLine(sub) ? `<div class="check-admin-subtask-meta">${formatAuditLine(sub)}</div>` : ''}
                          </div>
                          <div class="check-admin-actions">
                            <button class="check-mini-btn" onclick="openChecklistSubtaskEditModal('${section.key}','${list.id}','${task.id}','${sub.id}')">Wijzig</button>
                            <button class="check-mini-btn danger" onclick="confirmChecklistDelete('${section.key}','subtask','${list.id}','${task.id}','${sub.id}')">Verwijder</button>
                          </div>
                        </div>
                      `).join('')}
                    </div>
                  ` : `<div class="check-admin-empty">Nog geen subtaken.</div>`}
                </div>
              `).join('') : `<div class="check-admin-empty">Nog geen taken in deze checklist.</div>`}
            </div>
          </div>
        </div>`;
    }
    return `
      <div class="check-admin-layout">
        <div class="check-admin-toolbar">
          <div class="check-admin-note">Open per checklist het beheerscherm. Toevoegen en wijzigen gebeurt via popups.</div>
          <div class="check-admin-actions">
            <button class="btn" onclick="openPage('checklists')">← Terug</button>
            ${sections.map(section => `<button class="btn accent" onclick="openChecklistListModal('${section.key}')">+ ${section.title} checklist</button>`).join('')}
          </div>
        </div>
        ${sections.map(section => `
          <div class="check-admin-section">
            <div class="check-admin-section-head">
              <div>
                <div class="check-admin-title">${section.title}</div>
                <div class="check-admin-sub">${section.lists.length} checklist${section.lists.length === 1 ? '' : 's'}</div>
              </div>
            </div>
            <div class="check-admin-lists">
              ${section.lists.length ? section.lists.map(list => `
                <div class="check-admin-list">
                  <div class="check-admin-list-head">
                    <div>
                      <div class="check-admin-list-name">${escapeHtml(list.name || 'Checklist')}</div>
                      <div class="check-admin-list-meta">${formatTaskDaysLabel(list)} · ${safeArray(list.tasks).length} taken</div>
                    </div>
                    <div class="check-admin-actions">
                      <button class="check-mini-btn" onclick="setChecklistAdminEditor('manage-list', { section: '${section.key}', listId: '${list.id}' })">Beheer</button>
                      <button class="check-mini-btn" onclick="openChecklistListEditModal('${section.key}','${list.id}')">Wijzig</button>
                      <button class="check-mini-btn danger" onclick="confirmChecklistDelete('${section.key}','list','${list.id}')">Verwijder</button>
                    </div>
                  </div>
                </div>
              `).join('') : `<div class="check-admin-empty">Nog geen checklists in ${section.title.toLowerCase()}.</div>`}
            </div>
          </div>
        `).join('')}
      </div>`;
  }

  function setChecklistAdminEditor(mode='overview', payload={}){
    currentChecklistAdminEditor = { mode, section:'', listId:'', taskId:'', subtaskId:'', ...payload };
    renderChecklistManagerPage();
  }


  function bindChecklistManageButtonFallback(){
    if (window.__checklistManageFallbackBound) return;
    window.__checklistManageFallbackBound = true;
    document.addEventListener('click', function(e){
      const btn = e.target.closest('.check-settings-btn, .checklist-manage-action');
      if (!btn) return;
      e.preventDefault();
      e.stopPropagation();
      try{
        openChecklistManagerPage();
      }catch(err){
        try{
          currentChecklistAdminEditor = { mode:'overview', section:'', listId:'', taskId:'', subtaskId:'' };
          openPage('checklists-beheer');
          renderChecklistManagerPage();
        }catch(innerErr){}
      }
    }, true);
  }

  function openChecklistManagerPage(){
    setChecklistAdminEditor('overview');
    openPage('checklists-beheer');
    renderChecklistManagerPage();
    return false;
  }

  function openChecklistSettings(){
    openChecklistManagerPage();
  }

  function renderChecklistManagerEditor(){
    return '';
  }

  function renderChecklistManagerPage(){
    const wrap = document.getElementById('checklistManagerPage');
    if (!wrap) return;
    wrap.innerHTML = `${renderChecklistManagerEditor()}${renderChecklistManagerBody()}`;
  }

  async function saveChecklistAdminList(mode, listId=''){
    const section = document.getElementById('checkAdminListSection')?.value || currentChecklistAdminEditor.section;
    const name = document.getElementById('checkAdminListName')?.value || '';
    const day = document.getElementById('checkAdminListDay')?.value || 'altijd';
    const url = mode === 'new-list' ? (section === 'bar' ? '/api/bar-tasks/list-save' : '/api/kitchen/list-save') : (section === 'bar' ? '/api/bar-tasks/list-rename' : '/api/kitchen/list-rename');
    const payload = mode === 'new-list' ? { name, day } : { list_id: listId, name, day };
    try{
      await postJSON(url, payload);
      await loadData();
      renderChecklistsPage();
      setChecklistAdminEditor('overview');
      toast(mode === 'new-list' ? 'Checklist opgeslagen' : 'Checklist bijgewerkt');
    }catch(err){ toast(err.message, 'error'); }
  }

  async function saveChecklistAdminTask(mode, section, listId, taskId=''){
    const name = document.getElementById('checkAdminTaskName')?.value || '';
    const url = mode === 'new-task' ? (section === 'bar' ? '/api/bar-tasks/task-save' : '/api/kitchen/task-save') : (section === 'bar' ? '/api/bar-tasks/task-rename' : '/api/kitchen/task-rename');
    const payload = mode === 'new-task' ? { list_id: listId, name } : { list_id: listId, task_id: taskId, name };
    try{
      await postJSON(url, payload);
      await loadData();
      renderChecklistsPage();
      setChecklistAdminEditor('overview');
      toast(mode === 'new-task' ? 'Taak opgeslagen' : 'Taak bijgewerkt');
    }catch(err){ toast(err.message, 'error'); }
  }

  async function saveChecklistAdminSubtask(mode, section, listId, taskId, subtaskId=''){
    const name = document.getElementById('checkAdminSubtaskName')?.value || '';
    const url = mode === 'new-subtask' ? (section === 'bar' ? '/api/bar-tasks/subtask-save' : '/api/kitchen/subtask-save') : (section === 'bar' ? '/api/bar-tasks/subtask-rename' : '/api/kitchen/subtask-rename');
    const payload = mode === 'new-subtask' ? { list_id: listId, task_id: taskId, name } : { list_id: listId, task_id: taskId, subtask_id: subtaskId, name };
    try{
      await postJSON(url, payload);
      await loadData();
      renderChecklistsPage();
      setChecklistAdminEditor('overview');
      toast(mode === 'new-subtask' ? 'Subtaak opgeslagen' : 'Subtaak bijgewerkt');
    }catch(err){ toast(err.message, 'error'); }
  }

  function refreshChecklistSettingsModal(){
    renderChecklistManagerPage();
  }

  function getChecklistList(section, listId){
    const source = section === 'bar' ? safeArray(appData.bar_tasks?.lists) : safeArray(appData.kitchen?.lists);
    return source.find(item => item.id === listId) || null;
  }

  function renderChecklistDayCheckboxes(inputName, selectedDays){
    const selected = Array.isArray(selectedDays) && selectedDays.length ? selectedDays : [getChecklistDayLabel()];
    return `<div class="day-chip-row">${getTaskDayOptions().map(day => `
      <label class="day-chip ${selected.includes(day) ? 'active' : ''}">
        <input type="checkbox" name="${inputName}" value="${day}" ${selected.includes(day) ? 'checked' : ''} onchange="this.parentElement.classList.toggle('active', this.checked)">
        <span>${formatTaskDayLabel(day)}</span>
      </label>
    `).join('')}</div>`;
  }

  function selectedChecklistDaysFrom(inputName){
    const values = Array.from(document.querySelectorAll(`input[name="${inputName}"]:checked`)).map(el => el.value);
    return values.length ? values : ['altijd'];
  }

  function getChecklistTask(section, listId, taskId){
    const list = getChecklistList(section, listId);
    return safeArray(list?.tasks).find(item => item.id === taskId) || null;
  }

  function openChecklistListModal(section){
    const canManage = section === 'bar' ? hasPermission('manage_bar_tasklists') : hasPermission('manage_kitchen_tasklists');
    if (!canManage) return;
    openModal(`${section === 'bar' ? 'Bar' : 'Keuken'} checklist toevoegen`, 'Maak een nieuwe checklist aan.', `
      <div class="form-grid">
        <div class="field"><label>Naam checklist</label><input id="centralChecklistListName" placeholder="Bijv. Opening"></div>
        <div class="field"><label>Dagen</label>${renderChecklistDayCheckboxes('centralChecklistListDays', [getChecklistDayLabel()])}</div>
        <div class="form-actions">
          <button class="btn" onclick="closeModal()">Annuleer</button>
          <button class="btn accent" onclick="saveCentralChecklistList('${section}')">Opslaan</button>
        </div>
      </div>`);
  }

  async function saveCentralChecklistList(section){
    const url = section === 'bar' ? '/api/bar-tasks/list-save' : '/api/kitchen/list-save';
    try{
      await postJSON(url, { name: document.getElementById('centralChecklistListName').value, days: selectedChecklistDaysFrom('centralChecklistListDays') });
      closeModal();
      await loadData();
      renderChecklistsPage();
      setChecklistAdminEditor('overview');
      openPage('checklists-beheer');
      toast('Checklist opgeslagen');
    }catch(err){ toast(err.message, 'error'); }
  }

  function openChecklistListEditModal(section, listId){
    const list = getChecklistList(section, listId);
    if (!list) return;
    openModal('Checklist wijzigen', 'Pas naam of dagen van deze checklist aan.', `
      <div class="form-grid">
        <div class="field"><label>Naam checklist</label><input id="centralChecklistEditListName" value="${escapeHtml(list.name || '')}"></div>
        <div class="field"><label>Dagen</label>${renderChecklistDayCheckboxes('centralChecklistEditListDays', getChecklistListDays(list))}</div>
        <div class="form-actions">
          <button class="btn" onclick="closeModal()">Annuleer</button>
          <button class="btn accent" onclick="saveChecklistListEdit('${section}','${listId}')">Opslaan</button>
        </div>
      </div>`);
  }

  async function saveChecklistListEdit(section, listId){
    const url = section === 'bar' ? '/api/bar-tasks/list-rename' : '/api/kitchen/list-rename';
    try{
      await postJSON(url, { list_id: listId, name: document.getElementById('centralChecklistEditListName').value, days: selectedChecklistDaysFrom('centralChecklistEditListDays') });
      closeModal();
      await loadData();
      renderChecklistsPage();
      setChecklistAdminEditor('overview');
      openPage('checklists-beheer');
      toast('Checklist bijgewerkt');
    }catch(err){ toast(err.message, 'error'); }
  }

  function openChecklistTaskModal(section, listId){
    openModal('Taak toevoegen', 'Voeg een taak toe aan deze checklist.', `
      <div class="form-grid">
        <div class="field"><label>Naam taak</label><input id="centralChecklistTaskName" placeholder="Bijv. Koelingen checken"></div>
        <div class="form-actions">
          <button class="btn" onclick="closeModal()">Annuleer</button>
          <button class="btn accent" onclick="saveCentralChecklistTask('${section}','${listId}')">Opslaan</button>
        </div>
      </div>`);
  }

  async function saveCentralChecklistTask(section, listId){
    const url = section === 'bar' ? '/api/bar-tasks/task-save' : '/api/kitchen/task-save';
    try{
      await postJSON(url, { list_id: listId, name: document.getElementById('centralChecklistTaskName').value });
      closeModal();
      await loadData();
      renderChecklistsPage();
      setChecklistAdminEditor('manage-list', { section, listId });
      openPage('checklists-beheer');
      toast('Taak opgeslagen');
    }catch(err){ toast(err.message, 'error'); }
  }

  function openChecklistTaskEditModal(section, listId, taskId){
    const task = getChecklistTask(section, listId, taskId);
    if (!task) return;
    openModal('Taak wijzigen', 'Pas de naam van deze taak aan.', `
      <div class="form-grid">
        <div class="field"><label>Naam taak</label><input id="centralChecklistEditTaskName" value="${escapeHtml(task.name || '')}"></div>
        <div class="form-actions">
          <button class="btn" onclick="closeModal()">Annuleer</button>
          <button class="btn accent" onclick="saveChecklistTaskEdit('${section}','${listId}','${taskId}')">Opslaan</button>
        </div>
      </div>`);
  }

  async function saveChecklistTaskEdit(section, listId, taskId){
    const url = section === 'bar' ? '/api/bar-tasks/task-rename' : '/api/kitchen/task-rename';
    try{
      await postJSON(url, { list_id: listId, task_id: taskId, name: document.getElementById('centralChecklistEditTaskName').value });
      closeModal();
      await loadData();
      renderChecklistsPage();
      setChecklistAdminEditor('manage-list', { section, listId });
      openPage('checklists-beheer');
      toast('Taak bijgewerkt');
    }catch(err){ toast(err.message, 'error'); }
  }

  function openChecklistSubtaskModal(section, listId, taskId){
    openModal('Subtaak toevoegen', 'Voeg een subtaak toe onder deze taak.', `
      <div class="form-grid">
        <div class="field"><label>Naam subtaak</label><input id="centralChecklistSubtaskName" placeholder="Bijv. Frisse doeken klaarleggen"></div>
        <div class="form-actions">
          <button class="btn" onclick="closeModal()">Annuleer</button>
          <button class="btn accent" onclick="saveCentralChecklistSubtask('${section}','${listId}','${taskId}')">Opslaan</button>
        </div>
      </div>`);
  }

  async function saveCentralChecklistSubtask(section, listId, taskId){
    const url = section === 'bar' ? '/api/bar-tasks/subtask-save' : '/api/kitchen/subtask-save';
    try{
      await postJSON(url, { list_id: listId, task_id: taskId, name: document.getElementById('centralChecklistSubtaskName').value });
      closeModal();
      await loadData();
      renderChecklistsPage();
      setChecklistAdminEditor('manage-list', { section, listId });
      openPage('checklists-beheer');
      toast('Subtaak opgeslagen');
    }catch(err){ toast(err.message, 'error'); }
  }

  function openChecklistSubtaskEditModal(section, listId, taskId, subtaskId){
    const task = getChecklistTask(section, listId, taskId);
    const sub = safeArray(task?.subtasks).find(item => item.id === subtaskId) || null;
    if (!sub) return;
    openModal('Subtaak wijzigen', 'Pas de naam van deze subtaak aan.', `
      <div class="form-grid">
        <div class="field"><label>Naam subtaak</label><input id="centralChecklistEditSubtaskName" value="${escapeHtml(sub.name || '')}"></div>
        <div class="form-actions">
          <button class="btn" onclick="closeModal()">Annuleer</button>
          <button class="btn accent" onclick="saveChecklistSubtaskEdit('${section}','${listId}','${taskId}','${subtaskId}')">Opslaan</button>
        </div>
      </div>`);
  }

  async function saveChecklistSubtaskEdit(section, listId, taskId, subtaskId){
    const url = section === 'bar' ? '/api/bar-tasks/subtask-rename' : '/api/kitchen/subtask-rename';
    try{
      await postJSON(url, { list_id: listId, task_id: taskId, subtask_id: subtaskId, name: document.getElementById('centralChecklistEditSubtaskName').value });
      closeModal();
      await loadData();
      renderChecklistsPage();
      setChecklistAdminEditor('manage-list', { section, listId });
      openPage('checklists-beheer');
      toast('Subtaak bijgewerkt');
    }catch(err){ toast(err.message, 'error'); }
  }

  function confirmChecklistDelete(section, kind, listId, taskId='', subtaskId=''){
    const title = kind === 'list'
      ? 'Checklist verwijderen'
      : kind === 'task'
        ? 'Taak verwijderen'
        : 'Subtaak verwijderen';
    const bodyText = kind === 'list'
      ? 'Weet je zeker dat je deze checklist wilt verwijderen?'
      : kind === 'task'
        ? 'Weet je zeker dat je deze taak wilt verwijderen?'
        : 'Weet je zeker dat je deze subtaak wilt verwijderen?';

    openModal(title, bodyText, `
      <div class="form-actions">
        <button class="btn" onclick="closeModal()">Annuleer</button>
        <button class="btn danger" onclick="runChecklistDelete('${section}','${kind}','${listId}','${taskId}','${subtaskId}')">Ja, verwijder</button>
      </div>
    `);
  }

  async function runChecklistDelete(section, kind, listId, taskId='', subtaskId=''){
    try{
      let url = '';
      let payload = { list_id: listId };
      if (kind === 'list') {
        url = section === 'bar' ? '/api/bar-tasks/list-delete' : '/api/kitchen/list-delete';
      } else if (kind === 'task') {
        url = section === 'bar' ? '/api/bar-tasks/task-delete' : '/api/kitchen/task-delete';
        payload.task_id = taskId;
      } else {
        url = section === 'bar' ? '/api/bar-tasks/subtask-delete' : '/api/kitchen/subtask-delete';
        payload.task_id = taskId;
        payload.subtask_id = subtaskId;
      }
      await postJSON(url, payload);
      closeModal();
      await loadData();
      renderChecklistsPage();
      if (kind === 'list') {
        setChecklistAdminEditor('overview');
      } else {
        setChecklistAdminEditor('manage-list', { section, listId });
      }
      if (typeof renderChecklistManagerPage === 'function') renderChecklistManagerPage();
      openPage('checklists-beheer');
      toast(`${kind === 'list' ? 'Checklist' : kind === 'task' ? 'Taak' : 'Subtaak'} verwijderd`);
    }catch(err){
      toast(err.message, 'error');
    }
  }

  function checklistTaskStatus(task, section){
    const taskCheckedFn = section === 'bar' ? barTaskIsChecked : kitchenTaskIsChecked;
    const subtaskCheckedFn = section === 'bar' ? barSubtaskIsChecked : kitchenSubtaskIsChecked;
    return getTaskProgress(task, taskCheckedFn, subtaskCheckedFn);
  }

  function filterChecklistTasks(tasks, section){
    const items = safeArray(tasks);
    return items.filter(task => {
      const progress = checklistTaskStatus(task, section);
      if (currentChecklistFilter === 'done') return progress.isDone;
      if (currentChecklistFilter === 'todo') return !progress.isDone;
      return true;
    });
  }

  function filterChecklistSubtasks(task, section){
    const fn = section === 'bar' ? barSubtaskIsChecked : kitchenSubtaskIsChecked;
    return safeArray(task?.subtasks).filter(sub => {
      if (currentChecklistFilter === 'done') return fn(sub);
      if (currentChecklistFilter === 'todo') return !fn(sub);
      return true;
    });
  }

  function getChecklistSectionStats(lists, section){
    const taskCheckedFn = section === 'bar' ? barTaskIsChecked : kitchenTaskIsChecked;
    const visibleLists = safeArray(lists).map(list => ({ ...list, filteredTasks: filterChecklistTasks(list.tasks, section) })).filter(list => list.filteredTasks.length || currentChecklistFilter === 'all');
    const allTasks = safeArray(lists).flatMap(list => safeArray(list.tasks));
    const done = allTasks.filter(taskCheckedFn).length;
    return { visibleLists, total: allTasks.length, done, percent: allTasks.length ? Math.round((done / allTasks.length) * 100) : 0 };
  }

  function renderChecklistTaskItem(section, listId, task){
    const taskCheckedFn = section === 'bar' ? barTaskIsChecked : kitchenTaskIsChecked;
    const subtaskCheckedFn = section === 'bar' ? barSubtaskIsChecked : kitchenSubtaskIsChecked;
    const progress = getTaskProgress(task, taskCheckedFn, subtaskCheckedFn);
    const filteredSubs = filterChecklistSubtasks(task, section);
    const readOnly = !isChecklistToday();
    const taskAction = readOnly ? '' : (section === 'bar'
      ? `onclick="toggleBarTask('${listId}','${task.id}')"`
      : `onclick="toggleKitchenTask('${listId}','${task.id}')"`);
    return `
      <div class="check-task">
        <div class="check-task-head" ${taskAction}>
          <div class="check-circle ${progress.isDone ? 'done' : ''}">${progress.isDone ? '✓' : ''}</div>
          <div style="min-width:0;flex:1">
            <div class="check-task-title ${progress.isDone ? 'done' : ''}">${task.name || 'Taak'}</div>
            <div class="check-task-sub">${formatAuditLine(task) || (progress.totalSubs ? `${progress.doneSubs}/${progress.totalSubs} subtaken gedaan` : 'Losse taak')}</div>
          </div>
          <div class="check-task-right">
            <span class="badge ${progress.isDone ? 'good' : progress.status === 'progress' ? 'accent' : 'warn'}">${progress.isDone ? 'Klaar' : progress.status === 'progress' ? 'Bezig' : 'Open'}</span>
          </div>
        </div>
        ${filteredSubs.length ? `
          <div class="check-subtasks">
            ${filteredSubs.map(sub => {
              const done = subtaskCheckedFn(sub);
              const subAction = readOnly ? '' : (section === 'bar'
                ? `onclick="toggleBarSubtask('${listId}','${task.id}','${sub.id}')"`
                : `onclick="toggleKitchenSubtask('${listId}','${task.id}','${sub.id}')"`);
              return `
                <div class="check-subtask" ${subAction}>
                  <div class="check-subcircle ${done ? 'done' : ''}">${done ? '✓' : ''}</div>
                  <div style="min-width:0;flex:1">
                    <div class="check-subtask-title ${done ? 'done' : ''}">${sub.name || 'Subtaak'}</div>
                    ${formatAuditLine(sub) ? `<div class="check-subtask-meta">${formatAuditLine(sub)}</div>` : ''}
                  </div>
                  <span class="badge ${done ? 'good' : ''}">${done ? 'Klaar' : 'Open'}</span>
                </div>
              `;
            }).join('')}
          </div>
        ` : ''}
      </div>
    `;
  }

  function toggleChecklistList(section, listId){
    const el = document.getElementById(`checklist-list-${section}-${listId}`);
    if (el) el.classList.toggle('open');
  }

  function renderChecklistSection(target, title, section, lists){
    const stats = getChecklistSectionStats(lists, section);
    if (!stats.visibleLists.length && !stats.total){
      return '';
    }
    return `
      <div class="check-zone">
        <div class="check-zone-head">
          <div>
            <div class="check-zone-title">${title}</div>
            <div class="check-zone-sub">${stats.done} van ${stats.total} taken gedaan · ${formatTaskDayLabel(getChecklistDayLabel())}</div>
          </div>
          <div class="check-zone-right">
            <span class="check-zone-pill">${stats.percent}%</span>
            <span class="check-zone-count">${stats.done}/${stats.total || 0}</span>
          </div>
        </div>
        <div class="check-zone-progress"><span style="width:${stats.percent}%"></span></div>
        <div style="display:grid;gap:12px;margin-top:0">
          ${stats.visibleLists.map((list, index) => {
            const filteredTasks = list.filteredTasks;
            const total = safeArray(list.tasks).length;
            const done = safeArray(list.tasks).filter(section === 'bar' ? barTaskIsChecked : kitchenTaskIsChecked).length;
            const percent = total ? Math.round((done / total) * 100) : 0;
            return `
              <div class="check-list-card ${index === 0 ? 'open' : ''}" id="checklist-list-${section}-${list.id}">
                <div class="check-list-head" onclick="toggleChecklistList('${section}','${list.id}')">
                  <div class="check-list-main">
                    <div class="check-list-name">${list.name || 'Takenlijst'}</div>
                    <div class="check-list-meta">${done}/${total} taken gedaan · ${formatTaskDaysLabel(list)}</div>
                  </div>
                  <div class="check-list-right">
                    <span class="badge accent">${percent}%</span>
                    <div class="check-list-toggle">⌄</div>
                  </div>
                </div>
                <div class="check-list-body">
                  ${filteredTasks.length ? filteredTasks.map(task => renderChecklistTaskItem(section, list.id, task)).join('') : `<div class="check-empty">Geen taken zichtbaar voor het filter <strong>${currentChecklistFilter === 'todo' ? 'Te doen' : 'Klaar'}</strong>.</div>`}
                </div>
              </div>
            `;
          }).join('')}
        </div>
      </div>
    `;
  }

  function renderChecklistsPage(){
    const selectedDay = getChecklistDayLabel();
    currentKitchenTaskDay = selectedDay;
    currentBarTaskDay = selectedDay;
    ['all','todo','done'].forEach(filter => {
      const btn = document.getElementById(`checkFilter-${filter}`);
      if (btn) btn.classList.toggle('active', currentChecklistFilter === filter);
    });
    setText('checklistDateLabel', formatChecklistDateLabel());
    const sub = isChecklistToday()
      ? `Vandaag · ${formatTaskDayLabel(selectedDay)} · direct afvinken staat aan`
      : `${formatTaskDayLabel(selectedDay)} · je bekijkt de planning voor deze dag`; 
    setText('checklistDateSub', sub);

    const canSeeBarChecklists = hasPermission('access_bar') && hasPermission('use_bar_tasklists');
    const canSeeKitchenChecklists = hasPermission('access_kitchen') && hasPermission('use_kitchen_tasklists');
    const barLists = canSeeBarChecklists ? safeArray(appData.bar_tasks?.lists).filter(list => taskListMatchesDay(list, selectedDay)) : [];
    const kitchenLists = canSeeKitchenChecklists ? safeArray(appData.kitchen?.lists).filter(list => taskListMatchesDay(list, selectedDay)) : [];
    const barStats = getChecklistSectionStats(barLists, 'bar');
    const kitchenStats = getChecklistSectionStats(kitchenLists, 'kitchen');
    const total = barStats.total + kitchenStats.total;
    const done = barStats.done + kitchenStats.done;
    const percent = total ? Math.round((done / total) * 100) : 0;
    const progress = document.getElementById('checklistProgressCard');
    if (progress){
      progress.innerHTML = `
        <div class="check-progress-top">
          <div>
            <div class="check-progress-title">Voortgang ${isChecklistToday() ? 'vandaag' : 'planning'}</div>
            <div class="check-progress-count">${done}/${total} taken</div>
            <div class="check-progress-meta">${currentChecklistFilter === 'all' ? 'Alles in beeld' : currentChecklistFilter === 'todo' ? 'Alleen wat nog open staat' : 'Alleen afgeronde taken'}</div>
          </div>
          <div class="check-progress-percent">${percent}%</div>
        </div>
        <div class="check-progress-bar"><span style="width:${percent}%"></span></div>
        ${!isChecklistToday() ? `<div class="check-readonly" style="margin-top:12px">Voor andere dagen zie je alvast de juiste lijsten. Afvinken kan alleen op vandaag, zodat je bestaande systeem intact blijft.</div>` : ''}
      `;
    }
    const sections = document.getElementById('checklistSections');
    if (sections){
      const parts = [];
      if (canSeeBarChecklists) parts.push(renderChecklistSection(sections, 'Bar', 'bar', barLists));
      if (canSeeKitchenChecklists) parts.push(renderChecklistSection(sections, 'Keuken', 'kitchen', kitchenLists));
      sections.innerHTML = parts.filter(Boolean).join('') || '<div class="check-empty">Nog geen checklists gevonden voor deze dag.</div>';
    }
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
    const items = safeArray(tasks);
    const html = items.map(task => renderChecklistTaskCard(task, options)).join('');
    document.getElementById(targetId).innerHTML = html || '<div class="empty">Nog geen taken in deze lijst.</div>';
  }

  function renderTasklistSwitcher(lists, currentId, openCallName){
    const items = safeArray(lists);
    if (items.length <= 1) return '';
    return `
      <div class="task-switcher">
        <div class="task-switcher-label">Snel wisselen tussen lijsten</div>
        <div class="task-switcher-row">
          ${items.map(list => `<button class="task-switcher-btn ${list.id === currentId ? 'active' : ''}" onclick="${openCallName}('${list.id}')">${list.name || 'Takenlijst'}</button>`).join('')}
        </div>
      </div>
    `;
  }

  function renderKitchen(){
    const kitchen = appData.kitchen || { lists: [] };
    const allLists = safeArray(kitchen.lists);
    if (!currentKitchenTaskDay) currentKitchenTaskDay = getAmsterdamDayLabel();
    const lists = allLists.filter(list => taskListMatchesDay(list, currentKitchenTaskDay));
    const taskCount = lists.reduce((total, lst) => total + safeArray(lst.tasks).length, 0);
    const canManageTasklists = hasPermission('manage_kitchen_tasklists');

    setText('kitchenListCount', String(lists.length));
    setText('kitchenTaskCount', String(taskCount));
    setText('recipeCount', String(safeArray(appData.recipes?.items).length));
    renderTaskDaySwitcher('kitchenDaySwitcher', currentKitchenTaskDay, 'setKitchenTaskDay');

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
                  <div class="klist-sub">${formatTaskDaysLabel(list)} · ${done} van ${tasks.length} taken gedaan</div>
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
      'Nog geen takenlijsten gevonden voor deze dag.'
    );
  }

  
  function setKitchenTaskDay(day){
    currentKitchenTaskDay = day || 'altijd';
    renderKitchen();
  }

function renderKitchenListDetail(){
    const kitchen = appData.kitchen || { lists: [] };
    const allLists = safeArray(kitchen.lists);
    const visibleLists = allLists.filter(item => taskListMatchesDay(item, currentKitchenTaskDay));
    const list = allLists.find(item => item.id === currentKitchenListId) || { tasks: [], name: 'Takenlijst' };
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
          ${renderTasklistSwitcher(visibleLists, list.id, 'openBarListDetail')}
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
    if (!hasPermission('manage_kitchen_tasklists')) return;
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
          <div class="field"><label>Dag</label><select id="kitchenListDay">${getTaskDayOptions().map(day => `<option value="${day}" ${day === currentKitchenTaskDay ? 'selected' : ''}>${formatTaskDayLabel(day)}</option>`).join('')}</select></div>
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
      await postJSON('/api/kitchen/list-save', { name: document.getElementById('kitchenListName').value, day: document.getElementById('kitchenListDay').value });
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


  function defaultClientBarSlot(index){
    return { id: `slot_${index}`, label: `Vak ${index}`, product_id: '', product_name: '', image_url: ''};
  }

  function defaultClientBarShelf(index){
    return { id: `shelf_${index}`, name: `Plank ${index}`, facings: 9, height: 'medium', slots: Array.from({length:9}, (_,i) => defaultClientBarSlot(i + 1)) };
  }

  function defaultClientBarCooler(index){
    const shelves = [1,2,3].map(i => defaultClientBarShelf(i));
    shelves.push({ id: `shelf_4`, name: 'Bodem', facings: 9, height: 'low', is_floor: true, slots: Array.from({length:9}, (_,i) => defaultClientBarSlot(i + 1)) });
    return { id: `cooler_${index}`, name: `Koelkast ${index}`, shelves };
  }

  function defaultClientBarUnit(index){
    return { id: `unit_${index}`, name: `GB${index}`, coolers: [1,2,3].map(i => defaultClientBarCooler(i)) };
  }

  function normalizeClientBarLayout(layout){
    const item = layout || {};
    const rawUnits = safeArray(item.units);
    const units = rawUnits.slice(0,8).map((unit, unitIndex) => ({
      id: unit?.id || `unit_${unitIndex+1}`,
      name: unit?.name || `GB${unitIndex+1}`,
      coolers: safeArray(unit?.coolers).slice(0,3).map((cooler, coolerIndex) => ({
        id: cooler?.id || `cooler_${coolerIndex+1}`,
        name: cooler?.name || `Koelkast ${coolerIndex+1}`,
        shelves: safeArray(cooler?.shelves).map((shelf, shelfIndex) => ({
          id: shelf?.id || `shelf_${shelfIndex+1}`,
          name: shelf?.name || `Plank ${shelfIndex+1}`,
          facings: Math.max(1, Math.min(Number(shelf?.facings || shelf?.slots_per_shelf || shelf?.slot_count || 9) || 9, 9)),
          height: ["low","medium","high","wine"].includes(String(shelf?.height || shelf?.shelf_height || shelf?.height_level || 'medium')) ? String(shelf?.height || shelf?.shelf_height || shelf?.height_level || 'medium') : 'medium',
          slots: safeArray(shelf?.slots).map((slot, slotIndex) => ({
            id: slot?.id || `slot_${slotIndex+1}`,
            label: slot?.label || `Vak ${slotIndex+1}`,
            product_id: slot?.product_id || '',
            product_name: slot?.product_name || '',
            image_url: slot?.image_url || ''}))
        }))
      }))
    }));
    if(!units.length) units.push(...Array.from({length:4}, (_,i) => defaultClientBarUnit(i + 1)));
    units.forEach(unit => {
      while((unit.coolers || []).length < 3) unit.coolers.push(defaultClientBarCooler(unit.coolers.length + 1));
      unit.coolers = unit.coolers.slice(0,3);
      unit.coolers.forEach(cooler => {
        if(!safeArray(cooler.shelves).length){
          cooler.shelves = [1,2,3].map(i => defaultClientBarShelf(i));
          cooler.shelves.push({ id: 'shelf_4', name: 'Bodem', facings: 9, height: 'low', is_floor: true, slots: Array.from({length:9}, (_,i) => defaultClientBarSlot(i + 1)) });
        }
        cooler.shelves = safeArray(cooler.shelves).map((shelf, shelfIndex) => ({
          ...shelf,
          is_floor: Boolean(shelf?.is_floor || String(shelf?.name || '').trim().toLowerCase() === 'bodem')
        }));
        cooler.shelves.forEach((shelf, shelfIndex) => {
          const facings = Math.max(1, Math.min(Number(shelf?.facings || shelf?.slots_per_shelf || shelf?.slot_count || 9) || 9, 9));
          shelf.facings = facings;
          shelf.height = ["low","medium","high","wine"].includes(String(shelf?.height || shelf?.shelf_height || shelf?.height_level || 'medium')) ? String(shelf?.height || shelf?.shelf_height || shelf?.height_level || 'medium') : 'medium';
          if(!safeArray(shelf.slots).length) shelf.slots = Array.from({length:facings}, (_,i) => defaultClientBarSlot(i + 1));
          shelf.slots = shelf.slots.slice(0, facings).map((slot, slotIndex) => ({
            id: slot?.id || `slot_${slotIndex+1}`,
            label: slot?.label || `Vak ${slotIndex+1}`,
            product_id: slot?.product_id || '',
            product_name: slot?.product_name || '',
            image_url: slot?.image_url || ''}));
          while(shelf.slots.length < facings) shelf.slots.push(defaultClientBarSlot(shelf.slots.length + 1));
          shelf.name = shelf?.name || (shelf.is_floor ? 'Bodem' : `Plank ${shelfIndex+1}`);
          shelf.height = shelf.is_floor ? 'low' : shelf.height;
          shelf.id = shelf?.id || `shelf_${shelfIndex+1}`;
        });
        const floorShelves = cooler.shelves.filter(shelf => shelf.is_floor);
        const topShelves = cooler.shelves.filter(shelf => !shelf.is_floor).map((shelf, idx) => normalizeShelfShape({
          ...shelf,
          is_floor: false,
          id: shelf?.id || `shelf_${idx + 1}`,
          name: (shelf?.name || '').trim() || `Plank ${idx + 1}`}));
        const keptFloor = normalizeShelfShape({
          ...(floorShelves[0] || { id: `shelf_${topShelves.length + 1}`, name: 'Bodem', facings: 9, height: 'low', is_floor: true, slots: Array.from({length:9}, (_,i) => defaultClientBarSlot(i + 1)) }),
          is_floor: true,
          name: ((floorShelves[0]?.name) || 'Bodem').trim() || 'Bodem',
          facings: Math.max(1, Math.min(Number(floorShelves[0]?.facings || 9) || 9, 9)),
          height: 'low'
        });
        cooler.shelves = [...topShelves, keptFloor];
      });
    });
    return {
      id: item.id || '',
      name: item.name || 'Indeling',
      created_at: item.created_at || '',
      units
    };
  }

  function ensureBarLayoutSelection(){
    const items = safeArray(appData.bar_layouts?.items);
    if(!items.length){
      currentBarLayoutId = null;
      window.currentBarLayoutId = null;
      return null;
    }
    const wanted = currentBarLayoutId || appData.bar_layouts?.active_id || items[0]?.id;
    const found = items.find(item => item.id === wanted) || items[0];
    currentBarLayoutId = found?.id || null;
    window.currentBarLayoutId = currentBarLayoutId;
    return found || null;
  }

  function getSelectedBarLayout(){
    const selected = ensureBarLayoutSelection();
    return selected ? normalizeClientBarLayout(selected) : null;
  }

  function selectBarLayout(layoutId){
    currentBarLayoutId = layoutId || null;
    window.currentBarLayoutId = currentBarLayoutId;
    renderBarLayouts();
  }

  function escapeHtml(value=''){
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }


  function renderBarLayouts(){
    const data = appData.bar_layouts || { items: [], active_id: '' };
    const items = safeArray(data.items).map(normalizeClientBarLayout);
    const activeId = data.active_id || '';
    const listEl = document.getElementById('barLayoutsList');
    const activeBadge = document.getElementById('barLayoutActiveBadge');
    const info = document.getElementById('barLayoutInfo');
    const selectedBadge = document.getElementById('barLayoutSelectedBadge');
    const openEditorBtn = document.getElementById('barLayoutOpenEditorBtn');
    ensureBarLayoutSelection();
    const selected = items.find(x => x.id === currentBarLayoutId) || null;
    if(activeBadge) if(activeBadge) activeBadge.textContent = items.find(x => x.id === activeId)?.name || 'Geen actief';
    if(selectedBadge) selectedBadge.textContent = selected?.name || 'Geen indeling gekozen';
    if(openEditorBtn){
      openEditorBtn.disabled = !selected || !canManageBarLayouts();
      openEditorBtn.style.display = canManageBarLayouts() ? '' : 'none';
    }
    if(info){
      info.textContent = selected ? ((selected.note || 'Preset voor een event of standaard baropstelling.') + ' Gebruik Bekijken op de vloer en open de editor alleen voor echte wijzigingen.') : 'Kies een indeling uit de lijst. Daarna kun je direct naar Bekijken of Bewerken.';
    }
    renderBarLayoutReadonlyView();
    if(!listEl) return;
    if(!items.length){
      listEl.innerHTML = `<div class="empty">Nog geen indelingen opgeslagen. Maak er één aan voor bijvoorbeeld standaard, Koningsdag of eventavond.</div>`;
      return;
    }
    listEl.innerHTML = items.map(item => `
      <div class="list-item ${item.id === currentBarLayoutId ? 'is-selected' : ''}" onclick="selectBarLayout('${item.id}')">
        <div class="item-top">
          <div>
            <div class="item-title">${escapeHtml(item.name || 'Indeling')}</div>
            <div class="item-sub">${escapeHtml(item.note || 'Preset voor een event of standaard baropstelling.')}</div>
          </div>
          <span class="badge ${item.id === activeId ? 'accent' : ''}">${item.id === activeId ? 'Actief' : 'Preset'}</span>
        </div>
        <div class="meta-row">
          <span class="meta-chip">${escapeHtml(item.created_at || 'Zonder datum')}</span>
          <span class="meta-chip">${safeArray(item.units).length} unit${safeArray(item.units).length === 1 ? '' : 's'}</span>
          <span class="meta-chip">3 koelkastjes per unit</span>
        </div>
        <div class="item-actions" onclick="event.stopPropagation()">
          <button class="btn" onclick="openBarLayoutView('${item.id}')">Bekijken</button>
          ${canManageBarLayouts() ? `<button class="btn accent" onclick="openBarLayoutEditor('${item.id}')">Bewerken</button>` : ''}
          ${canManageBarLayouts() ? `${item.id === activeId ? `<span class="badge accent">Actief</span>` : `<button class="btn good" onclick="setActiveBarLayout('${item.id}')">Maak actief</button>`}<button class="btn" onclick="openBarLayoutModal('${item.id}')">Gegevens</button><button class="btn danger" onclick="confirmAction('Indeling verwijderen','Weet je zeker dat je deze indeling wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteBarLayout','${item.id}')&quot;)">Verwijderen</button>` : `${item.id === activeId ? `<span class="badge accent">Actief</span>` : ''}`}
        </div>
      </div>
    `).join('');
  }

  function changeBarLayoutReadonlyUnit(value){
    currentBarLayoutReadonlyUnitIndex = Number(value || 0);
    window.currentBarLayoutReadonlyUnitIndex = currentBarLayoutReadonlyUnitIndex;
    renderBarLayoutReadonlyView();
  }

  function renderBarLayoutReadonlyView(){
    const layout = getSelectedBarLayout();
    const stage = document.getElementById('barLayoutReadonlyStage');
    const unitSelect = document.getElementById('barLayoutReadonlyUnitSelect');
    const badge = document.getElementById('barLayoutReadonlyBadge');
    if(!stage) return;
    if(!layout){
      stage.innerHTML = `<div class="fridge-editor-empty">Kies of maak eerst een indeling aan. Daarna kun je hier dezelfde koelkastweergave bekijken als in de editor, maar dan zonder edit-controls.</div>`;
      if(unitSelect) unitSelect.innerHTML = '';
      if(badge) badge.textContent = '3 koelkastjes · kijkmodus';
      return;
    }
    const unitIndex = Math.max(0, Math.min(Number(currentBarLayoutReadonlyUnitIndex || 0), safeArray(layout.units).length - 1));
    currentBarLayoutReadonlyUnitIndex = unitIndex;
    window.currentBarLayoutReadonlyUnitIndex = unitIndex;
    const unit = layout.units[unitIndex] || layout.units[0];
    if(unitSelect){
      unitSelect.innerHTML = safeArray(layout.units).map((entry, idx) => `<option value="${idx}" ${idx === unitIndex ? 'selected' : ''}>${escapeHtml(entry.name || `GB${idx + 1}`)}</option>`).join('');
    }
    if(badge) badge.textContent = `${layout.name || 'Indeling'} · ${unit?.name || `GB${unitIndex + 1}`} · kijkmodus`;
    stage.innerHTML = renderBarLayoutStageHtml(layout, unitIndex, null, true);
  }

  function renderBarLayoutStageHtml(layout, unitIndex, target=null, readonly=false){
    const unit = layout?.units?.[unitIndex] || layout?.units?.[0];
    if(!unit){
      return `<div class="fridge-editor-empty">Geen unit gevonden.</div>`;
    }
    return `
      <div class="fridge-unit ${readonly ? 'readonly' : ''}">
        <div class="fridge-unit-top">
          <div>
            <div class="fridge-unit-name">${escapeHtml(unit.name || `GB${unitIndex + 1}`)}</div>
            <div class="fridge-unit-note">${readonly ? 'Kijkmodus · zelfde weergave als editor, maar zonder aanpasbare controls' : '3 brede koelkastjes naast elkaar · klik op een plank om direct die hele rij te vullen'}</div>
          </div>
          <span class="fridge-door-badge">${readonly ? 'Bekijk op de vloer' : 'Breed overzicht zoals op de vloer'}</span>
        </div>
        <div class="fridge-bank">
          ${safeArray(unit.coolers).map((cooler, coolerIndex) => `
            <div class="fridge-door">
              <div class="fridge-door-header">
                <div class="fridge-door-title">${escapeHtml(cooler.name || `Koelkast ${coolerIndex + 1}`)}</div>
                <span class="fridge-door-badge">deur ${coolerIndex + 1}</span>
              </div>
              <div class="fridge-door-frame">
                <div class="fridge-door-window">
                  <div class="fridge-handle"></div>
                  <div class="fridge-door-shelves">
                    ${safeArray(cooler.shelves)
                      .map((shelf, shelfIndex) => ({ shelf, shelfIndex }))
                      .sort((a, b) => Number(Boolean(a.shelf?.is_floor)) - Number(Boolean(b.shelf?.is_floor)))
                      .map(({ shelf, shelfIndex }) => {
                      const active = !readonly && target && target.coolerIndex === coolerIndex && target.shelfIndex === shelfIndex;
                      const facings = Math.max(1, Math.min(Number(shelf?.facings || 9) || 9, 9));
                      const shelfHeight = getShelfHeightPx(shelf?.height || 'medium');
                      const slots = safeArray(shelf.slots).slice(0, facings);
                      while(slots.length < facings) slots.push(defaultClientBarSlot(slots.length + 1));
                      const shelfClick = readonly ? '' : ` onclick="selectBarLayoutShelf(${unitIndex}, ${coolerIndex}, ${shelfIndex}, 0)"`;
                      return `
                        <div class="fridge-shelf ${shelf?.is_floor ? 'floor' : ''} ${active ? 'active' : ''}"${shelfClick}>
                          <div class="fridge-shelf-name">${escapeHtml(shelf.name || (shelf.is_floor ? 'Bodem' : `Plank ${shelfIndex + 1}`))}</div>
                          <div class="fridge-shelf-track" style="--slot-count:${facings};--shelf-height:${shelfHeight}px">
                            <div class="fridge-shelf-products">
                              ${slots.map((slot, slotIndex) => {
                                const filled = !!(slot.product_name || slot.product_id || slot.image_url);
                                const label = slot.product_name || '';
                                const isSelectedSlot = !readonly && target && target.coolerIndex === coolerIndex && target.shelfIndex === shelfIndex && target.slotIndex === slotIndex;
                                const resolvedImage = getResolvedSlotImage(slot);
                                const thumb = resolvedImage
                                  ? `<div class="fridge-item-thumb"><img src="${escapeHtml(resolvedImage)}" alt="${escapeHtml(label || 'Product')}"></div>`
                                  : `<div class="fridge-item-thumb">${filled ? `<span class="fridge-item-pill">${escapeHtml((label || '•').slice(0,2).toUpperCase())}</span>` : ''}</div>`;
                                if(readonly){
                                  return `<div class="fridge-item ${filled ? '' : 'empty'}" aria-hidden="true">${thumb}</div>`;
                                }
                                return `<button type="button" class="fridge-item ${filled ? '' : 'empty'} ${isSelectedSlot ? 'selected' : ''}" onclick="event.stopPropagation(); selectBarLayoutShelf(${unitIndex}, ${coolerIndex}, ${shelfIndex}, ${slotIndex})" aria-label="Plek ${slotIndex + 1}">${thumb}</button>`;
                              }).join('')}
                            </div>
                          </div>
                          <div class="fridge-shelf-beam"></div>
                        </div>
                      `;
                    }).join('')}
                  </div>
                </div>
              </div>
              <div class="fridge-base"></div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

function openBarLayoutModal(layoutId=null){
    if(!canManageBarLayouts()){ toast('Je mag indelingen niet aanpassen.', 'error'); return; }
    const items = safeArray(appData.bar_layouts?.items).map(normalizeClientBarLayout);
    const item = layoutId ? (items.find(entry => entry.id === layoutId) || {}) : {};
    openModal(
      layoutId ? 'Indeling bewerken' : 'Nieuwe indeling',
      'Sla hier een event- of standaardindeling op. Daarna kun je hem openen in de visuele koelkast-editor.',
      `
        <div class="field"><label>Naam indeling</label><input id="barLayoutName" value="${escapeHtml(item.name || '')}" placeholder="Bijv. Koningsdag"></div>
        <div class="field"><label>Korte notitie</label><input id="barLayoutNote" value="${escapeHtml(item.note || '')}" placeholder="Bijv. Buitenbar + extra bier vooraan"></div>
        <div class="form-actions">
          <button class="btn" onclick="closeModal()">Annuleren</button>
          <button class="btn accent" onclick="saveBarLayout('${layoutId || ''}')">Opslaan</button>
        </div>
      `
    );
  }

  async function saveBarLayout(layoutId=''){
    if(!canManageBarLayouts()){ toast('Je mag indelingen niet aanpassen.', 'error'); return; }
    try{
      const name = (document.getElementById('barLayoutName')?.value || '').trim();
      const note = (document.getElementById('barLayoutNote')?.value || '').trim();
      await postJSON('/api/manage/bar-layout-save', {
        layout_id: layoutId || null,
        name,
        note
      });
      closeModal();
      await loadData();
      const items = safeArray(appData.bar_layouts?.items).map(normalizeClientBarLayout);
      if (layoutId){
        currentBarLayoutId = layoutId;
      } else {
        const match = items.find(item => (item.name || '').trim().toLowerCase() === name.toLowerCase());
        currentBarLayoutId = match?.id || currentBarLayoutId;
      }
      window.currentBarLayoutId = currentBarLayoutId;
      openPage('bar-indeling');
      toast('Indeling opgeslagen');
    }catch(err){
      toast(err.message, 'error');
    }
  }

  async function setActiveBarLayout(layoutId){
    if(!canManageBarLayouts()){ toast('Je mag indelingen niet aanpassen.', 'error'); return; }
    try{
      await postJSON('/api/manage/bar-layout-set-active', { layout_id: layoutId });
      await loadData();
      currentBarLayoutId = layoutId;
      openPage('bar-indeling');
      toast('Actieve indeling aangepast');
    }catch(err){
      toast(err.message, 'error');
    }
  }

  async function deleteBarLayout(layoutId){
    if(!canManageBarLayouts()){ toast('Je mag indelingen niet aanpassen.', 'error'); return; }
    try{
      await postJSON('/api/manage/bar-layout-delete', { layout_id: layoutId });
      await loadData();
      openPage('bar-indeling');
      toast('Indeling verwijderd');
    }catch(err){
      toast(err.message, 'error');
    }
  }

  function getBarProductOptions(){
    const products = [];
    const seen = new Set();
    safeArray(appData.bar?.koelingen).forEach(koeling => {
      safeArray(koeling?.producten).forEach(product => {
        const id = String(product?.id || slugifyText(product?.naam || '') || '').trim();
        const name = String(product?.naam || '').trim();
        if(!name) return;
        const key = `${id}__${name.toLowerCase()}`;
        if(seen.has(key)) return;
        seen.add(key);
        products.push({
          id,
          name,
          image_url: product?.image_url || product?.image || product?.photo || product?.thumb || ''
        });
      });
    });
    return products.sort((a,b) => a.name.localeCompare(b.name, 'nl'));
  }


  function getBarProductImageByRef(productId='', productName=''){
    const id = String(productId || '').trim();
    const name = String(productName || '').trim().toLowerCase();
    const products = getBarProductOptions();
    const byId = id ? products.find(item => item.id === id && item.image_url) : null;
    if(byId?.image_url) return byId.image_url;
    const byName = name ? products.find(item => item.name.trim().toLowerCase() === name && item.image_url) : null;
    return byName?.image_url || '';
  }

  function getResolvedSlotImage(slot){
    return String(slot?.image_url || getBarProductImageByRef(slot?.product_id, slot?.product_name) || '').trim();
  }

  function slugifyText(value=''){
    return String(value || '').toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/^_+|_+$/g,'') || 'item';
  }


  function getBarLayoutPanelRoots(){
    const roots = [];
    if(isBarLayoutMobile()){
      const mobileBody = document.getElementById('barLayoutShelfMobileBody');
      const mobileSheet = document.getElementById('barLayoutShelfMobile');
      if(mobileBody) roots.push(mobileBody);
      if(mobileSheet) roots.push(mobileSheet);
    }
    const panel = document.getElementById('barLayoutShelfPanel');
    if(panel) roots.push(panel);
    return roots;
  }

  function getBarLayoutPanelField(id){
    for(const root of getBarLayoutPanelRoots()){
      const match = root?.querySelector?.(`#${id}`);
      if(match) return match;
    }
    return document.getElementById(id);
  }

  function getBarLayoutPanelValue(id, fallback=''){
    const field = getBarLayoutPanelField(id);
    return field ? field.value : fallback;
  }

  function setBarLayoutDirtyState(isDirty){
    window.barLayoutDirty = !!isDirty;
    const dirty = !!window.barLayoutDirty;
    const label = dirty ? 'Indeling opslaan *' : 'Indeling opslaan';
    ['barLayoutBottomSaveBtn'].forEach(id => {
      const btn = document.getElementById(id);
      if(btn) btn.textContent = label;
    });
    refreshBarLayoutMobileSaveLabel();
    document.querySelectorAll('.fridge-editor-btn.primary[onclick="saveCurrentBarLayoutStructure()"]')?.forEach?.(btn => {
      btn.textContent = dirty ? 'Opslaan *' : 'Opslaan';
    });
  }

  function refreshBarLayoutMobileSaveLabel(){
    const btn = document.getElementById('barLayoutMobileSaveBtn');
    if(!btn) return;
    btn.textContent = 'Plank opslaan';
  }


  function updateSelectedBarLayout(mutator){
    const items = safeArray(appData.bar_layouts?.items);
    const index = items.findIndex(item => item.id === currentBarLayoutId);
    if(index < 0) return null;
    const clone = JSON.parse(JSON.stringify(normalizeClientBarLayout(items[index])));
    mutator(clone);
    items[index] = clone;
    appData.bar_layouts.items = items;
    setBarLayoutDirtyState(true);
    return clone;
  }

  
  function getSelectedEditorUnitIndex(layout){
    const total = safeArray(layout?.units).length || 0;
    if(!total) return 0;
    if(typeof window.currentBarLayoutUnitIndex !== 'number') window.currentBarLayoutUnitIndex = 0;
    if(window.currentBarLayoutUnitIndex < 0) window.currentBarLayoutUnitIndex = 0;
    if(window.currentBarLayoutUnitIndex >= total) window.currentBarLayoutUnitIndex = total - 1;
    return window.currentBarLayoutUnitIndex;
  }

  function ensureSelectedShelf(layout){
    const unitIndex = getSelectedEditorUnitIndex(layout);
    const unit = safeArray(layout?.units)[unitIndex] || null;
    const defaultTarget = { unitIndex, coolerIndex: 0, shelfIndex: 0, slotIndex: 0 };
    if(!unit){
      window.currentBarLayoutShelfTarget = defaultTarget;
      return defaultTarget;
    }
    const target = window.currentBarLayoutShelfTarget || defaultTarget;
    const coolerCount = safeArray(unit.coolers).length || 1;
    const coolerIndex = Math.min(Math.max(Number(target.coolerIndex || 0), 0), coolerCount - 1);
    const shelfCount = safeArray(unit.coolers[coolerIndex]?.shelves).length || 1;
    const shelfIndex = Math.min(Math.max(Number(target.shelfIndex || 0), 0), shelfCount - 1);
    const shelf = unit.coolers[coolerIndex]?.shelves?.[shelfIndex] || { slots: [] };
    const slotCount = safeArray(shelf.slots).length || 9;
    const slotIndex = Math.min(Math.max(Number(target.slotIndex || 0), 0), slotCount - 1);
    const normalized = { unitIndex, coolerIndex, shelfIndex, slotIndex };
    window.currentBarLayoutShelfTarget = normalized;
    return normalized;
  }

  
  function isBarLayoutMobile(){
    return window.matchMedia('(max-width: 900px)').matches;
  }

  function closeBarLayoutMobileSheet(){
    document.getElementById('barLayoutShelfMobile')?.classList.remove('open');
    document.getElementById('barLayoutShelfMobileBackdrop')?.classList.remove('open');
    document.body.classList.remove('bar-layout-mobile-sheet-open');
  }

  function openBarLayoutMobileSheet(){
    document.getElementById('barLayoutShelfMobile')?.classList.add('open');
    document.getElementById('barLayoutShelfMobileBackdrop')?.classList.add('open');
    document.body.classList.add('bar-layout-mobile-sheet-open');
  }

  function syncBarLayoutMobileSheet(html='', meta=null){
    const body = document.getElementById('barLayoutShelfMobileBody');
    const title = document.getElementById('barLayoutShelfMobileTitle');
    const sub = document.getElementById('barLayoutShelfMobileSub');
    if(!body) return;
    body.innerHTML = html || '<div class="fridge-editor-empty">Tik op een plank om hem op telefoon te bewerken.</div>';
    if(title) title.textContent = meta?.title || 'Plank aanpassen';
    if(sub) sub.textContent = meta?.sub || 'Tik op een plank om hem op telefoon te bewerken.';
    if(isBarLayoutMobile() && html){
      openBarLayoutMobileSheet();
    }else if(!isBarLayoutMobile()){
      closeBarLayoutMobileSheet();
    }
  }

  function saveCurrentBarLayoutMobileSelection(){
    if(!canManageBarLayouts()){ toast('Je mag indelingen niet aanpassen.', 'error'); return; }
    const target = window.currentBarLayoutShelfTarget;
    if(!target){
      closeBarLayoutMobileSheet();
      return;
    }
    applyBarShelfSettings(target.unitIndex, target.coolerIndex, target.shelfIndex);
    toast('Plankinstellingen bijgewerkt');
    refreshBarLayoutMobileSaveLabel();
  }

function openBarLayoutEditor(layoutId=null){
    if(!canManageBarLayouts()){ toast('Je mag indelingen alleen bekijken.', 'error'); openBarLayoutView(layoutId || currentBarLayoutId); return; }
    if(layoutId) currentBarLayoutId = layoutId;
    window.currentBarLayoutId = currentBarLayoutId;
    window.currentBarLayoutShelfTarget = null;
    closeBarLayoutMobileSheet();
    setBarLayoutDirtyState(false);
        openPage('bar-indeling-editor');
    renderBarLayoutEditor();
  }

  function changeBarLayoutEditorUnit(value){
    window.currentBarLayoutUnitIndex = Number(value || 0);
    window.currentBarLayoutShelfTarget = null;
    closeBarLayoutMobileSheet();
        renderBarLayoutEditor();
  }
  function requestRemoveBarLayoutUnit(){
    if(!canManageBarLayouts()){ toast('Je mag indelingen niet aanpassen.', 'error'); return; }
    const layout = getSelectedBarLayout();
    const unitIndex = getSelectedEditorUnitIndex(layout);
    if(!layout || safeArray(layout.units).length <= 1){
      toast('Er moet minimaal 1 unit overblijven.', 'error');
      return;
    }
    const unitName = layout.units?.[unitIndex]?.name || `GB${unitIndex + 1}`;
    confirmAction('Unit verwijderen',`Weet je zeker dat je ${escapeHtml(unitName)} wilt verwijderen?`,'Verwijderen', 'doConfirmed(\'confirmRemoveBarLayoutUnit\')');
  }

  function confirmRemoveBarLayoutUnit(){
    if(!canManageBarLayouts()){ toast('Je mag indelingen niet aanpassen.', 'error'); return; }
    const layout = getSelectedBarLayout();
    const unitIndex = getSelectedEditorUnitIndex(layout);
    if(!layout || safeArray(layout.units).length <= 1){
      toast('Er moet minimaal 1 unit overblijven.', 'error');
      return;
    }
    updateSelectedBarLayout(current => {
      current.units.splice(unitIndex, 1);
      current.units = safeArray(current.units).map((unit, index) => ({
        ...unit,
        id: unit?.id || `unit_${index + 1}`,
        name: (unit?.name || `GB${index + 1}`).trim() || `GB${index + 1}`
      }));
    });
    window.currentBarLayoutUnitIndex = Math.max(0, Math.min(unitIndex, safeArray(getSelectedBarLayout()?.units).length - 1));
    window.currentBarLayoutShelfTarget = null;
    renderBarLayoutEditor();
  }


  function openBarLayoutView(layoutId=null){
    if(layoutId) currentBarLayoutId = layoutId;
    window.currentBarLayoutId = currentBarLayoutId;
    openPage('bar-indeling-view');
    renderBarLayoutReadonlyView();
  }

  function renameBarUnit(unitIndex, value){
    updateSelectedBarLayout(layout => {
      layout.units[unitIndex].name = String(value || '').trim() || `GB${unitIndex + 1}`;
    });
    renderBarLayoutEditor();
  }

  function renameBarCooler(unitIndex, coolerIndex, value){
    updateSelectedBarLayout(layout => {
      layout.units[unitIndex].coolers[coolerIndex].name = String(value || '').trim() || `Koelkast ${coolerIndex + 1}`;
    });
    renderBarLayoutEditor();
  }

  function getShelfHeightPx(height){
    const key = String(height || 'medium').toLowerCase();
    const isMobileViewport = typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(max-width: 900px)').matches;
    if(isMobileViewport){
      if(key === 'low') return 42;
      if(key === 'high') return 62;
      if(key === 'wine') return 72;
      return 52;
    }
    if(key === 'low') return 74;
    if(key === 'high') return 112;
    if(key === 'wine') return 132;
    return 92;
  }

  function normalizeShelfShape(shelf){
    const facings = Math.max(1, Math.min(Number(shelf?.facings || shelf?.slots_per_shelf || shelf?.slot_count || 9) || 9, 9));
    shelf.facings = facings;
    const defaultHeight = shelf?.is_floor ? 'low' : 'medium';
    shelf.height = ["low","medium","high","wine"].includes(String(shelf?.height || defaultHeight)) ? String(shelf.height || defaultHeight) : defaultHeight;
    shelf.slots = safeArray(shelf?.slots).slice(0, facings);
    while(shelf.slots.length < facings) shelf.slots.push(defaultClientBarSlot(shelf.slots.length + 1));
    return shelf;
  }

  function getPreferredShelfSlotIndex(shelf){
    const slots = safeArray(shelf?.slots).slice(0,9);
    const firstEmpty = slots.findIndex(slot => !(slot && (slot.product_name || slot.product_id || slot.image_url)));
    return firstEmpty >= 0 ? firstEmpty : 0;
  }

  function selectBarLayoutShelf(unitIndex, coolerIndex, shelfIndex, slotIndex=0){
    window.currentBarLayoutShelfTarget = { unitIndex, coolerIndex, shelfIndex, slotIndex };
        renderBarLayoutEditor();
    if(isBarLayoutMobile()) openBarLayoutMobileSheet();
  }

  function setBarShelfSlotProduct(unitIndex, coolerIndex, shelfIndex, slotIndex, productId){
    const product = getBarProductOptions().find(item => item.id === productId) || null;
    updateSelectedBarLayout(layout => {
      const slots = layout.units[unitIndex].coolers[coolerIndex].shelves[shelfIndex].slots;
      slots[slotIndex] = slots[slotIndex] || defaultClientBarSlot(slotIndex + 1);
      const slot = slots[slotIndex];
      slot.product_id = product ? product.id : '';
      slot.product_name = product ? product.name : '';
      slot.image_url = product ? (product.image_url || getBarProductImageByRef(product.id, product.name) || '') : '';
    });
    renderBarLayoutEditor();
  }

  function clearBarShelfSlot(unitIndex, coolerIndex, shelfIndex, slotIndex){
    updateSelectedBarLayout(layout => {
      layout.units[unitIndex].coolers[coolerIndex].shelves[shelfIndex].slots[slotIndex] = defaultClientBarSlot(slotIndex + 1);
    });
    renderBarLayoutEditor();
  }

  function setBarShelfSlotImage(unitIndex, coolerIndex, shelfIndex, slotIndex, value){
    updateSelectedBarLayout(layout => {
      layout.units[unitIndex].coolers[coolerIndex].shelves[shelfIndex].slots[slotIndex].image_url = String(value || '').trim();
    });
    renderBarLayoutEditor();
  }

  function setBarShelfSlotName(unitIndex, coolerIndex, shelfIndex, slotIndex, value){
    updateSelectedBarLayout(layout => {
      layout.units[unitIndex].coolers[coolerIndex].shelves[shelfIndex].slots[slotIndex].product_name = String(value || '').trim();
    });
    renderBarLayoutEditor();
  }

  function setBarShelfSlotNote(unitIndex, coolerIndex, shelfIndex, slotIndex, value){
    updateSelectedBarLayout(layout => {
      const slots = layout.units[unitIndex].coolers[coolerIndex].shelves[shelfIndex].slots;
      slots[slotIndex] = slots[slotIndex] || defaultClientBarSlot(slotIndex + 1);
      slots[slotIndex].note = String(value || '').trim();
    });
    renderBarLayoutEditor();
  }

  function applyBarShelfFacing(unitIndex, coolerIndex, shelfIndex, facingCount){
    const productId = document.getElementById('barShelfSelectedProduct')?.value || '';
    const manualName = (document.getElementById('barShelfManualName')?.value || '').trim();
    const manualNote = (document.getElementById('barShelfManualNote')?.value || '').trim();
    const selectedProduct = getBarProductOptions().find(item => item.id === productId) || null;
    const shelfCap = Math.max(1, Math.min(Number(getSelectedBarLayout()?.units?.[unitIndex]?.coolers?.[coolerIndex]?.shelves?.[shelfIndex]?.facings || 9) || 9, 9));
    const startSlot = Math.max(0, Math.min(Number(window.currentBarLayoutShelfTarget?.slotIndex || 0), shelfCap - 1));
    updateSelectedBarLayout(layout => {
      const shelf = layout.units[unitIndex].coolers[coolerIndex].shelves[shelfIndex];
      normalizeShelfShape(shelf);
      for(let offset = 0; offset < facingCount; offset += 1){
        const index = startSlot + offset;
        if(index > shelfCap - 1) break;
        shelf.slots[index] = shelf.slots[index] || defaultClientBarSlot(index + 1);
        shelf.slots[index].product_id = selectedProduct ? selectedProduct.id : '';
        shelf.slots[index].product_name = manualName || (selectedProduct ? selectedProduct.name : '');
        shelf.slots[index].image_url = selectedProduct ? (selectedProduct.image_url || getBarProductImageByRef(selectedProduct.id, selectedProduct.name) || '') : '';
        shelf.slots[index].note = manualNote;
      }
    });
    window.currentBarLayoutShelfTarget = { unitIndex, coolerIndex, shelfIndex, slotIndex: startSlot };
    renderBarLayoutEditor();
  }

  function renderBarLayoutShelfPanel(layout, target){
    const panel = document.getElementById('barLayoutShelfPanel');
    if(!panel) return;
    if(!layout){
      const emptyHtml = `<div class="fridge-editor-empty">Selecteer een indeling om de editor te gebruiken.</div>`;
      panel.innerHTML = emptyHtml;
      syncBarLayoutMobileSheet('', null);
      return;
    }
    if(!target){
      const emptyHtml = `<div class="fridge-editor-empty">Tik op een plank om op telefoon direct product, facings en plankinstellingen te openen.</div>`;
      panel.innerHTML = emptyHtml;
      syncBarLayoutMobileSheet('', null);
      return;
    }
    const unit = layout?.units?.[target.unitIndex];
    const cooler = unit?.coolers?.[target.coolerIndex];
    const shelf = cooler?.shelves?.[target.shelfIndex];
    if(!unit || !cooler || !shelf){
      const emptyHtml = `<div class="fridge-editor-empty">Selecteer een plank in de editor om product, facings en instellingen te openen.</div>`;
      panel.innerHTML = emptyHtml;
      syncBarLayoutMobileSheet('', null);
      return;
    }
    const selectedSlot = safeArray(shelf.slots)[target.slotIndex] || defaultClientBarSlot(target.slotIndex + 1);
    const options = getBarProductOptions();
    const selectedProductId = selectedSlot.product_id || '';
    const selectedProduct = options.find(opt => opt.id === selectedProductId) || null;
    const maxFacings = Math.max(1, Math.min(Number(shelf.facings || 9) || 9, 9));
    const activeFacingCount = Math.max(1, Math.min(Number(getBarLayoutPanelValue('barShelfFacingCount', 1) || 1) || 1, maxFacings));
    const panelHtml = `
      <h3>${escapeHtml(unit.name || `GB${target.unitIndex + 1}`)} · ${escapeHtml(cooler.name || `Koelkast ${target.coolerIndex + 1}`)}</h3>
      <p>${escapeHtml(shelf.name || (shelf.is_floor ? 'Bodem' : `Plank ${target.shelfIndex + 1}`))} · plek ${target.slotIndex + 1}</p>
      <div class="fridge-panel-section">
        <div class="fridge-panel-section-top">
          <div class="fridge-panel-section-title">Plank instellingen</div>
        </div>
        <div class="fridge-panel-grid">
          <div class="fridge-panel-block">
            <div class="fridge-panel-label">Unitnaam</div>
            <input id="barUnitNameInput" value="${escapeHtml(unit.name || `GB${target.unitIndex + 1}`)}" placeholder="Bijv. GB1">
          </div>
          <div class="fridge-panel-block">
            <div class="fridge-panel-label">Naam koelkastje</div>
            <input id="barCoolerNameInput" value="${escapeHtml(cooler.name || `Koelkast ${target.coolerIndex + 1}`)}" placeholder="Bijv. Wijn links">
          </div>
          <div class="fridge-panel-block">
            <div class="fridge-panel-label">Planknaam</div>
            <input id="barShelfNameInput" value="${escapeHtml(shelf.name || (shelf.is_floor ? 'Bodem' : `Plank ${target.shelfIndex + 1}`))}" placeholder="Bijv. Wijn boven">
          </div>
          <div class="fridge-panel-block">
            <div class="fridge-panel-label">Plankhoogte</div>
            <select id="barShelfHeightInput">
              <option value="low" ${String(shelf.height||'medium') === 'low' ? 'selected' : ''}>Laag</option>
              <option value="medium" ${String(shelf.height||'medium') === 'medium' ? 'selected' : ''}>Normaal</option>
              <option value="high" ${String(shelf.height||'medium') === 'high' ? 'selected' : ''}>Hoog</option>
              <option value="wine" ${String(shelf.height||'medium') === 'wine' ? 'selected' : ''}>Wijn / extra hoog</option>
            </select>
          </div>
          <div class="fridge-panel-block">
            <div class="fridge-panel-label">Aantal vakken op deze plank</div>
            <select id="barShelfFacingsInput">
              ${Array.from({length:9}, (_,i) => `<option value="${i+1}" ${maxFacings === (i+1) ? 'selected' : ''}>${i+1} van max 9</option>`).join('')}
            </select>
          </div>
        </div>
        <div class="fridge-panel-inline-actions fridge-panel-inline-actions--simple">
          <button class="fridge-inline-accent" onclick="addBarShelf(${target.unitIndex}, ${target.coolerIndex}, ${target.shelfIndex})">+ Plank toevoegen</button>
          <button class="fridge-inline-danger" onclick="requestRemoveBarShelf(${target.unitIndex}, ${target.coolerIndex}, ${target.shelfIndex})">${shelf.is_floor ? 'Verwijder bodem' : 'Verwijder plank'}</button>
          <button class="fridge-panel-save" onclick="applyBarShelfSettings(${target.unitIndex}, ${target.coolerIndex}, ${target.shelfIndex})">Wijzigingen opslaan</button>
        </div>
      </div>
      <div class="fridge-panel-block">
        <div class="fridge-panel-label">Product voor geselecteerde plek</div>
        <select id="barShelfSelectedProduct" onchange="setBarShelfSlotProduct(${target.unitIndex}, ${target.coolerIndex}, ${target.shelfIndex}, ${target.slotIndex}, this.value)">
          <option value="">Handmatig invullen</option>
          ${options.map(opt => `<option value="${escapeHtml(opt.id)}" ${opt.id === selectedProductId ? 'selected' : ''}>${escapeHtml(opt.name)}</option>`).join('')}
        </select>
      </div>
      <div class="fridge-panel-block">
        <div class="fridge-panel-label">Naam / label (optioneel)</div>
        <input id="barShelfManualName" value="${escapeHtml(selectedSlot.product_name || '')}" onchange="setBarShelfSlotName(${target.unitIndex}, ${target.coolerIndex}, ${target.shelfIndex}, ${target.slotIndex}, this.value)" placeholder="Bijv. Corona Extra">
      </div>
      <div class="fridge-panel-block">
        <div class="fridge-panel-label">Notitie (optioneel)</div>
        <input id="barShelfManualNote" value="${escapeHtml(selectedSlot.note || '')}" onchange="setBarShelfSlotNote(${target.unitIndex}, ${target.coolerIndex}, ${target.shelfIndex}, ${target.slotIndex}, this.value)" placeholder="Bijv. hardloper vooraan">
        <div class="fridge-panel-inline-actions">
          <button class="fridge-inline-danger" onclick="clearBarShelfSlot(${target.unitIndex}, ${target.coolerIndex}, ${target.shelfIndex}, ${target.slotIndex})">Maak geselecteerde plek leeg</button>
        </div>
      </div>
      <div class="fridge-panel-block">
        <div class="fridge-panel-label">Aantal facings vanaf geselecteerde plek</div>
        <div class="fridge-facing-grid">
          ${Array.from({length:maxFacings}, (_,i) => `<button class="fridge-facing-btn ${activeFacingCount === (i+1) ? 'active' : ''}" onclick="applyBarShelfFacing(${target.unitIndex}, ${target.coolerIndex}, ${target.shelfIndex}, ${i+1})">${i+1}</button>`).join('')}
        </div>
      </div>
      <div class="fridge-panel-block">
        <div class="fridge-panel-label">Plekken op deze plank</div>
        <div class="fridge-product-preview">
          ${safeArray(shelf.slots).slice(0,maxFacings).map((slot, index) => {
            const active = index === target.slotIndex;
            const resolvedImage = getResolvedSlotImage(slot);
            const thumb = resolvedImage ? `<img src="${escapeHtml(resolvedImage)}" alt="${escapeHtml(slot.product_name || slot.label || '')}">` : `<span>${escapeHtml((slot.product_name || slot.label || 'Vak').slice(0,2).toUpperCase())}</span>`;
            return `<button class="fridge-preview-card ${active ? 'active' : ''}" onclick="selectBarLayoutShelf(${target.unitIndex}, ${target.coolerIndex}, ${target.shelfIndex}, ${index})">
              <div class="fridge-preview-thumb">${thumb}</div>
              <div class="fridge-preview-name">${escapeHtml(slot.product_name || `Vak ${index + 1}`)}</div>
            </button>`;
          }).join('')}
        </div>
      </div>
      <div class="fridge-editor-note">Klik links op een plank of plek. Op telefoon opent onderin direct een slimme editor, zodat je niet meer hoeft te scrollen door één lange pagina.</div>
    `;
    panel.innerHTML = panelHtml;
    const mobileTitle = `${escapeHtml(unit.name || `GB${target.unitIndex + 1}`)} · ${escapeHtml(cooler.name || `Koelkast ${target.coolerIndex + 1}`)}`;
    const mobileSub = `${escapeHtml(shelf.name || (shelf.is_floor ? 'Bodem' : `Plank ${target.shelfIndex + 1}`))} · plek ${target.slotIndex + 1}`;
    syncBarLayoutMobileSheet(panelHtml, { title: mobileTitle, sub: mobileSub });
  }

  function applyBarShelfSettings(unitIndex, coolerIndex, shelfIndex){
    const unitName = String(getBarLayoutPanelValue('barUnitNameInput', '') || '').trim();
    const coolerName = String(getBarLayoutPanelValue('barCoolerNameInput', '') || '').trim();
    const shelfName = String(getBarLayoutPanelValue('barShelfNameInput', '') || '').trim();
    const height = String(getBarLayoutPanelValue('barShelfHeightInput', 'medium') || 'medium').trim();
    const facings = Math.max(1, Math.min(Number(getBarLayoutPanelValue('barShelfFacingsInput', 9) || 9) || 9, 9));
    updateSelectedBarLayout(layout => {
      const unit = layout.units[unitIndex];
      const cooler = unit.coolers[coolerIndex];
      const shelf = cooler.shelves[shelfIndex];
      unit.name = unitName || `GB${unitIndex + 1}`;
      cooler.name = coolerName || `Koelkast ${coolerIndex + 1}`;
      shelf.name = shelfName || (shelf.is_floor ? 'Bodem' : `Plank ${shelfIndex + 1}`);
      shelf.height = ['low','medium','high','wine'].includes(height) ? height : (shelf.is_floor ? 'low' : 'medium');
      shelf.facings = Math.max(1, Math.min(facings, 9));
      normalizeShelfShape(shelf);
      const floorShelf = cooler.shelves.find(entry => entry?.is_floor);
      if(floorShelf){
        floorShelf.facings = Math.max(1, Math.min(Number(floorShelf.facings || 9) || 9, 9));
        normalizeShelfShape(floorShelf);
      }
    });
    const nextSlot = Math.min(Number(window.currentBarLayoutShelfTarget?.slotIndex || 0), facings - 1);
    window.currentBarLayoutShelfTarget = { unitIndex, coolerIndex, shelfIndex, slotIndex: nextSlot };
    window.barShelfSettingsExpanded = false;
    renderBarLayoutEditor();
  }

  function setBarShelfHeight(unitIndex, coolerIndex, shelfIndex, value){
    const allowed = ['low','medium','high','wine'];
    updateSelectedBarLayout(layout => {
      const shelf = layout.units[unitIndex].coolers[coolerIndex].shelves[shelfIndex];
      shelf.height = allowed.includes(String(value || '').toLowerCase()) ? String(value).toLowerCase() : 'medium';
      normalizeShelfShape(shelf);
    });
    renderBarLayoutEditor();
  }

  function setBarShelfFacings(unitIndex, coolerIndex, shelfIndex, value){
    const facings = Math.max(1, Math.min(Number(value || 9) || 9, 9));
    updateSelectedBarLayout(layout => {
      const shelf = layout.units[unitIndex].coolers[coolerIndex].shelves[shelfIndex];
      shelf.facings = facings;
      normalizeShelfShape(shelf);
    });
    const nextSlot = Math.min(Number(window.currentBarLayoutShelfTarget?.slotIndex || 0), facings - 1);
    window.currentBarLayoutShelfTarget = { unitIndex, coolerIndex, shelfIndex, slotIndex: nextSlot };
    renderBarLayoutEditor();
  }

  function renameBarShelf(unitIndex, coolerIndex, shelfIndex, value){
    updateSelectedBarLayout(layout => {
      layout.units[unitIndex].coolers[coolerIndex].shelves[shelfIndex].name = String(value || '').trim() || `Plank ${shelfIndex + 1}`;
    });
    renderBarLayoutEditor();
  }

  function requestRemoveBarShelf(unitIndex, coolerIndex, shelfIndex){
    const selected = getSelectedBarLayout();
    const cooler = selected?.units?.[unitIndex]?.coolers?.[coolerIndex];
    if(!cooler) return;
    const shelves = safeArray(cooler.shelves);
    if(shelves.length <= 1){
      toast('Elke koelkast moet minstens 1 rij houden.', 'error');
      return;
    }
    const label = shelves[shelfIndex]?.is_floor ? 'bodem' : 'plank';
    confirmAction('Rij verwijderen',`Weet je zeker dat je deze ${label} wilt verwijderen?`,'Verwijderen', `doConfirmed('confirmRemoveBarShelf', ${unitIndex}, ${coolerIndex}, ${shelfIndex})`);
  }

  function confirmRemoveBarShelf(unitIndex, coolerIndex, shelfIndex){
    return removeBarShelf(unitIndex, coolerIndex, shelfIndex);
  }

  function addBarShelf(unitIndex, coolerIndex, shelfIndex){
    updateSelectedBarLayout(layout => {
      const cooler = layout.units[unitIndex].coolers[coolerIndex];
      let shelves = safeArray(cooler.shelves).map(shelf => normalizeShelfShape({ ...(shelf || {}) }));
      const floorIndex = shelves.findIndex(shelf => shelf?.is_floor);
      const insertAt = Math.max(0, Math.min(Number(shelfIndex || 0) + 1, floorIndex >= 0 ? floorIndex : shelves.length));
      const newShelfNumber = shelves.filter(shelf => !shelf?.is_floor).length + 1;
      shelves.splice(insertAt, 0, normalizeShelfShape({
        ...defaultClientBarShelf(newShelfNumber),
        id: `shelf_${Date.now()}`,
        name: `Plank ${newShelfNumber}`,
        facings: 9,
        height: 'medium',
        is_floor: false,
        slots: Array.from({length:9}, (_, idx) => defaultClientBarSlot(idx + 1))}));
      const floorShelf = shelves.find(shelf => shelf?.is_floor);
      const topShelves = shelves.filter(shelf => !shelf?.is_floor).map((shelf, idx) => ({
        ...shelf,
        id: shelf?.id || `shelf_${idx + 1}`,
        name: (shelf?.name || '').trim() || `Plank ${idx + 1}`,
        is_floor: false}));
      cooler.shelves = floorShelf ? [...topShelves, normalizeShelfShape({ ...floorShelf, is_floor: true, name: (floorShelf?.name || 'Bodem').trim() || 'Bodem', facings: Math.max(1, Math.min(Number(floorShelf?.facings || 9) || 9, 9)) })] : topShelves;
    });
    window.currentBarLayoutShelfTarget = { unitIndex, coolerIndex, shelfIndex: Number(shelfIndex || 0) + 1, slotIndex: 0 };
    renderBarLayoutEditor();
  }

  function removeBarShelf(unitIndex, coolerIndex, shelfIndex){
    const selected = getSelectedBarLayout();
    const cooler = selected?.units?.[unitIndex]?.coolers?.[coolerIndex];
    if(!cooler) return;
    const shelves = safeArray(cooler.shelves);
    if(shelves.length <= 1){
      toast('Elke koelkast moet minstens 1 rij houden.', 'error');
      return;
    }
    updateSelectedBarLayout(layout => {
      const targetCooler = layout.units[unitIndex].coolers[coolerIndex];
      targetCooler.shelves.splice(shelfIndex, 1);
      targetCooler.shelves = safeArray(targetCooler.shelves).map((shelf, index) => {
        const facings = Math.max(1, Math.min(Number(shelf?.facings || 9) || 9, 9));
        const slots = safeArray(shelf?.slots).slice(0, facings).map((slot, slotIndex) => ({
          ...defaultClientBarSlot(slotIndex + 1),
          ...(slot || {}),
          facing: slotIndex + 1}));
        while(slots.length < facings) slots.push(defaultClientBarSlot(slots.length + 1));
        return {
          ...shelf,
          id: shelf?.id || `shelf_${index + 1}`,
          name: (shelf?.name || '').trim() || (shelf?.is_floor ? 'Bodem' : `Plank ${index + 1}`),
          facings,
          height: shelf?.is_floor ? 'low' : (['low','medium','high','wine'].includes(String(shelf?.height || 'medium')) ? String(shelf.height || 'medium') : 'medium'),
          is_floor: Boolean(shelf?.is_floor),
          slots};
      });
    });
    const freshShelves = safeArray(getSelectedBarLayout()?.units?.[unitIndex]?.coolers?.[coolerIndex]?.shelves);
    const nextIndex = Math.max(0, Math.min(shelfIndex - 1, freshShelves.length - 1));
    window.currentBarLayoutShelfTarget = { unitIndex, coolerIndex, shelfIndex: nextIndex, slotIndex: 0 };
    renderBarLayoutEditor();
  }

  function renderBarLayoutEditor(){
    if(!canManageBarLayouts()){ openPage('bar-indeling-view'); return; }
    const layout = getSelectedBarLayout();
    const legacyWrap = document.getElementById('barLayoutEditor');
    if(legacyWrap){
      legacyWrap.innerHTML = layout ? `<div class="layout-editor-empty">Gebruik hieronder de kijkmodus. Open pas de editor als je echt iets wilt wijzigen.</div>` : `<div class="layout-editor-empty">Maak eerst een indeling aan. Daarna kun je hem fullscreen openen.</div>`;
    }
    const stage = document.getElementById('barLayoutFridgeStage');
    const title = document.getElementById('fridgeEditorTitle');
    const unitSelect = document.getElementById('fridgeEditorUnitSelect');
    const activeBadge = document.getElementById('fridgeEditorActiveBadge');
    if(!stage) return;
    if(!layout){
      stage.innerHTML = `<div class="fridge-editor-empty">Maak eerst een indeling aan vanuit het overzicht. Daarna kun je hier de 3 koelkastjes per unit visueel invullen.</div>`;
      renderBarLayoutShelfPanel(null, null);
      if(title) title.textContent = 'Indeling editor';
      if(unitSelect) unitSelect.innerHTML = '';
      return;
    }
    const unitIndex = getSelectedEditorUnitIndex(layout);
    const target = ensureSelectedShelf(layout);
    const unit = layout.units[unitIndex] || layout.units[0];
    if(title) title.textContent = `Indeling editor · ${layout.name || 'Indeling'} · ${unit?.name || ''}`;
    if(activeBadge) activeBadge.textContent = `${layout.name || 'Indeling'} · ${safeArray(layout.units).length} unit${safeArray(layout.units).length === 1 ? '' : 's'} · 9 facings per rij`;
    if(unitSelect){
      unitSelect.innerHTML = safeArray(layout.units).map((entry, idx) => `<option value="${idx}" ${idx === unitIndex ? 'selected' : ''}>${escapeHtml(entry.name || `GB${idx + 1}`)}</option>`).join('');
    }
    stage.innerHTML = renderBarLayoutStageHtml(layout, unitIndex, target, false);
    renderBarLayoutShelfPanel(layout, target);
    setBarLayoutDirtyState(!!window.barLayoutDirty);
  }

async function saveCurrentBarLayoutStructure(){
    if(!canManageBarLayouts()){ toast('Je mag indelingen niet aanpassen.', 'error'); return; }
    const layout = getSelectedBarLayout();
    if(!layout){
      toast('Kies eerst een indeling', 'error');
      return;
    }
    try{
      await postJSON('/api/manage/bar-layout-structure-save', { layout_id: layout.id, units: layout.units });
      await loadData();
      currentBarLayoutId = layout.id;
      setBarLayoutDirtyState(false);
      if(isBarLayoutMobile()) closeBarLayoutMobileSheet();
      openPage(currentPage === 'bar-indeling-editor' ? 'bar-indeling-editor' : (currentPage === 'bar-indeling-view' ? 'bar-indeling-view' : 'bar-indeling'));
      toast('Visuele indeling opgeslagen');
    }catch(err){
      toast(err.message, 'error');
    }
  }

  function renderBarTasks(){
    const data = appData.bar_tasks || { lists: [] };
    const allLists = safeArray(data.lists);
    if (!currentBarTaskDay) currentBarTaskDay = getAmsterdamDayLabel();
    const lists = allLists.filter(list => taskListMatchesDay(list, currentBarTaskDay));
    const canManageTasklists = hasPermission('manage_bar_tasklists');
    renderTaskDaySwitcher('barDaySwitcher', currentBarTaskDay, 'setBarTaskDay');
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
                  <div class="klist-sub">${formatTaskDaysLabel(list)} · ${done} van ${tasks.length} taken gedaan</div>
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
      'Nog geen bartakenlijsten gevonden voor deze dag.'
    );
  }

  
  function setBarTaskDay(day){
    currentBarTaskDay = day || 'altijd';
    renderBarTasks();
  }

function renderBarTaskListDetail(){
    const data = appData.bar_tasks || { lists: [] };
    const allLists = safeArray(data.lists);
    const visibleLists = allLists.filter(item => taskListMatchesDay(item, currentBarTaskDay));
    const list = allLists.find(item => item.id === currentBarListId) || { tasks: [], name: 'Bar checklist' };
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
          ${renderTasklistSwitcher(data.lists, list.id, 'openBarListDetail')}
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
    if (!hasPermission('manage_bar_tasklists')) return;
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
        <div class="field"><label>Dag</label><select id="barListDay">${getTaskDayOptions().map(day => `<option value="${day}" ${day === currentBarTaskDay ? 'selected' : ''}>${formatTaskDayLabel(day)}</option>`).join('')}</select></div>
        <div class="form-actions">
          <button class="btn" onclick="closeModal()">Annuleren</button>
          <button class="btn accent" onclick="saveBarList()">Opslaan</button>
        </div>
      </div>`);
  }

  async function saveBarList(){
    try{
      await postJSON('/api/bar-tasks/list-save', { name: document.getElementById('barListName').value, day: document.getElementById('barListDay').value });
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
    const isBarOnly = !!p.access_bar && !p.access_kitchen && (!!p.view_bijvullen || !!p.view_oplijst || !!p.adjust_stock || !!p.use_bar_tasklists);
    const isKitchenOnly = !!p.access_kitchen && !p.access_bar && (!!p.view_recipes || !!p.use_kitchen_tasklists);
    if (isBarOnly) return 'bar';
    if (isKitchenOnly) return 'keuken';
    return 'medewerker';
  }

  function basePermissionsForPreset(preset){
    const empty = {
      access_general:false, access_bar:false, access_kitchen:false,
      manage_diensten:false, manage_tips:false, view_bijvullen:false, view_oplijst:false,
      adjust_stock:false, view_recipes:false, use_tasklists:false, use_kitchen_tasklists:false, use_bar_tasklists:false,
      manage_dienst_types:false, manage_users:false, manage_products:false, manage_types:false,
      manage_locations:false, manage_recipes:false, manage_tasklists:false, manage_kitchen_tasklists:false, manage_bar_tasklists:false, manage_coolers:false, manage_bar_layouts:false
    };
    if (preset === 'medewerker'){
      return { ...empty,
        access_general:true, access_bar:true, access_kitchen:true,
        manage_diensten:true, manage_tips:true,
        view_bijvullen:true, view_oplijst:true, adjust_stock:true,
        view_recipes:true, use_tasklists:true, use_kitchen_tasklists:true, use_bar_tasklists:true
      };
    }
    if (preset === 'bar'){
      return { ...empty,
        access_general:true, manage_diensten:true, manage_tips:true,
        access_bar:true, view_bijvullen:true, view_oplijst:true, adjust_stock:true,
        use_tasklists:true, use_bar_tasklists:true
      };
    }
    if (preset === 'keuken'){
      return { ...empty,
        access_general:true, manage_diensten:true, manage_tips:true,
        access_kitchen:true, view_recipes:true,
        use_tasklists:true, use_kitchen_tasklists:true
      };
    }
    return { ...empty };
  }

  function setChecked(id, value){
    const el = document.getElementById(id);
    if (el) el.checked = !!value;
  }

  function applyPermissionPreset(preset){
    const base = preset === 'custom' ? basePermissionsForPreset('custom') : basePermissionsForPreset(preset);
    Object.keys(base).forEach(key => setChecked(`perm_${key}`, !!base[key]));
    const presetSelect = document.getElementById('permissionPreset');
    if (presetSelect) presetSelect.value = preset;
  }

  function syncPermissionPresetInfo(){
    const preset = document.getElementById('permissionPreset')?.value || 'medewerker';
    applyPermissionPreset(preset);
  }

  function togglePermissionFields(){
    const role = document.getElementById('userRole')?.value || 'medewerker';
    const wrap = document.getElementById('userPermissionsWrap');
    if (wrap) wrap.style.display = role === 'admin' ? 'none' : '';
  }

  function permissionRow(id, label, checked){
    return `<div class="permission-row"><span class="permission-inline-label">${label}</span><input type="checkbox" id="${id}" ${checked ? 'checked' : ''}></div>`;
  }

  function permissionCheckboxes(user){
    const preset = derivePermissionPreset(user);
    const p = user?.permissions || {};
    return `
      <div class="permission-grid compact">
        <div class="permission-panel">
          <div class="permission-kicker">Snelle rechten</div>
          <div class="permission-help">Kies een basisprofiel en verfijn daarna wat iemand wel of niet mag doen.</div>
          <div class="field" style="margin-bottom:8px">
            <label>Basisprofiel</label>
            <select id="permissionPreset" onchange="syncPermissionPresetInfo()">
              <option value="medewerker" ${preset === 'medewerker' ? 'selected' : ''}>Medewerker · dagelijks gebruik</option>
              <option value="bar" ${preset === 'bar' ? 'selected' : ''}>Bar medewerker</option>
              <option value="keuken" ${preset === 'keuken' ? 'selected' : ''}>Keuken medewerker</option>
            </select>
          </div>
          <div class="permission-actions">
            <button type="button" class="permission-chip" onclick="applyPermissionPreset('medewerker')">Medewerker</button>
            <button type="button" class="permission-chip" onclick="applyPermissionPreset('bar')">Bar</button>
            <button type="button" class="permission-chip" onclick="applyPermissionPreset('keuken')">Keuken</button>
            <button type="button" class="permission-chip" onclick="applyPermissionPreset('custom')">Alles uit</button>
          </div>
        </div>

        <div class="permission-sections">
          <div class="permission-panel">
            <div class="permission-kicker">Toegang</div>
            ${permissionRow('perm_access_general', 'Algemeen zichtbaar', !!p.access_general)}
            ${permissionRow('perm_access_bar', 'Bar zichtbaar', !!p.access_bar)}
            ${permissionRow('perm_access_kitchen', 'Keuken zichtbaar', !!p.access_kitchen)}
          </div>

          <div class="permission-panel">
            <div class="permission-kicker">Dagelijks gebruik</div>
            ${permissionRow('perm_manage_diensten', 'Diensten gebruiken', !!p.manage_diensten)}
            ${permissionRow('perm_manage_tips', 'Fooienpot aanpassen', !!p.manage_tips)}
            ${permissionRow('perm_view_bijvullen', 'Bijvuloverzicht openen', !!p.view_bijvullen)}
            ${permissionRow('perm_view_oplijst', 'Op-lijst openen', !!p.view_oplijst)}
            ${permissionRow('perm_adjust_stock', 'Koelingvoorraad aanpassen', !!p.adjust_stock)}
            ${permissionRow('perm_view_recipes', 'Recepten openen', !!p.view_recipes)}
          </div>

          <div class="permission-panel">
            <div class="permission-kicker">Takenlijsten</div>
            ${permissionRow('perm_use_bar_tasklists', 'Bar takenlijsten openen', !!p.use_bar_tasklists)}
            ${permissionRow('perm_manage_bar_tasklists', 'Bar takenlijsten beheren', !!p.manage_bar_tasklists)}
            ${permissionRow('perm_use_kitchen_tasklists', 'Keuken takenlijsten openen', !!p.use_kitchen_tasklists)}
            ${permissionRow('perm_manage_kitchen_tasklists', 'Keuken takenlijsten beheren', !!p.manage_kitchen_tasklists)}
          </div>

          <div class="permission-panel">
            <div class="permission-kicker">Beheer</div>
            ${permissionRow('perm_manage_dienst_types', 'Dienstsoorten beheren', !!p.manage_dienst_types)}
            ${permissionRow('perm_manage_users', 'Medewerkers beheren', !!p.manage_users)}
            ${permissionRow('perm_manage_products', 'Producten beheren', !!p.manage_products)}
            ${permissionRow('perm_manage_types', 'Productsoorten beheren', !!p.manage_types)}
            ${permissionRow('perm_manage_locations', 'Locaties beheren', !!p.manage_locations)}
            ${permissionRow('perm_manage_recipes', 'Recepten beheren', !!p.manage_recipes)}
            ${permissionRow('perm_manage_coolers', 'Koelingen beheren', !!p.manage_coolers)}
            ${permissionRow('perm_manage_bar_layouts', 'Bar indelingen beheren', !!p.manage_bar_layouts)}
          </div>
        </div>
      </div>
    `;
  }

  function collectUserPermissions(){
    const keys = [
      'access_general','access_bar','access_kitchen',
      'manage_diensten','manage_tips','view_bijvullen','view_oplijst','adjust_stock','view_recipes',
      'use_bar_tasklists','manage_bar_tasklists','use_kitchen_tasklists','manage_kitchen_tasklists',
      'manage_dienst_types','manage_users','manage_products','manage_types','manage_locations','manage_recipes','manage_coolers','manage_bar_layouts'
    ];
    const result = {};
    keys.forEach(key => {
      result[key] = !!document.getElementById(`perm_${key}`)?.checked;
    });
    result.use_tasklists = !!(result.use_kitchen_tasklists || result.use_bar_tasklists);
    result.manage_tasklists = !!(result.manage_kitchen_tasklists || result.manage_bar_tasklists);
    return result;
  }

  function permissionSummary(user){
    const p = user?.permissions || {};
    const sections = [];
    if (p.access_general) sections.push('Algemeen');
    if (p.access_bar) sections.push('Bar');
    if (p.access_kitchen) sections.push('Keuken');
    const beheer = [];
    if (p.manage_users) beheer.push('Medewerkers');
    if (p.manage_products) beheer.push('Producten');
    if (p.manage_coolers) beheer.push('Koelingen');
    if (p.manage_bar_layouts) beheer.push('Indelingen');
    if (p.manage_recipes) beheer.push('Recepten');
    let base = sections.length ? sections.join(' · ') : 'Beperkt';
    if (beheer.length) base += ` · Beheer: ${beheer.join(', ')}`;
    return base;
  }

function openUserModal(index=null){
    if (!isAdmin()) return;
    const user = index !== null ? safeArray(appData.auth?.users)[index] || {} : { role: 'medewerker', permissions: { access_general:true, access_bar:true, access_kitchen:true, manage_diensten:true, manage_tips:true, view_bijvullen:true, view_oplijst:true, adjust_stock:true, view_recipes:true, use_tasklists:true, use_kitchen_tasklists:true, use_bar_tasklists:true, manage_dienst_types:false, manage_users:false, manage_products:false, manage_types:false, manage_locations:false, manage_recipes:false, manage_tasklists:false, manage_kitchen_tasklists:false, manage_bar_tasklists:false, manage_coolers:false, manage_bar_layouts:false } };
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
    const { diensten, upcoming, thisWeek, changed, today } = collectDienstStats();
    const canManageDiensten = hasPermission('manage_diensten');

    const summaryGrid = document.getElementById('dienstenSummaryGrid');
    if (summaryGrid) summaryGrid.remove();

    const focusRows = [];
    if (today[0]){
      focusRows.push({
        title:`Vandaag · ${getDienstDisplayName(today[0])}`,
        sub:`${formatDienstDate(today[0].datum)}${getDienstTimeLabel(today[0]) ? ' · ' + getDienstTimeLabel(today[0]) : ''}${getDienstLocation(today[0]) ? ' · ' + getDienstLocation(today[0]) : ''}`,
        badge:dienstStatusLabel(today[0].status),
        badgeClass:dienstStatusBadgeClass(today[0].status)
      });
    }
    if (upcoming[0]){
      focusRows.push({
        title:`Volgende · ${getDienstDisplayName(upcoming[0])}`,
        sub:`${formatDienstDate(upcoming[0].datum)}${getDienstTimeLabel(upcoming[0]) ? ' · ' + getDienstTimeLabel(upcoming[0]) : ''}`,
        badge:getDienstLocation(upcoming[0]) || 'Gepland',
        badgeClass:getDienstLocation(upcoming[0]) ? 'accent' : ''
      });
    }
    thisWeek.slice(0,2).forEach(item => {
      focusRows.push({
        title:getDienstDisplayName(item),
        sub:`${formatDienstDate(item.datum)}${getDienstTimeLabel(item) ? ' · ' + getDienstTimeLabel(item) : ''}${getDienstNote(item) ? ' · ' + getDienstNote(item) : ''}`,
        badge:dienstStatusLabel(item.status),
        badgeClass:dienstStatusBadgeClass(item.status)
      });
    });
    setText('dienstenWeekBadge', thisWeek.length ? `${thisWeek.length} diensten` : '0 diensten');
    renderMiniRows('dienstenWeekList', focusRows.slice(0,4), 'Nog geen diensten in beeld.');

    const quickActions = document.getElementById('dienstenQuickActions');
    if (quickActions){
      quickActions.innerHTML = [
        `<button class="stat-card diensten-quick-card" onclick="setDienstenView('week', { keepDayFilter: true })"><div class="stat-label">Week</div><div class="stat-value">${thisWeek.length}</div><div class="stat-sub">Bekijk alleen deze week</div></button>`,
        `<button class="stat-card diensten-quick-card" onclick="setDienstDayFilter(String(new Date().getDay() || 0)); setDienstenView('all')"><div class="stat-label">Vandaag</div><div class="stat-value">${today.length}</div><div class="stat-sub">Open alleen vandaag</div></button>`,
        `<button class="stat-card diensten-quick-card" onclick="openPage('dienstsoorten')"><div class="stat-label">Soorten</div><div class="stat-value">${safeArray(appData.dienst_types).length}</div><div class="stat-sub">Beheer dienstsoorten</div></button>`,
        `<button class="stat-card diensten-quick-card" onclick="openDishImportModal()"><div class="stat-label">DISH</div><div class="stat-value">📸</div><div class="stat-sub">Importeer blauw gemarkeerde dagen</div></button>`,
        `<button class="stat-card diensten-quick-card" onclick="openCalendarLinkModal()"><div class="stat-label">Agenda</div><div class="stat-value">↗</div><div class="stat-sub">Koppel jouw diensten</div></button>`,
        `${canManageDiensten ? `<button class="stat-card diensten-quick-card" onclick="openDienstModal()"><div class="stat-label">Actie</div><div class="stat-value">+</div><div class="stat-sub">Nieuwe dienst toevoegen</div></button>` : ''}`
      ].join('');
    }
    setText('dienstenQuickBadge', currentDienstView === 'week' ? 'Weekmodus' : 'Planning');
    setText('dienstenQuickNote', currentDienstDayFilter === 'all' ? 'Gebruik de dagknoppen hieronder om je planning nog sneller te filteren.' : `Dagfilter actief: ${dienstDayLabel(currentDienstDayFilter)}.`);

    const baseDiensten = currentDienstView === 'week' ? thisWeek : diensten;
    const visibleDiensten = baseDiensten.filter(item => isDienstOnSelectedDay(item));
    const allBtn = document.getElementById('dienstenFilterAllBtn');
    const weekBtn = document.getElementById('dienstenFilterWeekBtn');
    if (allBtn) allBtn.classList.toggle('accent', currentDienstView === 'all');
    if (weekBtn) weekBtn.classList.toggle('accent', currentDienstView === 'week');
    setText('dienstenListIntro', currentDienstView === 'week' ? (appData.general?.diensten_personal_view ? 'Je ziet jouw diensten uit deze week.' : 'Je ziet nu alleen diensten uit deze week in compacte weekblokken.') : (appData.general?.diensten_personal_view ? 'Je ziet alleen jouw eigen geplande diensten.' : 'Je ziet alle geplande diensten in compacte weekblokken.'));

    const dayRow = document.getElementById('dienstenDayFilterRow');
    if (dayRow){
      const days = ['1','2','3','4','5','6','0'];
      dayRow.innerHTML = days.map(day => `<button type="button" class="task-switcher-btn ${currentDienstDayFilter === day ? 'active' : ''}" onclick="setDienstDayFilter('${day}')">${dienstDayLabel(day)}</button>`).join('');
    }

    const listEl = document.getElementById('dienstenList');
    if (!listEl) return;
    if (!visibleDiensten.length){
      listEl.innerHTML = `<div class="empty">${currentDienstView === 'week'
        ? (currentDienstDayFilter === 'all' ? 'Nog geen diensten in deze week.' : `Nog geen diensten op ${dienstDayLabel(currentDienstDayFilter)} in deze week.`)
        : (currentDienstDayFilter === 'all' ? 'Nog geen diensten gevonden.' : `Nog geen diensten op ${dienstDayLabel(currentDienstDayFilter)}.`)}</div>`;
      return;
    }

    const weekGroups = new Map();
    visibleDiensten.forEach(item => {
      const date = parseDienstDate(item.datum);
      const weekKey = date ? isoWeekKey(date) : 'zonder-week';
      if (!weekGroups.has(weekKey)) weekGroups.set(weekKey, new Map());
      const dateKey = item.datum || 'zonder-datum';
      if (!weekGroups.get(weekKey).has(dateKey)) weekGroups.get(weekKey).set(dateKey, []);
      weekGroups.get(weekKey).get(dateKey).push(item);
    });

    const sortedWeekEntries = Array.from(weekGroups.entries()).sort((a, b) => {
      if (a[0] === 'zonder-week') return 1;
      if (b[0] === 'zonder-week') return -1;
      return a[0].localeCompare(b[0]);
    });

    const currentDate = new Date();
    const currentWeekKey = isoWeekKey(currentDate);
    const weekRangeLabel = (weekMap) => {
      const keys = Array.from(weekMap.keys()).filter(k => k && k !== 'zonder-datum').sort((a,b)=> a.localeCompare(b));
      if (!keys.length) return 'Geen datumbereik';
      const first = keys[0];
      const last = keys[keys.length - 1];
      return first === last ? formatDienstDate(first) : `${formatDienstDate(first)} – ${formatDienstDate(last)}`;
    };

    listEl.innerHTML = sortedWeekEntries.map(([weekKey, dayMap], index) => {
      const weekItems = Array.from(dayMap.values()).flat();
      const sortedDays = Array.from(dayMap.entries()).sort((a, b) => a[0].localeCompare(b[0]));
      const shouldOpen = weekKey === currentWeekKey || (currentDienstView === 'week' && index === 0);
      return `
        <details class="dienst-week-compact" ${shouldOpen ? 'open' : ''}>
          <summary class="dienst-week-summary">
            <div class="dienst-week-summary-left">
              <div class="dienst-group-kicker">Week</div>
              <div class="dienst-week-summary-title">${weekKey === 'zonder-week' ? 'Geen week' : weekLabelFromKey(weekKey)}</div>
              <div class="dienst-week-summary-sub">${weekRangeLabel(dayMap)}</div>
            </div>
            <div class="dienst-week-summary-right">
              <span class="badge accent">${weekItems.length} ${weekItems.length === 1 ? 'dienst' : 'diensten'}</span>
              <span class="group-chevron">⌄</span>
            </div>
          </summary>
          <div class="dienst-week-compact-body">
            ${sortedDays.map(([dateKey, items]) => {
              const prettyDate = dateKey === 'zonder-datum' ? 'Geen datum' : formatDienstDate(dateKey);
              return `
                <section class="dienst-day-compact ${dateKey === getTodayString() ? 'is-today' : ''}">
                  <div class="dienst-day-compact-head">
                    <div class="dienst-day-compact-head-left">
                      <div class="dienst-day-compact-title">${prettyDate}</div>
                      ${dateKey === getTodayString() ? `<span class="badge accent">Vandaag</span>` : ``}
                    </div>
                    <span class="badge">${items.length}</span>
                  </div>
                  <div class="dienst-cards dienst-cards-compact">
                    ${items.map(item => {
                      const originalIndex = (item && item._global_index !== undefined) ? item._global_index : safeArray(appData.general?.diensten).indexOf(item);
                      return `
                        <article class="dienst-card-item dienst-card-item-compact ${item.status === 'gewijzigd' ? 'is-changed' : ''} ${String(item?.datum || '') === getTodayString() ? 'is-today' : ''}">
                          <div class="dienst-card-top">
                            <div class="dienst-card-time">${getDienstTimeLabel(item) || 'Tijd volgt'}</div>
                            <div class="dienst-card-main">
                              <div class="dienst-card-title">${getDienstDisplayName(item)}</div>
                              <div class="dienst-card-sub">${item.naam ? item.naam : 'Dienst'}${getDienstLocation(item) ? ' · ' + getDienstLocation(item) : ''}${item.rol ? ' · ' + item.rol : ''}${getDienstNote(item) ? ' · ' + getDienstNote(item) : ''}</div>
                            </div>
                            <div class="dienst-card-side">
                              <span class="badge ${dienstStatusBadgeClass(item.status)}">${dienstStatusLabel(item.status)}</span>
                              ${canManageDiensten ? `<div class="dienst-inline-actions"><button class="dienst-inline-btn accent" onclick="openDienstModal(${originalIndex})">Bewerk</button><button class="dienst-inline-btn danger" onclick="confirmAction('Dienst verwijderen','Weet je zeker dat je deze dienst wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteDienst',${originalIndex})&quot;)">Verwijder</button></div>` : ``}
                            </div>
                          </div>
                        </article>`;
                    }).join('')}
                  </div>
                </section>`;
            }).join('')}
          </div>
        </details>`;
    }).join('');
  }

    function renderAll(){
    applyPermissions();
    const newDienstBtn = document.getElementById('newDienstBtn');
    if (newDienstBtn) newDienstBtn.style.display = hasPermission('manage_diensten') ? '' : 'none';
    initFilters();
    renderDashboard();
    renderChecklistsPage();
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
    renderBarLayouts();
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

  function applyDienstTypeTimes(force=false){
    const name = document.getElementById('dienstNaam')?.value || '';
    const item = getDienstTypeByName(name);
    const startInput = document.getElementById('dienstStart');
    const endInput = document.getElementById('dienstEinde');
    const typeStart = normalizeDienstTimeValue(item.start || '');
    const typeEnd = normalizeDienstTimeValue(item.einde || '');
    if (startInput && (force || !normalizeDienstTimeValue(startInput.value || '')) && typeStart) startInput.value = typeStart;
    if (endInput && (force || !normalizeDienstTimeValue(endInput.value || '')) && typeEnd) endInput.value = typeEnd;
    return { typeStart, typeEnd };
  }

  function updateDienstTimePreview(){
    const name = document.getElementById('dienstNaam')?.value || '';
    const item = getDienstTypeByName(name);
    const startInput = document.getElementById('dienstStart');
    const endInput = document.getElementById('dienstEinde');
    const startValue = normalizeDienstTimeValue(startInput?.value || '') || normalizeDienstTimeValue(item.start || '') || '';
    const endValue = normalizeDienstTimeValue(endInput?.value || '') || normalizeDienstTimeValue(item.einde || '') || '';
    const text = buildDienstTimeLabel(startValue, endValue);
    const el = document.getElementById('dienstTimePreview');
    if (el) el.value = text || 'Geen tijden ingesteld';
  }

  function handleDienstTypeChange(){
    applyDienstTypeTimes(true);
    updateDienstTimePreview();
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


  function dishImportTypeSelectOptions(selected=''){
    const options = ['<option value="">Kies dienstsoort</option>'];
    safeArray(appData.dienst_types).forEach(item => {
      options.push(`<option value="${escapeHtml(item.naam)}" ${item.naam === selected ? 'selected' : ''}>${escapeHtml(item.naam)}</option>`);
    });
    return options.join('');
  }
  
  async function openCalendarLinkModal(){
    let url = String(appData?.auth?.calendar_url || '').trim();

    if (!url){
      try{
        const res = await fetch('/api/casa/calendar-link', { credentials:'same-origin' });
        const data = await res.json();
        if (data && data.ok && data.url){
          url = String(data.url || '').trim();
          appData.auth = appData.auth || {};
          appData.auth.calendar_url = url;
        }else if (data && data.message){
          toast(data.message, 'error');
          return;
        }
      }catch(err){}
    }

    if (!url){
      toast('Agenda link kon niet worden gemaakt. Log opnieuw in en probeer het nog eens.', 'error');
      return;
    }

    const webcalUrl = url.replace(/^https?:\/\//, 'webcal://');
    const feedCount = Number(appData?.auth?.calendar_event_count || 0);
    const firstEvent = String(appData?.auth?.calendar_first_event || '').trim();

    openModal(
      'Agenda koppelen',
      'Kopieer jouw persoonlijke agenda-link en voeg hem toe als agenda-abonnement.',
      `<div class="calendar-link-card">
        <div class="calendar-link-status">
          <div>
            <div class="calendar-link-kicker">Persoonlijke feed</div>
            <div class="calendar-link-title">${feedCount ? `${feedCount} diensten klaar voor agenda` : 'Agenda feed klaar'}</div>
            <div class="calendar-link-sub">${firstEvent || 'Na je Render deploy gebruik je deze HTTPS-link voor Apple Agenda, Google Calendar of Outlook.'}</div>
          </div>
          <span class="badge accent">ICS</span>
        </div>

        <div class="field">
          <label>Agenda-link</label>
          <input id="calendarFeedUrl" value="${url}" readonly onclick="this.select()">
        </div>

        <div class="overview-note">
          Deze link is persoonlijk. Deel hem niet met anderen. Je agenda-app ververst abonnementen periodiek automatisch.
        </div>

        <div class="calendar-link-actions">
          <button class="btn accent calendar-main-action" onclick="copyCalendarFeedUrl()">Kopieer agenda-link</button>
          <a class="btn calendar-secondary-action" href="${webcalUrl}" target="_blank" rel="noopener">Open in agenda-app</a>
        </div>
      </div>`
    );
  }

  async function copyCalendarFeedUrl(){
    const input = document.getElementById('calendarFeedUrl');
    const url = input?.value || String(appData?.auth?.calendar_url || '');
    try{
      await navigator.clipboard.writeText(url);
      toast('Agenda link gekopieerd.');
    }catch(err){
      if (input){
        input.select();
        document.execCommand('copy');
        toast('Agenda link gekopieerd.');
      }else{
        toast('Kopiëren lukt niet automatisch.', 'error');
      }
    }
  }

function openDishImportModal(){
    const now = new Date();
    const monthOptions = Array.from({length:12}, (_, idx) => `<option value="${idx + 1}" ${(idx + 1) === (now.getMonth() + 1) ? 'selected' : ''}>${new Intl.DateTimeFormat('nl-NL', { month:'long' }).format(new Date(2025, idx, 1))}</option>`).join('');
    const yearOptions = Array.from({length:5}, (_, idx) => {
      const year = now.getFullYear() - 1 + idx;
      return `<option value="${year}" ${year === now.getFullYear() ? 'selected' : ''}>${year}</option>`;
    }).join('');
    openModal('', 'Upload je DISH screenshot en bekijk eerst de preview.', `
      <div class="form-grid">
        <div class="field"><label>Screenshot van je DISH maandrooster</label><input id="dishImportFile" type="file" accept="image/*"></div>
        <div class="field"><label>Maand van screenshot</label><select id="dishImportMonth">${monthOptions}</select></div>
        <div class="field"><label>Jaar</label><select id="dishImportYear">${yearOptions}</select></div>
        <div class="field"><label><input id="dishImportBlueOnly" type="checkbox" checked style="width:auto;min-height:auto;margin-right:8px"> Alleen volledig blauwe dagen herkennen</label></div>
        <div class="overview-note">Preview eerst. v5 herkent alleen volledig blauwe DISH-dagen. Omcirkeld blauw en groen worden genegeerd. Daarna kies jij per dag zelf de juiste dienstsoort; de tijden komen automatisch uit je dienstsoorten.</div>
        <div id="dishImportPreview" class="mini-list"></div>
        <div class="form-actions">
          <button class="btn" onclick="closeModal()">Sluiten</button>
          <button class="btn" onclick="previewDishImport()">Preview</button>
          <button class="btn accent" id="dishImportConfirmBtn" onclick="applyDishImport()" style="display:none">Importeren</button>
        </div>
      </div>
    `);
    window.latestDishImportPreview = [];
  }
  async function readDishImportFile(){
    const fileInput = document.getElementById('dishImportFile');
    const file = fileInput?.files?.[0];
    if (!file) throw new Error('Kies eerst een screenshot.');
    return await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ''));
      reader.onerror = () => reject(new Error('Kon de screenshot niet lezen.'));
      reader.readAsDataURL(file);
    });
  }
  function dishImportIncludeColors(){
    return ['blue'];
  }
  function renderDishImportPreview(){
    const previewEl = document.getElementById('dishImportPreview');
    if (!previewEl) return;
    const items = safeArray(window.latestDishImportPreview);
    if (!items.length){
      previewEl.innerHTML = '<div class="empty">We herkenden nog geen dagen. Probeer eventueel een iets strakkere screenshot van alleen de maandkalender.</div>';
      return;
    }
    previewEl.innerHTML = items.map((item, index) => {
      const suggested = item.naam || item.suggested_name || '';
      return `
        <div class="mini-row" style="align-items:flex-start">
          <div style="min-width:0">
            <strong>${formatDienstDate(item.datum)}</strong>
            <span>Gedetecteerde kleur: ${item.color || 'blauw'}</span>
          </div>
          <div style="display:grid;gap:8px;min-width:220px;max-width:260px;width:100%">
            <select id="dishImportType_${index}" onchange="window.handleDishPreviewTypeChange(${index})">${dishImportTypeSelectOptions(suggested)}</select>
            <div id="dishImportTime_${index}" class="meta-chip">${item.start && item.einde ? item.start + ' - ' + item.einde : 'Kies een dienstsoort om tijden te vullen'}</div>
          </div>
        </div>
      `;
    }).join('');
  }
  function handleDishPreviewTypeChange(index){
    const item = safeArray(window.latestDishImportPreview)[index] || {};
    const selectedName = document.getElementById(`dishImportType_${index}`)?.value || '';
    const dienstType = getDienstTypeByName(selectedName);
    item.naam = selectedName;
    item.start = normalizeDienstTimeValue(dienstType.start || '') || '';
    item.einde = normalizeDienstTimeValue(dienstType.einde || '') || '';
    item.tijd = buildDienstTimeLabel(item.start, item.einde);
    const timeEl = document.getElementById(`dishImportTime_${index}`);
    if (timeEl) timeEl.textContent = item.tijd || 'Geen standaardtijd gevonden';
  }
  async function previewDishImport(){
    try{
      const payload = {
        image_data: await readDishImportFile(),
        month: document.getElementById('dishImportMonth')?.value,
        year: document.getElementById('dishImportYear')?.value,
        color_map: {},
        include_colors: dishImportIncludeColors()};
      const response = await postJSON('/api/manage/dish-import-preview', payload);
      window.latestDishImportPreview = safeArray(response.items);
      renderDishImportPreview();
      const confirmBtn = document.getElementById('dishImportConfirmBtn');
      if (confirmBtn) confirmBtn.style.display = window.latestDishImportPreview.length ? '' : 'none';
      toast(window.latestDishImportPreview.length ? 'Preview klaar' : 'Geen dagen herkend', window.latestDishImportPreview.length ? 'success' : 'error');
    }catch(err){
      toast(err.message, 'error');
    }
  }
  async function applyDishImport(){
    try{
      const items = safeArray(window.latestDishImportPreview).map((item, index) => {
        const selectedName = document.getElementById(`dishImportType_${index}`)?.value || item.naam || '';
        const dienstType = getDienstTypeByName(selectedName);
        const start = normalizeDienstTimeValue(dienstType.start || item.start || '') || '';
        const einde = normalizeDienstTimeValue(dienstType.einde || item.einde || '') || '';
        return {
          ...item,
          naam: selectedName,
          start,
          einde,
          tijd: buildDienstTimeLabel(start, einde)};
      }).filter(item => item.naam);
      if (!items.length) throw new Error('Kies in de preview minstens één dienstsoort.');
      const response = await postJSON('/api/manage/dish-import-apply', { items });
      closeModal();
      await loadData();
      openPage('diensten');
      setDienstenView('all', { render:false, scroll:false });
      currentDienstDayFilter = 'all';
      renderDiensten();
      toast(response.message || 'DISH diensten geïmporteerd');
    }catch(err){
      toast(err.message, 'error');
    }
  }
  window.openDishImportModal = openDishImportModal;
  window.handleDishPreviewTypeChange = handleDishPreviewTypeChange;

  function openDienstModal(index=null){
    const item = index !== null ? (safeArray(appData.general.diensten).find(d => String(d?._global_index) === String(index)) || safeArray(appData.general.diensten)[index] || {}) : {};
    const typeName = item.naam || item.medewerker || '';
    const dienstType = getDienstTypeByName(typeName);
    const startValue = normalizeDienstTimeValue(getDienstStart(item) || dienstType.start || '') || '';
    const endValue = normalizeDienstTimeValue(getDienstEnd(item) || dienstType.einde || '') || '';
    openModal(
      index === null ? 'Dienst toevoegen' : 'Dienst bewerken',
      'Vul de dienst rustig aan met datum, tijden, locatie, status en notitie. Alles blijft binnen je huidige dienstenfunctie.',
      `
        <div class="form-grid">
          <div class="field">
            <label>Dienstsoort</label>
            <select id="dienstNaam" onchange="window.handleDienstTypeChange()">${dienstTypeOptions(typeName)}</select>
          </div>
          <div class="field">
            <label>Datum</label>
            <input id="dienstDatum" type="date" value="${item.datum || ''}">
          </div>
          <div class="field">
            <label>Begintijd</label>
            <input id="dienstStart" type="time" value="${startValue}" onchange="window.updateDienstTimePreview()">
          </div>
          <div class="field">
            <label>Eindtijd</label>
            <input id="dienstEinde" type="time" value="${endValue}" onchange="window.updateDienstTimePreview()">
          </div>
          <div class="field">
            <label>Voorbeeld tijdsblok</label>
            <input id="dienstTimePreview" value="" disabled>
          </div>
          <div class="field">
            <label>Locatie / afdeling</label>
            <input id="dienstLocatie" value="${item.locatie || ''}" placeholder="Bijv. Bar, keuken of terras">
          </div>
          <div class="field">
            <label>Status</label>
            <select id="dienstStatus"></select>
          </div>
          <div class="field"><label>Notitie</label><input id="dienstRol" value="${getDienstNote(item)}" placeholder="Bijv. Floor / Extra druk / Sluitdienst"></div>
          ${hasPermission('manage_dienst_types') ? `<div class="actions"><button class="btn" onclick="openDienstTypeModal()">Dienstsoort toevoegen</button><button class="btn" onclick="openPage('dienstsoorten'); closeModal()">Beheer dienstsoorten</button></div>` : ''}
          <div class="form-actions">
            <button class="btn" onclick="closeModal()">Annuleren</button>
            <button class="btn accent" onclick="window.saveDienst(${index === null ? 'null' : index})">Opslaan</button>
          </div>
        </div>
      `
    );
    const statusEl = document.getElementById('dienstStatus');
    if (statusEl){
      const current = normalizeDienstStatus(item.status);
      statusEl.innerHTML = [
        {value:'ingepland', label:'Ingepland'},
        {value:'bevestigd', label:'Bevestigd'},
        {value:'gewijzigd', label:'Gewijzigd'},
        {value:'vervallen', label:'Vervallen'}
      ].map(opt => `<option value="${opt.value}" ${opt.value === current ? 'selected' : ''}>${opt.label}</option>`).join('');
    }
    updateDienstTimePreview();
  }

  window.applyDienstTypeTimes = applyDienstTypeTimes;
  window.updateDienstTimePreview = updateDienstTimePreview;
  window.handleDienstTypeChange = handleDienstTypeChange;

  async function saveDienst(index){
    const dienstNaam = document.getElementById('dienstNaam').value;
    const dienstType = getDienstTypeByName(dienstNaam);
    const start = normalizeDienstTimeValue(document.getElementById('dienstStart').value || dienstType.start || '') || '';
    const einde = normalizeDienstTimeValue(document.getElementById('dienstEinde').value || dienstType.einde || '') || '';
    const payload = {
      index,
      naam: dienstNaam,
      datum: document.getElementById('dienstDatum').value,
      start,
      einde,
      tijd: buildDienstTimeLabel(start, einde),
      locatie: document.getElementById('dienstLocatie').value,
      status: document.getElementById('dienstStatus').value,
      notitie: document.getElementById('dienstRol').value,
      rol: document.getElementById('dienstRol').value};
    try{
      await postJSON('/api/manage/dienst-save', payload);
      closeModal();
      currentDienstView = 'all';
      currentDienstDayFilter = 'all';
      await loadData();
      document.getElementById('dienstenListPanel')?.scrollIntoView({behavior:'smooth', block:'start'});
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
        locatie: document.getElementById('typeLocation').value});
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
          <div class="field" style="grid-column:1/-1"><label>Productfoto (blijft bewaard)</label><input id="productImageUrl" value="${product.image_url || product.image || product.photo || ''}" placeholder="https://..."></div>
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
        image_url: document.getElementById('productImageUrl')?.value || ''});
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
        op: false});
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
  bindChecklistManageButtonFallback();
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

@casa_cara.route("/api/bar-layouts")
def api_bar_layouts():
    return jsonify(get_bar_layouts_data())

@casa_cara.route("/api/manage/bar-layout-save", methods=["POST"])
def manage_bar_layout_save():
    if not has_layout_manage_permission():
        return permission_denied_response("Je mag indelingen niet aanpassen.")
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    note = (payload.get("note") or "").strip()
    if not name:
        return jsonify({"ok": False, "message": "Vul een naam in voor deze indeling."}), 400
    data = get_bar_layouts_data()
    items = data.get("items", [])
    layout_id = str(payload.get("layout_id") or "").strip()
    if layout_id:
        for item in items:
            if item.get("id") == layout_id:
                item["name"] = name
                item["note"] = note
                break
        else:
            return jsonify({"ok": False, "message": "Indeling niet gevonden."}), 404
    else:
        base_id = slugify(name)
        new_id = base_id
        counter = 2
        existing = {str(item.get("id") or "") for item in items}
        while new_id in existing:
            new_id = f"{base_id}_{counter}"
            counter += 1
        items.append({
            "id": new_id,
            "name": name,
            "note": note,
            "created_at": datetime.now().strftime("%d-%m-%Y %H:%M"),
            "units": default_bar_layout_structure()})
        if not data.get("active_id"):
            data["active_id"] = new_id
    data["items"] = items
    save_bar_layouts_data(data)
    return jsonify({"ok": True})

@casa_cara.route("/api/manage/bar-layout-delete", methods=["POST"])
def manage_bar_layout_delete():
    if not has_layout_manage_permission():
        return permission_denied_response("Je mag indelingen niet aanpassen.")
    payload = request.get_json(silent=True) or {}
    layout_id = str(payload.get("layout_id") or "").strip()
    if not layout_id:
        return jsonify({"ok": False, "message": "Ongeldige indeling."}), 400
    data = get_bar_layouts_data()
    items = [item for item in data.get("items", []) if item.get("id") != layout_id]
    if len(items) == len(data.get("items", [])):
        return jsonify({"ok": False, "message": "Indeling niet gevonden."}), 404
    data["items"] = items
    if data.get("active_id") == layout_id:
        data["active_id"] = items[0].get("id") if items else ""
    save_bar_layouts_data(data)
    return jsonify({"ok": True})

@casa_cara.route("/api/manage/bar-layout-set-active", methods=["POST"])
def manage_bar_layout_set_active():
    if not has_layout_manage_permission():
        return permission_denied_response("Je mag indelingen niet aanpassen.")
    payload = request.get_json(silent=True) or {}
    layout_id = str(payload.get("layout_id") or "").strip()
    data = get_bar_layouts_data()
    if not any(item.get("id") == layout_id for item in data.get("items", [])):
        return jsonify({"ok": False, "message": "Indeling niet gevonden."}), 404
    data["active_id"] = layout_id
    save_bar_layouts_data(data)
    return jsonify({"ok": True})


def get_product_image_for_layout(product_id: str = "", product_name: str = "") -> str:
    product_id = str(product_id or "").strip()
    product_name = str(product_name or "").strip().lower()
    for koeling in get_bar_data().get("koelingen", []):
        for product in koeling.get("producten", []):
            pid = str(product.get("id") or "").strip()
            pname = str(product.get("naam") or "").strip().lower()
            image = str(product.get("image_url") or product.get("image") or product.get("photo") or "").strip()
            if product_id and pid == product_id and image:
                return image
            if product_name and pname == product_name and image:
                return image
    return ""


def backfill_layout_product_images(units):
    units = normalize_layout_units(units)
    for unit in units:
        for cooler in unit.get("coolers", []):
            for shelf in cooler.get("shelves", []):
                for slot in shelf.get("slots", []):
                    if not str(slot.get("image_url") or "").strip() and (slot.get("product_id") or slot.get("product_name")):
                        slot["image_url"] = get_product_image_for_layout(slot.get("product_id"), slot.get("product_name"))
    return units

@casa_cara.route("/api/manage/bar-layout-structure-save", methods=["POST"])
def manage_bar_layout_structure_save():
    if not has_layout_manage_permission():
        return permission_denied_response("Je mag indelingen niet aanpassen.")
    payload = request.get_json(silent=True) or {}
    layout_id = str(payload.get("layout_id") or "").strip()
    if not layout_id:
        return jsonify({"ok": False, "message": "Ongeldige indeling."}), 400
    data = get_bar_layouts_data()
    for item in data.get("items", []):
        if item.get("id") == layout_id:
            item["units"] = backfill_layout_product_images(payload.get("units"))
            save_bar_layouts_data(data)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Indeling niet gevonden."}), 404

@casa_cara.route("/api/bar")
def api_bar():
    bar_data = get_bar_data()
    return jsonify({
        "koelingen": bar_data.get("koelingen", []),
        "fill_items": build_fill_items(bar_data)})

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
    start, einde, tijd = extract_dienst_times(
        payload.get("start") or "",
        payload.get("einde") or "",
        payload.get("tijd") or "",
    )
    rol = (payload.get("rol") or payload.get("notitie") or "").strip()
    notitie = (payload.get("notitie") or payload.get("rol") or "").strip()
    locatie = (payload.get("locatie") or "").strip()
    status = normalize_dienst_status(payload.get("status"))
    if not naam:
        return jsonify({"ok": False, "message": "Kies een dienstsoort."}), 400
    if not datum:
        return jsonify({"ok": False, "message": "Kies een datum."}), 400

    data = get_general_data()
    diensten = data.get("diensten", [])
    index = payload.get("index", None)
    now_iso = get_now_iso_minutes()

    current_owner = current_casa_owner_name()
    base = {
        "naam": naam,
        "datum": datum,
        "start": start,
        "einde": einde,
        "tijd": tijd,
        "rol": rol,
        "notitie": notitie,
        "locatie": locatie,
        "status": status,
        "updated_at": now_iso}

    if index is None:
        item = normalize_dienst_item({
            **base,
            "source": (payload.get("source") or "manual"),
            "owner_name": current_owner,
            "created_at": now_iso})
        diensten.append(item)
    else:
        try:
            index = int(index)
            existing = normalize_dienst_item(diensten[index])
            if not dienst_can_current_user_modify(existing):
                return permission_denied_response("Je mag alleen je eigen diensten aanpassen.")
            item = normalize_dienst_item({
                **existing,
                **base,
                "owner_name": existing.get("owner_name") or current_owner,
                "created_at": existing.get("created_at") or now_iso})
            diensten[index] = item
        except Exception:
            return jsonify({"ok": False, "message": "Ongeldige dienst."}), 400
    data["diensten"] = normalize_diensten(diensten)
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
    existing = normalize_dienst_item(diensten[index])
    if not dienst_can_current_user_modify(existing):
        return permission_denied_response("Je mag alleen je eigen diensten verwijderen.")
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
    day = normalize_task_day(payload.get("day"))
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
    day = normalize_task_day(payload.get("day"))
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
    image_url = str(payload.get("image_url") or payload.get("image") or payload.get("photo") or "").strip()
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
    if not image_url:
        for existing_koeling in bar.get("koelingen", []):
            for existing_product in existing_koeling.get("producten", []):
                if product_id and existing_product.get("id") == product_id and existing_koeling.get("id") == koeling_id:
                    continue
                if (existing_product.get("naam") or "").strip().lower() == naam.lower() and str(existing_product.get("image_url") or existing_product.get("image") or existing_product.get("photo") or "").strip():
                    image_url = str(existing_product.get("image_url") or existing_product.get("image") or existing_product.get("photo") or "").strip()
                    break
            if image_url:
                break
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
                product["image_url"] = image_url
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
        "image_url": image_url,
        "op": bool(payload.get("op", False))})
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
    if not image_url:
        for existing_koeling in bar.get("koelingen", []):
            for existing_product in existing_koeling.get("producten", []):
                if product_id and existing_product.get("id") == product_id and existing_koeling.get("id") == koeling_id:
                    continue
                if (existing_product.get("naam") or "").strip().lower() == naam.lower() and str(existing_product.get("image_url") or existing_product.get("image") or existing_product.get("photo") or "").strip():
                    image_url = str(existing_product.get("image_url") or existing_product.get("image") or existing_product.get("photo") or "").strip()
                    break
            if image_url:
                break
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
    if not image_url:
        for existing_koeling in bar.get("koelingen", []):
            for existing_product in existing_koeling.get("producten", []):
                if product_id and existing_product.get("id") == product_id and existing_koeling.get("id") == koeling_id:
                    continue
                if (existing_product.get("naam") or "").strip().lower() == naam.lower() and str(existing_product.get("image_url") or existing_product.get("image") or existing_product.get("photo") or "").strip():
                    image_url = str(existing_product.get("image_url") or existing_product.get("image") or existing_product.get("photo") or "").strip()
                    break
            if image_url:
                break
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
    if not image_url:
        for existing_koeling in bar.get("koelingen", []):
            for existing_product in existing_koeling.get("producten", []):
                if product_id and existing_product.get("id") == product_id and existing_koeling.get("id") == koeling_id:
                    continue
                if (existing_product.get("naam") or "").strip().lower() == naam.lower() and str(existing_product.get("image_url") or existing_product.get("image") or existing_product.get("photo") or "").strip():
                    image_url = str(existing_product.get("image_url") or existing_product.get("image") or existing_product.get("photo") or "").strip()
                    break
            if image_url:
                break
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

    start = normalize_dienst_time_value(payload.get("start") or "")
    einde = normalize_dienst_time_value(payload.get("einde") or "")

    items = get_dienst_types()
    replaced = False
    original_start = ""
    original_einde = ""
    for item in items:
        if original and item.get("naam") == original:
            original_start = normalize_dienst_time_value(item.get("start") or "")
            original_einde = normalize_dienst_time_value(item.get("einde") or "")
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
            current_start = normalize_dienst_time_value(item.get("start") or "")
            current_einde = normalize_dienst_time_value(item.get("einde") or "")
            if not current_start or current_start == original_start:
                item["start"] = start
            if not current_einde or current_einde == original_einde:
                item["einde"] = einde
            item["tijd"] = build_dienst_time_label(item.get("start") or "", item.get("einde") or "")
            item["updated_at"] = get_now_iso_minutes()
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
    if not has_tasklist_access("kitchen"):
        return permission_denied_response("Je hebt geen rechten om keuken takenlijsten te openen.")
    data = get_kitchen_data()
    today = get_today_iso()
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
    if not has_tasklist_access("kitchen", manage=True):
        return permission_denied_response("Je hebt geen rechten om keuken takenlijsten te beheren.")
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    raw_days = payload.get("days")
    if isinstance(raw_days, list):
        days = []
        for day_value in raw_days:
            normalized = normalize_task_day(day_value)
            if normalized not in days:
                days.append(normalized)
        if not days:
            days = [normalize_task_day(payload.get("day"))]
    else:
        days = [normalize_task_day(payload.get("day"))]
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
        "day": days[0] if days else "altijd",
        "days": days,
        "tasks": []
    })
    save_kitchen_data(data)
    return jsonify({"ok": True})

@casa_cara.route("/api/kitchen/list-delete", methods=["POST"])
def kitchen_list_delete():
    if not has_tasklist_access("kitchen", manage=True):
        return permission_denied_response("Je hebt geen rechten om keuken takenlijsten te beheren.")
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    data = get_kitchen_data()
    before = len(data.get("lists", []))
    data["lists"] = [item for item in data.get("lists", []) if item.get("id") != list_id]
    if len(data["lists"]) == before:
        return jsonify({"ok": False, "message": "Takenlijst niet gevonden."}), 404
    save_kitchen_data(data)
    return jsonify({"ok": True})

@casa_cara.route("/api/kitchen/list-rename", methods=["POST"])
def kitchen_list_rename():
    if not has_tasklist_access("kitchen", manage=True):
        return permission_denied_response("Je hebt geen rechten om keuken takenlijsten te beheren.")
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    name = (payload.get("name") or "").strip()
    raw_days = payload.get("days")
    if isinstance(raw_days, list):
        days = []
        for day_value in raw_days:
            normalized = normalize_task_day(day_value)
            if normalized not in days:
                days.append(normalized)
        if not days:
            days = [normalize_task_day(payload.get("day"))]
    else:
        days = [normalize_task_day(payload.get("day"))]
    if not list_id or not name:
        return jsonify({"ok": False, "message": "Checklist gegevens ontbreken."}), 400
    data = get_kitchen_data()
    for item in data.get("lists", []):
        if item.get("id") == list_id:
            item["name"] = name
            item["day"] = days[0] if days else "altijd"
            item["days"] = days
            save_kitchen_data(data)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Takenlijst niet gevonden."}), 404

@casa_cara.route("/api/kitchen/task-save", methods=["POST"])
def kitchen_task_save():
    if not has_tasklist_access("kitchen", manage=True):
        return permission_denied_response("Je hebt geen rechten om keuken takenlijsten te beheren.")
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
    if not has_tasklist_access("kitchen", manage=True):
        return permission_denied_response("Je hebt geen rechten om keuken takenlijsten te beheren.")
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

@casa_cara.route("/api/kitchen/task-rename", methods=["POST"])
def kitchen_task_rename():
    if not has_tasklist_access("kitchen", manage=True):
        return permission_denied_response("Je hebt geen rechten om keuken takenlijsten te beheren.")
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    task_id = payload.get("task_id")
    name = (payload.get("name") or "").strip()
    if not list_id or not task_id or not name:
        return jsonify({"ok": False, "message": "Taak gegevens ontbreken."}), 400
    data = get_kitchen_data()
    for item in data.get("lists", []):
        if item.get("id") == list_id:
            for task in item.get("tasks", []):
                if task.get("id") == task_id:
                    task["name"] = name
                    save_kitchen_data(data)
                    return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Taak niet gevonden."}), 404

@casa_cara.route("/api/kitchen/task-toggle", methods=["POST"])
def kitchen_task_toggle():
    if not has_tasklist_access("kitchen"):
        return permission_denied_response("Je hebt geen rechten om keuken takenlijsten te gebruiken.")
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    task_id = payload.get("task_id")
    today = get_today_iso()
    checked_by = (get_current_casa_user() or {}).get("name", "Onbekend")
    checked_at = get_now_iso_minutes()
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
    if not has_tasklist_access("kitchen", manage=True):
        return permission_denied_response("Je hebt geen rechten om keuken takenlijsten te beheren.")
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
    if not has_tasklist_access("kitchen", manage=True):
        return permission_denied_response("Je hebt geen rechten om keuken takenlijsten te beheren.")
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
                    sync_task_with_subtasks(task, get_today_iso())
                    save_kitchen_data(data)
                    return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Taak niet gevonden."}), 404

@casa_cara.route("/api/kitchen/subtask-rename", methods=["POST"])
def kitchen_subtask_rename():
    if not has_tasklist_access("kitchen", manage=True):
        return permission_denied_response("Je hebt geen rechten om keuken takenlijsten te beheren.")
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    task_id = payload.get("task_id")
    subtask_id = payload.get("subtask_id")
    name = (payload.get("name") or "").strip()
    if not list_id or not task_id or not subtask_id or not name:
        return jsonify({"ok": False, "message": "Subtaak gegevens ontbreken."}), 400
    data = get_kitchen_data()
    for item in data.get("lists", []):
        if item.get("id") == list_id:
            for task in item.get("tasks", []):
                if task.get("id") == task_id:
                    for sub in task.get("subtasks", []):
                        if sub.get("id") == subtask_id:
                            sub["name"] = name
                            save_kitchen_data(data)
                            return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Subtaak niet gevonden."}), 404

@casa_cara.route("/api/kitchen/subtask-toggle", methods=["POST"])
def kitchen_subtask_toggle():
    if not has_tasklist_access("kitchen"):
        return permission_denied_response("Je hebt geen rechten om keuken takenlijsten te gebruiken.")
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    task_id = payload.get("task_id")
    subtask_id = payload.get("subtask_id")
    today = get_today_iso()
    checked_by = (get_current_casa_user() or {}).get("name", "Onbekend")
    checked_at = get_now_iso_minutes()
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
    if not has_tasklist_access("bar"):
        return permission_denied_response("Je hebt geen rechten om bar takenlijsten te openen.")
    data = get_bar_tasks_data()
    today = get_today_iso()
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
    if not has_tasklist_access("bar", manage=True):
        return permission_denied_response("Je hebt geen rechten om bar takenlijsten te beheren.")
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    raw_days = payload.get("days")
    if isinstance(raw_days, list):
        days = []
        for day_value in raw_days:
            normalized = normalize_task_day(day_value)
            if normalized not in days:
                days.append(normalized)
        if not days:
            days = [normalize_task_day(payload.get("day"))]
    else:
        days = [normalize_task_day(payload.get("day"))]
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
    data["lists"].append({"id": new_id, "name": name, "day": days[0] if days else "altijd", "days": days, "tasks": []})
    save_bar_tasks_data(data)
    return jsonify({"ok": True})

@casa_cara.route("/api/bar-tasks/list-delete", methods=["POST"])
def bar_list_delete():
    if not has_tasklist_access("bar", manage=True):
        return permission_denied_response("Je hebt geen rechten om bar takenlijsten te beheren.")
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    data = get_bar_tasks_data()
    before = len(data.get("lists", []))
    data["lists"] = [item for item in data.get("lists", []) if item.get("id") != list_id]
    if len(data["lists"]) == before:
        return jsonify({"ok": False, "message": "Takenlijst niet gevonden."}), 404
    save_bar_tasks_data(data)
    return jsonify({"ok": True})

@casa_cara.route("/api/bar-tasks/list-rename", methods=["POST"])
def bar_list_rename():
    if not has_tasklist_access("bar", manage=True):
        return permission_denied_response("Je hebt geen rechten om bar takenlijsten te beheren.")
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    name = (payload.get("name") or "").strip()
    raw_days = payload.get("days")
    if isinstance(raw_days, list):
        days = []
        for day_value in raw_days:
            normalized = normalize_task_day(day_value)
            if normalized not in days:
                days.append(normalized)
        if not days:
            days = [normalize_task_day(payload.get("day"))]
    else:
        days = [normalize_task_day(payload.get("day"))]
    if not list_id or not name:
        return jsonify({"ok": False, "message": "Checklist gegevens ontbreken."}), 400
    data = get_bar_tasks_data()
    for item in data.get("lists", []):
        if item.get("id") == list_id:
            item["name"] = name
            item["day"] = days[0] if days else "altijd"
            item["days"] = days
            save_bar_tasks_data(data)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Takenlijst niet gevonden."}), 404

@casa_cara.route("/api/bar-tasks/task-save", methods=["POST"])
def bar_task_save():
    if not has_tasklist_access("bar", manage=True):
        return permission_denied_response("Je hebt geen rechten om bar takenlijsten te beheren.")
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
    if not has_tasklist_access("bar", manage=True):
        return permission_denied_response("Je hebt geen rechten om bar takenlijsten te beheren.")
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

@casa_cara.route("/api/bar-tasks/task-rename", methods=["POST"])
def bar_task_rename():
    if not has_tasklist_access("bar", manage=True):
        return permission_denied_response("Je hebt geen rechten om bar takenlijsten te beheren.")
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    task_id = payload.get("task_id")
    name = (payload.get("name") or "").strip()
    if not list_id or not task_id or not name:
        return jsonify({"ok": False, "message": "Taak gegevens ontbreken."}), 400
    data = get_bar_tasks_data()
    for item in data.get("lists", []):
        if item.get("id") == list_id:
            for task in item.get("tasks", []):
                if task.get("id") == task_id:
                    task["name"] = name
                    save_bar_tasks_data(data)
                    return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Taak niet gevonden."}), 404

@casa_cara.route("/api/bar-tasks/task-toggle", methods=["POST"])
def bar_task_toggle():
    if not has_tasklist_access("bar"):
        return permission_denied_response("Je hebt geen rechten om bar takenlijsten te gebruiken.")
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    task_id = payload.get("task_id")
    today = get_today_iso()
    checked_by = (get_current_casa_user() or {}).get("name", "Onbekend")
    checked_at = get_now_iso_minutes()
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
    if not has_tasklist_access("bar", manage=True):
        return permission_denied_response("Je hebt geen rechten om bar takenlijsten te beheren.")
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
    if not has_tasklist_access("bar", manage=True):
        return permission_denied_response("Je hebt geen rechten om bar takenlijsten te beheren.")
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
                    sync_task_with_subtasks(task, get_today_iso())
                    save_bar_tasks_data(data)
                    return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Taak niet gevonden."}), 404

@casa_cara.route("/api/bar-tasks/subtask-rename", methods=["POST"])
def bar_subtask_rename():
    if not has_tasklist_access("bar", manage=True):
        return permission_denied_response("Je hebt geen rechten om bar takenlijsten te beheren.")
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    task_id = payload.get("task_id")
    subtask_id = payload.get("subtask_id")
    name = (payload.get("name") or "").strip()
    if not list_id or not task_id or not subtask_id or not name:
        return jsonify({"ok": False, "message": "Subtaak gegevens ontbreken."}), 400
    data = get_bar_tasks_data()
    for item in data.get("lists", []):
        if item.get("id") == list_id:
            for task in item.get("tasks", []):
                if task.get("id") == task_id:
                    for sub in task.get("subtasks", []):
                        if sub.get("id") == subtask_id:
                            sub["name"] = name
                            save_bar_tasks_data(data)
                            return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Subtaak niet gevonden."}), 404

@casa_cara.route("/api/bar-tasks/subtask-toggle", methods=["POST"])
def bar_subtask_toggle():
    if not has_tasklist_access("bar"):
        return permission_denied_response("Je hebt geen rechten om bar takenlijsten te gebruiken.")
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    task_id = payload.get("task_id")
    subtask_id = payload.get("subtask_id")
    today = get_today_iso()
    checked_by = (get_current_casa_user() or {}).get("name", "Onbekend")
    checked_at = get_now_iso_minutes()
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
        "username": name,
        "pin": pin,
        "code": pin,
        "role": role,
        "active": True,
        "permissions": permissions}

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



@casa_cara.route("/api/manage/dish-import-preview", methods=["POST"])
def manage_dish_import_preview():
    if not has_casa_permission("manage_diensten"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    try:
        month = int(payload.get("month") or 0)
        year = int(payload.get("year") or 0)
        if month < 1 or month > 12 or year < 2020 or year > 2100:
            raise ValueError
    except Exception:
        return jsonify({"ok": False, "message": "Kies een geldige maand en jaar."}), 400

    try:
        items = build_dish_import_preview(
            payload.get("image_data") or "",
            year,
            month,
            payload.get("color_map") or {},
            payload.get("include_colors") or ["blue"],
        )
        return jsonify({"ok": True, "items": items})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc) or "Kon de DISH screenshot niet verwerken."}), 400


@casa_cara.route("/api/manage/dish-import-apply", methods=["POST"])
def manage_dish_import_apply():
    if not has_casa_permission("manage_diensten"):
        return permission_denied_response()
    payload = request.get_json(silent=True) or {}
    raw_items = payload.get("items") or []
    if not isinstance(raw_items, list) or not raw_items:
        return jsonify({"ok": False, "message": "Geen diensten om te importeren."}), 400

    data = get_general_data()
    diensten = [normalize_dienst_item(item) for item in data.get("diensten", [])]
    existing_keys = {
        (
            str(item.get("datum") or "").strip(),
            str(item.get("naam") or "").strip().lower(),
            str(item.get("start") or "").strip(),
            str(item.get("einde") or "").strip(),
            str(item.get("source") or "manual").strip(),
            str(item.get("owner_name") or "").strip().lower(),
        )
        for item in diensten
    }

    added = 0
    now_iso = get_now_iso_minutes()
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        naam = (raw.get("naam") or "").strip()
        datum = (raw.get("datum") or "").strip()
        if not naam or not datum:
            continue
        start, einde, tijd = extract_dienst_times(raw.get("start") or "", raw.get("einde") or "", raw.get("tijd") or "")
        source = (raw.get("source") or "dish_screenshot").strip() or "dish_screenshot"
        owner_name = current_casa_owner_name()
        key = (datum, naam.lower(), start, einde, source, owner_name.lower())
        if key in existing_keys:
            continue
        existing_keys.add(key)
        diensten.append(normalize_dienst_item({
            "naam": naam,
            "datum": datum,
            "start": start,
            "einde": einde,
            "tijd": tijd,
            "status": normalize_dienst_status(raw.get("status") or "ingepland"),
            "source": source,
            "owner_name": owner_name,
            "notitie": str(raw.get("notitie") or "").strip(),
            "rol": str(raw.get("rol") or "").strip(),
            "created_at": now_iso,
            "updated_at": now_iso,
            "last_synced_at": now_iso}))
        added += 1

    diensten.sort(key=lambda item: ((item.get("datum") or "9999-99-99"), normalize_dienst_time_value(item.get("start") or "23:59"), (item.get("naam") or "").lower()))
    data["diensten"] = diensten
    save_general_data(data)
    return jsonify({"ok": True, "message": f"{added} dienst{'en' if added != 1 else ''} toegevoegd."})


@casa_cara.route("/casa-cara-logout")
def casa_cara_logout():
    for key in ["casa_logged_in", "casa_user_pin", "casa_user_name", "casa_user_role"]:
        session.pop(key, None)
    return redirect("/casa-cara-login")
