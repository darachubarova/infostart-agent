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
from datetime import datetime, timezone
from pathlib import Path

REPO_URL    = "https://github.com/darachubarova/infolimp-comms.git"
LOCAL_REPO  = Path("C:/Users/vitae/messenger-repo")
SECRET_KEY  = os.environ.get("MESSENGER_HMAC_KEY", "").encode()
FROM_ID     = "infostart-agent"
TO_ID       = "infolimp"


def sign(payload: dict) -> str:
    """HMAC-SHA256 подпись тела сообщения."""
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hmac.new(SECRET_KEY, body.encode("utf-8"), hashlib.sha256).hexdigest()


def verify(payload: dict, signature: str) -> bool:
    expected = sign(payload)
    return hmac.compare_digest(expected, signature)


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
        if unread_only and env["id"] in read_ids:
            continue
        if channel and env.get("channel") != channel:
            continue

        sig = env.pop("signature", "")
        valid = verify(env, sig)
        env["signature"] = sig

        status = "✓" if valid else "✗ ПОДПИСЬ НЕ СОВПАДАЕТ"
        print(f"\n[{env['created_at'][:16]}] {env['from']} → {env['to']} "
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


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")

    s = sub.add_parser("send")
    s.add_argument("text")
    s.add_argument("--channel", default="general")
    s.add_argument("--type",    default="info")

    r = sub.add_parser("read")
    r.add_argument("--unread",  action="store_true")
    r.add_argument("--channel", default=None)

    args = parser.parse_args()

    if args.cmd == "send":
        send_message(args.text, args.channel, args.type)
    elif args.cmd == "read":
        read_messages(args.unread, args.channel)
    else:
        parser.print_help()
