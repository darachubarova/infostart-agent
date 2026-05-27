import { query } from "@anthropic-ai/claude-agent-sdk";

const MODE = process.env.MODE ?? "trends"; // "trends" | "forum"
const TOPIC_INDEX = Number(process.env.TOPIC_INDEX ?? 0);
const FORUM_SECTION = process.env.FORUM_SECTION ?? "forum9"; // forum8, forum9, forum63...

const TREND_TOPICS = [
  { focus: "разработка и инструменты" },
  { focus: "карьера, зарплаты и жизнь сообщества" },
  { focus: "интеграции и регуляторика" },
];

const TRENDS_PROMPT = (focus: string) => `
Ты — опытный автор для профессионального сообщества 1С-разработчиков.
Твои статьи публикуются от имени реальных людей — технических директоров и ведущих разработчиков.
Задача: написать статью уровня "публикую без правки".

## Фокус: ${focus}

## Шаг 1 — Данные
Загрузи параллельно 5 страниц:
https://infostart.ru/1c/articles/?period=30&sort=property_comments&object_view=22582&PAGEN_1=1
https://infostart.ru/1c/articles/?period=30&sort=property_comments&object_view=22582&PAGEN_1=2
https://infostart.ru/1c/articles/?period=30&sort=property_comments&object_view=22582&PAGEN_1=3
https://infostart.ru/1c/articles/?period=30&sort=property_comments&object_view=22582&PAGEN_1=4
https://infostart.ru/1c/articles/?period=30&sort=property_comments&object_view=22582&PAGEN_1=5

Отбери статьи по теме "${focus}". Для топ-3 — загрузи саму статью и комментарии.

## Шаг 2 — Анализ
Сохрани в raw_data.json и trends.json (trend_score = count × avg_comments, выбросы >3× — исключить).

## Шаг 3 — Статья
Файл: articles/trends_${focus.replace(/[^а-яё\w]/gi, "_")}_${new Date().toISOString().slice(0,10)}.md

Требования:
- 700–1000 слов, от первого лица
- Конкретные цитаты из комментариев как доказательства
- Неожиданный угол — не пересказ, а интерпретация
- Без списков, канцелярита, шаблонных фраз
- Заканчивается провокацией к читателю
`;

const FORUM_PROMPT = (section: string) => `
Ты — опытный автор для профессионального сообщества 1С-разработчиков.
Задача: найти на форуме infostart.ru реальные вопросы без ответов и написать по каждому исчерпывающую статью.

## Шаг 1 — Сканирование форума
Загрузи параллельно 3 страницы раздела:
https://forum.infostart.ru/${section}/?PAGEN_1=1
https://forum.infostart.ru/${section}/?PAGEN_1=2
https://forum.infostart.ru/${section}/?PAGEN_1=3

Отбери темы с 0–3 ответами — это вопросы без решения. Сохрани список в forum_topics.json.

## Шаг 2 — Глубокое чтение
Для топ-5 тем по релевантности (выбери сам) — загрузи полный тред: вопрос + все ответы.
Пойми: в чём реальная проблема? Что человек пытается сделать?

## Шаг 3 — Статьи
Для каждой из 5 тем напиши отдельную статью-ответ:
Файл: articles/forum_${section}_{slug}.md (slug — короткое английское название темы)

Требования к каждой статье:
- 400–600 слов — конкретно и по делу
- Отвечает на реальный вопрос из форума, но шире: объясняет контекст и причины
- Даёт работающее решение или несколько подходов с trade-offs
- Первый абзац — боль человека своими словами, чтобы он узнал себя
- Последний абзац — что делать если не помогло, куда смотреть дальше
- Тон: старший коллега объясняет младшему, без снисхождения
`;

const prompt = MODE === "forum"
  ? FORUM_PROMPT(FORUM_SECTION)
  : TRENDS_PROMPT(TREND_TOPICS[TOPIC_INDEX % TREND_TOPICS.length].focus);

// Создаём папку articles если нет
import { mkdirSync } from "fs";
try { mkdirSync("articles", { recursive: true }); } catch {}

// Forum → Haiku (дешевле, техника), Trends → Sonnet (нужен голос)
const model = MODE === "forum"
  ? "claude-haiku-4-5-20251001"
  : "claude-sonnet-4-6";

for await (const message of query({
  prompt,
  options: {
    allowedTools: ["WebFetch", "Write", "Read", "Bash"],
    permissionMode: "acceptEdits",
    maxTurns: 40,
    model,
  },
})) {
  if (message.type === "assistant" && message.message?.content) {
    for (const block of message.message.content) {
      if ("text" in block && block.text.trim()) process.stdout.write(block.text + "\n");
      else if ("name" in block) process.stdout.write(`[${block.name}]\n`);
    }
  } else if (message.type === "result") {
    console.log(`\n--- ${message.subtype} ---`);
  }
}
