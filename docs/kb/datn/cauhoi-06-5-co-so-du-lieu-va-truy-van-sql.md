# 5. Cơ sở dữ liệu và truy vấn SQL

Hệ thống có hai CSDL SQLite: `storage/app.db` (3 bảng `stories` , `chapters` , `jobs` , WAL, khóa ngoại CASCADE) là bản mirror của `story.json` , và `storage/kb_index.db` (bảng `kb_chunks` + bảng ảo FTS5 `kb_fts` ) cho chatbot. Máy hiện có 11 truyện, 65 chương, bảng `jobs` 0 dòng — cần nói trước nếu bị yêu cầu mở DB.

Lược đồ thật ( `orchestrator/db.py` ):

```
CREATE TABLE stories (
slug TEXT PRIMARY KEY, name TEXT NOT NULL, source TEXT, language TEXT,
status TEXT, pipeline_step INTEGER DEFAULT 1, created_at TEXT, updated_at
TEXT);
CREATE TABLE chapters (
id INTEGER PRIMARY KEY AUTOINCREMENT, story_slug TEXT NOT NULL, idx INTEGER
NOT NULL,
title TEXT, md_path TEXT, wav_path TEXT, mp4_path TEXT, status TEXT,  --
status: text | tts | video
UNIQUE(story_slug, idx),
FOREIGN KEY (story_slug) REFERENCES stories(slug) ON DELETE CASCADE);
CREATE TABLE jobs (
id INTEGER PRIMARY KEY AUTOINCREMENT, story_slug TEXT NOT NULL, step TEXT
NOT NULL,
status TEXT, message TEXT, started_at TEXT, ended_at TEXT,
FOREIGN KEY (story_slug) REFERENCES stories(slug) ON DELETE CASCADE);
CREATE INDEX idx_chapters_story ON chapters(story_slug);
CREATE INDEX idx_jobs_story ON jobs(story_slug);
```

## 5.1 Câu hỏi khái niệm

### 5.1.1 Hệ thống dùng CSDL gì? Vì sao SQLite mà không MySQL/PostgreSQL?
- **Mức:** ★
- **Ý trả lời chính:** SQLite nhúng trong process, một tệp, không cần cài server, hợp ứng dụng desktop một người dùng; dữ liệu nhỏ (metadata). MySQL/PostgreSQL cần dịch vụ chạy nền, cấu hình tài khoản — thừa. Nếu nhiều người dùng thì chuyển PostgreSQL.
- **Tra ở:** `db.py` , báo cáo 4.7

### 5.1.2 Sao vừa có `story.json` vừa có SQLite? Cái nào là nguồn sự thật?
- **Mức:** ★★
- **Ý trả lời chính:** `story.json` nằm cạnh dữ liệu nặng, là nguồn sự thật, chuyển thư mục là mang theo trạng thái. SQLite là mirror ( `_mirror_to_db` mỗi lần ghi `story.json` ) để thống kê nhanh; dựng lại được bằng `rebuild_db` / `POST /api/maintenance/rebuild-` `db` . Lỗi DB không được phá luồng tệp.
- **Tra ở:** `storage.py:207-` `222`

### 5.1.3 Vẽ/giải thích ERD. Quan hệ giữa các bảng?
- **Mức:** ★
- **Ý trả lời chính:** `stories` 1–N `chapters` , `stories` 1–N `jobs` , nối qua `story_slug →` `stories.slug` . Một truyện nhiều chương, nhiều lần chạy.
- **Tra ở:** Báo cáo Hình 3.10, Bảng 3.21

### 5.1.4 Khóa chính, khóa ngoại, ràng buộc UNIQUE trong lược đồ?
- **Mức:** ★
- **Ý trả lời chính:** PK: `stories.slug` , `chapters.id` , `jobs.id` . FK: `chapters.story_slug` , `jobs.story_slug` . `UNIQUE(story_slug, idx)` : một truyện không có hai chương cùng số thứ tự (khóa ứng viên).
- **Tra ở:** `db.py:17-50`

