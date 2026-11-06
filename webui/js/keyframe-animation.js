// Chuyển động theo "tư thế ghi lại" (keyframe). Dữ liệu là số thuần trong obj.userData.anim -> tự lưu cùng project:
//   { keys: [{ t, p:[x,y,z], q:[x,y,z,w], s:[x,y,z], bones?: [[x,y,z,w], ...] }] }  (sắp theo t)
// Vật có xương: mỗi khoá ghi cả tư thế từng xương -> nhân vật cử động được.
import * as THREE from 'three';
import { skinnedMeshOf } from './rig-builder.js';

const SAME_TIME = 0.02;
const bonesOf = (obj) => skinnedMeshOf(obj)?.skeleton.bones ?? null;
export const keysOf = (obj) => obj.userData.anim?.keys ?? [];
export const hasAnimation = (obj) => keysOf(obj).length > 0;

/** Bản sao sâu (cho Undo) — dữ liệu chỉ là số nên JSON là đủ. */
export const cloneAnim = (obj) => (obj.userData.anim ? JSON.parse(JSON.stringify(obj.userData.anim)) : null);

function snapshotKey(obj, t) {
  const key = { t, p: obj.position.toArray(), q: obj.quaternion.toArray(), s: obj.scale.toArray() };
  const bones = bonesOf(obj);
  if (bones) key.bones = bones.map((b) => b.quaternion.toArray());
  return key;
}

/** Ghi tư thế hiện tại tại thời điểm t (trùng thời điểm -> ghi đè). Trả về anim mới (không sửa obj). */
export function withKeyRecorded(obj, t) {
  const keys = keysOf(obj).filter((k) => Math.abs(k.t - t) > SAME_TIME);
  keys.push(snapshotKey(obj, t));
  keys.sort((a, b) => a.t - b.t);
  return { keys };
}

export function withKeyRemoved(obj, t) {
  const keys = keysOf(obj).filter((k) => Math.abs(k.t - t) > SAME_TIME);
  return keys.length ? { keys } : null;
}

const q0 = new THREE.Quaternion(), q1 = new THREE.Quaternion();

/** Đặt vật về tư thế tại thời điểm t (nội suy giữa 2 khoá gần nhất). */
export function applyAt(obj, t) {
  const keys = keysOf(obj);
  if (!keys.length) return;
  let i = keys.findIndex((k) => k.t > t);
  if (i === -1) i = keys.length;
  const a = keys[Math.max(0, i - 1)], b = keys[Math.min(keys.length - 1, i)];
  const alpha = b.t > a.t ? THREE.MathUtils.clamp((t - a.t) / (b.t - a.t), 0, 1) : 0;
  obj.position.fromArray(a.p).lerp(new THREE.Vector3().fromArray(b.p), alpha);
  obj.quaternion.slerpQuaternions(q0.fromArray(a.q), q1.fromArray(b.q), alpha);
  obj.scale.fromArray(a.s).lerp(new THREE.Vector3().fromArray(b.s), alpha);
  const bones = bonesOf(obj);
  if (bones && a.bones && b.bones) {
    bones.forEach((bone, k) => { if (a.bones[k] && b.bones[k]) bone.quaternion.slerpQuaternions(q0.fromArray(a.bones[k]), q1.fromArray(b.bones[k]), alpha); });
  }
}

/** Mẫu nhanh, tính từ tư thế hiện tại của vật. Trả về anim mới. */
export const PRESETS = {
  // 4 khoá 0°/120°/240°/360°: nếu chỉ 0° và 360° thì nội suy đi đường ngắn nhất = đứng yên.
  turntable: { label: 'Bàn xoay 360°', make: (obj, d) => keysFromSteps(obj, d, 4, (o, i) => o.rotateY((Math.PI * 2 * i) / 3)) },
  bounce: { label: 'Nảy lên xuống', make: (obj, d) => keysFromSteps(obj, d, 3, (o, i, h) => { o.position.y += i === 1 ? h * 0.4 : 0; }) },
  sway: { label: 'Lắc lư', make: (obj, d) => keysFromSteps(obj, d, 5, (o, i) => o.rotateZ([0, 0.26, 0, -0.26, 0][i])) },
  grow: { label: 'Phóng to rồi thu lại', make: (obj, d) => keysFromSteps(obj, d, 3, (o, i) => o.scale.multiplyScalar(i === 1 ? 1.5 : 1)) },
};

/** n khoá cách đều trong d giây; mỗi khoá = tư thế gốc + biến đổi `step(bản sao, i, chiều cao vật)`. */
function keysFromSteps(obj, d, n, step) {
  const h = new THREE.Box3().setFromObject(obj).getSize(new THREE.Vector3()).y;
  const keys = [];
  for (let i = 0; i < n; i++) {
    const o = new THREE.Object3D();
    o.position.copy(obj.position); o.quaternion.copy(obj.quaternion); o.scale.copy(obj.scale);
    step(o, i, h);
    const key = { t: (d * i) / (n - 1), p: o.position.toArray(), q: o.quaternion.toArray(), s: o.scale.toArray() };
    const bones = bonesOf(obj);
    if (bones) key.bones = bones.map((b) => b.quaternion.toArray());
    keys.push(key);
  }
  return { keys };
}

/** AnimationClip chuẩn cho GLB (game engine đọc được). Track nhắm theo uuid (GLTFExporter tìm được node). */
export function buildClip(objects, duration) {
  const tracks = [];
  for (const obj of objects) {
    const keys = keysOf(obj);
    if (keys.length < 2) continue;
    const times = keys.map((k) => k.t);
    tracks.push(new THREE.VectorKeyframeTrack(`${obj.uuid}.position`, times, keys.flatMap((k) => k.p)));
    tracks.push(new THREE.QuaternionKeyframeTrack(`${obj.uuid}.quaternion`, times, keys.flatMap((k) => k.q)));
    tracks.push(new THREE.VectorKeyframeTrack(`${obj.uuid}.scale`, times, keys.flatMap((k) => k.s)));
    const bones = bonesOf(obj);
    if (bones && keys.every((k) => k.bones)) {
      bones.forEach((b, i) => tracks.push(new THREE.QuaternionKeyframeTrack(`${b.uuid}.quaternion`, times, keys.flatMap((k) => k.bones[i]))));
    }
  }
  return tracks.length ? new THREE.AnimationClip('Easy3D', duration, tracks) : null;
}
