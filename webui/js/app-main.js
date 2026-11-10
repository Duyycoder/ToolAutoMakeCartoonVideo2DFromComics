// Điểm khởi động: nối viewport, store, undo, gizmo, panel, toolbar, phím tắt, kéo thả.
import { createViewport } from './viewport-scene-setup.js';
import { SceneObjectStore } from './scene-object-store.js';
import { CommandStack } from './undo-redo-command-stack.js';
import { createGizmo } from './transform-gizmo-controls.js';
import { createOutliner } from './scene-outliner-panel.js';
import { createPropertiesPanel } from './object-properties-panel.js';
import { createEditorActions } from './editor-actions.js';
import { createMeshTools } from './mesh-tools-actions.js';
import { createAppearanceActions } from './appearance-actions.js';
import { openImageExportDialog } from './image-export-dialog.js';
import { setupEditingModes } from './editing-modes-setup.js';
import { createTimelinePanel } from './animation-timeline-panel.js';
import { blenderMessage, blenderReady, refreshBlenderStatus } from './blender-tools-actions.js';
import { createProjectFileActions } from './project-file-actions.js';
import { IMAGE_EXTENSIONS, openImageTo3DWizard } from './image-to-3d-wizard.js';
import { shouldShowWelcome, showWelcome } from './welcome-screen.js';
import { initStatusBar } from './status-bar.js';
import { extOf, MODEL_EXTENSIONS } from './model-import-export.js';
import { createLightingPanel } from './lighting-adjust-panel.js';
import { applyLighting, fitSunToScene } from './lighting-presets.js';
import { toast } from './toast-notifications.js';

const $ = (sel) => document.querySelector(sel);
const viewportEl = $('#viewport');
const viewport = createViewport(viewportEl);
const store = new SceneObjectStore(viewport.objectsRoot);
const stack = new CommandStack();
const gizmo = createGizmo(viewport, store, stack);
// Model tải trên mạng có thể hàng triệu tam giác -> app chậm, Chỉnh điểm/Nặn khó. Gợi ý giảm ngay.
const HEAVY_TRIANGLES = 300000, TARGET_TRIANGLES = 200000;
const warnIfHeavy = (obj) => {
  const tris = store.triangleCount(obj);
  if (tris <= HEAVY_TRIANGLES) return;
  toast(`Mô hình rất nặng (${tris.toLocaleString('vi-VN')} tam giác) nên app có thể chậm. Giảm còn ~200 nghìn? (vẫn giữ màu/texture)`,
    { type: 'warn', timeout: 20000, action: { label: 'Giảm chi tiết', onClick: () => meshTools.simplify(obj, TARGET_TRIANGLES / tris) } });
};
const actions = createEditorActions({ viewport, store, stack, onModelAdded: warnIfHeavy });
const files = createProjectFileActions({ viewport, store, getProjectName: () => $('#project-name').value.trim() });
createOutliner($('#outliner'), store);
const appearance = createAppearanceActions({ viewport, store, stack });
const meshTools = createMeshTools({ store, stack });
createPropertiesPanel($('#props'), store, actions, meshTools, appearance);
initStatusBar(store);
refreshBlenderStatus().then(() => store.changed()); // panel Sửa hình hiện nút Blender khi đã cài
const { editMode, paintMode, sculptMode, rigMode, leaveModes, activeMode } = setupEditingModes({ viewport, viewportEl, store, stack, gizmo });
const timeline = createTimelinePanel(viewportEl, { viewport, store, stack, onVideo: (blob, ext) => files.saveVideo(blob, ext) });
const lightingPanel = createLightingPanel(viewportEl, { viewport, stack });
applyLighting(viewport, 'studio');
let sunFitQueued = false; // cảnh đổi -> nắng + vùng bóng đổ ôm lại cảnh (gộp nhiều lần đổi trong 1 frame)
store.addEventListener('changed', () => {
  if (sunFitQueued) return;
  sunFitQueued = true;
  requestAnimationFrame(() => { sunFitQueued = false; fitSunToScene(viewport); });
});
// Chỉ cho smoke test (tests/ui-smoke-test.mjs mở ?test=1) đọc vị trí vật/camera để kéo gizmo bằng chuột thật.
if (new URLSearchParams(location.search).has('test')) window.easy3d = { viewport, store, editMode, paintMode, sculptMode, rigMode, timeline };

