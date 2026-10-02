# Chương 06. Bước 3a — Phân cảnh ngữ nghĩa, trích xuất nhân vật & sinh prompt bằng LLM

- Phạm vi chương: phần "biên kịch + đạo diễn hình ảnh" của Bước 3 (dựng video). Đầu vào là một chương truyện `.md` (tiếng Việt) và file audio lồng tiếng `.wav` của chương đó; đầu ra là danh sách `Scene` đã có mốc thời gian và prompt tiếng Anh sẵn sàng đưa cho Stable Diffusion (chương sau).

- Mọi đường dẫn trong chương này tính từ `AIVoice/apps/MediaComposer/` nếu không ghi rõ khác. Số dòng trích dẫn ứng với commit `f219bd9` (nhánh `main` ).

## 1. Vai trò trong hệ thống

### 1.1. Vị trí trong pipeline tổng

Hệ thống có 5 bước lớn (cào/dịch → TTS → dựng video → autosub → ghép). Bước 3 được orchestrator FastAPI gọi bằng một subprocess riêng:

- `orchestrator/pipeline.py:525-551` dựng câu lệnh: `AIVoice/.venv/Scripts/python.exe`

```
AIVoice/apps/MediaComposer/adapter_video_cli.py --story-name ... --genre ... --input-dir ... --llm-api-key ... --
```

- `llm-base-url...--llm-model...` kèm `--use-semantic-split` / `--extract-characters` (mặc định bật, `orchestrator/pipeline.py:560-569` ). LLM mặc định cho Bước 3: `default_llm_engine = "ollama"` , `default_llm_model = DEFAULT_OLLAMA_MODEL = "qwen2.5:3b-` `instruct"` ( `orchestrator/config.py:10` , `:81-82` ). Nghĩa là mặc định chạy local, qua endpoint tương thích OpenAI của Ollama ( `http://localhost:11434/v1` ).

Bên trong subprocess, Bước 3 lại chia thành 3 "trạm" ( `app/services/storytelling/orchestrator.py` ):

- **Trạm:** Trạm 1 · **Hàm:** `step1_generate_script` (dòng 190) · **Việc làm:** Đọc audio → tách cảnh → map thời gian → sinh prompt · **Chương tài liệu:** Chương này (3a)
- **Trạm:** Trạm 2 · **Hàm:** `step2_generate_images` (dòng 328) · **Việc làm:** Sinh ảnh SD, IP-Adapter, LoRA, face detailer · **Chương tài liệu:** Chương sinh ảnh
- **Trạm:** Trạm 3 · **Hàm:** `step3_render_final` (dòng 543) · **Việc làm:** Upscale + ghép video FFmpeg · **Chương tài liệu:** Chương dựng video

Trước Trạm 1 còn một bước chạy một lần cho mỗi truyện: trích xuất nhân vật ( `adapter_video_cli.py:170-209` ) để tạo "character bible".

### 1.2. Input / Output của chương này

Input

- `chapter_xxx.md` : văn bản chương đã dịch/biên tập, tiếng Việt. `chapter_xxx.wav` : audio lồng tiếng đọc nguyên văn file `.md` (Bước 2). (tùy chọn) `.srt` có sẵn. `StoryContext` của truyện: danh sách nhân vật ( `Character` ), thể loại ( `genre` ), file style ( `style_prompt.txt` ).

Output: `list[Scene]` được lưu trong `state.json` với `step = "SCRIPT_READY"` ( `orchestrator.py:324` ). Mỗi `Scene` (định nghĩa ở `models.py:4-19` ):

```
@dataclass
class Scene:
    scene_id: int
                            # 0-indexed
    text_vi: str
                            # Văn bản tiếng Việt gốc
    word_count: int
    start_time: float
                            # giây, từ SRT
                            # giây, từ SRT
    end_time: float
    duration_sec: float
                            # = end_time - start_time
    image_prompt: str
                            # EN, do LLM sinh
    characters_in_scene: List[str]
                                    # tên nhân vật được detect
    primary_character: str
                            # nhân vật dùng face embedding
                            # 0=chưa refine, 1-4=đã thử cấp nào
    fallback_level: int
    accepted_seed: int
                            # seed của ảnh được chọn
                            # đường dẫn ảnh đã chọn
    frame_path: str
    shot_type: str = "wide"
                             # close | medium | wide
```

Ngoài các field chính thức, code còn gắn thuộc tính động (runtime fields) để truyền dữ liệu giữa các bước mà không phá cấu trúc `asdict` : `_semantic_meta` , `_llm_background_prompt` , `_llm_layout` , `_llm_action` ( `models.py:22-27` ). `scene_to_dict` / `scene_from_dict` giữ chúng qua lần resume ( `models.py:30-51` ).

### 1.3. Bức tranh một câu

- "Máy đọc chương truyện, nhờ LLM chia thành các cảnh có ý nghĩa (đổi địa điểm, đổi nhân vật, đổi hành động), gán cho mỗi cảnh một khoảng thời gian khớp với giọng đọc, rồi nhờ LLM viết cho mỗi cảnh một câu lệnh vẽ bằng tiếng Anh theo đúng 'ngôn ngữ' mà Stable Diffusion hiểu, trong khi phong cách vẽ và ngoại hình nhân vật được hệ thống khóa cứng để các cảnh đồng nhất."

## 2. Nền tảng lý thuyết từ gốc

Phần này dạy các khái niệm cần để trả lời hội đồng. Mỗi mục đi theo thứ tự: trực giác → cơ chế → toán nhẹ → hạn chế.

### 2.1. Phân đoạn văn bản (text segmentation)

Trực giác. Một chương truyện 2.000–4.000 từ đọc ra 10–20 phút audio. Nếu chỉ vẽ 1 ảnh thì video nhàm; nếu vẽ 1 ảnh mỗi câu thì hàng trăm ảnh — chậm và giật. Cần chia văn bản thành cảnh: một đoạn liên tục mà người xem cảm nhận là "cùng một khung hình".

Ba cấp độ phân đoạn:

- **Cấp:** Hình thức · **Đơn vị:** Đoạn văn (paragraph) · **Cách nhận biết:** Dòng trống · **Trong dự án:** `_extract_paragraphs` tách theo dòng trống
- **Cấp:** Cú pháp · **Đơn vị:** Câu · **Cách nhận biết:** Dấu `. ! ? … ;` · **Trong dự án:** Regex `(?<=[\.\!\?\…;])\s+`
- **Cấp:** Ngữ nghĩa · **Đơn vị:** Cảnh (scene) · **Cách nhận biết:** Đổi địa điểm / nhân vật / hành động / thời gian · **Trong dự án:** LLM quyết định

Hai trường phái phân đoạn ngữ nghĩa kinh điển:

- 1. Dựa trên độ tương đồng liên tiếp (TextTiling, Hearst 1997; và biến thể hiện đại dùng sentence embedding): biểu diễn mỗi câu/đoạn thành vector, đo độ giống giữa hai khối liền kề; chỗ độ giống tụt sâu là ranh giới chủ đề. 2. Dựa trên mô hình sinh (LLM): đưa cả văn bản đã đánh số, yêu cầu LLM trả về danh sách ranh giới. LLM "hiểu" đổi cảnh theo nghĩa kể chuyện (nhân vật mới bước vào, trời chuyển tối) chứ không chỉ theo từ vựng.

Dự án dùng trường phái 2 (LLM), có trường phái "không ngữ nghĩa" (đếm từ) làm phương án dự phòng ( `md_parser.py` ). Dự án không dùng sentence embedding/cosine similarity cho văn bản ở bước này — grep `app/` và `orchestrator/` không có `SentenceTransformer` / `sentence_transformers` . Cosine similarity có xuất hiện trong dự án nhưng cho embedding ảnh (so độ giống khuôn mặt nhân vật: `face_detailer.py:174` , `dataset_collector.py:179` ), thuộc chương sinh ảnh. Hội đồng rất hay hỏi phương án embedding cho văn bản, nên mục 2.2 vẫn dạy để em so sánh được.

### 2.2. Sentence embedding & cosine similarity (để so sánh phương án)

Trực giác. Embedding là "tọa độ ý nghĩa": mỗi câu được ánh xạ thành một điểm trong không gian nhiều chiều (vd 384 hoặc 768 chiều), sao cho câu có nghĩa gần nhau thì điểm gần nhau. "Nàng rút kiếm" và "Cô ấy tuốt gươm" gần nhau dù không chung từ nào.

Cơ chế. Một mô hình Transformer encoder (vd họ Sentence-BERT) đọc câu, cho ra vector cho từng token, rồi lấy trung bình (mean pooling) thành một vector câu. Mô hình được huấn luyện bằng contrastive learning: kéo cặp câu cùng nghĩa lại gần, đẩy cặp khác nghĩa ra xa.

Toán. Với hai vector `a` , `b` :

```
cos(a, b) = (a · b) / (‖a‖ · ‖b‖) = Σ aᵢbᵢ / ( sqrt(Σ aᵢ²) · sqrt(Σ bᵢ²) )
```

- `a · b` : tích vô hướng — cộng dồn tích từng chiều. `‖a‖` : độ dài vector. Kết quả trong `[-1, 1]` : 1 = cùng hướng (cùng nghĩa), 0 = không liên quan. Dùng cosine thay vì khoảng cách Euclid vì ta quan tâm hướng (ý nghĩa) chứ không phải độ dài (thường phụ thuộc độ dài câu).

Áp dụng vào tách cảnh (nếu dùng): tính `sᵢ= cos(eᵢ, eᵢ₊₁)` giữa các đoạn liền kề; cắt cảnh ở các vị trí `sᵢ` là cực tiểu cục bộ và thấp hơn ngưỡng.

Hạn chế (lý do dự án không chọn):

- Chỉ đo "giống nhau về chủ đề", không biết địa điểm hay ai đang có mặt — hai câu cùng nói về kiếm nhưng khác bối cảnh vẫn giống nhau. Không sinh ra metadata ( `location` , `characters` , `time_of_day` , `action` ) mà bước sinh prompt cần. Cần nạp thêm một model embedding tiếng Việt (VRAM/RAM) — trong khi LLM đã được nạp sẵn cho bước sinh prompt.

2.3. Độ giống chuỗi ký tự: `difflib.SequenceMatcher`

Đây là "similarity" thực sự được dùng trong chương này — để khớp văn bản cảnh với phụ đề SRT ( `srt_mapper.py:418-421` ).

Trực giác. So hai chuỗi, tìm các khúc trùng nhau dài nhất, rồi tính tỉ lệ ký tự trùng.

Cơ chế (thuật toán Ratcliff/Obershelp, bản trong `difflib` ): tìm khối con chung dài nhất giữa hai chuỗi, rồi đệ quy cho phần bên trái và bên phải của khối đó. `get_matching_blocks()` trả về danh sách các khối `(a, b, size)` .

Toán.

```
ratio = 2 · M / T
```

- `M` : tổng số ký tự thuộc các khối khớp. `T` : tổng độ dài hai chuỗi. `ratio = 1` khi hai chuỗi giống hệt.

