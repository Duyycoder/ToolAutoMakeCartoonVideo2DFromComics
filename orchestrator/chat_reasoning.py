"""Quy trình suy luận nhiều lượt cho trợ lý chạy model nhỏ (qwen2.5:3b).

Model 3B trả lời sai chủ yếu vì ba lý do, không phải vì "không biết nghĩ":
  1. Lấy sai tài liệu: câu hỏi diễn đạt khác tài liệu ("test tự động" ↔ "passed"),
     hoặc là câu nối tiếp ("thế còn cái kia?") không tự mang chủ đề.
  2. Bị nhồi quá nhiều đoạn không liên quan — model nhỏ chép lẫn lộn.
  3. Bịa chi tiết cụ thể (con số, tên tệp) nghe rất tự tin.

Nên thay vì bắt model "suy nghĩ dài" (tốn token, model 3B nghĩ dài cũng không
đúng hơn), mỗi lượt gọi được giao MỘT việc hẹp, đầu ra JSON ngắn mà code kiểm
được, còn phần cần chính xác tuyệt đối thì làm bằng code:

  B0 (code)  Tra nhanh bằng IDF trên câu gốc, đo độ chắc.
  B1 (LLM)   Hiểu câu hỏi: viết lại thành câu tự đủ nghĩa, phân loại, sinh từ
             khoá + từ đồng nghĩa. CHỈ chạy khi cần (câu nối tiếp, tra nhanh yếu).
  B2 (code)  Tra lại với mọi biến thể câu hỏi, gộp điểm lấy cao nhất.
  B3 (LLM)   Chọn đoạn: đọc đoạn trích ngắn của ~8 ứng viên, chọn ≤ 3 đoạn thật
             sự chứa câu trả lời, hoặc nói "không đoạn nào". Đây là chỗ lọc câu
             ngoài phạm vi theo NGHĨA mà khớp từ khoá không làm được.
  B4 (code)  Nối đoạn kế tiếp cùng mục để câu trả lời không bị cắt ngang.
  B5 (LLM)   Trả lời theo khuôn cố định (câu trả lời trước, giải thích sau, nguồn).
  B6 (code)  Soát con số / tên tệp trong câu trả lời có nằm trong tài liệu không,
             không có thì gắn cảnh báo — chặn đúng kiểu sai nguy hiểm nhất.

Lượt LLM nội bộ dùng `format=json`, temperature 0, num_predict nhỏ nên mỗi lượt
chỉ tốn khoảng một giây. Lỗi ở bất kỳ lượt nào đều rơi về đường cũ (truy xuất
IDF thuần) chứ không chặn câu trả lời.
"""
import json
import logging
import re
import time
from typing import AsyncGenerator, Awaitable, Callable, Dict, List, Optional

from orchestrator import kb_index
from orchestrator.chatbot import remove_vietnamese_diacritics

logger = logging.getLogger(__name__)

DATN = "datn"
GUIDE = kb_index.DEFAULT_COLLECTION

STAGES = {
    "phan_tich": "Đang hiểu câu hỏi…",
    "chon_tai_lieu": "Đang chọn đoạn tài liệu liên quan…",
    "tra_loi": "Đang soạn câu trả lời…",
}

# Ngưỡng điểm IDF (đã chuẩn hoá) — điểm vượt 1.0 nghĩa là khớp cả tiêu đề mục.
STRONG_SCORE = 1.2        # đủ chắc để bỏ qua lượt hiểu câu hỏi
KEEP_IF_REJECTED = 1.8    # model bảo "không đoạn nào" nhưng khớp tới mức này thì vẫn giữ đoạn đầu

LLMCall = Callable[..., Awaitable[str]]

_FOLLOWUP_MARKERS = (
    "no", "cai do", "cai nay", "cai kia", "vay", "the con", "con cai", "tiep",
    # Không có "như thế": "như thế nào" là cụm hỏi bình thường, không trỏ về lượt trước.
    "o tren", "nhu vay", "dieu do", "phan do", "y do",
)


