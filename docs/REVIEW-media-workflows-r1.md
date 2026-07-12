# REVIEW R1 — Nghiệm thu Media Workflows: KHÔNG ĐẠT (7 lỗi phải sửa)

> Người review đã kiểm tra TRỰC TIẾP code (không dựa vào walkthrough), chạy lại `py_compile` + `pytest` (11/11 pass) và inspect signature thư viện trong venv thật.
> **Nguyên nhân gốc lọt lỗi:** kiểm thử chỉ chạy `--prepare-only` — nhánh workflow đầy đủ (Whisper/OCR) CHƯA TỪNG được chạy.
>
> **Quy tắc sửa:** chỉ sửa đúng 7 mục dưới đây, KHÔNG refactor gì thêm. Sửa xong task nào tick task đó. BUG-1/2/6 nằm trong submodule `AIVoice` (commit ở repo con trước, rồi cập nhật con trỏ ở repo tổng). BUG-3/4/5/7 ở repo tổng.

---

## 🔴 BUG-1 (CHẶN) — ImportError vỡ toàn bộ Bước 4 workflow thật

**File:** `AIVoice/apps/MediaComposer/adapter_autosub_cli.py:113-114`

```python
# HIỆN TẠI (SAI — class MediaComposer không tồn tại):
from app.services.composer import MediaComposer
composer = MediaComposer()
```

`composer.py` chỉ định nghĩa `class ComposerWorkflow` và singleton `composer = ComposerWorkflow()` (dòng 461).

**Sửa thành (dùng singleton, giống webui/Main.py:2744):**
```python
from app.services.composer import composer
```
(xoá dòng `composer = MediaComposer()`).

**Nghiệm thu:** chạy adapter với `--sub-source whisper` trên video ngắn → không ImportError, ra file `*_autosub_*.mp4`.

---

## 🔴 BUG-2 (CHẶN) — Sai tên tham số videocr → TypeError, vỡ 100% chế độ OCR

**File:** `AIVoice/apps/MediaComposer/app/services/subtitle_extractor.py:94-96`

Signature THẬT đã inspect từ `.venv` (`inspect.signature`):
```
save_subtitles_to_file(video_path: str, file_path='subtitle.srt', lang='ch', time_start='0:00',
    time_end='', conf_threshold=75, sim_threshold=80, use_fullframe=False, det_model_dir=None,
    rec_model_dir=None, use_gpu=False, brightness_threshold=None, similar_image_threshold=100,
    similar_pixel_threshold=25, frames_to_skip=1, crop_x=None, crop_y=None, crop_width=None, crop_height=None)
```

→ `file_path` là **đường dẫn SRT ĐẦU RA**, tham số `subtitle_path` **KHÔNG tồn tại**.

```python
# HIỆN TẠI (SAI):
kwargs = {
    "file_path": video_path,        # ← video bị coi là SRT output; nếu chạy được sẽ GHI ĐÈ SRT LÊN VIDEO
    "subtitle_path": output_srt,    # ← TypeError: unexpected keyword argument
    ...
}

# SỬA THÀNH:
kwargs = {
    "video_path": video_path,
    "file_path": output_srt,
    ...
}
```
Các key còn lại (`lang`, `time_start`, `time_end`, `conf_threshold`, `sim_threshold`, `use_fullframe`, `use_gpu`, `crop_x/crop_y/crop_width/crop_height`) đều khớp signature — giữ nguyên.

**Nghiệm thu:** chạy adapter `--sub-source ocr --crop-...` trên video hardsub tiếng Trung ngắn → ra `ocr_subtitles.srt` có nội dung + mốc thời gian; file video KHÔNG bị ghi đè.

---

## 🟠 BUG-3 (TRUNG BÌNH) — task_key lệch giữa main.py và pipeline → SSE trắng, không Stop được (Bước 4 độc lập)

**File:** `orchestrator/pipeline.py:398` và `orchestrator/main.py:338,346-347`

- main.py sinh `task_id` → trả UI `task_key = f"autosub_{task_id}_step4"` và truyền `autosub_args["task_id"] = task_id`.
- pipeline.py:398 **tự sinh `task_id = uuid.uuid4().hex[:8]` MỚI**, không đọc `autosub_args["task_id"]` → process đăng ký dưới key khác → UI mở SSE + Stop bằng key không tồn tại.

**Sửa (pipeline.py):**
```python
# THAY dòng: task_id = uuid.uuid4().hex[:8]
task_id = autosub_args.get("task_id") or uuid.uuid4().hex[:8]
```

