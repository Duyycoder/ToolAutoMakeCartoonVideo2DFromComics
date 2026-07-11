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

        python_exe = os.path.abspath("AIVoice/.venv/Scripts/python.exe")
        adapter_path = os.path.abspath("AIVoice/adapter_tts_cli.py")

        cmd = [
            python_exe, adapter_path,
            "--input-dir", tts_input_dir,
            "--output-dir", tts_input_dir,
            "--engine", tts_args.get("engine", "edge"),
            "--voice", tts_args.get("voice", "vi-VN-NamMinhNeural"),
            "--speed", str(tts_args.get("speed", 1.0)),
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
        if tts_args.get("normalize", True):
            cmd.append("--normalize")
        else:
            cmd.append("--no-normalize")
        if tts_args.get("use_cache", False):
            cmd.append("--use-cache")
        else:
            cmd.append("--no-cache")
        if tts_args.get("cache_threshold") is not None:
            cmd += ["--cache-threshold", str(tts_args["cache_threshold"])]
        if tts_args.get("vieneu_mode"):
            cmd += ["--vieneu-mode", str(tts_args["vieneu_mode"])]
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

        cmd = [
            python_exe, adapter_path,
            "--story-name", story_name,
            "--genre", video_args.get("genre", "tien_hiep"),
            "--input-dir", video_input_dir,
            "--output-dir", video_output_dir,
            "--style", video_args.get("style", "anime_2d_flat"),
            "--checkpoint", video_args.get("checkpoint") or "anything-v5",
            "--bgm-path", video_args.get("bgm_path") or "",
            "--bgm-volume", str(video_args.get("bgm_volume") if video_args.get("bgm_volume") is not None else 0.15)
        ]
        if video_args.get("enable_upscale", True):
            cmd.append("--enable-upscale")
        else:
            cmd.append("--no-upscale")
        if video_args.get("burn_subtitles", True):
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
            
        if video_args.get("enable_face_detailer", True):
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
