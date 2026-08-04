# Chatbot RAG v2 — chia nhỏ tri thức, truy xuất bằng SQLite FTS5

> **Nhánh:** `feat/chatbot-assistant` (tiếp nối, không tách nhánh mới).
> **Trạng thái:** kế hoạch — đã kiểm chứng khả thi FTS5, chưa viết code.
> **Tài liệu liên quan:** [PLAN-chatbot-assistant.md](PLAN-chatbot-assistant.md),
> [PLAN-chatbot-scenarios.md](PLAN-chatbot-scenarios.md).
> **Quyết định đã chốt:** dùng **SQLite FTS5/BM25**, KHÔNG dùng embedding.
> **Đã quyết định KHÔNG làm:** fine-tune model (lý do ở mục 7).

---

## 1. Xuất phát điểm — số đo thật, không phải ước lượng

Đo ngày 2026-08-04 trên `qwen2.5:3b`, GPU RTX 3060 Laptop 6GB:

| Chỉ số | Giá trị |
|---|---|
| Số mảnh kiến thức | 111 đoạn, 30KB |
| Cỡ mảnh trung bình | 283 ký tự (~140 token) |
| Mảnh lớn nhất | 1822 ký tự (~910 token) |
| Context KB mỗi câu | 985 token, cao nhất 2545 |
| Số mảnh dùng mỗi câu | 5.4 |
| Truy xuất: QA / từ chối | 100% / 87.5% |
| LLM thật: QA / từ chối | 92.9% / 100% |

Đây đã là kết quả sau khi chia nhỏ file tham số theo từng tham số (giảm 33% context
so với gộp cả bước) và thêm trọng số IDF (nâng tỉ lệ chặn từ 37.5% lên 87.5%).

**Vấn đề còn lại:** cách chấm điểm hiện tại là IDF tự viết. Mỗi lần nạp thêm tài
liệu, tỉ lệ chặn lại tụt và phải dò lại ngưỡng bằng tay. Đã phải làm việc đó ba lần
trong một ngày. Đó là dấu hiệu của công cụ sai, không phải tham số sai.

---

## 2. Vì sao FTS5/BM25 chứ không phải embedding

| | IDF tự viết (nay) | **FTS5/BM25** | Embedding |
|---|---|---|---|
| Phụ thuộc mới | không | **không** (sẵn trong Python) | model embedding + VRAM |
| Chuẩn hoá điểm | tự chế, phải dò lại khi đổi KB | **BM25 chuẩn, có bão hoà độ dài** | cosine, ổn định |
| Tiếng Việt không dấu | tự bỏ dấu | **`remove_diacritics 2` sẵn có** | tuỳ model |
| Hiểu từ đồng nghĩa | không | không | có |
| Chi phí mỗi câu | ~0 | **~0** | thêm một lượt suy luận |
| VRAM | 0 | **0** | +0.5–2GB, tranh với SD |

Kho tri thức chỉ ~30KB và toàn thuật ngữ khớp mặt chữ (tên nút, tên tham số, tên
engine). Đây đúng là địa hình BM25 mạnh nhất, còn embedding thì trả giá VRAM để đổi
lấy khả năng hiểu đồng nghĩa mà ta gần như không cần.

### 2.1 Đã kiểm chứng khả thi

```
sqlite3 3.45.1 trong AIVoice/.venv  — FTS5 CÓ SẴN
tokenize='unicode61 remove_diacritics 2'  → "buoc 2" khớp "Bước 2"  ✓
```

### 2.2 Phát hiện quyết định thiết kế: FTS5 mặc định là **AND**

```
q='engine zzzxxx'      → 0 kết quả   (AND ngầm định)
q='engine OR zzzxxx'   → 1 kết quả
```

Hệ quả hai mặt:

- **Lợi:** câu ngoài phạm vi chứa bất kỳ từ lạ nào sẽ trả về 0 kết quả — tự động
  từ chối, không cần ngưỡng. Đây có thể là thứ đẩy tỉ lệ chặn lên trên 90%.
- **Hại:** câu hợp lệ gõ sai một chữ hoặc dùng từ hiếm cũng về 0.

→ **Chiến lược hai nhịp:** chạy AND trước; rỗng thì chạy lại bằng OR + BM25 + ngưỡng.
Có precision khi có thể, có recall khi cần.

---

## 3. Kiến trúc đích

```text
Câu hỏi
  │
  ├─(1) Cache câu lặp ─────────────► trả lời ngay, 0 giây          (mục 6)
  │
  ├─(2) Router lệnh L1/L2/L3 ──────► truy vấn dữ liệu / thẻ xác nhận
  │
  ├─(3) Truy xuất FTS5             AND → rỗng thì OR + BM25
  │      │
  │      ├─ 0 kết quả ────────────► từ chối, gợi ý 3 mục gần nhất
  │      │
  │      ├─ điểm tốt, cùng chủ đề ► (5) trả lời một lượt
  │      │
  │      └─ điểm tầm tầm / tản mát► (4) lượt suy nghĩ rồi mới (5)
  │
  └─(5) Prompt đầy đủ: system + few-shot + mảnh KB + ngữ cảnh truyện + lịch sử
```

