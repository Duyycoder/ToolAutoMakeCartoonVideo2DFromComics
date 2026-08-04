"""Sinh KB "gặp thông báo lỗi này thì làm gì" từ chính thông báo trong mã nguồn.

Vì sao không viết tay toàn bộ: câu chữ thông báo đổi theo code, viết tay sẽ lệch
và trợ lý sẽ mô tả một thông báo không còn tồn tại. Script rút thẳng chuỗi từ
`detail=...` (backend) và `alert(...)` (giao diện), rồi ghép với bảng cách-sửa
viết tay bên dưới.

Chuỗi khớp bằng `match` (một đoạn con ổn định), nên đổi chữ quanh nó vẫn khớp.
Thông báo chưa có cách sửa sẽ được liệt kê ở cuối bản in để biết còn thiếu gì.

Chạy:
    AIVoice\\.venv\\Scripts\\python.exe scripts/gen_kb_faq.py
"""
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "docs", "kb", "09-thong-bao-loi.md")

PY_FILES = ["orchestrator/main.py", "orchestrator/pipeline.py",
            "orchestrator/auto_run.py", "orchestrator/storage.py"]
JS_FILES = ["webui/app.js"]

# (đoạn khớp, tiêu đề, nguyên nhân, cách sửa)
REMEDIES = [
    ("Chuỗi tự động đang chạy",
     "Chuỗi tự động đang chạy cho truyện này",
     "Bạn đã bấm 'Chạy tự động 1→4' cho truyện này, nên các nút chạy từng bước bị khoá để hai luồng không giẫm lên nhau.",
     "Bấm **Dừng chuỗi** ở đầu trang, đợi trạng thái đổi, rồi mới chạy bước lẻ."),
    ("already active for this story",
     "Bước này đang chạy rồi",
     "Một tiến trình cùng loại vẫn đang chạy cho truyện này.",
     "Đợi nó xong, hoặc bấm nút **Dừng** của đúng bước đó trước khi chạy lại."),
    ("Tiến trình Autosub đang chạy",
     "Tiến trình Tự Động Tạo Phụ Đề đang chạy",
     "Công cụ phụ đề đang xử lý một video khác.",
     "Đợi xong hoặc bấm Dừng ở khung Tự Động Tạo Phụ Đề."),
    ("Tiến trình Ghép Video đang chạy",
     "Tiến trình Ghép Video đang chạy",
     "Bước 4 (Ghép Video) chưa kết thúc.",
     "Đợi tiến trình hiện tại xong rồi ghép tiếp."),
    ("Story name cannot be empty",
     "Chưa nhập tên truyện",
     "Ô tên truyện đang để trống khi bấm Tạo truyện mới.",
     "Nhập một tên bất kỳ (tiếng Việt có dấu được) rồi bấm lại."),
    ("not found",
     "Không tìm thấy truyện",
     "Truyện đã bị xoá khỏi thư mục `storage/truyen/`, hoặc tên gõ vào không khớp.",
     "Chọn lại truyện ở danh sách bên trái. Nếu vừa xoá thủ công, bấm **Đồng bộ lại CSDL** ở tab Thống Kê."),
    ("Vui lòng nhập chủ đề",
     "Chưa nhập chủ đề cho AI sáng tác",
     "Nguồn truyện đang chọn là 'Sáng tác bằng AI' nhưng ô ý tưởng còn trống.",
     "Gõ vài câu mô tả ý tưởng truyện vào ô chủ đề, rồi chạy lại Bước 1."),
    ("Cần cung cấp video_path hoặc download_url",
     "Chưa chỉ định video đầu vào",
     "Công cụ phụ đề cần một video: hoặc file có sẵn trên máy, hoặc link để tải.",
     "Điền đường dẫn file `.mp4` trên máy, hoặc dán link video rồi bấm **Tải & Xem trước**."),
    ("quá 15 phút",
     "Tải video quá lâu và bị huỷ",
     "Quá 15 phút mà video chưa tải xong — thường do mạng chậm, link hỏng, hoặc video quá dài.",
     "Kiểm tra lại link, thử tải thủ công rồi trỏ vào file trên máy. Video dài nên tải sẵn trước."),
    ("Không tạo được ảnh xem trước",
     "Không tạo được ảnh xem trước",
     "FFmpeg không đọc được file video (hỏng, tải dở, hoặc định dạng lạ).",
     "Mở thử video bằng trình phát khác. Nếu không phát được thì tải lại; nếu phát được, thử chuyển sang `.mp4` chuẩn."),
    ("Failed to save global configuration",
     "Không lưu được cấu hình chung",
     "Không ghi được `configs/global_config.json` — thường do thiếu quyền ghi hoặc file đang bị chương trình khác mở.",
     "Đóng file nếu đang mở bằng editor. Nếu cài trong `Program Files`, chạy ứng dụng với quyền quản trị hoặc chuyển thư mục cài sang ổ khác."),
    ("Không ghi được configs/ui_settings.json",
     "Không lưu được cấu hình giao diện",
     "Cùng nguyên nhân với lỗi lưu cấu hình chung: thiếu quyền ghi vào thư mục `configs/`.",
     "Kiểm tra quyền ghi của thư mục cài đặt, hoặc đóng chương trình đang giữ file."),
    ("No active running task found",
     "Không tìm thấy tiến trình để dừng",
     "Tiến trình đã tự kết thúc trước khi bạn kịp bấm Dừng.",
     "Không cần làm gì. Tải lại trang để giao diện đồng bộ trạng thái mới."),
    ("Không có chuỗi tự động nào đang chạy",
     "Không có chuỗi tự động nào đang chạy",
     "Bạn bấm Dừng chuỗi khi chuỗi đã kết thúc.",
     "Bỏ qua thông báo này. Tải lại trang nếu nút vẫn hiển thị sai."),
    ("Failed to start pipeline",
     "Không khởi động được bước xử lý",
     "Tiến trình con không chạy được — hay gặp nhất là chưa chạy `setup.bat`, thiếu môi trường ảo, hoặc thiếu model AI.",
     "Mở `logs/app.log` xem dòng lỗi cuối. Nếu là máy mới, chạy `setup.bat` cho đủ trước."),
    ("Không khởi tạo được pipeline",
     "Không khởi tạo được bước xử lý",
     "Giống lỗi trên: thiếu môi trường hoặc tham số đầu vào không hợp lệ.",
     "Kiểm tra `logs/app.log`, và xác nhận đã chọn truyện cùng đầy đủ tham số của bước."),
    ("Lỗi kết nối tới",
     "Lỗi kết nối tới server",
     "Giao diện không gọi được orchestrator ở cổng 8100 — thường do cửa sổ ứng dụng còn mở nhưng tiến trình nền đã tắt.",
     "Đóng hẳn ứng dụng rồi mở lại bằng `run.bat`. Nếu vẫn lỗi, chạy `run.bat debug` để xem console báo gì."),
    ("Vui lòng chọn truyện trước",
     "Chưa chọn truyện",
     "Hầu hết thao tác cần biết đang làm việc với truyện nào.",
     "Chọn một truyện ở danh sách bên trái, hoặc bấm **+ Tạo truyện mới**."),
    ("Vui lòng chọn ít nhất 2 video",
     "Chọn chưa đủ video để ghép",
     "Bước 4 (Ghép Video) cần từ hai video trở lên mới có gì để nối.",
     "Tích chọn ít nhất hai file trong danh sách video của truyện rồi bấm ghép."),
    ("Chế độ OCR yêu cầu chuẩn bị video trước",
     "Chế độ OCR chưa có video để đọc",
     "OCR đọc chữ cháy sẵn trên khung hình nên phải có video cục bộ trước khi chạy.",
     "Bấm **Tải & Xem trước** để chuẩn bị video, rồi mới chọn chế độ OCR."),
    ("Vui lòng nhập đường dẫn video",
     "Chưa nhập đường dẫn video",
     "Đang chọn nguồn video cục bộ nhưng ô đường dẫn để trống.",
     "Dán đường dẫn đầy đủ tới file `.mp4` trên máy, ví dụ `D:\\\\video\\\\tap1.mp4`."),
    ("Vui lòng nhập link video",
     "Chưa nhập link video",
     "Đang chọn nguồn tải về nhưng chưa dán link.",
     "Dán link video vào ô, rồi bấm **Tải & Xem trước**."),
    ("Trợ lý AI đang bị tắt",
     "Trợ lý AI đang bị tắt",
     "Khoá `chatbot.enabled` trong cấu hình đang để `false`.",
     "Vào tab **Cấu Hình Chung**, mục Trợ Lý AI, bật lại rồi bấm Lưu cấu hình."),
    ("Trợ lý đang trả lời câu trước",
     "Trợ lý đang bận trả lời",
     "Mỗi lần chỉ phục vụ được một câu hỏi để không nạp hai lượt vào GPU cùng lúc.",
     "Đợi câu trả lời hiện tại xong, hoặc bấm nút **Dừng** rồi hỏi lại."),
    ("không nằm trong danh sách hỗ trợ",
     "Model trợ lý không được hỗ trợ",
     "Tên model gửi lên không có trong danh sách model đã kiểm định cho trợ lý.",
     "Chọn model từ ô **Model** ngay trên khung trợ lý thay vì gõ tay."),
    ("Truyện không tồn tại",
     "Truyện không tồn tại",
     "Thư mục truyện đã bị xoá hoặc đổi tên bên ngoài ứng dụng.",
     "Chọn lại truyện khác, rồi bấm **Đồng bộ lại CSDL** ở tab Thống Kê để dọn mục cũ."),
    ("Không lưu được cấu hình",
     "Không lưu được cấu hình chung",
     "Không ghi được `configs/global_config.json` — thường do thiếu quyền ghi hoặc file đang bị chương trình khác mở.",
     "Đóng file nếu đang mở bằng editor. Nếu cài trong `Program Files`, chạy ứng dụng với quyền quản trị hoặc chuyển thư mục cài sang ổ khác."),
    ("prepare_done",
     "Chuẩn bị video thất bại",
     "Bước tải/cắt video không trả về kết quả — link hỏng, mạng đứt, hoặc video có định dạng FFmpeg không đọc được.",
     "Thử tải video thủ công rồi trỏ vào file trên máy. Xem `logs/app.log` để biết FFmpeg báo gì."),
    ("prepare_only",
     "Chuẩn bị video thất bại",
     "Bước tải/cắt video không trả về kết quả — link hỏng, mạng đứt, hoặc video có định dạng FFmpeg không đọc được.",
     "Thử tải video thủ công rồi trỏ vào file trên máy. Xem `logs/app.log` để biết FFmpeg báo gì."),
    ("Lỗi chuẩn bị",
     "Chuẩn bị video thất bại",
     "Bước tải/cắt video không trả về kết quả — link hỏng, mạng đứt, hoặc video có định dạng FFmpeg không đọc được.",
     "Thử tải video thủ công rồi trỏ vào file trên máy. Xem `logs/app.log` để biết FFmpeg báo gì."),
    # Các thông báo dạng vỏ bọc: chữ phía trước cố định, lỗi thật nằm sau dấu hai chấm.
    ("Lỗi khi", "Thông báo dạng “… : <chi tiết>”", None, None),
    ("Lỗi khởi chạy", "Thông báo dạng “… : <chi tiết>”", None, None),
    ("Lỗi mạng", "Thông báo dạng “… : <chi tiết>”", None, None),
    ("Không thể dừng tiến trình", "Thông báo dạng “… : <chi tiết>”", None, None),
    ("Không chạy được chuỗi tự động", "Thông báo dạng “… : <chi tiết>”", None, None),
]

