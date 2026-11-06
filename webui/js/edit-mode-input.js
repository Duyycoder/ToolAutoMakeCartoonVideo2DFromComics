// Chuột + phím trong chế độ "Chỉnh điểm": bấm chọn / kéo khung chọn, phím tắt kiểu Blender.
export function attachEditModeInput(viewport, editMode, viewportEl) {
  const canvas = viewport.renderer.domElement;
  const rectEl = Object.assign(document.createElement('div'), { className: 'select-rect', hidden: true });
  viewportEl.append(rectEl);
  let down = null;
  let throughAll = false;

  const rectFrom = (a, b) => ({
    left: Math.min(a.x, b.x), right: Math.max(a.x, b.x), top: Math.min(a.y, b.y), bottom: Math.max(a.y, b.y),
  });

  canvas.addEventListener('pointerdown', (e) => {
    if (!editMode.active || e.button !== 0) return;
    down = { x: e.clientX, y: e.clientY, additive: e.shiftKey || e.ctrlKey, box: editMode.tool === 'box' };
    if (down.box) viewport.orbit.enabled = false; // kéo khung, không xoay camera
  });
  window.addEventListener('pointermove', (e) => {
    if (!down?.box) return;
    const r = rectFrom(down, { x: e.clientX, y: e.clientY });
    const v = viewportEl.getBoundingClientRect();
    Object.assign(rectEl.style, { left: `${r.left - v.left}px`, top: `${r.top - v.top}px`,
      width: `${r.right - r.left}px`, height: `${r.bottom - r.top}px` });
    rectEl.hidden = false;
  });
  window.addEventListener('pointerup', (e) => {
    if (!down) return;
    const start = down;
    down = null;
    rectEl.hidden = true;
    if (!editMode.active) return;
    const onGizmo = editMode.consumeGizmoPointer();
    const moved = Math.hypot(e.clientX - start.x, e.clientY - start.y);
    if (start.box) {
      viewport.orbit.enabled = true;
      if (moved > 4) return editMode.selectBox(rectFrom(start, { x: e.clientX, y: e.clientY }), start.additive, throughAll);
    }
    if (!onGizmo && moved < 5) editMode.clickSelect(e.clientX, e.clientY, start.additive);
  });

  // Capture: chạy TRƯỚC phím tắt của app (W/E/R, Delete, Ctrl+Z...) và chặn lại khi đang chỉnh điểm.
  document.addEventListener('keydown', (e) => {
    if (!editMode.active || e.target.closest?.('input, textarea')) return;
    const ctrl = e.ctrlKey || e.metaKey;
    const key = e.key.toLowerCase();
    const map = {
      tab: () => editMode.exit(), escape: () => editMode.exit(),
      delete: () => editMode.deleteSelection(), backspace: () => editMode.deleteSelection(),
      z: ctrl && (() => (e.shiftKey ? editMode.redo() : editMode.undo())), y: ctrl && (() => editMode.redo()),
      a: !ctrl && (() => editMode.selectAll()),
      1: () => editMode.setSelectMode('vertex'), 2: () => editMode.setSelectMode('face'),
      w: !ctrl && (() => editMode.setGizmoMode('translate')), e: !ctrl && (() => editMode.setGizmoMode('rotate')),
      r: !ctrl && (() => editMode.setGizmoMode('scale')),
    };
    if (map[key]) {
      e.preventDefault();
      e.stopPropagation();
      map[key]();
    }
  }, true);

  return { setThroughAll(v) { throughAll = v; } };
}
