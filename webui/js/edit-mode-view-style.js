// Kiểu xem khi "Chỉnh điểm": TỐI GIẢN (mặt phẳng lì, vật khác mờ đi -> nhìn rõ điểm/mặt/cạnh)
// hoặc ĐẸP (vật liệu thật). Người dùng bật/tắt bằng ô "Xem tối giản".
import * as THREE from 'three';
import { createGhosting } from './scene-ghosting.js';

const WHITE = new THREE.Color(1, 1, 1);
const OFFSET = { polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 }; // đẩy mặt ra sau -> lưới/điểm nổi lên

export function createEditViewStyle(store) {
  const ghosting = createGhosting(store);
  let st = null; // { mesh, minimal, simple, pretty, baseColor, hadColors }
  const ghostOthers = (active, on) => (on ? ghosting.on(active) : ghosting.off());

  const api = {
    /** original: vật liệu đầu tiên của mesh (vật gộp nhiều chất liệu -> dùng chất liệu đầu). */
    begin(obj, mesh, original, hadColors) {
      const simple = new THREE.MeshLambertMaterial({ color: WHITE, flatShading: true, ...OFFSET });
      const pretty = Object.assign(original.clone(), { flatShading: true, ...OFFSET });
      st = { obj, mesh, minimal: true, simple, pretty, hadColors, baseColor: original.color?.clone() ?? WHITE.clone() };
      api.setMinimal(true);
    },
    end() {
      ghostOthers(null, false);
      st = null;
    },
    setMinimal(on) {
      st.minimal = on;
      st.mesh.material = on ? st.simple : st.pretty;
      ghostOthers(st.obj, on);
    },
    get minimal() { return st?.minimal ?? true; },
    get baseColor() { return st.baseColor; },
    /** Vật liệu hiện tại (để lấy màu/vertexColors khi kết thúc). */
    get current() { return st.mesh.material; },

    /** Có màu đỉnh (vd. vừa tô màu) -> bật vertexColors; vật vốn không có màu đỉnh thì màu nền trắng. */
    syncColors(hasColor) {
      for (const mat of [st.simple, st.pretty]) {
        mat.vertexColors = hasColor;
        mat.color.copy(hasColor && !st.hadColors ? WHITE : st.baseColor);
        mat.needsUpdate = true;
      }
    },
  };
  return api;
}
