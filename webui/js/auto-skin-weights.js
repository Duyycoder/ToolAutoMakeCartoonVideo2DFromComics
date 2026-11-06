// Tự tính "trọng lượng da" (mỗi đỉnh chịu ảnh hưởng của xương nào, bao nhiêu) theo khoảng cách tới đoạn xương.
// Đủ tốt cho người mới; chỗ nách/háng có thể hơi thô — thanh "Độ mềm khớp" chỉnh độ hoà giữa các xương.
import * as THREE from 'three';
import { UNITY_NAME_OF_LABEL } from './skeleton-templates.js';

/** Mỗi khớp sở hữu các đoạn từ nó tới các khớp con (khớp lá = 1 điểm). */
function segmentsOf(joints) {
  return joints.map((j, i) => {
    const kids = joints.filter((k) => k.parent === i);
    return kids.length ? kids.map((k) => [j.position, k.position]) : [[j.position, j.position]];
  });
}

/** Khoảng cách điểm p tới đoạn ab — tính bằng số thuần (gọi hàng triệu lần, không tạo object). */
const segDist = (p, a, b) => {
  const abx = b.x - a.x, aby = b.y - a.y, abz = b.z - a.z;
  const len2 = abx * abx + aby * aby + abz * abz;
  let t = len2 ? ((p.x - a.x) * abx + (p.y - a.y) * aby + (p.z - a.z) * abz) / len2 : 0;
  t = Math.min(1, Math.max(0, t));
  const dx = p.x - (a.x + abx * t), dy = p.y - (a.y + aby * t), dz = p.z - (a.z + abz * t);
  return Math.sqrt(dx * dx + dy * dy + dz * dz);
};

/**
 * @param positions Float32Array (local, cùng hệ với joints)
 * @param softness 0..1 — 0: mỗi đỉnh gần như theo 1 xương (cứng), 1: hoà nhiều xương (mềm)
 * @returns { skinIndex: Uint16Array(n*4), skinWeight: Float32Array(n*4) }
 */
export function computeSkinWeights(positions, joints, softness = 0.5) {
  const segs = segmentsOf(joints);
  const n = positions.length / 3;
  const skinIndex = new Uint16Array(n * 4), skinWeight = new Float32Array(n * 4);
  const power = 2 + (1 - softness) * 10; // càng cao càng "cứng"
  const p = new THREE.Vector3();
  const dist = new Float32Array(joints.length);
  for (let v = 0; v < n; v++) {
    p.fromArray(positions, v * 3);
    for (let j = 0; j < joints.length; j++) {
      let d = Infinity;
      for (const [a, b] of segs[j]) d = Math.min(d, segDist(p, a, b));
      dist[j] = Math.max(d, 1e-6);
    }
    // 4 xương gần nhất, trọng số ∝ 1/d^power rồi chuẩn hoá tổng = 1.
    const best = Array.from(dist.keys()).sort((a, b) => dist[a] - dist[b]).slice(0, 4);
    const raw = best.map((j) => (dist[best[0]] / dist[j]) ** power);
    const sum = raw.reduce((a, b) => a + b, 0);
    best.forEach((j, k) => { skinIndex[v * 4 + k] = j; skinWeight[v * 4 + k] = raw[k] / sum; });
  }
  return { skinIndex, skinWeight };
}

/** Tách vùng đầu khỏi tay/thân trên mẫu Người; làm mềm vùng chuyển tiếp ngay dưới cổ. */
export function protectHeadWeights(positions, joints, { skinIndex, skinWeight }, frame) {
  if (!frame?.height) return;
  const names = joints.map((j) => UNITY_NAME_OF_LABEL[j.name] ?? UNITY_NAME_OF_LABEL[j.label] ?? j.name);
  const head = names.indexOf('Head'), neck = names.indexOf('Neck');
  const left = names.indexOf('LeftUpperArm'), right = names.indexOf('RightUpperArm');
  if ([head, neck, left, right].some((i) => i < 0) || joints[head].parent !== neck) return;

  const { H, height } = frame;
  const h = (i) => joints[i].position.dot(H);
  const headParts = new Set([head]);
  let highestArm = -Infinity;
  const terminal = joints.filter((j) => j.parent === head).length === 1;
  joints.forEach((j, i) => {
    for (let parent = j.parent; parent >= 0; parent = joints[parent].parent) {
      if (parent === left || parent === right) { highestArm = Math.max(highestArm, h(i)); break; }
      if (parent === head) {
        // Điểm đánh dấu đỉnh đầu của mẫu Người không điều khiển da.
        if (names[i] !== 'HeadTop_End' && !(terminal && /^Bone_\d+$/.test(names[i]))) headParts.add(i);
        break;
      }
    }
  });
  const full = Math.max(h(neck) - 0.015 * height, Math.max(h(left), h(right)) + 0.025 * height, highestArm + 0.045 * height);
  const band = height * 0.03;
  for (let i = 0; i < positions.length; i += 3) {
    const y = positions[i] * H.x + positions[i + 1] * H.y + positions[i + 2] * H.z;
    if (y <= full - band) continue;
    const blend = THREE.MathUtils.smoothstep(y, full - band, full);
    const start = i / 3 * 4;
    let headSlot = -1, weakest = start;
    for (let k = start; k < start + 4; k++) {
      if (skinIndex[k] === head) headSlot = k;
      if (!headParts.has(skinIndex[k])) skinWeight[k] *= 1 - blend;
      if (skinWeight[k] < skinWeight[weakest]) weakest = k;
    }
    if (headSlot < 0) {
      headSlot = weakest;
      skinIndex[headSlot] = head;
      skinWeight[headSlot] = 0;
    }
    let sum = 0;
    for (let k = start; k < start + 4; k++) sum += skinWeight[k];
    skinWeight[headSlot] += Math.max(0, 1 - sum);
  }
}
