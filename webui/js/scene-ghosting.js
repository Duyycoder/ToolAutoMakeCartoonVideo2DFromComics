// Làm mờ mọi vật KHÁC vật đang chỉnh (Chỉnh điểm / Tô vẽ / Nặn hình) -> vật khác không che mất chỗ đang sửa.
import * as THREE from 'three';

export function createGhosting(store) {
  const ghost = new THREE.MeshBasicMaterial({ color: 0x8a90a0, transparent: true, opacity: 0.12, depthWrite: false });
  let saved = [];
  return {
    /** `active` có thể là phần con (chọn trong cây) -> chỉ giữ nó và các phần bên trong; thân vật chứa nó cũng mờ. */
    on(active) {
      this.off();
      const keep = new Set();
      active?.traverse((m) => keep.add(m));
      store.root.traverse((m) => {
        if (m.isMesh && !keep.has(m)) { saved.push([m, m.material]); m.material = ghost; }
      });
    },
    off() {
      saved.forEach(([m, mat]) => { m.material = mat; });
      saved = [];
    },
  };
}