Code dùng ngưỡng `ratio>=0.5` ( `srt_mapper.py:421` ). Lý do dùng so khớp chuỗi thay cho embedding: SRT là bản chép lời của chính văn bản đó (hoặc do Whisper nghe lại audio đọc nguyên văn), nên hai phía giống nhau gần như nguyên văn — so khớp ký tự là đủ và tất định.

Hệ quả toán học cần biết. Vì `M≤min(len(a), len(b))` , nên `ratio≤2·len(a) / (len(a) + len(b))` . Nếu chuỗi `b` (cửa sổ SRT) dài gấp hơn 3 lần chuỗi `a` (văn bản cảnh) thì `ratio` không thể đạt 0.5 dù khớp hoàn hảo. Điều này ảnh hưởng trực tiếp tới cách code dùng ngưỡng (xem mục 4.4.3).

### 2.4. Mô hình ngôn ngữ lớn (LLM) — những gì cần biết cho chương này

Trực giác. LLM là máy "đoán token tiếp theo" cực giỏi. Cho nó một đoạn mở đầu (prompt), nó viết tiếp từng token một.

Cơ chế.

- Văn bản được tách thành token (mảnh từ) bằng tokenizer BPE; mỗi token thành vector embedding.

- Chồng nhiều lớp Transformer decoder với self-attention: mỗi token "nhìn" các token trước nó để quyết định ngữ cảnh. Lớp cuối cho ra phân phối xác suất trên toàn bộ từ vựng: `P(t`ₙ `|t₁…t`ₙ`₋₁)` .

Temperature (T). Xác suất được tính bằng softmax có chia nhiệt độ:

```
P(token i) = exp(zᵢ / T) / Σⱼ exp(zⱼ / T)
```

- `zᵢ`: điểm (logit) mô hình cho token `i` . `T` nhỏ (0.2–0.4) → phân phối nhọn → chọn gần như luôn token tốt nhất → ổn định, ít bịa. `T` lớn → sáng tạo, dễ lạc. Dự án chọn: tách cảnh `temperature=0.3` ( `semantic_scene_splitter.py:178` ); sinh prompt và Director's Note `0.4` (cùng dùng `_call_llm` , `llm_prompter.py:21` ); trích danh sách nhân vật `0.3` ( `character_extractor.py:70` ), còn bước "refine" sinh `keywords_en` dùng `0.4` ( `character_extractor.py:106` ). Các tác vụ này cần đúng định dạng hơn là sáng tạo.

Context window. LLM chỉ "thấy" được một số token nhất định mỗi lần gọi. Với Ollama, con số thực tế không phải là context tối đa của model (Qwen2.5 hỗ trợ 32K) mà là tham số `num_ctx` của server. Vượt quá thì phần đầu prompt bị cắt âm thầm hoặc chất lượng giảm. Đây là lý do dự án chunk văn bản (mục 4.3.3) và cắt văn bản dài khi trích nhân vật (mục 4.5).

- Cạm bẫy cần nói thật: Bước 3 gọi Ollama qua endpoint tương thích OpenAI ( `/v1` ) và không truyền `num_ctx` . Chính tài liệu dự án đã ghi nhận lớp `/v1` của Ollama không nhận `num_ctx` ( `docs/PLAN-chatbot-assistant.md:83` ), nên server dùng giá trị mặc định (tài liệu đó ghi 2048 token; con số thật phụ thuộc phiên bản Ollama và biến môi trường `OLLAMA_CONTEXT_LENGTH` , chưa xác minh trên máy chạy thật). Trong khi đó một chunk tách cảnh có thể tới 6000 từ tiếng Việt, tức cỡ 8–12 nghìn token (ước lượng). Vì vậy với chương dài, LLM local có thể chỉ "thấy" một phần văn bản → trả chỉ số không phủ kín → validate hỏng → rơi về `md_parser` . Chatbot của dự án đã chuyển sang API native `/api/chat` kèm `options.num_ctx` ( `orchestrator/llm.py:103-122` ); Bước 3 thì chưa.

`max_tokens` . Trần số token đầu ra. Nếu JSON dài hơn trần, câu trả lời bị cụt → JSON hỏng. Code đặt: tách cảnh 4000, sinh prompt 800, director 3000, trích nhân vật 2500.

System prompt vs user prompt. `system` = "luật chơi, vai trò" (cố định cho mọi cảnh); `user` = dữ liệu của lần gọi này (văn bản cảnh). Tách như vậy giúp tái dùng luật và model tuân thủ tốt hơn.

### 2.5. Structured output (JSON) và độ bền (robustness)

Vấn đề. Code cần dữ liệu có cấu trúc (danh sách chỉ số đoạn, tên nhân vật...). LLM lại sinh văn bản tự do — có thể kèm lời dẫn "Đây là kết quả:", bọc trong `json, thiếu dấu ngoặc, hoặc bịa chỉ số.

Các lớp phòng thủ chuẩn (và dự án dùng lớp nào):

- **Lớp:** 1. Chỉ dẫn trong prompt · **Ý tưởng:** Mô tả schema + "KHÔNG text ngoài JSON" · **Dự án:** Có, mọi prompt
- **Lớp:** 2. JSON mode của API · **Ý tưởng:** `response_format={"type": "json_object"}` → server ép đầu ra là JSON hợp lệ (Ollama/OpenAI hỗ trợ bằng constrained decoding) · **Dự án:** Có ở tách cảnh, sinh prompt, Director's Note (cùng `_call_llm` ), `PromptTranslator` ; không có ở `character_extractor`
- **Lớp:** 3. Parse phòng thủ · **Ý tưởng:** Cắt từ `{` đầu tiên tới `}` cuối cùng rồi `json.loads` · **Dự án:** Có ( `_parse_json_response` , `_parse_json_from_text` , `llm_prompter.py:172-` `179` )
- **Lớp:** 4. Validate ngữ nghĩa · **Ý tưởng:** Kiểm tra dữ liệu có đúng về logic không (chỉ số phủ kín, liên tiếp...) · **Dự án:** Có ở tách cảnh ( `_validate_scene_coverage` )
- **Lớp:** 5. Retry · **Ý tưởng:** Gọi lại khi hỏng · **Dự án:** Ở tầng ứng dụng: chỉ sinh prompt ( `retries=1` → tối đa 2 lần). Ở tầng mạng: client `openai` mặc định tự retry lỗi kết nối/timeout/429/5xx tối đa 2 lần ( `DEFAULT_MAX_RETRIES = 2` trong thư viện; code không đổi `max_retries` )
- **Lớp:** 6. Fallback · **Ý tưởng:** Có phương án khi LLM hỏng · **Dự án:** Tách cảnh → `md_parser` ; sinh prompt → prompt phong cảnh; Director → `{}` ; trích nhân vật → danh sách rỗng (truyện không có character bible)
- **Lớp:** 7. Fail-fast · **Ý tưởng:** Khi tất cả đều hỏng, dừng thay vì chạy tiếp ra rác · **Dự án:** Có ( `AllPromptsFailedError` )

Constrained decoding là gì? Khi bật JSON mode, bộ sinh chỉ cho phép chọn những token giữ cho chuỗi vẫn là tiền tố của một JSON hợp lệ (loại bỏ token sai ngữ pháp bằng cách gán xác suất 0). Nó đảm bảo cú pháp đúng, nhưng không đảm bảo nội dung đúng (LLM vẫn có thể bịa `"paragraphs": [0, 5, 2]` ). Vì vậy lớp 4 (validate) là bắt buộc.

### 2.6. CLIP text encoder & vì sao prompt phải là tiếng Anh

Stable Diffusion 1.5 (checkpoint mặc định `anything-v5` ) không đọc chữ trực tiếp. Prompt đi qua CLIP text encoder (text encoder của CLIP ViT-L/14) để thành vector điều kiện cho U-Net. Cụ thể: prompt → tối đa 77 token → encoder cho ra một ma trận 77 × 768 (mỗi vị trí token một vector ngữ cảnh). U-Net dùng ma trận này qua cross-attention: mỗi vùng ảnh (query) "hỏi" các token (key/value) xem nên vẽ gì ở đó. Vì vậy mỗi token trong prompt thực sự là một "nguồn chỉ dẫn" mà các điểm ảnh có thể chú ý tới.

- CLIP được OpenAI huấn luyện trên ~400 triệu cặp (ảnh, chú thích) lấy từ Internet — chủ yếu là tiếng Anh. Nó học "từ tiếng Anh X ↔ đặc trưng hình ảnh Y" bằng contrastive learning (cặp đúng cosine cao, cặp sai cosine thấp). Tokenizer của CLIP là BPE với ~49.408 token, tối ưu cho tiếng Anh. Chữ Việt có dấu như "Lạc Lan Tuyết" bị băm thành nhiều mảnh byte vô nghĩa với CLIP → vừa tốn token, vừa không mang ý nghĩa hình ảnh. Giới hạn 77 token: CLIP nhận tối đa 77 token (gồm token bắt đầu/kết thúc). Vượt quá thì bị cắt. Dự án xử lý bằng thư viện compel (nối nhiều đoạn 77 token) — `image_generator.py:590-630` , cấu hình `truncate_long_prompts=False` . Các checkpoint anime (Anything V5) được fine-tune trên ảnh có tag kiểu Danbooru ( `1girl, long hair, white dress` ), nên tag ngắn phân cách dấu phẩy hiệu quả hơn câu văn đầy đủ.

→ Kết luận: phải dịch + chuyển thể văn Việt thành tag tiếng Anh. Đây không phải dịch máy thông thường mà là "chuyển ngôn ngữ kể chuyện sang ngôn ngữ mô tả thị giác".

### 2.7. Prompt engineering cho Stable Diffusion

a) Thứ tự token quan trọng. Trong thực tế với SD1.5, tag đứng đầu prompt thường ảnh hưởng mạnh hơn. Đây là kinh nghiệm thực nghiệm của cộng đồng, có một giải thích hợp lý: text encoder của CLIP dùng causal attention mask (mỗi token chỉ nhìn các token đứng trước), nên token đầu ảnh hưởng tới vector của mọi token sau, còn token cuối thì không ảnh hưởng ngược lại; thêm vào đó chú thích trong dữ liệu huấn luyện thường đặt chủ thể chính lên đầu. Code tận dụng điều này: `build_locked_prompt` đặt style → hành động có trọng số → nội dung ( `style_lock.py:103-127` ).

b) Trọng số attention (cú pháp A1111). `(tag:1.3)` nghĩa là nhấn mạnh `tag` 1.3 lần, `(tag:0.8)` là giảm nhẹ. Cơ chế không phải nhân embedding đầu vào của từ, mà can thiệp vào ma trận đầu ra 77×768 của CLIP tại các vị trí token của `tag` . Thư viện compel (bản 2.3.1 trong `AIVoice/.venv` ) làm như sau cho trọng số `w` : mã hóa thêm một prompt rỗng được `z_empty` , rồi tính `z'` `= z_empty + w · (z − z_empty)` cho các token có trọng số — tức là kéo dài "độ lệch so với không nói gì" theo hệ số `w` ( `compel/embeddings_provider.py` , đoạn `z_delta_from_empty` ). Cú pháp này chỉ có tác dụng khi prompt được mã hóa qua compel; nếu đưa chuỗi thô vào diffusers thì dấu ngoặc và số trở thành token rác. Vì thế code chuyển `(tag:1.3)` → `(tag)1.3` (cú pháp compel) ở `image_generator.py:572-579` , và nếu thiếu compel thì xóa sạch cú pháp trọng số ( `_strip_weights` , dòng 581-588).

