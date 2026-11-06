// FBX/OBJ dùng MeshPhong/MeshLambert: KHÔNG nhận ánh sáng môi trường (scene.environment) -> trông tối, bóng nhựa,
// đổi preset ánh sáng gần như không thấy khác; xuất GLB cũng bị đổi vật liệu kém. Đổi sang MeshStandardMaterial (PBR)
// ngay khi mở file: giữ màu, ảnh texture, normal/bump, phát sáng, trong suốt.
import * as THREE from 'three';

const KEEP = ['name', 'map', 'normalMap', 'bumpMap', 'bumpScale', 'aoMap', 'alphaMap', 'emissiveMap', 'emissiveIntensity',
  'lightMap', 'transparent', 'opacity', 'alphaTest', 'side', 'vertexColors', 'flatShading', 'visible', 'depthWrite'];

function toStandard(mat) {
  if (!mat?.isMeshPhongMaterial && !mat?.isMeshLambertMaterial) return mat;
  const out = new THREE.MeshStandardMaterial();
  for (const key of KEEP) if (mat[key] !== undefined) out[key] = mat[key];
  out.color.copy(mat.color);
  out.emissive.copy(mat.emissive);
  if (mat.normalScale) out.normalScale.copy(mat.normalScale);
  // Phong: shininess cao = bóng. Ước lượng độ nhám; vật liệu FBX hiếm khi là kim loại thật.
  out.roughness = mat.isMeshPhongMaterial ? THREE.MathUtils.clamp(1 - mat.shininess / 200, 0.4, 1) : 1;
  out.metalness = 0;
  out.userData = { ...mat.userData };
  return out;
}

/** Đổi mọi vật liệu Phong/Lambert trong `obj` sang PBR (tại chỗ). */
export function standardizeMaterials(obj) {
  obj.traverse((m) => {
    if (!m.isMesh) return;
    m.material = Array.isArray(m.material) ? m.material.map(toStandard) : toStandard(m.material);
  });
}
