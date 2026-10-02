# 2. Lý thuyết cơ bản và công nghệ

Hội đồng KTPM hay hỏi lý thuyết theo kiểu "X là gì, sao em dùng X, sao không dùng Y". Mỗi câu dưới đây trả lời theo ba nhịp: định nghĩa một câu → trong dự án dùng ở đâu, tham số nào → vì sao chọn thay vì phương án khác.

Bốn công thức phải viết được lên bảng: attention, CFG, LoRA, IDF.

```
\text{Attention}(Q,K,V)=\mathrm{softmax}\!\left(\frac{QK^\top}
{\sqrt{d_k}}\right)V \qquad \hat\varepsilon=\varepsilon_{neg}+s\,
(\varepsilon_{pos}-\varepsilon_{neg}),\ s=5.0 \qquad \Delta W=BA,\ r\ll d
\qquad \mathrm{IDF}(t)=\ln\frac{N}{1+df(t)}
```

## 2.1 Backend, tiến trình, giao tiếp web

### 2.1.1 Process và thread khác nhau thế nào? Dự án dùng cái nào ở đâu?
- **Mức:** ★
- **Ý trả lời chính:** Process có không gian nhớ riêng, OS thu hồi toàn bộ tài nguyên (cả VRAM) khi thoát; thread chia chung bộ nhớ trong một process. Subprocess cho worker AI (crawl, dịch, TTS, video); thread cho reader log, auto-run, nguồn local/ai_write, merge video, uvicorn.
- **Tra ở:** ch01

### 2.1.2 GIL là gì? Sao dùng thread mà vẫn nhanh?
- **Mức:** ★★
- **Ý trả lời chính:** GIL chỉ cho một thread chạy bytecode Python tại một thời điểm. Việc chờ I/O (HTTP tới Ollama, đọc pipe) nhả GIL, nên `ThreadPoolExecutor(max_workers=4)` sinh prompt vẫn giảm thời gian chờ. Việc nặng CPU/GPU đã nằm ở process khác.
- **Tra ở:** ch06 câu 13

### 2.1.3 Sao dùng `subprocess` mà không dùng `multiprocessing` ?
- **Mức:** ★★
- **Ý trả lời chính:** `multiprocessing` dùng chung interpreter/venv với cha. `subprocess` chạy python của venv khác ( `toolCaoTruyen/.venv` , `AIVoice/.venv` ), giao tiếp qua argv → stdout → exit code, kill được cả cây.
- **Tra ở:** ch01, `pipeline.py:150,` `411`

### 2.1.4 REST là gì? API của em có RESTful không?
- **Mức:** ★
- **Ý trả lời chính:** Kiến trúc dùng HTTP method trên tài nguyên có URL, stateless, dữ liệu JSON. API có 39 route: `POST /api/stories` , `POST` `/api/pipeline/step1..5` , `GET` `/api/pipeline/status/{task_key}` … Gần REST; vài endpoint kiểu lệnh ( `/api/chat/unload` , `/api/maintenance/rebuild-db` ) là RPC trên HTTP.
- **Tra ở:** ch01, ch02

### 2.1.5 Mã trạng thái HTTP em dùng những mã nào, ý nghĩa?
- **Mức:** ★
- **Ý trả lời chính:** 200 OK; 400 bước đang chạy/auto-run đang chạy; 404 không tìm thấy; 409 trùng tên truyện, hoặc GPU đang heavy (chatbot trả kèm `lookup_answer` ); 429 chatbot đang trả lời câu trước ( `single_chat_lock` ).
- **Tra ở:** ch01, ch12

### 2.1.6 FastAPI là gì? Sao không dùng Flask/Django?
- **Mức:** ★
- **Ý trả lời chính:** Framework ASGI, validate request bằng pydantic, tự sinh OpenAPI `/docs` , hỗ trợ async và `StreamingResponse` cho SSE/NDJSON. Django nặng (ORM, admin) không cần; Flask là WSGI, stream dài và async kém tiện hơn.
- **Tra ở:** ch01

### 2.1.7 ASGI khác WSGI? uvicorn là gì?
- **Mức:** ★★
- **Ý trả lời chính:** WSGI đồng bộ, mỗi request giữ một worker; ASGI bất đồng bộ, giữ được kết nối dài (SSE). uvicorn là ASGI server chạy FastAPI, trong dự án chạy ở thread daemon của `desktop.py` .
- **Tra ở:** ch01

### 2.1.8 Một request SSE kéo dài hàng giờ có làm đứng server không?
- **Mức:** ★★
- **Ý trả lời chính:** Không. Endpoint `def` và generator đồng bộ được Starlette chạy trong threadpool, nên `q.get` chặn không làm đứng event loop; endpoint `async def` như `/api/chat` dùng `await asyncio.to_thread(...)` .
- **Tra ở:** ch01 câu 8

### 2.1.9 Pydantic dùng để làm gì?
- **Mức:** ★
- **Ý trả lời chính:** Khai báo schema request ( `Step1Schema` … `Step5Schema` , `AutoRunSchema` ), tự validate kiểu/giá trị mặc định, sai thì trả 422.
- **Tra ở:** `main.py:104-212`

### 2.1.10 SSE là gì? Khác WebSocket và polling ra sao?
- **Mức:** ★
- **Ý trả lời chính:** HTTP response `text/event-stream` không đóng, server ghi dần `data: ...\n\n` , một chiều, `EventSource` tự reconnect. WebSocket hai chiều qua Upgrade, phức tạp hơn; polling tốn request và trễ. Log chỉ đi một chiều, lệnh dừng đã có REST → SSE đủ.
- **Tra ở:** ch02 câu 2, `main.py:509-` `515`

### 2.1.11 `[PING]` để làm gì?
- **Mức:** ★★
- **Ý trả lời chính:** Heartbeat khi queue rỗng quá 1 s: giữ kết nối sống, cho vòng lặp kiểm task đã xong chưa, phát hiện client ngắt để thread không kẹt. Dự án gửi message thật `data: [PING]` thay cho comment `:` nên client tự bỏ qua.
- **Tra ở:** ch02 câu 6

### 2.1.12 Server đóng stream SSE thì trình duyệt có hiểu là xong không?
- **Mức:** ★★
- **Ý trả lời chính:** Không, `EventSource` coi là rớt mạng và tự nối lại. Vì vậy server gửi dòng quy ước `[SYSTEM] Process completed` `(exit_code=N).` , client `source.close()` khi nhận.
- **Tra ở:** `app.js:1312-1326`

### 2.1.13 JSON Lines / NDJSON là gì, dùng ở đâu?
- **Mức:** ★
- **Ý trả lời chính:** Mỗi dòng là một object JSON độc lập, đọc được theo luồng. Worker in `{"event": ...}` ra stdout ( `log_json` , flush ngay); chatbot stream NDJSON ( `delta/done/agent_action` ).
- **Tra ở:** ch01, ch12

### 2.1.14 Producer–consumer trong dự án nằm ở đâu? Sentinel là gì?
- **Mức:** ★★
- **Ý trả lời chính:** Reader thread (producer) `readline()` từ pipe → `queue.Queue` (thread-safe) → SSE generator (consumer). Khi process xong, sau callback, đặt `None` (sentinel) vào queue để báo hết luồng.
- **Tra ở:** `process_manager.py:66-` `119`

### 2.1.15 Exit code là gì? Vì sao dựa vào nó chứ không dựa vào log?
- **Mức:** ★
- **Ý trả lời chính:** Số nguyên process trả về OS khi kết thúc, 0 là thành công. Log chỉ để hiển thị, có thể sai định dạng; exit code là hợp đồng chuẩn của OS.
- **Tra ở:** ch00 câu 4

### 2.1.16 Máy trạng thái (FSM) là gì? FSM của em có ép thứ tự bước không?
- **Mức:** ★★
- **Ý trả lời chính:** Tập trạng thái + sự kiện chuyển. Truyện đi CREATED → CRAWLING/TRANSLATING → TRANSLATED → VOICE_* → VIDEO_* (+ *_FAILED, CANCELLED). Không ép: điều kiện thật là file trên đĩa, để chạy lại từng bước linh hoạt.
- **Tra ở:** ch00 §5.6

### 2.1.17 Idempotent là gì? Ở đâu trong hệ thống?
- **Mức:** ★
- **Ý trả lời chính:** Chạy lại nhiều lần cho cùng kết quả. Dịch bỏ qua chương có `[VI]` ; TTS bỏ qua chương có `.wav` ; Bước 3 đọc `batch_state.json` ; chuẩn hóa tên chương lần 2 không đổi; `model_preflight` có marker `.preflight_ok` .
- **Tra ở:** ch13 câu 13

### 2.1.18 Lock/mutex dùng ở đâu?
- **Mức:** ★★
- **Ý trả lời chính:** `threading.Lock` bảo vệ bảng task trong `ProcessManager` ( `is_running` ), `single_chat_lock` cho chatbot, lock khi pull model Ollama.
- **Tra ở:** ch01, ch12

### 2.1.19 CORS là gì? Đã cấu hình CORS thì API an toàn chưa?
- **Mức:** ★
- **Ý trả lời chính:** Chính sách trình duyệt cho phép trang ở origin khác đọc phản hồi. Chưa đủ: CORS không phải xác thực, curl bỏ qua CORS. Lớp bảo vệ chính là bind `127.0.0.1` ; chương trình khác trên cùng máy vẫn gọi được.
- **Tra ở:** ch13 câu 16

### 2.1.20 SPA là gì? Sao không dùng React/Vue?
- **Mức:** ★
- **Ý trả lời chính:** Trang đơn, chuyển tab bằng ẩn/hiện section. UI chủ yếu là form + console log cho một người; JS thuần không cần Node/bundler, installer chỉ cần Python. Đổi lại `app.js` dài ~2.100 dòng, phải tự đồng bộ DOM.
- **Tra ở:** ch02 câu 1

### 2.1.21 pywebview/WebView2 là gì? Sao không mở trình duyệt?
- **Mức:** ★
- **Ý trả lời chính:** WebView2 là engine Chromium nhúng của Windows; pywebview bọc thành cửa sổ desktop 1280×840 để trông như ứng dụng. GUI loop phải chạy ở main thread nên uvicorn chạy thread phụ. Thiếu WebView2 thì tự mở trình duyệt.
- **Tra ở:** `desktop.py:101-108, 141-` `217`

