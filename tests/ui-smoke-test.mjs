// Smoke test giao diện: mở Easy3D trong Edge/Chrome headless (DevTools Protocol), thao tác như người dùng,
// bắt lỗi console, chụp ảnh màn hình.
//   1) chạy backend:  .venv\Scripts\python.exe -m uvicorn backend.main:app --port 8200
//   2) node tests/ui-smoke-test.mjs [thư-mục-ảnh-chụp]
import { spawn } from 'node:child_process';
import { existsSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const APP = 'http://127.0.0.1:8200/';
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
await evaluate(`${q('.swatch[title="#ff5c5c"]')}.click();`);
check('Đổi màu đỏ', await evaluate(`return ${q('.swatch.current')}?.title;`) === '#ff5c5c');
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
  const simp = S.simplifyGeometry(sphere, 0.3);
  const two = M.unifyAttributes([new THREE.BoxGeometry().toNonIndexed().translate(-2, 0, 0), new THREE.BoxGeometry().translate(2, 0, 0)]);
  const { mergeGeometries } = await import('three/addons/utils/BufferGeometryUtils.js');
  const parts = M.splitLooseParts(mergeGeometries(two.map((g) => g.index ? g : g.setIndex([...Array(g.attributes.position.count).keys()]))));
  const carved = M.booleanGeometry(new THREE.BoxGeometry(1, 1, 1), new THREE.SphereGeometry(0.7, 32, 16), 'subtract');
  return { smoothVerts: smooth.attributes.position.count, smoothSize: sz.x, sphereTris: S.triangleCountOf(sphere),
           simpTris: S.triangleCountOf(simp), parts: parts.length, carvedVerts: carved.attributes.position.count };`);
check('Làm mượt hộp: chia nhỏ lưới + bo tròn, không teo quá', pure.smoothVerts > 1000 && pure.smoothSize > 0.75 && pure.smoothSize < 1.01, JSON.stringify(pure));
check('Giảm chi tiết cầu còn ~30%', pure.simpTris < pure.sphereTris * 0.45, `${pure.sphereTris} -> ${pure.simpTris}`);
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
await selectByName('Cầu 1');
await shot('02-editor.png');

await evaluate(`${q('[data-action="image-to-3d"]')}.click();`); await sleep(800);
await shot('03-image-wizard.png');
check('Wizard tạo từ ảnh mở, báo trạng thái AI', await evaluate(`return !!${q('.dropzone')} && !!${q('.banner')} && ${q('#go')}.disabled;`));

console.log(JSON.stringify({ results, errors }, null, 2));
browser.kill();
process.exit(results.every((r) => r.ok) && !errors.length ? 0 : 1);
