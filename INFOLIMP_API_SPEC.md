# API для зеркалирования статей — спецификация для infolimp.ru

## Что нужно реализовать

Один POST-эндпоинт для создания статьи. Если статья с таким `slug` уже существует — обновить, не дублировать.

---

## Эндпоинт

```
POST /api/articles
```

### Заголовки запроса

```
Content-Type: application/json; charset=utf-8
Authorization: Bearer <API_KEY>
```

`API_KEY` — любая строка, которую вы генерируете и передаёте нам в секрете.

---

## Тело запроса (JSON)

```json
{
  "title":        "Session not found: почему Claude Desktop теряет сессию",
  "slug":         "forum_forum9_mcp-vanessa-claude-session",
  "content":      "# Заголовок\n\nТекст статьи в формате Markdown...",
  "date":         "2026-05-27",
  "tags":         ["1С", "разработка", "форум"],
  "category":     "Форум",
  "canonical_url":"https://darachubarova.github.io/infostart-agent/posts/forum_forum9_mcp-vanessa-claude-session/",
  "author":       "1С Инсайдер"
}
```

| Поле           | Тип     | Описание                                              |
|----------------|---------|-------------------------------------------------------|
| `title`        | string  | Заголовок статьи                                      |
| `slug`         | string  | Уникальный идентификатор (латиница, цифры, дефисы)    |
| `content`      | string  | Тело статьи в Markdown                                |
| `date`         | string  | Дата публикации (YYYY-MM-DD)                          |
| `tags`         | array   | Теги                                                  |
| `category`     | string  | Категория («Форум» или «Тренды»)                      |
| `canonical_url`| string  | Ссылка на оригинал — важна для SEO                    |
| `author`       | string  | Имя автора                                            |

---

## Ответ

### Успех (200 или 201)

```json
{
  "id":  42,
  "url": "https://infolimp.ru/articles/forum_forum9_mcp-vanessa-claude-session.html"
}
```

### Ошибка (4xx / 5xx)

```json
{
  "error": "Описание ошибки"
}
```

---

## Логика на стороне сервера

- Если `slug` уже существует — **обновить** статью (upsert), не создавать дубль
- `canonical_url` желательно добавить как `<link rel="canonical">` в `<head>` страницы — это даёт SEO-вес оригиналу и вам одновременно
- Markdown можно рендерить в HTML любой библиотекой (Python: `markdown2`, PHP: `Parsedown`, JS: `marked`)
- Авторизацию проверять по заголовку `Authorization: Bearer <token>`

---

## Что передать нам после реализации

1. Финальный URL эндпоинта (например, `https://infolimp.ru/api/articles`)
2. API-ключ (любая случайная строка, например `openssl rand -hex 32`)

Мы добавим их в секреты GitHub Actions — и зеркалирование заработает автоматически после каждой публикации.