### 2.1.22 Virtualenv là gì? Sao mỗi submodule một venv?
- **Mức:** ★
- **Ý trả lời chính:** Môi trường Python cô lập có bộ thư viện riêng. Selenium, torch, onnxruntime, PaddleOCR xung đột phiên bản/DLL; tách venv thì không phải hòa giải dependency.
- **Tra ở:** Q9

### 2.1.23 Git submodule là gì? Sao dùng?
- **Mức:** ★★
- **Ý trả lời chính:** Repo con được trỏ tới một commit cụ thể trong repo cha. `toolCaoTruyen` và `AIVoice` phát triển và chạy độc lập được; khi clone phải `--recursive` , push submodule trước rồi mới cập nhật con trỏ ở repo cha.
- **Tra ở:** ch00 §6

### 2.1.24 Truyền cấu hình qua biến môi trường, tham số CLI, file config khác nhau gì?
- **Mức:** ★★
- **Ý trả lời chính:** Bước 3 dùng cả ba: `config.toml` (sd_*), CLI (style, checkpoint, render mode, LLM), env ( `MC_STORAGE_TASKS` , `CUDA_VISIBLE_DEVICES` ). Env và file không lộ trong danh sách process; CLI thì lộ, nên API key không nên đi qua CLI.
- **Tra ở:** ch01 câu 12, Q17

### 2.1.25 XSS là gì? Giao diện chống XSS chưa?
- **Mức:** ★
- **Ý trả lời chính:** Chèn script vào trang qua dữ liệu hiển thị. Log dùng `textContent` ; chatbot `escapeHTML` trước khi render markdown; bảng thống kê escape bằng `_statEsc` . Còn vài chỗ chưa escape (tên file video, slug trong thẻ chatbot), rủi ro thấp vì dữ liệu do máy tự sinh.
- **Tra ở:** ch02 câu 14

## 2.2 LLM và dịch (Bước 1)

### 2.2.1 LLM là gì, hoạt động thế nào?
- **Mức:** ★
- **Ý trả lời chính:** Transformer decoder-only học dự đoán token kế tiếp. Sinh văn bản là vòng lặp: tính phân phối token kế → lấy mẫu → nối vào → lặp tới stop token. Instruction tuning giúp nó hiểu "hãy dịch" là nhiệm vụ.
- **Tra ở:** ch04 câu 1, Q23

### 2.2.2 Token, tokenizer, BPE là gì?
- **Mức:** ★
- **Ý trả lời chính:** Token là mảnh chữ model xử lý. BPE bắt đầu từ byte/ký tự, lặp lại việc gộp cặp hay gặp nhất; byte- level BPE (Qwen, Llama) không bao giờ OOV. Tiếng Việt có dấu tốn nhiều token hơn nên `num_predict` `= max(2048, chunk×15)` .
- **Tra ở:** ch04 §2.1, `ollama_translator.py:42`

### 2.2.3 Embedding và positional encoding là gì?
- **Mức:** ★
- **Ý trả lời chính:** Embedding tra token ID ra vector "tọa độ ý nghĩa". Transformer xử lý song song nên cần vị trí; Qwen/Llama dùng RoPE (xoay Q/K theo vị trí).
- **Tra ở:** ch04 §2.2

### 2.2.4 Giải thích công thức attention. Vì sao chia √d_k?
- **Mức:** ★★
- **Ý trả lời chính:** Q là "câu hỏi", K là "nhãn", V là "nội dung"; QKᵀ đo độ khớp mọi cặp token; chia √d_k giữ phương sai ổn định để softmax không bão hòa; softmax ra trọng số tổng 1; nhân V lấy trung bình có trọng số. Ví dụ "hắn" chú ý lên "Cố An" để dịch đúng đại từ.
- **Tra ở:** ch04 câu 2

### 2.2.5 Self-attention, cross- attention, multi-head, GQA khác nhau?
- **Mức:** ★★
- **Ý trả lời chính:** Self: Q/K/V cùng chuỗi. Cross: Q từ chuỗi này, K/V từ chuỗi khác (U- Net đọc text). Multi-head: nhiều phép chiếu song song học quan hệ khác nhau. GQA: nhiều head Q dùng chung ít head K/V để giảm KV cache (Qwen2.5-7B có 4 KV- head).
- **Tra ở:** ch04, ch07

### 2.2.6 Encoder-decoder, decoder-only khác gì?
- **Mức:** ★★
- **Ý trả lời chính:** Transformer gốc 2017 có encoder + decoder cho dịch máy (Whisper vẫn dùng kiểu này). LLM hiện đại (GPT, Qwen, Llama) là decoder- only, dịch bằng prompt.
- **Tra ở:** ch04 §2.4, ch10

### 2.2.7 Temperature, top_p, top_k là gì? Vì sao dịch dùng thấp, sáng tác dùng cao?
- **Mức:** ★
- **Ý trả lời chính:** Temperature chia logit trước softmax (p ∝ exp(z/T)): thấp → phân phối nhọn, gần tham lam, ổn định. top_p lấy mẫu trong nhóm chiếm p xác suất; top_k giới hạn k token. Dịch 0.02–0.2 (hạ còn 0.02 khi rò chữ Hán), sáng tác 0.85, chatbot 0.4/top_p 0.9; HY-MT2 0.7/top_k 20/top_p 0.6 theo nhà phát hành.
- **Tra ở:** ch04 câu 3, `ollama_translator.py:450`

### 2.2.8 Context window là gì? Vượt thì sao?
- **Mức:** ★
- **Ý trả lời chính:** Tổng token prompt + output trong một lượt ( `num_ctx` ). Attention O(n²), KV cache tăng tuyến tính nên bị giới hạn. Vượt thì cắt đầu hoặc dừng sớm. Dịch 2048–2560, chatbot 8192, cảnh báo truncated khi prompt ≥ 95%.
- **Tra ở:** ch04 câu 15, `llm.py:160`

### 2.2.9 KV cache là gì, tốn bao nhiêu?
- **Mức:** ★★
- **Ý trả lời chính:** Lưu K/V của mọi token đã qua để không tính lại. ≈ 2 × số layer × số KV-head × head_dim × num_ctx × 2 byte; Qwen2.5-7B ở 2048 token ≈ 115 MB.
- **Tra ở:** ch04 §4

### 2.2.10 Quantization là gì? Q4_K_M, Q8_0 nghĩa là gì? Ảnh hưởng chất lượng?
- **Mức:** ★★
- **Ý trả lời chính:** Lưu trọng số bằng ít bit kèm hệ số scale theo khối, w ≈ s·q. Q4_K_M ≈ 4,85 bit (7,6B tham số còn ~4,6 GB); Q8_0 8 bit (HY-MT2 1,8B ~2 GB). Giảm nhẹ chất lượng, giảm nhiều khi xuống 2–3 bit.
- **Tra ở:** ch04 câu 4, Q25

### 2.2.11 Ollama là gì? Sao không gọi thư viện Python trực tiếp?
- **Mức:** ★
- **Ý trả lời chính:** Runtime/server cục bộ bọc llama.cpp: pull/create model, tự nạp GPU, API HTTP cổng 11434 (native + OpenAI-compatible). Nhờ HTTP, bước dịch không cần cài PyTorch; đổi model chỉ đổi tên; `keep_alive=0` nhả VRAM trước khi sinh ảnh.
- **Tra ở:** ch04 câu 5, Q24

### 2.2.12 GGUF và Modelfile là gì? Sao phải tự viết Modelfile cho HY-MT2?
- **Mức:** ★★
- **Ý trả lời chính:** GGUF: file trọng số lượng tử + metadata của llama.cpp. Modelfile khai `FROM` , `TEMPLATE` , `PARAMETER` . Chat template tự sinh của HY-MT2 bị hỏng (model chỉ trả "onse"), nên em viết lại theo special token gốc và stop token.
- **Tra ở:** `toolCaoTruyen/ollama_models/Modelfile.hy-` `mt2:3-17`

### 2.2.13 Vì sao chạy LLM local mà không dùng GPT/Gemini?
- **Mức:** ★★
- **Ý trả lời chính:** Không gửi nội dung ra ngoài, không phí theo token, chạy offline. Gemini vẫn là tùy chọn; client OpenAI-compatible nên đổi chỉ cần đổi `base_url` /model.
- **Tra ở:** ch04, ch06 câu 14

### 2.2.14 Model nào dùng cho việc gì?
- **Mức:** ★★
- **Ý trả lời chính:** Dịch: `qwen2.5:7b-instruct` (Ollama) hoặc HY-MT2 1,8B chuyên dịch; phân cảnh/prompt Bước 3: Qwen2.5 (cấu hình máy hiện đặt 7B); chatbot `qwen2.5:3b` (~2,8 GB) để sống chung GPU. Kiểm lại `configs/global_config.json` trên máy demo trước khi nói.
- **Tra ở:** ch04, ch06, ch12

### 2.2.15 Model chuyên dịch (HY- MT2) và model chat (Qwen) khác gì trong code?
- **Mức:** ★★
- **Ý trả lời chính:** MT dùng một message user theo template cố định, glossary chèn theo cú pháp terminology intervention, không system prompt/few-shot; nhẹ, ít "chém" nhưng không trích xuất JSON được. Chat dùng system prompt 9 yêu cầu + genre + glossary.
- **Tra ở:** ch04 câu 11

### 2.2.16 Vì sao chia chương thành chunk 350–500 ký tự?
- **Mức:** ★
- **Ý trả lời chính:** Model nhỏ với input dài hay bỏ câu, sót chữ Hán; chunk nhỏ giữ `num_ctx` 2048 tiết kiệm VRAM; lỗi khoanh vùng từng đoạn nên vá rẻ. Chia theo ranh giới `\n\n` . Gemini context lớn dùng 1000.
- **Tra ở:** `ollama_translator.py:67-101`

### 2.2.17 Làm sao bảo đảm bản dịch không sót chữ Hán?
- **Mức:** ★★★
- **Ý trả lời chính:** Dịch 2 tầng. Tầng 1: cắt cụt ( `done_reason=='length'` ) thì gọi lại với num_predict ×1.5; còn chữ Hán thì dịch lại ở 0.02. Tầng 2: kiểm 3 lỗi (untranslated, leak, content_missing), Zero Tolerance một ký tự `[一-]` cũng là lỗi; vá tối đa 3 lượt; thất bại thì chèn `[[MISSING_CHUNK:n]]` + `.translation_report.json` . Kết quả 0/214.034.
- **Tra ở:** Q26

