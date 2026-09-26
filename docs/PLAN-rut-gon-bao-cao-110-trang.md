# PLAN — Rút gọn báo cáo ĐATN từ 155 → ~108 trang (giữ nguyên 100% format)

Ngày lập: 21/09/2026
File nguồn: `F:\programfiles\ToolAutoMakeCartoonVideo2DFromComics\CNTT_2022600930_DaoKhuongDuy_baocao.docx`
Bản sao giống hệt (md5 `f4f26cc4…`): `D:\TLHT\_DATN\CNTT_2022600930_DaoKhuongDuy_baocao.docx` — sửa xong phải đồng bộ cả hai.

---

## 1. Feedback của thầy → việc phải làm

| Thầy nói | Hiểu là | Việc |
|---|---|---|
| "Bỏ truy vết 3.9 trang 124" | Mục **3.9. Truy vết yêu cầu – thiết kế** (Bảng 3.22). Trang 124 của bản in = trang 109–110 đánh số thân bài (đầu quyển 14–15 trang) → nằm gọn trong mục 3.9 (thân bài 108–112) | Bỏ hẳn mục 3.9 |
| "Phần giải thích hơi dài cần co lại, 110 trang là đẹp" | Cắt ~45 trang, chủ yếu ở phần diễn giải | Xem ngân sách mục 3 |
| "Viết công nghệ nhiều nhưng quá chi tiết" | Chương 2 (lý thuyết) và Chương 4 (hiện thực) sa đà vào chi tiết kỹ thuật | P5 + P6 |

## 2. Hiện trạng đã đo (Word repaginate, không phải ước lượng)

- **155 trang** = 14–15 trang đầu quyển (bìa + i–xi) + 140–141 trang thân bài. Độ lệch ±1 do MỤC LỤC và vị trí caption không khớp tuyệt đối ở Chương 4–5; đo lại chính xác sau khi cập nhật trường ở B7.

> ⚠️ **Câu hỏi còn treo, nên hỏi lại thầy:** "110 trang" là **tổng số trang cả quyển** hay **số trang thân bài**? Plan này bám mốc **tổng 110** (thầy đọc bản in nên "trang 124" là số trang vật lý → nhiều khả năng thầy đang nói tổng). Nếu là thân bài thì chỉ cần cắt ~30 trang, tức bỏ bớt P5–P8.

- 29.739 từ, 58 hình, 40 bảng (37 bảng có caption), 760 đoạn cấp thân bài
- Quy cách hiện tại **đang đúng chuẩn HaUI**, phải giữ nguyên:
  - Trang 21 × 29,7 cm; lề T2,5 / D2,0 / Trái 3,5 / Phải 2,0 → **vùng chữ 15,5 × 25,2 cm**
  - `Normal`: Times New Roman 14pt, dãn dòng 1,5, thụt dòng đầu 1,0 cm (567 twip), căn đều
  - `Figure Caption` / `Table Caption`: 11pt, dãn 1,0, căn giữa, cách 3pt/8pt
  - `Heading 1`: 16pt căn giữa; 3 section (bìa / La Mã / Ả Rập)

**Phân bố trang thật (số trang vật lý):**

| Mục | Trang | Số trang |
|---|---|---|
| Đầu quyển | 1–15 | 15 |
| Mở đầu + Chương 1 | 16–24 | 9 |
| Chương 2 | 25–41 | 17 |
| **Chương 3** | **42–127** | **86 (62% thân bài)** |
| — 3.1 + 3.2 + 3.2.1 | 42–50 | 9 |
| — **3.2.2 Đặc tả 16 UC** | **51–82** | **32** |
| — 3.3 → 3.5 | 83–90 | 8 |
| — **3.6 VOPC (16 hình)** | **91–103** | **13** |
| — **3.7 Trình tự (16 hình)** | **104–120** | **17** |
| — 3.8 Giao diện | 121–122 | 2 |
| — **3.9 Truy vết + 3.10** | **122–127** | **6** |
| Chương 4 | 128–139 | 12 |
| Chương 5 | 140–152 | 13 |
| Kết luận + TLTK | 153–155 | 3 |

## 3. Ngân sách cắt trang

| # | Việc | Trước | Sau | Tiết kiệm |
|---|---|---|---|---|
| P1 | 3.2.2 — co gọn cả 16 bảng đặc tả UC tại chỗ | 32 | 16 | **−16** |
| P2 | 3.6 — thu nhỏ 16 hình VOPC + rút đoạn giải thích | 13 | 7 | **−6** |
| P3 | 3.7 — giữ 8 biểu đồ trình tự của UC lõi | 17 | 8 | **−9** |
| P4 | 3.9 — bỏ hẳn (ý thầy) | 6 | 1 (còn 3.10) | **−5** |
| P5 | Chương 2 — cắt chi tiết công nghệ | 17 | 13 | **−4** |
| P6 | Chương 4 — cắt chi tiết trùng Ch.2 **+ gộp 6 tiểu mục quá mỏng** | 12 | 9 | **−3** |
| P7 | Mở đầu + Chương 1 — rút văn (KHÔNG cắt 1.3) | 9 | 7 | **−2** |
| P8 | Chương 5 — rút văn, **đo lại rồi cập nhật số liệu** | 13 | 12 | **−1** |
| | **TỔNG** | **155** | **≈109** | **−46** |

