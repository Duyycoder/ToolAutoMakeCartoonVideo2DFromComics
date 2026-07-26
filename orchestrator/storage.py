import os
import re
import json
import time
import shutil
import unicodedata
from typing import Dict, Any, List, Optional
import datetime

try:
    from orchestrator import db
except ImportError:  # cho phép import khi chạy trực tiếp trong thư mục orchestrator
    import db

def slugify(text: str) -> str:
    """
    Converts Vietnamese and Unicode text into a safe ASCII slug for directories.
    Example: "Đắc Kỷ Trụ Vương" -> "dac_ky_tru_vuong"
    """
    if not text:
        return "unknown"
        
    # Convert to lowercase
    text = text.lower()
    
    # Replace common Vietnamese accents manually to get clean results
    replacements = {
        '[áàảãạăắằẳẵặâấầẩẫậ]': 'a',
        '[éèẻẽẹêếềểễệ]': 'e',
        '[íìỉĩị]': 'i',
        '[óòỏõọôốồổỗộơớờởỡợ]': 'o',
        '[úùủũụưứừửữự]': 'u',
        '[ýỳỷỹỵ]': 'y',
        'đ': 'd'
    }
    for regex_pat, replacement in replacements.items():
        text = re.sub(regex_pat, replacement, text)
        
    # Standard normalization and remove non-ascii characters
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    
    # Replace non-word characters with underscore, clean duplicates
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '_', text).strip('_')
    
    if not text:
        return "unknown"
    return text

