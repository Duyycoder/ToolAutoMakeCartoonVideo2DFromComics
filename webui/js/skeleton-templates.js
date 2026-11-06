// Mẫu xương cho người mới: khớp đặt theo TỈ LỆ khung bao của vật (đứng thẳng +Y, mặt trước +Z),
// người dùng chỉ cần kéo chỉnh lại cho khớp hình. `mirror`: khớp đối xứng (kéo 1 bên, bên kia theo).
import * as THREE from 'three';

// [tên, khớp cha, x, y, z] — x: -1..1 (trái..phải theo nửa bề rộng), y: 0..1 (chân..đỉnh), z: -1..1.
const HUMAN = [
  ['Hông', null, 0, 0.5, 0], ['Bụng', 'Hông', 0, 0.6, 0], ['Ngực', 'Bụng', 0, 0.72, 0],
  ['Cổ', 'Ngực', 0, 0.82, 0], ['Đầu', 'Cổ', 0, 0.9, 0], ['Đỉnh đầu', 'Đầu', 0, 1, 0],
  ['Vai trái', 'Ngực', -0.3, 0.78, 0], ['Khuỷu trái', 'Vai trái', -0.6, 0.66, 0],
  ['Cổ tay trái', 'Khuỷu trái', -0.85, 0.55, 0], ['Bàn tay trái', 'Cổ tay trái', -1, 0.5, 0],
  ['Vai phải', 'Ngực', 0.3, 0.78, 0], ['Khuỷu phải', 'Vai phải', 0.6, 0.66, 0],
  ['Cổ tay phải', 'Khuỷu phải', 0.85, 0.55, 0], ['Bàn tay phải', 'Cổ tay phải', 1, 0.5, 0],
  ['Đùi trái', 'Hông', -0.2, 0.47, 0], ['Gối trái', 'Đùi trái', -0.2, 0.26, 0],
  ['Cổ chân trái', 'Gối trái', -0.2, 0.05, 0], ['Mũi chân trái', 'Cổ chân trái', -0.2, 0, 0.6],
  ['Đùi phải', 'Hông', 0.2, 0.47, 0], ['Gối phải', 'Đùi phải', 0.2, 0.26, 0],
  ['Cổ chân phải', 'Gối phải', 0.2, 0.05, 0], ['Mũi chân phải', 'Cổ chân phải', 0.2, 0, 0.6],
];

export const SKELETON_TEMPLATES = {
  human: { label: '🧍 Người', hint: 'Đầu, thân, 2 tay, 2 chân — hợp nhân vật đứng thẳng' },
  chain: { label: '🐍 Chuỗi', hint: 'Một dãy khớp dọc theo vật — đuôi, rắn, dây, cành cây' },
};

const mirrorName = (n) => (n.includes('trái') ? n.replace('trái', 'phải') : n.includes('phải') ? n.replace('phải', 'trái') : null);

/** Danh sách khớp { name, parent (chỉ số|-1), position (local), mirror (chỉ số|-1) } vừa khung `box`. */
export function fitTemplate(key, box) {
  const size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3());
  let rows;
  if (key === 'chain') {
    // Dọc theo trục dài nhất của vật, 6 khớp.
    const axis = size.x >= size.y && size.x >= size.z ? 'x' : size.y >= size.z ? 'y' : 'z';
    rows = Array.from({ length: 6 }, (_, i) => {
      const p = center.clone();
      p[axis] = box.min[axis] + (size[axis] * i) / 5;
      return [`Khớp ${i + 1}`, i ? `Khớp ${i}` : null, p];
    });
  } else {
    rows = HUMAN.map(([name, parent, x, y, z]) => [name, parent,
      new THREE.Vector3(center.x + (x * size.x) / 2, box.min.y + y * size.y, center.z + (z * size.z) / 2)]);
  }
  const names = rows.map((r) => r[0]);
  return rows.map(([name, parent, position]) => ({
    name, position, parent: parent ? names.indexOf(parent) : -1, mirror: names.indexOf(mirrorName(name)),
  }));
}