# Nội dung dùng chung cho nhóm vỏ bọc ở trên.
WRAPPER_CAUSE = "Đây chỉ là lớp vỏ hiển thị. Phần sau dấu hai chấm mới là lỗi thật."
WRAPPER_FIX = (
    "Đọc phần sau dấu hai chấm rồi tra đúng mục tương ứng trong tài liệu này. "
    "Nếu nội dung đó cũng không rõ, mở `logs/app.log` xem dòng cuối cùng."
)

# Không phải lỗi — không đưa vào FAQ.
SUCCESS_PREFIXES = ("Đã ",)


def extract(paths, pattern) -> list:
    found = []
    for rel in paths:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            continue
        with open(p, "r", encoding="utf-8") as f:
            src = f.read()
        for msg in re.findall(pattern, src):
            found.append((os.path.basename(rel), msg))
    return found


def main():
    msgs = extract(PY_FILES, r'detail=f?"([^"]{12,})"')
    msgs += extract(JS_FILES, r'alert\(\s*[`"\']([^`"\']{12,})')

    msgs = [(s, m) for s, m in msgs if not m.startswith(SUCCESS_PREFIXES)]

    matched, unmatched = {}, []
    for _src, msg in msgs:
        hit = next((r for r in REMEDIES if r[0] in msg), None)
        if hit:
            matched.setdefault(hit[1], {"remedy": hit, "samples": set()})["samples"].add(msg)
        else:
            unmatched.append(msg)

    lines = [
        "# Gặp thông báo lỗi này thì làm gì",
        "",
        "> Sinh tự động bằng `scripts/gen_kb_faq.py` — các câu thông báo lấy thẳng từ",
        "> mã nguồn nên luôn khớp đúng chữ hiện trên màn hình. Sửa cách khắc phục thì",
        "> sửa bảng `REMEDIES` trong script rồi chạy lại.",
        "",
    ]
    for title, data in matched.items():
        _m, _t, cause, fix = data["remedy"]
        cause = cause or WRAPPER_CAUSE
        fix = fix or WRAPPER_FIX
        lines.append(f"## {title}")
        lines.append("")
        lines.append("Thông báo trên màn hình:")
        for s in sorted(data["samples"]):
            lines.append(f"- *{s}*")
        lines.append("")
        lines.append(f"**Nguyên nhân:** {cause}")
        lines.append("")
        lines.append(f"**Cách sửa:** {fix}")
        lines.append("")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    total = len(msgs)
    covered = sum(len(d["samples"]) for d in matched.values())
    print(f"Đã ghi {OUT}")
    print(f"  {len(matched)} mục FAQ, phủ {covered}/{total} thông báo ({covered/total*100:.0f}%)")
    if unmatched:
        print(f"  Chưa có cách sửa cho {len(set(unmatched))} thông báo:")
        for m in sorted(set(unmatched))[:12]:
            print(f"    - {m[:80]}")


if __name__ == "__main__":
    main()
    sys.exit(0)
