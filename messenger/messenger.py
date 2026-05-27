"""
Служебный мессенджер infostart-agent <-> infolimp.ru

Транспорт: приватный GitHub-репозиторий darachubarova/infolimp-comms
Безопасность: HMAC-SHA256 подпись каждого сообщения

Использование:
  python messenger.py send "Текст сообщения" --channel general --type info
  python messenger.py read
  python messenger.py read --unread
"""
import os, sys, json, hmac, hashlib, uuid, subprocess
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from datetime import datetime, timezone
from pathlib import Path

REPO_URL      = "https://github.com/darachubarova/infolimp-comms.git"
LOCAL_REPO    = Path("C:/Users/vitae/messenger-repo")
SECRET_KEY    = os.environ.get("MESSENGER_HMAC_KEY", "").encode()
FROM_ID       = "infostart-agent"
TO_ID         = "infolimp"
INFOLIMP_API  = os.environ.get("INFOLIMP_API_URL", "https://infolimp.ru/api/articles")
INFOLIMP_KEY  = os.environ.get("INFOLIMP_API_KEY", "")
MESSENGER_API  = "https://infolimp.ru/api/messenger"
INBOX_API      = f"{MESSENGER_API}/inbox"
SEND_API       = f"{MESSENGER_API}/send"
ARTICLES_API   = os.environ.get("INFOLIMP_API_URL", "https://infolimp.ru/api/articles")
ARTICLES_PAGE  = "https://infolimp.ru/articles/"
REPLY_PREFIX   = "reply-infostart-"  # slug prefix for infolimp.ru -> us replies


def _canon(payload: dict) -> str:
    """Канонічна строка — стійка до JSON-переформатування."""
    return "|".join([
        payload.get("from",""), payload.get("to",""),
        payload.get("channel",""), payload.get("type",""),
        payload.get("text",""), payload.get("created_at",""),
    ])

def sign(payload: dict) -> str:
    canon = _canon(payload)
    return hmac.new(SECRET_KEY, canon.encode("utf-8"), hashlib.sha256).hexdigest()

def verify(payload: dict, signature: str) -> bool:
    return hmac.compare_digest(sign(payload), signature)


def git(*args, cwd=LOCAL_REPO):
    result = subprocess.run(["git"] + list(args), cwd=str(cwd),
                            capture_output=True, text=True)
    if result.returncode != 0 and "nothing to commit" not in result.stdout:
        pass
    return result.stdout.strip()


def sync_repo():
    """Клонировать или подтянуть последние изменения."""
    if not LOCAL_REPO.exists():
        subprocess.run(["git", "clone", REPO_URL, str(LOCAL_REPO)],
                       capture_output=True)
        git("config", "user.email", "agent@infostart-agent.bot")
        git("config", "user.name",  "Infostart Agent")
    else:
        git("pull", "--rebase", "--autostash")


def push_repo():
    git("push")


