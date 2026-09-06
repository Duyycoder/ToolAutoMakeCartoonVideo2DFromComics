"""Thư viện video: nơi duy nhất biết dữ liệu nằm ở đâu trên đĩa.

Bố cục (mọi thứ nằm dưới `storage_dir` trong global_config.json):

    storage/
      videos/<entry_id>/
          video.json          # siêu dữ liệu: link nguồn, nền tảng, W/H, thời lượng...
          <ten>.mp4           # video gốc (tải về hoặc trỏ tới file ngoài)
          subs/*.srt          # phụ đề gốc + phụ đề đã dịch
          output/*.mp4        # video đã gắn phụ đề / lồng tiếng
      merged/                 # video ghép nhiều mục
      tasks/                  # thư mục làm việc tạm (ảnh xem trước OCR...)

`video.json` do adapter cào video ghi ra (chạy trong AIVoice/.venv). Orchestrator
CHỈ đọc/ghi JSON và quét thư mục — không import yt-dlp/torch (kiến trúc: mọi thứ
nặng chạy ở tiến trình con để tự nhả VRAM).
"""
import datetime
import json
import os
import re
import shutil
import time
import unicodedata
from typing import Any, Dict, List, Optional

VIDEO_EXTS = (".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv", ".ts", ".m4v")
SUB_EXTS = (".srt", ".vtt", ".ass")
# entry_id là TÊN THƯ MỤC do người dùng gián tiếp điều khiển (tiêu đề video) nên
# phải kiểm tra trước khi ghép đường dẫn — chặn "..", ổ đĩa khác, dấu gạch chéo.
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,120}$")


def slugify(text: str, max_len: int = 60) -> str:
    """Chuỗi an toàn cho tên thư mục/tệp: bỏ dấu tiếng Việt, chỉ còn [a-z0-9_-]."""
    if not text:
        return "video"
    text = text.strip().lower().replace("đ", "d")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text).strip("_")
    return text[:max_len].strip("_") or "video"


def human_size(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024 or unit == "GB":
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} GB"


