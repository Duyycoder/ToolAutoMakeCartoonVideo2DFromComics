// Thanh công cụ + chuột/phím cho "Ghép xương" (2 bước: Đặt khớp -> Tạo dáng).
import * as THREE from 'three';
import { SKELETON_TEMPLATES } from './skeleton-templates.js';
import { listRigTemplates, loadRigTemplate } from './rig-template-library.js';
import { toast } from './toast-notifications.js';

export function createRigToolbar(viewportEl, rigMode) {
  const bar = Object.assign(document.createElement('div'), { className: 'edit-toolbar rig-toolbar', hidden: true });
  bar.innerHTML = `
    <div class="edit-row" id="rig-place">
      <b class="edit-title">🦴 Ghép xương: <span class="rig-name"></span> — Bước 1/2: đặt khớp</b>
      <div class="seg" id="rig-templates"></div>
      <select id="rig-saved" title="Mẫu xương đã lưu (💾 trong cây xương)"><option value="">📁 Mẫu đã lưu…</option></select>
      <span class="sep"></span>
      <button data-op="autoFit" title="Dò lại tay, chân, thân theo hình và đặt khớp vào giữa">✨ Tự khớp</button>
      <button data-op="turn" data-arg="1" title="Xương nằm vuông góc với hình? Xoay hướng 90° rồi tự khớp lại">↻ 90°</button>
      <button data-op="turn" data-arg="2" title="Trái/phải bị ngược? Quay mặt trước ra sau rồi tự khớp lại">⇄ Quay mặt</button>
      <span class="sep"></span>
      <span class="edit-count">Cả bộ xương:</span>
      <div class="seg" id="rig-whole">
        <button data-whole="translate" title="Dời cả bộ xương">✥</button><button data-whole="rotate" title="Xoay cả bộ xương (kéo vòng tròn)">⟳</button><button data-whole="scale" title="Co giãn cả bộ xương">⤢</button>
      </div>
      <button data-op="undo" title="Hoàn tác (Ctrl+Z)">↶</button><button data-op="redo" title="Làm lại (Ctrl+Y)">↷</button>
      <button class="primary" data-op="bind">🔗 Gắn vào hình</button><button data-op="exit">✕ Huỷ</button>
    </div>
    <div class="edit-row" id="rig-place-options">
      <label class="edit-check" title="Dời khớp tay/chân bên trái thì bên phải đi theo"><input type="checkbox" data-opt="mirror"> Kéo đối xứng</label>
      <label class="edit-check" title="Dời 1 khớp thì các khớp con (vd. vai -> khuỷu, tay) đi cùng"><input type="checkbox" data-opt="branch"> Kéo cả nhánh</label>
      <label class="edit-check" title="Khi kéo, khớp tự nằm GIỮA bề dày tay/chân dưới con trỏ (không lòi ra trước/sau)"><input type="checkbox" data-opt="autoDepth"> Tự vào giữa bề dày</label>
      <label class="edit-soft" title="Thấp: chỗ gập sắc nét. Cao: chỗ gập uốn mềm">Độ mềm khớp
        <input type="range" id="rig-soft" min="0" max="1" step="0.05"></label>
    </div>
    <div class="edit-row" id="rig-pose">
      <b class="edit-title">🦴 Tạo dáng: <span class="rig-name"></span> — Bước 2/2</b>
      <span class="edit-count" id="rig-selected"></span>
      <button data-op="undo" title="Hoàn tác (Ctrl+Z)">↶</button><button data-op="redo" title="Làm lại (Ctrl+Y)">↷</button>
      <button data-op="resetPose" title="Về tư thế lúc mới gắn xương">⟲ Đặt lại tư thế</button>
      <button data-op="editJoints" title="Quay lại bước 1: dời / thêm / xoá khớp rồi gắn lại">✏ Sửa khớp</button>
      <button data-op="unrig" title="Bỏ xương, giữ dáng hiện tại thành hình thường">Gỡ xương (giữ dáng)</button>
      <button class="primary" data-op="exit" title="Xong (Enter)">✔ Xong</button>
    </div>
    <div class="edit-hint" id="rig-hint"></div>`;
  viewportEl.append(bar);
  const $ = (sel) => bar.querySelector(sel);
  const saved = $('#rig-saved');

  $('#rig-templates').append(...Object.entries(SKELETON_TEMPLATES).map(([key, t]) => {
    const b = Object.assign(document.createElement('button'), { textContent: t.label, title: t.hint });
    b.dataset.template = key;
    b.onclick = () => rigMode.setTemplate(key);
    return b;
  }));
  bar.addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (btn?.dataset.op) rigMode[btn.dataset.op](btn.dataset.arg ? Number(btn.dataset.arg) : undefined);
    if (btn?.dataset.whole) rigMode.setWhole(btn.dataset.whole);
  });
  bar.querySelectorAll('[data-opt]').forEach((el) => { el.onchange = () => rigMode.setOption(el.dataset.opt, el.checked); });
  $('#rig-soft').oninput = (e) => rigMode.setOption('softness', Number(e.target.value));

  async function refreshSaved() {
    try {
      const files = await listRigTemplates();
      saved.replaceChildren(saved.options[0], ...files.map((f) => Object.assign(document.createElement('option'), { value: f, textContent: f.replace(/\.json$/, '') })));
    } catch { /* backend chưa có thư mục mẫu -> để trống */ }
  }
  saved.onchange = async () => {
    const file = saved.value;
    saved.value = '';
    if (!file) return;
    try { rigMode.useTemplate(await loadRigTemplate(file)); } catch (err) { toast(`Không mở được mẫu: ${err.message}`, { type: 'err' }); }
  };

  let wasShown = false;
  return {
    refreshSaved,
    update(info) {
      bar.hidden = !info;
      if (info && !wasShown) refreshSaved();
      wasShown = !!info;
      if (!info) return;
      const place = info.stage === 'place';
      $('#rig-place').hidden = $('#rig-place-options').hidden = !place;
      $('#rig-pose').hidden = place;
      bar.querySelectorAll('.rig-name').forEach((el) => { el.textContent = info.name; });
      bar.querySelectorAll('[data-template]').forEach((b) => b.classList.toggle('active', b.dataset.template === info.template));
      bar.querySelectorAll('[data-whole]').forEach((b) => b.classList.toggle('active', b.dataset.whole === info.whole));
      bar.querySelectorAll('[data-opt]').forEach((el) => { el.checked = info[el.dataset.opt]; });
      $('#rig-soft').value = info.softness;
      $('#rig-selected').textContent = info.selected ? `Đang chọn: ${info.selected}` : 'Chưa chọn khớp';
      bar.querySelectorAll('[data-op="undo"]').forEach((b) => { b.disabled = !info.canUndo; });
      bar.querySelectorAll('[data-op="redo"]').forEach((b) => { b.disabled = !info.canRedo; });
      $('#rig-pose [data-op="editJoints"]').disabled = !info.canEdit;
      $('#rig-hint').textContent = !place
        ? 'Bấm 1 khớp rồi kéo vòng tròn màu để xoay phần đó · bắt đầu kéo ngoài vật để xoay góc nhìn'
        : info.whole ? 'Kéo tay cầm để biến đổi CẢ bộ xương · bấm lại nút đang sáng hoặc bấm 1 chấm để quay về chỉnh từng khớp'
          : 'Kéo thẳng chấm xanh để dời khớp (mũi tên màu: dời theo 1 trục) · đặt khớp ở GIỮA tay/chân, ngay chỗ gập (khuỷu, gối, cổ)';
    },
  };
}

