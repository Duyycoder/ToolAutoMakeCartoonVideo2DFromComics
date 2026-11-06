// Ánh sáng cả cảnh: preset = bộ thông số khởi đầu, người dùng chỉnh tiếp từng thông số (lighting-adjust-panel.js).
// Lưu trong project (GLTF extras của objectsRoot): lighting = tên preset, lightSettings = thông số đang dùng.
// Nắng (DirectionalLight) đặt theo HƯỚNG (xoay quanh + độ cao) quanh tâm cảnh; vùng bóng đổ ôm vừa cảnh
// -> vật to/ở xa gốc không bị mất bóng, vật nhỏ có bóng nét.
import * as THREE from 'three';

export const LIGHTING_PRESETS = {
  studio: { label: 'Studio', bg: 0x1c1e24, hemi: [0xffffff, 0x3a3d4a, 0.6], sun: [0xffffff, 2.0, [5, 8, 4]], env: 1, exposure: 1 },
  outdoor: { label: 'Ngoài trời', bg: 0x9cc9f5, hemi: [0xd8ecff, 0x6b8f4e, 1.0], sun: [0xfff2d6, 3.0, [6, 10, 3]], env: 0.8, exposure: 1 },
  sunset: { label: 'Hoàng hôn', bg: 0x3a2440, hemi: [0xffb36b, 0x2a1a3a, 0.55], sun: [0xff8a3d, 2.8, [-8, 2.5, 4]], env: 0.45, exposure: 1.05 },
  night: { label: 'Ban đêm', bg: 0x070b18, hemi: [0x4a5d9a, 0x0a0a14, 0.25], sun: [0x9fb4ff, 0.6, [3, 8, -4]], env: 0.15, exposure: 0.9 },
  stage: { label: 'Sân khấu', bg: 0x000000, hemi: [0xffffff, 0x000000, 0.05], sun: [0xffffff, 3.5, [0, 10, 2]], env: 0.1, exposure: 1 },
};

const hex = (n) => `#${new THREE.Color(n).getHexString()}`;

/** Thông số của 1 preset: { sunAz, sunEl (độ), sunIntensity, sunColor, sky, ground, ambient, env, exposure, background, shadows }. */
export function presetSettings(key) {
  const p = LIGHTING_PRESETS[key];
  const [x, y, z] = p.sun[2];
  return {
    sunAz: Math.round(THREE.MathUtils.radToDeg(Math.atan2(x, z))),
    sunEl: Math.round(THREE.MathUtils.radToDeg(Math.asin(y / Math.hypot(x, y, z)))),
    sunIntensity: p.sun[1], sunColor: hex(p.sun[0]), sky: hex(p.hemi[0]), ground: hex(p.hemi[1]), ambient: p.hemi[2],
    env: p.env, exposure: p.exposure, background: hex(p.bg), shadows: true,
  };
}

/** Hộp bao các vật đang hiện (bỏ đèn) — để đặt nắng và vùng bóng đổ. */
function sceneBox(objectsRoot) {
  const box = new THREE.Box3();
  for (const o of objectsRoot.children) {
    if (o.visible && o.userData.kind !== 'light') box.expandByObject(o);
  }
  return box.isEmpty() ? box.set(new THREE.Vector3(-1, 0, -1), new THREE.Vector3(1, 1, 1)) : box;
}

/** Đặt nắng theo hướng quanh tâm cảnh + vùng bóng đổ vừa cảnh. Gọi lại khi cảnh đổi. */
export function fitSunToScene(viewport) {
  const { lights: { sun }, objectsRoot } = viewport;
  const s = objectsRoot.userData.lightSettings ?? presetSettings('studio');
  const sphere = sceneBox(objectsRoot).getBoundingSphere(new THREE.Sphere());
  const r = Math.max(sphere.radius, 0.5);
  const dir = new THREE.Vector3().setFromSphericalCoords(1, THREE.MathUtils.degToRad(90 - s.sunEl), THREE.MathUtils.degToRad(s.sunAz));
  sun.target.position.copy(sphere.center);
  sun.position.copy(sphere.center).addScaledVector(dir, r * 3);
  Object.assign(sun.shadow.camera, { left: -r * 1.3, right: r * 1.3, top: r * 1.3, bottom: -r * 1.3, near: r * 0.5, far: r * 6 });
  sun.shadow.camera.updateProjectionMatrix();
  sun.target.updateMatrixWorld();
}

/** Áp toàn bộ thông số; `presetKey` (nếu có) = tên preset vừa chọn. */
export function applyLightSettings(viewport, settings, presetKey = null) {
  const { scene, renderer, lights: { hemi, sun }, objectsRoot } = viewport;
  scene.background.set(settings.background);
  hemi.color.set(settings.sky);
  hemi.groundColor.set(settings.ground);
  hemi.intensity = settings.ambient;
  sun.color.set(settings.sunColor);
  sun.intensity = settings.sunIntensity;
  sun.castShadow = settings.shadows;
  scene.environmentIntensity = settings.env;
  renderer.toneMappingExposure = settings.exposure;
  objectsRoot.userData.lightSettings = { ...settings };
  if (presetKey) objectsRoot.userData.lighting = presetKey;
  fitSunToScene(viewport);
}

export function applyLighting(viewport, key) {
  if (LIGHTING_PRESETS[key]) applyLightSettings(viewport, presetSettings(key), key);
}

/** Mở project: preset đã lưu, rồi thông số đã chỉnh tay (project cũ chỉ có preset). */
export function restoreLighting(viewport, key, settings) {
  const preset = LIGHTING_PRESETS[key] ? key : 'studio';
  applyLightSettings(viewport, { ...presetSettings(preset), ...(settings ?? {}) }, preset);
}
