# PLAN — Cải thiện repo tổng: Bảo mật + Chất lượng code + Test + Dọn dẹp

> **Phạm vi:** repo tổng (`orchestrator/`, `webui/`, `tests/`, `configs/`, CI, scripts root).
> Các mục nằm trong submodule (AIVoice / toolCaoTruyen) được **đánh dấu [SUBMODULE]** và commit theo quy trình con-trước-tổng-sau (xem README).
> **Trạng thái:** DRAFT — chờ duyệt, **chưa sửa code**.
> **Nguyên tắc chạy:** mỗi task xong → `python -m py_compile <file>`; task đụng orchestrator → `pytest -q` ở repo tổng phải xanh.
> **Ràng buộc đã biết:** PAT thiếu scope `workflow` → thay đổi `.github/workflows/*` phải push thủ công bằng token có scope (memory: git-push-workflow-scope).

Thứ tự thực thi tối ưu: **P1 → P2 → P3 → P4**. P2 phụ thuộc P1 (helper LLM dùng key từ config đã gộp). P3 kiểm chứng P1+P2. P4 độc lập, làm lúc nào cũng được.

---

## P1 — Bảo mật & cấu hình  (rủi ro thấp, giá trị cao)

### P1.1 — Bỏ secret hardcode, đưa key proxy vào config
- **File:** [orchestrator/pipeline.py:300](../orchestrator/pipeline.py) và [:441](../orchestrator/pipeline.py) — hiện `resolved_key = llm_api_key or "sk-gemini-YrVw…"`.
- **Sửa:** đọc từ config, ví dụ `g_config.get("crawler", {}).get("gemini_offline_key", "")`; nếu rỗng → nêu cảnh báo/`ValueError` rõ ràng thay vì nhét key thật.
- **Thêm** khoá `gemini_offline_key` vào `crawler` trong [configs/config.example.json](../configs/config.example.json) (và default ở P1.3). Vì `crawler` khai báo kiểu `dict` trong schema nên khoá lồng này **không bị rớt khi lưu** (xem P1.5).
- **Nghiệm thu:** `git grep "sk-gemini"` trong file tracked = rỗng; Bước 3/4 vẫn resolve được key từ config.

### P1.2 — Siết CORS về localhost
- **File:** [orchestrator/main.py:21-27](../orchestrator/main.py) — hiện `allow_origins=["*"]` + `allow_credentials=True` (sai spec + rủi ro CSRF từ web ngoài gọi `localhost:8100`).
- **Sửa:** `allow_origins=["http://127.0.0.1:8100", "http://localhost:8100"]`, cân nhắc `allow_credentials=False` (UI phục vụ same-origin nên không cần).
- **Nghiệm thu:** mở UI tại `127.0.0.1:8100` vẫn chạy; trang web khác không gọi được API (thử fetch từ console tab khác → bị CORS chặn).

### P1.3 — Gộp nguồn cấu hình (config.py vs config.example.json)
- **Vấn đề:** `default_cfg` trong [orchestrator/config.py:11-31](../orchestrator/config.py) lệch với [config.example.json](../configs/config.example.json): thiếu `crawler.ollama_base_url`, `crawler.gemini_offline_base_url`, `crawler.gemini_offline_key`, `tts.kokoro_voice/vieneu_*`, `video.default_llm_engine/default_llm_model`; `default_site` là `69shuba` vs `local`.
- **Sửa:** đồng bộ `default_cfg` khớp cấu trúc `config.example.json` (giữ placeholder key rỗng). Đây là 1 nguồn sự thật cho các khoá mà pipeline thực sự đọc.
- **Nghiệm thu:** mọi khoá pipeline truy cập (`crawler.ollama_base_url`, `crawler.gemini_offline_base_url`, `video.default_llm_model`, `tts.kokoro_voice`, `tts.vieneu_voice`) đều có mặt ở **cả** `default_cfg` lẫn example. Thêm test đối chiếu 2 tập khoá (P3).

### P1.4 — Thống nhất model default
- **Vấn đề:** default Gemini lệch nhau: `gemini-2.5-flash` (Bước 1, [main.py:255](../orchestrator/main.py)), `gemini-3-flash` (Bước 3/4 gemini_api), `gemini-2.0-flash` (gemini online).
- **✅ ĐÃ CHỐT:** proxy local canonical = **`gemini-2.5-flash`** → đổi `gemini-3-flash` ở [pipeline.py:302,443](../orchestrator/pipeline.py) và ở [config.example.json](../configs/config.example.json) (`video.default_llm_model`) về `gemini-2.5-flash`.
- **Sửa:** đưa 3 hằng vào một nơi (đề xuất `orchestrator/config.py`): `DEFAULT_GEMINI_ONLINE_MODEL="gemini-2.0-flash"`, `DEFAULT_GEMINI_PROXY_MODEL="gemini-2.5-flash"`, `DEFAULT_OLLAMA_MODEL="qwen2.5:3b-instruct"`; Bước 1/3/4 import dùng chung.
- **Nghiệm thu:** mỗi default định nghĩa đúng 1 chỗ; `git grep "gemini-3-flash"` = rỗng; grep tên model chỉ ra file hằng.

