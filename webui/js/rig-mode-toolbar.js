// Thanh công cụ + chuột/phím cho "Ghép xương" (2 bước: Đặt khớp -> Tạo dáng).
import * as THREE from 'three';
import { SKELETON_TEMPLATES } from './skeleton-templates.js';

export function createRigToolbar(viewportEl, rigMode) {
  const bar = Object.assign(document.createElement('div'), { className: 'edit-toolbar rig-toolbar', hidden: true });
  bar.innerHTML = `
    <div class="edit-row" id="rig-place">
      <b class="edit-title">🦴 Ghép xương: <span class="rig-name"></span> — Bước 1/2: đặt khớp</b>
      <div class="seg" id="rig-templates"></div>
      <label class="edit-check" title="Dời khớp tay/chân bên trái thì bên phải đi theo"><input type="checkbox" id="rig-mirror"> Kéo đối xứng</label>
      <label class="edit-soft" title="Thấp: chỗ gập sắc nét. Cao: chỗ gập uốn mềm">Độ mềm khớp
        <input type="range" id="rig-soft" min="0" max="1" step="0.05"></label>
      <button class="primary" data-op="bind">🔗 Gắn vào hình</button><button data-op="exit">✕ Huỷ</button>
    </div>
    <div class="edit-row" id="rig-pose">
      <b class="edit-title">🦴 Tạo dáng: <span class="rig-name"></span> — Bước 2/2</b>
      <span class="edit-count" id="rig-selected"></span>
      <button data-op="undo" title="Hoàn tác (Ctrl+Z)">↶</button><button data-op="redo" title="Làm lại (Ctrl+Y)">↷</button>
      <button data-op="resetPose" title="Về tư thế lúc mới gắn xương">⟲ Đặt lại tư thế</button>
      <button data-op="unrig" title="Bỏ xương, giữ dáng hiện tại thành hình thường">Gỡ xương (giữ dáng)</button>
      <button class="primary" data-op="exit" title="Xong (Enter)">✔ Xong</button>
    </div>
    <div class="edit-hint" id="rig-hint"></div>`;
  viewportEl.append(bar);
  const $ = (sel) => bar.querySelector(sel);

  $('#rig-templates').append(...Object.entries(SKELETON_TEMPLATES).map(([key, t]) => {
    const b = Object.assign(document.createElement('button'), { textContent: t.label, title: t.hint });
    b.dataset.template = key;
    b.onclick = () => rigMode.setTemplate(key);
    return b;
  }));
  bar.addEventListener('click', (e) => {
    const op = e.target.closest('button')?.dataset.op;
    if (op) rigMode[op]();
  });
  $('#rig-mirror').onchange = (e) => rigMode.setMirror(e.target.checked);
  $('#rig-soft').oninput = (e) => rigMode.setSoftness(Number(e.target.value));

  return {
    update(info) {
      bar.hidden = !info;
      if (!info) return;
      const place = info.stage === 'place';
      $('#rig-place').hidden = !place;
      $('#rig-pose').hidden = place;
      bar.querySelectorAll('.rig-name').forEach((el) => { el.textContent = info.name; });
      bar.querySelectorAll('[data-template]').forEach((b) => b.classList.toggle('active', b.dataset.template === info.template));
      $('#rig-mirror').checked = info.mirror;
      $('#rig-soft').value = info.softness;
      $('#rig-selected').textContent = info.selected ? `Đang chọn: ${info.selected}` : 'Chưa chọn khớp';
      $('#rig-pose [data-op="undo"]').disabled = !info.canUndo;
      $('#rig-pose [data-op="redo"]').disabled = !info.canRedo;
      $('#rig-hint').textContent = place
        ? 'Bấm 1 chấm xanh rồi kéo mũi tên để dời khớp · đặt khớp ở GIỮA tay/chân và ngay chỗ gập (khuỷu, gối, cổ)'
        : 'Bấm 1 khớp rồi kéo vòng tròn màu để xoay phần đó · bắt đầu kéo ngoài vật để xoay góc nhìn';
    },
  };
}

/** Bấm (không kéo) vào chấm khớp để chọn; bấm chỗ trống để bỏ chọn. Phím: Esc/Enter xong, Ctrl+Z/Y. */
export function attachRigInput(viewport, rigMode) {
  const canvas = viewport.renderer.domElement;
  const raycaster = new THREE.Raycaster();
  let down = null;
  canvas.addEventListener('pointerdown', (e) => { if (rigMode.active && e.button === 0) down = { x: e.clientX, y: e.clientY }; });
  canvas.addEventListener('pointerup', (e) => {
    if (!rigMode.active || !down) return;
    const onGizmo = rigMode.consumePointer();
    const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y);
    down = null;
    if (onGizmo || moved > 5) return;
    const r = canvas.getBoundingClientRect();
    raycaster.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), viewport.camera);
    rigMode.select(rigMode.pick(raycaster));
  });
  document.addEventListener('keydown', (e) => {
    if (!rigMode.active || e.target.closest?.('input, textarea')) return;
    const ctrl = e.ctrlKey || e.metaKey, key = e.key.toLowerCase();
    const map = {
      escape: () => rigMode.exit(), enter: () => rigMode.exit(),
      z: ctrl && (() => (e.shiftKey ? rigMode.redo() : rigMode.undo())), y: ctrl && (() => rigMode.redo()),
    };
    if (map[key]) { e.preventDefault(); e.stopPropagation(); map[key](); return; }
    if (!ctrl) e.stopPropagation(); // chặn W/E/R/Delete... của app khi đang ghép xương
  }, true);
}
