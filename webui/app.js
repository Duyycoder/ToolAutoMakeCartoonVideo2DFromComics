// API Base URL
const API_BASE = "";

// Global State
let activeStoryName = "";
let activeStorySlug = "";
let currentLogsSse = null;
let currentTaskKeys = {};
let step4State = { preparedPath: null, natW: null, natH: null, crop: null };

// DOM Elements
const elStorySelect = document.getElementById("storySelect");
const elBtnNewStory = document.getElementById("btnNewStory");
const elModalNewStory = document.getElementById("modalNewStory");
const elNewStoryName = document.getElementById("newStoryName");
const elBtnCancelStory = document.getElementById("btnCancelStory");
const elBtnConfirmStory = document.getElementById("btnConfirmStory");

const elActiveStoryTitle = document.getElementById("activeStoryTitle");
const elActiveStorySubtitle = document.getElementById("activeStorySubtitle");
const elPipelineStatusBadge = document.getElementById("pipelineStatusBadge");

// Tabs
const navItems = document.querySelectorAll(".nav-item");
const tabPanels = document.querySelectorAll(".tab-panel");

// Initialize application
document.addEventListener("DOMContentLoaded", async () => {
    initTabs();
    setupEventHandlers();   // gắn listener TRƯỚC để applyAllSettings dispatch 'change' có tác dụng
    buildConfigMirror();    // nhân bản control từng bước vào Cấu Hình Chung (phải chạy trước loadGlobalConfig)
    fetchGpuInfo();
    await loadStories();
    await loadGlobalConfig();
    // Cấu hình người dùng đã lưu phải áp SAU CÙNG để thắng các giá trị default
    await loadAndApplySettings();
    resumeAutoRunUi();
});

// Fetch GPU info from backend
async function fetchGpuInfo() {
    try {
        const textLabel = document.getElementById("gpuInfoText");
        textLabel.textContent = "Đang kiểm tra GPU...";
        // Call backend API (assume we will add it to main.py)
        const response = await fetch(`${API_BASE}/api/system/gpu-info`);
        if (response.ok) {
            const data = await response.json();
            textLabel.textContent = `GPU: ${data.name || 'Không tìm thấy'} | VRAM: ${data.vram || 'N/A'}`;
        } else {
            textLabel.textContent = "Lỗi không lấy được GPU Info.";
        }
    } catch (e) {
        document.getElementById("gpuInfoText").textContent = "Lỗi kết nối GPU Info.";
    }
}

// Tab Navigation Logic
function initTabs() {
    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const targetTab = item.getAttribute("data-tab");
            
            navItems.forEach(nav => nav.classList.remove("active"));
            tabPanels.forEach(panel => panel.classList.remove("active"));
            
            item.classList.add("active");
            document.getElementById(`tab-${targetTab}`).classList.add("active");
        });
    });
}

// Fetch list of projects/stories
async function loadStories() {
    try {
        const response = await fetch(`${API_BASE}/api/stories`);
        const stories = await response.json();
        
        // Save current selection if any
        const prevSelected = elStorySelect.value;
        
        elStorySelect.innerHTML = `<option value="" disabled selected>Chọn truyện hoặc tạo mới...</option>`;
        
        stories.forEach(story => {
            const opt = document.createElement("option");
            opt.value = story.story_name;
            opt.textContent = `${story.story_name} [${story.status}]`;
            elStorySelect.appendChild(opt);
        });

        if (prevSelected && stories.some(s => s.story_name === prevSelected)) {
            elStorySelect.value = prevSelected;
            selectStory(prevSelected);
        }
    } catch (e) {
        console.error("Lỗi khi tải danh sách truyện:", e);
    }
}

// UI Event Listeners for Step 1
document.getElementById('s1Source').addEventListener('change', (e) => {
    const val = e.target.value;
    const storyIdGroup = document.getElementById('s1StoryIdGroup');
    const localFolderGroup = document.getElementById('s1LocalFolderGroup');
    const storyIdInput = document.getElementById('s1StoryId');
    const localFolderInput = document.getElementById('s1LocalFolder');
    
    const topicGroup = document.getElementById('s1TopicGroup');
    const topicInput = document.getElementById('s1Topic');
    [storyIdGroup, localFolderGroup, topicGroup].forEach(g => { if (g) g.style.display = 'none'; });
    [storyIdInput, localFolderInput, topicInput].forEach(inp => { if (inp) inp.removeAttribute('required'); });
    if (val === 'local') {
        if (localFolderGroup) localFolderGroup.style.display = 'block';
        if (localFolderInput) localFolderInput.setAttribute('required', 'true');
    } else if (val === 'ai_write') {
        if (topicGroup) topicGroup.style.display = 'block';
        if (topicInput) topicInput.setAttribute('required', 'true');
    } else {
        if (storyIdGroup) storyIdGroup.style.display = 'block';
        if (storyIdInput) storyIdInput.setAttribute('required', 'true');
    }
});
// A1: đồng bộ hiển thị nhóm field theo nguồn đang chọn khi tải trang
document.getElementById('s1Source').dispatchEvent(new Event('change'));

// Select a story and load its metadata details
async function selectStory(storyName) {
    activeStoryName = storyName;
    try {
        const response = await fetch(`${API_BASE}/api/stories/${encodeURIComponent(storyName)}`);
        const meta = await response.json();

        elActiveStoryTitle.textContent = meta.story_name;
        elActiveStorySubtitle.textContent = `Thư mục lưu trữ: ${meta.story_dir} | Chương đã cào: ${meta.raw_chapters_count || 0}`;
        activeStorySlug = meta.story_slug || "";

        // Update badge status
        updateStatusBadge(meta.status);

        // Khôi phục trạng thái nút Bắt đầu/Dừng sau khi reload trang hoặc
        // đổi truyện: hỏi server xem bước nào đang thực sự chạy.
        restoreRunningTasks(meta.story_slug);
        resumeAutoRunUi();
    } catch (e) {
        console.error("Lỗi khi chọn truyện:", e);
    }
}

// Đồng bộ UI với trạng thái chạy thật ở server (sau reload, UI mặc định
// luôn hiện "Bắt đầu" kể cả khi task còn chạy -> bấm bị lỗi "already active"
// mà không có nút Dừng). Đồng thời tự nối lại luồng log của bước đang chạy.
async function restoreRunningTasks(storySlug) {
    if (!storySlug) return;
    let attachStep = null, attachKey = null;
    for (let i = 1; i <= 5; i++) {
        const stepName = `step${i}`;
        const key = `${storySlug}_step${i}`;
        try {
            const res = await fetch(`${API_BASE}/api/pipeline/status/${encodeURIComponent(key)}`, { cache: "no-store" });
            if (!res.ok) continue;
            const st = await res.json();
            toggleFormButtons(stepName, !!st.running);
            if (st.running) {
                currentTaskKeys[stepName] = key;
                attachStep = stepName;
                attachKey = key;
            }
        } catch (e) { /* server chưa sẵn sàng thì bỏ qua */ }
    }
    // Chỉ có một luồng SSE toàn cục -> bám vào bước đang chạy sau cùng,
    // và không cướp luồng nếu đã có EventSource đang mở.
    if (attachKey && !currentLogsSse) {
        appendConsoleLog(attachStep, "[SYSTEM] Phát hiện tiến trình đang chạy — nối lại luồng log...", "log-system");
        streamLogs(attachStep, attachKey);
    }
}

// Sau khi gửi lệnh dừng: chờ server xác nhận task đã giải phóng rồi trả
// nút về "Bắt đầu" (dự phòng cho trường hợp SSE không còn mở, vd sau reload).
async function waitTaskStopped(stepName, taskKey, tries = 25) {
    const btnStop = document.getElementById(`btnStopStep${stepName.slice(-1)}`);
    for (let i = 0; i < tries; i++) {
        await new Promise(r => setTimeout(r, 400));
        // SSE đã nhận tín hiệu kết thúc và tự trả nút thì thôi không poll nữa
        if (btnStop && btnStop.style.display === "none") return;
        try {
            const res = await fetch(`${API_BASE}/api/pipeline/status/${encodeURIComponent(taskKey)}`, { cache: "no-store" });
            if (!res.ok) continue;
            const st = await res.json();
            if (!st.running) {
                toggleFormButtons(stepName, false);
                appendConsoleLog(stepName, "[SYSTEM] Tiến trình đã dừng hẳn. Có thể bắt đầu lại.", "log-success");
                loadStories();
                return;
            }
        } catch (e) { /* thử lại ở vòng sau */ }
    }
    appendConsoleLog(stepName, "[SYSTEM] Tiến trình dừng chậm bất thường — hãy thử bấm Dừng lần nữa.", "log-warn");
}

// ==========================================================================
// Payload builders — dùng chung cho nút chạy lẻ từng bước VÀ chuỗi Chạy tự động
// ==========================================================================
function buildStep1Payload() {
    const engine = document.getElementById("s1Engine").value;
    return {
        story_name: activeStoryName,
        source_site: document.getElementById("s1Source").value,
        base_url: document.getElementById("s1BaseUrl")?.value || null,
        story_id: document.getElementById("s1StoryId").value,
        local_folder: document.getElementById("s1LocalFolder")?.value,
        topic: document.getElementById("s1Topic")?.value || null,
        start_chapter_id: document.getElementById("s1StartChapterId").value || null,
        max_chapters: parseInt(document.getElementById("s1NumChapters").value) || 1,
        engine: engine,
        ollama_model: document.getElementById("s1OllamaModel").value,
        gemini_api_key: (engine === "gemini" || engine === "gemini_api")
            ? (document.getElementById("s1GeminiKey").value || "") : "",
        gemini_offline_base_url: document.getElementById("s1GeminiOfflineUrl")?.value || "",
        gemini_offline_model: document.getElementById("s1GeminiOfflineModel")?.value || "",
        genre: document.getElementById("s1Genre").value,
        auto_extract: document.getElementById("s1AutoExtract").checked,
        auto_translate: document.getElementById("s1AutoTranslate")?.checked,
        continue_download: document.getElementById("s1ContinueDownload")?.checked,
        glossary_extract_engine: document.getElementById("s1GlossaryEngine")?.value || "same_as_trans",
        glossary_extract_ollama_model: document.getElementById("s1GlossaryOllamaModel")?.value || ""
    };
}

