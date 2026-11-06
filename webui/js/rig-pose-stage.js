// Bước 2 "Tạo dáng": xoay, dời theo trục hoặc kéo trên mặt phẳng màn hình;
// kết thúc lượt (Xong / Sửa khớp) = 1 bước Undo của app. Chấm khớp đi theo xương mỗi frame.
import * as THREE from 'three';
import { disableSkinFrustumCulling, skinnedMeshOf } from './rig-builder.js';
import { dragPlane } from './rig-joint-drag.js';
import { createBoneMove, wristOfHandTip } from './rig-limb-ik.js';

export const snapshotPose = (bones) => bones.map((b) => ({ position: b.position.clone(), quaternion: b.quaternion.clone() }));
export const applyPose = (bones, pose) => bones.forEach((b, i) => {
  b.position.copy(pose[i].position);
  b.quaternion.copy(pose[i].quaternion);
});
export const bindPoseOf = (group) => group.userData.bindPositions.map((p, i) => ({
  position: new THREE.Vector3().fromArray(p), quaternion: new THREE.Quaternion().fromArray(group.userData.bindQuats[i]),
}));
const poseChanged = (bones, before) => bones.some((b, i) =>
  !b.position.equals(before[i].position) || !b.quaternion.equals(before[i].quaternion));

function startWorldMove(s, origin) {
  const selected = new Set([...s.selectedBones].map((i) => s.bones[i]));
  const roots = [...selected].filter((bone) => {
    for (let parent = bone.parent; parent; parent = parent.parent) {
      if (selected.has(parent)) return false; // xương con đi theo xương cha đã chọn
    }
    return true;
  });
  const available = new Set(s.bones);
  const rotations = new Map();
  const starts = [];
  for (const bone of roots) {
    const world = bone.getWorldPosition(new THREE.Vector3());
    if (!s.lockBoneLengths || !bone.parent?.isBone) {
      starts.push({ bone, world, local: bone.position.clone() });
      continue;
    }
    const ik = createBoneMove(bone, available);
    if (!ik) continue;
    for (const joint of ik.joints) {
      available.delete(joint);
      rotations.set(joint, joint.quaternion.clone());
    }
    starts.push({ world, ik });
  }
  return { origin: origin.clone(), starts, rotations };
}

function moveInWorld(move, target) {
  const delta = target.clone().sub(move.origin);
  const atStart = delta.lengthSq() < 1e-20;
  // Giải lại từ lúc bắt đầu kéo để hướng gập không lệch dần sau mỗi lần rê chuột.
  for (const [joint, rotation] of move.rotations) joint.quaternion.copy(rotation);
  for (const { bone, world, local, ik } of move.starts) {
    if (atStart) { if (bone) bone.position.copy(local); continue; }
    const next = world.clone().add(delta);
    if (ik) ik.moveTo(next);
    else bone.position.copy(bone.parent ? bone.parent.worldToLocal(next) : next);
  }
}

