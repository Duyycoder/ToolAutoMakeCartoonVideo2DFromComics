"""Chuyển tài liệu PDF (in từ HTML bằng Chrome) thành Markdown cho kho tri thức trợ lý.

Cách dùng:
    python scripts/pdf_sang_kb.py <file.pdf> <thư_mục_ra> --tien-to ontap --tach 2

`--tach N`: mỗi tiêu đề cấp N mở một file mới (cấp 1 = cỡ chữ tiêu đề lớn nhất).

Vì sao không dùng thẳng `page.get_text()` hay `find_tables().extract()`:
- get_text() làm phẳng bảng thành từng ô một dòng, mất quan hệ hàng–cột, và in
  lẫn chữ của sơ đồ (flowchart, sequence) vào giữa văn bản.
- find_tables() bị khung nền của mã inline đánh lừa (sinh hàng/cột giả) và làm rơi
  dấu gạch dưới trong tên hàm (`num_predict` -> "num predict _").
Ở đây chỉ dùng HÌNH HỌC: đường kẻ ngang phủ gần hết bề rộng bảng là ranh giới
hàng; vị trí chữ ở hàng tiêu đề là ranh giới cột; chữ lấy từ span gốc nên đúng ký
tự. Chữ có cỡ lạ (nhãn sơ đồ, đầu/chân trang) bị bỏ.

Bảng hỏi–đáp (cột đầu là "#", có cột "Câu hỏi") được viết lại thành mỗi câu một
tiêu đề con: khi chia mảnh, mỗi câu hỏi tự đứng vững và tiêu đề khớp từ khoá được
cộng điểm khi truy xuất.
"""
import argparse
import collections
import os
import re
import unicodedata

import pymupdf

MONO_HINTS = ("Mono", "Type3", "Courier", "Consolas")
HEADING_HINTS = ("Bold", "Serif", "SemiBold")


def slug(text: str, limit: int = 48) -> str:
    t = unicodedata.normalize("NFD", text)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "D")
    t = re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-").lower()
    return t[:limit].rstrip("-") or "muc"


def is_mono(font: str) -> bool:
    return any(h in font for h in MONO_HINTS)


def is_heading_font(span) -> bool:
    return any(h in span["font"] for h in HEADING_HINTS) or bool(span["flags"] & 16)


def is_bold(span) -> bool:
    return "Bold" in span["font"] or "Semi" in span["font"] or bool(span["flags"] & 16)


class Profile:
    """Dò từ chính file: cỡ chữ văn bản hợp lệ và bảng cỡ chữ -> cấp tiêu đề."""

    def __init__(self, doc):
        total = collections.Counter()
        headish = collections.Counter()
        for page in doc:
            for b in page.get_text("dict")["blocks"]:
                for line in b.get("lines", []):
                    for s in line["spans"]:
                        n = len(s["text"].strip())
                        if not n or is_mono(s["font"]) or "KaTeX" in s["font"]:
                            continue
                        sz = round(s["size"], 1)
                        total[sz] += n
                        if is_heading_font(s):
                            headish[sz] += n
        all_chars = sum(total.values())
        self.body = total.most_common(1)[0][0]
        # Cỡ chữ văn bản: chiếm >= 3% toàn văn. Nhãn sơ đồ (9.1pt, 2.8pt...) rơi ra ngoài.
        self.text_sizes = {sz for sz, n in total.items() if n >= all_chars * 0.03}
        # Cỡ tiêu đề: lớn hơn thân bài và phần lớn ký tự ở cỡ đó là chữ đậm/serif.
        big = sorted(
            {sz for sz in headish
             if sz > self.body + 0.5 and headish[sz] >= 0.6 * total[sz] and headish[sz] >= 15},
            reverse=True,
        )
        self.levels = {sz: i + 1 for i, sz in enumerate(big)}

    def keep(self, span) -> bool:
        sz = round(span["size"], 1)
        if is_mono(span["font"]):
            return sz >= 5.5
        if sz <= 6.5:
            return False
        if "KaTeX" in span["font"] or "Segoe" in span["font"] or "DejaVu" in span["font"]:
            return True
        return sz in self.levels or any(abs(sz - t) < 0.15 for t in self.text_sizes)

    def line_level(self, spans) -> int:
        """Cấp tiêu đề của một dòng — mọi span có chữ đều phải là font tiêu đề."""
        vis = [s for s in spans if s["text"].strip()]
        if not vis:
            return 0
        sz = round(vis[0]["size"], 1)
        if sz not in self.levels:
            return 0
        if all(is_heading_font(s) and round(s["size"], 1) == sz for s in vis):
            return self.levels[sz]
        return 0


