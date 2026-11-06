// Wizard "Tạo từ ảnh": chọn ảnh -> chọn chất lượng -> AI chạy (tiến độ thật qua SSE) -> mô hình vào cảnh.
import { api } from './backend-api-client.js';
import { openModal } from './modal-dialog.js';
import { baseNameOf } from './model-import-export.js';

export const IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'webp'];

const MODELS = [
  ['triposr', '⚡ Nhanh — TripoSR', 'Khoảng 30 giây. Hợp để thử nhanh'],
  ['hunyuan', '💎 Chất lượng cao — Hunyuan3D', 'Vài phút. Hình chi tiết hơn rõ rệt, màu lấy từ ảnh'],
];
const MODEL_KEY = 'easy3d.imageTo3dModel';

const QUALITIES = [
  ['fast', 'Nhanh', 'Xem thử, ít chi tiết'],
  ['balanced', 'Cân bằng', 'Khuyên dùng'],
  ['detailed', 'Chi tiết', 'Đẹp hơn, chậm hơn, tốn bộ nhớ GPU hơn'],
];

/** onResult(url, name): nạp GLB kết quả vào cảnh. */
export async function openImageTo3DWizard({ initialFile = null, onResult }) {
  const dlg = openModal({ onClose: () => stopWatching?.() });
  const state = { file: initialFile, quality: 'balanced', model: localStorage.getItem(MODEL_KEY) ?? 'triposr', status: null };
  let stopWatching = null;
  try {
    state.status = await api.aiStatus();
  } catch (err) {
    state.status = { ready: false, cuda: false, message: err.message, models: {} };
  }
  const modelStatus = (key) => state.status.models?.[key] ?? { ready: false, message: state.status.message };
  if (!modelStatus(state.model).ready && modelStatus('triposr').ready) state.model = 'triposr';
  renderChoose();

  function renderChoose(errorMsg = '') {
    dlg.setClosable(true);
    const { cuda } = state.status;
    const { ready, message } = modelStatus(state.model);
    const banner = !ready ? `<div class="banner err">⚠ ${message}</div>`
      : !cuda ? `<div class="banner warn">🐢 ${message}</div>` : '';
    dlg.modal.innerHTML = `
      <button class="modal-close" title="Đóng (Esc)">✕</button>
      <h2>🪄 Tạo mô hình 3D từ ảnh</h2>
      <p class="sub">AI chạy ngay trên máy bạn — ảnh không gửi lên mạng.</p>
      ${banner}${errorMsg ? '<div class="banner err" id="err"></div>' : ''}
      <div class="wizard-grid">
        <div>
          <div class="dropzone" id="dz"><span class="big">🖼</span>
            <b>Bấm để chọn ảnh</b><small>hoặc kéo thả ảnh vào đây (PNG, JPG, WEBP)</small></div>
          <input type="file" id="pick" accept="image/png,image/jpeg,image/webp" hidden>
          <div class="good-photo"><b>Mẹo để ra kết quả đẹp:</b><ul>
            <li>Chỉ 1 vật thể, nằm trọn trong ảnh</li><li>Chụp chéo góc 3/4, đủ sáng</li>
            <li>Nền càng đơn giản càng tốt (AI tự xoá nền)</li></ul></div>
        </div>
        <div><b>Mô hình AI</b><div class="quality" id="m" style="margin:8px 0 14px"></div>
          <b>Chất lượng</b><div class="quality" id="q" style="margin-top:8px"></div></div>
      </div>
      <div class="modal-footer"><button id="cancel">Đóng</button>
        <button class="primary" id="go">Tạo mô hình 3D ✨</button></div>`;
    if (errorMsg) dlg.modal.querySelector('#err').textContent = `⚠ ${errorMsg}`;

    const mEl = dlg.modal.querySelector('#m');
    for (const [key, label, hint] of MODELS) {
      const row = document.createElement('label');
      row.innerHTML = '<input type="radio" name="model"><span><b></b><small></small></span>';
      const st = modelStatus(key);
      row.querySelector('b').textContent = label;
      row.querySelector('small').textContent = st.ready ? hint : st.message;
      const radio = row.querySelector('input');
      radio.checked = key === state.model;
      radio.onchange = () => { state.model = key; localStorage.setItem(MODEL_KEY, key); renderChoose(); };
      if (!st.ready && key !== state.model) row.classList.add('unavailable');
      mEl.append(row);
    }
    const q = dlg.modal.querySelector('#q');
    for (const [key, label, hint] of QUALITIES) {
      const row = document.createElement('label');
      row.innerHTML = `<input type="radio" name="quality" value="${key}"><span><b></b><small></small></span>`;
      row.querySelector('b').textContent = label;
      row.querySelector('small').textContent = hint;
      const radio = row.querySelector('input');
      radio.checked = key === state.quality;
      radio.onchange = () => { state.quality = key; };
      q.append(row);
    }

    const dz = dlg.modal.querySelector('#dz');
    const pick = dlg.modal.querySelector('#pick');
    const go = dlg.modal.querySelector('#go');
    const showPreview = () => {
      go.disabled = !state.file || !ready;
      if (!state.file) return;
      const img = document.createElement('img');
      img.src = URL.createObjectURL(state.file);
      const name = document.createElement('small');
      name.textContent = `${state.file.name} — bấm để đổi ảnh`;
      dz.replaceChildren(img, name);
    };
    const setFile = (file) => {
      if (!file) return;
      if (!IMAGE_EXTENSIONS.includes(file.name.split('.').pop().toLowerCase())) {
        return renderChoose('Chỉ nhận ảnh PNG, JPG hoặc WEBP.');
      }
      state.file = file;
      showPreview();
    };
    dz.onclick = () => pick.click();
    pick.onchange = () => setFile(pick.files[0]);
    dz.ondragover = (e) => { e.preventDefault(); dz.classList.add('over'); };
    dz.ondragleave = () => dz.classList.remove('over');
    dz.ondrop = (e) => { e.preventDefault(); e.stopPropagation(); dz.classList.remove('over'); setFile(e.dataTransfer.files[0]); };
    dlg.modal.querySelector('.modal-close').onclick = dlg.close;
    dlg.modal.querySelector('#cancel').onclick = dlg.close;
    go.onclick = start;
    showPreview();
  }

  async function start() {
    let job;
    try {
      job = await api.startImageTo3D(state.file, state.quality, state.model);
    } catch (err) {
      return renderChoose(err.message);
    }
    dlg.setClosable(false);
    dlg.modal.innerHTML = `
      <h2>🪄 AI đang làm việc...</h2>
      <div class="progress-wrap"><div class="spinner"></div>
        <div class="progress-bar"><div id="bar"></div></div>
        <div class="progress-msg" id="msg">Đang xếp hàng...</div></div>
      <div class="modal-footer"><small class="info-line">Lần đầu nạp model có thể mất 1-2 phút.</small>
        <button id="stop" class="danger">Huỷ</button></div>`;
    const bar = dlg.modal.querySelector('#bar');
    const msg = dlg.modal.querySelector('#msg');
    dlg.modal.querySelector('#stop').onclick = () => api.cancelJob(job.id).catch(() => {});

    stopWatching = api.watchJob(job.id, async (ev) => {
      if (ev.msg) msg.textContent = ev.msg;
      if (typeof ev.pct === 'number') bar.style.width = `${ev.pct}%`;
      if (ev.type !== 'status') return;
      if (ev.status === 'done') {
        bar.style.width = '100%';
        msg.textContent = 'Xong! Đang đưa mô hình vào cảnh...';
        try {
          await onResult(api.resultUrl(job.id), baseNameOf(state.file.name));
          dlg.close();
        } catch (err) {
          renderChoose(`Không mở được mô hình kết quả: ${err.message}`);
        }
      } else if (ev.status === 'error') {
        renderChoose(ev.msg);
      } else if (ev.status === 'cancelled') {
        renderChoose();
      }
    });
  }
}
