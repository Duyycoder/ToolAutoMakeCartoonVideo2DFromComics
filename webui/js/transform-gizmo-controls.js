// Gizmo di chuyển/xoay/co giãn gắn vào vật đang chọn. Mỗi lần kéo xong = 1 bước Undo.
import * as THREE from 'three';
import { TransformControls } from 'three/addons/controls/TransformControls.js';
import { sameTransform, snapshotTransform, transformCommand } from './scene-edit-commands.js';

const MODE_LABELS = { translate: 'Di chuyển', rotate: 'Xoay', scale: 'Co giãn' };

export function createGizmo(viewport, store, stack) {
  const gizmo = new TransformControls(viewport.camera, viewport.renderer.domElement);
  // Bật bắt dính mặc định: người mới dễ đặt vật thẳng hàng.
  gizmo.setTranslationSnap(0.05);
  gizmo.setRotationSnap(THREE.MathUtils.degToRad(15));
  gizmo.setScaleSnap(0.05);
  const helper = gizmo.getHelper();
  helper.userData.editorOnly = true; // ẩn khi xuất ảnh
  viewport.scene.add(helper);

  let before = null;
  let pointerOnGizmo = false; // để click vào tay cầm không bị hiểu là "bỏ chọn"

  gizmo.addEventListener('mouseDown', () => { pointerOnGizmo = true; });
  gizmo.addEventListener('dragging-changed', (e) => {
    viewport.orbit.enabled = !e.value;
    const obj = gizmo.object;
    if (!obj) return;
    if (e.value) {
      before = snapshotTransform(obj);
      return;
    }
    const after = snapshotTransform(obj);
    if (before && !sameTransform(before, after)) {
      stack.push(transformCommand(store, obj, before, after, MODE_LABELS[gizmo.mode]));
    }
    before = null;
  });
  gizmo.addEventListener('objectChange', () => store.transformed());

  const sync = () => {
    const obj = store.selected;
    if (obj && obj.visible && obj.parent) gizmo.attach(obj);
    else gizmo.detach();
  };
  store.addEventListener('selection', sync);
  store.addEventListener('changed', sync);

  return {
    setMode(mode) { gizmo.setMode(mode); },
    get mode() { return gizmo.mode; },
    /** true nếu lần nhấn chuột vừa rồi rơi vào tay cầm gizmo (rồi reset cờ). */
    consumePointer() {
      const was = pointerOnGizmo || gizmo.dragging;
      pointerOnGizmo = false;
      return was;
    },
  };
}
