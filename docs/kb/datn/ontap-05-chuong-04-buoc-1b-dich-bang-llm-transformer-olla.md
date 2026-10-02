# Chương 04. Bước 1b — Dịch bằng LLM (Transformer, Ollama, quantization, glossary)

- Mục tiêu chương: sau khi đọc xong, bạn giải thích được (1) một LLM "hiểu" và "sinh" chữ như thế nào, (2) vì sao một model 7 tỷ tham số chạy được trên GPU 6GB, (3) hệ thống dịch của đồ án chia chương, dựng prompt, ép tên riêng, phát hiện lỗi và tự vá ra sao — với file/hàm/tham số thật trong repo.

- Quy ước trích dẫn: `path/file.py:LINE` . Mọi con số cấu hình trong chương đều đọc từ code. Những con số lấy từ kiến thức chung (không nằm trong repo) được ghi rõ là "tham khảo".

## 1. Vai trò trong hệ thống

### 1.1 Vị trí trong pipeline

Pipeline 5 bước của đồ án: (1) Cào + Dịch → (2) TTS → (3) Sinh video → (4) Autosub → (5) Ghép. Chương này là nửa sau của Bước 1 ("Bước 1b"): biến chương truyện gốc (thường là tiếng Trung, cũng hỗ trợ Anh/Nhật/Hàn) thành tiếng Việt.

Ngoài ra Bước 1 còn một nguồn thay thế: "Sáng tác bằng AI" ( `source=="ai_write"` ) — LLM tự viết truyện tiếng Việt, bỏ qua bước dịch (mục 4.10).

- **Thành phần:** Orchestrator gọi dịch · **Vị trí:** `orchestrator/pipeline.py:172` ( `translate_cmd` ), `:239` ( `cwd="toolCaoTruyen"` ) · **Vai trò:** Dựng command line, chạy subprocess sau khi cào xong
- **Thành phần:** CLI adapter · **Vị trí:** `toolCaoTruyen/adapter_cli.py:70` `handle_translate()` · **Vai trò:** Quét file, nạp glossary, chọn engine, lặp dịch từng chương, vá lỗi, in log JSON
- **Thành phần:** Interface chung · **Vị trí:** `toolCaoTruyen/translator/base.py:7` `TranslatorEngine` · **Vai trò:** Hợp đồng `translate/translate_file/extract_glossary_from_text/is_available` + cơ chế vá `[[MISSING_CHUNK:n]]`
- **Thành phần:** Engine local · **Vị trí:** `toolCaoTruyen/translator/ollama_translator.py:10` `OllamaTranslator` · **Vai trò:** Gọi Ollama `/api/chat`
- **Thành phần:** Engine cloud · **Vị trí:** `translator/gemini_translator.py:14` `GeminiTranslator` · **Vai trò:** Gọi Google Gemini REST `v1beta`
- **Thành phần:** Engine proxy · **Vị trí:** `translator/gemini_api_translator.py:13` `GeminiApiTranslator` · **Vai trò:** Gọi endpoint OpenAI-compatible (mặc định `http://localhost:7860/v1` )
- **Thành phần:** Cấu hình model · **Vị trí:** `translator/registry.py:11OLLAMA_MODELS` · **Vai trò:** chunk size, num_ctx, temperature, prompt_style theo từng model
- **Thành phần:** Từ điển · **Vị trí:** `translator/glossary_manager.py` , `toolCaoTruyen/common_idioms.json` · **Vai trò:** Glossary global + per-story + thành ngữ
- **Thành phần:** Modelfile · **Vị trí:** `toolCaoTruyen/ollama_models/Modelfile.hy-mt2` · **Vai trò:** Đóng gói model chuyên dịch HY-MT2 vào Ollama
- **Thành phần:** LLM dùng chung · **Vị trí:** `orchestrator/llm.py` · **Vai trò:** `resolve_llm` , `chat` (OpenAI-compatible), `chat_stream_ollama` , `unload_ollama`
- **Thành phần:** Sáng tác AI · **Vị trí:** `orchestrator/story_writer.py:24` `generate_story()` · **Vai trò:** Viết truyện nhiều chương có tóm tắt nối mạch

### 1.2 Input / Output

Input: thư mục `storage/<truyện>/raw/` chứa các file `Chương NNNN -<tiêuđềgốc>.md` (do crawler sinh). Lưu ý orchestrator truyền cùng một thư mục cho `--input-dir` và `--output-dir` ( `orchestrator/pipeline.py:172-176` ).

Output (cũng trong `raw/` ):

- `Chương NNNN - [VI]<tiêuđềđã dịch>.md` — bản dịch. Nhãn `" - [VI] "` là "hợp đồng" giữa các bước: bước dịch chỉ lấy file không có nhãn, TTS/ghép video chỉ lấy file có nhãn ( `orchestrator/chapter_naming.py` , docstring đầu file). `Chương NNNN - ....translation_report.json` — báo cáo dịch máy đọc được ( `ollama_translator.py:737-755` ). `glossary.json` của truyện (per-story glossary) — `glossary_manager.py:21-23` ( `load_story_glossary` ). File gốc bị xoá nếu dịch sạch 100% (đã backup trong `_original.zip` lúc cào) — `adapter_cli.py:374-381` . Log JSON từng dòng ra stdout ( `log_json` , `adapter_cli.py:16-19` ), orchestrator đọc và đẩy lên web UI qua SSE.

Trạng thái story: `TRANSLATING` → `TRANSLATED` (exit code 0) hoặc `TRANSLATE_FAILED` / `CANCELLED` ( `pipeline.py:205-218` ).

## 2. Nền tảng lý thuyết từ gốc

Phần này dạy theo thứ tự: chữ → token → vector → Transformer → sinh chữ từng bước → điều khiển độ "phiêu" → vì sao model biết làm theo lệnh → chạy nó trên máy nhà bằng cách nén.

### 2.1 Token và tokenization

Trực giác. Máy tính không đọc "chữ", nó chỉ xử lý số. Cần một bước cắt văn bản thành các mảnh nhỏ gọi là token, mỗi token có một số ID trong vocabulary (từ vựng cố định, thường 30k–150k mục).

Vì sao không cắt theo từ hoặc theo ký tự?

- Cắt theo từ: vocabulary khổng lồ, gặp từ mới (tên riêng "Cố An") là bó tay (out-of-vocabulary). Cắt theo ký tự: chuỗi quá dài, model phải học lại chính tả từ đầu. Subword (BPE — Byte Pair Encoding) là điểm giữa: bắt đầu từ byte/ký tự, lặp lại việc gộp cặp xuất hiện nhiều nhất thành token mới. Từ phổ biến thành 1 token, từ hiếm bị tách thành vài mảnh. Với byte-level BPE (GPT-2, Llama 3, Qwen dùng biến thể này) thì không bao giờ có OOV vì tệ nhất vẫn rơi về 256 byte; BPE theo ký tự thuần thì vẫn có thể gặp ký tự lạ (khi đó dùng token `<unk>` hoặc byte-fallback như SentencePiece). Quá trình huấn luyện tokenizer (đếm cặp, gộp) chạy một lần trước khi huấn luyện model; sau đó bảng gộp cố định, model nào đi với tokenizer đó.

Ví dụ minh hoạ (không phải output thật của tokenizer): "tu luyện" có thể thành `["tu", " luy", "ện"]` ; 筑基 có thể là 1–2 token.

Hệ quả thực tế trong đồ án:

- Mọi giới hạn của LLM (context window, `num_predict` , `maxOutputTokens` ) tính bằng token, còn code chia chương theo ký tự ( `max_chunk_chars` ). Tỉ lệ ký tự/token khác nhau theo ngôn ngữ: chữ Hán rất "đặc" (một ký tự mang nhiều nghĩa), tiếng Việt có dấu thường tốn nhiều token hơn trên cùng lượng nghĩa (tham khảo — phụ thuộc tokenizer từng model). Vì vậy code dành ngân sách output rất rộng: `num_predict = max(2048, max_chunk_chars * 15)` ( `ollama_translator.py:42` ). Mỗi model có tokenizer riêng → chat template, special token riêng (xem 2.7, Modelfile HY-MT2).

### 2.2 Embedding — biến token thành vector ý nghĩa

Mỗi token ID được tra vào một bảng embedding `E` kích thước `|V|× d` (d = số chiều, vài nghìn). Kết quả là vector `x` ∈ `R^d` .

Trực giác: embedding là "toạ độ ý nghĩa". Qua huấn luyện, các token có ngữ cảnh giống nhau nằm gần nhau ( `sưhuynh` gần `sư` `đệ`, xa `máy tính` ). Khoảng cách/tích vô hướng giữa vector phản ánh độ liên quan.

Vì Transformer xử lý song song mọi token, nó không tự biết thứ tự → cần positional encoding. Các LLM hiện đại (Qwen, Llama...) dùng RoPE (Rotary Position Embedding): xoay vector query/key một góc tỉ lệ với vị trí, nên tích vô hướng giữa hai token phụ thuộc vào khoảng cách tương đối của chúng (tham khảo kiến trúc chung, không có trong code đồ án).

### 2.3 Transformer và self-attention

Bài toán: trong câu "顾安 bước vào dược viên, hắn bắt đầu trồng trọt", để dịch "hắn" đúng, model phải biết "hắn" trỏ tới "Cố An". Mỗi token cần nhìn các token khác và lấy thông tin phù hợp. Đó là attention.

Ẩn dụ thư viện: mỗi token phát ra ba vector:

- Query (Q) — "tôi đang tìm gì?" Key (K) — "tôi là nhãn gì, ai tìm thì khớp?" Value (V) — "nội dung tôi mang theo".

Token hiện tại so Query của mình với Key của mọi token, khớp càng nhiều thì lấy càng nhiều Value của token đó.

Công thức:

```
Attention(Q, K, V) = softmax( Q · K^T / sqrt(d_k) ) · V
```

Giải thích từng ký hiệu:

