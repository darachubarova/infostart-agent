# Внутренний мессенджер — техническое задание для backend infolimp.ru

## Зачем это нужно

Нам нужен простой канал оперативной связи между двумя сторонами:
- **infostart-agent** (наша сторона) — автоматические агенты + ручное управление
- **infolimp.ru** (ваша сторона) — редакция, backend, администраторы

Сценарии использования:
- Агент опубликовал статью → автоматически уведомляет infolimp о новой публикации
- Агент обнаружил ошибку API → отправляет алерт
- infolimp нашёл проблему с контентом → сообщает нам
- Мы ставим задачу → они видят её, отвечают

---

## Что нужно реализовать

Три эндпоинта. Хранилище — любое (SQLite, SQL Server, даже JSON-файл на старте).

---

### 1. Отправить сообщение

```
POST /api/messenger/send
Authorization: Bearer <API_KEY>
Content-Type: application/json

{
  "from":    "infostart-agent",
  "to":      "infolimp",
  "channel": "general",
  "type":    "info",
  "text":    "Опубликовано 5 новых статей. Проверьте canonical в <head>.",
  "payload": { "articles": ["slug-1", "slug-2"] }
}
```

| Поле      | Тип    | Значения                                      |
|-----------|--------|-----------------------------------------------|
| `from`    | string | `"infostart-agent"` или `"infolimp"`          |
| `to`      | string | `"infolimp"` или `"infostart-agent"`          |
| `channel` | string | `"general"`, `"alerts"`, `"tasks"`, `"tech"`  |
| `type`    | string | `"info"`, `"task"`, `"alert"`, `"reply"`      |
| `text`    | string | Текст сообщения                               |
| `payload` | object | Любые дополнительные данные (опционально)     |

**Ответ:**
```json
{ "id": "msg_0042", "created_at": "2026-05-27T10:00:00Z" }
```

---

### 2. Получить новые сообщения

```
GET /api/messenger/inbox?to=infostart-agent&since=2026-05-27T10:00:00Z&unread=true
Authorization: Bearer <API_KEY>
```

| Параметр  | Описание                                          |
|-----------|---------------------------------------------------|
| `to`      | Получатель (фильтр)                               |
| `since`   | ISO8601 timestamp — только сообщения после него   |
| `unread`  | `true` — только непрочитанные                     |
| `channel` | Опционально — фильтр по каналу                    |

**Ответ:**
```json
[
  {
    "id":         "msg_0041",
    "from":       "infolimp",
    "channel":    "tech",
    "type":       "reply",
    "text":       "Canonical в <head> проставлен, проверьте.",
    "payload":    null,
    "created_at": "2026-05-27T11:00:00Z",
    "read":       false
  }
]
```

---

### 3. Отметить прочитанным

```
POST /api/messenger/read
Authorization: Bearer <API_KEY>
Content-Type: application/json

{ "ids": ["msg_0041", "msg_0042"] }
```

**Ответ:** `{ "ok": true }`

---

## Авторизация

Один общий ключ на оба направления (тот же что используем для статей), или отдельный — на ваше усмотрение.

---

## Что реализуем мы (infostart-agent)

После каждого деплоя статей — автоматически отправляем сообщение в канал `general`:
```
Опубликовано N статей: [список slug'ов]. Сайт: https://darachubarova.github.io/infostart-agent/
```

При ошибке API (HTTP 4xx/5xx) — алерт в канал `alerts`.

Раз в час наши агенты читают `inbox` и при наличии сообщений типа `task` — обрабатывают их (например, перепубликовать статью, обновить slug).

---

## Минимальная реализация (можно за 2 часа)

Если хотите стартовать быстро — достаточно только `send` и `inbox`. Хранить в таблице:

```sql
CREATE TABLE messages (
  id         VARCHAR(20) PRIMARY KEY,
  from_who   VARCHAR(50),
  to_who     VARCHAR(50),
  channel    VARCHAR(20),
  type       VARCHAR(20),
  text       NVARCHAR(MAX),
  payload    NVARCHAR(MAX),
  created_at DATETIME DEFAULT GETDATE(),
  is_read    BIT DEFAULT 0
);
```

IIS + любой ASP.NET контроллер сверху — и готово.

---

## Что передать нам после реализации

- URL эндпоинтов (скорее всего `https://infolimp.ru/api/messenger/...`)
- API-ключ (можно тот же что для статей)
