// Điểm khởi động: nối viewport, store, undo, gizmo, panel, toolbar, phím tắt, kéo thả.
import { createViewport } from './viewport-scene-setup.js';
import { SceneObjectStore } from './scene-object-store.js';
import { CommandStack } from './undo-redo-command-stack.js';
import { createGizmo } from './transform-gizmo-controls.js';
import { createOutliner } from './scene-outliner-panel.js';
import { createPropertiesPanel } from './object-properties-panel.js';
import { createEditorActions } from './editor-actions.js';
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
createPropertiesPanel($('#props'), store, actions);
initStatusBar(store);

const fileInput = $('#file-input');
const openImageWizard = (initialFile = null) => openImageTo3DWizard({
  initialFile,
  onResult: (url, name) => actions.addModelFromUrl(url, name)
    .then(() => toast('Đã tạo mô hình 3D! Bấm vào nó để tô màu, xoay, co giãn.', { type: 'ok', timeout: 7000 })),
});

// ---------- Toolbar & menu ----------
function setMode(mode) {
  gizmo.setMode(mode);
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
  open: () => fileInput.click(),
  save: () => files.save(),
  'toggle-export': () => toggleMenu('#export-menu'),
  'toggle-shapes': () => toggleMenu('#shape-menu'),
  undo: () => { const c = stack.undo(); if (c) toast(`Đã hoàn tác: ${c.label}`, { timeout: 1800 }); },
  redo: () => { const c = stack.redo(); if (c) toast(`Đã làm lại: ${c.label}`, { timeout: 1800 }); },
  help: () => showWelcome(welcomeHandlers),
  'image-to-3d': () => openImageWizard(),
  'frame-all': () => viewport.frameObjects(store.selected ?? viewport.objectsRoot),
};
document.addEventListener('click', (e) => {
  const btn = e.target.closest('button');
  if (!btn?.closest('.menu')) document.querySelectorAll('.menu-list').forEach((m) => { m.hidden = true; });
  if (!btn) return;
  if (btn.dataset.action) ACTIONS[btn.dataset.action]?.();
  if (btn.dataset.mode) setMode(btn.dataset.mode);
  if (btn.dataset.shape) { actions.addShape(btn.dataset.shape); btn.closest('.menu-list').hidden = true; }
  if (btn.dataset.export) { files.export(btn.dataset.export); btn.closest('.menu-list').hidden = true; }
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
  if (!downAt || downAt.b !== 0 || onGizmo) return;
  if (Math.hypot(e.clientX - downAt.x, e.clientY - downAt.y) < 5) store.select(viewport.pick(e.clientX, e.clientY));
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
    s: ctrl && ACTIONS.save, o: ctrl && ACTIONS.open, d: ctrl && sel && (() => actions.duplicate(sel)),
    w: !ctrl && (() => setMode('translate')), e: !ctrl && (() => setMode('rotate')),
    r: !ctrl && (() => setMode('scale')), f: !ctrl && ACTIONS['frame-all'],
    delete: sel && (() => actions.remove(sel)), backspace: sel && (() => actions.remove(sel)),
    escape: () => store.select(null),
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
