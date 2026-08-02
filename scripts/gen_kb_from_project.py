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
        rows = selects_in(pans[tab], label_map)
        if not rows:
            continue
        lines.append(f"## Lựa chọn hợp lệ — {navs.get(tab, tab)}")
        lines.append("")
        for sid, label, opts in rows:
            title = label or sid
            lines.append(f"**{title}** (`{sid}`) — các giá trị hợp lệ:")
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