### P1.5 — (nhỏ) Schema config nuốt khoá top-level lạ
- **Vấn đề:** `POST /api/config` dùng `GlobalConfigSchema` + `config.dict()` ([main.py:35,197](../orchestrator/main.py)); khoá top-level ngoài schema (vd `orchestrator_port`) bị **rớt khi lưu**. (Khoá lồng trong `crawler/tts/video` an toàn vì kiểu `dict`.)
- **Sửa:** thêm `orchestrator_port: Optional[int]` vào schema (và field top-level khác nếu có), hoặc cho schema `extra="allow"` + dùng `model_dump()`.
- **Nghiệm thu:** lưu config qua UI rồi đọc lại → `orchestrator_port` còn nguyên.

---

## P2 — Chất lượng code

### P2.1 — Tách helper `_resolve_llm()` (chống trùng lặp)
- **Vấn đề:** khối resolve LLM ở Bước 3 ([pipeline.py:288-302](../orchestrator/pipeline.py)) và Bước 4 ([:430-443](../orchestrator/pipeline.py)) gần như y hệt (~15 dòng, cùng hardcode key + model).
- **Sửa:** thêm `NovelPipeline._resolve_llm(self, args: dict, g_config: dict) -> tuple[str, str, str]` trả `(key, base_url, model)`, xử lý 3 nhánh `gemini` / `ollama` / `gemini_api` (dùng hằng từ P1.4, key từ P1.1), raise `ValueError` khi thiếu key online. Thay cả 2 khối bằng lời gọi helper.
- **Nghiệm thu:** 11 test hiện có vẫn xanh (chúng test resolve Bước 3); thêm 2-3 test gọi helper trực tiếp (P3).

### P2.2 — Sửa các chỗ `except` nuốt lỗi
- [process_manager.py:73](../orchestrator/process_manager.py) `except Exception: pass` quanh `on_completed` → log lỗi (ít nhất `print`/đẩy vào queue). Đây là chỗ nguy hiểm nhất: callback pipeline hỏng mà im lặng.
- [main.py:418](../orchestrator/main.py) parse JSON prepare → `except json.JSONDecodeError: continue` (thu hẹp).
- [video_merger.py:85](../orchestrator/video_merger.py) `except:` khi `os.remove` → `except OSError:`.
- [pipeline.py:149](../orchestrator/pipeline.py) `_copy_local` bắt `e` nhưng không dùng → log `e` (đẩy vào queue) trước `on_crawl_completed(1)`.
- **Nghiệm thu:** ruff E722 = 0; lỗi copy/parse/callback giờ hiện ra log.

### P2.3 — Dọn 16 lỗi ruff còn lại
- `ruff check orchestrator tests --fix` cho 12 lỗi tự sửa (F401 import thừa, F541 f-string).
- Tay: F841 biến không dùng (`translated_dir` [pipeline.py:21](../orchestrator/pipeline.py), `slug` [main.py:464](../orchestrator/main.py)); phần E722 đã xử ở P2.2.
- **Nghiệm thu:** `ruff check orchestrator tests` → 0 error.

### P2.4 — Nâng cấp CI/CD lên mô hình chuyên nghiệp  ⚠️ [đụng `.github/workflows/*` → cần PAT scope `workflow` để push]

**Hiện trạng:** `ci.yml` chỉ chạy trên `main` (nhánh `dev/**` không được kiểm), lint chỉ bắt lỗi nặng, không cache, không chặn merge. `release.yml` đóng gói khi tag `v*` nhưng **không chạy test trước khi phát hành**.

> ⚠️ Mọi thay đổi file workflow cần token có scope `workflow`. Kế hoạch: tôi **tạo/sửa file trong working tree**; **bước push workflow là bạn làm** (token có scope) hoặc cấp scope cho tôi. Các thay đổi non-workflow (requirements.txt, config, code) push bình thường.

#### P2.4a — `ci.yml`: tách job + trigger rộng + cache + concurrency
- **Trigger:** `push` vào `main` **và `dev/**`**; `pull_request` vào `main`.
- **Concurrency:** huỷ run cũ khi có push mới cùng ref (tiết kiệm phút CI):
  ```yaml
  concurrency:
    group: ci-${{ github.ref }}
    cancel-in-progress: true
  ```