c) Negative prompt. SD dùng Classifier-Free Guidance (CFG). Ở mỗi bước khử nhiễu `t` , U-Net được chạy hai lần:

```
ε̂ = ε(x_t, t, c_neg) + s · ( ε(x_t, t, c_pos) − ε(x_t, t, c_neg) )
```

- `x_t` : latent đang nhiễu ở bước `t` . `ε(x_t, t, c_pos)` : dự đoán nhiễu khi có điều kiện prompt dương. `ε(x_t, t, c_neg)` : dự đoán nhiễu với prompt âm (trong CFG gốc, chỗ này là điều kiện rỗng ∅; negative prompt chỉ là thay ∅ bằng embedding của prompt âm). `s` : guidance scale (dự án mặc định `5.0` , `config.py:51` ).

Công thức cho thấy ảnh được đẩy về phía prompt dương và ra xa prompt âm. Nên negative prompt là nơi liệt kê thứ không muốn: `(worst quality, low quality:1.4), 3d, photorealistic, text, watermark...` (preset `resource/image_presets/thuy_mac.txt` ).

d) Tag thể loại/khung hình. `1boy` , `1girl` , `solo` , `no humans, scenery` , `wide shot` , `cowboy shot` , `upper body` — đây là từ vựng Danbooru mà model anime hiểu rất chắc.

e) Style drift. Nếu mỗi cảnh LLM tự viết `anime` , `realistic` , `cinematic lighting` ... thì mỗi frame một phong cách. Giải pháp: khóa style ở một nguồn duy nhất và lọc bỏ tag style trong phần LLM viết (mục 4.6).

### 2.8. Nhất quán nhân vật: "character bible"

Trong phim hoạt hình, "character sheet/bible" là tài liệu mô tả cố định ngoại hình mỗi nhân vật để mọi họa sĩ vẽ giống nhau. Với AI:

LLM không có trí nhớ giữa các lần gọi. Nếu mỗi cảnh LLM tự tưởng tượng Lạc Lan Tuyết thì cảnh 1 tóc đen, cảnh 5 tóc bạc. Giải pháp tầng văn bản: lưu một mô tả cố định ( `description` ) và bộ tag tiếng Anh cố định ( `keywords_en` ) cho mỗi nhân vật, và bắt LLM chép nguyên bộ tag vào prompt mỗi khi nhân vật xuất hiện. Giải pháp tầng hình ảnh (chương sau): IP-Adapter (ảnh tham chiếu), LoRA nhân vật. Chương này chỉ lo tầng văn bản và chuẩn bị dữ liệu ( `primary_character` ) cho tầng hình ảnh.

### 2.9. Quản lý ngữ cảnh xuyên cảnh (context management)

Hai loại "ngữ cảnh" cần phân biệt:

1. Ngữ cảnh của truyện (bền, lưu đĩa): nhân vật, thể loại, style → `ContextManager` lưu ở `storage/contexts/<story_slug>/` (hoặc `$MC_STORAGE_TASKS/contexts/<story_slug>/` nếu đặt biến môi trường, `context_manager.py:12-26` ). Dùng cho mọi chương. 2. Ngữ cảnh xuyên cảnh trong một chương (tạm thời, trong prompt): cảnh 2 phải biết cảnh 1 đang ở sân chùa. Cách dự án làm:

- Director's Note: một lần gọi LLM đọc cả chương, viết 1 câu chỉ đạo cho mỗi cảnh, nhấn mạnh tính liên tục ( `generate_storyboard_context` , `llm_prompter.py:221-266` ). Semantic metadata từ bước tách cảnh ( `location` , `action` , `time_of_day` ) được nối vào prompt từng cảnh. Nối chunk: khi chương dài phải chia chunk, 2 cảnh cuối của chunk trước được đưa vào đầu chunk sau ( `semantic_scene_splitter.py:164-168` , `199-202` ).

Đây là kỹ thuật "tóm tắt toàn cục + cửa sổ trượt" — thay vì nhồi cả chương vào mỗi lần gọi (tốn context, chậm), ta chắt lọc thông tin toàn cục thành một câu ngắn cho từng cảnh.

## 3. Vì sao chọn công nghệ này (so sánh phương án)

### 3.1. Tách cảnh

- **Phương án:** Chia đều theo thời gian (mỗi N giây một ảnh) · **Ưu:** Đơn giản, tất định · **Nhược:** Cắt ngang câu, ngang hành động · **Quyết định:** Chỉ là fallback cuối ( `_fallback_uniform_duration` )
- **Phương án:** Chia theo số từ/đoạn ( `md_parser` ) · **Ưu:** Không cần LLM, nhanh · **Nhược:** Không hiểu nghĩa; mặc định mục tiêu 5s/cảnh → rất nhiều cảnh · **Quyết định:** Fallback khi LLM hỏng
- **Phương án:** TextTiling / embedding + cosine · **Ưu:** Không cần sinh văn bản · **Nhược:** Không trả metadata; cần thêm model; không hiểu "đổi địa điểm" · **Quyết định:** Không dùng
- **Phương án:** LLM + JSON + validate · **Ưu:** Hiểu nghĩa kể chuyện; trả kèm location/characters/action/time; dùng lại LLM đã có · **Nhược:** Chậm hơn; có thể bịa → cần validate & fallback · **Quyết định:** Chọn

### 3.2. LLM nào, chạy ở đâu

Code gọi LLM qua thư viện `openai` với `base_url` cấu hình được ( `app/services/llm.py:61-71` ). Nhờ đó cùng một đoạn code chạy được với Ollama local ( `http://localhost:11434/v1` ), Gemini qua endpoint tương thích OpenAI, hay OpenAI thật — chỉ đổi 3 tham số `--llm-api-key/--llm-base-url/--llm-model` . Mặc định Ollama + `qwen2.5:3b-instruct` : chạy offline, không tốn phí, không gửi truyện ra ngoài; Qwen2.5 hỗ trợ tiếng Việt khá và có bản instruct tuân lệnh tốt. Model 3B (lượng tử hóa Q4) chiếm khoảng 2.8 GB VRAM — con số này lấy từ

bảng hồ sơ model của chatbot ( `orchestrator/chatbot.py:56` , đo ở `num_ctx` 8192), dùng làm tham khảo cho Bước 3 — vừa GPU 6 GB. Model "suy luận" (ví dụ qwen3 — thông điệp lỗi chỉ nêu tên này) bị khuyến cáo tránh vì chậm và dễ timeout — thông điệp lỗi ở `llm_prompter.py:319-324` nói rõ điều này; timeout HTTP là 60 giây ( `llm.py:70-71` ). Lưu ý: client `openai` mặc định tự thử lại tối đa 2 lần khi timeout, nên một lời gọi treo có thể chờ tới cỡ 3 × 60 s trước khi code nhận lỗi. VRAM: LLM và Stable Diffusion không cùng nằm trên GPU 6 GB được. Trước Trạm 2, code gọi `unload_local_llm()` gửi `keep_alive=0` tới `/api/generate` của Ollama để giải phóng model ( `llm.py:79-100` , gọi ở `orchestrator.py:369-370` ).

### 3.3. Dịch Việt → prompt Anh: vì sao để LLM làm luôn

- **Phương án:** Đưa thẳng tiếng Việt vào SD · **Nhược:** CLIP không hiểu, token rác
- **Phương án:** Google Translate / NLLB rồi đưa câu dịch vào SD · **Nhược:** Ra câu văn tiếng Anh dài, không phải tag; giữ cả chi tiết không vẽ được ("hắn đã mở tiệm ba năm"); tên riêng vẫn lọt vào
- **Phương án:** LLM vừa dịch vừa chuyển thể thành tag · **Nhược:** Chọn lọc thứ vẽ được, bỏ tên riêng, thêm tag khung hình, chép tag nhân vật — trong một lần gọi

### 3.4. Vì sao khóa style bằng code thay vì tin LLM

LLM nhỏ (3B) hay "thêm mắm muối": `masterpiece, anime, cinematic lighting` . Mỗi cảnh thêm khác nhau → style trôi. Code chọn hàm thuần, tất định ( `style_lock.py` ) để lọc và ghép — test được không cần GPU, kết quả lặp lại được.

## 4. Hiện thực trong code

### 4.1. Sơ đồ module

- **File:** `adapter_video_cli.py` · **Vai trò:** Điểm vào subprocess; nạp/tạo context; trích nhân vật; gọi batch · **Hàm chính:** `main()`
- **File:** `app/services/storytelling/batch_video_runner.py` · **Vai trò:** Chạy nhiều chương, Pass A/Pass B · **Hàm chính:** `run_batch` , `_process_single_item_pass_a`
- **File:** `app/services/storytelling/orchestrator.py` · **Vai trò:** 3 trạm · **Hàm chính:** `step1_generate_script` , `_convert_semantic_to_scenes`
- **File:** `app/services/storytelling/audio_utils.py` · **Vai trò:** Đọc thời lượng audio chính xác · **Hàm chính:** `get_audio_duration`
- **File:** `app/services/storytelling/semantic_scene_splitter.py` · **Vai trò:** Tách cảnh bằng LLM · **Hàm chính:** `split_scenes_semantic`
- **File:** `app/services/storytelling/md_parser.py` · **Vai trò:** Tách cảnh theo số từ (fallback) · **Hàm chính:** `parse_md_to_scenes`
- **File:** `app/services/storytelling/srt_mapper.py` · **Vai trò:** Gán thời gian cho cảnh; tự tạo SRT · **Hàm chính:** `map_semantic_scenes_to_srt` , `generate_srt_from_scenes` , `map_scenes_to_timeline`
- **File:** `app/services/storytelling/llm_prompter.py` · **Vai trò:** Director's Note + prompt từng cảnh · **Hàm chính:** `generate_prompts_batch` , `_process_scene_with_retry`
- **File:** `app/services/storytelling/style_lock.py` · **Vai trò:** Khóa style, trọng số hành động · **Hàm chính:** `build_locked_prompt` , `strip_style_drift`
- **File:** `app/services/storytelling/prompt_translator.py` · **Vai trò:** Dịch mô tả tự do → prompt (luồng tạo ảnh lẻ), cắt độ dài · **Hàm chính:** `translate_and_build_prompt` , `_clamp_prompt_words`
- **File:** `app/services/storytelling/character_extractor.py` · **Vai trò:** Trích nhân vật bằng LLM · **Hàm chính:** `process_chapters_and_extract_characters`
- **File:** `app/services/storytelling/character_bootstrap.py` · **Vai trò:** Tự sinh ảnh seed + dataset + train LoRA cho nhân vật chính · **Hàm chính:** `bootstrap_and_train` , `auto_train_leads`
- **File:** `app/services/storytelling/context_manager.py` · **Vai trò:** Lưu/đọc context truyện · **Hàm chính:** `ContextManager`
- **File:** `app/services/storytelling/models.py` · **Vai trò:** Dataclass · **Hàm chính:** `Scene` , `Character` , `StoryContext`
- **File:** `app/services/llm.py` · **Vai trò:** Tạo client LLM, unload Ollama · **Hàm chính:** `get_llm_client` , `unload_local_llm`
- **File:** `app/config.py` · **Vai trò:** Cấu hình mặc định + `config.toml` · **Hàm chính:** `Config` , `load_storytelling_config`