class VideoLibrary:
    def __init__(self, base_storage_dir: str = "storage"):
        self.base_dir = os.path.abspath(base_storage_dir)
        self.videos_dir = os.path.join(self.base_dir, "videos")
        self.tasks_dir = os.path.join(self.base_dir, "tasks")
        self.merged_dir = os.path.join(self.base_dir, "merged")
        for d in (self.videos_dir, self.tasks_dir, self.merged_dir):
            os.makedirs(d, exist_ok=True)

    # ---------------- đường dẫn ----------------
    def entry_dir(self, entry_id: str) -> str:
        """Thư mục của một mục thư viện. Raise ValueError nếu id không hợp lệ."""
        if not entry_id or not SAFE_ID.match(entry_id):
            raise ValueError(f"Mã video không hợp lệ: {entry_id!r}")
        path = os.path.abspath(os.path.join(self.videos_dir, entry_id))
        if os.path.dirname(path) != self.videos_dir:
            raise ValueError(f"Mã video không hợp lệ: {entry_id!r}")
        return path

    def subs_dir(self, entry_id: str) -> str:
        return os.path.join(self.entry_dir(entry_id), "subs")

    def output_dir(self, entry_id: str) -> str:
        return os.path.join(self.entry_dir(entry_id), "output")

    def meta_path(self, entry_id: str) -> str:
        return os.path.join(self.entry_dir(entry_id), "video.json")

    def unique_entry_id(self, base: str) -> str:
        """Sinh entry_id chưa dùng từ một gợi ý tên (thêm hậu tố _2, _3...)."""
        base = slugify(base)
        candidate, n = base, 1
        while os.path.exists(os.path.join(self.videos_dir, candidate)):
            n += 1
            candidate = f"{base}_{n}"
        return candidate

    # ---------------- đọc/ghi ----------------
    def read_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        try:
            path = self.meta_path(entry_id)
        except ValueError:
            return None
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                meta = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return None
        meta["entry_id"] = entry_id
        return self._decorate(meta)

    def write_entry(self, entry_id: str, meta: Dict[str, Any]) -> bool:
        try:
            path = self.meta_path(entry_id)
        except ValueError:
            return False
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Các trường dẫn xuất (quét đĩa) không lưu xuống file — luôn tính lại khi đọc.
        clean = {k: v for k, v in meta.items()
                 if k not in ("subs", "outputs", "has_translation", "exists", "size_human")}
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(clean, fh, ensure_ascii=False, indent=2)
            return True
        except OSError:
            return False

    def list_entries(self) -> List[Dict[str, Any]]:
        """Toàn bộ thư viện, mới nhất trước."""
        out = []
        if not os.path.isdir(self.videos_dir):
            return out
        for name in sorted(os.listdir(self.videos_dir)):
            if not os.path.isdir(os.path.join(self.videos_dir, name)):
                continue
            meta = self.read_entry(name)
            if meta:
                out.append(meta)
        out.sort(key=lambda m: m.get("created_at", ""), reverse=True)
        return out

    def _decorate(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        """Bổ sung thông tin quét từ đĩa (phụ đề, bản đã dịch, file còn không)."""
        entry_id = meta["entry_id"]
        meta["subs"] = self.list_subs(entry_id)
        meta["outputs"] = self.list_outputs(entry_id)
        meta["has_translation"] = bool(meta["outputs"]) or any(
            s["name"].endswith(".vi.srt") for s in meta["subs"])
        video_file = meta.get("file") or ""
        meta["exists"] = bool(video_file) and os.path.exists(video_file)
        if meta["exists"] and not meta.get("size"):
            try:
                meta["size"] = os.path.getsize(video_file)
            except OSError:
                meta["size"] = 0
        meta["size_human"] = human_size(meta.get("size") or 0)
        return meta

    @staticmethod
    def _list_files(directory: str, exts: tuple) -> List[Dict[str, Any]]:
        items = []
        if not os.path.isdir(directory):
            return items
        for name in sorted(os.listdir(directory)):
            path = os.path.join(directory, name)
            if not os.path.isfile(path) or not name.lower().endswith(exts):
                continue
            try:
                stat = os.stat(path)
            except OSError:
                continue
            items.append({
                "name": name,
                "path": path,
                "size": stat.st_size,
                "size_human": human_size(stat.st_size),
                "mtime": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            })
        return items

    def list_subs(self, entry_id: str) -> List[Dict[str, Any]]:
        return self._list_files(self.subs_dir(entry_id), SUB_EXTS)

    def list_outputs(self, entry_id: str) -> List[Dict[str, Any]]:
        return self._list_files(self.output_dir(entry_id), VIDEO_EXTS)

    def find_file(self, entry_id: str, kind: str, name: str) -> str:
        """Đường dẫn tuyệt đối của một file con (kind = source|sub|output).

        Chống path traversal: chỉ nhận basename thuần và bắt buộc nằm trong thư
        mục của chính mục đó (người dùng gửi tên file qua URL).
        """
        entry = self.read_entry(entry_id)
        if not entry:
            raise FileNotFoundError(f"Không có video '{entry_id}' trong thư viện.")
        if kind == "source":
            path = entry.get("file") or ""
            if not path or not os.path.exists(path):
                raise FileNotFoundError("File video gốc không còn trên đĩa.")
            return path
        if os.path.basename(name) != name:
            raise ValueError(f"Tên file không hợp lệ: {name!r}")
        base = self.subs_dir(entry_id) if kind == "sub" else self.output_dir(entry_id)
        path = os.path.abspath(os.path.join(base, name))
        if os.path.dirname(path) != os.path.abspath(base) or not os.path.exists(path):
            raise FileNotFoundError(f"Không tìm thấy file: {name}")
        return path

    # ---------------- tạo mục ----------------
    def register_local(self, video_path: str, title: str = "", copy_file: bool = False) -> Dict[str, Any]:
        """Đưa một video có sẵn trên máy vào thư viện.

        Mặc định chỉ TRỎ tới file gốc (`copy_file=False`) — video hàng GB không
        nên nhân đôi chỉ để gắn phụ đề. Khi xoá mục, file gốc ngoài thư viện được
        giữ nguyên (xem `delete_entry`).
        """
        src = os.path.abspath(video_path)
        if not os.path.exists(src):
            raise FileNotFoundError(f"Không tìm thấy video: {video_path}")
        if not src.lower().endswith(VIDEO_EXTS):
            raise ValueError(f"Định dạng không được hỗ trợ: {os.path.splitext(src)[1] or '(không rõ)'}")

        display = (title or os.path.splitext(os.path.basename(src))[0]).strip()
        entry_id = self.unique_entry_id(display)
        entry_dir = self.entry_dir(entry_id)
        os.makedirs(entry_dir, exist_ok=True)

        final_path = src
        if copy_file:
            final_path = os.path.join(entry_dir, slugify(display) + os.path.splitext(src)[1].lower())
            shutil.copy2(src, final_path)

        meta = {
            "entry_id": entry_id,
            "source_id": "",
            "title": display,
            "url": "",
            "platform": "local",
            "uploader": "",
            "file": final_path,
            "size": os.path.getsize(final_path),
            "source": "import",
            "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "width": 0, "height": 0, "duration": 0,
        }
        self.write_entry(entry_id, meta)
        return self.read_entry(entry_id)

    def add_sub(self, entry_id: str, filename: str, content: str) -> Dict[str, Any]:
        """Lưu một file phụ đề (người dùng tải lên hoặc sửa tay trên giao diện)."""
        if not self.read_entry(entry_id):
            raise FileNotFoundError(f"Không có video '{entry_id}' trong thư viện.")
        name = os.path.basename(filename or "").strip() or "phu_de.srt"
        if not name.lower().endswith(SUB_EXTS):
            name += ".srt"
        subs = self.subs_dir(entry_id)
        os.makedirs(subs, exist_ok=True)
        path = os.path.join(subs, name)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        return {"name": name, "path": path, "size": os.path.getsize(path)}

    # ---------------- xoá & dọn dẹp ----------------
    def delete_entry(self, entry_id: str, delete_source_file: bool = True) -> bool:
        """Xoá một mục. Video 'import' trỏ ra ngoài thư viện KHÔNG bị đụng tới."""
        entry = self.read_entry(entry_id)
        if not entry:
            return False
        entry_dir = self.entry_dir(entry_id)
        src = entry.get("file") or ""
        inside = bool(src) and os.path.abspath(src).startswith(entry_dir + os.sep)
        if delete_source_file and src and not inside and entry.get("source") == "import":
            pass  # file gốc của người dùng nằm ngoài thư viện — không xoá
        shutil.rmtree(entry_dir, ignore_errors=True)
        return not os.path.exists(entry_dir)

    def cleanup_tasks(self, keep_days: float = 0, dry_run: bool = False) -> Dict[str, Any]:
        """Xoá thư mục làm việc tạm trong tasks/ (ảnh xem trước, video tải thử...)."""
        removed, freed = [], 0
        if not os.path.isdir(self.tasks_dir):
            return {"removed": [], "count": 0, "freed_mb": 0, "dry_run": dry_run}
        cutoff = time.time() - keep_days * 86400
        for name in os.listdir(self.tasks_dir):
            path = os.path.join(self.tasks_dir, name)
            if not os.path.isdir(path):
                continue
            try:
                if os.path.getmtime(path) > cutoff:
                    continue
            except OSError:
                continue
            freed += self._dir_size(path)
            if not dry_run:
                shutil.rmtree(path, ignore_errors=True)
            removed.append(name)
        return {"removed": removed, "count": len(removed),
                "freed_mb": round(freed / 1e6, 1), "dry_run": dry_run}

    @staticmethod
    def _dir_size(path: str) -> int:
        total = 0
        for root, _dirs, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        return total

    def stats(self) -> Dict[str, Any]:
        entries = self.list_entries()
        total_bytes = sum(e.get("size") or 0 for e in entries)
        outputs = sum(len(e.get("outputs") or []) for e in entries)
        subs = sum(len(e.get("subs") or []) for e in entries)
        merged = self._list_files(self.merged_dir, VIDEO_EXTS)
        return {
            "videos": len(entries),
            "translated": sum(1 for e in entries if e.get("has_translation")),
            "outputs": outputs,
            "subs": subs,
            "merged": len(merged),
            "duration_total": round(sum(float(e.get("duration") or 0) for e in entries), 1),
            "size_total": total_bytes,
            "size_total_human": human_size(total_bytes),
            "storage_dir": self.base_dir,
        }
