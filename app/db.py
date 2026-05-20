import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "reservations.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name TEXT NOT NULL,
    server_id TEXT NOT NULL,
    purpose   TEXT NOT NULL,
    use_gpu   INTEGER NOT NULL,
    start_at  TEXT NOT NULL,
    end_at    TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reservations_server_time
    ON reservations(server_id, start_at, end_at);
"""


@contextmanager
def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def has_gpu_conflict(
    server_id: str, start_at: str, end_at: str, exclude_id: int | None = None
) -> bool:
    # 既存のGPU使用予約と時間帯が重なるかを判定
    query = """
        SELECT COUNT(*) FROM reservations
        WHERE server_id = ?
          AND use_gpu = 1
          AND NOT (end_at <= ? OR start_at >= ?)
    """
    params: list = [server_id, start_at, end_at]
    if exclude_id is not None:
        query += " AND id != ?"
        params.append(exclude_id)
    with get_conn() as conn:
        return conn.execute(query, params).fetchone()[0] > 0


def add_reservation(
    user_name: str,
    server_id: str,
    purpose: str,
    use_gpu: bool,
    start_at: str,
    end_at: str,
) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO reservations
                (user_name, server_id, purpose, use_gpu,
                 start_at, end_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_name, server_id, purpose, int(use_gpu),
             start_at, end_at, now, now),
        )
        return cur.lastrowid


def update_reservation(
    res_id: int,
    user_name: str,
    server_id: str,
    purpose: str,
    use_gpu: bool,
    start_at: str,
    end_at: str,
) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.execute(
            """UPDATE reservations SET
                user_name=?, server_id=?, purpose=?, use_gpu=?,
                start_at=?, end_at=?, updated_at=?
                WHERE id=?""",
            (user_name, server_id, purpose, int(use_gpu),
             start_at, end_at, now, res_id),
        )


def delete_reservation(res_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM reservations WHERE id=?", (res_id,))


def list_reservations(server_id: str | None = None) -> list[dict]:
    query = "SELECT * FROM reservations"
    params: list = []
    if server_id:
        query += " WHERE server_id = ?"
        params.append(server_id)
    query += " ORDER BY start_at"
    with get_conn() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def get_reservation(res_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM reservations WHERE id=?", (res_id,)
        ).fetchone()
        return dict(row) if row else None


def find_available_slots(
    server_id: str,
    target_date: date,
    duration_hours: int,
    use_gpu: bool,
    business_start_hour: int = 9,
    business_end_hour: int = 21,
    max_results: int = 5,
) -> list[tuple[str, str]]:
    """指定日の業務時間内で、連続して空いている候補スロットを返す。

    干渉判定:
      use_gpu=True  : 同一サーバのGPUあり予約のみを占有とみなす（既存の予約ルールと一致）
      use_gpu=False : 同一サーバの全予約を占有とみなす（混雑回避視点）

    Returns: [(start_at_iso, end_at_iso), ...] 最大 max_results 件、早い時刻順。
    """
    biz_window = business_end_hour - business_start_hour
    if duration_hours <= 0 or duration_hours > biz_window:
        return []

    biz_start = datetime.combine(target_date, time(business_start_hour, 0))
    biz_end = datetime.combine(target_date, time(business_end_hour, 0))

    gpu_filter = "AND use_gpu = 1" if use_gpu else ""
    query = f"""
        SELECT start_at, end_at FROM reservations
        WHERE server_id = ?
          {gpu_filter}
          AND NOT (end_at <= ? OR start_at >= ?)
    """
    params = [
        server_id,
        biz_start.isoformat(timespec="seconds"),
        biz_end.isoformat(timespec="seconds"),
    ]

    with get_conn() as conn:
        blockers = [
            (datetime.fromisoformat(r[0]), datetime.fromisoformat(r[1]))
            for r in conn.execute(query, params).fetchall()
        ]

    candidates: list[tuple[str, str]] = []
    for start_h in range(business_start_hour, business_end_hour - duration_hours + 1):
        cand_start = datetime.combine(target_date, time(start_h, 0))
        cand_end = cand_start + timedelta(hours=duration_hours)

        conflict = any(
            not (cand_end <= b_start or cand_start >= b_end)
            for b_start, b_end in blockers
        )
        if not conflict:
            candidates.append((
                cand_start.isoformat(timespec="seconds"),
                cand_end.isoformat(timespec="seconds"),
            ))
            if len(candidates) >= max_results:
                break

    return candidates