### 2.2.18 Tiêu chí 0 ký tự Hán có chứng minh dịch đúng nghĩa không?
- **Mức:** ★★
- **Ý trả lời chính:** Không. Nó đo "không sót chữ", không đo độ đúng. Chưa đo BLEU/COMET hay đánh giá người; hướng: LLM-as-judge/COMET trên mẫu có bản dịch chuẩn.
- **Tra ở:** ch04 câu 14

### 2.2.19 Glossary hoạt động thế nào? Sao chỉ 20 thuật ngữ?
- **Mức:** ★★
- **Ý trả lời chính:** Ba lớp `common_idioms <` `global_glossary.json <` `glossary.json` của truyện, chỉ thêm key mới. Mỗi chunk chỉ chèn thuật ngữ thật sự xuất hiện, tối đa 20, để không tốn context và không nhiễu model nhỏ. Sau mỗi chương LLM trích thuật ngữ mới (JSON mode).
- **Tra ở:** Q27, `glossary_manager.py`

### 2.2.20 Gemini từ chối dịch vì chính sách an toàn thì sao?
- **Mức:** ★★
- **Ý trả lời chính:** `finishReason` SAFETY/PROHIBITED_CONTENT → `GeminiSafetyBlockError` ; riêng chunk đó chuyển sang `OllamaTranslator` , chunk sau quay lại Gemini. Đã đặt `BLOCK_NONE` .
- **Tra ở:** `gemini_translator.py:496-525`

### 2.2.21 Sáng tác nhiều chương giữ mạch truyện thế nào khi LLM không có trí nhớ?
- **Mức:** ★★
- **Ý trả lời chính:** Rolling summary: sau mỗi chương tóm tắt 2–3 câu (temperature 0.3), nối vào và giữ 2.500 ký tự cuối. Số từ mỗi chương kẹp [200, 4000], mặc định 800.
- **Tra ở:** `story_writer.py:52-87` , `pipeline.py:28-33`

### 2.2.22 Prompt engineering, few-shot, JSON mode là gì?
- **Mức:** ★
- **Ý trả lời chính:** Thiết kế lời nhắc để điều khiển đầu ra; few-shot = kèm vài ví dụ mẫu (dùng cho qwen3:8b khi dịch); JSON mode ép cú pháp JSON hợp lệ ( `response_format=json_object` ) cho trích glossary, nhân vật, chia cảnh.
- **Tra ở:** ch04, ch06

### 2.2.23 "Ảo giác" (hallucination) là gì? Em chống thế nào?
- **Mức:** ★
- **Ý trả lời chính:** Model sinh nội dung trôi chảy nhưng sai. Chống bằng: temperature thấp, kiểm bất biến bằng code (chia cảnh), Zero Tolerance (dịch), cổng điểm + quy tắc ghi nguồn (chatbot), số liệu do code đếm chứ không để LLM tự nói.
- **Tra ở:** ch06, ch12

### 2.2.24 Vì sao có `orchestrator/llm.py` riêng khi `toolCaoTruyen` đã có translator?
- **Mức:** ★★
- **Ý trả lời chính:** Translator chạy trong subprocess, venv riêng. `llm.py` phục vụ tính năng trong orchestrator: sáng tác, chatbot streaming, unload VRAM; chuẩn OpenAI-compatible nên một hàm `chat()` gọi được Gemini, Ollama `/v1` và proxy.
- **Tra ở:** ch04 câu 12

### 2.2.25 Có dùng LangChain không? Sao không?
- **Mức:** ★★
- **Ý trả lời chính:** Không. Gọi HTTP trực tiếp để kiểm soát `num_ctx` , `keep_alive` , `think=false` ; thêm framework là thêm lớp trừu tượng không cần.
- **Tra ở:** ch14 §2.3

## 2.3 Cào truyện và nguồn truyện (Bước 1a)

### 2.3.1 Bước 1 có mấy nguồn truyện?
- **Mức:** ★
- **Ý trả lời chính:** Ba: thư mục cục bộ ( `chapter_naming.normalize_dir` ), AI tự sáng tác ( `story_writer` ), cào web (subprocess `adapter_cli.py crawl` ).
- **Tra ở:** `pipeline.py:135-390`

### 2.3.2 Web crawler là gì? HTML parsing, DOM, CSS selector là gì?
- **Mức:** ★
- **Ý trả lời chính:** Chương trình tải trang và trích dữ liệu. BeautifulSoup dựng cây DOM từ HTML; CSS selector ( `div.txtnav` ) chỉ đường tới node. Code thử 6 selector nội dung trong vòng lặp theo thứ tự ưu tiên.
- **Tra ở:** ch03 câu 8, `shuba69.py:223-235`

### 2.3.3 Sao dùng Selenium mà không dùng `requests` ?
- **Mức:** ★★
- **Ý trả lời chính:** Site nằm sau Cloudflare, trang "Just a moment" cần chạy JS để cấp cookie `cf_clearance` ; `requests` không chạy JS, TLS fingerprint khác Chrome. Selenium điều khiển Chrome thật; chậm hơn vài giây/chương, không đáng kể so với TTS/SD.
- **Tra ở:** `crawler_engine.py:14-76`

### 2.3.4 Sao không chạy headless?
- **Mức:** ★★
- **Ý trả lời chính:** Cloudflare phát hiện headless. Cửa sổ được đẩy ra ngoài màn hình ( `--window-` `position=-2400,0` ).
- **Tra ở:** `crawler_engine.py:23`

### 2.3.5 Việc ẩn dấu hiệu bot có vi phạm đạo đức không?
- **Mức:** ★★★
- **Ý trả lời chính:** Thừa nhận crawler có kỹ thuật vượt Cloudflare (tắt `AutomationControlled` , ẩn `navigator.webdriver` qua CDP) và chưa đọc robots.txt. Vì vậy nguồn mặc định thiết kế là local/public domain, crawler chỉ là tùy chọn kỹ thuật.
- **Tra ở:** ch03 câu 3, 14

### 2.3.6 Sao đi theo nút "`下一章`" thay vì tăng ID chương? Crawler duyệt BFS hay DFS?
- **Mức:** ★★
- **Ý trả lời chính:** ID trên site không liên tục; theo link thật luôn đúng thứ tự, chương cuối trỏ về `/book/` nên biết hết truyện. Không phải BFS/DFS: đi một chuỗi như danh sách liên kết, `visited_urls` phát hiện chu trình.
- **Tra ở:** `shuba69.py:305-366`

### 2.3.7 Mất mạng giữa chừng thì tải tiếp thế nào?
- **Mức:** ★★
- **Ý trả lời chính:** Sau mỗi chương ghi `.crawler_state.json` ( `last_chapter_index` , `next_url` , `reached_end` ). `--continue-download` nhảy tới `next_url` , hoặc tra mục lục tìm chương `disk_index + 1` ; không xác định được thì dừng và báo.
- **Tra ở:** `crawler_engine.py:345-464`

### 2.3.8 Tránh spam server, lặp vô hạn thế nào?
- **Mức:** ★
- **Ý trả lời chính:** Nghỉ ngẫu nhiên 1,0–2,5 s giữa các chương; tối đa 10 lần thử mỗi URL; `visited_urls` ; `finally: driver.quit()` .
- **Tra ở:** ch03 câu 6

### 2.3.9 Xử lý encoding tiếng Trung (GBK) thế nào?
- **Mức:** ★★
- **Ý trả lời chính:** Không tự decode byte: `page_source` đã là Unicode do Chrome decode theo charset. Ghi UTF-8, log `ensure_ascii=False` , đặt `PYTHONIOENCODING=utf-8` cho process con.
- **Tra ở:** `process_manager.py:43`

### 2.3.10 Lọc quảng cáo khỏi nội dung thế nào?
- **Mức:** ★
- **Ý trả lời chính:** Hai tầng: `decompose` các thẻ script/style/iframe/điều hướng; bỏ dòng khớp 16 regex `AD_PATTERNS` .
- **Tra ở:** `shuba69.py:10-27, 248-303`

### 2.3.11 Thêm nguồn truyện mới cần làm gì?
- **Mức:** ★
- **Ý trả lời chính:** Strategy + Registry: class kế thừa `BaseSourceParser` cài `build_chapter_url` , `get_html` , `parse_chapter` , `is_valid_response` , rồi thêm một dòng vào `SOURCES` . Engine không sửa.
- **Tra ở:** `sources/registry.py:7-10`

### 2.3.12 Cào không được chương nào thì hệ thống báo gì?
- **Mức:** ★★★
- **Ý trả lời chính:** Trả lời thật: log `crawl_warn "No chapters` `downloaded."` nhưng adapter vẫn thoát mã 0, nên orchestrator vẫn sang dịch/CRAWLED. Sửa: engine trả số chương tải được, adapter `sys.exit(1)` khi bằng 0.
- **Tra ở:** `adapter_cli.py:60-64`

### 2.3.13 Nguồn local: chuẩn hóa tên chương làm gì?
- **Mức:** ★★
- **Ý trả lời chính:** Regex nhận dạng số/tên chương, đánh số lại thành `Chương 0001 - <tên>.md` ; chạy lần 2 không đổi (idempotent, có test).
- **Tra ở:** `orchestrator/chapter_naming.py`

### 2.3.14 Tìm truyện bằng tên tiếng Việt hoạt động ra sao?
- **Mức:** ★★
- **Ý trả lời chính:** LLM dịch tên Hán-Việt sang tên Trung (few-shot), tìm qua DuckDuckGo → Yahoo → form POST; rỗng thì LLM sinh 5 tên thay thế. Tính năng nằm ở UI riêng của tool; WebUI chính nhận ID/link.
- **Tra ở:** `core/intelligent_search.py`

### 2.3.15 Chọn nguồn metruyenchu trên UI thì sao?
- **Mức:** ★★★
- **Ý trả lời chính:** Bug đã biết: tên option UI ( `metruyenchu` , `tangthuvien` ) không khớp key registry ( `metruyenchuvn` ) nên `get_source` ném `ValueError` . Sửa bằng bảng ánh xạ tên. (Cấu hình máy hiện có `crawler.default_site = biquge` — kiểm nguồn này có trong registry không.)
- **Tra ở:** ch14 §2.3

## 2.4 Tổng hợp giọng nói và âm thanh (Bước 2)

