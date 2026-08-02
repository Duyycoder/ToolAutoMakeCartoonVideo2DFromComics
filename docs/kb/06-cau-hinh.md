# Cấu Hình Toàn Cục & Cấu Hình Trợ Lý

## Cấu hình toàn cục (global_config)
Nằm tại tab **Cấu Hình Chung** trên WebUI (lưu vào `configs/config.json`). Bao gồm:
- `api_keys.gemini`: API Key cho Google Gemini.
- `crawler.ollama_base_url`: URL mặc định của Ollama (`http://localhost:11434/v1`).

## Cấu hình Trợ lý AI (Chatbot)
Khối `chatbot` điều khiển trợ lý hội thoại nổi trên WebUI:
- `enabled`: Bật/tắt trợ lý AI (mặc định `true`).
- `model`: Tên model Ollama cho trợ lý (khuyên dùng `qwen2.5:3b-instruct`).
- `share_model_with_step3`: Dùng chung model với Bước 3 nếu Bước 3 chọn engine Ollama.
- `block_when_busy`: Cảnh báo / chặn khi GPU đang chạy tác vụ nặng (`heavy`).
- `auto_unload_before_pipeline`: Tự nhả trợ lý khỏi VRAM khi pipeline khởi động.
- `autostart_ollama`: Tự khởi động Ollama server nếu cổng 11434 chưa mở.
- `kb_token_budget`: Số token KB tối đa nạp mỗi lượt là 3000 token.
- `max_sessions`: Số phiên chat tối đa lưu trong RAM là 20 phiên.
- `session_ttl_minutes`: Thời gian lưu phiên chat (TTL) là 120 phút.

## Trạng thái Badge Trợ Lý AI
Màu sắc của badge trên nút widget trợ lý:
- Màu xanh: Trợ lý sẵn sàng (Ready / Ollama online).
- Màu vàng: Trợ lý bận (Busy / GPU bận).
- Màu xám: Trợ lý ngoại tuyến (Offline / Ollama offline).

## Phạm vi hỗ trợ của Trợ Lý
Trợ lý chỉ trả lời hai nhóm nội dung: cách vận hành công cụ này, và dữ liệu truyện
đang có trong thư mục `storage`. Ngoài hai nhóm đó, trợ lý trả lời "tài liệu hiện
có không đề cập" thay vì suy đoán.
