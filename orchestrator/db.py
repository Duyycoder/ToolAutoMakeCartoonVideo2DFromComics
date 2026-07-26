"""
Lớp lưu trữ metadata nhẹ bằng SQLite (A4).

Dữ liệu NHẸ (metadata truyện/chương/job) lưu trong SQLite `app.db`.
Dữ liệu NẶNG (md, wav, mp4, khung ảnh) vẫn nằm trên đĩa dưới thư mục dữ liệu.

Thiết kế theo đúng ERD trong báo cáo: stories (1) — (N) chapters, stories (1) — (N) jobs.
Lớp này được thiết kế để MIRROR song song với story.json (không phá luồng tệp cũ):
mỗi khi ghi story.json, StorageManager đồng bộ luôn sang DB để có nguồn truy vấn thống nhất
(phục vụ thống kê, dashboard, và kiểm chứng thiết kế dữ liệu).
"""
import os
import sqlite3
import datetime
from typing import Any, Dict, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS stories (
    slug          TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    source        TEXT,
    language      TEXT,
    status        TEXT,
    pipeline_step INTEGER DEFAULT 1,
    created_at    TEXT,
    updated_at    TEXT
);
CREATE TABLE IF NOT EXISTS chapters (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    story_slug TEXT NOT NULL,
    idx        INTEGER NOT NULL,
    title      TEXT,
    md_path    TEXT,
    wav_path   TEXT,
    mp4_path   TEXT,
    status     TEXT,
    UNIQUE(story_slug, idx),
    FOREIGN KEY (story_slug) REFERENCES stories(slug) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS jobs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    story_slug TEXT NOT NULL,
    step       TEXT NOT NULL,
    status     TEXT,
    message    TEXT,
    started_at TEXT,
    ended_at   TEXT,
    FOREIGN KEY (story_slug) REFERENCES stories(slug) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_chapters_story ON chapters(story_slug);
CREATE INDEX IF NOT EXISTS idx_jobs_story ON jobs(story_slug);
"""


def _now() -> str:
    return datetime.datetime.now().isoformat()


def connect(db_path: str) -> sqlite3.Connection:
    """Mở kết nối ngắn hạn (mỗi thao tác tự mở/đóng) — an toàn khi gọi từ nhiều luồng."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(db_path: str) -> None:
    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def upsert_story(db_path: str, meta: Dict[str, Any]) -> None:
    """Đồng bộ một bản ghi story từ dict story.json vào bảng stories."""
    slug = meta.get("story_slug") or meta.get("slug")
    if not slug:
        return
    row = (
        slug,
        meta.get("story_name") or meta.get("name") or slug,
        (meta.get("crawler") or {}).get("source_url") or meta.get("source") or "",
        meta.get("language") or (meta.get("crawler") or {}).get("language") or "",
        meta.get("status", "CREATED"),
        int(meta.get("pipeline_step", 1) or 1),
        meta.get("created_at") or _now(),
        meta.get("updated_at") or _now(),
    )
    conn = connect(db_path)
    try:
        conn.execute(
            """INSERT INTO stories (slug, name, source, language, status, pipeline_step, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(slug) DO UPDATE SET
                 name=excluded.name, source=excluded.source, language=excluded.language,
                 status=excluded.status, pipeline_step=excluded.pipeline_step,
                 updated_at=excluded.updated_at""",
            row,
        )
        conn.commit()
    finally:
        conn.close()


def replace_chapters(db_path: str, slug: str, chapters: List[Dict[str, Any]]) -> None:
    """Thay toàn bộ danh sách chương của một truyện (đồng bộ từ đĩa)."""
    conn = connect(db_path)
    try:
        conn.execute("DELETE FROM chapters WHERE story_slug=?", (slug,))
        conn.executemany(
            """INSERT INTO chapters (story_slug, idx, title, md_path, wav_path, mp4_path, status)
               VALUES (?,?,?,?,?,?,?)""",
            [
                (slug, c.get("idx", i + 1), c.get("title", ""),
                 c.get("md_path"), c.get("wav_path"), c.get("mp4_path"), c.get("status", ""))
                for i, c in enumerate(chapters)
            ],
        )
        conn.commit()
    finally:
        conn.close()


def add_job(db_path: str, slug: str, step: str, status: str = "RUNNING", message: str = "") -> int:
    conn = connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO jobs (story_slug, step, status, message, started_at) VALUES (?,?,?,?,?)",
            (slug, step, status, message, _now()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def finish_job(db_path: str, job_id: int, status: str, message: str = "") -> None:
    conn = connect(db_path)
    try:
        conn.execute(
            "UPDATE jobs SET status=?, message=?, ended_at=? WHERE id=?",
            (status, message, _now(), job_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_stories(db_path: str) -> List[Dict[str, Any]]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """SELECT s.*, (SELECT COUNT(*) FROM chapters c WHERE c.story_slug = s.slug) AS chapter_count
               FROM stories s ORDER BY updated_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_story(db_path: str, slug: str) -> Optional[Dict[str, Any]]:
    conn = connect(db_path)
    try:
        r = conn.execute("SELECT * FROM stories WHERE slug=?", (slug,)).fetchone()
        if not r:
            return None
        story = dict(r)
        story["chapters"] = [dict(x) for x in conn.execute(
            "SELECT * FROM chapters WHERE story_slug=? ORDER BY idx", (slug,)).fetchall()]
        story["jobs"] = [dict(x) for x in conn.execute(
            "SELECT * FROM jobs WHERE story_slug=? ORDER BY id DESC", (slug,)).fetchall()]
        return story
    finally:
        conn.close()


def delete_story(db_path: str, slug: str) -> None:
    conn = connect(db_path)
    try:
        conn.execute("DELETE FROM stories WHERE slug=?", (slug,))
        conn.commit()
    finally:
        conn.close()


def stats(db_path: str) -> Dict[str, Any]:
    """Số liệu tổng hợp phục vụ dashboard/thống kê."""
    conn = connect(db_path)
    try:
        def scalar(q, *a):
            return conn.execute(q, a).fetchone()[0]
        return {
            "total_stories": scalar("SELECT COUNT(*) FROM stories"),
            "total_chapters": scalar("SELECT COUNT(*) FROM chapters"),
            "videos_done": scalar("SELECT COUNT(*) FROM chapters WHERE mp4_path IS NOT NULL AND mp4_path<>''"),
            "jobs_failed": scalar("SELECT COUNT(*) FROM jobs WHERE status LIKE '%FAIL%'"),
        }
    finally:
        conn.close()