### 2.4.1 TTS hoạt động thế nào?
- **Mức:** ★
- **Ý trả lời chính:** Văn bản được chuẩn hóa (số → chữ), chuyển thành âm vị/token, mạng neural sinh đặc trưng âm (mel hoặc latent), vocoder chuyển thành sóng âm.
- **Tra ở:** Q29

### 2.4.2 Bước 2 nhận gì, trả gì?
- **Mức:** ★
- **Ý trả lời chính:** Nhận `.md` có `" -` `[VI] "` trong `raw/` (hoặc `translated/` nếu có); trả `.wav` cùng tên, cùng thư mục; bỏ qua chương đã có `.wav/.mp3` .
- **Tra ở:** `pipeline.py:403-431` , `adapter_tts_cli.py:157-212`

### 2.4.3 Vì sao 5 engine? Engine nào mặc định?
- **Mức:** ★
- **Ý trả lời chính:** Đánh đổi: Edge (online, tự nhiên, nhanh, cần mạng), Piper (offline, rất nhẹ, CPU), Kokoro/VieNeu (offline, tự nhiên hơn, cần GPU), XTTSv2 (clone giọng, nặng ~5,6 GB). Tài liệu ôn tập ghi mặc định Edge; cấu hình máy hiện đặt `tts.default_engine` `= kokoro` — nói theo máy demo.
- **Tra ở:** Q30, `configs/global_config.json`

### 2.4.4 VITS khác Tacotron + HiFi- GAN thế nào?
- **Mức:** ★★
- **Ý trả lời chính:** VITS huấn luyện end- to-end một mạng: VAE + normalizing flow + MAS (học alignment) + stochastic duration predictor + loss GAN; không có mel trung gian giữa hai model train riêng nên ít lỗi tích lũy, suy luận nhanh.
- **Tra ở:** ch05 câu 4

### 2.4.5 `length_scale` là gì?
- **Mức:** ★
- **Ý trả lời chính:** Hệ số nhân trường độ âm vị; `length_scale =` `1/speed` (speed 1,25 → 0,8 → đọc nhanh 25%).
- **Tra ở:** `piper.py:85-86`

### 2.4.6 Voice cloning zero-shot hoạt động ra sao? Rủi ro?
- **Mức:** ★★
- **Ý trả lời chính:** XTTSv2 tính từ audio mẫu `gpt_cond_latent` (điều kiện GPT) và `speaker_embedding` (điều kiện decoder); GPT sinh token âm thanh, decoder ra sóng 24 kHz; không train thêm, cache latent. Rủi ro giả giọng, giấy phép Coqui hạn chế thương mại.
- **Tra ở:** `clone.py:198-219`

### 2.4.7 Vì sao chunk 30 từ / 240 ký tự?
- **Mức:** ★★
- **Ý trả lời chính:** XTTSv2 tiếng Việt giới hạn ~250 ký tự (vượt → CUDA assertion); model tự hồi quy câu dài dễ lặp/nuốt chữ; chunk nhỏ cho phép song song và retry. Thuật toán hai chiều: bẻ câu dài, gộp câu ngắn.
- **Tra ở:** `text.py:36`

### 2.4.8 Vì sao số luồng khác nhau theo engine?
- **Mức:** ★★
- **Ý trả lời chính:** GPU (clone/kokoro/vieneu) = 1 để chống OOM và model không thread- safe; Piper ONNX = 6; Edge = 3 có stagger tránh rate-limit.
- **Tra ở:** `src/main.py:249-273`

### 2.4.9 Chuẩn hóa tiếng Việt làm gì? Vì sao ép NFC?
- **Mức:** ★
- **Ý trả lời chính:** NFC, chữ thường, ký hiệu (% → "phần trăm"), viết tắt, số → chữ ( `num2words` ). Chữ có dấu mã hóa được 1 code point (NFC) hoặc nhiều (NFD); tokenizer chỉ nhận một dạng. Hạn chế: "3,5" → "ba phẩy năm mươi", chưa xử lý ngày tháng.
- **Tra ở:** `text.py:168-216`

### 2.4.10 LUFS là gì? Vì sao −14?
- **Mức:** ★
- **Ý trả lời chính:** Độ to cảm nhận theo ITU-R BS.1770 (K- weighting + gating), khác đo peak. −14 LUFS là mức phổ biến của nền tảng stream, các chương to đều nhau; sau đó kẹp peak 0,98 để không clip.
- **Tra ở:** `audio.py:164-193`

### 2.4.11 Semantic cache là gì? Sao mặc định tắt?
- **Mức:** ★★
- **Ý trả lời chính:** Lưu audio theo câu, tra câu mới bằng cosine trên embedding all- MiniLM-L6-v2 + FAISS, ngưỡng 0,95. Tắt vì "giống nghĩa" không đảm bảo "giống chữ" nên có thể đọc sai câu, model embedding là tiếng Anh. Đây là FAISS duy nhất trong repo, không phải của chatbot.
- **Tra ở:** ch05 câu 14

### 2.4.12 Edge lỗi mạng thì sao?
- **Mức:** ★★
- **Ý trả lời chính:** Mỗi chunk retry 5 lần, backoff 2/5/10/15 s. Vẫn lỗi thì chương đó FAILED, chương khác chạy tiếp, process vẫn exit 0 (nên trạng thái vẫn VOICE_GENERATED — hạn chế đã biết); chạy lại chỉ đọc chương thiếu.
- **Tra ở:** `edge.py:36-61`

### 2.4.13 Làm sao TTS không tràn VRAM?
- **Mức:** ★★
- **Ý trả lời chính:** Process riêng; engine GPU 1 worker; XTTSv2 FP16 autocast + SDPA, `empty_cache` sau mỗi chunk/file; process thoát thì driver thu hồi hết. GPU 6 GB nên dùng Edge/Piper để chừa VRAM cho Bước 3.
- **Tra ở:** ch05 câu 15

### 2.4.14 WAV là gì, sample rate, mono/stereo, PCM?
- **Mức:** ★
- **Ý trả lời chính:** WAV là container chứa PCM không nén; sample rate là số mẫu/giây (XTTS 24 kHz, Whisper cần 16 kHz mono). Ghép chunk chèn 0,3 s lặng, fade 0,1 s.
- **Tra ở:** ch05, ch10

## 2.5 Phân cảnh, nhân vật và sinh prompt (Bước 3a)

Lưu ý: bộ tách cảnh được viết lại ngày 01/10 (commit `34cf736` trong AIVoice), sau khi tài liệu ôn tập và báo cáo đã chốt. Các câu dưới đây theo code hiện tại; nếu hội đồng đọc báo cáo thì nói rõ "bản cũ → bản mới, vì sao đổi".

### 2.5.1 Em tách cảnh bằng gì? Có dùng embedding/cosine không?
- **Mức:** ★
- **Ý trả lời chính:** Bằng LLM + luật code, không embedding. Văn bản chia thành đoạn đánh số `[i]` ; LLM (JSON mode, temperature 0.2) chỉ trả mốc bắt đầu cảnh kèm location, time_of_day, characters, action; code dựng cảnh từ các mốc. LLM hiểu ranh giới kể chuyện (đổi địa điểm, nhân vật); cosine chỉ đo độ giống chủ đề.
- **Tra ở:** `semantic_scene_splitter.py:53-` `75`

### 2.5.2 Vì sao đổi từ "LLM viết cả danh sách cảnh" sang "LLM chỉ đánh mốc"?
- **Mức:** ★★★
- **Ý trả lời chính:** Bản cũ: đề ~2.900 token + trả lời ~3.850 token vượt context 4.096 của Ollama → Ollama cắt đầu ngữ cảnh (chính là truyện) → cảnh sau bịa, JSON cụt, chờ 60 s × 3 rồi rơi về `md_parser` . Bản mới: mỗi phần ~1.100 từ, trả lời ≤ 1.000 token, tổng ~3.200 token vừa 4.096.
- **Tra ở:** docstring `semantic_scene_splitter.py:1-` `16`

### 2.5.3 LLM trả JSON sai hoặc bịa chỉ số thì sao?
- **Mức:** ★★★
- **Ý trả lời chính:** Mốc ngoài phần đang xét, trùng, sai kiểu bị bỏ; mốc 0 luôn có. Cảnh = khoảng [start, end) giữa hai mốc liên tiếp nên phủ kín, liên tiếp, đúng thứ tự theo cách dựng, không cần kiểm bất biến sau. Phần nào LLM hỏng (parse lỗi, timeout, rỗng) thì phần đó chia thuần bằng code; response hỏng ghi vào `storage/logs/llm_errors/` . Chỉ trả None khi chương rỗng.
- **Tra ở:** `_boundaries_to_ranges` , `_call_llm_boundaries`

### 2.5.4 Độ dài cảnh được cân thế nào?
- **Mức:** ★★
- **Ý trả lời chính:** `_normalize_ranges` : (1) gộp cảnh liền nhau cùng địa điểm + thời điểm nếu tổng ≤ 60 s; (2) cảnh < 20 s gộp vào hàng xóm "rẻ" hơn; (3) trần số cảnh = ⌈T/30⌉; (4) cảnh > 60 s cắt ở đoạn gần giữa số từ, phần sau gắn "(tiếp)". Mục tiêu ~40 s/cảnh, ~12 cảnh/chương.
- **Tra ở:** `SCENE_MIN_SEC/TARGET/MAX =` `20/40/60`

### 2.5.5 Thời lượng mỗi cảnh tính thế nào?
- **Mức:** ★
- **Ý trả lời chính:** Đọc chính xác độ dài WAV (wave → ffmpeg → pydub, hỏng hết thì báo lỗi, không đoán), chia theo tỷ lệ số từ dur_i = T·w_i/Σw, cảnh cuối ép kết thúc đúng T. Hợp lý vì TTS đọc nguyên văn với tốc độ gần đều.
- **Tra ở:** `srt_mapper.py:197, 322-356` , `audio_utils.py`

### 2.5.6 Vì sao không dùng Whisper để lấy timing?
- **Mức:** ★★
- **Ý trả lời chính:** Whisper medium tốn 2–3 GB VRAM và ~60 s/chương; audio đọc nguyên văn nên đã biết lời, chỉ cần phân bổ thời gian. Adapter ép `use_whisper=False` .
- **Tra ở:** `adapter_video_cli.py:269`

### 2.5.7 Vì sao prompt phải tiếng Anh? Sao không dùng Google Translate?
- **Mức:** ★
- **Ý trả lời chính:** CLIP text encoder học trên cặp ảnh–chú thích tiếng Anh, tokenizer BPE tối ưu tiếng Anh. Model anime fine-tune trên tag kiểu Danbooru, nên LLM vừa dịch vừa chuyển thể thành tag ngắn, bỏ tên riêng, thêm tag khung hình.
- **Tra ở:** ch06 câu 5

