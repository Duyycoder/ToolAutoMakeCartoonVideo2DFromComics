# REVIEW R3 — iQiyi/Cookies + Tùy chỉnh phụ đề + rà lỗi cũ

> Review trực tiếp diff: AIVoice `32f69e7..5d47352`, repo tổng `7c24e5d..91b7ad1`. Đã chạy `pytest` (11/11 ✅), `py_compile` toàn bộ file đổi (✅), và kiểm tra runtime trong `.venv` (yt-dlp 2026.07.04, iqiyi extractor tồn tại, phantomjs.exe, danh sách font).
>
> **Kết luận nhanh:** Không có lỗi crash. Cookies nối đủ + bảo mật đúng. **NHƯNG tính năng chọn Font (mục nổi bật nhất bạn vừa thêm) sẽ ÂM THẦM KHÔNG ÁP DỤNG** với font đi kèm app — đây là finding #1 phải sửa. Ngoài ra iQiyi/phantomjs đang gắn ở chỗ dễ vỡ, và vài lỗi nhỏ ở style.

---

## 🔴 F1 (CHỨC NĂNG — quan trọng nhất) — Font tùy chỉnh không áp dụng vì thiếu `fontsdir`

**File:** `AIVoice/apps/MediaComposer/app/services/video.py` — `burn_subtitles_ffmpeg` (dòng ~1578 & ~1591).

**Vấn đề:** Nhánh burn mặc định (`burn_method="ffmpeg"`) dùng filter `subtitles=...:force_style='FontName=...'`. libass phân giải `FontName` qua **fontconfig hệ thống**, KHÔNG biết thư mục `resource/fonts` của app. Đã xác minh `grep fontsdir` trong video.py → **không có**; `fontsdir` chỉ dùng ở nhánh moviepy (`generate_video`, dòng 934), KHÔNG dùng ở ffmpeg.

**Hệ quả thực tế:** Các font đi kèm KHÔNG cài sẵn trên Windows — `Montserrat` (đang là **option mặc định được chọn**!), `Be Vietnam Pro`, `Charm`, `UTM Kabel KT` — sẽ bị libass fallback về font mặc định. Người dùng chọn font, log báo thành công, nhưng video ra **sai font** mà không có cảnh báo. (Arial/Microsoft YaHei/STHeiti có thể may mắn có sẵn trên Windows nên "đôi khi đúng" — càng dễ hiểu nhầm là đã chạy.)

**Cách sửa (thêm `fontsdir` trỏ vào `utils.font_dir()`, escape kiểu tương đối như `sub_filter_path`):**
```python
# ngay sau: sub_filter_path = rel_sub.replace("\\", "/")
from app.utils import utils  # nếu chưa import ở đầu file thì đã có utils sẵn
font_dir_abs = utils.font_dir()
try:
    rel_fonts = os.path.relpath(font_dir_abs, start=work_dir).replace("\\", "/")
except ValueError:
    rel_fonts = font_dir_abs.replace("\\", "/")   # khác ổ đĩa: dùng tuyệt đối (chấp nhận rủi ro escaping)
fonts_dir_opt = f":fontsdir={rel_fonts}"

# rồi ở CẢ HAI lệnh ffmpeg, đổi:
#   "-vf", f"subtitles={sub_filter_path}{force_style_str}"
# thành:
    "-vf", f"subtitles={sub_filter_path}{fonts_dir_opt}{force_style_str}",
```
**Nghiệm thu:** burn với `--font-name "UTM Kabel KT.ttf"` (font chắc chắn KHÔNG có trên Windows) → mở video thấy đúng nét chữ đó, không phải Arial mặc định.

> Lưu ý phụ: tên family trong `mapping` (video.py:1503-1518) phải khớp **tên family bên trong file font**, không phải tên file. `UTM Kabel KT` map thành chính nó — cần kiểm tên family thật của file `.ttf` (mở bằng ffprobe/nhìn thuộc tính). Nếu lệch, dù có fontsdir libass vẫn không khớp. Nên xác minh 1-2 font khi test F1.

---

## 🟠 I1 (iQiyi — hoạt động nhưng DỄ VỠ) — phantomjs.exe nằm trong site-packages

**Hiện trạng đã xác minh:** `phantomjs.exe` được đặt trong `AIVoice/.venv/Lib/site-packages/imageio_ffmpeg/binaries/`, và `video_downloader.py:20-23` prepend thư mục ffmpeg vào `PATH` để yt-dlp tìm thấy. iqiyi extractor (`iqiyi`, `iq.com`) có tồn tại trong yt-dlp 2026.07.04.

**Vấn đề:**
1. **Không tái lập được:** venv bị `.gitignore` → phantomjs.exe KHÔNG được commit. Cài lại venv / `pip install --force imageio_ffmpeg` là **mất phantomjs** → iQiyi VIP hỏng âm thầm trên máy khác hoặc sau khi chạy lại `setup.bat`.
2. Đặt file lạ vào thư mục binaries của thư viện bên thứ ba là anti-pattern.

**Cách tối ưu hơn (khuyến nghị):**
- Chuyển `phantomjs.exe` vào thư mục ổn định thuộc dự án, ví dụ `AIVoice/apps/MediaComposer/third_party/phantomjs/phantomjs.exe` (hoặc `models/`), rồi trong `download_video` prepend **thư mục đó** vào PATH thay vì thư mục ffmpeg. Ưu điểm: không phụ thuộc vòng đời của imageio_ffmpeg, có thể tài liệu hoá cho `setup.bat` tải/giải nén về đúng chỗ.
- Vì file nhị phân lớn không nên commit thẳng, thêm bước tải phantomjs trong `setup.bat` (hoặc README ghi rõ đường dẫn cần đặt).
- **Kiểm tra thực tế cần làm:** nhiều URL `iq.com` (bản quốc tế) KHÔNG cần phantomjs; chỉ `iqiyi.com` (bản TQ) mới cần. Hãy test đúng loại URL bạn định dùng — nếu chỉ dùng iq.com, có thể KHÔNG cần phantomjs, giảm được cả gánh nặng này.

