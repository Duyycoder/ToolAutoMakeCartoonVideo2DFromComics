// Khối có sẵn cho người mới: kích thước ~1 m, tự đặt lên sàn, mỗi khối một màu dễ phân biệt.
import * as THREE from 'three';

export const SHAPES = {
  box: { label: 'Hộp', icon: '⬛', make: () => new THREE.BoxGeometry(1, 1, 1) },
  sphere: { label: 'Cầu', icon: '⚪', make: () => new THREE.SphereGeometry(0.5, 48, 24) },
  cylinder: { label: 'Trụ', icon: '🛢', make: () => new THREE.CylinderGeometry(0.5, 0.5, 1, 48) },
  cone: { label: 'Nón', icon: '🔺', make: () => new THREE.ConeGeometry(0.5, 1, 48) },
  torus: { label: 'Vòng xuyến', icon: '🍩', make: () => new THREE.TorusGeometry(0.4, 0.15, 24, 64) },
  plane: { label: 'Tấm phẳng', icon: '▭', make: () => new THREE.BoxGeometry(1.5, 0.04, 1.5) },
};

const PALETTE = [0x5b8cff, 0xff7a59, 0x5fd08a, 0xf2c94c, 0xbb6bd9, 0x56ccf2];
let colorIndex = 0;

export function createPrimitive(type, name) {
  const shape = SHAPES[type];
  if (!shape) throw new Error(`Không có khối: ${type}`);
  const material = new THREE.MeshStandardMaterial({
    color: PALETTE[colorIndex++ % PALETTE.length], roughness: 0.45, metalness: 0,
  });
  material.userData.preset = 'plastic';
  const mesh = new THREE.Mesh(shape.make(), material);
  mesh.name = name;
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  mesh.userData.kind = type;
  mesh.geometry.computeBoundingBox();
  mesh.position.y = -mesh.geometry.boundingBox.min.y; // đáy chạm sàn
  return mesh;
}

/** Biểu tượng hiển thị trong danh sách vật thể. */
export function iconFor(obj) {
  const kind = obj.userData.kind;
  if (kind === 'ai') return '🪄';
  return SHAPES[kind]?.icon ?? '📦';
}
