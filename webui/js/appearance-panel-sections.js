// Panel: "🎨 Vân & vật liệu nâng cao" cho vật thường, "💡 Đèn" cho đèn.
import { PATTERNS } from './procedural-texture-library.js';
import { getLightLook } from './scene-light-objects.js';

const el = (tag, props = {}, children = []) => {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
};
let advancedOpen = false;

const firstMaterial = (obj) => {
  let mat = null;
  obj.traverse((m) => { if (!mat && m.isMesh) mat = Array.isArray(m.material) ? m.material[0] : m.material; });
  return mat;
};

/** Thanh trượt 0..1: kéo = xem trước, thả = 1 bước Undo. */
function liveSlider(label, value, onPreview, onBegin, onCommit) {
  const slider = el('input', { type: 'range', min: 0, max: 1, step: 0.01, value });
  slider.onpointerdown = onBegin;
  slider.oninput = () => onPreview(Number(slider.value));
  slider.onchange = onCommit;
  return el('div', { className: 'field' }, [el('label', { textContent: label }), slider]);
}

export function appearanceSection(obj, appearance) {
  const details = el('details', { className: 'tool-section', open: advancedOpen });
  details.ontoggle = () => { advancedOpen = details.open; };
  details.append(el('summary', { textContent: '🎨 Vân & vật liệu nâng cao' }));

  const mat = firstMaterial(obj);
  const current = mat?.map?.userData?.pattern ?? null;
  const chip = (text, key, onClick) => Object.assign(
    el('button', { className: `chip${current === key ? ' current' : ''}`, textContent: text }), { onclick: onClick });
  const fileInput = el('input', { type: 'file', accept: 'image/png,image/jpeg,image/webp', hidden: true });
  fileInput.onchange = () => { if (fileInput.files[0]) appearance.setImageTexture(obj, fileInput.files[0]); };
  details.append(el('div', { className: 'field' }, [
    el('label', { textContent: 'Vân bề mặt' }),
    el('div', { className: 'chips' }, [
      chip('Không vân', null, () => appearance.setPattern(obj, null)),
      ...Object.entries(PATTERNS).map(([key, p]) => chip(p.label, key, () => appearance.setPattern(obj, key))),
      chip('🖼 Ảnh của bạn…', 'image', () => fileInput.click()),
    ]),
    fileInput,
  ]));

  const begin = () => appearance.beginMaterialEdit(obj);
  const slider = (label, value, mutate) => liveSlider(label, value,
    (v) => appearance.previewMaterial(obj, (m) => mutate(m, v)), begin, () => appearance.commitMaterialEdit(obj, label));
  details.append(
    slider('Độ bóng', 1 - (mat?.roughness ?? 0.5), (m, v) => { if ('roughness' in m) m.roughness = 1 - v; }),
    slider('Kim loại', mat?.metalness ?? 0, (m, v) => { if ('metalness' in m) m.metalness = v; }),
    slider('Trong suốt', 1 - (mat?.opacity ?? 1), (m, v) => { m.opacity = 1 - v; m.transparent = v > 0.001; }),
    slider('Phát sáng', mat?.emissive?.getHex() ? mat.emissiveIntensity / 2 : 0, (m, v) => {
      if (!m.emissive) return;
      m.emissive.copy(m.color ?? m.emissive);
      m.emissiveIntensity = v * 2;
    }),
  );
  return details;
}

const LIGHT_COLORS = ['#fff1c9', '#ffffff', '#ffd08a', '#ff8a5c', '#ff5c8a', '#c48aff', '#7aa8ff', '#7af0d0'];

export function lightSection(obj, appearance) {
  const look = getLightLook(obj);
  const swatches = el('div', { className: 'swatches' }, LIGHT_COLORS.map((hex) => {
    const sw = el('button', { className: `swatch${look.color === hex ? ' current' : ''}`, title: hex });
    sw.style.background = hex;
    sw.onclick = () => appearance.setLightColor(obj, hex);
    return sw;
  }));
  const intensity = el('input', { type: 'range', min: 0, max: 150, step: 1, value: look.intensity });
  intensity.oninput = () => appearance.previewLightIntensity(obj, Number(intensity.value));
  intensity.onchange = () => appearance.commitLightIntensity(obj);
  return el('div', {}, [
    el('div', { className: 'field' }, [el('label', { textContent: 'Màu ánh sáng' }), swatches]),
    el('div', { className: 'field' }, [el('label', { textContent: 'Độ sáng' }), intensity]),
    el('div', { className: 'info-line', textContent: 'Mẹo: đổi "Ánh sáng" trên thanh trên cùng sang Ban đêm để đèn nổi bật.' }),
  ]);
}