---

## 🟡 I2 (NHỎ) — Đường dẫn cookies phân giải theo cwd sai gốc

**File:** `AIVoice/apps/MediaComposer/app/services/video_downloader.py:69-74`

`abs_cookies_path = os.path.abspath(cookies_file)` — subprocess chạy `cwd="AIVoice"` nên đường dẫn tương đối phân giải theo `AIVoice/`. Nhưng placeholder ở UI Cấu hình chung gợi ý `configs/cookies_iqiyi.txt` (tương đối **repo gốc**). Người dùng nhập theo gợi ý → resolve thành `AIVoice/configs/cookies_iqiyi.txt` → không thấy → chỉ log `download_warning` rồi **tải tiếp không cookies → iQiyi VIP thất bại khó hiểu**.

**Cách sửa:** phân giải cookies theo **repo gốc** (2 cấp trên MediaComposer) khi là đường dẫn tương đối, hoặc đổi placeholder/tài liệu yêu cầu **đường dẫn tuyệt đối**. Tối thiểu: khi không tìm thấy cookies mà platform là iqiyi/bilibili → nâng cảnh báo rõ hơn (hoặc dừng) thay vì tải im lặng.

**Điểm tốt (không cần sửa):** `cookiefile` là opt yt-dlp chuẩn ✅; `.gitignore` có `*cookies*` + `**/cookies.json`, `git ls-files | grep cookie` = rỗng → không rò rỉ ✅; wiring UI (global `cfgDownloaderCookies` → `video.downloader_cookies`; per-URL `s4CookiesFile` override) đủ và đúng ✅.

---

## 🟡 S1 (NHỎ) — Giá trị 0 hợp lệ bị `|| null` nuốt mất

**File:** `webui/app.js:777,780,782`
```js
stroke_width: parseFloat(...) || null,   // stroke_width = 0 (bỏ viền) -> null -> quay về default 1.5
bg_alpha:     parseInt(...)  || null,     // bg_alpha = 0 (nền trong suốt) -> null -> quay về 140
custom_position: parseFloat(...) || null, // custom_position = 0 (sát mép trên) -> null
```
`0 || null === null` trong JS → người dùng KHÔNG thể đặt các giá trị 0 hợp lệ; server dùng default thay vì 0.

**Cách sửa:** thay bằng kiểm tra rỗng tường minh, ví dụ:
```js
stroke_width: (v => v === "" ? null : Number(v))(document.getElementById("s4StrokeWidth").value),
```
(áp dụng cho cả 3 field số có thể bằng 0).

---

## 🟡 S2 (NHỎ / KIỂM BẰNG MẮT) — Vị trí "custom" tính margin theo chiều cao cố định 360px

**File:** `video.py` (khối `position == "custom"`): `margin_v = int((100 - custom_y_ratio) * 3.6)`.
Hệ số 3.6 ⇒ giả định chiều cao video = 360px. Trên video 1080p, vị trí % yêu cầu sẽ lệch ~3x, và alignment vẫn neo đáy (align=2). Không crash. **Cần xem bằng mắt** khi test; nếu cần đúng %, tính MarginV theo chiều cao thật của video (lấy bằng moviepy như CB5) hoặc dùng `\pos` trong ASS. Ưu tiên thấp.

## 🟡 S3 (KIỂM BẰNG MẮT) — Hộp nền BorderStyle=3 + alpha
`bg_style="Box"` set cả `OutlineColour` lẫn `BackColour` = màu hộp, và ghép alpha bằng `replace("&H00", "&H{alpha}")`. Logic chuỗi ổn (đã rà: chỉ một tiền tố `&H` nên replace không đụng phần màu). Nhưng cách libass vẽ hộp ở BorderStyle=3 tuỳ renderer → **xem bằng mắt** xác nhận hộp + độ mờ đúng ý.

---

## Rà lỗi cũ (theo yêu cầu "kiểm tra code cũ")
- **BUG-7 (R2) vẫn là no-op:** clamp `max(0,…)` nằm trong khối `if crop_x>=0 …` nên vô tác dụng. Vô hại. (pipeline.py:474-480)
- **CB2 vẫn CHƯA nghiệm thu chức năng (mở từ R2):** đường dịch LLM chưa từng chạy với video có lời + proxy bật. Vẫn phải test E2E có tiếng nói và **nhìn mắt phụ đề tiếng Việt**. Xem [REVIEW-media-workflows-r2.md](REVIEW-media-workflows-r2.md).
- Không phát hiện crash mới; `pytest` 11/11, `py_compile` toàn bộ file đổi đều OK.

---

## Việc cần làm (ưu tiên giảm dần)
1. **F1** — thêm `fontsdir` vào filter subtitles (nếu không, tính năng chọn font coi như không có tác dụng). Sửa + test bằng font chắc chắn không có trên Windows.
2. **I1** — chuyển phantomjs.exe ra thư mục ổn định + PATH trỏ vào đó (hoặc xác nhận iq.com không cần phantomjs rồi bỏ). Đảm bảo tái lập được sau `setup.bat`.
3. **I2, S1** — sửa gốc phân giải cookies + bỏ `|| null` cho field số có thể bằng 0.
4. **S2, S3** — xem bằng mắt khi test E2E; chỉnh nếu lệch.
5. **CB2 (R2)** — nghiệm thu E2E dịch có tiếng nói (chưa xong).
