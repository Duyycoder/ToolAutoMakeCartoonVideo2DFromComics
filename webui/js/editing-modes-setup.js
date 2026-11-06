// Khởi tạo các chế độ chỉnh trực tiếp (chỉ 1 cái bật tại 1 lúc): Chỉnh điểm, Tô vẽ, Nặn hình, Ghép xương.
import { createEditMode } from './edit-mode-controller.js';
import { attachEditModeInput } from './edit-mode-input.js';
import { createEditToolbar } from './edit-mode-toolbar.js';
import { createPaintMode } from './paint-mode-controller.js';
import { createImagePlacement } from './paint-image-placement.js';
import { createPaintToolbar } from './paint-mode-toolbar.js';
import { attachSurfaceInput } from './surface-input.js';
import { createSculptMode } from './sculpt-mode-controller.js';
import { createSculptToolbar } from './sculpt-mode-toolbar.js';
import { createRigMode } from './rig-mode-controller.js';
import { attachRigInput, createRigToolbar } from './rig-mode-toolbar.js';
import { createBoneTreePanel } from './rig-bone-tree-panel.js';
import { toast } from './toast-notifications.js';

export function setupEditingModes({ viewport, viewportEl, store, stack, gizmo }) {
  const ctx = { viewport, store, stack, gizmo };
  const bars = {};

  const editMode = createEditMode({ ...ctx, onChange: (info) => bars.edit?.update(info) });
  bars.edit = createEditToolbar(viewportEl, editMode, attachEditModeInput(viewport, editMode, viewportEl));

  const paintMode = createPaintMode({ ...ctx, onChange: (info) => bars.paint?.update(info) });
  const placement = createImagePlacement(viewport, paintMode, viewportEl, () => bars.paint?.update(paintMode.info()));
  attachSurfaceInput(viewport, viewportEl, paintMode.inputAdapter((hex) => {
    paintMode.setBrush({ color: hex, mode: 'paint' });
    toast(`Đã lấy màu ${hex} — kéo để tô.`, { timeout: 2000 });
  }));
  bars.paint = createPaintToolbar(viewportEl, paintMode, placement);

  const sculptMode = createSculptMode({ ...ctx, onChange: (info) => bars.sculpt?.update(info) });
  attachSurfaceInput(viewport, viewportEl, sculptMode.inputAdapter());
  bars.sculpt = createSculptToolbar(viewportEl, sculptMode);

  const rigMode = createRigMode({ ...ctx, onChange: (info) => { bars.rig?.update(info); bars.rigTree?.update(info); } });
  bars.rig = createRigToolbar(viewportEl, rigMode);
  bars.rigTree = createBoneTreePanel(viewportEl, rigMode, { onTemplateSaved: () => bars.rig.refreshSaved() });
  attachRigInput(viewport, rigMode);

  const modes = [editMode, paintMode, sculptMode, rigMode];
  return {
    editMode, paintMode, sculptMode, rigMode,
    /** Thoát chế độ đang bật (lưu lượt chỉnh) trước khi làm việc khác: lưu file, mở file... */
    leaveModes: () => modes.forEach((m) => { if (m.active) m.exit(); }),
    activeMode: () => modes.find((m) => m.active),
  };
}
