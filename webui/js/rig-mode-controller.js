// Chế độ "Ghép xương" 2 bước cho người mới:
//  1) Đặt khớp (rig-place-editing.js): mẫu tự khớp theo hình thật (rig-body-frame + skeleton-auto-fit), kéo chỉnh -> "Gắn vào hình".
//  2) Tạo dáng: bấm khớp, kéo vòng tròn để xoay. Undo riêng từng lần xoay; "Xong" = 1 bước Undo của app.
//  Vật đã gắn bằng Easy3D: "Sửa khớp" quay lại bước 1 với khớp cũ (gắn lại thay vật cũ, giữ chuyển động).
import * as THREE from 'three';
import { TransformControls } from 'three/addons/controls/TransformControls.js';
import { chainTemplate, relinkMirrors } from './skeleton-templates.js';
import { autoFitHuman } from './skeleton-auto-fit.js';
import { computeBodyFrame, turnFrame } from './rig-body-frame.js';
import { bakePoseToMesh, buildRiggedObject, isRigged, jointsFromRig, objectLocalGeometry, skinnedMeshOf } from './rig-builder.js';
import { createRigHelpers } from './rig-helpers-view.js';
import { createPlaceEditing } from './rig-place-editing.js';
import { prepareRaycastMesh } from './rig-joint-drag.js';
import { createRigNaming } from './rig-bone-naming.js';
import { applyQuats, bindQuatsOf, createPoseStage, snapshotQuats } from './rig-pose-stage.js';
import { jointsToTemplate, templateToJoints } from './rig-template-library.js';
import { createGhosting } from './scene-ghosting.js';
import { meshesOf } from './mesh-split-merge-operations.js';
import { addObjectCommand, batchCommand, removeObjectCommand } from './scene-edit-commands.js';
import { toast } from './toast-notifications.js';

const ARMS_REPORT = { buông: 'tay buông', 'chữ T': 'tay dang ngang', mẫu: 'tay theo mẫu (hãy kéo chỉnh)' };

