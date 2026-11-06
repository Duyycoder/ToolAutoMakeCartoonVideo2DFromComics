// Thanh công cụ + chuột/phím cho "Ghép xương" (2 bước: Đặt khớp -> Tạo dáng).
import * as THREE from 'three';
import { SKELETON_TEMPLATES } from './skeleton-templates.js';
import { listRigTemplates, loadRigTemplate } from './rig-template-library.js';
import { toast } from './toast-notifications.js';

const POSE_HINTS = {
  rotate: 'Kéo vòng tròn màu để xoay khớp đang có tay cầm.',
  translate: 'Kéo mũi tên X, Y hoặc Z để đặt đích theo trục của cảnh.',
  screen: 'Kéo chấm khớp để đặt đích theo mặt phẳng màn hình.',
};

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
      <div class="seg" role="group" aria-label="Cách chỉnh xương">
        <button data-pose-mode="rotate" title="Xoay xương quanh khớp">Xoay</button>
        <button data-pose-mode="translate" title="Dời xương theo các trục X, Y, Z của cảnh">Dời 3D</button>
        <button data-pose-mode="screen" title="Đặt đích theo mặt phẳng của góc nhìn hiện tại">Dời 2D</button>
      </div>
      <label class="edit-check" title="Xoay các khớp để theo điểm kéo trong tầm với. Bỏ chọn để cho phép kéo giãn xương.">
        <input type="checkbox" data-opt="lockBoneLengths" checked> Giữ chiều dài xương
      </label>
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
    if (btn?.dataset.poseMode) rigMode.setPoseMode(btn.dataset.poseMode);
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
      bar.querySelectorAll('[data-pose-mode]').forEach((b) => {
        const active = b.dataset.poseMode === info.poseMode;
        b.classList.toggle('active', active);
        b.setAttribute('aria-pressed', String(active));
      });
      bar.querySelectorAll('[data-opt]').forEach((el) => { el.checked = info[el.dataset.opt]; });
      $('#rig-soft').value = info.softness;
      $('#rig-selected').textContent = info.selectedCount > 1 ? `Đã chọn ${info.selectedCount} khớp`
        : info.selected ? `Đang chọn: ${info.selected}` : 'Chưa chọn khớp';
      bar.querySelectorAll('[data-op="undo"]').forEach((b) => { b.disabled = !info.canUndo; });
      bar.querySelectorAll('[data-op="redo"]').forEach((b) => { b.disabled = !info.canRedo; });
      $('#rig-pose [data-op="editJoints"]').disabled = !info.canEdit;
      const lengthHint = info.poseMode === 'rotate' ? '' : info.lockBoneLengths
        ? ' Kéo cổ tay hoặc cổ chân trong tầm với để gập khuỷu hoặc gối, giữ vai và hông tại chỗ. Kéo khớp gốc (Hông) để dời cả nhân vật.'
        : ' Chế độ kéo tự do có thể làm giãn xương.';
      $('#rig-hint').textContent = !place
        ? `${POSE_HINTS[info.poseMode]}${lengthHint} Giữ Shift và kéo khung để chọn thêm, hoặc Shift + bấm để bật/tắt từng khớp. Bấm “Ghi tư thế” trên thanh Chuyển động để lưu dáng.`
        : info.whole ? 'Kéo tay cầm để biến đổi CẢ bộ xương · bấm lại nút đang sáng hoặc bấm 1 chấm để quay về chỉnh từng khớp'
          : 'Kéo thẳng chấm xanh để dời khớp (mũi tên màu: dời theo 1 trục) · đặt khớp ở GIỮA tay/chân, ngay chỗ gập (khuỷu, gối, cổ)';
    },
  };
}

