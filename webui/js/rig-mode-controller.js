// Chế độ "Ghép xương" 2 bước cho người mới:
//  1) Đặt khớp: chọn mẫu (Người / Chuỗi), kéo các chấm cho khớp hình (kéo đối xứng trái↔phải) -> "Gắn vào hình".
//  2) Tạo dáng: bấm khớp, kéo vòng tròn để xoay. Undo riêng từng lần xoay; "Xong" = 1 bước Undo của app.
import * as THREE from 'three';
import { TransformControls } from 'three/addons/controls/TransformControls.js';
import { fitTemplate } from './skeleton-templates.js';
import { bakePoseToMesh, buildRiggedObject, isRigged, objectLocalGeometry, skinnedMeshOf } from './rig-builder.js';
import { createRigHelpers } from './rig-helpers-view.js';
import { createGhosting } from './scene-ghosting.js';
import { meshesOf } from './mesh-split-merge-operations.js';
import { addObjectCommand, batchCommand, removeObjectCommand } from './scene-edit-commands.js';
import { toast } from './toast-notifications.js';

const snapshotQuats = (bones) => bones.map((b) => b.quaternion.clone());
const applyQuats = (bones, quats) => bones.forEach((b, i) => b.quaternion.copy(quats[i]));

export function createRigMode({ viewport, store, stack, gizmo, onChange }) {
  let s = null;
  let raf = 0;
  const helpers = createRigHelpers(viewport.scene);
  const ghosting = createGhosting(store);
  const tc = new TransformControls(viewport.camera, viewport.renderer.domElement);
  tc.getHelper().userData.editorOnly = true;
  viewport.scene.add(tc.getHelper());
  let pointerOnGizmo = false;
  let dragBefore = null;

  tc.addEventListener('mouseDown', () => { pointerOnGizmo = true; });
  tc.addEventListener('dragging-changed', (e) => {
    viewport.orbit.enabled = !e.value;
    if (s?.stage !== 'pose') return;
    if (e.value) dragBefore = snapshotQuats(s.bones);
    else if (dragBefore) { s.undo.push(dragBefore); s.redo = []; dragBefore = null; onChange(api.info()); }
  });
  tc.addEventListener('objectChange', () => {
    if (s?.stage !== 'place' || s.selected < 0) return;
    const j = s.joints[s.selected];
    j.position.copy(helpers.handle(s.selected).position);
    const m = s.mirror && j.mirror >= 0 ? s.joints[j.mirror] : null;
    if (m) m.position.set(2 * s.symX - j.position.x, j.position.y, j.position.z);
    helpers.update(s.joints.map((k) => k.position));
  });

  const boneWorld = () => s.bones.map((b) => b.getWorldPosition(new THREE.Vector3()));
  const tick = () => { // tư thế đổi -> chấm khớp đi theo xương
    if (s?.stage !== 'pose') return;
    helpers.update(boneWorld());
    raf = requestAnimationFrame(tick);
  };

  function startPlace(template) {
    const { geometry } = objectLocalGeometry(s.obj);
    const box = geometry.boundingBox;
    Object.assign(s, { stage: 'place', template, joints: fitTemplate(template, box), selected: -1,
      symX: (box.min.x + box.max.x) / 2, size: box.getSize(new THREE.Vector3()).length() });
    tc.detach();
    s.obj.updateWorldMatrix(true, false);
    helpers.show(s.joints.map((j) => j.position), s.joints.map((j) => j.parent), s.obj.matrixWorld, s.size * 0.018);
    onChange(api.info());
  }

  function startPose(group) {
    const skinned = skinnedMeshOf(group);
    const bones = skinned.skeleton.bones;
    group.userData.bindQuats ??= bones.map((b) => b.quaternion.toArray()); // lưu cùng project -> "Đặt lại tư thế"
    Object.assign(s, { stage: 'pose', obj: group, bones, startQuats: snapshotQuats(bones), selected: -1, undo: [], redo: [] });
    tc.detach();
    group.updateWorldMatrix(true, true);
    const size = new THREE.Box3().setFromObject(group).getSize(new THREE.Vector3()).length();
    helpers.show(boneWorld(), bones.map((b) => bones.indexOf(b.parent)), null, size * 0.018);
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(tick);
    onChange(api.info());
  }

  const api = {
    get active() { return !!s; },
    get stage() { return s?.stage; },
    get joints() { return s?.joints ?? null; }, // smoke test: tìm vị trí chấm khớp để bấm chuột thật

    enter(obj) {
      if (s) return;
      if (!obj) return toast('Hãy bấm chọn 1 vật trước.', { type: 'warn' });
      if (obj.userData.kind === 'light') return toast('Đèn không gắn xương được.', { type: 'warn' });
      if (!isRigged(obj) && meshesOf(obj).length !== 1) {
        return toast('Vật này gồm nhiều phần — hãy "Gộp lưới" trước khi gắn xương.', { type: 'warn', timeout: 7000 });
      }
      s = { obj, mirror: true, softness: 0.5, undo: [], redo: [] };
      ghosting.on(obj);
      gizmo.setEnabled(false);
      document.body.classList.add('rig-mode');
      if (isRigged(obj)) startPose(obj);
      else { startPlace('human'); toast('Kéo các chấm xanh cho khớp với tay, chân, đầu... rồi bấm "Gắn vào hình".', { timeout: 8000 }); }
    },

    exit() {
      if (!s) return;
      if (s.stage === 'pose') {
        const before = s.startQuats, after = snapshotQuats(s.bones), bones = s.bones;
        if (before.some((q, i) => !q.equals(after[i]))) {
          stack.push({ label: 'Tạo dáng', do: () => { applyQuats(bones, after); store.changed(); },
            undo: () => { applyQuats(bones, before); store.changed(); } });
        }
      }
      cancelAnimationFrame(raf);
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
      s.selected = i;
      helpers.setSelected(i);
      if (i < 0) tc.detach();
      else if (s.stage === 'place') { tc.setMode('translate'); tc.attach(helpers.handle(i)); }
      else { tc.setMode('rotate'); tc.setSpace('local'); tc.attach(s.bones[i]); }
      onChange(api.info());
    },
    pick(raycaster) { return helpers.pick(raycaster); },
    consumePointer() { const was = pointerOnGizmo || tc.dragging; pointerOnGizmo = false; return was; },

    setTemplate(key) { if (s.stage === 'place') startPlace(key); },
    setMirror(v) { s.mirror = v; onChange(api.info()); },
    setSoftness(v) { s.softness = v; onChange(api.info()); },

    /** Bước 1 -> 2: tính trọng lượng da, thay vật bằng vật có xương (1 bước Undo của app). */
    bind() {
      const old = s.obj;
      const group = buildRiggedObject(old, s.joints, s.softness);
      stack.execute(batchCommand('Gắn xương', [removeObjectCommand(store, old), addObjectCommand(store, group)]));
      ghosting.on(group);
      startPose(group);
      toast('Đã gắn xương! Bấm vào 1 khớp rồi kéo vòng tròn màu để xoay — tạo dáng tuỳ ý.', { type: 'ok', timeout: 8000 });
    },

    resetPose() {
      s.undo.push(snapshotQuats(s.bones)); s.redo = [];
      applyQuats(s.bones, s.obj.userData.bindQuats.map((q) => new THREE.Quaternion().fromArray(q)));
      onChange(api.info());
    },
    /** Gỡ xương, giữ dáng đang tạo thành hình thường (để sửa hình / nặn / tô tiếp). */
    unrig() {
      const group = s.obj;
      api.exit();
      const mesh = bakePoseToMesh(group);
      stack.execute(batchCommand('Gỡ xương', [removeObjectCommand(store, group), addObjectCommand(store, mesh)]));
      toast('Đã gỡ xương — hình giữ nguyên dáng vừa tạo.', { type: 'ok' });
    },

    undo() { swap(s?.undo, s?.redo); },
    redo() { swap(s?.redo, s?.undo); },

    info() {
      if (!s) return null;
      return { name: s.obj.name, stage: s.stage, template: s.template, mirror: s.mirror, softness: s.softness,
        selected: s.selected >= 0 ? (s.stage === 'place' ? s.joints[s.selected].name : s.bones[s.selected].name) : null,
        canUndo: s.undo.length > 0, canRedo: s.redo.length > 0 };
    },
  };

  function swap(from, to) {
    if (s?.stage !== 'pose' || !from?.length) return;
    to.push(snapshotQuats(s.bones));
    applyQuats(s.bones, from.pop());
    onChange(api.info());
  }

  return api;
}
