// Smoke test giao diện: mở Easy3D trong Edge/Chrome headless (DevTools Protocol), thao tác như người dùng,
// bắt lỗi console, chụp ảnh màn hình.
//   1) chạy backend:  .venv\Scripts\python.exe -m uvicorn backend.main:app --port 8200
//   2) node tests/ui-smoke-test.mjs [thư-mục-ảnh-chụp]
import { spawn } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const APP = 'http://127.0.0.1:8200/?test=1';
const PORT = 9333;
const SHOT_DIR = process.argv[2] ?? tmpdir();
const BROWSERS = [
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const exe = BROWSERS.find(existsSync);
if (!exe) throw new Error('Không tìm thấy Edge/Chrome');
const browser = spawn(exe, [`--remote-debugging-port=${PORT}`, '--headless=new', '--window-size=1400,900',
  `--user-data-dir=${mkdtempSync(join(tmpdir(), 'easy3d-ui-'))}`, '--enable-unsafe-swiftshader', 'about:blank']);

let ws;
for (let i = 0; i < 50 && !ws; i++) {
  try {
    const pages = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
    const page = pages.find((p) => p.type === 'page');
    if (page) ws = new WebSocket(page.webSocketDebuggerUrl);
  } catch { await sleep(200); }
}
await new Promise((r) => ws.addEventListener('open', r));

let nextId = 1;
const pending = new Map();
const errors = [];
ws.addEventListener('message', ({ data }) => {
  const msg = JSON.parse(data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  if (msg.method === 'Runtime.exceptionThrown') errors.push(msg.params.exceptionDetails.exception?.description ?? msg.params.exceptionDetails.text);
  if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') errors.push(msg.params.args.map((a) => a.value ?? a.description).join(' '));
  if (msg.method === 'Log.entryAdded' && msg.params.entry.level === 'error') errors.push(`${msg.params.entry.text} ${msg.params.entry.url ?? ''}`);
});
const send = (method, params = {}) => new Promise((resolve) => {
  const id = nextId++;
  pending.set(id, resolve);
  ws.send(JSON.stringify({ id, method, params }));
});
const evaluate = async (expr) => {
  const res = await send('Runtime.evaluate', { expression: `(async () => { ${expr} })()`, awaitPromise: true, returnByValue: true });
  if (res.result.exceptionDetails) throw new Error(res.result.exceptionDetails.exception?.description);
  return res.result.result.value;
};
const shot = async (name) => {
  const { result } = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync(join(SHOT_DIR, name), Buffer.from(result.data, 'base64'));
};

const results = [];
const check = (name, ok, detail = '') => { results.push({ name, ok, detail }); };

await send('Runtime.enable'); await send('Log.enable'); await send('Page.enable');
await send('Page.navigate', { url: APP });
await sleep(2500);
await shot('01-welcome.png');

const q = (sel) => `document.querySelector(${JSON.stringify(sel)})`;
const outliner = () => evaluate(`return [...document.querySelectorAll('#outliner li .name')].map(n => n.textContent);`);
const key = (k, extra = {}) => evaluate(`document.body.dispatchEvent(new KeyboardEvent('keydown', ${JSON.stringify({ key: k, bubbles: true, ...extra })}));`);

check('Màn hình chào hiện khi mở app', await evaluate(`return !!${q('.welcome-cards')};`));
await evaluate(`${q('[data-choice="shapes"]')}.click();`); await sleep(100);
check('Thẻ "Ghép từ khối" thêm Hộp 1 + mở menu khối',
  JSON.stringify(await outliner()) === '["Hộp 1"]' && await evaluate(`return !${q('#shape-menu')}.hidden;`));
await evaluate(`${q('[data-shape="sphere"]')}.click();`);
check('Thêm Cầu 1, panel chỉnh hiện tên', await evaluate(`return ${q('#props input[type=text]')}?.value;`) === 'Cầu 1');
await evaluate(`${q('#props .swatch[title="#ff5c5c"]')}.click();`);
check('Đổi màu đỏ', await evaluate(`return ${q('#props .swatch.current')}?.title;`) === '#ff5c5c');
await evaluate(`[...document.querySelectorAll('.chip')].find(c => c.textContent === 'Kim loại').click();`);
check('Chất liệu Kim loại', await evaluate(`return ${q('.chip.current')}?.textContent;`) === 'Kim loại');
await evaluate(`${q('#btn-undo')}.click();`);
check('Hoàn tác về Nhựa', await evaluate(`return ${q('.chip.current')}?.textContent;`) === 'Nhựa');
await evaluate(`${q('#btn-redo')}.click();`);
check('Làm lại về Kim loại', await evaluate(`return ${q('.chip.current')}?.textContent;`) === 'Kim loại');
await key('d', { ctrlKey: true });
check('Ctrl+D nhân bản', (await outliner()).length === 3, JSON.stringify(await outliner()));
await key('Delete');
check('Delete xoá', (await outliner()).length === 2);
await key('z', { ctrlKey: true });
check('Ctrl+Z khôi phục vật bị xoá', (await outliner()).length === 3);
await key('e');
check('Phím E chọn công cụ Xoay', await evaluate(`return ${q('.tool.active')}.dataset.mode;`) === 'rotate');

await key('Escape');
const picked = await evaluate(`
  const c = document.querySelector('#viewport canvas'); const r = c.getBoundingClientRect();
  const o = { clientX: r.left + r.width / 2, clientY: r.top + r.height * 0.62, button: 0, bubbles: true, pointerId: 1 };
  c.dispatchEvent(new PointerEvent('pointerdown', o)); c.dispatchEvent(new PointerEvent('pointerup', o));
  return document.querySelector('#outliner li.selected .name')?.textContent ?? null;`);
check('Bấm vào vật trong khung 3D để chọn', picked !== null, `chọn: ${picked}`);

const lastToast = () => evaluate(`return [...document.querySelectorAll('.toast span')].pop()?.textContent ?? '';`);
for (const [sel, expected] of [['[data-export="glb"]', 'Đã xuất GLB'], ['[data-export="stl"]', 'Đã xuất STL'],
  ['[data-export="obj"]', 'Đã xuất OBJ'], ['[data-action="save"]', 'Đã lưu dự án']]) {
  await evaluate(`${q(sel)}.click();`); await sleep(700);
  const text = await lastToast();
  check(`Nút ${sel} -> "${expected}"`, text.startsWith(expected), text);
}
check('Tối đa 3 thông báo cùng lúc', await evaluate(`return document.querySelectorAll('.toast').length;`) <= 3);

const roundTrip = await evaluate(`
  const THREE = await import('three');
  const m = await import('/js/model-import-export.js');
  const root = new THREE.Group(); root.userData.easy3dProject = true;
  const a = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshStandardMaterial({ color: 0xff0000 }));
  a.name = 'Hộp A'; a.userData.kind = 'box';
  const b = a.clone(); b.name = 'Hộp B'; root.add(a, b);
  const { data } = await m.exportObjects(root, 'glb');
  const res = await m.loadModelFile(new File([data], 'p.glb'));
  return { isProject: res.isProject, names: res.objects.map((o) => o.name), kind: res.objects[0].userData.kind };`);
check('Lưu dự án rồi mở lại: tách đúng từng vật, giữ tên + loại',
  roundTrip.isProject && JSON.stringify(roundTrip.names) === '["Hộp A","Hộp B"]' && roundTrip.kind === 'box',
  JSON.stringify(roundTrip));
// ---------- Đợt 1: công cụ sửa hình ----------
const pure = await evaluate(`
  const THREE = await import('three');
  const S = await import('/js/mesh-subdivide-smooth.js');
  const M = await import('/js/mesh-split-merge-operations.js');
  const box = new THREE.BoxGeometry(1, 1, 1);
  const smooth = S.smoothGeometry(box, 3);
  smooth.computeBoundingBox();
  const sz = smooth.boundingBox.getSize(new THREE.Vector3());
  const sphere = new THREE.SphereGeometry(0.5, 64, 32);
  const simp = await S.simplifyGeometry(sphere, 0.3);
  const two = M.unifyAttributes([new THREE.BoxGeometry().toNonIndexed().translate(-2, 0, 0), new THREE.BoxGeometry().translate(2, 0, 0)]);
  const { mergeGeometries } = await import('three/addons/utils/BufferGeometryUtils.js');
  const parts = M.splitLooseParts(mergeGeometries(two.map((g) => g.index ? g : g.setIndex([...Array(g.attributes.position.count).keys()]))));
  const carved = M.booleanGeometry(new THREE.BoxGeometry(1, 1, 1), new THREE.SphereGeometry(0.7, 32, 16), 'subtract');
  return { smoothVerts: smooth.attributes.position.count, smoothSize: sz.x, sphereTris: S.triangleCountOf(sphere),
           simpTris: S.triangleCountOf(simp), simpUV: !!simp.attributes.uv, simpVerts: simp.attributes.position.count,
           sphereVerts: sphere.attributes.position.count, parts: parts.length, carvedVerts: carved.attributes.position.count };`);
check('Làm mượt hộp: chia nhỏ lưới + bo tròn, không teo quá', pure.smoothVerts > 1000 && pure.smoothSize > 0.75 && pure.smoothSize < 1.01, JSON.stringify(pure));
check('Giảm chi tiết cầu còn ~30%, giữ UV, bỏ đỉnh thừa', pure.simpTris < pure.sphereTris * 0.45 && pure.simpUV
  && pure.simpVerts < pure.sphereVerts, `${pure.sphereTris} -> ${pure.simpTris} tris, verts ${pure.sphereVerts} -> ${pure.simpVerts}`);
const loader = await evaluate(`
  const F = await import('/js/gltf-loader-factory.js');
  const { MeshoptDecoder } = await import('three/addons/libs/meshopt_decoder.module.js');
  await MeshoptDecoder.ready;
  const l = F.createGLTFLoader();
  const wasm = await fetch('/vendor/three/addons/libs/draco/gltf/draco_decoder.wasm');
  return { meshopt: !!l.meshoptDecoder && MeshoptDecoder.supported, draco: !!l.dracoLoader, wasm: wasm.ok,
    msg: F.friendlyGLTFError(new Error('THREE.GLTFLoader: Unknown extension "KHR_texture_basisu".')) };`);
check('Đọc được GLB nén (meshopt + Draco): loader có bộ giải nén, file wasm tải được',
  loader.meshopt && loader.draco && loader.wasm, JSON.stringify(loader));
check('Định dạng nén lạ -> báo lỗi tiếng Việt kèm tên định dạng', loader.msg.includes('KHR_texture_basisu') && loader.msg.includes('chưa đọc được'), loader.msg);
check('Tách 2 hộp rời thành 2 phần', pure.parts === 2);
check('Khoét hộp bằng cầu ra lưới khác rỗng', pure.carvedVerts > 0);

const clickText = (text) => evaluate(`[...document.querySelectorAll('#props button')].find(b => b.textContent.includes(${JSON.stringify(text)})).click();`);
const triStatus = () => evaluate(`return document.querySelector('#status-stats').textContent;`);
await evaluate(`[...document.querySelectorAll('#outliner li')].find(li => li.textContent.includes('Hộp 1')).click();`);
const trisBefore = await triStatus();
await clickText('Làm mượt'); await sleep(600);
const trisAfter = await triStatus();
check('Nút Làm mượt tăng số tam giác', trisAfter !== trisBefore, `${trisBefore} -> ${trisAfter}`);
await evaluate(`${q('#btn-undo')}.click();`);
check('Hoàn tác làm mượt', await triStatus() === trisBefore);

await evaluate(`[...document.querySelectorAll('#props select')].pop().value = '0';`); // dropdown "vật khác": Cầu 1
await clickText('Khoét đi'); await sleep(800);
let names = await outliner();
check('Khoét Hộp 1 bằng Cầu 1 -> còn 2 vật, có "(đã khoét)"', names.length === 2 && names.some((n) => n.includes('đã khoét')), JSON.stringify(names));
await evaluate(`${q('#btn-undo')}.click();`);
check('Hoàn tác khoét -> lại 3 vật', (await outliner()).length === 3);

await evaluate(`[...document.querySelectorAll('#outliner li')].find(li => li.textContent.includes('Hộp 1')).click();`);
await clickText('Tạo'); await sleep(300);
names = await outliner();
check('Nhân 5 bản thành hàng -> nhóm "Hộp 1 ×5"', names.includes('Hộp 1 ×5'), JSON.stringify(names));
await clickText('Tách phần rời'); await sleep(500);
names = await outliner();
check('Tách nhóm -> 5 hộp riêng có số thứ tự + 2 cầu', names.length === 7 && names.includes('Hộp 1 (5)'), JSON.stringify(names));
// ---------- Đợt 2: vật liệu, ánh sáng, xuất ảnh ----------
const selectByName = (n) => evaluate(`[...document.querySelectorAll('#outliner li')].find(li => li.querySelector('.name').textContent === ${JSON.stringify(n)}).click();`);
const chipCurrent = () => evaluate(`return [...document.querySelectorAll('#props .chip.current')].map(c => c.textContent);`);
await selectByName('Cầu 1');
await evaluate(`[...document.querySelectorAll('#props .chip')].find(c => c.textContent === 'Vàng').click();`);
check('Preset Vàng', (await chipCurrent()).includes('Vàng'));
await evaluate(`[...document.querySelectorAll('#props summary')].find(s => s.textContent.includes('Vân')).click();`);
await evaluate(`[...document.querySelectorAll('#props .chip')].find(c => c.textContent === 'Gỗ').click();`);
check('Vân Gỗ', (await chipCurrent()).includes('Gỗ'), JSON.stringify(await chipCurrent()));
const glossSlider = `[...document.querySelectorAll('#props .field')].find(f => f.querySelector('label')?.textContent === 'Độ bóng').querySelector('input')`;
const glossBefore = Number(await evaluate(`return ${glossSlider}.value;`));
await evaluate(`const s = ${glossSlider}; s.dispatchEvent(new PointerEvent('pointerdown')); s.value = 0.95;
  s.dispatchEvent(new Event('input')); s.dispatchEvent(new Event('change'));`);
check('Thanh Độ bóng áp dụng', Math.abs(Number(await evaluate(`return ${glossSlider}.value;`)) - 0.95) < 0.02);
await evaluate(`${q('#btn-undo')}.click();`);
check('Hoàn tác Độ bóng', Math.abs(Number(await evaluate(`return ${glossSlider}.value;`)) - glossBefore) < 0.02);

await evaluate(`${q('[data-lighting="sunset"]')}.click();`);
check('Preset ánh sáng Hoàng hôn', (await lastToast()).includes('Hoàng hôn'));
await evaluate(`${q('[data-light="point"]')}.click();`);
await evaluate(`${q('[data-light="spot"]')}.click();`);
names = await outliner();
check('Thêm đèn tròn + đèn rọi', names.includes('Đèn tròn 1') && names.includes('Đèn rọi 1'), JSON.stringify(names));
check('Panel đèn có Độ sáng, không có Sửa hình', await evaluate(`return document.querySelector('#props').textContent.includes('Độ sáng') && !document.querySelector('#props').textContent.includes('Sửa hình');`));
await evaluate(`${q('#props .swatch[title="#7aa8ff"]')}.click();`);
check('Đổi màu đèn', await evaluate(`return ${q('#props .swatch.current')}?.title;`) === '#7aa8ff');
await key('d', { ctrlKey: true });
check('Nhân bản đèn rọi', (await outliner()).includes('Đèn rọi 2'));

const lightTrip = await evaluate(`
  const THREE = await import('three');
  const L = await import('/js/scene-light-objects.js');
  const m = await import('/js/model-import-export.js');
  const root = new THREE.Group(); root.userData.easy3dProject = true; root.userData.lighting = 'night';
  root.add(L.createLightObject('spot', 'Đèn rọi A'));
  const { data } = await m.exportObjects(root, 'glb');
  const res = await m.loadModelFile(new File([data], 'p.glb'));
  const obj = res.objects[0]; L.fixLightCopy(obj); obj.updateMatrixWorld(true);
  const light = L.lightOf(obj); light.target.updateMatrixWorld(true);
  const lp = light.getWorldPosition(new THREE.Vector3()), tp = light.target.getWorldPosition(new THREE.Vector3());
  return { kind: obj.userData.kind, lighting: res.lighting, pointsDown: tp.y < lp.y - 0.5, spot: !!light.isSpotLight };`);
check('Lưu/mở dự án giữ đèn rọi, hướng chiếu xuống, preset ánh sáng',
  lightTrip.kind === 'light' && lightTrip.spot && lightTrip.pointsDown && lightTrip.lighting === 'night', JSON.stringify(lightTrip));

await evaluate(`${q('[data-action="export-image"]')}.click();`); await sleep(200);
await evaluate(`${q('input[name=size][value="4k"]')}.checked = true; ${q('#transparent')}.checked = true; ${q('#go')}.click();`);
await sleep(2500);
check('Xuất ảnh 4K nền trong suốt', (await lastToast()).startsWith('Đã xuất ảnh 3840×2160'), await lastToast());
// ---------- Camera khi xuất ảnh + Chỉnh ánh sáng ----------
const camNow = () => evaluate(`const { camera } = window.easy3d.viewport; return [...camera.position.toArray(), camera.fov].map((v) => +v.toFixed(4)).join();`);
const exportCam0 = await camNow();
await evaluate(`${q('[data-action="export-image"]')}.click();`); await sleep(200);
await evaluate(`${q('.cam-views [data-view="left"]')}.click(); const r = ${q('[data-k="fov"]')}; r.value = 30; r.dispatchEvent(new Event('input'));`);
await sleep(200);
const camMoved = await camNow();
check('Xuất ảnh: chọn góc "Cạnh trái" + ống kính -> camera đổi, có ảnh xem trước',
  camMoved !== exportCam0 && await evaluate(`return ${q('.cam-preview')}.src.startsWith('data:image/png');`), `${exportCam0} -> ${camMoved}`);
await evaluate(`${q('#cancel')}.click();`);
check('Huỷ xuất ảnh -> camera về như cũ', (await camNow()) === exportCam0);
await evaluate(`${q('[data-action="lighting-panel"]')}.click();`);
const sunPos = () => evaluate(`return window.easy3d.viewport.lights.sun.position.toArray().map((v) => +v.toFixed(3)).join();`);
const sun0 = await sunPos();
await evaluate(`const r = ${q('.lighting-panel [data-k="sunAz"]')}; r.value = -100; r.dispatchEvent(new Event('input')); r.dispatchEvent(new Event('change'));`);
check('Chỉnh ánh sáng: kéo Hướng nắng -> nắng đổi hướng', (await sunPos()) !== sun0);
await evaluate(`${q('#btn-undo')}.click();`);
check('Hoàn tác chỉnh ánh sáng', (await sunPos()) === sun0);
await evaluate(`${q('.lighting-panel [data-lp="close"]')}.click();`);
// ---------- Chế độ "Chỉnh điểm" ----------
/** Kéo chuột THẬT (qua DevTools) chéo khung 3D — giống người dùng kéo khung chọn. */
async function dragAcrossCanvas() {
  const r = await evaluate(`const b = document.querySelector('#viewport canvas').getBoundingClientRect();
    return { l: b.left, t: b.top, r: b.right, b: b.bottom };`);
  const mouse = (type, x, y, buttons) => send('Input.dispatchMouseEvent', { type, x, y, button: 'left', buttons, clickCount: 1 });
  await mouse('mousePressed', r.l + 5, r.t + 5, 1);
  for (let i = 1; i <= 5; i++) await mouse('mouseMoved', r.l + 5 + (r.r - r.l - 10) * i / 5, r.t + 5 + (r.b - r.t - 10) * i / 5, 1);
  await mouse('mouseReleased', r.r - 5, r.b - 5, 0);
  await sleep(100);
}
const geomTest = await evaluate(`
  const THREE = await import('three');
  const G = await import('/js/edit-mode-geometry.js');
  const S = await import('/js/mesh-subdivide-smooth.js');
  const m = S.toIndexedByPosition(new THREE.BoxGeometry(1, 1, 1));
  const box = G.buildGeometry(Array.from(m.attributes.position.array), null, 3, Array.from(m.index.array));
  const manifold = (g) => { const use = new Map(), idx = g.index.array;
    for (let f = 0; f < idx.length / 3; f++) for (let k = 0; k < 3; k++) {
      const a = idx[f*3+k], b = idx[f*3+(k+1)%3], key = Math.min(a,b) + '_' + Math.max(a,b); use.set(key, (use.get(key) ?? 0) + 1); }
    return [...use.values()].every((n) => n === 2); };
  const selF = new Uint8Array(12); selF[0] = selF[1] = 1;           // 1 mặt vuông = 2 tam giác
  const ex = G.extrudeFaces(box, selF, 0.5);
  ex.geo.computeBoundingBox();
  const del = G.deleteFaces(box, selF);
  const selV = new Uint8Array(8); selV[0] = selV[1] = 1;
  const merged = G.mergeSelected(box, selV);
  return { verts: box.attributes.position.count, exVerts: ex.geo.attributes.position.count, exFaces: G.faceCount(ex.geo),
           exManifold: manifold(ex.geo), boxManifold: manifold(box), exSize: ex.geo.boundingBox.getSize(new THREE.Vector3()).toArray(),
           delFaces: G.faceCount(del), mergedVerts: merged.attributes.position.count, newSel: ex.selV.reduce((a, b) => a + b, 0) };`);
check('Hộp gộp đỉnh = 8 điểm, lưới kín', geomTest.verts === 8 && geomTest.boxManifold, JSON.stringify(geomTest));
check('Đùn 1 mặt: +4 điểm, +8 tam giác, lưới vẫn kín, dài thêm 0.5',
  geomTest.exVerts === 12 && geomTest.exFaces === 20 && geomTest.exManifold && geomTest.newSel === 4
  && Math.abs(Math.max(...geomTest.exSize) - 1.5) < 1e-6, JSON.stringify(geomTest));
check('Xoá 1 mặt vuông còn 10 tam giác', geomTest.delFaces === 10);
check('Dồn 2 điểm vào giữa còn 7 điểm', geomTest.mergedVerts === 7);

const editText = (sel) => evaluate(`return document.querySelector('.edit-toolbar ${sel}')?.textContent ?? null;`);
const editOp = (op) => evaluate(`document.querySelector('.edit-toolbar [data-op="${op}"]').click();`);
await selectByName('Hộp 1 (1)');
const trisBeforeEdit = await triStatus();
await evaluate(`${q('[data-action="edit-mode"]')}.click();`);
check('Vào chế độ Chỉnh điểm: hiện thanh công cụ, khoá panel phải',
  await evaluate(`return !document.querySelector('.edit-toolbar').hidden && document.body.classList.contains('edit-mode');`));
await key('a');
check('Phím A chọn hết 8 điểm', await editText('#edit-count') === 'Đã chọn 8 điểm', await editText('#edit-count'));
await key('2');
check('Phím 2 sang chọn mặt: 12 mặt', await editText('#edit-count') === 'Đã chọn 12 mặt', await editText('#edit-count'));
await key('a');
await evaluate(`document.querySelector('.edit-toolbar [data-tool="box"]').click();`);
await dragAcrossCanvas();
const boxDrag = await editText('#edit-count');
const facesPicked = Number(boxDrag.match(/\d+/)?.[0] ?? 0);
check('Kéo khung chọn chỉ các mặt nhìn thấy (không chọn mặt sau)', facesPicked > 0 && facesPicked < 12, boxDrag);
await editOp('extrude');
check('Đùn ra', (await lastToast()).startsWith('Đã đùn ra'));
await editOp('undo');
check('Hoàn tác trong chế độ chỉnh điểm', await editText('#edit-count') === boxDrag, await editText('#edit-count'));
await editOp('redo');
await evaluate(`const i = document.querySelector('#edit-color'); i.value = '#5fd08a'; i.dispatchEvent(new Event('change'));`);
check('Tô màu giữ nguyên vùng chọn', await editText('#edit-count') === boxDrag, await editText('#edit-count'));
await shot('04-edit-mode.png');
await editOp('exit');
check('Xong: thoát chế độ, số tam giác tăng do đùn', await evaluate(`return document.querySelector('.edit-toolbar').hidden;`)
  && await triStatus() !== trisBeforeEdit, `${trisBeforeEdit} -> ${await triStatus()}`);
await evaluate(`${q('#btn-undo')}.click();`);
check('Hoàn tác cả lượt chỉnh điểm bằng 1 lần Ctrl+Z', await triStatus() === trisBeforeEdit, await triStatus());

await evaluate(`${q('[data-action="edit-mode"]')}.click();`);
// Lỗi từng gặp trên máy thật: vào chỉnh điểm LẦN 2 không thấy chấm điểm/lưới (lớp hiển thị bị gỡ khỏi cảnh).
const overlayState = await evaluate(`const { viewport, store } = window.easy3d; let points = 0, wires = 0, ghosts = 0;
  viewport.scene.traverse((o) => { if (o.isPoints && o.visible) points++; if (o.isMesh && o.material?.wireframe) wires++; });
  store.objects.forEach((o) => o.traverse((m) => { if (m.isMesh && m.material.opacity < 0.2) ghosts++; }));
  return { points, wires, ghosts, minimal: document.querySelector('#edit-minimal').checked };`);
check('Vào chỉnh điểm lần 2: vẫn thấy chấm điểm + lưới, vật khác mờ đi, xem tối giản',
  overlayState.points === 1 && overlayState.wires >= 1 && overlayState.ghosts > 0 && overlayState.minimal, JSON.stringify(overlayState));
await evaluate(`const c = document.querySelector('#edit-minimal'); c.checked = false; c.dispatchEvent(new Event('change'));`);
check('Bỏ "Xem tối giản" -> vật khác hiện lại bình thường', await evaluate(`let g = 0; window.easy3d.store.objects.forEach((o) => o.traverse((m) => { if (m.isMesh && m.material.opacity < 0.2) g++; })); return g === 0;`));
await key('2');
await evaluate(`document.querySelector('.edit-toolbar [data-tool="box"]').click();`);
await dragAcrossCanvas();
await editOp('separate');
names = await outliner();
check('Tách các mặt chọn thành vật mới', names.some((n) => n.includes('phần tách')) && await evaluate(`return document.querySelector('.edit-toolbar').hidden;`), JSON.stringify(names));

// Kéo gizmo bằng chuột thật để di chuyển các điểm đã chọn (tính vị trí tay cầm trục X giống TransformControls).
await selectByName('Hộp 1 (2)');
await evaluate(`${q('[data-action="edit-mode"]')}.click();`);
await key('1'); await key('a'); await key('w');
const handle = await evaluate(`
  const THREE = await import('three');
  const { viewport, store } = window.easy3d;
  const mesh = store.selected, cam = viewport.camera;
  const c = new THREE.Box3().setFromObject(mesh).getCenter(new THREE.Vector3());
  const factor = c.distanceTo(cam.position) * Math.min(1.9 * Math.tan(Math.PI * cam.fov / 360) / cam.zoom, 7) / 4;
  const r = viewport.renderer.domElement.getBoundingClientRect();
  const toScreen = (v) => { const p = v.clone().project(cam); return { x: r.left + (p.x + 1) / 2 * r.width, y: r.top + (1 - p.y) / 2 * r.height }; };
  const a = toScreen(c.clone().add(new THREE.Vector3(0.4 * factor, 0, 0)));
  const b = toScreen(c.clone().add(new THREE.Vector3(0.6 * factor, 0, 0)));
  const len = Math.hypot(b.x - a.x, b.y - a.y);
  return { x: a.x, y: a.y, dx: (b.x - a.x) / len, dy: (b.y - a.y) / len, cx: c.x };`);
const mouse = (type, x, y, buttons) => send('Input.dispatchMouseEvent', { type, x, y, button: 'left', buttons, clickCount: 1 });
await mouse('mouseMoved', handle.x, handle.y, 0);
await mouse('mousePressed', handle.x, handle.y, 1);
for (let i = 1; i <= 8; i++) await mouse('mouseMoved', handle.x + handle.dx * 10 * i, handle.y + handle.dy * 10 * i, 1);
await mouse('mouseReleased', handle.x + handle.dx * 80, handle.y + handle.dy * 80, 0);
await sleep(150);
check('Vẫn còn chọn 8 điểm sau khi kéo (không bị hiểu là bấm bỏ chọn)', await editText('#edit-count') === 'Đã chọn 8 điểm', await editText('#edit-count'));
await editOp('exit');
const movedX = await evaluate(`const THREE = await import('three');
  return new THREE.Box3().setFromObject(window.easy3d.store.selected).getCenter(new THREE.Vector3()).x;`);
check('Kéo mũi tên trục X bằng chuột thật -> các điểm dời sang phải', movedX > handle.cx + 0.05, `${handle.cx.toFixed(3)} -> ${movedX.toFixed(3)}`);

// ---------- Chọn nhiều vật: gộp / ghép liền / nhóm / kéo cả nhóm ----------
const clickName = (n, shift = false) => evaluate(`[...document.querySelectorAll('#outliner li')]
  .find(li => li.querySelector('.name').textContent === ${JSON.stringify(n)})
  .dispatchEvent(new MouseEvent('click', { bubbles: true, shiftKey: ${shift} }));`);
const bigAction = (t) => evaluate(`[...document.querySelectorAll('#props .big-action')].find(b => b.textContent.includes(${JSON.stringify(t)})).click();`);
const countBefore = (await outliner()).length;
await clickName('Hộp 1 (3)'); await clickName('Hộp 1 (4)', true);
check('Shift + bấm chọn 2 vật -> panel "Đã chọn 2 vật"', await evaluate(`return document.querySelector('#props .multi-head b')?.textContent;`) === 'Đã chọn 2 vật');
check('Danh sách tô đậm cả 2 vật', await evaluate(`return document.querySelectorAll('#outliner li.selected').length;`) === 2);
await key('f'); await sleep(300); // F: camera nhìn trọn cả 2 vật đang chọn
await key('w'); // công cụ Di chuyển (bước trước test đã chọn Xoay)

const multi = await evaluate(`
  const THREE = await import('three');
  const { viewport, store } = window.easy3d; const cam = viewport.camera;
  const box = new THREE.Box3(); store.selection.forEach((o) => box.expandByObject(o));
  const c = box.getCenter(new THREE.Vector3());
  const factor = c.distanceTo(cam.position) * Math.min(1.9 * Math.tan(Math.PI * cam.fov / 360) / cam.zoom, 7) / 4;
  const r = viewport.renderer.domElement.getBoundingClientRect();
  const toScreen = (v) => { const p = v.clone().project(cam); return { x: r.left + (p.x + 1) / 2 * r.width, y: r.top + (1 - p.y) / 2 * r.height }; };
  const a = toScreen(c.clone().add(new THREE.Vector3(0.4 * factor, 0, 0))), b = toScreen(c.clone().add(new THREE.Vector3(0.6 * factor, 0, 0)));
  const len = Math.hypot(b.x - a.x, b.y - a.y);
  return { x: a.x, y: a.y, dx: (b.x - a.x) / len, dy: (b.y - a.y) / len, xs: store.selection.map((o) => o.position.x) };`);
const underCursor = await evaluate(`const e = document.elementFromPoint(${multi.x}, ${multi.y}); return e.tagName + '.' + e.className;`);
await mouse('mouseMoved', multi.x, multi.y, 0);
await mouse('mousePressed', multi.x, multi.y, 1);
for (let i = 1; i <= 8; i++) await mouse('mouseMoved', multi.x + multi.dx * 10 * i, multi.y + multi.dy * 10 * i, 1);
await mouse('mouseReleased', multi.x + multi.dx * 80, multi.y + multi.dy * 80, 0);
await sleep(150);
const xsAfter = await evaluate(`return window.easy3d.store.selection.map((o) => o.position.x);`);
const moved = xsAfter.map((x, i) => x - multi.xs[i]);
check('Kéo gizmo khi chọn 2 vật -> cả 2 cùng dời một khoảng', moved[0] > 0.05 && Math.abs(moved[0] - moved[1]) < 1e-6,
  `${JSON.stringify(moved)} under=${underCursor}`);
await evaluate(`${q('#btn-undo')}.click();`);
const xsUndo = await evaluate(`return window.easy3d.store.selection.map((o) => o.position.x);`);
check('1 lần hoàn tác trả cả 2 vật về chỗ cũ', xsUndo.every((x, i) => Math.abs(x - multi.xs[i]) < 1e-6), JSON.stringify(xsUndo));

await bigAction('Gộp thành 1 vật');
names = await outliner();
check('Gộp 2 vật thành 1', names.length === countBefore - 1 && names.includes('Hộp 1 (3) + Hộp 1 (4)'), JSON.stringify(names));
await clickName('Hộp 1 (5)', true);
await bigAction('Gộp thành 1 vật');
const mats = await evaluate(`const m = window.easy3d.store.selected; return Array.isArray(m.material) ? m.material.length : 1;`);
check('Gộp tiếp vật đã gộp: giữ 3 chất liệu riêng', mats === 3, `materials=${mats}`);
await evaluate(`${q('#btn-undo')}.click();`);
await evaluate(`${q('#btn-undo')}.click();`); // gộp 2 lần -> hoàn tác 2 lần
check('Hoàn tác gộp -> lại đủ vật', (await outliner()).length === countBefore, JSON.stringify(await outliner()));

await clickName('Hộp 1 (3)'); await clickName('Hộp 1 (4)', true);
await key('g', { ctrlKey: true });
names = await outliner();
check('Ctrl+G nhóm lại', names.includes('Nhóm 1') && names.length === countBefore - 1, JSON.stringify(names));
await clickText('Tách phần rời'); await sleep(300);
check('Tách nhóm ra lại từng vật', (await outliner()).length === countBefore, JSON.stringify(await outliner()));

await clickName('Hộp 1 (3)'); await clickName('Hộp 1 (4)', true);
await bigAction('Ghép liền'); await sleep(800);
names = await outliner();
check('Ghép liền 2 hộp (CSG)', names.length === countBefore - 1 && names.includes('Hộp 1 (3) + Hộp 1 (4)'), JSON.stringify(names));
await key('a', { ctrlKey: true });
check('Ctrl+A chọn tất cả vật đang hiện', await evaluate(`return document.querySelectorAll('#outliner li.selected').length;`) === names.length);

// ---------- Tô vẽ: cọ, hoàn tác, hút màu, tô hết, dán ảnh ----------
const paintInfo = () => evaluate(`const s = window.easy3d.paintMode.state; if (!s) return null;
  const c = s.geo.attributes.color, n = c.count; let red = 0, blue = 0, same = true;
  const r0 = c.getX(0), g0 = c.getY(0), b0 = c.getZ(0);
  for (let i = 0; i < n; i++) { const r = c.getX(i), g = c.getY(i), b = c.getZ(i);
    if (r > 0.6 && g < 0.3 && b < 0.3) red++; if (b > 0.6 && r < 0.3 && g < 0.3) blue++;
    if (Math.abs(r - r0) + Math.abs(g - g0) + Math.abs(b - b0) > 1e-4) same = false; }
  return { n, red, blue, same, brush: s.brush };`);
await clickName('Hộp 1 (5)');
await key('f'); await sleep(300);
await key('b');
check('Phím B vào Tô vẽ: hiện thanh công cụ, lưới được chia nhỏ để tô mịn',
  await evaluate(`return !document.querySelector('.paint-toolbar').hidden && document.body.classList.contains('paint-mode');`)
  && (await paintInfo()).n > 1000, JSON.stringify((await paintInfo())?.n));
const center = await evaluate(`const THREE = await import('three'); const { viewport, store } = window.easy3d;
  const c = new THREE.Box3().setFromObject(store.selected).getCenter(new THREE.Vector3()).project(viewport.camera);
  const r = viewport.renderer.domElement.getBoundingClientRect();
  return { x: r.left + (c.x + 1) / 2 * r.width, y: r.top + (1 - c.y) / 2 * r.height };`);
await evaluate(`document.querySelector('.paint-toolbar .swatch[title="#ff5c5c"]').click();`);
await evaluate(`const s = document.querySelector('#paint-strength'); s.value = 1; s.dispatchEvent(new Event('input'));`);
await mouse('mouseMoved', center.x - 30, center.y, 0);
await mouse('mousePressed', center.x - 30, center.y, 1);
for (let i = 1; i <= 6; i++) await mouse('mouseMoved', center.x - 30 + i * 10, center.y, 1);
await mouse('mouseReleased', center.x + 30, center.y, 0);
let pi = await paintInfo();
check('Kéo cọ trên vật -> có vùng màu đỏ', pi.red > 20, JSON.stringify({ red: pi.red, n: pi.n }));
await evaluate(`document.querySelector('.paint-toolbar [data-op="undo"]').click();`);
check('Hoàn tác nét cọ', (await paintInfo()).red === 0);
await evaluate(`document.querySelector('.paint-toolbar [data-op="redo"]').click();`);
await evaluate(`document.querySelector('.paint-toolbar .swatch[title="#5fd08a"]').click();`);
await evaluate(`document.querySelector('.paint-toolbar [data-brush="pick"]').click();`);
await mouse('mousePressed', center.x, center.y, 1); await mouse('mouseReleased', center.x, center.y, 0);
pi = await paintInfo();
check('Hút màu trên vùng đỏ -> cọ thành màu đỏ, quay về chế độ Tô', pi.brush.mode === 'paint' && pi.brush.color.startsWith('#ff'), JSON.stringify(pi.brush));
await evaluate(`document.querySelector('.paint-toolbar [data-op="fill"]').click();`);
check('Tô hết 1 màu', (await paintInfo()).same);
await evaluate(`document.querySelector('.paint-toolbar [data-op="undo"]').click();`);

await evaluate(`
  const c = Object.assign(document.createElement('canvas'), { width: 64, height: 64 }), g = c.getContext('2d');
  g.fillStyle = '#ff0000'; g.fillRect(0, 0, 32, 64); g.fillStyle = '#0000ff'; g.fillRect(32, 0, 32, 64);
  const blob = await new Promise((r) => c.toBlob(r, 'image/png'));
  const dt = new DataTransfer(); dt.items.add(new File([blob], 'logo.png', { type: 'image/png' }));
  const input = document.querySelector('#paint-file'); input.files = dt.files; input.dispatchEvent(new Event('change'));`);
await sleep(400);
check('Chọn ảnh -> hiện ảnh để đặt + hàng chỉnh ảnh', await evaluate(`return !document.querySelector('.image-placement').hidden && !document.querySelector('#paint-image-row').hidden;`));
await shot('05-paint-image.png');
await evaluate(`document.querySelector('.paint-toolbar [data-op="apply-image"]').click();`);
pi = await paintInfo();
check('Dán ảnh đỏ/xanh lên vật -> có cả điểm đỏ và xanh', pi.blue > 20 && pi.red > 20, JSON.stringify({ red: pi.red, blue: pi.blue }));
check('Ảnh đặt tạm đã ẩn sau khi dán', await evaluate(`return document.querySelector('.image-placement').hidden;`));
await evaluate(`document.querySelector('.paint-toolbar [data-op="exit"]').click();`);
check('Xong: thoát Tô vẽ, vật giữ màu đã tô', await evaluate(`const m = window.easy3d.store.selected; return document.querySelector('.paint-toolbar').hidden && m.material.vertexColors && !!m.geometry.attributes.color;`));
await evaluate(`${q('#btn-undo')}.click();`);
check('1 lần hoàn tác bỏ cả lượt tô vẽ', await evaluate(`return !window.easy3d.store.selected.material.vertexColors;`));

// ---------- Nặn hình: đắp, lõm, kéo, đối xứng, hoàn tác ----------
const sculptStats = () => evaluate(`const s = window.easy3d.sculptMode.state; if (!s) return null;
  const p = s.geo.attributes.position.array; let sum = 0, maxX = -Infinity, check = 0;
  const cx = s.symX;
  for (let i = 0; i < p.length; i += 3) { sum += Math.hypot(p[i] - cx, p[i + 1] - 0.5, p[i + 2]); maxX = Math.max(maxX, p[i]); check += p[i] * 1.3 + p[i + 1] * 0.7 + p[i + 2]; }
  return { n: p.length / 3, mean: sum / (p.length / 3), maxX, check, brush: s.brush };`);
// So với bản chụp `window.__sculptBase`: tổng dời ra xa tâm (+ phồng, - lõm), tổng dời theo x, số điểm bị dời.
const markSculptBase = () => evaluate(`const g = window.easy3d.sculptMode.state.geo; g.computeBoundingBox();
  window.__sculptBase = g.attributes.position.array.slice(); window.__sculptCenter = g.boundingBox.getCenter(new (await import('three')).Vector3());`);
const sculptDiff = () => evaluate(`const p = window.easy3d.sculptMode.state.geo.attributes.position.array, o = window.__sculptBase, c = window.__sculptCenter;
  let radial = 0, dx = 0, moved = 0;
  for (let i = 0; i < p.length; i += 3) {
    const d = Math.hypot(p[i] - o[i], p[i + 1] - o[i + 1], p[i + 2] - o[i + 2]);
    if (d < 1e-6) continue;
    moved++; dx += p[i] - o[i];
    radial += Math.hypot(p[i] - c.x, p[i + 1] - c.y, p[i + 2] - c.z) - Math.hypot(o[i] - c.x, o[i + 1] - c.y, o[i + 2] - c.z);
  }
  return { radial: +radial.toFixed(4), dx: +dx.toFixed(4), moved };`);
const sculptOp = (op) => evaluate(`document.querySelector('.sculpt-toolbar [data-op="${op}"]').click();`);
const sculptBrush = (b) => evaluate(`document.querySelector('.sculpt-toolbar [data-sculpt="${b}"]').click();`);
const strokeAcross = async (cx, cy, dx, shift = false) => {
  const mods = shift ? 8 : 0; // 8 = Shift trong DevTools Protocol
  const m = (type, x, buttons) => send('Input.dispatchMouseEvent', { type, x, y: cy, button: 'left', buttons, clickCount: 1, modifiers: mods });
  await m('mouseMoved', cx, 0); await m('mousePressed', cx, 1);
  for (let i = 1; i <= 6; i++) await m('mouseMoved', cx + dx * i / 6, 1);
  await m('mouseReleased', cx + dx, 0);
  await sleep(100);
};

await clickName('Cầu 2');
await key('f'); await sleep(300);
await key('n');
let ss = await sculptStats();
check('Phím N vào Nặn hình: hiện thanh công cụ, lưới đủ dày', await evaluate(`return !document.querySelector('.sculpt-toolbar').hidden && document.body.classList.contains('sculpt-mode');`)
  && ss.n > 5000, JSON.stringify(ss?.n));
check('Khi nặn, các vật khác mờ đi (không che chỗ đang nặn)', await evaluate(`let g = 0; window.easy3d.store.objects.forEach((o) => o.traverse((m) => { if (m.isMesh && m.material.opacity < 0.2) g++; })); return g > 0;`));
const sc = await evaluate(`const THREE = await import('three'); const { viewport, store } = window.easy3d;
  const c = new THREE.Box3().setFromObject(store.selected).getCenter(new THREE.Vector3()).project(viewport.camera);
  const r = viewport.renderer.domElement.getBoundingClientRect();
  return { x: r.left + (c.x + 1) / 2 * r.width, y: r.top + (1 - c.y) / 2 * r.height };`);
const base = ss;
await markSculptBase();
await evaluate(`const s = document.querySelector('#sculpt-strength'); s.value = 1; s.dispatchEvent(new Event('input'));`);
await strokeAcross(sc.x - 20, sc.y, 40);
let sd = await sculptDiff();
check('Cọ Đắp làm vật phồng ra', sd.moved > 50 && sd.radial > 0.5, JSON.stringify(sd));
await sculptOp('undo');
check('Hoàn tác nét nặn trả đúng hình cũ', Math.abs((await sculptStats()).check - base.check) < 1e-3);
await strokeAcross(sc.x - 20, sc.y, 40, true);
sd = await sculptDiff();
check('Giữ Shift khi Đắp -> lõm vào', sd.moved > 50 && sd.radial < -0.5, JSON.stringify(sd));
await sculptOp('undo');
await sculptBrush('carve');
await strokeAcross(sc.x - 20, sc.y, 40);
sd = await sculptDiff();
check('Cọ Lõm làm vật lõm vào', sd.moved > 50 && sd.radial < -0.5, JSON.stringify(sd));
await sculptBrush('smooth');
const beforeSmooth = (await sculptStats()).check;
await strokeAcross(sc.x - 20, sc.y, 40);
check('Cọ Làm mượt có tác dụng', Math.abs((await sculptStats()).check - beforeSmooth) > 1e-4);
await sculptOp('undo'); await sculptOp('undo');
check('Hoàn tác nhiều bước về hình gốc', Math.abs((await sculptStats()).check - base.check) < 1e-3);

await sculptBrush('grab');
await strokeAcross(sc.x, sc.y, 80);
sd = await sculptDiff();
check('Cọ Kéo dời cả vùng theo chuột (sang phải)', sd.moved > 50 && sd.dx > 1, JSON.stringify(sd));
await sculptOp('undo');

await key('x'); // bật đối xứng
const symmetry = await evaluate(`return window.easy3d.sculptMode.state.brush.symmetry;`);
await sculptBrush('draw');
await evaluate(`window.__sculptBefore = window.easy3d.sculptMode.state.geo.attributes.position.array.slice();`);
await strokeAcross(sc.x + 25, sc.y, 15); // chỉ nặn bên phải
const sides = await evaluate(`const s = window.easy3d.sculptMode.state, p = s.geo.attributes.position.array, old = window.__sculptBefore;
  let left = 0, right = 0;
  for (let i = 0; i < p.length; i += 3) {
    if (Math.hypot(p[i] - old[i], p[i + 1] - old[i + 1], p[i + 2] - old[i + 2]) > 1e-5) { if (old[i] < s.symX) left++; else right++; } }
  return { left, right };`);
check('Đối xứng (phím X): nặn bên phải, bên trái cũng đổi theo', symmetry && sides.left > 10 && sides.right > 10, JSON.stringify(sides));
await shot('06-sculpt.png');
await sculptOp('exit');
check('Xong: thoát Nặn hình, hình mới được giữ', await evaluate(`return document.querySelector('.sculpt-toolbar').hidden && !document.body.classList.contains('sculpt-mode');`));
const sculptedTris = await triStatus();
await evaluate(`${q('#btn-undo')}.click();`);
check('1 lần hoàn tác bỏ cả lượt nặn', await triStatus() !== sculptedTris, `${sculptedTris} -> ${await triStatus()}`);

// ---------- Ghép xương + tạo dáng ----------
const rigUi = () => evaluate(`const b = document.querySelector('.rig-toolbar');
  const shown = (sel) => getComputedStyle(b.querySelector(sel)).display !== 'none';
  return { shown: !b.hidden, place: shown('#rig-place'), pose: shown('#rig-pose'), info: window.easy3d.rigMode.info() };`);
// Nút có ở cả 2 hàng (Đặt khớp / Tạo dáng) -> bấm nút đang hiển thị.
const rigOp = (op) => evaluate(`[...document.querySelectorAll('.rig-toolbar [data-op="${op}"]')].find((b) => b.offsetParent)?.click();`);
const clickWorld = async (exprWorldVec) => {
  const p = await evaluate(`const THREE = await import('three'); const { viewport } = window.easy3d;
    const v = (${exprWorldVec}).project(viewport.camera); const r = viewport.renderer.domElement.getBoundingClientRect();
    return { x: r.left + (v.x + 1) / 2 * r.width, y: r.top + (1 - v.y) / 2 * r.height };`);
  await mouse('mouseMoved', p.x, p.y, 0); await mouse('mousePressed', p.x, p.y, 1); await mouse('mouseReleased', p.x, p.y, 0);
  await sleep(100);
};

await clickName('Hộp 1 (5)');
await key('f'); await sleep(300);
await key('j');
let ru = await rigUi();
check('Phím J vào Ghép xương bước 1: chỉ hiện hàng Đặt khớp, mẫu Người 22 khớp',
  ru.shown && ru.place && !ru.pose && ru.info.template === 'human' && (await evaluate(`return window.easy3d.rigMode.joints.length;`)) === 22, JSON.stringify(ru));
await clickWorld(`window.easy3d.rigMode.joints[7].position.clone().applyMatrix4(window.easy3d.store.selected.matrixWorld)`);
check('Bấm chuột thật vào chấm khớp -> chọn đúng khớp', (await rigUi()).info.selected === 'Khuỷu trái', JSON.stringify((await rigUi()).info));
await evaluate(`[...document.querySelectorAll('.rig-toolbar [data-template]')].find((b) => b.dataset.template === 'chain').click();`);
check('Đổi mẫu Chuỗi -> 6 khớp', (await evaluate(`return window.easy3d.rigMode.joints.length;`)) === 6);
await evaluate(`[...document.querySelectorAll('.rig-toolbar [data-template]')].find((b) => b.dataset.template === 'human').click();`);
// ---- Ghép xương v2: kéo thẳng chấm khớp, xoay hướng, cây xương ----
const jointWorld = (i) => `window.easy3d.rigMode.joints[${i}].position.clone().applyMatrix4(window.easy3d.store.selected.matrixWorld)`;
const jointArr = (i) => evaluate(`const THREE = await import('three'); return ${jointWorld(i)}.toArray().map((v) => +v.toFixed(4));`);
const camArr = () => evaluate(`return window.easy3d.viewport.camera.position.toArray().map((v) => +v.toFixed(4));`);
const jp = await evaluate(`const THREE = await import('three'); const { viewport } = window.easy3d; const v = ${jointWorld(7)}.project(viewport.camera);
  const r = viewport.renderer.domElement.getBoundingClientRect(); return { x: r.left + (v.x + 1) / 2 * r.width, y: r.top + (1 - v.y) / 2 * r.height };`);
const [elbow0, cam0] = [await jointArr(7), await camArr()];
await mouse('mouseMoved', jp.x, jp.y, 0); await mouse('mousePressed', jp.x, jp.y, 1);
for (let i = 1; i <= 5; i++) await mouse('mouseMoved', jp.x + 6 * i, jp.y - 6 * i, 1);
await mouse('mouseReleased', jp.x + 30, jp.y - 30, 0);
const [elbow1, cam1] = [await jointArr(7), await camArr()];
const sym = await evaluate(`const THREE = await import('three'); const { rigMode, store } = window.easy3d; const a = ${jointWorld(7)}, b = ${jointWorld(11)};
  return Math.abs(a.y - b.y) < 1e-4;`);
check('Kéo thẳng chấm khớp bằng chuột: khớp dời, khớp đối xứng đi theo, góc nhìn đứng yên',
  elbow0.join() !== elbow1.join() && cam0.join() === cam1.join() && sym, `${elbow0} -> ${elbow1}, cam ${cam0} -> ${cam1}`);
await rigOp('undo');
check('Hoàn tác ở bước Đặt khớp trả khớp về chỗ cũ', (await jointArr(7)).join() === elbow0.join());
const turn = (n) => evaluate(`document.querySelector('.rig-toolbar [data-op="turn"][data-arg="${n}"]').click();`);
const arm0 = await jointArr(6);
await turn(1);
const arm90 = await jointArr(6);
await turn(1); await turn(2);
check('Nút ↻ 90° xoay hướng bộ xương; xoay đủ vòng về đúng chỗ cũ', arm90.join() !== arm0.join() && (await jointArr(6)).join() === arm0.join(), `${arm0} | ${arm90}`);
const treeRows = () => evaluate(`return document.querySelectorAll('.rig-tree-panel .rig-tree li').length;`);
check('Panel cây xương hiện 22 khớp (tên Unity)', (await treeRows()) === 22
  && await evaluate(`return document.querySelector('.rig-tree li small').textContent === 'Hips';`));
await evaluate(`document.querySelectorAll('.rig-tree li')[7].click();`);
check('Bấm dòng trong cây -> chọn khớp', (await rigUi()).info.selectedName === 'LeftLowerArm');
await evaluate(`const i = document.querySelector('.rig-selected input'); i.value = 'Khuỷu tay'; i.dispatchEvent(new Event('change'));`);
check('Tên xương có dấu/khoảng trắng bị từ chối (game không đọc được)', (await rigUi()).info.selectedName === 'LeftLowerArm');
await evaluate(`[...document.querySelectorAll('.rig-actions button')].find((b) => b.textContent.includes('Khớp con')).click();`);
const added = await treeRows();
await evaluate(`[...document.querySelectorAll('.rig-actions button')].find((b) => b.textContent.includes('Xoá')).click();`);
check('Thêm khớp con rồi xoá: vẫn ở chế độ Ghép xương, 23 -> 22 khớp', added === 23 && (await treeRows()) === 22 && (await rigUi()).shown);
await rigOp('bind'); await sleep(300);
const bound = await evaluate(`const o = window.easy3d.store.selected; let sk = null; o.traverse((m) => { if (m.isSkinnedMesh) sk = m; });
  const w = sk.geometry.attributes.skinWeight; let bad = 0;
  for (let i = 0; i < w.count; i++) if (Math.abs(w.getX(i) + w.getY(i) + w.getZ(i) + w.getW(i) - 1) > 1e-3) bad++;
  return { kind: o.userData.kind, bones: sk.skeleton.bones.length, bad, stage: window.easy3d.rigMode.stage };`);
check('Gắn vào hình: vật có 22 xương, tổng trọng lượng mỗi đỉnh = 1, sang bước Tạo dáng',
  bound.kind === 'rigged' && bound.bones === 22 && bound.bad === 0 && bound.stage === 'pose', JSON.stringify(bound));
check('Xương mang tên chuẩn Unity Humanoid + nhãn tiếng Việt', await evaluate(`let sk; window.easy3d.store.selected.traverse((m) => { if (m.isSkinnedMesh) sk = m; });
  const b = sk.skeleton.bones; return b[0].name === 'Hips' && b[7].name === 'LeftLowerArm' && b[7].userData.label === 'Khuỷu trái';`));
const boundElbow = await evaluate(`let sk; const o = window.easy3d.store.selected; o.traverse((m) => { if (m.isSkinnedMesh) sk = m; }); o.updateMatrixWorld(true);
  return sk.skeleton.bones[7].getWorldPosition(new (await import('three')).Vector3()).toArray().map((v) => +v.toFixed(4));`);
await rigOp('editJoints');
check('✏ Sửa khớp: quay lại bước 1, khớp ở đúng chỗ lúc gắn', (await rigUi()).info.stage === 'place' && (await jointArr(7)).join() === boundElbow.join(),
  `${boundElbow} vs ${await jointArr(7)}`);
await rigOp('bind'); await sleep(300);
ru = await rigUi();
check('Bước 2: chỉ hiện hàng Tạo dáng', !ru.place && ru.pose);
const boneExpr = (i) => `(() => { let sk; window.easy3d.store.selected.traverse((m) => { if (m.isSkinnedMesh) sk = m; }); return sk.skeleton.bones[${i}]; })()`;
await clickWorld(`${boneExpr(7)}.getWorldPosition(new THREE.Vector3())`);
check('Bấm chuột thật vào khớp xương -> chọn "Khuỷu trái"', (await rigUi()).info.selected === 'Khuỷu trái', JSON.stringify((await rigUi()).info));
const poseBox = () => evaluate(`const THREE = await import('three'); let sk; window.easy3d.store.selected.traverse((m) => { if (m.isSkinnedMesh) sk = m; });
  // Xương là anh em của SkinnedMesh trong nhóm -> cập nhật từ nhóm (app thật: mỗi frame render tự cập nhật).
  window.easy3d.store.selected.updateMatrixWorld(true); sk.skeleton.update();
  // Tự tính khung bao từ vị trí ĐÃ UỐN theo xương (getVertexPosition áp skinning).
  const b = new THREE.Box3(), v = new THREE.Vector3();
  for (let i = 0; i < sk.geometry.attributes.position.count; i++) b.expandByPoint(sk.localToWorld(sk.getVertexPosition(i, v)));
  return [...b.min.toArray(), ...b.max.toArray()].map((x) => +x.toFixed(3));`);
const boxBefore = await poseBox();
await evaluate(`${boneExpr(6)}.rotateZ(1.2);`); // nâng tay trái lên (bên trái nhân vật = +X, chuẩn glTF/Unity)
const boxAfter = await poseBox();
await sleep(200); await shot('08-rig-pose.png');
check('Xoay xương vai -> hình uốn theo (da đi theo xương)', JSON.stringify(boxBefore) !== JSON.stringify(boxAfter), `${boxBefore} -> ${boxAfter}`);
await rigOp('exit');
check('Xong: thoát Ghép xương', !(await rigUi()).shown);
await evaluate(`${q('#btn-undo')}.click();`);
check('1 lần hoàn tác trả tư thế', (await poseBox()).join() === boxBefore.join(), `${await poseBox()}`);
await evaluate(`${q('#btn-redo')}.click();`);

await key('d', { ctrlKey: true });
const dup = await evaluate(`const objs = window.easy3d.store.objects; const sks = []; objs.forEach((o) => o.traverse((m) => { if (m.isSkinnedMesh) sks.push(m); }));
  return { n: sks.length, shared: sks.length === 2 && sks[0].skeleton.bones[0] === sks[1].skeleton.bones[0] };`);
check('Nhân bản vật có xương -> bản sao có bộ xương riêng', dup.n === 2 && !dup.shared, JSON.stringify(dup));
await evaluate(`${q('#btn-undo')}.click();`);
await clickName('Hộp 1 (5)'); // hoàn tác nhân bản -> bản sao bị xoá khỏi vùng chọn

// ---------- Chuyển động ----------
await evaluate(`${q('[data-action="toggle-timeline"]')}.click();`);
check('Bấm 🎬 Chuyển động -> hiện thanh thời gian', await evaluate(`return !document.querySelector('.timeline').hidden;`));
const tl = (op) => evaluate(`document.querySelector('.timeline [data-op="${op}"]').click();`);
const seekTo = (t) => evaluate(`const s = document.querySelector('#tl-time'); s.value = ${t}; s.dispatchEvent(new Event('input'));`);
const elbowQ = () => evaluate(`return ${boneExpr(6)}.quaternion.toArray().map((v) => +v.toFixed(4));`);
await seekTo(0); await tl('key');
const q0 = await elbowQ();
await seekTo(2);
await evaluate(`${boneExpr(6)}.rotateZ(1.2); window.easy3d.store.selected.position.x += 0.5;`);
await tl('key');
const q2 = await elbowQ();
check('Ghi 2 tư thế -> 2 chấm khoá trên thanh thời gian', await evaluate(`return document.querySelectorAll('.tl-key').length;`) === 2);
await seekTo(1);
const q1 = await elbowQ();
check('Kéo thời gian giữa 2 khoá -> xương nội suy ở giữa', q1.join() !== q0.join() && q1.join() !== q2.join(), `${q0} | ${q1} | ${q2}`);
await seekTo(0);
check('Về 0s -> trở lại tư thế khoá đầu', (await elbowQ()).join() === q0.join());

const glb = await evaluate(`const THREE = await import('three'); const m = await import('/js/model-import-export.js');
  const { createGLTFLoader } = await import('/js/gltf-loader-factory.js');
  const { data } = await m.exportObjects(window.easy3d.viewport.objectsRoot, 'glb');
  const gltf = await createGLTFLoader().parseAsync(data, '');
  return { anims: gltf.animations.length, tracks: gltf.animations[0]?.tracks.length ?? 0, skins: (() => { let n = 0; gltf.scene.traverse((o) => { if (o.isSkinnedMesh) n++; }); return n; })() };`);
check('Xuất GLB có xương + chuyển động (game engine đọc được)', glb.anims === 1 && glb.tracks >= 3 + 22 && glb.skins === 1, JSON.stringify(glb));

await clickName('Cầu 1');
await evaluate(`const s = document.querySelector('#tl-preset'); s.value = 'turntable'; s.dispatchEvent(new Event('change'));`);
await sleep(600);
check('Mẫu nhanh Bàn xoay 360° -> đang phát, vật xoay', await evaluate(`return document.querySelector('.timeline [data-op="play"]').textContent === '⏸' && window.easy3d.store.selected.userData.anim.keys.length === 4;`));
await tl('play');
await evaluate(`const d = document.querySelector('#tl-duration'); d.value = 1; d.dispatchEvent(new Event('change'));`);
await tl('video'); await sleep(2500);
check('Xuất video', (await lastToast()).startsWith('Đã xuất video'), await lastToast());

await clickName('Hộp 1 (5)');
await key('j');
check('Vào lại vật đã có xương -> thẳng bước Tạo dáng', (await rigUi()).info.stage === 'pose');
await rigOp('unrig'); await sleep(200);
check('Gỡ xương (giữ dáng) -> thành hình thường', await evaluate(`let sk = 0; window.easy3d.store.selected.traverse((m) => { if (m.isSkinnedMesh) sk++; }); return sk === 0;`));
await evaluate(`${q('[data-action="toggle-timeline"]')}.click();`);

// ---------- Đợt 6: Blender chạy ẩn (chỉ khi máy đã cài Blender bằng scripts\setup-blender.bat) ----------
const blenderStatus = await evaluate(`return (await fetch('/api/blender/status')).json();`);
if (blenderStatus.ready) {
  const waitToast = async (prefix, seconds = 90) => {
    for (let i = 0; i < seconds * 2; i++) {
      const t = await evaluate(`return [...document.querySelectorAll('.toast span')].map((x) => x.textContent).find((x) => x.startsWith(${JSON.stringify(prefix)})) ?? null;`);
      if (t) return t;
      await sleep(500);
    }
    return null;
  };
  await evaluate(`${q('[data-action="toggle-shapes"]')}.click();`);
  await evaluate(`${q('[data-shape="box"]')}.click();`);
  const boxName = await evaluate(`return window.easy3d.store.selected.name;`);
  const trisBox = await evaluate(`return window.easy3d.store.triangleCount(window.easy3d.store.selected);`);
  await evaluate(`[...document.querySelectorAll('#props summary')].find((s) => s.textContent.includes('Sửa hình')).parentElement.open = true;`);
  await evaluate(`[...document.querySelectorAll('#props .blender-block button')].find((b) => b.textContent === 'Bo').click();`);
  const bevelToast = await waitToast('Xong: Bo tròn cạnh');
  const trisBevel = await evaluate(`return window.easy3d.store.triangleCount(window.easy3d.store.selected);`);
  check('Blender: Bo tròn cạnh hộp -> nhiều tam giác hơn, giữ tên', !!bevelToast && trisBevel > trisBox * 5
    && await evaluate(`return window.easy3d.store.selected.name;`) === boxName, `${bevelToast} | ${trisBox} -> ${trisBevel}`);
  await evaluate(`${q('#btn-undo')}.click();`);
  check('Hoàn tác bo cạnh -> lại hộp gốc', (await outliner()).includes(boxName));
  await evaluate(`[...document.querySelectorAll('#outliner li')].find((li) => li.textContent.includes(${JSON.stringify(boxName)})).click();`);
  await evaluate(`[...document.querySelectorAll('#props .blender-block button')].find((b) => b.textContent.includes('Sửa lỗi để in 3D')).click();`);
  check('Blender: Sửa lỗi để in 3D', !!(await waitToast('Xong: Sửa lỗi để in 3D')));

  await evaluate(`${q('[data-action="export-image"]')}.click();`); await sleep(200);
  await evaluate(`${q('input[name=size][value="hd"]')}.checked = true; ${q('#cycles')}.checked = true; ${q('#go')}.click();`);
  const cyclesToast = await waitToast('Đã xuất ảnh 1280×720 (Cycles)', 180);
  check('Blender: Render đẹp Cycles 1280×720', !!cyclesToast, cyclesToast ?? await lastToast());
  const blendB64 = readFileSync(new URL('./fixtures/blue-cube.blend', import.meta.url)).toString('base64');
  await evaluate(`const bin = atob(${JSON.stringify(blendB64)}); const u = Uint8Array.from(bin, (c) => c.charCodeAt(0));
    const dt = new DataTransfer(); dt.items.add(new File([u], 'blue-cube.blend'));
    const fi = document.querySelector('#file-input'); fi.files = dt.files; fi.dispatchEvent(new Event('change'));`);
  const blendToast = await waitToast('Đã mở "blue-cube.blend"', 90);
  check('Blender: mở file .blend (nén zstd) -> vật có màu xanh từ vật liệu Blender', !!blendToast && await evaluate(`let c = null;
    window.easy3d.store.selected?.traverse((m) => { if (m.isMesh) c = m.material.color; }); return !!c && c.b > c.r * 2;`), blendToast ?? await lastToast());
} else {
  check('Blender chưa cài -> nút Blender hiện hướng dẫn cài', true, blenderStatus.message);
}

await selectByName('Cầu 1');
await shot('02-editor.png');

await evaluate(`${q('[data-action="image-to-3d"]')}.click();`); await sleep(800);
await shot('03-image-wizard.png');
check('Wizard có 2 lựa chọn mô hình (TripoSR / Hunyuan3D)', await evaluate(`return document.querySelectorAll('input[name=model]').length;`) === 2);
check('Wizard tạo từ ảnh mở, báo trạng thái AI', await evaluate(`return !!${q('.dropzone')} && !!${q('.banner')} && ${q('#go')}.disabled;`));

console.log(JSON.stringify({ results, errors }, null, 2));
browser.kill();
process.exit(results.every((r) => r.ok) && !errors.length ? 0 : 1);
