"""Sinh tài liệu KB từ CHÍNH mã nguồn dự án, không viết tay.

Lý do tồn tại: KB viết tay lệch khỏi thực tế rất nhanh. Bản KB đầu tiên của dự án
này từng mô tả một chế độ render "Image-Only" không hề tồn tại, và đánh số bước
theo tên hàm trong code thay vì theo nhãn hiển thị trên giao diện. Trợ lý đọc phải
tài liệu sai thì trả lời sai một cách tự tin — tệ hơn là không trả lời.

Script này rút thẳng từ nguồn sự thật:
  - webui/index.html   -> nhãn các bước, mọi <select> và lựa chọn hợp lệ
  - orchestrator/config.py -> giá trị mặc định của cấu hình

Chạy lại mỗi khi đổi giao diện hoặc cấu hình:
    AIVoice\\.venv\\Scripts\\python.exe scripts/gen_kb_from_project.py
"""
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INDEX = os.path.join(ROOT, "webui", "index.html")
CONFIG = os.path.join(ROOT, "orchestrator", "config.py")
OUT = os.path.join(ROOT, "docs", "kb", "08-tham-so-thuc-te.md")

# tab id trong code -> nhãn người dùng thấy. Hai cái này KHÔNG trùng nhau:
# nút "Bước 4: Ghép Video" có data-tab="step5", còn data-tab="step4" là công cụ
# phụ đề không đánh số. Bảng dưới được kiểm chứng lại từ index.html khi chạy.
PANEL_ORDER = ["step1", "step2", "step3", "step5", "step4", "settings"]


