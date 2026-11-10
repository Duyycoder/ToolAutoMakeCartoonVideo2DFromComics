// Các phần bên trong 1 vật (để danh sách vật thể hiện ra và tách ra sửa riêng).
import { copyOriginalLook, rememberOriginalLook } from './material-preset-library.js';

/**
 * Nhóm (Ctrl+G, nhân mảng) -> các vật con. Model nhập 1 gốc lồng nhiều lưới (FBX: thân > bơm > tay cầm) -> từng lưới.
 * Lưới có xương không tách lẻ (mất liên kết với xương). Đèn -> [] (bóng đèn chỉ là hình minh hoạ).
 */
export function partsOf(obj) {
  if (obj.userData.kind === 'light') return [];
  if (!obj.isMesh && obj.children.length > 1) return obj.children;
  const meshes = [];
  let skinned = false;
  obj.traverse((o) => { if (o.isMesh) meshes.push(o); if (o.isSkinnedMesh) skinned = true; });
  return skinned || meshes.length < 2 ? [] : meshes;
}

/** Bản sao độc lập của từng phần, đặt đúng chỗ đang thấy. Trả về [] nếu vật không có nhiều phần. */
export function detachParts(obj) {
  const parts = partsOf(obj);
  const wholeChildren = parts === obj.children; // vật con của nhóm: giữ nguyên cả cây con
  return parts.map((part) => {
    const copy = part.clone(wholeChildren);
    part.updateWorldMatrix(true, false);
    part.matrixWorld.decompose(copy.position, copy.quaternion, copy.scale);
    copy.name = part.name || obj.name;
    copy.userData = { ...part.userData, kind: part.userData.kind ?? obj.userData.kind };
    if (wholeChildren) {
      copyOriginalLook(part, copy);
    } else {
      // Các lưới FBX thường dùng chung 1 vật liệu -> tách riêng, đổi màu 1 phần không đổi cả vật.
      copy.material = Array.isArray(part.material) ? part.material.map((m) => m.clone()) : part.material.clone();
      rememberOriginalLook(copy);
    }
    return copy;
  });
}
