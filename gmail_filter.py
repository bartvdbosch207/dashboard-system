import os
import sys
import json
import base64
import pickle
import subprocess
from pathlib import Path
from datetime import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels',
]

IS_RENDER = bool(os.environ.get('RENDER')) or bool(os.environ.get('PORT'))
BASE_DIR = Path(__file__).resolve().parent if IS_RENDER else Path('/Users/bartvandenbosch/Desktop/Dropbox')
DATA_ROOT = Path(os.environ.get('INBOX_PILOT_DATA_DIR', str(BASE_DIR / 'data' / 'gmail_runtime'))) if IS_RENDER else BASE_DIR
SYSTEM_DIR = Path(os.environ.get('INBOX_PILOT_SYSTEM_DIR', str(BASE_DIR / 'System'))) if not IS_RENDER else BASE_DIR
DOWNLOAD_MAP = Path(os.environ.get('INBOX_PILOT_DOWNLOAD_DIR', str(BASE_DIR if not IS_RENDER else (DATA_ROOT / 'downloads'))))
SORTEER_SCRIPT = Path(os.environ.get('INBOX_PILOT_SORT_SCRIPT', str(SYSTEM_DIR / 'sorteer.py')))
CREDENTIALS_FILE = Path(os.environ.get('GMAIL_CREDENTIALS_FILE', str(SYSTEM_DIR / 'credentials.json')))
TOKEN_FILE = Path(os.environ.get('GMAIL_TOKEN_FILE', str(DATA_ROOT / 'token_gmail.json')))
LEGACY_TOKEN_FILE = Path(os.environ.get('GMAIL_LEGACY_TOKEN_FILE', str(SYSTEM_DIR / 'token_gmail.pkl')))
PROCESSED_DOWNLOADS_FILE = DATA_ROOT / 'processed_downloads.json'
PROCESSED_MESSAGES_FILE = DATA_ROOT / 'processed_messages.json'
STATS_FILE = DATA_ROOT / 'dashboard_stats.json'
TRASH_HISTORY_FILE = DATA_ROOT / 'trash_history.json'
DOWNLOAD_HISTORY_FILE = DATA_ROOT / 'downloads_history.json'
KEPT_HISTORY_FILE = DATA_ROOT / 'kept_history.json'
ACTIVITY_HISTORY_FILE = DATA_ROOT / 'activity_history.json'
PENDING_TRASH_FILE = DATA_ROOT / 'pending_trash.json'
LOCK_FILE = DATA_ROOT / 'run.lock'

LABELS = {
    'protected': 'Inbox Pilot/Protected',
    'important': 'Inbox Pilot/Important',
    'pdf': 'Inbox Pilot/PDF',
    'review': 'Inbox Pilot/Review',
    'kept': 'Inbox Pilot/Kept',
}

NOOIT_VERWIJDEREN = [
    'veiligheid@mborijnland.nl', 'no-reply@mborijnland.nl', 'loonstrook', 'factuur',
    'noreply@mijn.overheid.nl', 'studentzaken@mborijnland.nl', 'noreply@zorgenzekerheid.nl',
    '_noreply@odido.nl', 'jeugdvoorzitter@rijnsburgseboys.nl', 'loondesk@vanwezelacc.nl',
    'mlander@mborijnland.nl', 'info@mborijnland.nl', 'no-reply@cbr.nl',
    'reply@email.duo.nl', 'noreply@studielink.nl',
]

BELANGRIJK = [
    'factuur', 'invoice', 'belasting', 'tax', 'overheid', 'bank', 'rekening', 'rabobank',
    'verzekering', 'zorg en zekerheid', 'rijnsburgse boys', 'loon', 'salary', 'payslip',
    'mborijnland', 'htv', 'school'
]

ONGEWENST = [
    'nieuwsbrief', 'unsubscribe', 'afmelden', 'sale', 'korting', 'actie', 'deal',
    'promo', 'advertentie', 'aanbieding', 'social', 'notification', 'update',
    'black friday', 'cyber monday', 'marketing', 'campaign', 'campagne'
]

MAX_RESULTS_PER_PAGE = 200
MAX_HISTORY = 500

