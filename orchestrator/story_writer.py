"""Sinh truyện bằng LLM cục bộ (A1 — nguồn "Sáng tác bằng AI").

Gọi một endpoint tương thích chuẩn OpenAI (Gemini-local :7860 hoặc Ollama :11434)
để viết truyện tiếng Việt từ một chủ đề, xuất ra các tệp
"Chương NNNN - [VI] Tiêu đề.md" — đúng quy tắc đặt tên mà bước TTS và ghép video
phía sau dùng để nhận diện chương (chúng lọc theo " - [VI] ").

Đây là nội dung TỰ SINH nên hoàn toàn "sạch bản quyền" — không cào, không dùng
tác phẩm của người khác. Chạy cục bộ, không phụ thuộc dịch vụ trả phí.
"""
import os
from typing import Callable, Optional

from orchestrator.chapter_naming import chapter_filename as _chapter_filename
from orchestrator.chapter_naming import title_from_text as _title_from


def _chat(base_url: str, model: str, api_key: str, messages: list,
          temperature: float = 0.85, timeout: float = 300.0) -> str:
    from .llm import chat
    return chat(base_url, model, api_key, messages, temperature=temperature, timeout=timeout)


def generate_story(
    base_url: str,
    model: str,
    api_key: str,
    topic: str,
    num_chapters: int,
    out_dir: str,
    genre: str = "",
    words_per_chapter: int = 800,
    progress: Optional[Callable[[str], None]] = None,
) -> int:
    """Sinh `num_chapters` chương từ `topic`, ghi ra out_dir. Trả về số chương đã ghi."""
    os.makedirs(out_dir, exist_ok=True)

    def log(msg: str):
        if progress:
            progress(msg)

    genre_txt = f" thể loại {genre}" if genre else ""
    system = (
        f"Bạn là một nhà văn Việt Nam giàu trí tưởng tượng, chuyên viết truyện dài kỳ{genre_txt}. "
        "Hãy viết văn xuôi tiếng Việt tự nhiên, mạch lạc, giàu hình ảnh, có hội thoại và diễn biến hấp dẫn. "
        "Mỗi chương bắt đầu bằng một dòng tiêu đề ngắn gọn, sau đó là nội dung. "
        "Chỉ trả về nội dung chương, không thêm lời dẫn hay ghi chú ngoài truyện."
    )
    summary = ""  # tóm tắt diễn biến để giữ mạch truyện giữa các chương
    written = 0

    for i in range(1, num_chapters + 1):
        log(f"[Sáng tác] Đang viết chương {i}/{num_chapters}...")
        if i == 1:
            user = (
                f"Hãy viết CHƯƠNG 1 cho một truyện dài với ý tưởng sau:\n\n{topic}\n\n"
                f"Độ dài khoảng {words_per_chapter} từ. Giới thiệu bối cảnh và nhân vật chính một cách cuốn hút."
            )
        else:
            user = (
                f"Ý tưởng truyện:\n{topic}\n\n"
                f"Tóm tắt các chương trước:\n{summary}\n\n"
                f"Hãy viết tiếp CHƯƠNG {i}, độ dài khoảng {words_per_chapter} từ, "
                f"nối tiếp mạch truyện một cách tự nhiên và có cao trào."
            )
        content = _chat(base_url, model, api_key,
                        [{"role": "system", "content": system},
                         {"role": "user", "content": user}])
        if not content:
            raise RuntimeError(f"LLM trả về rỗng ở chương {i}")

        title = _title_from(content, i)
        out_path = os.path.join(out_dir, _chapter_filename(i, title))
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        written += 1
        log(f"[Sáng tác] Xong chương {i}/{num_chapters}: {title}")

        # Cập nhật tóm tắt (dùng chính LLM tóm tắt ngắn để giữ mạch, có fallback)
        try:
            s = _chat(base_url, model, api_key,
                      [{"role": "user", "content":
                        f"Tóm tắt chương sau trong 2-3 câu tiếng Việt, chỉ nêu diễn biến chính:\n\n{content[:4000]}"}],
                      temperature=0.3, timeout=120.0)
            summary = (summary + f"\n- Chương {i}: {s}").strip()[-2500:]
        except Exception:
            summary = (summary + f"\n- Chương {i}: {content[:200]}").strip()[-2500:]

    log(f"[Sáng tác] Hoàn tất {written} chương.")
    return written