- `Q = X·W_Q` , `K = X·W_K` , `V = X·W_V` : X là ma trận embedding của n token (n × d), các `W` là trọng số học được. `Q · K^T` : ma trận n × n, ô (i, j) là điểm tương đồng giữa token i (hỏi) và token j (được hỏi). `/ sqrt(d_k)` : chia cho căn số chiều của key. Khi d_k lớn, tích vô hướng có phương sai lớn → softmax bị "bão hoà" (một ô gần 1, còn lại gần 0) → gradient gần 0, khó học. Chia `sqrt(d_k)` đưa phương sai về ~1. `softmax` theo từng hàng: biến điểm thành trọng số dương, tổng bằng 1: `softmax(z)_j = exp(z_j) /Σ_k exp(z_k)` . Nhân với `V` : output của token i là trung bình có trọng số các Value.

Causal mask (cho LLM sinh chữ): token i chỉ được nhìn token ≤ i (không nhìn tương lai), thực hiện bằng cách gán `-∞` cho ô j > i trước softmax.

Multi-head attention: chạy h bộ (Q, K, V) song song, mỗi "head" học một kiểu quan hệ (ngữ pháp, đồng tham chiếu, cặp dịch...), rồi nối lại.

Công thức multi-head: `MultiHead(X) = Concat(head_1,..., head_h) · W_O` , với `head_i = Attention(X·W_Q^i, X·W_K^i,` `X·W_V^i)` và `d_k = d / h` .

Một block Transformer (bản gốc 2017, "post-norm") = Multi-head attention → Add & Norm → Feed-Forward Network (MLP 2 lớp áp dụng riêng từng token) → Add & Norm. "Add" là residual connection (cộng input vào output để gradient chảy qua nhiều lớp dễ hơn), "Norm" là LayerNorm. Các LLM hiện đại như Qwen/Llama dùng biến thể pre-norm (chuẩn hoá trước attention/FFN, dùng RMSNorm) và FFN kiểu SwiGLU — cùng ý tưởng, ổn định hơn khi huấn luyện sâu. Cuối chồng block là một lớp tuyến tính chiếu vector về kích thước `|V|` → ra logits. LLM xếp chồng vài chục block (Qwen2.5-7B: 28 block — tham khảo config công khai của model).

Độ phức tạp: ma trận `QK^T` là n × n → chi phí O(n²) theo độ dài chuỗi. Đây là lý do context window có giới hạn và vì sao code không nhồi cả chương vào một lần gọi.

### 2.4 LLM decoder-only và sinh tự hồi quy (autoregressive)

Transformer gốc (2017) có encoder + decoder, thiết kế cho dịch máy. Các LLM hiện đại (GPT, Qwen, Llama, Gemini...) dùng decoder-only: chỉ một chồng block có causal mask, huấn luyện với một nhiệm vụ duy nhất:

- Cho chuỗi token `t_1..t_{i}` , dự đoán phân phối xác suất của `t_{i+1}` .

Huấn luyện bằng hàm mất mát cross-entropy: `L = −Σ_i log P(t_{i+1}|t_1..t_i)` — tức phạt model khi nó gán xác suất thấp cho token thật sự xuất hiện tiếp theo trong dữ liệu. Nhờ causal mask, một câu dài n token cho ra n bài toán "đoán tiếp" cùng lúc trong một lượt forward.

Sinh văn bản = lặp:

- 1. Đưa prompt vào → model trả vector logits `z` (một số cho mỗi token trong vocabulary). 2. Chuyển logits thành xác suất bằng softmax, chọn một token (sampling, mục 2.5). 3. Nối token đó vào chuỗi, quay lại bước 1. 4. Dừng khi gặp stop token (ví dụ `<`｜`hy_EOT`｜`>` trong Modelfile HY-MT2) hoặc chạm giới hạn số token output.

Hai pha khi chạy:

