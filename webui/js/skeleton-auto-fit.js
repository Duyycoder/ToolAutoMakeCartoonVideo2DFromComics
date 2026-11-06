// Tự đặt khớp mẫu Người theo HÌNH THẬT: cắt vật thành lát ngang (theo khung thân), mỗi lát tách các cụm
// liền nhau theo bề ngang -> 2 cụm giữa ở dưới là 2 chân, cụm ngoài cùng tách khỏi thân là tay buông,
// vật rộng ngang (tư thế chữ T) thì dò tay theo bề ngang. Cuối cùng mọi khớp vào GIỮA bề dày (trước-sau).
import { humanTemplate } from './skeleton-templates.js';

const SLICES = 64;

function sliceClusters(frame) {
  const { pts, min, height } = frame;
  const buckets = Array.from({ length: SLICES }, () => []);
  for (let i = 0; i < pts.length; i += 3) {
    buckets[Math.max(0, Math.min(SLICES - 1, Math.floor(((pts[i + 1] - min[1]) / height) * SLICES)))].push(pts[i]);
  }
  const gap = height * 0.02; // khe hở tối thiểu giữa 2 bộ phận
  return buckets.map((us) => {
    us.sort((a, b) => a - b);
    const out = [];
    for (let i = 1, start = 0; i <= us.length; i++) {
      if (i < us.length && us[i] - us[i - 1] <= gap) continue;
      if (i - start >= 4) out.push({ lo: us[start], hi: us[i - 1], c: (us[start] + us[i - 1]) / 2 });
      start = i;
    }
    return out;
  });
}

const quantile = (sorted, q) => sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * q))];

/** Giữa bề dày trước-sau quanh (u, h): bỏ 15% hai đầu (gai, vạt áo) cho khỏi lệch. */
function depthCenter(frame, u, h, r) {
  const { pts } = frame;
  for (let rr = r; rr < frame.height; rr *= 2) {
    const fs = [];
    for (let i = 0; i < pts.length; i += 3) {
      const du = pts[i] - u, dh = pts[i + 1] - h;
      if (du * du + dh * dh < rr * rr) fs.push(pts[i + 2]);
    }
    if (fs.length >= 8) {
      fs.sort((a, b) => a - b);
      return (quantile(fs, 0.15) + quantile(fs, 0.85)) / 2;
    }
  }
  return (frame.min[2] + frame.max[2]) / 2;
}

/** Đưa 1 khớp (toạ độ local) vào giữa bề dày, giữ nguyên vị trí ngang/cao. */
export function centerJointDepth(frame, position) {
  const [u, h] = frame.toFrame(position);
  return frame.toLocal(u, h, depthCenter(frame, u, h, frame.height * 0.04));
}

function findLegs(slices, cu) {
  const legs = [];
  let top = -1;
  for (let k = 0; k < SLICES * 0.65; k++) {
    const cl = slices[k];
    if (!cl.length && k < 2) continue;
    if (!cl.length || cl.some((c) => c.lo <= cu && c.hi >= cu)) break; // hết khe giữa 2 chân = đáy quần
    const L = cl.filter((c) => c.lo > cu).sort((a, b) => a.lo - b.lo)[0]; // cụm trong cùng mỗi bên
    const R = cl.filter((c) => c.hi < cu).sort((a, b) => b.hi - a.hi)[0];
    if (!L || !R) break;
    legs[k] = { L, R };
    top = k;
  }
  return top >= SLICES * 0.12 ? { top, legs } : null;
}

/** Chữ T: vật rộng ngang, nhưng thân (dưới tầm tay) hẹp hơn hẳn — khối hộp/vật tròn không bị nhận nhầm. */
function isTPose(slices, kTorso, cu, width, height) {
  const torso = slices[kTorso].find((c) => c.lo <= cu && c.hi >= cu);
  return width > height * 0.8 && !!torso && torso.hi - torso.lo < width * 0.5;
}