function buildStep2Payload() {
    return {
        story_name: activeStoryName,
        engine: document.getElementById("s2Engine").value,
        voice: document.getElementById("s2Voice").value,
        speed: parseFloat(document.getElementById("s2Speed").value),
        model: document.getElementById("s2Model").value || null,
        ref_audio: document.getElementById("s2RefAudio").value || null,
        phonemize: document.getElementById("s2Phonemize").checked,
        normalize: document.getElementById("s2Normalize").checked,
        target_lufs: parseFloat(document.getElementById("s2TargetLufs").value),
        fade_in: parseFloat(document.getElementById("s2FadeIn").value),
        fade_out: parseFloat(document.getElementById("s2FadeOut").value),
        silence_duration: parseFloat(document.getElementById("s2Silence").value),
        device: document.getElementById("s2Device").value,
        use_cache: document.getElementById("s2UseCache").checked,
        cache_threshold: parseFloat(document.getElementById("s2CacheThreshold").value),
        vieneu_mode: document.getElementById("s2VieneuMode").value,
        vieneu_emotion: document.getElementById("s2VieneuEmotion").value,
        temperature: parseFloat(document.getElementById("s2Temperature").value)
    };
}

function buildStep3Payload() {
    return {
        story_name: activeStoryName,
        genre: document.getElementById("s3Genre").value,
        style: document.getElementById("s3Style").value,
        checkpoint: document.getElementById("s3Checkpoint").value,
        bgm_path: document.getElementById("s3Bgm").value,
        bgm_volume: parseFloat(document.getElementById("s3BgmVolume").value),
        enable_upscale: document.getElementById("s3Upscale").checked,
        burn_subtitles: document.getElementById("s3Subtitles").checked,
        use_semantic_split: document.getElementById("s3Semantic").checked,
        extract_characters: document.getElementById("s3ExtractChars").checked,
        enable_face_detailer: document.getElementById("s3FaceDetailer").checked,
        render_mode: document.getElementById("s3RenderMode").value,
        hardware_profile: document.getElementById("s3HardwareProfile").value,
        device: document.getElementById("s3GpuDevice").value,
        llm_engine: document.getElementById("s3LlmEngine").value,
        llm_api_key: document.getElementById("s3GeminiKey").value || null,
        llm_offline_base_url: document.getElementById("s3GeminiOfflineUrl").value || null,
        llm_offline_model: (document.getElementById("s3LlmEngine").value === "ollama"
            ? document.getElementById("s3OllamaModel").value
            : document.getElementById("s3LlmModel").value) || null
    };
}

// ==========================================================================
// Lưu / khôi phục TOÀN BỘ cấu hình UI (mọi form + tab settings + truyện đang chọn)
// ==========================================================================
function collectAllSettings() {
    const data = { fields: {}, radios: {}, story: elStorySelect.value || "" };
    document.querySelectorAll(".tab-panel input[id], .tab-panel select[id], .tab-panel textarea[id]").forEach(el => {
        if (el.closest("#tab-settings")) return;       // Cấu Hình Chung lưu riêng ở global_config.json
        if (el.type === "radio") return;               // radio lưu theo nhóm bên dưới
        if (el.type === "checkbox") data.fields[el.id] = { c: el.checked };
        else data.fields[el.id] = { v: el.value };
    });
    document.querySelectorAll(".tab-panel input[type=radio][name]").forEach(el => {
        if (el.checked) data.radios[el.name] = el.value;
    });
    return data;
}

function applyAllSettings(saved) {
    if (!saved || !saved.fields) return;
    for (const [id, val] of Object.entries(saved.fields)) {
        const el = document.getElementById(id);
        if (!el) continue;                              // field đã bị xóa ở version mới
        if (el.closest("#tab-settings")) continue;      // Cấu Hình Chung do global_config quản lý (bỏ qua snapshot cũ)
        if (val.c !== undefined) {
            el.checked = val.c;
        } else if (val.v !== undefined) {
            // Dropdown load async (vd model Ollama) chưa có option -> chèn tạm để
            // giữ giá trị; loadOllamaModels() sẵn logic giữ "previous selection".
            if (el.tagName === "SELECT" && val.v !== "" && ![...el.options].some(o => o.value === val.v)) {
                const opt = document.createElement("option");
                opt.value = val.v;
                opt.textContent = val.v;
                el.appendChild(opt);
            }
            el.value = val.v;
        } else {
            continue;
        }
        // Cho các handler ẩn/hiện nhóm phụ thuộc (engine -> key/model...) chạy đúng.
        // Duyệt theo thứ tự DOM nên field bị handler ghi đè sẽ được áp lại sau đó.
        el.dispatchEvent(new Event("change", { bubbles: true }));
    }
    for (const [name, v] of Object.entries(saved.radios || {})) {
        const radio = document.querySelector(`input[type=radio][name="${name}"][value="${v}"]`);
        if (radio && !radio.checked) {
            radio.checked = true;
            radio.dispatchEvent(new Event("change", { bubbles: true }));
        }
    }
    if (saved.story && [...elStorySelect.options].some(o => o.value === saved.story)) {
        elStorySelect.value = saved.story;
        selectStory(saved.story);
    }
}

async function saveAllSettings() {
    const btn = document.getElementById("btnSaveSettings");
    try {
        const res = await fetch(`${API_BASE}/api/ui-settings`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(collectAllSettings())
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        if (btn) {
            const old = btn.textContent;
            btn.textContent = "✓ Đã lưu!";
            setTimeout(() => { btn.textContent = old; }, 1600);
        }
    } catch (e) {
        alert("Không lưu được cấu hình: " + e.message);
    }
}

async function loadAndApplySettings() {
    try {
        const res = await fetch(`${API_BASE}/api/ui-settings`, { cache: "no-store" });
        if (!res.ok) return;
        applyAllSettings(await res.json());
    } catch (e) {
        console.error("Không tải được cấu hình đã lưu:", e);
    }
}

// ==========================================================================
// Chạy tự động Bước 1→4 (backend chạy chuỗi; UI chỉ theo dõi qua polling)
// ==========================================================================
// "Bước 4: Ghép Video" trên sidebar là task nội bộ step5
const INTERNAL_STEP_BY_DISPLAY = { 1: 1, 2: 2, 3: 3, 4: 5 };
let autoRunPollTimer = null;
let autoRunLastStep = null;

function setAutoRunUi(running, text) {
    const st = document.getElementById("autoRunStatus");
    const btnRun = document.getElementById("btnAutoRun");
    const btnStop = document.getElementById("btnStopAutoRun");
    if (btnRun) btnRun.style.display = running ? "none" : "";
    if (btnStop) btnStop.style.display = running ? "" : "none";
    if (st) {
        st.style.display = text ? "" : "none";
        st.textContent = text || "";
    }
}

async function startAutoRun() {
    if (!activeStoryName) return alert("Vui lòng chọn truyện trước!");
    if (!confirm(`Chạy tự động Bước 1→4 cho "${activeStoryName}" với cấu hình đang chọn?\n` +
                 "Các bước sẽ nối tiếp nhau không cần canh máy (Bước 3 có thể chạy nhiều giờ).")) return;
    const body = {
        story_name: activeStoryName,
        step1: buildStep1Payload(),
        step2: buildStep2Payload(),
        step3: buildStep3Payload()
    };
    try {
        const res = await fetch(`${API_BASE}/api/pipeline/auto-run`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        });
        const data = await res.json();
        if (!res.ok) return alert(`Không chạy được chuỗi tự động: ${data.detail}`);
        autoRunLastStep = null;
        setAutoRunUi(true, "⏳ Đang khởi động chuỗi tự động...");
        pollAutoRun();
    } catch (e) {
        alert("Lỗi kết nối tới server: " + e);
    }
}

async function stopAutoRun() {
    if (!activeStoryName) return;
    if (!confirm("Dừng chuỗi tự động? Bước đang chạy sẽ bị hủy.")) return;
    try {
        await fetch(`${API_BASE}/api/pipeline/auto-run/stop?story_name=${encodeURIComponent(activeStoryName)}`,
                    { method: "POST" });
    } catch (e) { /* poll bên dưới sẽ phản ánh trạng thái thật */ }
    pollAutoRun();
}

// Chuyển tab + bám luồng log của bước chuỗi đang chạy
function followAutoRunStep(displayStep) {
    const internal = INTERNAL_STEP_BY_DISPLAY[displayStep];
    if (!internal || !activeStorySlug) return;
    const stepName = `step${internal}`;
    const navBtn = document.querySelector(`.nav-item[data-tab="${stepName}"]`);
    if (navBtn) navBtn.click();
    toggleFormButtons(stepName, true);
    // Chờ ngắn cho backend kịp tạo log queue của bước mới rồi mới nối SSE
    const key = `${activeStorySlug}_step${internal}`;
    setTimeout(() => streamLogs(stepName, key), 800);
}