def span_text(spans):
    """Ghép các span của một dòng; mã inline bọc backtick."""
    out = ""
    for s in spans:
        t = s["text"]
        if not t:
            continue
        if is_mono(s["font"]) and t.strip():
            core = t.strip()
            lead = " " if t[:1].isspace() else ""
            tail = " " if t[-1:].isspace() else ""
            if out.endswith("`") and not lead:
                out = out[:-1] + core + "`" + tail
            else:
                out += f"{lead}`{core}`{tail}"
        else:
            out += t
    out = re.sub(r"`\s*`", "", out)
    out = re.sub(r"[\x00-\x08\x0b-\x1f​]", "", out)
    return re.sub(r"[ \t]+", " ", out).strip()


def page_lines(page, prof):
    lines = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            spans = [s for s in ln["spans"] if prof.keep(s)]
            if not spans or not "".join(s["text"] for s in spans).strip():
                continue
            vis = [s for s in spans if s["text"].strip()]
            # Công thức hiển thị (KaTeX) bị PDF cắt thành mảnh ký hiệu rời ("∥ε −ε",
            # "(x , t, c)∥") — đọc không ra nghĩa, chỉ làm nhiễu truy xuất.
            if all("KaTeX" in s["font"] for s in vis):
                continue
            lines.append({
                "x0": min(s["bbox"][0] for s in spans),
                "x1": max(s["bbox"][2] for s in spans),
                "y0": min(s["bbox"][1] for s in spans),
                "y1": max(s["bbox"][3] for s in spans),
                "size": round(vis[0]["size"], 1),
                "spans": spans,
                "lvl": prof.line_level(spans),
                "mono": all(is_mono(s["font"]) for s in vis),
                "bold": all(is_bold(s) for s in vis),
                "text": span_text(spans),
            })
    lines.sort(key=lambda l: (round(l["y0"]), l["x0"]))
    return lines


def separators(page, min_width: float = 150):
    """Đường kẻ ngang (gộp các đoạn cùng y) -> [(y, x0, x1)]."""
    segs = collections.defaultdict(list)
    for dr in page.get_drawings():
        for it in dr["items"]:
            if it[0] == "l":
                a, b = it[1], it[2]
                if abs(a.y - b.y) < 0.6 and abs(a.x - b.x) > 20:
                    segs[round(a.y)].append((min(a.x, b.x), max(a.x, b.x)))
            elif it[0] == "re":
                r = it[1]
                if r.height < 1.5 and r.width > 20:
                    segs[round(r.y0)].append((r.x0, r.x1))
    out = []
    for y, parts in segs.items():
        x0, x1 = min(p[0] for p in parts), max(p[1] for p in parts)
        covered = sum(p[1] - p[0] for p in parts)
        if x1 - x0 >= min_width and covered >= 0.6 * (x1 - x0):
            out.append((y, x0, x1))
    return sorted(out)


def table_groups(seps, lines):
    """Nhóm đường kẻ theo BỀ RỘNG (không theo thứ tự): khung nền của mã inline cũng
    là đường ngang nhưng hẹp hơn bảng, nếu nhóm theo thứ tự nó sẽ cắt đôi bảng.
    Giữa hai đường kẻ có tiêu đề hoặc dòng văn rộng hơn mọi ô -> hai bảng khác nhau."""
    by_ext = collections.defaultdict(list)
    for y, x0, x1 in seps:
        by_ext[(round(x0 / 8), round(x1 / 8))].append((y, x0, x1))
    groups = []
    for arr in by_ext.values():
        if len(arr) < 2:
            continue
        arr.sort()
        cur = {"x0": arr[0][1], "x1": arr[0][2], "ys": [arr[0][0]]}
        for y, x0, x1 in arr[1:]:
            py = cur["ys"][-1]
            width = x1 - x0
            blocked = any(py < (l["y0"] + l["y1"]) / 2 < y and
                          (l["lvl"] or l["x1"] - l["x0"] > 0.85 * width) for l in lines)
            if blocked:
                groups.append(cur)
                cur = {"x0": x0, "x1": x1, "ys": [y]}
            else:
                cur["ys"].append(y)
        groups.append(cur)
    groups = [g for g in groups if len(g["ys"]) >= 2]
    # Bỏ nhóm nằm lọt trong nhóm khác (khung mã trong ô bảng).
    def inside(a, b):
        return a is not b and a["x1"] - a["x0"] < b["x1"] - b["x0"] - 10 and \
            b["ys"][0] - 1 <= a["ys"][0] and a["ys"][-1] <= b["ys"][-1] + 1
    groups = [g for g in groups if not any(inside(g, o) for o in groups)]
    return sorted(groups, key=lambda g: g["ys"][0])


