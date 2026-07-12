# REVIEW R2 — Media Workflows: CODE ĐẠT, nhưng NGHIỆM THU CHỨC NĂNG CHƯA HỢP LỆ

> Người review kiểm tra trực tiếp diff của cả submodule AIVoice (`83967ce..32f69e7`) và repo tổng (`790176d..ec35c09`), chạy lại `pytest` (11/11 ✅) + `py_compile` (✅), và inspect hành vi `translate_srt`/`parse_srt` trong `.venv` thật.

## Phần ĐẠT — 7 bản vá R1 đều đúng code

| Bug | Trạng thái | Ghi chú xác minh |
|---|---|---|
| BUG-1 | ✅ ĐÚNG | `from app.services.composer import composer` (singleton). Thêm `os.makedirs(output_dir)` trước copy — hợp lý. |
| BUG-2 | ✅ ĐÚNG | `video_path`/`file_path` khớp **chính xác** signature thật của `save_subtitles_to_file` đã inspect. |
| BUG-3 | ✅ ĐÚNG | `task_id = autosub_args.get("task_id") or uuid...` — task_key giờ khớp giữa main.py và pipeline.py. |
| BUG-4 | ✅ ĐÚNG | Duyệt `s.get("story_slug")` trên dict, đọc meta bằng `story_name` (str). |
| BUG-5 | ✅ ĐÚNG | Đã xoá dead code sau `return True`. |
| BUG-6 | ✅ ĐÚNG | `finally` bọc trong `if not args.prepare_only`. |
| BUG-7 | ⚠️ NO-OP | Clamp `max(0,…)` đặt BÊN TRONG khối `if crop_x>=0 and …` → điều kiện đã đảm bảo ≥0, nên clamp vô tác dụng. Vô hại, không cần sửa lại; nếu muốn đúng ý thì clamp phải nằm NGOÀI khối `if`. |

**2 thay đổi thêm (ngoài R1) — vị trí hợp lý, chấp nhận:**
- **Empty-subtitle fallback** (`composer.py:366-381`): đặt SAU `translate_srt`, TRƯỚC dubbing/burn → cover cả 2 nhánh whisper & OCR. Ghi dummy `1\n00:00:00,000 --> 00:00:01,000\n \n` khi SRT rỗng. **KHÔNG che giấu CB2** (lỗi CB2 tạo SRT *có nội dung* tiếng gốc, không rỗng → không rơi vào nhánh dummy). OK.
- **PaddleX oneDNN env** (`subtitle_extractor.py:2-5`): set ở đầu module, trước khi `videocr` được import lazy trong hàm → có hiệu lực. OK.

---

## 🔴 VẤN ĐỀ CHẶN NGHIỆM THU — "E2E Whisper" đã chạy là VÔ HIỆU

**Bằng chứng:**
- Video test `aqz-KE-bpKQ` = **Big Buck Bunny** — phim hoạt hình **KHÔNG có lời thoại** (chỉ nhạc/tiếng động vật).
- Đã xác minh trong `.venv`: `parse_srt('') → []`. Với video không lời, Whisper trả **0 segment** → `source_subtitles.srt` rỗng → `translate_srt` gặp `segments==[]` nên **short-circuit ở translation.py:65-70, KHÔNG hề gọi LLM dịch** → sau đó nhánh **dummy-subtitle mới toanh** ghi đè.
- Kết quả: bài test "E2E Whisper thành công" chỉ chứng minh **đúng cái fallback mà chính agent vừa thêm** không crash. Nó **chưa từng chạy qua**: (a) Whisper ra text thật, (b) dịch LLM, (c) burn phụ đề có chữ.

→ **CB2 — lỗi im lặng nguy hiểm nhất (sai key ⇒ phụ đề ra tiếng gốc mà log vẫn "thành công") — VẪN CHƯA ĐƯỢC KIỂM CHỨNG.** Đây đúng là hạng mục #1 mà R1 yêu cầu nghiệm thu bằng mắt.

**"E2E OCR" cũng chưa đủ:** walkthrough chỉ nói "processed frames successfully", KHÔNG xác nhận video ra có **phụ đề tiếng Việt**. Vì OCR cũng đi qua `translate_srt`, mà lúc review **Gemini proxy :7860 đang TẮT** (đã kiểm: `PROXY DOWN`). Nếu chạy OCR khi proxy tắt → `translate_srt` thiếu key → copy nguyên tiếng Trung (translation.py:73-77) → video ra sub tiếng Trung, KHÔNG phải tiếng Việt.

**Người review KHÔNG thể tự hoàn tất kiểm chứng dịch** vì proxy :7860 đang tắt và cần GPU/model. Cần bạn (hoặc agent) chạy lại theo đúng kịch bản dưới.

---

## Việc cần làm cho vòng nghiệm thu tiếp theo (R3)

1. **BẬT Gemini proxy trước:** `toolCaoTruyen/Gemini-API/start_server.bat` (hoặc chạy `run.bat`), xác nhận `http://localhost:7860/v1/models` trả 200.
2. **E2E Whisper CÓ LỜI (bắt buộc):** dùng video/clip **có tiếng nói tiếng Anh** dài ~1-2 phút (bất kỳ clip hợp pháp bạn có; KHÔNG dùng Big Buck Bunny). Chạy Bước 4 (Whisper, không voiceover) →
   - Mở video kết quả, **nhìn bằng mắt xác nhận phụ đề là TIẾNG VIỆT** (không phải tiếng Anh).
   - Kiểm tra KHÔNG thấy log `autosub_warn` "Bản dịch trùng bản gốc".
3. **E2E OCR có lời/chữ (bắt buộc):** video hardsub **tiếng Trung** ngắn → Tải & Xem trước → vẽ ROI → chạy → xác nhận: log `ocr_roi` in đúng toạ độ + phụ đề video ra **tiếng Việt**.
4. **Voiceover (nếu dùng):** bật 1 lần với engine `edge` để chắc nhánh lồng tiếng + ducking chạy (nhánh này cũng chưa test lần nào).
5. Chỉ khi cả 3 mục 2-4 pass bằng mắt → nghiệm thu ĐẠT. Không cần sửa code nếu pass (7 bug đã vá đúng); nếu mục 2 ra phụ đề tiếng Anh → quay lại soi CB2 (resolve key ở pipeline.py:427-440 + set `openai_*` ở adapter:88-93).

## Tuỳ chọn (không chặn)
- BUG-7: chuyển 4 dòng clamp ra NGOÀI khối `if` để thực sự có tác dụng (hoặc bỏ hẳn vì UI đã quy đổi biên).
