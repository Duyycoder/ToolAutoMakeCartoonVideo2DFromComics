// File chọn kèm model (ảnh texture, .bin của .gltf, hoặc cả bộ trong .zip): loader tìm theo tên file trong các file
// này thay vì tải từ server. Ảnh model không nhắc tới (FBX chỉ có UV, ảnh giao riêng) -> tự gán theo tên file.
import * as THREE from 'three';
import { TGALoader } from 'three/addons/loaders/TGALoader.js';
import { unzipSync } from 'three/addons/libs/fflate.module.js';

const fileNameOf = (path) => path.split(/[\\/]/).pop();
const WHITE_PIXEL = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC';
const IMAGE_FILE = /\.(png|jpe?g|webp|tga)$/i;
// Hậu tố tên ảnh theo quy ước Substance/Unity/Blender -> ô vật liệu. Ảnh khác (Metallic, AO...) bỏ qua.
const SLOTS = [
  ['map', /base_?colou?r|albedo|diffuse|(^|[^a-z])col(or)?([^a-z]|$)/i],
  ['normalMap', /normal|(^|[^a-z])nrm([^a-z]|$)/i],
];
const normalize = (s) => s.toLowerCase().replace(/[^a-z0-9]/g, '');

/** .zip (vd. bộ FBX + ảnh Easy3D xuất trên web) -> các file bên trong, bỏ thư mục. */
export async function expandZips(files) {
  const out = [];
  for (const file of files) {
    if (!/\.zip$/i.test(file.name)) { out.push(file); continue; }
    const entries = unzipSync(new Uint8Array(await file.arrayBuffer()));
    for (const [path, data] of Object.entries(entries)) {
      if (!path.endsWith('/') && !path.startsWith('__MACOSX/')) out.push(new File([data], fileNameOf(path)));
    }
  }
  return out;
}

/**
 * `manager`: LoadingManager cho loader. Loader đòi file theo tên -> trả blob của file cùng tên (không phân biệt hoa thường);
 * tên không có thì ghi vào `missing` và trả ảnh trắng (ảnh hỏng làm vật đen, trắng thì vẫn hiện màu vật liệu).
 */
export function createCompanionLoader(companions) {
  const byName = new Map(companions.map((f) => [f.name.toLowerCase(), f]));
  const used = new Set();
  const missing = new Set();
  const urls = [];
  const manager = new THREE.LoadingManager(() => urls.splice(0).forEach((u) => URL.revokeObjectURL(u)));
  manager.setURLModifier((url) => {
    if (/^(blob|data):/.test(url)) return url; // ảnh nhúng sẵn trong file
    const name = decodeURIComponent(fileNameOf(url));
    const file = byName.get(name.toLowerCase());
    if (!file) { missing.add(name); return WHITE_PIXEL; }
    used.add(file);
    urls.push(URL.createObjectURL(file));
    return urls.at(-1);
  });
  manager.addHandler(/\.tga$/i, new TGALoader(manager)); // FBX từ Unity/3ds Max hay dùng ảnh TGA, trình duyệt không tự đọc được

  function loadTexture(file, slot) {
    const url = URL.createObjectURL(file);
    const loader = manager.getHandler(file.name) ?? new THREE.TextureLoader(manager);
    const texture = loader.load(url, () => URL.revokeObjectURL(url), undefined, () => URL.revokeObjectURL(url));
    texture.colorSpace = slot === 'map' ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    return texture;
  }

  /**
   * Gán ảnh chưa được dùng vào vật liệu còn trống ô tương ứng: 1 ảnh mỗi loại -> mọi vật liệu; nhiều ảnh -> ảnh có
   * chứa tên vật liệu. Chỉ 1 ảnh, tên không theo quy ước -> coi là ảnh màu. Trả về { assigned, unused } (tên file).
   */
  function assignUnreferenced(root) {
    const images = companions.filter((f) => IMAGE_FILE.test(f.name) && !used.has(f));
    const slotOf = (f) => SLOTS.find(([, re]) => re.test(f.name))?.[0] ?? (images.length === 1 ? 'map' : null);
    const materials = new Set();
    root.traverse((m) => { if (m.isMesh) [m.material].flat().forEach((x) => x && materials.add(x)); });
    const assigned = new Map(); // file -> texture (dùng chung cho các vật liệu)
    for (const [slot] of SLOTS) {
      const candidates = images.filter((f) => slotOf(f) === slot);
      for (const material of materials) {
        if (!candidates.length || material[slot]) continue;
        const file = candidates.length === 1 ? candidates[0]
          : candidates.find((f) => material.name && normalize(f.name).includes(normalize(material.name)));
        if (!file) continue;
        if (!assigned.has(file)) assigned.set(file, loadTexture(file, slot));
        material[slot] = assigned.get(file);
        if (slot === 'map') material.color.set(0xffffff); // màu đơn cũ chỉ là màu tạm khi chưa có ảnh, giữ lại sẽ nhuộm ảnh
        material.needsUpdate = true;
      }
    }
    return {
      assigned: [...assigned.keys()].map((f) => f.name),
      unused: images.filter((f) => !assigned.has(f)).map((f) => f.name),
    };
  }

  return { manager, missing, assignUnreferenced };
}