def looks_followup(message: str, history: List[dict]) -> bool:
    """Câu nối tiếp: có lịch sử, và câu ngắn hoặc chứa đại từ trỏ về lượt trước."""
    if not any(m.get("role") == "user" for m in history):
        return False
    norm = " " + re.sub(r"[^\w\s]", " ", remove_vietnamese_diacritics(message)) + " "
    if len(norm.split()) <= 6:
        return True
    return any(f" {m} " in norm for m in _FOLLOWUP_MARKERS)


# ------------------------------------------------------------- B1 hiểu câu hỏi
def build_analyze_messages(question: str, history: List[dict]) -> List[dict]:
    turns = []
    for m in history[-4:]:
        who = "Người dùng" if m.get("role") == "user" else "Trợ lý"
        text = re.sub(r"\s+", " ", m.get("content", ""))[:300]
        turns.append(f"{who}: {text}")
    convo = "\n".join(turns) if turns else "(trống)"
    user = (
        f"Hội thoại trước:\n{convo}\n\n"
        f"Câu hỏi mới: «{question}»\n\n"
        "Trả về JSON đúng 4 khoá:\n"
        "- \"cau_hoi\": viết lại câu hỏi mới cho đầy đủ, tự hiểu được mà không cần đọc "
        "hội thoại (thay 'nó', 'cái đó' bằng tên cụ thể). Câu đã đủ nghĩa thì giữ nguyên.\n"
        "- \"loai\": một trong \"huong_dan\" (cách dùng phần mềm: bấm nút, cấu hình, lỗi "
        "khi chạy), \"do_an\" (lý thuyết, công nghệ, kiến trúc, lý do thiết kế, số liệu "
        "đánh giá, CSDL/SQL, code nằm ở đâu, câu hỏi bảo vệ đồ án, báo cáo), \"truyen\" "
        "(nội dung hay tiến độ truyện đang chọn), \"ngoai\" (không liên quan).\n"
        "- \"tu_khoa\": 4-8 từ khoá để tra tài liệu: thuật ngữ trong câu hỏi, từ đồng "
        "nghĩa tiếng Việt, tên tiếng Anh, tên hàm/tệp nếu có.\n"
        "- \"y_nho\": nếu câu hỏi hỏi 2-3 điều KHÁC NHAU (\"X là gì và vì sao chọn X\", "
        "\"so sánh A với B\", nhiều câu hỏi gộp làm một) thì tách thành 2-3 câu hỏi con, "
        "mỗi câu tự đủ nghĩa. Câu chỉ hỏi một điều thì để [].\n\n"
        "Ví dụ 1: {\"cau_hoi\": \"Vì sao dùng SSE thay cho WebSocket để đẩy log?\", "
        "\"loai\": \"do_an\", \"tu_khoa\": [\"SSE\", \"WebSocket\", \"EventSource\", "
        "\"log realtime\", \"một chiều\"], \"y_nho\": []}\n"
        "Ví dụ 2: {\"cau_hoi\": \"LoRA là gì và khác IP-Adapter thế nào?\", \"loai\": "
        "\"do_an\", \"tu_khoa\": [\"LoRA\", \"IP-Adapter\", \"hạng thấp\", \"ảnh tham chiếu\"], "
        "\"y_nho\": [\"LoRA là gì?\", \"LoRA khác IP-Adapter thế nào?\"]}"
    )
    return [
        {"role": "system", "content": (
            "Bạn phân tích câu hỏi gửi tới trợ lý của phần mềm tự động làm video hoạt "
            "hình 2D từ truyện chữ. Phần mềm này cũng là đồ án tốt nghiệp của người "
            "dùng. Chỉ trả về JSON."
        )},
        {"role": "user", "content": user},
    ]


_LOAI = {"huong_dan", "do_an", "truyen", "ngoai"}


