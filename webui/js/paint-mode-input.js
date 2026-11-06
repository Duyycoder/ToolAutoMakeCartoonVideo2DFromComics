// Chuột + phím khi "Tô vẽ": kéo trên vật = tô; bắt đầu kéo ngoài vật = xoay góc nhìn như thường.
// Vòng tròn trên bề mặt cho thấy cỡ cọ.
import * as THREE from 'three';
import { colorAtFace } from './paint-brush-engine.js';

export function attachPaintModeInput(viewport, paintMode, viewportEl, { onPickColor }) {
  const raycaster = new THREE.Raycaster();
  raycaster.firstHitOnly = true; // three-mesh-bvh: chỉ cần điểm chạm đầu tiên
  const cursor = new THREE.Mesh(new THREE.RingGeometry(0.92, 1, 48),
    new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.85, depthTest: false, side: THREE.DoubleSide }));
  cursor.userData.editorOnly = true;
  cursor.renderOrder = 999;
  cursor.visible = false;
  viewport.scene.add(cursor);
  let stroke = null; // { last: Vector3 local }

  function hitAt(e) {
    const r = viewport.renderer.domElement.getBoundingClientRect();
    raycaster.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1,
      -((e.clientY - r.top) / r.height) * 2 + 1), viewport.camera);
    return raycaster.intersectObject(paintMode.state.mesh, false)[0] ?? null;
  }

  function updateCursor(hit) {
    cursor.visible = !!hit;
    if (!hit) return;
    const mesh = paintMode.state.mesh;
    const n = hit.face.normal.clone().transformDirection(mesh.matrixWorld);
    cursor.position.copy(hit.point).addScaledVector(n, 0.002);
    cursor.lookAt(hit.point.clone().add(n));
    cursor.scale.setScalar(paintMode.brushRadius() * Math.abs(mesh.getWorldScale(new THREE.Vector3()).x));
  }

  /** Tô từ điểm trước tới điểm hiện tại theo từng bước nhỏ -> kéo nhanh nét vẫn liền. */
  function paintTo(local) {
    const step = paintMode.brushRadius() * 0.3;
    const from = stroke.last ?? local;
    const n = Math.max(1, Math.ceil(from.distanceTo(local) / step));
    for (let i = 1; i <= n; i++) paintMode.paintAt(from.clone().lerp(local, i / n));
    stroke.last = local;
  }

  // Capture trên khung chứa: chạy TRƯỚC OrbitControls -> quyết định tô hay xoay camera.
  viewportEl.addEventListener('pointerdown', (e) => {
    if (!paintMode.active || e.button !== 0 || e.target !== viewport.renderer.domElement) return;
    const hit = hitAt(e);
    viewport.orbit.enabled = !hit;
    if (!hit) return;
    const local = paintMode.state.mesh.worldToLocal(hit.point.clone());
    if (paintMode.state.brush.mode === 'pick') {
      onPickColor(colorAtFace(paintMode.state.geo, hit.face, local));
      return;
    }
    paintMode.snapshot();
    stroke = { last: null };
    paintTo(local);
  }, true);

  window.addEventListener('pointermove', (e) => {
    if (!paintMode.active) { cursor.visible = false; return; }
    if (e.target !== viewport.renderer.domElement && !stroke) { cursor.visible = false; return; }
    const hit = hitAt(e);
    updateCursor(hit);
    if (stroke && hit) paintTo(paintMode.state.mesh.worldToLocal(hit.point.clone()));
  });
  window.addEventListener('pointerup', () => {
    stroke = null;
    viewport.orbit.enabled = true;
  });

  document.addEventListener('keydown', (e) => {
    if (!paintMode.active || e.target.closest?.('input, textarea')) return;
    const ctrl = e.ctrlKey || e.metaKey;
    const key = e.key.toLowerCase();
    const size = paintMode.state.brush.size;
    const map = {
      escape: () => paintMode.exit(), enter: () => paintMode.exit(),
      z: ctrl && (() => (e.shiftKey ? paintMode.redo() : paintMode.undo())), y: ctrl && (() => paintMode.redo()),
      '[': () => paintMode.setBrush({ size: Math.max(0, size - 0.05) }),
      ']': () => paintMode.setBrush({ size: Math.min(1, size + 0.05) }),
    };
    // Chặn phím tắt của app (Delete, W/E/R, Tab...) khi đang tô, trừ khi đã xử lý ở trên.
    if (map[key]) { e.preventDefault(); e.stopPropagation(); map[key](); return; }
    if (!ctrl) e.stopPropagation();
  }, true);

  return { hideCursor() { cursor.visible = false; } };
}
