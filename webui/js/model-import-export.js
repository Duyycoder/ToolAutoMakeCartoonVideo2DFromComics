// Mở file 3D (GLB/GLTF/OBJ/STL/FBX/MESHY) và xuất cảnh (GLB/STL/OBJ).
import * as THREE from 'three';
import { createGLTFLoader, friendlyGLTFError } from './gltf-loader-factory.js';
import { decodeMeshyFile } from './meshy-decoder.js';
import { buildClip } from './keyframe-animation.js';
import { standardizeMaterials } from './material-standardize.js';
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { FBXLoader } from 'three/addons/loaders/FBXLoader.js';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
import { STLExporter } from 'three/addons/exporters/STLExporter.js';
import { OBJExporter } from 'three/addons/exporters/OBJExporter.js';

export const MODEL_EXTENSIONS = ['glb', 'gltf', 'obj', 'stl', 'fbx', 'meshy', 'blend']; // blend: đổi qua Blender ẩn (editor-actions)
export const extOf = (name) => name.split('.').pop().toLowerCase();
export const baseNameOf = (name) => name.replace(/\.[^.]+$/, '');

/**
 * Đọc file người dùng chọn. Trả về { objects, isProject }:
 *  - isProject = true: file .glb do Easy3D lưu -> tách lại từng vật thể như lúc lưu.
 *  - ngược lại: 1 vật thể đã chuẩn hoá (đặt giữa, chạm sàn, cỡ hợp lý).
 */
export async function loadModelFile(file) {
  const ext = extOf(file.name);
  const buffer = await file.arrayBuffer();
  let obj;
  try {
    if (ext === 'glb' || ext === 'gltf' || ext === 'meshy') {
      const gltfBuffer = ext === 'meshy' ? await decodeMeshyFile(buffer) : buffer;
      const gltf = await createGLTFLoader().parseAsync(gltfBuffer, '');
      const project = gltf.scene.children.find((c) => c.userData?.easy3dProject);
      if (project) {
        // GLTFLoader đổi khoảng trắng trong tên node thành "_" -> lấy lại tên gốc đã cất khi lưu.
        project.children.forEach((o) => { o.name = o.userData.easy3dName ?? o.name; });
        return { objects: [...project.children], isProject: true, lighting: project.userData.lighting, lightSettings: project.userData.lightSettings };
      }
      obj = gltf.scene;
    } else if (ext === 'obj') {
      obj = new OBJLoader().parse(new TextDecoder().decode(buffer));
    } else if (ext === 'stl') {
      const geometry = new STLLoader().parse(buffer);
      obj = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ color: 0xb8c0d0, roughness: 0.5 }));
    } else if (ext === 'fbx') {
      obj = new FBXLoader().parse(buffer, '');
    } else {
      throw new Error(`Chưa hỗ trợ định dạng .${ext}`);
    }
  } catch (err) {
    const hint = ext === 'gltf' ? ' File .gltf có file .bin/texture đi kèm — hãy dùng .glb.' : '';
    throw new Error(`Không đọc được file "${file.name}". ${friendlyGLTFError(err)}${hint}`);
  }
  prepareImported(obj);
  return { objects: [obj], isProject: false };
}

/** Tải GLB từ URL (kết quả AI). */
export async function loadModelUrl(url) {
  const gltf = await createGLTFLoader().loadAsync(url);
  prepareImported(gltf.scene);
  return gltf.scene;
}

/** Bật bóng đổ; file quá to/quá nhỏ (vd. STL đơn vị mm) -> đưa về cao ~1 m; đặt giữa + chạm sàn. */
export function prepareImported(obj) {
  standardizeMaterials(obj); // FBX/OBJ Phong -> PBR: ăn ánh sáng môi trường như vật khác
  obj.traverse((m) => {
    if (m.isMesh) { m.castShadow = true; m.receiveShadow = true; }
  });
  const size = new THREE.Box3().setFromObject(obj).getSize(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z);
  if (maxDim > 20 || (maxDim > 0 && maxDim < 0.05)) obj.scale.multiplyScalar(1 / maxDim);
  const box = new THREE.Box3().setFromObject(obj);
  const center = box.getCenter(new THREE.Vector3());
  obj.position.x -= center.x;
  obj.position.z -= center.z;
  obj.position.y -= box.min.y;
}

/** Vị trí mới (chưa áp dụng) để vật chạm sàn. */
export function floorPosition(obj) {
  const box = new THREE.Box3().setFromObject(obj);
  return obj.position.clone().setY(obj.position.y - box.min.y);
}

/** Bản sao chỉ gồm vật đang hiện (STL/OBJ exporter không tự bỏ vật ẩn). */
function visibleCopy(root, scale = 1) {
  const group = new THREE.Group();
  // Bỏ đèn: bóng đèn chỉ để nhìn thấy trong app, không phải hình cần in/xuất.
  root.children.filter((c) => c.visible && c.userData.kind !== 'light').forEach((c) => group.add(c.clone()));
  group.scale.setScalar(scale);
  group.updateMatrixWorld(true);
  return group;
}

/** Xuất cảnh. Trả về { data: ArrayBuffer|string, ext }. */
export async function exportObjects(root, format) {
  if (format === 'glb') {
    root.children.forEach((o) => { o.userData.easy3dName = o.name; }); // xem loadModelFile
    // Kèm chuyển động (nếu có) -> Unity/Godot/Blender phát được ngay.
    const clip = buildClip(root.children, root.userData.animDuration ?? 4);
    const data = await new GLTFExporter().parseAsync(root, { binary: true, onlyVisible: true, animations: clip ? [clip] : [] });
    return { data, ext: 'glb' };
  }
  if (format === 'stl') {
    // Máy in 3D/slicer hiểu STL theo milimét: 1 m = 1000 mm.
    const view = new STLExporter().parse(visibleCopy(root, 1000), { binary: true });
    return { data: view.buffer, ext: 'stl' };
  }
  if (format === 'obj') {
    return { data: new OBJExporter().parse(visibleCopy(root)), ext: 'obj' };
  }
  throw new Error(`Định dạng xuất không hỗ trợ: ${format}`);
}