export function createPoseStage({ camera, helpers, tc, pivot, stack, store, getState, notify }) {
  let raf = 0;
  let gizmoDrag = null;
  let screenDrag = null;
  const boneWorld = (s) => s.bones.map((b) => b.getWorldPosition(new THREE.Vector3()));
  const tick = () => {
    const s = getState();
    if (s?.stage !== 'pose') return;
    const points = boneWorld(s);
    helpers.update(points);
    if (s.poseMode === 'translate' && s.selected >= 0 && !tc.dragging) pivot.position.copy(points[s.selected]);
    raf = requestAnimationFrame(tick);
  };

  function swap(from, to) {
    const s = getState();
    if (!from.length) return;
    to.push(snapshotPose(s.bones));
    applyPose(s.bones, from.pop());
    notify();
  }

  function remember(before) {
    const s = getState();
    if (!poseChanged(s.bones, before)) return;
    s.undo.push(before);
    s.redo = [];
    notify();
  }

  function focus(s, i) {
    s.selected = i;
    helpers.setSelected(i, s.selectedBones);
    if (i < 0 || s.poseMode === 'screen') tc.detach();
    else if (s.poseMode === 'rotate') {
      tc.setMode('rotate');
      tc.setSpace('local');
      const bone = s.bones[i];
      tc.attach(wristOfHandTip(bone) ?? bone);
    } else {
      // Tay cầm ở hệ thế giới; dùng ma trận cha để giữ đúng trục kể cả khi rig bị co giãn.
      s.bones[i].getWorldPosition(pivot.position);
      pivot.quaternion.identity();
      pivot.scale.setScalar(1);
      tc.setMode('translate');
      tc.setSpace('world');
      tc.attach(pivot);
    }
  }

  const api = {
    start(group) {
      const s = getState();
      const bones = skinnedMeshOf(group).skeleton.bones;
      disableSkinFrustumCulling(group);
      group.userData.bindQuats ??= bones.map((b) => b.quaternion.toArray()); // lưu cùng project -> "Đặt lại tư thế"
      group.userData.bindPositions ??= bones.map((b) => b.position.toArray());
      Object.assign(s, { stage: 'pose', poseMode: 'rotate', obj: group, bones, startPose: snapshotPose(bones),
        selected: -1, selectedBones: new Set(), undo: [], redo: [], restorePose: null });
      tc.detach();
      group.updateWorldMatrix(true, true);
      const size = new THREE.Box3().setFromObject(group).getSize(new THREE.Vector3()).length();
      helpers.show(boneWorld(s), bones.map((b) => bones.indexOf(b.parent)), null, size * 0.018);
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(tick);
      notify();
    },
    stop() { cancelAnimationFrame(raf); gizmoDrag = screenDrag = null; },
    get dragging() { return !!screenDrag; },

    /** Ghi lượt tạo dáng (nếu có đổi) thành 1 bước Undo của app. */
    commit() {
      const s = getState();
      const { startPose: before, bones } = s;
      if (!poseChanged(bones, before)) return;
      const after = snapshotPose(bones);
      const apply = (snapshot) => { applyPose(bones, snapshot); store.changed(); };
      stack.push({ label: 'Tạo dáng', do: () => apply(after), undo: () => apply(before) });
      s.startPose = after;
    },

    dragChanged(started) {
      const s = getState();
      if (started) {
        gizmoDrag = { before: snapshotPose(s.bones), move: s.poseMode === 'translate' ? startWorldMove(s, pivot.position) : null };
      } else if (gizmoDrag) {
        remember(gizmoDrag.before);
        gizmoDrag = null;
      }
    },
    cancelGizmoDrag() {
      if (!gizmoDrag) return;
      applyPose(getState().bones, gizmoDrag.before);
      gizmoDrag = null;
    },
    setMode(mode) {
      const s = getState();
      s.poseMode = mode;
      focus(s, s.selected);
    },
    select(i, additive = false) {
      const s = getState();
      if (!additive) s.selectedBones.clear();
      if (i < 0) { if (!additive) focus(s, -1); return; }
      if (additive && s.selectedBones.delete(i)) {
        focus(s, s.selected === i ? ([...s.selectedBones].at(-1) ?? -1) : s.selected);
        return;
      }
      s.selectedBones.add(i);
      focus(s, i);
    },
    selectBox(box, canvas) {
      const s = getState();
      let active = s.selected;
      boneWorld(s).forEach((point, i) => {
        const { x, y, z } = point.project(camera);
        if (Math.abs(x) > 1 || Math.abs(y) > 1 || Math.abs(z) > 1) return;
        const left = canvas.left + (x + 1) * canvas.width / 2;
        const top = canvas.top + (1 - y) * canvas.height / 2;
        if (left < box.left || left > box.right || top < box.top || top > box.bottom) return;
        if (!s.selectedBones.has(i)) active = i;
        s.selectedBones.add(i);
      });
      focus(s, active);
    },
    gizmoMoved() { if (gizmoDrag?.move) moveInWorld(gizmoDrag.move, pivot.position); },

    beginDrag(raycaster) {
      const s = getState();
      const i = helpers.pick(raycaster);
      if (i < 0) return false;
      const bone = s.bones[i];
      const world = bone.getWorldPosition(new THREE.Vector3());
      const plane = dragPlane(world, camera);
      const hit = raycaster.ray.intersectPlane(plane, new THREE.Vector3());
      if (!hit) return false;
      if (s.selectedBones.has(i)) focus(s, i);
      else api.select(i);
      screenDrag = { plane, move: startWorldMove(s, hit), before: snapshotPose(s.bones) };
      notify();
      return true;
    },
    dragTo(raycaster) {
      if (!screenDrag) return;
      const world = raycaster.ray.intersectPlane(screenDrag.plane, new THREE.Vector3());
      if (world) moveInWorld(screenDrag.move, world);
    },
    endDrag() {
      if (!screenDrag) return;
      const { before } = screenDrag;
      screenDrag = null;
      remember(before);
    },
    cancelDrag() {
      if (!screenDrag) return;
      applyPose(getState().bones, screenDrag.before);
      screenDrag = null;
      notify();
    },
    resetPose() {
      const s = getState();
      const before = snapshotPose(s.bones);
      applyPose(s.bones, bindPoseOf(s.obj));
      remember(before);
    },
    undo() { const s = getState(); swap(s.undo, s.redo); },
    redo() { const s = getState(); swap(s.redo, s.undo); },
  };
  return api;
}