def read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def strip_tags(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()


def nav_labels(html: str) -> dict:
    """data-tab -> nhãn hiển thị trên thanh điều hướng."""
    out = {}
    for tab, body in re.findall(
        r'<button class="nav-item[^"]*" data-tab="([^"]+)">(.*?)</button>', html, re.S
    ):
        m = re.search(r'<span class="nav-title">(.*?)</span>', body, re.S)
        if m:
            out[tab] = strip_tags(m.group(1))
    return out


def panels(html: str) -> dict:
    """tab id -> HTML của panel tương ứng."""
    out = {}
    for tab, body in re.findall(
        r'<section class="tab-panel[^"]*" id="tab-([^"]+)">(.*?)</section>', html, re.S
    ):
        out[tab] = body
    return out


def labels_for(html: str) -> dict:
    """id của input/select -> nhãn <label for=...> đi kèm."""
    out = {}
    for target, text in re.findall(r'<label for="([^"]+)"[^>]*>(.*?)</label>', html, re.S):
        out[target] = strip_tags(text)
    return out


def checkboxes_in(body: str) -> list:
    """Các ô tích trong một panel, kèm nhãn hiển thị.

    Bản đầu chỉ quét <select> nên toàn bộ ô tích vắng mặt khỏi KB — hỏi "có nên
    bật Lọc tách giọng nền (Demucs) không?" thì trợ lý trả lời "tài liệu không đề
    cập", dù đó là một ô có thật ngay trên màn hình.
    """
    rows = []
    for label_html in re.findall(r"<label[^>]*>(.*?)</label>", body, re.S):
        m = re.search(r'<input[^>]*type="checkbox"[^>]*id="([^"]+)"', label_html)
        if not m:
            continue
        text = strip_tags(label_html)
        if text:
            rows.append((m.group(1), text))
    return rows


def inputs_in(body: str, label_map: dict) -> list:
    """Các ô nhập chữ/số, kèm nhãn và gợi ý (placeholder).

    Bản trước chỉ quét <select> và ô tích, nên mọi ô NHẬP đều vắng khỏi tài liệu.
    Hậu quả thật: hỏi "đổi đường dẫn lưu video tải về ở bước tạo phụ đề thế nào?"
    thì trợ lý nói "tài liệu không đề cập", dù ô "Thư mục đầu ra" nằm ngay đó.

    Placeholder thường mang thông tin quý nhất ("Bỏ trống = mặc định ..."), nên
    phải lấy cả nó chứ không chỉ nhãn.
    """
    rows = []
    pattern = r'<input[^>]*id="([^"]+)"[^>]*>'
    for tag in re.findall(r"<input[^>]*>", body):
        m_type = re.search(r'type="([^"]+)"', tag)
        kind = (m_type.group(1) if m_type else "text").lower()
        if kind not in ("text", "number", "password"):
            continue
        m_id = re.search(r'id="([^"]+)"', tag)
        if not m_id:
            continue
        sid = m_id.group(1)
        label = label_map.get(sid, "")
        if not label:
            continue
        m_ph = re.search(r'placeholder="([^"]*)"', tag)
        rows.append((sid, label, strip_tags(m_ph.group(1)) if m_ph else "", kind))
    del pattern
    return rows


def selects_in(body: str, label_map: dict) -> list:
    rows = []
    for sid, inner in re.findall(r'<select[^>]*id="([^"]+)"[^>]*>(.*?)</select>', body, re.S):
        opts = []
        for val, text in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>(.*?)</option>', inner, re.S):
            if val == "":
                continue
            opts.append((val, strip_tags(text)))
        if opts:
            rows.append((sid, label_map.get(sid, ""), opts))
    return rows


def config_defaults(src: str) -> list:
    """Các khối cấu hình mặc định trong load_global_config()."""
    out = []
    for block in ["tts", "video", "translate", "chatbot"]:
        m = re.search(r'"%s":\s*\{(.*?)\n            \}' % block, src, re.S)
        if not m:
            continue
        pairs = re.findall(r'"([\w_]+)":\s*([^,\n]+)', m.group(1))
        out.append((block, pairs))
    return out


def main():
    for p in (INDEX, CONFIG):
        if not os.path.exists(p):
            print(f"Thiếu {p}")
            sys.exit(1)

    html = read(INDEX)
    navs = nav_labels(html)
    pans = panels(html)
    label_map = labels_for(html)
    cfg_src = read(CONFIG)

    lines = [
        "# Tham số thực tế của ứng dụng",
        "",
        "> Tệp này được SINH TỰ ĐỘNG từ `webui/index.html` và `orchestrator/config.py`",
        "> bằng `scripts/gen_kb_from_project.py`. Không sửa tay — sửa mã nguồn rồi chạy lại.",
        "> Mọi lựa chọn liệt kê ở đây là lựa chọn CÓ THẬT trên giao diện.",
        "",
        "## Tên các bước trên giao diện",
        "",
        "Số hiệu hiển thị cho người dùng KHÔNG trùng tên hàm trong mã nguồn:",
        "",
        "| Người dùng thấy | Mã nội bộ |",
        "|---|---|",
    ]
    for tab in PANEL_ORDER:
        if tab in navs:
            lines.append(f"| {navs[tab]} | `{tab}` |")
    lines.append("")

    for tab in PANEL_ORDER:
        if tab not in pans:
            continue

        boxes = checkboxes_in(pans[tab])
        if boxes:
            step_name = navs.get(tab, tab)
            lines.append(f"## Các tuỳ chọn bật/tắt — {step_name}")
            lines.append("")
            lines.append(f"Những ô tích có trên màn hình {step_name}:")
            for _cid, text in boxes:
                lines.append(f"- **{text}**")
            lines.append("")

        fields = inputs_in(pans[tab], label_map)
        if fields:
            step_name = navs.get(tab, tab)
            lines.append(f"## Các ô cần nhập — {step_name}")
            lines.append("")
            # MỖI ô một mục con `###` -> bộ chia cắt thành một mảnh riêng.
            # Gộp cả nhóm vào một mảnh thì model chọn nhầm ô: hỏi về "Thư mục đầu
            # ra" mà nó chỉ sang "Đường dẫn file Cookies" nằm cùng mảnh.
            for _fid, label, hint, kind in fields:
                loai = "số" if kind == "number" else "chữ"
                lines.append(f"### {label}")
                lines.append("")
                lines.append(f"Ô nhập {loai} ở màn hình {step_name}.")
                if hint:
                    lines.append(f"Gợi ý ghi sẵn trong ô: {hint}")
                lines.append("")

        rows = selects_in(pans[tab], label_map)
        if not rows:
            continue
        # MỘT đoạn `##` cho MỖI tham số, không gộp cả bước vào một đoạn.
        #
        # Bản trước gộp toàn bộ select của một bước thành một đoạn ~1000 token.
        # Hỏi "Bước 3 chọn checkpoint nào" là nuốt trọn cả nghìn token mô tả mọi
        # dropdown khác của bước đó, trong khi câu trả lời chỉ cần vài chục token.
        # Chia nhỏ giúp nạp đúng phần cần, ngân sách context còn chỗ cho nhiều
        # mảnh kiến thức khác nhau cùng lúc.
        step = navs.get(tab, tab)
        for sid, label, opts in rows:
            title = label or sid
            lines.append(f"## {title} — {step}")
            lines.append("")
            # KHÔNG in id nội bộ (`s4SubSource`...) vào câu mô tả. Model đọc nó
            # như tên nút và hướng dẫn người dùng "bấm vào nút s4SubSource" —
            # một thứ không tồn tại trên màn hình. Chỉ dùng nhãn hiển thị.
            lines.append(f'Ô chọn **{title}** ở mục {step}. Các giá trị hợp lệ:')
            for val, text in opts:
                lines.append(f"- `{val}`: {text}")
            lines.append("")

    lines.append("## Giá trị mặc định trong cấu hình")
    lines.append("")
    for block, pairs in config_defaults(cfg_src):
        lines.append(f"**Khối `{block}`:**")
        for k, v in pairs:
            lines.append(f"- `{k}` = {v.strip()}")
        lines.append("")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    n_sel = sum(len(selects_in(pans[t], label_map)) for t in PANEL_ORDER if t in pans)
    print(f"Đã ghi {OUT}")
    print(f"  {len(navs)} nhãn bước, {n_sel} nhóm lựa chọn, {os.path.getsize(OUT)} byte")


if __name__ == "__main__":
    main()
