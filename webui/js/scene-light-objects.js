// Đèn do người dùng thêm vào cảnh: là 1 "vật thể" (bóng đèn nhỏ phát sáng) để chọn/kéo như vật khác.
import * as THREE from 'three';

export const LIGHT_TYPES = {
  point: { label: 'Đèn tròn', hint: 'Toả sáng mọi hướng, như bóng đèn' },
  spot: { label: 'Đèn rọi', hint: 'Chiếu xuống thành vùng sáng, có bóng đổ' },
};

export function createLightObject(type, name) {
  const color = 0xfff1c9;
  const group = new THREE.Group();
  group.name = name;
  group.userData.kind = 'light';

  const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.08, 24, 12), new THREE.MeshBasicMaterial({ color }));
  bulb.userData.bulb = true;
  const light = type === 'spot'
    ? new THREE.SpotLight(color, 40, 0, Math.PI / 6, 0.4, 2)
    : new THREE.PointLight(color, 15, 0, 2);
  if (type === 'spot') {
    light.castShadow = true;
    light.shadow.mapSize.set(1024, 1024);
    // Chuẩn glTF: đèn chiếu theo -Z -> target là con của đèn tại (0,0,-1), xoay đèn để -Z chĩa xuống.
    // Đặt kiểu khác thì lưu GLB xong mở lại đèn sẽ quay sai hướng.
    const target = new THREE.Object3D();
    target.position.set(0, 0, -1);
    light.add(target);
    light.target = target;
    light.rotation.x = -Math.PI / 2;
  }
  group.add(light, bulb);
  group.position.set(0, 2, 0);
  return group;
}

export const lightOf = (obj) => {
  let found = null;
  obj.traverse((o) => { if (!found && o.isLight) found = o; });
  return found;
};

/**
 * Sau clone()/mở file: SpotLight.target phải trỏ về object con của chính nó (không thì đèn quay sai hướng);
 * material bóng đèn phải riêng (clone() dùng chung -> đổi màu 1 đèn thì đèn kia đổi theo).
 */
export function fixLightCopy(obj) {
  obj.traverse((o) => {
    if (o.isSpotLight && o.children[0]) o.target = o.children[0];
    if (o.userData.bulb) o.material = o.material.clone();
  });
}

export const isLightObject = (obj) => obj?.userData.kind === 'light';

/** Đổi màu/độ sáng đèn (cập nhật cả màu bóng đèn). */
export function setLightLook(obj, { color, intensity }) {
  const light = lightOf(obj);
  if (!light) return;
  if (color !== undefined) {
    light.color.set(color);
    obj.traverse((o) => { if (o.userData.bulb) o.material.color.set(color); });
  }
  if (intensity !== undefined) light.intensity = intensity;
}

export function getLightLook(obj) {
  const light = lightOf(obj);
  return light ? { color: `#${light.color.getHexString()}`, intensity: light.intensity } : null;
}