Sai số ước lượng ±3 trang → phải **đo lại bằng Word sau mỗi bước** (mục 7). Dự phòng nếu còn hụt: rút Bảng 3.20 (Quyết định kiến trúc) và Bảng 3.21 (Từ điển dữ liệu) ở 3.3/3.4.

> **Đã bỏ hạng mục "đầu quyển −1 trang" của bản plan đầu.** Bỏ 8 mục khỏi DANH MỤC HÌNH chỉ bớt 8 dòng ≈ 0,2 trang, không đủ để chắc chắn rụng một trang — không được tính vào ngân sách.

---

## 4. Việc chi tiết

### P1 — 3.2.2: co gọn 16 bảng đặc tả (32 → 16 trang) — VIỆC NẶNG NHẤT

Mỗi bảng hiện **13 dòng, 317–496 từ**, chiếm đúng 2 trang. Rút còn **7 dòng, ≤ 220 từ** → ~1 trang/UC.

Cấu trúc mới của mỗi bảng đặc tả:

| Dòng | Nội dung | Ghi chú |
|---|---|---|
| 1 | **Use case** | Gộp "Mã use case" + "Tên use case": `UC01 – Khởi tạo hoặc chọn truyện` |
| 2 | **Tác nhân** | Giữ "Người dùng"; hệ thống hỗ trợ ghi trong ngoặc nếu thật cần |
| 3 | **Mô tả tóm tắt** | ≤ 2 câu, ≤ 40 từ |
| 4 | **Điều kiện tiên quyết** | Gộp luôn "Điều kiện kích hoạt": `…; kích hoạt khi người dùng …` |
| 5 | **Luồng sự kiện chính** | ≤ 6 bước, mỗi bước ≤ 15 từ. **Bỏ tên hàm/endpoint/tên file** trừ khi là điểm mấu chốt |
| 6 | **Luồng rẽ nhánh và ngoại lệ** | Gộp 2 dòng cũ, ≤ 3 mục |
| 7 | **Hậu điều kiện** | 1 câu |

**Bỏ 3 dòng:** `Nhóm` (đã có ở Bảng 3.3), `Hệ thống hỗ trợ` (đã nói ở 3.1.1), `Ghi chú`.

**Giữ nguyên:** 16 tiêu đề `3.2.2.1 … 3.2.2.16`, 16 câu dẫn `Bảng 3.x trình bày đặc tả chi tiết…`, 16 caption `Bảng 3.4 … Bảng 3.19`.
→ **Không phải đánh số lại bảng nào.**

Kiểm tra sau P1: tổng từ trong 16 bảng ≤ 3.600 (hiện 7.908).

### P2 — 3.6 VOPC: thu nhỏ hình + rút giải thích (13 → 7 trang), giữ đủ 16 hình

1. **Thu 16 hình về 75% bề ngang:** 15,5 cm → **11,6 cm** (hình 15,0 cm → 11,25 cm), chiều cao co theo tỉ lệ.
   - An toàn in ấn: ảnh gốc 3444 px → DPI hiệu dụng tăng từ 564 lên **752 DPI**, thừa xa ngưỡng 300.
   - Nhãn trong VOPC rất to (2–6 hộp/hình) nên 75% vẫn đọc rõ — đã kiểm bằng mắt trên `image21.png`.
2. **Rút đoạn giải thích** dưới mỗi hình từ ~90 từ xuống **≤ 45 từ**: giữ đúng "vì sao tách lớp này", bỏ phần kể lại nội dung hình.
3. **Giữ câu dẫn 1 dòng** trước mỗi hình (đúng quy cách: hình phải được dẫn trong thân bài).

Ước tính khối/hình sau khi sửa: 0,75 (dẫn) + 6,26 (hình) + 0,75 (caption) + 1,5 (giải thích) ≈ **9,3 cm**. Word không cắt đôi một hình nên mỗi trang hao ~3 cm cuối trang → dùng 22 cm/trang thay vì 25,2: 16 × 9,3 / 22 ≈ **6,8 trang**. Vì vậy lấy mốc **−6**, không phải −7.

### P3 — 3.7: giữ 8 biểu đồ trình tự của UC lõi (17 → 8 trang)

Biểu đồ trình tự cao 13–19,4 cm, thu nhỏ **không cứu được** (muốn 2 hình/trang phải xuống 63% → chữ còn ~4,3pt, không đọc được). Chỉ còn cách giảm số hình.

**Giữ 8 (một biểu đồ cho mỗi mắt xích chính của pipeline + 2 mô-đun đặc thù):**

| Số cũ | UC | Lý do giữ | Số mới |
|---|---|---|---|
| Hình 3.31 | UC03 Sáng tác truyện bằng AI | đóng góp riêng của đề tài | **3.29** |
| Hình 3.32 | UC04 Dịch và chuẩn hóa | RQ1 – nhất quán ngữ nghĩa | **3.30** |
| Hình 3.34 | UC06 Sinh giọng đọc | Bước 2, sinh trục thời gian | **3.31** |
| Hình 3.35 | UC07 Sinh ảnh + Studio | trọng tâm đề tài, RQ2 | **3.32** |
| Hình 3.36 | UC08 Ghép video | Bước 5, đầu ra cuối | **3.33** |
| Hình 3.38 | UC10 AutoRun | điều phối đa tiến trình (tên đề tài) | **3.34** |
| Hình 3.41 | UC13 Khôi phục checkpoint | RQ3 – khả năng phục hồi | **3.35** |
| Hình 3.44 | UC16 Trợ lý AI | mô-đun độc lập, có đánh giá riêng ở Ch.5 | **3.36** |

