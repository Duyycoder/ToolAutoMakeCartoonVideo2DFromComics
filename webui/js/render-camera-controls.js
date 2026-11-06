// Khung "📷 Camera" trong hộp thoại Xuất ảnh: góc nhìn nhanh, xoay quanh / độ cao / khoảng cách / ống kính, "Vừa khung",
// ảnh xem trước ĐÚNG khung hình sẽ xuất (tỉ lệ theo kích thước đã chọn). Sửa thẳng camera khung nhìn
// (render thường + Cycles đều dùng camera này); restore() trả camera về như lúc mở hộp thoại (nút Huỷ).
import * as THREE from 'three';

// [khoá, nhãn, góc xoay quanh (độ, 0 = nhìn từ +Z = mặt trước), độ cao (độ)]
const VIEWS = [
  ['front', 'Trước', 0, 8], ['three-quarter', 'Chéo 3/4', 35, 20], ['left', 'Cạnh trái', 90, 8],
  ['right', 'Cạnh phải', -90, 8], ['back', 'Sau', 180, 8], ['top', 'Trên xuống', 0, 85],
];
const PREVIEW_W = 340;
const deg = THREE.MathUtils.radToDeg, rad = THREE.MathUtils.degToRad;
const lensMM = (fov) => Math.round(12 / Math.tan(rad(fov) / 2)); // tiêu cự tương đương máy ảnh full-frame

export function createRenderCameraPanel({ viewport, getAspect, frameTarget }) {
  const { camera, orbit } = viewport;
  const saved = { position: camera.position.clone(), target: orbit.target.clone(), fov: camera.fov };
  const el = document.createElement('div');
  el.className = 'render-camera';
  el.innerHTML = `
    <b>📷 Camera</b>
    <div class="cam-views"></div>
    <label>Xoay quanh <input type="range" data-k="az" min="-180" max="180" step="1"><span></span></label>
    <label>Độ cao <input type="range" data-k="el" min="-10" max="89" step="1"><span></span></label>
    <label>Khoảng cách <input type="range" data-k="dist" min="0.2" max="20" step="0.01"><span></span></label>
    <label>Ống kính <input type="range" data-k="fov" min="12" max="90" step="1"><span></span></label>
    <div class="cam-actions"><button type="button" data-cam="fit" title="Đưa vật đang chọn (hoặc cả cảnh) vừa khung hình">⌖ Vừa khung</button>
      <button type="button" data-cam="reset" title="Về góc nhìn lúc mở hộp thoại">⟲ Như lúc mở</button></div>
    <img class="cam-preview" alt="Xem trước khung hình">`;
  const input = (k) => el.querySelector(`[data-k="${k}"]`);
  const preview = el.querySelector('.cam-preview');

  const spherical = () => new THREE.Spherical().setFromVector3(camera.position.clone().sub(orbit.target));
  function place(azDeg, elDeg, dist) {
    const s = new THREE.Spherical(dist, rad(90 - elDeg), rad(azDeg));
    camera.position.copy(orbit.target).add(new THREE.Vector3().setFromSpherical(s));
    camera.lookAt(orbit.target);
  }

  let pending = false;
  function refresh() { // đồng bộ thanh trượt theo camera + vẽ lại xem trước (gộp nhiều lần gọi trong 1 frame)
    const s = spherical();
    const values = { az: deg(s.theta), el: 90 - deg(s.phi), dist: s.radius, fov: camera.fov };
    input('dist').max = Math.max(20, s.radius * 2);
    for (const [k, v] of Object.entries(values)) input(k).value = v;
    input('az').nextElementSibling.textContent = `${Math.round(values.az)}°`;
    input('el').nextElementSibling.textContent = `${Math.round(values.el)}°`;
    input('dist').nextElementSibling.textContent = `${values.dist.toFixed(2)} m`;
    input('fov').nextElementSibling.textContent = `${lensMM(values.fov)} mm`;
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => {
      pending = false;
      const aspect = getAspect();
      preview.src = viewport.renderImage({ width: PREVIEW_W, height: Math.round(PREVIEW_W / aspect), hideHelpers: true });
    });
  }

  el.querySelector('.cam-views').append(...VIEWS.map(([key, label, az, elev]) => {
    const b = Object.assign(document.createElement('button'), { type: 'button', textContent: label });
    b.dataset.view = key;
    b.onclick = () => { place(az, elev, spherical().radius); refresh(); };
    return b;
  }));
  el.querySelectorAll('input[type=range]').forEach((r) => {
    r.oninput = () => {
      if (r.dataset.k === 'fov') { camera.fov = Number(r.value); camera.updateProjectionMatrix(); }
      else place(Number(input('az').value), Number(input('el').value), Number(input('dist').value));
      refresh();
    };
  });
  el.querySelector('[data-cam="fit"]').onclick = () => { viewport.frameObjects(frameTarget()); camera.lookAt(orbit.target); refresh(); };
  el.querySelector('[data-cam="reset"]').onclick = () => { restore(); refresh(); };

  function restore() {
    camera.position.copy(saved.position);
    orbit.target.copy(saved.target);
    camera.fov = saved.fov;
    camera.updateProjectionMatrix();
    camera.lookAt(orbit.target);
  }

  return { el, refresh, restore };
}
