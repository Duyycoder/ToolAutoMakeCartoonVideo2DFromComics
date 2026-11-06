// Vân bề mặt vẽ bằng canvas (không cần file ảnh, chạy offline) + ảnh của người dùng làm texture.
import * as THREE from 'three';

const SIZE = 512;

/** PRNG có seed -> vân giống nhau mỗi lần tạo. */
function rng(seed) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

export const PATTERNS = {
  wood: {
    label: 'Gỗ', draw(g, s) {
      const r = rng(7);
      g.fillStyle = '#b5814f'; g.fillRect(0, 0, s, s);
      for (let y = 0; y < s; y += 3) {
        const wave = Math.sin(y * 0.045) * 10 + Math.sin(y * 0.013) * 22;
        g.fillStyle = `rgba(90,50,20,${0.08 + r() * 0.22})`;
        g.fillRect(0, y + wave * 0.05, s, 2 + r() * 2);
      }
    },
  },
  brick: {
    label: 'Gạch', draw(g, s) {
      const r = rng(3);
      g.fillStyle = '#d9d2c5'; g.fillRect(0, 0, s, s);
      const h = s / 8, w = s / 4;
      for (let row = 0; row < 8; row++) {
        for (let col = -1; col < 5; col++) {
          const x = col * w + (row % 2) * (w / 2);
          g.fillStyle = `hsl(${12 + r() * 10}, ${45 + r() * 15}%, ${38 + r() * 10}%)`;
          g.fillRect(x + 3, row * h + 3, w - 6, h - 6);
        }
      }
    },
  },
  checker: {
    label: 'Ca-rô', draw(g, s) {
      const n = 8, c = s / n;
      for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
        g.fillStyle = (i + j) % 2 ? '#2b2d33' : '#f1f1f1';
        g.fillRect(i * c, j * c, c, c);
      }
    },
  },
  stripes: {
    label: 'Sọc', draw(g, s) {
      for (let i = 0; i < 8; i++) {
        g.fillStyle = i % 2 ? '#f5f5f5' : '#e64c4c';
        g.fillRect(i * (s / 8), 0, s / 8, s);
      }
    },
  },
  marble: {
    label: 'Đá hoa', draw(g, s) {
      const r = rng(11);
      g.fillStyle = '#eeeeec'; g.fillRect(0, 0, s, s);
      g.strokeStyle = 'rgba(120,120,130,0.35)';
      for (let k = 0; k < 14; k++) {
        g.lineWidth = 0.5 + r() * 2.5;
        g.beginPath();
        let x = r() * s, y = 0;
        g.moveTo(x, y);
        while (y < s) { x += (r() - 0.5) * 40; y += 12 + r() * 20; g.lineTo(x, y); }
        g.stroke();
      }
    },
  },
  dots: {
    label: 'Chấm bi', draw(g, s) {
      g.fillStyle = '#ffd6e0'; g.fillRect(0, 0, s, s);
      g.fillStyle = '#ffffff';
      const step = s / 6;
      for (let i = 0; i < 6; i++) for (let j = 0; j < 6; j++) {
        g.beginPath();
        g.arc(i * step + step / 2 + (j % 2) * step / 2, j * step + step / 2, step * 0.22, 0, Math.PI * 2);
        g.fill();
      }
    },
  },
};

function configure(texture, repeat) {
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(repeat, repeat);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  return texture;
}

export function patternTexture(key, repeat = 2) {
  const canvas = Object.assign(document.createElement('canvas'), { width: SIZE, height: SIZE });
  PATTERNS[key].draw(canvas.getContext('2d'), SIZE);
  const texture = configure(new THREE.CanvasTexture(canvas), repeat);
  texture.userData.pattern = key;
  return texture;
}

/** Ảnh người dùng chọn -> texture (vẽ lại lên canvas để GLTFExporter xuất được). */
export async function imageFileTexture(file) {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, 2048 / Math.max(bitmap.width, bitmap.height));
  const canvas = Object.assign(document.createElement('canvas'),
    { width: Math.round(bitmap.width * scale), height: Math.round(bitmap.height * scale) });
  canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  const texture = configure(new THREE.CanvasTexture(canvas), 1);
  texture.userData.pattern = 'image';
  return texture;
}

/**
 * Model AI/nhập vào thường không có UV -> chiếu hình hộp: mỗi đỉnh lấy 2 trục vuông góc
 * với hướng pháp tuyến chính. Đủ để vân hiện ra hợp lý cho người mới.
 */
export function ensureUV(geometry) {
  if (geometry.attributes.uv) return;
  if (!geometry.attributes.normal) geometry.computeVertexNormals();
  geometry.computeBoundingBox();
  const { min } = geometry.boundingBox;
  const size = geometry.boundingBox.getSize(new THREE.Vector3());
  const span = Math.max(size.x, size.y, size.z) || 1;
  const pos = geometry.attributes.position, nor = geometry.attributes.normal;
  const uv = new Float32Array(pos.count * 2);
  for (let i = 0; i < pos.count; i++) {
    const nx = Math.abs(nor.getX(i)), ny = Math.abs(nor.getY(i)), nz = Math.abs(nor.getZ(i));
    const x = (pos.getX(i) - min.x) / span, y = (pos.getY(i) - min.y) / span, z = (pos.getZ(i) - min.z) / span;
    const [u, v] = nx >= ny && nx >= nz ? [z, y] : ny >= nz ? [x, z] : [x, y];
    uv[i * 2] = u; uv[i * 2 + 1] = v;
  }
  geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
}