### 2.5.8 Nhân vật được trích xuất ra sao?
- **Mức:** ★★
- **Ý trả lời chính:** Đọc tối đa 5 chương đầu (mỗi chương cắt 10.000 ký tự), LLM trả 5–10 nhân vật, khử trùng theo tên, gọi thêm một lần sinh `keywords_en` , lưu vào `context.json` . Hạn chế: "web search" chỉ là lời trong prompt, Ollama không truy cập Internet.
- **Tra ở:** `character_extractor.py`

### 2.5.9 Giữ nhân vật nhất quán ở tầng văn bản thế nào?
- **Mức:** ★★
- **Ý trả lời chính:** Character bible ( `name` , `description` , `keywords_en` ); LLM phải chép nguyên keywords khi nhân vật xuất hiện, không viết tên vào prompt; tên chỉ nằm ở `primary_character` để lấy ảnh ref/LoRA. Hạn chế: LLM trả tên hiển thị còn tra theo slug.
- **Tra ở:** ch06 câu 6

### 2.5.10 Style lock là gì?
- **Mức:** ★★
- **Ý trả lời chính:** Style chỉ có một nguồn `style_prompt.txt` (chép từ preset); LLM bị cấm viết tag style; `strip_style_drift` lọc ~60 tag (masterpiece, anime, tên model…) theo khớp nguyên tag; `build_locked_prompt` xếp style → (action:1.35) → nội dung. Hàm thuần, có 9 unit test.
- **Tra ở:** `style_lock.py:62, 103`

### 2.5.11 Cú pháp `(tag:1.35)` có tác dụng thật không?
- **Mức:** ★★
- **Ý trả lời chính:** Chỉ khi encode qua `compel` : z' = z_empty + 1.35·(z − z_empty) tại token của tag, U-Net chú ý mạnh hơn. Thiếu compel thì code xóa cú pháp. 1.25–1.45 hợp lý, cao hơn dễ méo giải phẫu.
- **Tra ở:** ch06 câu 9

### 2.5.12 Cảnh sau biết bối cảnh cảnh trước bằng cách nào?
- **Mức:** ★★
- **Ý trả lời chính:** Story Director/Director's Note (LLM đọc chương, viết chỉ đạo mỗi cảnh; bản 01/10 đã thu gọn cho vừa 4.096 token); nối location/action/time_of_day vào prompt; khi tách cảnh, phần sau nhận `prev_location` của phần trước.
- **Tra ở:** `llm_prompter.py` , `_call_llm_boundaries`

### 2.5.13 LLM chết giữa chừng thì sao?
- **Mức:** ★★
- **Ý trả lời chính:** Tách cảnh: không retry (retry cùng đề chỉ đốt thêm thời gian), timeout 600 s chỉ để không treo, phần hỏng chia bằng code. Sinh prompt: mỗi cảnh thử 2 lần, hỏng thì prompt dự phòng `scenery,` `wide landscape, no` `humans` ; tất cả hỏng thì `AllPromptsFailedError` dừng luôn để không đốt GPU sinh ảnh rác.
- **Tra ở:** `SPLIT_LLM_TIMEOUT_SEC` , ch06 câu 12

### 2.5.14 Model cấu hình cho Bước 3 không có trong Ollama thì sao?
- **Mức:** ★★
- **Ý trả lời chính:** Từ 01/10: pipeline hỏi danh sách model Ollama; model đã chọn không có thì tự đổi sang `qwen2.5:7b-instruct` hoặc model qwen2.5/llama đầu tiên có sẵn, ghi cảnh báo vào log.
- **Tra ở:** `pipeline.py` `start_step_3_video`

### 2.5.15 Điểm yếu còn lại của bước này?
- **Mức:** ★★
- **Ý trả lời chính:** Không retry tầng tách cảnh; khử trùng nhân vật theo tên chính xác nên một người có thể thành hai; chưa đo độ hợp lý của ranh giới cảnh bằng người chấm; báo cáo và tài liệu ôn tập mô tả bản cũ (kiểm 3 bất biến, gộp < 8 s, chia > 27 s).
- **Tra ở:** —

## 2.6 Sinh ảnh: Diffusion và Stable Diffusion (Bước 3b)

### 2.6.1 Diffusion model học cái gì?
- **Mức:** ★
- **Ý trả lời chính:** Khi huấn luyện thêm nhiễu Gauss dần vào ảnh (forward), dạy U-Net dự đoán nhiễu đã thêm ở mức t bằng loss MSE ‖ε − ε_θ(x_t, t, c)‖². Khi sinh, bắt đầu từ nhiễu thuần và khử dần (reverse). Dự án không train lại SD.
- **Tra ở:** ch07 câu 1, Q33

### 2.6.2 "Stable Diffusion" khác diffusion thường ở đâu? Latent space là gì?
- **Mức:** ★
- **Ý trả lời chính:** Latent diffusion: khử nhiễu trên latent của VAE nén 8 lần mỗi chiều, 4 kênh. 768×432 → latent 4×54×96, ít hơn ~48 lần giá trị → chạy được 6 GB.
- **Tra ở:** ch07 câu 2

### 2.6.3 SD gồm những thành phần nào?
- **Mức:** ★
- **Ý trả lời chính:** CLIP text encoder (prompt → 77×768), U-Net (dự đoán nhiễu, đọc text bằng cross-attention), VAE (encode/decode ảnh ↔ latent), scheduler (quy tắc trừ nhiễu từng bước).
- **Tra ở:** ch07

### 2.6.4 U-Net biết đang ở bước nhiễu nào bằng cách nào?
- **Mức:** ★★
- **Ý trả lời chính:** Bước t mã hóa bằng sinusoidal embedding qua MLP, cộng vào mọi ResNet block. t lớn quyết định bố cục, t nhỏ tinh chỉnh chi tiết.
- **Tra ở:** ch07 câu 17

### 2.6.5 Classifier- Free Guidance là gì? Vì sao CFG = 5.0?
- **Mức:** ★★★
- **Ý trả lời chính:** Mỗi bước U-Net chạy hai lần (có/không điều kiện) rồi ngoại suy ε = ε_uncond + s·(ε_cond − ε_uncond). s lớn bám prompt hơn nhưng cháy màu/méo. Đo được: 1.5 với 8 bước làm model bỏ qua prompt, nên nâng lên 5.0 (cấu hình máy hiện đặt `sd_guidance = 10` với 28 bước — thống nhất trước khi nói).
- **Tra ở:** `app/config.py:46-50` , Q34

### 2.6.6 Negative prompt hoạt động thế nào?
- **Mức:** ★
- **Ý trả lời chính:** Thay nhánh "không điều kiện" trong CFG bằng embedding negative → đẩy ảnh xa khái niệm đó (chữ, watermark, tay dị dạng). Chỉ tác dụng khi CFG > 1. Lấy từ phần sau `-` `--` của preset.
- **Tra ở:** `resource/image_presets/*.txt`

### 2.6.7 Vì sao chỉ 8 bước mà vẫn ra ảnh?
- **Mức:** ★★★
- **Ý trả lời chính:** Hyper-SD LoRA (ByteDance) chưng cất để đi đường khử nhiễu ngắn. steps < 15: Euler + Hyper- SD15-8steps-CFG; steps ≥ 15: DPM++ 2M Karras, không Hyper- SD ( `QUALITY_MODE_MIN_STEPS =` `15` ).
- **Tra ở:** `image_generator.py:23, 339-` `419`

### 2.6.8 Euler và DPM++ khác gì? Karras là gì?
- **Mức:** ★★
- **Ý trả lời chính:** Cả hai giải ODE khử nhiễu. Euler bậc 1 đi theo tiếp tuyến; DPM++ 2M bậc 2 multistep dùng bước trước ước lượng độ cong, chính xác hơn cùng số bước. Karras sigmas dồn bước vào vùng nhiễu thấp.
- **Tra ở:** ch07 câu 7

### 2.6.9 Seed là gì? Tái lập được ảnh không?
- **Mức:** ★
- **Ý trả lời chính:** Khởi tạo nhiễu ban đầu. Cùng seed + mọi tham số + phần cứng → gần như giống hệt. Seed −1 random; `accepted_seed` lưu vào `state.json` .
- **Tra ở:** Q37

### 2.6.10 Prompt dài hơn 77 token thì sao?
- **Mức:** ★★
- **Ý trả lời chính:** CLIP chỉ nhận 77 token. `compel` với `truncate_long_prompts=False` chia đoạn rồi nối embedding; prompt còn bị kẹp 75 từ bằng `_clamp_prompt_words` .
- **Tra ở:** `image_generator.py:571-631`

### 2.6.11 Vì sao SD1.5 mà không SDXL/Flux?
- **Mức:** ★★
- **Ý trả lời chính:** U-Net SD1.5 ~0,86 tỷ tham số chạy fp16 thoải mái 6 GB; SDXL ~2,6 tỷ, 1024 px, phải offload rất chậm. Hệ sinh thái anime SD1.5 lớn (anything- v5, IP-Adapter Plus Face, Hyper- SD), train LoRA nhanh ở 512 px. Đánh đổi: tay, mặt nhỏ kém.
- **Tra ở:** Q36, `hardware_adapter.py:50`

### 2.6.12 Làm sao chạy được trên 6 GB?
- **Mức:** ★★
- **Ý trả lời chính:** fp16, SDPA attention, CPU offload + VAE slicing khi < 7 GB, unload Ollama trước khi nạp SD, sinh tuần tự, `empty_cache` giữa batch, batch 2-pass tách SD và ESRGAN.
- **Tra ở:** ch07 câu 10

### 2.6.13 Bug khó nhất em tìm ra? (dải đen)
- **Mức:** ★★★
- **Ý trả lời chính:** Dải đen dọc 512/384 px ở 9/41 frame (22%): VAE tiling + tràn số fp16, vị trí dải khớp biên ô tile; latent 96×54 chỉ chiều rộng vượt ô 64 nên chỉ có dải dọc. Sửa: tiling chỉ khi cạnh ≥ 1024 ( `VAE_TILING_MIN_EDGE` ), `has_dead_region` + sinh lại seed mới (tối đa 2), khóa bằng `tests/test_vae_dead_region.py` . Lỗi khung đen khác từ Real- ESRGAN fp16 → fp32 + fallback PIL.
- **Tra ở:** Q40, `postprocess.py:41-42,` `135-146`

