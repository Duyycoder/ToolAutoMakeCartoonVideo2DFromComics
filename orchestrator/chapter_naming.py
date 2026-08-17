"""Quy tắc đặt tên tệp chương — dùng chung cho mọi nguồn đầu vào.

Các bước phía sau nhận diện chương HOÀN TOÀN qua tên tệp:

    Bản gốc chưa dịch :  "Chương NNNN - Tiêu đề gốc.md"
    Bản tiếng Việt    :  "Chương NNNN - [VI] Tiêu đề.md"

Bước dịch chỉ lấy tệp KHÔNG có " - [VI] "; bước lồng tiếng (TTS) và ghép video
thì ngược lại, chỉ lấy tệp CÓ " - [VI] ". Tệp sai quy tắc bị bỏ qua lặng lẽ —
không báo lỗi — nên người dùng chỉ thấy "không có gì để đọc".

Nguồn "Cào truyện" tự sinh đúng tên. Hai nguồn còn lại thì không:
  * "Sáng tác bằng AI" — trước đây ghi ra chuong_0001.md
  * "Thư mục cục bộ"   — người dùng tự tải truyện về, tên tệp tuỳ ý
Module này chuẩn hoá cho hai nguồn đó.
"""
import os
import re
from typing import Callable, List, Optional, Tuple

VI_MARKER = " - [VI] "

# Phần mở rộng được coi là tệp chương. Chuẩn hoá về .md vì bước dịch và bước
# ghép video chỉ quét .md (bước TTS thì nhận cả .txt).
CHAPTER_EXTS = (".md", ".txt")

MAX_TITLE_LEN = 80

# Các cách đánh số chương thường gặp ở truyện tải về, xét theo thứ tự ưu tiên.
_INDEX_PATTERNS = (
    # 第12章 / 第 12 章 (nguồn Trung)
    re.compile(r"第\s*(\d+)\s*[章回]"),
    # Chương 12 / chuong_0012 / Chapter 12 / Chap.12 / Ch 12
    re.compile(r"(?:ch[uư][oơ]ng|chapter|chap|ch)\s*[_\-.\s]*0*(\d+)", re.IGNORECASE),
    # c12 / c_12 (kiểu đặt tên rút gọn của nhiều trang truyện)
    re.compile(r"(?:^|[\s_\-])c[_\-.]?0*(\d+)(?:$|[\s_\-.])", re.IGNORECASE),
    # Tên tệp chỉ có số: 012 / 12
    re.compile(r"^\s*0*(\d+)\s*$"),
    # Số ở cuối tên: "Truyen ABC - 12"
    re.compile(r"[\s_\-.]0*(\d+)\s*$"),
)


def sanitize_filename(name: str) -> str:
    """Bỏ ký tự Windows cấm trong tên tệp và gộp khoảng trắng thừa."""
    name = re.sub(r'[\\/*?:"<>|]', " ", name)
    return re.sub(r"\s+", " ", name).strip(" .")


def chapter_filename(idx: int, title: str, translated: bool = True, ext: str = ".md") -> str:
    """Tên tệp chương chuẩn.

    translated=True  -> "Chương NNNN - [VI] Tiêu đề.md" (sẵn sàng cho TTS)
    translated=False -> "Chương NNNN - Tiêu đề.md"      (chờ bước dịch xử lý)
    """
    title = sanitize_filename(title)[:MAX_TITLE_LEN].strip()
    if not title:
        title = f"Chương {idx}"
    marker = "[VI] " if translated else ""
    return f"Chương {idx:04d} - {marker}{title}{ext}"


def parse_chapter_index(filename: str) -> Optional[int]:
    """Đoán số thứ tự chương từ tên tệp. Trả về None nếu không tìm thấy."""
    base = os.path.splitext(os.path.basename(filename))[0]
    # Bỏ nhãn [VI] để không lẫn vào phần dò số
    base = base.replace(VI_MARKER, " - ")
    for pattern in _INDEX_PATTERNS:
        m = pattern.search(base)
        if m:
            try:
                idx = int(m.group(1))
            except ValueError:
                continue
            if idx > 0:
                return idx
    return None


