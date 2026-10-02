# 7. Yêu cầu sửa nhỏ tại chỗ (live coding)

Cách làm chung: nói trước sẽ sửa tệp nào, sửa, rồi chứng minh bằng một trong ba cách — chạy test liên quan ( `AIVoice/.venv/Scripts/python.exe -m pytest -q` `tests/test_xxx.py` ), gọi API trong `http://127.0.0.1:8100/docs` , hoặc bấm thử trên giao diện. Sửa orchestrator thì phải khởi động lại app; sửa `webui/` chỉ cần Ctrl+F5. Những yêu cầu có bẫy "phải sửa hai chỗ" được đánh dấu ★★★.

## 7.1 Đổi cổng 8100 sang 8200
- **Mức:** ★★★
- **Sửa ở đâu:** `orchestrator/desktop.py:19` + `orchestrator/main.py:48`
- **Cách làm, lưu ý, kiểm chứng:** Đổi `PORT` VÀ danh sách `allow_origins` ; quên CORS thì cửa sổ vẫn chạy (cùng origin) nhưng gọi từ origin cũ bị chặn. `global_config.json` có `orchestrator_port` nhưng `desktop.py` đang hardcode.

## 7.2 Đổi ngưỡng khớp tài liệu của chatbot 0,75 → 0,6
- **Mức:** ★
- **Sửa ở đâu:** `configs/global_config.json` → `chatbot.kb_min_score` (hoặc tab Cấu hình)
- **Cách làm, lưu ý, kiểm chứng:** Không sửa code; kiểm bằng `scripts/eval_chatbot.py` xem QA/từ chối đổi ra sao.

## 7.3 Đổi giới hạn số từ mỗi chương sáng tác (200– 4.000)
- **Mức:** ★
- **Sửa ở đâu:** `orchestrator/pipeline.py:38-41`
- **Cách làm, lưu ý, kiểm chứng:** `max(200, min(4000, int(words)))` ; mặc định 800 ở `translate.words_per_chapter` . Thêm `min` / `max` cho ô nhập trong `index.html` .

## 7.4 Đổi kích thước chunk TTS 30 từ → 40
- **Mức:** ★
- **Sửa ở đâu:** `AIVoice/configs/default.json:17` ( `max_words` ); `AIVoice/src/utils/text.py:36`
- **Cách làm, lưu ý, kiểm chứng:** Giữ `max_chars` ≤ 240 nếu dùng XTTS (giới hạn ~250 ký tự). Test: `AIVoice` test chunk.

## 7.5 Đổi số bước / CFG / kích thước ảnh mặc định
- **Mức:** ★
- **Sửa ở đâu:** Tab Cấu hình → `global_config.json` ( `video.sd_*` ); mặc định code ở `orchestrator/config.py:14` `SD_TUNING_DEFAULTS` ; giới hạn ở `mediacomposer_config.pyLIMITS`
- **Cách làm, lưu ý, kiểm chứng:** Giá trị ngoài `LIMITS` bị kẹp. steps ≥ 15 tự chuyển DPM++ Karras và bỏ Hyper-SD.

## 7.6 Đổi âm lượng nhạc nền 0,15 → 0,1
- **Mức:** ★
- **Sửa ở đâu:** `global_config.jsonvideo.bgm_volume`
- **Cách làm, lưu ý, kiểm chứng:** Truyền xuống qua `--bgm-volume` (pipeline.py), ffmpeg `volume=` trong `video_assembler.py` .

## 7.7 Đổi tiền tố tên video tổng `TongHop_`
- **Mức:** ★★★
- **Sửa ở đâu:** `pipeline.py:123, 833` + `video_merger.py:8` + `main.py:911`
- **Cách làm, lưu ý, kiểm chứng:** Phải đổi cả bộ lọc trong `_select_files` , nếu không lần ghép sau sẽ ghép lồng cả video tổng cũ. Test: `tests/test_video_merger.py` .

## 7.8 Thêm một ô số liệu vào trang Thống kê (vd số chương đã có giọng)
- **Mức:** ★★
- **Sửa ở đâu:** `orchestrator/db.pystats()` + `webui/app.js` `loadStats` ( `:2101` )
- **Cách làm, lưu ý, kiểm chứng:** Thêm `"voices_done": scalar("SELECT` `COUNT(*) FROM chapters WHERE` `wav_path IS NOT NULL AND` `wav_path<>''")` , rồi hiển thị ở `loadStats` . Kiểm `GET /api/stats` .

## 7.9 Ghi lịch sử chạy vào bảng `jobs` (đang rỗng)
- **Mức:** ★★
- **Sửa ở đâu:** `orchestrator/pipeline.py` các `start_step_*` + callback `on_*_completed`
- **Cách làm, lưu ý, kiểm chứng:** Gọi `db.add_job` trước `start_process` , `db.finish_job` trong callback (mẫu bên dưới). Kiểm: chạy Bước 2, `SELECT * FROM` `jobs` .