### 2.6.14 fp16, fp32, bf16 khác gì?
- **Mức:** ★★
- **Ý trả lời chính:** fp16: 1 dấu, 5 mũ, 10 định trị, max 65504, nửa bộ nhớ fp32, nhanh trên Tensor Core nhưng dễ tràn. bf16 có 8 bit mũ như fp32 nên không tràn, nhưng chỉ nhanh từ Ampere và kém chính xác hơn; code chỉ chọn fp16/fp32.
- **Tra ở:** ch13 câu 8, 17

### 2.6.15 img2img và strength là gì?
- **Mức:** ★★
- **Ý trả lời chính:** Encode ảnh → thêm nhiễu tới mức strength → khử từ đó; strength thấp giữ bố cục. Face Detailer 0.45 (kẹp 0.30–0.55), unify 0.28, trần 0.45. Dùng `from_pipe` chia sẻ component, không tốn thêm VRAM.
- **Tra ở:** ch07 câu 12

### 2.6.16 Checkpoint khác LoRA thế nào?
- **Mức:** ★
- **Ý trả lời chính:** Checkpoint là toàn bộ trọng số (U- Net + VAE + text encoder, ~2 GB fp16); LoRA là phần bù hạng thấp vài MB–chục MB, trộn nhiều cái qua `set_adapters` . UI có 5 checkpoint, mặc định anything-v5.
- **Tra ở:** ch07 câu 14

### 2.6.17 Vì sao tắt safety checker?
- **Mức:** ★★
- **Ý trả lời chính:** `safety_checker=None` : tiết kiệm VRAM/thời gian, tránh ảnh bị bôi đen do lọc nhầm; nội dung do người dùng kiểm soát. Đánh đổi có chủ ý; hướng: thêm bộ lọc nội dung.
- **Tra ở:** `image_generator.py:201-206`

### 2.6.18 Kích thước ảnh theo cỡ cảnh? Upscale thế nào?
- **Mức:** ★
- **Ý trả lời chính:** close 576×704, medium 704×528, wide 768×432; Real-ESRGAN x4plus anime 6B (GAN siêu phân giải 4×, fp32) lên 1920×1080.
- **Tra ở:** ch00 §5.2, `postprocess.py`

### 2.6.19 Dataset/kiến trúc GAN của Real-ESRGAN là gì, sao không dùng SD upscale?
- **Mức:** ★★
- **Ý trả lời chính:** GAN: generator tạo ảnh nét, discriminator phân biệt thật/giả; Real-ESRGAN train với mô phỏng suy giảm thực tế. Nhanh, một lượt, không đổi nội dung như SD upscale (img2img) nên giữ nguyên khuôn mặt.
- **Tra ở:** ch07, ch11

## 2.7 LoRA, IP-Adapter và nhất quán nhân vật (Bước 3c)

### 2.7.1 LoRA là gì? Vì sao không fine-tune toàn bộ?
- **Mức:** ★
- **Ý trả lời chính:** Đóng băng W₀, học ΔW = B·A hạng r nhỏ, scale α/r. Ví dụ `to_q` 320×320 = 102.400 tham số, LoRA rank 8 chỉ 5.120. LoRA style `thuy_mac` rank 8: 1.594.368 tham số ≈ 0,19% U-Net, file 6,4 MB. Fine-tune toàn bộ tốn VRAM/dữ liệu, dễ quên kiến thức cũ, file hàng GB.
- **Tra ở:** Q41, ch08 câu 1

### 2.7.2 LoRA gắn vào lớp nào, vì sao?
- **Mức:** ★★
- **Ý trả lời chính:** `to_q` , `to_k` , `to_v` , `to_out.0` của cả self- và cross-attention trong 16 transformer block. Cross-attention là nơi text tác động lên ảnh; self-attention ảnh hưởng nét vẽ/bố cục, hữu ích cho style.
- **Tra ở:** ch08 câu 2

### 2.7.3 Loss khi train LoRA? Tham số train?
- **Mức:** ★★
- **Ý trả lời chính:** Giống pre-training SD: thêm nhiễu vào latent tại timestep ngẫu nhiên, `F.mse_loss(noise_pred,` `noise)` , gradient chỉ vào LoRA. Nhân vật: rank 16, alpha 16, LR 1e- 4, AdamW wd 1e-2, 512 px, 600– 1000 bước. Style: rank 8, LR 8e-5, 1.500 bước, 46 ảnh.
- **Tra ở:** `train_character_lora.py:157-` `163`

### 2.7.4 Caption khi train: vì sao style dùng caption riêng từng ảnh, nhân vật dùng caption chung?
- **Mức:** ★★
- **Ý trả lời chính:** Model gán những gì caption không giải thích vào trigger chung. Nhân vật: muốn khuôn mặt gắn vào instance prompt. Style: caption mô tả nội dung từng ảnh, phần còn lại là cách vẽ dồn vào trigger `thuymac ink` `wash style` .
- **Tra ở:** ch08 câu 5

### 2.7.5 IP-Adapter khác LoRA thế nào?
- **Mức:** ★★
- **Ý trả lời chính:** LoRA học vào trọng số, phải train. IP-Adapter không train cho từng nhân vật: ảnh ref qua CLIP image encoder thành token ảnh, đi vào nhánh cross-attention riêng (decoupled) song song với text; `scale` 0.6. Cảnh không nhân vật: ảnh xám + scale 0.
- **Tra ở:** Q42

### 2.7.6 LoRA, DreamBooth, Textual Inversion, IP- Adapter khác nhau?
- **Mức:** ★★
- **Ý trả lời chính:** DreamBooth fine-tune (thường toàn bộ) U-Net + prior preservation, nặng GB. Textual Inversion học một vector token, nhẹ nhưng yếu. LoRA cân bằng, file MB. IP-Adapter dùng ngay, giữ identity kém chắc hơn.
- **Tra ở:** ch08 câu 8

### 2.7.7 Giữ khuôn mặt nhân vật giữa các cảnh bằng cơ chế nào? Đã đo chưa?
- **Mức:** ★★★
- **Ý trả lời chính:** Ba kênh: text (style lock + keywords cố định), ảnh (IP- Adapter ref), trọng số (LoRA nhân vật 0.8 + LoRA style 0.45); thêm face detailer tùy chọn. Chưa đo CLIP similarity định lượng (H2 chưa kiểm chứng).
- **Tra ở:** Q43

### 2.7.8 Chưa có ảnh nhân vật thì lấy gì train LoRA?
- **Mức:** ★★★
- **Ý trả lời chính:** `character_bootstrap` : sinh 1 ảnh seed 512×640 từ keywords, IP-Adapter scale 0.7 sinh ~14 biến thể cùng mặt (tối đa 26 lần thử), crop mặt, ≥ 5 ảnh thì train rank 16 (Studio 700 bước), chỉ cho 2 nhân vật xuất hiện nhiều nhất, một lần mỗi truyện. Hạn chế: LoRA học cả khiếm khuyết của ảnh seed, chưa prior preservation.
- **Tra ở:** Q44, `character_bootstrap.py`

### 2.7.9 Đổi checkpoint thì LoRA cũ còn dùng được không?
- **Mức:** ★★
- **Ý trả lời chính:** Không đảm bảo vì ΔW tương đối với W₀ của đúng base model. `has_trained_lora` đọc `<slug>.json` , checkpoint khác thì train lại.
- **Tra ở:** `character_bootstrap.py:57-66`

### 2.7.10 Nhiều LoRA cùng bật thì kết hợp thế nào? Có fuse không?
- **Mức:** ★★
- **Ý trả lời chính:** `set_adapters(names,` `weights)` : ΔW cộng tuyến tính có trọng số (Hyper-SD 1.0, style, nhân vật 0.8). Không fuse vì đổi Fast/Quality và nhân vật liên tục; fuse/unfuse lặp có thể hỏng trọng số.
- **Tra ở:** `image_generator.py:383-386`

### 2.7.11 Vì sao style LoRA weight 0.45?
- **Mức:** ★★
- **Ý trả lời chính:** Quét cùng seed 7777 ở 0; 0.25; 0.4; 0.55; 0.7: 0.40–0.55 dùng được, ≥ 0.70 tan chi tiết tay/chân, ≤ 0.25 gần như không khác base.
- **Tra ở:** `style_weight_sweep.py` , `config.py:73-75`

### 2.7.12 Face detector dùng gì? Sao chạy subprocess?
- **Mức:** ★★
- **Ý trả lời chính:** `lbpcascade_animeface` (LBP + cascade kiểu Viola–Jones) qua OpenCV. OpenCV và PyTorch cùng nạp OpenMP trên Windows gây crash native không traceback, nên cô lập process.
- **Tra ở:** `scripts/detect_faces_cli.py`

### 2.7.13 Face detailer làm gì? Biết mặt vẽ lại tốt hơn bằng cách nào?
- **Mức:** ★★
- **Ý trả lời chính:** Crop mặt (nới 65%), phóng 512×512, img2img 0.45, 14 bước DPM++, CFG 6.0, dán lại bằng feather mask. Ba cổng: vẫn detect được mặt; CLIP sim mặt mới–cũ ≥ 0.55; sim với ref không giảm. Rớt thì giữ mặt gốc. Mặc định tắt ( `enable_face_detailer=False` ) vì chậm.
- **Tra ở:** `face_detailer.py:387-406`

### 2.7.14 Dữ liệu train LoRA phong cách lấy từ đâu?
- **Mức:** ★★
- **Ý trả lời chính:** Met Museum Open Access API, chỉ ảnh public domain/CC0, có `manifest.json` ghi nguồn; lọc thư pháp/triện/tranh màu, cắt ô trượt 512.
- **Tra ở:** Q59, `scripts/build_style_dataset.py`

### 2.7.15 Tránh ảnh xấu lọt vào dataset nhân vật thế nào?
- **Mức:** ★★
- **Ý trả lời chính:** `maybe_collect` chỉ nhận ảnh sau upscale, cảnh 1 nhân vật, mặt ≥ 160 px, CLIP sim với ref ≥ 0.55/0.60; trần 40 ảnh, không xóa ảnh approved.
- **Tra ở:** `dataset_collector.py`

## 2.8 Studio compositing và tách nền (Bước 3d)

