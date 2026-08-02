"""Đo chất lượng phản hồi Chatbot trên bộ câu hỏi nghiệm thu.

Hai chế độ, đo hai thứ KHÁC NHAU — không được lẫn lộn:

  --mode retrieval  (mặc định)  Chỉ đo tầng truy xuất KB: cổng ngưỡng có chặn
                                đúng câu ngoài phạm vi không, và câu hợp lệ có
                                lấy được đoạn tài liệu chứa đáp án không.
                                Chạy được mọi lúc, KHÔNG cần Ollama.

  --mode llm                    Đo câu trả lời THẬT do model sinh ra. Cần Ollama
                                đang chạy và đã pull model. Đây mới là số đo
                                "chất lượng phản hồi"; chế độ retrieval không
                                thay thế được nó.

Chạy:
    AIVoice\\.venv\\Scripts\\python.exe scripts/eval_chatbot.py
    AIVoice\\.venv\\Scripts\\python.exe scripts/eval_chatbot.py --mode llm
"""
import os
import sys
import json
import asyncio
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from orchestrator.chatbot import ChatManager, remove_vietnamese_diacritics  # noqa: E402
from orchestrator.config import load_global_config  # noqa: E402
from orchestrator.llm import chat_stream_ollama  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KB_DIR = os.path.join(ROOT, "docs", "kb")
QUESTIONS = os.path.join(ROOT, "tests", "eval", "kb_questions.jsonl")

# Câu trả lời được coi là "từ chối" nếu chứa một trong các mẫu này.
REFUSAL_MARKERS = [
    "khong de cap", "khong co trong tai lieu", "khong tim thay",
    "tai lieu hien co khong", "ngoai pham vi",
]


def load_questions() -> list:
    if not os.path.exists(QUESTIONS):
        print(f"Không tìm thấy {QUESTIONS}")
        sys.exit(1)
    with open(QUESTIONS, "r", encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def _hit(answer: str, keywords: list) -> bool:
    norm = remove_vietnamese_diacritics(answer)
    return any(remove_vietnamese_diacritics(kw) in norm for kw in keywords)


def eval_retrieval(mgr: ChatManager, items: list, min_score: float) -> dict:
    """Đo tầng truy xuất. Vị từ từ chối CHỈ là cổng ngưỡng — không có mệnh đề nào khác.

    Bản trước dùng `max_score < min_score OR not topic_in_kb`, trong đó
    topic_in_kb dò các từ "phở bò", "giá vàng"... trong KB. KB là tài liệu về
    công cụ dựng video nên không bao giờ chứa chúng, khiến vế phải luôn đúng và
    mọi câu đều PASS bất kể cổng ngưỡng có hoạt động hay không.
    """
    res = {"qa_total": 0, "qa_pass": 0, "ref_total": 0, "ref_pass": 0, "fails": []}
    for it in items:
        q = it["q"]
        if it.get("type") == "refusal":
            res["ref_total"] += 1
            _, score = mgr.select_kb(q, min_score=min_score)
            if score < min_score:
                res["ref_pass"] += 1
            else:
                res["fails"].append(f"[REF lọt lưới] score={score:.3f}  {q}")
        else:
            res["qa_total"] += 1
            # Phải dùng ĐÚNG cổng ngưỡng của luồng chat thật. Nếu chấm QA bằng
            # ngưỡng dễ hơn (lookup_only dùng 0.20) thì một câu hợp lệ bị cổng
            # 0.50 chặn vẫn được tính là đạt — che mất cái giá của việc siết cổng.
            sections, score = mgr.select_kb(q, min_score=min_score)
            if score < min_score:
                res["fails"].append(f"[QA bị cổng chặn oan] score={score:.3f}  {q}")
                continue
            text = " ".join(s["content"] for s in sections)
            if _hit(text, it.get("must_include", [])):
                res["qa_pass"] += 1
            else:
                res["fails"].append(f"[QA trượt] {q} -> cần: {it.get('must_include')}")
    return res


async def _ask_llm(mgr: ChatManager, cfg: dict, question: str, min_score: float) -> str:
    """Chạy đúng luồng thật: cổng ngưỡng -> system prompt -> Ollama."""
    sections, score = mgr.select_kb(question, min_score=min_score)
    if score < min_score:
        return "Tài liệu hiện có không đề cập điều này."

    system_prompt = mgr.build_system_prompt(sections, "")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]
    parts = []
    async for chunk in chat_stream_ollama(
        base_url=cfg.get("base_url") or "http://localhost:11434",
        model=cfg.get("model", "qwen2.5:3b"),
        messages=messages,
        temperature=cfg.get("temperature", 0.4),
        num_ctx=cfg.get("num_ctx", 8192),
    ):
        if chunk.get("delta"):
            parts.append(chunk["delta"])
    return "".join(parts)


