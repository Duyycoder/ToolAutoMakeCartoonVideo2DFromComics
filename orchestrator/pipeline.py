import os
import datetime
from orchestrator.storage import StorageManager
from orchestrator.process_manager import ProcessManager


def _resolve_ai_write_args(crawl_args: dict, trans_args: dict) -> dict:
    """Suy ra tham số LLM cho nguồn 'ai_write' từ crawl/trans args.

    Dùng chung cho endpoint Bước 1 lẻ và chuỗi auto-run để chỉ có MỘT nơi quyết
    định engine/base_url/model — tránh lệch hành vi giữa hai lối chạy.
    """
    from .config import load_global_config
    g = load_global_config()
    engine = (trans_args.get("engine") or "").lower()
    if engine == "ollama":
        base_url = g.get("crawler", {}).get("ollama_base_url", "http://localhost:11434/v1")
        model = trans_args.get("ollama_model") or "qwen2.5:7b-instruct"
        api_key = ""
    else:
        base_url = trans_args.get("gemini_offline_base_url") or g.get("crawler", {}).get(
            "gemini_offline_base_url", "http://localhost:7860/v1")
        model = trans_args.get("gemini_offline_model") or "gemini-2.5-flash"
        api_key = trans_args.get("gemini_api_key") or g.get("api_keys", {}).get("gemini", "")
    return {
        "base_url": base_url, "model": model, "api_key": api_key,
        "topic": (crawl_args.get("topic") or "").strip(),
        "num_chapters": crawl_args.get("num_chapters") or 1,
        "genre": trans_args.get("genre") or "",
    }


