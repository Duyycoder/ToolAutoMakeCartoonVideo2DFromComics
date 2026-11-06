// Lớp hiển thị khi chỉnh điểm: khung lưới, chấm điểm (đen = chưa chọn, cam = đã chọn), mặt đã chọn tô cam.
import * as THREE from 'three';

const UNSELECTED = new THREE.Color(0x15171c);
const SELECTED = new THREE.Color(0xff9f43);

export function createEditOverlays(scene) {
  const group = new THREE.Group();
  group.userData.editorOnly = true;
  group.matrixAutoUpdate = false; // đi theo ma trận của vật đang chỉnh
  scene.add(group);

  // Lưới + chấm vẽ đè lên trên (depthTest bật để không thấy điểm mặt sau), đậm cho dễ nhìn.
  const wireMat = new THREE.MeshBasicMaterial({ color: 0x0b0d12, wireframe: true, transparent: true, opacity: 0.75 });
  const pointMat = new THREE.PointsMaterial({ size: 9, sizeAttenuation: false, vertexColors: true });
  const faceMat = new THREE.MeshBasicMaterial({
    color: SELECTED, transparent: true, opacity: 0.45, side: THREE.DoubleSide, depthWrite: false,
    polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,
  });
  let wire = null, points = null, faces = null;

  function clear() {
    for (const o of [wire, points, faces]) if (o) { group.remove(o); if (o !== wire) o.geometry.dispose(); }
    wire = points = faces = null;
  }

  return {
    /** Gọi lại mỗi khi đổi geometry (đổi số đỉnh/mặt). */
    rebuild(mesh, geo) {
      clear();
      mesh.updateWorldMatrix(true, false);
      group.matrix.copy(mesh.matrixWorld);
      group.matrixWorldNeedsUpdate = true;
      wire = new THREE.Mesh(geo, wireMat);
      const pg = new THREE.BufferGeometry();
      pg.setAttribute('position', geo.attributes.position); // dùng chung -> kéo điểm là chấm đi theo
      pg.setAttribute('color', new THREE.Float32BufferAttribute(new Float32Array(geo.attributes.position.count * 3), 3));
      points = new THREE.Points(pg, pointMat);
      const fg = new THREE.BufferGeometry();
      fg.setAttribute('position', geo.attributes.position);
      fg.setIndex([]);
      faces = new THREE.Mesh(fg, faceMat);
      for (const o of [wire, points, faces]) { o.frustumCulled = false; group.add(o); }
    },

    /** Tô màu theo vùng chọn. mode 'vertex' hiện chấm, 'face' tô mặt. */
    showSelection(geo, selV, selF, mode) {
      if (!points) return;
      points.visible = mode === 'vertex';
      const colors = points.geometry.attributes.color;
      for (let i = 0; i < colors.count; i++) {
        const c = selV[i] ? SELECTED : UNSELECTED;
        colors.setXYZ(i, c.r, c.g, c.b);
      }
      colors.needsUpdate = true;
      const idx = geo.index.array, sel = [];
      for (let f = 0; f < selF.length; f++) if (selF[f]) sel.push(idx[f * 3], idx[f * 3 + 1], idx[f * 3 + 2]);
      faces.geometry.setIndex(sel);
    },

    /** Thoát chế độ: chỉ gỡ lớp hiển thị, GIỮ group trong cảnh để lần sau vào lại vẫn thấy. */
    hide() {
      clear();
    },
  };
}