const fileInput = $('#file-input');
const openImageWizard = (initialFile = null) => openImageTo3DWizard({
  initialFile,
  onResult: (url, name) => actions.addModelFromUrl(url, name)
    .then(() => toast('Đã tạo mô hình 3D! Bấm vào nó để tô màu, xoay, co giãn.', { type: 'ok', timeout: 7000 })),
});

// ---------- Toolbar & menu ----------
function setMode(mode) {
  gizmo.setMode(mode);
  if (editMode.active) editMode.setGizmoMode(mode);
  document.querySelectorAll('[data-mode]').forEach((b) => b.classList.toggle('active', b.dataset.mode === mode));
}
const toggleMenu = (id) => {
  const menu = $(id);
  const willOpen = menu.hidden;
  document.querySelectorAll('.menu-list').forEach((m) => { m.hidden = true; });
  menu.hidden = !willOpen;
};
const ACTIONS = {
  new: () => actions.clearScene(),
  open: () => { leaveModes(); fileInput.click(); },
  save: () => { leaveModes(); files.save(); },
  'export-character': () => files.exportCharacter(store.selected),
  'export-character-fbx': () => files.exportCharacter(store.selected, 'fbx'),
  'toggle-export': () => toggleMenu('#export-menu'),
  'toggle-shapes': () => toggleMenu('#shape-menu'),
  'toggle-lighting': () => toggleMenu('#lighting-menu'),
  'toggle-grid': () => appearance.toggleGrid(),
  'lighting-panel': () => lightingPanel.toggle(),
  'toggle-timeline': () => timeline.toggle(),
  'export-image': () => openImageExportDialog({
    viewport, onExport: (url, size, renderBlob) => files.saveImage(url, size, renderBlob),
    frameTarget: () => (store.selection.length ? store.selection : viewport.objectsRoot),
    cycles: { ready: blenderReady(), message: blenderMessage(), render: (opts) => meshTools.blender.render(viewport, opts) },
  }),
  'edit-mode': () => (editMode.active ? editMode.exit() : (leaveModes(), editMode.enter(store.selected))),
  'paint-mode': () => (paintMode.active ? paintMode.exit() : (leaveModes(), paintMode.enter(store.selected))),
  'sculpt-mode': () => (sculptMode.active ? sculptMode.exit() : (leaveModes(), sculptMode.enter(store.selected))),
  'rig-mode': () => (rigMode.active ? rigMode.exit() : (leaveModes(), rigMode.enter(store.selected))),
  undo: () => { if (activeMode()) return activeMode().undo(); const c = stack.undo(); if (c) toast(`Đã hoàn tác: ${c.label}`, { timeout: 1800 }); },
  redo: () => { if (activeMode()) return activeMode().redo(); const c = stack.redo(); if (c) toast(`Đã làm lại: ${c.label}`, { timeout: 1800 }); },
  help: () => showWelcome(welcomeHandlers),
  'image-to-3d': () => openImageWizard(),
  'frame-all': () => viewport.frameObjects(store.selection.length ? store.selection : viewport.objectsRoot),
};
document.addEventListener('click', (e) => {
  const btn = e.target.closest('button');
  if (!btn?.closest('.menu')) document.querySelectorAll('.menu-list').forEach((m) => { m.hidden = true; });
  if (!btn) return;
  // Bấm chức năng khác của app khi đang chỉnh điểm -> lưu lượt chỉnh trước (như bấm "Xong").
  const keepsEditing = ['undo', 'redo', 'edit-mode', 'paint-mode', 'sculpt-mode', 'rig-mode', 'help'].includes(btn.dataset.action) || btn.dataset.mode
    || btn.closest('.edit-toolbar, .timeline') || btn.dataset.action?.startsWith('toggle-'); // tạo dáng rồi Ghi tư thế liền mạch
  if (!keepsEditing) leaveModes();
  if (btn.dataset.action) ACTIONS[btn.dataset.action]?.();
  if (btn.dataset.mode) setMode(btn.dataset.mode);
  if (btn.dataset.shape) actions.addShape(btn.dataset.shape);
  if (btn.dataset.export) files.export(btn.dataset.export);
  if (btn.dataset.lighting) { appearance.setLighting(btn.dataset.lighting); lightingPanel.sync(); }
  if (btn.dataset.light) appearance.addLight(btn.dataset.light);
  const menuList = btn.closest('.menu-list');
  if (menuList) menuList.hidden = true; // chọn xong 1 mục thì đóng menu
});
fileInput.onchange = () => {
  if (fileInput.files.length) actions.openFiles([...fileInput.files]); // mô hình + ảnh texture chọn cùng lúc
  fileInput.value = '';
};
const syncUndoButtons = () => {
  $('#btn-undo').disabled = !stack.canUndo;
  $('#btn-redo').disabled = !stack.canRedo;
};
stack.addEventListener('change', syncUndoButtons);
syncUndoButtons();

