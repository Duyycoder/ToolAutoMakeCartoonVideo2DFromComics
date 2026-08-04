# Hướng dẫn khởi động (cho người không biết code)

Chỉ có **3 bước**. Làm đúng thứ tự là chạy được.

---

## Bước 1 — Cài Git (chỉ làm 1 lần duy nhất)

Tải và cài: **https://git-scm.com/download/win**

Cứ bấm **Next** liên tục cho tới **Install**, xong bấm **Finish**. Không cần chỉnh gì.

---

## Bước 2 — Tải phần mềm về máy (chỉ làm 1 lần duy nhất)

1. Mở **File Explorer**, vào ổ đĩa còn trống ít nhất **60 GB** (ví dụ ổ `D:`).
2. Bấm vào **thanh địa chỉ** ở trên cùng, xoá hết chữ trong đó, gõ `cmd` rồi bấm **Enter**.
   → Một cửa sổ nền đen hiện ra.
3. Copy nguyên dòng dưới đây, dán vào cửa sổ đen (bấm chuột phải để dán), rồi bấm **Enter**:

```
git clone --recursive https://github.com/Duyycoder/ToolAutoMakeCartoonVideo2DFromComics.git
```

4. Chờ tải xong (vài phút). Xong sẽ có thư mục mới tên `ToolAutoMakeCartoonVideo2DFromComics`.

> ⚠️ Nhớ giữ chữ `--recursive`. Thiếu nó là tải thiếu, phần mềm sẽ không chạy.

---

## Bước 3 — Mở phần mềm

Vào thư mục vừa tải về, **nháy đúp chuột vào file `run.bat`**.

- **Lần đầu tiên:** máy sẽ tự cài đặt mọi thứ (Python, thư viện, mô hình AI). Việc này mất **30–60 phút** và **cần Internet**. Cứ để cửa sổ đen chạy, **không được tắt giữa chừng**. Xong nó tự mở giao diện phần mềm.
- **Những lần sau:** nháy đúp `run.bat` là giao diện mở ra sau vài giây.

**Xong. Không phải làm gì thêm.**

Thiếu mô hình AI nào thì phần mềm **tự tải bổ sung** trong lúc chạy — bạn không cần cài tay.

---

## Khi gặp trục trặc

| Hiện tượng | Cách xử lý |
|---|---|
| Nháy `run.bat` không thấy gì | Chờ 1–2 phút. Vẫn không được thì nháy đúp `run.bat debug` để xem báo lỗi. |
| Báo thiếu Git / thiếu submodule | Làm lại Bước 1 và Bước 2. |
| Cài giữa chừng bị mất mạng | Nối lại mạng rồi nháy đúp `run.bat` lần nữa — nó chạy tiếp chỗ còn thiếu. |
| Trợ lý AI trả lời "Không kết nối được Ollama" | Cài **https://ollama.com** rồi mở lại `run.bat`. Model sẽ tự tải. |
| Muốn tắt phần mềm | Đóng cửa sổ ứng dụng — mọi thứ tự tắt sạch. |

---

## Máy cần có gì

- Windows 10 hoặc 11
- Ổ cứng trống **≥ 60 GB**
- Card màn hình **NVIDIA ≥ 6 GB** (không có vẫn chạy được nhưng rất chậm)
- Internet (cho lần cài đầu tiên)

*Muốn hiểu sâu hơn về hệ thống thì đọc [README.md](README.md).*
