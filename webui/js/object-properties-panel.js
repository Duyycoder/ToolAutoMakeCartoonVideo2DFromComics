// Panel "Tuỳ chỉnh" cho vật đang chọn: tên, màu, chất liệu, kích thước, các nút nhanh.
// Mọi thay đổi đi qua `actions` (editor-actions.js) để có Undo.
import * as THREE from 'three';
import { MATERIAL_PRESETS, getColorHex, getPresetKey, hasOriginalLook } from './material-preset-library.js';
import { meshToolsSection } from './mesh-tools-panel.js';
import { appearanceSection, lightSection } from './appearance-panel-sections.js';
import { isLightObject } from './scene-light-objects.js';

const COLORS = ['#f5f5f5', '#9aa0b1', '#2b2d33', '#ff5c5c', '#ff9f43', '#f2c94c', '#5fd08a',
  '#2ec4b6', '#56ccf2', '#5b8cff', '#8a5bff', '#e056fd', '#b07a4f'];

const el = (tag, props = {}, children = []) => {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
};
const field = (label, ...children) => el('div', { className: 'field' }, [el('label', { textContent: label }), ...children]);

export function createPropertiesPanel(container, store, actions, meshTools, appearance) {
  let sizeInfo = null;
  let slider = null;

  function sizeText(obj) {
    const s = new THREE.Box3().setFromObject(obj).getSize(new THREE.Vector3()).multiplyScalar(100);
    return `Kích thước thật: ${s.x.toFixed(0)} × ${s.y.toFixed(0)} × ${s.z.toFixed(0)} cm · ${store.triangleCount(obj).toLocaleString('vi-VN')} tam giác`;
  }

  function render() {
    const obj = store.selected;
    container.replaceChildren(el('h3', { textContent: 'Tuỳ chỉnh' }));
    if (!obj) {
      container.append(el('div', { className: 'props-empty', innerHTML: 'Bấm vào một vật thể<br>trong khung 3D để chỉnh sửa' }));
      sizeInfo = slider = null;
      return;
    }

    const name = el('input', { type: 'text', value: obj.name, spellcheck: false });
    name.onchange = () => actions.rename(obj, name.value.trim() || obj.name);
    const quickButton = (text, title, fn, cls = '') => {
      const b = el('button', { textContent: text, title, className: cls });
      b.onclick = () => fn(obj);
      return b;
    };

    if (isLightObject(obj)) { // đèn: chỉ màu + độ sáng, không có vật liệu/sửa hình
      sizeInfo = slider = null;
      container.append(field('Tên', name), lightSection(obj, appearance), el('div', { className: 'field btn-grid' }, [
        quickButton('⧉ Nhân bản', 'Tạo bản sao (Ctrl+D)', actions.duplicate),
        quickButton('🗑 Xoá', 'Xoá đèn (phím Delete)', actions.remove, 'danger'),
      ]));
      return;
    }

    const current = getColorHex(obj);
    const swatches = el('div', { className: 'swatches' });
    if (hasOriginalLook(obj)) {
      const orig = el('button', { className: `swatch original${current === null ? ' current' : ''}`, title: 'Màu gốc' });
      orig.onclick = () => actions.setColor(obj, null);
      swatches.append(orig);
    }
    for (const hex of COLORS) {
      const sw = el('button', { className: `swatch${current === hex ? ' current' : ''}`, title: hex });
      sw.style.background = hex;
      sw.onclick = () => actions.setColor(obj, hex);
      swatches.append(sw);
    }
    const picker = el('input', { type: 'color', value: current ?? '#ffffff' });
    picker.onchange = () => actions.setColor(obj, picker.value);
    swatches.append(el('div', { className: 'swatch custom', title: 'Chọn màu khác', textContent: '＋' }, [picker]));

    const preset = getPresetKey(obj);
    const chips = el('div', { className: 'chips' });
    for (const [key, p] of Object.entries(MATERIAL_PRESETS)) {
      const chip = el('button', { className: `chip${key === preset ? ' current' : ''}`, textContent: p.label });
      chip.onclick = () => actions.setPreset(obj, key);
      chips.append(chip);
    }

    // Thanh trượt logarit: 10% .. 500%, giữ nguyên tỉ lệ các chiều.
    slider = el('input', { type: 'range', min: -1, max: 0.7, step: 0.01 });
    slider.value = Math.log10(Math.abs(obj.scale.x) || 1);
    slider.onpointerdown = () => actions.beginScale(obj);
    slider.oninput = () => actions.previewScale(obj, 10 ** Number(slider.value));
    slider.onchange = () => actions.commitScale(obj);

    const btn = (text, title, fn, cls = '') => {
      const b = el('button', { textContent: text, title, className: cls });
      b.onclick = () => fn(obj);
      return b;
    };
    sizeInfo = el('div', { className: 'info-line', textContent: sizeText(obj) });

    container.append(
      field('Tên', name),
      field('Màu sắc', swatches),
      field('Chất liệu', chips),
      field('Phóng to / thu nhỏ', slider),
      el('div', { className: 'field btn-grid' }, [
        btn('⬇ Đặt lên sàn', 'Hạ vật xuống chạm mặt sàn', actions.dropToFloor),
        btn('⊕ Về giữa', 'Đưa vật về giữa sàn', actions.center),
        btn('⧉ Nhân bản', 'Tạo bản sao (Ctrl+D)', actions.duplicate),
        btn('🗑 Xoá', 'Xoá vật thể (phím Delete)', actions.remove, 'danger'),
      ]),
      sizeInfo,
      appearanceSection(obj, appearance),
      meshToolsSection(obj, store, meshTools),
    );
  }

  store.addEventListener('selection', render);
  store.addEventListener('changed', render);
  // Khi kéo gizmo chỉ cập nhật số liệu, không vẽ lại cả panel (giữ focus ô nhập).
  store.addEventListener('transform', () => {
    if (!store.selected || !sizeInfo) return;
    sizeInfo.textContent = sizeText(store.selected);
    if (document.activeElement !== slider) slider.value = Math.log10(Math.abs(store.selected.scale.x) || 1);
  });
  render();
}