### 2.8.1 Studio compositing là gì, vì sao cần?
- **Mức:** ★
- **Ý trả lời chính:** Vẽ nền riêng (cache theo location + time_of_day), vẽ từng nhân vật riêng khung 512×768 trên nền xám, tách nền ra alpha, ghép theo layout, unify pass img2img 0.28. Vì SD1.5 vẽ nhân vật nhỏ trong khung rộng hay hỏng mặt/tay, nhiều nhân vật trong một prompt dễ trộn đặc điểm.
- **Tra ở:** Q45, `studio/*.py`

### 2.8.2 Matting khác segmentation thế nào? Dự án dùng cái nào?
- **Mức:** ★★
- **Ý trả lời chính:** Segmentation gán nhãn rời rạc; matting ước lượng α liên tục [0,1] (C = αF + (1−α)B). Dự án dùng segmentation isnet-anime (rembg) + feather Gaussian 3 px để xấp xỉ matting, không phải matting đúng nghĩa.
- **Tra ở:** ch09 câu 2, 17

### 2.8.3 Vì sao matting là bài toán khó?
- **Mức:** ★★★
- **Ý trả lời chính:** Mỗi pixel 3 phương trình (R,G,B) nhưng 7 ẩn (F 3, B 3, α) → ill- posed; phải thêm giả thiết (chroma-key biết B; GrabCut dùng GMM; mạng nơ-ron dùng tri thức học).
- **Tra ở:** ch09 câu 3

### 2.8.4 Sao bỏ chroma-key làm engine chính?
- **Mức:** ★★
- **Ý trả lời chính:** SD1.5 không đảm bảo nền phẳng đúng màu; thực nghiệm coverage = 1.0 (không cắt được gì). isnet- anime nhận hình dáng nhân vật; chroma và GrabCut giữ làm lưới an toàn; nền xám #9CA3AF để không ám xanh.
- **Tra ở:** ch09 câu 4

### 2.8.5 GrabCut hoạt động thế nào?
- **Mức:** ★★
- **Ý trả lời chính:** Hai GMM 5 thành phần cho nền và tiền cảnh, năng lượng = chi phí màu + chi phí biên, giải bằng min- cut, lặp 5 lần; morphology open/close khử đốm.
- **Tra ở:** ch09 câu 6