def title_from_filename(filename: str) -> str:
    """Phần tiêu đề còn lại sau khi bỏ số chương khỏi tên tệp."""
    base = os.path.splitext(os.path.basename(filename))[0]
    base = base.replace(VI_MARKER, " ")
    base = re.sub(r"第\s*\d+\s*[章回]", " ", base)
    base = re.sub(r"(?:ch[uư][oơ]ng|chapter|chap|ch)\s*[_\-.\s]*\d+", " ", base, flags=re.IGNORECASE)
    base = re.sub(r"(?:^|[\s_\-])c[_\-.]?\d+(?=$|[\s_\-.])", " ", base, flags=re.IGNORECASE)
    base = re.sub(r"^\s*\d+\s*", " ", base)
    base = re.sub(r"[\s_\-.]\d+\s*$", " ", base)
    base = base.replace("_", " ")
    # Bỏ dấu phân cách thừa còn sót ở hai đầu
    base = base.strip(" -–—:.·|")
    return sanitize_filename(base)


def title_from_text(text: str, idx: int) -> str:
    """Lấy tiêu đề từ dòng đầu nội dung chương (nếu dùng được)."""
    first = (text.strip().splitlines() or [""])[0].strip()
    first = re.sub(r"^#+\s*", "", first)
    first = first.strip("*# ").strip()
    # Bỏ tiền tố "Chương N:" vì số chương đã nằm ở đầu tên tệp
    first = re.sub(r"^(?:ch[uư][oơ]ng|chapter)\s*\d+\s*[:.\-–—]?\s*", "", first, flags=re.IGNORECASE)
    first = sanitize_filename(first)
    if not first:
        return f"Chương {idx}"
    return first[:MAX_TITLE_LEN].strip()


# Tên đã đúng quy tắc: "Chương NNNN - ..." (bốn chữ số, có thể kèm nhãn [VI])
_CANONICAL = re.compile(r"^Chương \d{4} - (\[VI\] )?\S")


def is_canonical(filename: str, translated: bool = True) -> bool:
    """Tên tệp đã đúng quy tắc cho trạng thái mong muốn hay chưa.

    `translated=True` đòi hỏi có thêm nhãn [VI]; `translated=False` thì bản gốc
    chưa dịch (không nhãn) cũng được coi là đúng — bước dịch sẽ tự gắn nhãn.
    """
    if not filename.lower().endswith(".md"):
        return False
    if not _CANONICAL.match(filename):
        return False
    return VI_MARKER in filename or not translated


def chapter_prefix(filename: str) -> str:
    """Phần "Chương NNNN" ở đầu tên tệp — khoá nhận diện chương của cả pipeline."""
    return filename.split(" - ")[0]


def _natural_key(name: str):
    """Khoá sắp xếp hiểu số: 'ch9' đứng trước 'ch10'."""
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", name)]


def _read_head(path: str, limit: int = 2000) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except OSError:
        return ""


def list_chapter_files(src_dir: str) -> List[str]:
    """Các tệp được coi là chương trong `src_dir` (không đệ quy), sắp xếp tự nhiên."""
    return sorted(
        (f for f in os.listdir(src_dir)
         if f.lower().endswith(CHAPTER_EXTS) and not f.startswith("_")),
        key=_natural_key,
    )