**Bỏ 8:** Hình 3.29 (UC01), 3.30 (UC02), 3.33 (UC05), 3.37 (UC09), 3.39 (UC11), 3.40 (UC12), 3.42 (UC14), 3.43 (UC15) — kèm câu dẫn + caption + đoạn giải thích của từng hình.

**Đoạn mở đầu 3.7 hiện đã viết sẵn** *"…các biểu đồ trình tự được xây dựng cho những chức năng chính của hệ thống"* — tức là văn bản đang hứa "chức năng chính" nhưng lại vẽ đủ 16. Cắt xuống 8 làm câu này **đúng hơn hiện tại**, chỉ cần thêm một vế nêu tiêu chí: *"…cho tám use case cốt lõi phủ đủ các bước của pipeline và hai mô-đun đặc thù; các use case quản lý và tiện ích còn lại đã được đặc tả ở mục 3.2.2 và mô hình hoá ở mục 3.6."*

**Đánh số lại (phạm vi ảnh hưởng đã kiểm, rất hẹp):**
- Hình 3.13–3.28 (VOPC): **không đổi**
- 8 hình trình tự còn lại → 3.29–3.36
- 3 hình giao diện 3.45/3.46/3.47 → **3.37/3.38/3.39**
- Tổng hình: 57 → **49**

> **Đã kiểm bằng script:** Hình 3.13–3.44 **chỉ** xuất hiện trong (a) chính câu dẫn của nó và (b) Bảng 3.22 — mà Bảng 3.22 bị xoá ở P4. Không có tham chiếu chéo nào từ Chương 4/5. Hình 3.45–3.47 chỉ được nhắc trong 3.8. → đánh số lại chỉ đụng ~11 caption + 11 câu dẫn.

### P4 — Bỏ hẳn mục 3.9 (6 → 1 trang)

Xoá 4 khối liền nhau:
1. `Heading 2` — "3.9. Truy vết yêu cầu – thiết kế"
2. Đoạn dẫn "Để bảo đảm mỗi yêu cầu đều có mô hình thiết kế tương ứng…"
3. `Table Caption` — "Bảng 3.22. Ma trận truy vết yêu cầu – thiết kế"
4. Bảng 17 × 4

Rồi đổi `3.10. Tiểu kết chương` → **`3.9. Tiểu kết chương`**.

> Bảng 3.22 là **bảng cuối cùng của Chương 3** → bỏ đi **không phải đánh số lại bảng nào**. Nội dung truy vết vẫn còn ở Bảng 4.5 (thiết kế → mã nguồn).

Sửa 1 câu trong tiểu kết cho khỏi hụt mạch: bỏ vế "Các mô hình này tạo chuỗi truy vết…" hoặc đổi thành "Các mô hình này nối mục tiêu người dùng với lớp tham gia và thông điệp thực thi…".

### P5 — Chương 2: cắt chi tiết công nghệ (17 → 13 trang)

Nguyên tắc: **giữ đủ 7 công thức và mọi tham số có thật trong mã nguồn** (đó là thứ phân biệt báo cáo này với bài tổng thuật); **cắt phần giảng lại lý thuyết**.

| Mục | Từ hiện tại | Mục tiêu | Cắt gì |
|---|---|---|---|
| 2.1.1 | 498 | 330 | Rút 4 gạch đầu dòng dữ liệu trung gian còn 1 dòng/loại |
| 2.2.1 Transformer | 513 | 260 | Giữ công thức (2.1) + 1 đoạn Q/K/V ≤ 90 từ; gộp giải thích √dₖ vào 1 câu; **giữ nguyên danh sách 4 chỗ dùng LLM** |
| 2.2.3 Sáng tác | 323 | 200 | Giữ công thức (2.2) + tham số thật (0,85 / 0,3 / 2.500 ký tự / 200–4.000 từ); cắt phần diễn giải "vấn đề cửa sổ ngữ cảnh" |
| 2.4 Khuếch tán | 376 | 230 | Rút mô tả thêm/khử nhiễu còn 3–4 câu; giữ (2.3) + lý do chọn SD cho GPU 6GB |
| 2.5.1 LoRA | 239 | 150 | Giữ (2.4) + "dùng ở đâu, tham số nào"; cắt giảng lý thuyết low-rank |
| 2.5.2 IP-Adapter | 191 | 140 | Giữ (2.5) + λ = 0,6 ∈ [0,1] |
| 2.6 Studio | 302 | 200 | Giữ (2.6); rút đoạn giải thích alpha/matting |
| 2.8 Trợ lý AI | 389 | 230 | Giữ (2.7) + ngưỡng kb_min_score = 0,75; **cắt phần mô tả ChatManager vì trùng nguyên xi mục 4.8** |
| 2.10 Tiểu kết | 156 | 90 | Rút liệt kê dài |