def _load_json(text: str) -> Optional[dict]:
    text = (text or "").strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                data = json.loads(m.group(0))
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def parse_analysis(text: str, question: str) -> Optional[dict]:
    data = _load_json(text)
    if not data:
        return None
    cau_hoi = str(data.get("cau_hoi") or "").strip() or question
    loai = str(data.get("loai") or "").strip()
    kws = data.get("tu_khoa") or []
    if isinstance(kws, str):
        kws = re.split(r"[,;]", kws)
    kws = [str(k).strip() for k in kws if str(k).strip()][:10]
    subs = data.get("y_nho") or []
    if isinstance(subs, str):
        subs = [subs]
    subs = [str(q).strip()[:200] for q in subs if isinstance(q, (str, int)) and len(str(q).strip()) > 5][:3]
    return {
        "cau_hoi": cau_hoi[:300],
        "loai": loai if loai in _LOAI else "",
        "tu_khoa": kws,
        "y_nho": subs,
    }


# ------------------------------------------------------------- B0/B2 truy xuất
def retrieve(chat_mgr, variants: List[str], active_tab: str, cfg: dict,
             loai: str = "") -> List[dict]:
    """Ứng viên từ mọi bộ tri thức, điểm = cao nhất qua các biến thể câu hỏi.

    Mỗi biến thể chấm riêng rồi lấy max, KHÔNG gộp từ khoá vào một câu dài: gộp
    làm loãng tỷ lệ khớp (guard 40%) và câu gốc vốn khớp tốt lại bị đánh trượt.
    """
    guide_min = cfg.get("kb_min_score", 0.75)
    datn_min = cfg.get("datn_min_score", 0.6)
    # Số ứng viên mỗi bộ — nghiêng về bộ mà loại câu hỏi chỉ tới.
    quota = {GUIDE: 4, DATN: 6}
    if loai == "huong_dan":
        quota = {GUIDE: 6, DATN: 2}
    elif loai == "do_an":
        quota = {GUIDE: 2, DATN: 6}

    out: List[dict] = []
    for col in chat_mgr.collections():
        best: Dict[str, tuple] = {}
        for v in variants:
            if not v or not v.strip():
                continue
            scored, _mx = chat_mgr.score_sections(v, active_tab=active_tab, collection=col)
            for s, sec in scored[:20]:
                if s > best.get(sec["id"], (0, None))[0]:
                    best[sec["id"]] = (s, sec)
        floor = guide_min if col == GUIDE else datn_min
        ranked = sorted(best.values(), key=lambda x: -x[0])
        ranked = [x for x in ranked if x[0] >= floor][: quota.get(col, 3)]
        out.extend({"score": s, "sec": sec} for s, sec in ranked)
    out.sort(key=lambda c: -c["score"])
    return out


# ---------------------------------------------------------------- B3 chọn đoạn
def _snippet(sec: dict, limit: int = 300) -> str:
    body = sec["content"]
    if body.startswith("[") and "]\n" in body:
        body = body.split("]\n", 1)[1]
    body = re.sub(r"\s+", " ", body).strip()
    return body[:limit] + ("…" if len(body) > limit else "")


def build_rerank_messages(question: str, cands: List[dict]) -> List[dict]:
    lines = []
    for i, c in enumerate(cands, 1):
        sec = c["sec"]
        lines.append(f"[{i}] (mục: {sec.get('path') or sec.get('header')})\n{_snippet(sec)}")
    user = (
        f"Câu hỏi: «{question}»\n\n"
        "Các đoạn tài liệu:\n" + "\n\n".join(lines) + "\n\n"
        "Chọn tối đa 3 đoạn CHỨA thông tin để trả lời câu hỏi, đoạn sát nhất đứng trước. "
        "Đoạn chỉ trùng chữ mà nói chuyện khác thì KHÔNG chọn. Không đoạn nào phù hợp "
        "thì trả mảng rỗng.\n"
        "Trả về JSON: {\"chon\": [số, ...]}"
    )
    return [
        {"role": "system", "content": "Bạn chọn đoạn tài liệu giúp trả lời câu hỏi. Chỉ trả về JSON."},
        {"role": "user", "content": user},
    ]


