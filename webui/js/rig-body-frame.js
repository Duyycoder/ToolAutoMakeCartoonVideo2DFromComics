// "Khung thân" của nhân vật, tính trong toạ độ LOCAL của vật (cùng hệ với khớp/xương):
//   H = hướng lên THẬT (world +Y, kể cả khi vật FBX/Z-up đã bị xoay), U = bên TRÁI nhân vật, F = mặt trước.
// Bề ngang (vai) thường rộng hơn bề sâu -> trục ngang dài hơn là U; mặt trước đoán theo mũi chân, không rõ thì theo camera.
// Toạ độ khung: (u, h, f) = (p·U, p·H, p·F). Glb/Unity: nhân vật nhìn +Z thì bên trái là +X  ->  U = H × F.
import * as THREE from 'three';

const MAX_SAMPLES = 60000;

const localDir = (inv, x, y, z) => new THREE.Vector3(x, y, z).transformDirection(inv);

function extentAlong(positions, step, axis) {
  let lo = Infinity, hi = -Infinity;
  for (let i = 0; i < positions.length; i += step * 3) {
    const d = positions[i] * axis.x + positions[i + 1] * axis.y + positions[i + 2] * axis.z;
    if (d < lo) lo = d;
    if (d > hi) hi = d;
  }
  return hi - lo;
}

/**
 * Đoán mặt trước theo bàn chân: mũi chân chìa ra trước hơn gót so với cẳng chân.
 * Trả về +1 (F đúng), -1 (ngược) hoặc 0 (không rõ).
 */
function footFacing(pts) {
  let hMin = Infinity, hMax = -Infinity;
  for (let i = 1; i < pts.length; i += 3) { hMin = Math.min(hMin, pts[i]); hMax = Math.max(hMax, pts[i]); }
  const height = hMax - hMin;
  const feet = [], shins = [];
  for (let i = 0; i < pts.length; i += 3) {
    const t = (pts[i + 1] - hMin) / height;
    if (t < 0.04) feet.push(pts[i + 2]); else if (t > 0.1 && t < 0.25) shins.push(pts[i + 2]);
  }
  if (feet.length < 20 || shins.length < 20) return 0;
  const mid = (arr) => arr.sort((a, b) => a - b)[arr.length >> 1];
  const lo = (arr) => arr[Math.floor(arr.length * 0.05)], hi = (arr) => arr[Math.floor(arr.length * 0.95)];
  const shin = mid(shins);
  feet.sort((a, b) => a - b);
  const forward = hi(feet) - shin, backward = shin - lo(feet); // mũi chân xa cẳng chân hơn gót
  const depth = hi(feet) - lo(feet);
  if (Math.abs(forward - backward) < depth * 0.12) return 0;
  return forward > backward ? 1 : -1;
}

/** Tạo khung từ hệ trục (U trái, H lên, F trước) + mẫu điểm của vật (Float32Array local). */
export function frameFromAxes(U, H, F, positions) {
  const step = Math.max(1, Math.ceil(positions.length / 3 / MAX_SAMPLES));
  const n = Math.floor(positions.length / 3 / step);
  const pts = new Float32Array(n * 3);
  const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
  const v = new THREE.Vector3();
  for (let k = 0; k < n; k++) {
    v.fromArray(positions, k * step * 3);
    const c = [v.dot(U), v.dot(H), v.dot(F)];
    for (let a = 0; a < 3; a++) {
      pts[k * 3 + a] = c[a];
      const x = pts[k * 3 + a]; // min/max theo giá trị ĐÃ làm tròn Float32 -> không điểm nào lọt ra ngoài
      if (x < min[a]) min[a] = x;
      if (x > max[a]) max[a] = x;
    }
  }
  return {
    U, H, F, pts, min, max,
    height: max[1] - min[1],
    toLocal: (u, h, f) => new THREE.Vector3().addScaledVector(U, u).addScaledVector(H, h).addScaledVector(F, f),
    toFrame: (p) => [p.dot(U), p.dot(H), p.dot(F)],
  };
}

/**
 * @param obj vật (đã updateWorldMatrix) · positions: Float32Array toạ độ local của vật
 * @param cameraLocal vị trí camera trong toạ độ local của vật (đoán mặt trước khi chân không rõ)
 */
export function computeBodyFrame(obj, positions, cameraLocal) {
  const inv = obj.matrixWorld.clone().invert();
  const H = localDir(inv, 0, 1, 0);
  const X = localDir(inv, 1, 0, 0), Z = localDir(inv, 0, 0, 1);
  const step = Math.max(1, Math.ceil(positions.length / 3 / MAX_SAMPLES));
  // Trục ngang dài hơn = vai (U); trục còn lại = trước/sau (F).
  const lateralIsX = extentAlong(positions, step, X) >= extentAlong(positions, step, Z);
  let F = (lateralIsX ? Z : X).clone();
  const trial = frameFromAxes(new THREE.Vector3().crossVectors(H, F), H, F, positions);
  let sign = footFacing(trial.pts);
  if (!sign) {
    const center = trial.toLocal((trial.min[0] + trial.max[0]) / 2, 0, (trial.min[2] + trial.max[2]) / 2);
    sign = cameraLocal.clone().sub(center).dot(F) >= 0 ? 1 : -1; // không rõ -> mặt trước quay về phía camera
  }
  if (sign < 0) F.negate();
  return frameFromAxes(new THREE.Vector3().crossVectors(H, F), H, F, positions);
}

/** Xoay khung quanh trục lên `quarterTurns` × 90° (1: xoay 90°, 2: quay mặt) — khi đoán sai hướng. */
export function turnFrame(frame, quarterTurns, positions) {
  const q = new THREE.Quaternion().setFromAxisAngle(frame.H, (Math.PI / 2) * quarterTurns);
  const F = frame.F.clone().applyQuaternion(q);
  return frameFromAxes(new THREE.Vector3().crossVectors(frame.H, F), frame.H.clone(), F, positions);
}
