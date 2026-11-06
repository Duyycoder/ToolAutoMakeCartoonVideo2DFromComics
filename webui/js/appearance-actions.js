// Thao tác "ngoại hình" (đều Undo được): vân bề mặt, chỉnh vật liệu nâng cao, đèn, ánh sáng cảnh.
import { addObjectCommand, materialCommand, snapshotMaterials } from './scene-edit-commands.js';
import { ensureUV, imageFileTexture, PATTERNS, patternTexture } from './procedural-texture-library.js';
import { createLightObject, getLightLook, LIGHT_TYPES, setLightLook } from './scene-light-objects.js';
import { applyLighting, LIGHTING_PRESETS } from './lighting-presets.js';
import { meshesOf } from './mesh-split-merge-operations.js';
import * as THREE from 'three';
import { toast } from './toast-notifications.js';

const mapMaterials = (obj, fn) => meshesOf(obj).forEach((m) => {
  m.material = Array.isArray(m.material) ? m.material.map(fn) : fn(m.material);
});

const lightCommand = (store, obj, before, after, label) => ({
  label,
  do: () => { setLightLook(obj, after); store.changed(); },
  undo: () => { setLightLook(obj, before); store.changed(); },
});

export function createAppearanceActions({ viewport, store, stack }) {
  let materialSession = null;
  let lightBefore = null;

  /** Clone material rồi sửa -> material cũ còn nguyên cho Undo. */
  function changeMaterials(obj, label, mutate) {
    const before = snapshotMaterials(obj);
    mapMaterials(obj, (mat) => { const c = mat.clone(); mutate(c); c.needsUpdate = true; return c; });
    stack.push(materialCommand(store, before, snapshotMaterials(obj), label));
    store.changed();
  }

  function applyTexture(obj, texture, label) {
    meshesOf(obj).forEach((m) => ensureUV(m.geometry)); // model AI không có UV
    changeMaterials(obj, label, (mat) => {
      mat.map = texture;
      mat.color?.set('#ffffff'); // màu trắng để vân hiện đúng màu
      mat.vertexColors = false;
    });
  }

  const self = {
    setPattern(obj, key) {
      if (!key) return changeMaterials(obj, 'Bỏ vân', (mat) => { mat.map = null; });
      applyTexture(obj, patternTexture(key), `Vân ${PATTERNS[key].label}`);
    },

    async setImageTexture(obj, file) {
      try {
        applyTexture(obj, await imageFileTexture(file), 'Ảnh làm vân');
      } catch {
        toast(`Không đọc được ảnh "${file.name}".`, { type: 'err' });
      }
    },

    // Thanh trượt vật liệu: xem trước khi kéo, thả tay = 1 bước Undo.
    beginMaterialEdit(obj) {
      materialSession = { before: snapshotMaterials(obj) };
      mapMaterials(obj, (mat) => mat.clone());
    },
    previewMaterial(obj, mutate) {
      if (!materialSession) self.beginMaterialEdit(obj);
      mapMaterials(obj, (mat) => { mutate(mat); mat.needsUpdate = true; return mat; });
    },
    commitMaterialEdit(obj, label) {
      if (!materialSession) return;
      stack.push(materialCommand(store, materialSession.before, snapshotMaterials(obj), label));
      materialSession = null;
      store.changed();
    },

    addLight(type) {
      const obj = createLightObject(type, store.nextName(LIGHT_TYPES[type].label));
      // Đặt chéo phía trước-trên cảnh, cách theo cỡ cảnh; đèn sau lệch sang bên -> không chồng lên đèn cũ.
      const box = new THREE.Box3();
      store.objects.forEach((o) => { if (o.visible && o.userData.kind !== 'light') box.expandByObject(o); });
      if (box.isEmpty()) box.set(new THREE.Vector3(-0.5, 0, -0.5), new THREE.Vector3(0.5, 1, 0.5));
      const size = Math.max(box.getSize(new THREE.Vector3()).length(), 0.5), center = box.getCenter(new THREE.Vector3());
      const existing = store.objects.filter((o) => o.userData.kind === 'light').length;
      obj.position.set(center.x + size * 0.5 * Math.sin(existing * 1.9), box.max.y + size * 0.35, center.z + size * 0.5 * Math.cos(existing * 1.9));
      stack.execute(addObjectCommand(store, obj));
      toast(`Đã thêm ${LIGHT_TYPES[type].label.toLowerCase()} — kéo mũi tên để đổi chỗ chiếu sáng.`, { type: 'ok' });
    },
    setLightColor(obj, color) {
      const before = getLightLook(obj);
      stack.execute(lightCommand(store, obj, before, { ...before, color }, 'Màu đèn'));
    },
    previewLightIntensity(obj, intensity) {
      lightBefore ??= getLightLook(obj);
      setLightLook(obj, { intensity });
    },
    commitLightIntensity(obj) {
      if (!lightBefore) return;
      stack.push(lightCommand(store, obj, lightBefore, getLightLook(obj), 'Độ sáng đèn'));
      lightBefore = null;
    },

    setLighting(key) {
      applyLighting(viewport, key);
      toast(`Ánh sáng: ${LIGHTING_PRESETS[key].label}`, { timeout: 1800 });
    },
    toggleGrid() {
      viewport.grid.visible = !viewport.grid.visible;
    },
  };
  return self;
}
