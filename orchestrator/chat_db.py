"""
Trợ lý AI trả lời câu hỏi về dữ liệu trong CSDL `app.db` (truyện / chương / job).

Model 3B viết SQL không đáng tin (đo 02/10: ~5/11 câu đúng, hay quên ngoặc OR,
tự thêm điều kiện, đoán slug). Nên đảo vai: CODE phân loại câu hỏi, tự chạy
các truy vấn cố định và TÍNH SẴN số liệu (đếm, nhóm theo trạng thái/bước/tháng,
chương còn thiếu âm thanh/video); model chỉ việc đọc khối dữ liệu đó và diễn đạt.

Loại câu hỏi (một câu có thể thuộc nhiều loại):
- tong_quan  : luôn có — số liệu toàn bộ + bảng mọi truyện (dữ liệu nhỏ, đọc hết được).
- truyen     : câu nhắc tên truyện (hoặc "truyện này") — chi tiết chương của truyện đó.
- job        : câu hỏi về job / tác vụ / lịch sử chạy.
"""
import datetime
import re
import sqlite3
from collections import Counter, OrderedDict
from typing import Dict, List, Optional

from orchestrator.chatbot import remove_vietnamese_diacritics

STATUS_VI = {
    "CREATED": "mới tạo", "CRAWLING": "đang cào", "CRAWLED": "đã cào",
    "TRANSLATING": "đang dịch", "TRANSLATED": "đã dịch", "TRANSLATE_FAILED": "lỗi dịch",
    "WRITING": "đang viết", "WRITE_FAILED": "lỗi viết",
    "VOICE_GENERATING": "đang lồng tiếng", "VOICE_GENERATED": "đã lồng tiếng",
    "VOICE_FAILED": "lỗi lồng tiếng",
    "VIDEO_GENERATING": "đang làm video", "VIDEO_GENERATED": "đã làm video",
    "VIDEO_FAILED": "lỗi video", "CANCELLED": "đã huỷ",
    "AUTOSUB_RUNNING": "đang làm phụ đề", "AUTOSUB_COMPLETED": "đã làm phụ đề",
    "AUTOSUB_FAILED": "lỗi phụ đề",
}
STEP_VI = {1: "bước 1 (cào/dịch)", 2: "bước 2 (lồng tiếng)", 3: "bước 3 (video)"}

# ---------------------------------------------------------------- phân loại

# Câu hỏi về DỮ LIỆU của app: phải nhắc tới thứ có trong DB VÀ có dạng hỏi
# số liệu/danh sách. Không bắt chữ "chương" đứng riêng vì câu hỏi đồ án
# ("chương 3 báo cáo nói gì") rất nhiều — chỉ nhận khi đi cùng "truyện",
# tên truyện, hoặc dạng đếm ("bao nhiêu chương").
_DATA_NOUN = re.compile(
    r"\b(truyen|video|am thanh|audio|file wav|file mp4|job|tac vu|csdl|co so du lieu|database|db|app\.db)\b"
)
_DATA_ASK = re.compile(
    r"\b(bao nhieu|may|nhung|nao|liet ke|danh sach|dem|thong ke|tong|tong so|nhieu nhat|it nhat|"
    r"moi nhat|gan day|gan nhat|cu nhat|trang thai|da xong|chua xong|chua co|da co|bi loi|loi|"
    r"that bai|huy|dang dich|da dich|cap nhat|con thieu|thieu|tien do|den dau)\b"
)
_HOWTO = re.compile(r"\b(lam sao|nhu the nao|the nao|la gi|vi sao|tai sao|cach)\b")
_COUNT_CHAPTERS = re.compile(r"\bbao nhieu (chuong|chap)\b")
_JOB = re.compile(r"\b(job|tac vu|lich su chay|lan chay)\b")
_THIS_STORY = re.compile(r"\btruyen (nay|hien tai|dang mo|dang chon)\b")
_FORCE_PREFIX = re.compile(r"^\s*/(db|sql)\b\s*", re.I)

# Từ quá phổ biến trong tên truyện, đứng một mình không đủ để nhận ra truyện.
_COMMON = {"nguoi", "truyen", "chuong", "the", "gioi", "cua", "trong", "va", "la", "cuoc", "song",
           "nam", "tro", "ve", "co", "mot", "nhung", "duoc", "khong", "em", "anh"}


def _norm(s: str) -> str:
    s = remove_vietnamese_diacritics(s or "").lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def strip_force_prefix(message: str) -> str:
    return _FORCE_PREFIX.sub("", message, count=1)


