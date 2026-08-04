# Gặp thông báo lỗi này thì làm gì

> Sinh tự động bằng `scripts/gen_kb_faq.py` — các câu thông báo lấy thẳng từ
> mã nguồn nên luôn khớp đúng chữ hiện trên màn hình. Sửa cách khắc phục thì
> sửa bảng `REMEDIES` trong script rồi chạy lại.

## Chuỗi tự động đang chạy cho truyện này

Thông báo trên màn hình:
- *Chuỗi tự động đang chạy cho truyện này — bấm 'Dừng chuỗi' trước.*

**Nguyên nhân:** Bạn đã bấm 'Chạy tự động 1→4' cho truyện này, nên các nút chạy từng bước bị khoá để hai luồng không giẫm lên nhau.

**Cách sửa:** Bấm **Dừng chuỗi** ở đầu trang, đợi trạng thái đổi, rồi mới chạy bước lẻ.

## Không lưu được cấu hình chung

Thông báo trên màn hình:
- *Failed to save global configuration.*
- *Không lưu được cấu hình.*
- *Không lưu được cấu hình: *

**Nguyên nhân:** Không ghi được `configs/global_config.json` — thường do thiếu quyền ghi hoặc file đang bị chương trình khác mở.

**Cách sửa:** Đóng file nếu đang mở bằng editor. Nếu cài trong `Program Files`, chạy ứng dụng với quyền quản trị hoặc chuyển thư mục cài sang ổ khác.

## Chưa nhập tên truyện

Thông báo trên màn hình:
- *Story name cannot be empty.*

**Nguyên nhân:** Ô tên truyện đang để trống khi bấm Tạo truyện mới.

**Cách sửa:** Nhập một tên bất kỳ (tiếng Việt có dấu được) rồi bấm lại.

## Không tìm thấy truyện

Thông báo trên màn hình:
- *Story '{story_name}' not found.*

**Nguyên nhân:** Truyện đã bị xoá khỏi thư mục `storage/truyen/`, hoặc tên gõ vào không khớp.

**Cách sửa:** Chọn lại truyện ở danh sách bên trái. Nếu vừa xoá thủ công, bấm **Đồng bộ lại CSDL** ở tab Thống Kê.

## Bước này đang chạy rồi

Thông báo trên màn hình:
- *A TTS process is already active for this story.*
- *A crawl/translate process is already active for this story.*
- *A video generation process is already active for this story.*

**Nguyên nhân:** Một tiến trình cùng loại vẫn đang chạy cho truyện này.

**Cách sửa:** Đợi nó xong, hoặc bấm nút **Dừng** của đúng bước đó trước khi chạy lại.

## Chưa nhập chủ đề cho AI sáng tác

Thông báo trên màn hình:
- *Vui lòng nhập chủ đề/ý tưởng để AI sáng tác truyện.*

**Nguyên nhân:** Nguồn truyện đang chọn là 'Sáng tác bằng AI' nhưng ô ý tưởng còn trống.

**Cách sửa:** Gõ vài câu mô tả ý tưởng truyện vào ô chủ đề, rồi chạy lại Bước 1.

## Không khởi động được bước xử lý

Thông báo trên màn hình:
- *Failed to start pipeline Step 1.*
- *Failed to start pipeline Step 2.*
- *Failed to start pipeline Step 3.*

**Nguyên nhân:** Tiến trình con không chạy được — hay gặp nhất là chưa chạy `setup.bat`, thiếu môi trường ảo, hoặc thiếu model AI.

**Cách sửa:** Mở `logs/app.log` xem dòng lỗi cuối. Nếu là máy mới, chạy `setup.bat` cho đủ trước.

## Không tìm thấy tiến trình để dừng

Thông báo trên màn hình:
- *No active running task found for key '{task_key}'.*

**Nguyên nhân:** Tiến trình đã tự kết thúc trước khi bạn kịp bấm Dừng.

**Cách sửa:** Không cần làm gì. Tải lại trang để giao diện đồng bộ trạng thái mới.

## Không có chuỗi tự động nào đang chạy

Thông báo trên màn hình:
- *Không có chuỗi tự động nào đang chạy cho truyện này.*

**Nguyên nhân:** Bạn bấm Dừng chuỗi khi chuỗi đã kết thúc.

