// Mẫu xương cho người mới. Tên xương = chuẩn Unity Humanoid (Unity tự map Avatar), nhãn tiếng Việt chỉ để hiển thị.
// Toạ độ mẫu theo KHUNG THÂN (rig-body-frame.js): x = bên TRÁI nhân vật (-1..1 nửa bề ngang), y = 0..1 chân..đỉnh,
// z = mặt trước (-1..1 nửa bề sâu). Mẫu chỉ là điểm xuất phát; skeleton-auto-fit.js dời khớp theo hình thật.
import * as THREE from 'three';

// [tên Unity, nhãn, khớp cha, x, y, z]
const HUMAN = [
  ['Hips', 'Hông', null, 0, 0.5, 0], ['Spine', 'Bụng', 'Hips', 0, 0.6, 0], ['Chest', 'Ngực', 'Spine', 0, 0.72, 0],
  ['Neck', 'Cổ', 'Chest', 0, 0.82, 0], ['Head', 'Đầu', 'Neck', 0, 0.9, 0], ['HeadTop_End', 'Đỉnh đầu', 'Head', 0, 1, 0],
  ['LeftUpperArm', 'Vai trái', 'Chest', 0.3, 0.78, 0], ['LeftLowerArm', 'Khuỷu trái', 'LeftUpperArm', 0.6, 0.66, 0],
  ['LeftHand', 'Cổ tay trái', 'LeftLowerArm', 0.85, 0.55, 0], ['LeftHand_End', 'Bàn tay trái', 'LeftHand', 1, 0.5, 0],
  ['RightUpperArm', 'Vai phải', 'Chest', -0.3, 0.78, 0], ['RightLowerArm', 'Khuỷu phải', 'RightUpperArm', -0.6, 0.66, 0],
  ['RightHand', 'Cổ tay phải', 'RightLowerArm', -0.85, 0.55, 0], ['RightHand_End', 'Bàn tay phải', 'RightHand', -1, 0.5, 0],
  ['LeftUpperLeg', 'Đùi trái', 'Hips', 0.2, 0.47, 0], ['LeftLowerLeg', 'Gối trái', 'LeftUpperLeg', 0.2, 0.26, 0],
  ['LeftFoot', 'Cổ chân trái', 'LeftLowerLeg', 0.2, 0.05, 0], ['LeftToes', 'Mũi chân trái', 'LeftFoot', 0.2, 0, 0.6],
  ['RightUpperLeg', 'Đùi phải', 'Hips', -0.2, 0.47, 0], ['RightLowerLeg', 'Gối phải', 'RightUpperLeg', -0.2, 0.26, 0],
  ['RightFoot', 'Cổ chân phải', 'RightLowerLeg', -0.2, 0.05, 0], ['RightToes', 'Mũi chân phải', 'RightFoot', -0.2, 0, 0.6],
];

export const SKELETON_TEMPLATES = {
  human: { label: '🧍 Người', hint: 'Đầu, thân, 2 tay, 2 chân — tự dò tay chân theo hình, tên xương chuẩn Unity Humanoid' },
  chain: { label: '🐍 Chuỗi', hint: 'Một dãy khớp dọc theo vật — đuôi, rắn, dây, cành cây' },
};

/** Nhãn tiếng Việt -> tên Unity: đổi tên xương của vật gắn bằng bản cũ (tên tiếng Việt). */
export const UNITY_NAME_OF_LABEL = Object.fromEntries(HUMAN.map(([name, label]) => [label, name]));

const SIDE_SWAP = [['Left', 'Right'], ['trái', 'phải']];
/** Tên khớp đối xứng (Left <-> Right, trái <-> phải) hoặc null. */
export function mirrorNameOf(name) {
  for (const [a, b] of SIDE_SWAP) {
    if (name.includes(a)) return name.replace(a, b);
    if (name.includes(b)) return name.replace(b, a);
  }
  return null;
}

/** Tính lại chỉ số khớp đối xứng (sau khi thêm/xoá/đổi tên khớp). */
export function relinkMirrors(joints) {
  const names = joints.map((j) => j.name);
  joints.forEach((j) => { j.mirror = names.indexOf(mirrorNameOf(j.name)); });
  return joints;
}

/** rows: [{ name, label, parentName, position }] -> [{ name, label, parent (chỉ số|-1), mirror, position }]. */
export function linkJoints(rows) {
  const names = rows.map((r) => r.name);
  return relinkMirrors(rows.map(({ name, label, parentName, position }) => ({
    name, label: label ?? name, position, parent: parentName ? names.indexOf(parentName) : -1,
  })));
}

/** Mẫu Người đặt theo tỉ lệ khung thân `frame` (điểm xuất phát / khi tự dò không ra). */
export function humanTemplate(frame) {
  const { min, max } = frame;
  const cu = (min[0] + max[0]) / 2, cf = (min[2] + max[2]) / 2;
  const hu = (max[0] - min[0]) / 2, hh = max[1] - min[1], hf = (max[2] - min[2]) / 2;
  return linkJoints(HUMAN.map(([name, label, parentName, x, y, z]) => ({
    name, label, parentName, position: frame.toLocal(cu + x * hu, min[1] + y * hh, cf + z * hf),
  })));
}

/** Mẫu Chuỗi: 6 khớp dọc trục dài nhất của khung bao local `box`. */
export function chainTemplate(box) {
  const size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3());
  const axis = size.x >= size.y && size.x >= size.z ? 'x' : size.y >= size.z ? 'y' : 'z';
  return linkJoints(Array.from({ length: 6 }, (_, i) => {
    const p = center.clone();
    p[axis] = box.min[axis] + (size[axis] * i) / 5;
    return { name: `Chain_${i + 1}`, label: `Khớp ${i + 1}`, parentName: i ? `Chain_${i}` : null, position: p };
  }));
}
