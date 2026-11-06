// Gửi vật/cảnh sang Blender chạy ẩn (backend/routes_blender.py): bo tròn cạnh, làm lưới đều, sửa lỗi in 3D, render Cycles.
import * as THREE from 'three';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { api } from './backend-api-client.js';
import { createGLTFLoader } from './gltf-loader-factory.js';
import { firstMaterialOf, meshesOf, unifyAttributes } from './mesh-split-merge-operations.js';
import { addObjectCommand, batchCommand, removeObjectCommand } from './scene-edit-commands.js';
import { copyOriginalLook } from './material-preset-library.js';
import { toast } from './toast-notifications.js';

const LABELS = { bevel: 'Bo tròn cạnh', remesh: 'Làm lưới đều', repair: 'Sửa lỗi để in 3D', render: 'Render đẹp' };
let status = null; // lấy 1 lần khi mở app (panel vẽ đồng bộ)
export const refreshBlenderStatus = () => api.blenderStatus().then((s) => { status = s; }).catch(() => { status = null; });
export const blenderReady = () => !!status?.ready;
export const blenderMessage = () => status?.message ?? 'Đang kiểm tra Blender...';

/** Chạy 1 thao tác Blender, hiện tiến độ trên toast; trả về job đã xong (hoặc ném lỗi). */
async function runJob(op, params, glbData) {
  if (!blenderReady()) throw new Error(blenderMessage());
  const job = await api.runBlender(op, params, new Blob([glbData], { type: 'model/gltf-binary' }));
  const note = toast(`${LABELS[op]}: đang xếp hàng...`, { timeout: 0 });
  try {
    return await new Promise((resolve, reject) => {
      api.watchJob(job.id, (ev) => {
        if (ev.msg) note.querySelector('span').textContent = `${LABELS[op]}: ${ev.msg}`;
        if (ev.type !== 'status') return;
        if (ev.status === 'done') resolve({ ...job, result: ev.result });
        else if (ev.status === 'error' || ev.status === 'cancelled') reject(new Error(ev.msg));
      });
    });
  } finally {
    note.remove();
  }
}

/** Vật đặt ở gốc toạ độ (không xoay/co giãn) -> kết quả trả về nằm đúng hệ toạ độ của vật. */
async function exportAtOrigin(obj) {
  const copy = obj.clone();
  copy.position.set(0, 0, 0);
  copy.quaternion.identity();
  copy.scale.set(1, 1, 1);
  const wrap = new THREE.Group();
  wrap.add(copy);
  return new GLTFExporter().parseAsync(wrap, { binary: true });
}

/** Blender luôn render nền trong suốt (để có bóng trên sàn) -> lót màu nền của cảnh nếu người dùng muốn nền đặc. */
async function withBackground(png, color) {
  const bitmap = await createImageBitmap(png);
  const canvas = Object.assign(document.createElement('canvas'), { width: bitmap.width, height: bitmap.height });
  const g = canvas.getContext('2d');
  g.fillStyle = color;
  g.fillRect(0, 0, canvas.width, canvas.height);
  g.drawImage(bitmap, 0, 0);
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
}

export function createBlenderTools({ store, stack }) {
  return {
    /** bevel / remesh / repair: thay vật bằng lưới Blender trả về, giữ vật liệu + vị trí (1 bước Undo). */
    async meshOp(obj, op, params = {}) {
      try {
        const job = await runJob(op, params, await exportAtOrigin(obj));
        const gltf = await createGLTFLoader().loadAsync(api.resultUrl(job.id));
        gltf.scene.updateMatrixWorld(true);
        const geos = meshesOf(gltf.scene).map((m) => m.geometry.clone().applyMatrix4(m.matrixWorld));
        const geometry = geos.length === 1 ? geos[0] : mergeGeometries(unifyAttributes(geos), false);
        const material = firstMaterialOf(meshesOf(obj)[0]);
        if (geometry.attributes.color && !material.vertexColors) geometry.deleteAttribute('color');
        const mesh = new THREE.Mesh(geometry, material);
        Object.assign(mesh, { name: obj.name, castShadow: true, receiveShadow: true });
        mesh.position.copy(obj.position); mesh.quaternion.copy(obj.quaternion); mesh.scale.copy(obj.scale);
        mesh.userData.kind = 'edited';
        copyOriginalLook(obj, mesh);
        stack.execute(batchCommand(LABELS[op], [removeObjectCommand(store, obj), addObjectCommand(store, mesh)]));
        const r = job.result ?? {};
        const extra = op === 'repair' ? ` — cạnh lỗi: ${r.non_manifold_before} → ${r.non_manifold_after}` : '';
        toast(`Xong: ${LABELS[op]} (${r.seconds ?? '?'} s)${extra}`, { type: 'ok', timeout: 7000 });
      } catch (err) {
        toast(`${LABELS[op]} thất bại: ${err.message}`, { type: 'err', timeout: 9000 });
      }
    },

    /** Render cả cảnh (vật đang hiện) bằng Cycles theo góc nhìn + ánh sáng hiện tại. Trả về Blob PNG. */
    async render(viewport, { width, height, transparent, samples = 96 }) {
      const { camera, orbit, scene, lights } = viewport;
      const params = {
        width, height, transparent, samples, fov: camera.fov,
        camera_position: camera.position.toArray(), camera_target: orbit.target.toArray(),
        background: `#${scene.background.getHexString()}`,
        sun_position: lights.sun.position.toArray(), sun_color: `#${lights.sun.color.getHexString()}`,
        sun_intensity: lights.sun.intensity, ambient: lights.hemi.intensity * 0.6 + (scene.environmentIntensity ?? 1) * 0.3,
      };
      const data = await new GLTFExporter().parseAsync(viewport.objectsRoot, { binary: true, onlyVisible: true });
      const job = await runJob('render', params, data);
      const png = await (await fetch(api.resultImageUrl(job.id))).blob();
      return transparent ? png : withBackground(png, params.background);
    },
  };
}
