import os
import sys
import json
import base64
import pickle
import subprocess
from datetime import datetime

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

BASE_DIR = "/Users/bartvandenbosch/Desktop/Dropbox"
SYSTEM_DIR = os.path.join(BASE_DIR, "System")

DOWNLOAD_MAP = BASE_DIR
SORTEER_SCRIPT = os.path.join(SYSTEM_DIR, "sorteer.py")
CREDENTIALS_FILE = os.path.join(SYSTEM_DIR, "credentials.json")
TOKEN_FILE = os.path.join(SYSTEM_DIR, "token_gmail.pkl")
PROCESSED_DOWNLOADS_FILE = os.path.join(BASE_DIR, "processed_downloads.json")
PROCESSED_MESSAGES_FILE = os.path.join(BASE_DIR, "processed_messages.json")
STATS_FILE = os.path.join(BASE_DIR, "dashboard_stats.json")
TRASH_HISTORY_FILE = os.path.join(BASE_DIR, "trash_history.json")
DOWNLOAD_HISTORY_FILE = os.path.join(BASE_DIR, "downloads_history.json")
KEPT_HISTORY_FILE = os.path.join(BASE_DIR, "kept_history.json")
ACTIVITY_HISTORY_FILE = os.path.join(BASE_DIR, "activity_history.json")
PENDING_TRASH_FILE = os.path.join(BASE_DIR, "pending_trash.json")
LOCK_FILE = os.path.join(BASE_DIR, "run.lock")

NOOIT_VERWIJDEREN = [
    "veiligheid@mborijnland.nl", "no-reply@mborijnland.nl", "loonstrook", "factuur",
    "noreply@mijn.overheid.nl", "studentzaken@mborijnland.nl", "noreply@zorgenzekerheid.nl",
    "_noreply@odido.nl", "jeugdvoorzitter@rijnsburgseboys.nl", "loondesk@vanwezelacc.nl",
    "mlander@mborijnland.nl", "info@mborijnland.nl", "no-reply@cbr.nl",
    "reply@email.duo.nl", "noreply@studielink.nl",
]

BELANGRIJK = [
    "factuur", "invoice", "belasting", "tax", "overheid", "bank", "rekening", "rabobank",
    "verzekering", "zorg en zekerheid", "rijnsburgse boys", "loon", "salary", "payslip",
    "mborijnland", "htv", "school"
]

ONGEWENST = [
    "nieuwsbrief", "unsubscribe", "afmelden", "sale", "korting", "actie", "deal",
    "promo", "advertentie", "aanbieding", "social", "notification", "update",
    "black friday", "cyber monday", "marketing", "campaign", "campagne"
]

MAX_RESULTS_PER_PAGE = 200
MAX_HISTORY = 500

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


def now_str():
    return datetime.now().strftime("%d-%m-%Y %H:%M:%S")


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(temp_path, path)


def append_history(path, item):
    items = load_json(path, [])
    items.append(item)
    save_json(path, items[-MAX_HISTORY:])


def load_stats():
    stats = DEFAULT_STATS.copy()
    stats.update(load_json(STATS_FILE, {}))
    return stats


def save_stats(stats):
    save_json(STATS_FILE, stats)


def add_log(stats, message):
    entry = {"time": now_str(), "message": message}
    stats.setdefault("logs", [])
    stats["logs"].append(entry)
    stats["logs"] = stats["logs"][-50:]
    append_history(ACTIVITY_HISTORY_FILE, entry)


def reset_run_deltas(stats):
    for key in [
        "run_scanned_delta",
        "run_pdfs_delta",
        "run_trashed_delta",
        "run_protected_delta",
        "run_important_delta",
        "run_duplicate_delta",
    ]:
        stats[key] = 0


def is_locked():
    return os.path.exists(LOCK_FILE)


def create_lock():
    with open(LOCK_FILE, "w", encoding="utf-8") as f:
        f.write(now_str())


def remove_lock():
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
        except Exception:
            pass


def get_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, 'wb') as f:
            pickle.dump(creds, f)

    return build('gmail', 'v1', credentials=creds)


def get_all_messages(service, query):
    messages = []
    page_token = None

    while True:
        response = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=MAX_RESULTS_PER_PAGE,
            pageToken=page_token
        ).execute()

        messages.extend(response.get('messages', []))
        page_token = response.get('nextPageToken')

        if not page_token:
            break

    return messages


def get_message(service, msg_id):
    try:
        return service.users().messages().get(userId='me', id=msg_id, format='full').execute()
    except Exception:
        return None


def get_header(msg, name):
    headers = msg.get('payload', {}).get('headers', [])
    for h in headers:
        if h.get('name', '').lower() == name.lower():
            return h.get('value', '')
    return ""


def extract_parts(payload):
    parts = []
    if 'parts' in payload:
        for part in payload['parts']:
            parts.extend(extract_parts(part))
    else:
        parts.append(payload)
    return parts


