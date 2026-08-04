# Hướng dẫn cập nhật & khởi động

**Dành cho máy đã có sẵn dự án nhưng đang ở phiên bản cũ.**
Không cần biết code. Làm đúng 4 bước dưới đây.

> 📄 Bản in đẹp có hình minh hoạ: **[HUONG-DAN-KHOI-DONG.pdf](HUONG-DAN-KHOI-DONG.pdf)**

---

## Trước khi bắt đầu — yên tâm về dữ liệu

| Sẽ bị ghi đè | Được giữ nguyên |
|---|---|
| Mã nguồn (các file lệnh của phần mềm) | ✅ Truyện & video đã tạo — thư mục `storage` |
| | ✅ API key và cấu hình — thư mục `configs` |
| | ✅ Thư viện và mô hình AI đã tải về |

Nói ngắn gọn: **bạn không mất truyện, không mất video, không phải nhập lại API key.**

---

## Bước 1 — Tìm đúng thư mục dự án

Mở **File Explorer**, tìm thư mục tên:

```
ToolAutoMakeCartoonVideo2DFromComics
```

Mở nó ra, bên trong phải nhìn thấy các file như `run.bat`, `setup.bat`, `README.md`.
**Nhìn thấy đúng những file này là đúng thư mục.**

> 🔍 **Không nhớ để ở đâu?** Bấm phím **Windows**, gõ `ToolAutoMakeCartoon`, Windows sẽ tìm giúp. Hoặc mở File Explorer, bấm vào **This PC**, gõ tên đó vào ô tìm kiếm góc trên bên phải rồi chờ.

---

## Bước 2 — Mở cửa sổ lệnh **ngay tại thư mục đó**

Đây là bước hay làm sai nhất. Làm đúng như sau:

1. Đang đứng trong thư mục ở Bước 1.
2. Bấm chuột vào **thanh địa chỉ** trên cùng (chỗ hiện đường dẫn thư mục).
3. **Xoá sạch** chữ đang có trong đó.
4. Gõ `cmd` rồi bấm **Enter**.

Một cửa sổ nền đen hiện ra. Dòng đầu tiên của nó **phải kết thúc bằng** `\ToolAutoMakeCartoonVideo2DFromComics>`.

> ⚠️ Nếu dòng đó không có tên thư mục dự án → bạn đang đứng sai chỗ. Đóng cửa sổ đen, quay lại Bước 1.

---

## Bước 3 — Tải bộ cập nhật (chỉ làm 1 lần duy nhất)

Copy nguyên dòng dưới đây, dán vào cửa sổ đen (**bấm chuột phải để dán**), rồi bấm **Enter**:

```
curl -L -o CAP-NHAT.bat https://raw.githubusercontent.com/Duyycoder/ToolAutoMakeCartoonVideo2DFromComics/main/CAP-NHAT.bat
```

Nếu báo lỗi mạng hoặc chờ quá lâu, dùng dòng này thay thế:

```
curl -L -o CAP-NHAT.bat https://ghfast.top/https://raw.githubusercontent.com/Duyycoder/ToolAutoMakeCartoonVideo2DFromComics/main/CAP-NHAT.bat
```

Xong thì trong thư mục dự án sẽ có thêm file mới tên **`CAP-NHAT.bat`**. Đóng cửa sổ đen lại.

> 💡 **Cách khác, không cần tải file:** dán thẳng dòng dưới đây vào cửa sổ đen rồi bấm Enter. Nó cập nhật ngay, và xong xuôi thì `CAP-NHAT.bat` cũng tự có sẵn trong thư mục cho những lần sau:
>
> ```
> git fetch origin && git checkout main && git reset --hard origin/main && git submodule sync --recursive && git submodule update --init --recursive --force
> ```
>
> Dùng cách này thì **bỏ qua Bước 4**, chỉ cần nháy đúp `run.bat`.

---

## Bước 4 — Nháy đúp `CAP-NHAT.bat`

1. Nó hiện phiên bản bạn đang dùng, rồi hỏi xác nhận.
2. Gõ chữ **`Y`** rồi bấm **Enter**.
3. Ngồi chờ. Nó tự tải bản mới, tự cập nhật, rồi **tự mở phần mềm**.

**Lần đầu sau khi cập nhật có thể lâu hơn bình thường** vì phần mềm tự tải bổ sung phần còn thiếu. Cứ để chạy, đừng tắt giữa chừng.

### ✅ Xong. Từ nay về sau

- **Muốn cập nhật:** nháy đúp `CAP-NHAT.bat`
- **Chỉ muốn mở phần mềm:** nháy đúp `run.bat`

---

## Khi gặp trục trặc

| Hiện tượng | Cách xử lý |
|---|---|
| Cửa sổ đen báo `'curl' is not recognized` | Máy Windows quá cũ. Tải file bằng tay: mở trình duyệt vào link ở Bước 3, bấm chuột phải → **Save as**, lưu vào thư mục dự án với tên đúng `CAP-NHAT.bat`. |
| Báo `[LOI] May nay chua cai Git` | Cài Git tại **https://git-scm.com/download/win** (bấm Next liên tục), xong nháy đúp `CAP-NHAT.bat` lại. |
| Báo `[LOI] File nay dang nam ngoai thu muc du an` | File `CAP-NHAT.bat` bị lưu nhầm chỗ (hay gặp nhất là vào **Downloads**). Chuyển nó vào đúng thư mục ở Bước 1. |
| Báo `[LOI] Khong tai duoc` | Mất mạng. Nối lại mạng rồi nháy đúp `CAP-NHAT.bat` lần nữa. |
| Cập nhật xong nhưng phần mềm không mở | Nháy đúp `run.bat debug` để xem báo lỗi thật. |
| Trợ lý AI trả lời "Không kết nối được Ollama" | Cài **https://ollama.com** rồi mở lại `run.bat`. Mô hình sẽ tự tải. |
| Muốn tắt phần mềm | Đóng cửa sổ ứng dụng — mọi tiến trình tự tắt sạch. |

---

## Máy chưa từng có dự án này?

Chỉ khi đó mới cần tải mới. Làm Bước 2 ở một ổ đĩa còn trống **≥ 60 GB**, rồi dán lệnh:

```
git clone --recursive https://github.com/Duyycoder/ToolAutoMakeCartoonVideo2DFromComics.git
```

Mạng chậm thì dùng bản qua máy chủ trung gian:

```
git clone --recursive https://ghfast.top/https://github.com/Duyycoder/ToolAutoMakeCartoonVideo2DFromComics.git
```

> ⚠️ Nhớ giữ chữ `--recursive`. Thiếu nó là tải thiếu, phần mềm sẽ không chạy.

Tải xong, vào thư mục vừa hiện ra và **nháy đúp `run.bat`** — nó tự cài mọi thứ (30–60 phút, cần Internet).

---

## Máy cần có gì

- Windows 10 hoặc 11
- Ổ cứng trống **≥ 60 GB**
- Card màn hình **NVIDIA ≥ 6 GB** (không có vẫn chạy được nhưng rất chậm)
- Internet

*Muốn hiểu sâu hơn về hệ thống thì đọc [README.md](README.md).*
