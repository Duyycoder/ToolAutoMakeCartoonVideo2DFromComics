// Preset ánh sáng + nền cho cả cảnh. Lưu tên preset trong project để mở lại đúng không khí.
export const LIGHTING_PRESETS = {
  studio: { label: 'Studio', bg: 0x1c1e24, hemi: [0xffffff, 0x3a3d4a, 0.6], sun: [0xffffff, 2.0, [5, 8, 4]], env: 1, exposure: 1 },
  outdoor: { label: 'Ngoài trời', bg: 0x9cc9f5, hemi: [0xd8ecff, 0x6b8f4e, 1.0], sun: [0xfff2d6, 3.0, [6, 10, 3]], env: 0.8, exposure: 1 },
  sunset: { label: 'Hoàng hôn', bg: 0x3a2440, hemi: [0xffb36b, 0x2a1a3a, 0.55], sun: [0xff8a3d, 2.8, [-8, 2.5, 4]], env: 0.45, exposure: 1.05 },
  night: { label: 'Ban đêm', bg: 0x070b18, hemi: [0x4a5d9a, 0x0a0a14, 0.25], sun: [0x9fb4ff, 0.6, [3, 8, -4]], env: 0.15, exposure: 0.9 },
  stage: { label: 'Sân khấu', bg: 0x000000, hemi: [0xffffff, 0x000000, 0.05], sun: [0xffffff, 3.5, [0, 10, 2]], env: 0.1, exposure: 1 },
};

export function applyLighting(viewport, key) {
  const p = LIGHTING_PRESETS[key];
  if (!p) return;
  const { scene, renderer, lights, objectsRoot } = viewport;
  scene.background.set(p.bg);
  lights.hemi.color.set(p.hemi[0]);
  lights.hemi.groundColor.set(p.hemi[1]);
  lights.hemi.intensity = p.hemi[2];
  lights.sun.color.set(p.sun[0]);
  lights.sun.intensity = p.sun[1];
  lights.sun.position.set(...p.sun[2]);
  scene.environmentIntensity = p.env;
  renderer.toneMappingExposure = p.exposure;
  objectsRoot.userData.lighting = key; // lưu cùng project (GLTF extras)
}