**Cách sửa:** Bỏ qua thông báo này. Tải lại trang nếu nút vẫn hiển thị sai.

## Không lưu được cấu hình giao diện

Thông báo trên màn hình:
- *Không ghi được configs/ui_settings.json.*

**Nguyên nhân:** Cùng nguyên nhân với lỗi lưu cấu hình chung: thiếu quyền ghi vào thư mục `configs/`.

**Cách sửa:** Kiểm tra quyền ghi của thư mục cài đặt, hoặc đóng chương trình đang giữ file.

## Chưa chỉ định video đầu vào

Thông báo trên màn hình:
- *Cần cung cấp video_path hoặc download_url.*

**Nguyên nhân:** Công cụ phụ đề cần một video: hoặc file có sẵn trên máy, hoặc link để tải.

**Cách sửa:** Điền đường dẫn file `.mp4` trên máy, hoặc dán link video rồi bấm **Tải & Xem trước**.

## Tiến trình Tự Động Tạo Phụ Đề đang chạy

Thông báo trên màn hình:
- *Tiến trình Autosub đang chạy cho truyện/tác vụ này.*

**Nguyên nhân:** Công cụ phụ đề đang xử lý một video khác.

**Cách sửa:** Đợi xong hoặc bấm Dừng ở khung Tự Động Tạo Phụ Đề.

## Không khởi tạo được bước xử lý

Thông báo trên màn hình:
- *Không khởi tạo được pipeline Bước 4.*
- *Không khởi tạo được pipeline Bước 5.*

**Nguyên nhân:** Giống lỗi trên: thiếu môi trường hoặc tham số đầu vào không hợp lệ.

**Cách sửa:** Kiểm tra `logs/app.log`, và xác nhận đã chọn truyện cùng đầy đủ tham số của bước.

## Tải video quá lâu và bị huỷ

Thông báo trên màn hình:
- *Tải/chuẩn bị video quá 15 phút — kiểm tra link hoặc mạng.*

**Nguyên nhân:** Quá 15 phút mà video chưa tải xong — thường do mạng chậm, link hỏng, hoặc video quá dài.

**Cách sửa:** Kiểm tra lại link, thử tải thủ công rồi trỏ vào file trên máy. Video dài nên tải sẵn trước.

## Chuẩn bị video thất bại

Thông báo trên màn hình:
- *Không nhận được phản hồi prepare_done. Log: {err_msg}*
- *Lỗi chuẩn bị: ${err.message}*
- *Lỗi prepare_only: {err_msg}*

**Nguyên nhân:** Bước tải/cắt video không trả về kết quả — link hỏng, mạng đứt, hoặc video có định dạng FFmpeg không đọc được.

**Cách sửa:** Thử tải video thủ công rồi trỏ vào file trên máy. Xem `logs/app.log` để biết FFmpeg báo gì.

## Không tạo được ảnh xem trước

Thông báo trên màn hình:
- *Không tạo được ảnh xem trước.*

**Nguyên nhân:** FFmpeg không đọc được file video (hỏng, tải dở, hoặc định dạng lạ).

**Cách sửa:** Mở thử video bằng trình phát khác. Nếu không phát được thì tải lại; nếu phát được, thử chuyển sang `.mp4` chuẩn.

## Tiến trình Ghép Video đang chạy

Thông báo trên màn hình:
- *Tiến trình Ghép Video đang chạy.*

**Nguyên nhân:** Bước 4 (Ghép Video) chưa kết thúc.

**Cách sửa:** Đợi tiến trình hiện tại xong rồi ghép tiếp.

## Truyện không tồn tại

Thông báo trên màn hình:
- *Truyện không tồn tại.*

**Nguyên nhân:** Thư mục truyện đã bị xoá hoặc đổi tên bên ngoài ứng dụng.

**Cách sửa:** Chọn lại truyện khác, rồi bấm **Đồng bộ lại CSDL** ở tab Thống Kê để dọn mục cũ.

## Trợ lý AI đang bị tắt

Thông báo trên màn hình:
- *Trợ lý AI đang bị tắt trong Cấu Hình Chung.*

**Nguyên nhân:** Khoá `chatbot.enabled` trong cấu hình đang để `false`.

