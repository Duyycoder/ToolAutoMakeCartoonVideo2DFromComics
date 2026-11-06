// Mẫu xương tự lưu (thư mục library/rigs/*.json qua backend): toạ độ chuẩn hoá theo KHUNG THÂN
// (-1..1 bề ngang/sâu, 0..1 chiều cao) -> áp được cho nhân vật khác cỡ, khác hướng đặt.
import { api } from './backend-api-client.js';
import { linkJoints } from './skeleton-templates.js';

const extent = ({ min, max }) => ({
  cu: (min[0] + max[0]) / 2, cf: (min[2] + max[2]) / 2,
  hu: (max[0] - min[0]) / 2 || 1, hh: max[1] - min[1] || 1, hf: (max[2] - min[2]) / 2 || 1,
});

export function jointsToTemplate(name, joints, frame) {
  const e = extent(frame);
  return {
    version: 1, name,
    joints: joints.map((j) => {
      const [u, h, f] = frame.toFrame(j.position);
      return { name: j.name, label: j.label, parent: j.parent >= 0 ? joints[j.parent].name : null,
        p: [(u - e.cu) / e.hu, (h - frame.min[1]) / e.hh, (f - e.cf) / e.hf].map((v) => +v.toFixed(4)) };
    }),
  };
}

/** Kiểm tra file mẫu (có thể do người dùng sửa tay) trước khi dùng. */
function validate(tpl) {
  const list = tpl?.joints;
  if (!Array.isArray(list) || list.length < 2 || list.length > 256) throw new Error('File mẫu xương không hợp lệ');
  const names = new Set(list.map((j) => j.name));
  if (names.size !== list.length) throw new Error('File mẫu xương có tên trùng nhau');
  const roots = list.filter((j) => j.parent === null || j.parent === undefined);
  if (roots.length !== 1 || list.some((j) => j.parent && !names.has(j.parent))) throw new Error('File mẫu xương phải có đúng 1 khớp gốc');
  const parentOf = new Map(list.map((j) => [j.name, j.parent ?? null]));
  for (const j of list) { // đi ngược lên gốc: vòng cha-con -> file hỏng
    const seen = new Set();
    for (let n = j.name; n !== null; n = parentOf.get(n)) {
      if (seen.has(n)) throw new Error('File mẫu xương có vòng cha-con');
      seen.add(n);
    }
  }
  if (list.some((j) => typeof j.name !== 'string' || !Array.isArray(j.p) || j.p.length !== 3 || j.p.some((v) => !Number.isFinite(v)))) {
    throw new Error('File mẫu xương thiếu tên hoặc toạ độ');
  }
}

export function templateToJoints(tpl, frame) {
  validate(tpl);
  const e = extent(frame);
  return linkJoints(tpl.joints.map((j) => ({
    name: j.name, label: j.label ?? j.name, parentName: j.parent ?? null,
    position: frame.toLocal(e.cu + j.p[0] * e.hu, frame.min[1] + j.p[1] * e.hh, e.cf + j.p[2] * e.hf),
  })));
}

export const listRigTemplates = () => api.listFiles('rigs');
export const loadRigTemplate = (file) => api.readJson('rigs', file);
export const saveRigTemplate = (tpl) => api.saveFile('rigs', `${tpl.name}.json`, new Blob([JSON.stringify(tpl, null, 1)], { type: 'application/json' }));
