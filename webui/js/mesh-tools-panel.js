// Nhóm "🛠 Sửa hình" trong panel Tuỳ chỉnh.
const el = (tag, props = {}, children = []) => {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
};
let sectionOpen = true; // nhớ trạng thái gập/mở giữa các lần vẽ lại panel

function sliderRow(label, { min, max, value, step = 1, format }, buttonText, onApply) {
  const valueEl = el('span', { className: 'value', textContent: format(value) });
  const slider = el('input', { type: 'range', min, max, step, value });
  slider.oninput = () => { valueEl.textContent = format(Number(slider.value)); };
  const btn = el('button', { textContent: buttonText });
  btn.onclick = () => onApply(Number(slider.value));
  return el('div', { className: 'field' }, [
    el('label', {}, [label, ' ', valueEl]), el('div', { className: 'inline' }, [slider, btn]),
  ]);
}

import { isRigged, RIGGED_WARNING } from './rig-builder.js';
import { blenderMessage, blenderReady } from './blender-tools-actions.js';

export function meshToolsSection(obj, store, tools) {
  const details = el('details', { className: 'tool-section', open: sectionOpen });
  details.ontoggle = () => { sectionOpen = details.open; };
  details.append(el('summary', { textContent: '🛠 Sửa hình' }));
  if (isRigged(obj)) { // sửa hình sẽ làm hỏng phần da gắn với xương
    details.append(el('div', { className: 'info-line', textContent: RIGGED_WARNING }));
    return details;
  }

  details.append(
    sliderRow('Làm mượt', { min: 1, max: 10, value: 3, format: (v) => `mức ${v}` }, 'Làm mượt',
      (v) => tools.smooth(obj, v)),
    sliderRow('Giảm chi tiết', { min: 10, max: 90, value: 50, step: 5, format: (v) => `giữ ${v}%` }, 'Giảm',
      (v) => tools.simplify(obj, v / 100)),
  );

  const btn = (text, title, fn) => Object.assign(el('button', { textContent: text, title }), { onclick: fn });
  details.append(el('div', { className: 'field btn-grid' }, [
    btn('⇋ Nhân đối xứng', 'Tạo bản lật gương ở phía bên kia (trái ↔ phải)', () => tools.mirrorCopy(obj)),
    btn('✂ Tách phần rời', 'Mỗi mảnh không dính nhau (hoặc mỗi vật trong nhóm) thành 1 vật riêng', () => tools.separate(obj)),
  ]));

  const count = el('input', { type: 'number', min: 2, max: 20, value: 5, className: 'num' });
  const mode = el('select', {}, [el('option', { value: 'line', textContent: 'Thành hàng' }),
    el('option', { value: 'circle', textContent: 'Vòng tròn' })]);
  details.append(el('div', { className: 'field' }, [
    el('label', { textContent: 'Nhân thành nhiều bản' }),
    el('div', { className: 'inline' }, [count, mode, btn('Tạo', 'Tạo các bản sao', () => {
      tools.array(obj, Math.min(20, Math.max(2, Number(count.value) || 2)), mode.value);
    })]),
  ]));

  const others = store.objects.filter((o) => o !== obj && o.visible);
  const target = el('select', {}, others.map((o, i) => el('option', { value: i, textContent: o.name })));
  const pick = () => others[Number(target.value)];
  details.append(el('div', { className: 'field' }, others.length ? [
    el('label', { textContent: 'Kết hợp với vật khác' }),
    target,
    el('div', { className: 'btn-grid', style: 'margin-top:6px' }, [
      btn('➕ Ghép liền', 'Hợp 2 vật thành 1 khối liền', () => tools.boolean(obj, pick(), 'union')),
      btn('➖ Khoét đi', 'Dùng vật kia khoét lỗ vào vật này', () => tools.boolean(obj, pick(), 'subtract')),
      btn('◎ Phần chung', 'Chỉ giữ phần 2 vật chồng lên nhau', () => tools.boolean(obj, pick(), 'intersect')),
      btn('🔗 Gộp lưới', 'Gộp thành 1 vật, giữ màu riêng từng phần', () => tools.join(obj, pick())),
    ]),
    el('div', { className: 'info-line', textContent: 'Mẹo: giữ Shift + bấm để chọn nhiều vật, rồi gộp / nhóm cùng lúc.' }),
  ] : [el('div', { className: 'info-line', textContent: 'Thêm 1 vật nữa để ghép / khoét / gộp.' })]));
  details.append(blenderBlock(obj, tools));
  return details;
}

/** Thao tác chạy bằng Blender ẩn (chậm hơn vài giây nhưng chất lượng như phần mềm chuyên nghiệp). */
function blenderBlock(obj, tools) {
  const box = el('div', { className: 'field blender-block' }, [el('label', { textContent: '🟠 Blender (chất lượng cao)' })]);
  if (!blenderReady()) {
    box.append(el('div', { className: 'info-line', textContent: blenderMessage() }));
    return box;
  }
  const b = tools.blender;
  box.append(
    sliderRow('Bo tròn cạnh', { min: 5, max: 100, value: 30, step: 5, format: (v) => `độ bo ${v}%` }, 'Bo',
      (v) => b.meshOp(obj, 'bevel', { amount: v / 100, segments: 3 })),
    sliderRow('Làm lưới đều', { min: 0, max: 100, value: 50, step: 5, format: (v) => `chi tiết ${v}%` }, 'Làm đều',
      (v) => b.meshOp(obj, 'remesh', { detail: v / 100 })),
    Object.assign(el('button', { textContent: '🖨 Sửa lỗi để in 3D', title: 'Khép lỗ hở, gộp điểm trùng, sửa mặt lật (để máy in 3D / slicer không báo lỗi)' }),
      { onclick: () => b.meshOp(obj, 'repair') }),
    el('div', { className: 'info-line', textContent: 'Làm lưới đều sẽ bỏ vân/texture (lưới mới hoàn toàn).' }),
  );
  return box;
}