Điểm khác cốt lõi so với hiện tại: **(1) cache**, **(3) BM25 thay IDF**, **(4) lượt
suy nghĩ có điều kiện**.

---

## 4. Chia nhỏ sâu hơn

Đã làm: tách file tham số theo từng tham số (81 → 111 mảnh, −33% context).

Còn lại:

| Nguồn | Hiện tại | Chia thành |
|---|---|---|
| `09-thong-bao-loi.md` | 1 đoạn/nhóm lỗi, có đoạn gộp nhiều thông báo | 1 đoạn/thông báo |
| `08` mục "Giá trị mặc định" | 1 đoạn 1822 ký tự cho cả 4 khối config | 1 đoạn/khối |
| KB viết tay (00–07, 10) | đoạn theo `##`, có đoạn dài | tách mục con `###` thành mảnh riêng |

**Trần cứng: 400 ký tự mỗi mảnh.** Vượt thì cắt tiếp theo gạch đầu dòng. Mục tiêu:
mảnh trung bình ~150 token, mỗi câu ghép 6–8 mảnh mà tổng vẫn dưới 800 token —
thấp hơn 985 hiện tại dù dùng nhiều mảnh hơn.

**Lưu ý bắt buộc:** mỗi mảnh phải **tự đứng vững**. Mảnh "- `classic`: 1 ảnh/cảnh"
tách khỏi tiêu đề "Chế độ render — Bước 3" là vô nghĩa. Khi cắt, luôn nhân bản
đường dẫn ngữ cảnh vào đầu mảnh (`Bước 3 › Chế độ render › classic`). Đây là chỗ
dễ hỏng nhất của việc chia nhỏ, và là lý do phải đo lại chất lượng sau mỗi lần cắt
sâu hơn.

---

## 5. Lượt suy nghĩ có điều kiện

Không hỏi model "có cần suy nghĩ không" — model 3B trả lời câu đó không đáng tin,
mà lại tốn đúng một lượt gọi ở chỗ định tiết kiệm. Dùng **tín hiệu miễn phí từ truy
xuất**:

| Tín hiệu | Nghĩa | Hành động |
|---|---|---|
| 0 kết quả | ngoài phạm vi | từ chối, không gọi LLM |
| Top-1 vượt trội, các mảnh cùng file | câu rõ ràng | trả lời một lượt |
| Điểm sát nhau, mảnh rải ≥3 file khác nhau | câu mơ hồ | **chạy lượt suy nghĩ** |

Lượt suy nghĩ: cho model đọc **tiêu đề** các mảnh (không phải nội dung) và chọn ra
2–3 mảnh thật sự liên quan, rồi mới nạp nội dung của chúng vào lượt trả lời. Prompt
ngắn nên lượt này rẻ.

Ca thật cần nó: *"Bước 1 báo không kết nối được"* hiện lôi nhầm đoạn TTS lên đầu vì
các mảnh rải rác nhiều file — đúng điều kiện dòng thứ ba.

Nếu đo xong thấy vẫn bịa nhiều thì bật cho mọi câu. Để **số liệu quyết định**, không
quyết trước.

---

## 6. Cache câu lặp

Băm câu hỏi đã chuẩn hoá (bỏ dấu, gộp khoảng trắng) làm khoá; lưu câu trả lời và
danh sách mảnh KB đã dùng. Trả lời lại tức thì, 0 giây, 0 VRAM.

Vô hiệu hoá cache khi: KB đổi (so `mtime`), đổi model, hoặc câu hỏi có kèm ngữ cảnh
truyện (vai B — dữ liệu thay đổi liên tục). Cache **chỉ áp dụng cho vai A**.

Đây là thứ giảm thời gian chờ thật sự cho người dùng mới — họ hỏi lặp rất nhiều.

---

## 7. Fine-tune: quyết định KHÔNG làm

Ghi lại để sau này không phải bàn lại.

1. **Fine-tune dạy phong cách, không dạy sự thật.** Nhồi tài liệu vào trọng số thì
   model trả lời đúng giọng văn nhưng sai số liệu, sai tên nút, và mất dòng `Nguồn:`
   để kiểm chứng. Nó biến lỗi "thỉnh thoảng từ chối" thành lỗi "bịa trôi chảy,
   không truy vết được" — tệ hơn hẳn.
2. **Tri thức đổi liên tục.** `gen_kb_from_project.py` sinh lại mỗi khi đổi giao
   diện; riêng ngày 2026-08-04 đã chạy lại ba lần. Fine-tune thì thêm một dropdown
   là phải train lại.