### 5.1.5 Vì sao dùng `slug` (khóa tự nhiên) làm khóa chính thay vì id số? Đổi tên truyện thì sao?
- **Mức:** ★★
- **Ý trả lời chính:** Slug cũng là tên thư mục, duy nhất, nên dùng thẳng làm khóa cho đồng bộ tệp↔DB. Nhược: đổi tên là đổi PK, mà FK không khai `ON UPDATE` `CASCADE` . Code đổi tên bằng cách đổi thư mục, xóa bản ghi cũ rồi mirror lại. Thiết kế tốt hơn: `id` `INTEGER` làm PK, `slug` UNIQUE.
- **Tra ở:** `main.py` `patch_story`

### 5.1.6 Lược đồ đạt chuẩn mấy?
- **Mức:** ★★
- **Ý trả lời chính:** 1NF: giá trị nguyên tố. 2NF/3NF: thuộc tính phụ thuộc trực tiếp vào khóa (stories theo slug; chapters theo id/(story_slug, idx)). Điểm dư thừa có chủ đích: `chapters.status` suy ra được từ các path, giữ để truy vấn nhanh.
- **Tra ở:** `db.py`

### 5.1.7 Vì sao không lưu WAV/MP4/PNG vào DB (BLOB)?
- **Mức:** ★★
- **Ý trả lời chính:** Tệp lớn làm DB phình nhanh, chậm sao lưu, ffmpeg/TTS cần đường dẫn tệp thật. DB chỉ lưu metadata + đường dẫn.
- **Tra ở:** Báo cáo 4.7

### 5.1.8 WAL là gì? Vì sao bật?
- **Mức:** ★★
- **Ý trả lời chính:** Write-Ahead Logging: ghi thay đổi vào tệp log trước rồi checkpoint vào DB; người đọc không chặn người ghi. Hợp với nhiều thread (callback ghi, dashboard đọc) cùng lúc.
- **Tra ở:** `db.pyconnect`

### 5.1.9 Mở `app.db` bằng DB Browser thì `PRAGMA` `foreign_keys` = 0, vậy khóa ngoại có tác dụng không?
- **Mức:** ★★★
- **Ý trả lời chính:** SQLite bật khóa ngoại theo từng kết nối, mặc định tắt. Code chạy `PRAGMA foreign_keys=ON` mỗi lần `connect()` , nên trong ứng dụng CASCADE có hiệu lực; công cụ ngoài thì không.
- **Tra ở:** `db.pyconnect`

### 5.1.10 Kết nối DB được quản lý thế nào khi có nhiều thread?
- **Mức:** ★★
- **Ý trả lời chính:** Kết nối ngắn hạn: mỗi thao tác tự mở/đóng ( `try/finally` `conn.close()` ), `check_same_thread=False` , `timeout=15` chờ khóa, `row_factory = sqlite3.Row` để đọc theo tên cột.
- **Tra ở:** `db.py`

### 5.1.11 Transaction nằm ở đâu? `replace_chapters` có atomic không?
- **Mức:** ★★
- **Ý trả lời chính:** `DELETE` rồi `executemany INSERT` trong cùng kết nối, `commit()` một lần cuối → một transaction, lỗi giữa chừng thì không commit. ACID: Atomicity, Consistency, Isolation, Durability.
- **Tra ở:** `db.py` `replace_chapters`

### 5.1.12 Chống SQL injection thế nào?
- **Mức:** ★
- **Ý trả lời chính:** Mọi truy vấn dùng tham số `?` ( `conn.execute(sql, (slug,))` ), không nối chuỗi.
- **Tra ở:** `db.py`

### 5.1.13 Index `idx_chapters_story` để làm gì? Kiểm tra có dùng index không?
- **Mức:** ★★
- **Ý trả lời chính:** Tăng tốc lọc/nối theo `story_slug` (đếm chương mỗi truyện, lấy chi tiết). Kiểm bằng `EXPLAIN QUERY` `PLAN SELECT * FROM chapters` `WHERE story_slug='x';` → "SEARCH chapters USING INDEX idx_chapters_story".
- **Tra ở:** `db.py`

### 5.1.14 Bảng `jobs` dùng để làm gì? Sao không có dữ liệu?
- **Mức:** ★★★
- **Ý trả lời chính:** Thiết kế để ghi lịch sử lần chạy và lỗi (NFR01). Hàm `add_job` / `finish_job` đã có nhưng chưa được gọi ở đâu, nên bảng rỗng và chỉ số `jobs_failed` luôn 0. Nói thẳng; hướng sửa: gọi `add_job` khi spawn, `finish_job` trong callback (xem 7.9).
- **Tra ở:** Q16

