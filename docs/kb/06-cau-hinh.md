# Cấu Hình Toàn Cục & Cấu Hình Trợ Lý

## Nhập hoặc đổi API key Gemini ở đâu?
Mở tab **Cấu Hình Chung** trên giao diện, mục **🔑 API & Kết Nối**, ô
**"Gemini API Key (dùng chung mọi bước)"**. Nhập xong bấm **Lưu cấu hình**.
Key này dùng chung cho mọi bước, không cần nhập lại ở từng bước.

## Cấu hình toàn cục được lưu vào file nào?
`configs/global_config.json`. File này bị `.gitignore` loại trừ nên key thật không
bao giờ bị commit. Bản mẫu không chứa key là `configs/config.example.json`.

## Khác nhau giữa global_config.json và ui_settings.json?
- `configs/global_config.json`: giá trị mặc định của hệ thống, do tab **Cấu Hình
  Chung** ghi. Các bước lấy giá trị này khi bạn chưa chọn gì khác.
- `configs/ui_settings.json`: trạng thái form bạn đang điền trên giao diện (truyện
  đang chọn, lựa chọn từng bước), khôi phục lại khi mở app lần sau.

## Đổi thư mục lưu trữ dữ liệu sang ổ khác thế nào?
Sửa khoá `storage_dir` trong `configs/global_config.json`. Mặc định là `storage`.
Dữ liệu nặng (chương truyện, giọng đọc, video) nằm trong thư mục này.

## Cấu hình Trợ lý AI nằm ở đâu và gồm những gì?
Tab **Cấu Hình Chung**, mục **🤖 Trợ Lý AI**. Các khoá trong khối `chatbot`:
- `enabled`: bật/tắt trợ lý.
- `model`: tên model Ollama trợ lý dùng.
- `share_model_with_step3`: dùng chung model với Bước 3 để đỡ nạp/nhả nhiều model.
- `block_when_busy`: chặn hỏi khi GPU đang chạy tác vụ nặng.
- `auto_unload_before_pipeline`: tự nhả trợ lý khỏi VRAM khi pipeline khởi động.
- `autostart_ollama`: tự bật Ollama nếu cổng 11434 chưa mở.
- `kb_token_budget`: số token tài liệu nạp mỗi lượt, mặc định 3000.
- `kb_min_score`: ngưỡng điểm tối thiểu; dưới ngưỡng trợ lý từ chối thay vì đoán.
- `max_sessions`: số phiên chat giữ trong RAM, mặc định 20.
- `session_ttl_minutes`: thời gian giữ một phiên, mặc định 120 phút.

## Màu badge trên nút trợ lý nghĩa là gì?
- Xanh: trợ lý sẵn sàng, Ollama đang chạy.
- Vàng: GPU đang bận chạy tác vụ nặng, trợ lý chuyển sang chế độ tra cứu tài liệu.
- Xám: Ollama chưa chạy hoặc chưa tải model.

## Trợ lý trả lời được những gì?
Chỉ hai nhóm: cách vận hành công cụ này, và dữ liệu truyện đang có trong thư mục
`storage`. Ngoài hai nhóm đó, trợ lý trả lời "tài liệu hiện có không đề cập" thay
vì suy đoán.