Cắt ≈ 1.300 từ (31%) ≈ 3,4 trang. Thêm: **thu 7 hình Chương 2 về 85%** (73,9 cm → 62,8 cm) ≈ 0,4 trang. Tổng **−4**.

### P6 — Chương 4: gộp tiểu mục + cắt trùng lặp (12 → 9 trang)

**Việc 1 — chữa chỗ vụn nhất của cả báo cáo.** Chương 4 có 2.370 từ mà đeo **11 mục + 8 tiểu mục**, tức trung bình một tiêu đề cho ~130 từ. Sáu tiểu mục chỉ dài đúng một đoạn: 4.2.1 (71 từ), 4.3.1 (74), 4.4 (73), 4.5.1 (69), 4.5.3 (73), 4.6 (100). Đọc lên rất gãy khúc. Gộp lại:

- **4.2** giữ nguyên tiêu đề, bỏ 4.2.1/4.2.2 → một mục liền mạch về NovelPipeline, ProcessManager, AutoRunManager và SSE
- **4.3** bỏ 4.3.1/4.3.2 → một mục "Hiện thực Bước 1"
- **4.5** giữ 4.5.1 và 4.5.2, gộp 4.5.3 + 4.5.4 thành "Sinh lớp, unify và cổng chất lượng"

Kết quả: 11 mục + 8 tiểu mục → 11 mục + 3 tiểu mục. Riêng việc bỏ 5 tiêu đề (mỗi tiêu đề chiếm dòng + khoảng cách trước 8pt) đã tiết kiệm ~0,5 trang, và quan trọng hơn là hết cảm giác liệt kê rời rạc.

**Việc 2 — cắt ~700 từ** ở những chỗ nhắc lại nguyên lý đã nói ở Chương 2:
- **4.2.2** (255 từ): bỏ phần mô tả lại cơ chế SSE
- **4.5.2** (149+): bỏ đoạn nhắc lại IP-Adapter scale 0,6 / [0,1] — đã có ở 2.5.2
- **4.5.4** (255 từ): giữ Bảng 4.3, rút văn còn ~150 từ
- **4.8** (390+ từ): giữ Bảng 4.4 và **giữ nguyên số liệu 41 test / 25-28 QA / 7-8 từ chối**, cắt phần mô tả lại IDF/ngưỡng — đã có ở 2.8
- **4.3.2** (228 từ): rút còn ~150, bỏ tên hàm nội bộ ít giá trị

Giữ nguyên toàn bộ 5 bảng của Chương 4.

### P7 — Mở đầu + Chương 1 (9 → 7 trang)

- Mục 1 "Lý do chọn đề tài": 226 → 150 từ
- 1.1 "Bài toán…": 668 → 450 từ (bỏ phần kể lại bối cảnh ngành)
- 1.5 "Phạm vi chức năng": 239 → 170 từ
- Gộp 1.2.1 (79 từ) + 1.2.2 (81) + 1.2.3 (57) thành **một mục 1.2 với ba đoạn có câu chủ đề** — ba tiêu đề cho 217 từ là quá vụn
- **KHÔNG cắt 1.3 "Khảo sát nhóm giải pháp liên quan"** (đang chỉ có 254 từ + Bảng 1.1). Đây đã là phần mỏng nhất so với chuẩn một đồ án tốt nghiệp; hội đồng hay hỏi "công trình liên quan". Nếu sau khi cắt xong còn dư trang thì **viết thêm** cho mục này, đừng cắt.
- Giữ nguyên: mục tiêu, câu hỏi nghiên cứu, Bảng 1.1

### P8 — Chương 5 (13 → 12 trang) + SỬA SỐ LIỆU ĐÃ LỖI THỜI

> ⚠️ **Sửa lại chỉ dẫn ở bản plan đầu.** Bản đầu ghi "không đụng vào bất kỳ con số nào" — làm vậy sẽ giữ nguyên một con số đã sai. Đã chạy lại thật ngày 21/09/2026 trên máy này:

| Số liệu | Báo cáo đang ghi | Đo lại 21/09/2026 | Kết luận |
|---|---|---|---|
| Tổng kiểm thử | **173 passed** | **174 passed** | ❌ phải sửa |
| Thời gian chạy | 7,86 giây | 7,28 giây (lần chạy nguội đầu tiên 22,03 s) | ✅ cùng cỡ, chỉ cần đổi ngày |
| Nhóm Trợ lý AI | **41** | **42** | ❌ phải sửa |
| Nhóm AI Writer | 4 | 4 | ✅ |
| Nhóm lưu trữ | 6 | 6 | ✅ |
| Eval KB — QA | 25/28 = 89,3% | 25/28 = 89,3% | ✅ |
| Eval KB — từ chối | 7/8 = 87,5% | 7/8 = 87,5% | ✅ |

Hai con số **173** và **41** xuất hiện ở **9 chỗ**: TÓM TẮT ĐỒ ÁN, mục 4.8, 5.1.3, 5.2.x, 5.4.3, KẾT LUẬN, Bảng 4.5, Bảng 5.1, Bảng 5.6. Phải sửa đồng bộ cả 9 chỗ, kể cả câu "tập kiểm thử đã tăng từ 63 lên 173" → "lên 174".

