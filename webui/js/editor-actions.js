// Mọi thao tác chỉnh sửa của người dùng — đều đi qua CommandStack để Undo được.
import * as THREE from 'three';
import { createPrimitive, SHAPES } from './primitive-shape-factory.js';
import {
  applyColor, applyPreset, copyOriginalLook, MATERIAL_PRESETS, rememberOriginalLook, restoreOriginalLook,
} from './material-preset-library.js';
import {
  addObjectCommand, batchCommand, materialCommand, removeObjectCommand, renameCommand,
  sameTransform, snapshotMaterials, snapshotTransform, transformCommand,
} from './scene-edit-commands.js';
import {
  MODEL_EXTENSIONS, baseNameOf, extOf, floorPosition, loadModelFile, loadModelUrl,
} from './model-import-export.js';
import { expandZips } from './model-companion-files.js';
import { convertBlendFile } from './blender-tools-actions.js';
import { toast } from './toast-notifications.js';
import { restoreLighting } from './lighting-presets.js';
import { fixLightCopy } from './scene-light-objects.js';
import { cloneObject } from './rig-builder.js';

export function createEditorActions({ viewport, store, stack, onModelAdded = null }) {
  const run = (cmd) => stack.execute(cmd);
  let scaleBefore = null;

  /** Đặt vật mới lệch sang trái/phải để không chồng lên vật cũ. */
  function spreadPosition(obj) {
    const n = store.objects.length;
    if (n) obj.position.x += (n % 2 ? 1 : -1) * Math.ceil(n / 2) * 1.3;
  }

  function changeMaterial(obj, label, mutate) {
    const before = snapshotMaterials(obj);
    mutate();
    const after = snapshotMaterials(obj);
    stack.push(materialCommand(store, before, after, label));
    store.changed();
  }

  function makeCopy(obj) {
    const copy = cloneObject(obj);
    copy.name = store.nextName(obj.name.replace(/\s\d+$/, ''));
    copy.position.x += 1.2;
    copyOriginalLook(obj, copy);
    fixLightCopy(copy);
    return copy;
  }

  function moveTo(obj, position, label) {
    const before = snapshotTransform(obj);
    const after = { ...before, p: position };
    if (!sameTransform(before, after)) run(transformCommand(store, obj, before, after, label));
  }

  /** .blend: Blender ẩn đổi sang GLB rồi mở như model thường (sửa, tô, gắn xương... như mọi vật khác). */
  async function openBlend(file) {
    const { url, stats } = await convertBlendFile(file);
    const obj = await loadModelUrl(url);
    obj.name = store.nextName(baseNameOf(file.name));
    actions.addModel(obj, 'imported');
    const missing = stats.missing_images?.length ? ` — thiếu ${stats.missing_images.length} ảnh texture nằm ngoài file (${stats.missing_images.join(', ')})` : '';
    toast(`Đã mở "${file.name}": ${stats.objects ?? '?'} vật${missing}`, { type: missing ? 'warn' : 'ok', timeout: missing ? 10000 : 5000 });
  }

  const actions = {
    addShape(type) {
      const obj = createPrimitive(type, store.nextName(SHAPES[type].label));
      spreadPosition(obj);
      run(addObjectCommand(store, obj));
    },

    /** Thêm model (AI / file nhập) và đưa camera tới nó. */
    addModel(obj, kind) {
      obj.userData.kind = kind;
      rememberOriginalLook(obj);
      spreadPosition(obj);
      run(addObjectCommand(store, obj));
      viewport.frameObjects(obj);
      onModelAdded?.(obj); // vd. cảnh báo model quá nặng
    },

    async addModelFromUrl(url, name) {
      const obj = await loadModelUrl(url);
      obj.name = store.nextName(name);
      actions.addModel(obj, 'ai');
    },

    /** Chọn/thả nhiều file cùng lúc (hoặc .zip): mỗi file mô hình được mở, các file còn lại (ảnh texture...) là đồ đi kèm. */
    async openFiles(files) {
      try {
        const all = await expandZips(files);
        const models = all.filter((f) => MODEL_EXTENSIONS.includes(extOf(f.name)));
        if (!models.length) return toast(`Không thấy file mô hình (${MODEL_EXTENSIONS.join('/').toUpperCase()}) trong các file đã chọn.`, { type: 'warn' });
        const extras = all.filter((f) => !models.includes(f));
        for (const model of models) await actions.openFile(model, extras);
      } catch (err) {
        toast(`Không mở được file: ${err.message}`, { type: 'err', timeout: 8000 });
      }
    },

    async openFile(file, extras = []) {
      try {
        if (extOf(file.name) === 'blend') return await openBlend(file);
        const { objects, isProject, lighting, lightSettings, missing = [], assigned = [], unused = [] } = await loadModelFile(file, extras);
        if (isProject) {
          if (lighting || lightSettings) restoreLighting(viewport, lighting, lightSettings);
          objects.forEach(fixLightCopy);
          objects.forEach(rememberOriginalLook);
          run(batchCommand(`Mở "${file.name}"`, objects.map((o) => addObjectCommand(store, o))));
          viewport.frameObjects();
        } else {
          objects[0].name = store.nextName(baseNameOf(file.name));
          actions.addModel(objects[0], 'imported');
        }
        if (missing.length) {
          return toast(`Đã mở "${file.name}" nhưng thiếu ${missing.length} ảnh texture: ${missing.join(', ')}. `
            + 'Hãy chọn (giữ Ctrl) hoặc kéo thả file mô hình cùng các ảnh này một lượt.', { type: 'warn', timeout: 12000 });
        }
        const notes = [
          assigned.length && `file không ghi tên ảnh nên đã tự gán theo tên: ${assigned.join(', ')}`,
          unused.length && `chưa biết gán ảnh ${unused.join(', ')} vào đâu (tên ảnh cần có BaseColor/Albedo hoặc Normal)`,
        ].filter(Boolean);
        toast(`Đã mở "${file.name}"${notes.length ? ` — ${notes.join('; ')}` : ''}`, { type: unused.length ? 'warn' : 'ok', timeout: notes.length ? 10000 : 4000 });
      } catch (err) {
        toast(err.message, { type: 'err', timeout: 8000 });
      }
    },

    remove(obj) { run(removeObjectCommand(store, obj)); },

    /** Xoá / nhân bản tất cả vật đang chọn — 1 bước Undo. */
    removeMany(objs) {
      if (objs.length === 1) return actions.remove(objs[0]);
      run(batchCommand(`Xoá ${objs.length} vật`, objs.map((o) => removeObjectCommand(store, o))));
    },
    duplicateMany(objs) {
      const copies = objs.map(makeCopy);
      // Bản sao phần con nằm cùng vật cha với bản gốc (toạ độ là toạ độ trong vật cha).
      run(batchCommand(`Nhân bản ${copies.length} vật`, copies.map((c, i) => addObjectCommand(store, c, objs[i].parent))));
      store.selectMany(copies); // chọn sẵn các bản sao để kéo đi luôn
    },
    duplicate(obj) { actions.duplicateMany([obj]); },

    clearScene() {
      if (!store.objects.length) return;
      run(batchCommand('Xoá cảnh', [...store.objects].map((o) => removeObjectCommand(store, o))));
      toast('Đã xoá hết vật thể.', { action: { label: 'Hoàn tác', onClick: () => stack.undo() } });
    },

    rename(obj, name) {
      if (name !== obj.name) run(renameCommand(store, obj, obj.name, name));
    },

    setColor(obj, hex) {
      changeMaterial(obj, 'Đổi màu', () => (hex ? applyColor(obj, hex) : restoreOriginalLook(obj)));
    },
    setColorMany(objs, hex) {
      const shapes = objs.filter((o) => o.userData.kind !== 'light');
      const cmds = shapes.map((o) => {
        const before = snapshotMaterials(o);
        applyColor(o, hex);
        return materialCommand(store, before, snapshotMaterials(o), 'Đổi màu');
      });
      stack.push(batchCommand(`Đổi màu ${shapes.length} vật`, cmds));
      store.changed();
    },

    setPreset(obj, key) {
      changeMaterial(obj, `Chất liệu ${MATERIAL_PRESETS[key].label}`, () => applyPreset(obj, key));
    },

    beginScale(obj) { scaleBefore = snapshotTransform(obj); },
    previewScale(obj, factor) {
      if (!scaleBefore) actions.beginScale(obj); // kéo bằng bàn phím không có pointerdown
      obj.scale.multiplyScalar(factor / (Math.abs(obj.scale.x) || 1)); // scale âm = vật lật gương
      store.transformed();
    },
    commitScale(obj) {
      if (!scaleBefore) return;
      const after = snapshotTransform(obj);
      if (!sameTransform(scaleBefore, after)) stack.push(transformCommand(store, obj, scaleBefore, after, 'Co giãn'));
      scaleBefore = null;
    },

    dropToFloor(obj) { moveTo(obj, floorPosition(obj), 'Đặt lên sàn'); },
    center(obj) {
      const c = new THREE.Box3().setFromObject(obj).getCenter(new THREE.Vector3());
      const target = obj.getWorldPosition(new THREE.Vector3()).sub(new THREE.Vector3(c.x, 0, c.z));
      moveTo(obj, obj.parent.worldToLocal(target), 'Về giữa'); // phần con: đổi về toạ độ trong vật cha
    },
  };
  return actions;
}