### 4.2. Khởi động: adapter, context, trích nhân vật

(1) Truyền LLM an toàn. `adapter_video_cli.py:81-86` dùng `config.set_app_override(...)` chứ không gán thẳng `config.app[...]` . Lý do (ghi trong `config.py:137-149` ): `load_storytelling_config()` gọi `load_config()` nhiều lần, mỗi lần `update()` giá trị rỗng từ `config.toml` đè lên → key LLM truyền qua CLI bị xóa giữa chừng. Override được giữ trong bộ nhớ và không bao giờ ghi ra đĩa ( `save_config` , dòng 167-181) — tránh lộ API key.

(2) Kiểm tra đầu vào trước khi tải model ( `adapter_video_cli.py:100-128` ): phân biệt 4 trường hợp (thư mục không tồn tại, rỗng, không có `.md` , có `.md` nhưng không ghép được audio) để báo đúng bước bị lỗi.

(3) Context truyện. `ContextManager(story_slug)` → nếu chưa có `context.json` thì `create_context` (dòng 151-158). Style preset được chép thật vào `style_prompt.txt` bằng `apply_style_preset` ( `context_manager.py:56-85` ); mặc định `thuy_mac` .

(4) Trích nhân vật (chỉ khi context chưa có nhân vật) — `adapter_video_cli.py:171-209` :

- Đọc 5 chương đầu ( `items[:5]` ).

Gọi `process_chapters_and_extract_characters(..., enable_web_search=True)` . Mỗi nhân vật thành `Character(name, slug=slugify(name), keywords_en, description, has_embedding=False)` rồi `save_context` .

4.3. Tách cảnh ngữ nghĩa — `semantic_scene_splitter.py`

Hàm tổng (dòng 26-50) là một pipeline 5 bước, bất kỳ bước nào trả `None` là caller chuyển sang `md_parser` :

```
def split_scenes_semantic(md_text, total_audio_duration,
                          min_scene_sec=8.0, max_scene_sec=15.0):
    paragraphs = _extract_paragraphs(md_text)
    if not paragraphs:
        return None
    raw_scenes = _call_llm_split(paragraphs, total_audio_duration)
    if raw_scenes is None:
        return None
    if not _validate_scene_coverage(raw_scenes, len(paragraphs)):
        return None
    scenes = _build_scenes(raw_scenes, paragraphs)
    total_words = sum(len(p.split()) for p in paragraphs)
    scenes = _enforce_duration_bounds(
        scenes, total_words, total_audio_duration, min_scene_sec, max_scene_sec)
    return scenes
```

4.3.1. `_extract_paragraphs` (dòng 53-108) — chuẩn hóa đơn vị

1. Tách theo dòng trống thành đoạn. 2. Bỏ dòng tiêu đề H1 ( `#` ) và dòng quảng cáo chứa `"mờiđọc"` , `"bộtruyện về"` , `"http"` (rác từ trang web cào). 3. Gộp đoạn < 5 từ vào đoạn trước (tránh đoạn kiểu "Hừ!" đứng một mình). 4. Chia nhỏ đoạn > 60 từ thành cụm câu ~35 từ bằng regex `(?<=[\.\!\?\…;])\s+` .

Bước 4 là một bản vá quan trọng (comment dòng 84-87): truyện convert thường cả chương chỉ 1–2 khối không xuống dòng; vì LLM chỉ được ghép đoạn liền kề, nếu chỉ có 2 đoạn thì cả video chỉ có 2 cảnh. Chia cụm ~35 từ tạo ra "đơn vị chia cảnh" đủ mịn.

`(?<=...)` là lookbehind: cắt tại khoảng trắng đứng sau dấu kết câu, nên dấu câu vẫn dính với câu trước.

4.3.2. Prompt tách cảnh (dòng 126-152)

Văn bản được đánh số `[0]...` , `[1]...` (dòng 120-123) — đây là mẹo quan trọng: bắt LLM trả chỉ số chứ không chép lại văn bản → đầu ra ngắn, và ta có thể kiểm chứng bằng code. Các yêu cầu trong system prompt:

Mục tiêu 10–14 cảnh/chương, ưu tiên gộp mạnh các đoạn cùng bối cảnh ("ít cảnh hơn = ít lần vẽ ảnh hơn"). Mỗi cảnh ước tính 30–50 giây (theo tỉ lệ số từ × tổng thời lượng). Ranh giới cảnh = đổi địa điểm / nhóm nhân vật / hành động chính / thời gian. Cảnh là dãy đoạn liên tiếp, không bỏ sót, không chồng lấn. Schema JSON: `{"scenes": [{"paragraphs": [...], "location", "characters", "time_of_day", "action", "summary"}]}` .

Tham số gọi: `temperature=0.3` , `max_tokens=4000` , `response_format={"type": "json_object"}` (dòng 172-181).

4.3.3. Chunking cho chương dài (dòng 154-204)

`CHUNK_WORD_LIMIT = 6000` từ. Nếu tổng ≤ 6000 → 1 lần gọi; nếu lớn hơn → `_split_into_chunks` gom đoạn đã đánh số cho tới khi gần chạm 6000 từ (dòng 207-223). Chỉ số đoạn giữ toàn cục (vì đánh số trước khi chia), nên kết quả các chunk nối thẳng được. Nối ngữ cảnh: 2 cảnh cuối của chunk trước (dạng JSON) được chèn vào đầu tin nhắn chunk sau với tiêu đề "Ngữ cảnh nối (2 cảnh cuối chunk trước)" (dòng 164-168, 199-202). Bất kỳ chunk nào lỗi mạng / parse hỏng / rỗng → trả `None` cho cả chương (không chấp nhận kết quả nửa vời). Response hỏng được ghi vào `storage/logs/llm_errors/semantic_split_<tag>_<timestamp>.txt` ( `_log_llm_error` , dòng 367-382) để debug sau. Hai điểm tinh tế khi đọc code: (a) mọi chunk dùng cùng một system prompt "10–14 cảnh cho cả chương", nên chương dài bị chia chunk có thể ra 10–14 cảnh mỗi chunk; (b) prompt không dặn LLM "đừng trả lại các đoạn trong phần ngữ cảnh nối"

- — nếu LLM lỡ đưa lại chỉ số của chunk trước thì chỉ số bị trùng và `_validate_scene_coverage` sẽ loại cả chương. Mặc định chương 2.000–4.000 từ thì không bị chunk (≤ 6000), nên hai điểm này chỉ ảnh hưởng chương rất dài.

4.3.4. Parse và validate (dòng 226-276)

`_parse_json_response` cắt từ `{` đầu tới `}` cuối — chịu được lời dẫn hoặc code fence. Sau đó `_validate_scene_coverage` kiểm tra 3 bất biến:

```
expected = list(range(n_paragraphs))
                                             # (1) phủ kín & không trùng
if sorted(all_indices) != expected:
    return False
for scene in raw_scenes:
    paras = scene["paragraphs"]
    if paras != list(range(min(paras), max(paras) + 1)):
                                                           # (2) liên tiếp
        return False
prev_max = -1
for scene in raw_scenes:
    paras = scene["paragraphs"]
    if min(paras) <= prev_max:
                                             # (3) đúng thứ tự, không chồng
        return False
    prev_max = max(paras)
```

Ý nghĩa: (1) mọi câu trong truyện đều xuất hiện đúng một lần — không mất lời thoại; (2) một cảnh không nhảy cóc; (3) cảnh theo thứ tự thời gian. Validate hỏng → trả `None` → fallback. (Đã chạy thử: đầu vào `[[0,2],[1,3]]` bị từ chối với log "paragraphs not contiguous: [0, 2]".)

4.3.5. `_enforce_duration_bounds` (dòng 299-364) — luật hậu kiểm

Thời lượng ước tính của cảnh: `est = (sốtừcảnh / tổng sốtừ) × tổng thời lượng audio` .

- Gộp cảnh quá ngắn: `est<min_sec` (8 s) và đã có cảnh trước → nối text, nối chỉ số, hợp nhân vật ( `set` ), nối action bằng `"; "` . Cắt cảnh quá dài: `est > max_sec × 1.8` (= 27 s) và có ≥ 2 đoạn → chia đôi theo số đoạn; nửa sau có action thêm `"` `(tiếp)"` . Chỉ chia một lần (không đệ quy).

- Quan sát trung thực cần biết khi bảo vệ: system prompt xin cảnh 30–50 s, nhưng luật hậu kiểm lại cắt cảnh > 27 s (với `max_scene_sec=15.0` mặc định). Hai con số này không khớp: nhiều cảnh LLM trả về sẽ bị chia đôi. Hệ quả thực tế là số cảnh cuối nhiều hơn 10–14 mà prompt nhắm tới. Nếu hội đồng hỏi, trả lời thẳng: "đây là tham số chưa đồng bộ, hướng sửa là nâng `max_scene_sec` hoặc truyền tham số từ cấu hình".

4.4. Chuyển sang `Scene` và gán thời gian

4.4.1. Đọc thời lượng audio — `audio_utils.get_audio_duration`

Thử lần lượt: module `wave` (cho `.wav` ) → `ffmpeg` đóng gói trong `imageio-ffmpeg` , parse `Duration: HH:MM:SS.xx` từ stderr (timeout 120 s) → `pydub` . Hỏng cả 3 → raise `RuntimeError` chứ không đoán. Comment dòng 4-6 kể lý do: bản cũ fallback âm thầm 60 s, khiến audio 10 phút bị chia 2 cảnh và video bị cắt còn 60 giây.

4.4.2. `_convert_semantic_to_scenes` ( `orchestrator.py:138-188` )

- Mỗi `SemanticScene` → `Scene` với thời gian = 0 (điền sau). `primary_character` : nhân vật đầu tiên trong danh sách của cảnh mà có dữ liệu identity (ảnh ref hoặc face embedding, `has_identity` ). So tên bằng `normalize` = NFKD + bỏ dấu + lowercase + bỏ khoảng trắng/gạch dưới — để "Lạc Lan Tuyết" khớp "lac_lan_tuyet". Gắn `_semantic_meta = {location, action, summary, time_of_day}` .