async function pollAutoRun() {
    clearTimeout(autoRunPollTimer);
    if (!activeStoryName) { setAutoRunUi(false, null); return; }
    try {
        const res = await fetch(`${API_BASE}/api/pipeline/auto-run/${encodeURIComponent(activeStoryName)}`,
                                { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const st = await res.json();
        if (st.running) {
            setAutoRunUi(true, `⏳ Tự động: Bước ${st.current_step}/${st.total_steps} — ${st.step_label}`);
            // Đổi bước, hoặc SSE bị rớt -> bám lại luồng log
            if (st.current_step !== autoRunLastStep || !currentLogsSse) {
                autoRunLastStep = st.current_step;
                followAutoRunStep(st.current_step);
            }
            autoRunPollTimer = setTimeout(pollAutoRun, 2000);
            return;
        }
        autoRunLastStep = null;
        if (st.finished) {
            setAutoRunUi(false, st.error ? `❌ Chuỗi dừng: ${st.error}` : "✅ Đã hoàn thành Bước 1→4!");
            loadStories();
        } else {
            setAutoRunUi(false, null);
        }
    } catch (e) {
        // server chưa phản hồi -> thử lại
        autoRunPollTimer = setTimeout(pollAutoRun, 3000);
    }
}

// Gọi khi mở app / đổi truyện: nếu chuỗi đang chạy (vd sau reload) thì nối lại UI
function resumeAutoRunUi() {
    autoRunLastStep = null;
    pollAutoRun();
}

function updateStatusBadge(status) {
    elPipelineStatusBadge.textContent = status;
    elPipelineStatusBadge.className = "badge"; // Reset classes
    
    if (["CRAWLING", "TRANSLATING", "VOICE_GENERATING", "VIDEO_GENERATING"].includes(status)) {
        elPipelineStatusBadge.classList.add("badge-active");
    } else if (["TRANSLATED", "VOICE_GENERATED", "VIDEO_GENERATED"].includes(status)) {
        elPipelineStatusBadge.classList.add("badge-success");
    } else {
        elPipelineStatusBadge.classList.add("badge-inactive");
    }
}

// Setup popup dialog, inputs overrides toggles and forms
function setupEventHandlers() {
    // New Story Dialog Toggles
    elBtnNewStory.addEventListener("click", () => elModalNewStory.classList.add("open"));
    elBtnCancelStory.addEventListener("click", () => elModalNewStory.classList.remove("open"));
    
    elBtnConfirmStory.addEventListener("click", async () => {
        const name = elNewStoryName.value.trim();
        if (!name) return;
        
        try {
            const response = await fetch(`${API_BASE}/api/stories`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ story_name: name })
            });
            const res = await response.json();
            
            if (response.ok && res.status === "success") {
                elNewStoryName.value = "";
                elModalNewStory.classList.remove("open");
                await loadStories();
                elStorySelect.value = name;
                selectStory(name);
            } else {
                alert(`Lỗi khi tạo truyện mới: ${res.detail || 'Lỗi không xác định'}`);
            }
        } catch (e) {
            alert("Lỗi mạng khi tạo truyện mới: " + e);
        }
    });

    elStorySelect.addEventListener("change", (e) => {
        selectStory(e.target.value);
    });

    // Dynamic Options Displays depending on dropdown select values
    const elS1Engine = document.getElementById("s1Engine");
    const elGroupOllama = document.getElementById("groupOllamaModel");
    const elGroupGemini = document.getElementById("groupGeminiKey");
    
    elS1Engine.addEventListener("change", () => {
        elGroupOllama.style.display = elS1Engine.value === "ollama" ? "block" : "none";
        elGroupGemini.style.display = elS1Engine.value === "gemini" ? "block" : "none";
        if (elS1Engine.value === "ollama") {
            loadOllamaModels();
        }
    });

    const elS1AutoExtract = document.getElementById("s1AutoExtract");
    const elBlockS1GlossaryConfig = document.getElementById("blockS1GlossaryConfig");
    const elS1GlossaryEngine = document.getElementById("s1GlossaryEngine");
    const elGroupS1GlossaryOllama = document.getElementById("groupS1GlossaryOllama");

    if (elS1AutoExtract && elBlockS1GlossaryConfig) {
        elS1AutoExtract.addEventListener("change", () => {
            elBlockS1GlossaryConfig.style.display = elS1AutoExtract.checked ? "flex" : "none";
        });
    }

    if (elS1GlossaryEngine && elGroupS1GlossaryOllama) {
        elS1GlossaryEngine.addEventListener("change", () => {
            elGroupS1GlossaryOllama.style.display = elS1GlossaryEngine.value === "ollama" ? "block" : "none";
            if (elS1GlossaryEngine.value === "ollama") {
                loadGlossaryOllamaModels();
            }
        });
    }

    const elS2Engine = document.getElementById("s2Engine");
    const elGroupTtsModel = document.getElementById("groupTtsModel");
    const elGroupRefAudio = document.getElementById("groupRefAudio");
    const elS2Preset = document.getElementById("s2Preset");

    elS2Preset.addEventListener("change", async () => {
        const val = elS2Preset.value;
        if (val === "default") return;
        
        // Hardcode a few presets for demo since backend preset endpoint isn't fully set up
        const presets = {
            "fast": { engine: "edge", voice: "vi-VN-NamMinhNeural", speed: 1.15, normalize: true, lufs: -14.0 },
            "female_reading": { engine: "edge", voice: "vi-VN-HoaiMyNeural", speed: 1.0, normalize: true, lufs: -14.0 },
            "offline_cloning": { engine: "clone", speed: 1.0, normalize: true, lufs: -14.0, phonemize: true },
            "offline_fast": { engine: "piper", speed: 1.2, normalize: false },
            "kokoro_vi": { engine: "kokoro", speed: 1.0 },
            "vieneu": { engine: "vieneu", speed: 1.0 }
        };
        const p = presets[val];
        if (p) {
            if (p.engine) {
                elS2Engine.value = p.engine;
                elS2Engine.dispatchEvent(new Event('change'));
            }
            if (p.voice) document.getElementById("s2Voice").value = p.voice;
            if (p.speed) document.getElementById("s2Speed").value = p.speed;
            if (p.normalize !== undefined) document.getElementById("s2Normalize").checked = p.normalize;
            if (p.lufs !== undefined) document.getElementById("s2TargetLufs").value = p.lufs;
            if (p.phonemize !== undefined) document.getElementById("s2Phonemize").checked = p.phonemize;
        }
    });

    elS2Engine.addEventListener("change", () => {
        const eng = elS2Engine.value;
        document.getElementById("groupGeminiKey").style.display = (eng === "gemini" || eng === "gemini_api") ? "block" : "none";
        if(document.getElementById("groupGeminiOfflineUrl")) {
            document.getElementById("groupGeminiOfflineUrl").style.display = (eng === "gemini_api") ? "block" : "none";
            document.getElementById("groupGeminiOfflineModel").style.display = (eng === "gemini_api") ? "block" : "none";
        }
        elGroupTtsModel.style.display = (eng === "piper" || eng === "clone" || eng === "kokoro" || eng === "vieneu") ? "block" : "none";
        document.getElementById("groupVieneuOptions").style.display = (eng === "vieneu") ? "grid" : "none";
        
        // Auto-update voice/model fields based on engine to mimic AIVoice UI
        const voiceSelect = document.getElementById("s2Voice");
        const modelInput = document.getElementById("s2Model");
        voiceSelect.innerHTML = "";
        
        if (eng === "edge") {
            voiceSelect.innerHTML = `<option value="vi-VN-NamMinhNeural">vi-VN-NamMinhNeural (Nam - VN)</option>
                                     <option value="vi-VN-HoaiMyNeural">vi-VN-HoaiMyNeural (Nữ - VN)</option>
                                     <option value="en-US-AriaNeural">en-US-AriaNeural (Nữ - US)</option>
                                     <option value="en-US-GuyNeural">en-US-GuyNeural (Nam - US)</option>
                                     <option value="en-GB-SoniaNeural">en-GB-SoniaNeural (Nữ - UK)</option>`;
            elGroupRefAudio.style.display = "none";
        } else if (eng === "clone") {
            voiceSelect.innerHTML = `<option value="vi">Tiếng Việt (vi)</option>`;
            if(!modelInput.value || !modelInput.value.includes("xtts")) modelInput.value = "models/xttsv2";
            elGroupRefAudio.style.display = "block";
        } else if (eng === "piper") {
            voiceSelect.innerHTML = `<option value="models/piper/vi_VN-vais1000-medium.onnx">VAIS1000 (Medium)</option>
                                     <option value="models/piper/vi_VN-vivos-x_low.onnx">VIVOS (X-Low)</option>
                                     <option value="models/piper/en_US-lessac-medium.onnx">EN Lessac (Medium)</option>`;
            modelInput.value = voiceSelect.value;
            elGroupRefAudio.style.display = "none";
        } else if (eng === "kokoro") {
            voiceSelect.innerHTML = `<option value="diem_trinh">Diễm Trinh (Nữ miền Nam)</option>
                                     <option value="hung_thinh">Hưng Thịnh (Nam miền Nam)</option>
                                     <option value="mai_linh">Mai Linh (Nữ miền Bắc)</option>
                                     <option value="mai_loan">Mai Loan (Nữ miền Bắc)</option>
                                     <option value="manh_dung">Mạnh Dũng (Nam miền Bắc)</option>
                                     <option value="my_yen">Mỹ Yến (Nữ miền Nam)</option>
                                     <option value="ngoc_huyen">Ngọc Huyền (Nữ miền Bắc)</option>
                                     <option value="phat_tai">Phát Tài (Nam miền Nam)</option>
                                     <option value="thanh_dat">Thành Đạt (Nam miền Bắc)</option>
                                     <option value="thuc_trinh">Thục Trinh (Nữ miền Bắc)</option>
                                     <option value="tuan_ngoc">Tuấn Ngọc (Nam miền Bắc)</option>
                                     <option value="storyvert">Storyvert (Nữ miền Bắc)</option>
                                     <option value="duc_an">Đức An (Nam miền Bắc)</option>
                                     <option value="duc_duy">Đức Duy (Nam miền Bắc)</option>`;
            if(!modelInput.value || !modelInput.value.includes("kokoro")) modelInput.value = "models/kokoro";
            elGroupRefAudio.style.display = "none";
        } else if (eng === "vieneu") {
            voiceSelect.innerHTML = `<option value="Ngọc Lan">Ngọc Lan (Nữ - Dịu dàng)</option>
                                     <option value="Gia Bảo">Gia Bảo (Nam - Mượt mà)</option>
                                     <option value="Thái Sơn">Thái Sơn (Nam - Chắc khỏe)</option>
                                     <option value="Đức Trí">Đức Trí (Nam - Rõ ràng)</option>
                                     <option value="Mỹ Duyên">Mỹ Duyên (Nữ - Mượt mà)</option>
                                     <option value="Trúc Ly">Trúc Ly (Nữ - Trẻ trung)</option>
                                     <option value="Xuân Vĩnh">Xuân Vĩnh (Nam - Vui tươi)</option>
                                     <option value="Trọng Hữu">Trọng Hữu (Nam - Uyên bác)</option>
                                     <option value="Bình An">Bình An (Nam - Điềm đạm)</option>
                                     <option value="Ngọc Linh">Ngọc Linh (Nữ - Tươi sáng)</option>
                                     <option value="ref_audio">Sử dụng file giọng mẫu (Clone)</option>`;
            if(!modelInput.value || !modelInput.value.includes("vieneu")) modelInput.value = "models/vieneu";
            elGroupRefAudio.style.display = voiceSelect.value === "ref_audio" ? "block" : "none";
        } else {
            voiceSelect.innerHTML = `<option value="default">Mặc định</option>`;
            elGroupRefAudio.style.display = "none";
        }
    });

    document.getElementById("s2Voice").addEventListener("change", (e) => {
        const eng = elS2Engine.value;
        const val = e.target.value;
        const modelInput = document.getElementById("s2Model");
        
        if (eng === "piper") {
            modelInput.value = val;
        } else if (eng === "vieneu") {
            elGroupRefAudio.style.display = val === "ref_audio" ? "block" : "none";
        }
    });

    const elS3LlmEngine = document.getElementById("s3LlmEngine");
    const elGroupS3GeminiKey = document.getElementById("groupS3GeminiKey");
    const elGroupS3GeminiOfflineUrl = document.getElementById("groupS3GeminiOfflineUrl");
    const elGroupS3LlmModel = document.getElementById("groupS3LlmModel");
    const elGroupS3OllamaModel = document.getElementById("groupS3OllamaModel");

    elS3LlmEngine.addEventListener("change", () => {
        const eng = elS3LlmEngine.value;
        const isOllama = (eng === "ollama");
        elGroupS3GeminiKey.style.display = (eng === "gemini" || eng === "gemini_api") ? "block" : "none";
        elGroupS3GeminiOfflineUrl.style.display = (eng === "gemini_api" || isOllama) ? "block" : "none";
        // Ollama chọn model bằng dropdown; Gemini nhập model bằng text
        elGroupS3OllamaModel.style.display = isOllama ? "block" : "none";
        elGroupS3LlmModel.style.display = isOllama ? "none" : "block";

        const modelInput = document.getElementById("s3LlmModel");
        if (eng === "gemini") {
            modelInput.value = "gemini-2.0-flash";
        } else {
            modelInput.value = "gemini-3-flash";
        }

        if (isOllama) {
            loadOllamaModels("s3OllamaModel", "s3OllamaStatus");
        }

        // Xóa URL cũ khi đổi engine để backend tự resolve theo engine mới (tránh trỏ nhầm cổng)
        const urlInput = document.getElementById("s3GeminiOfflineUrl");
        if (urlInput) {
            urlInput.value = "";
            urlInput.placeholder = isOllama ? "http://localhost:11434/v1" : "http://localhost:7860/v1";
        }
    });

    const btnClearCache = document.getElementById("btnClearCache");
    if (btnClearCache) {
        btnClearCache.addEventListener("click", async () => {
            if(confirm("Bạn có chắc chắn muốn xóa toàn bộ cache giọng đọc không?")) {
                try {
                    const response = await fetch(`${API_BASE}/api/system/clear-cache`, { method: "POST" });
                    const res = await response.json();
                    alert(res.message || "Đã xóa cache thành công.");
                } catch (e) {
                    alert("Lỗi khi xóa cache.");
                }
            }
        });
    }

    // Form Submits: Step 1, Step 2, Step 3
    document.getElementById("formStep1").addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!activeStoryName) return alert("Vui lòng chọn truyện trước!");
        
        const payload = buildStep1Payload();

        toggleFormButtons("step1", true);
        clearConsole("step1");
        
        const taskKey = await postPipelineAction("step1", payload);
        if (taskKey) {
            // Background save to global config
            try {
                const cfgRes = await fetch(`${API_BASE}/api/config`);
                const config = await cfgRes.json();
                let changed = false;
                if(payload.engine === "gemini_api" && payload.gemini_offline_base_url) {
                    if(!config.crawler) config.crawler = {};
                    config.crawler.gemini_offline_base_url = payload.gemini_offline_base_url;
                    changed = true;
                }
                if((payload.engine === "gemini" || payload.engine === "gemini_api") && payload.gemini_api_key) {
                    if(!config.api_keys) config.api_keys = {};
                    config.api_keys.gemini = payload.gemini_api_key;
                    changed = true;
                }
                if(changed) {
                    await fetch(`${API_BASE}/api/config`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(config)
                    });
                }
            } catch(e) { console.error("Error auto-saving config:", e); }
            
            streamLogs("step1", taskKey);
        } else {
            toggleFormButtons("step1", false);
        }
    });

    document.getElementById("formStep2").addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!activeStoryName) return alert("Vui lòng chọn truyện trước!");

        const payload = buildStep2Payload();

        toggleFormButtons("step2", true);
        clearConsole("step2");

        const taskKey = await postPipelineAction("step2", payload);
        if (taskKey) {
            streamLogs("step2", taskKey);
        } else {
            toggleFormButtons("step2", false);
        }
    });

    document.getElementById("formStep3").addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!activeStoryName) return alert("Vui lòng chọn truyện trước!");

        const payload = buildStep3Payload();

        toggleFormButtons("step3", true);
        clearConsole("step3");

        const taskKey = await postPipelineAction("step3", payload);
        if (taskKey) {
            streamLogs("step3", taskKey);
        } else {
            toggleFormButtons("step3", false);
        }
    });

    // Cancel Process handlers
    document.getElementById("btnStopStep1").addEventListener("click", () => stopPipelineTask("step1", 1));
    document.getElementById("btnStopStep2").addEventListener("click", () => stopPipelineTask("step2", 2));
    document.getElementById("btnStopStep3").addEventListener("click", () => stopPipelineTask("step3", 3));

    // Global Settings Form Submit
    document.getElementById("formSettings").addEventListener("submit", async (e) => {
        e.preventDefault();
        // Gộp lên cấu hình đã nạp để KHÔNG mất các khóa không hiển thị trên form
        // (vd orchestrator_port, crawler.gemini_offline_key). Mọi field mang
        // data-cfg tự động ghi vào đúng nhánh JSON tương ứng.
        const payload = JSON.parse(JSON.stringify(_globalConfig || {}));
        document.querySelectorAll("#formSettings [data-cfg]").forEach(el => {
            cfgSetByPath(payload, el.dataset.cfg, cfgReadField(el));
        });
        // Bảo đảm các mục bắt buộc theo GlobalConfigSchema luôn tồn tại
        payload.api_keys = payload.api_keys || {};
        payload.crawler = payload.crawler || {};
        payload.tts = payload.tts || {};
        payload.video = payload.video || {};
        if (payload.storage_dir === undefined || payload.storage_dir === null) payload.storage_dir = "storage";
        _globalConfig = payload;

        try {
            const response = await fetch(`${API_BASE}/api/config`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const res = await response.json();
            if (res.status === "success") {
                // Áp mặc định mới vào các bước ngay và chốt snapshot để giữ nguyên
                // sau khi tải lại (nếu không, ui_settings cũ có thể ghi đè).
                applyConfigDefaultsToSteps();
                await saveAllSettings();
                alert("Đã lưu cấu hình. Các bước đã áp mặc định mới.");
            }
        } catch (e) {
            alert("Lỗi khi lưu cấu hình: " + e);
        }
    });

    // --- STEP 4 EVENT HANDLERS ---
    const radiosS4 = document.getElementsByName("s4VideoSource");
    const groupS4Local = document.getElementById("groupS4Local");
    const groupS4Url = document.getElementById("groupS4Url");
    radiosS4.forEach(r => {
        r.addEventListener("change", () => {
            const isLocal = r.value === "local";
            groupS4Local.style.display = isLocal ? "block" : "none";
            groupS4Url.style.display = isLocal ? "none" : "block";
        });
    });

    const elS4SubSource = document.getElementById("s4SubSource");
    const elGroupS4OcrPreview = document.getElementById("groupS4OcrPreview");
    const elGroupS4CleanAudio = document.getElementById("groupS4CleanAudio");
    elS4SubSource.addEventListener("change", () => {
        const isOcr = elS4SubSource.value === "ocr";
        elGroupS4OcrPreview.style.display = isOcr ? "block" : "none";
        elGroupS4CleanAudio.style.display = isOcr ? "none" : "block";
    });

    const elS4EnableVoiceover = document.getElementById("s4EnableVoiceover");
    const elGroupS4Voiceover = document.getElementById("groupS4Voiceover");
    elS4EnableVoiceover.addEventListener("change", () => {
        elGroupS4Voiceover.style.display = elS4EnableVoiceover.checked ? "block" : "none";
    });
    
    const elS4TtsEngine = document.getElementById("s4TtsEngine");
    const elGroupS4AutoClone = document.getElementById("groupS4AutoClone");
    elS4TtsEngine.addEventListener("change", () => {
        elGroupS4AutoClone.style.display = elS4TtsEngine.value === "clone" ? "block" : "none";
        
        // Auto set default voice depending on engine
        const voiceInput = document.getElementById("s4TtsVoice");
        if (elS4TtsEngine.value === "edge") {
            voiceInput.value = "vi-VN-NamMinhNeural";
        } else if (elS4TtsEngine.value === "kokoro") {
            voiceInput.value = "thuc_trinh";
        } else if (elS4TtsEngine.value === "vieneu") {
            voiceInput.value = "Ngọc Lan";
        } else if (elS4TtsEngine.value === "piper") {
            voiceInput.value = "vi_VN-vais1000-medium.onnx";
        } else {
            voiceInput.value = "";
        }
    });

    const elS4LlmEngine = document.getElementById("s4LlmEngine");
    const elGroupS4GeminiKey = document.getElementById("groupS4GeminiKey");
    const elGroupS4GeminiOfflineUrl = document.getElementById("groupS4GeminiOfflineUrl");
    const elGroupS4OllamaModel = document.getElementById("groupS4OllamaModel");
    const elGroupS4LlmModel = document.getElementById("groupS4LlmModel");
    
    elS4LlmEngine.addEventListener("change", () => {
        const eng = elS4LlmEngine.value;
        const isOllama = (eng === "ollama");
        elGroupS4GeminiKey.style.display = (eng === "gemini" || eng === "gemini_api") ? "block" : "none";
        elGroupS4GeminiOfflineUrl.style.display = (eng === "gemini_api" || isOllama) ? "block" : "none";
        elGroupS4OllamaModel.style.display = isOllama ? "block" : "none";
        elGroupS4LlmModel.style.display = isOllama ? "none" : "block";
        
        const modelInput = document.getElementById("s4LlmModel");
        if (eng === "gemini") {
            modelInput.value = "gemini-2.0-flash";
        } else {
            modelInput.value = "gemini-3-flash";
        }
        
        if (isOllama) {
            loadOllamaModels("s4OllamaModel", "s4OllamaStatus");
        }
    });

    // Subtitle customization styles toggles
    const elS4BgStyle = document.getElementById("s4BgStyle");
    const elGroupS4BgColor = document.getElementById("groupS4BgColor");
    const elGroupS4BgAlpha = document.getElementById("groupS4BgAlpha");
    
    elS4BgStyle.addEventListener("change", () => {
        const isBox = (elS4BgStyle.value === "Box");
        elGroupS4BgColor.style.display = isBox ? "block" : "none";
        elGroupS4BgAlpha.style.display = isBox ? "block" : "none";
    });
    
    const elS4SubPosition = document.getElementById("s4SubPosition");
    const elGroupS4CustomPosition = document.getElementById("groupS4CustomPosition");
    
    elS4SubPosition.addEventListener("change", () => {
        const isCustom = (elS4SubPosition.value === "custom");
        elGroupS4CustomPosition.style.display = isCustom ? "block" : "none";
    });

    const elBtnS4Prepare = document.getElementById("btnS4Prepare");
    const elS4RoiSelectionArea = document.getElementById("s4RoiSelectionArea");
    const elS4PreviewImg = document.getElementById("s4PreviewImg");
    
    elBtnS4Prepare.addEventListener("click", async () => {
        const isLocal = document.querySelector('input[name="s4VideoSource"]:checked').value === "local";
        const videoPath = document.getElementById("s4LocalPath").value.trim();
        const downloadUrl = document.getElementById("s4Url").value.trim();
        const platform = document.getElementById("s4Platform").value;
        
        if (isLocal && !videoPath) {
            return alert("Vui lòng nhập đường dẫn video cục bộ!");
        }
        if (!isLocal && !downloadUrl) {
            return alert("Vui lòng nhập link video tải về!");
        }
        
        elBtnS4Prepare.disabled = true;
        elBtnS4Prepare.textContent = "Đang tải & chuẩn bị...";
        clearConsole("step4");
        appendConsoleLog("step4", "[SYSTEM] Bắt đầu chuẩn bị video. Tiến trình này chạy prepare-only ở background thread...", "log-system");
        
        try {
            const body = {};
            if (isLocal) {
                body.video_path = videoPath;
            } else {
                body.download_url = downloadUrl;
                body.platform = platform;
                body.cookies_file = document.getElementById("s4CookiesFile").value.trim() || null;
            }
            
            const response = await fetch(`${API_BASE}/api/autosub/prepare`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body)
            });
            
            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || "Không thể chuẩn bị video.");
            }
            
            const data = await response.json();
            step4State.preparedPath = data.prepared_path;
            step4State.natW = data.width;
            step4State.natH = data.height;
            step4State.crop = null;
            
            // Set image preview
            elS4PreviewImg.src = data.preview_b64;
            elS4RoiSelectionArea.style.display = "block";
            
            // Remove old ROI boxes if any
            const oldBoxes = elS4PreviewImg.parentElement.querySelectorAll("div");
            oldBoxes.forEach(b => b.remove());
            
            // Setup ROI Selector
            setupRoiSelector(elS4PreviewImg, data.width, data.height, (crop) => {
                step4State.crop = crop;
                appendConsoleLog("step4", `[SYSTEM] Đã vẽ vùng OCR (pixel gốc): x=${crop.x}, y=${crop.y}, w=${crop.w}, h=${crop.h}`, "log-system");
            });
            
            appendConsoleLog("step4", `[THÀNH CÔNG] Đã chuẩn bị xong video! Kích thước: ${data.width}x${data.height}, Thời lượng: ${data.duration}s.`, "log-success");
            appendConsoleLog("step4", "Hãy vẽ khoanh vùng phụ đề trên ảnh preview để tiếp tục.", "log-system");
            
        } catch (err) {
            alert(`Lỗi chuẩn bị: ${err.message}`);
            appendConsoleLog("step4", `[ERROR] Chuẩn bị thất bại: ${err.message}`, "log-error");
        } finally {
            elBtnS4Prepare.disabled = false;
            elBtnS4Prepare.textContent = "Tải & Xem trước";
        }
    });

    document.getElementById("formStep4").addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const isLocal = document.querySelector('input[name="s4VideoSource"]:checked').value === "local";
        const videoPath = isLocal ? document.getElementById("s4LocalPath").value.trim() : step4State.preparedPath;
        const downloadUrl = isLocal ? "" : document.getElementById("s4Url").value.trim();
        const subSource = document.getElementById("s4SubSource").value;
        
        if (subSource === "ocr" && !videoPath) {
            return alert("Chế độ OCR yêu cầu chuẩn bị video trước bằng nút 'Tải & Xem trước'!");
        }
        
        if (isLocal && !videoPath) {
            return alert("Vui lòng nhập đường dẫn video!");
        }
        if (!isLocal && !downloadUrl && !videoPath) {
            return alert("Vui lòng nhập link video hoặc chuẩn bị video trước!");
        }
        
        const payload = {
            story_name: activeStoryName || null,
            video_path: videoPath || null,
            download_url: downloadUrl || null,
            platform: document.getElementById("s4Platform").value,
            source_lang: document.getElementById("s4SourceLang").value,
            sub_source: subSource,
            burn_method: document.getElementById("s4BurnMethod").value,
            clean_audio: document.getElementById("s4CleanAudio").checked,
            enable_voiceover: elS4EnableVoiceover.checked,
            tts_engine: elS4TtsEngine.value,
            tts_voice: document.getElementById("s4TtsVoice").value,
            auto_clone: document.getElementById("s4AutoClone").checked,
            ducking_ratio: parseFloat(document.getElementById("s4DuckingRatio").value),
            llm_engine: elS4LlmEngine.value,
            llm_api_key: document.getElementById("s4GeminiKey").value || null,
            llm_offline_base_url: document.getElementById("s4GeminiOfflineUrl").value || null,
            llm_offline_model: (elS4LlmEngine.value === "ollama"
                ? document.getElementById("s4OllamaModel").value
                : document.getElementById("s4LlmModel").value) || null,
            
            // Subtitle Customization Styling fields
            font_name: document.getElementById("s4FontName").value || null,
            font_size: document.getElementById("s4FontSize").value === "" ? null : parseInt(document.getElementById("s4FontSize").value),
            text_color: document.getElementById("s4TextColor").value || null,
            stroke_color: document.getElementById("s4StrokeColor").value || null,
            stroke_width: document.getElementById("s4StrokeWidth").value === "" ? null : parseFloat(document.getElementById("s4StrokeWidth").value),
            bg_style: document.getElementById("s4BgStyle").value || null,
            bg_color: document.getElementById("s4BgColor").value || null,
            bg_alpha: document.getElementById("s4BgAlpha").value === "" ? null : parseInt(document.getElementById("s4BgAlpha").value),
            sub_position: document.getElementById("s4SubPosition").value || null,
            custom_position: document.getElementById("s4CustomPosition").value === "" ? null : parseFloat(document.getElementById("s4CustomPosition").value),
            cookies_file: document.getElementById("s4CookiesFile").value.trim() || null,
            output_dir: document.getElementById("s4OutputDir")?.value.trim() || null
        };
        
        if (subSource === "ocr" && step4State.crop) {
            payload.crop_x = step4State.crop.x;
            payload.crop_y = step4State.crop.y;
            payload.crop_w = step4State.crop.w;
            payload.crop_h = step4State.crop.h;
        }
        
        toggleFormButtons("step4", true);
        clearConsole("step4");
        
        const taskKey = await postPipelineAction("step4", payload);
        if (taskKey) {
            currentTaskKeys["step4"] = taskKey;
            streamLogs("step4", taskKey);
        } else {
            toggleFormButtons("step4", false);
        }
    });
    
    document.getElementById("btnStopStep4").addEventListener("click", () => stopTaskByKey("step4"));

    // --- STEP 5 EVENT HANDLERS ---
    const elBtnS5LoadVideos = document.getElementById("btnS5LoadVideos");
    elBtnS5LoadVideos.addEventListener("click", () => {
        if (!activeStoryName) {
            return alert("Vui lòng chọn truyện trước!");
        }
        loadStoryVideos(activeStoryName);
    });
    
    document.getElementById("formStep5").addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!activeStoryName) return alert("Vui lòng chọn truyện trước!");
        
        const checkboxes = document.querySelectorAll('#s5VideoListContainer input[type="checkbox"]:checked');
        const selectedFiles = Array.from(checkboxes).map(cb => cb.value);
        
        if (selectedFiles.length < 2) {
            return alert("Vui lòng chọn ít nhất 2 video để ghép!");
        }
        
        const payload = {
            story_name: activeStoryName,
            selected_files: selectedFiles
        };
        
        toggleFormButtons("step5", true);
        clearConsole("step5");
        
        const taskKey = await postPipelineAction("step5", payload);
        if (taskKey) {
            currentTaskKeys["step5"] = taskKey;
            streamLogs("step5", taskKey);
        } else {
            toggleFormButtons("step5", false);
        }
    });

    document.getElementById("btnStopStep5").addEventListener("click", () => {
        appendConsoleLog("step5", "[SYSTEM] Tiến trình ghép video chạy bằng thread không thể dừng cưỡng bức.", "log-warn");
    });

    // Lưu toàn bộ cấu hình + chuỗi Chạy tự động 1→4 (nút trên top-header)
    document.getElementById("btnSaveSettings")?.addEventListener("click", saveAllSettings);
    document.getElementById("btnAutoRun")?.addEventListener("click", startAutoRun);
    document.getElementById("btnStopAutoRun")?.addEventListener("click", stopAutoRun);
}

