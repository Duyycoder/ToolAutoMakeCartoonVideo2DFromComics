# 10. Quyển báo cáo, quy cách, tài liệu tham khảo, quá trình làm

Bản hiện hành: `KTPM_2022600930_DaoKhuongDuy_baocao_v2` (112 trang, 01/10/2026), 5 chương + Mở đầu, Kết luận, 28 tài liệu tham khảo. Thành viên hội đồng phản biện thường lật báo cáo và hỏi theo trang.

## 10.1 Bố cục báo cáo gồm gì?
- **Mức:** ★
- **Ý trả lời chính:** Ch.1 bài toán, thách thức, khoảng trống; Ch.2 cơ sở khoa học và pipeline; Ch.3 yêu cầu + thiết kế UML; Ch.4 hiện thực và ánh xạ mã nguồn; Ch.5 kiểm thử, đánh giá, lỗi tồn đọng.

## 10.2 Số liệu ở lý do chọn đề tài lấy từ đâu?
- **Mức:** ★
- **Ý trả lời chính:** CNNIC báo cáo lần thứ 55: 575 triệu người dùng văn học mạng tại Trung Quốc (12/2024), 51,9% người dùng Internet [27]. Viện KHXH Trung Quốc 2025: thị trường chuyển thể 367,61 tỷ NDT, +23,13% [28, qua Tân Hoa xã]. Luật BVDLCN 91/2025/QH15 có hiệu lực 01/01/2026 [5].

## 10.3 Vì sao dùng số liệu Trung Quốc cho đề tài ở Việt Nam? Em đọc được tài liệu tiếng Trung không?
- **Mức:** ★★
- **Ý trả lời chính:** Trung Quốc là thị trường nguồn của truyện mà hệ thống dịch sang tiếng Việt; chưa có số liệu tương đương của Việt Nam. Trả lời thật về cách đọc (bản dịch máy + đối chiếu con số trong bản gốc).

## 10.4 Mục tiêu cụ thể của đề tài? Đạt mục tiêu nào, chưa đạt mục tiêu nào?
- **Mức:** ★
- **Ý trả lời chính:** 6 mục tiêu (Mở đầu mục 2). Lưu ý mục tiêu 4 ghi "Storytelling Studio làm chế độ dựng chính" — Studio đã hiện thực nhưng chưa là mặc định (9.1.1), nên nói là đạt một phần.

## 10.5 Giả thuyết H1–H5 là gì, đã kiểm chứng chưa?
- **Mức:** ★★
- **Ý trả lời chính:** H1 Studio giảm xung đột nhiều nhân vật; H2 LoRA + IP-Adapter giảm trôi nhận dạng; H3 unify strength thấp không phá mặt; H4 lưu trạng thái theo bước giảm chi phí chạy lại; H5 tra cứu 0-VRAM duy trì hỗ trợ khi heavy. H4, H5 kiểm chứng một phần (TC05, TC14, TC15); H1–H3 chưa định lượng.

## 10.6 Vì sao đặt giả thuyết mà không kiểm chứng hết?
- **Mức:** ★★
- **Ý trả lời chính:** Nói thẳng: thiếu tập ảnh chuẩn và người chấm; báo cáo không điền số giả định. Cách kiểm H1: tỷ lệ cảnh qua gate, số lần fallback; H2: cosine CLIP giữa mặt các cảnh; H3: so trước/sau ở vài mức strength.

## 10.7 Chương 2 nhiều công thức mà thiếu bảng so sánh công nghệ?
- **Mức:** ★★
- **Ý trả lời chính:** Điểm trình bày đã biết. Chuẩn bị nói miệng lựa chọn và phương án thay thế: SD1.5 vs SDXL/Flux; Ollama vs API; IDF vs BM25 vs embedding; SSE vs WebSocket; SQLite vs PostgreSQL; JS thuần vs React (mục 2 và 4 của bộ này).

## 10.8 Quy cách trình bày theo quy định nào?
- **Mức:** ★
- **Ý trả lời chính:** Phụ lục 01 quy định ĐA/KLTN của trường: Times New Roman 14, dãn dòng 1,5, lề trên 2,5 / dưới 2 / trái 3,5 / phải 2 cm; mục tối đa 4 cấp; hình đánh số theo chương, chú thích dưới hình; bảng chú thích trên bảng.

## 10.9 Tài liệu tham khảo sắp xếp theo quy tắc gì? [1] là ai?
- **Mức:** ★★
- **Ý trả lời chính:** Tiếng Việt trước, tiếng Anh theo họ tác giả A–Z, tiếng Trung để cuối (CNNIC [27], Tân Hoa xã [28]). [1] là kho mã nguồn của chính đề tài, dẫn ở Bảng 4.1 để người đọc tra code.