def columns_from(rows_lines):
    """Ranh giới cột: vị trí x0 xuất hiện ở >= 40% số hàng."""
    cnt = collections.Counter()
    for r in rows_lines:
        for x in {round(l["x0"] / 4) * 4 for l in r}:
            cnt[x] += 1
    need = max(1, int(0.4 * len(rows_lines)))
    cols = sorted(x for x, n in cnt.items() if n >= need)
    merged = []
    for c in cols:
        if not merged or c - merged[-1] > 14:
            merged.append(c)
    return merged


def cells_of(row_lines, cols):
    cells = [[] for _ in cols]
    for ln in sorted(row_lines, key=lambda l: (round(l["y0"]), l["x0"])):
        j = 0
        for i, c in enumerate(cols):
            if ln["x0"] >= c - 6:
                j = i
        cells[j].append(ln["text"])
    return [re.sub(r"\s+", " ", " ".join(c)).strip() for c in cells]


def build_tables(lines, groups, prev):
    """Gán dòng vào bảng; trả (bảng hợp lệ, các dòng còn lại cho dòng chảy)."""
    used = set()
    tables = []
    for gi, g in enumerate(groups):
        top, bot = g["ys"][0], g["ys"][-1]
        inside = [i for i, l in enumerate(lines)
                  if i not in used and l["lvl"] == 0 and g["x0"] - 6 <= l["x0"] <= g["x1"]
                  and top - 1 <= (l["y0"] + l["y1"]) / 2 <= bot + 1]
        # Bảng chạy tới hết trang thì hàng cuối không có viền dưới. Bảng kết thúc
        # giữa trang thì có viền, và mọi thứ bên dưới là văn bản khác. Nên: nhận
        # phần dưới viền cuối làm hàng bảng CHỈ KHI toàn bộ phần đó trông như ô
        # bảng (không có tiêu đề, không có dòng văn trải rộng một mình).
        tail = []
        if gi == len(groups) - 1:
            below = [i for i, l in enumerate(lines) if i not in used and (l["y0"] + l["y1"]) / 2 > bot + 1]
            width = g["x1"] - g["x0"]

            def cell_like(i):
                l = lines[i]
                same_row = any(abs(lines[j]["y0"] - l["y0"]) < 2 for j in below if j != i)
                return not l["lvl"] and (l["x1"] - l["x0"] <= 0.6 * width or same_row)
            if below and all(cell_like(i) for i in below):
                tail = below
        idx = inside + tail
        if not idx:
            continue
        bounds = list(g["ys"])
        if tail:
            bounds.append(max(lines[i]["y1"] for i in tail) + 1)
        rows = []
        for k in range(len(bounds) - 1):
            r = [lines[i] for i in idx if bounds[k] - 1 <= (lines[i]["y0"] + lines[i]["y1"]) / 2 < bounds[k + 1]]
            if r:
                rows.append(r)
        if len(rows) < 2:
            continue
        first = rows[0]
        # Bảng nối tiếp từ trang trước: là bảng đầu trang và không có chữ nào phía trên.
        cont = prev is not None and gi == 0 and not any(l["y1"] < top - 2 for l in lines)
        if cont:
            # Chrome lặp lại hàng tiêu đề ở đầu mỗi trang; hàng dữ liệu thì không.
            header_like = cells_of(first, prev["cols"]) == prev["header"]
        else:
            header_like = all(l["bold"] for l in first) or first[0]["text"] == "#" or (
                len(first) >= 2 and all(len(l["text"]) <= 40 for l in first))
        if header_like:
            cols = sorted({round(l["x0"]) for l in first})
            merged = []
            for c in cols:
                if not merged or c - merged[-1] > 12:
                    merged.append(c)
            cols = merged
            header = cells_of(first, cols)
            body = rows[1:]
        elif cont:
            cols, header = prev["cols"], prev["header"]
            body = rows
        else:
            cols = columns_from(rows)
            header = None
            body = rows
        if len(cols) < 2:
            continue
        cell_rows = [cells_of(r, cols) for r in body]
        multi = sum(1 for r in cell_rows if sum(1 for c in r if c) >= 2)
        if cell_rows and multi < 0.5 * len(cell_rows):
            continue  # không phải bảng (khung trích dẫn, đường kẻ trang trí)
        used.update(idx)
        tables.append({"kind": "table", "y0": top, "header": header, "cols": cols,
                       "rows": cell_rows, "cont": cont})
    rest = [l for i, l in enumerate(lines) if i not in used]
    return tables, rest


