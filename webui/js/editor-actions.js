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
import { baseNameOf, floorPosition, loadModelFile, loadModelUrl } from './model-import-export.js';
import { toast } from './toast-notifications.js';
import { applyLighting } from './lighting-presets.js';
import { fixLightCopy } from './scene-light-objects.js';

export function createEditorActions({ viewport, store, stack }) {
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

  function moveTo(obj, position, label) {
    const before = snapshotTransform(obj);
    const after = { ...before, p: position };
    if (!sameTransform(before, after)) run(transformCommand(store, obj, before, after, label));
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
    },

    async addModelFromUrl(url, name) {
      const obj = await loadModelUrl(url);
      obj.name = store.nextName(name);
      actions.addModel(obj, 'ai');
    },

    async openFile(file) {
      try {
        const { objects, isProject, lighting } = await loadModelFile(file);
        if (isProject) {
          if (lighting) applyLighting(viewport, lighting);
          objects.forEach(fixLightCopy);
          objects.forEach(rememberOriginalLook);
          run(batchCommand(`Mở "${file.name}"`, objects.map((o) => addObjectCommand(store, o))));
          viewport.frameObjects();
        } else {
          objects[0].name = store.nextName(baseNameOf(file.name));
          actions.addModel(objects[0], 'imported');
        }
        toast(`Đã mở "${file.name}"`, { type: 'ok' });
      } catch (err) {
        toast(err.message, { type: 'err', timeout: 8000 });
      }
    },

    remove(obj) { run(removeObjectCommand(store, obj)); },

    duplicate(obj) {
      const copy = obj.clone();
      copy.name = store.nextName(obj.name.replace(/\s\d+$/, ''));
      copy.position.x += 1.2;
      copyOriginalLook(obj, copy);
      fixLightCopy(copy);
      run(addObjectCommand(store, copy));
    },

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
      const box = new THREE.Box3().setFromObject(obj);
      const c = box.getCenter(new THREE.Vector3());
      moveTo(obj, obj.position.clone().sub(new THREE.Vector3(c.x, 0, c.z)), 'Về giữa');
    },
  };
  return actions;
}