/** Kéo chấm khớp / bấm để chọn; giữ Shift để chọn nhiều khớp khi tạo dáng. */
export function attachRigInput(viewport, rigMode) {
  const canvas = viewport.renderer.domElement;
  const viewportEl = canvas.parentElement;
  const boxOverlay = Object.assign(document.createElement('div'), { className: 'select-rect rig-select-rect', hidden: true });
  viewportEl.append(boxOverlay);
  const raycaster = new THREE.Raycaster();
  let down = null;
  const moved = (e, start) => Math.hypot(e.clientX - start.x, e.clientY - start.y) > 5;
  const boxFrom = (e, { x, y }) => ({
    left: Math.min(x, e.clientX), top: Math.min(y, e.clientY), right: Math.max(x, e.clientX), bottom: Math.max(y, e.clientY),
  });
  const castFrom = (e) => {
    const r = canvas.getBoundingClientRect();
    raycaster.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), viewport.camera);
    return raycaster;
  };
  // capture: chạy TRƯỚC OrbitControls -> bấm trúng chấm khớp thì kéo khớp, không xoay góc nhìn.
  canvas.addEventListener('pointerdown', (e) => {
    if (!rigMode.active || e.button !== 0 || down?.drag || down?.box) return;
    const { stage } = rigMode;
    const box = stage === 'pose' && e.shiftKey;
    down = { id: e.pointerId, x: e.clientX, y: e.clientY, stage, drag: null, box };
    if (box) {
      viewport.orbit.enabled = false;
      canvas.setPointerCapture(e.pointerId);
      e.stopImmediatePropagation();
      return;
    }
    const screen = stage === 'pose' && rigMode.info().poseMode === 'screen';
    const drag = screen ? rigMode.pose : (stage === 'place' && !rigMode.gizmoHot() ? rigMode.place : null);
    if (drag?.beginDrag(castFrom(e))) {
      down.drag = drag;
      viewport.orbit.enabled = false;
      canvas.setPointerCapture(e.pointerId);
      if (screen) e.stopImmediatePropagation();
    }
  }, true);
  canvas.addEventListener('pointermove', (e) => {
    if (down?.id !== e.pointerId || down.stage !== rigMode.stage) return;
    if (down.box) {
      if (!down.boxDragged && !moved(e, down)) return;
      down.boxDragged = true;
      const rect = boxFrom(e, down), viewportRect = viewportEl.getBoundingClientRect();
      Object.assign(boxOverlay.style, { left: `${rect.left - viewportRect.left}px`, top: `${rect.top - viewportRect.top}px`,
        width: `${rect.right - rect.left}px`, height: `${rect.bottom - rect.top}px` });
      boxOverlay.hidden = false;
    } else down.drag?.dragTo(castFrom(e));
  });
  const finish = (e, cancelled = false) => {
    if (down?.id !== e.pointerId) return;
    const start = down;
    const { stage, drag, box, boxDragged } = start;
    down = null;
    if (box) {
      boxOverlay.hidden = true;
      viewport.orbit.enabled = true;
      if (cancelled || stage !== rigMode.stage) return;
      if (boxDragged || moved(e, start)) rigMode.selectBox(boxFrom(e, start));
      else {
        const i = rigMode.pick(castFrom(e));
        if (i >= 0) rigMode.select(i, true);
      }
      return;
    }
    if (drag) {
      viewport.orbit.enabled = true;
      if (stage === rigMode.stage) {
        if (cancelled && stage === 'pose') drag.cancelDrag();
        else drag.endDrag();
        rigMode.consumePointer();
      }
      return;
    }
    if (cancelled || stage !== rigMode.stage) return;
    const onGizmo = rigMode.consumePointer();
    if (onGizmo || moved(e, start)) return;
    rigMode.select(rigMode.pick(castFrom(e)));
  };
  canvas.addEventListener('pointerup', (e) => finish(e));
  canvas.addEventListener('pointercancel', (e) => finish(e, true));
  canvas.addEventListener('lostpointercapture', (e) => finish(e, true));
  document.addEventListener('keydown', (e) => {
    if (!rigMode.active || e.target.closest?.('input, textarea, select')) return;
    if (down?.drag || down?.box) { e.preventDefault(); e.stopPropagation(); return; } // đang kéo: chờ thả chuột
    const ctrl = e.ctrlKey || e.metaKey, key = e.key.toLowerCase();
    const map = {
      escape: () => rigMode.exit(), enter: () => rigMode.exit(),
      z: ctrl && (() => (e.shiftKey ? rigMode.redo() : rigMode.undo())), y: ctrl && (() => rigMode.redo()),
    };
    if (map[key]) { e.preventDefault(); e.stopPropagation(); map[key](); return; }
    if (!ctrl) e.stopPropagation(); // chặn W/E/R/Delete... của app khi đang ghép xương
  }, true);
}