### 2.8.6 Công thức ghép lớp là gì?
- **Mức:** ★
- **Ý trả lời chính:** Toán tử "over" Porter–Duff C = αF + (1−α)B; theo `z_order` tăng dần (painter's algorithm): trim, scale LANCZOS, harmonize, anchor, `alpha_composite` .
- **Tra ở:** `studio/compositor.py`

### 2.8.7 Biết matte hỏng bằng cách nào?
- **Mức:** ★★
- **Ý trả lời chính:** `alpha_coverage` = tỷ lệ pixel α > 16/255, hợp lệ trong [0.05, 0.95]. Hỏng thì thử GrabCut, vẫn hỏng thì `MatteQualityError` và render classic cảnh đó.
- **Tra ở:** `studio_pipeline.py`

### 2.8.8 Unify pass có làm hỏng bố cục không? Có tốn VRAM không?
- **Mức:** ★★
- **Ý trả lời chính:** Không: strength 0.28 ≈ 4/16 bước chỉ vẽ lại bề mặt (ánh sáng, nét, mép); trần 0.45; prompt không nhắc nhân vật, IP-Adapter scale 0. Dùng `from_pipe` chung U- Net/VAE nên không tốn thêm VRAM.
- **Tra ở:** ch09 câu 8, 9

### 2.8.9 Layout do ai quyết? LLM sai thì sao?
- **Mức:** ★★
- **Ý trả lời chính:** Mặc định LLM trả anchor/scale/z/pose; parser trả None nếu sai kiểu, ngoài [0,1], trùng/thiếu nhân vật → heuristic theo cỡ cảnh (close 1.0 giữa; medium 0.8 đáy; wide 0.45 đáy; 2 người trái-phải).
- **Tra ở:** `build_layer_plan_from_llm`

### 2.8.10 Khi nào Studio tự lùi về classic? Vì sao Studio không phải mặc định?
- **Mức:** ★★★
- **Ý trả lời chính:** Lùi khi: tên nhân vật không có trong context, > 3 nhân vật, có tag tương tác (hug, fight, kiss…), matte rớt cổng, hoặc exception. Không mặc định vì với thủy mặc isnet-anime chỉ giữ 0,3% pixel (coverage 0,003), và phong cách mực đã che điểm yếu mặt/tay. Báo cáo ghi "studio mặc định" là lệch, cần đính chính.
- **Tra ở:** Q46, ch09 câu 12, 14

### 2.8.11 Sao không dùng BiRefNet hay SAM?
- **Mức:** ★★
- **Ý trả lời chính:** isnet-anime chuyên nhân vật anime, chạy CPU ~0,9 s/ảnh nên không tranh VRAM; BiRefNet nặng hơn, SAM cần prompt điểm/hộp. Interface `Matter` cho đổi model bằng cấu hình `studio_matte_model` ; chưa đo model khác.
- **Tra ở:** ch09 câu 16

### 2.8.12 Background cache có rủi ro gì?
- **Mức:** ★★
- **Ý trả lời chính:** Khóa `safe_location_id(location +` `"_" + time_of_day)` , lưu trong `<context_dir>/bg_cache` . Khóa không chứa style/checkpoint nên đổi phong cách có thể dùng lại nền cũ.
- **Tra ở:** ch09 câu 11

## 2.9 Whisper và phụ đề (Autosub)

### 2.9.1 Whisper dùng ở đâu? Có dùng trong video truyện không?
- **Mức:** ★
- **Ý trả lời chính:** Chỉ trong công cụ Autosub rời. Video truyện không dùng: phụ đề sinh từ kịch bản (chữ đúng 100%), timing tỷ lệ số từ, tiết kiệm ~60 s/chương và VRAM.
- **Tra ở:** `adapter_video_cli.py:222`

### 2.9.2 Whisper nhận gì, biến đổi thế nào?
- **Mức:** ★★
- **Ý trả lời chính:** Audio 16 kHz mono → cửa sổ 25 ms bước 10 ms → FFT → 80 bộ lọc Mel → log → ma trận 80×3000 cho 30 s; encoder Transformer đọc, decoder sinh token chữ + token thời gian.
- **Tra ở:** `composer.py:330-341`

### 2.9.3 Vì sao thang Mel và log?
- **Mức:** ★★
- **Ý trả lời chính:** Tai cảm nhận tần số và độ to gần logarit; Mel nén vùng cao, giữ chi tiết vùng thấp chứa âm vị; log thu hẹp dải giá trị giúp học ổn định.
- **Tra ở:** ch10 câu 2

### 2.9.4 Whisper khác ASR truyền thống? Timestamp từng từ lấy từ đâu?
- **Mức:** ★★
- **Ý trả lời chính:** End-to-end, không cần từ điển phát âm/LM riêng, train 680.000 giờ đa ngôn ngữ; có thể ảo giác. Mốc từng từ từ trọng số cross-attention của alignment head, căn bằng DTW ( `word_timestamps=True` ).
- **Tra ở:** `subtitle.py:40`

### 2.9.5 VAD là gì? faster- whisper, int8 là gì?
- **Mức:** ★★
- **Ý trả lời chính:** Silero VAD lọc đoạn không tiếng nói, giảm ảo giác; `min_silence_duration_ms=500` . faster-whisper chạy CTranslate2 (C++), int8 mỗi trọng số 1 byte + scale, model medium ~0,8 GB, chạy CPU để nhường VRAM.
- **Tra ở:** ch10 câu 5–7

### 2.9.6 SRT và ASS khác gì? Burn cứng hay phụ đề mềm?
- **Mức:** ★
- **Ý trả lời chính:** SRT: chỉ số, thời gian `HH:MM:SS,mmm` , chữ. ASS có style (font, màu, viền). Lưu SRT, burn bằng filter `subtitles` (libass) + `force_style` . Burn cứng vì nhiều nền tảng không đọc track phụ đề; đổi lại phải encode lại. Mặc định video truyện `burn_subtitles=False` .
- **Tra ở:** ch10 câu 10, 11

### 2.9.7 Sai số timing theo số từ có cộng dồn không?
- **Mức:** ★★
- **Ý trả lời chính:** Không ra toàn chương: tổng lấy chính xác từ WAV, cảnh cuối ép đúng tổng; phụ đề neo trong từng cảnh. Sai số chỉ trong nội bộ cảnh; chưa đo WER/độ lệch.
- **Tra ở:** ch10 câu 9, 15

### 2.9.8 Video không tiếng hoặc nhạc nền to thì sao?
- **Mức:** ★★
- **Ý trả lời chính:** Không tiếng/chữ in sẵn: `sub_source="ocr"` chạy PaddleOCR trong process con. Nhạc to: Demucs `htdemucs --two-` `stems vocals` tách giọng trước Whisper, lỗi thì dùng audio gốc.
- **Tra ở:** `composer.py:347-359` , `audio_cleaner.py`

## 2.10 Dựng và ghép video bằng ffmpeg (Bước 3e và Bước 4)

### 2.10.1 ffmpeg ghép ảnh thành video bằng cách nào?
- **Mức:** ★
- **Ý trả lời chính:** Concat demuxer với `duration.txt` (mỗi ảnh `file '...'` + `duration` `<giây>` , ảnh cuối lặp lại vì demuxer bỏ duration mục cuối) → scale+pad 1920×1080, `-r 24` , `-pix_fmt` `yuv420p` , H.264. Lượt 2 mux audio/BGM/phụ đề.
- **Tra ở:** `video_assembler.py:104-` `157`

### 2.10.2 Container và codec khác gì? Video của em dùng gì?
- **Mức:** ★
- **Ý trả lời chính:** Codec là thuật toán nén một luồng (H.264, AAC); container là hộp chứa luồng + timestamp + metadata (MP4, WAV). Đầu ra: MP4 chứa H.264 yuv420p 24 fps 1920×1080 + AAC 192 kbps.
- **Tra ở:** ch11 câu 5

### 2.10.3 Vì sao ép yuv420p? CRF là gì?
- **Mức:** ★★
- **Ý trả lời chính:** PNG là RGB, không ép thì x264 có thể xuất 4:4:4 nhiều trình phát không chạy; 4:2:0 giảm độ phân giải màu, hợp mắt người. CRF giữ chất lượng cảm nhận không đổi, 0–51 thấp là đẹp; dựng chương mặc định 23 + `ultrafast` , fallback ghép dùng CRF 20.
- **Tra ở:** ch11 câu 6, 7

### 2.10.4 Keyframe/GOP là gì, liên quan gì đồ án?
- **Mức:** ★★
- **Ý trả lời chính:** I-frame giải mã độc lập, cần cho tua và cho nối bằng stream copy. Không đặt `-g` nên mặc định keyint=250; ảnh tĩnh nên P-frame gần như rỗng, file rất nhỏ.
- **Tra ở:** ch11 câu 8

### 2.10.5 NVENC là gì? Máy không có NVIDIA thì sao?
- **Mức:** ★★
- **Ý trả lời chính:** Khối mã hóa phần cứng riêng trên GPU, nhanh, không tranh CUDA core với SD. Driver không hỗ trợ thì `_run_ffmpeg_with_nvenc_fallback` thay bằng libx264 và bỏ option riêng NVENC.
- **Tra ở:** ch11 câu 9

### 2.10.6 Hình và tiếng khớp nhau thế nào? Ghép nhạc nền ra sao?
- **Mức:** ★★
- **Ý trả lời chính:** Tổng `duration_sec` các cảnh = độ dài audio; lượt 2 dùng `-t` `total_dur` . BGM: `amix=inputs=2:duration=first` , giọng 1.0, nhạc 0.15 (≈ −16,5 dB). Hạn chế: amix chuẩn hóa theo số input nên giọng có thể nhỏ đi; sửa bằng `normalize=0` + ducking.
- **Tra ở:** ch11 câu 4, 10

### 2.10.7 Bước ghép (Bước 4) khác bước dựng thế nào? Vì sao nhanh?
- **Mức:** ★
- **Ý trả lời chính:** Concat `-c copy` : chỉ demux/mux, không giải mã/mã hóa lại, nhanh như tốc độ đĩa, không mất chất lượng. Điều kiện: các file cùng thông số; lỗi thì re-encode libx264. Thứ tự `sorted(glob('*.mp4'))` , loại `TongHop_*` .
- **Tra ở:** `video_merger.py:6-12`

### 2.10.8 Vì sao chia Pass A / Pass B?
- **Mức:** ★★
- **Ý trả lời chính:** GPU 6–8 GB không chứa đồng thời SD và Real-ESRGAN. Pass A sinh ảnh mọi chương → release SD → Pass B upscale + dựng video. Mỗi model nạp một lần; OOM ở Pass A retry một lần sau release.
- **Tra ở:** `batch_video_runner.py:359-` `515`

### 2.10.9 Ken Burns là gì? Em sẽ cài thế nào?
- **Mức:** ★★
- **Ý trả lời chính:** Mô phỏng camera zoom/pan trên ảnh tĩnh: mỗi frame cắt cửa sổ W/z(t) × H/z(t), z tăng 1,0→1,15. ffmpeg `zoompan=z=...:x=...:y=...:d=` `<frame>:s=1920x1080:fps=24` , áp lên ảnh lớn trước để tránh rung; chuyển cảnh bằng `xfade` .
- **Tra ở:** ch11 câu 2

### 2.10.10 Vì sao chạy ffmpeg với `cwd=work_dir` và copy SRT thành `temp_sub.srt` ?
- **Mức:** ★★
- **Ý trả lời chính:** Trong filtergraph dấu `:` là ký tự phân tách, đường dẫn `C:\...` và tên tiếng Việt có khoảng trắng dễ hỏng cú pháp; dùng tên tương đối cố định.
- **Tra ở:** ch11 câu 15

## 2.11 Trợ lý AI: RAG, IDF, agent, streaming

### 2.11.1 RAG là gì? Sao chatbot cần RAG?
- **Mức:** ★
- **Ý trả lời chính:** Truy xuất đoạn tài liệu liên quan rồi đưa vào prompt để LLM trả lời dựa trên đó. Qwen2.5 3B chưa thấy phần mềm này, hỏi thẳng sẽ bịa tên nút/tham số; sửa `docs/kb/*.md` là cập nhật tri thức, không cần train.
- **Tra ở:** ch12 câu 1

### 2.11.2 Có dùng embedding/vector DB không? Vì sao?
- **Mức:** ★★★
- **Ý trả lời chính:** Không. Lexical: khớp từ khóa không dấu trọng số IDF. Lý do: embedding tốn VRAM (chia với SD), KB nhỏ (~179 mảnh, ~49 KB) toàn thuật ngữ khớp mặt chữ, đã đo đạt yêu cầu. Hạn chế: không hiểu đồng nghĩa. FAISS trong repo là của cache TTS.
- **Tra ở:** Q50

### 2.11.3 Giải thích công thức chấm điểm.
- **Mức:** ★★
- **Ý trả lời chính:** IDF = ln(N/(1+df)), từ chưa gặp nhận ln N. Khớp nội dung cộng 1,0×IDF, khớp tiêu đề 1,5×IDF; cần khớp ≥ 40% từ khóa và ≥ 2 từ; tab đang mở ×1,3; chia tổng IDF câu hỏi; cao nhất < 0,75 thì coi là không khớp tài liệu (xem 2.11.7 về thay đổi ngày 01/10).
- **Tra ở:** ch12 câu 3, `chatbot.py`

### 2.11.4 Vì sao chia cho tổng IDF mà không chia số từ?
- **Mức:** ★★
- **Ý trả lời chính:** Câu toàn từ phổ biến không tự được điểm cao; câu nhiều từ lạ (IDF lớn nhất) bị kéo điểm xuống → cơ chế tự từ chối. Ví dụ "phở bò gia truyền" tổng IDF 17,2 chỉ đạt 0,49.
- **Tra ở:** ch12 câu 4

### 2.11.5 TF-IDF, BM25 là gì? Sao không dùng BM25 có sẵn trong FTS5?
- **Mức:** ★★
- **Ý trả lời chính:** TF-IDF: tần suất × độ hiếm; BM25 cải tiến bằng bão hòa tần suất và chuẩn hóa độ dài. Đã cài và đo: IDF 28/28 QA, chặn 7/8; BM25 27/28 + 7/8 hoặc 28/28 + 6/8 tùy ngưỡng. Đo lại khi KB > ~240 mảnh.
- **Tra ở:** `kb_index.py:13-` `22`

### 2.11.6 Chunking tài liệu thế nào?
- **Mức:** ★★
- **Ý trả lời chính:** Theo tiêu đề `#/##/###` , trần 400 ký tự, cắt tiếp theo dòng trống rồi theo dòng; mỗi mảnh mang đường dẫn tiêu đề ở đầu để tự đứng vững. Context mỗi câu giảm 1.473 → 854 token (−42%).
- **Tra ở:** ch12 câu 6

### 2.11.7 Chatbot làm sao không bịa?
- **Mức:** ★★
- **Ý trả lời chính:** Cổng 0,75: (bản trong báo cáo) không đủ điểm thì từ chối cố định, không gọi LLM. Từ commit 01/10 đã đổi: không khớp thì thử lại với câu hỏi trước (câu nối tiếp), vẫn không khớp thì gọi LLM với prompt suy luận bắt mở đầu "`⚠️` Ngoài tài liệu — đây là suy luận:", câu ngoài phạm vi hẳn thì quy tắc 6 bảo LLM nói ngắn là ngoài phạm vi. Số đo từ chối 7/8 là của bản cũ, cần đo lại; system prompt 7 quy tắc (chỉ dùng `<tailieu>` , suy luận phải dán nhãn, cấm bịa tên nút, kết "Nguồn:"); số liệu do code đếm. Vẫn còn 1/8 câu ngoài phạm vi lọt cổng.
- **Tra ở:** Q51

### 2.11.8 "Agent" có tự chạy pipeline không?
- **Mức:** ★★
- **Ý trả lời chính:** Không. Router regex tất định ( `route_intent` ), không phải ReAct. L1 đọc trạng thái từ đĩa; L2/L3 chỉ trả `agent_action` , UI hiện thẻ xác nhận, người dùng bấm mới gọi API. Model 3B function-calling không đáng tin.
- **Tra ở:** Q53, ch12 câu 8

### 2.11.9 Chatbot tranh GPU với Bước 3 thì sao?
- **Mức:** ★★
- **Ý trả lời chính:** `get_gpu_weight` trả none/medium/heavy; heavy (step3/step4/chuỗi tự động) thì `/api/chat` trả 409 kèm `lookup_answer` (3 mảnh KB nguyên văn, 0 VRAM). Trước mỗi bước lẻ UI gọi `/api/chat/unload` ( `keep_alive=0` ).
- **Tra ở:** Q52

### 2.11.10 Sao gọi `/api/chat` native mà không dùng `/v1` OpenAI- compatible?
- **Mức:** ★★
- **Ý trả lời chính:** `/v1` của Ollama bỏ qua `num_ctx` , context về 2048 và KB bị cắt không báo. Native cho đặt `num_ctx=8192` và nhận `prompt_eval_count` để cảnh báo cắt cụt.
- **Tra ở:** ch12 câu 11

### 2.11.11 Đánh giá chatbot thế nào? Tránh "học tủ" bộ eval ra sao?
- **Mức:** ★★
- **Ý trả lời chính:** 36 câu: 28 QA có `must_include` + 8 câu ngoài phạm vi; hai chế độ retrieval và llm. Đã gỡ lỗi nhét từ khóa eval vào stopwords, có test chặn tái phạm. Còn tồn: 2 ví dụ few-shot trùng câu eval; cần tập held-out.
- **Tra ở:** ch12 câu 12, 13

### 2.11.12 Chống prompt injection từ nội dung truyện thế nào?
- **Mức:** ★★
- **Ý trả lời chính:** Nội dung bọc trong `<noidungtruyen>` + quy tắc coi đó là dữ liệu, chỉ trích 500 ký tự; client escape HTML trước khi render. Giảm thiểu, không tuyệt đối.
- **Tra ở:** ch12 câu 14

### 2.11.13 Streaming câu trả lời hoạt động thế nào? Sao không dùng SSE?
- **Mức:** ★
- **Ý trả lời chính:** Ollama `stream: true` trả NDJSON → `chat_stream_ollama` yield `{"delta"}` → `StreamingResponse` → `fetch` + `ReadableStream` tách theo `\n` . EventSource chỉ GET không body, còn chatbot cần POST và hủy bằng `AbortController` .
- **Tra ở:** `chat.js` , `llm.py`
