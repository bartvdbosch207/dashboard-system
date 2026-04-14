
from flask import Blueprint, render_template_string, jsonify, request
import json
from pathlib import Path

casa_cara = Blueprint("casa_cara", __name__)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "casa_cara"

BAR_FILE = DATA_DIR / "bar_koelingen.json"
GENERAL_FILE = DATA_DIR / "algemeen.json"
PRODUCT_TYPES_FILE = DATA_DIR / "product_soorten.json"
LOCATIONS_FILE = DATA_DIR / "locaties.json"
DIENST_TYPES_FILE = DATA_DIR / "dienst_soorten.json"
KITCHEN_FILE = DATA_DIR / "kitchen_tasks.json"
RECIPES_FILE = DATA_DIR / "recipes.json"

def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

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
    data = load_json(GENERAL_FILE, {"fooienpot": 0, "diensten": []})
    if not isinstance(data, dict):
        data = {"fooienpot": 0, "diensten": []}
    data.setdefault("fooienpot", 0)
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


def get_kitchen_data():
    data = load_json(KITCHEN_FILE, {"lists": []})
    if not isinstance(data, dict):
        data = {"lists": []}
    data.setdefault("lists", [])
    return data

def save_kitchen_data(data):
    save_json(KITCHEN_FILE, data)

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
    return {
        "bar": {
            "koelingen": bar_data.get("koelingen", []),
            "fill_items": build_fill_items(bar_data),
        },
        "general": general_data,
        "types": get_types(),
        "locations": get_locations(),
        "dienst_types": get_dienst_types(),
        "kitchen": get_kitchen_data(),
        "recipes": get_recipes_data(),
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
      background:linear-gradient(180deg,#070b12,#0b111a 60%,#070b12);
      color:var(--text);
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,system-ui,sans-serif;
      overscroll-behavior:none;
    }
    body{touch-action:manipulation}
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
      gap:12px;
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
      background:rgba(255,255,255,.015);
      border-radius:14px;
      padding:12px;
    }
    .recipe-card{
      border:1px solid var(--line);
      background:rgba(255,255,255,.02);
      border-radius:18px;
      padding:14px;
    }
    @media (max-width:640px){
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
      margin-top:14px;
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
    .ktask{
      border:1px solid var(--line);
      background:rgba(255,255,255,.02);
      border-radius:18px;
      padding:14px;
      box-shadow:0 10px 24px rgba(0,0,0,.12);
    }
    .ktask-row,.ksub-row{
      display:flex;
      align-items:flex-start;
      gap:12px;
      cursor:pointer;
    }
    .kcheck{
      width:30px;
      height:30px;
      min-width:30px;
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
      font-size:15px;
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
      font-size:13px;
      margin-top:4px;
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
      background:rgba(255,255,255,.015);
      border-radius:14px;
      padding:12px;
    }
    .ksub-title{
      font-size:14px;
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
      .klist-card,.ktask,.ksub{padding:13px}
      .klist-icon{width:34px;height:34px;min-width:34px}
      .klist-name{font-size:15px}
      .kprogress{margin-top:10px}
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
        <button class="sub-btn" data-page="dienstsoorten" onclick="openPage('dienstsoorten'); closeDrawer();">Dienstsoorten</button>
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
        <button class="sub-btn" data-page="bar-productsoorten" onclick="openPage('bar-productsoorten'); closeDrawer();">Productsoorten</button>
        <button class="sub-btn" data-page="bar-locaties" onclick="openPage('bar-locaties'); closeDrawer();">Locaties</button>
        <button class="sub-btn" data-page="bar-oplijst" onclick="openPage('bar-oplijst'); closeDrawer();">Op / niet op voorraad</button>
        <button class="sub-btn" data-page="bar-bijvullen" onclick="openPage('bar-bijvullen'); closeDrawer();">Bijvuloverzicht</button>
      </div>
    </nav>

    <div class="logout-wrap">
      <a class="home-btn" href="/">← Terug naar home</a>
      <a class="logout-btn" href="/logout">⎋ Uitloggen</a>
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
        <div class="stats-grid">
          <button class="stat-card" onclick="openPage('bar-koelingen')">
            <div class="stat-label">Bar</div>
            <div class="stat-value" style="font-size:22px">Koelingen</div>
            <div class="stat-sub">Overzicht per koeling en status</div>
          </button>
          <button class="stat-card" onclick="openPage('bar-productsoorten')">
            <div class="stat-label">Bar</div>
            <div class="stat-value" style="font-size:22px">Productsoorten</div>
            <div class="stat-sub">Geordend per soort en locatie</div>
          </button>
          <button class="stat-card" onclick="openPage('bar-locaties')">
            <div class="stat-label">Bar</div>
            <div class="stat-value" style="font-size:22px">Locaties</div>
            <div class="stat-sub">Opslagplekken en indeling</div>
          </button>
          <button class="stat-card" onclick="openPage('bar-bijvullen')">
            <div class="stat-label">Bar</div>
            <div class="stat-value" style="font-size:22px">Bijvullen</div>
            <div class="stat-sub">Wat direct aandacht nodig heeft</div>
          </button>
        </div>
      </div>
    </section>

    <section class="page" id="page-algemeen-dashboard">
      <div class="hero">
        <h1>📋 Algemeen overzicht</h1>
        <p>Alles wat niet specifiek bij keuken of bar hoort, op één rustige plek.</p>
      </div>
      <div class="stack">
        <div class="panel">
          <div class="panel-head">
            <div style="display:flex;align-items:center;gap:10px">
              <div class="stat-icon">€</div>
              <h3 class="panel-title">Fooienpot</h3>
            </div>
            <div class="actions">
              <span class="badge accent" id="tipsBadge">€ 0,00</span>
              <button class="btn accent" onclick="openTipsModal()">Aanpassen</button>
            </div>
          </div>
          <div class="item-sub">Huidige stand van de fooienpot op basis van je bestaande data.</div>
        </div>
        <div class="panel">
          <div class="panel-head">
            <div style="display:flex;align-items:center;gap:10px">
              <div class="stat-icon">👥</div>
              <h3 class="panel-title">Diensten</h3>
            </div>
            <div class="actions">
              <span class="badge" id="dienstenBadge">0 gepland</span>
              <button class="btn accent" onclick="openDienstModal()">Dienst toevoegen</button>
            </div>
          </div>
          <div class="item-sub">Gebruik dit als rustige verzamelplek voor de dag- en weekindeling.</div>
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
          <button class="btn accent" onclick="openDienstModal()">Nieuwe dienst</button>
        </div>
        <div class="list" id="dienstenList"></div>
      </div>
    </section>

    <section class="page" id="page-dienstsoorten">
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
          <button class="btn accent" onclick="openDienstTypeModal()">Dienstsoort toevoegen</button>
        </div>
        <div class="list" id="dienstTypesList"></div>
      </div>
    </section>

    <section class="page" id="page-fooienpot">
      <div class="hero">
        <h1>💰 Fooienpot</h1>
        <p>De huidige stand uit je bestaande Casa Cara data.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Stand</h3>
          <div class="actions">
            <span class="badge accent" id="tipsPageAmount">€ 0,00</span>
            <button class="btn accent" onclick="openTipsModal()">Aanpassen</button>
          </div>
        </div>
        <div class="item-sub">Deze pagina is nu ook direct bewerkbaar, zonder terug te vallen op de oude alles-in-één pagina.</div>
      </div>
    </section>

    <section class="page" id="page-keuken-overzicht">
      <div class="hero">
        <h1>🍳 Keuken</h1>
        <p>De keuken krijgt dezelfde rustige structuur als Bar. Je takenlijsten en recepten krijgen een eigen vaste plek, zodat alles overzichtelijk blijft.</p>
      </div>
      <div class="stats-grid">
        <button class="stat-card" onclick="openPage('keuken-takenlijsten')">
          <div class="stat-icon">☑</div>
          <div class="stat-label">Keuken</div>
          <div class="stat-value" id="kitchenListCount">0</div>
          <div class="stat-sub">Takenlijsten</div>
        </button>
        <button class="stat-card" onclick="openPage('keuken-takenlijsten')">
          <div class="stat-icon">✓</div>
          <div class="stat-label">Vandaag</div>
          <div class="stat-value" id="kitchenTaskCount">0</div>
          <div class="stat-sub">Taken in totaal</div>
        </button>
        <button class="stat-card" onclick="openPage('keuken-recepten')">
          <div class="stat-icon">🍝</div>
          <div class="stat-label">Keuken</div>
          <div class="stat-value" id="recipeCount">0</div>
          <div class="stat-sub">Recepten</div>
        </button>
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
          <button class="btn accent" onclick="openKitchenListModal()">Takenlijst toevoegen</button>
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
            <button class="btn accent" onclick="openKitchenManagePage(window.currentKitchenListId)">⚙️ Beheer</button>
          </div>
        </div>
        <div class="list" id="kitchenDetailList"></div>
      </div>
    </section>

    <section class="page" id="page-keuken-takenlijst-beheer">
      <div class="hero">
        <h1 id="kitchenManageTitle">⚙️ Takenlijst beheren</h1>
        <p>Pas hier alleen de inhoud van deze takenlijst aan. De checklist zelf blijft rustig voor gebruik op de werkvloer.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Beheer</h3>
          <div class="actions">
            <button class="btn" onclick="openPage('keuken-takenlijst-detail')">Terug naar checklist</button>
            <button class="btn accent" onclick="openKitchenTaskModal(window.currentKitchenListId)">+ Taak toevoegen</button>
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
          <button class="btn accent" onclick="openRecipeModal()">Recept toevoegen</button>
        </div>
        <div class="list" id="recipesList"></div>
      </div>
    </section>

    <section class="page" id="page-bar-overzicht">
      <div class="hero">
        <h1>🍸 Bar overzicht</h1>
        <p>De bar-sectie is nu opgesplitst in losse pagina’s met beheeracties op de juiste plek.</p>
      </div>
      <div class="stats-grid">
        <button class="stat-card" onclick="openPage('bar-koelingen')">
          <div class="stat-icon">❄</div><div class="stat-label">Bar</div>
          <div class="stat-value" id="barOverviewCoolers">0</div>
          <div class="stat-sub">Koelingen</div>
        </button>
        <button class="stat-card" onclick="openPage('bar-productsoorten')">
          <div class="stat-icon">◫</div><div class="stat-label">Bar</div>
          <div class="stat-value" id="barOverviewTypes">0</div>
          <div class="stat-sub">Productsoorten</div>
        </button>
        <button class="stat-card" onclick="openPage('bar-locaties')">
          <div class="stat-icon">⌖</div><div class="stat-label">Bar</div>
          <div class="stat-value" id="barOverviewLocations">0</div>
          <div class="stat-sub">Locaties</div>
        </button>
        <button class="stat-card" onclick="openPage('bar-bijvullen')">
          <div class="stat-icon">!</div><div class="stat-label">Bar</div>
          <div class="stat-value" id="barOverviewFill">0</div>
          <div class="stat-sub">Bijvullen nodig</div>
        </button>
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
          <button class="btn accent" onclick="openKoelingModal()">Koeling toevoegen</button>
        </div>
        <div class="actions" style="margin-bottom:12px">
          <select id="koelingFilterLocatie" class="btn" onchange="renderCoolers()"></select>
          <select id="koelingFilterSoort" class="btn" onchange="renderCoolers()"></select>
        </div>
        <div class="list" id="coolersList"></div>
      </div>
    </section>

    <section class="page" id="page-bar-productsoorten">
      <div class="hero">
        <h1>🏷️ Bar · Productsoorten</h1>
        <p>Je productsoorten in een vaste volgorde, met de gekoppelde locatie erbij.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Productsoorten</h3>
          <button class="btn accent" onclick="openTypeModal()">Productsoort toevoegen</button>
        </div>
        <div class="list" id="typesList"></div>
      </div>
    </section>

    <section class="page" id="page-bar-locaties">
      <div class="hero">
        <h1>📍 Bar · Locaties</h1>
        <p>Alle locaties overzichtelijk onder elkaar, nu ook direct bewerkbaar.</p>
      </div>
      <div class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Locaties</h3>
          <button class="btn accent" onclick="openLocationModal()">Locatie toevoegen</button>
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
            <button class="btn accent" onclick="openProductModal(window.currentKoelingId)">Product toevoegen</button>
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
  let appData = { bar: { koelingen: [], fill_items: [] }, general: { fooienpot: 0, diensten: [] }, types: [], locations: [] };
  let currentPage = 'dashboard';
  let currentKoelingId = null;
  let currentKitchenListId = null;
  window.currentKoelingId = null;
  window.currentKitchenListId = null;

  function euro(value){
    const num = Number(value || 0);
    return new Intl.NumberFormat('nl-NL', { style: 'currency', currency: 'EUR' }).format(num);
  }
  function setText(id, value){
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }
  function pageId(name){ return 'page-' + name; }
  function safeArray(value){ return Array.isArray(value) ? value : []; }

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

  function toggleGroup(group){
    const list = document.getElementById('group-' + group);
    const toggle = document.getElementById('toggle-' + group);
    list.classList.toggle('open');
    toggle.classList.toggle('expanded');
  }

  function activateNav(page){
    document.querySelectorAll('.nav-btn[data-page], .sub-btn[data-page]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.page === page);
    });
  }

  function pageMeta(page){
    const map = {
      'dashboard': ['Dashboard', 'Casa Cara'],
      'algemeen-dashboard': ['Algemeen', 'Overzicht'],
      'diensten': ['Algemeen', 'Diensten'],
      'dienstsoorten': ['Algemeen', 'Dienstsoorten'],
      'fooienpot': ['Algemeen', 'Fooienpot'],
      'keuken-overzicht': ['Keuken', 'Overzicht'],
      'keuken-takenlijsten': ['Keuken', 'Takenlijsten'],
      'keuken-takenlijst-detail': ['Keuken', 'Takenlijst'],
      'keuken-takenlijst-beheer': ['Keuken', 'Takenlijst beheren'],
      'keuken-recepten': ['Keuken', 'Recepten'],
      'bar-overzicht': ['Bar', 'Overzicht'],
      'bar-koelingen': ['Bar', 'Koelingen'],
      'bar-productsoorten': ['Bar', 'Productsoorten'],
      'bar-locaties': ['Bar', 'Locaties'],
      'bar-oplijst': ['Bar', 'Op / niet op voorraad'],
      'bar-bijvullen': ['Bar', 'Bijvuloverzicht'],
      'bar-koeling-detail': ['Bar', 'Koeling detail'],
    };
    return map[page] || ['Casa Cara', 'Overzicht'];
  }

  function openPage(page){
    currentPage = page;
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const el = document.getElementById(pageId(page));
    if (el) el.classList.add('active');
    const [kicker, title] = pageMeta(page);
    setText('topKicker', kicker);
    setText('topTitle', title);
    activateNav(page);
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
              <button class="btn accent" onclick="openProductModal('${koeling.id}','${product.id}')">Bewerken</button>
              <button class="btn danger" onclick="confirmAction('Product verwijderen','Weet je zeker dat je dit product wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteProduct','${koeling.id}','${product.id}')&quot;)">Verwijderen</button>
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
              <button class="btn accent" onclick="closeModal(); openProductModal('${koeling.id}','${product.id}')">Bewerken</button>
            </div>
          </div>
        </div>
      `
    );
  }

  function renderDashboard(){
    const koelingen = safeArray(appData.bar.koelingen);
    const fill = safeArray(appData.bar.fill_items);
    const diensten = safeArray(appData.general.diensten);
    const types = safeArray(appData.types);
    const locations = safeArray(appData.locations);
    const tips = appData.general.fooienpot || 0;

    setText('statLowStock', String(fill.length));
    setText('statCoolers', String(koelingen.length));
    setText('statTips', euro(tips));
    setText('statShifts', String(diensten.length));

    setText('tipsBadge', euro(tips));
    setText('dienstenBadge', `${diensten.length} gepland`);
    setText('tipsPageAmount', euro(tips));

    setText('barOverviewCoolers', String(koelingen.length));
    setText('barOverviewTypes', String(types.length));
    setText('barOverviewLocations', String(locations.length));
    setText('barOverviewFill', String(fill.length));
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
              <button class="btn accent" onclick="openKoelingModal('${koeling.id}')">Bewerken</button>
              <button class="btn" onclick="openProductModal('${koeling.id}')">Product toevoegen</button>
              <button class="btn danger" onclick="confirmAction('Koeling verwijderen','Weet je zeker dat je deze koeling wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteKoeling','${koeling.id}')&quot;)">Verwijderen</button>
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
          <div class="item-actions">
            <button class="btn accent" onclick="openTypeModal('${encodeURIComponent(type.naam)}')">Bewerken</button>
            <button class="btn danger" onclick="confirmAction('Productsoort verwijderen','Weet je zeker dat je deze productsoort wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteType','${encodeURIComponent(type.naam)}')&quot;)">Verwijderen</button>
          </div>
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
            <div class="item-actions">
              <button class="btn accent" onclick="openLocationModal('${encodeURIComponent(location)}')">Bewerken</button>
              <button class="btn danger" onclick="confirmAction('Locatie verwijderen','Weet je zeker dat je deze locatie wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteLocation','${encodeURIComponent(location)}')&quot;)">Verwijderen</button>
            </div>
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
            <button class="btn accent" onclick="openProductModal('${item.koeling_id}','${item.id}')">Bewerken</button>
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
            <button class="btn accent" onclick="openProductModal('${item.koeling_id}','${item.product_id}')">Bewerken</button>
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

  function renderKitchen(){
    const kitchen = appData.kitchen || { lists: [] };
    const lists = safeArray(kitchen.lists);
    const taskCount = lists.reduce((total, lst) => total + safeArray(lst.tasks).length, 0);

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
              <button class="btn danger" onclick="confirmAction('Takenlijst verwijderen','Weet je zeker dat je deze takenlijst wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteKitchenList','${list.id}')&quot;)">Verwijderen</button>
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

    renderList(
      'kitchenDetailList',
      tasks,
      (task) => `
        <div class="ktask">
          <div class="ktask-row" onclick="toggleKitchenTask('${list.id}','${task.id}')">
            <div class="kcheck ${kitchenTaskIsChecked(task) ? 'done' : ''}">${kitchenTaskIsChecked(task) ? '✓' : ''}</div>
            <div style="min-width:0;flex:1">
              <div class="ktask-title ${kitchenTaskIsChecked(task) ? 'done' : ''}">${task.name || 'Taak'}</div>
              <div class="ktask-meta">${safeArray(task.subtasks).length} subtaken</div>
            </div>
            <span class="badge ${kitchenTaskIsChecked(task) ? 'good' : 'warn'}">${kitchenTaskIsChecked(task) ? 'Gedaan' : 'Open'}</span>
          </div>
          ${safeArray(task.subtasks).length ? `
            <div class="ksub-wrap">
              ${safeArray(task.subtasks).map(sub => `
                <div class="ksub">
                  <div class="ksub-row" onclick="toggleKitchenSubtask('${list.id}','${task.id}','${sub.id}')">
                    <div class="kcheck ${kitchenSubtaskIsChecked(sub) ? 'done' : ''}" style="width:24px;height:24px;min-width:24px;font-size:12px">${kitchenSubtaskIsChecked(sub) ? '✓' : ''}</div>
                    <div style="min-width:0;flex:1">
                      <div class="ksub-title ${kitchenSubtaskIsChecked(sub) ? 'done' : ''}">${sub.name || 'Subtaak'}</div>
                    </div>
                    <span class="badge ${kitchenSubtaskIsChecked(sub) ? 'good' : ''}">${kitchenSubtaskIsChecked(sub) ? 'Gedaan' : 'Open'}</span>
                  </div>
                </div>
              `).join('')}
            </div>
          ` : ''}
        </div>
      `,
      'Nog geen taken in deze lijst.'
    );
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
            <button class="btn accent" onclick="openRecipeModal(${index})">Bewerken</button>
            <button class="btn danger" onclick="confirmAction('Recept verwijderen','Weet je zeker dat je dit recept wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteRecipe',${index})&quot;)">Verwijderen</button>
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
              <button class="btn accent" onclick="closeModal(); openRecipeModal(${index})">Bewerken</button>
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

  function renderDiensten(){
    const diensten = safeArray(appData.general.diensten);
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
          <div class="item-actions">
            <button class="btn accent" onclick="openDienstModal(${index})">Bewerken</button>
            <button class="btn danger" onclick="confirmAction('Dienst verwijderen','Weet je zeker dat je deze dienst wilt verwijderen?','Verwijderen', &quot;doConfirmed('deleteDienst',${index})&quot;)">Verwijderen</button>
          </div>
        </div>
      `,
      'Nog geen diensten gevonden.'
    );
  }

  function renderAll(){
    initFilters();
    renderDashboard();
    renderCoolers();
    renderTypes();
    renderLocations();
    renderStockAlerts();
    renderFill();
    renderDiensten();
    renderDienstTypes();
    renderKitchen();
    renderKitchenManagePage();
    renderRecipes();
    if (currentPage === 'bar-koeling-detail' && currentKoelingId){
      renderKoelingDetail();
    }
    if (currentPage === 'keuken-takenlijst-detail' && currentKitchenListId){
      renderKitchenListDetail();
    }
  }

  async function loadData(){
    const res = await fetch('/api/casa-data');
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
      'Voer een bedrag in en kies of dit erbij of eraf moet.',
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
          <div class="actions">
            <button class="btn" onclick="openDienstTypeModal()">Dienstsoort toevoegen</button>
            <button class="btn" onclick="openPage('dienstsoorten'); closeModal()">Beheer dienstsoorten</button>
          </div>
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

    bar = get_bar_data()
    koeling = next((k for k in bar.get("koelingen", []) if k.get("id") == koeling_id), None)
    if not koeling:
        return jsonify({"ok": False, "message": "Koeling niet gevonden."}), 404

    koeling.setdefault("producten", [])
    if product_id:
        for product in koeling["producten"]:
            if product.get("id") == product_id:
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

    new_id = slugify(naam)
    existing = {p.get("id") for p in koeling["producten"]}
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
    today = __import__("datetime").date.today().isoformat()
    changed = False
    for item in data.get("lists", []):
        for task in item.get("tasks", []):
            if task.get("last_checked") != today and task.get("checked"):
                task["checked"] = False
                changed = True
            for sub in task.get("subtasks", []):
                if sub.get("last_checked") != today and sub.get("checked"):
                    sub["checked"] = False
                    changed = True
    if changed:
        save_kitchen_data(data)
    return jsonify(data)

@casa_cara.route("/api/kitchen/list-save", methods=["POST"])
def kitchen_list_save():
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
                "subtasks": []
            })
            save_kitchen_data(data)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Takenlijst niet gevonden."}), 404