- **Job `lint`** (ubuntu, py3.11, pin `ruff==<ver>`): `ruff check orchestrator tests` (full, bỏ `--select` hẹp) **+ `ruff format --check orchestrator tests`**.
- **Job `test`** (ubuntu, py3.11, cache pip qua `actions/setup-python` với `cache: pip`): `python -m compileall orchestrator -q` → `pytest -q --cov=orchestrator --cov-report=term-missing` (thêm `pytest-cov` vào tooling CI).
- **Bước validate config:** một step nhỏ chạy `python -c "..."` kiểm `configs/config.example.json` parse được và chứa đủ khoá bắt buộc (đồng bộ P1.3).
- **Nghiệm thu:** push nhánh `dev/**` cũng chạy CI; lint mới/format sai → đỏ; test có báo coverage.

#### P2.4b — `release.yml`: cổng test trước khi phát hành
- Thêm `needs`/step chạy `pytest -q` **trước** bước đóng gói, để tag `v*` không bao giờ release code đỏ.
- Giữ `permissions: contents: write` (đã least-privilege ✅), giữ `generate_release_notes`.
- Cân nhắc bổ sung `docs/` và `global_glossary.json` vào gói zip (tuỳ bạn).
- **Nghiệm thu:** tag thử trên nhánh có test đỏ → release bị chặn; test xanh → ra artifact.

#### P2.4c — `.github/dependabot.yml`: tự cập nhật dependency
- Ecosystem `github-actions` (weekly) để bump version action; thêm `pip` (thư mục `orchestrator/`) sau khi có requirements.txt (P4.2).
- **Nghiệm thu:** Dependabot mở PR bump khi có bản mới.

#### P2.4d — (khuyến nghị, không phải file) Branch protection cho `main`
- Thiết lập trên GitHub Settings → Branches: yêu cầu `lint` + `test` xanh mới merge; chặn push thẳng vào `main`. Tôi ghi hướng dẫn, bạn bật trong UITHub.

---

## P3 — Test coverage

Thêm vào `tests/` (được CI chạy). Mục tiêu: phủ các helper "âm thầm sai thì hỏng nặng".

### P3.1 — `tests/test_storage.py` cho `slugify()`
- Ca: dấu tiếng Việt → ascii (`"Đắc Kỷ Trụ Vương"` → `"dac_ky_tru_vuong"`), `đ→d`, khoảng trắng/gạch → `_`, gộp trùng, strip `_`, chuỗi rỗng, toàn ký hiệu.
- **Nghiệm thu:** phủ nhánh chính; chạy không cần GPU.

### P3.2 — `tests/test_video_merger.py` (chống path-traversal)
- **Refactor nhỏ để test được:** tách logic lọc file trong [video_merger.py](../orchestrator/video_merger.py) thành hàm thuần `_select_files(mp4_files, only_files) -> list` (giữ nguyên hành vi: bỏ `TongHop_*`, `only_files` chỉ nhận basename thuần nằm trong danh sách quét).
- Ca: `only_files=["../secret.mp4"]` hoặc đường dẫn tuyệt đối → bị loại; basename hợp lệ → nhận; `only_files=None` → tất cả trừ `TongHop_*`.
- **Nghiệm thu:** test chạy không cần ffmpeg (chỉ test hàm lọc).

### P3.3 — Mở rộng test build-cmd cho Bước 1/4/5
- Nối tiếp kiểu `test_pipeline_llm.py` (stub Storage/Process, bắt `captured_cmd`):
  - **Bước 1:** crawl cmd đúng flag khi `source≠local`; nhánh `local` không tạo crawl cmd.
  - **Bước 4:** `--crop-*` chỉ xuất hiện khi cả 4 giá trị hợp lệ (kiểm BUG-7 ở P4.5); flag styling (`--font-name`, `--bg-alpha`…) chỉ nối khi có; cookies nối từ config.
  - **Bước 5:** gọi `start_step_5_merge` khởi tạo queue `{slug}_step5` đúng.
- **Nghiệm thu:** `pytest -q` xanh, số test tăng; cập nhật badge/con số trong README nếu cần.

---

## P4 — Dọn dẹp & tài liệu  (độc lập)

### P4.1 — Chuyển script `test_*.py` ở root khỏi tên gây nhầm
- `git mv` [test_manual.py](../test_manual.py), [test_pipeline.py](../test_pipeline.py), [test_repair_real.py](../test_repair_real.py) → `scripts/manual/` (đổi tên bỏ tiền tố `test_`, vd `smoke_step1.py`). Chúng là script tích hợp cần server/GPU thật, không phải unit test.
- **Nghiệm thu:** root sạch; `pytest` vẫn chỉ thu `tests/`; script vẫn chạy tay được.