class NovelPipeline:
    def __init__(self, storage_mgr: StorageManager, process_mgr: ProcessManager):
        self.storage_mgr = storage_mgr
        self.process_mgr = process_mgr

    def _resolve_llm(self, llm_engine: str, args: dict, g_config: dict, default_model: str) -> tuple[str, str, str]:
        from .llm import resolve_llm
        return resolve_llm(llm_engine, args, g_config, default_model)

    def _finalize_video_task(self, story_name: str, video_output_dir: str,
                             task_key: str, exit_code: int) -> bool:
        """Merge output và chỉ công bố VIDEO_GENERATED khi có video thật."""
        meta = self.storage_mgr.read_story_meta(story_name)
        if not meta:
            return False

        success = False
        if exit_code == 0:
            import time
            from orchestrator.video_merger import merge_videos

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(
                video_output_dir, f"TongHop_{timestamp}.mp4")
            q = self.process_mgr.log_queues.get(task_key)
            if q:
                q.put(f"\n[SYSTEM] Đang hợp nhất video vào {output_file}...\n")
            success = merge_videos(video_output_dir, output_file)
            if q:
                q.put(
                    "[SYSTEM] Đã hợp nhất video thành công!\n" if success
                    else "[SYSTEM] Lỗi khi hợp nhất video.\n")

        if success:
            meta["status"] = "VIDEO_GENERATED"
        elif self.process_mgr.was_user_stopped(task_key):
            meta["status"] = "CANCELLED"
        else:
            meta["status"] = "VIDEO_FAILED"
        if success:
            meta["pipeline_step"] = 3
        meta["updated_at"] = datetime.datetime.now().isoformat()
        self.storage_mgr.write_story_meta(story_name, meta)
        return success

    def start_step_1_crawl_translate(self, story_name: str, crawl_args: dict, trans_args: dict) -> bool:
        """Runs crawl subcommand, and on success, triggers translate subcommand."""
        story_meta = self.storage_mgr.read_story_meta(story_name)
        if not story_meta:
            return False

        # Nguồn "Sáng tác bằng AI" đi cùng entry point này để cả endpoint lẻ lẫn
        # chuỗi auto-run đều chạy đúng (sinh truyện bằng LLM thay vì cào/dịch).
        if crawl_args.get("source") == "ai_write":
            return self.start_ai_write(
                story_name, _resolve_ai_write_args(crawl_args, trans_args))

        story_dir = self.storage_mgr.get_story_dir(story_name)
        raw_dir = os.path.join(story_dir, "raw")

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

        def finish_step1(exit_code: int):
            self.process_mgr.mark_completed(task_key, exit_code)
            q = self.process_mgr.log_queues.get(task_key)
            if q:
                q.put(None)

        def on_translate_completed(exit_code: int):
            meta = self.storage_mgr.read_story_meta(story_name)
            if not meta:
                return
            if exit_code == 0:
                meta["status"] = "TRANSLATED"
                meta["pipeline_step"] = 2
            elif self.process_mgr.was_user_stopped(task_key):
                meta["status"] = "CANCELLED"
            else:
                meta["status"] = "TRANSLATE_FAILED"
            meta["updated_at"] = datetime.datetime.now().isoformat()
            self.storage_mgr.write_story_meta(story_name, meta)

        def on_crawl_completed(exit_code: int):
            meta = self.storage_mgr.read_story_meta(story_name)
            if not meta:
                finish_step1(1)
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
                    started = self.process_mgr.start_process(
                        task_key=task_key,
                        cmd=translate_cmd,
                        cwd="toolCaoTruyen",
                        on_completed=on_translate_completed,
                        close_queue_on_exit=True,
                        reuse_queue=True
                    )
                    if not started:
                        meta["status"] = "TRANSLATE_FAILED"
                        meta["updated_at"] = datetime.datetime.now().isoformat()
                        self.storage_mgr.write_story_meta(story_name, meta)
                        q = self.process_mgr.log_queues.get(task_key)
                        if q:
                            q.put("[Pipeline] Không thể khởi động tiến trình dịch.\n")
                        finish_step1(1)
                else:
                    meta["status"] = "CRAWLED"
                    meta["updated_at"] = datetime.datetime.now().isoformat()
                    self.storage_mgr.write_story_meta(story_name, meta)
                    finish_step1(0)
            else:
                meta["status"] = ("CANCELLED"
                                  if self.process_mgr.was_user_stopped(task_key)
                                  else "CRAWL_FAILED")
                meta["updated_at"] = datetime.datetime.now().isoformat()
                self.storage_mgr.write_story_meta(story_name, meta)
                finish_step1(exit_code or 1)

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
            import queue as _q
            import threading
            import shutil
            local_queue = _q.Queue()
            if not self.process_mgr.register_manual_task(task_key, local_queue):
                return False

            def _copy_local():
                # Gọi on_crawl_completed đúng MỘT lần: tách phần copy (có thể lỗi)
                # khỏi callback hoàn tất để callback không bị chạy lại khi nó ném lỗi.
                local_dir = crawl_args.get("local_folder")
                exit_code = 1
                try:
                    if local_dir and os.path.exists(local_dir):
                        copied = 0
                        for item in os.listdir(local_dir):
                            if item.endswith(".md") or item.endswith(".txt"):
                                shutil.copy2(os.path.join(local_dir, item), os.path.join(raw_dir, item))
                                copied += 1
                        if copied:
                            exit_code = 0
                        else:
                            local_queue.put(
                                "[Pipeline] Không tìm thấy file .md/.txt trong thư mục cục bộ.\n")
                    else:
                        local_queue.put(
                            "[Pipeline] Thư mục cục bộ không tồn tại.\n")
                except Exception as e:
                    local_queue.put(
                        f"[Pipeline] Lỗi khi copy thư mục cục bộ: {e}\n")
                    exit_code = 1
                on_crawl_completed(exit_code)
            threading.Thread(target=_copy_local, daemon=True).start()
            return True

    def start_ai_write(self, story_name: str, ai_args: dict) -> bool:
        """Sáng tác truyện bằng LLM cục bộ (nguồn 'ai_write').

        Chạy bằng thread (tác vụ I/O gọi LLM, không dùng GPU) qua cơ chế manual task.
        Nội dung sinh ra là tiếng Việt nên bỏ qua bước dịch → chuyển thẳng sang bước TTS.
        """
        import threading
        import queue as _queue

        story_meta = self.storage_mgr.read_story_meta(story_name)
        if not story_meta:
            return False
        story_dir = self.storage_mgr.get_story_dir(story_name)
        raw_dir = os.path.join(story_dir, "raw")
        os.makedirs(raw_dir, exist_ok=True)
        task_key = f"{story_meta['story_slug']}_step1"

        q = _queue.Queue()
        if not self.process_mgr.register_manual_task(task_key, q):
            return False

        story_meta["status"] = "WRITING"
        story_meta["updated_at"] = datetime.datetime.now().isoformat()
        self.storage_mgr.write_story_meta(story_name, story_meta)

        def _run():
            from orchestrator import story_writer
            try:
                q.put("[Pipeline] Bắt đầu sáng tác truyện bằng LLM cục bộ...\n")
                n = story_writer.generate_story(
                    base_url=ai_args["base_url"], model=ai_args["model"],
                    api_key=ai_args.get("api_key", ""), topic=ai_args["topic"],
                    num_chapters=int(ai_args.get("num_chapters", 1) or 1),
                    out_dir=raw_dir, genre=ai_args.get("genre", ""),
                    progress=lambda m: q.put(m + "\n"),
                )
                meta = self.storage_mgr.read_story_meta(story_name)
                if meta:
                    meta["status"] = "TRANSLATED"  # nội dung đã là tiếng Việt
                    meta["pipeline_step"] = 2
                    meta["updated_at"] = datetime.datetime.now().isoformat()
                    self.storage_mgr.write_story_meta(story_name, meta)
                q.put(f"[Pipeline] Đã sáng tác {n} chương (tiếng Việt).\n")
                self.process_mgr.mark_completed(task_key, 0)
            except Exception as e:
                meta = self.storage_mgr.read_story_meta(story_name)
                if meta:
                    meta["status"] = "WRITE_FAILED"
                    meta["updated_at"] = datetime.datetime.now().isoformat()
                    self.storage_mgr.write_story_meta(story_name, meta)
                q.put(f"[ERROR] Sáng tác thất bại: {e}\n")
                self.process_mgr.mark_completed(task_key, 1)
            finally:
                q.put(None)

        threading.Thread(target=_run, daemon=True).start()
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
            elif self.process_mgr.was_user_stopped(task_key):
                meta["status"] = "CANCELLED"
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

        # Áp tham số sinh ảnh từ Cấu Hình Chung xuống config.toml của MediaComposer
        # TRƯỚC khi spawn tiến trình con — tiến trình đọc config lúc khởi động, ghi
        # sau đó là không kịp. Best-effort: lỗi thì vẫn chạy với cấu hình cũ.
        try:
            from orchestrator import mediacomposer_config
            from orchestrator.config import load_global_config as _load_cfg
            mediacomposer_config.apply_sd_params(_load_cfg().get("video", {}))
        except Exception as e:
            print(f"[WARN] Không áp được tham số sinh ảnh: {e}")

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
        resolved_key, resolved_base_url, resolved_model = self._resolve_llm(
            llm_engine, video_args, g_config, video_cfg.get("default_llm_model")
        )

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

        # Studio Compositing: "classic" (1 anh/canh) | "studio" (render theo lop roi ghep)
        render_mode = video_args.get("render_mode") or "classic"
        cmd.extend(["--render-mode", render_mode])

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
            return self._finalize_video_task(
                story_name, video_output_dir, task_key, exit_code)

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
            default_output_dir = os.path.join(self.storage_mgr.get_story_dir(story_name), "video")
            task_key = f"{slug}_step4"
        else:
            default_output_dir = os.path.join(self.storage_mgr.tasks_dir, f"autosub_{task_id}")
            task_key = f"autosub_{task_id}_step4"

        python_exe = os.path.abspath("AIVoice/.venv/Scripts/python.exe")
        adapter_path = os.path.abspath("AIVoice/apps/MediaComposer/adapter_autosub_cli.py")

        from orchestrator.config import load_global_config
        g_config = load_global_config()
        video_cfg = g_config.get("video", {})
        autosub_cfg = g_config.get("autosub", {})

        # Thư mục đầu ra: ưu tiên yêu cầu -> Cấu Hình Chung -> mặc định (video truyện / tác vụ tạm).
        # Video tải về (tạm) và video đã gắn sub đều nằm ở đây (adapter dùng chung --output-dir).
        output_dir = (autosub_args.get("output_dir") or autosub_cfg.get("output_dir") or "").strip() or default_output_dir
        os.makedirs(output_dir, exist_ok=True)
        ocr_use_gpu = autosub_args.get("ocr_use_gpu")
        if ocr_use_gpu is None:
            ocr_use_gpu = video_cfg.get("ocr_use_gpu", True)
        
        # Resolve LLM parameters for translation
        llm_engine = autosub_args.get("llm_engine") or video_cfg.get("default_llm_engine") or "gemini_api"
        resolved_key, resolved_base_url, resolved_model = self._resolve_llm(
            llm_engine, autosub_args, g_config, video_cfg.get("default_llm_model")
        )
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

        if ocr_use_gpu:
            cmd.append("--use-gpu")

        def on_autosub_completed(exit_code: int):
            if story_name:
                meta = self.storage_mgr.read_story_meta(story_name)
                if meta:
                    if exit_code == 0:
                        meta["status"] = "AUTOSUB_COMPLETED"
                    elif self.process_mgr.was_user_stopped(task_key):
                        meta["status"] = "CANCELLED"
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
        if not self.process_mgr.register_manual_task(task_key, q):
            return False
        
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
            ok = False
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
                self.process_mgr.mark_completed(task_key, 0 if ok else 1)
                q.put(None)
                
        threading.Thread(target=_run, daemon=True).start()
        return True