/** Kéo chấm khớp / bấm để chọn; bấm chỗ trống để bỏ chọn. Phím: Esc/Enter xong, Ctrl+Z/Y. */
export function attachRigInput(viewport, rigMode) {
  const canvas = viewport.renderer.domElement;
  const raycaster = new THREE.Raycaster();
  let down = null, dragging = false;
  const castFrom = (e) => {
    const r = canvas.getBoundingClientRect();
    raycaster.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), viewport.camera);
    return raycaster;
  };
  // capture: chạy TRƯỚC OrbitControls -> bấm trúng chấm khớp thì kéo khớp, không xoay góc nhìn.
  canvas.addEventListener('pointerdown', (e) => {
    if (!rigMode.active || e.button !== 0) return;
    down = { x: e.clientX, y: e.clientY };
    if (rigMode.stage === 'place' && !rigMode.gizmoHot() && rigMode.place.beginDrag(castFrom(e))) {
      dragging = true;
      viewport.orbit.enabled = false;
      canvas.setPointerCapture(e.pointerId);
    }
  }, true);
  canvas.addEventListener('pointermove', (e) => { if (dragging) rigMode.place.dragTo(castFrom(e)); });
  const finishDrag = () => {
    dragging = false;
    down = null;
    viewport.orbit.enabled = true; // luôn trả lại xoay góc nhìn, kể cả khi đã thoát chế độ
    if (rigMode.active) { rigMode.place.endDrag(); rigMode.consumePointer(); }
  };
  canvas.addEventListener('pointercancel', () => { if (dragging) finishDrag(); });
  canvas.addEventListener('pointerup', (e) => {
    if (dragging) return finishDrag();
    if (!rigMode.active || !down) return;
    const onGizmo = rigMode.consumePointer();
    const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y);
    down = null;
    if (onGizmo || moved > 5) return;
    rigMode.select(rigMode.pick(castFrom(e)));
  });
  document.addEventListener('keydown', (e) => {
    if (!rigMode.active || e.target.closest?.('input, textarea, select')) return;
    if (dragging) { e.preventDefault(); e.stopPropagation(); return; } // đang kéo chấm: chờ thả chuột
    const ctrl = e.ctrlKey || e.metaKey, key = e.key.toLowerCase();
    const map = {
      escape: () => rigMode.exit(), enter: () => rigMode.exit(),
      z: ctrl && (() => (e.shiftKey ? rigMode.redo() : rigMode.undo())), y: ctrl && (() => rigMode.redo()),
    };
    if (map[key]) { e.preventDefault(); e.stopPropagation(); map[key](); return; }
    if (!ctrl) e.stopPropagation(); // chặn W/E/R/Delete... của app khi đang ghép xương
  }, true);
}