DEFAULT_STATS = {
    'last_run': None,
    'last_status': 'Nog niet uitgevoerd',
    'emails_scanned': 0,
    'pdfs_downloaded': 0,
    'emails_trashed': 0,
    'protected_kept': 0,
    'important_kept': 0,
    'duplicate_skipped': 0,
    'last_run_mode': 'volledig',
    'is_running': False,
    'progress_current': 0,
    'progress_total': 0,
    'run_scanned_delta': 0,
    'run_pdfs_delta': 0,
    'run_trashed_delta': 0,
    'run_protected_delta': 0,
    'run_important_delta': 0,
    'run_duplicate_delta': 0,
    'logs': []
}


def ensure_runtime_paths():
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_MAP.mkdir(parents=True, exist_ok=True)
    for path, default in [
        (PROCESSED_DOWNLOADS_FILE, []),
        (PROCESSED_MESSAGES_FILE, []),
        (TRASH_HISTORY_FILE, []),
        (DOWNLOAD_HISTORY_FILE, []),
        (KEPT_HISTORY_FILE, []),
        (ACTIVITY_HISTORY_FILE, []),
        (PENDING_TRASH_FILE, []),
        (STATS_FILE, DEFAULT_STATS),
    ]:
        if not path.exists():
            save_json(path, default)


def now_str():
    return datetime.now().strftime('%d-%m-%Y %H:%M:%S')


