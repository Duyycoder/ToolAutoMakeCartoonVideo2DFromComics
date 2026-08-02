# Bước 1 — Cào & Dịch / AI Sáng Tác

## Nguồn nhập nội dung
Tại tab Bước 1, người dùng có thể chọn 3 nguồn dữ liệu:
1. **Cào Web (Crawler):** Nhập link truyện từ các trang hỗ trợ để tự động tải về.
2. **Thư mục cục bộ (Local folder):** Chọn thư mục máy tính chứa sẵn các file văn bản (.txt, .md).
3. **AI Sáng Tác (Story Writer):** Nhập chủ đề và thể loại để LLM tự viết truyện tiếng Việt từ đầu.

## Bộ máy dịch (LLM Engine)
Hệ thống hỗ trợ 3 bộ máy xử lý ngôn ngữ:
- **Gemini Online:** Dùng Google Gemini API (cần API Key). Nhanh, chất lượng cao, 0 tốn VRAM.
- **Local Gemini Proxy:** Dùng proxy cục bộ cổng 7860.
- **Ollama (Local):** Chạy model LLM cục bộ cổng 11434 (ví dụ `qwen2.5:3b-instruct`). Khuyên dùng cho máy offline.

## Glossary — Quản lý thuật ngữ
Hỗ trợ thay thế từ ngữ Hán Việt hoặc dịch sai bằng bảng glossary. File glossary được lưu theo từng truyện để đảm bảo nhất quán tên nhân vật và địa danh.
