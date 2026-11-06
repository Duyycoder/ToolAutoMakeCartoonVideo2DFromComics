// Sửa cấu trúc bộ khớp (hàm thuần, trả về mảng MỚI): kiểm tra tên xương, thêm khớp con, xoá khớp.
// Khớp: { name, label, parent (chỉ số|-1), mirror, position (Vector3 local) }.
import { relinkMirrors } from './skeleton-templates.js';

const VALID_BONE_NAME = /^[A-Za-z0-9_.:-]{1,48}$/; // tên an toàn cho Unity/Blender/Godot

/** Lý do tên xương không dùng được (null = hợp lệ). */
export function boneNameProblem(name, otherNames) {
  if (!VALID_BONE_NAME.test(name)) return 'Tên xương chỉ dùng chữ không dấu, số và _ . : - (tối đa 48 ký tự).';
  if (otherNames.includes(name)) return `Đã có xương tên "${name}".`;
  return null;
}

export const cloneJoints = (joints) => joints.map((j) => ({ ...j, position: j.position.clone() }));

/** Thêm khớp con của khớp p, nối tiếp hướng xương cha (khớp gốc: dời lên `upStep`). */
export function withChildAdded(joints, p, upStep) {
  const names = new Set(joints.map((j) => j.name));
  let n = joints.length + 1;
  while (names.has(`Bone_${n}`)) n++;
  const parent = joints[p], grand = joints[parent.parent];
  const offset = grand ? parent.position.clone().sub(grand.position).multiplyScalar(0.5) : upStep;
  const out = cloneJoints(joints);
  out.push({ name: `Bone_${n}`, label: `Bone_${n}`, parent: p, mirror: -1, position: parent.position.clone().add(offset) });
  return relinkMirrors(out);
}

/** Xoá khớp i, khớp con nối vào khớp cha của nó. Trả về { joints } hoặc { error }. */
export function withJointRemoved(joints, i) {
  const kids = joints.filter((j) => j.parent === i).length;
  if (joints[i].parent < 0 && kids !== 1) return { error: 'Khớp gốc chỉ xoá được khi nó có đúng 1 khớp con.' };
  if (joints.length <= 2) return { error: 'Bộ xương cần ít nhất 2 khớp.' };
  const removedParent = joints[i].parent;
  const shift = (k) => (k > i ? k - 1 : k);
  const remap = (k) => (k === i ? shift(removedParent) : shift(k));
  return { joints: relinkMirrors(cloneJoints(joints).filter((_, k) => k !== i).map((j) => ({ ...j, parent: remap(j.parent) }))) };
}
