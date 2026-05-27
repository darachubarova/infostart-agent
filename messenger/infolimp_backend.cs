// Вставьте в контроллер ASP.NET. Таблица messages уже описана ниже.
// Требует: System.Data.SqlClient или Microsoft.Data.SqlClient

using Microsoft.AspNetCore.Mvc;
using System.Data.SqlClient;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

[ApiController]
[Route("api/messenger")]
public class MessengerController : ControllerBase
{
    static readonly string ConnStr  = Environment.GetEnvironmentVariable("DB_CONNSTR")!;
    static readonly string ApiKey   = Environment.GetEnvironmentVariable("MESSENGER_API_KEY")!;
    static readonly string HmacKey  = Environment.GetEnvironmentVariable("MESSENGER_HMAC_KEY")!;

    // ── Auth ──────────────────────────────────────────────────────────────
    bool Authorized() =>
        Request.Headers.TryGetValue("Authorization", out var h) &&
        h.ToString() == $"Bearer {ApiKey}";

    // ── HMAC verify ───────────────────────────────────────────────────────
    bool VerifyHmac(MessageDto m, string sig)
    {
        var canon = $"{m.from}|{m.to}|{m.channel}|{m.type}|{m.text}|{m.created_at}";
        using var hmac = new HMACSHA256(Encoding.UTF8.GetBytes(HmacKey));
        var expected   = Convert.ToHexString(
            hmac.ComputeHash(Encoding.UTF8.GetBytes(canon))
        ).ToLower();
        return expected == sig?.ToLower();
    }

    // ── POST /api/messenger/send ──────────────────────────────────────────
    [HttpPost("send")]
    public IActionResult Send([FromBody] JsonElement body)
    {
        if (!Authorized()) return Unauthorized();

        var sig = body.TryGetProperty("signature", out var s) ? s.GetString() : "";
        var m   = JsonSerializer.Deserialize<MessageDto>(body.GetRawText())!;

        if (!VerifyHmac(m, sig!))
            return BadRequest(new { error = "HMAC mismatch" });

        var id = $"msg_{Guid.NewGuid().ToString("N")[..12]}";

        using var conn = new SqlConnection(ConnStr);
        conn.Open();
        new SqlCommand($@"
            INSERT INTO messages (id, from_who, to_who, channel, type, text, payload, created_at)
            VALUES ('{id}', '{m.from}', '{m.to}', '{m.channel}', '{m.type}',
                    N'{m.text.Replace("'", "''")}',
                    N'{(m.payload ?? "{}").Replace("'", "''")}',
                    '{m.created_at}')", conn).ExecuteNonQuery();

        return Ok(new { id, created_at = m.created_at });
    }

    // ── GET /api/messenger/inbox ──────────────────────────────────────────
    [HttpGet("inbox")]
    public IActionResult Inbox(
        [FromQuery] string to      = "infostart-agent",
        [FromQuery] bool   unread  = false,
        [FromQuery] string? channel = null)
    {
        if (!Authorized()) return Unauthorized();

        var where = $"WHERE to_who = '{to}'";
        if (unread)   where += " AND is_read = 0";
        if (channel != null) where += $" AND channel = '{channel}'";

        using var conn = new SqlConnection(ConnStr);
        conn.Open();
        var cmd = new SqlCommand(
            $"SELECT id,from_who,to_who,channel,type,text,payload,created_at,is_read " +
            $"FROM messages {where} ORDER BY created_at", conn);

        var msgs = new List<object>();
        using var rdr = cmd.ExecuteReader();
        while (rdr.Read())
            msgs.Add(new {
                id         = rdr["id"],
                from       = rdr["from_who"],
                to         = rdr["to_who"],
                channel    = rdr["channel"],
                type       = rdr["type"],
                text       = rdr["text"],
                payload    = rdr["payload"] == DBNull.Value ? null : rdr["payload"],
                created_at = rdr["created_at"],
                read       = (bool)rdr["is_read"]
            });

        return Ok(msgs);
    }

    // ── POST /api/messenger/read ──────────────────────────────────────────
    [HttpPost("read")]
    public IActionResult MarkRead([FromBody] ReadDto dto)
    {
        if (!Authorized()) return Unauthorized();
        if (dto.ids == null || dto.ids.Length == 0) return Ok(new { ok = true });

        var ids = string.Join(",", dto.ids.Select(id => $"'{id}'"));
        using var conn = new SqlConnection(ConnStr);
        conn.Open();
        new SqlCommand($"UPDATE messages SET is_read=1 WHERE id IN ({ids})", conn)
            .ExecuteNonQuery();

        return Ok(new { ok = true });
    }
}

// ── DTOs ─────────────────────────────────────────────────────────────────
public record MessageDto(
    string from, string to, string channel, string type,
    string text, string? payload, string created_at, string? signature
);
public record ReadDto(string[] ids);

/*
── SQL таблица (выполнить один раз) ──────────────────────────────────────
CREATE TABLE messages (
  id         VARCHAR(20)   PRIMARY KEY,
  from_who   VARCHAR(50)   NOT NULL,
  to_who     VARCHAR(50)   NOT NULL,
  channel    VARCHAR(20)   NOT NULL DEFAULT 'general',
  type       VARCHAR(20)   NOT NULL DEFAULT 'info',
  text       NVARCHAR(MAX) NOT NULL,
  payload    NVARCHAR(MAX) NULL,
  created_at VARCHAR(35)   NOT NULL,
  is_read    BIT           NOT NULL DEFAULT 0
);

── Environment variables ─────────────────────────────────────────────────
MESSENGER_API_KEY  = (тот же ключ что для /api/articles)
MESSENGER_HMAC_KEY = 80fa7ae88d1d9d78f14a394917104ca773e6db448e93bc0e798953eca3c7c1bd58c95be9e9a8aa1397dc5d09857e20be6b7e1fa0bc2c5465477ce42a251477eb
DB_CONNSTR         = (строка подключения к SQL Server)

── Как написать нам сообщение ───────────────────────────────────────────
Просто вставьте запись напрямую в таблицу messages:
INSERT INTO messages (id, from_who, to_who, channel, type, text, created_at)
VALUES ('msg_manual_001', 'infolimp', 'infostart-agent', 'general', 'info',
        N'Текст вашего сообщения', GETUTCDATE())

Мы опрашиваем /api/messenger/inbox каждый час автоматически.
*/