def parse_rerank(text: str, n: int) -> Optional[List[int]]:
    """Chỉ số 0-based đã chọn; [] = model bảo không đoạn nào; None = đọc không được."""
    data = _load_json(text)
    raw = None
    if data is not None:
        raw = data.get("chon")
        if raw is None:
            vals = [v for v in data.values() if isinstance(v, list)]
            # JSON hợp lệ mà không có danh sách nào ({} hay {"chon": "không"}) cũng
            # là câu trả lời "không đoạn nào", không phải lỗi đọc.
            raw = vals[0] if vals else []
    if raw is None:
        nums = re.findall(r"\d+", text or "")
        if not nums:
            return None
        raw = nums
    picked = []
    for v in raw if isinstance(raw, list) else [raw]:
        try:
            k = int(v) - 1
        except (TypeError, ValueError):
            continue
        if 0 <= k < n and k not in picked:
            picked.append(k)
    return picked[:3]


# ------------------------------------------------------------ B4 nối mạch đoạn
def expand_neighbors(chat_mgr, picked: List[dict], budget_chars: int = 4200) -> List[dict]:
    """Thêm mảnh kế tiếp cùng mục (tài liệu đồ án) khi còn ngân sách.

    Mảnh 800 ký tự cắt theo ranh giới dòng, nên đoạn trả lời dài hay bị chẻ đôi:
    mảnh được chọn chứa câu hỏi, câu trả lời nằm nửa sau ở mảnh kế.
    """
    out, seen = [], set()
    total = sum(len(s["content"]) for s in picked)
    for sec in picked:
        if sec["id"] in seen:
            continue
        out.append(sec)
        seen.add(sec["id"])
        if sec.get("collection") == GUIDE:
            continue
        nxt = chat_mgr._by_seq.get((sec.get("seq") or 0) + 1)
        if nxt and nxt["file"] == sec["file"] and nxt["path"] == sec["path"] \
                and nxt["id"] not in seen and total + len(nxt["content"]) <= budget_chars:
            out.append(nxt)
            seen.add(nxt["id"])
            total += len(nxt["content"])
    return out


# --------------------------------------------------------- B5 prompt trả lời
def build_study_prompt(sections: List[dict], story_context: str = "") -> str:
    """Prompt cho câu hỏi về đồ án: ngắn, ít luật, có khuôn trả lời cố định.

    Model 3B làm theo khuôn tốt hơn hẳn làm theo danh sách luật dài. Khuôn "trả
    lời trước – giải thích sau – nguồn" cũng đúng cách nói trước hội đồng.
    """
    docs = "\n\n".join(f"--- {s.get('path') or s['file']} ---\n{_body(s)}" for s in sections)
    prompt = (
        "Bạn là trợ giảng giúp sinh viên ôn bảo vệ đồ án tốt nghiệp \"Nền tảng đa tiến "
        "trình tự động sản xuất video hoạt hình 2D từ truyện chữ bằng các mô hình AI "
        "local\". Trả lời dựa vào TÀI LIỆU giữa hai thẻ <tailieu>.\n\n"
        "CÁCH TRẢ LỜI (không chép các chữ hướng dẫn này vào câu trả lời):\n"
        "- Mở đầu bằng 1-2 câu trả lời thẳng vào câu hỏi.\n"
        "- Tiếp theo 2-5 gạch đầu dòng giải thích. Giữ NGUYÊN con số, tên tệp, tên hàm như "
        "trong tài liệu, không tự thêm số.\n"
        "- Tài liệu không đủ thì nói rõ thiếu gì. Muốn bổ sung kiến thức chung thì mở đầu "
        "đoạn đó bằng đúng dòng '⚠️ Ngoài tài liệu — đây là suy luận:'.\n"
        "- Kết thúc bằng 'Nguồn: ' và tên mục tài liệu đã dùng.\n"
        "Viết tiếng Việt, ngắn gọn như đang trả lời hội đồng.\n\n"
        "VÍ DỤ:\n"
        "Hỏi: Vì sao dùng SSE mà không dùng WebSocket?\n"
        "Đáp: Vì log chỉ cần đi một chiều từ server xuống trình duyệt, SSE đủ và đơn giản hơn.\n"
        "- SSE là response HTTP không đóng, trình duyệt có EventSource tự kết nối lại.\n"
        "- WebSocket hai chiều, phức tạp hơn mức cần; lệnh dừng đã có REST riêng.\n"
        "Nguồn: Chương 02 › Câu hỏi hội đồng\n\n"
        f"<tailieu>\n{docs}\n</tailieu>\n"
    )
    if story_context:
        prompt += f"\n<ngucanhtruyen>\n{story_context}\n</ngucanhtruyen>\n"
    return prompt


