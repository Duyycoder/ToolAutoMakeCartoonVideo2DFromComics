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
  ['[data-export="obj"]', 'Đã xuất OBJ'], ['[data-export="png"]', 'Đã chụp ảnh'], ['[data-action="save"]', 'Đã lưu dự án']]) {
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
await shot('02-editor.png');

await evaluate(`${q('[data-action="image-to-3d"]')}.click();`); await sleep(800);
await shot('03-image-wizard.png');
check('Wizard tạo từ ảnh mở, báo trạng thái AI', await evaluate(`return !!${q('.dropzone')} && !!${q('.banner')} && ${q('#go')}.disabled;`));

console.log(JSON.stringify({ results, errors }, null, 2));
browser.kill();
process.exit(results.every((r) => r.ok) && !errors.length ? 0 : 1);
