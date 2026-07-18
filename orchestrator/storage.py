import os
import re
import json
import unicodedata
from typing import Dict, Any, List, Optional
import datetime

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