def _body(sec: dict) -> str:
    body = sec["content"]
    if body.startswith("[") and "]\n" in body:
        body = body.split("]\n", 1)[1]
    return body.strip()


# ------------------------------------------------------- B6 soát chi tiết cụ thể
_NUM = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)+%?|(?<![\w.,])\d{3,}(?![\w])|\b\d+(?:[.,]\d+)?\s?(?:GB|MB|%|ms|giây|phút)\b")
_FILE = re.compile(r"\b[\w./-]+\.(?:py|js|json|md|toml|bat|db|css|html|yml|safetensors)\b")
_CODE = re.compile(r"`([^`\n]{2,60})`")


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s.lower()).replace(",", ".")


def grounding_issues(answer: str, context: str, limit: int = 4) -> List[str]:
    """Con số, tên tệp, mã trong câu trả lời mà KHÔNG có trong tài liệu đã đưa.

    Đây là kiểu sai nguy hiểm nhất của model nhỏ: bịa một con số cụ thể nghe rất
    hợp lý. Soát bằng code, không tin model tự kiểm.
    """
    ctx = _norm(context)
    found: List[str] = []
    cands = [m.group(0) for m in _NUM.finditer(answer)]
    cands += [m.group(0) for m in _FILE.finditer(answer)]
    cands += [m.group(1) for m in _CODE.finditer(answer)]
    for c in cands:
        key = _norm(c).rstrip("%")
        if not key or key in ctx or c in found:
            continue
        found.append(c.strip())
        if len(found) >= limit:
            break
    return found


# ------------------------------------------------- câu nhiều ý: trả lời từng ý
_MULTI_HINT = re.compile(
    r"\b(va|voi|so sanh|khac nhau|khac gi|giong|dong thoi|ngoai ra|con|roi|sau do)\b"
)


def worth_splitting(question: str, parts: List[str]) -> bool:
    """Chỉ tách khi câu thật sự nhiều ý — model 3B đôi khi tách cả câu một ý,
    mà mỗi ý thêm là thêm 2 lượt gọi (~5 giây)."""
    if len(parts) < 2:
        return False
    norm = remove_vietnamese_diacritics(question)
    signals = question.count("?") >= 2 or len(norm.split()) >= 14 or bool(_MULTI_HINT.search(norm))
    distinct = len({remove_vietnamese_diacritics(p).strip() for p in parts}) == len(parts)
    return signals and distinct


def build_part_prompt(sections: List[dict]) -> str:
    docs = "\n\n".join(f"--- {s.get('path') or s['file']} ---\n{_body(s)}" for s in sections)
    return (
        "Trả lời NGẮN (2-4 câu) câu hỏi của người dùng, CHỈ dựa vào tài liệu giữa hai thẻ "
        "<tailieu>. Giữ nguyên con số, tên tệp, tên hàm như trong tài liệu. Tài liệu không "
        "nói tới thì trả lời đúng một câu: 'Tài liệu không đề cập.'\n\n"
        f"<tailieu>\n{docs or '(không có)'}\n</tailieu>\n"
    )


