// Bước 1 "Đặt khớp": kéo khớp (đối xứng trái↔phải, kéo cả nhánh, tự vào giữa bề dày), dời/xoay/co giãn CẢ bộ xương,
// thêm/xoá/đổi tên khớp, Undo riêng. Khớp lưu toạ độ LOCAL của vật; mặt phẳng đối xứng = (điểm P0, pháp tuyến U).
import * as THREE from 'three';
import { descendantsOf, dragPlane, surfaceMidpoint } from './rig-joint-drag.js';
import { centerJointDepth } from './skeleton-auto-fit.js';
import { relinkMirrors } from './skeleton-templates.js';
import { boneNameProblem, cloneJoints, withChildAdded, withJointRemoved } from './rig-joint-structure.js';
import { toast } from './toast-notifications.js';

const MAX_UNDO = 60;

export function createPlaceEditing({ viewport, helpers, tc, pivot, onChange }) {
  let s = null; // state của rig-mode-controller (stage 'place')
  let drag = null, whole = null;

  const snapshot = () => ({ joints: cloneJoints(s.joints), sym: { P0: s.sym.P0.clone(), U: s.sym.U.clone() } });
  function pushUndo(snap = snapshot()) {
    s.undo.push(snap);
    if (s.undo.length > MAX_UNDO) s.undo.shift();
    s.redo = [];
  }
  const mirrorPoint = (p) => p.clone().addScaledVector(s.sym.U, -2 * p.clone().sub(s.sym.P0).dot(s.sym.U));
  const toLocal = (world) => s.obj.worldToLocal(world.clone());
  const toWorld = (local) => local.clone().applyMatrix4(s.obj.matrixWorld);

  function redraw(full = false) {
    const pts = s.joints.map((j) => j.position);
    if (full) {
      helpers.show(pts, s.joints.map((j) => j.parent), s.obj.matrixWorld, s.size * 0.018);
      helpers.setSelected(s.selected);
    } else helpers.update(pts);
  }

  /** Dời khớp i tới `local`; kéo cả nhánh thì con cháu đi cùng; đối xứng thì khớp bên kia đi theo. */
  function moveJoint(i, local, starts = null) {
    const base = starts ?? s.joints.map((j) => j.position.clone());
    const delta = local.clone().sub(base[i]);
    const moved = [i, ...(s.branch ? descendantsOf(s.joints, i) : [])];
    moved.forEach((k) => s.joints[k].position.copy(base[k]).add(delta));
    if (s.mirror) {
      moved.forEach((k) => {
        const m = s.joints[k].mirror;
        if (m >= 0 && !moved.includes(m)) s.joints[m].position.copy(mirrorPoint(s.joints[k].position));
      });
    }
    redraw();
  }

  const api = {
    attach(state) { s = state; whole = null; drag = null; },
    detach() { s = null; drag = null; whole = null; },
    redraw,
    snapshot, pushUndo,

    /** attachGizmo = false khi đang kéo chấm: gizmo gắn ngay dưới con trỏ sẽ tưởng bị kéo theo. */
    select(i, attachGizmo = true) {
      api.setWhole(null);
      s.selected = i;
      helpers.setSelected(i);
      tc.detach();
      if (i >= 0 && attachGizmo) { tc.setMode('translate'); tc.setSpace('world'); tc.attach(helpers.handle(i)); }
    },

    // ---- kéo thẳng chấm khớp ----
    beginDrag(raycaster) {
      const i = helpers.pick(raycaster);
      if (i < 0) return false;
      api.select(i, false);
      const world = toWorld(s.joints[i].position);
      drag = { i, plane: dragPlane(world, viewport.camera), starts: s.joints.map((j) => j.position.clone()), before: snapshot(), moved: false };
      return true;
    },
    dragTo(raycaster) {
      if (!drag) return;
      let world = s.autoDepth ? surfaceMidpoint(raycaster, s.mesh) : null;
      world ??= raycaster.ray.intersectPlane(drag.plane, new THREE.Vector3());
      if (!world) return;
      moveJoint(drag.i, toLocal(world), drag.starts);
      drag.moved = true;
    },
    endDrag() {
      if (!drag) return false;
      const { moved, before, i } = drag;
      drag = null;
      api.select(i);
      if (moved) { pushUndo(before); onChange(); }
      return true;
    },
    get dragging() { return !!drag; },

    // ---- mũi tên TransformControls trên khớp đang chọn ----
    gizmoMoved() {
      if (whole) return api.wholeMoved();
      if (s.selected < 0) return;
      const handle = helpers.handle(s.selected).position.clone(); // helpers dùng toạ độ local
      moveJoint(s.selected, handle);
    },
    gizmoDrag(started) {
      if (started) s.gizmoBefore = snapshot();
      else if (s.gizmoBefore) { pushUndo(s.gizmoBefore); s.gizmoBefore = null; if (whole) api.setWhole(whole.mode); onChange(); }
    },

    // ---- cả bộ xương: dời / xoay / co giãn quanh khớp gốc ----
    setWhole(mode) {
      whole = null;
      if (!mode) { if (tc.object === pivot) tc.detach(); return; }
      s.selected = -1;
      helpers.setSelected(-1);
      const root = s.joints.find((j) => j.parent < 0) ?? s.joints[0];
      s.obj.updateWorldMatrix(true, false);
      pivot.position.copy(toWorld(root.position));
      s.obj.getWorldQuaternion(pivot.quaternion);
      pivot.scale.setScalar(1);
      pivot.updateMatrixWorld(true);
      whole = { mode, base: pivot.matrixWorld.clone().invert(), starts: cloneJoints(s.joints), sym: { P0: s.sym.P0.clone(), U: s.sym.U.clone() } };
      tc.setMode(mode);
      tc.setSpace('local');
      tc.attach(pivot);
    },
    wholeMoved() {
      pivot.updateMatrixWorld(true);
      const objW = s.obj.matrixWorld, inv = objW.clone().invert();
      const m = inv.multiply(pivot.matrixWorld).multiply(whole.base).multiply(objW); // delta, toạ độ local
      whole.starts.forEach((j, k) => s.joints[k].position.copy(j.position).applyMatrix4(m));
      s.sym.P0.copy(whole.sym.P0).applyMatrix4(m);
      s.sym.U.copy(whole.sym.U).transformDirection(m);
      redraw();
    },
    get wholeMode() { return whole?.mode ?? null; },

    // ---- sửa cấu trúc ----
    replaceJoints(joints, sym = null) {
      pushUndo();
      s.joints = joints;
      if (sym) s.sym = sym;
      s.selected = -1;
      tc.detach();
      redraw(true);
      onChange();
    },
    centerDepth(all) {
      pushUndo();
      const idx = all ? s.joints.map((_, k) => k) : [s.selected];
      idx.forEach((k) => { s.joints[k].position = centerJointDepth(s.frame, s.joints[k].position); });
      redraw(true);
      onChange();
    },
    addChild() {
      pushUndo();
      s.joints = withChildAdded(s.joints, Math.max(0, s.selected), s.frame.H.clone().multiplyScalar(s.frame.height * 0.08));
      redraw(true);
      api.select(s.joints.length - 1);
      onChange();
    },
    removeSelected() {
      if (s.selected < 0) return;
      const res = withJointRemoved(s.joints, s.selected);
      if (res.error) return toast(res.error, { type: 'warn' });
      pushUndo();
      s.joints = res.joints;
      s.selected = -1;
      tc.detach();
      redraw(true);
      onChange();
    },
    rename(i, name) {
      name = name.trim();
      const problem = boneNameProblem(name, s.joints.filter((_, k) => k !== i).map((j) => j.name));
      if (problem) { toast(problem, { type: 'warn', timeout: 6000 }); return false; }
      pushUndo();
      s.joints[i].name = name;
      relinkMirrors(s.joints);
      onChange();
      return true;
    },
    /** Nhập toạ độ số (thế giới, mét). */
    setWorldPosition(i, world) {
      pushUndo();
      moveJoint(i, toLocal(world));
      if (s.selected === i) tc.attach(helpers.handle(i));
      onChange();
    },
    worldPosition: (i) => toWorld(s.joints[i].position),

    undo() { swap(s.undo, s.redo); },
    redo() { swap(s.redo, s.undo); },
  };

  function swap(from, to) {
    if (!from.length) return;
    to.push(snapshot());
    const snap = from.pop();
    s.joints = snap.joints;
    s.sym = snap.sym;
    s.selected = -1;
    whole = null;
    tc.detach();
    redraw(true);
    onChange();
  }

  return api;
}