def flow_items(lines):
    """Dòng -> đoạn văn, khối mã, tiêu đề (dựa vào khoảng cách dọc)."""
    if not lines:
        return []
    margin = collections.Counter(round(l["x0"]) for l in lines if not l["mono"]).most_common(1)
    margin = margin[0][0] if margin else 0
    items, cur = [], None
    for l in lines:
        kind = "h" if l["lvl"] else ("code" if l["mono"] else "p")
        h = max(l["y1"] - l["y0"], 1)
        if cur and cur["kind"] == kind:
            gap = l["y0"] - cur["y1"]
            same = (kind == "h" and cur["lvl"] == l["lvl"] and gap < 6) or \
                   (kind == "p" and gap < 0.45 * h and abs(l["x0"] - cur["x"]) < 30) or \
                   (kind == "code" and gap < 0.9 * h)
            if same:
                if kind == "code":
                    cur["text"] += "\n" + code_line(l, cur["x"])
                else:
                    cur["text"] += " " + l["text"]
                cur["y1"] = l["y1"]
                continue
        cur = {"kind": kind, "lvl": l["lvl"], "y0": l["y0"], "y1": l["y1"], "x": l["x0"],
               "text": code_line(l, l["x0"]) if kind == "code" else l["text"],
               "indent": kind == "p" and l["x0"] > margin + 6}
        items.append(cur)
    return items


def code_line(l, base_x):
    raw = "".join(s["text"] for s in l["spans"]).rstrip()
    w = 0.6 * l["size"]
    pad = max(0, int(round((l["x0"] - base_x) / w))) if w else 0
    return " " * pad + raw.lstrip()


def extract(doc, prof):
    items, prev = [], None
    for page in doc:
        lines = page_lines(page, prof)
        groups = table_groups(separators(page), lines)
        tables, rest = build_tables(lines, groups, prev)
        page_items = flow_items(rest) + tables
        page_items.sort(key=lambda it: it["y0"])
        for it in page_items:
            if it["kind"] == "table":
                if it["cont"] and items and items[-1]["kind"] == "table":
                    last = items[-1]
                    for r in it["rows"]:
                        if r == last["header"]:
                            continue
                        if last["rows"] and not r[0] and any(r):
                            last["rows"][-1] = [(a + " " + b).strip() for a, b in zip(last["rows"][-1], r)]
                        else:
                            last["rows"].append(r)
                    continue
            items.append(it)
        prev = items[-1] if items and items[-1]["kind"] == "table" else None
    return items


QA_HEADERS = ("Câu hỏi", "Yêu cầu của hội đồng", "Câu bẫy")
TERM_HEADERS = ("Thuật ngữ",)


