// Đổi tên xương (cả 2 bước) + "Tên chuẩn Unity" (xương gắn bằng bản cũ mang tên tiếng Việt) + đổi tên nhân vật.
// Bước Tạo dáng: đổi tên là 1 bước Undo của app (xương đã nằm trong cảnh).
import { renameCommand } from './scene-edit-commands.js';
import { relinkMirrors, UNITY_NAME_OF_LABEL } from './skeleton-templates.js';
import { boneNameProblem } from './rig-joint-structure.js';
import { toast } from './toast-notifications.js';

export function createRigNaming({ stack, store, getState, place, onChange }) {
  const renameBones = (pairs, label) => stack.execute({
    label,
    do: () => { pairs.forEach(([b, , to]) => { b.name = to; }); onChange(); },
    undo: () => { pairs.forEach(([b, from]) => { b.name = from; }); onChange(); },
  });

  return {
    rename(i, name) {
      const s = getState();
      if (s.stage === 'place') return place.rename(i, name);
      name = name.trim();
      const problem = boneNameProblem(name, s.bones.filter((_, k) => k !== i).map((b) => b.name));
      if (problem) { toast(problem, { type: 'warn', timeout: 6000 }); return false; }
      renameBones([[s.bones[i], s.bones[i].name, name]], 'Đổi tên xương');
      return true;
    },

    /** Xương có nhãn/tên tiếng Việt của mẫu Người -> tên Unity Humanoid (Hips, LeftUpperArm...). */
    unityNames() {
      const s = getState();
      const items = s.stage === 'place' ? s.joints : s.bones.map((b) => ({ name: b.name, label: b.userData.label ?? b.name, bone: b }));
      const target = (it) => UNITY_NAME_OF_LABEL[it.name] ?? UNITY_NAME_OF_LABEL[it.label];
      const todo = items.filter((it) => target(it) && target(it) !== it.name);
      if (!todo.length) return toast('Tên xương đã theo chuẩn Unity (hoặc không phải mẫu Người).', { timeout: 4000 });
      if (s.stage === 'place') {
        place.pushUndo();
        todo.forEach((it) => { it.name = target(it); }); // nhãn tiếng Việt giữ nguyên
        relinkMirrors(s.joints);
        onChange();
      } else {
        todo.forEach((it) => { it.bone.userData.label ??= it.name; });
        renameBones(todo.map((it) => [it.bone, it.name, target(it)]), 'Tên xương chuẩn Unity');
      }
      toast(`Đã đổi ${todo.length} xương sang tên chuẩn Unity Humanoid.`, { type: 'ok' });
    },

    renameObject(name) {
      const s = getState();
      name = name.trim();
      if (!name || name === s.obj.name) return;
      stack.execute(renameCommand(store, s.obj, s.obj.name, name));
      onChange();
    },
  };
}