/** Tay buông: cụm ngoài cùng nằm ngoài thân (trên đáy quần) / ngoài chân (dưới đáy quần). */
function findArmDown(slices, side, cu, legs, height) {
  const key = side > 0 ? 'L' : 'R';
  const outer = (k) => {
    const cl = slices[k] ?? [];
    const inner = legs && k <= legs.top ? legs.legs[k]?.[key] : cl.find((c) => c.lo <= cu && c.hi >= cu);
    if (!inner) return null;
    const beyond = cl.filter((c) => (side > 0 ? c.lo > inner.hi : c.hi < inner.lo));
    return beyond.length ? beyond.reduce((a, b) => (side * b.c > side * a.c ? b : a)) : null;
  };
  let kTop = -1;
  for (let k = Math.floor(SLICES * 0.8); k > (legs?.top ?? SLICES * 0.3); k--) if (outer(k)) { kTop = k; break; }
  if (kTop < 0) return null;
  // Đi xuống theo cánh tay; cho phép hụt 2 lát (khuỷu chạm hông), tâm cụm không nhảy quá xa.
  const path = { [kTop]: outer(kTop) };
  let kBot = kTop, miss = 0;
  for (let k = kTop - 1; k >= 0 && miss <= 2; k--) {
    const c = outer(k);
    if (c && Math.abs(c.c - path[kBot].c) < height * 0.12) { path[k] = c; kBot = k; miss = 0; } else miss++;
  }
  if (kTop - kBot < SLICES * 0.15) return null; // quá ngắn: gai/vạt áo, không phải tay
  return { kTop, kBot, path };
}