### 5.1.15 Ngày giờ lưu kiểu gì?
- **Mức:** ★★
- **Ý trả lời chính:** `TEXT` dạng ISO 8601 ( `datetime.now().isoformat()` ), vì SQLite không có kiểu DATE riêng; so sánh/sắp xếp chuỗi ISO đúng thứ tự thời gian, tính toán bằng `julianday()` .
- **Tra ở:** `db.py_now`

### 5.1.16 Sao không dùng ORM (SQLAlchemy)?
- **Mức:** ★★
- **Ý trả lời chính:** 3 bảng, vài truy vấn; `sqlite3` chuẩn đủ và không thêm phụ thuộc. ORM có lợi khi lược đồ lớn hoặc cần migration (Alembic).
- **Tra ở:** `db.py`

### 5.1.17 Migration lược đồ làm sao?
- **Mức:** ★★
- **Ý trả lời chính:** Hiện dùng `CREATE TABLE IF NOT` `EXISTS` , không có phiên bản lược đồ. Thêm cột thì `ALTER TABLE ...` `ADD COLUMN` + `PRAGMA` `user_version` ; hoặc xóa `app.db` rồi `rebuild_db` vì DB chỉ là mirror.
- **Tra ở:** —

### 5.1.18 FTS5 là gì? `kb_fts` khai báo ra sao?
- **Mức:** ★★
- **Ý trả lời chính:** Bảng ảo tìm kiếm toàn văn của SQLite (chỉ mục ngược). `kb_fts` là contentless ( `content=''` ), tokenizer `unicode61` `remove_diacritics 2` (bỏ dấu tiếng Việt); nối với `kb_chunks` qua `rowid` . Contentless không cho DELETE nên nạp lại = dựng lại bảng.
- **Tra ở:** `kb_index.py:33-` `46, 145`

### 5.1.19 `bm25()` trong FTS5 trả gì?
- **Mức:** ★★
- **Ý trả lời chính:** Điểm BM25 âm, càng âm càng khớp; code đảo dấu để so ngưỡng. FTS5 mặc định AND mọi từ nên câu chứa một từ lạ là rỗng — lý do code thử nhiều nhịp (AND rồi OR).
- **Tra ở:** `kb_index.py:233-` `280`

### 5.1.20 Thao tác CRUD trên dữ liệu truyện nằm ở đâu?
- **Mức:** ★
- **Ý trả lời chính:** Create: `POST /api/stories` . Read: `GET /api/stories` , `/api/stats` , `/api/stats/stories/{name}` . Update: `PATCH` `/api/stories/{name}` (đổi tên/trạng thái). Delete: `DELETE` `/api/stories/{name}` . Hai endpoint cuối mới thêm, chưa commit, chưa có trong báo cáo.
- **Tra ở:** `main.py:222-420,` `511-526`

## 5.2 Viết truy vấn tại chỗ

Hội đồng hay đưa yêu cầu rồi bắt viết trên giấy hoặc chạy thử. Các câu dưới đây đúng lược đồ trên; câu nào có trong code thì ghi nguồn.

1. Liệt kê truyện kèm số chương, mới cập nhật lên đầu (truy vấn thật của `db.list_stories` , dùng subquery tương quan):

```
SELECT s.*, (SELECT COUNT(*) FROM chapters c WHERE c.story_slug = s.slug) AS
chapter_count
FROM stories s ORDER BY updated_at DESC;
```

2. Cùng kết quả nhưng bằng JOIN + GROUP BY (truyện 0 chương vẫn hiện nhờ LEFT JOIN):

```
SELECT s.slug, s.name, COUNT(c.id) AS chapter_count
FROM stories s LEFT JOIN chapters c ON c.story_slug = s.slug
GROUP BY s.slug, s.name
ORDER BY s.updated_at DESC;
```

3. Số liệu Dashboard (truy vấn thật của `db.stats` ):

```
SELECT COUNT(*) FROM stories;
SELECT COUNT(*) FROM chapters;
SELECT COUNT(*) FROM chapters WHERE mp4_path IS NOT NULL AND mp4_path <> '';
SELECT COUNT(*) FROM jobs WHERE status LIKE '%FAIL%';
```

