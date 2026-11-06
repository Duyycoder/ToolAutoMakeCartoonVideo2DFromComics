// Viewport 3D: renderer, camera, ánh sáng, sàn + lưới, OrbitControls, chọn vật bằng chuột.
// 1 đơn vị = 1 mét (chuẩn glTF). Lưới 10 m, mỗi ô 50 cm.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

export function createViewport(container) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true, alpha: true }); // alpha: xuất ảnh nền trong suốt
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  container.prepend(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1c1e24);
  // Ánh sáng môi trường: không có thì chất liệu kim loại/kính trông đen sì.
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

  const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 500);
  camera.position.set(3.5, 2.6, 4.5);
  const orbit = new OrbitControls(camera, renderer.domElement);
  orbit.target.set(0, 0.5, 0);
  orbit.enableDamping = true;
  orbit.maxPolarAngle = Math.PI * 0.495; // không cho camera chui xuống dưới sàn

  const hemi = new THREE.HemisphereLight(0xffffff, 0x3a3d4a, 0.6);
  scene.add(hemi);
  const sun = new THREE.DirectionalLight(0xffffff, 2.0);
  sun.position.set(5, 8, 4);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -8, right: 8, top: 8, bottom: -8, near: 0.5, far: 30 });
  sun.shadow.bias = -0.0005;
  scene.add(sun);

  const grid = new THREE.GridHelper(10, 20, 0x5b6275, 0x353946);
  grid.material.transparent = true;
  grid.material.opacity = 0.8;
  grid.userData.editorOnly = true; // ẩn khi xuất ảnh
  scene.add(grid);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(40, 40),
    new THREE.ShadowMaterial({ opacity: 0.28 }));
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);

  // Mọi vật thể của người dùng nằm trong group này -> export/raycast chỉ đụng tới đây.
  const objectsRoot = new THREE.Group();
  objectsRoot.name = 'Easy3D';
  objectsRoot.userData.easy3dProject = true;
  scene.add(objectsRoot);

  const resize = () => {
    const { clientWidth: w, clientHeight: h } = container;
    if (!w || !h) return;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  };
  new ResizeObserver(resize).observe(container);
  resize();

  renderer.setAnimationLoop(() => {
    orbit.update();
    renderer.render(scene, camera);
  });

  const raycaster = new THREE.Raycaster();

  /** Trả về vật thể cấp cao nhất (con trực tiếp của objectsRoot) dưới con trỏ, hoặc null. */
  function pick(clientX, clientY) {
    const rect = renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(((clientX - rect.left) / rect.width) * 2 - 1,
      -((clientY - rect.top) / rect.height) * 2 + 1);
    raycaster.setFromCamera(ndc, camera);
    const hits = raycaster.intersectObjects(objectsRoot.children, true)
      .filter((h) => isVisibleChain(h.object, objectsRoot));
    if (!hits.length) return null;
    let obj = hits[0].object;
    while (obj.parent && obj.parent !== objectsRoot) obj = obj.parent;
    return obj;
  }

  /** Đưa camera nhìn trọn 1 vật, nhiều vật (mảng) hoặc cả cảnh. */
  function frameObjects(target = objectsRoot) {
    const box = new THREE.Box3();
    (Array.isArray(target) ? target : [target]).forEach((o) => box.expandByObject(o));
    if (box.isEmpty()) box.set(new THREE.Vector3(-1, 0, -1), new THREE.Vector3(1, 1, 1));
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3()).length();
    const dist = Math.max(size, 0.5) / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2))) * 1.1;
    const dir = camera.position.clone().sub(orbit.target).normalize();
    orbit.target.copy(center);
    camera.position.copy(center).addScaledVector(dir, dist);
  }

  /** Render ảnh PNG ở độ phân giải tuỳ ý, ẩn lưới/gizmo, tuỳ chọn nền trong suốt. */
  function renderImage({ width, height, transparent = false, hideHelpers = true }) {
    const size = renderer.getSize(new THREE.Vector2());
    const ratio = renderer.getPixelRatio();
    const background = scene.background;
    const hidden = [];
    if (hideHelpers) {
      scene.traverse((o) => { if (o.userData.editorOnly && o.visible) { o.visible = false; hidden.push(o); } });
    }
    renderer.setPixelRatio(1);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    if (transparent) scene.background = null;
    try {
      renderer.render(scene, camera);
      return renderer.domElement.toDataURL('image/png');
    } finally {
      scene.background = background;
      hidden.forEach((o) => { o.visible = true; });
      renderer.setPixelRatio(ratio);
      renderer.setSize(size.x, size.y, false);
      camera.aspect = size.x / size.y;
      camera.updateProjectionMatrix();
    }
  }

  const canvasSize = () => renderer.getDrawingBufferSize(new THREE.Vector2());

  return { scene, camera, renderer, orbit, objectsRoot, grid, lights: { hemi, sun }, pick, frameObjects, renderImage, canvasSize };
}

function isVisibleChain(obj, stopAt) {
  for (let o = obj; o && o !== stopAt; o = o.parent) if (!o.visible) return false;
  return true;
}
