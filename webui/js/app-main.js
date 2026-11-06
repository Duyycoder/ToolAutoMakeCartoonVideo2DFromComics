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
import { createEditMode } from './edit-mode-controller.js';
import { attachEditModeInput } from './edit-mode-input.js';
import { createEditToolbar } from './edit-mode-toolbar.js';
import { createPaintMode } from './paint-mode-controller.js';
import { attachSurfaceInput } from './surface-input.js';
import { createSculptMode } from './sculpt-mode-controller.js';
import { createSculptToolbar } from './sculpt-mode-toolbar.js';
import { createImagePlacement } from './paint-image-placement.js';
import { createPaintToolbar } from './paint-mode-toolbar.js';
import { createProjectFileActions } from './project-file-actions.js';
import { IMAGE_EXTENSIONS, openImageTo3DWizard } from './image-to-3d-wizard.js';
import { shouldShowWelcome, showWelcome } from './welcome-screen.js';
import { initStatusBar } from './status-bar.js';
import { extOf, MODEL_EXTENSIONS } from './model-import-export.js';
import { toast } from './toast-notifications.js';

const $ = (sel) => document.querySelector(sel);
const viewportEl = $('#viewport');
const viewport = createViewport(viewportEl);
const store = new SceneObjectStore(viewport.objectsRoot);
const stack = new CommandStack();
const gizmo = createGizmo(viewport, store, stack);
const actions = createEditorActions({ viewport, store, stack });
const files = createProjectFileActions({ viewport, store, getProjectName: () => $('#project-name').value.trim() });
createOutliner($('#outliner'), store);
const appearance = createAppearanceActions({ viewport, store, stack });
const meshTools = createMeshTools({ store, stack });
createPropertiesPanel($('#props'), store, actions, meshTools, appearance);
initStatusBar(store);
let editToolbar = null;
const editMode = createEditMode({ viewport, store, stack, gizmo, onChange: (info) => editToolbar?.update(info) });
editToolbar = createEditToolbar(viewportEl, editMode, attachEditModeInput(viewport, editMode, viewportEl));
let paintToolbar = null;
const paintMode = createPaintMode({ viewport, store, stack, gizmo, onChange: (info) => paintToolbar?.update(info) });
const placement = createImagePlacement(viewport, paintMode, viewportEl, () => paintToolbar?.update(paintMode.info()));
attachSurfaceInput(viewport, viewportEl, paintMode.inputAdapter((hex) => {
  paintMode.setBrush({ color: hex, mode: 'paint' });
  toast(`Đã lấy màu ${hex} — kéo để tô.`, { timeout: 2000 });
}));
paintToolbar = createPaintToolbar(viewportEl, paintMode, placement);
let sculptToolbar = null;
const sculptMode = createSculptMode({ viewport, store, stack, gizmo, onChange: (info) => sculptToolbar?.update(info) });
attachSurfaceInput(viewport, viewportEl, sculptMode.inputAdapter());
sculptToolbar = createSculptToolbar(viewportEl, sculptMode);
const modes = [editMode, paintMode, sculptMode]; // các chế độ chỉnh trực tiếp (chỉ 1 cái bật tại 1 lúc)
/** Thoát Chỉnh điểm / Tô vẽ (lưu lượt chỉnh) trước khi làm việc khác: lưu file, mở file... */
const leaveModes = () => modes.forEach((m) => { if (m.active) m.exit(); });
const activeMode = () => modes.find((m) => m.active);
// Chỉ cho smoke test (tests/ui-smoke-test.mjs mở ?test=1) đọc vị trí vật/camera để kéo gizmo bằng chuột thật.
if (new URLSearchParams(location.search).has('test')) window.easy3d = { viewport, store, editMode, paintMode, sculptMode };

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
  'toggle-export': () => toggleMenu('#export-menu'),
  'toggle-shapes': () => toggleMenu('#shape-menu'),
  'toggle-lighting': () => toggleMenu('#lighting-menu'),
  'toggle-grid': () => appearance.toggleGrid(),
  'export-image': () => openImageExportDialog({ viewport, onExport: (url, size) => files.saveImage(url, size) }),
  'edit-mode': () => (editMode.active ? editMode.exit() : (leaveModes(), editMode.enter(store.selected))),
  'paint-mode': () => (paintMode.active ? paintMode.exit() : (leaveModes(), paintMode.enter(store.selected))),
  'sculpt-mode': () => (sculptMode.active ? sculptMode.exit() : (leaveModes(), sculptMode.enter(store.selected))),
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
  const keepsEditing = ['undo', 'redo', 'edit-mode', 'paint-mode', 'sculpt-mode', 'help'].includes(btn.dataset.action) || btn.dataset.mode
    || btn.closest('.edit-toolbar') || btn.dataset.action?.startsWith('toggle-');
  if (!keepsEditing) leaveModes();
  if (btn.dataset.action) ACTIONS[btn.dataset.action]?.();
  if (btn.dataset.mode) setMode(btn.dataset.mode);
  if (btn.dataset.shape) actions.addShape(btn.dataset.shape);
  if (btn.dataset.export) files.export(btn.dataset.export);
  if (btn.dataset.lighting) appearance.setLighting(btn.dataset.lighting);
  if (btn.dataset.light) appearance.addLight(btn.dataset.light);
  const menuList = btn.closest('.menu-list');
  if (menuList) menuList.hidden = true; // chọn xong 1 mục thì đóng menu
});
fileInput.onchange = () => {
  if (fileInput.files[0]) actions.openFile(fileInput.files[0]);
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
    tab: () => editMode.enter(store.selected),
    b: !ctrl && (() => { leaveModes(); paintMode.enter(store.selected); }),
    n: !ctrl && (() => { leaveModes(); sculptMode.enter(store.selected); }),
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
  const file = e.dataTransfer.files[0];
  if (!file || document.querySelector('.modal-backdrop')) return;
  const ext = extOf(file.name);
  if (IMAGE_EXTENSIONS.includes(ext)) openImageWizard(file);
  else if (MODEL_EXTENSIONS.includes(ext)) actions.openFile(file);
  else toast(`Không mở được file .${ext}. Hỗ trợ: ảnh PNG/JPG, mô hình GLB/OBJ/STL/FBX.`, { type: 'warn' });
});

// ---------- Màn hình chào ----------
const welcomeHandlers = {
  onImage: () => openImageWizard(),
  // setTimeout: chờ sự kiện click hiện tại lan xong (handler document sẽ đóng mọi menu).
  onShapes: () => { actions.addShape('box'); setTimeout(() => toggleMenu('#shape-menu')); },
  onOpen: () => fileInput.click(),
};
if (shouldShowWelcome()) showWelcome(welcomeHandlers);
