// Làm mờ mọi vật KHÁC vật đang chỉnh (Chỉnh điểm / Tô vẽ / Nặn hình) -> vật khác không che mất chỗ đang sửa.
import * as THREE from 'three';

export function createGhosting(store) {
  const ghost = new THREE.MeshBasicMaterial({ color: 0x8a90a0, transparent: true, opacity: 0.12, depthWrite: false });
  let saved = [];
  return {
    on(active) {
      this.off();
      for (const o of store.objects) {
        if (o === active) continue;
        o.traverse((m) => { if (m.isMesh) { saved.push([m, m.material]); m.material = ghost; } });
      }
    },
    off() {
      saved.forEach(([m, mat]) => { m.material = mat; });
      saved = [];
    },
  };
}