class StorageManager:
    def __init__(self, base_storage_dir: str = "storage"):
        # Resolve path to absolute early to remain valid across directory changes
        self.base_dir = os.path.abspath(base_storage_dir)
        self.truyen_dir = os.path.join(self.base_dir, "truyen")
        self.tasks_dir = os.path.join(self.base_dir, "tasks")
        os.makedirs(self.truyen_dir, exist_ok=True)
        os.makedirs(self.tasks_dir, exist_ok=True)
        # A4: CSDL nhẹ SQLite đặt ngay trong thư mục dữ liệu (đi cùng dữ liệu nặng)
        self.db_path = os.path.join(self.base_dir, "app.db")
        try:
            db.init_db(self.db_path)
        except Exception:
            pass

    def get_story_dir(self, story_name: str) -> str:
        """Returns the absolute path to a story's workspace."""
        slug = slugify(story_name)
        return os.path.join(self.truyen_dir, slug)

    def init_story_workspace(self, story_name: str) -> Dict[str, str]:
        """
        Creates the standardized directory structure for a story.
        """
        story_dir = self.get_story_dir(story_name)
        if os.path.exists(story_dir):
            raise ValueError(f"Dự án '{story_name}' đã tồn tại.")
            
        dirs = {
            "root": story_dir,
            "raw": os.path.join(story_dir, "raw"),
            "video": os.path.join(story_dir, "video")
        }
        for d in dirs.values():
            os.makedirs(d, exist_ok=True)
            
        # Initialize default story.json if not exists
        story_json_path = os.path.join(story_dir, "story.json")
        if not os.path.exists(story_json_path):
            default_meta = {
                "story_name": story_name,
                "story_slug": slugify(story_name),
                "status": "CREATED", # CREATED -> CRAWLED -> TRANSLATED -> VOICE_GENERATED -> VIDEO_GENERATED
                "crawler": {
                    "source_url": "",
                    "total_chapters": 0,
                    "chapters": []
                },
                "translator": {
                    "engine": "gemini",
                    "translated_chapters": 0
                },
                "tts": {
                    "engine": "edge",
                    "voice": "vi-VN-NamMinhNeural",
                    "speed": 1.0,
                    "normalize": True
                },
                "video": {
                    "style": "anime",
                    "aspect_ratio": "16:9",
                    "subtitles_enabled": True
                },
                "pipeline_step": 1, # 1: crawl/translate, 2: tts, 3: video
                "created_at": datetime.datetime.now().isoformat(),
                "updated_at": datetime.datetime.now().isoformat()
            }
            self.write_story_meta(story_name, default_meta)
            
        return dirs

    def get_story_meta_path(self, story_name: str) -> str:
        story_dir = self.get_story_dir(story_name)
        return os.path.join(story_dir, "story.json")

    def read_story_meta(self, story_name: str) -> Optional[Dict[str, Any]]:
        path = self.get_story_meta_path(story_name)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def write_story_meta(self, story_name: str, meta: Dict[str, Any]) -> bool:
        path = self.get_story_meta_path(story_name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)
            # A4: đồng bộ (mirror) metadata nhẹ sang SQLite — không phá luồng tệp cũ
            try:
                self._mirror_to_db(story_name, meta)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def list_stories(self) -> List[Dict[str, Any]]:
        """Scans the storage directory and returns list of metadata for all stories."""
        stories = []
        if not os.path.exists(self.truyen_dir):
            return stories
            
        for item in os.listdir(self.truyen_dir):
            item_path = os.path.join(self.truyen_dir, item)
            if os.path.isdir(item_path):
                story_json = os.path.join(item_path, "story.json")
                if os.path.exists(story_json):
                    try:
                        with open(story_json, "r", encoding="utf-8") as f:
                            stories.append(json.load(f))
                    except Exception:
                        pass
        return stories

    # ---------- A4: đồng bộ SQLite ----------
    def _scan_chapters(self, story_name: str) -> List[Dict[str, Any]]:
        """Quét đĩa để lập danh sách chương (md + wav + mp4) cho một truyện."""
        story_dir = self.get_story_dir(story_name)
        base = None
        for sub in ("translated", "raw"):
            d = os.path.join(story_dir, sub)
            if os.path.isdir(d) and any(f.endswith(".md") for f in os.listdir(d)):
                base = d
                break
        if not base:
            return []
        video_dir = os.path.join(story_dir, "video")
        chapters = []
        mds = sorted(f for f in os.listdir(base) if f.endswith(".md"))
        for i, md in enumerate(mds, 1):
            stem = os.path.splitext(md)[0]
            wav = os.path.join(base, stem + ".wav")
            mp4 = os.path.join(video_dir, stem + ".mp4")
            has_wav, has_mp4 = os.path.exists(wav), os.path.exists(mp4)
            status = "video" if has_mp4 else ("tts" if has_wav else "text")
            chapters.append({
                "idx": i, "title": stem,
                "md_path": os.path.join(base, md),
                "wav_path": wav if has_wav else None,
                "mp4_path": mp4 if has_mp4 else None,
                "status": status,
            })
        return chapters

    def _mirror_to_db(self, story_name: str, meta: Dict[str, Any]) -> None:
        slug = meta.get("story_slug") or slugify(story_name)
        meta = dict(meta)
        meta.setdefault("story_slug", slug)
        db.upsert_story(self.db_path, meta)
        db.replace_chapters(self.db_path, slug, self._scan_chapters(story_name))

    def rebuild_db(self) -> int:
        """Dựng lại toàn bộ SQLite từ các story.json trên đĩa (chạy 1 lần để nạp dữ liệu cũ)."""
        n = 0
        for meta in self.list_stories():
            name = meta.get("story_name")
            if name:
                self._mirror_to_db(name, meta)
                n += 1
        return n

    # ---------- Dọn dẹp file sinh ra ----------
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

    # Tên thư mục KHÔNG BAO GIỜ xóa khi dọn dẹp (tri thức nhân vật, LoRA, ref...)
    PROTECTED_DIRS = ("contexts", "character_loras")
    # Thư mục làm việc trung gian có thể sinh lại — an toàn để xóa
    _TEMP_FRAME_DIRS = ("draft_frames", "final_frames", "scenes", "temp_audio", "temp")
    _UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-")

    def cleanup_tasks(self, keep_days: float = 0, dry_run: bool = False) -> Dict[str, Any]:
        """Xóa các thư mục làm việc TẠM trong tasks/ (khung ảnh trung gian, thư mục job uuid).

        BẢO VỆ: không đụng tới `contexts` (tri thức nhân vật/LoRA). Chỉ xóa thư mục job
        dạng uuid và các thư mục khung ảnh trung gian (draft_frames/final_frames/...).
        keep_days=0 => xóa tất cả (đủ điều kiện); keep_days=N => chỉ xóa thứ cũ hơn N ngày.
        dry_run=True => chỉ liệt kê, không xóa.
        """
        removed, freed = [], 0
        if not os.path.isdir(self.tasks_dir):
            return {"removed": [], "count": 0, "freed_mb": 0, "dry_run": dry_run}
        cutoff = time.time() - keep_days * 86400
        targets: List[str] = []
        for root, dirs, _files in os.walk(self.tasks_dir):
            rel_parts = os.path.relpath(root, self.tasks_dir).split(os.sep)
            if any(part in self.PROTECTED_DIRS for part in rel_parts):
                dirs[:] = []  # không đi sâu vào vùng được bảo vệ
                continue
            for d in list(dirs):
                if d in self.PROTECTED_DIRS:
                    continue
                if self._UUID_RE.match(d) or d in self._TEMP_FRAME_DIRS:
                    targets.append(os.path.join(root, d))
                    dirs.remove(d)  # đã đánh dấu xóa, không cần duyệt bên trong
        for p in targets:
            try:
                if os.path.getmtime(p) > cutoff:
                    continue
            except OSError:
                continue
            freed += self._dir_size(p)
            if not dry_run:
                shutil.rmtree(p, ignore_errors=True)
            removed.append(os.path.relpath(p, self.tasks_dir))
        return {"removed": removed, "count": len(removed),
                "freed_mb": round(freed / 1e6, 1), "dry_run": dry_run}

    def delete_story(self, story_name: str) -> bool:
        """Xóa toàn bộ dữ liệu một truyện (thư mục + bản ghi DB). Thao tác không hoàn tác."""
        story_dir = self.get_story_dir(story_name)
        slug = slugify(story_name)
        if os.path.isdir(story_dir):
            shutil.rmtree(story_dir, ignore_errors=True)
        try:
            db.delete_story(self.db_path, slug)
        except Exception:
            pass
        return True
