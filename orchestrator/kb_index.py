"""Chỉ mục tri thức cho trợ lý: chia nhỏ Markdown + tìm kiếm bằng SQLite FTS5.

Nguồn sự thật vẫn là `docs/kb/*.md` — git theo dõi được, review được. SQLite chỉ
là chỉ mục SINH LẠI ĐƯỢC: xoá đi nạp lại là xong, không mất tri thức.

Module này làm HAI việc, và chỉ một trong hai đang được dùng ở luồng chính:

1. **Chia nhỏ + lưu mảnh** (`chunk_markdown`, `build_index`, `load_chunks`) — ĐANG
   DÙNG. Cắt theo cấp tiêu đề, trần 400 ký tự, nhân bản đường dẫn ngữ cảnh vào đầu
   mỗi mảnh. Đo được: context mỗi câu giảm từ 1473 xuống 854 token (−42%).

2. **Tìm kiếm BM25 qua FTS5** (`search`) — CÓ SẴN NHƯNG CHƯA DÙNG MẶC ĐỊNH.
   Đo trên bộ eval 36 câu (2026-08-04), BM25 thua bộ chấm IDF trong `chatbot.py`:

       IDF  : QA 28/28 (100%)  | chặn ngoài phạm vi 7/8 (87.5%)
       BM25 : QA 27/28 (96.4%) | chặn 7/8 (87.5%)      -- ngưỡng 1.40
       BM25 : QA 28/28 (100%)  | chặn 6/8 (75.0%)      -- ngưỡng 1.35

   IDF trội hơn ở mọi điểm vận hành, nên giữ IDF. Không xoá `search()` vì lợi thế
   của BM25 là ổn định khi kho tri thức lớn — hãy đo lại bằng
   `scripts/eval_chatbot.py` khi KB vượt khoảng gấp đôi hiện tại (~240 mảnh);
   rất có thể lúc đó BM25 mới thắng.
"""
import os
import re
import sqlite3
from typing import List, Tuple

# Trần độ dài một mảnh. Vượt thì cắt tiếp theo ranh giới dòng/gạch đầu dòng.
MAX_CHUNK_CHARS = 400

SCHEMA = """
CREATE TABLE IF NOT EXISTS kb_chunks (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    file      TEXT NOT NULL,
    path      TEXT NOT NULL,   -- "Tổng quan › Cấu trúc lưu trữ" — ngữ cảnh của mảnh
    header    TEXT NOT NULL,
    content   TEXT NOT NULL,   -- nội dung đưa vào prompt (đã kèm đường dẫn ngữ cảnh)
    mtime     REAL NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS kb_fts USING fts5(
    body,
    content='',
    tokenize='unicode61 remove_diacritics 2'
);
"""