// ---------- Chọn vật bằng chuột (bấm nhả tại chỗ, không phải kéo xoay camera) ----------
let downAt = null;
viewport.renderer.domElement.addEventListener('pointerdown', (e) => { downAt = { x: e.clientX, y: e.clientY, b: e.button }; });
viewport.renderer.domElement.addEventListener('pointerup', (e) => {
  const onGizmo = gizmo.consumePointer();
  if (!downAt || downAt.b !== 0 || onGizmo || activeMode()) return; // các chế độ chỉnh trực tiếp tự xử lý chuột
  if (Math.hypot(e.clientX - downAt.x, e.clientY - downAt.y) < 5) {
    const picked = viewport.pick(e.clientX, e.clientY);
    if (e.shiftKey || e.ctrlKey) store.toggleSelect(picked); // Shift + bấm: chọn nhiều
    else store.select(picked);
  }
  downAt = null;
});

// ---------- Phím tắt ----------
document.addEventListener('keydown', (e) => {
  if (e.target.closest?.('input, textarea') || document.querySelector('.modal-backdrop')) return;
  const ctrl = e.ctrlKey || e.metaKey;
  const key = e.key.toLowerCase();
  const sel = store.selected;
  const map = {
    z: ctrl && (e.shiftKey ? ACTIONS.redo : ACTIONS.undo), y: ctrl && ACTIONS.redo,
    s: ctrl && ACTIONS.save, o: ctrl && ACTIONS.open, d: ctrl && sel && (() => actions.duplicateMany([...store.selection])),
    g: ctrl && sel && (() => meshTools.many.group([...store.selection])),
    a: ctrl && (() => store.selectMany(store.objects.filter((o) => o.visible))),
    w: !ctrl && (() => setMode('translate')), e: !ctrl && (() => setMode('rotate')),
    r: !ctrl && (() => setMode('scale')), f: !ctrl && ACTIONS['frame-all'],
    delete: sel && (() => actions.removeMany([...store.selection])),
    backspace: sel && (() => actions.removeMany([...store.selection])),
    escape: () => store.select(null),
    ' ': timeline.visible && (() => (timeline.playing ? timeline.pause() : timeline.play())),
    tab: () => editMode.enter(store.selected),
    b: !ctrl && (() => { leaveModes(); paintMode.enter(store.selected); }),
    n: !ctrl && (() => { leaveModes(); sculptMode.enter(store.selected); }),
    j: !ctrl && (() => { leaveModes(); rigMode.enter(store.selected); }),
  };
  if (map[key]) { e.preventDefault(); map[key](); }
});

// ---------- Kéo thả file vào cửa sổ ----------
const overlay = $('#drop-overlay');
window.addEventListener('dragover', (e) => { e.preventDefault(); if (!document.querySelector('.modal-backdrop')) overlay.hidden = false; });
window.addEventListener('dragleave', (e) => { if (!e.relatedTarget) overlay.hidden = true; });
window.addEventListener('drop', (e) => {
  e.preventDefault();
  overlay.hidden = true;
  const files = [...e.dataTransfer.files];
  if (!files.length || document.querySelector('.modal-backdrop')) return;
  const exts = files.map((f) => extOf(f.name));
  // Có mô hình/zip -> mở mô hình, ảnh thả cùng là texture của nó; chỉ 1 ảnh -> tạo 3D từ ảnh.
  if (exts.some((x) => MODEL_EXTENSIONS.includes(x) || x === 'zip')) actions.openFiles(files);
  else if (IMAGE_EXTENSIONS.includes(exts[0])) openImageWizard(files[0]);
  else toast(`Không mở được file .${exts[0]}. Hỗ trợ: ảnh PNG/JPG, mô hình ${MODEL_EXTENSIONS.join('/').toUpperCase()}, ZIP.`, { type: 'warn' });
});

// ---------- Màn hình chào ----------
const welcomeHandlers = {
  onImage: () => openImageWizard(),
  // setTimeout: chờ sự kiện click hiện tại lan xong (handler document sẽ đóng mọi menu).
  onShapes: () => { actions.addShape('box'); setTimeout(() => toggleMenu('#shape-menu')); },
  onOpen: () => fileInput.click(),
};
if (shouldShowWelcome()) showWelcome(welcomeHandlers);
