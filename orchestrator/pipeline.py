import os
import shutil
import datetime
from typing import Dict, Any, Optional
from orchestrator.storage import StorageManager
from orchestrator.process_manager import ProcessManager

class NovelPipeline:
    def __init__(self, storage_mgr: StorageManager, process_mgr: ProcessManager):
        self.storage_mgr = storage_mgr
        self.process_mgr = process_mgr

    def start_step_1_crawl_translate(self, story_name: str, crawl_args: dict, trans_args: dict) -> bool:
        """Runs crawl subcommand, and on success, triggers translate subcommand."""
        story_meta = self.storage_mgr.read_story_meta(story_name)
        if not story_meta:
            return False

        story_dir = self.storage_mgr.get_story_dir(story_name)
        raw_dir = os.path.join(story_dir, "raw")
        translated_dir = os.path.join(story_dir, "translated")

        python_exe = os.path.abspath("toolCaoTruyen/.venv/Scripts/python.exe")
        adapter_path = os.path.abspath("toolCaoTruyen/adapter_cli.py")

        # 1. Crawl Command
        crawl_cmd = None
        if crawl_args.get("source") != "local":
            crawl_cmd = [
                python_exe, adapter_path, "crawl",
                "--source", crawl_args["source"],
                "--story-id", crawl_args.get("story_id") or "Auto",
                "--start-chapter-id", crawl_args.get("start_chapter_id") or "Auto",
                "--num-chapters", str(crawl_args.get("num_chapters", 1)),
                "--output-dir", raw_dir
            ]
            
            if crawl_args.get("base_url"):
                crawl_cmd.extend(["--base-url", crawl_args["base_url"]])

            if crawl_args.get("continue_download"):
                crawl_cmd.append("--continue-download")

        # 2. Translate Command (runs after crawl succeeds)
        translate_cmd = [
            python_exe, adapter_path, "translate",
            "--input-dir", raw_dir,
            "--output-dir", raw_dir,
            "--engine", trans_args.get("engine") or "gemini_api",
        ]
        if trans_args.get("ollama_model"):
            translate_cmd.extend(["--ollama-model", trans_args.get("ollama_model")])
        if trans_args.get("gemini_api_key"):
            translate_cmd.extend(["--gemini-api-key", trans_args.get("gemini_api_key")])
            translate_cmd.extend(["--gemini-offline-key", trans_args.get("gemini_api_key")])
        if trans_args.get("gemini_model"):
            translate_cmd.extend(["--gemini-model", trans_args.get("gemini_model")])
        if trans_args.get("gemini_offline_base_url"):
            translate_cmd.extend(["--gemini-offline-base-url", trans_args.get("gemini_offline_base_url")])
        if trans_args.get("gemini_offline_model"):
            translate_cmd.extend(["--gemini-offline-model", trans_args.get("gemini_offline_model")])
        if trans_args.get("genre"):
            translate_cmd.extend(["--genre", trans_args.get("genre")])
        if trans_args.get("auto_extract", True):
            translate_cmd.append("--auto-extract")
        if trans_args.get("glossary_extract_engine"):
            translate_cmd.extend(["--glossary-extract-engine", trans_args.get("glossary_extract_engine")])
        if trans_args.get("glossary_extract_ollama_model"):
            translate_cmd.extend(["--glossary-extract-ollama-model", trans_args.get("glossary_extract_ollama_model")])

        task_key = f"{story_meta['story_slug']}_step1"

        def on_translate_completed(exit_code: int):
            meta = self.storage_mgr.read_story_meta(story_name)
            if not meta:
                return
            if exit_code == 0:
                meta["status"] = "TRANSLATED"
                meta["pipeline_step"] = 2
            else:
                meta["status"] = "TRANSLATE_FAILED"
            meta["updated_at"] = datetime.datetime.now().isoformat()
            self.storage_mgr.write_story_meta(story_name, meta)

        def on_crawl_completed(exit_code: int):
            meta = self.storage_mgr.read_story_meta(story_name)
            if not meta:
                # If meta is not found, we still need to close the queue!
                if task_key in self.process_mgr.log_queues:
                    self.process_mgr.log_queues[task_key].put(None)
                return
            if exit_code == 0:
                if trans_args.get("auto_translate", True):
                    # Crawl succeeded -> start translation immediately
                    meta["status"] = "TRANSLATING"
                    meta["updated_at"] = datetime.datetime.now().isoformat()
                    self.storage_mgr.write_story_meta(story_name, meta)
                    
                    if task_key in self.process_mgr.log_queues:
                        self.process_mgr.log_queues[task_key].put("\n[Pipeline] Bắt đầu tự động dịch...\n")
                    
                    # Start translation process on the same queue!
                    self.process_mgr.start_process(
                        task_key=task_key,
                        cmd=translate_cmd,
                        cwd="toolCaoTruyen",
                        on_completed=on_translate_completed,
                        close_queue_on_exit=True,
                        reuse_queue=True
                    )
                else:
                    meta["status"] = "CRAWLED"
                    meta["updated_at"] = datetime.datetime.now().isoformat()
                    self.storage_mgr.write_story_meta(story_name, meta)
                    self.process_mgr.log_queues[task_key].put(None)
            else:
                meta["status"] = "CRAWL_FAILED"
                meta["updated_at"] = datetime.datetime.now().isoformat()
                self.storage_mgr.write_story_meta(story_name, meta)
                self.process_mgr.log_queues[task_key].put(None)

        # Start Crawling
        story_meta["status"] = "CRAWLING"
        story_meta["updated_at"] = datetime.datetime.now().isoformat()
        self.storage_mgr.write_story_meta(story_name, story_meta)

        if crawl_cmd:
            return self.process_mgr.start_process(
                task_key=task_key,
                cmd=crawl_cmd,
                cwd="toolCaoTruyen",
                on_completed=on_crawl_completed,
                close_queue_on_exit=False # Important! Wait for on_crawl_completed to close queue if not translating
            )
        else:
            # Handle local folder copy in a background thread to not block
            import threading
            import shutil
            def _copy_local():
                local_dir = crawl_args.get("local_folder")
                try:
                    if local_dir and os.path.exists(local_dir):
                        for item in os.listdir(local_dir):
                            if item.endswith(".md") or item.endswith(".txt"):
                                shutil.copy2(os.path.join(local_dir, item), os.path.join(raw_dir, item))
                        on_crawl_completed(0)
                    else:
                        on_crawl_completed(1)
                except Exception as e:
                    on_crawl_completed(1)
            threading.Thread(target=_copy_local, daemon=True).start()
            return True

    def start_step_2_tts(self, story_name: str, tts_args: dict) -> bool:
        """Runs tts adapter on translated chapters."""
        story_meta = self.storage_mgr.read_story_meta(story_name)
        if not story_meta:
            return False

        story_dir = self.storage_mgr.get_story_dir(story_name)
        raw_dir = os.path.join(story_dir, "raw")
        translated_dir = os.path.join(story_dir, "translated")

        # Determine TTS input: use translated if available, otherwise raw
        tts_input_dir = raw_dir
        if os.path.isdir(translated_dir) and any(f.endswith('.md') for f in os.listdir(translated_dir)):
            tts_input_dir = translated_dir

        from orchestrator.config import load_global_config
        g_config = load_global_config()
        tts_cfg = g_config.get("tts", {})

        python_exe = os.path.abspath("AIVoice/.venv/Scripts/python.exe")
        adapter_path = os.path.abspath("AIVoice/adapter_tts_cli.py")

        engine = tts_args.get("engine") or tts_cfg.get("default_engine", "edge")
        
        # Determine voice fallback depending on engine
        if engine == "kokoro":
            default_voice = tts_cfg.get("kokoro_voice", "thuc_trinh")
        elif engine == "vieneu":
            default_voice = tts_cfg.get("vieneu_voice") or "Ngọc Lan"
        else:
            default_voice = tts_cfg.get("default_voice", "vi-VN-NamMinhNeural")
            
        voice = tts_args.get("voice") or default_voice
        speed = tts_args.get("speed") if tts_args.get("speed") is not None else tts_cfg.get("speed", 1.0)
        normalize_val = tts_args.get("normalize") if tts_args.get("normalize") is not None else tts_cfg.get("normalize", True)

        cmd = [
            python_exe, adapter_path,
            "--input-dir", tts_input_dir,
            "--output-dir", tts_input_dir,
            "--engine", engine,
            "--voice", voice,
            "--speed", str(speed),
            "--target-lufs", str(tts_args.get("target_lufs") if tts_args.get("target_lufs") is not None else -14.0),
            "--fade-in", str(tts_args.get("fade_in") if tts_args.get("fade_in") is not None else 0.1),
            "--fade-out", str(tts_args.get("fade_out") if tts_args.get("fade_out") is not None else 0.1),
            "--silence-duration", str(tts_args.get("silence_duration") if tts_args.get("silence_duration") is not None else 0.3),
            "--device", tts_args.get("device") or "cuda"
        ]
        if tts_args.get("preset"):
            cmd += ["--preset", tts_args["preset"]]
        if tts_args.get("model"):
            cmd += ["--model", os.path.abspath(tts_args["model"])]
        if tts_args.get("ref_audio"):
            cmd += ["--ref-audio", os.path.abspath(tts_args["ref_audio"])]
        if tts_args.get("phonemize", False):
            cmd.append("--phonemize")
        else:
            cmd.append("--no-phonemize")
            
        if normalize_val:
            cmd.append("--normalize")
        else:
            cmd.append("--no-normalize")
            
        if tts_args.get("use_cache", False):
            cmd.append("--use-cache")
        else:
            cmd.append("--no-cache")
        if tts_args.get("cache_threshold") is not None:
            cmd += ["--cache-threshold", str(tts_args["cache_threshold"])]
            
        vieneu_mode = tts_args.get("vieneu_mode") or tts_cfg.get("vieneu_mode", "v3turbo")
        if vieneu_mode:
            cmd += ["--vieneu-mode", str(vieneu_mode)]
        if tts_args.get("vieneu_emotion"):
            cmd += ["--vieneu-emotion", str(tts_args["vieneu_emotion"])]
        if tts_args.get("temperature") is not None:
            cmd += ["--temperature", str(tts_args["temperature"])]

        task_key = f"{story_meta['story_slug']}_step2"

        def on_tts_completed(exit_code: int):
            meta = self.storage_mgr.read_story_meta(story_name)
            if not meta:
                return
            if exit_code == 0:
                meta["status"] = "VOICE_GENERATED"
                meta["pipeline_step"] = 3
            else:
                meta["status"] = "VOICE_FAILED"
            meta["updated_at"] = datetime.datetime.now().isoformat()
            self.storage_mgr.write_story_meta(story_name, meta)

        story_meta["status"] = "VOICE_GENERATING"
        story_meta["updated_at"] = datetime.datetime.now().isoformat()
        self.storage_mgr.write_story_meta(story_name, story_meta)

        return self.process_mgr.start_process(
            task_key=task_key,
            cmd=cmd,
            cwd="AIVoice",
            on_completed=on_tts_completed
        )

    def start_step_3_video(self, story_name: str, video_args: dict) -> bool:
        """Arranges inputs and runs MediaComposer video generation on chapters."""
        story_meta = self.storage_mgr.read_story_meta(story_name)
        if not story_meta:
            return False

        story_dir = self.storage_mgr.get_story_dir(story_name)
        raw_dir = os.path.join(story_dir, "raw")
        translated_dir = os.path.join(story_dir, "translated")
        video_output_dir = os.path.join(story_dir, "video")

        # Determine Video input: use translated if available, otherwise raw
        video_input_dir = raw_dir
        if os.path.isdir(translated_dir) and any(f.endswith('.md') for f in os.listdir(translated_dir)):
            video_input_dir = translated_dir

        python_exe = os.path.abspath("AIVoice/.venv/Scripts/python.exe")
        adapter_path = os.path.abspath("AIVoice/apps/MediaComposer/adapter_video_cli.py")

        from orchestrator.config import load_global_config
        g_config = load_global_config()
        video_cfg = g_config.get("video", {})

        # Resolve LLM parameters for Step 3
        llm_engine = video_args.get("llm_engine") or video_cfg.get("default_llm_engine") or "gemini_api"
        llm_api_key = video_args.get("llm_api_key")
        llm_offline_base_url = video_args.get("llm_offline_base_url")
        llm_offline_model = video_args.get("llm_offline_model") or video_cfg.get("default_llm_model")

        if llm_engine == "gemini":  # Gemini Online (AI Studio)
            resolved_key = llm_api_key or g_config.get("api_keys", {}).get("gemini", "")
            if not resolved_key:
                raise ValueError("Đã chọn Gemini Online nhưng chưa có API Key. Nhập key ở Bước 3 hoặc lưu vào Cấu Hình Chung (api_keys.gemini).")
            resolved_base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            resolved_model = llm_offline_model or "gemini-2.0-flash"
        elif llm_engine == "ollama":  # Ollama (Local)
            resolved_key = "ollama"  # placeholder: get_llm_client() yeu cau key khac rong
            resolved_base_url = llm_offline_base_url or g_config.get("crawler", {}).get("ollama_base_url") or "http://localhost:11434/v1"
            # Mac dinh qwen2.5:3b-instruct (~2-3GB VRAM) — vua GPU 6GB khi chay cung SD
            resolved_model = llm_offline_model or "qwen2.5:3b-instruct"
        else:  # gemini_api (Local Gemini proxy)
            resolved_key = llm_api_key or "sk-gemini-YrVwXWGegzkFlevHPdQy7Fpry14HJVirqvnuxukz"
            resolved_base_url = llm_offline_base_url or g_config.get("crawler", {}).get("gemini_offline_base_url") or "http://localhost:7860/v1"
            resolved_model = llm_offline_model or "gemini-3-flash"

        cmd = [
            python_exe, adapter_path,
            "--story-name", story_name,
            "--genre", video_args.get("genre", "tien_hiep"),
            "--input-dir", video_input_dir,
            "--output-dir", video_output_dir,
            "--style", video_args.get("style") or video_cfg.get("default_style") or "anime_2d_flat",
            "--checkpoint", video_args.get("checkpoint") or video_cfg.get("default_checkpoint") or "anything-v5",
            "--bgm-path", video_args.get("bgm_path") or "",
            "--bgm-volume", str(video_args.get("bgm_volume") if video_args.get("bgm_volume") is not None else video_cfg.get("bgm_volume", 0.15)),
            "--llm-api-key", resolved_key,
            "--llm-base-url", resolved_base_url,
            "--llm-model", resolved_model
        ]
        if video_args.get("enable_upscale", True):
            cmd.append("--enable-upscale")
        else:
            cmd.append("--no-upscale")
        if video_args.get("burn_subtitles", False):
            cmd.append("--burn-subtitles")
        else:
            cmd.append("--no-subtitles")
        if video_args.get("use_semantic_split", True):
            cmd.append("--use-semantic-split")
        else:
            cmd.append("--no-semantic-split")
            
        if video_args.get("extract_characters", True):
            cmd.append("--extract-characters")
        else:
            cmd.append("--no-extract-characters")
            
        if video_args.get("enable_face_detailer", False):
            cmd.append("--enable-face-detailer")
        else:
            cmd.append("--no-face-detailer")
            
        hw_profile = video_args.get("hardware_profile", "auto")
        cmd.extend(["--hardware-profile", hw_profile])

        # Set MC_STORAGE_TASKS environment variable to redirect MediaComposer outputs into the storage/tasks folder
        env_override = {
            "MC_STORAGE_TASKS": self.storage_mgr.tasks_dir
        }
        device = video_args.get("device", "auto")
        if device == "cpu":
            env_override["CUDA_VISIBLE_DEVICES"] = ""
        elif device.startswith("cuda:"):
            env_override["CUDA_VISIBLE_DEVICES"] = device.split(":")[1]

        task_key = f"{story_meta['story_slug']}_step3"

        def on_video_completed(exit_code: int):
            meta = self.storage_mgr.read_story_meta(story_name)
            if not meta:
                return
            if exit_code == 0:
                # Merge videos
                import time
                from orchestrator.video_merger import merge_videos
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                output_file = os.path.join(video_output_dir, f"TongHop_{timestamp}.mp4")
                if task_key in self.process_mgr.log_queues:
                    self.process_mgr.log_queues[task_key].put(f"\n[SYSTEM] Đang hợp nhất video vào {output_file}...\n")
                
                success = merge_videos(video_output_dir, output_file)
                if success and task_key in self.process_mgr.log_queues:
                    self.process_mgr.log_queues[task_key].put(f"[SYSTEM] Đã hợp nhất video thành công!\n")
                elif not success and task_key in self.process_mgr.log_queues:
                    self.process_mgr.log_queues[task_key].put(f"[SYSTEM] Lỗi khi hợp nhất video.\n")
                    
                meta["status"] = "VIDEO_GENERATED"
                meta["pipeline_step"] = 3 # Complete!
            else:
                meta["status"] = "VIDEO_FAILED"
            meta["updated_at"] = datetime.datetime.now().isoformat()
            self.storage_mgr.write_story_meta(story_name, meta)

        story_meta["status"] = "VIDEO_GENERATING"
        story_meta["updated_at"] = datetime.datetime.now().isoformat()
        self.storage_mgr.write_story_meta(story_name, story_meta)

        return self.process_mgr.start_process(
            task_key=task_key,
            cmd=cmd,
            cwd="AIVoice",
            env_override=env_override,
            on_completed=on_video_completed
        )

    def start_step_4_autosub(self, story_name: str | None, autosub_args: dict) -> bool:
        """Runs MediaComposer autosub and dubbing workflow on a video."""
        import datetime
        import uuid
        task_id = autosub_args.get("task_id") or uuid.uuid4().hex[:8]
        
        slug = ""
        if story_name:
            story_meta = self.storage_mgr.read_story_meta(story_name)
            if not story_meta:
                return False
            slug = story_meta['story_slug']
            output_dir = os.path.join(self.storage_mgr.get_story_dir(story_name), "video")
            task_key = f"{slug}_step4"
        else:
            output_dir = os.path.join(self.storage_mgr.tasks_dir, f"autosub_{task_id}")
            task_key = f"autosub_{task_id}_step4"
            
        os.makedirs(output_dir, exist_ok=True)
        
        python_exe = os.path.abspath("AIVoice/.venv/Scripts/python.exe")
        adapter_path = os.path.abspath("AIVoice/apps/MediaComposer/adapter_autosub_cli.py")
        
        from orchestrator.config import load_global_config
        g_config = load_global_config()
        video_cfg = g_config.get("video", {})
        
        # Resolve LLM parameters for translation
        llm_engine = autosub_args.get("llm_engine") or video_cfg.get("default_llm_engine") or "gemini_api"
        llm_api_key = autosub_args.get("llm_api_key")
        llm_offline_base_url = autosub_args.get("llm_offline_base_url")
        llm_offline_model = autosub_args.get("llm_offline_model") or video_cfg.get("default_llm_model")

        if llm_engine == "gemini":  # Gemini Online
            resolved_key = llm_api_key or g_config.get("api_keys", {}).get("gemini", "")
            if not resolved_key:
                raise ValueError("Đã chọn Gemini Online nhưng chưa có API Key. Nhập key ở Bước 4 hoặc lưu vào Cấu Hình Chung (api_keys.gemini).")
            resolved_base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            resolved_model = llm_offline_model or "gemini-2.0-flash"
        elif llm_engine == "ollama":  # Ollama (Local)
            resolved_key = "ollama"
            resolved_base_url = llm_offline_base_url or g_config.get("crawler", {}).get("ollama_base_url") or "http://localhost:11434/v1"
            resolved_model = llm_offline_model or "qwen2.5:3b-instruct"
        else:  # gemini_api (Local Gemini proxy)
            resolved_key = llm_api_key or "sk-gemini-YrVwXWGegzkFlevHPdQy7Fpry14HJVirqvnuxukz"
            resolved_base_url = llm_offline_base_url or g_config.get("crawler", {}).get("gemini_offline_base_url") or "http://localhost:7860/v1"
            resolved_model = llm_offline_model or "gemini-3-flash"
            
        cmd = [
            python_exe, adapter_path,
            "--output-dir", output_dir,
            "--source-lang", autosub_args.get("source_lang", "English"),
            "--sub-source", autosub_args.get("sub_source", "whisper"),
            "--burn-method", autosub_args.get("burn_method", "ffmpeg"),
            "--tts-engine", autosub_args.get("tts_engine", "edge"),
            "--tts-voice", autosub_args.get("tts_voice") or "",
            "--ducking-ratio", str(autosub_args.get("ducking_ratio", 90.0)),
            "--llm-api-key", resolved_key,
            "--llm-base-url", resolved_base_url,
            "--llm-model", resolved_model
        ]
        
        if autosub_args.get("video_path"):
            cmd.extend(["--video-path", autosub_args.get("video_path")])
        if autosub_args.get("download_url"):
            cmd.extend(["--download-url", autosub_args.get("download_url")])
            if autosub_args.get("platform"):
                cmd.extend(["--platform", autosub_args.get("platform")])
                
        if autosub_args.get("clean_audio"):
            cmd.append("--clean-audio")
        if autosub_args.get("enable_voiceover"):
            cmd.append("--enable-voiceover")
        if autosub_args.get("auto_clone"):
            cmd.append("--auto-clone")
            
        crop_x = autosub_args.get("crop_x", -1)
        crop_y = autosub_args.get("crop_y", -1)
        crop_w = autosub_args.get("crop_w", -1)
        crop_h = autosub_args.get("crop_h", -1)
        if crop_x >= 0 and crop_y >= 0 and crop_w > 0 and crop_h > 0:
            crop_x = max(0, crop_x)
            crop_y = max(0, crop_y)
            crop_w = max(0, crop_w)
            crop_h = max(0, crop_h)
            cmd.extend([
                "--crop-x", str(crop_x),
                "--crop-y", str(crop_y),
                "--crop-w", str(crop_w),
                "--crop-h", str(crop_h)
            ])

        # Append subtitle styling parameters if provided
        if autosub_args.get("font_name"):
            cmd.extend(["--font-name", autosub_args.get("font_name")])
        if autosub_args.get("font_size"):
            cmd.extend(["--font-size", str(autosub_args.get("font_size"))])
        if autosub_args.get("text_color"):
            cmd.extend(["--text-color", autosub_args.get("text_color")])
        if autosub_args.get("stroke_color"):
            cmd.extend(["--stroke-color", autosub_args.get("stroke_color")])
        if autosub_args.get("stroke_width") is not None:
            cmd.extend(["--stroke-width", str(autosub_args.get("stroke_width"))])
        if autosub_args.get("bg_style"):
            cmd.extend(["--bg-style", autosub_args.get("bg_style")])
        if autosub_args.get("bg_color"):
            cmd.extend(["--bg-color", autosub_args.get("bg_color")])
        if autosub_args.get("bg_alpha") is not None:
            cmd.extend(["--bg-alpha", str(autosub_args.get("bg_alpha"))])
        if autosub_args.get("sub_position"):
            cmd.extend(["--sub-position", autosub_args.get("sub_position")])
        if autosub_args.get("custom_position") is not None:
            cmd.extend(["--custom-position", str(autosub_args.get("custom_position"))])

        # Resolve cookies file from args or global config
        cookies_file = autosub_args.get("cookies_file") or g_config.get("video", {}).get("downloader_cookies", "")
        if cookies_file:
            cmd.extend(["--cookies-file", cookies_file])

        def on_autosub_completed(exit_code: int):
            if story_name:
                meta = self.storage_mgr.read_story_meta(story_name)
                if meta:
                    if exit_code == 0:
                        meta["status"] = "AUTOSUB_COMPLETED"
                    else:
                        meta["status"] = "AUTOSUB_FAILED"
                    meta["updated_at"] = datetime.datetime.now().isoformat()
                    self.storage_mgr.write_story_meta(story_name, meta)

        if story_name:
            story_meta = self.storage_mgr.read_story_meta(story_name)
            if story_meta:
                story_meta["status"] = "AUTOSUB_RUNNING"
                story_meta["updated_at"] = datetime.datetime.now().isoformat()
                self.storage_mgr.write_story_meta(story_name, story_meta)

        return self.process_mgr.start_process(
            task_key=task_key,
            cmd=cmd,
            cwd="AIVoice",
            on_completed=on_autosub_completed
        )

    def start_step_5_merge(self, story_name: str, selected_files: list[str] | None = None) -> bool:
        """Merges specific or all story chapter videos in a background thread."""
        import queue as _q
        import threading
        import time
        import contextlib
        
        meta = self.storage_mgr.read_story_meta(story_name)
        if not meta:
            return False
            
        task_key = f"{meta['story_slug']}_step5"
        q = _q.Queue()
        self.process_mgr.log_queues[task_key] = q
        
        video_dir = os.path.join(self.storage_mgr.get_story_dir(story_name), "video")
        out = os.path.join(video_dir, f"TongHop_{time.strftime('%Y%m%d_%H%M%S')}.mp4")
        
        class QueueWriter:
            def __init__(self, queue):
                self.queue = queue
            def write(self, message):
                if message.strip():
                    self.queue.put(message.strip() + "\n")
            def flush(self):
                pass
                
        def _run():
            try:
                from orchestrator.video_merger import merge_videos
                q.put(f"[SYSTEM] Bắt đầu ghép video vào {out}...\n")
                
                writer = QueueWriter(q)
                with contextlib.redirect_stdout(writer):
                    ok = merge_videos(video_dir, out, only_files=selected_files)
                    
                q.put("[SYSTEM] Ghép video thành công!\n" if ok
                      else "[SYSTEM] Ghép thất bại — xem chi tiết phía trên.\n")
            except Exception as e:
                q.put(f"[ERROR] {e}\n")
            finally:
                q.put(None)
                
        threading.Thread(target=_run, daemon=True).start()
        return True
