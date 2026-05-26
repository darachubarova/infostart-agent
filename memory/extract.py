"""
Принимает текст сессии (stdin или файл), извлекает сущности и связи
через Claude API, записывает в граф, обновляет context.md.

Использование:
    python extract.py "текст сессии"
    cat session.txt | python extract.py
"""
import sys
import json
import os
import anthropic
from pathlib import Path

# Загружаем .env из корня проекта
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent))
from graph import init_schema, add_concepts_and_relations, get_context_summary

SYSTEM = """Ты — система извлечения знаний. Из текста диалога извлекаешь концепции и связи между ними.

Верни JSON строго в формате:
{
  "nodes": [
    {"name": "...", "type": "tool|project|plan|concept|person|decision", "description": "одна фраза"}
  ],
  "edges": [
    {"from": "...", "to": "...", "label": "глагол/фраза", "weight": 0.0-1.0}
  ]
}

Правила:
- Только значимые концепции (не стоп-слова, не мелкие детали)
- Имена — короткие, на русском, в именительном падеже
- weight: 1.0 = ключевая связь, 0.5 = упомянутая, 0.2 = слабая
- Максимум 15 узлов и 20 рёбер на сессию
"""

def extract(session_text: str) -> dict:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=SYSTEM,
        messages=[{"role": "user", "content": f"Диалог:\n\n{session_text[:6000]}"}]
    )
    text = response.content[0].text.strip()
    # Вырезаем JSON если обёрнут в ```
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                text = part
                break
    # Находим границы JSON объекта
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        text = text[start:end]
    return json.loads(text)

def update_context_md(summary: str):
    path = Path(__file__).parent / "context.md"
    path.write_text(summary, encoding="utf-8")

def main():
    if len(sys.argv) > 1:
        session_text = " ".join(sys.argv[1:])
    else:
        session_text = sys.stdin.read()

    if not session_text.strip():
        print("Нет текста для обработки.")
        return

    print("Извлекаю концепции и связи...")
    init_schema()
    data = extract(session_text)
    print(f"  Найдено: {len(data.get('nodes', []))} узлов, {len(data.get('edges', []))} связей")
    add_concepts_and_relations(data)

    summary = get_context_summary()
    update_context_md(summary)
    print("Graf obnovlen. memory/context.md zapisan.")

if __name__ == "__main__":
    main()