def has_pdf(msg):
    return any(
        part.get('filename', '').lower().endswith('.pdf')
        for part in extract_parts(msg.get('payload', {}))
    )


def is_match(text, keywords):
    text = text.lower()
    return any(k.lower() in text for k in keywords)


def save_pdf_attachment(service, msg, msg_id, processed_downloads, stats):
    subject = get_header(msg, "subject")
    sender = get_header(msg, "from")
    text = f"{subject} {sender}".lower()

    if not is_match(text, BELANGRIJK) and not is_match(text, NOOIT_VERWIJDEREN):
        return

    for part in extract_parts(msg.get('payload', {})):
        filename = part.get('filename', '')
        body = part.get('body', {})

        if filename.lower().endswith('.pdf') and body.get('attachmentId'):
            unique_key = f"{msg_id}:{filename}"

            if unique_key in processed_downloads:
                stats["duplicate_skipped"] += 1
                stats["run_duplicate_delta"] += 1
                add_log(stats, f"Dubbele download overgeslagen: {filename}")
                continue

            try:
                attachment = service.users().messages().attachments().get(
                    userId='me',
                    messageId=msg_id,
                    id=body['attachmentId']
                ).execute()

                data = base64.urlsafe_b64decode(attachment['data'].encode('UTF-8'))
                filepath = os.path.join(DOWNLOAD_MAP, filename)

                if os.path.exists(filepath):
                    stats["duplicate_skipped"] += 1
                    stats["run_duplicate_delta"] += 1
                    add_log(stats, f"Bestand bestond al, skip: {filename}")
                    processed_downloads.add(unique_key)
                    continue

                with open(filepath, 'wb') as f:
                    f.write(data)

                subprocess.run(
                    ["/Library/Frameworks/Python.framework/Versions/3.14/bin/python3", SORTEER_SCRIPT, filepath],
                    check=False
                )

                processed_downloads.add(unique_key)
                stats["pdfs_downloaded"] += 1
                stats["run_pdfs_delta"] += 1
                add_log(stats, f"PDF gedownload en verwerkt: {filename}")
                append_history(DOWNLOAD_HISTORY_FILE, {
                    "time": now_str(),
                    "filename": filename,
                    "subject": subject,
                    "sender": sender,
                    "message_id": msg_id
                })
            except Exception as e:
                add_log(stats, f"Fout bij PDF {filename}: {e}")


def parse_mode():
    if "--approve-trash" in sys.argv[1:]:
        return "approve"

    if "--reject-trash" in sys.argv[1:]:
        return "reject"

    for arg in sys.argv[1:]:
        if arg.startswith("--mode="):
            mode = arg.split("=", 1)[1].strip().lower()
            if mode in {"full", "cleanup", "pdfs"}:
                return mode

    return "full"


def approve_pending_trash():
    if is_locked():
        stats = load_stats()
        stats["last_status"] = "Er draait al een Gmail-check"
        add_log(stats, "Goedkeuren geblokkeerd: er draait al een proces")
        save_stats(stats)
        return

    create_lock()

    try:
        stats = load_stats()
        reset_run_deltas(stats)
        stats["is_running"] = True
        stats["last_status"] = "Goedgekeurde mails worden verplaatst"
        save_stats(stats)

        items = load_json(PENDING_TRASH_FILE, [])
        if not items:
            stats["is_running"] = False
            stats["progress_current"] = 0
            stats["progress_total"] = 0
            stats["last_status"] = "Geen wachtende mails gevonden"
            save_stats(stats)
            return

        service = get_service()
        stats["progress_total"] = len(items)
        stats["progress_current"] = 0
        save_stats(stats)

        for idx, item in enumerate(items, start=1):
            stats["progress_current"] = idx
            save_stats(stats)

            try:
                service.users().messages().trash(userId='me', id=item["message_id"]).execute()
                stats["emails_trashed"] += 1
                stats["run_trashed_delta"] += 1
                add_log(stats, f"Naar prullenbak: {item.get('subject', '')}")
                append_history(TRASH_HISTORY_FILE, {
                    "time": now_str(),
                    "subject": item.get("subject", ""),
                    "sender": item.get("sender", ""),
                    "message_id": item.get("message_id", "")
                })
            except Exception as e:
                add_log(stats, f"Fout bij prullenbak: {e}")

        save_json(PENDING_TRASH_FILE, [])
        stats["is_running"] = False
        stats["progress_current"] = stats["progress_total"]
        stats["last_status"] = "Goedgekeurde mails zijn naar prullenbak verplaatst"
        save_stats(stats)

    finally:
        remove_lock()


def reject_pending_trash():
    if is_locked():
        stats = load_stats()
        stats["last_status"] = "Er draait al een Gmail-check"
        add_log(stats, "Afwijzen geblokkeerd: er draait al een proces")
        save_stats(stats)
        return

    create_lock()

    try:
        stats = load_stats()
        save_json(PENDING_TRASH_FILE, [])
        stats["progress_current"] = 0
        stats["progress_total"] = 0
        stats["last_status"] = "Prullenbak-goedkeuring geannuleerd"
        add_log(stats, "Wachtende prullenbak-lijst geannuleerd vanuit dashboard")
        save_stats(stats)
    finally:
        remove_lock()