def table_md(it, depth):
    header, rows = it["header"], [r for r in it["rows"] if any(r)]
    if not header:
        return "\n".join("- " + " · ".join(c for c in r if c) for r in rows)
    hashes = "#" * min(depth + 1, 4)
    qcol = next((i for i, h in enumerate(header) if h in QA_HEADERS or h.startswith('"Code')), None)
    title_cols = None
    if qcol is not None and header[0] == "#":
        title_cols = (0, qcol)
    elif header[0] in TERM_HEADERS:
        title_cols = (0,)
    if title_cols:
        out = []
        for r in rows:
            out.append(f"{hashes} " + " ".join(r[i] for i in title_cols).strip())
            for i, h in enumerate(header):
                if i not in title_cols and r[i]:
                    out.append(f"- **{h}:** {r[i]}")
            out.append("")
        return "\n".join(out).strip()
    return "\n".join("- " + " · ".join(f"**{h}:** {c}" for h, c in zip(header, r) if c) for r in rows)


_Q_ITEM = re.compile(r"^(Q\d+\s*●*|\d{1,2}\.)\s+(.{8,})$")


def split_question(text: str):
    """'Q33 ●●● SD sinh ảnh thế nào? Khi huấn luyện…' -> ('Q33 SD sinh ảnh thế nào?', 'Khi…').

    Lấy dấu '?' CUỐI CÙNG trong 180 ký tự đầu, vì nhiều câu hỏi gồm hai vế
    ("LoRA là gì? Vì sao không fine-tune toàn bộ?")."""
    m = _Q_ITEM.match(text)
    if not m:
        return None
    label, rest = m.group(1), m.group(2)
    cut = rest.rfind("?", 0, 180)
    if cut < 5:
        return None
    label = re.sub(r"\s*●+", "", label).strip()
    return f"{label} {rest[:cut + 1].strip()}", rest[cut + 1:].strip()


def to_files(items, split_level, prefix):
    files, cur, depth = [], None, 1
    for it in items:
        if it["kind"] == "h":
            text = re.sub(r"^▾\s*", "", it["text"]).strip()
            if it["lvl"] <= split_level or cur is None:
                cur = [text, ["# " + text]]
                files.append(cur)
                depth = 1
                continue
            depth = min(it["lvl"] - split_level + 1, 4)
            cur[1].append("#" * depth + " " + text)
        elif cur is None:
            continue
        elif it["kind"] == "p":
            t = re.sub(r"^`?▾`?\s*", "▾ ", it["text"])
            if not re.search(r"\w{2,}", t):
                continue  # mảnh ký hiệu còn sót lại của công thức/sơ đồ
            qa = split_question(t)
            if t.startswith("▾") or t in ("Tóm tắt 1 phút", "Câu hỏi hội đồng có thể hỏi"):
                depth = 2
                cur[1].append("## " + t.lstrip("▾ ").strip())
            elif qa:
                # Câu hỏi luyện tập -> tiêu đề riêng để mảnh tự đứng vững khi bị cắt.
                cur[1].append("#" * min(depth + 1, 4) + " " + qa[0])
                if qa[1]:
                    cur[1].append(qa[1])
            else:
                cur[1].append(("- " if it.get("indent") else "") + t)
        elif it["kind"] == "code":
            cur[1].append("```\n" + it["text"] + "\n```")
        elif it["kind"] == "table":
            cur[1].append(table_md(it, depth))
    out = []
    for i, (title, body) in enumerate(files):
        text = "\n\n".join(x.strip("\n") for x in body if x.strip())
        out.append((f"{prefix}-{i:02d}-{slug(title)}.md", re.sub(r"\n{3,}", "\n\n", text) + "\n"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("out_dir")
    ap.add_argument("--tien-to", default="tl")
    ap.add_argument("--tach", type=int, default=1)
    ap.add_argument("--nguon", default="", help="Dòng ghi nguồn chèn dưới tiêu đề mỗi file")
    a = ap.parse_args()

    doc = pymupdf.open(a.pdf)
    prof = Profile(doc)
    print(f"Thân bài {prof.body}pt, cỡ văn bản {sorted(prof.text_sizes)}, cấp tiêu đề {prof.levels}")
    files = to_files(extract(doc, prof), a.tach, a.tien_to)
    os.makedirs(a.out_dir, exist_ok=True)
    for name, text in files:
        if a.nguon:
            first, _, rest = text.partition("\n")
            text = f"{first}\n\n> {a.nguon}\n{rest}"
        with open(os.path.join(a.out_dir, name), "w", encoding="utf-8") as f:
            f.write(text)
        print(f"{name}: {len(text):,} ký tự")


if __name__ == "__main__":
    main()
