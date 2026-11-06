// Panel "Chỉnh ánh sáng" (nổi trên khung 3D, không che cảnh): hướng + độ cao + độ sáng + màu nắng, ánh sáng nền,
// phản chiếu môi trường, độ phơi sáng, màu nền, bóng đổ. Kéo = xem ngay; thả tay = 1 bước Undo.
import { applyLightSettings, LIGHTING_PRESETS, presetSettings } from './lighting-presets.js';

// [khoá, nhãn, min, max, bước, đơn vị hiển thị]
const SLIDERS = [
  ['sunAz', 'Hướng nắng', -180, 180, 1, (v) => `${v}°`],
  ['sunEl', 'Độ cao nắng', 3, 90, 1, (v) => `${v}°`],
  ['sunIntensity', 'Độ sáng nắng', 0, 8, 0.05, (v) => v.toFixed(2)],
  ['ambient', 'Ánh sáng nền', 0, 3, 0.05, (v) => v.toFixed(2)],
  ['env', 'Phản chiếu', 0, 2, 0.05, (v) => v.toFixed(2)],
  ['exposure', 'Độ phơi sáng', 0.3, 2.5, 0.05, (v) => v.toFixed(2)],
];
const COLORS = [['sunColor', 'Màu nắng'], ['sky', 'Màu trời'], ['ground', 'Màu đất'], ['background', 'Màu nền']];

export function createLightingPanel(viewportEl, { viewport, stack }) {
  const panel = Object.assign(document.createElement('aside'), { className: 'lighting-panel', hidden: true });
  panel.innerHTML = `<div class="lp-head"><b>💡 Chỉnh ánh sáng</b><button data-lp="close" title="Đóng">✕</button></div>
    <div class="lp-presets"></div><div class="lp-body"></div>
    <label class="lp-check"><input type="checkbox" data-k="shadows"> Bóng đổ</label>`;
  viewportEl.append(panel);
  const body = panel.querySelector('.lp-body');
  const current = () => ({ ...(viewport.objectsRoot.userData.lightSettings ?? presetSettings('studio')) });
  let before = null;

  const commit = (label) => {
    const from = before, to = current();
    before = null;
    if (!from || JSON.stringify(from) === JSON.stringify(to)) return;
    stack.push({ label, do: () => { applyLightSettings(viewport, to); sync(); }, undo: () => { applyLightSettings(viewport, from); sync(); } });
  };
  const set = (key, value) => {
    before ??= current();
    applyLightSettings(viewport, { ...current(), [key]: value });
  };

  for (const [key, label, min, max, step] of SLIDERS) {
    const row = document.createElement('label');
    row.className = 'lp-row';
    row.innerHTML = `<span>${label}</span><input type="range" data-k="${key}" min="${min}" max="${max}" step="${step}"><output></output>`;
    const input = row.querySelector('input');
    input.oninput = () => { set(key, Number(input.value)); sync(); };
    input.onchange = () => commit(label);
    body.append(row);
  }
  const colors = document.createElement('div');
  colors.className = 'lp-colors';
  for (const [key, label] of COLORS) {
    const row = document.createElement('label');
    row.innerHTML = `<input type="color" data-k="${key}"><span>${label}</span>`;
    const input = row.querySelector('input');
    input.oninput = () => set(key, input.value);
    input.onchange = () => commit(label);
    colors.append(row);
  }
  body.append(colors);
  const shadows = panel.querySelector('[data-k="shadows"]');
  shadows.onchange = () => { set('shadows', shadows.checked); commit('Bóng đổ'); };
  panel.querySelector('.lp-presets').append(...Object.entries(LIGHTING_PRESETS).map(([key, p]) => {
    const b = Object.assign(document.createElement('button'), { textContent: p.label, title: 'Bắt đầu từ preset này rồi chỉnh tiếp' });
    b.onclick = () => {
      before = current();
      applyLightSettings(viewport, presetSettings(key), key);
      commit(`Ánh sáng: ${p.label}`);
      sync();
    };
    return b;
  }));
  panel.querySelector('[data-lp="close"]').onclick = () => { panel.hidden = true; };
  panel.addEventListener('keydown', (e) => e.stopPropagation()); // phím trong panel không kích hoạt phím tắt app
  panel.addEventListener('click', (e) => e.stopPropagation()); // không để app tưởng bấm ra ngoài (thoát chế độ đang chỉnh)

  function sync() {
    if (panel.hidden) return;
    const s = current();
    for (const [key, , , , , fmt] of SLIDERS) {
      const input = panel.querySelector(`[data-k="${key}"]`);
      input.value = s[key];
      input.nextElementSibling.textContent = fmt(Number(s[key]));
    }
    for (const [key] of COLORS) panel.querySelector(`[data-k="${key}"]`).value = s[key];
    shadows.checked = s.shadows;
  }

  return {
    toggle() { panel.hidden = !panel.hidden; sync(); },
    sync,
  };
}