export function autoFitHuman(frame) {
  const joints = humanTemplate(frame);
  const { min, max, height } = frame;
  if (!(height > 0)) return { joints, report: { legs: false, arms: 'mẫu' } }; // vật phẳng nằm ngang
  const slices = sliceClusters(frame);
  const slab = height / SLICES;
  const hOf = (k) => min[1] + (k + 0.5) * slab;
  const kOf = (h) => Math.max(0, Math.min(SLICES - 1, Math.floor((h - min[1]) / slab)));
  const cu = (min[0] + max[0]) / 2;
  const at = {}; // tên khớp -> [u, h] (f tính sau)
  const legs = findLegs(slices, cu);
  const report = { legs: !!legs, arms: 'mẫu' };

  if (legs) {
    const crotch = hOf(legs.top) + slab / 2;
    const ankle = min[1] + 0.1 * (crotch - min[1]);
    const knee = ankle + 0.5 * (crotch - ankle);
    for (const [side, key] of [['Left', 'L'], ['Right', 'R']]) {
      const uAt = (h) => (legs.legs[Math.min(kOf(h), legs.top)] ?? legs.legs[legs.top])[key].c;
      at[`${side}UpperLeg`] = [uAt(crotch - slab), crotch - slab];
      at[`${side}LowerLeg`] = [uAt(knee), knee];
      at[`${side}Foot`] = [uAt(ankle), ankle];
      at[`${side}Toes`] = [uAt(ankle), min[1] + height * 0.02];
    }
    at.Hips = [cu, crotch + height * 0.05];
  }

  const arms = [1, -1].map((side) => findArmDown(slices, side, cu, legs, height));
  let shoulderH = null;
  if (arms[0] && arms[1]) {
    report.arms = 'buông';
    const hs = [];
    arms.forEach((arm, i) => {
      const side = i ? 'Right' : 'Left', sgn = i ? -1 : 1;
      const top = arm.path[arm.kTop], w = top.hi - top.lo;
      const sh = Math.min(hOf(arm.kTop) + w / 2, max[1] - height * 0.05);
      const len = sh - (hOf(arm.kBot) - slab / 2);
      const uAt = (h) => {
        let k = Math.min(kOf(h), arm.kTop); // vai cao hơn lát trên cùng của tay -> dùng lát trên cùng
        while (!arm.path[k] && k < arm.kTop) k++;
        return arm.path[k].c;
      };
      at[`${side}UpperArm`] = [top.c - sgn * w * 0.15, sh];
      for (const [name, t] of [['LowerArm', 0.42], ['Hand', 0.75], ['Hand_End', 0.93]]) at[side + name] = [uAt(sh - t * len), sh - t * len];
      hs.push(sh);
    });
    shoulderH = (hs[0] + hs[1]) / 2;
  } else if (isTPose(slices, kOf(min[1] + height * 0.6), cu, max[0] - min[0], height)) {
    report.arms = 'chữ T';
    // Tay dang ngang: dọc bề ngang, độ cao = trung vị các điểm (phần trên người) trong dải hẹp.
    const hAtU = (u) => {
      const hs = [];
      for (let i = 0; i < frame.pts.length; i += 3) {
        if (Math.abs(frame.pts[i] - u) < height * 0.02 && frame.pts[i + 1] > min[1] + height * 0.45) hs.push(frame.pts[i + 1]);
      }
      return hs.length ? hs.sort((a, b) => a - b)[hs.length >> 1] : min[1] + height * 0.78;
    };
    const torso = slices[kOf(min[1] + height * 0.6)].find((c) => c.lo <= cu && c.hi >= cu);
    const half = (torso.hi - torso.lo) / 2;
    for (const [side, end] of [['Left', max[0]], ['Right', min[0]]]) {
      const su = cu + Math.sign(end - cu) * half * 0.8;
      for (const [name, t] of [['UpperArm', 0], ['LowerArm', 0.45], ['Hand', 0.8], ['Hand_End', 0.95]]) {
        const u = su + t * (end - su);
        at[side + name] = [u, hAtU(u)];
      }
    }
    shoulderH = (at.LeftUpperArm[1] + at.RightUpperArm[1]) / 2;
  }

  if (legs || shoulderH !== null) {
    const hips = at.Hips?.[1] ?? min[1] + height * 0.5;
    let top = max[1];
    for (let k = SLICES - 1; k > 0; k--) if (slices[k].some((c) => c.lo <= cu && c.hi >= cu)) { top = hOf(k) + slab / 2; break; }
    const sh = shoulderH ?? min[1] + height * 0.78;
    const neck = Math.max(hips + slab * 3, sh + 0.3 * (top - sh));
    const torsoU = (h) => slices[kOf(h)].find((c) => c.lo <= cu && c.hi >= cu)?.c ?? cu;
    Object.assign(at, {
      Hips: [torsoU(hips), hips],
      Spine: [torsoU(hips + 0.31 * (neck - hips)), hips + 0.31 * (neck - hips)],
      Chest: [torsoU(hips + 0.69 * (neck - hips)), hips + 0.69 * (neck - hips)],
      Neck: [torsoU(neck), neck], Head: [torsoU((neck + top) / 2), (neck + top) / 2], HeadTop_End: [torsoU(top - slab), top],
    });
  }

  // Ghép lại: khớp nào dò được thì dùng (u, h) dò; mọi khớp vào giữa bề dày; mũi chân chìa ra trước.
  for (const j of joints) {
    const [u0, h0] = frame.toFrame(j.position);
    const [u, h] = at[j.name] ?? [u0, h0];
    let f = depthCenter(frame, u, h, height * 0.04);
    if (j.name.endsWith('Toes') && at[j.name]) f = toeForward(frame, u, h, f);
    j.position = frame.toLocal(u, h, f);
  }
  return { joints, report };
}

/** Mũi chân: 75% từ cổ chân tới điểm xa nhất phía trước của bàn chân. */
function toeForward(frame, u, h, fAnkle) {
  const { pts, height } = frame;
  let far = fAnkle;
  for (let i = 0; i < pts.length; i += 3) {
    if (Math.abs(pts[i] - u) < height * 0.06 && pts[i + 1] < h + height * 0.04 && pts[i + 2] > far) far = pts[i + 2];
  }
  return fAnkle + 0.75 * (far - fAnkle);
}