**Cách sửa:** Vào tab **Cấu Hình Chung**, mục Trợ Lý AI, bật lại rồi bấm Lưu cấu hình.

## Trợ lý đang bận trả lời

Thông báo trên màn hình:
- *Trợ lý đang trả lời câu trước.*

**Nguyên nhân:** Mỗi lần chỉ phục vụ được một câu hỏi để không nạp hai lượt vào GPU cùng lúc.

**Cách sửa:** Đợi câu trả lời hiện tại xong, hoặc bấm nút **Dừng** rồi hỏi lại.

## Model trợ lý không được hỗ trợ

Thông báo trên màn hình:
- *Model '{body.model}' không nằm trong danh sách hỗ trợ.*

**Nguyên nhân:** Tên model gửi lên không có trong danh sách model đã kiểm định cho trợ lý.

**Cách sửa:** Chọn model từ ô **Model** ngay trên khung trợ lý thay vì gõ tay.

## Chưa chọn truyện

Thông báo trên màn hình:
- *Vui lòng chọn truyện trước!*

**Nguyên nhân:** Hầu hết thao tác cần biết đang làm việc với truyện nào.

**Cách sửa:** Chọn một truyện ở danh sách bên trái, hoặc bấm **+ Tạo truyện mới**.

## Thông báo dạng “… : <chi tiết>”

Thông báo trên màn hình:
- *Không chạy được chuỗi tự động: ${data.detail}*
- *Không thể dừng tiến trình: *
- *Lỗi khi dừng tiến trình: *
- *Lỗi khi lưu cấu hình: *
- *Lỗi khi tạo truyện mới: ${res.detail || *
- *Lỗi khi xóa cache.*
- *Lỗi khởi chạy: ${err.detail}*
- *Lỗi mạng khi tạo truyện mới: *

**Nguyên nhân:** Đây chỉ là lớp vỏ hiển thị. Phần sau dấu hai chấm mới là lỗi thật.

**Cách sửa:** Đọc phần sau dấu hai chấm rồi tra đúng mục tương ứng trong tài liệu này. Nếu nội dung đó cũng không rõ, mở `logs/app.log` xem dòng cuối cùng.

## Lỗi kết nối tới server

Thông báo trên màn hình:
- *Lỗi kết nối tới Server: *
- *Lỗi kết nối tới server: *

**Nguyên nhân:** Giao diện không gọi được orchestrator ở cổng 8100 — thường do cửa sổ ứng dụng còn mở nhưng tiến trình nền đã tắt.

**Cách sửa:** Đóng hẳn ứng dụng rồi mở lại bằng `run.bat`. Nếu vẫn lỗi, chạy `run.bat debug` để xem console báo gì.

## Chưa nhập đường dẫn video

Thông báo trên màn hình:
- *Vui lòng nhập đường dẫn video cục bộ!*
- *Vui lòng nhập đường dẫn video!*

**Nguyên nhân:** Đang chọn nguồn video cục bộ nhưng ô đường dẫn để trống.

**Cách sửa:** Dán đường dẫn đầy đủ tới file `.mp4` trên máy, ví dụ `D:\\video\\tap1.mp4`.

## Chưa nhập link video

Thông báo trên màn hình:
- *Vui lòng nhập link video hoặc chuẩn bị video trước!*
- *Vui lòng nhập link video tải về!*

**Nguyên nhân:** Đang chọn nguồn tải về nhưng chưa dán link.

**Cách sửa:** Dán link video vào ô, rồi bấm **Tải & Xem trước**.

## Chế độ OCR chưa có video để đọc

Thông báo trên màn hình:
- *Chế độ OCR yêu cầu chuẩn bị video trước bằng nút *

**Nguyên nhân:** OCR đọc chữ cháy sẵn trên khung hình nên phải có video cục bộ trước khi chạy.

**Cách sửa:** Bấm **Tải & Xem trước** để chuẩn bị video, rồi mới chọn chế độ OCR.

## Chọn chưa đủ video để ghép

Thông báo trên màn hình:
- *Vui lòng chọn ít nhất 2 video để ghép!*

**Nguyên nhân:** Bước 4 (Ghép Video) cần từ hai video trở lên mới có gì để nối.

**Cách sửa:** Tích chọn ít nhất hai file trong danh sách video của truyện rồi bấm ghép.