@casa_cara.route("/api/kitchen/task-delete", methods=["POST"])
def kitchen_task_delete():
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
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    task_id = payload.get("task_id")
    today = __import__("datetime").date.today().isoformat()
    data = get_kitchen_data()
    for item in data.get("lists", []):
        if item.get("id") == list_id:
            for task in item.get("tasks", []):
                if task.get("id") == task_id:
                    is_checked = bool(task.get("checked")) and task.get("last_checked") == today
                    task["checked"] = not is_checked
                    task["last_checked"] = today if not is_checked else ""
                    save_kitchen_data(data)
                    return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Taak niet gevonden."}), 404

@casa_cara.route("/api/kitchen/subtask-save", methods=["POST"])
def kitchen_subtask_save():
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
                        "last_checked": ""
                    })
                    save_kitchen_data(data)
                    return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Taak niet gevonden."}), 404

@casa_cara.route("/api/kitchen/subtask-delete", methods=["POST"])
def kitchen_subtask_delete():
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
                    save_kitchen_data(data)
                    return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Taak niet gevonden."}), 404

@casa_cara.route("/api/kitchen/subtask-toggle", methods=["POST"])
def kitchen_subtask_toggle():
    payload = request.get_json(silent=True) or {}
    list_id = payload.get("list_id")
    task_id = payload.get("task_id")
    subtask_id = payload.get("subtask_id")
    today = __import__("datetime").date.today().isoformat()
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
                            save_kitchen_data(data)
                            return jsonify({"ok": True})
    return jsonify({"ok": False, "message": "Subtaak niet gevonden."}), 404


@casa_cara.route("/api/recipes/save", methods=["POST"])
def recipe_save():
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
