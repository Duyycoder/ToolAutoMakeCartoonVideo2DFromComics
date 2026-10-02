# 0. Cách dùng bộ câu hỏi

Bộ này gom các câu Hội đồng có thể hỏi, từ câu cực cơ bản (code ở đâu, SQL viết sao) đến câu xoáy. Nguồn: 15 chương của tài liệu ôn tập (bản dựng 30/09/2026) đối chiếu với mã nguồn repo. Mỗi câu có ý trả lời ngắn và chỗ tra lại.

- Mức: ★ gần như chắc bị hỏi · ★★ cần hiểu sâu · ★★★ câu xoáy, câu bẫy. Tra ở: `chXX` là chương trong tài liệu ôn tập; `tệp:dòng` là vị trí trong repo. Số dòng lấy theo bản dựng 30/09; các tệp `main.py` , `app.js` , `index.html` đã sửa sau đó nên có thể lệch vài dòng. Cách nói: câu đầu là kết luận, câu sau là số liệu + nguồn. Tự nêu hạn chế trước khi bị hỏi. Không biết thì nói sẽ kiểm tra ở tệp nào, không bịa.

Số liệu phải thuộc (nói số trong báo cáo đã nộp, bổ sung số mới nếu được hỏi):

- **Số liệu:** Test repo tổng · **Giá trị:** 173 passed / 21 tệp / 7,86 s (báo cáo); chạy lại 29/09: 178 passed / 22 tệp / 21,63 s; chạy lại 01/10: 223 passed / 26 tệp / 23,54 s · **Nguồn:** ch13
- **Số liệu:** Test MediaComposer (không cần GPU) · **Giá trị:** 136 passed / 44,25 s (chạy lại 01/10: 138 passed / 46,93 s) · **Nguồn:** ch13
- **Số liệu:** Rò chữ Hán sau dịch · **Giá trị:** 0 / 214.034 ký tự, 26 chương · **Nguồn:** Báo cáo 5.5
- **Số liệu:** Trợ lý AI truy xuất đúng · **Giá trị:** 25/28 = 89,3% (ngưỡng ≥ 80%, đạt) · **Nguồn:** Báo cáo 5.5, `scripts/eval_chatbot.py`
- **Số liệu:** Trợ lý AI từ chối ngoài phạm vi · **Giá trị:** 7/8 = 87,5% (ngưỡng ≥ 90%, chưa đạt) — đo trên bản trước 01/10; code hiện không còn từ chối cứng (xem 2.11.7) · **Nguồn:** Báo cáo 5.5
- **Số liệu:** VRAM đỉnh Bước 3 · **Giá trị:** ≈ 4,0 GB trên máy 6 GB · **Nguồn:** Báo cáo 5.4.2
- **Số liệu:** Thời gian Bước 3 · **Giá trị:** ≈ 2,6 phút cho video 45 s (≈ 3,47× thời lượng) · **Nguồn:** Báo cáo Bảng 5.4
- **Số liệu:** Thời gian TTS Piper · **Giá trị:** ≈ 2,7 phút/chương · **Nguồn:** Báo cáo Bảng 5.4
- **Số liệu:** Tham số SD mặc định · **Giá trị:** 8 bước, CFG 5.0, 768×432 → 1920×1080, 24 fps, IP- Adapter 0.6 · **Nguồn:** `orchestrator/config.py:14-27`
- **Số liệu:** Dữ liệu thử · **Giá trị:** 5 truyện, 32 chương (26 có audio, 3 có video) · **Nguồn:** Báo cáo 5.3
- **Số liệu:** Máy đo · **Giá trị:** Win 11, Python 3.11, i7- 12650H, RAM 15,6 GB, RTX 3060 Laptop 6 GB · **Nguồn:** Báo cáo Bảng 5.1