## 7.10 Kiểm tên truyện không rỗng, tối đa 100 ký tự
- **Mức:** ★★
- **Sửa ở đâu:** `orchestrator/main.py:103CreateStorySchema`
- **Cách làm, lưu ý, kiểm chứng:** `story_name: str =` `Field(min_length=1, max_length=100)` → FastAPI tự trả 422. Hoặc kiểm tay trong route và `raise HTTPException(400)` .

## 7.11 Thêm API lấy danh sách chương của một truyện
- **Mức:** ★★
- **Sửa ở đâu:** `orchestrator/main.py`
- **Cách làm, lưu ý, kiểm chứng:** Route `GET` `/api/stories/{name}/chapters` trả `storage_mgr.scan_chapters(name)` ; 404 nếu không có `story.json` (mẫu bên dưới). Thử ở `/docs` .

## 7.12 Ghi `story.json` an toàn khi mất điện (atomic)
- **Mức:** ★★
- **Sửa ở đâu:** `orchestrator/storage.py:135write_story_meta`
- **Cách làm, lưu ý, kiểm chứng:** Ghi ra `story.json.tmp` rồi `os.replace(tmp, path)` (mẫu bên dưới). Test: `tests/test_storage.py` .

## 7.13 Tăng số dòng log giữ trên màn hình 4.000 → 10.000
- **Mức:** ★
- **Sửa ở đâu:** `webui/app.js:1321MAX_CONSOLE_LINES`
- **Cách làm, lưu ý, kiểm chứng:** Nhiều quá làm DOM phình, trang chậm.

## 7.14 Đổi chu kỳ PING 1 s → 5 s
- **Mức:** ★
- **Sửa ở đâu:** `orchestrator/process_manager.py:293` `q.get(timeout=1.0)`
- **Cách làm, lưu ý, kiểm chứng:** Đổi làm chậm phát hiện client ngắt và phát hiện task xong khi reconnect.

## 7.15 Thêm một loại sự kiện log mới hiển thị màu riêng
- **Mức:** ★★
- **Sửa ở đâu:** Worker: `log_json("ten_event", {...})` ; UI: `webui/app.jsstreamLogs` ( `:1343` ) thêm case
- **Cách làm, lưu ý, kiểm chứng:** Event không có case thì hiển thị thô.

## 7.16 Đổi giọng/engine TTS mặc định
- **Mức:** ★
- **Sửa ở đâu:** `global_config.jsontts.default_engine` , `tts.default_voice` ; option ở `webui/index.html`
- **Cách làm, lưu ý, kiểm chứng:** Engine offline nếu muốn demo không mạng (Piper).

## 7.17 Thêm một phong cách ảnh mới
- **Mức:** ★★
- **Sửa ở đâu:** `MC/resource/image_presets/<ten>.txt` (positive `---` negative) + option trong `index.html`
- **Cách làm, lưu ý, kiểm chứng:** Không sửa Python: preset được nạp theo tên; LLM bị cấm viết tag style nên style chỉ đến từ file này.

## 7.18 Thêm từ vào glossary cố định
- **Mức:** ★
- **Sửa ở đâu:** `global_glossary.json` (repo gốc) hoặc `raw/glossary.json` của truyện
- **Cách làm, lưu ý, kiểm chứng:** Glossary chỉ thêm key mới, không ghi đè — sửa tay thì có hiệu lực lần dịch sau.

## 7.19 Đổi ngưỡng VRAM chọn `cuda_high` 7 GB → 8 GB
- **Mức:** ★★
- **Sửa ở đâu:** `ST/hardware_adapter.py:58`
- **Cách làm, lưu ý, kiểm chứng:** Card 8 GB thực báo ~7,6 GiB, đặt 8,0 thì card 8 GB rơi về `cuda_low` — giải thích vì sao giữ 7,0.

## 7.20 Đổi ngưỡng tỷ lệ khớp từ khóa 40% của chatbot
- **Mức:** ★★
- **Sửa ở đâu:** `orchestrator/chatbot.py:321` ( `match_ratio <` `0.4` )
- **Cách làm, lưu ý, kiểm chứng:** Chạy lại `tests/test_chatbot*.py` và `scripts/eval_chatbot.py` (có test chống overfit stopwords).

## 7.21 Bỏ lần ghép trùng trong chạy tự động
- **Mức:** ★★
- **Sửa ở đâu:** `orchestrator/auto_run.py:13CHAIN_STEPS` hoặc `pipeline.py:109`
- **Cách làm, lưu ý, kiểm chứng:** Bỏ step5 khỏi chuỗi (step3 đã merge), hoặc thêm cờ không merge khi chạy từ chuỗi. Test: `tests/test_auto_run.py` .

## 7.22 Truyền API key qua biến môi trường thay vì tham số dòng lệnh
- **Mức:** ★★
- **Sửa ở đâu:** `pipeline.py` (chỗ thêm `--llm-api-key` / `--api-` `key` ) + adapter tương ứng
- **Cách làm, lưu ý, kiểm chứng:** Thêm vào `env_override` (vd `LLM_API_KEY` ), adapter đọc `os.environ` ; bỏ khỏi `cmd` .