export function createRigMode({ viewport, store, stack, gizmo, onChange }) {
  let s = null;
  const helpers = createRigHelpers(viewport.scene);
  const ghosting = createGhosting(store);
  const tc = new TransformControls(viewport.camera, viewport.renderer.domElement);
  tc.getHelper().userData.editorOnly = true;
  viewport.scene.add(tc.getHelper());
  const pivot = new THREE.Object3D(); // tâm biến đổi "cả bộ xương"
  pivot.userData.editorOnly = true;
  viewport.scene.add(pivot);
  const notify = () => onChange(api.info());
  const place = createPlaceEditing({ viewport, helpers, tc, pivot, onChange: notify });
  const pose = createPoseStage({ helpers, tc, stack, store, getState: () => s, notify });
  let pointerOnGizmo = false;

  tc.addEventListener('mouseDown', () => { pointerOnGizmo = true; });
  tc.addEventListener('dragging-changed', (e) => {
    viewport.orbit.enabled = !e.value;
    if (s?.stage === 'place') place.gizmoDrag(e.value);
    else if (s?.stage === 'pose') pose.dragChanged(e.value);
  });
  tc.addEventListener('objectChange', () => { if (s?.stage === 'place') place.gizmoMoved(); });

  const busy = () => place.dragging || tc.dragging; // đang kéo: Undo giữa chừng làm lệch trạng thái
  const closePlace = () => { s?.cleanupRaycast?.(); if (s) s.cleanupRaycast = null; place.detach(); };
  const symOf = (frame) => ({ P0: frame.toLocal((frame.min[0] + frame.max[0]) / 2, 0, 0), U: frame.U.clone() });

  function fitJoints(template) {
    if (template === 'chain') return chainTemplate(s.box);
    const { joints, report } = autoFitHuman(s.frame);
    s.fitReport = `Tự khớp: ${report.legs ? '2 chân' : 'chân theo mẫu'}, ${ARMS_REPORT[report.arms]}.`;
    return joints;
  }

  function startPlace({ template, joints = null }) {
    closePlace();
    s.obj.updateWorldMatrix(true, true);
    const { geometry } = objectLocalGeometry(s.obj);
    Object.assign(s, { stage: 'place', template, selected: -1, undo: [], redo: [],
      positions: geometry.attributes.position.array, box: geometry.boundingBox, mesh: meshesOf(s.obj)[0] });
    s.size = s.box.getSize(new THREE.Vector3()).length();
    s.frame = computeBodyFrame(s.obj, s.positions, s.obj.worldToLocal(viewport.camera.position.clone()));
    s.sym = symOf(s.frame);
    s.cleanupRaycast = prepareRaycastMesh(s.mesh);
    s.joints = joints ?? fitJoints(template);
    tc.detach();
    place.attach(s);
    place.redraw(true);
    notify();
  }

  function startPose(group) {
    closePlace();
    pose.start(group);
  }

  const api = {
    get active() { return !!s; },
    get stage() { return s?.stage; },
    get joints() { return s?.joints ?? null; }, // smoke test: tìm vị trí chấm khớp để bấm chuột thật
    place,

    enter(obj) {
      if (s) return;
      if (!obj) return toast('Hãy bấm chọn 1 vật trước.', { type: 'warn' });
      if (obj.userData.kind === 'light') return toast('Đèn không gắn xương được.', { type: 'warn' });
      if (!isRigged(obj) && meshesOf(obj).length !== 1) {
        return toast('Vật này gồm nhiều phần — hãy "Gộp lưới" trước khi gắn xương.', { type: 'warn', timeout: 7000 });
      }
      s = { obj, mirror: true, branch: false, autoDepth: true, softness: 0.5, undo: [], redo: [] };
      ghosting.on(obj);
      gizmo.setEnabled(false);
      document.body.classList.add('rig-mode');
      if (isRigged(obj)) return startPose(obj);
      startPlace({ template: 'human' });
      toast(`${s.fitReport} Kéo thẳng chấm xanh để chỉnh; xương sai hướng thì bấm "↻ 90°" hoặc "⇄ Quay mặt".`, { timeout: 9000 });
    },

    exit() {
      if (!s) return;
      if (s.stage === 'pose') pose.commit();
      if (s.restoreQuats) applyQuats(s.bones, s.restoreQuats); // huỷ "Sửa khớp" -> về tư thế đang tạo
      pose.stop();
      closePlace();
      tc.detach();
      helpers.hide();
      ghosting.off();
      s = null;
      gizmo.setEnabled(true);
      document.body.classList.remove('rig-mode');
      store.changed();
      onChange(null);
    },

    select(i) {
      if (s.stage === 'place') place.select(i);
      else pose.select(i);
      notify();
    },
    pick(raycaster) { return helpers.pick(raycaster); },
    consumePointer() { const was = pointerOnGizmo || tc.dragging; pointerOnGizmo = false; return was; },
    /** Con trỏ đang trên tay cầm gizmo -> để TransformControls xử lý, không kéo chấm khớp. */
    gizmoHot: () => tc.dragging || (!!tc.object && tc.axis !== null),

    setTemplate(key) { if (s.stage === 'place') { s.template = key; place.replaceJoints(fitJoints(key), symOf(s.frame)); } },
    autoFit() {
      if (s.template === 'custom') s.template = 'human';
      place.replaceJoints(fitJoints(s.template), symOf(s.frame));
      toast(s.template === 'human' ? s.fitReport : 'Đã đặt lại theo mẫu.', { timeout: 5000 });
    },
    /** Đoán sai hướng: xoay khung thân quanh trục lên rồi tự khớp lại. */
    turn(quarterTurns) { s.frame = turnFrame(s.frame, quarterTurns, s.positions); api.autoFit(); },
    setOption(key, v) { s[key] = v; notify(); },
    /** Bật/tắt (bấm lại) chế độ dời / xoay / co giãn CẢ bộ xương. */
    setWhole(mode) { place.setWhole(place.wholeMode === mode ? null : mode); notify(); },
    useTemplate(tpl) { s.template = 'custom'; place.replaceJoints(templateToJoints(tpl, s.frame), symOf(s.frame)); },
    templateOf: (name) => jointsToTemplate(name, s.joints, s.frame),

    /** Bước 1 -> 2: tính trọng lượng da, thay vật bằng vật có xương (1 bước Undo của app). */
    bind() {
      const old = s.obj, oldNames = isRigged(old) ? skinnedMeshOf(old).skeleton.bones.map((b) => b.name).join('|') : '';
      closePlace();
      const group = buildRiggedObject(old, s.joints, s.softness);
      if (old.userData.anim) { // giữ chuyển động; số xương đổi thì bỏ phần tư thế xương
        group.userData.anim = JSON.parse(JSON.stringify(old.userData.anim));
        if (oldNames !== s.joints.map((j) => j.name).join('|')) group.userData.anim.keys.forEach((k) => delete k.bones); // khớp đổi -> chỉ số lệch
      }
      if (s.restoreQuats) applyQuats(s.bones, s.restoreQuats); // vật cũ (nằm trong Undo) giữ tư thế cũ
      s.restoreQuats = null;
      stack.execute(batchCommand('Gắn xương', [removeObjectCommand(store, old), addObjectCommand(store, group)]));
      ghosting.on(group);
      startPose(group);
      toast('Đã gắn xương! Bấm vào 1 khớp rồi kéo vòng tròn màu để xoay — tạo dáng tuỳ ý.', { type: 'ok', timeout: 8000 });
    },

    /** Bước 2 -> 1 (vật gắn bằng Easy3D): chỉnh lại vị trí / thêm / xoá khớp rồi gắn lại. */
    editJoints() {
      if (s.obj.userData.kind !== 'rigged') return toast('Chỉ sửa khớp được với xương gắn bằng Easy3D.', { type: 'warn', timeout: 6000 });
      pose.commit();
      const bones = s.bones, current = snapshotQuats(bones);
      applyQuats(bones, bindQuatsOf(s.obj)); // về tư thế lúc gắn: hình khớp đúng chỗ xương
      startPlace({ template: 'custom', joints: relinkMirrors(jointsFromRig(s.obj)) });
      Object.assign(s, { bones, restoreQuats: current });
    },

    resetPose: () => pose.resetPose(),
    /** Gỡ xương, giữ dáng đang tạo thành hình thường (để sửa hình / nặn / tô tiếp). */
    unrig() {
      const group = s.obj;
      api.exit();
      const mesh = bakePoseToMesh(group);
      stack.execute(batchCommand('Gỡ xương', [removeObjectCommand(store, group), addObjectCommand(store, mesh)]));
      toast('Đã gỡ xương — hình giữ nguyên dáng vừa tạo.', { type: 'ok' });
    },

    undo() { if (!s || busy()) return; if (s.stage === 'place') place.undo(); else pose.undo(); },
    redo() { if (!s || busy()) return; if (s.stage === 'place') place.redo(); else pose.redo(); },

    /** Cây xương cho panel: [{ name, label, parent }] theo thứ tự khớp/xương. */
    tree() {
      if (!s) return [];
      if (s.stage === 'place') return s.joints.map(({ name, label, parent }) => ({ name, label, parent }));
      return s.bones.map((b) => ({ name: b.name, label: b.userData.label ?? b.name, parent: s.bones.indexOf(b.parent) }));
    },

    info() {
      if (!s) return null;
      const t = api.tree()[s.selected];
      return { name: s.obj.name, stage: s.stage, template: s.template, mirror: s.mirror, branch: s.branch, autoDepth: s.autoDepth,
        softness: s.softness, whole: s.stage === 'place' ? place.wholeMode : null, index: s.selected,
        selected: t?.label ?? null, selectedName: t?.name ?? null, canEdit: s.obj.userData.kind === 'rigged',
        canUndo: s.undo.length > 0, canRedo: s.redo.length > 0 };
    },
  };
  api.naming = createRigNaming({ stack, store, getState: () => s, place, onChange: notify });

  return api;
}