async def eval_llm(mgr: ChatManager, items: list, cfg: dict, min_score: float) -> dict:
    res = {"qa_total": 0, "qa_pass": 0, "ref_total": 0, "ref_pass": 0, "fails": []}
    for it in items:
        q = it["q"]
        try:
            answer = await _ask_llm(mgr, cfg, q, min_score)
        except Exception as e:
            print(f"\nKhông gọi được Ollama: {e}")
            print("Bật Ollama (`ollama serve`) và pull model trước khi chạy --mode llm.")
            sys.exit(2)

        if it.get("type") == "refusal":
            res["ref_total"] += 1
            if _hit(answer, REFUSAL_MARKERS):
                res["ref_pass"] += 1
            else:
                res["fails"].append(f"[REF bịa] {q} -> {answer[:110]}")
        else:
            res["qa_total"] += 1
            if _hit(answer, it.get("must_include", [])):
                res["qa_pass"] += 1
            else:
                res["fails"].append(f"[QA sai] {q} -> {answer[:110]}")
    return res


def report(mode: str, res: dict, min_score: float, show_fails: bool):
    qa_rate = res["qa_pass"] / res["qa_total"] * 100 if res["qa_total"] else 0.0
    ref_rate = res["ref_pass"] / res["ref_total"] * 100 if res["ref_total"] else 0.0
    label = ("TRUY XUẤT KB (không qua LLM)" if mode == "retrieval"
             else "CÂU TRẢ LỜI THẬT CỦA MODEL")

    print(f"\n=========== EVAL — {label} ===========")
    print(f"kb_min_score = {min_score}")
    print(f"Nhóm QA đúng:       {res['qa_pass']}/{res['qa_total']} ({qa_rate:.1f}%)   ngưỡng ≥80%")
    print(f"Nhóm từ chối đúng:  {res['ref_pass']}/{res['ref_total']} ({ref_rate:.1f}%)   ngưỡng ≥90%")
    if mode == "retrieval":
        print("Lưu ý: đây KHÔNG phải chất lượng phản hồi. Dùng --mode llm để đo điều đó.")
    print("=" * 52)

    if show_fails and res["fails"]:
        print("\nCác câu chưa đạt:")
        for line in res["fails"]:
            print("  " + line)
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["retrieval", "llm"], default="retrieval")
    ap.add_argument("--quiet", action="store_true", help="Không in danh sách câu trượt")
    ap.add_argument("--model", default="", help="Ghi đè model Ollama (vd qwen2.5:3b)")
    args = ap.parse_args()

    cfg = dict(load_global_config().get("chatbot", {}))
    if args.model:
        cfg["model"] = args.model
    min_score = cfg.get("kb_min_score", 0.65)
    mgr = ChatManager(None, None, None, kb_dir=KB_DIR)
    items = load_questions()

    if args.mode == "retrieval":
        res = eval_retrieval(mgr, items, min_score)
    else:
        res = asyncio.run(eval_llm(mgr, items, cfg, min_score))

    report(args.mode, res, min_score, not args.quiet)


if __name__ == "__main__":
    main()
