// Dựng vật có xương (SkinnedMesh) từ 1 vật thường + danh sách khớp; gỡ xương (giữ dáng hiện tại).
// Cấu trúc: Group (vật trong cảnh, giữ vị trí/xoay/cỡ) > [SkinnedMesh, xương gốc > xương con...].
import * as THREE from 'three';
import { clone as cloneSkinned } from 'three/addons/utils/SkeletonUtils.js';
import { meshesOf } from './mesh-split-merge-operations.js';
import { toCreasedNormals } from 'three/addons/utils/BufferGeometryUtils.js';
import { densify, toFloatAttribute, toIndexedByPosition } from './mesh-subdivide-smooth.js';
import { computeSkinWeights } from './auto-skin-weights.js';
import { copyOriginalLook } from './material-preset-library.js';

export const isRigged = (obj) => {
  let found = false;
  obj?.traverse((o) => { if (o.isSkinnedMesh) found = true; });
  return found;
};

/** Nhân bản vật; vật có xương phải dùng SkeletonUtils (clone() thường dùng chung xương với bản gốc). */
export const cloneObject = (obj) => (isRigged(obj) ? cloneSkinned(obj) : obj.clone());

export const RIGGED_WARNING = 'Vật đã gắn xương — vào 🦴 Ghép xương > "Gỡ xương (giữ dáng)" trước khi sửa hình.';

export const skinnedMeshOf = (obj) => {
  let found = null;
  obj.traverse((o) => { if (!found && o.isSkinnedMesh) found = o; });
  return found;
};

/** Biên da thay đổi theo xương. Tránh tính lại toàn bộ đỉnh trong mỗi khung hình. */
export function disableSkinFrustumCulling(obj) {
  obj.traverse((o) => { if (o.isSkinnedMesh) o.frustumCulled = false; });
}

/** Geometry của mesh (duy nhất) trong `obj`, đưa về hệ toạ độ của chính `obj`. */
export function objectLocalGeometry(obj) {
  const mesh = meshesOf(obj)[0];
  obj.updateWorldMatrix(true, true);
  const rel = obj.matrixWorld.clone().invert().multiply(mesh.matrixWorld);
  const g = new THREE.BufferGeometry();
  for (const [name, attr] of Object.entries(mesh.geometry.attributes)) {
    if (name !== 'skinIndex' && name !== 'skinWeight') g.setAttribute(name, toFloatAttribute(attr));
  }
  if (mesh.geometry.index) g.setIndex(Array.from(mesh.geometry.index.array));
  mesh.geometry.groups.forEach((gr) => g.addGroup(gr.start, gr.count, gr.materialIndex));
  g.applyMatrix4(rel);
  g.computeBoundingBox();
  return { geometry: g, mesh };
}

function wrapLike(obj, kind) {
  const group = new THREE.Group();
  group.name = obj.name;
  group.userData.kind = kind;
  group.position.copy(obj.position);
  group.quaternion.copy(obj.quaternion);
  group.scale.copy(obj.scale);
  return group;
}

/** joints: [{ name, parent, position (toạ độ của obj) }] -> Group có SkinnedMesh + bộ xương. */
export function buildRiggedObject(obj, joints, softness) {
  let { geometry, mesh } = objectLocalGeometry(obj);
  // Vật quá ít điểm (khối có sẵn: hộp 24 điểm) không uốn được ở chỗ gập -> chia nhỏ trước, giữ cạnh sắc.
  if (geometry.attributes.position.count < 3000 && !Array.isArray(mesh.material)) {
    geometry = toCreasedNormals(densify(toIndexedByPosition(geometry), 8000, 120000), Math.PI / 6);
  }
  const { skinIndex, skinWeight } = computeSkinWeights(geometry.attributes.position.array, joints, softness);
  geometry.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(skinIndex, 4));
  geometry.setAttribute('skinWeight', new THREE.Float32BufferAttribute(skinWeight, 4));

  const bones = joints.map((j) => {
    const bone = Object.assign(new THREE.Bone(), { name: j.name });
    bone.userData.label = j.label ?? j.name; // nhãn tiếng Việt hiển thị trong cây xương
    return bone;
  });
  joints.forEach((j, i) => {
    const parentPos = j.parent >= 0 ? joints[j.parent].position : new THREE.Vector3();
    bones[i].position.copy(j.position).sub(parentPos);
    if (j.parent >= 0) bones[j.parent].add(bones[i]);
  });
  const group = wrapLike(obj, 'rigged');
  const skinned = new THREE.SkinnedMesh(geometry, mesh.material);
  skinned.name = `${obj.name} (da)`;
  skinned.castShadow = skinned.receiveShadow = true;
  group.add(skinned, bones[joints.findIndex((j) => j.parent < 0)]);
  group.updateMatrixWorld(true);
  skinned.bind(new THREE.Skeleton(bones));
  group.userData.bindPositions = bones.map((b) => b.position.toArray());
  copyOriginalLook(obj, group);
  return group;
}

/**
 * Khớp (toạ độ local của nhóm) của vật do Easy3D gắn xương -> quay lại bước Đặt khớp.
 * Controller đưa xương về tư thế lúc gắn trước khi gọi. Cộng dồn vị trí local để lấy khớp gốc.
 */
export function jointsFromRig(group) {
  const bones = skinnedMeshOf(group).skeleton.bones;
  return bones.map((b) => {
    const position = new THREE.Vector3();
    for (let x = b; x?.isBone; x = x.parent) position.add(x.position);
    return { name: b.name, label: b.userData.label ?? b.name, parent: bones.indexOf(b.parent), position };
  });
}

/** Gỡ xương nhưng GIỮ dáng đang tạo: nướng vị trí đã uốn vào lưới thường. */
export function bakePoseToMesh(group) {
  const skinned = skinnedMeshOf(group);
  group.updateMatrixWorld(true);
  skinned.skeleton.update(); // ma trận xương của dáng hiện tại (bình thường chỉ cập nhật khi render)
  const src = skinned.geometry;
  const g = new THREE.BufferGeometry();
  for (const [name, attr] of Object.entries(src.attributes)) {
    if (name !== 'skinIndex' && name !== 'skinWeight') g.setAttribute(name, toFloatAttribute(attr));
  }
  if (src.index) g.setIndex(Array.from(src.index.array));
  src.groups.forEach((gr) => g.addGroup(gr.start, gr.count, gr.materialIndex));
  const pos = g.attributes.position, v = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) {
    skinned.applyBoneTransform(i, v.fromBufferAttribute(src.attributes.position, i));
    pos.setXYZ(i, v.x, v.y, v.z);
  }
  // applyBoneTransform trả về toạ độ của skinned mesh (bindMode 'attached' + mesh ở gốc nhóm).
  g.computeVertexNormals();
  const mesh = new THREE.Mesh(g, skinned.material);
  mesh.name = group.name;
  mesh.castShadow = mesh.receiveShadow = true;
  mesh.userData.kind = 'edited';
  mesh.position.copy(group.position);
  mesh.quaternion.copy(group.quaternion);
  mesh.scale.copy(group.scale);
  copyOriginalLook(group, mesh);
  return mesh;
}
