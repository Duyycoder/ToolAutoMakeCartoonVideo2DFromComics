// Bước 2 "Tạo dáng": bấm khớp, kéo vòng tròn để xoay xương; Undo riêng từng lần xoay;
// kết thúc lượt (Xong / Sửa khớp) = 1 bước Undo của app. Chấm khớp đi theo xương mỗi frame.
import * as THREE from 'three';
import { skinnedMeshOf } from './rig-builder.js';

export const snapshotQuats = (bones) => bones.map((b) => b.quaternion.clone());
export const applyQuats = (bones, quats) => bones.forEach((b, i) => b.quaternion.copy(quats[i]));
export const bindQuatsOf = (group) => group.userData.bindQuats.map((q) => new THREE.Quaternion().fromArray(q));

export function createPoseStage({ helpers, tc, stack, store, getState, notify }) {
  let raf = 0;
  let dragBefore = null;
  const boneWorld = (s) => s.bones.map((b) => b.getWorldPosition(new THREE.Vector3()));
  const tick = () => {
    const s = getState();
    if (s?.stage !== 'pose') return;
    helpers.update(boneWorld(s));
    raf = requestAnimationFrame(tick);
  };

  function swap(from, to) {
    const s = getState();
    if (!from.length) return;
    to.push(snapshotQuats(s.bones));
    applyQuats(s.bones, from.pop());
    notify();
  }

  return {
    start(group) {
      const s = getState();
      const bones = skinnedMeshOf(group).skeleton.bones;
      group.userData.bindQuats ??= bones.map((b) => b.quaternion.toArray()); // lưu cùng project -> "Đặt lại tư thế"
      Object.assign(s, { stage: 'pose', obj: group, bones, startQuats: snapshotQuats(bones), selected: -1, undo: [], redo: [], restoreQuats: null });
      tc.detach();
      group.updateWorldMatrix(true, true);
      const size = new THREE.Box3().setFromObject(group).getSize(new THREE.Vector3()).length();
      helpers.show(boneWorld(s), bones.map((b) => bones.indexOf(b.parent)), null, size * 0.018);
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(tick);
      notify();
    },
    stop() { cancelAnimationFrame(raf); },

    /** Ghi lượt tạo dáng (nếu có đổi) thành 1 bước Undo của app. */
    commit() {
      const s = getState();
      const before = s.startQuats, after = snapshotQuats(s.bones), bones = s.bones;
      if (before.some((q, i) => !q.equals(after[i]))) {
        stack.push({ label: 'Tạo dáng', do: () => { applyQuats(bones, after); store.changed(); },
          undo: () => { applyQuats(bones, before); store.changed(); } });
      }
      s.startQuats = after;
    },

    dragChanged(started) {
      const s = getState();
      if (started) dragBefore = snapshotQuats(s.bones);
      else if (dragBefore) { s.undo.push(dragBefore); s.redo = []; dragBefore = null; notify(); }
    },
    select(i) {
      const s = getState();
      s.selected = i;
      helpers.setSelected(i);
      if (i < 0) tc.detach(); else { tc.setMode('rotate'); tc.setSpace('local'); tc.attach(s.bones[i]); }
    },
    resetPose() {
      const s = getState();
      s.undo.push(snapshotQuats(s.bones)); s.redo = [];
      applyQuats(s.bones, bindQuatsOf(s.obj));
      notify();
    },
    undo() { const s = getState(); swap(s.undo, s.redo); },
    redo() { const s = getState(); swap(s.redo, s.undo); },
  };
}
