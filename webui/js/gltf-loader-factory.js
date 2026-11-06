// GLTFLoader đọc được cả file GLB đã NÉN (rất phổ biến khi tải model trên mạng):
//  - EXT_meshopt_compression (gltfpack, nhiều trang tạo model AI) -> MeshoptDecoder
//  - KHR_draco_mesh_compression (Sketchfab, Blender khi bật nén) -> DRACOLoader (wasm, chạy offline)
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';

let draco = null;

export function createGLTFLoader() {
  if (!draco) {
    draco = new DRACOLoader();
    draco.setDecoderPath(new URL('../vendor/three/addons/libs/draco/gltf/', import.meta.url).href);
  }
  return new GLTFLoader().setDRACOLoader(draco).setMeshoptDecoder(MeshoptDecoder);
}

/** Lỗi đọc glTF -> câu tiếng Việt dễ hiểu (vd. file dùng kiểu nén chưa hỗ trợ). */
export function friendlyGLTFError(err) {
  const ext = String(err?.message ?? err).match(/(KHR|EXT)_[A-Za-z0-9_]+/)?.[0];
  if (ext) return `File dùng định dạng "${ext}" mà Easy3D chưa đọc được. Hãy xuất lại file GLB ở chế độ không nén.`;
  return err?.message ?? String(err);
}