def build_synthesis_prompt(parts: List[dict], story_context: str = "") -> str:
    """Lượt tổng hợp: chỉ được dùng các câu trả lời từng ý — không đọc lại tài liệu,
    nên prompt ngắn và model không có chỗ để lạc sang chi tiết khác."""
    blocks = []
    for i, p in enumerate(parts, 1):
        src = ", ".join(dict.fromkeys(s.get("path") or s["file"] for s in p["sections"])) or "không có"
        blocks.append(f"Ý {i}: {p['question']}\nTrả lời: {p.get('answer', '').strip()}\nNguồn: {src}")
    prompt = (
        "Bạn là trợ giảng giúp sinh viên ôn bảo vệ đồ án tốt nghiệp. Câu hỏi của người "
        "dùng gồm nhiều ý; từng ý đã được trả lời riêng từ tài liệu (giữa hai thẻ <cacy>).\n\n"
        "Viết câu trả lời cuối:\n"
        "1. Dòng đầu: trả lời tổng quát cả câu hỏi trong 1-2 câu.\n"
        "2. Mỗi ý một đoạn ngắn, mở đầu bằng tên ý in đậm. Chỉ dùng thông tin trong <cacy>, "
        "giữ nguyên con số và tên tệp, KHÔNG thêm chi tiết mới.\n"
        "3. Ý nào 'Tài liệu không đề cập' thì nói rõ như vậy.\n"
        "4. Dòng cuối: 'Nguồn: ' + các mục đã dùng.\n\n"
        "<cacy>\n" + "\n\n".join(blocks) + "\n</cacy>\n"
    )
    if story_context:
        prompt += f"\n<ngucanhtruyen>\n{story_context}\n</ngucanhtruyen>\n"
    return prompt


async def answer_parts(*, llm: LLMCall, parts: List[dict], cfg: dict) -> AsyncGenerator[dict, None]:
    """Trả lời từng ý (không stream ra màn hình), phát tiến độ từng ý."""
    n = len(parts)
    for i, p in enumerate(parts, 1):
        yield {"stage": "y_con", "text": f"Đang trả lời ý {i}/{n}: {p['question'][:80]}"}
        t0 = time.perf_counter()
        try:
            p["answer"] = (await llm(
                [{"role": "system", "content": build_part_prompt(p["sections"])},
                 {"role": "user", "content": p["question"]}],
                num_predict=cfg.get("part_num_predict", 280), temperature=0.2,
            )).strip()
        except Exception as e:
            logger.warning(f"[Chatbot] Trả lời ý {i} lỗi: {e}")
            p["answer"] = "Tài liệu không đề cập."
        p["ms"] = int((time.perf_counter() - t0) * 1000)
    yield {"parts_done": parts}


