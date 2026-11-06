// Chất liệu dạng "preset" dễ hiểu thay vì thông số roughness/metalness.
// Luôn tạo material MỚI (không sửa material cũ) -> Undo chỉ cần gán lại material cũ.
import * as THREE from 'three';

export const MATERIAL_PRESETS = {
  plastic: { label: 'Nhựa', make: () => new THREE.MeshStandardMaterial({ roughness: 0.45, metalness: 0 }) },
  matte: { label: 'Mờ (gỗ, đất)', make: () => new THREE.MeshStandardMaterial({ roughness: 0.95, metalness: 0 }) },
  metal: { label: 'Kim loại', make: () => new THREE.MeshStandardMaterial({ roughness: 0.25, metalness: 1 }) },
  glass: {
    label: 'Kính',
    make: () => new THREE.MeshPhysicalMaterial({ roughness: 0.05, metalness: 0, transparent: true, opacity: 0.35 }),
  },
  toon: { label: 'Hoạt hình', make: () => new THREE.MeshToonMaterial() },
  glow: { label: 'Phát sáng', make: () => new THREE.MeshStandardMaterial({ emissiveIntensity: 1.2 }) },
  // `color`: preset tự đặt màu đặc trưng (vàng phải có màu vàng).
  rubber: { label: 'Cao su', make: () => new THREE.MeshStandardMaterial({ roughness: 1, metalness: 0 }) },
  gold: { label: 'Vàng', color: '#ffc845', make: () => new THREE.MeshStandardMaterial({ roughness: 0.2, metalness: 1 }) },
  chrome: { label: 'Chrome', color: '#e8e8ea', make: () => new THREE.MeshStandardMaterial({ roughness: 0.03, metalness: 1 }) },
  ceramic: {
    label: 'Gốm sứ',
    make: () => new THREE.MeshPhysicalMaterial({ roughness: 0.35, clearcoat: 1, clearcoatRoughness: 0.08 }),
  },
  fabric: {
    label: 'Vải',
    make: () => new THREE.MeshPhysicalMaterial({ roughness: 1, sheen: 1, sheenRoughness: 0.6, sheenColor: 0xffffff }),
  },
  jade: {
    label: 'Ngọc',
    color: '#4fbf8a',
    make: () => new THREE.MeshPhysicalMaterial({ roughness: 0.25, transmission: 0.6, thickness: 0.5 }),
  },
};

// Màu/texture gốc của model AI hoặc file nhập vào — để nút "Màu gốc" khôi phục.
// Dùng WeakMap vì Object3D.clone() JSON-hoá userData (không chứa được material).
const originalLooks = new WeakMap();

const meshesOf = (obj) => {
  const list = [];
  obj.traverse((m) => { if (m.isMesh) list.push(m); });
  return list;
};

const mapMaterials = (mesh, fn) => {
  mesh.material = Array.isArray(mesh.material) ? mesh.material.map(fn) : fn(mesh.material);
};

const firstMaterial = (obj) => {
  const mesh = meshesOf(obj)[0];
  return mesh && (Array.isArray(mesh.material) ? mesh.material[0] : mesh.material);
};

export function rememberOriginalLook(obj) {
  originalLooks.set(obj, meshesOf(obj).map((m) => m.material));
}

export function copyOriginalLook(from, to) {
  if (originalLooks.has(from)) originalLooks.set(to, originalLooks.get(from));
}

export const hasOriginalLook = (obj) => originalLooks.has(obj);

export function restoreOriginalLook(obj) {
  const mats = originalLooks.get(obj);
  if (!mats) return;
  meshesOf(obj).forEach((m, i) => { if (mats[i]) m.material = mats[i]; });
}

export function applyPreset(obj, key) {
  const preset = MATERIAL_PRESETS[key];
  meshesOf(obj).forEach((mesh) => mapMaterials(mesh, (old) => {
    const mat = preset.make();
    if (old.color) mat.color.copy(old.color);
    mat.map = old.map ?? null;
    mat.vertexColors = old.vertexColors;
    if (preset.color) {
      mat.color.set(preset.color);
      mat.vertexColors = false;
    }
    if (key === 'glow') mat.emissive.copy(mat.color);
    mat.userData.preset = key;
    return mat;
  }));
}

/** Tô 1 màu đồng nhất (bỏ màu đỉnh/texture của model AI — "Màu gốc" để lấy lại). */
export function applyColor(obj, hex) {
  meshesOf(obj).forEach((mesh) => mapMaterials(mesh, (old) => {
    const mat = old.clone();
    mat.color?.set(hex);
    mat.vertexColors = false;
    mat.map = null;
    if (mat.userData.preset === 'glow') mat.emissive.set(hex);
    mat.needsUpdate = true;
    return mat;
  }));
}

export const getPresetKey = (obj) => firstMaterial(obj)?.userData?.preset ?? 'plastic';

export function getColorHex(obj) {
  const mat = firstMaterial(obj);
  if (!mat?.color || mat.vertexColors || mat.map) return null; // đang dùng màu gốc
  return `#${mat.color.getHexString()}`;
}
