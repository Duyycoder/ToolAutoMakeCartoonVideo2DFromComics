// API Base URL
const API_BASE = "";

// Global State
let activeStoryName = "";
let currentLogsSse = null;

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
document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    loadStories();
    loadGlobalConfig();
    fetchGpuInfo();
    setupEventHandlers();
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
    
    if (val === 'local') {
        if(storyIdGroup) storyIdGroup.style.display = 'none';
        if(localFolderGroup) localFolderGroup.style.display = 'block';
        if(storyIdInput) storyIdInput.removeAttribute('required');
        if(localFolderInput) localFolderInput.setAttribute('required', 'true');
    } else {
        if(storyIdGroup) storyIdGroup.style.display = 'block';
        if(localFolderGroup) localFolderGroup.style.display = 'none';
        if(storyIdInput) storyIdInput.setAttribute('required', 'true');
        if(localFolderInput) localFolderInput.removeAttribute('required');
    }
});

// Select a story and load its metadata details
async function selectStory(storyName) {
    activeStoryName = storyName;
    try {
        const response = await fetch(`${API_BASE}/api/stories/${encodeURIComponent(storyName)}`);
        const meta = await response.json();
        
        elActiveStoryTitle.textContent = meta.story_name;
        elActiveStorySubtitle.textContent = `Thư mục lưu trữ: ${meta.story_dir} | Chương đã cào: ${meta.raw_chapters_count || 0}`;
        
        // Update badge status
        updateStatusBadge(meta.status);
    } catch (e) {
        console.error("Lỗi khi chọn truyện:", e);
    }
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
        
        const payload = {
            story_name: activeStoryName,
            source_site: document.getElementById("s1Source").value,
            base_url: document.getElementById("s1BaseUrl")?.value || null,
            story_id: document.getElementById("s1StoryId").value,
            local_folder: document.getElementById("s1LocalFolder")?.value,
            start_chapter_id: document.getElementById("s1StartChapterId").value || null,
            max_chapters: parseInt(document.getElementById("s1NumChapters").value) || 1,
            engine: elS1Engine.value,
            ollama_model: document.getElementById("s1OllamaModel").value,
            gemini_api_key: (elS1Engine.value === "gemini" || elS1Engine.value === "gemini_api")
                ? (document.getElementById("s1GeminiKey").value || "") : "",
            gemini_offline_base_url: document.getElementById("s1GeminiOfflineUrl")?.value || "",
            gemini_offline_model: document.getElementById("s1GeminiOfflineModel")?.value || "",
            genre: document.getElementById("s1Genre").value,
            auto_extract: document.getElementById("s1AutoExtract").checked,
            auto_translate: document.getElementById("s1AutoTranslate")?.checked,
            continue_download: document.getElementById("s1ContinueDownload")?.checked
        };

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

        const payload = {
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

        const payload = {
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
            hardware_profile: document.getElementById("s3HardwareProfile").value,
            device: document.getElementById("s3GpuDevice").value
        };

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
        const payload = {
            api_keys: {
                gemini: document.getElementById("cfgGeminiKey").value
            },
            storage_dir: document.getElementById("cfgStorageDir").value,
            crawler: {
                default_site: document.getElementById("cfgDefaultSite").value,
                gemini_offline_base_url: document.getElementById("cfgGeminiOfflineUrl").value
            },
            tts: {
                default_engine: document.getElementById("cfgTtsEngine").value,
                default_voice: document.getElementById("cfgTtsVoice").value,
                normalize: document.getElementById("cfgTtsNormalize").checked,
                speed: parseFloat(document.getElementById("cfgTtsSpeed").value)
            },
            video: {
                default_style: document.getElementById("cfgVideoStyle").value,
                use_gpu: document.getElementById("cfgVideoGpu").checked
            }
        };

        try {
            const response = await fetch(`${API_BASE}/api/config`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const res = await response.json();
            if (res.status === "success") {
                alert("Đã lưu cấu hình thành công!");
            }
        } catch (e) {
            alert("Lỗi khi lưu cấu hình: " + e);
        }
    });
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
function appendConsoleLog(stepName, text, className = "") {
    const consoleBox = document.getElementById(`logConsole-${stepName}`);
    if (!consoleBox) return;
    
    const span = document.createElement("span");
    if (className) span.className = className;
    span.textContent = text;
    consoleBox.appendChild(span);
    
    // Auto scroll to bottom
    consoleBox.scrollTop = consoleBox.scrollHeight;
}

// Stream logs from Server-Sent Events (SSE)
function streamLogs(stepName, taskKey) {
    if (currentLogsSse) {
        currentLogsSse.close();
    }

    appendConsoleLog(stepName, `[SYSTEM] Đang mở luồng EventSource kết nối tới logs task: ${taskKey}...`, "log-system");
    currentLogsSse = new EventSource(`${API_BASE}/api/pipeline/logs/${encodeURIComponent(taskKey)}`);

    currentLogsSse.onmessage = (event) => {
        const rawLine = event.data;
        if (rawLine === "[PING]") return; // Keep-alive signal
        
        if (rawLine.startsWith("[SYSTEM] Process completed.")) {
            appendConsoleLog(stepName, "[SYSTEM] Quy trình hoàn thành xong.", "log-success");
            currentLogsSse.close();
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

    currentLogsSse.onerror = (e) => {
        appendConsoleLog(stepName, "[SYSTEM ERROR] Đứt kết nối luồng logs SSE. Kiểm tra trạng thái máy chủ.", "log-error");
        currentLogsSse.close();
        toggleFormButtons(stepName, false);
        loadStories();
    };
}

// Load danh sách model Ollama (model đã cài + model khuyến nghị) vào dropdown
async function loadOllamaModels() {
    const sel = document.getElementById("s1OllamaModel");
    const status = document.getElementById("s1OllamaStatus");
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

// Load Global Configuration from database
async function loadGlobalConfig() {
    try {
        const response = await fetch(`${API_BASE}/api/config`);
        const config = await response.json();
        
        document.getElementById("cfgGeminiKey").value = config.api_keys?.gemini || "";
        document.getElementById("cfgStorageDir").value = config.storage_dir || "storage";
        document.getElementById("cfgDefaultSite").value = config.crawler?.default_site || "69shuba";
        document.getElementById("cfgGeminiOfflineUrl").value = config.crawler?.gemini_offline_base_url || "http://localhost:7860/v1";
        
        // Also load into Step 1 if not already modified
        if(!document.getElementById("s1GeminiOfflineUrl").value) {
            document.getElementById("s1GeminiOfflineUrl").value = config.crawler?.gemini_offline_base_url || "http://localhost:7860/v1";
        }
        if(!document.getElementById("s1GeminiKey").value && config.api_keys?.gemini) {
            document.getElementById("s1GeminiKey").value = config.api_keys.gemini;
        }
        
        document.getElementById("cfgTtsEngine").value = config.tts?.default_engine || "edge";
        document.getElementById("cfgTtsVoice").value = config.tts?.default_voice || "vi-VN-NamMinhNeural";
        document.getElementById("cfgTtsSpeed").value = config.tts?.speed || 1.0;
        document.getElementById("cfgTtsNormalize").checked = config.tts?.normalize !== false;
        
        document.getElementById("cfgVideoStyle").value = config.video?.default_style || "anime_2d_flat";
        document.getElementById("cfgVideoGpu").checked = config.video?.use_gpu !== false;
    } catch (e) {
        console.error("Lỗi khi tải cấu hình chung:", e);
    }
}
