// Hiển thị khớp (chấm tròn) + xương (đường nối) luôn nổi trên hình; bấm vào chấm để chọn khớp.
import * as THREE from 'three';

const NORMAL = new THREE.Color(0x5b8cff), SELECTED = new THREE.Color(0xff9f43);

export function createRigHelpers(scene) {
  const group = new THREE.Group();
  group.userData.editorOnly = true;
  group.matrixAutoUpdate = false;
  scene.add(group);
  const lineMat = new THREE.LineBasicMaterial({ color: 0xdfe6ff, depthTest: false, transparent: true, opacity: 0.9 });
  let spheres = [], parents = [], lines = null, selected = -1;

  function clear() {
    spheres.forEach((s) => { s.geometry.dispose(); s.material.dispose(); group.remove(s); });
    if (lines) { lines.geometry.dispose(); group.remove(lines); }
    spheres = []; lines = null; selected = -1;
  }

  const api = {
    /** points: toạ độ trong `matrix` (null = thế giới); parentIdx[i] = chỉ số khớp cha hoặc -1. */
    show(points, parentIdx, matrix, radius) {
      clear();
      parents = parentIdx;
      group.matrix.copy(matrix ?? new THREE.Matrix4());
      group.matrixWorldNeedsUpdate = true;
      const geo = new THREE.SphereGeometry(radius, 16, 8);
      spheres = points.map((p, i) => {
        const s = new THREE.Mesh(geo.clone(), new THREE.MeshBasicMaterial({ color: NORMAL, depthTest: false, transparent: true }));
        s.renderOrder = 1001;
        s.position.copy(p);
        s.userData.jointIndex = i;
        group.add(s);
        return s;
      });
      const lg = new THREE.BufferGeometry();
      lg.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(points.length * 6), 3));
      lines = new THREE.LineSegments(lg, lineMat);
      lines.renderOrder = 1000;
      lines.frustumCulled = false;
      group.add(lines);
      api.update(points);
    },
    update(points) {
      points.forEach((p, i) => spheres[i]?.position.copy(p));
      const attr = lines.geometry.attributes.position;
      points.forEach((p, i) => {
        const q = parents[i] >= 0 ? points[parents[i]] : p; // khớp gốc: đoạn rỗng
        attr.setXYZ(i * 2, q.x, q.y, q.z);
        attr.setXYZ(i * 2 + 1, p.x, p.y, p.z);
      });
      attr.needsUpdate = true;
    },
    setSelected(i, selection = null) {
      selected = i;
      spheres.forEach((s, k) => s.material.color.copy(k === i || selection?.has(k) ? SELECTED : NORMAL));
    },
    get selected() { return selected; },
    handle: (i) => spheres[i],
    pick(raycaster) {
      group.updateMatrixWorld(true); // vừa show() xong có thể chưa render
      const hit = raycaster.intersectObjects(spheres, false)[0];
      return hit ? hit.object.userData.jointIndex : -1;
    },
    hide: clear,
  };
  return api;
}