**Nghiệm thu:** POST `/api/pipeline/step4` KHÔNG kèm `story_name` → mở SSE `/api/pipeline/logs/<task_key trả về>` thấy log chảy (không phải "No active log queue found"); Stop hoạt động.

---

## 🟠 BUG-4 (TRUNG BÌNH) — stop-task không bao giờ cập nhật status truyện

**File:** `orchestrator/main.py:474-477`

`storage_mgr.list_stories()` trả **list[dict] meta**, nhưng vòng lặp gọi `storage_mgr.read_story_meta(s)` với `s` là dict → bên trong `slugify(dict)` → AttributeError → bị `except Exception: pass` nuốt → meta không bao giờ được set `CANCELLED`.

**Sửa:**
```python
for s in stories:
    if s.get("story_slug") == slug:
        story_name = s.get("story_name")
        meta = storage_mgr.read_story_meta(story_name)
        if meta:
            meta["status"] = "CANCELLED"
            storage_mgr.write_story_meta(story_name, meta)
        break
```

**Nghiệm thu:** chạy step4 gắn truyện → stop-task → `storage/truyen/<slug>/story.json` có `"status": "CANCELLED"`.

---

## 🟡 BUG-5 (NHỎ) — Dead code trong video_merger.py

**File:** `orchestrator/video_merger.py:79-80` — cặp `print(...)/return True` thứ hai nằm SAU `return True` (không bao giờ chạy). Xoá 2 dòng 79-80.

---

## 🟡 BUG-6 (NHỎ) — `--prepare-only` vẫn load faster-whisper + torch ở finally

**File:** `AIVoice/apps/MediaComposer/adapter_autosub_cli.py:167-179`

`sys.exit(0)` ở nhánh prepare vẫn chạy `finally` → `from app.services.subtitle import release_whisper_model` (kéo faster_whisper + app.config→torch) + `import torch` → prepare chậm thêm nhiều giây vô ích, ngược yêu cầu "prepare-only nhẹ".

**Sửa:** bọc thân finally:
```python
finally:
    if not args.prepare_only:
        try:
            from app.services.subtitle import release_whisper_model
            release_whisper_model()
        except Exception:
            pass
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass
        gc.collect()
```
(Lưu ý: `args` phải đã parse trước khối try — hiện đúng như vậy, dòng 45.)

**Nghiệm thu:** đo thời gian chạy `--prepare-only` trên video local nhỏ giảm rõ so với trước (không còn độ trễ import torch).

---

## 🟡 BUG-7 (NHỎ) — Server chưa clamp crop trong biên ảnh (plan yêu cầu)

**File:** `orchestrator/main.py` (endpoint step4) hoặc `orchestrator/pipeline.py` (khối crop dòng 470-480).

Hiện chỉ check `>= 0` / `> 0`. Thêm clamp phòng UI gửi lệch (không có width/height ở server → clamp mức tối thiểu):
```python
crop_x = max(0, crop_x); crop_y = max(0, crop_y)
crop_w = max(0, crop_w); crop_h = max(0, crop_h)
```
(Đủ dùng — biên trên đã được UI quy đổi từ kích thước gốc; videocr tự chịu crop vượt biên nhẹ.)

---

## Sau khi sửa xong — nghiệm thu lại BẮT BUỘC (theo thứ tự)

1. `python -m py_compile` mọi file đã sửa (cả 2 repo); `pytest -q` repo tổng vẫn 11/11.
2. **End-to-end Whisper:** Bước 4, video tiếng Anh ngắn (~1-2 phút), link YouTube hoặc local → video ra có phụ đề **TIẾNG VIỆT** (mở xem bằng mắt — CB2 là lỗi im lặng: nếu key sai, sub vẫn ra nhưng là tiếng gốc).
3. **End-to-end OCR:** Bước 4, video hardsub tiếng Trung → Tải & Xem trước → vẽ ROI → chạy → sub tiếng Việt; xác nhận log `ocr_roi` in đúng toạ độ đã vẽ.
4. **Bước 4 độc lập (không chọn truyện):** SSE hiển thị log + nút Dừng hoạt động (BUG-3).
5. **Bước 5:** chọn ≥2 video chương → `TongHop_*.mp4` phát liền mạch; chạy lần 2 không gộp file TongHop cũ.
6. Sau khi mọi thứ pass: commit submodule AIVoice trước → cập nhật con trỏ + commit repo tổng.