- Lưu ý: `characters_in_scene` và `primary_character` gán ở đây chỉ là giá trị tạm. Khi sinh prompt (mục 4.6.4), `_process_scene_with_retry` ghi đè cả hai bằng giá trị LLM trả về ( `llm_prompter.py:196-197` ). Giá trị ở đây là slug (vd `lac_lan_tuyet` ), còn giá trị LLM trả là tên hiển thị (vd `Lạc Lan Tuyết` ) — hệ quả xem mục 6.6.

4.4.3. Map thời gian — `srt_mapper.map_semantic_scenes_to_srt`

Chính sách "M1" ( `orchestrator.py:266-297` , `adapter_video_cli.py:222` ): không dùng Whisper mặc định ( `use_whisper=False` ) vì Whisper medium tốn ~2–3 GB VRAM và ~60 s/chương.

- Có SRT → khớp văn bản bằng `difflib` (mục 2.3): 1. Chuẩn hóa hai phía: NFKD bỏ dấu, lowercase, bỏ dấu câu. 2. Trải SRT thành chuỗi từ, ghi `word_to_block` (từ thứ k thuộc block nào). 3. Với mỗi cảnh: cửa sổ tìm chỉ về phía trước, từ `cursor` tới `cursor + len(scene_words) + 2000` từ (comment trong code ghi "±2000" nhưng code thực tế chỉ tiến); `ratio>=0.5` → lấy block của từ khớp đầu và cuối làm `start/end` ; đẩy `cursor` tiến lên (tuyến tính, không quay lui). 4. `ratio<0.5` → gán theo tỉ lệ số từ ( `_assign_proportional_timing` ).

- Quan sát quan trọng (đã chạy thử): `ratio` được tính giữa cả văn bản cảnh và cả cửa sổ SRT (dài hơn cảnh tới ~2000 từ). Theo cận trên ở mục 2.3, khi cửa sổ dài hơn 3 lần cảnh thì `ratio<0.5` bất kể khớp tốt đến đâu. Chạy thử với 10 cảnh × 150 từ, SRT khớp nguyên văn: cảnh 0 được `ratio = 0.183` , cảnh 5 được `0.326` , chỉ cảnh cuối (cửa sổ ngắn lại) mới đạt `1.0` . Nghĩa là trên thực tế, đa số cảnh vẫn rơi về timing tỉ lệ số từ kể cả khi có SRT. Cách sửa đúng là dùng `matcher.find_longest_match` / `get_matching_blocks` để đo độ phủ của chuỗi cảnh ( `M / len(a)` ) thay cho `ratio()` . SRT chỉ được dùng khi thư mục đầu vào có file `.srt` cùng tên chương ( `scan_batch_dir` , `batch_video_runner.py:101` ); luồng mặc định tắt Whisper và thường không có file này, nên lỗi này ít ảnh hưởng luồng mặc định. - Không có SRT → `_fallback_proportional_duration` (dòng 197-216): `duration_i = T × wᵢ/Σw` , cảnh cuối ép kết thúc đúng `T` . - `_fix_monotonic` (dòng 335-349): đảm bảo `start` tăng dần, không chồng, cảnh cuối kết thúc bằng tổng thời lượng.

Vì sao chia theo tỉ lệ số từ là hợp lý? Audio do TTS đọc nguyên văn với tốc độ gần như đều, nên thời gian đọc ≈ tỉ lệ thuận với số từ. Đây là giả định mạnh nhưng đúng với TTS (khác với người đọc có ngừng nghỉ tùy hứng).

- Ghi chú code: `map_semantic_scenes_to_srt` được định nghĩa hai lần trong `srt_mapper.py` (dòng 219 và 356). Python dùng định nghĩa sau cùng (dòng 356, gọi `_assign_proportional_timing` ). Hai bản gần như giống hệt — là trùng lặp còn sót, không gây lỗi.

4.4.4. Tự tạo phụ đề từ kịch bản — `generate_srt_from_scenes` (dòng 487-540)

Khi không có SRT: tách câu trong từng cảnh; câu > 22 từ tách tiếp theo dấu phẩy; mỗi câu nhận khoảng thời gian tỉ lệ số từ bên trong cảnh. Lưu `generated_from_script.srt` trong `task_dir` . Lý do chia theo câu: một block phụ đề 15–30 s thì không ai đọc kịp.

4.4.5. Nhánh fallback — `md_parser.parse_md_to_scenes`

Dùng khi semantic split trả `None` . Tách câu khi đoạn > 20 từ; gom câu tới khi thời lượng ước tính ≥ `scene_target_duration =` `5.0` s (dòng 8); nếu file < 5 đoạn thì tự nâng mục tiêu. Sau đó `map_scenes_to_timeline` nhóm block SRT theo khoảng lặng > 0.5 s ( `silence_gap_threshold` ) và gán tuyến tính cho cảnh; không có SRT + không Whisper → timing tỉ lệ số từ và ghi file `.srt` cạnh audio.

4.5. Trích xuất nhân vật — `character_extractor.py`

Luồng `process_chapters_and_extract_characters` (dòng 138-195):

- 1. Với từng chương (tối đa 5 do adapter truyền): cắt còn 10.000 ký tự nếu dài hơn (dòng 157-158) — bảo vệ context window của LLM local. 2. `extract_characters_from_text` : system prompt tiếng Việt yêu cầu 5–10 nhân vật quan trọng, mỗi nhân vật có `name` , `text_description` (bám nguyên tác: tuổi, vóc dáng, giới tính, địa vị), `search_query` . `temperature=0.3` , `max_tokens=2500` (mặc định của `call_llm` , dòng 8). 3. Khử trùng lặp theo tên chính xác ( `seen_names` ). 4. Nếu `enable_web_search=True` (adapter luôn truyền `True` ): `refine_character_with_web_search` yêu cầu LLM trả `description` (Việt), `keywords_en` (tag SD: `1boy, handsome, athletic build, short black hair, black robe` ) và `image_urls` . Code còn quét thêm URL ảnh dạng Markdown `![..](url)` và URL trần đuôi `.png/.jpg/.jpeg/.webp` bằng regex (dòng 124-135). 5. Nếu tắt web search: `keywords_en = "1boy/1girl, detailed face"` (placeholder).

Hai điểm phải nói thật với hội đồng:

- Hàm này gọi LLM không kèm `response_format=json_object` (dòng 16-21) → chỉ dựa vào parse phòng thủ. "Web search" thực chất chỉ là lời yêu cầu trong prompt; code không gắn tool tìm kiếm nào. Với Ollama local, model không truy cập Internet, nên `description/keywords_en` đến từ kiến thức sẵn có của model và mô tả trong truyện; `image_urls` có thể là URL model bịa ra. Tính năng tìm kiếm thật chỉ có nếu endpoint phía sau tự hỗ trợ grounding.

Character bible được lưu thế nào — `Character` ( `models.py:54-67` ): `name, slug, description, keywords_en, has_embedding,` `lora_status, lora_trained_at, instance_prompt, auto_collect, ref_source` . File `storage/contexts/<slug>/context.json` ; ảnh ref ở `characters/<slug>/ref.png` , dataset ở `characters/<slug>/dataset/` (trần 40 ảnh, xóa `auto_*` cũ trước, không bao giờ tự xóa `approved_*` — `context_manager.py:317-354` ).

Character bootstrap ( `character_bootstrap.py` ) — cầu nối sang chương sinh ảnh, giải bài toán "con gà – quả trứng" (muốn nhân vật đồng nhất cần LoRA; train LoRA cần 10–20 ảnh đồng nhất):

- 1. Chỉ tự sinh khi dataset còn mỏng (< 8 ảnh, `bootstrap_and_train` ). Nếu chưa có ref: sinh ảnh seed chân dung từ `keywords_en` + style (512×640, không IP-Adapter) → lưu làm ref ( `generate_seed_ref` ). 2. Từ ref, dùng IP-Adapter ( `scale 0.7` ) sinh biến thể theo 14 kiểu góc/biểu cảm trong `_VARIATIONS` , mục tiêu `_TARGET_IMAGES = 14` , tối đa `_MAX_ATTEMPTS = 26` lần. 3. Đủ ≥ 5 ảnh → train LoRA; idempotent nhờ `has_trained_lora` (kiểm cả checkpoint khớp). 4. Ai gọi? Chỉ `StudioPipeline` (chế độ `render_mode="studio"` ) gọi `auto_train_leads` ( `studio/studio_pipeline.py:475-` `512` ). Nhân vật chính được chọn là `max_leads=2` nhân vật xuất hiện ở nhiều cảnh nhất ( `_detect_lead_slugs` , đếm bằng `Counter` ). Ở chế độ mặc định `classic` thì bước auto-train này không chạy. Cấu hình `studio_auto_train_*` ở `config.py:111-113` (700 bước).

Liên hệ với chương này: `keywords_en` do LLM trích ra ở bước 4 chính là đầu vào của ảnh seed. Tag sai (vd nam chính bị gán `1girl` ) sẽ lan sang toàn bộ ảnh.

4.6. Sinh prompt cho từng cảnh — `llm_prompter.py`

4.6.1. `generate_prompts_batch` (dòng 268-326)

```
system_prompt = _build_system_prompt(context)
director_notes = generate_storyboard_context(scenes, context)
for i in range(0, total_scenes, batch_size):
                                                      # batch_size = 8
    batch = scenes[i:i + batch_size]
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(_process_scene_with_retry, scene,
                   system_prompt, context, 1,
                   director_notes.get(str(scene.scene_id), ""))
                   for scene in batch]
        for future in as_completed(futures):
            if not future.result():
                failed_scenes += 1
```

(đã rút gọn nhẹ phần log và try/except). Điểm chính:

- Một lời gọi Director cho cả chương, sau đó mỗi cảnh một lời gọi. Chạy song song 4 luồng trong lô 8 cảnh. Vì lời gọi LLM là I/O (chờ HTTP), thread vẫn tăng tốc dù Python có GIL; với Ollama, mức song song thật phụ thuộc cấu hình server. Đếm cảnh thất bại. Tất cả đều thất bại → raise `AllPromptsFailedError` (dòng 316-324). Comment dòng 297-299 kể lỗi cũ: kết quả bị bỏ qua ( `pass` ), LLM chết mà pipeline vẫn báo thành công rồi đốt hàng chục phút GPU ra ảnh vô nghĩa.

4.6.2. Director's Note — `generate_storyboard_context` (dòng 221-266)

Ghép `Scene {id}: {text_vi}` cho toàn chương; system prompt đóng vai "Storyboard Director", yêu cầu 1 câu chỉ đạo thị giác/cảnh, tập trung "ai trong khung, đang làm gì, ở đâu", và liên tục giữa các cảnh ("nếu cảnh 1 ở sân thì cảnh 2 có lẽ vẫn ở đó"). Đầu ra: JSON `{"0": "...", "1": "..."}` ; `max_tokens=3000` . Lỗi → trả `{}` và các cảnh vẫn sinh prompt được (chỉ thiếu ghi chú).