### P4.2 — Thêm khai báo dependency cho orchestrator
- Tạo `orchestrator/requirements.txt` (pin version): `fastapi`, `uvicorn`, `sse-starlette`, `pydantic`, `requests`. (Option A giữ nguyên cài vào `AIVoice/.venv` — đây là bản kê deps để tái lập/CI, không đổi đích cài.)
- (Tuỳ chọn) `requirements-dev.txt`: `ruff`, `pytest`, `pytest-cov` — CI (P2.4) cài từ đây thay vì gõ tay.
- [setup.bat:155](../setup.bat) trỏ vào file này thay vì liệt kê tay.
- **Nghiệm thu:** cài lại từ file khớp deps hiện dùng; import orchestrator OK.

### P4.3 — Sửa README cho khớp thực tế (Option A — ĐÃ CHỐT)
- **Vấn đề:** README nói orchestrator có "venv siêu nhẹ riêng (không torch)" ([README.md:14](../README.md)) nhưng thực tế cài chung `AIVoice/.venv` ([setup.bat:155](../setup.bat), [run.bat:38](../run.bat)).
- **✅ Chọn Option A — chỉ sửa tài liệu, KHÔNG đổi code/venv:**
  - Sửa [README.md:14](../README.md) (và mô tả kiến trúc liên quan): nói rõ orchestrator **dùng chung `AIVoice/.venv`** (nhẹ vì bản thân orchestrator không `import torch`; các bước AI nặng vẫn chạy subprocess và tự nhả VRAM). Bỏ câu "venv siêu nhẹ riêng".
  - Không sửa `setup.bat`/`run.bat`; không tạo venv mới.
- **Nghiệm thu:** README khớp `setup.bat`/`run.bat`; không có thay đổi hành vi runtime.

### P4.4 — Dọn thay đổi treo trong submodule AIVoice  [SUBMODULE]
- Đang có `M apps/MediaComposer/webui/Main.py` và thư mục chưa track `apps/MediaComposer/ai_images/`.
- **Việc:** xem diff `Main.py` → commit (nếu chủ ý) hoặc revert; quyết định `ai_images/` (gitignore hay xoá). Theo quy trình con-trước rồi cập nhật con trỏ ở repo tổng.
- **Nghiệm thu:** `cd AIVoice && git status` sạch; con trỏ submodule ở repo tổng nhất quán.

### P4.5 — Bug tồn đọng nhỏ
- **BUG-7 (dead code):** [pipeline.py:477-487](../orchestrator/pipeline.py) — clamp `max(0,…)` nằm trong `if crop_x>=0…` nên vô tác dụng → xoá block clamp thừa (giữ nhánh nối `--crop-*`).
- **S1 (webui):** `0 || null` nuốt giá trị 0 hợp lệ ở [app.js:777,780,782](../webui/app.js) (`stroke_width`, `bg_alpha`, `custom_position`) → thay bằng kiểm rỗng tường minh `v === "" ? null : Number(v)`.
- **[SUBMODULE] F1 (fontsdir):** font tùy chỉnh không áp dụng do thiếu `fontsdir` trong filter subtitles của AIVoice — xem [REVIEW-media-workflows-r3.md](REVIEW-media-workflows-r3.md#f1). Để riêng vì nằm trong submodule + cần test E2E burn phụ đề.
- **Nghiệm thu:** BUG-7 test ở P3.3; S1 nhập 0 lưu đúng 0.

---

## Tổng kết thứ tự & cổng kiểm

| Phase | Nội dung | Cổng kiểm sau phase |
|-------|----------|---------------------|
| P1 | Secret, CORS, gộp config, model default, schema | `pytest -q` xanh; `git grep sk-gemini` rỗng |
| P2 | Helper `_resolve_llm`, sửa except, dọn ruff, CI ruff full | `ruff check orchestrator tests` = 0; `pytest -q` xanh |
| P3 | Test slugify / video_merger / bước 1·4·5 | `pytest -q` xanh (nhiều test hơn) |
| P4 | Dọn script, requirements, README, submodule, S1/BUG-7 | `pytest -q` xanh; root & submodule sạch |

## Quyết định đã chốt
1. ✅ **Model proxy (P1.4):** `gemini-2.5-flash`.
2. ✅ **Venv (P4.3):** **Option A** — chỉ sửa README cho khớp thực tế (dùng chung `AIVoice/.venv`), không đổi code/venv.
3. ✅ **CI/CD (P2.4):** dựng theo mô hình chuyên nghiệp (2 job lint/test, trigger `dev/**`, cache, concurrency, cổng test khi release, Dependabot). File workflow do **bạn push** bằng token scope `workflow` (hoặc cấp scope cho tôi).

**Plan đã hoàn chỉnh — không còn quyết định treo.** Chờ bạn ra hiệu "bắt đầu" để tôi thực thi tuần tự P1 → P4.
