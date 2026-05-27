"""Конвертирует статьи из articles/ в Hugo-формат site/content/posts/"""
import os, re
from pathlib import Path
from datetime import date

SRC = Path("articles")
DST = Path("site/content/posts")
DST.mkdir(parents=True, exist_ok=True)

TAG_MAP = {
    "forum_forum9": ["разработка", "1С", "форум"],
    "forum_forum8": ["ERP", "1С", "форум"],
    "trends_dev": ["тренды", "инструменты", "разработка"],
    "trends_career": ["тренды", "карьера", "сообщество"],
    "trends_integration": ["тренды", "интеграции", "регуляторика"],
    "trends_разработка": ["тренды", "инструменты", "разработка"],
    "trends_карьера": ["тренды", "карьера", "сообщество"],
    "trends_интеграции": ["тренды", "интеграции", "регуляторика"],
    "article": ["тренды", "1С"],
}

def get_tags(filename):
    for key, tags in TAG_MAP.items():
        if key in filename:
            return tags
    return ["1С"]

def get_category(filename):
    if "forum" in filename:
        return "Форум"
    return "Тренды"

for src_file in SRC.glob("*.md"):
    text = src_file.read_text(encoding="utf-8")
    lines = text.strip().splitlines()

    # Извлекаем заголовок
    title = ""
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            break
    if not title:
        title = src_file.stem.replace("_", " ").replace("-", " ")

    # Ищем дату в имени файла
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", src_file.stem)
    pub_date = date_match.group(1) if date_match else str(date.today())

    tags = get_tags(src_file.stem)
    category = get_category(src_file.stem)

    # Убираем заголовок из тела (Hugo сам его рендерит)
    body_lines = [l for l in lines if not l.startswith("# " + title)]
    body = "\n".join(body_lines).strip()

    frontmatter = f"""---
title: "{title.replace('"', "'")}"
date: {pub_date}
tags: {tags}
categories: ["{category}"]
draft: false
---

"""
    dst_file = DST / src_file.name
    dst_file.write_text(frontmatter + body, encoding="utf-8")
    print(f"  {src_file.name} -> {dst_file.name}")

print(f"Готово: {len(list(SRC.glob('*.md')))} статей конвертировано.")