4.6.3. System prompt sinh prompt — `_build_system_prompt` (dòng 74-134)

Nội dung chính (tiếng Anh, vì model instruct tuân lệnh tiếng Anh tốt và đầu ra cũng là tiếng Anh):

Nhấn "You are a TEXT-ONLY AI. DO NOT generate images." — chống model đa năng trả lời kiểu "tôi không vẽ được". Schema: `image_prompt` , `action` , `characters` , `primary_character` , `shot_type` ( `close|medium|wide` ), `background_prompt` , `layout[]` (cho chế độ Studio). Luật thể loại `GENRE_SPECIFIC_RULES` (dòng 30-56): `tien_hiep` (cấm yếu tố hiện đại; núi mây, Hanfu, phi kiếm), `ngon_tinh` (đô thị, lãng mạn), `khoa_huyen` (sci-fi), `default` . Tỉ lệ cỡ cảnh gợi ý: ~30% close, 40% medium, 30% wide. 9 luật "CRITICAL SD PROMPT RULES", đáng nhớ nhất: 1. Chỉ tag tiếng Anh phân cách dấu phẩy, không câu văn. 2. Môi trường trước; cấm `simple background` . 3. Cấm viết tag style (liệt kê cụ thể) — style đã khóa và được in ra trong prompt để LLM biết. 4. Không đưa tên nhân vật vào `image_prompt` (CLIP không đọc được tên Việt); chép `keywords` của nhân vật; thêm `solo` , `1boy 1girl` ...; cảnh không người → `no humans, scenery` ; nhân vật nam không được nữ tính hóa. 5. Một tag camera ở cuối. 6. Trường `action` : 2–4 động từ vật lý cụ thể ("swinging a sword downward"), cấm "standing", "feeling sad"; không tự thêm trọng số (hệ thống tự thêm). 7. `image_prompt` dưới 35 từ — model ảnh yếu theo prompt ngắn tốt hơn. Danh sách nhân vật được gửi dạng JSON `{name, description, keywords}` , với `keywords` đã lọc các tag chân dung ( `upper body` , `portrait` , `close up` , `looking at viewer` ... — dòng 79-80) để tag nhân vật không kéo mọi cảnh thành ảnh chân dung.

4.6.4. Xử lý từng cảnh — `_process_scene_with_retry` (dòng 136-219)

User prompt = `Scene text:<text_vi>` + `Director's Note` + `Location/Action/Time of day` từ `_semantic_meta` . Vòng lặp `for` `attempt in range(retries + 1)` với `retries=1` → tối đa 2 lần gọi:

1. `_call_llm` ( `temperature=0.4` , `max_tokens=800` , JSON mode). Rỗng → thử lại. 2. Cắt `{...}` , `json.loads` ; nếu LLM trả list thì lấy phần tử đầu; không phải dict → thử lại. 3. Có `image_prompt` → `build_locked_prompt(locked_style, raw_prompt, action=raw_action, action_weight=1.35)` . 4. Gán `characters_in_scene` , `primary_character` , `shot_type` (giá trị lạ → `"wide"` ), `_llm_background_prompt` , `_llm_layout` , `_llm_action` . 5. Trần 75 từ bằng `PromptTranslator._clamp_prompt_words(..., max_words=75)` — cắt ở ranh giới tag, không cắt giữa tag. Chú ý: hàm đếm từ (tách theo khoảng trắng), không đếm token CLIP; 75 từ thường thành hơn 77 token (dấu phẩy, ngoặc, trọng số đều là token). Việc này không gây mất prompt vì compel nối nhiều khối 77 token ( `truncate_long_prompts=False` ); trần 75 từ chỉ để prompt không bị loãng. Vì style đứng đầu, nếu bị cắt thì phần bị mất là nội dung ở cuối.

Hết lượt vẫn hỏng → fallback: `build_locked_prompt(locked_style, "scenery, wide landscape, no humans")` và trả `False` (để được đếm là thất bại).

`action_weight` đọc từ `studio_action_weight = 1.35` ( `config.py:81` ; comment: 1.25–1.45 hợp lý, cao hơn dễ méo giải phẫu).

4.6.5. Khóa style — `style_lock.build_locked_prompt`

```
def build_locked_prompt(style_positive, content_prompt, action="",
                        action_weight=1.35, extra=()):
    style = ", ".join(_split_tags(style_positive))
    content = strip_style_drift(content_prompt)
    content = dedupe_against(content, style)
    parts = [style]
    if action.strip():
        weighted = weight_action(strip_style_drift(action), action_weight)
        parts.append(weighted)
        content = dedupe_against(content, strip_style_drift(action))
    parts.append(content)
    parts.extend(str(x).strip() for x in extra if str(x).strip())
    return ", ".join(p for p in parts if p)
```

`strip_style_drift` : bỏ mọi tag nằm trong `_STYLE_DRIFT_TERMS` (59 tag chất lượng/chất liệu/ánh sáng như `masterpiece` , `anime` , `realistic` , `cinematic lighting` , `depth of field` ...) và tag chứa tên model ( `anything v5` , `dreamshaper` ...). So

khớp sau khi `_normalize` bỏ cú pháp trọng số. `dedupe_against` : bỏ tag trùng với style để khỏi tốn token. `weight_action` : bọc mỗi tag hành động thành `(tag:1.35)` , tag đã có trọng số thì giữ. Style lấy từ `StoryContext.get_positive_prompt()` = phần trước `---` của `style_prompt.txt` + `learned_corrections.prompt_additions` ( `models.py:99-109` ). Negative = phần sau `---` + `prompt_removals` (dòng 111- 122).

Phía sinh ảnh, `_ensure_quality_tags` ( `image_generator.py:557-570` ) chỉ thêm `masterpiece, best quality, highres` khi 120 ký tự đầu chưa có — vì style preset đã có `(masterpiece, best quality:1.2)` nên thực tế không bị thêm lặp.

4.7. `prompt_translator.py` — dịch mô tả tự do (luồng tạo ảnh lẻ)

Lớp `PromptTranslator` phục vụ luồng người dùng gõ mô tả tiếng Việt để tạo một ảnh (không phải luồng batch video), nhưng chứa các nguyên lý dịch cần trình bày:

`match_characters_in_text` : khớp tên nhân vật trong mô tả bằng `normalize` (bỏ dấu) — nhân vật đầu tiên khớp là `primary_char_slug` . `load_style_preset` : đọc `resource/image_presets/<tên>.txt` , tách positive/negative bằng `---` . `adapt_style_to_model` (dòng 185-209): nếu checkpoint không phải anything-v5 thì bỏ tag `Anything V5` ; nếu checkpoint là realistic/dreamshaper thì bỏ `realistic, photorealistic, photograph, real-life` khỏi negative (tránh negative đánh nhau với chính model). `TRANSLATE_SYSTEM_PROMPT` (dòng 15-40): cấu trúc `[Style], [(Main Action:1.3)], [Character keywords], [Background],` `[Camera&Lighting]` ; hành động và ngoại hình phải nằm trong 40 từ đầu; positive < 60 từ, negative < 50 từ; không đưa tên nhân vật vào prompt; nhấn tag nam ( `1boy, male focus, mature man` ) vì model anime thiên về vẽ nữ. Fallback khi LLM hỏng: `"{style}, {mô tảgốc}"` (dòng 270-272) — lưu ý mô tả gốc là tiếng Việt, nên fallback này chất lượng thấp. `_clamp_prompt_words` (dòng 281-297): hàm tĩnh được chính `llm_prompter` tái dùng với trần 75 từ. `generate_custom_preset` : LLM sinh preset style từ mô tả, lưu file `.txt` với tên đã lọc ký tự an toàn `[^a-zA-Z0-9_-]` .

## 5. Sơ đồ luồng

### 5.1. Luồng tổng Trạm 1

### 5.2. Tách cảnh ngữ nghĩa và các chốt an toàn

### 5.3. Sinh prompt một cảnh

## 6. Ví dụ minh họa từ đầu đến cuối (đã chạy thử bằng code thật)

Ví dụ dưới được chạy bằng chính các hàm `_extract_paragraphs` , `_validate_scene_coverage` , `_build_scenes` , `_enforce_duration_bounds` , `build_locked_prompt` , `_clamp_prompt_words` trong repo (Python của `AIVoice/.venv` ). Phần phản hồi LLM là giả lập để minh họa (không gọi LLM thật).

### 6.1. Đầu vào

```
# Chương 1: Tiệm nhỏ
```

```
Dịch Phong ngồi sau quầy gỗ của tiệm tạp hóa nhỏ, ngáp dài nhìn ra con phố vắng. Nắng chiều rọi qua ô cửa, bụi bay lơ lửng.
```

```
Hắn đã mở tiệm ba năm, chưa từng có vị khách nào mua quá một bình rượu.
```

```
Bỗng cửa tiệm bị đẩy mạnh. Một thiếu nữ áo trắng bước vào, trường kiếm đeo sau lưng, ánh mắt lạnh như băng. Nàng là Lạc Lan Tuyết, đệ tử
chân truyền của Thiên Kiếm Tông.
```

```
Nàng rút kiếm, mũi kiếm chỉ thẳng vào ngực Dịch Phong. Bên ngoài, trời bắt đầu đổ mưa.
```

Giả sử audio dài 40 giây.

6.2. `_extract_paragraphs` (kết quả thật)

Dòng H1 bị bỏ. Không đoạn nào < 5 từ hay > 60 từ nên giữ nguyên. Log: "4 đoạn gốc → 4 đơn vị chia cảnh (99 từ)".

- **Chỉ số:** [0] · **Số từ:** 28 · **Nội dung (rút gọn):** Dịch Phong ngồi sau quầy gỗ... bụi bay lơ lửng.
- **Chỉ số:** [1] · **Số từ:** 17 · **Nội dung (rút gọn):** Hắn đã mở tiệm ba năm...
- **Chỉ số:** [2] · **Số từ:** 36 · **Nội dung (rút gọn):** Bỗng cửa tiệm bị đẩy mạnh... Thiên Kiếm Tông.
- **Chỉ số:** [3] · **Số từ:** 18 · **Nội dung (rút gọn):** Nàng rút kiếm... trời bắt đầu đổ mưa.

### 6.3. LLM tách cảnh (giả lập) và validate

```
{"scenes": [
  {"paragraphs": [0, 1], "location": "tiệm tạp hóa", "characters": ["Dịch Phong"],
   "time_of_day": "dusk", "action": "ngồi ngáp sau quầy", "summary": "Dịch Phong buồn chán trong tiệm"},
  {"paragraphs": [2, 3], "location": "tiệm tạp hóa", "characters": ["Dịch Phong", "Lạc Lan Tuyết"],
   "time_of_day": "dusk", "action": "rút kiếm chỉ vào Dịch Phong", "summary": "Lạc Lan Tuyết xông vào"}
]}
```

