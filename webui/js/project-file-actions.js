// Lưu dự án / xuất file / chụp ảnh. Bản desktop ghi qua backend (cửa sổ desktop không có hộp thoại tải xuống);
// bản online (mở qua tên miền, không phải localhost) tải thẳng về máy người dùng.
import * as THREE from 'three';
import { api } from './backend-api-client.js';
import { convertGlbToFbx } from './blender-tools-actions.js';
import { exportObjects } from './model-import-export.js';
import { cloneObject, isRigged } from './rig-builder.js';
import { toast } from './toast-notifications.js';

const FORMAT_LABELS = { glb: 'GLB (cho game)', fbx: 'FBX (cho Unity)', stl: 'STL (in 3D)', obj: 'OBJ' };

/** Tên file map: 1 map -> theo nhân vật; nhiều map -> thêm tên chất liệu để biết gán cho chất liệu nào. Rút gọn vì tên file tối đa 120 ký tự. */
function metallicMapName(name, material, total) {
  return `${name.slice(0, 60)}${total > 1 ? `_${material.slice(0, 40)}` : ''}_MetallicSmoothness.png`;
}

function openFolderAction(kind, folder = null) {
  return { label: 'Mở thư mục', onClick: () => api.openFolder(kind, folder).catch((e) => toast(e.message, { type: 'err' })) };
}

const IS_ONLINE = !['127.0.0.1', 'localhost'].includes(location.hostname);

function downloadToBrowser(name, data) {
  const url = URL.createObjectURL(data instanceof Blob ? data : new Blob([data]));
  const link = Object.assign(document.createElement('a'), { href: url, download: name });
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

/** FBX + texture + map vào chung 1 thư mục game/<Tên>/ -> kéo cả thư mục vào Unity là có đủ hình. */
async function saveFbxBundle(name, fbx, label) {
  const maps = fbx.metallicMaps;
  const files = [
    [`${name}.fbx`, fbx.data],
    ...fbx.textures.map((t) => [t.name, t.blob]),
    ...maps.map((m) => [metallicMapName(name, m.material, maps.length), m.blob]),
  ];
  if (fbx.tintDropped) toast(`${fbx.tintDropped} chất liệu mất màu phủ (tint) trên texture vì FBX không chứa được. Texture vẫn giữ.`, { type: 'warn', timeout: 9000 });
  // Map là dữ liệu tuyến tính: để sRGB bật thì Unity đọc sai độ kim loại.
  const mapNote = maps.length ? ` Map Metallic: gán tay vào Metallic Map, tắt sRGB.` : '';
  if (IS_ONLINE) {
    files.forEach(([file, data]) => downloadToBrowser(file, data));
    return toast(`${label}: đã tải ${files.length} file. Để chung 1 thư mục rồi kéo vào Assets của Unity.${mapNote}`, { type: 'ok', timeout: 10000 });
  }
  const saved = [];
  for (const [file, data] of files) saved.push(await api.saveFile('game', file, data, name));
  const folder = saved[0].path.split(/[\\/]/).slice(-2, -1)[0];
  toast(`${label}: game/${folder}/ — kéo cả thư mục vào Assets của Unity.${mapNote}`, { type: 'ok', action: openFolderAction('game', folder), timeout: 10000 });
}

function dataUrlToBlob(dataUrl) {
  const bin = atob(dataUrl.split(',')[1]);
  const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
  return new Blob([bytes], { type: 'image/png' });
}

export function createProjectFileActions({ viewport, store, getProjectName }) {
  const hasVisible = () => store.objects.some((o) => o.visible);

  async function writeFile(kind, ext, data, successLabel) {
    const name = `${getProjectName() || 'du-an'}.${ext}`;
    if (IS_ONLINE) {
      downloadToBrowser(name, data);
      return toast(`${successLabel}: ${name}`, { type: 'ok' });
    }
    const res = await api.saveFile(kind, name, data);
    toast(`${successLabel}: ${res.name}`, { type: 'ok', action: openFolderAction(kind), timeout: 7000 });
  }

  return {
    async save() {
      if (!store.objects.length) return toast('Cảnh đang trống — chưa có gì để lưu.', { type: 'warn' });
      try {
        const { data } = await exportObjects(viewport.objectsRoot, 'glb');
        await writeFile('projects', 'glb', data, 'Đã lưu dự án');
      } catch (err) {
        toast(`Lưu thất bại: ${err.message}`, { type: 'err', timeout: 8000 });
      }
    },

    /** Video quay từ thanh Chuyển động (animation-timeline-panel.js). */
    async saveVideo(blob, ext) {
      await writeFile('output', ext, blob, `Đã xuất video ${ext.toUpperCase()}`);
    },

    /** Ảnh đã render (image-export-dialog.js) -> file PNG. `renderBlob`: render bằng Blender (trả Blob). */
    async saveImage(dataUrl, sizeLabel, renderBlob = null) {
      try {
        const blob = renderBlob ? await renderBlob() : dataUrlToBlob(dataUrl);
        await writeFile('output', 'png', blob, `Đã xuất ảnh ${sizeLabel}`);
      } catch (err) {
        toast(`Xuất ảnh thất bại: ${err.message}`, { type: 'err', timeout: 8000 });
      }
    },

    /** 1 nhân vật -> output/game/<Tên>/<Tên>.glb|.fbx (xương tên Unity + chuyển động) để kéo thẳng vào project game. */
    async exportCharacter(obj, format = 'glb') {
      if (!obj || obj.userData.kind === 'light') return toast('Hãy bấm chọn nhân vật cần xuất trước.', { type: 'warn' });
      try {
        const root = new THREE.Group();
        root.userData.animDuration = viewport.objectsRoot.userData.animDuration;
        root.add(cloneObject(obj));
        const { data } = await exportObjects(root, 'glb');
        const name = obj.name.trim() || 'NhanVat';
        if (format === 'fbx') return await saveFbxBundle(name, await convertGlbToFbx(data), `Đã xuất nhân vật FBX${isRigged(obj) ? ' (có xương)' : ''}`);
        if (IS_ONLINE) {
          downloadToBrowser(`${name}.glb`, data);
          return toast(`Đã tải nhân vật: ${name}.glb`, { type: 'ok' });
        }
        const res = await api.saveFile('game', `${name}.glb`, data, name);
        const folder = res.path.split(/[\\/]/).slice(-2, -1)[0];
        toast(`Đã xuất nhân vật: game/${folder}/${res.name}${isRigged(obj) ? ' (có xương)' : ''}`,
          { type: 'ok', action: openFolderAction('game', folder), timeout: 8000 });
      } catch (err) {
        toast(`Xuất nhân vật thất bại: ${err.message}`, { type: 'err', timeout: 8000 });
      }
    },

    async export(format) {
      try {
        if (!hasVisible()) return toast('Không có vật thể nào đang hiện để xuất.', { type: 'warn' });
        if (format === 'fbx') {
          const { data: glb } = await exportObjects(viewport.objectsRoot, 'glb');
          return await saveFbxBundle(getProjectName() || 'du-an', await convertGlbToFbx(glb), `Đã xuất ${FORMAT_LABELS.fbx}`);
        }
        const { data, ext } = await exportObjects(viewport.objectsRoot, format);
        await writeFile('output', ext, data, `Đã xuất ${FORMAT_LABELS[format]}`);
      } catch (err) {
        toast(`Xuất file thất bại: ${err.message}`, { type: 'err', timeout: 8000 });
      }
    },
  };
}