- Prefill (xử lý prompt): tính song song toàn bộ prompt, nhanh. Decode (sinh từng token): tuần tự, mỗi token một lượt forward. Để không tính lại attention cho các token cũ, runtime lưu KV cache (Key/Value của mọi token đã qua ở mọi layer). KV cache tăng tuyến tính theo độ dài context → tốn VRAM (mục

Liên hệ code: khi output chạm giới hạn, Ollama trả `done_reason=="length"` ; code bắt đúng tín hiệu này để biết bản dịch bị cắt cụt ( `ollama_translator.py:412, 430` ). Với Gemini là `finishReason=="MAX_TOKENS"` ( `gemini_translator.py:264-265,` `385` ).

Encoder-decoder vs decoder-only trong dịch: các hệ Neural MT chuyên dịch (Google Neural Machine Translation 2016 dùng LSTM, MarianMT/Transformer gốc dùng Transformer) là encoder-decoder: encoder đọc câu nguồn, decoder sinh câu đích và "nhìn" encoder qua cross-attention. (Trước 2016 Google Translate là dịch máy thống kê theo cụm từ — SMT.) LLM decoder-only dịch bằng cách "tiếp tục văn bản" sau một prompt "hãy dịch...". Ưu điểm: hiểu ngữ cảnh rộng, làm theo chỉ dẫn (xưng hô, thể loại, glossary). Nhược: có thể "chém", bỏ câu, sót chữ gốc — đó là lý do code có hệ thống kiểm tra leak/thiếu câu.

### 2.5 Sampling: temperature, top-k, top-p, repeat penalty

Từ logits `z_i` , xác suất chọn token i:

```
p_i = exp(z_i / T) / Σ_j exp(z_j / T)
```

- Temperature T: T → 0: phân phối nhọn, gần như luôn chọn token điểm cao nhất (greedy) → ổn định, lặp lại được, ít sáng tạo. Hợp với dịch. T = 1: giữ nguyên phân phối model học được. T > 1: phẳng hơn, "phiêu" hơn. Hợp với viết truyện. Top-k: chỉ giữ k token xác suất cao nhất rồi chuẩn hoá lại. Top-p (nucleus sampling): giữ tập token nhỏ nhất có tổng xác suất ≥ p. Linh hoạt hơn top-k: khi model chắc chắn, tập này rất nhỏ; khi phân vân, tập rộng hơn. Repeat penalty (llama.cpp): giảm logits của token đã xuất hiện gần đây (chia logit dương cho hệ số > 1) để tránh lặp vòng.

Giá trị thật trong code:

- **Nơi dùng:** Ollama mặc định (constructor) · **temperature:** 0.1 · **top_p:** 0.9 · **top_k:** – · **repeat_penalty:** – · **Nguồn:** `ollama_translator.py:16, 36`
- **Nơi dùng:** `hy-mt2:1.8b` , `translategemma:4b` · **temperature:** 0.7 · **top_p:** 0.6 · **top_k:** 20 · **repeat_penalty:** 1.05 · **Nguồn:** `registry.py:15-34` , `Modelfile.hy-mt2:18-` `21`
- **Nơi dùng:** `qwen3:8b` · **temperature:** 0.05 · **top_p:** 0.9 · **top_k:** – · **repeat_penalty:** – · **Nguồn:** `registry.py:43-49`
- **Nơi dùng:** Dịch lại khi leak (Tầng 1) · **temperature:** 0.02 · **Nguồn:** `ollama_translator.py:450`
- **Nơi dùng:** Vá Tầng 2 (Ollama) · **temperature:** 0.02 · **Nguồn:** `ollama_translator.py:606-607`
- **Nơi dùng:** `_translate_single_paragraph` · **temperature:** 0.05 → 0.02 → 0.01 · **Nguồn:** `ollama_translator.py:683-687`
- **Nơi dùng:** Gemini dịch · **temperature:** 0.2 (retry leak 0.05) · **Nguồn:** `gemini_translator.py:19, 404`
- **Nơi dùng:** Vá Tầng 2 (Gemini) · **temperature:** 0.05 · **Nguồn:** `gemini_translator.py:632-633`
- **Nơi dùng:** Trích glossary Gemini · **temperature:** 0.1 · **Nguồn:** `gemini_translator.py:233`
- **Nơi dùng:** Sáng tác truyện · **temperature:** 0.85 · **Nguồn:** `story_writer.py:19` , `llm.py:74`
- **Nơi dùng:** Tóm tắt chương (sáng tác) · **temperature:** 0.3 · **Nguồn:** `story_writer.py:84`
- **Nơi dùng:** Chatbot stream · **temperature:** 0.4 · **top_p:** 0.9 · **repeat_penalty:** 1.05 · **Nguồn:** `llm.py:99-101`

Lưu ý cơ chế: `call_ollama_api` luôn gửi `temperature` , `top_p` , `num_ctx` , `num_predict` trong `options` , còn `top_k` / `repeat_penalty` chỉ gửi khi registry có khai báo ( `ollama_translator.py:379-388` ). Giá trị trong `options` của request ghi đè `PARAMETER` mặc định trong Modelfile — nên khi code hạ temperature xuống 0.02 thì HY-MT2 cũng chạy ở 0.02 chứ không phải 0.7.

Nhận xét để trả lời hội đồng: dịch dùng temperature thấp (bám sát, nhất quán), sáng tác dùng cao (đa dạng). Riêng HY-MT2 dùng 0.7/top_p 0.6/top_k 20 là bộ tham số khuyến nghị của nhà phát hành model (tham khảo model card Hunyuan-MT;

trong repo chỉ thấy các giá trị này được chép vào `registry.py` và Modelfile, không có comment nguồn): top_k/top_p chặt đã cắt đuôi phân phối, nên T = 0.7 vẫn an toàn. Khi phát hiện lỗi, code hạ temperature xuống 0.02 để model "ngoan" nhất có thể.

### 2.6 Context window

Context window = tổng số token model "nhìn thấy" trong một lượt: prompt (system + glossary + few-shot + đoạn cần dịch) + output. Trong Ollama là option `num_ctx` .

- Vượt quá → phần đầu bị cắt/"quên", hoặc output bị chặn. Tăng `num_ctx` → KV cache tăng tuyến tính → tốn VRAM.

Giá trị thật: `num_ctx` mặc định 4096 trong constructor ( `ollama_translator.py:15` ), nhưng registry ghi đè: 2048 cho `hy-mt2` , `translategemma` , `qwen2.5:7b-instruct` ; 2560 cho `qwen3:8b` vì có few-shot ( `registry.py:18, 28, 40, 47` ). Comment trong code: "2048 đủ cho system prompt + glossary + chunk 350 chars + output, tiết kiệm ~50% VRAM KV cache so với 4096 (quan trọng với GPU 6GB)" ( `registry.py:38-40` ). Chatbot dùng `num_ctx=8192` ( `llm.py:103` ) và tự đánh dấu `truncated` khi `prompt_eval_count>=95%num_ctx` ( `llm.py:160` ).

Lưu ý kỹ thuật (trung thực): `num_predict` được đặt `max(2048, chunk*15)` = 5250 (chunk 350) hoặc 7500 (chunk 500), lớn hơn `num_ctx` = 2048. Vì output nằm chung cửa sổ context, giới hạn thực tế của output là phần còn lại của `num_ctx` , không phải `num_predict` . Nói cách khác `num_predict` ở đây đóng vai "không giới hạn thêm" chứ không phải ngân sách chính xác. Hành vi cụ thể khi vượt `num_ctx` phụ thuộc phiên bản Ollama (một số phiên bản "context shift" — bỏ bớt token cũ để sinh tiếp, một số dừng và trả `done_reason: "length"` ) — code không tự kiểm tra điều này (chưa xác minh bằng chạy thật).

### 2.7 Instruction tuning và chat template

Model chỉ pretrain (đoán token tiếp theo trên internet) sẽ "viết tiếp" chứ không "làm theo lệnh". Để có model instruct/chat:

- 1. SFT (Supervised Fine-Tuning): huấn luyện tiếp trên cặp (chỉ dẫn → câu trả lời mẫu). 2. RLHF / DPO: tối ưu theo đánh giá ưa thích của con người.

Dữ liệu SFT được bọc trong chat template với special token đánh dấu vai: system / user / assistant. Khi chạy, phải dùng đúng template model đã học, nếu không model "lạc vai".

Ví dụ thật — `Modelfile.hy-mt2:14` :

```
TEMPLATE """{{ if .System }}<hy_beginofsentence>{{ .System }}<hy_placeholderno3>{{ else }}<hy_beginofsentence>{{ end }}<
hy_User>{{ .Prompt }}<hy_Assistant>{{ .Response }}"""
PARAMETER stop <hy_placeholderno2>
PARAMETER stop <hy_endofsentence>
PARAMETER stop <hy_EOT>
```

Chú thích đầu file giải thích vì sao phải tự viết template: bản GGUF pull thẳng từ HuggingFace có template tự sinh bị hỏng (chứa literal `"onse }}"` , không chèn `.Prompt` ) khiến model chỉ trả chuỗi rác `"onse"` ( `Modelfile.hy-mt2:3-6` ). Đây là một bài học thực tế đáng kể khi bảo vệ: LLM không chỉ là trọng số — template sai là hỏng hoàn toàn.

Các role trong API chat của đồ án: `{"role": "system"|"user"|"assistant", "content":...}` ( `ollama_translator.py:344-` `377` ). Ollama tự render danh sách messages qua TEMPLATE thành chuỗi token.

Few-shot prompting: chèn vài cặp user→assistant mẫu trước câu hỏi thật để model bắt chước định dạng/xưng hô — code dùng cho `qwen3:8b` ( `few_shot: True` , `registry.py:46` ; mẫu theo thể loại ở `ollama_translator.py:356-372` ).

### 2.8 Ollama, llama.cpp và GGUF

Ollama là runtime chạy LLM cục bộ (viết bằng Go), bên trong dùng engine llama.cpp / thư viện tensor GGML (C/C++, tối ưu CPU và GPU qua CUDA/Metal/Vulkan; các bản Ollama mới có thêm engine riêng cho một số kiến trúc nhưng vẫn dựa trên GGML — tham khảo). Ollama thêm:

- Quản lý model như Docker: `ollama pull` , `ollama create -f Modelfile` , `ollama rm` , `ollama list` ( `/api/tags` ). HTTP server cổng 11434: API native `/api/chat` , `/api/generate` , `/api/tags` và API OpenAI-compatible `/v1/chat/completions` . Tự nạp model vào VRAM khi có request, giữ lại một thời gian ( `keep_alive` , mặc định 5 phút — tham khảo), gửi `keep_alive: 0` để nhả ngay — đồ án dùng ở `llm.py:169-188unload_ollama()` .

- Tự chia layer giữa GPU và CPU nếu không đủ VRAM (offload một phần — chậm hơn nhưng vẫn chạy).

GGUF là định dạng file của llama.cpp: một file chứa trọng số (đã lượng tử hoá) + metadata (kiến trúc, tokenizer, chat template gốc). Tag `hf.co/tencent/Hy-MT2-1.8B-GGUF:Q8_0` nghĩa là: lấy từ HuggingFace, repo của Tencent, biến thể lượng tử Q8_0 ( `Modelfile.hy-mt2:13` ).

Modelfile giống Dockerfile cho model: `FROM` (trọng số gốc), `TEMPLATE` (chat template), `PARAMETER` (sampling mặc định, stop token), `SYSTEM` (system prompt mặc định — HY-MT2 không đặt). Quy trình cài trong `install_hy_mt2.bat` : pull GGUF (~2GB) → `ollama create hy-mt2:1.8b -f Modelfile.hy-mt2` → `ollama rm` bản gốc để khỏi tốn đĩa.

### 2.9 Quantization (lượng tử hoá) và phép tính VRAM

Vấn đề: trọng số huấn luyện ở FP16/BF16 = 2 byte/tham số. Model 7.6 tỷ tham số → ~15 GB, không vừa GPU 6GB.

Ý tưởng: lưu mỗi trọng số bằng ít bit hơn, chấp nhận sai số nhỏ. Trọng số mạng nơ-ron phân bố quanh 0, dư thừa lớn nên nén được.

Cơ chế block quantization (llama.cpp):

- Chia trọng số thành block 32 phần tử. Mỗi block lưu một scale `s` (FP16) và các số nguyên nhỏ `q_i` . Giải nén: `w_i≈s · q_i` . Q8_0: `q_i` là int8 (−127..127), `s = max|w|/ 127` . Mỗi block: 32 byte + 2 byte scale = 34 byte/32 trọng số ≈ 8.5 bit/trọng số. Sai số rất nhỏ, gần như không mất chất lượng. Q4_0: `q_i` 4 bit (16 mức, 0..15), giải nén `w_i≈s · (q_i − 8)` ; mỗi block 16 byte + 2 byte scale = 18 byte/32 trọng số → ≈ 4.5 bit/trọng số. Lượng tử hoá ở đây là post-training (nén trọng số sau khi huấn luyện xong, không huấn luyện lại). Khi tính toán, llama.cpp giải nén từng block "on the fly" trong kernel GPU — nên nhẹ bộ nhớ nhưng phép tính vẫn gần như ở độ chính xác cao. Q4_K_M ("K-quant, Medium"): cấu trúc super-block 256 phần tử có scale/min lượng tử hoá hai cấp, một số tensor quan trọng giữ bit cao hơn → trung bình ≈ 4.8–4.9 bit/trọng số, chất lượng tốt hơn Q4_0 đáng kể. Đây là mức mặc định của phần lớn tag Ollama như `qwen2.5:7b-instruct` (tham khảo thư viện Ollama).

Công thức VRAM gần đúng:

```
VRAM ≈ (số tham số × bit/trọng số / 8)  +  KV cache  +  overhead runtime (~0.3–0.8 GB)
KV cache ≈ 2 (K và V) × số layer × số KV-head × head_dim × num_ctx × 2 byte (FP16)
```

Tính cho model trong đồ án (tham khảo thông số công khai của model, không nằm trong repo):

- **Model:** `hy-mt2:1.8b` · **Tham số:** ~1.8B · **Quant:** Q8_0 (8.5 bpw) · **Trọng số ≈:** 1.8e9 × 8.5 / 8 ≈ 1.9 GB · **Ghi chú:** Khớp "~2GB" trong `install_hy_mt2.bat:4`
- **Model:** `qwen2.5:7b-instruct` · **Tham số:** ~7.6B · **Quant:** Q4_K_M (~4.85 bpw) · **Trọng số ≈:** ≈ 4.6 GB · **Ghi chú:** Khớp label "~5GB VRAM" ở `orchestrator/main.py:287`
- **Model:** `qwen2.5:3b-instruct` · **Tham số:** ~3.1B · **Quant:** Q4_K_M · **Trọng số ≈:** ≈ 1.9 GB · **Ghi chú:** Label "~2-3GB VRAM" ( `main.py:284` )

KV cache của Qwen2.5-7B (28 layer, 4 KV-head nhờ GQA — Grouped-Query Attention, head_dim 128): mỗi token ≈ 2×28×4×128×2 byte ≈ 56 KB → `num_ctx` 2048 ≈ 115 MB, 4096 ≈ 230 MB. Tức giảm `num_ctx` 4096 → 2048 đúng là giảm 50% KV cache như comment ở `registry.py:38-39` , dù con số tuyệt đối nhỏ so với trọng số. Trên GPU 6GB đang phải chia sẻ với Stable Diffusion/TTS, mỗi trăm MB đều có ý nghĩa.

Vì sao HY-MT2 chọn Q8_0 chứ không Q4? Model nhỏ (1.8B) ít dư thừa hơn, nén 4-bit làm mất chất lượng rõ hơn; mà Q8_0 vẫn chỉ ~2GB — dư dả cho GPU 6GB.

### 2.10 Tên riêng tiếng Trung → Hán Việt: vì sao khó

Tiếng Việt có hệ âm Hán Việt: mỗi chữ Hán có một cách đọc Hán Việt tương đối cố định ( 顾 → Cố, 安 → An, 张 → Trương, 春 秋 → Xuân Thu). Truyện tiên hiệp dịch sang tiếng Việt theo quy ước dùng Hán Việt cho tên người, địa danh, công pháp, cảnh giới ( 筑基 → Trúc Cơ).

LLM hay sai theo ba kiểu:

- 1. Dịch nghĩa thay vì phiên âm: 药谷 thành "thung lũng thuốc" thay vì "Dược Cốc". 2. Ra pinyin: "Gu An" thay vì "Cố An". 3. Không nhất quán giữa các chunk/chương: chương 1 "Cơ Thiếu Ngọc", chương 5 "Cơ Tiểu Ngọc" — vì mỗi lượt gọi LLM là độc lập, model không có trí nhớ giữa các request.

Giải pháp của đồ án: glossary injection — tra từ điển, chèn đúng những thuật ngữ xuất hiện trong chunk vào prompt trước khi dịch (không phải search-replace sau dịch), kết hợp tự động trích xuất thuật ngữ mới mỗi chương để glossary tự lớn lên (mục 4.5–4.6).

## 3. Vì sao chọn công nghệ này (so sánh phương án)

### 3.1 LLM vs dịch máy truyền thống

- **Tiêu chí:** Xưng hô theo thể loại (ta/ngươi vs tôi/cậu) · **Google Translate / MT truyền thống:** Không điều khiển được · **LLM (Qwen, Gemini, HY-MT2):** Điều khiển qua system prompt theo `genre` ( `ollama_translator.py:217-239` )
- **Tiêu chí:** Ép tên riêng Hán Việt · **Google Translate / MT truyền thống:** Bản miễn phí không có glossary; Cloud Translation bản Advanced có glossary nhưng trả phí, cấu hình riêng, không hiểu ngữ cảnh tu tiên · **LLM (Qwen, Gemini, HY-MT2):** Chèn glossary vào prompt
- **Tiêu chí:** Chạy offline · **Google Translate / MT truyền thống:** Không · **LLM (Qwen, Gemini, HY-MT2):** Có (Ollama)
- **Tiêu chí:** Chi phí · **Google Translate / MT truyền thống:** API trả phí theo ký tự · **LLM (Qwen, Gemini, HY-MT2):** Local miễn phí; Gemini có free tier
- **Tiêu chí:** Rủi ro · **Google Translate / MT truyền thống:** Ổn định · **LLM (Qwen, Gemini, HY-MT2):** Có thể bỏ câu, sót chữ Hán → cần kiểm tra/vá

### 3.2 Ba engine và lý do tồn tại

- **Engine:** `ollama` · **Ưu:** Offline 100%, không quota, không bị safety filter · **Nhược:** Tốn VRAM, chất lượng phụ thuộc model nhỏ · **Code:** `ollama_translator.py`
- **Engine:** `gemini` · **Ưu:** Chất lượng cao, context lớn, không tốn VRAM · **Nhược:** Cần API key, rate limit free tier, safety filter hay chặn cảnh bạo lực · **Code:** `gemini_translator.py`
- **Engine:** `gemini_api` · **Ưu:** OpenAI-compatible, đổi `base_url` là chạy; mặc định trỏ proxy local :7860 · **Nhược:** Proxy bỏ qua `temperature` / `max_tokens` (xem 6), vấn đề ToS khi dùng proxy web · **Code:** `gemini_api_translator.py`

Mặc định: CLI `--engine gemini_api` ( `adapter_cli.py:409` ), orchestrator cũng fallback `gemini_api` khi `trans_args` không có engine ( `pipeline.py:176` ), web UI chọn sẵn `gemini_api` ( `webui/index.html:195` ), nhưng cấu hình chung `translate.default_engine = "ollama"` ( `orchestrator/config.py:47` ). Khi demo trước hội đồng nên chạy Ollama để không phụ thuộc mạng/quota.

### 3.3 Chọn model nào trong Ollama

`registry.py` định nghĩa 4 model, chia 2 nhóm:

- Model chuyên dịch (MT) — `hy-mt2:1.8b` (Tencent Hunyuan-MT2, 36 ngôn ngữ có tiếng Việt), `translategemma:4b` (Google, 55 ngôn ngữ). Nhỏ, nhẹ, được huấn luyện riêng cho dịch nên ít "chém". Nhưng chỉ biết dịch: không làm được việc khác như trích xuất JSON. Endpoint `/api/ollama/models` gắn nhãn `hy-mt2:1.8b` là "khuyến nghị Bước 1" ( `orchestrator/main.py:285` ). Model chat tổng quát — `qwen2.5:7b-instruct` ("Đã kiểm thử"), `qwen3:8b` ("Đã tối ưu giảm leak"). Qwen (Alibaba) được huấn luyện rất nhiều dữ liệu tiếng Trung → hiểu văn tiên hiệp tốt; làm được cả trích xuất glossary.

Vì sao không dùng model 14B/32B: không vừa GPU 6GB cùng lúc với các bước khác.

### 3.4 Vì sao chunk nhỏ (350–500 ký tự) thay vì cả chương

Model nhỏ với chunk dài hay bỏ câu hoặc để sót chữ Hán (hiện tượng "lười" khi output dài). Chunk ngắn → `num_ctx` nhỏ → tiết kiệm VRAM. Lỗi khoanh vùng được theo từng đoạn, vá lại rẻ. Comment `max_chunk_chars: int = 350, # Benchmark optimal size` ( `ollama_translator.py:17` ). Gemini context lớn nên dùng 1000 ( `gemini_translator.py:20` ). Đánh đổi: mất một phần ngữ cảnh giữa các chunk (đại từ có thể không nhất quán). Glossary bù đắp phần tên riêng.

## 4. Hiện thực trong code

### 4.1 Orchestrator khởi chạy bước dịch

`NovelPipeline.start_step_1_crawl_translate()` ( `orchestrator/pipeline.py:135` ):

Nếu `source=="ai_write"` → rẽ sang `start_ai_write` (dòng 144-145). Dựng `crawl_cmd` và `translate_cmd` dùng python của venv riêng `toolCaoTruyen/.venv/Scripts/python.exe` (dòng 150- 151). Cách ly dependency giữa các submodule. Khi crawl thành công ( `on_crawl_completed` ), nếu `auto_translate` bật thì đặt `status = "TRANSLATING"` và `start_process(..., cmd=translate_cmd, cwd="toolCaoTruyen", reuse_queue=True)` — dùng cùng log queue để UI thấy log liên tục (dòng 222-243). `cwd="toolCaoTruyen"` quan trọng: `adapter_cli` dùng đường dẫn tương đối `"."` để tìm `global_glossary.json` và `common_idioms.json` ( `adapter_cli.py:144, 225` ).

4.2 `adapter_cli.py translate` — vòng lặp chính

Các bước trong `handle_translate()` ( `adapter_cli.py:70-388` ):

1. Lọc file cần dịch (dòng 95-120): lấy `.md` không bắt đầu bằng `_` , bỏ file có `" - [VI] "` , và bỏ file gốc nếu prefix `Chương` `NNNN` đã có bản `[VI]` → idempotent, chạy lại không dịch trùng. 2. Nạp glossary (143-146): `GlossaryManager(root_dir=".")` + `load_story_glossary(input_dir)` → `get_combined_glossary()` . 3. Khởi tạo engine qua `TRANSLATOR_ENGINES` (151-172). Với Ollama, `chunk_size` lấy từ registry, mặc định 350. 4. Chọn glossary extractor (174-217) theo `--glossary-extract-engine` ( `gemini` | `ollama` | `gemini_api` | `same_as_trans` ); có thể dùng model khác với model dịch (ví dụ dịch bằng HY-MT2, trích xuất bằng Qwen). 5. `set_genre` , nạp `common_idioms.json` (220-231), `set_glossary` (233). 6. Bỏ auto-extract cho model MT nếu không có extractor riêng (235-242) — vì model chuyên dịch không trả JSON được. 7. Với từng file (251-381):

- Dịch tên file: nếu đã có bản `[VI]` cũ thì ghi đè đúng tên đó, ngược lại gọi `translate_filename_fn` ( `toolCaoTruyen/app.py:199` ) — tách prefix `Chương NNNN -` , chỉ dịch nếu tiêu đề chứa chữ Hán, cắt 80 ký tự, trả `"` `{prefix}[VI] {tiêuđề}.md"` . Trích glossary mới → `save_story_glossary` + `save_global_glossary` → `set_glossary` lại ngay (282-301). Chính chương này và các chương sau dùng luôn (trích trước `translate_file` ). Nếu extractor riêng không `is_available()` thì dùng chính translator để trích (dòng 287). `translator.translate_file(...)` (304). Nếu ghi đè bản dịch cũ → xoá `.wav/.mp3` cũ vì không còn khớp nội dung (307-315). Vá lỗi tối đa 3 vòng `MAX_REPAIR_ROUNDS = 3` (323-357), dừng sớm nếu 2 vòng liên tiếp không vá thêm. Sạch lỗi → `file_success` + xoá file gốc; còn lỗi → `file_failed` , giữ file gốc để debug (360-381).

8. Exit code 0 → orchestrator đặt `TRANSLATED` .

Tham số CLI và mặc định ( `adapter_cli.py:405-421` ):

- **Tham số:** `--engine` · **Mặc định:** `gemini_api`
- **Tham số:** `--ollama-model` · **Mặc định:** `qwen2.5:7b-instruct`
- **Tham số:** `--gemini-model` · **Mặc định:** `gemini-2.5-flash`
- **Tham số:** `--gemini-offline-base-url` · **Mặc định:** `http://localhost:7860/v1`
- **Tham số:** `--gemini-offline-model` · **Mặc định:** `gemini-2.5-flash`
- **Tham số:** `--leak-threshold` · **Mặc định:** 10
- **Tham số:** `--genre` · **Mặc định:** `tien_hiep`
- **Tham số:** `--auto-extract` · **Mặc định:** `store_true` , `default=True`
- **Tham số:** `--glossary-extract-engine` · **Mặc định:** `gemini`

### 4.3 Kiến trúc lớp: Strategy + Template

Strategy pattern: `TRANSLATOR_ENGINES = {"ollama":..., "gemini":..., "gemini_api":...}` ( `registry.py:5-9` ); adapter chọn class bằng chuỗi. `TranslatorEngine` ( `base.py:7` ) giữ state chung: `glossary` , `common_idioms` , `genre` (mặc định `"tien_hiep"` ), `last_report` , và triển khai sẵn `repair_missing_chunks()` . `GeminiApiTranslator` kế thừa `GeminiTranslator` , override tầng gọi HTTP ( `_execute_api_call` , `call_gemini_api` ) để đổi định dạng Gemini → OpenAI Chat Completions ( `gemini_api_translator.py:45-207` ), cộng thêm `is_available` (cần cả key lẫn `base_url` ), `extract_glossary_from_text` (prompt ngắn hơn bản Gemini) và `translate` (gọi `super().translate()` rồi đổi `engine` trong report thành `"gemini_api"` , dòng 254-271). Toàn bộ chunking 2 tầng dùng lại. Toàn bộ HTTP trong `translator/` dùng `urllib.request` của stdlib (không thêm `requests` ).

### 4.4 Cấu hình model tự nạp từ registry

`OllamaTranslator.__init__` ( `ollama_translator.py:11-43` ) đọc `OLLAMA_MODELS.get(model, {})` và ghi đè tham số constructor:

```
self.temperature = model_config.get("temperature", temperature)
self.max_chunk_chars = model_config.get("chunk_size_chars", max_chunk_chars)
self.few_shot = model_config.get("few_shot", False)
self.num_ctx = model_config.get("num_ctx", num_ctx)
self.prompt_style = model_config.get("prompt_style", "chat")
self.top_p = model_config.get("top_p", 0.9)
self.top_k = model_config.get("top_k")
self.repeat_penalty = model_config.get("repeat_penalty")
...
self.chinese_char_pattern = re.compile(r"[\u4e00-\u9fff]")
self.num_predict = max(2048, self.max_chunk_chars * 15)
```

Bảng tổng hợp registry ( `registry.py:11-50` ):

- **Model:** `hy-mt2:1.8b` · **prompt_style:** `hunyuan_mt` · **chunk:** 500 · **num_ctx:** 2048 · **temp:** 0.7 · **few_shot:** –
- **Model:** `translategemma:4b` · **prompt_style:** `translategemma` · **chunk:** 500 · **num_ctx:** 2048 · **temp:** 0.7 · **few_shot:** –
- **Model:** `qwen2.5:7b-instruct` · **prompt_style:** `chat` (mặc định) · **chunk:** 350 · **num_ctx:** 2048 · **temp:** 0.1 (mặc định) · **few_shot:** False
- **Model:** `qwen3:8b` · **prompt_style:** `chat` · **chunk:** 400 · **num_ctx:** 2560 · **temp:** 0.05 · **few_shot:** True

`[\u4e00-\u9fff]` là dải CJK Unified Ideographs cơ bản của Unicode (U+4E00–U+9FFF, ~20.000 chữ Hán thông dụng) — dùng để phát hiện chữ Hán còn sót. Dải này không bao gồm dấu câu Trung ( ，。！？ nằm ở U+3000–U+303F / U+FF00–U+FFEF) và chữ Hán hiếm ở CJK Extension A/B, nên dấu câu Trung sót lại không bị tính là leak.

Lưu ý: vì registry ghi đè sau constructor, tham số dòng lệnh chỉ có tác dụng với model không có trong registry; ví dụ `qwen2.5:7b-instruct` không khai báo `temperature` nên dùng mặc định constructor 0.1.

### 4.5 Chunking theo đoạn văn

`split_text_into_chunks()` ( `ollama_translator.py:67-101` ) — tham lam (greedy) theo ranh giới `\n\n` :

- Bỏ đoạn rỗng. Đoạn dài hơn `max_chunk_chars` → đứng riêng một chunk (không cắt giữa đoạn — giữ nguyên câu). Cộng dồn đoạn vào chunk hiện tại cho đến khi `current_length + para_len + 2 > max_chunk_chars` (+2 là 2 ký tự `\n\n` ).

Tiêu đề chương (dòng đầu bắt đầu bằng `#` ) được tách và dịch riêng với `is_title=True` ( `ollama_translator.py:475-492` ) — system prompt thêm câu "This is the chapter title. Keep it short and preserve Markdown heading prefix."

### 4.6 Glossary: 3 tầng dữ liệu và thuật toán chọn thuật ngữ

Ba nguồn:

- **Nguồn:** Thành ngữ hệ thống · **File:** `toolCaoTruyen/common_idioms.json` (17 mục, ví dụ `→giảheoăn hổ`, `→trúc cơ` , `→Dược Cốc` ) · **Độ ưu tiên:** Thấp nhất · **Ghi chú:** Nạp bằng `set_common_idioms`
- **Nguồn:** Global glossary · **File:** `global_glossary.json` tại cwd ( `toolCaoTruyen/` ) · **Độ ưu tiên:** Trung bình · **Ghi chú:** Dùng chung mọi truyện, file bị gitignore
- **Nguồn:** Per-story glossary · **File:** `<raw_dir>/glossary.json` · **Độ ưu tiên:** Cao nhất · **Ghi chú:** `get_combined_glossary()` : `combined =` `global.copy(); combined.update(story)` ( `glossary_manager.py:25-31` )

Lưu ý: file `global_glossary.json` hiện có ở gốc repo (19 mục, tên riêng Harry Potter như 邓布利多 `→Dumbledore` ; file này đang được git track dù `.gitignore` gốc có dòng `global_glossary.json` — tức đã commit trước khi thêm ignore) — nhưng khi chạy qua orchestrator, `cwd` là `toolCaoTruyen/` nên adapter đọc `toolCaoTruyen/global_glossary.json` (hiện không tồn tại trong working tree; sẽ được tạo ở lần lưu đầu). File ở gốc repo nhiều khả năng sinh ra khi chạy thử từ thư mục gốc — code không nêu rõ, cần xác nhận nếu hội đồng hỏi.

Chính sách ghi "chỉ thêm, không sửa": `save_story_glossary` và `save_global_glossary` chỉ thêm key chưa tồn tại ( `glossary_manager.py:44-47, 67-70` ). Docstring nói rõ lý do: "tránh rò rỉ từ dịch sai từ LLM" — tức một lần LLM trích sai không thể ghi đè bản đúng người dùng đã sửa.

Chọn thuật ngữ cho từng chunk — `_select_active_glossary()` ( `ollama_translator.py:130-168` ):

```
for k, v in self.common_idioms.items():
    if k in chunk_text:
        matching_idioms[k] = v
for k, v in self.glossary.items():
    if k in chunk_text:
        matching_glossary[k] = v
merged_candidates = matching_idioms.copy()
merged_candidates.update(matching_glossary)
selected_keys = list(matching_glossary.keys())[:20]
if len(selected_keys) < 20:
    for k in matching_idioms.keys():
        if k not in selected_keys:
            selected_keys.append(k)
            if len(selected_keys) >= 20:
                break
```

Ý nghĩa:

- Chỉ chèn thuật ngữ thực sự xuất hiện trong chunk (so khớp chuỗi con `k in chunk_text` ) → prompt ngắn, không làm model phân tâm, tiết kiệm context. Tối đa 20 thuật ngữ, glossary ưu tiên hơn idioms. Độ phức tạp O(|glossary| × |chunk|) — chấp nhận được với glossary vài trăm mục.

### 4.7 Prompt design: hai kiểu prompt

(a) `prompt_style=="chat"` (Qwen) — `build_system_prompt()` ( `ollama_translator.py:205-268` ):

- Vai trò: "You are an expert translator specializing in translating {lang} web novels to Vietnamese." `Context:` theo genre — 4 thể loại `tien_hiep` , `do_thi` , `khoa_huyen` , `generic` (dòng 217-238). Ví dụ tiên hiệp: dùng "ta/ngươi", "hắn/nàng", giữ "sư phụ/sư huynh", nhưng linh hoạt nếu nhân vật xuyên không hiện đại. 9 yêu cầu đánh số (dòng 245-254): giữ Markdown, tên riêng theo Hán Việt hoặc glossary, không để lọt ký tự gốc, chỉ xuất bản dịch, không xuất pinyin thô ( `'Hu Ling Zhi'` ), dịch thành ngữ tự nhiên, tránh từ hiện đại trong bối cảnh cổ. Glossary chèn cuối dưới nhãn mạnh: "CRITICAL REQUIREMENT: You MUST strictly use the following Glossary..." dạng `-` 顾安 `-> CốAn` . Với `qwen3:8b` : thêm 1 cặp few-shot theo genre (dòng 353-374).

Prompt viết bằng tiếng Anh — lý do hợp lý là các model chat được SFT chủ yếu bằng tiếng Anh/Trung nên làm theo chỉ dẫn tiếng Anh ổn định hơn (đây là nhận định kinh nghiệm, code không ghi lý do; chưa xác minh bằng benchmark trong repo).

(b) `prompt_style` chuyên dịch — `_build_mt_prompt()` ( `ollama_translator.py:170-203` ), chỉ 1 message user, không system prompt, không few-shot, theo template chính thức của nhà phát hành:

```
if self.prompt_style == "hunyuan_mt":
    parts = []
    if glossary_terms:
        term_lines = "\n".join(f"{k}  {v}" for k, v in glossary_terms.items())
        parts.append(f"\n{term_lines}\n")
    parts.append(f" \n\n{text}")
    return "\n".join(parts)
```

Dịch nghĩa: "Tham khảo bản dịch sau: X dịch thành Y ... Dịch văn bản sau sang tiếng Việt, chỉ xuất kết quả dịch, không giải thích thêm". Đây là cơ chế terminology intervention mà HY-MT hỗ trợ chính thức. `translategemma` dùng template tiếng Anh "You are a professional Chinese (zh) to Vietnamese (vi) translator..." với `Use these exact translations for specific terms: X-> Y;` `..` .

Điều kiện chọn đường MT ( `ollama_translator.py:337-341` ): `prompt_style` là MT và không có `system_instruction` tuỳ biến và không yêu cầu JSON. Tức các lời gọi đặc biệt (trích glossary) vẫn đi đường chat.

### 4.8 Gọi Ollama API

`call_ollama_api()` ( `ollama_translator.py:321-420` ) gửi POST `http://localhost:11434/api/chat` :

```
options = {
    "temperature": self.temperature,
    "top_p": self.top_p,
    "num_ctx": self.num_ctx,
    "num_predict": num_predict
}
...
payload = {
    "model": self.model,
    "messages": messages,
    "stream": False,
    "options": options
}
if response_json:
    payload["format"] = "json"
```

- `stream: False` — đợi trọn kết quả (dịch cần cả đoạn để kiểm tra). `format: "json"` — Ollama ràng buộc output là JSON hợp lệ (constrained decoding bằng grammar) — dùng khi trích glossary. Timeout 600 giây, retry 2 lần với backoff `[3, 6]` giây (dòng 405-420). Lưu `done_reason` để phát hiện cắt cụt. `is_available()` gọi `/api/tags` , khớp tên model đầy đủ hoặc phần trước dấu `:` (dòng 45-65). Nếu thiếu model: hướng dẫn `ollama pull` , riêng `hy-mt2` hướng dẫn chạy `install_hy_mt2.bat` (dòng 464-473).

### 4.9 Dịch 2 tầng và kiểm soát chất lượng (trái tim của module)

Tầng 1 — dịch từng chunk tuần tự ( `ollama_translator.py:498-526` ):

- Mảng `translated_chunks = [None] * total_chunks` giữ đúng thứ tự tuyệt đối. `translate_chunk_with_retry()` (dòng 422-458): 1. Gọi API. Nếu `done_reason=="length"` → gọi lại với `num_predict × 1.5` ; vẫn cắt → `ValueError("output_truncated")` . 2. Nếu `has_chinese_leak(output)` → dịch lại với temperature 0.02. Lỗi → giữ nguyên chunk gốc, đánh dấu trạng thái `truncated` hoặc `failed` để Tầng 2 xử lý.

Căn đoạn (paragraph alignment) (dòng 528-549): tách chunk gốc và bản dịch theo `\n\n` . Nếu số đoạn lệch, thử tách bản dịch theo `\n` đơn (model MT hay trả mỗi đoạn một dòng). Vẫn lệch → gán bản dịch rỗng cho mọi đoạn của chunk → buộc dịch lại từng đoạn ở Tầng 2.

Tầng 2 — quét từng đoạn (dòng 551-639), 3 tiêu chí:

- **Lý do:** `untranslated` · **Điều kiện:** `orig_p==trans_p` hoặc rỗng · **Ý nghĩa:** Model nhại lại gốc hoặc không trả gì
- **Lý do:** `leak` · **Điều kiện:** `has_chinese_leak(trans_p)` · **Ý nghĩa:** Còn ký tự Hán (Zero Tolerance: ≥ 1 ký tự là lỗi, `ollama_translator.py:103-114` )
- **Lý do:** `content_missing` · **Điều kiện:** `get_sentence_count(trans)<` `get_sentence_count(orig)` · **Ý nghĩa:** Model nuốt câu

Đếm câu: `re.split(r'[.!?`。！？`\n]+', text)` ( `utils.py:11` ) — tách theo dấu kết câu Anh/Việt và Trung.

Đoạn chỉ gồm dấu câu ( `not re.search(r"\w", orig_p)` ) giữ nguyên. Chunk `truncated` → đánh marker ngay.

`has_chinese_leak()` (dòng 116-128) kiểm tra từng đoạn con khi văn bản có nhiều đoạn — docstring gọi là "chống pha loãng": nếu dùng ngưỡng tỉ lệ trên cả khối dài, vài ký tự sót có thể bị chìm. Nói cho chính xác: với Zero Tolerance hiện tại ( `contains_chinese_leak` trả True khi có ≥ 1 ký tự Hán, bỏ qua `threshold_ratio` / `min_chars` ), kiểm tra từng đoạn cho cùng kết quả như kiểm tra cả khối; việc tách đoạn là dấu vết của thiết kế ngưỡng tỉ lệ trước đây.

Vá đoạn lỗi bằng `retry_translate_paragraph()` ( `utils.py:32-104` ) — 3 lượt leo thang:

- **Lượt:** 1 · **temperature:** `temp_pass2` (Ollama: 0.02; Gemini: 0.05) · **token multiplier:** 1.0 (dùng `num_predict` gốc) · **Điều kiện chấp nhận:** khác gốc, không leak, đủ số câu
- **Lượt:** 2 · **temperature:** `temp_pass3` (Ollama 0.02; Gemini 0.05) · **token multiplier:** 1.5 · **Điều kiện chấp nhận:** như trên
- **Lượt:** 3 · **temperature:** `temp_pass3` (Ollama 0.02; Gemini 0.05) · **token multiplier:** 2.0 · **Điều kiện chấp nhận:** nới lỏng: bỏ điều kiện số câu

Giá trị Ollama truyền ở `ollama_translator.py:606-607` , Gemini ở `gemini_translator.py:632-633` . Tham số `default_temp` của hàm được nhận nhưng không dùng.

Thất bại cả 3 → thay đoạn bằng marker `[[MISSING_CHUNK:<chunk_index>]]` và ghi vào `failed_chunks` gồm `chunk_index` , `char_position_start` , `reason` , `original_text_preview` (60 ký tự), `original_text` đầy đủ (dòng 625-632). Nguyên tắc thiết kế: lỗi phải hiện rõ, không âm thầm để lọt bản dịch tồi.

Báo cáo `last_report` (dòng 649-656): `engine` , `total_chunks` , `total_paras` , `success_direct` , `success_fallback` , `failed_chunks` . `translate_file()` ghi ra `<tên gốc>.translation_report.json` cạnh file output, `refresh_failed_positions()` ( `base.py:73-83` ) cập nhật `line_number` và `marker` chính xác theo file thật.

Vá sau khi ghi file — `repair_missing_chunks()` ( `base.py:102-235` ):

Tìm các marker bằng regex `\[\[MISSING_CHUNK:\d+\]\]` ( `base.py:9` ); marker thứ k ↔ entry thứ k trong `failed_chunks` . Lấy `original_text` ; với report cũ chỉ có preview thì tra ngược file nguồn bằng `startswith(preview)` rồi fallback `preview[:30] in sp` . Dịch lại bằng `_translate_single_paragraph()` . Bản của Ollama ( `ollama_translator.py:665-715` ) override bản base để chỉ gọi API trực tiếp (không chạy lại cả pipeline — tránh sinh marker mới), 3 lần ở temperature 0.05 / 0.02 / 0.01 với token ×1.0 / ×1.5 / ×2.0; đoạn ngắn < 100 ký tự với model chat được bọc thêm chỉ dẫn "Translate the following single Chinese sentence..." vì model hay nhại lại câu ngắn. Chấp nhận kết quả còn ≤ 5 ký tự Hán ("tốt hơn marker") — `base.py:189-196` , `ollama_translator.py:708-711` . Ghép lại file, cập nhật report. Adapter gọi tối đa 3 vòng.

### 4.10 Trích xuất glossary tự động (vòng lặp tự học)

`OllamaTranslator.extract_glossary_from_text()` ( `ollama_translator.py:270-319` ):

Prompt tiếng Việt yêu cầu lập glossary 4 nhóm: tên nhân vật, địa danh/môn phái, thuật ngữ tu tiên/công pháp/thảo dược, từ lóng mạng. Dùng ví dụ đúng và ví dụ phản diện (negative examples): "KHÔNG dịch 药谷 thành thung lũng thuốc", "KHÔNG dịch 修为 thành thiên tài", "金手指 -> Ngón tay vàng, KHÔNG dịch thành kim chỉ tay". Liệt kê các key đã có: "BỎ QUA và KHÔNG trích xuất lại...". Chỉ đưa 1500 ký tự đầu chương (Ollama, dòng 292); Gemini/Gemini API dùng 3000 ( `gemini_translator.py:226` , `gemini_api_translator.py:227` ). Gọi với `system_instruction="You are a JSON data extractor. Output raw JSON only."` , `response_json=True` ( `format:` `"json"` ), thử 2 lần. Hậu xử lý robust: cắt từ `{` đầu tiên đến `}` cuối cùng, `json.loads` , chỉ giữ cặp string-string, `strip()` . Bản Gemini ( `gemini_translator.py:204-251` ) khác một chút: dùng `responseMimeType: "application/json"` , temperature 0.1, chỉ 1 lần gọi (không vòng thử lại), bóc rào json` rồi `json.loads` , trả nguyên dict (không lọc string-string). Bản `gemini_api` ( `gemini_api_translator.py:209-252` ) dùng prompt ngắn hơn (không có ví dụ phản diện).

Vòng lặp: chương N → trích tên mới → lưu story + global → `set_glossary` lại → chương N+1 được ép dùng tên đó. Càng dịch càng nhất quán.

### 4.11 Engine Gemini và Gemini API

`GeminiTranslator` ( `gemini_translator.py` ):

Endpoint: `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key=...` (dòng 284). Payload: `contents` , `systemInstruction` , `generationConfig {temperature, maxOutputTokens: 4096}` , và `safetySettings` với 4 category đặt `BLOCK_NONE` (dòng 290-313) — vì truyện mạng hay có bạo lực. Rate limiting phía client: tối thiểu 5 giây giữa hai request (dòng 319-323) — phù hợp free tier. Retry: 429/503 với backoff `[6, 12, 24]` giây, tôn trọng header `Retry-After` ; lỗi 400 ném ngay (dòng 315-375). `finishReasonSAFETY` / `PROHIBITED_CONTENT` → `GeminiSafetyBlockError` (dòng 266-267).

Fallback cloud → local ( `_get_ollama_fallback_translator` , dòng 414-428): khi một chunk bị chặn/lỗi/cắt cụt, chỉ riêng chunk đó được dịch bằng Ollama (model đọc từ `toolCaoTruyen/config.json` qua `core.config_manager.load_config()` , khoá `translator.ollama_model` , mặc định `qwen2.5:7b-instruct` ; nếu không có `config.json` thì hàm trả `None` và không fallback được), rồi chunk sau quay lại Gemini (dòng 496-525). Trạng thái chunk ghi `fallback_success` . Fallback này cũng áp dụng cho tiêu đề (dòng 454-470) và cho `translate_fn` của Tầng 2 (dòng 604-622). Lưu ý: fallback gọi `OllamaTranslator.translate()` — tức chạy cả pipeline 2 tầng của Ollama cho riêng chunk đó. Có thêm nhánh chặn ở mức prompt: `promptFeedback.blockReason` → `GeminiSafetyBlockError` (dòng 272-274). Timeout mỗi request 90 giây (dòng 259). MAX_TOKENS → thử lại `min(8192, 4096 × 1.5)` = 6144 token (dòng 391).

`GeminiApiTranslator` ( `gemini_api_translator.py` ):

Chuyển payload: `systemInstruction` → message `system` , `contents` → message `user` , `maxOutputTokens` → `max_tokens` , `responseMimeType: application/json` → `response_format: {"type": "json_object"}` ; `finish_reason: "length"` → `MAX_TOKENS` , `"content_filter"` → safety error (dòng 45-119). Header `Authorization: Bearer<key>` ; khoảng cách request 1 giây (dòng 152-156).

4.12 `orchestrator/llm.py` — hạ tầng LLM dùng chung

Module này không dùng cho bước dịch (bước dịch chạy trong subprocess `toolCaoTruyen` ), mà cho sáng tác AI, phân cảnh Bước 3, Autosub và chatbot:

`resolve_llm(engine, args, g_config, default_model)` (dòng 20-66) → `(api_key, base_url, model)` . Thứ tự chọn model: `args["llm_offline_model"]` → `default_model` do nơi gọi truyền (Bước 3/Autosub truyền `video.default_llm_model` trong cấu hình chung, `pipeline.py:534-536, 650-652` ) → mới tới các hằng `DEFAULT_*` dưới đây (chỉ dùng khi hai nguồn trước rỗng). Sáng tác AI không qua `resolve_llm` mà dùng `_resolve_ai_write_args` (mục 4.13). `gemini` → base `https://generativelanguage.googleapis.com/v1beta/openai/` (endpoint OpenAI-compatible chính chủ của Google), model mặc định `DEFAULT_GEMINI_ONLINE_MODEL = "gemini-2.0-flash"` ; thiếu key → `ValueError` có hướng dẫn. `ollama` → key giả `"ollama"` , base `http://localhost:11434/v1` , model mặc định `DEFAULT_OLLAMA_MODEL =` `"qwen2.5:3b-instruct"` ( `orchestrator/config.py:8-10` ). còn lại ( `gemini_api` ) → base `http://localhost:7860/v1` (hoặc `crawler.gemini_offline_base_url` ), model `DEFAULT_GEMINI_PROXY_MODEL = "gemini-3-flash"` ; cũng ném `ValueError` nếu không tìm được key. `chat()` (dòng 69-87): POST `{base_url}/chat/completions` bằng `httpx` , temperature mặc định 0.85, timeout 300s. Một hàm dùng cho mọi nhà cung cấp nhờ chuẩn OpenAI-compatible. `chat_stream_ollama()` (dòng 94-166): gọi native `/api/chat` với `stream: True` , đọc NDJSON từng dòng, yield `{"delta":` `...}` ; với model "thinking" ( `qwen3` , `deepseek-r1` , `magistral` ) đặt `think: False` vì khối suy luận sẽ ăn hết `num_predict=512` và trả content rỗng (dòng 90-139). `unload_ollama()` (dòng 169-188): POST `/api/generate` với `keep_alive: 0` để nhả VRAM; dùng khi đổi model chatbot tránh hai model cùng chiếm VRAM gây OOM trên máy 6GB ( `orchestrator/main.py:1163-1170` , `set_chat_model` ; ngoài ra còn gọi ở `main.py:1049` ).

4.13 Sáng tác bằng AI — `story_writer.generate_story()`

Tham số được suy ra bởi `_resolve_ai_write_args()` ( `orchestrator/pipeline.py:8-40` ):

Engine `ollama` → base `ollama_base_url` (mặc định `http://localhost:11434/v1` ), model `trans_args.ollama_model` hoặc `qwen2.5:7b-instruct` . Khác → base Gemini proxy `:7860/v1` , model mặc định `gemini-2.5-flash` . `words_per_chapter` kẹp trong [200, 4000], mặc định 800 — "để model nhỏ không bị ép viết quá dài rồi lạc mạch".

Chạy trong thread (không phải subprocess) vì chỉ là I/O gọi HTTP ( `pipeline.py:333-390` , `start_ai_write` ), đăng ký bằng `register_manual_task` . Status `WRITING` → `TRANSLATED` (nội dung đã là tiếng Việt, bỏ qua bước dịch) hoặc `WRITE_FAILED` .

Thuật toán ( `story_writer.py:24-90` ):

1. System prompt: nhà văn Việt Nam, viết truyện dài kỳ (kèm thể loại), mỗi chương mở đầu bằng dòng tiêu đề, chỉ trả nội dung. 2. Chương 1: đưa ý tưởng `topic` + độ dài. 3. Chương i > 1: đưa `topic` + tóm tắt các chương trước + "viết tiếp chương i".

4. Sau mỗi chương, gọi LLM lần 2 tóm tắt 2–3 câu (temperature 0.3, timeout 120s, chỉ đưa 4000 ký tự đầu); lỗi thì fallback 200 ký tự đầu chương. 5. `summary` được cắt giữ 2500 ký tự cuối → bộ nhớ "trượt" có kích thước cố định, không làm tràn context dù truyện dài. 6. Ghi file tên chuẩn `Chương NNNN - [VI] Tiêuđề.md` qua `chapter_filename()` và `title_from_text()` (bỏ `#` , bỏ tiền tố "Chương N:").

Đây là kỹ thuật rolling summary memory — giải pháp kinh điển cho giới hạn context window của LLM. Lợi ích đồ án: nội dung tự sinh nên sạch bản quyền khi demo.

## 5. Sơ đồ luồng

### 5.1 Luồng tổng thể Bước 1b

### 5.2 Dịch 2 tầng trong một chương

### 5.3 Tuần tự một lời gọi Ollama

### 5.4 Fallback Gemini → Ollama

### 5.5 Sáng tác AI với rolling summary

## 6. Hạn chế & hướng phát triển

Phần này quan trọng: chủ động nêu hạn chế cho thấy bạn hiểu sâu hệ thống. Tất cả dưới đây đều kiểm chứng từ code.

1. Proxy `gemini_api` bỏ qua `temperature` / `max_tokens` . Route `/v1/chat/completions` của proxy ( `toolCaoTruyen/Gemini-` `API/server/routes/chat.py` ) chỉ ghép messages thành prompt rồi gọi `generate_content` ; schema có trường `temperature` , `max_tokens` ( `server/schemas.py:23-24` ) nhưng route không dùng. Hệ quả: chiến lược "hạ temperature khi leak" và "tăng max_tokens khi cắt cụt" không có tác dụng với engine `gemini_api` . Thêm nữa, schema response mặc định `finish_reason: "stop"` ( `server/schemas.py:40` ) nên proxy không bao giờ báo `"length"` → nhánh phát hiện cắt cụt `MAX_TOKENS` cũng không kích hoạt; `response_format` (JSON mode) không có trong schema request nên bị bỏ qua. Proxy cũng gộp mọi message thành một chuỗi prompt dạng `[System Instructions:...]\n\nUser:...` ( `routes/chat.py:28-` `52` ). Với `ollama` / `gemini` thì hoạt động đúng. 2. `GeminiApiTranslator` không chọn glossary theo chunk. `call_gemini_api` gọi `build_system_prompt(source_lang,` `is_title)` không truyền `chunk_text` ( `gemini_api_translator.py:130` ), nên nhánh `else` lấy 20 mục đầu tiên của glossary bất kể chunk ( `gemini_translator.py:187-191` ), và idioms không được dùng. Glossary lớn hơn 20 mục thì các tên xuất hiện trong chunk có thể không được chèn. Sửa: truyền `text` như `GeminiTranslator` ( `gemini_translator.py:286` ).

3. `leak_threshold_percent` gần như không có tác dụng. Tham số được nhận và tính `leak_threshold_ratio` nhưng `contains_chinese_leak()` áp dụng Zero Tolerance (≥ 1 ký tự Hán là lỗi) ( `ollama_translator.py:103-114` ). Đây là quyết định chủ ý (comment "Zero Tolerance") nhưng tham số CLI `--leak-threshold` gây hiểu nhầm. 4. Không bắt được lỗi dịch sai nghĩa. Ba tiêu chí (untranslated/leak/content_missing) chỉ bắt lỗi hình thức. Bản dịch trôi chảy nhưng sai nghĩa vẫn qua. Đếm câu bằng dấu câu cũng thô (câu tiếng Việt có thể gộp/tách khác gốc). Hướng phát triển: back-translation, LLM-as-judge, hoặc metric như COMET trên tập mẫu. 5. Mất ngữ cảnh giữa các chunk. Mỗi chunk dịch độc lập, không kèm đoạn trước → đại từ/xưng hô có thể không nhất quán. `utils.py` có sẵn `get_context_before/get_context_after` nhưng hiện không được dùng (chỉ import). Hướng: chèn 1–2 câu trước làm ngữ cảnh chỉ-đọc. 6. Trích glossary có thể sai và "khoá cứng". Chính sách chỉ-thêm bảo vệ bản đúng, nhưng nếu lần đầu trích sai thì sai mãi cho đến khi người dùng sửa tay `glossary.json` . Chỉ nhìn 1500/3000 ký tự đầu chương → tên xuất hiện cuối chương bị bỏ sót. So khớp `k in chunk_text` không phân biệt ranh giới từ (tiếng Trung không có dấu cách) nên một key ngắn có thể khớp nhầm bên trong từ dài hơn. 7. Model MT + `same_as_trans` . Nhánh bỏ qua auto-extract cho model MT chỉ kích hoạt khi `glossary_extractor is None` ( `adapter_cli.py:238` ). Với cấu hình chung mặc định `glossary_extract_engine: "same_as_trans"` ( `orchestrator/config.py:54` ), extractor chính là translator nên vẫn gọi trích xuất JSON trên model MT 1.8B; kết quả nhiều khả năng rỗng sau 2 lần thử (không gây hỏng, chỉ tốn thời gian). Chưa kiểm chứng bằng chạy thật trong phạm vi tài liệu này. 8. `--auto-extract` không tắt được qua CLI vì `action="store_true", default=True` ( `adapter_cli.py:418` ).

9. `num_predict` > `num_ctx` như phân tích ở 2.6 — ngân sách output thật bị giới hạn bởi context 2048. 9b. `is_available()` khớp quá rộng. Ngoài khớp tên đầy đủ, hàm coi là có model nếu phần trước dấu `:` trùng ( `ollama_translator.py:59-62` ). Ví dụ máy chỉ cài `qwen2.5:3b-instruct` thì `qwen2.5:7b-instruct` vẫn được coi là "sẵn sàng", rồi lời gọi `/api/chat` mới lỗi (model not found) → chunk rơi vào trạng thái `failed` . Chưa kiểm chứng bằng chạy thật.

10. Tuần tự, không song song. Chunk dịch lần lượt để giữ thứ tự và tránh tràn VRAM; Gemini còn bị giãn 5s/request. Chương dài dịch chậm. Hướng: batch nhiều chunk cho cloud, hoặc `OLLAMA_NUM_PARALLEL` khi VRAM dư.

11. Sáng tác AI: không có kiểm soát độ dài thực tế (chỉ "khoảng N từ" trong prompt), rolling summary 2500 ký tự có thể quên chi tiết xa; không có bảng nhân vật cố định. 12. Vấn đề ToS: proxy Gemini web là tuỳ chọn tiện lợi lúc phát triển; hệ thống có 2 đường hợp lệ (Gemini API chính chủ, Ollama offline). Nên demo bằng Ollama.

Hướng phát triển tổng quát: thêm context window trượt, đánh giá chất lượng tự động, UI sửa glossary, fine-tune LoRA một model nhỏ chuyên văn tiên hiệp Trung→Việt, hỗ trợ song song có kiểm soát VRAM.

## Câu hỏi hội đồng có thể hỏi

### 1. LLM dịch văn bản như thế nào về bản chất?

LLM decoder-only chỉ học một việc: dự đoán token tiếp theo. Ta đưa prompt "hãy dịch đoạn sau sang tiếng Việt: <đoạn Trung>", model sinh từng token tiếng Việt, mỗi bước dùng self-attention nhìn lại toàn bộ đoạn gốc và phần đã dịch, lấy mẫu một token, nối vào, lặp đến khi gặp stop token. Nhờ instruction tuning, nó hiểu "dịch" là nhiệm vụ cần làm.

2. Giải thích công thức attention. `softmax(QK^T/sqrt(d_k))V` : Q là "câu hỏi" của mỗi token, K là "nhãn", V là "nội dung". `QK^T` đo độ khớp mọi cặp token; chia `sqrt(d_k)` để phương sai ổn định, softmax khỏi bão hoà; softmax ra trọng số tổng bằng 1; nhân V để lấy trung bình có trọng số thông tin. Ví dụ "hắn" sẽ đặt trọng số cao lên "Cố An" để dịch đúng đại từ.

### 3. Vì sao temperature khi dịch thấp (0.02–0.2) mà khi viết truyện lại 0.85?

`p_i` ∝ `exp(z_i/T)` : T nhỏ làm phân phối nhọn, gần greedy → ổn định, bám nghĩa, ít bịa. Viết truyện cần đa dạng nên T cao. Code còn chủ động hạ xuống 0.02 khi phát hiện rò rỉ chữ Hán ( `ollama_translator.py:450` ). Riêng HY-MT2 dùng 0.7 nhưng kèm top_k 20, top_p 0.6 theo khuyến nghị nhà phát hành.

### 4. Model 7B sao chạy được trên GPU 6GB?

Quantization: Q4_K_M lưu mỗi trọng số ~4.85 bit thay vì 16 bit → 7.6B tham số còn ~4.6GB. Block 32 trọng số dùng chung một scale, `w≈s·q` . Cộng KV cache (~115MB ở num_ctx 2048) và overhead. Code còn giảm `num_ctx` về 2048 để tiết kiệm KV cache ( `registry.py:38-40` ) và có `unload_ollama` (keep_alive=0) để nhả VRAM.

### 5. Ollama là gì, khác gì gọi thư viện Python trực tiếp?

Ollama là runtime/server cục bộ bọc llama.cpp: quản lý model (pull/create), tự nạp vào GPU, API HTTP cổng 11434 cả native lẫn OpenAI-compatible. Nhờ HTTP, bước dịch chạy ở venv riêng mà không cần cài PyTorch/CUDA cho model ngôn ngữ; đổi model chỉ đổi tên.

### 6. GGUF và Modelfile để làm gì? Tại sao phải tự viết Modelfile cho HY-MT2?

GGUF là file trọng số lượng tử + metadata của llama.cpp. Modelfile khai báo `FROM` , `TEMPLATE` , `PARAMETER` . Bản GGUF của HY-MT2 có chat template tự sinh bị hỏng (chứa `"onse }}"` , không chèn `.Prompt` ) nên model chỉ trả rác "onse"; em viết lại TEMPLATE theo special token gốc `<`｜ `hy_User`｜`>` , `<`｜`hy_Assistant`｜`>` và stop token ( `Modelfile.hy-mt2:3-17` ).

### 7. Tại sao chia chương thành chunk 350–500 ký tự?

Model nhỏ với input dài hay bỏ câu, sót chữ Hán; chunk nhỏ giữ `num_ctx` 2048 để tiết kiệm VRAM; lỗi khoanh vùng từng đoạn nên vá rẻ. Chia theo ranh giới đoạn `\n\n` , không cắt giữa đoạn ( `ollama_translator.py:67-101` ). Gemini context lớn nên dùng 1000.

### 8. Làm sao đảm bảo tên nhân vật nhất quán giữa các chương?

Glossary 3 tầng: idioms < global < per-story. Trước khi dịch mỗi chunk, chọn tối đa 20 thuật ngữ xuất hiện trong chunk chèn vào prompt với nhãn "CRITICAL REQUIREMENT" (hoặc "参考下面的翻译" cho HY-MT2). Mỗi chương, LLM trích tên mới ra JSON, lưu lại và áp dụng ngay chương sau. Ghi chỉ- thêm để LLM không ghi đè bản đúng.

### 9. Hệ thống phát hiện bản dịch lỗi bằng cách nào?

Ba tiêu chí từng đoạn: `untranslated` (rỗng/giống gốc), `leak` (còn ≥ 1 ký tự trong `[\u4e00-\u9fff]` ), `content_missing` (số câu dịch < số câu gốc). Thêm `done_reason=="length"` để phát hiện cắt cụt. Lỗi → dịch lại 3 lượt với temperature thấp và ngân sách token tăng dần ×1.5, ×2.0. Không vá được → marker `[[MISSING_CHUNK:n]]` + report JSON, sau đó `repair_missing_chunks` thử thêm tối đa 3 vòng.

### 10. Nếu Gemini từ chối dịch vì chính sách an toàn thì sao?

`finishReason` SAFETY/PROHIBITED_CONTENT → `GeminiSafetyBlockError` ; riêng chunk đó được chuyển sang `OllamaTranslator` local, chunk sau quay lại Gemini ( `gemini_translator.py:496-525` ). Đã đặt `safetySettingsBLOCK_NONE` để giảm chặn.

### 11. Model chuyên dịch (HY-MT2) và model chat (Qwen) khác nhau thế nào trong code?

`prompt_style` : MT dùng 1 message user theo template cố định của nhà phát hành, glossary chèn theo cú pháp terminology intervention, không system prompt/few-shot; chat dùng system prompt 9 yêu cầu + genre + glossary. MT nhẹ (1.8B, ~2GB) và ít chém nhưng không làm được trích xuất JSON.

### 12. Vì sao có cả `orchestrator/llm.py` riêng khi `toolCaoTruyen` đã có translator?

Translator chạy trong subprocess, venv riêng của submodule. `llm.py` là hạ tầng cho các tính năng trong orchestrator: sáng tác AI, phân cảnh/autosub (resolve engine), chatbot streaming, unload VRAM. Nó dùng chuẩn OpenAI-compatible nên một hàm `chat()` gọi được Gemini chính chủ, Ollama `/v1` và proxy.

### 13. Sáng tác AI giữ mạch truyện qua nhiều chương thế nào khi LLM không có trí nhớ?

Rolling summary: sau mỗi chương, gọi LLM tóm tắt 2–3 câu (temperature 0.3), nối vào `summary` và giữ 2500 ký tự cuối; chương sau nhận `topic + summary` . Bộ nhớ kích thước cố định nên không tràn context ( `story_writer.py:52-87` ).

### 14. Hạn chế lớn nhất của module dịch?

Chỉ kiểm tra lỗi hình thức, không bắt được sai nghĩa; mất ngữ cảnh giữa chunk; proxy `gemini_api` bỏ qua temperature/max_tokens nên cơ chế retry không có tác dụng với engine đó; `GeminiApiTranslator` chỉ chèn 20 mục glossary đầu thay vì theo chunk. Hướng: context trượt, LLM-as-judge/COMET, sửa truyền `chunk_text` .

### 15. Context window là gì, vượt thì sao?

Tổng token prompt + output model xử lý trong một lượt ( `num_ctx` ). Attention O(n²) và KV cache tuyến tính theo n nên bị giới hạn. Vượt thì phần đầu bị cắt hoặc output dừng sớm. Code đặt 2048– 2560 cho dịch, 8192 cho chatbot và cảnh báo `truncated` khi prompt ≥ 95% `num_ctx` ( `llm.py:160` ).

## Tóm tắt 1 phút

"Bước 1b biến chương truyện tiếng Trung thành tiếng Việt bằng mô hình ngôn ngữ lớn. Về bản chất, LLM là Transformer decoder-only: văn bản được cắt thành token, đổi thành vector embedding, qua nhiều lớp self-attention — công thức softmax của Q nhân K chuyển vị chia căn d, nhân V — rồi dự đoán từng token tiếp theo; temperature thấp giúp bản dịch ổn định. Để chạy offline trên GPU 6GB, em dùng Ollama, bên trong là llama.cpp với file GGUF lượng tử hoá: Qwen 7B ở 4 bit còn khoảng 4,6GB, model chuyên dịch HY-MT2 1,8B ở Q8 chỉ khoảng 2GB, và em phải tự viết Modelfile vì chat template gốc bị hỏng. Hệ thống có ba engine — Ollama, Gemini, Gemini qua endpoint OpenAI-compatible — chọn theo Strategy pattern, Gemini bị chặn thì tự

chuyển chunk đó sang Ollama. Mỗi chương được chia chunk 350 đến 500 ký tự theo đoạn; trước khi dịch, hệ thống chèn tối đa 20 thuật ngữ từ glossary ba tầng vào prompt để ép tên Hán Việt nhất quán, và mỗi chương tự trích tên mới bổ sung glossary. Sau khi dịch, mỗi đoạn được kiểm tra ba lỗi: chưa dịch, sót chữ Hán, thiếu câu; lỗi thì dịch lại tối đa 3 lượt với temperature thấp dần, cuối cùng vẫn lỗi thì đánh dấu MISSING_CHUNK kèm báo cáo JSON để vá tiếp. Ngoài ra còn chế độ AI tự sáng tác truyện, giữ mạch bằng tóm tắt trượt 2500 ký tự."