Lý do lệch: mã nguồn đã đổi sau ngày chốt 12/09 (2 commit WebUI ngày 20/09). Rủi ro thật: hội đồng gõ `pytest` sẽ ra 174, lệch với báo cáo.

Lệnh đo lại, chạy ngay trước khi nộp:

```bash
python -m pytest tests -q
```

Chỉ rút văn: 5.1.2 (353 → 250), 5.2 (377 → 280), 5.5.2 (255 → 180). **Giữ nguyên** các số liệu còn lại: VRAM 4,0 GB, 26 chương / 214.034 ký tự, rò rỉ chữ Hán 0,0%.

### P9 — SỬA LỖI DANH MỤC HÌNH / BẢNG SAI TRANG (bắt buộc, không tốn trang)

**Đây là lỗi trình bày nặng nhất đang có trong file, không liên quan tới việc cắt trang.** Đã đối chiếu từng mục với trang thật:

- **DANH MỤC HÌNH VẼ: 45/57 mục ghi sai số trang.** Lệch tăng dần, nặng nhất Hình 4.1 ghi trang 91 trong khi thực tế nằm ở trang 122 thân bài — **sai 31 trang**. Toàn bộ Hình 3.13–3.28 ghi dồn vào trang 74–75, Hình 3.29–3.44 ghi dồn hết vào trang 76.
- **DANH MỤC BẢNG BIỂU: 22/37 mục ghi sai.** Bảng 5.7 ghi trang 110, thực tế 134.
- MỤC LỤC thì **đúng** — chỉ hai danh mục hình/bảng bị bỏ quên khi cập nhật trường lần cuối.

Nguyên nhân: ba trường TOC được cập nhật không đồng bộ ở lần lưu cuối. Cách sửa: mục 6 Nguyên tắc 4 (đặt `w:dirty="true"` cho cả ba trường, hoặc mở Word bấm Ctrl+A → F9 → chọn "Update entire table"). **Phải kiểm lại bằng mắt sau khi cập nhật**, đừng tin là xong.

---

## 5. Giao thức giữ nguyên format — BẮT BUỘC

> Đây là phần quan trọng nhất. Mọi thao tác sửa đều phải theo 9 nguyên tắc dưới.

**NT1 — Chỉ sửa `word/document.xml`.** Không đụng `styles.xml`, `numbering.xml`, `theme1.xml`, `settings.xml`, `sectPr`. Cách duy nhất để định dạng "biến mất" là vô tình ghi đè các file này.

**NT2 — Sửa chữ ở mức `run`, không ghi đè cả đoạn.**
- 269/336 đoạn thân bài chỉ có **1 run** → ghi text mới vào `p.runs[0].text`, giữ nguyên `<w:rPr>`.
- 67 đoạn nhiều run: **đã kiểm — tất cả run đều `bold=None, italic=None, font=None`**, chỉ bị tách do dấu gạch nối. Ghi toàn bộ text mới vào `runs[0]`, gỡ các run còn lại.
- **Cấm** `p.clear()`, cấm dựng lại đoạn từ đầu, cấm `copy.deepcopy` đoạn mẫu rồi ghi đè text.

**NT3 — Xoá khối thì xoá cả cụm và dọn bookmark.**
Bỏ 1 hình = xoá đúng 4 khối liền nhau: câu dẫn → đoạn chứa ảnh → caption → đoạn giải thích.
Caption có `<w:bookmarkStart>`/`<w:bookmarkEnd>` do trường TOC sinh (tài liệu có 293 bookmark) → phải gỡ **cả cặp cùng `w:id`**; nếu `bookmarkEnd` nằm ở đoạn khác thì gỡ riêng. Xoá bằng `el.getparent().remove(el)`.

**NT4 — Không sửa tay mục lục / danh mục.**
Tài liệu có 3 trường TOC: `TOC \o "1-3"`, `TOC \t "Figure Caption,1"`, `TOC \t "Table Caption,1"`.
Sau khi sửa xong, đặt `w:dirty="true"` lên `<w:fldChar w:fldCharType="begin">` của **cả 3** → Word tự dựng lại khi mở.
⚠️ **MỤC LỤC nằm trong `<w:sdt>`** nên `Document.paragraphs` của python-docx **không nhìn thấy nó**. Script duyệt body phải **bỏ qua `w:sdt`** để không vô tình sửa trúng. Tuyệt đối không sửa các đoạn style `Mucluc1/2/3` hay `toc 1`.

**NT5 — Thu nhỏ hình phải sửa 2 nơi.**
Mỗi drawing có `<wp:extent cx cy>` **và** `<a:ext cx cy>` — sửa thiếu một trong hai là ảnh méo/lệch.
Ảnh dạng **anchor** (`wp:anchor`, ví dụ Hình 5.1) **không xuất hiện trong `doc.inline_shapes`** → phải duyệt thẳng XML.
Giữ đúng tỉ lệ w/h. Chặn bề ngang **≤ 15,5 cm** — bản V10 từng có 5 ảnh tràn lề.

**NT6 — Thứ tự con trong `<w:pPr>` do lược đồ ép:** `ind` → `jc` → `rPr`. Append bừa vào cuối `pPr` là lỗi XSD (Word vẫn mở nhưng file sai chuẩn). Kế hoạch này không cần chèn thuộc tính mới — nếu phải chèn thì theo đúng thứ tự trên.