`_validate_scene_coverage` → `True` . (Nếu LLM trả `[[0,2],[1,3]]` → `False` , fallback `md_parser` .)

### 6.4. Luật thời lượng (kết quả thật)

`est = sốtừ/ 99 × 40` :

- **Cảnh:** 0 · **Đoạn:** [0, 1] · **Số từ:** 45 · **Ước tính:** 18.18 s · **Hành động của luật:** 8 ≤ 18.18 ≤ 27 → giữ
- **Cảnh:** 1 · **Đoạn:** [2, 3] · **Số từ:** 54 · **Ước tính:** 21.82 s · **Hành động của luật:** giữ

Để thấy luật hoạt động, đổi audio thành 120 s: cảnh 0 ≈ 54.5 s > 27 → chia thành [0] (≈ 33.9 s) và [1] (≈ 20.6 s); cảnh 1 ≈ 65.5 s → [2] (≈ 43.6 s) và [3] (≈ 21.8 s). Cảnh [2] vẫn > 27 s nhưng không bị chia tiếp vì luật chỉ chạy một lượt. Ngược lại, nếu audio chỉ 10 s: cảnh 1 ≈ 5.45 s < 8 → bị gộp vào cảnh 0.

### 6.5. Map thời gian (không có SRT)

`_fallback_proportional_duration` với T = 40: cảnh 0 `0.00→18.18` , cảnh 1 `18.18→40.00` (cảnh cuối ép đúng 40). Sau đó `generate_srt_from_scenes` tách câu, ví dụ câu "Bỗng cửa tiệm bị đẩy mạnh." (6 từ) trong cảnh 1 (54 từ, 21.82 s) nhận ≈ 21.82 × 6/54 ≈ 2.4 s.

### 6.6. Sinh prompt cảnh 1

Giả sử context có nhân vật:

- Dịch Phong: `keywords_en = "1boy, male focus, plain grey robe, short black hair"` Lạc Lan Tuyết: `keywords_en = "1girl, white hanfu, long black hair, cold eyes"`

User prompt gửi LLM (dạng):

```
Scene text:
Bỗng cửa tiệm bị đẩy mạnh. Một thiếu nữ áo trắng bước vào, ...
```

```
Director's Note (Visual Context):
Lạc Lan Tuyết bursts into the shop and points her sword at Dịch Phong.
Location: tiệm tạp hóa
Action: rút kiếm chỉ vào Dịch Phong
Time of day: dusk
```

LLM (giả lập) trả về — chú ý nó phạm luật khi thêm `anime, masterpiece, cinematic lighting` :

```
{"image_prompt": "1girl, white hanfu, long black hair, cold eyes, sword, 1boy, male focus, plain grey robe, wooden counter, small grocery
shop interior, rain outside window, anime, masterpiece, cinematic lighting, medium shot",
 "action": "drawing sword, pointing sword at man's chest",
 "characters": ["Lạc Lan Tuyết", "Dịch Phong"],
 "primary_character": "Lạc Lan Tuyết",
 "shot_type": "medium"}
```

`build_locked_prompt` với style `thuy_mac` cho kết quả thật:

```
thuymac ink wash style, (masterpiece, best quality:1.2), ink wash painting, monochrome grayscale,
heavy black ink, dry brush strokes, bold silhouette, high contrast, misty atmosphere,
rice paper texture, generous negative space, (drawing sword:1.35),
(pointing sword at man's chest:1.35), 1girl, white hanfu, long black hair, cold eyes, sword,
1boy, male focus, plain grey robe, wooden counter, small grocery shop interior,
rain outside window, medium shot
```

Quan sát:

`anime` , `masterpiece` , `cinematic lighting` do LLM tự thêm đã bị lọc bởi `strip_style_drift` . Hành động lên ngay sau style với trọng số 1.35. Tổng 63 từ < 75 → `_clamp_prompt_words` không cắt. Tên "Lạc Lan Tuyết" không có trong prompt; `primary_character = "Lạc Lan Tuyết"` là kênh riêng để Trạm 2 biết nhân vật nào cần ảnh ref/LoRA. Quan sát khi đọc code Trạm 2 (chưa kiểm chứng bằng chạy thật): `_resolve_primary_character` ( `orchestrator.py:68-` `86` ) tìm nhân vật bằng cách (1) dò tên/slug trong `image_prompt` — nhưng luật 4a đã cấm tên trong prompt; (2) fallback `ctx_mgr.get_character(scene.primary_character)` — hàm này so khớp slug ( `context_manager.py:265-271` ), trong khi LLM trả tên hiển thị "Lạc Lan Tuyết" (slug là `lac_lan_tuyet` ). Nếu LLM không trả đúng slug thì cả hai nhánh đều trượt, và cảnh sẽ sinh không có IP-Adapter/LoRA của nhân vật. Hàm `_resolve_scene_character_any` (dòng 88-108) thì có so khớp theo tên đã chuẩn hóa, nhưng chỉ dùng cho bootstrap ref. Nếu hội đồng hỏi về độ nhất quán nhân vật, đây là điểm em nên nhận là hạn chế và hướng sửa là chuẩn hóa tên → slug ngay sau khi nhận JSON từ LLM. `shot_type = "medium"` → Trạm 2 sinh khung 704×528 ( `orchestrator.py:457-462` ). Negative prompt = phần sau `---` của `thuy_mac.txt` : `(worst quality, low quality:1.4), 3d, photorealistic,` `photograph, saturated colors,... text, watermark, signature,...` .

## 7. Hạn chế & hướng phát triển

- **#:** 1 · **Hạn chế (có căn cứ code):** Prompt tách cảnh xin 30–50 s nhưng luật hậu kiểm chia cảnh > 27 s ( `max_scene_sec=15.0 ×` `1.8` ) · **Hệ quả:** Số cảnh nhiều hơn mục tiêu, tốn thời gian sinh ảnh · **Hướng phát triển:** Đồng bộ tham số, đưa vào `config.toml`
- **#:** 2 · **Hạn chế (có căn cứ code):** Chia cảnh quá dài chỉ một lượt, chia đôi theo số đoạn (không theo số từ) · **Hệ quả:** Còn cảnh dài; hai nửa có thể lệch · **Hướng phát triển:** Chia đệ quy/cân bằng theo số từ
- **#:** 3 · **Hạn chế (có căn cứ code):** Một chunk hỏng → bỏ cả kết quả semantic · **Hệ quả:** Chương dài dễ rơi về `md_parser` · **Hướng phát triển:** Retry riêng từng chunk; chỉ fallback đoạn hỏng
- **#:** 4 · **Hạn chế (có căn cứ code):** Semantic split không retry (khác sinh prompt có retry) · **Hệ quả:** Một lần JSON hỏng là mất · **Hướng phát triển:** Thêm retry có phản hồi lỗi validate cho LLM
- **#:** 5 · **Hạn chế (có căn cứ code):** Trích nhân vật không dùng JSON mode; "web search" chỉ là lời nhắc · **Hệ quả:** Có thể parse hỏng; `image_urls` có thể bịa · **Hướng phát triển:** Bật `response_format` ; tích hợp tool search thật hoặc bỏ trường URL
- **#:** 6 · **Hạn chế (có căn cứ code):** Khử trùng nhân vật theo tên chính xác · **Hệ quả:** "Tuyết nhi" và "Lạc Lan Tuyết" thành 2 nhân vật · **Hướng phát triển:** Chuẩn hóa alias bằng LLM hoặc embedding tên
- **#:** 7 · **Hạn chế (có căn cứ code):** Chỉ đọc 5 chương đầu, cắt 10.000 ký tự · **Hệ quả:** Nhân vật xuất hiện muộn không có trong bible · **Hướng phát triển:** Cập nhật bible tăng dần theo chương
- **#:** 8 · **Hạn chế (có căn cứ code):** Timing theo tỉ lệ số từ giả định tốc độ đọc đều · **Hệ quả:** Lệch vài giây ở đoạn có ngắt nghỉ dài · **Hướng phát triển:** Lấy timestamp trực tiếp từ TTS; hoặc forced alignment
- **#:** 9 · **Hạn chế (có căn cứ code):** Director's Note gửi cả chương một lần · **Hệ quả:** Chương rất dài có thể vượt context LLM nhỏ · **Hướng phát triển:** Chunk giống bước tách cảnh
- **#:** 10 · **Hạn chế (có căn cứ code):** Fallback prompt là cảnh phong cảnh chung · **Hệ quả:** Cảnh hỏng không liên quan nội dung · **Hướng phát triển:** Fallback dùng `_semantic_meta.location` + tag nhân vật
- **#:** 11 · **Hạn chế (có căn cứ code):** `map_semantic_scenes_to_srt` định nghĩa 2 lần · **Hệ quả:** Trùng lặp mã · **Hướng phát triển:** Xóa bản thừa
- **#:** 12 · **Hạn chế (có căn cứ code):** Không có sentence embedding · **Hệ quả:** Không có tín hiệu ngữ nghĩa độc lập để đối chiếu LLM · **Hướng phát triển:** Dùng embedding + cosine như bộ kiểm tra chéo ranh giới cảnh
- **#:** 13 · **Hạn chế (có căn cứ code):** Bước 3 gọi Ollama qua `/v1` , không đặt `num_ctx` · **Hệ quả:** Chunk 6000 từ có thể vượt context mặc định → LLM thấy thiếu văn bản → validate hỏng · **Hướng phát triển:** Gọi `/api/chat` kèm `options.num_ctx` như chatbot, hoặc giảm `CHUNK_WORD_LIMIT`
- **#:** 14 · **Hạn chế (có căn cứ code):** So khớp SRT dùng `ratio()` trên cả cửa sổ ~2000 từ · **Hệ quả:** `ratio` gần như luôn < 0.5 → đa số cảnh vẫn chia theo tỉ lệ từ · **Hướng phát triển:** Đo độ phủ `M / len(scene)` thay cho `ratio()`
- **#:** 15 · **Hạn chế (có căn cứ code):** `primary_character` LLM trả tên hiển thị, Trạm 2 tra theo slug · **Hệ quả:** Có thể mất IP-Adapter/LoRA ở luồng classic (quan sát từ code) · **Hướng phát triển:** Chuẩn hóa tên → slug ngay sau khi parse JSON

## Câu hỏi hội đồng có thể hỏi

### 1. Em tách cảnh bằng gì? Có dùng embedding/cosine similarity không?

Dạ, em tách cảnh bằng LLM ( `semantic_scene_splitter.py` ), không dùng embedding. Văn bản được chia thành các đơn vị đánh số `[0], [1]...` , LLM trả JSON danh sách chỉ số đoạn cho từng cảnh kèm location, characters, time_of_day, action. Em chọn LLM vì nó hiểu ranh giới kể chuyện (đổi địa điểm, nhân vật mới xuất hiện) và trả luôn metadata cho bước sinh prompt, trong khi cosine giữa embedding chỉ đo độ giống chủ đề. Ở bước này, độ đo similarity duy nhất em dùng là `difflib.SequenceMatcher` để khớp văn bản cảnh với phụ đề SRT (cosine chỉ dùng ở chương sinh ảnh, để so embedding khuôn mặt).

