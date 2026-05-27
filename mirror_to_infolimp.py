"""Зеркалирует новые статьи из site/content/posts/ на infolimp.ru через API."""
import os, re, json, hashlib
from pathlib import Path
from datetime import date
import urllib.request
import urllib.error

API_URL = os.environ.get("INFOLIMP_API_URL", "https://infolimp.ru/api/articles")
API_KEY = os.environ.get("INFOLIMP_API_KEY", "")
CANONICAL_BASE = "https://darachubarova.github.io/infostart-agent/posts/"
POSTED_FILE = Path("infolimp_posted.json")
POSTS_DIR = Path("site/content/posts")

_TRANSLIT_MAP = {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh','з':'z',
    'и':'i','й':'j','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r',
    'с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh',
    'щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
}
_TRANSLIT_MAP.update({k.upper(): v.capitalize() for k, v in _TRANSLIT_MAP.items()})

def slugify(text: str) -> str:
    text = "".join(_TRANSLIT_MAP.get(c, c) for c in text)
    text = re.sub(r"[^a-zA-Z0-9_-]", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text.lower()


def load_posted():
    if POSTED_FILE.exists():
        return set(json.loads(POSTED_FILE.read_text(encoding="utf-8")))
    return set()


def save_posted(posted: set):
    POSTED_FILE.write_text(json.dumps(sorted(posted), ensure_ascii=False, indent=2), encoding="utf-8")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Возвращает (frontmatter dict, body markdown)."""
    if not text.startswith("---"):
        return {}, text
    end = text.index("---", 3)
    fm_raw = text[3:end].strip()
    body = text[end + 3:].strip()
    fm = {}
    for line in fm_raw.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip('"')
    return fm, body


def post_article(slug: str, fm: dict, body: str) -> bool:
    slug = slugify(slug)
    canonical = f"{CANONICAL_BASE}{slug}/"
    tags_raw = fm.get("tags", "['1С']")
    tags = re.findall(r"'([^']+)'", tags_raw)

    payload = json.dumps({
        "title": fm.get("title", slug),
        "slug": slug,
        "content": body,
        "date": fm.get("date", str(date.today())),
        "tags": tags,
        "category": fm.get("categories", "Статьи").strip("[]\"'"),
        "canonical_url": canonical,
        "author": "1С Инсайдер",
    }, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            print(f"  OK  {slug} -> {result.get('url', '?')}")
            return True
    except urllib.error.HTTPError as e:
        print(f"  ERR {slug}: HTTP {e.code} {e.read().decode()}")
        return False
    except Exception as e:
        print(f"  ERR {slug}: {e}")
        return False


def main():
    if not API_KEY:
        print("INFOLIMP_API_KEY не задан — пропускаем зеркалирование.")
        return

    posted = load_posted()
    new_count = 0

    for md_file in sorted(POSTS_DIR.glob("*.md")):
        slug = md_file.stem
        if slug in posted:
            continue

        text = md_file.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(text)

        if fm.get("draft", "false").lower() == "true":
            continue

        print(f"Публикуем: {slug}")
        if post_article(slug, fm, body):
            posted.add(slug)
            new_count += 1

    save_posted(posted)
    print(f"Готово: {new_count} новых статей отправлено на infolimp.ru")


if __name__ == "__main__":
    main()