## 7.23 Thêm hiệu ứng Ken Burns
- **Mức:** ★★
- **Sửa ở đâu:** `ST/video_assembler.py:117assemble_video`
- **Cách làm, lưu ý, kiểm chứng:** Thay concat ảnh tĩnh bằng mỗi cảnh một đoạn `zoompan=z='min(zoom+0.0008,1.15)':d=` `<frame>:s=1920x1080:fps=24` , nối bằng `xfade` . Nói được ý tưởng là đủ, không cần gõ hết tại chỗ.

## 7.24 Tắt upscale Real- ESRGAN để chạy nhanh
- **Mức:** ★
- **Sửa ở đâu:** `global_config.jsonvideo.enable_upscale`
- **Cách làm, lưu ý, kiểm chứng:** Truyền qua `--enable-upscale` ; tắt thì PIL resize.

## 7.25 Thêm tìm kiếm/sắp xếp truyện trên Dashboard
- **Mức:** ★★
- **Sửa ở đâu:** `db.pylist_stories` + `app.js`
- **Cách làm, lưu ý, kiểm chứng:** Thêm tham số `q` : `WHERE name LIKE ?` với `f"%{q}%"` (vẫn dùng `?` ), `ORDER BY` theo cột được chọn từ whitelist — không nối chuỗi tên cột từ người dùng.

## 7.26 Thêm xác nhận trước khi xóa truyện
- **Mức:** ★★
- **Sửa ở đâu:** `webui/app.js` (hàm gọi `DELETE` `/api/stories/{name}` )
- **Cách làm, lưu ý, kiểm chứng:** `if (!confirm(...)) return;` trước `fetch` . Backend đã chặn xóa khi truyện đang chạy (400).

## 7.27 Đổi số lần thử lại khi Edge TTS lỗi mạng
- **Mức:** ★
- **Sửa ở đâu:** `AIVoice/src/engines/edge.py:36-61`
- **Cách làm, lưu ý, kiểm chứng:** Retry 5 lần, backoff 2/5/10/15 s.

## 7.28 Đổi kích thước chunk dịch
- **Mức:** ★★
- **Sửa ở đâu:** `toolCaoTruyen/translator/ollama_translator.p` `y:67-101` ; tham số model ở `translator/registry.py`
- **Cách làm, lưu ý, kiểm chứng:** Chunk lớn hơn cần tăng `num_ctx` (tốn VRAM KV cache).

## 7.29 Đổi độ dài cảnh mục tiêu (20/40/60 s)
- **Mức:** ★★
- **Sửa ở đâu:** `ST/semantic_scene_splitter.pySCENE_MIN_SEC` , `SCENE_TARGET_SEC` , `SCENE_MAX_SEC`
- **Cách làm, lưu ý, kiểm chứng:** Trần số cảnh dùng hằng 30 s riêng trong `_normalize_ranges` . Test: `MC/tests/test_storytelling_smoke.py` .

## 7.30 Đổi render mode mặc định sang Studio
- **Mức:** ★★★
- **Sửa ở đâu:** `global_config.jsonvideo.render_mode` + `MC/app/config.py:86` + `MC/adapter_video_cli.py:101`
- **Cách làm, lưu ý, kiểm chứng:** Ba chỗ có mặc định; còn `Step3Schema` gửi "auto" thì pipeline không truyền cờ. Nói rõ vì sao đang để classic (coverage 0,003 với thủy mặc).

Mẫu 7.9 — ghi job cho Bước 2 ( `pipeline.py` , quanh `start_step_2_tts` ):

```
from orchestrator import db
job_id = db.add_job(self.storage_mgr.db_path, story_meta["story_slug"],
"step2")
```

```
def on_tts_completed(exit_code: int):
status = ("DONE" if exit_code == 0
else "CANCELLED" if self.process_mgr.was_user_stopped(task_key)
else "FAILED")
db.finish_job(self.storage_mgr.db_path, job_id, status, f"exit_code=
{exit_code}")
...  # giữ nguyên phần cập nhật story.json
```

Mẫu 7.11 — API danh sách chương ( `main.py` ):

```
@app.get("/api/stories/{story_name}/chapters")
def list_chapters(story_name: str):
if not storage_mgr.read_story_meta(story_name):
raise HTTPException(status_code=404, detail="Không tìm thấy truyện")
return {"chapters": storage_mgr.scan_chapters(story_name)}
```

Mẫu 7.12 — ghi `story.json` atomic ( `storage.pywrite_story_meta` ):

```
tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
json.dump(meta, f, indent=2, ensure_ascii=False)
f.flush()
os.fsync(f.fileno())
os.replace(tmp, path)  # đổi tên nguyên tử: file cũ hoặc file mới, không bao
giờ nửa vời
```
