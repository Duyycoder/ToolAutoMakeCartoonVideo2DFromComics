// Thanh "🎬 Chuyển động" dưới khung 3D: kéo thời gian, Phát/Dừng, Ghi tư thế, Xoá khoá, mẫu nhanh, xuất video.
// Cách dùng cho người mới: dời/xoay vật (hoặc tạo dáng xương) -> Ghi tư thế -> kéo thời gian -> đổi tư thế -> Ghi tiếp.
import { applyAt, cloneAnim, hasAnimation, keysOf, PRESETS, withKeyRecorded, withKeyRemoved } from './keyframe-animation.js';
import { recordCanvas } from './video-recorder.js';
import { toast } from './toast-notifications.js';

export function createTimelinePanel(viewportEl, { viewport, store, stack, onVideo }) {
  const root = viewport.objectsRoot;
  const bar = Object.assign(document.createElement('div'), { className: 'timeline', hidden: true });
  bar.innerHTML = `
    <button data-op="play" title="Phát / Dừng (phím cách)">▶</button>
    <div class="timeline-track"><input type="range" id="tl-time" min="0" step="0.01" value="0"><div class="tl-keys"></div></div>
    <span class="tl-label" id="tl-label"></span>
    <label class="edit-soft" title="Độ dài (giây)">⏱<input type="number" id="tl-duration" min="1" max="30" step="1" class="num"></label>
    <button data-op="key" class="primary" title="Ghi tư thế hiện tại của vật đang chọn tại thời điểm này">📍 Ghi tư thế</button>
    <button data-op="unkey" title="Xoá khoá tại thời điểm này">🗑 Xoá khoá</button>
    <select id="tl-preset"><option value="">✨ Mẫu nhanh…</option>${Object.entries(PRESETS).map(([k, p]) => `<option value="${k}">${p.label}</option>`).join('')}</select>
    <button data-op="video" title="Quay toàn bộ chuyển động thành video">🎥 Xuất video</button>`;
  viewportEl.append(bar);
  const $ = (sel) => bar.querySelector(sel);
  let playing = false, last = 0, raf = 0;

  const duration = () => root.userData.animDuration ?? 4;
  const time = () => Number($('#tl-time').value);
  const animated = () => store.objects.filter(hasAnimation);

  function seek(t) {
    $('#tl-time').value = t;
    animated().forEach((o) => applyAt(o, t));
    store.transformed();
    render();
  }

  function render() {
    $('#tl-time').max = duration();
    $('#tl-duration').value = duration();
    $('#tl-label').textContent = `${time().toFixed(1)} / ${duration().toFixed(0)} s`;
    $('[data-op="play"]').textContent = playing ? '⏸' : '▶';
    const keys = store.selected ? keysOf(store.selected) : [];
    $('.tl-keys').replaceChildren(...keys.map((k) => {
      const dot = Object.assign(document.createElement('button'), { className: 'tl-key', title: `Khoá tại ${k.t.toFixed(2)} s` });
      dot.style.left = `${(k.t / duration()) * 100}%`;
      dot.onclick = () => seek(k.t);
      return dot;
    }));
  }

  /** Đổi chuyển động của 1 vật thành 1 bước Undo. */
  function setAnim(obj, after, label) {
    const before = cloneAnim(obj);
    const apply = (a) => { if (a) obj.userData.anim = a; else delete obj.userData.anim; render(); };
    stack.execute({ label, do: () => apply(after && JSON.parse(JSON.stringify(after))), undo: () => apply(before) });
  }

  function frame(now) {
    if (!playing) return;
    let t = time() + (now - last) / 1000;
    last = now;
    if (t > duration()) t = 0; // lặp lại
    seek(t);
    raf = requestAnimationFrame(frame);
  }

  const api = {
    get visible() { return !bar.hidden; },
    get playing() { return playing; },
    toggle() { bar.hidden = !bar.hidden; if (bar.hidden) api.pause(); render(); },
    play() { playing = true; last = performance.now(); raf = requestAnimationFrame(frame); render(); },
    pause() { playing = false; cancelAnimationFrame(raf); render(); },
    seek,
    recordKey() {
      const obj = store.selected;
      if (!obj) return toast('Hãy chọn 1 vật trước khi ghi tư thế.', { type: 'warn' });
      setAnim(obj, withKeyRecorded(obj, time()), 'Ghi tư thế');
      toast(`Đã ghi tư thế của "${obj.name}" tại ${time().toFixed(1)} s. Kéo thời gian, đổi tư thế rồi ghi tiếp.`, { type: 'ok' });
    },
    removeKey() {
      if (store.selected) setAnim(store.selected, withKeyRemoved(store.selected, time()), 'Xoá khoá');
    },
    applyPreset(key) {
      const obj = store.selected;
      if (!obj) return toast('Hãy chọn 1 vật trước.', { type: 'warn' });
      setAnim(obj, PRESETS[key].make(obj, duration()), PRESETS[key].label);
      api.play();
    },
    async exportVideo() {
      if (!animated().length) return toast('Chưa có chuyển động nào — hãy Ghi tư thế hoặc chọn Mẫu nhanh.', { type: 'warn' });
      api.pause();
      const helpers = [];
      viewport.scene.traverse((o) => { if (o.userData.editorOnly && o.visible) { o.visible = false; helpers.push(o); } });
      const note = toast(`Đang quay video ${duration()} giây...`, { timeout: 0 });
      try {
        seek(0);
        const recording = recordCanvas(viewport.renderer.domElement, duration());
        api.play();
        const { blob, ext } = await recording;
        await onVideo(blob, ext);
      } catch (err) {
        toast(`Quay video lỗi: ${err.message}`, { type: 'err' });
      } finally {
        api.pause();
        helpers.forEach((o) => { o.visible = true; });
        note.remove();
      }
    },
  };

  $('#tl-time').oninput = () => { api.pause(); seek(time()); };
  $('#tl-duration').onchange = (e) => { root.userData.animDuration = Math.min(30, Math.max(1, Number(e.target.value) || 4)); render(); };
  $('#tl-preset').onchange = (e) => { if (e.target.value) api.applyPreset(e.target.value); e.target.value = ''; };
  const ops = { play: () => (playing ? api.pause() : api.play()), key: api.recordKey, unkey: api.removeKey, video: api.exportVideo };
  bar.addEventListener('click', (e) => { const op = e.target.closest('button')?.dataset.op; if (op) ops[op](); });
  store.addEventListener('selection', render);
  return api;
}