def load_json(path, default):
    path = Path(path)
    if not path.exists():
        return default
    try:
        with path.open('r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + '.tmp')
    with temp_path.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(temp_path, path)


def append_history(path, item):
    items = load_json(path, [])
    items.append(item)
    save_json(path, items[-MAX_HISTORY:])


def load_stats():
    ensure_runtime_paths()
    stats = DEFAULT_STATS.copy()
    stats.update(load_json(STATS_FILE, {}))
    return stats


def save_stats(stats):
    save_json(STATS_FILE, stats)


def add_log(stats, message):
    entry = {'time': now_str(), 'message': message}
    stats.setdefault('logs', [])
    stats['logs'].append(entry)
    stats['logs'] = stats['logs'][-50:]
    append_history(ACTIVITY_HISTORY_FILE, entry)


def reset_run_deltas(stats):
    for key in [
        'run_scanned_delta',
        'run_pdfs_delta',
        'run_trashed_delta',
        'run_protected_delta',
        'run_important_delta',
        'run_duplicate_delta',
    ]:
        stats[key] = 0


def is_locked():
    return LOCK_FILE.exists()


def create_lock():
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(now_str(), encoding='utf-8')


def remove_lock():
    if LOCK_FILE.exists():
        try:
            LOCK_FILE.unlink()
        except Exception:
            pass


def load_client_config():
    raw = os.environ.get('GMAIL_CREDENTIALS_JSON', '').strip()
    if raw:
        return json.loads(raw)
    if CREDENTIALS_FILE.exists():
        return json.loads(CREDENTIALS_FILE.read_text(encoding='utf-8'))
    return None


def load_saved_credentials():
    raw = os.environ.get('GMAIL_TOKEN_JSON', '').strip()
    if raw:
        return Credentials.from_authorized_user_info(json.loads(raw), SCOPES)

    if TOKEN_FILE.exists():
        try:
            return Credentials.from_authorized_user_info(json.loads(TOKEN_FILE.read_text(encoding='utf-8')), SCOPES)
        except Exception:
            pass

    if LEGACY_TOKEN_FILE.exists():
        try:
            with LEGACY_TOKEN_FILE.open('rb') as f:
                return pickle.load(f)
        except Exception:
            pass

    return None


def persist_credentials(creds):
    ensure_runtime_paths()
    try:
        TOKEN_FILE.write_text(creds.to_json(), encoding='utf-8')
    except Exception:
        pass


def get_service():
    ensure_runtime_paths()
    creds = load_saved_credentials()

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        persist_credentials(creds)

    if not creds or not creds.valid:
        if IS_RENDER:
            raise RuntimeError(
                'Geen geldige Gmail-token op de server. Zet GMAIL_TOKEN_JSON als secret of mount een persistent disk met token_gmail.json.'
            )

        client_config = load_client_config()
        if not client_config:
            raise RuntimeError('Geen Gmail credentials gevonden. Voeg credentials.json toe of zet GMAIL_CREDENTIALS_JSON.')
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        creds = flow.run_local_server(port=0)
        persist_credentials(creds)

    return build('gmail', 'v1', credentials=creds)


def get_label_map(service):
    response = service.users().labels().list(userId='me').execute()
    return {item['name']: item['id'] for item in response.get('labels', [])}


def ensure_user_label(service, name):
    label_map = get_label_map(service)
    if name in label_map:
        return label_map[name]
    created = service.users().labels().create(
        userId='me',
        body={
            'name': name,
            'labelListVisibility': 'labelShow',
            'messageListVisibility': 'show',
        },
    ).execute()
    return created['id']


def apply_labels(service, msg_id, add_names=None, remove_ids=None):
    add_ids = []
    for name in add_names or []:
        add_ids.append(ensure_user_label(service, name))
    body = {
        'addLabelIds': list(dict.fromkeys(add_ids)),
        'removeLabelIds': list(dict.fromkeys(remove_ids or [])),
    }
    service.users().messages().modify(userId='me', id=msg_id, body=body).execute()


def archive_with_labels(service, msg_id, labels):
    apply_labels(service, msg_id, add_names=labels, remove_ids=['INBOX', 'UNREAD'])


def get_all_messages(service, query):
    messages = []
    page_token = None
    while True:
        response = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=MAX_RESULTS_PER_PAGE,
            pageToken=page_token,
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
    return ''


def extract_parts(payload):
    parts = []
    if 'parts' in payload:
        for part in payload['parts']:
            parts.extend(extract_parts(part))
    else:
        parts.append(payload)
    return parts


def has_pdf(msg):
    return any(part.get('filename', '').lower().endswith('.pdf') for part in extract_parts(msg.get('payload', {})))


def is_match(text, keywords):
    text = text.lower()
    return any(k.lower() in text for k in keywords)


def classify_message(msg):
    subject = get_header(msg, 'subject')
    sender = get_header(msg, 'from')
    text = f'{subject} {sender}'.lower()
    reasons = []
    if is_match(text, NOOIT_VERWIJDEREN):
        for keyword in NOOIT_VERWIJDEREN:
            if keyword.lower() in text:
                reasons.append(f'beschermd keyword: {keyword}')
                break
        return 'protected', reasons, text
    if is_match(text, BELANGRIJK):
        for keyword in BELANGRIJK:
            if keyword.lower() in text:
                reasons.append(f'belangrijk keyword: {keyword}')
                break
        return 'important', reasons, text
    if has_pdf(msg):
        reasons.append('bevat pdf-bijlage')
        return 'pdf', reasons, text
    if is_match(text, ONGEWENST):
        for keyword in ONGEWENST:
            if keyword.lower() in text:
                reasons.append(f'ongewenst keyword: {keyword}')
                break
    else:
        reasons.append('geen pdf en niet gemarkeerd als belangrijk')
    return 'review', reasons, text


def maybe_sort_download(filepath):
    if SORTEER_SCRIPT.exists():
        python_bin = os.environ.get('PYTHON_BIN') or sys.executable
        subprocess.run([python_bin, str(SORTEER_SCRIPT), str(filepath)], check=False)


def save_pdf_attachment(service, msg, msg_id, processed_downloads, stats):
    subject = get_header(msg, 'subject')
    sender = get_header(msg, 'from')

    for part in extract_parts(msg.get('payload', {})):
        filename = part.get('filename', '')
        body = part.get('body', {})
        if filename.lower().endswith('.pdf') and body.get('attachmentId'):
            unique_key = f'{msg_id}:{filename}'
            if unique_key in processed_downloads:
                stats['duplicate_skipped'] += 1
                stats['run_duplicate_delta'] += 1
                add_log(stats, f'Dubbele download overgeslagen: {filename}')
                continue
            try:
                attachment = service.users().messages().attachments().get(
                    userId='me', messageId=msg_id, id=body['attachmentId']
                ).execute()
                data = base64.urlsafe_b64decode(attachment['data'].encode('UTF-8'))
                filepath = DOWNLOAD_MAP / filename
                if filepath.exists():
                    stats['duplicate_skipped'] += 1
                    stats['run_duplicate_delta'] += 1
                    add_log(stats, f'Bestand bestond al, skip: {filename}')
                    processed_downloads.add(unique_key)
                    continue
                filepath.write_bytes(data)
                maybe_sort_download(filepath)
                processed_downloads.add(unique_key)
                stats['pdfs_downloaded'] += 1
                stats['run_pdfs_delta'] += 1
                add_log(stats, f'PDF gedownload en verwerkt: {filename}')
                append_history(DOWNLOAD_HISTORY_FILE, {
                    'time': now_str(),
                    'filename': filename,
                    'subject': subject,
                    'sender': sender,
                    'message_id': msg_id,
                })
            except Exception as e:
                add_log(stats, f'Fout bij PDF {filename}: {e}')


def parse_mode():
    if '--approve-trash' in sys.argv[1:]:
        return 'approve'
    if '--reject-trash' in sys.argv[1:]:
        return 'reject'
    for arg in sys.argv[1:]:
        if arg.startswith('--mode='):
            mode = arg.split('=', 1)[1].strip().lower()
            if mode in {'full', 'cleanup', 'pdfs'}:
                return mode
    return 'full'


def approve_pending_trash():
    ensure_runtime_paths()
    if is_locked():
        stats = load_stats()
        stats['last_status'] = 'Er draait al een Gmail-check'
        add_log(stats, 'Goedkeuren geblokkeerd: er draait al een proces')
        save_stats(stats)
        return

    create_lock()
    try:
        stats = load_stats()
        reset_run_deltas(stats)
        stats['is_running'] = True
        stats['last_status'] = 'Goedgekeurde mails worden verplaatst'
        save_stats(stats)

        items = load_json(PENDING_TRASH_FILE, [])
        if not items:
            stats['is_running'] = False
            stats['progress_current'] = 0
            stats['progress_total'] = 0
            stats['last_status'] = 'Geen wachtende mails gevonden'
            save_stats(stats)
            return

        service = get_service()
        stats['progress_total'] = len(items)
        stats['progress_current'] = 0
        save_stats(stats)

        for idx, item in enumerate(items, start=1):
            stats['progress_current'] = idx
            save_stats(stats)
            try:
                service.users().messages().trash(userId='me', id=item['message_id']).execute()
                stats['emails_trashed'] += 1
                stats['run_trashed_delta'] += 1
                add_log(stats, f"Naar prullenbak: {item.get('subject', '')}")
                append_history(TRASH_HISTORY_FILE, {
                    'time': now_str(),
                    'subject': item.get('subject', ''),
                    'sender': item.get('sender', ''),
                    'message_id': item.get('message_id', ''),
                })
            except Exception as e:
                add_log(stats, f'Fout bij prullenbak: {e}')

        save_json(PENDING_TRASH_FILE, [])
        stats['is_running'] = False
        stats['progress_current'] = stats['progress_total']
        stats['last_status'] = 'Goedgekeurde mails zijn naar prullenbak verplaatst'
        save_stats(stats)
    finally:
        remove_lock()


def reject_pending_trash():
    ensure_runtime_paths()
    if is_locked():
        stats = load_stats()
        stats['last_status'] = 'Er draait al een Gmail-check'
        add_log(stats, 'Afwijzen geblokkeerd: er draait al een proces')
        save_stats(stats)
        return

    create_lock()
    try:
        stats = load_stats()
        items = load_json(PENDING_TRASH_FILE, [])
        if items:
            service = get_service()
            for item in items:
                try:
                    archive_with_labels(service, item['message_id'], [LABELS['kept']])
                except Exception as e:
                    add_log(stats, f"Kon review-mail niet als bewaard labelen: {e}")
        save_json(PENDING_TRASH_FILE, [])
        stats['progress_current'] = 0
        stats['progress_total'] = 0
        stats['last_status'] = 'Prullenbak-goedkeuring geannuleerd; mails zijn als bewaard gearchiveerd'
        add_log(stats, 'Wachtende prullenbak-lijst geannuleerd vanuit dashboard')
        save_stats(stats)
    finally:
        remove_lock()


def cleanup(mode='full'):
    ensure_runtime_paths()
    if is_locked():
        stats = load_stats()
        stats['last_status'] = 'Er draait al een Gmail-check'
        add_log(stats, 'Nieuwe run geblokkeerd: er draait al een proces')
        save_stats(stats)
        return

    create_lock()
    try:
        service = get_service()

        stats = load_stats()
        reset_run_deltas(stats)
        stats['last_run'] = now_str()
        stats['last_status'] = 'Bezig met Gmail-check'
        stats['last_run_mode'] = mode
        stats['is_running'] = True
        stats['progress_current'] = 0
        stats['progress_total'] = 0
        save_stats(stats)

        processed_messages = set(load_json(PROCESSED_MESSAGES_FILE, []))
        processed_downloads = set(load_json(PROCESSED_DOWNLOADS_FILE, []))

        all_messages = get_all_messages(service, query='in:inbox -in:trash -in:spam')
        todo = [m for m in all_messages if m['id'] not in processed_messages]

        stats['emails_scanned'] += len(todo)
        stats['run_scanned_delta'] = len(todo)
        stats['progress_total'] = len(todo)
        add_log(stats, f'{len(todo)} nieuwe mails gescand ({mode})')
        save_stats(stats)

        to_review = []

        for idx, m in enumerate(todo, start=1):
            msg_id = m['id']
            stats['progress_current'] = idx
            save_stats(stats)

            msg = get_message(service, msg_id)
            if not msg:
                processed_messages.add(msg_id)
                continue

            subject = get_header(msg, 'subject')
            sender = get_header(msg, 'from')
            category, reasons, text = classify_message(msg)

            if category == 'protected':
                stats['protected_kept'] += 1
                stats['run_protected_delta'] += 1
                add_log(stats, f'Beschermd bewaard en gearchiveerd: {subject}')
                archive_with_labels(service, msg_id, [LABELS['protected']])
                append_history(KEPT_HISTORY_FILE, {
                    'time': now_str(),
                    'type': 'beschermd',
                    'subject': subject,
                    'sender': sender,
                    'message_id': msg_id,
                    'reason': '; '.join(reasons),
                })
                if mode in ('full', 'pdfs') and has_pdf(msg):
                    save_pdf_attachment(service, msg, msg_id, processed_downloads, stats)
                processed_messages.add(msg_id)
                continue

            if category == 'important':
                stats['important_kept'] += 1
                stats['run_important_delta'] += 1
                add_log(stats, f'Belangrijk bewaard en gearchiveerd: {subject}')
                archive_with_labels(service, msg_id, [LABELS['important']])
                append_history(KEPT_HISTORY_FILE, {
                    'time': now_str(),
                    'type': 'belangrijk',
                    'subject': subject,
                    'sender': sender,
                    'message_id': msg_id,
                    'reason': '; '.join(reasons),
                })
                if mode in ('full', 'pdfs') and has_pdf(msg):
                    save_pdf_attachment(service, msg, msg_id, processed_downloads, stats)
                processed_messages.add(msg_id)
                continue

            if category == 'pdf':
                archive_with_labels(service, msg_id, [LABELS['pdf']])
                if mode in ('full', 'pdfs'):
                    save_pdf_attachment(service, msg, msg_id, processed_downloads, stats)
                add_log(stats, f'PDF-mail gearchiveerd: {subject}')
                append_history(KEPT_HISTORY_FILE, {
                    'time': now_str(),
                    'type': 'pdf',
                    'subject': subject,
                    'sender': sender,
                    'message_id': msg_id,
                    'reason': '; '.join(reasons),
                })
                processed_messages.add(msg_id)
                continue

            archive_with_labels(service, msg_id, [LABELS['review']])
            to_review.append({
                'message_id': msg_id,
                'subject': subject,
                'sender': sender,
                'time': now_str(),
                'reasons': reasons,
                'bucket': 'review',
            })
            processed_messages.add(msg_id)

        save_json(PROCESSED_MESSAGES_FILE, sorted(list(processed_messages)))
        save_json(PROCESSED_DOWNLOADS_FILE, sorted(list(processed_downloads)))

        if mode == 'pdfs':
            stats['is_running'] = False
            stats['last_status'] = 'PDF-check voltooid'
            save_stats(stats)
            return

        if not to_review:
            stats['is_running'] = False
            stats['last_status'] = 'Inbox verwerkt en gearchiveerd; geen review nodig'
            add_log(stats, 'Geen mails meer in review nodig')
            save_json(PENDING_TRASH_FILE, [])
            save_stats(stats)
            return

        save_json(PENDING_TRASH_FILE, to_review)
        stats['is_running'] = False
        stats['last_status'] = f'Inbox leeg; {len(to_review)} mail(s) staan in review'
        add_log(stats, f'{len(to_review)} mail(s) wachten op dashboard-review')
        save_stats(stats)
    except Exception as e:
        stats = load_stats()
        stats['is_running'] = False
        stats['last_status'] = f'Fout tijdens Gmail-check: {e}'
        add_log(stats, f'Onverwachte fout tijdens cleanup: {e}')
        save_stats(stats)
        raise
    finally:
        remove_lock()


if __name__ == '__main__':
    mode = parse_mode()
    if mode == 'approve':
        approve_pending_trash()
    elif mode == 'reject':
        reject_pending_trash()
    else:
        cleanup(mode=mode)