**NT7 — Số hiệu hình/bảng là CHỮ THƯỜNG, không phải trường.**
Đã kiểm: **0 trường SEQ, 0 trường REF** trong toàn tài liệu. Nên đánh số lại phải tự làm bằng script, và phải quét cả:
- caption (`Figure Caption` / `Table Caption`)
- thân bài (286 tham chiếu `Hình x.y` / `Bảng x.y`, kể cả dạng `H.3.x`)
- **ô bảng** (57 tham chiếu, gần hết nằm trong Bảng 3.22 sẽ bị xoá)

**NT8 — Không chạm vào 3 bảng không caption ở bìa** (`ĐÀO KHƯƠNG DUY`, `CBHD :`, `Từ viết tắt`) — 2 bảng đầu là bảng dàn trang bìa.

**NT9 — Đóng Word trước khi chạy script.** Nếu file đang mở trong Word, Word sẽ ghi đè lại lúc lưu và mất sạch thay đổi.

---

## 6. Thứ tự thực hiện

Làm từ việc **rủi ro thấp / lợi nhiều** trước, **đo lại trang sau mỗi bước**, mỗi bước xuất ra một file riêng để lùi được.

| Bước | Việc | File ra | Trang dự kiến |
|---|---|---|---|
| B0 | Sao lưu `…_baocao_GOC.docx` ở cả F:\ và D:\TLHT\_DATN | — | 155 |
| B1 | **P4** bỏ mục 3.9 (không đánh số lại → an toàn nhất) | `_b1.docx` | ~150 |
| B2 | **P3** bỏ 8 hình trình tự + đánh số lại 3.29–3.39 | `_b2.docx` | ~141 |
| B3 | **P2** thu nhỏ 16 VOPC + rút 16 đoạn giải thích | `_b3.docx` | ~134 |
| B4a | **P1 thử nghiệm: co đúng 2 bảng UC (UC01, UC07)** rồi đo lại | `_b4a.docx` | đo thật |
| B4b | **P1** co 14 bảng còn lại, kiểm sau mỗi 4 UC | `_b4.docx` | ~118 |
| B5 | **P5** Chương 2 + **P6** Chương 4 (gộp tiểu mục trước, cắt chữ sau) | `_b5.docx` | ~112 |
| B6 | **P7** Mở đầu/Ch.1 + **P8** Ch.5 (kèm sửa 173→174, 41→42 ở 9 chỗ) | `_b6.docx` | ~109 |
| B7 | **P9** mở Word → cập nhật 3 trường TOC → **soát mắt danh mục hình/bảng** → lưu → xuất PDF | `…_baocao.docx` | **≈109** |
| B8 | Đồng bộ sang `D:\TLHT\_DATN\`; dọn 8 ảnh mồ côi trong `word/media` | — | — |

**Vì sao tách B4a:** P1 là hạng mục nặng nhất (−16 trang, chiếm 35% ngân sách) nhưng cũng là hạng mục ước lượng mong manh nhất — con số "1 trang/UC" suy ra từ tỉ lệ từ/chiều cao chứ chưa đo thật lần nào. Co 2 bảng rồi đo, lấy số thật nhân 16; nếu ra 1,3 trang/UC thì phải bù bằng phương án dự phòng **trước khi** làm 14 bảng còn lại, chứ không phải phát hiện lúc đã sửa xong.

Sau B4b, nếu số trang lệch nhiều so với dự kiến thì điều chỉnh mức cắt ở B5/B6 (hoặc dùng phương án dự phòng ở mục 3) thay vì cắt mù.

**Rủi ro lớn nhất của cả plan nằm ở P1**: viết lại ~4.300 từ nội dung đặc tả. Không rút gọn theo cảm tính — mỗi bước trong "Luồng sự kiện chính" phải còn đối chiếu được với mã nguồn thật (`orchestrator/main.py`, `pipeline.py`, `story_writer.py`). Rút ngắn thì được, bịa hoặc đổi hành vi thì không.

Các file `_b*.docx` để trong scratchpad của phiên, **không** để cạnh file thật để tránh nộp nhầm.

## 7. Bộ kiểm tra tự động (`verify.py`) — chạy sau mỗi bước

1. **Số trang** qua Word COM `doc.ComputeStatistics(2)` sau `Repaginate()` — mục tiêu ≤ 112.
2. **Tham chiếu không gãy:** mọi `Hình x.y` / `Bảng x.y` / `H.x.y` trong thân bài phải có caption tương ứng; ngược lại mọi caption phải được nhắc ≥ 1 lần.
3. **Số hiệu liên tục:** Hình 2.1–2.7, 3.1–3.39, 4.1, 5.1–5.2; Bảng 1.1, 2.1–2.2, 3.1–3.21, 4.1–4.5, 5.1–5.7. Không nhảy số, không trùng.
4. **Ảnh:** không ảnh nào rộng > 15,5 cm; DPI hiệu dụng ≥ 300; `wp:extent` và `a:ext` khớp nhau.
5. **Định dạng thân bài:** mọi đoạn `Normal` giữ thụt dòng đầu 567 twip, dãn 1,5, TNR 14, căn đều.
6. **Style nguyên vẹn:** tập style dùng trong `document.xml` trước/sau phải **giống hệt** (so bằng set).
7. **Bookmark:** mọi `bookmarkStart` có `bookmarkEnd` cùng `w:id`.
8. **Số liệu Chương 5 đã cập nhật đúng:** không còn chuỗi `173 ` hay `41 kiểm thử`/`41 unit` nào sót; `89,3`, `87,5`, `214.034`, `4,0 GB` vẫn nguyên.
9. **Danh mục hình/bảng khớp trang thật:** so từng mục với trang vật lý, độ lệch phải là hằng số bằng số trang đầu quyển (±1). Đây là bộ kiểm bắt được lỗi 45/57 + 22/37 nói ở P9.
10. Mở lại bằng Word không hiện cảnh báo sửa lỗi; xuất PDF thành công.
11. Đọc lại bằng mắt 5 chỗ: một bảng UC đã co, mục 3.7 sau khi cắt hình, chỗ nối 3.8 → 3.9 (Tiểu kết) sau khi bỏ truy vết, mục 4.2 sau khi gộp tiểu mục, và TÓM TẮT ĐỒ ÁN.

## 8. Rollback

Giữ toàn bộ `_b1.docx … _b6.docx` cho tới khi bản cuối được thầy duyệt. Sai ở bước nào thì quay lại file bước trước đó, không sửa ngược.

## 9. Ngoài file .docx — rà soát toàn dự án (21/09/2026)

Không nằm trong ngân sách cắt trang, nhưng ảnh hưởng trực tiếp tới buổi bảo vệ. Xếp theo mức nghiêm trọng.

### 9.1. Giao diện thật vẫn lộ chữ "Cào" và tên trang nguồn Trung Quốc — RỦI RO CAO

Báo cáo đã sạch tuyệt đối (0 lần "cào/69shuba/bypass/cookie"), nhưng **phần mềm chạy thật thì chưa**:

| Nơi | Nội dung |
|---|---|
| `webui/index.html:133` | `<option value="69shuba">Web: 69shu (Tiếng Trung)</option>` |
| `webui/index.html:918` | nhãn checkbox "Tự động dịch sau khi **cào**/nhập" |
| `docs/kb/01-buoc1-cao-dich.md` | ngay tên tệp, và dòng 5 "**Cào Web** (Crawler)" |
| `docs/kb/00-tong-quan.md:7` | "Bước 1 — **Cào** & Dịch / AI Sáng Tác" |
| `docs/kb/08-tham-so-thuc-te.md:68` | `69shuba: Web: 69shu (Tiếng Trung)` |
| `README.md` dòng 18, 25 | "**Cào** truyện + dịch AI", bảng pipeline |

Hội đồng chỉ cần mở tab Bước 1, hoặc hỏi Trợ lý AI một câu về Bước 1 (trợ lý trích thẳng `docs/kb/`), là thấy mâu thuẫn với báo cáo. Việc cần làm: đổi nhãn hiển thị sang "Nguồn web (tùy chọn)", đổi tên/nội dung tệp KB, sửa README. Đây là đúng hạng mục A1 trong `KE_HOACH_KHAC_PHUC_LO_HONG.md` — đã từng sửa ở `webui/app.js` nhưng bản redesign `index.html` ngày 20/09 chưa sửa.

### 9.2. Bản demo sạch chưa có video, bản có video thì không sạch — RỦI RO CAO

- `storage_demo/` (60 KB, 13 tệp): 2 truyện sạch — "Người gác đèn biển", "Chuyến tàu mùa hạ" — nhưng **không có một tệp `.mp4` / `.wav` / `.srt` nào**. Cả hai đang dừng ở trạng thái TRANSLATED.
- `storage/` (1,0 GB): có video thật, nhưng tên truyện là truyện mạng Trung Quốc đã dịch và có cả một truyện phái sinh Harry Potter (`bang_hoc_tap_hogwarts`). Ngoài ra còn `storage/truyen/hvl/video/dl_XyHE6NFYwLs.mp4` — video tải về từ YouTube.

Việc cần làm trước buổi bảo vệ: **chạy trọn Bước 2→5 cho một truyện trong `storage_demo`** để có video demo sạch, và trỏ ứng dụng vào `storage_demo` khi trình diễn.

### 9.3. Hình giao diện trong báo cáo — ĐÃ KIỂM, KHÔNG SAO

Đã lo Hình 3.45–3.47 bị cũ vì WebUI được redesign ngày 20/09. Kiểm lại: ba ảnh chụp **đúng bản giao diện mới** (nền tối, thương hiệu "AutoCartoon", sidebar Bước 1–4 + Cấu Hình Chung + Thống Kê), độ phân giải ~338 DPI. Không phải chụp lại.

Một chi tiết nhỏ: ảnh Bước 3 hiển thị ô Style là giá trị thô `anime_2d_flat`; thay đổi chưa commit hiện đổi mặc định sang `thuy_mac` và thêm lựa chọn "Điện Ảnh Bán Thực". Nếu chốt các thay đổi này thì chụp lại riêng Hình 3.47 cho khớp, không bắt buộc.

### 9.4. Mô-đun có trong mã nhưng không xuất hiện trong báo cáo — CÂN NHẮC

`model_preflight.py`, `ollama_manager.py`, `desktop.py` (vỏ ứng dụng desktop), `mediacomposer_config.py`. Riêng `character_bootstrap` (tự huấn luyện Character LoRA một lần cho mỗi truyện) chỉ được nhắc thoáng ở mục 4.5.2 bằng cụm "mô-đun bootstrap hỗ trợ chuẩn bị ảnh hạt giống".

Đã kiểm lại `video_downloader.py`: nằm ở `AIVoice/apps/MediaComposer/app/services/`, được `adapter_autosub_cli.py` gọi — tức nó là **đường vào của Bước 4 (autosub)** chứ không phải một tính năng riêng bị bỏ quên. Mục 4.6 đã mô tả đúng ("trường hợp người dùng có video/âm thanh cần hậu xử lý"), không phải bổ sung gì. Chỉ lưu ý: chính mô-đun này sinh ra tệp `storage/truyen/hvl/video/dl_XyHE6NFYwLs.mp4` tải từ YouTube — thêm một lý do phải trỏ ứng dụng vào `storage_demo` khi trình diễn (mục 9.2).

Đây là một **đóng góp đang bị bán rẻ**. Nhưng bối cảnh hiện tại là đang phải cắt 46 trang, nên khuyến nghị: **không thêm mục mới**, chỉ nâng cụm từ ở 4.5.2 thành một câu nói rõ "hệ thống tự huấn luyện Character LoRA cho nhân vật chính một lần cho mỗi truyện" — tốn 0 trang, được thêm một điểm đáng nói khi thuyết trình.

### 9.5. Lẫn lộn cách đánh số bước — LỖI TRÌNH BÀY

Cùng một thứ đang có ba cách gọi trong ba tài liệu:

| Nơi | Cách gọi |
|---|---|
| API / báo cáo mục 2.1.2 | step1…step5, ghép video = **step5** |
| Giao diện | ghép video mang nhãn **"Bước 4"**, autosub tách thành công cụ riêng |
| `README.md` | "pipeline **4 bước**" |
| Báo cáo mục 4.2.2 | "AutoRunManager gọi các bước lõi theo thứ tự **1 → 2 → 3 → 5**" |
| Báo cáo mục 4.6 | "Hiện thực **Bước 4** (autosub) và **Bước 5** (ghép video)" |

Báo cáo đã có hẳn một đoạn ở cuối 2.1.2 để giải thích chuyện này — nhưng chính việc phải giải thích là dấu hiệu quy ước chưa ổn, và người đọc đi tới mục 4.6 vẫn vấp. Khuyến nghị: **giữ đúng một quy ước số hiệu endpoint (step1–step5) trong toàn báo cáo**, và ở Bảng 2.1 thêm một cột "Nhãn trên giao diện". Bỏ đoạn giải thích dài ở 2.1.2 (tiết kiệm luôn ~90 từ). Sửa tiêu đề 4.6 thành "Hiện thực autosub (step4) và ghép video (step5)".

### 9.6. Các mục quá mỏng ngoài Chương 4 — LỖI TRÌNH BÀY

Toàn báo cáo có **23 mục dưới 110 từ**, trong đó 14 mục chỉ có đúng một đoạn văn. Ngoài cụm Chương 4 đã xử ở P6 và cụm 1.2 đã xử ở P7, còn: 2.7 (80 từ), 2.2.4 (98), 5.2.2 (73), 5.4.2 (99), 5.4.3 (98), 1.6 (44), 3.10 (79). Các mục tiểu kết ngắn thì chấp nhận được; nhưng **2.7 "Siêu phân giải, cổng chất lượng và fallback" (80 từ)** nên gộp vào 2.6, và **5.4.2 + 5.4.3** nên gộp thành một mục "Đánh giá định tính và mô-đun Trợ lý AI".

### 9.7. Mục 3.2.2.1–3.2.2.16 không xuất hiện trong MỤC LỤC — CÓ CHỦ Ý, GIỮ NGUYÊN

16 tiêu đề cấp 4 này được định dạng `Normal` chứ không phải Heading 4, nên trường TOC (`\o "1-3"`) không bắt. Người đọc thấy số mục "3.2.2.7" trong thân bài nhưng tra mục lục không có. Đây là đánh đổi có lý (thêm 16 dòng vào mục lục sẽ làm mục lục dài thêm gần một trang) — **giữ nguyên**, chỉ ghi nhận để nếu thầy hỏi thì trả lời được.

---

## 10. Ghi chú kỹ thuật

- Máy **không có LibreOffice** → xuất PDF bằng Word COM qua pywin32 (`soffice.py` của skill docx chết vì gọi `socket.AF_UNIX`).
- `python` toàn cục có `python-docx 1.2.0` (đủ dùng); cần vẽ hình thì dùng `AIVoice\.venv\Scripts\python.exe` (matplotlib toàn cục hỏng do numpy 1.x/2.x).
- Script Python có đường dẫn Windows phải viết bằng Write tool — heredoc của bash nuốt dấu `\`.
- File hiện 16,2 MB / 58 ảnh; sau khi bỏ 8 ảnh trình tự (mỗi ảnh ~2600×3000 px) nên xoá luôn part trong `word/media` → file giảm còn ~13 MB.