def _foreign_tokens(name: str) -> List[str]:
    """Từ trong tên KHÔNG mang dấu tiếng Việt (Hogwarts, Infinity, Honoha...).
    Từ có dấu như "Nhất", "chúa", "lòng" sau khi bỏ dấu trùng với chữ thường
    trong câu hỏi ("nhiều chương nhất", "chưa có") nên không dùng làm dấu hiệu."""
    out = []
    for w in re.findall(r"\w+", name or ""):
        n = _norm(w)
        if n == w.lower() and len(n) >= 5 and not n.isdigit():
            out.append(n)
    return out


def match_stories(question: str, stories: List[dict]) -> List[dict]:
    """Truyện được nhắc trong câu: khớp ≥2 từ liền nhau của tên (không phải toàn
    từ phổ biến), hoặc một từ ngoại lai chỉ có trong tên đúng một truyện ("hogwarts")."""
    q = f" {_norm(question)} "
    foreign = Counter(t for s in stories for t in set(_foreign_tokens(s["name"])))
    scored = []
    for s in stories:
        toks = _norm(s["name"]).split()
        best = 0
        for i in range(len(toks)):
            for j in range(len(toks), i, -1):
                if j - i <= best:
                    break
                gram = toks[i:j]
                if f" {' '.join(gram)} " in q and not all(t in _COMMON for t in gram):
                    best = j - i
                    break
        rare = any(foreign[t] == 1 and f" {t} " in q for t in _foreign_tokens(s["name"]))
        if best >= 2 or rare:
            scored.append((best + (1 if rare else 0), s))
    scored.sort(key=lambda x: -x[0])
    return [s for _, s in scored[:2]]


def classify(question: str, stories: List[dict], current_story: str = "") -> Optional[dict]:
    """None nếu không phải câu hỏi dữ liệu; ngược lại {"loai": [...], "truyen": [...]}."""
    forced = bool(_FORCE_PREFIX.match(question))
    q = strip_force_prefix(question)
    norm = _norm(q)
    named = match_stories(q, stories)
    explicit = bool(named)
    if not named and current_story and _THIS_STORY.search(norm):
        cur = _norm(current_story)
        named = [s for s in stories if _norm(s["name"]) == cur or s["slug"] == current_story][:1]

    if not forced:
        if _HOWTO.search(norm):
            return None
        is_data = (
            _COUNT_CHAPTERS.search(norm)
            or (_DATA_NOUN.search(norm) and _DATA_ASK.search(norm))
            or (named and (_DATA_ASK.search(norm) or re.search(r"\b(chuong|video|am thanh)\b", norm)))
        )
        if not is_data:
            return None

    loai = ["tong_quan"]
    if named:
        loai.append("truyen")
    if _JOB.search(norm):
        loai.append("job")
    return {"loai": loai, "truyen": named, "ro_ten": explicit}


def is_data_question(message: str) -> bool:
    """Phân loại nhanh không cần DB (không nhận ra tên truyện)."""
    return classify(message, []) is not None


# ---------------------------------------------------------------- lấy dữ liệu

def _connect_ro(db_path: str) -> sqlite3.Connection:
    uri = "file:" + db_path.replace("\\", "/") + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def _has(x) -> bool:
    return x not in (None, "")