def plan_renames(
    src_dir: str,
    translated: bool = True,
    log: Optional[Callable[[str], None]] = None,
    include_canonical: bool = False,
) -> List[Tuple[str, str]]:
    """Lập bản đồ "tên cũ -> tên chuẩn" cho các tệp chương trong `src_dir`.

    Tệp đã đúng quy tắc được giữ nguyên và không tham gia vào việc đánh số, nhờ
    vậy chạy lại trên thư mục raw/ của truyện đã cào (có sẵn cặp bản gốc + bản
    [VI] trùng số chương) cũng không xáo trộn gì.

    `include_canonical=True` thì các tệp đó vẫn có mặt trong bản đồ dưới dạng
    "giữ nguyên tên" — cần khi chép sang thư mục khác, vì bỏ chúng ra khỏi bản
    đồ đồng nghĩa với không chép gì cả.

    Số chương lấy từ tên tệp; nếu có tệp không đoán được số, hoặc số bị trùng
    nhau, thì đánh số lại theo thứ tự sắp xếp tự nhiên của tên tệp — an toàn hơn
    là để hai chương mang cùng một số, vì bước TTS sẽ coi chúng là bản trùng và
    chỉ đọc một.
    """
    def say(msg: str):
        if log:
            log(msg)

    names = list_chapter_files(src_dir)
    if not names:
        return []

    canonical = [f for f in names if is_canonical(f, translated)]
    taken_prefixes = {chapter_prefix(f) for f in canonical}
    keep = [(f, f) for f in canonical] if include_canonical else []
    pending = [f for f in names if not is_canonical(f, translated)]
    if not pending:
        return keep

    indices = [parse_chapter_index(f) for f in pending]
    found = [i for i in indices if i is not None]
    use_positional = False
    if len(found) != len(pending):
        use_positional = True
        say(f"[Đặt tên] {len(pending) - len(found)}/{len(pending)} tệp không có số chương "
            f"trong tên — đánh số lại theo thứ tự tên tệp.")
    elif len(set(found)) != len(found):
        use_positional = True
        say("[Đặt tên] Số chương trong tên tệp bị trùng — đánh số lại theo thứ tự tên tệp.")

    plan = list(keep)
    for pos, fname in enumerate(pending, 1):
        idx = pos if use_positional else indices[pos - 1]
        # Tệp đã mang nhãn [VI] thì giữ nguyên nhãn, dù bước dịch có chạy hay không
        is_vi = translated or VI_MARKER in fname
        title = title_from_filename(fname)
        if not title:
            title = title_from_text(_read_head(os.path.join(src_dir, fname)), idx)
        new_name = chapter_filename(idx, title, translated=is_vi)
        if chapter_prefix(new_name) in taken_prefixes:
            say(f"[Đặt tên] Bỏ qua '{fname}': đã có tệp đúng quy tắc cho "
                f"{chapter_prefix(new_name)}.")
            continue
        plan.append((fname, new_name))
    return plan


def normalize_dir(
    src_dir: str,
    dst_dir: Optional[str] = None,
    translated: bool = True,
    log: Optional[Callable[[str], None]] = None,
    dry_run: bool = False,
) -> int:
    """Chuẩn hoá tên các tệp chương.

    dst_dir=None  -> đổi tên tại chỗ.
    dst_dir khác  -> chép sang thư mục đích với tên chuẩn (giữ nguyên thư mục nguồn).
    Trả về số tệp đã xử lý.
    """
    import shutil

    def say(msg: str):
        if log:
            log(msg)

    in_place = dst_dir is None or os.path.abspath(dst_dir) == os.path.abspath(src_dir)
    out_dir = src_dir if in_place else dst_dir
    if not in_place and not dry_run:
        os.makedirs(out_dir, exist_ok=True)

    done = 0
    plan = plan_renames(src_dir, translated=translated, log=log,
                        include_canonical=not in_place)
    for old_name, new_name in plan:
        src = os.path.join(src_dir, old_name)
        dst = os.path.join(out_dir, new_name)
        if os.path.abspath(src) == os.path.abspath(dst):
            done += 1
            continue
        if os.path.exists(dst):
            say(f"[Đặt tên] Bỏ qua '{old_name}': '{new_name}' đã tồn tại.")
            continue
        if old_name != new_name:
            say(f"[Đặt tên] {old_name}  ->  {new_name}")
        if not dry_run:
            if in_place:
                os.rename(src, dst)
            else:
                shutil.copy2(src, dst)
        done += 1
    return done
