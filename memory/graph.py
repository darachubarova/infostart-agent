"""
Граф общей памяти. Схема, запись, чтение.
"""
import kuzu
from pathlib import Path

DB_PATH = Path(__file__).parent / "kuzu_db"

def get_conn():
    db = kuzu.Database(str(DB_PATH))
    return kuzu.Connection(db)

def init_schema():
    conn = get_conn()
    conn.execute(
        "CREATE NODE TABLE IF NOT EXISTS Concept "
        "(name STRING, kind STRING, info STRING, PRIMARY KEY (name))"
    )
    conn.execute(
        "CREATE REL TABLE IF NOT EXISTS RELATES "
        "(FROM Concept TO Concept, label STRING, weight DOUBLE, since STRING)"
    )
    print("Схема инициализирована.")

def _node_exists(conn, name: str) -> bool:
    r = conn.execute("MATCH (c:Concept {name: $n}) RETURN c.name", {"n": name})
    return r.get_num_tuples() > 0

def _edge_exists(conn, src: str, dst: str, label: str) -> bool:
    r = conn.execute(
        "MATCH (a:Concept {name: $a})-[r:RELATES]->(b:Concept {name: $b}) "
        "WHERE r.label = $l RETURN r.label",
        {"a": src, "b": dst, "l": label}
    )
    return r.get_num_tuples() > 0

def add_concepts_and_relations(data: dict):
    from datetime import date
    today = str(date.today())
    conn = get_conn()

    for node in data.get("nodes", []):
        name = node.get("name", "").strip()
        if not name:
            continue
        kind = node.get("type", "concept")
        info = node.get("description", "")
        if _node_exists(conn, name):
            conn.execute(
                "MATCH (c:Concept {name: $n}) SET c.kind = $k, c.info = $i",
                {"n": name, "k": kind, "i": info}
            )
        else:
            conn.execute(
                "CREATE (:Concept {name: $n, kind: $k, info: $i})",
                {"n": name, "k": kind, "i": info}
            )

    for edge in data.get("edges", []):
        src = edge.get("from", "").strip()
        dst = edge.get("to", "").strip()
        label = edge.get("label", "связан с")
        weight = float(edge.get("weight", 1.0))
        if not src or not dst:
            continue
        if not _node_exists(conn, src) or not _node_exists(conn, dst):
            continue
        if not _edge_exists(conn, src, dst, label):
            conn.execute(
                "MATCH (a:Concept {name: $a}), (b:Concept {name: $b}) "
                "CREATE (a)-[:RELATES {label: $l, weight: $w, since: $s}]->(b)",
                {"a": src, "b": dst, "l": label, "w": weight, "s": today}
            )

def get_context_summary(limit: int = 40) -> str:
    conn = get_conn()

    nodes = conn.execute(
        "MATCH (c:Concept) RETURN c.name, c.kind, c.info ORDER BY c.name LIMIT $lim",
        {"lim": limit}
    ).get_as_df()

    edges = conn.execute(
        "MATCH (a:Concept)-[r:RELATES]->(b:Concept) "
        "RETURN a.name, r.label, b.name, r.since ORDER BY r.weight DESC LIMIT $lim",
        {"lim": limit}
    ).get_as_df()

    if nodes.empty:
        return "Граф памяти пуст — первая сессия."

    lines = ["## Общая память (граф знаний)\n", "### Концепции"]
    for _, row in nodes.iterrows():
        lines.append(f"- **{row['c.name']}** [{row['c.kind']}]: {row['c.info']}")

    lines.append("\n### Связи")
    for _, row in edges.iterrows():
        lines.append(f"- {row['a.name']} → *{row['r.label']}* → {row['b.name']}  _(с {row['r.since']})_")

    return "\n".join(lines)

if __name__ == "__main__":
    init_schema()