# ---------------------------------------------------------------- điều phối
async def plan_answer(*, chat_mgr, llm: LLMCall, question: str, history: List[dict],
                      active_tab: str, cfg: dict) -> AsyncGenerator[dict, None]:
    """Chạy B0–B4. Phát {"stage": ...} trước mỗi lượt LLM, cuối cùng phát
    {"plan": {...}}: các mảnh đã chọn, câu hỏi đã hiểu, các ý con (nếu tách) và
    nhật ký thời gian từng bước."""
    mode = cfg.get("reasoning", "auto")  # auto | deep | fast
    steps: List[dict] = []
    state = {"analysis": None, "analysed": False, "variants": [question]}

    def log(name: str, t0: float, **extra):
        steps.append({"buoc": name, "ms": int((time.perf_counter() - t0) * 1000), **extra})

    async def analyse():
        state["analysed"] = True
        t0 = time.perf_counter()
        try:
            raw = await llm(build_analyze_messages(question, history),
                            num_predict=260, temperature=0.0, fmt="json")
            state["analysis"] = parse_analysis(raw, question)
        except Exception as e:  # lượt phụ hỏng không được chặn câu trả lời
            logger.warning(f"[Chatbot] Lượt hiểu câu hỏi lỗi: {e}")
        a = state["analysis"]
        log("hieu_cau_hoi", t0, ket_qua=a)
        if a:
            state["variants"] = [question, a["cau_hoi"], " ".join(a["tu_khoa"])]

    t = time.perf_counter()
    cands = retrieve(chat_mgr, [question], active_tab, cfg)
    best = cands[0]["score"] if cands else 0.0
    log("tra_nhanh", t, ung_vien=len(cands), diem=round(best, 2))

    # "auto" chỉ bỏ lượt hiểu câu hỏi khi câu hỏi về CÁCH DÙNG khớp rất rõ tài liệu
    # hướng dẫn — bộ đó nhỏ, từ vựng sát giao diện, IDF đã đủ. Câu về đồ án thì
    # luôn hiểu lại: người hỏi diễn đạt khác tài liệu ("test tự động" ↔ "passed",
    # "tốn tối đa" ↔ "đỉnh") và chỉ từ đồng nghĩa do model sinh mới bắc cầu được.
    followup = looks_followup(question, history)
    guide_sure = bool(cands) and cands[0]["sec"].get("collection") == GUIDE and best >= STRONG_SCORE
    if mode == "deep" or (mode == "auto" and (followup or not guide_sure)):
        yield {"stage": "phan_tich", "text": STAGES["phan_tich"]}
        await analyse()
    if followup and not state["analysis"]:
        # Model không trả được: dùng mẹo cũ — ghép với câu hỏi trước.
        state["variants"] += chat_mgr.followup_queries(question, history)

    analysis = state["analysis"] or {}
    loai = analysis.get("loai", "")
    if len(state["variants"]) > 1:
        t = time.perf_counter()
        cands = retrieve(chat_mgr, state["variants"], active_tab, cfg, loai=loai)
        log("tra_lai", t, ung_vien=len(cands), diem=round(cands[0]["score"], 2) if cands else 0)

    def guide_gate(texts: List[str]) -> List[dict]:
        """Đoạn HƯỚNG DẪN qua cổng IDF (ngưỡng chỉnh trên bộ đo 36 câu, chặn đúng 7/8
        câu ngoài phạm vi) thì luôn giữ — lượt chọn của model 3B từ chối oan đúng loại
        câu này ("badge màu gì", "TTL bao nhiêu phút"). Chỉ chấm trên câu hỏi TỰ
        NHIÊN: ngưỡng được chỉnh cho câu hỏi, chuỗi từ khoá mở rộng sẽ lọt cổng."""
        keep: List[dict] = []
        for txt in texts:
            secs, _ = chat_mgr.select_kb(txt, active_tab=active_tab,
                                         min_score=cfg.get("kb_min_score", 0.75))
            for s in secs[:2]:
                if s not in keep:
                    keep.append(s)
        return keep[:2]

    async def choose(q: str, cands: List[dict], loai: str, gate_texts: List[str]):
        """Chọn mảnh cho một câu hỏi. Phát stage trước lượt LLM; trả về qua state.

        Không loại câu theo nhãn "ngoai" của lượt hiểu câu hỏi: đo được nhãn đó sai
        với câu hợp lệ ("Khóa ngoại của bảng chapters…" bị xếp "ngoài" vì chữ
        "ngoại"). Lượt chọn đoạn, đọc nội dung thật, là trọng tài tin cậy hơn."""
        guide_keep = guide_gate(gate_texts)
        picked: List[dict] = []
        rejected = False
        top = cands[: cfg.get("rerank_candidates", 8)]
        if top and (mode == "fast" or len(top) == 1):
            picked = [c["sec"] for c in top[:3]]
        elif top:
            yield {"stage": "chon_tai_lieu", "text": STAGES["chon_tai_lieu"]}
            t0 = time.perf_counter()
            idx = None
            try:
                raw = await llm(build_rerank_messages(q, top),
                                num_predict=40, temperature=0.0, fmt="json")
                idx = parse_rerank(raw, len(top))
            except Exception as e:
                logger.warning(f"[Chatbot] Lượt chọn đoạn lỗi: {e}")
            log("chon_doan", t0, chon=[k + 1 for k in (idx or [])])
            if idx is None:
                picked = [c["sec"] for c in top[:3]]
            elif not idx:
                rejected = True
            else:
                picked = [top[k]["sec"] for k in idx]
                # Lưới an toàn: đoạn điểm IDF cao nhất đúng ở ~85% câu (đo trên bộ
                # đồ án), model 3B đôi khi bỏ sót nó — luôn kèm theo.
                if top[0]["sec"] not in picked:
                    picked.append(top[0]["sec"])
        state["choice"] = (picked, rejected, top, guide_keep)

    async def resolve_rejection(top: List[dict]):
        """Model bảo "không đoạn nào". Đo được: đúng với mọi câu ngoài phạm vi, nhưng
        cũng từ chối oan ~10% câu hợp lệ, nhất là câu hỏi con số mà đoạn trích ngắn
        chưa lộ ra số. Hỏi ý kiến thứ hai từ lượt hiểu câu hỏi: câu thuộc đồ án/hướng
        dẫn và khớp từ khoá rõ thì vẫn đưa 2 đoạn đầu — prompt trả lời tự nói "tài liệu
        không đề cập" nếu đoạn không dùng được, còn bỏ trắng thì model chỉ còn đoán."""
        if not state["analysed"]:
            yield {"stage": "phan_tich", "text": STAGES["phan_tich"]}
            await analyse()
        lo = (state["analysis"] or {}).get("loai", "")
        state["rescued"] = [c["sec"] for c in top[:2]] if lo in ("do_an", "huong_dan") \
            and top and top[0]["score"] >= STRONG_SCORE else []

    async def pick_for(q: str, cands: List[dict], loai: str, gate_texts: List[str]):
        async for ev in choose(q, cands, loai, gate_texts):
            yield ev
        picked, rejected, top, guide_keep = state["choice"]
        if rejected:
            async for ev in resolve_rejection(top):
                yield ev
            picked = state["rescued"]
        for sec in guide_keep:
            if sec not in picked:
                picked.append(sec)
        state["picked"] = picked

    # Câu nhiều ý: mỗi ý tra và chọn tài liệu riêng — một lần tra cho cả câu dài
    # thường chỉ trúng ý có từ khoá nổi nhất, các ý còn lại không có tài liệu.
    sub_qs = analysis.get("y_nho") or []
    parts: List[dict] = []
    if mode != "fast" and worth_splitting(question, sub_qs):
        for i, sq in enumerate(sub_qs[: cfg.get("max_parts", 3)], 1):
            t = time.perf_counter()
            c_i = retrieve(chat_mgr, [sq, f"{sq} {' '.join(analysis.get('tu_khoa', []))}"],
                           active_tab, cfg, loai=loai)
            log(f"tra_y_{i}", t, ung_vien=len(c_i))
            async for ev in pick_for(sq, c_i, loai, [sq]):
                yield ev
            parts.append({"question": sq, "sections": expand_neighbors(
                chat_mgr, state["picked"], cfg.get("part_context_chars", 2600))})
        sections = []
        for p in parts:
            for s in p["sections"]:
                if s not in sections:
                    sections.append(s)
    else:
        gate = [question] + ([analysis["cau_hoi"]] if analysis.get("cau_hoi") else [])
        async for ev in pick_for(analysis.get("cau_hoi") or question, cands, loai, gate):
            yield ev
        sections = expand_neighbors(chat_mgr, state["picked"], cfg.get("context_chars", 4200))

    kind = DATN if any(s.get("collection") == DATN for s in sections) else (GUIDE if sections else "")
    yield {"plan": {
        "sections": sections,
        "parts": parts,
        "kind": kind,
        "question": analysis.get("cau_hoi") or question,
        "analysis": state["analysis"],
        "steps": steps,
    }}


