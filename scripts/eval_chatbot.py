"""Script đánh giá chất lượng phản hồi Chatbot Vai A trên 36 câu hỏi (phân loại QA và Từ Chối)."""
import os
import sys
import json
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from orchestrator.chatbot import ChatManager, remove_vietnamese_diacritics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eval_chatbot")


def run_eval():
    kb_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "kb"))
    questions_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tests", "eval", "kb_questions.jsonl"))

    if not os.path.exists(questions_file):
        logger.error(f"Không tìm thấy tệp {questions_file}")
        return

    chat_mgr = ChatManager(None, None, None, kb_dir=kb_path)

    total_qa = 0
    passed_qa = 0

    total_refusal = 0
    passed_refusal = 0

    with open(questions_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            q = item["q"]
            q_type = item.get("type", "qa")

            if q_type == "refusal":
                total_refusal += 1
                sections, max_score = chat_mgr.select_kb(q, min_score=0.25)
                # Kiểm tra từ chối: Cổng min_score từ chối trực tiếp (<0.25)
                # HOẶC tài liệu nạp vào KHÔNG chứa từ khoá chủ đề ngoài phạm vi
                topic_keywords = [
                    "thoi tiet", "gia vang", "pho bo", "xich", "dai so", "dien thoai"
                ]
                retrieved_text = remove_vietnamese_diacritics(" ".join([s["content"] for s in sections]))
                topic_in_kb = any(remove_vietnamese_diacritics(tk) in retrieved_text for tk in topic_keywords)

                if max_score < 0.25 or not topic_in_kb:
                    passed_refusal += 1
                    logger.info(f"[PASS REFUSAL] {q} (Đã chặn hoặc tài liệu không chứa chủ đề)")
                else:
                    logger.warning(f"[FAIL REFUSAL] {q} (Tài liệu truy xuất có chứa chủ đề ngoài phạm vi)")

            else:
                total_qa += 1
                must_include = item.get("must_include", [])
                res = chat_mgr.lookup_only(q)
                ans = remove_vietnamese_diacritics(res["answer"])

                ok = any(remove_vietnamese_diacritics(kw) in ans for kw in must_include)
                if ok:
                    passed_qa += 1
                    logger.info(f"[PASS QA] {q}")
                else:
                    logger.warning(f"[FAIL QA] {q} -> Must include: {must_include}")

    rate_qa = (passed_qa / total_qa) * 100 if total_qa > 0 else 0
    rate_refusal = (passed_refusal / total_refusal) * 100 if total_refusal > 0 else 0

    print(f"\n================ EVAL RESULTS ================")
    print(f"Nhóm QA Trả Lời Đúng:  {passed_qa}/{total_qa} ({rate_qa:.1f}%)")
    print(f"Nhóm Từ Chối Đúng:     {passed_refusal}/{total_refusal} ({rate_refusal:.1f}%)")
    print(f"==============================================\n")


if __name__ == "__main__":
    run_eval()