def send_message(text: str, channel: str = "general", msg_type: str = "info",
                 payload: dict = None):
    if not SECRET_KEY:
        print("MESSENGER_HMAC_KEY не задан")
        sys.exit(1)

    sync_repo()

    msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    ts     = datetime.now(timezone.utc).isoformat()

    body = {
        "id":         msg_id,
        "from":       FROM_ID,
        "to":         TO_ID,
        "channel":    channel,
        "type":       msg_type,
        "text":       text,
        "payload":    payload or {},
        "created_at": ts,
    }
    sig = sign(body)

    envelope = {**body, "signature": sig}

    out_dir = LOCAL_REPO / "outbox" / FROM_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    msg_file = out_dir / f"{msg_id}.json"
    msg_file.write_text(json.dumps(envelope, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    git("add", ".")
    git("commit", "-m", f"msg: {FROM_ID} -> {TO_ID} [{channel}] {msg_id}")
    push_repo()

    print(f"Отправлено: {msg_id}")
    print(f"  Подпись:  {sig[:16]}...")
    return msg_id


def read_messages(unread_only: bool = False, channel: str = None):
    if not SECRET_KEY:
        print("MESSENGER_HMAC_KEY не задан")
        sys.exit(1)

    sync_repo()

    inbox_dir = LOCAL_REPO / "outbox" / TO_ID
    if not inbox_dir.exists():
        print("Нет входящих сообщений.")
        return []

    read_log = LOCAL_REPO / f".read_{FROM_ID}"
    read_ids  = set(read_log.read_text(encoding="utf-8").splitlines()) \
                if read_log.exists() else set()

    messages = []
    for f in sorted(inbox_dir.glob("*.json")):
        env = json.loads(f.read_text(encoding="utf-8"))
        if "id" not in env:
            env["id"] = f.stem
        if unread_only and env["id"] in read_ids:
            continue
        if channel and env.get("channel") != channel:
            continue

        sig = env.pop("signature", "")
        valid = verify(env, sig)
        env["signature"] = sig

        status = "[OK]" if valid else "[!] ПОДПИСЬ НЕ СОВПАДАЕТ"
        print(f"\n[{env['created_at'][:16]}] {env['from']} -> {env['to']} "
              f"[{env['channel']}] {status}")
        print(f"  {env['text']}")
        if env.get("payload"):
            print(f"  payload: {env['payload']}")

        messages.append(env)
        read_ids.add(env["id"])

    read_log.write_text("\n".join(read_ids), encoding="utf-8")
    git("add", ".")
    git("commit", "-m", f"read: {FROM_ID} отметил прочитанными")
    push_repo()

    if not messages:
        print("Нет новых сообщений.")
    return messages


def send_via_rest(text: str, channel: str = "general", msg_type: str = "info",
                  payload: dict = None):
    """Отправить сообщение через REST API infolimp.ru (не требует GitHub-токена)."""
    import urllib.request, urllib.error
    if not INFOLIMP_KEY:
        print("INFOLIMP_API_KEY не задан")
        return None

    ts   = datetime.now(timezone.utc).isoformat()
    body = {
        "from":       FROM_ID,
        "to":         TO_ID,
        "channel":    channel,
        "type":       msg_type,
        "text":       text,
        "payload":    payload or {},
        "created_at": ts,
    }
    body["signature"] = sign(body)

    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req  = urllib.request.Request(
        SEND_API,
        data=data,
        headers={
            "Authorization": f"Bearer {INFOLIMP_KEY}",
            "Content-Type":  "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            msg_id = result.get("id", "?")
            print(f"Отправлено (REST): {msg_id}")
            print(f"  Подпись: {body['signature'][:16]}...")
            return msg_id
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        print(f"Ошибка REST send: HTTP {e.code} — {body_text[:200]}")
        return None
    except Exception as e:
        print(f"REST send недоступен: {e}")
        return None


def send_via_articles(text: str, channel: str = "general", msg_type: str = "info",
                      payload: dict = None):
    """Отправить сообщение через articles API (всегда работает, не требует нового эндпоинта)."""
    import urllib.request, urllib.error
    from datetime import date
    if not INFOLIMP_KEY:
        print("INFOLIMP_API_KEY не задан")
        return None

    ts   = datetime.now(timezone.utc).isoformat()
    body = {
        "from": FROM_ID, "to": TO_ID, "channel": channel,
        "type": msg_type, "text": text,
        "payload": payload or {}, "created_at": ts,
    }
    sig = sign(body)

    msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    slug   = f"msg-from-infostart-{msg_id}"

    content = (
        f"channel:{channel} type:{msg_type}\n\n"
        f"{text}\n\n"
        f"HMAC:{sig}\ncreated_at:{ts}"
    )
    article = {
        "title":         f"[MSG] {text[:60]}",
        "slug":          slug,
        "content":       content,
        "date":          str(date.today()),
        "tags":          ["messenger", channel],
        "category":      "messenger",
        "canonical_url": "https://darachubarova.github.io/infostart-agent/",
        "author":        FROM_ID,
    }
    data = json.dumps(article, ensure_ascii=False).encode("utf-8")
    req  = urllib.request.Request(
        ARTICLES_API, data=data,
        headers={"Authorization": f"Bearer {INFOLIMP_KEY}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            print(f"Отправлено (articles): {msg_id}")
            print(f"  URL: {result.get('url', '?')}")
            return msg_id
    except urllib.error.HTTPError as e:
        print(f"Ошибка articles send: HTTP {e.code} — {e.read().decode()[:200]}")
        return None
    except Exception as e:
        print(f"Articles send ошибка: {e}")
        return None


def read_from_articles_scrape(unread_only: bool = False):
    """Читаем ответы infolimp.ru — статьи с slug 'reply-infostart-*' на их сайте."""
    import urllib.request, urllib.error, re
    read_log  = Path("messenger_read_articles.json")
    read_ids  = set(json.loads(read_log.read_text(encoding="utf-8"))) \
                if read_log.exists() else set()

    try:
        req = urllib.request.Request(ARTICLES_PAGE,
                                     headers={"User-Agent": "infostart-agent/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"Scrape ошибка: {e}")
        return None  # None = ошибка

    slugs = re.findall(r"/articles/(" + re.escape(REPLY_PREFIX) + r"[a-z0-9_-]+)\.html", html)
    if not slugs:
        print("Нет ответов от infolimp.ru.")
        return []

    messages = []
    for slug in slugs:
        if unread_only and slug in read_ids:
            continue
        try:
            req2 = urllib.request.Request(
                f"{ARTICLES_PAGE}{slug}.html",
                headers={"User-Agent": "infostart-agent/1.0"}
            )
            with urllib.request.urlopen(req2, timeout=10) as resp2:
                page = resp2.read().decode("utf-8", errors="replace")
            text_match = re.search(r"<article[^>]*>(.*?)</article>", page, re.DOTALL)
            raw  = re.sub("<[^>]+>", " ", text_match.group(1)) if text_match else page
            text = re.sub(r"\s+", " ", raw).strip()

            # Extract HMAC and verify
            sig_match = re.search(r"HMAC:([a-f0-9]{64})", text)
            ts_match  = re.search(r"created_at:([\d\-T:.+Z]+)", text)
            sig = sig_match.group(1) if sig_match else ""
            ts  = ts_match.group(1)  if ts_match  else ""

            env = {"from": TO_ID, "to": FROM_ID, "channel": "general",
                   "type": "reply", "text": text[:300],
                   "payload": {}, "created_at": ts}
            valid  = verify(env, sig) if sig else False
            status = "[OK]" if valid else "[подпись не проверена]"

            print(f"\n[{ts[:16]}] infolimp -> infostart-agent [scrape] {status}")
            print(f"  {text[:200]}")

            messages.append({"id": slug, "from": TO_ID, "text": text,
                             "created_at": ts, "signature": sig})
            read_ids.add(slug)
        except Exception as e:
            print(f"  Ошибка чтения {slug}: {e}")

    read_log.write_text(json.dumps(sorted(read_ids)), encoding="utf-8")
    if not messages:
        print("Нет новых ответов.")
    return messages


def read_from_rest_api(unread_only: bool = False, channel: str = None):
    """Читаем сообщения от infolimp.ru через их REST API (не требует GitHub-токена)."""
    import urllib.request, urllib.error
    params = f"?to={FROM_ID}&unread={'true' if unread_only else 'false'}"
    if channel:
        params += f"&channel={channel}"
    req = urllib.request.Request(
        INBOX_API + params,
        headers={"Authorization": f"Bearer {INFOLIMP_KEY}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            messages = json.loads(resp.read())
            if not messages:
                print("Нет новых сообщений от infolimp.ru.")
                return []
            for msg in messages:
                sig = msg.pop("signature", "")
                valid = verify(msg, sig) if sig else False
                msg["signature"] = sig
                status = "[OK]" if valid else "[!] ПОДПИСЬ НЕ СОВПАДАЕТ"
                print(f"\n[{msg.get('created_at','?')[:16]}] {msg.get('from')} -> {msg.get('to')} [{msg.get('channel')}] {status}")
                print(f"  {msg.get('text','')}")
            return messages
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("REST inbox ещё не готов на infolimp.ru — используем Git-канал.")
        else:
            print(f"Ошибка REST API: HTTP {e.code}")
        return None  # None = ошибка, [] = успешно пусто
    except Exception as e:
        print(f"REST API недоступен: {e}")
        return None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")

    s = sub.add_parser("send")
    s.add_argument("text")
    s.add_argument("--channel", default="general")
    s.add_argument("--type",    default="info")
    s.add_argument("--git",     action="store_true",
                   help="Отправить через Git-канал (резервный)")

    r = sub.add_parser("read")
    r.add_argument("--unread",  action="store_true")
    r.add_argument("--channel", default=None)
    r.add_argument("--git",     action="store_true",
                   help="Читать через Git-канал (резервный)")

    args = parser.parse_args()

    if args.cmd == "send":
        if args.git or not INFOLIMP_KEY:
            send_message(args.text, args.channel, args.type)
        else:
            # Цепочка: REST messenger -> articles API -> git
            result = send_via_rest(args.text, args.channel, args.type)
            if result is None:
                result = send_via_articles(args.text, args.channel, args.type)
            if result is None:
                print("Articles API недоступен, пробуем Git-канал...")
                send_message(args.text, args.channel, args.type)
    elif args.cmd == "read":
        if args.git or not INFOLIMP_KEY:
            read_messages(args.unread, args.channel)
        else:
            # Цепочка: REST messenger -> scrape articles -> git
            msgs = read_from_rest_api(args.unread, args.channel)
            if msgs is None:
                msgs = read_from_articles_scrape(args.unread)
            if msgs is None:  # ошибка articles — fallback на Git
                read_messages(args.unread, args.channel)
    else:
        parser.print_help()
