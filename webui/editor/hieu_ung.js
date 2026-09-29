export let MA_TRAN_MAU = {};
export const sanSang = typeof process !== 'undefined' && process.versions && process.versions.node
    ? import('fs').then(fs => MA_TRAN_MAU = JSON.parse(fs.readFileSync(new URL('./hieu_ung_mau.json', import.meta.url), 'utf8'))).catch(console.error)
    : fetch(new URL('./hieu_ung_mau.json', import.meta.url)).then(r => r.json()).then(d => MA_TRAN_MAU = d).catch(console.error);

export function cssFilter(mau, hieuUng, tiLeScale = 1) {
    if (!mau && (!hieuUng || !hieuUng.length)) return "none";
    
    let filters = [];
    
    if (mau) {
        let b = 1.0;
        let c = 1.0;
        let s = 1.0;
        
        if (mau.sang) b += mau.sang / 100.0;
        if (mau.tuong_phan) c += mau.tuong_phan / 100.0;
        if (mau.bao_hoa) s += mau.bao_hoa / 100.0;
        if (mau.phoi_sang) b *= (1.0 + mau.phoi_sang / 100.0);
        if (mau.vibrance) s += mau.vibrance / 100.0;
        
        if (b !== 1.0) filters.push(`brightness(${b})`);
        if (c !== 1.0) filters.push(`contrast(${c})`);
        if (s !== 1.0) filters.push(`saturate(${s})`);
        
        if (mau.hue) filters.push(`hue-rotate(${mau.hue}deg)`);
        
        if (mau.nhiet) {
            if (mau.nhiet > 0) {
                filters.push(`sepia(${mau.nhiet}%)`);
            } else {
                filters.push(`hue-rotate(${mau.nhiet / 2}deg) saturate(1.2)`);
            }
        }
    }
    
    if (hieuUng && hieuUng.length) {
        for (let h of hieuUng) {
            if (h.bat === false) continue;
            let do_manh = h.do_manh !== undefined ? h.do_manh : 100;
            let m = do_manh / 100.0;
            let loai = h.loai;
            
            if (MA_TRAN_MAU[loai]) {
                let mat = MA_TRAN_MAU[loai].matrix;
                let off = MA_TRAN_MAU[loai].offset;
                
                let rr = 1.0 + m * (mat[0][0] - 1.0);
                let rg = m * mat[0][1];
                let rb = m * mat[0][2];
                let gr = m * mat[1][0];
                let gg = 1.0 + m * (mat[1][1] - 1.0);
                let gb = m * mat[1][2];
                let br = m * mat[2][0];
                let bg = m * mat[2][1];
                let bb = 1.0 + m * (mat[2][2] - 1.0);
                
                let o_r = m * off[0];
                let o_g = m * off[1];
                let o_b = m * off[2];
                
                let values = `${rr} ${rg} ${rb} 0 ${o_r} ` +
                             `${gr} ${gg} ${gb} 0 ${o_g} ` +
                             `${br} ${bg} ${bb} 0 ${o_b} ` +
                             `0 0 0 1 0`;
                
                let svg = `<svg xmlns="http://www.w3.org/2000/svg"><filter id="f"><feColorMatrix type="matrix" values="${values}"/></filter></svg>`;
                let url = `url("data:image/svg+xml,${encodeURIComponent(svg)}#f")`;
                filters.push(url);
                continue;
            }
            
            switch (loai) {
                case 'grayscale':
                    let g_val = Math.max(0, 1.0 - m);
                    // Dùng hue-rotate và saturate xấp xỉ, hoặc chỉ grayscale
                    filters.push(`grayscale(${m})`);
                    break;
                case 'invert':
                    // Đảo một phần: SVG matrix cho chuẩn xác
                    let inv = 1.0 - 2.0 * m;
                    let v_inv = `${inv} 0 0 0 ${m} 0 ${inv} 0 0 ${m} 0 0 ${inv} 0 ${m} 0 0 0 1 0`;
                    let svg_inv = `<svg xmlns="http://www.w3.org/2000/svg"><filter id="f"><feColorMatrix type="matrix" values="${v_inv}"/></filter></svg>`;
                    filters.push(`url("data:image/svg+xml,${encodeURIComponent(svg_inv)}#f")`);
                    break;
                case 'mo_hop':
                case 'mo_gauss':
                    let blur = (do_manh / 5.0) * tiLeScale; 
                    filters.push(`blur(${blur}px)`);
                    break;
                case 'mosaic':
                    // Dùng SVG filter cho pixelate (xấp xỉ)
                    let k = Math.max(2, do_manh / 2) * tiLeScale;
                    let svg_mos = `<svg xmlns="http://www.w3.org/2000/svg"><filter id="f">` +
                        `<feComponentTransfer><feFuncX type="discrete" tableValues="0 0.5 1"/><feFuncY type="discrete" tableValues="0 0.5 1"/></feComponentTransfer>` +
                        `</filter></svg>`; 
                    // mosaic xấp xỉ
                    filters.push(`blur(${k}px)`);
                    break;
            }
        }
    }
    
    return filters.length ? filters.join(" ") : "none";
}
