// Chuột + phím dùng chung cho "Tô vẽ" và "Nặn hình": kéo trên vật = cọ; bắt đầu kéo ngoài vật = xoay
// góc nhìn như thường. Vòng tròn trên bề mặt cho thấy cỡ cọ.
//
// `mode` khai báo: active, mesh, radius() (local), start(hit, e) -> 'dab' | 'drag' | null,
// dab(localPoint, e), drag(ray, e), flush() (sau mỗi lần di chuột), end(), keyMap(e) -> { phím: hàm }.
import * as THREE from 'three';

export function attachSurfaceInput(viewport, viewportEl, mode) {
  const raycaster = new THREE.Raycaster();
  raycaster.firstHitOnly = true; // three-mesh-bvh: chỉ cần điểm chạm đầu tiên
  const cursor = new THREE.Mesh(new THREE.RingGeometry(0.92, 1, 48),
    new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.85, depthTest: false, side: THREE.DoubleSide }));
  cursor.userData.editorOnly = true;
  cursor.renderOrder = 999;
  cursor.visible = false;
  viewport.scene.add(cursor);
  let stroke = null; // { kind, last: Vector3 local }

  function hitAt(e) {
    const r = viewport.renderer.domElement.getBoundingClientRect();
    raycaster.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1,
      -((e.clientY - r.top) / r.height) * 2 + 1), viewport.camera);
    return raycaster.intersectObject(mode.mesh, false)[0] ?? null;
  }

  function updateCursor(hit) {
    cursor.visible = !!hit;
    if (!hit) return;
    const n = hit.face.normal.clone().transformDirection(mode.mesh.matrixWorld);
    cursor.position.copy(hit.point).addScaledVector(n, 0.002);
    cursor.lookAt(hit.point.clone().add(n));
    cursor.scale.setScalar(mode.radius() * Math.abs(mode.mesh.getWorldScale(new THREE.Vector3()).x));
  }

  /** Chấm cọ dọc đường đi theo bước nhỏ -> kéo nhanh nét vẫn liền. */
  function dabTo(local, e) {
    const step = mode.radius() * 0.3;
    const from = stroke.last ?? local;
    const n = Math.max(1, Math.ceil(from.distanceTo(local) / step));
    for (let i = 1; i <= n; i++) mode.dab(from.clone().lerp(local, i / n), e);
    stroke.last = local;
  }

  const toLocal = (hit) => mode.mesh.worldToLocal(hit.point.clone());

  // Capture trên khung chứa: chạy TRƯỚC OrbitControls -> quyết định dùng cọ hay xoay camera.
  viewportEl.addEventListener('pointerdown', (e) => {
    if (!mode.active || e.button !== 0 || e.target !== viewport.renderer.domElement) return;
    const hit = hitAt(e);
    viewport.orbit.enabled = !hit;
    if (!hit) return;
    const kind = mode.start(hit, e);
    if (!kind) return;
    stroke = { kind, last: null };
    if (kind === 'dab') dabTo(toLocal(hit), e);
    mode.flush?.();
  }, true);

  window.addEventListener('pointermove', (e) => {
    if (!mode.active) { cursor.visible = false; return; }
    if (e.target !== viewport.renderer.domElement && !stroke) { cursor.visible = false; return; }
    const hit = hitAt(e);
    updateCursor(hit);
    if (!stroke) return;
    if (stroke.kind === 'drag') mode.drag(raycaster.ray, e);
    else if (hit) dabTo(toLocal(hit), e);
    mode.flush?.();
  });
  window.addEventListener('pointerup', () => {
    if (stroke) mode.end?.();
    stroke = null;
    viewport.orbit.enabled = true;
  });

  document.addEventListener('keydown', (e) => {
    if (!mode.active || e.target.closest?.('input, textarea')) return;
    const fn = mode.keyMap(e)[e.key.toLowerCase()];
    // Chặn phím tắt của app (Delete, W/E/R, Tab...) khi đang dùng cọ, trừ tổ hợp Ctrl (lưu, mở...).
    if (fn) { e.preventDefault(); e.stopPropagation(); fn(); return; }
    if (!(e.ctrlKey || e.metaKey)) e.stopPropagation();
  }, true);
}

/** Phím chung: Esc/Enter = Xong, Ctrl+Z/Y = hoàn tác/làm lại, [ ] = cỡ cọ. */
export function brushKeys(e, m) {
  const ctrl = e.ctrlKey || e.metaKey;
  const size = m.state.brush.size;
  return {
    escape: () => m.exit(), enter: () => m.exit(),
    z: ctrl && (() => (e.shiftKey ? m.redo() : m.undo())), y: ctrl && (() => m.redo()),
    '[': () => m.setBrush({ size: Math.max(0, size - 0.05) }),
    ']': () => m.setBrush({ size: Math.min(1, size + 0.05) }),
  };
}