def load_stories(db_path: str) -> List[dict]:
    conn = _connect_ro(db_path)
    try:
        rows = conn.execute(
            """SELECT s.slug, s.name, s.status, s.pipeline_step, s.created_at, s.updated_at,
                      COUNT(c.id) AS chuong,
                      SUM(CASE WHEN c.wav_path IS NOT NULL AND c.wav_path <> '' THEN 1 ELSE 0 END) AS am_thanh,
                      SUM(CASE WHEN c.mp4_path IS NOT NULL AND c.mp4_path <> '' THEN 1 ELSE 0 END) AS video
               FROM stories s LEFT JOIN chapters c ON c.story_slug = s.slug
               GROUP BY s.slug ORDER BY s.updated_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _day(ts: Optional[str]) -> str:
    return (ts or "")[:10] or "?"


def _ranges(nums: List[int]) -> str:
    """[1,2,3,5,7,8] -> '1–3, 5, 7–8' để model khỏi phải đọc dãy dài."""
    out, start, prev = [], None, None
    for n in sorted(nums):
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append(f"{start}–{prev}" if prev > start else f"{start}")
            start = prev = n
    if start is not None:
        out.append(f"{start}–{prev}" if prev > start else f"{start}")
    return ", ".join(out)


def _missing(what: str, chs: List[dict], key: str) -> str:
    """Câu trọn nghĩa — model 3B từng đọc "CHƯA có video (1): 2" thành "đủ cả".
    Ít chương thiếu thì ghi luôn tên chương cho khỏi đoán."""
    total = len(chs)
    miss = [c for c in chs if not _has(c[key])]
    if not total:
        return f"Truyện chưa có chương nào nên chưa có {what}."
    if not miss:
        return f"Tất cả {total} chương đều đã có {what}."
    if len(miss) == total:
        return f"Cả {total} chương đều CHƯA có {what}."
    head = f"{total - len(miss)}/{total} chương đã có {what}; còn {len(miss)} chương CHƯA có {what}"
    if len(miss) <= 5:
        return head + ": " + "; ".join(f"chương số {c['idx']} \"{(c['title'] or '')[:60]}\"" for c in miss) + "."
    return head + ", gồm chương số: " + _ranges([c["idx"] for c in miss]) + "."


def _status(s: str) -> str:
    return f"{s} ({STATUS_VI.get(s, s)})" if s else "?"


def block_overview(stories: List[dict], short: bool = False) -> str:
    n_ch = sum(s["chuong"] or 0 for s in stories)
    n_wav = sum(s["am_thanh"] or 0 for s in stories)
    n_mp4 = sum(s["video"] or 0 for s in stories)
    lines = [
        "## Tổng quan toàn bộ CSDL",
        f"- Tổng số truyện: {len(stories)}",
        f"- Tổng số chương: {n_ch}; chương đã có âm thanh: {n_wav}; chương đã có video: {n_mp4}",
    ]
    if short:
        # Câu hỏi nhắm một truyện: khối dài làm model 3B đọc lẫn sang truyện khác.
        return "\n".join(lines)
    by_status: Dict[str, List[str]] = OrderedDict()
    for s in sorted(stories, key=lambda x: x["status"] or ""):
        by_status.setdefault(s["status"] or "?", []).append(s["name"])
    lines.append("- Truyện theo trạng thái:")
    for st, names in by_status.items():
        lines.append(f"  - {_status(st)}: {len(names)} truyện — " + "; ".join(names))
    failed = [s["name"] for s in stories if (s["status"] or "").endswith("FAILED")]
    lines.append(f"- Truyện đang bị lỗi: {len(failed)}" + (" — " + "; ".join(failed) if failed else ""))
    by_step: Dict[int, List[str]] = {}
    for s in stories:
        by_step.setdefault(int(s["pipeline_step"] or 1), []).append(s["name"])
    lines.append("- Truyện theo bước đang ở:")
    for st in sorted(by_step):
        lines.append(f"  - {STEP_VI.get(st, f'bước {st}')}: {len(by_step[st])} truyện — " + "; ".join(by_step[st]))
    by_month: Dict[str, List[str]] = {}
    for s in stories:
        if s["created_at"]:
            by_month.setdefault(s["created_at"][:7], []).append(s["name"])
    lines.append("- Truyện tạo theo tháng (năm-tháng):")
    for m in sorted(by_month):
        lines.append(f"  - {m}: {len(by_month[m])} truyện — " + "; ".join(by_month[m]))
    if stories:
        newest = stories[0]
        oldest = min(stories, key=lambda x: x["created_at"] or "9999")
        lines.append(f"- Truyện cập nhật gần nhất: {newest['name']} ({_day(newest['updated_at'])})")
        lines.append(f"- Truyện tạo sớm nhất: {oldest['name']} ({_day(oldest['created_at'])})")
        most = max(stories, key=lambda x: x["chuong"] or 0)
        lines.append(f"- Truyện nhiều chương nhất: {most['name']} ({most['chuong']} chương)")
    lines.append("")
    lines.append("## Bảng các truyện (mới cập nhật trước)")
    lines.append("Tên | Trạng thái | Bước | Chương | Có âm thanh | Có video | Ngày tạo | Cập nhật")
    for s in stories:
        lines.append(
            f"{s['name']} | {_status(s['status'])} | {s['pipeline_step']} | {s['chuong'] or 0} | "
            f"{s['am_thanh'] or 0} | {s['video'] or 0} | {_day(s['created_at'])} | {_day(s['updated_at'])}"
        )
    return "\n".join(lines)


def block_story(db_path: str, story: dict, max_titles: int = 30) -> str:
    conn = _connect_ro(db_path)
    try:
        chs = [dict(r) for r in conn.execute(
            "SELECT idx, title, wav_path, mp4_path, status FROM chapters WHERE story_slug=? ORDER BY idx",
            (story["slug"],)).fetchall()]
    finally:
        conn.close()
    no_wav = [c["idx"] for c in chs if not _has(c["wav_path"])]
    no_mp4 = [c["idx"] for c in chs if not _has(c["mp4_path"])]
    lines = [
        f"## Truyện \"{story['name']}\"",
        f"- Trạng thái: {_status(story['status'])}; đang ở {STEP_VI.get(int(story['pipeline_step'] or 1))}",
        f"- Ngày tạo: {_day(story['created_at'])}; cập nhật: {_day(story['updated_at'])}",
        f"- Số chương: {len(chs)}; có âm thanh: {len(chs) - len(no_wav)}; có video: {len(chs) - len(no_mp4)}",
        "- " + _missing("âm thanh", chs, "wav_path"),
        "- " + _missing("video", chs, "mp4_path"),
    ]
    if chs:
        lines.append("- Danh sách chương (số | tên | âm thanh | video):")
        for c in chs[:max_titles]:
            title = (c["title"] or "")[:70]
            lines.append(f"  {c['idx']} | {title} | {'có' if _has(c['wav_path']) else 'chưa'} | "
                         f"{'có' if _has(c['mp4_path']) else 'chưa'}")
        if len(chs) > max_titles:
            lines.append(f"  … còn {len(chs) - max_titles} chương nữa")
    return "\n".join(lines)


def block_jobs(db_path: str, stories: List[dict], limit: int = 20) -> str:
    names = {s["slug"]: s["name"] for s in stories}
    conn = _connect_ro(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM jobs WHERE status LIKE '%FAIL%'").fetchone()[0]
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
    finally:
        conn.close()
    lines = ["## Job / tác vụ", f"- Tổng số job đã ghi: {total}; thất bại: {failed}"]
    if not total:
        lines.append("- Bảng jobs chưa có bản ghi nào (hệ thống chưa ghi lịch sử job vào CSDL).")
    for r in rows:
        lines.append(f"  - #{r['id']} {names.get(r['story_slug'], r['story_slug'])} | {r['step']} | "
                     f"{r['status']} | {_day(r['started_at'])} | {(r['message'] or '')[:80]}")
    return "\n".join(lines)


# Bộ lọc nhận từ câu hỏi: (mẫu trên câu không dấu, mô tả, hàm lọc truyện).
_STEP_FILTERS = [
    (r"\bbuoc (1|mot|cao|dich)\b", "đang ở bước 1 (cào/dịch)", lambda s: int(s["pipeline_step"] or 1) == 1),
    (r"\bbuoc (2|hai|long tieng|tts)\b", "đang ở bước 2 (lồng tiếng)", lambda s: int(s["pipeline_step"] or 1) == 2),
    (r"\bbuoc (3|ba|video|lam video)\b", "đang ở bước 3 (video)", lambda s: int(s["pipeline_step"] or 1) == 3),
]
_STATUS_FILTERS = [
    (r"\bloi video\b", "trạng thái lỗi video", lambda st: st == "VIDEO_FAILED"),
    (r"\bloi (long tieng|giong|am thanh)\b", "trạng thái lỗi lồng tiếng", lambda st: st == "VOICE_FAILED"),
    (r"\bloi dich\b", "trạng thái lỗi dịch", lambda st: st == "TRANSLATE_FAILED"),
    (r"\b(bi loi|loi|that bai|hong)\b", "trạng thái lỗi", lambda st: st.endswith("FAILED")),
    (r"\b(huy|da huy|bi huy)\b", "trạng thái đã huỷ", lambda st: st == "CANCELLED"),
    (r"\bdang dich\b", "trạng thái đang dịch", lambda st: st == "TRANSLATING"),
    (r"\bda dich\b", "trạng thái đã dịch", lambda st: st == "TRANSLATED"),
    (r"\b(da long tieng|da co giong)\b", "trạng thái đã lồng tiếng", lambda st: st == "VOICE_GENERATED"),
    (r"\b(da (lam|co|xong) video|xong video)\b", "trạng thái đã làm video", lambda st: st == "VIDEO_GENERATED"),
]


def find_filters(question: str) -> List[tuple]:
    """Bộ lọc truyện suy ra từ câu hỏi; mỗi nhóm (bước/trạng thái/tháng) lấy một."""
    norm = _norm(question)
    out = []
    for pat, label, fn in _STEP_FILTERS:
        if re.search(pat, norm):
            out.append((label, fn))
            break
    for pat, label, fn in _STATUS_FILTERS:
        if re.search(pat, norm):
            out.append((label, lambda s, fn=fn: fn(s["status"] or "")))
            break
    m = re.search(r"\bthang (\d{1,2})(?: (?:nam )?(\d{4}))?\b", norm)
    if m:
        year = m.group(2) or str(datetime.date.today().year)
        ym = f"{year}-{int(m.group(1)):02d}"
        out.append((f"tạo trong tháng {ym}", lambda s, ym=ym: (s["created_at"] or "").startswith(ym)))
    return out


def filter_stories(stories: List[dict], filters: List[tuple]) -> List[dict]:
    return [s for s in stories if all(fn(s) for _, fn in filters)]


def block_filtered(stories: List[dict], filters: List[tuple]) -> str:
    hit = filter_stories(stories, filters)
    cond = " và ".join(label for label, _ in filters)
    lines = [f"## KẾT QUẢ KHỚP CÂU HỎI — truyện {cond}: {len(hit)} truyện"]
    for s in hit:
        lines.append(f"- {s['name']} — {_status(s['status'])}, bước {s['pipeline_step']}, "
                     f"{s['chuong'] or 0} chương, tạo {_day(s['created_at'])}")
    if not hit:
        lines.append("- (không có truyện nào)")
    return "\n".join(lines)


def gather(db_path: str, question: str, current_story: str = "") -> Optional[dict]:
    """Phân loại câu hỏi rồi lấy dữ liệu cần. None nếu không phải câu hỏi dữ liệu."""
    stories = load_stories(db_path)
    kind = classify(question, stories, current_story)
    if kind is None:
        return None
    blocks = []
    for s in kind["truyen"]:
        blocks.append(block_story(db_path, s))
    if "job" in kind["loai"]:
        blocks.append(block_jobs(db_path, stories))
    filters = [] if (kind["truyen"] or "job" in kind["loai"]) else find_filters(question)
    hits: List[str] = []
    if filters:
        kind["loai"].append("loc")
        blocks.append(block_filtered(stories, filters))
        hits = [s["name"] for s in filter_stories(stories, filters)]
    blocks.append(block_overview(stories, short=bool(kind["truyen"] or filters)))
    return {
        "loai": kind["loai"],
        "truyen": [s["name"] for s in kind["truyen"]],
        "ro_ten": kind["ro_ten"],
        "hits": hits,
        "context": "\n\n".join(blocks),
    }


def build_answer_messages(question: str, data: dict, history: Optional[List[dict]] = None) -> List[dict]:
    system = (
        "Bạn là trợ lý của ứng dụng làm video từ truyện. Trả lời câu hỏi bằng tiếng Việt, ngắn gọn.\n"
        "Dữ liệu dưới đây do hệ thống đọc từ CSDL lúc này; các con số đã được tính sẵn — "
        "hãy dùng đúng số đó, KHÔNG tự đếm lại, KHÔNG bịa thêm truyện/chương/số liệu.\n"
        "Nếu dữ liệu không đủ để trả lời thì nói rõ là CSDL không có thông tin đó.\n"
        "Nếu có phần KẾT QUẢ KHỚP CÂU HỎI thì trả lời theo phần đó và liệt kê ĐỦ mọi mục trong đó.\n"
        "Danh sách dài (trên 10 mục) thì nêu số lượng và vài mục tiêu biểu.\n\n"
        f"{data['context']}"
    )
    msgs = [{"role": "system", "content": system}]
    for h in (history or [])[-4:]:
        msgs.append({"role": h["role"], "content": h["content"][:400]})
    msgs.append({"role": "user", "content": question})
    return msgs


def missing_hits(answer: str, data: dict, max_hits: int = 10) -> List[str]:
    """Truyện khớp bộ lọc mà câu trả lời bỏ sót (3B hay rơi mất một mục)."""
    hits = data.get("hits") or []
    if not hits or len(hits) > max_hits:
        return []
    a = _norm(answer)
    return [h for h in hits if _norm(h) not in a]


def completeness_note(answer: str, data: dict) -> str:
    miss = missing_hits(answer, data)
    if not miss:
        return ""
    return ("\n\n_Danh sách đầy đủ theo CSDL ("
            + str(len(data["hits"])) + "): " + "; ".join(data["hits"]) + "._")