def cleanup(mode="full"):
    if is_locked():
        stats = load_stats()
        stats["last_status"] = "Er draait al een Gmail-check"
        add_log(stats, "Nieuwe run geblokkeerd: er draait al een proces")
        save_stats(stats)
        return

    create_lock()

    try:
        service = get_service()

        stats = load_stats()
        reset_run_deltas(stats)
        stats["last_run"] = now_str()
        stats["last_status"] = "Bezig met Gmail-check"
        stats["last_run_mode"] = mode
        stats["is_running"] = True
        stats["progress_current"] = 0
        stats["progress_total"] = 0
        save_stats(stats)

        processed_messages = set(load_json(PROCESSED_MESSAGES_FILE, []))
        processed_downloads = set(load_json(PROCESSED_DOWNLOADS_FILE, []))

        all_messages = get_all_messages(service, query="in:inbox -in:trash -in:spam")
        todo = [m for m in all_messages if m["id"] not in processed_messages]

        stats["emails_scanned"] += len(todo)
        stats["run_scanned_delta"] = len(todo)
        stats["progress_total"] = len(todo)
        add_log(stats, f"{len(todo)} nieuwe mails gescand ({mode})")
        save_stats(stats)

        to_trash = []

        for idx, m in enumerate(todo, start=1):
            msg_id = m["id"]
            stats["progress_current"] = idx
            save_stats(stats)

            msg = get_message(service, msg_id)
            if not msg:
                processed_messages.add(msg_id)
                continue

            subject = get_header(msg, "subject")
            sender = get_header(msg, "from")
            text = f"{subject} {sender}".lower()

            if is_match(text, NOOIT_VERWIJDEREN):
                stats["protected_kept"] += 1
                stats["run_protected_delta"] += 1
                add_log(stats, f"Beschermd bewaard: {subject}")
                append_history(KEPT_HISTORY_FILE, {
                    "time": now_str(),
                    "type": "beschermd",
                    "subject": subject,
                    "sender": sender,
                    "message_id": msg_id
                })

                if mode in ("full", "pdfs") and has_pdf(msg):
                    save_pdf_attachment(service, msg, msg_id, processed_downloads, stats)

                processed_messages.add(msg_id)
                continue

            if is_match(text, BELANGRIJK):
                stats["important_kept"] += 1
                stats["run_important_delta"] += 1
                add_log(stats, f"Belangrijk bewaard: {subject}")
                append_history(KEPT_HISTORY_FILE, {
                    "time": now_str(),
                    "type": "belangrijk",
                    "subject": subject,
                    "sender": sender,
                    "message_id": msg_id
                })

                if mode in ("full", "pdfs") and has_pdf(msg):
                    save_pdf_attachment(service, msg, msg_id, processed_downloads, stats)

                processed_messages.add(msg_id)
                continue

            if mode == "pdfs":
                if has_pdf(msg):
                    save_pdf_attachment(service, msg, msg_id, processed_downloads, stats)

                processed_messages.add(msg_id)
                continue

            if is_match(text, ONGEWENST) or not has_pdf(msg):
                to_trash.append({
                    "message_id": msg_id,
                    "subject": subject,
                    "sender": sender,
                    "time": now_str()
                })

            processed_messages.add(msg_id)

        save_json(PROCESSED_MESSAGES_FILE, sorted(list(processed_messages)))
        save_json(PROCESSED_DOWNLOADS_FILE, sorted(list(processed_downloads)))

        if mode == "pdfs":
            stats["is_running"] = False
            stats["last_status"] = "PDF-check voltooid"
            save_stats(stats)
            return

        if not to_trash:
            stats["is_running"] = False
            stats["last_status"] = "Geen mails om te verplaatsen"
            add_log(stats, "Geen mails om naar prullenbak te verplaatsen")
            save_json(PENDING_TRASH_FILE, [])
            save_stats(stats)
            return

        save_json(PENDING_TRASH_FILE, to_trash)
        stats["is_running"] = False
        stats["last_status"] = f"Wacht op goedkeuring voor {len(to_trash)} mail(s)"
        add_log(stats, f"{len(to_trash)} mail(s) wachten op dashboard-goedkeuring")
        save_stats(stats)

    except Exception as e:
        stats = load_stats()
        stats["is_running"] = False
        stats["last_status"] = f"Fout tijdens Gmail-check: {e}"
        add_log(stats, f"Onverwachte fout tijdens cleanup: {e}")
        save_stats(stats)
        raise

    finally:
        remove_lock()


if __name__ == "__main__":
    mode = parse_mode()

    if mode == "approve":
        approve_pending_trash()
    elif mode == "reject":
        reject_pending_trash()
    else:
        cleanup(mode=mode)