### 2. Nếu LLM trả JSON sai hoặc bịa chỉ số đoạn thì sao?

Có 4 lớp bảo vệ: (1) JSON mode ( `response_format=json_object` ) đảm bảo cú pháp; (2) parse phòng thủ cắt `{...}` ; (3) `_validate_scene_coverage` kiểm tra ba bất biến: phủ kín 0..N-1 không trùng, mỗi cảnh liên tiếp, các cảnh không chồng và đúng thứ tự; (4) fallback: sai một điều là trả `None` và pipeline chuyển sang `md_parser` chia theo số từ. Response hỏng được ghi vào `storage/logs/llm_errors/` . Em cũng nói rõ: tách cảnh không có retry ở tầng ứng dụng, chỉ có retry mạng mặc định của client `openai` .

### 3. Thời lượng mỗi cảnh được tính thế nào?

Có SRT thì khớp văn bản cảnh với SRT bằng `difflib` (ratio ≥ 0.5) để lấy start/end của block; em cũng biết hạn chế là `ratio` tính trên cả cửa sổ ~2000 từ nên thường dưới 0.5 và cảnh rơi về chia tỉ lệ. Không có SRT (mặc định vì tắt Whisper) thì chia theo tỉ lệ số từ: `duration_i = T × wᵢ/Σw` , cảnh cuối ép kết thúc đúng tổng thời lượng. Hợp lý vì audio do TTS đọc nguyên văn với tốc độ gần đều. Tổng thời lượng T đọc chính xác bằng `wave` /ffmpeg/pydub; đọc không được thì báo lỗi luôn chứ không đoán.

### 4. Vì sao không dùng Whisper để lấy timing?

Whisper medium tốn khoảng 2–3 GB VRAM và ~60 giây mỗi chương (comment `orchestrator.py:275-277` ). Vì audio đọc nguyên văn kịch bản nên em đã biết sẵn lời, chỉ cần phân bổ thời gian; adapter đặt cứng `use_whisper=False` . Whisper vẫn còn làm tùy chọn.

### 5. Vì sao phải dịch sang tiếng Anh? Sao không dùng Google Translate?

Stable Diffusion mã hóa prompt bằng CLIP text encoder, được huấn luyện trên cặp ảnh–chú thích chủ yếu tiếng Anh, tokenizer BPE cũng tối ưu cho tiếng Anh; chữ Việt có dấu bị băm thành token vô nghĩa. Google Translate cho ra câu văn dài và giữ cả chi tiết không vẽ được, còn model anime lại được fine-tune trên tag kiểu Danbooru. Nên em để LLM làm cả hai việc trong một lần gọi: dịch và chuyển thể thành tag ngắn, bỏ tên riêng, thêm tag khung hình.

### 6. Làm sao để nhân vật nhất quán giữa các cảnh ở tầng văn bản?

Mỗi truyện có một character bible lưu trong `context.json` : `name` , `description` , `keywords_en` . System prompt gửi danh sách này và bắt LLM chép nguyên `keywords` vào prompt khi nhân vật xuất hiện, đồng thời không được viết tên vào prompt. Tên chỉ nằm ở trường `primary_character` để Trạm 2 lấy ảnh ref (IP-Adapter) hoặc LoRA của nhân vật đó. Em cũng nhận một hạn chế: LLM trả tên hiển thị còn Trạm 2 tra theo slug, nên cần thêm bước chuẩn hóa tên → slug để chắc chắn nhân vật được nhận ra.

### 7. Nhân vật được trích xuất ra sao?

`character_extractor.py` : đọc tối đa 5 chương đầu, mỗi chương cắt còn 10.000 ký tự, LLM trả 5–10 nhân vật với mô tả bám nguyên tác. Khử trùng theo tên, sau đó một lần gọi nữa sinh `keywords_en` (tag SD) cho từng nhân vật. Em cũng xin nói rõ hạn chế: phần "web search" chỉ là lời yêu cầu trong prompt; với Ollama local thì model không truy cập Internet được.

### 8. Style của các cảnh được giữ đồng nhất thế nào?

Style chỉ có một nguồn là file `style_prompt.txt` của truyện (chép từ preset, vd `thuy_mac` ). LLM bị cấm viết tag style, và kể cả nó cố viết thì `strip_style_drift` cũng lọc bỏ khoảng 60 tag như `masterpiece` , `anime` , `cinematic lighting` , tên model. `build_locked_prompt` luôn ghép theo thứ tự style → hành động có trọng số → nội dung. Tất cả đều là hàm thuần nên tất định và test được.

### 9. Cú pháp `(tag:1.35)` là gì, có tác dụng thật không?

Đó là trọng số attention kiểu A1111. Với compel, vector đầu ra của CLIP tại các token của tag được kéo xa khỏi vector của prompt rỗng theo hệ số 1.35: `z' = z_empty + 1.35·(z −` `z_empty)` , nên U-Net chú ý tới tag đó mạnh hơn qua cross-attention. Nó chỉ có tác dụng khi prompt được mã hóa qua thư viện compel; code chuyển cú pháp sang `(tag)1.35` của compel. Nếu thiếu compel thì code xóa sạch cú pháp trọng số để không thành token rác. Giá trị 1.35 lấy từ `studio_action_weight` : 1.25–1.45 là hợp lý, cao hơn dễ méo giải phẫu.

### 10. Negative prompt đến từ đâu và hoạt động thế nào?

Negative prompt là phần sau dấu `---` trong file style, cộng thêm `prompt_removals` đã học. Trong Classifier-Free Guidance, dự đoán nhiễu được đẩy về phía prompt dương và ra xa prompt âm: `ε̂=ε_neg + s(ε_pos −ε_neg)` , với `s = 5.0` . Vì vậy liệt kê `low quality, 3d, text, watermark...` sẽ đẩy ảnh tránh những đặc điểm đó.

### 11. Làm sao đảm bảo cảnh sau biết bối cảnh cảnh trước?

Em dùng ba cơ chế. Thứ nhất là Director's Note: một lần gọi LLM đọc cả chương, viết một câu chỉ đạo cho mỗi cảnh, nhấn tính liên tục. Thứ hai, `location/action/time_of_day` từ bước tách cảnh được nối vào prompt. Thứ ba, khi phải chia chunk thì 2 cảnh cuối của chunk trước được đưa vào chunk sau. Em không nhồi cả chương vào mỗi lời gọi vì model 3B có context nhỏ và sẽ chậm.

### 12. LLM chết giữa chừng thì hệ thống xử lý thế nào?

Mỗi cảnh được thử tối đa 2 lần; hỏng thì dùng prompt dự phòng `scenery, wide landscape, no humans` (vẫn có style) và bị đếm là thất bại. Nếu tất cả cảnh đều thất bại thì raise `AllPromptsFailedError` và dừng luôn, để không đốt hàng chục phút GPU sinh ra ảnh không liên quan đến truyện. Timeout mỗi lời gọi HTTP là 60 giây, và client `openai` tự thử lại tối đa 2 lần khi timeout hoặc lỗi kết nối.

### 13. Vì sao chạy song song 4 luồng mà không bị GIL?

Việc gọi LLM là I/O: thread chủ yếu chờ phản hồi HTTP, lúc đó GIL được nhả. Nên `ThreadPoolExecutor(max_workers=4)` vẫn giảm tổng thời gian chờ. Còn mức song song thật thì phụ thuộc server Ollama có xử lý đồng thời hay không.

### 14. Vì sao dùng LLM local (Ollama qwen2.5:3b) mà không dùng GPT/Gemini?

Chạy offline, không mất phí, không gửi nội dung truyện ra ngoài; qwen2.5 instruct hiểu tiếng Việt khá, bản 3B lượng tử hóa chiếm khoảng 2.8 GB VRAM (số đo trong bảng hồ sơ model của dự án) nên vừa GPU 6 GB. Code gọi qua client OpenAI với `base_url` cấu hình được nên đổi sang Gemini/OpenAI chỉ cần đổi tham số. Trước khi sinh ảnh, code gửi `keep_alive=0` để Ollama nhả VRAM cho Stable Diffusion.

### 15. Điểm yếu lớn nhất của bước này là gì?

Em nói thẳng: prompt xin cảnh 30–50 giây nhưng luật hậu kiểm lại chia cảnh dài hơn 27 giây, nên số cảnh thường nhiều hơn mục tiêu. Semantic split không có retry, một chunk hỏng là mất cả chương. Trích nhân vật khử trùng theo tên chính xác nên dễ tách một người thành hai. Hướng sửa: đồng bộ tham số, retry theo chunk, chuẩn hóa alias nhân vật.

### 16. Chương dài thì LLM local có đọc hết được không?

Em chia chunk 6000 từ và nối 2 cảnh cuối chunk trước vào chunk sau. Nhưng em cũng nhận thấy Bước 3 gọi Ollama qua endpoint tương thích OpenAI nên không đặt được `num_ctx` ; server dùng context mặc định vài nghìn token, trong khi 6000 từ tiếng Việt là cỡ 8–12 nghìn token. Nên với chương dài, model có thể bị cắt đầu vào, trả chỉ số thiếu và hệ thống rơi về `md_parser` — không sai kết quả nhưng mất chất lượng. Hướng sửa là gọi API native `/api/chat` kèm `num_ctx` như phần chatbot đã làm, hoặc giảm kích thước chunk.

## Tóm tắt 1 phút

"Bước 3a biến một chương truyện tiếng Việt thành kịch bản hình ảnh. Đầu tiên, nếu truyện mới, LLM đọc 5 chương đầu để lập character bible: tên, mô tả và bộ tag tiếng Anh cố định cho từng nhân vật. Với mỗi chương, em đo chính xác thời lượng audio, rồi chia văn bản thành các đơn vị đánh số và nhờ LLM gom thành các cảnh ngữ nghĩa, tức là đổi cảnh khi đổi địa điểm, nhân vật, hành động hoặc thời gian. Kết quả JSON được kiểm tra chặt: phủ kín, liên tiếp, không chồng; sai là rơi về cách chia theo số từ. Mỗi cảnh được gán thời gian bằng cách khớp với phụ đề, hoặc chia theo tỉ lệ số từ vì TTS đọc nguyên văn. Sau đó LLM làm đạo diễn: viết ghi chú liên tục cho cả chương, rồi viết cho từng cảnh một prompt tag tiếng Anh, vì Stable Diffusion hiểu qua CLIP vốn học bằng tiếng Anh. Phần style được hệ thống khóa cứng, tag style LLM tự thêm bị lọc, hành động được đặt trọng số 1.35 ngay sau style. Các lời gọi LLM quan trọng đều có JSON mode, parse phòng thủ và phương án dự phòng; bước sinh prompt còn thử lại mỗi cảnh, và nếu toàn bộ thất bại thì hệ thống dừng thay vì sinh ảnh rác."