def _connect(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def _split_long(text: str, limit: int = MAX_CHUNK_CHARS) -> List[str]:
    """Cắt đoạn dài theo ranh giới tự nhiên: dòng trống trước, rồi từng dòng."""
    text = text.strip()
    if len(text) <= limit:
        return [text] if text else []

    out, buf = [], ""
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block:
            continue
        if len(block) > limit:
            if buf:
                out.append(buf)
                buf = ""
            line_buf = ""
            for line in block.splitlines():
                if len(line_buf) + len(line) + 1 > limit and line_buf:
                    out.append(line_buf.strip())
                    line_buf = ""
                line_buf += line + "\n"
            if line_buf.strip():
                out.append(line_buf.strip())
        elif len(buf) + len(block) + 2 > limit:
            if buf:
                out.append(buf)
            buf = block
        else:
            buf = (buf + "\n\n" + block).strip()
    if buf:
        out.append(buf)
    return out


def chunk_markdown(text: str, fname: str) -> List[dict]:
    """Chia một file Markdown thành các mảnh tự đứng vững.

    Mỗi mảnh được nhân bản đường dẫn ngữ cảnh ở đầu. Không có nó, mảnh
    "- `classic`: 1 ảnh/cảnh" tách khỏi tiêu đề "Chế độ render — Bước 3" là vô
    nghĩa với cả người đọc lẫn model. Đây là chỗ dễ hỏng nhất khi chia nhỏ.
    """
    doc_title = ""
    h2 = ""
    h3 = ""
    buf: List[str] = []
    chunks: List[dict] = []

    def flush():
        nonlocal buf
        body = "\n".join(buf).strip()
        buf = []
        if not body:
            return
        parts = [p for p in (doc_title, h2, h3) if p]
        path = " › ".join(parts)
        header = h3 or h2 or doc_title
        for piece in _split_long(body):
            chunks.append({
                "file": fname,
                "path": path,
                "header": header,
                # Đường dẫn ngữ cảnh đi kèm nội dung: vừa để model hiểu mảnh này
                # thuộc đâu, vừa để FTS5 tìm được theo tên bước/tên tham số.
                "content": f"[{path}]\n{piece}" if path else piece,
            })

    for line in text.splitlines():
        m1 = re.match(r"^#\s+(.*)", line)
        m2 = re.match(r"^##\s+(.*)", line)
        m3 = re.match(r"^###\s+(.*)", line)
        if m1:
            flush()
            doc_title, h2, h3 = m1.group(1).strip(), "", ""
        elif m2:
            flush()
            h2, h3 = m2.group(1).strip(), ""
        elif m3:
            flush()
            h3 = m3.group(1).strip()
        else:
            buf.append(line)
    flush()
    return chunks


def build_index(kb_dir: str, db_path: str) -> int:
    """Nạp lại toàn bộ chỉ mục từ thư mục KB. Trả về số mảnh."""
    conn = _connect(db_path)
    try:
        # Bảng FTS5 dạng contentless không cho DELETE, nên nạp lại = dựng lại bảng.
        conn.executescript(
            "DROP TABLE IF EXISTS kb_fts; DROP TABLE IF EXISTS kb_chunks;"
        )
        conn.executescript(SCHEMA)

        n = 0
        if os.path.isdir(kb_dir):
            for fname in sorted(os.listdir(kb_dir)):
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(kb_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        text = f.read()
                except OSError:
                    continue
                mtime = os.path.getmtime(fpath)
                for ch in chunk_markdown(text, fname):
                    cur = conn.execute(
                        "INSERT INTO kb_chunks(file, path, header, content, mtime)"
                        " VALUES (?,?,?,?,?)",
                        (ch["file"], ch["path"], ch["header"], ch["content"], mtime),
                    )
                    conn.execute(
                        "INSERT INTO kb_fts(rowid, body) VALUES (?,?)",
                        (cur.lastrowid, ch["content"]),
                    )
                    n += 1
        conn.commit()
        return n
    finally:
        conn.close()


def load_chunks(db_path: str) -> List[dict]:
    """Đọc toàn bộ mảnh từ chỉ mục để chấm điểm trong bộ nhớ."""
    if not os.path.exists(db_path):
        return []
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id, file, path, header, content FROM kb_chunks ORDER BY id"
        ).fetchall()
        return [{
            "file": r["file"],
            "path": r["path"],
            "header": r["header"],
            "content": r["content"],
            "id": f'{r["file"]}#{r["id"]}',
        } for r in rows]
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def kb_mtime(kb_dir: str) -> float:
    """mtime lớn nhất trong thư mục KB — dùng để biết chỉ mục có cũ không."""
    latest = 0.0
    if os.path.isdir(kb_dir):
        for fname in os.listdir(kb_dir):
            if fname.endswith(".md"):
                latest = max(latest, os.path.getmtime(os.path.join(kb_dir, fname)))
    return latest


def index_is_stale(kb_dir: str, db_path: str) -> bool:
    if not os.path.exists(db_path):
        return True
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT MAX(mtime) AS m, COUNT(*) AS c FROM kb_chunks").fetchone()
    except sqlite3.Error:
        return True
    finally:
        conn.close()
    if not row or not row["c"]:
        return True
    return kb_mtime(kb_dir) > (row["m"] or 0)


_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _terms(query: str) -> List[str]:
    """Tách từ khoá và BỎ HƯ TỪ trước khi dựng truy vấn.

    Quan trọng với nhịp AND: FTS5 bắt buộc mọi từ phải cùng xuất hiện trong một
    mảnh. Để nguyên hư từ thì "Bước 3 chọn checkpoint nào?" đòi mảnh phải chứa cả
    "nào" — gần như chắc chắn rỗng, rồi rơi xuống OR và trả về rác. Bỏ hư từ giúp
    AND thành công đúng ở những câu nó nên thành công.
    """
    from orchestrator.chatbot import VIETNAMESE_STOPWORDS, remove_vietnamese_diacritics

    out = []
    for t in _TOKEN_RE.findall(query):
        if len(t) <= 1:
            continue
        if remove_vietnamese_diacritics(t) in VIETNAMESE_STOPWORDS:
            continue
        out.append(t)
    # Câu chỉ toàn hư từ: giữ nguyên từ gốc còn hơn không tìm gì.
    return out or [t for t in _TOKEN_RE.findall(query) if len(t) > 1]


def search(db_path: str, query: str, limit: int = 8) -> List[Tuple[dict, float]]:
    """Tìm mảnh liên quan. Trả về [(mảnh, điểm dương càng cao càng khớp)].

    Hai nhịp:
      1. AND — FTS5 mặc định. Rất chặt: câu chứa một từ lạ là về rỗng, nên câu
         ngoài phạm vi tự bị loại mà không cần ngưỡng.
      2. Nếu AND rỗng, chạy lại bằng OR rồi mới dựa vào ngưỡng để lọc. Giữ được
         recall cho câu hợp lệ dùng từ hiếm hoặc gõ thiếu.
    """
    terms = _terms(query)
    if not terms:
        return []

    conn = _connect(db_path)
    try:
        for phase, expr in (("AND", " ".join(f'"{t}"' for t in terms)),
                            ("OR", " OR ".join(f'"{t}"' for t in terms))):
            try:
                rows = conn.execute(
                    "SELECT c.file, c.path, c.header, c.content, bm25(kb_fts) AS score"
                    " FROM kb_fts JOIN kb_chunks c ON c.id = kb_fts.rowid"
                    " WHERE kb_fts MATCH ? ORDER BY score LIMIT ?",
                    (expr, limit),
                ).fetchall()
            except sqlite3.Error:
                rows = []
            if rows:
                # bm25() của SQLite trả SỐ ÂM, càng âm càng khớp. Đảo dấu để
                # phần còn lại của hệ thống dùng quy ước "điểm cao = liên quan",
                # rồi chia cho số từ khoá để câu dài không tự nhiên được điểm cao.
                n = max(len(terms), 1)
                out = [({
                    "file": r["file"],
                    "path": r["path"],
                    "header": r["header"],
                    "content": r["content"],
                    "id": f'{r["file"]}#{r["path"]}',
                    "phase": phase,
                }, -float(r["score"]) / n) for r in rows]
                return out
        return []
    finally:
        conn.close()