4. Mỗi truyện có bao nhiêu chương ở từng trạng thái, và tỷ lệ % đã có video:

```
SELECT story_slug,
SUM(status = 'text')  AS chi_van_ban,
SUM(status = 'tts')   AS co_giong,
SUM(status = 'video') AS co_video,
ROUND(100.0 * SUM(status = 'video') / COUNT(*), 1) AS pct_video
FROM chapters GROUP BY story_slug ORDER BY pct_video DESC;
```

5. Truyện chưa có video nào (NOT EXISTS):

```
SELECT s.slug, s.name, s.status FROM stories s
WHERE NOT EXISTS (SELECT 1 FROM chapters c WHERE c.story_slug = s.slug AND
c.status = 'video');
```

6. Chương đã có văn bản nhưng chưa có giọng (việc còn lại của Bước 2):

```
SELECT story_slug, idx, title FROM chapters
WHERE md_path IS NOT NULL AND (wav_path IS NULL OR wav_path = '')
ORDER BY story_slug, idx;
```

7. Truyện đang lỗi hoặc bị hủy; top 3 truyện nhiều chương nhất:

```
SELECT slug, name, status, updated_at FROM stories
WHERE status LIKE '%FAILED' OR status = 'CANCELLED' ORDER BY updated_at DESC;
```

```
SELECT story_slug, COUNT(*) AS n FROM chapters GROUP BY story_slug
HAVING COUNT(*) > 0 ORDER BY n DESC LIMIT 3;
```

- 8. Ghi/cập nhật truyện bằng upsert (truy vấn thật của `db.upsert_story` ):

```
INSERT INTO stories (slug, name, source, language, status, pipeline_step,
created_at, updated_at)
VALUES (?,?,?,?,?,?,?,?)
ON CONFLICT(slug) DO UPDATE SET
name=excluded.name, source=excluded.source, language=excluded.language,
status=excluded.status, pipeline_step=excluded.pipeline_step,
updated_at=excluded.updated_at;
```

- 9. Xóa truyện, chương và job tự xóa theo (ON DELETE CASCADE, cần bật khóa ngoại trên kết nối):

```
PRAGMA foreign_keys = ON;
DELETE FROM stories WHERE slug = ?;
```

10. Cập nhật trạng thái một truyện; đánh dấu kết thúc job (truy vấn thật của `db.finish_job` ):

```
UPDATE stories SET status = 'VOICE_GENERATED', pipeline_step = 3, updated_at
= ? WHERE slug = ?;
UPDATE jobs SET status = ?, message = ?, ended_at = ? WHERE id = ?;
```

11. Thời gian chạy trung bình mỗi bước (giây) và số lần lỗi — câu "nâng cao" trên bảng `jobs` (hiện rỗng):

```
SELECT step,
COUNT(*) AS so_lan,
ROUND(AVG((julianday(ended_at) - julianday(started_at)) * 86400), 1)
AS tb_giay,
SUM(status LIKE '%FAIL%') AS so_loi
FROM jobs WHERE ended_at IS NOT NULL
GROUP BY step ORDER BY step;
```

12. Job gần nhất của mỗi truyện (window function, SQLite ≥ 3.25):

```
SELECT * FROM (
SELECT j.*, ROW_NUMBER() OVER (PARTITION BY story_slug ORDER BY id DESC) AS
rn FROM jobs j
) WHERE rn = 1;
```

13. Phân trang danh sách chương (trang 2, 20 dòng/trang) và tạo view thống kê:

```
SELECT idx, title, status FROM chapters WHERE story_slug = ? ORDER BY idx
LIMIT 20 OFFSET 20;
```

```
CREATE VIEW v_tien_do AS
SELECT s.slug, s.name, s.status, COUNT(c.id) AS tong, SUM(c.status = 'video')
AS xong
FROM stories s LEFT JOIN chapters c ON c.story_slug = s.slug GROUP BY s.slug;
```

14. Tìm mảnh tri thức cho chatbot bằng FTS5 + BM25 (dạng truy vấn trong `kb_index.search` ):

```
SELECT c.file, c.path, c.header, c.content, bm25(kb_fts) AS score
FROM kb_fts JOIN kb_chunks c ON c.id = kb_fts.rowid
WHERE kb_fts MATCH ? ORDER BY score LIMIT 5;
```
