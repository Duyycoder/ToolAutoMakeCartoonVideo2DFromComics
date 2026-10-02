/**
 * Chatbot Widget Client JS
 * Hỗ trợ streaming fetch, ReadableStream, AbortController, Pre-warm, Modal 409 & Agent Cards
 */
(function () {
  let sessionId = localStorage.getItem("chatbot_session_id");
  if (!sessionId) {
    sessionId = "s-" + Date.now().toString(36) + "-" + Math.random().toString(36).substring(2, 6);
    localStorage.setItem("chatbot_session_id", sessionId);
  }

  let abortController = null;
  let isStreaming = false;

  // DOM Elements
  let widgetContainer, toggleBtn, badge, panel, messagesBox, inputArea, sendBtn;
  let modelSelect, modelNote, modelInfo = null;
  let reasonSelect = null;

  function escapeHTML(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function renderMarkdown(text) {
    if (!text) return "";
    let html = escapeHTML(text);
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    // Code blocks & inline code
    html = html.replace(/```([\s\S]*?)```/g, "<pre><code>$1</code></pre>");
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    // Lists
    html = html.replace(/^\s*-\s+(.*)$/gm, "<li>$1</li>");
    // Newlines
    html = html.replace(/\n/g, "<br>");
    return html;
  }

  function getActiveTab() {
    const activeTabEl = document.querySelector(".tab-button.active, .nav-item.active");
    if (!activeTabEl) return "step1";
    const id = activeTabEl.id || activeTabEl.getAttribute("data-tab") || "";
    if (id.includes("1")) return "step1";
    if (id.includes("2")) return "step2";
    if (id.includes("3")) return "step3";
    if (id.includes("4")) return "step4";
    if (id.includes("5")) return "step5";
    if (id.includes("config")) return "config";
    return "step1";
  }

  function getSelectedStory() {
    const selectEl = document.getElementById("storySelect") || document.getElementById("currentStory");
    if (!selectEl) return "";
    // Ô <select> chưa chọn thì textContent là chữ của MỌI lựa chọn gộp lại —
    // từng bị gửi lên làm tên truyện. Chỉ phần tử hiển thị mới lấy chữ.
    if (selectEl.tagName === "SELECT") return selectEl.value || "";
    return selectEl.textContent.trim();
  }

  function initDOM() {
    widgetContainer = document.getElementById("chatWidget");
    if (!widgetContainer) return;

    widgetContainer.innerHTML = `
      <button class="chat-toggle-btn" id="chatToggleBtn" title="Trợ lý AI">
        🤖
        <span class="chat-badge offline" id="chatBadge"></span>
      </button>

      <div class="chat-panel" id="chatPanel">
        <div class="chat-header">
          <div class="chat-header-title">
            <span>Trợ Lý AI</span>
            <small id="chatSubTitle" style="font-size: 11px; opacity: 0.7; font-weight: normal;"></small>
          </div>
          <div class="chat-header-actions">
            <button class="chat-icon-btn" id="chatNewBtn" title="Cuộc trò chuyện mới">🔄</button>
            <button class="chat-icon-btn" id="chatCloseBtn" title="Thu nhỏ">✖</button>
          </div>
        </div>

        <div class="chat-modelbar">
          <label for="chatModelSelect">Model</label>
          <select id="chatModelSelect"></select>
          <select id="chatReasonSelect" aria-label="Chế độ suy luận" title="Chế độ suy luận — Tự động: chỉ hiểu lại câu hỏi khi cần. Kỹ: luôn hiểu lại, chậm hơn nhưng chắc hơn. Nhanh: bỏ các lượt suy luận phụ.">
            <option value="auto">Tự động</option>
            <option value="deep">Kỹ</option>
            <option value="fast">Nhanh</option>
          </select>
          <span class="chat-modelbar-gpu" id="chatGpuInfo"></span>
        </div>
        <div class="chat-modelbar-note" id="chatModelNote"></div>

        <div class="chat-messages" id="chatMessages">
          <div class="chat-msg assistant">
            Xin chào! Tôi là Trợ Lý AI. Tôi có thể giúp bạn giải đáp thắc mắc vận hành hoặc tư vấn nội dung truyện.
          </div>
        </div>

        <div class="chat-input-area">
          <textarea id="chatInput" placeholder="Nhập câu hỏi hoặc lệnh..." rows="1"></textarea>
          <button class="chat-send-btn" id="chatSendBtn">Gửi</button>
        </div>
      </div>
    `;

    toggleBtn = document.getElementById("chatToggleBtn");
    badge = document.getElementById("chatBadge");
    panel = document.getElementById("chatPanel");
    messagesBox = document.getElementById("chatMessages");
    inputArea = document.getElementById("chatInput");
    sendBtn = document.getElementById("chatSendBtn");

    toggleBtn.addEventListener("click", togglePanel);
    document.getElementById("chatCloseBtn").addEventListener("click", togglePanel);
    document.getElementById("chatNewBtn").addEventListener("click", clearSession);

    sendBtn.addEventListener("click", handleSend);
    inputArea.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    });

    modelSelect = document.getElementById("chatModelSelect");
    modelNote = document.getElementById("chatModelNote");
    modelSelect.addEventListener("change", onModelChange);

    // Chế độ suy luận là lựa chọn riêng của người xem -> nhớ trong trình duyệt.
    reasonSelect = document.getElementById("chatReasonSelect");
    try {
      const saved = localStorage.getItem("chatReasoning");
      if (saved) reasonSelect.value = saved;
    } catch (e) { /* trình duyệt chặn localStorage: dùng mặc định */ }
    reasonSelect.addEventListener("change", () => {
      try { localStorage.setItem("chatReasoning", reasonSelect.value); } catch (e) { /* bỏ qua */ }
    });

    checkHealth();
    setInterval(checkHealth, 10000);
    loadModels();
  }

  // ---------------------------------------------------------------- Chọn model
  function describe(m, tier) {
    // Model nặng hơn VRAM của máy vẫn hiện ra, nhưng phải nói rõ hệ quả thay vì
    // ẩn đi — người dùng máy 6GB có quyền chọn model to khi không dựng video.
    const warn = m.fits ? "" : " — nặng cho máy này";
    const miss = m.installed ? "" : " (chưa tải)";
    return `${m.name} — ${m.vram_gb}GB${warn}${miss}`;
  }

  async function loadModels() {
    try {
      const res = await fetch("/api/chat/models");
      if (!res.ok) return;
      modelInfo = await res.json();

      const gpuEl = document.getElementById("chatGpuInfo");
      if (modelInfo.gpu_vram_mb) {
        const gb = Math.round(modelInfo.gpu_vram_mb / 1024);
        gpuEl.textContent = `GPU ${gb}GB`;
        gpuEl.title = modelInfo.gpu_name || "";
      } else {
        gpuEl.textContent = "Không thấy GPU";
      }

      modelSelect.innerHTML = "";
      const groups = {
        "6gb": "Hợp máy 6GB VRAM",
        "8gb": "Cần máy 8GB VRAM trở lên",
      };
      for (const [tier, label] of Object.entries(groups)) {
        const list = modelInfo.models.filter((m) => m.tiers[0] === tier);
        if (!list.length) continue;
        const og = document.createElement("optgroup");
        og.label = label;
        for (const m of list) {
          const opt = document.createElement("option");
          opt.value = m.name;
          opt.textContent = describe(m, modelInfo.tier);
          opt.disabled = !m.installed;
          if (m.name === modelInfo.current) opt.selected = true;
          og.appendChild(opt);
        }
        modelSelect.appendChild(og);
      }
      renderModelNote(modelInfo.current);
    } catch (_) {}
  }

  function renderModelNote(name) {
    if (!modelInfo) return;
    const m = modelInfo.models.find((x) => x.name === name);
    if (!m) { modelNote.textContent = ""; return; }
    const rec = modelInfo.recommended === name ? "Khuyến nghị cho máy này. " : "";
    modelNote.textContent = rec + m.note;
    modelNote.className = "chat-modelbar-note" + (m.fits ? "" : " warn");
  }

  async function onModelChange() {
    const name = modelSelect.value;
    modelNote.textContent = "Đang đổi model…";
    try {
      const res = await fetch("/api/chat/model", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: name }),
      });
      const data = await res.json();
      if (!res.ok) {
        modelNote.textContent = "Không đổi được: " + (data.detail || "lỗi không rõ");
        return;
      }
      modelInfo.current = name;
      renderModelNote(name);
      appendMessage("assistant", `Đã chuyển sang model **${name}**. Câu hỏi tiếp theo sẽ mất vài giây để nạp model.`);
      checkHealth();
    } catch (e) {
      modelNote.textContent = "Lỗi kết nối khi đổi model.";
    }
  }

  function togglePanel() {
    const isOpen = panel.classList.toggle("open");
    if (isOpen) {
      inputArea.focus();
      prewarmModel();
      loadModels();
    }
  }

  // Danh sách model chỉ biết model nào "đã tải" khi hỏi được Ollama. Nếu trang mở
  // lúc Ollama chưa chạy, mọi model bị khoá "(chưa tải)" và trước đây không bao giờ
  // tự mở lại — người dùng tưởng không được chọn qwen2.5:7b-instruct.
  let lastOllamaOnline = null;

  async function checkHealth() {
    try {
      const res = await fetch("/api/chat/health");
      if (!res.ok) throw new Error();
      const data = await res.json();
      if (data.ollama_online && lastOllamaOnline === false) loadModels();
      lastOllamaOnline = !!data.ollama_online;

      badge.className = "chat-badge";
      if (!data.ollama_online) {
        badge.classList.add("offline");
        badge.title = "Ollama Offline";
      } else if (data.busy) {
        badge.classList.add("busy");
        badge.title = "GPU bận (" + (data.busy_tasks.join(", ") || "pipeline") + ")";
      } else {
        badge.classList.add("ready");
        badge.title = "Trợ lý sẵn sàng (" + data.model + ")";
      }
    } catch {
      badge.className = "chat-badge offline";
      badge.title = "Không kết nối được server";
    }
  }

  async function prewarmModel() {
    try {
      fetch("/api/chat/prewarm", { method: "POST" });
    } catch {}
  }

  async function clearSession() {
    try {
      await fetch(`/api/chat/sessions/${sessionId}`, { method: "DELETE" });
    } catch {}
    messagesBox.innerHTML = `
      <div class="chat-msg assistant">
        Đã bắt đầu cuộc trò chuyện mới! Tôi có thể giúp gì cho bạn?
      </div>
    `;
  }

  function appendMessage(role, text, mode = "") {
    const div = document.createElement("div");
    div.className = `chat-msg ${role} ${mode}`;
    div.innerHTML = renderMarkdown(text);
    messagesBox.appendChild(div);
    messagesBox.scrollTop = messagesBox.scrollHeight;
    return div;
  }

  function renderCard(cardData) {
    const div = document.createElement("div");
    div.className = "chat-card";

    if (cardData.type === "story_list") {
      div.innerHTML = `
        <div class="chat-card-title">Danh sách truyện (${cardData.count})</div>
        <ul>
          ${cardData.data.map(s => `<li><strong>${escapeHTML(s.title || s.story_name)}</strong> (slug: <code>${s.story_slug}</code>)</li>`).join("")}
        </ul>
      `;
    } else if (cardData.type === "story_report") {
      div.innerHTML = `
        <div class="chat-card-title">Báo cáo truyện "${escapeHTML(cardData.story)}"</div>
        <div>- Trạng thái: <code>${cardData.status}</code></div>
        <div>- Số chương: <strong>${cardData.chapters}</strong></div>
        <div>- File âm thanh: <strong>${cardData.audio_files}</strong></div>
        <div>- File video: <strong>${cardData.video_files}</strong></div>
      `;
    } else if (cardData.type === "system_status") {
      div.innerHTML = `
        <div class="chat-card-title">Trạng thái hệ thống</div>
        <div>- Mức GPU: <code>${cardData.gpu_weight}</code></div>
        <div>- Task đang chạy: ${cardData.running_tasks.length ? cardData.running_tasks.map(t => `<code>${t}</code>`).join(", ") : "Không có"}</div>
      `;
    }
    messagesBox.appendChild(div);
    messagesBox.scrollTop = messagesBox.scrollHeight;
  }

  // Số bước theo thanh bên -> form của bước đó (Bước 4 "Ghép Video" là formStep5).
  const STEP_FORMS = {
    1: { tab: "step1", form: "formStep1", name: "Nguồn & Dịch" },
    2: { tab: "step2", form: "formStep2", name: "Sinh Giọng" },
    3: { tab: "step3", form: "formStep3", name: "Dựng Hoạt Hình" },
    4: { tab: "step5", form: "formStep5", name: "Ghép Video" },
  };

  // Chạy bằng chính nút "Bắt đầu" của form: giữ nguyên kiểm tra, khoá nút,
  // log trực tiếp và lưu cấu hình như khi người dùng tự bấm. Trước đây thẻ gọi
  // thẳng API (chỉ bước 1, không log), các bước khác bấm "Chấp nhận" không có gì xảy ra.
  function runStepFromChat(args) {
    const step = STEP_FORMS[args.n];
    const form = step && document.getElementById(step.form);
    if (!form) {
      appendMessage("assistant", `Không tìm thấy form của Bước ${args.n}.`);
      return;
    }
    if (!getSelectedStory()) {
      appendMessage("assistant", "Chưa chọn truyện — hãy chọn truyện ở thanh bên trái rồi chạy lại.");
      return;
    }
    document.querySelector(`.nav-item[data-tab="${step.tab}"]`)?.click();
    if (args.n === 1 && args.max_chapters) {
      const num = document.getElementById("s1NumChapters");
      if (num) num.value = args.max_chapters;
    }
    const btn = form.querySelector('button[type="submit"]');
    if (btn && btn.disabled) {
      appendMessage("assistant", `Nút chạy Bước ${args.n} đang bị khoá (đang chạy hoặc chưa đủ điều kiện). Xem thông báo trên trang.`);
      return;
    }
    form.requestSubmit(btn || undefined);
    appendMessage("assistant", `Đã bắt đầu Bước ${args.n}: ${step.name}. Theo dõi tiến độ ở khung log của bước này.`);
  }

  function renderConfirmationCard(action, args) {
    const div = document.createElement("div");
    div.className = "chat-card";
    
    let title = "▶ Xác nhận thực thi lệnh";
    let detail = "";

    if (action === "run_step") {
      const step = STEP_FORMS[args.n];
      title = `▶ Chạy Bước ${args.n}${step ? ": " + step.name : ""}`;
      const story = getSelectedStory();
      detail = `Truyện: ${escapeHTML(story || "(chưa chọn)")} — dùng thiết lập đang có ở form bước này`;
      if (args.max_chapters) detail += `; số chương: ${args.max_chapters}`;
    } else if (action === "select_story") {
      title = `▶ Chuyển sang truyện "${escapeHTML(args.name)}"`;
    }

    div.innerHTML = `
      <div class="chat-card-title">${title}</div>
      <div style="font-size:12px; opacity:0.8;">${detail}</div>
      <div class="chat-card-actions">
        <button class="chat-btn-sm chat-btn-primary" id="confirmActionBtn">Chấp nhận chạy</button>
        <button class="chat-btn-sm chat-btn-secondary" id="cancelActionBtn">Huỷ</button>
      </div>
    `;

    messagesBox.appendChild(div);
    messagesBox.scrollTop = messagesBox.scrollHeight;

    div.querySelector("#confirmActionBtn").addEventListener("click", () => {
      div.remove();
      if (action === "select_story" && window.selectStory) {
        window.selectStory(args.name);
        appendMessage("assistant", `Đã chuyển sang truyện **${args.name}**.`);
      } else if (action === "run_step") {
        runStepFromChat(args);
      }
    });

    div.querySelector("#cancelActionBtn").addEventListener("click", () => {
      div.remove();
      appendMessage("assistant", "Đã huỷ lệnh.");
    });
  }

  function show409Modal(detailData, originalMessage) {
    const div = document.createElement("div");
    div.className = "chat-card";
    div.innerHTML = `
      <div class="chat-card-title" style="color:var(--warning-text);">GPU đang bận (${detailData.busy_tasks ? detailData.busy_tasks.join(", ") : "Pipeline"})</div>
      <div style="font-size:12px; margin-bottom:8px;">Pipeline đang chạy cần toàn bộ bộ nhớ GPU. Hãy chọn một tùy chọn:</div>
      <div class="chat-card-actions" style="flex-direction:column; gap:6px;">
        <button class="chat-btn-sm chat-btn-warning" id="modalLookupBtn">Tra cứu tài liệu (0 VRAM)</button>
        <button class="chat-btn-sm chat-btn-primary" id="modalForceBtn">Dừng pipeline để hỏi đầy đủ</button>
        <button class="chat-btn-sm chat-btn-secondary" id="modalCancelBtn">Để sau, đóng trợ lý</button>
      </div>
    `;
    messagesBox.appendChild(div);
    messagesBox.scrollTop = messagesBox.scrollHeight;

    div.querySelector("#modalLookupBtn").addEventListener("click", () => {
      div.remove();
      if (detailData.lookup_answer && detailData.lookup_answer.answer) {
        appendMessage("assistant", detailData.lookup_answer.answer, "lookup");
      } else {
        sendMessage(originalMessage, { mode: "lookup" });
      }
    });

    div.querySelector("#modalForceBtn").addEventListener("click", async () => {
      div.remove();
      appendMessage("assistant", "Đang dừng tiến trình pipeline...");
      if (window.stopPipelineTask && detailData.busy_tasks && detailData.busy_tasks[0]) {
        window.stopPipelineTask(detailData.busy_tasks[0]);
      }
      setTimeout(() => {
        sendMessage(originalMessage, { force: true });
      }, 1500);
    });

    div.querySelector("#modalCancelBtn").addEventListener("click", () => {
      div.remove();
    });
  }

  async function handleSend() {
    if (isStreaming) {
      if (abortController) abortController.abort();
      return;
    }

    const text = inputArea.value.trim();
    if (!text) return;

    inputArea.value = "";
    appendMessage("user", text);
    await sendMessage(text);
  }

  // Nhật ký các bước suy luận, gập lại dưới câu trả lời — để biết trợ lý đã hiểu
  // câu hỏi thành gì và lấy tài liệu nào, thay vì phải tin mù.
  const STEP_NAMES = {
    tra_nhanh: "Tra nhanh", hieu_cau_hoi: "Hiểu câu hỏi", tra_lai: "Tra lại",
    chon_doan: "Chọn đoạn",
  };

  // Dữ liệu hệ thống đã tự đọc từ CSDL cho câu hỏi này — gập lại để người dùng tự soát số liệu.
  const DB_LOAI = { tong_quan: "tổng quan", truyen: "chi tiết truyện", job: "job", loc: "lọc" };
  function renderDbResult(db) {
    const box = document.createElement("details");
    box.className = "chat-steps chat-db";
    const sum = document.createElement("summary");
    const loai = (db.loai || []).map(x => DB_LOAI[x] || x).join(", ");
    const truyen = (db.truyen || []).length ? ` — ${db.truyen.join("; ")}` : "";
    sum.textContent = `Dữ liệu đã đọc từ CSDL (${loai})${truyen}`;
    box.appendChild(sum);
    const pre = document.createElement("pre");
    pre.className = "chat-db-sql chat-db-wrap";
    pre.textContent = db.context || "";
    box.appendChild(pre);
    return box;
  }

  function renderSteps(steps, sources) {
    const box = document.createElement("details");
    box.className = "chat-steps";
    const total = steps.reduce((s, x) => s + (x.ms || 0), 0);
    const sum = document.createElement("summary");
    sum.textContent = `Các bước suy luận (${(total / 1000).toFixed(1)} s)`;
    box.appendChild(sum);
    const ul = document.createElement("ul");
    for (const st of steps) {
      const li = document.createElement("li");
      const name = STEP_NAMES[st.buoc] || (st.buoc.startsWith("tra_y_") ? "Tra ý " + st.buoc.slice(6) : st.buoc);
      let extra = "";
      if (st.ket_qua && st.ket_qua.cau_hoi) extra = ` — hiểu là: “${st.ket_qua.cau_hoi}”`;
      if (st.ket_qua && st.ket_qua.y_nho && st.ket_qua.y_nho.length > 1) extra += ` (${st.ket_qua.y_nho.length} ý)`;
      if (Array.isArray(st.chon)) extra = st.chon.length ? ` — chọn đoạn ${st.chon.join(", ")}` : " — không đoạn nào khớp";
      li.textContent = `${name}: ${st.ms} ms${extra}`;
      ul.appendChild(li);
    }
    if (sources.length) {
      const li = document.createElement("li");
      li.textContent = "Tài liệu: " + sources.join(", ");
      ul.appendChild(li);
    }
    box.appendChild(ul);
    return box;
  }

  async function sendMessage(messageText, options = {}) {
    isStreaming = true;
    sendBtn.textContent = "Dừng";
    sendBtn.classList.add("chat-btn-warning");
    inputArea.disabled = true;

    abortController = new AbortController();

    const assistantMsgDiv = appendMessage("assistant", "...");
    let fullText = "";

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: abortController.signal,
        body: JSON.stringify({
          session_id: sessionId,
          message: messageText,
          story_name: getSelectedStory(),
          active_tab: getActiveTab(),
          mode: options.mode || "auto",
          reasoning: reasonSelect ? reasonSelect.value : "",
          force: !!options.force
        })
      });

      if (res.status === 409) {
        assistantMsgDiv.remove();
        const detailData = await res.json();
        show409Modal(detailData, messageText);
        return;
      }

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: "Lỗi kết nối server" }));
        assistantMsgDiv.innerHTML = `<span style="color:#ef4444;">Lỗi (${res.status}): ${escapeHTML(errData.detail || "Thất bại")}</span>`;
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();

        let lines;
        if (done) {
          // Dòng cuối có thể KHÔNG kết thúc bằng "\n". Nếu bỏ qua phần còn lại
          // trong buffer thì một phản hồi gói gọn trong đúng một dòng sẽ bị mất
          // trắng và widget đứng mãi ở dấu "..." — đúng lỗi đã xảy ra với nhánh
          // lệnh agent. Luôn xả nốt buffer trước khi thoát.
          lines = buffer.trim() ? [buffer] : [];
          buffer = "";
        } else {
          buffer += decoder.decode(value, { stream: true });
          lines = buffer.split("\n");
          buffer = lines.pop();
        }

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const chunk = JSON.parse(line);

            if (chunk.agent_action) {
              assistantMsgDiv.remove();
              renderConfirmationCard(chunk.agent_action, chunk.args);
              return;
            }

            if (chunk.agent_result) {
              assistantMsgDiv.remove();
              renderCard(chunk.agent_result);
              return;
            }

            // Tiến độ các bước suy luận (hiểu câu hỏi, chọn tài liệu, từng ý...).
            // Chỉ hiện khi chưa có chữ trả lời; chữ đầu tiên tới thì thay chỗ.
            if (chunk.stage && !fullText) {
              assistantMsgDiv.innerHTML = `<span class="chat-stage">${escapeHTML(chunk.text || "Đang suy luận…")}</span>`;
              messagesBox.scrollTop = messagesBox.scrollHeight;
            }

            if (chunk.delta) {
              fullText += chunk.delta;
              assistantMsgDiv.innerHTML = renderMarkdown(fullText);
              messagesBox.scrollTop = messagesBox.scrollHeight;
            }

            if (chunk.done && chunk.db) {
              assistantMsgDiv.appendChild(renderDbResult(chunk.db));
              messagesBox.scrollTop = messagesBox.scrollHeight;
            }

            if (chunk.done && Array.isArray(chunk.steps) && chunk.steps.length) {
              assistantMsgDiv.appendChild(renderSteps(chunk.steps, chunk.sources || []));
            }

            if (chunk.done && chunk.truncated) {
              const truncBanner = document.createElement("div");
              truncBanner.className = "chat-truncated-banner";
              truncBanner.textContent = "Ngữ cảnh quá dài, câu trả lời có thể thiếu.";
              assistantMsgDiv.insertBefore(truncBanner, assistantMsgDiv.firstChild);
            }
          } catch (e) {
            // Dòng NDJSON có thể bị cắt giữa chừng — bỏ qua là đúng.
            // Nhưng nuốt im lặng MỌI lỗi sẽ giấu luôn bug render, nên vẫn log.
            console.warn("[Chatbot] Bỏ qua dòng stream không đọc được:", e.message, line);
          }
        }

        if (done) break;
      }
    } catch (err) {
      if (err.name === "AbortError") {
        assistantMsgDiv.innerHTML += " <em style='opacity:0.6;'>(Đã dừng sinh)</em>";
      } else {
        assistantMsgDiv.innerHTML = `<span style="color:#ef4444;">Lỗi kết nối: ${escapeHTML(err.message)}</span>`;
      }
    } finally {
      isStreaming = false;
      sendBtn.textContent = "Gửi";
      sendBtn.classList.remove("chat-btn-warning");
      inputArea.disabled = false;
      inputArea.focus();
    }
  }

  // Khởi chạy khi DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDOM);
  } else {
    initDOM();
  }
})();