3. **Máy 6GB không train nổi.** LoRA cho model 3B cần ~8–12GB VRAM, buộc phải thuê
   GPU đám mây — mâu thuẫn với luận điểm "chạy hoàn toàn cục bộ, không phụ thuộc
   dịch vụ trả phí" của đồ án.
4. **Không giải đúng bài toán.** Context KB hiện là 985/8192 token, chưa tới 12%.
   Nút thắt tốc độ là nạp model và sinh token, không phải độ dài prompt.

**Ngoại lệ duy nhất đáng cân nhắc về sau:** fine-tune *văn phong trả lời* (ngắn, có
gạch đầu dòng, luôn kèm `Nguồn:`, biết từ chối) bằng vài trăm mẫu — không dạy sự
thật. Nhưng few-shot trong prompt đang làm được việc đó với chi phí bằng không, nên
chưa có lý do.

---

## 8. Phân kỳ và tiêu chí nghiệm thu

Mỗi giai đoạn phải **đo trước/sau** bằng `scripts/eval_chatbot.py` cả hai chế độ.
Không cải thiện thì revert, không giữ lại "cho có".

| GĐ | Nội dung | Công | Tiêu chí đạt |
|---|---|---|---|
| **R1** | Bảng SQLite `kb_chunks` + FTS5, script nạp từ `docs/kb/` | 0.5 ngày | Nạp đủ 111 mảnh, truy vấn ra kết quả đúng |
| **R2** | Thay `select_kb` sang AND→OR + BM25, giữ nguyên chữ ký hàm | 1 ngày | Từ chối **≥90%** (nay 87.5%), QA **giữ 100%** |
| **R3** | Chia nhỏ sâu hơn, trần 400 ký tự, nhân bản đường dẫn ngữ cảnh | 0.75 ngày | Context/câu **≤800 token** (nay 985), QA không tụt |
| **R4** | Lượt suy nghĩ có điều kiện | 1 ngày | Ca "Bước 1 không kết nối" trả lời đúng; thời gian trung bình tăng **≤30%** |
| **R5** | Cache câu lặp cho vai A | 0.5 ngày | Câu hỏi lặp trả lời **<0.3 giây** |
| **R6** | Test hồi quy + cập nhật eval + README | 0.5 ngày | `ruff` sạch, toàn bộ test xanh |

**Tổng ≈ 4.25 ngày.**

Thứ tự có lý do: R2 trước R3 vì phải có thước đo ổn định (BM25) rồi mới chia nhỏ,
nếu không lại rơi vào cảnh dò ngưỡng bằng tay sau mỗi lần cắt.

---

## 9. Rủi ro

| Rủi ro | Mức | Xử lý |
|---|---|---|
| Chia nhỏ làm mảnh mất ngữ cảnh, trả lời cụt | **Cao** | Nhân bản đường dẫn ngữ cảnh vào đầu mảnh; đo lại QA sau mỗi lần cắt (mục 4) |
| AND quá chặt, câu hợp lệ về 0 kết quả | Trung bình | Nhịp hai OR + BM25 (mục 2.2); thêm ca gõ sai chính tả vào bộ eval |
| BM25 đổi thang điểm, ngưỡng cũ vô nghĩa | Trung bình | Hiệu chỉnh lại bằng quét ngưỡng như đã làm; điểm BM25 của SQLite là **số âm**, càng âm càng khớp — dễ sai dấu |
| Nhiều mảnh nhỏ → nhiều cơ hội trùng ngẫu nhiên | Trung bình | Đã thấy thật: chia nhỏ làm tỉ lệ chặn tụt 87.5%→75%. Chia nhỏ và siết cổng phải đi cùng nhau |
| Cache trả lời cũ sau khi sửa KB | Thấp | Khoá cache gồm `mtime` của KB và tên model |
| Lượt suy nghĩ làm chậm gấp đôi | Thấp | Chỉ chạy khi mảnh tản mát; đo thời gian trung bình, vượt +30% thì tắt |

---

## 10. Quyết định còn treo

1. **Nguồn sự thật của KB** — giữ `docs/kb/*.md` rồi nạp vào SQLite (dễ đọc, dễ
   review, git theo dõi được), hay chuyển hẳn vào SQLite? Khuyến nghị: **giữ file
   Markdown**, SQLite chỉ là chỉ mục sinh lại được. Mất chỉ mục thì nạp lại, không
   mất tri thức.
2. **Đặt chỉ mục ở đâu** — dùng chung `storage/*.db` hiện có hay file riêng
   `storage/kb_index.db`? Khuyến nghị **file riêng**, để xoá/nạp lại không đụng dữ
   liệu truyện.
3. **Ngưỡng nghiệm thu từ chối** — hiện đặt ≥90%. Với FTS5 AND có thể đạt cao hơn;
   sau R2 nên xem lại con số này dựa trên số đo thật.