## 10.10 Tài liệu nào quan trọng nhất với em? Nói nội dung của [x].
- **Mức:** ★★
- **Ý trả lời chính:** Chuẩn bị 1 câu cho mỗi bài nền: [23] Vaswani 2017 — Transformer/attention; [11] Ho 2020 — DDPM; [12] Ho & Salimans 2022 — CFG; [20] Rombach 2022 — latent diffusion; [13] Hu 2022 — LoRA; [26] Ye 2023 — IP-Adapter; [14] Kim 2021 — VITS; [16] Porter & Duff 1984 — alpha compositing; [21] Spärck Jones 1972 — IDF; [19] Radford 2021 — CLIP; [24] Wang 2021 — Real-ESRGAN; [25] Wu 2023 — Tune-A-Video.

## 10.11 Giáo trình nào được dùng cho phần phân tích thiết kế và kiểm thử?
- **Mức:** ★★
- **Ý trả lời chính:** [2] Vũ Thị Dương và cộng sự (2015), [3] Phùng Đức Hòa chủ biên — công nghệ phần mềm / phân tích thiết kế hướng đối tượng; [4] Hoàng Quang Huy, Đỗ Ngọc Sơn (2016) — Kiểm thử phần mềm; [9] Fowler — UML Distilled; [10] Gamma và cộng sự — Design Patterns.

## 10.12 Báo cáo có mấy hình, bảng? Hình nào em tự vẽ?
- **Mức:** ★
- **Ý trả lời chính:** Đếm lại trong danh mục hình/bảng trước buổi bảo vệ. Biết công cụ vẽ UML đã dùng và ảnh giao diện là ảnh chụp thật hay mockup.

## 10.13 Lời cảm ơn/cam đoan, phiếu giao đề tài?
- **Mức:** ★★
- **Ý trả lời chính:** Theo ghi chú riêng: thứ tự cảm ơn/cam đoan cần rà lại theo mẫu trường, thiếu Phiếu giao đề tài, câu "Đồ án chắc chắn còn những điểm chưa hoàn thiện" trong lời cảm ơn. Nếu bị nhắc: nhận và bổ sung bản in nộp lưu.

## 10.14 Hạn chế viết lặp ở mục 5.6 và Kết luận?
- **Mức:** ★★
- **Ý trả lời chính:** Nhận; 5.6 là hạn chế của thực nghiệm, Kết luận là hạn chế của sản phẩm — nên gộp/phân biệt rõ hơn.

## 10.15 Em làm đề tài trong bao lâu, theo kế hoạch nào?
- **Mức:** ★
- **Ý trả lời chính:** Chuẩn bị mốc thật: bắt đầu các submodule từ trước, chốt đề tài theo kế hoạch ĐATN HKP2 2025–2026, báo cáo hoàn thiện tháng 7–9/2026, chốt test 12/09/2026. Kiểm lại các mốc này bằng `git log` trước khi nói.

## 10.16 Em tự làm hay có dùng mã nguồn mở/AI hỗ trợ?
- **Mức:** ★★
- **Ý trả lời chính:** Mã nguồn mở: chỉ rõ ranh giới (Q65, 1.21 MoneyPrinterTurbo). Trợ lý lập trình AI: trả lời trung thực là có dùng như công cụ, em là người ra quyết định thiết kế, đo đạc và kiểm thử; chứng minh bằng giải thích một đoạn code bất kỳ hội đồng chỉ.

## 10.17 Thầy hướng dẫn góp ý những gì, em đã sửa ra sao?
- **Mức:** ★
- **Ý trả lời chính:** Tự điền 2–3 góp ý thật của ThS. Trần Thanh Hùng và thay đổi tương ứng — tài liệu này không có thông tin đó. Các thay đổi lớn có thật trong quá trình làm (để ghép với góp ý nếu đúng): chuyển nguồn mặc định sang thư mục cục bộ + thêm Sáng tác AI, thêm SQLite đúng ERD, sửa khung đen Real-ESRGAN.

## 10.18 Quản lý mã nguồn thế nào?
- **Mức:** ★
- **Ý trả lời chính:** Git + GitHub, 1 repo tổng + 2 submodule; nhánh `feat/*` cho tính năng, `main` ổn định; CI chạy mỗi push/PR; release theo tag. Lưu ý: hiện có thay đổi chưa commit (Dashboard).

## 10.19 Chạy demo lại từ đầu một chương cho hội đồng xem được không?
- **Mức:** ★
- **Ý trả lời chính:** Bước 1 nguồn local + Bước 2 Piper chạy nhanh; Bước 3 cho xem log 20–30 s rồi bấm Dừng (nói về CANCELLED, `taskkill /T` ); mở video đã chạy sẵn; có video quay sẵn dự phòng.

## 10.20 Nếu demo lỗi giữa chừng thì sao?
- **Mức:** ★★
- **Ý trả lời chính:** Bình tĩnh đọc log, nói nguyên nhân khả dĩ (Ollama chưa chạy, mất mạng với Edge, OOM), chuyển sang video quay sẵn; đây cũng là dịp chứng minh lỗi chỉ làm hỏng bước đó, app không sập.