// Common function to send pipeline actions to the backend
async function postPipelineAction(stepName, payload) {
    try {
        const response = await fetch(`${API_BASE}/api/pipeline/${stepName}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            const err = await response.json();
            alert(`Lỗi khởi chạy: ${err.detail}`);
            return null;
        }

        const data = await response.json();
        return data.task_key;
    } catch (e) {
        alert("Lỗi kết nối tới Server: " + e);
        return null;
    }
}

// Stop pipeline action
async function stopPipelineTask(stepName, stepNum) {
    if (!activeStoryName) return;
    try {
        const response = await fetch(`${API_BASE}/api/pipeline/stop?story_name=${encodeURIComponent(activeStoryName)}&step=${stepNum}`, {
            method: "POST"
        });
        const res = await response.json();
        if (res.status === "success") {
            appendConsoleLog(stepName, "[SYSTEM] Đã gửi yêu cầu dừng tiến trình thành công.", "log-system");
            waitTaskStopped(stepName, res.task_key || "");
        } else {
            alert("Không thể dừng tiến trình: " + res.detail);
        }
    } catch (e) {
        alert("Lỗi khi dừng tiến trình: " + e);
    }
}

// Dynamic display of stop and run buttons depending on state
function toggleFormButtons(stepName, isRunning) {
    const btnStart = document.getElementById(`btnStartStep${stepName.slice(-1)}`);
    const btnStop = document.getElementById(`btnStopStep${stepName.slice(-1)}`);
    
    if (isRunning) {
        btnStart.style.display = "none";
        btnStop.style.display = "block";
    } else {
        btnStart.style.display = "block";
        btnStop.style.display = "none";
    }
}

// Clean log terminal
function clearConsole(stepName) {
    const consoleBox = document.getElementById(`logConsole-${stepName}`);
    if (consoleBox) consoleBox.innerHTML = "";
}

// Output formatted SSE logs to console
// Giới hạn số dòng log giữ trong DOM. Render 1 chương có thể phun hàng chục nghìn
// dòng (tiến trình diffusion mỗi cảnh); nếu không cắt bớt, WebView2 phình bộ nhớ
// tới mức "Out of Memory" và sập trang. Giữ ~4000 span cuối là quá đủ để theo dõi.
const MAX_CONSOLE_LINES = 4000;

function appendConsoleLog(stepName, text, className = "") {
    const consoleBox = document.getElementById(`logConsole-${stepName}`);
    if (!consoleBox) return;
    
    const span = document.createElement("span");
    if (className) span.className = className;
    span.textContent = text;
    consoleBox.appendChild(span);

    // Cắt bớt các dòng cũ nhất khi vượt trần (chống rò rỉ bộ nhớ renderer).
    let overflow = consoleBox.childElementCount - MAX_CONSOLE_LINES;
    while (overflow-- > 0 && consoleBox.firstChild) {
        consoleBox.removeChild(consoleBox.firstChild);
    }
    
    // Auto scroll to bottom
    consoleBox.scrollTop = consoleBox.scrollHeight;
}

// Stream logs from Server-Sent Events (SSE)
function streamLogs(stepName, taskKey) {
    if (currentLogsSse) {
        currentLogsSse.close();
    }

    appendConsoleLog(stepName, `[SYSTEM] Đang mở luồng EventSource kết nối tới logs task: ${taskKey}...`, "log-system");
    const source = new EventSource(`${API_BASE}/api/pipeline/logs/${encodeURIComponent(taskKey)}`);
    currentLogsSse = source;
    let terminalReceived = false;
    let reconnectNoticeShown = false;
    let statusCheckInFlight = false;

    source.onopen = () => {
        reconnectNoticeShown = false;
    };

    source.onmessage = (event) => {
        if (currentLogsSse !== source || terminalReceived) return;
        const rawLine = event.data;
        if (rawLine === "[PING]") return; // Keep-alive signal
        
        if (rawLine.startsWith("[SYSTEM] Process completed")) {
            terminalReceived = true;
            const exitMatch = rawLine.match(/exit_code=(-?\d+)/);
            const terminalOk = !exitMatch || Number(exitMatch[1]) === 0;
            appendConsoleLog(
                stepName,
                terminalOk ? "[SYSTEM] Quy trình hoàn thành xong."
                           : `[SYSTEM ERROR] Quy trình kết thúc với mã lỗi ${exitMatch[1]}.`,
                terminalOk ? "log-success" : "log-error"
            );
            source.close();
            if (currentLogsSse === source) currentLogsSse = null;
            toggleFormButtons(stepName, false);
            loadStories(); // Reload to capture status changes
            return;
        }

        // Color coding depending on stdout messages
        let logClass = "";
        let displayText = rawLine;

        try {
            const parsed = JSON.parse(rawLine);
            if (parsed.event) {
                switch(parsed.event) {
                    case "crawl_start":
                        displayText = `[HỆ THỐNG] Bắt đầu cào truyện. Nguồn: ${parsed.source}, Thư mục lưu: ${parsed.output_dir}`;
                        logClass = "log-system";
                        break;
                    case "crawl_completed":
                        displayText = `[THÀNH CÔNG] Quá trình cào hoàn tất.`;
                        logClass = "log-success";
                        break;
                    case "crawl_failed":
                        displayText = `[LỖI CÀO TRUYỆN] ${parsed.error}`;
                        logClass = "log-error";
                        break;
                    case "translate_start":
                        displayText = `[HỆ THỐNG] Bắt đầu tiến trình dịch. Tổng số file: ${parsed.total_files}, Engine: ${parsed.engine}`;
                        logClass = "log-system";
                        break;
                    case "file_start":
                        displayText = `[DỊCH] Đang xử lý file ${parsed.index}/${parsed.total}: ${parsed.original}...`;
                        break;
                    case "file_log":
                        displayText = parsed.message;
                        break;
                    case "file_success":
                        displayText = `[THÀNH CÔNG] Đã dịch xong file: ${parsed.file}`;
                        logClass = "log-success";
                        break;
                    case "file_failed":
                        displayText = `[CẢNH BÁO] File ${parsed.file} dịch hoàn tất nhưng có ${parsed.failed_paragraphs}/${parsed.total_paragraphs} đoạn dịch lỗi/không thành công (đã giữ nguyên bản gốc).`;
                        logClass = "log-warn";
                        break;
                    case "translate_completed":
                        displayText = `[THÀNH CÔNG] Tiến trình dịch hoàn tất!`;
                        logClass = "log-success";
                        break;
                    case "translate_warn":
                        displayText = `[CẢNH BÁO] ${parsed.message}`;
                        logClass = "log-warn";
                        break;
                    case "file_repair_start": {
                        const roundInfo = parsed.round ? ` (Vòng ${parsed.round}/${parsed.max_rounds})` : "";
                        displayText = `[DỊCH VÁ] File ${parsed.file} có ${parsed.failed_paragraphs} đoạn lỗi. Đang tự động dịch lại${roundInfo}...`;
                        logClass = "log-warn";
                        break;
                    }
                    case "file_repair_done": {
                        const roundLabel = parsed.round ? ` (vòng ${parsed.round})` : "";
                        if (parsed.still_failed > 0) {
                            displayText = `[DỊCH VÁ] Đã vá ${parsed.repaired} đoạn${roundLabel}, còn ${parsed.still_failed} đoạn lỗi trong file ${parsed.file}.`;
                            logClass = "log-warn";
                        } else {
                            displayText = `[THÀNH CÔNG] Đã dịch vá toàn bộ ${parsed.repaired} đoạn lỗi của file ${parsed.file}${roundLabel}.`;
                            logClass = "log-success";
                        }
                        break;
                    }
                    case "file_repair_warn":
                        displayText = `[CẢNH BÁO] Lỗi khi dịch vá file ${parsed.file} (vòng ${parsed.round || "?"}): ${parsed.error}`;
                        logClass = "log-warn";
                        break;
                    case "translate_failed":
                        displayText = `[LỖI DỊCH] Tiến trình dịch bị lỗi: ${parsed.error}`;
                        logClass = "log-danger";
                        break;
                    case "tts_file_start":
                        displayText = `[TTS] Đang sinh giọng đọc file ${parsed.index}/${parsed.total}: ${parsed.file}...`;
                        break;
                    case "tts_file_success":
                        displayText = `[THÀNH CÔNG] Đã sinh giọng đọc xong file: ${parsed.file}`;
                        logClass = "log-success";
                        break;
                    case "tts_file_failed":
                        displayText = `[LỖI TTS] Không thể sinh giọng đọc cho file: ${parsed.file}`;
                        logClass = "log-danger";
                        break;
                    case "tts_batch_completed":
                        displayText = `[THÀNH CÔNG] Tiến trình TTS hoàn tất!`;
                        logClass = "log-success";
                        break;
                    case "tts_file_skip":
                        displayText = `[CẢNH BÁO] Bỏ qua file ${parsed.file}: ${parsed.reason}`;
                        logClass = "log-warn";
                        break;
                    case "autosub_init":
                        displayText = `[HỆ THỐNG] Khởi tạo quy trình phụ đề: ${parsed.video_path || ''}`;
                        logClass = "log-system";
                        break;
                    case "download_start":
                        displayText = `[HỆ THỐNG] Bắt đầu tải video từ URL: ${parsed.url}`;
                        logClass = "log-system";
                        break;
                    case "download_progress":
                        displayText = `[TẢI VIDEO] Tiến trình: ${parsed.percent}% | Tốc độ: ${parsed.speed || 'N/A'} | ETA: ${parsed.eta || 0}s`;
                        break;
                    case "download_done":
                        displayText = `[THÀNH CÔNG] Đã tải video thành công: ${parsed.path}`;
                        logClass = "log-success";
                        break;
                    case "download_error":
                        displayText = `[LỖI TẢI VIDEO] ${parsed.error}`;
                        logClass = "log-error";
                        break;
                    case "ocr_start":
                        displayText = `[OCR] Bắt đầu trích xuất chữ hardsub từ hình...`;
                        logClass = "log-system";
                        break;
                    case "ocr_roi":
                        displayText = `[OCR ROI] Vùng chọn: x=${parsed.crop_x}, y=${parsed.crop_y}, w=${parsed.crop_width}, h=${parsed.crop_height}`;
                        break;
                    case "ocr_progress":
                        displayText = `[OCR] ${parsed.message}`;
                        break;
                    case "ocr_done":
                        displayText = `[THÀNH CÔNG] Đã trích xuất phụ đề OCR xong: ${parsed.output_srt}`;
                        logClass = "log-success";
                        break;
                    case "ocr_error":
                        displayText = `[LỖI OCR] ${parsed.error}`;
                        logClass = "log-error";
                        break;
                    case "autosub_progress":
                        displayText = `[AUTOSUB] ${parsed.message} (${parsed.percent}%)`;
                        break;
                    case "autosub_done":
                        displayText = `[THÀNH CÔNG] Quy trình phụ đề hoàn tất. Video đầu ra: ${parsed.output}`;
                        logClass = "log-success";
                        break;
                    case "autosub_error":
                        displayText = `[LỖI AUTOSUB] ${parsed.error}`;
                        logClass = "log-error";
                        break;
                    case "autosub_warn":
                        displayText = `[CẢNH BÁO AUTOSUB] ${parsed.message}`;
                        logClass = "log-warn";
                        break;
                    default:
                        displayText = rawLine;
                }
            }
        } catch(e) {
            // Not JSON, fallback to text matching
            if (rawLine.includes("[ERROR]") || rawLine.includes("[✗]") || rawLine.includes("Traceback") || rawLine.includes("Error:") || rawLine.includes("[LỖI")) {
                logClass = "log-error";
            } else if (rawLine.includes("[✓]") || rawLine.includes("Success:") || rawLine.includes("[THÀNH CÔNG]")) {
                logClass = "log-success";
            } else if (rawLine.includes("[WARN]") || rawLine.includes("[!]") || rawLine.includes("[CẢNH BÁO]")) {
                logClass = "log-warn";
            } else if (rawLine.startsWith("[SYSTEM]") || rawLine.startsWith("[HỆ THỐNG]")) {
                logClass = "log-system";
            }
        }

        appendConsoleLog(stepName, displayText, logClass);
    };

    source.onerror = async () => {
        if (currentLogsSse !== source || terminalReceived || statusCheckInFlight) return;
        statusCheckInFlight = true;

        try {
            const response = await fetch(
                `${API_BASE}/api/pipeline/status/${encodeURIComponent(taskKey)}`,
                { cache: "no-store" }
            );
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const status = await response.json();
            // Trong lúc fetch, terminal cũ có thể đã tới hoặc người dùng đã
            // khởi động task mới. Handler cũ tuyệt đối không được đổi UI mới.
            if (currentLogsSse !== source || terminalReceived) return;

            if (status.completed) {
                terminalReceived = true;
                source.close();
                if (currentLogsSse === source) currentLogsSse = null;
                const ok = status.exit_code === 0;
                appendConsoleLog(
                    stepName,
                    ok ? "[SYSTEM] Quy trình đã hoàn thành; luồng log đã đóng."
                       : `[SYSTEM ERROR] Quy trình kết thúc với mã lỗi ${status.exit_code}.`,
                    ok ? "log-success" : "log-error"
                );
                toggleFormButtons(stepName, false);
                loadStories();
                return;
            }

            if (status.running) {
                if (!reconnectNoticeShown) {
                    reconnectNoticeShown = true;
                    appendConsoleLog(
                        stepName,
                        "[SYSTEM] Luồng log tạm gián đoạn; máy chủ vẫn chạy và EventSource đang tự kết nối lại...",
                        "log-warn"
                    );
                }
                return; // Giữ EventSource mở để trình duyệt tự reconnect.
            }

            source.close();
            if (currentLogsSse === source) currentLogsSse = null;
            appendConsoleLog(
                stepName,
                "[SYSTEM] Luồng log đã đóng và task không còn chạy. Đang tải lại trạng thái.",
                "log-warn"
            );
            toggleFormButtons(stepName, false);
            loadStories();
        } catch (error) {
            if (currentLogsSse !== source || terminalReceived) return;
            source.close();
            if (currentLogsSse === source) currentLogsSse = null;
            appendConsoleLog(
                stepName,
                `[SYSTEM ERROR] Không liên lạc được máy chủ khi kiểm tra SSE: ${error.message}`,
                "log-error"
            );
            toggleFormButtons(stepName, false);
        } finally {
            statusCheckInFlight = false;
        }
    };
}

// Load danh sách model Ollama (model đã cài + model khuyến nghị) vào dropdown.
// Dùng chung cho Bước 1 (s1OllamaModel) và Bước 3 (s3OllamaModel).
async function loadOllamaModels(selectId = "s1OllamaModel", statusId = "s1OllamaStatus") {
    const sel = document.getElementById(selectId);
    const status = document.getElementById(statusId);
    if (!sel) return;
    const previous = sel.value;
    try {
        const res = await fetch(`${API_BASE}/api/ollama/models`);
        const data = await res.json();
        const models = data.models || [];
        if (models.length > 0) {
            sel.innerHTML = "";
            models.forEach(m => {
                const opt = document.createElement("option");
                opt.value = m.name;
                let text = m.name;
                if (m.label) text += ` — ${m.label}`;
                if (!m.installed) text += " (chưa cài, cần: ollama pull)";
                opt.textContent = text;
                sel.appendChild(opt);
            });
            // Giữ lại lựa chọn trước đó nếu vẫn tồn tại
            if (previous && [...sel.options].some(o => o.value === previous)) {
                sel.value = previous;
            } else {
                const firstInstalled = models.find(m => m.installed);
                if (firstInstalled) sel.value = firstInstalled.name;
            }
        }
        if (status) {
            status.textContent = data.ollama_online
                ? `Ollama đang chạy — ${models.filter(m => m.installed).length} model đã cài.`
                : "Không kết nối được Ollama (http://localhost:11434). Hãy mở Ollama trước khi dịch.";
            status.style.color = data.ollama_online ? "" : "#e0a800";
        }
    } catch (e) {
        if (status) {
            status.textContent = "Không tải được danh sách model (server orchestrator chưa chạy?).";
            status.style.color = "#e0a800";
        }
    }
}

// Load danh sách model Ollama cho trích xuất Glossary
async function loadGlossaryOllamaModels() {
    const sel = document.getElementById("s1GlossaryOllamaModel");
    if (!sel) return;
    const previous = sel.value;
    try {
        const res = await fetch(`${API_BASE}/api/ollama/models`);
        const data = await res.json();
        const models = data.models || [];
        sel.innerHTML = "";
        
        const optDefault = document.createElement("option");
        optDefault.value = "";
        optDefault.textContent = "Sử dụng Model mặc định của Ollama";
        sel.appendChild(optDefault);
        
        models.forEach(m => {
            const opt = document.createElement("option");
            opt.value = m.name;
            let text = m.name;
            if (m.label) text += ` — ${m.label}`;
            if (!m.installed) text += " (chưa cài, cần: ollama pull)";
            opt.textContent = text;
            sel.appendChild(opt);
        });
        
        if (previous && [...sel.options].some(o => o.value === previous)) {
            sel.value = previous;
        }
    } catch (e) {
        console.error("Không tải được danh sách model cho glossary: ", e);
    }
}

// Load Global Configuration from database
// ==========================================================================
// Cấu Hình Chung "mirror toàn bộ": tiện ích đọc/ghi theo đường dẫn + nhân bản
// control của từng bước vào tab Cấu Hình để chỉnh MẶC ĐỊNH dùng chung.
// ==========================================================================
let _globalConfig = {};

function cfgGetByPath(obj, path) {
    return path.split(".").reduce((o, k) => (o == null ? undefined : o[k]), obj);
}
function cfgSetByPath(obj, path, val) {
    const keys = path.split(".");
    let o = obj;
    for (let i = 0; i < keys.length - 1; i++) {
        if (typeof o[keys[i]] !== "object" || o[keys[i]] == null) o[keys[i]] = {};
        o = o[keys[i]];
    }
    o[keys[keys.length - 1]] = val;
}
function cfgReadField(el) {
    if (el.type === "checkbox") return el.checked;
    if (el.type === "number") {
        if (el.value === "") return null;
        const n = parseFloat(el.value);
        return isNaN(n) ? el.value : n;
    }
    return el.value;
}
function cfgWriteField(el, v) {
    if (el.type === "checkbox") { el.checked = !!v; return; }
    if (el.tagName === "SELECT" && v !== "" && v != null &&
        ![...el.options].some(o => o.value === String(v))) {
        const opt = document.createElement("option");
        opt.value = String(v); opt.textContent = String(v);
        el.appendChild(opt);
    }
    el.value = v;
}

// Nhân bản control gốc của từng bước vào các placeholder .cfg-clone trong tab
// Cấu Hình. Placeholder mang: data-clone (id control gốc) + data-cfg (đường dẫn
// trong global_config) + tùy chọn data-seed (mặc định gieo về chính control gốc).
function buildConfigMirror() {
    document.querySelectorAll(".cfg-clone[data-clone]").forEach(ph => {
        const src = document.getElementById(ph.dataset.clone);
        if (!src) return;
        const clone = src.cloneNode(true);   // copy đúng loại control + toàn bộ <option>
        clone.id = "cfg_" + ph.dataset.clone;
        clone.removeAttribute("required");
        clone.removeAttribute("name");
        clone.querySelectorAll?.("[id]").forEach(el => el.removeAttribute("id"));
        if (ph.dataset.cfg) clone.dataset.cfg = ph.dataset.cfg;
        clone.dataset.seed = ph.dataset.seed || ph.dataset.clone;  // gieo về control gốc
        ph.replaceWith(clone);
    });
}

// Gieo MẶC ĐỊNH từ các field Cấu Hình Chung vào form của từng bước. Control
// engine đặt trước field phụ thuộc trong HTML nên dispatch 'change' của nó
// (ẩn/hiện, tự đặt voice) chạy trước, rồi field phụ thuộc ghi đè lại.
function applyConfigDefaultsToSteps() {
    document.querySelectorAll("#formSettings [data-seed]").forEach(el => {
        const tgt = document.getElementById(el.dataset.seed);
        if (!tgt) return;
        cfgWriteField(tgt, cfgReadField(el));
        tgt.dispatchEvent(new Event("change", { bubbles: true }));
    });
    seedS2VoiceFromConfig();  // giọng đọc phụ thuộc engine -> gieo sau cùng
}

// s2Voice được engine dựng lại option khi 'change'; chọn giọng đúng theo engine
// từ cấu hình (kokoro_voice / vieneu_voice / default_voice) sau khi engine đã seed.
function seedS2VoiceFromConfig() {
    const s2Voice = document.getElementById("s2Voice");
    if (!s2Voice) return;
    const engine = document.getElementById("cfgTtsEngine")?.value || "edge";
    if (engine === "kokoro") {
        s2Voice.value = document.getElementById("cfgTtsKokoroVoice")?.value || "thuc_trinh";
    } else if (engine === "vieneu") {
        s2Voice.value = document.getElementById("cfgTtsVieneuVoice")?.value
            || document.getElementById("cfgTtsVoice")?.value || "Ngọc Lan";
        const mode = document.getElementById("s2VieneuMode");
        if (mode) mode.value = document.getElementById("cfgTtsVieneuMode")?.value || "v3turbo";
    } else {
        s2Voice.value = document.getElementById("cfgTtsVoice")?.value || "vi-VN-NamMinhNeural";
    }
}

async function loadGlobalConfig() {
    try {
        const response = await fetch(`${API_BASE}/api/config`);
        const config = await response.json();
        _globalConfig = config || {};

        // 1) Nạp mọi field trong Cấu Hình Chung theo data-cfg
        document.querySelectorAll("#formSettings [data-cfg]").forEach(el => {
            const v = cfgGetByPath(config, el.dataset.cfg);
            if (v !== undefined && v !== null) cfgWriteField(el, v);
        });

        // 2) Gieo MẶC ĐỊNH vào field của từng bước
        applyConfigDefaultsToSteps();

        // 3) Gieo chuyên biệt cho khóa API/URL Bước 1 (chỉ khi field còn trống,
        //    tránh ghi đè key người dùng đã nhập riêng cho bước này).
        if (!document.getElementById("s1GeminiOfflineUrl").value) {
            document.getElementById("s1GeminiOfflineUrl").value = config.crawler?.gemini_offline_base_url || "http://localhost:7860/v1";
        }
        if (!document.getElementById("s1GeminiKey").value && config.api_keys?.gemini) {
            document.getElementById("s1GeminiKey").value = config.api_keys.gemini;
        }
    } catch (e) {
        console.error("Lỗi khi tải cấu hình chung:", e);
    }
}

function setupRoiSelector(imgEl, natW, natH, onChange) {
    const box = document.createElement("div");
    box.style.cssText = "position:absolute;border:2px dashed #4ade80;background:rgba(74,222,128,.15);pointer-events:none;display:none;z-index:10;";
    imgEl.parentElement.appendChild(box);
    let sx = 0, sy = 0, drag = false, rect = null;
    const rel = (e) => {
        const r = imgEl.getBoundingClientRect();
        return [Math.min(Math.max(e.clientX - r.left, 0), r.width),
                Math.min(Math.max(e.clientY - r.top, 0), r.height)];
    };
    imgEl.addEventListener("mousedown", (e) => {
        [sx, sy] = rel(e);
        drag = true;
        rect = null;
        box.style.display = "none";
        e.preventDefault();
    });
    window.addEventListener("mousemove", (e) => {
        if (!drag) return;
        const [x, y] = rel(e);
        rect = { x: Math.min(sx, x), y: Math.min(sy, y), w: Math.abs(x - sx), h: Math.abs(y - sy) };
        Object.assign(box.style, { display: "block", left: rect.x + "px", top: rect.y + "px",
                                   width: rect.w + "px", height: rect.h + "px" });
    });
    window.addEventListener("mouseup", () => {
        if (!drag) return;
        drag = false;
        if (rect && rect.w > 5 && rect.h > 5) {
            const r = imgEl.getBoundingClientRect(), kx = natW / r.width, ky = natH / r.height;
            onChange({ x: Math.round(rect.x * kx), y: Math.round(rect.y * ky),
                       w: Math.round(rect.w * kx), h: Math.round(rect.h * ky) });  // PIXEL GỐC
        }
    });
}

async function stopTaskByKey(stepName) {
    const key = currentTaskKeys[stepName];
    if (!key) return;
    try {
        const res = await fetch(`${API_BASE}/api/pipeline/stop-task?task_key=${encodeURIComponent(key)}`, { method: "POST" });
        const data = await res.json();
        appendConsoleLog(stepName, res.ok ? "[SYSTEM] Đã gửi yêu cầu dừng." : `[SYSTEM] Không dừng được: ${data.detail}`, "log-system");
        if (res.ok) waitTaskStopped(stepName, key);
    } catch(e) {
        appendConsoleLog(stepName, `[SYSTEM ERROR] Lỗi khi dừng: ${e}`, "log-error");
    }
}

async function loadStoryVideos(storyName) {
    const container = document.getElementById("s5VideoListContainer");
    if (!container) return;
    
    container.innerHTML = "<p class='help-text' style='text-align:center;'>Đang tải danh sách video...</p>";
    
    try {
        const res = await fetch(`${API_BASE}/api/stories/${encodeURIComponent(storyName)}/videos`);
        if (!res.ok) {
            throw new Error("Không thể tải danh sách video.");
        }
        const videos = await res.json();
        
        if (!videos || videos.length === 0) {
            container.innerHTML = "<p class='help-text' style='text-align:center;'>Không tìm thấy video nào trong thư mục video của truyện này.</p>";
            document.getElementById("btnStartStep5").disabled = true;
            return;
        }
        
        container.innerHTML = "";
        
        videos.forEach(v => {
            const div = document.createElement("div");
            div.style.cssText = "display: flex; align-items: center; margin-bottom: 8px; font-size: 14px;";
            
            const cb = document.createElement("input");
            cb.type = "checkbox";
            cb.value = v.name;
            cb.id = `cb_video_${v.name.replace(/\./g, '_')}`;
            cb.checked = !v.is_merged;
            cb.style.marginRight = "10px";
            
            const label = document.createElement("label");
            label.htmlFor = cb.id;
            label.style.cursor = "pointer";
            
            const sizeMB = (v.size / (1024 * 1024)).toFixed(2);
            const tag = v.is_merged ? " <span style='color:#f59e0b;'>[ĐÃ GHÉP]</span>" : "";
            label.innerHTML = `${v.name} <small style='opacity:0.6;'>(${sizeMB} MB)</small>${tag}`;
            
            div.appendChild(cb);
            div.appendChild(label);
            container.appendChild(div);
            
            cb.addEventListener("change", updateStep5ButtonState);
        });
        
        updateStep5ButtonState();
        
    } catch (err) {
        container.innerHTML = `<p class='help-text' style='color:#f87171; text-align:center;'>Lỗi: ${err.message}</p>`;
        document.getElementById("btnStartStep5").disabled = true;
    }
}

function updateStep5ButtonState() {
    const checkboxes = document.querySelectorAll('#s5VideoListContainer input[type="checkbox"]:checked');
    const btn = document.getElementById("btnStartStep5");
    if (btn) {
        btn.disabled = checkboxes.length < 2;
    }
}

// ===== Dashboard / Thống kê (A4) =====
function _statEsc(t) {
    return (t == null ? "" : String(t)).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
async function loadStats() {
    try {
        const r = await fetch(`${API_BASE}/api/stats`, { cache: "no-store" });
        const d = await r.json();
        const dirEl = document.getElementById("statsStorageDir");
        if (dirEl) dirEl.textContent = d.storage_dir || "—";
        const cards = [
            ["Bộ truyện", d.total_stories], ["Chương", d.total_chapters],
            ["Video hoàn tất", d.videos_done], ["Job lỗi", d.jobs_failed],
        ];
        document.getElementById("statsCards").innerHTML = cards.map(([lbl, val]) =>
            `<div class="stat-card"><div class="stat-value">${val ?? 0}</div><div class="stat-label">${lbl}</div></div>`).join("");
        const rows = (d.stories || []).map(s =>
            `<tr><td>${_statEsc(s.name || s.slug)}</td><td>${_statEsc(s.status || "")}</td><td>${s.chapter_count ?? 0}</td><td>${_statEsc((s.updated_at || "").slice(0, 16).replace("T", " "))}</td></tr>`).join("");
        document.getElementById("statsStoriesBody").innerHTML = rows ||
            `<tr><td colspan="4" style="color:var(--text-muted)">Chưa có dữ liệu</td></tr>`;
    } catch (e) {
        document.getElementById("statsCards").innerHTML = `<div style="color:var(--danger)">Lỗi tải thống kê: ${e}</div>`;
    }
}
async function previewCleanup() {
    const el = document.getElementById("cleanupInfo");
    el.textContent = "Đang kiểm tra...";
    try {
        const r = await fetch(`${API_BASE}/api/maintenance/cleanup-tasks?dry_run=true`, { method: "POST" });
        const d = await r.json();
        el.innerHTML = `Có <strong>${d.count}</strong> thư mục tạm, sẽ giải phóng ~<strong>${d.freed_mb} MB</strong>. Tri thức nhân vật/LoRA được giữ nguyên.`;
    } catch (e) { el.textContent = "Lỗi: " + e; }
}
async function doCleanup() {
    if (!confirm("Xóa các thư mục làm việc tạm (khung ảnh trung gian)?\nTri thức nhân vật/LoRA được giữ nguyên. Thao tác không hoàn tác.")) return;
    const el = document.getElementById("cleanupInfo");
    el.textContent = "Đang dọn dẹp...";
    try {
        const r = await fetch(`${API_BASE}/api/maintenance/cleanup-tasks?dry_run=false`, { method: "POST" });
        const d = await r.json();
        el.innerHTML = `✅ Đã xóa <strong>${d.count}</strong> thư mục, giải phóng ~<strong>${d.freed_mb} MB</strong>.`;
    } catch (e) { el.textContent = "Lỗi: " + e; }
}
async function rebuildStatsDb() {
    try {
        const r = await fetch(`${API_BASE}/api/maintenance/rebuild-db`, { method: "POST" });
        const d = await r.json();
        alert(`Đã đồng bộ ${d.synced} truyện vào CSDL.`);
        loadStats();
    } catch (e) { alert("Lỗi: " + e); }
}
document.querySelector('.nav-item[data-tab="stats"]')?.addEventListener("click", loadStats);
