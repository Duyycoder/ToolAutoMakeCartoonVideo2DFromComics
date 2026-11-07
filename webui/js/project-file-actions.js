// Lưu dự án / xuất file / chụp ảnh. Bản desktop ghi qua backend (cửa sổ desktop không có hộp thoại tải xuống);
// bản online (mở qua tên miền, không phải localhost) tải thẳng về máy người dùng.
import * as THREE from 'three';
import { api } from './backend-api-client.js';
import { exportObjects } from './model-import-export.js';
import { cloneObject, isRigged } from './rig-builder.js';
import { toast } from './toast-notifications.js';

const FORMAT_LABELS = { glb: 'GLB (cho game)', stl: 'STL (in 3D)', obj: 'OBJ' };

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

    /** 1 nhân vật -> output/game/<Tên>/<Tên>.glb (xương tên Unity + chuyển động) để kéo thẳng vào project game. */
    async exportCharacter(obj) {
      if (!obj || obj.userData.kind === 'light') return toast('Hãy bấm chọn nhân vật cần xuất trước.', { type: 'warn' });
      try {
        const root = new THREE.Group();
        root.userData.animDuration = viewport.objectsRoot.userData.animDuration;
        root.add(cloneObject(obj));
        const { data } = await exportObjects(root, 'glb');
        const name = obj.name.trim() || 'NhanVat';
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
        const { data, ext } = await exportObjects(viewport.objectsRoot, format);
        await writeFile('output', ext, data, `Đã xuất ${FORMAT_LABELS[format]}`);
      } catch (err) {
        toast(`Xuất file thất bại: ${err.message}`, { type: 'err', timeout: 8000 });
      }
    },
  };
}
