/* Phiên xuất dở trong OPFS — để bị dừng giữa chừng (khoá màn hình, tab bị giết, mất mạng) thì xuất TIẾP được.
   Hình mã hoá theo khúc 10 s (mỗi khúc mở đầu bằng keyframe); khúc xong là ghi ngay:
     xuat_do/<pid>/khuc_NNN.bin (gói nối liền) + khuc_NNN.json ([ts µs, dur µs, key, vị trí, độ dài])
     xuat_do/<pid>/phien.json = {khoa (hash dự án + tuỳ chọn), so_khuc (đã xong), cau_hinh (decoderConfig), luc, ...}
   Trình duyệt không ghi luồng được (createWritable) → giữ khúc trong RAM, không xuất tiếp được (như trước).
   Phiên quá 3 ngày bị xoá (như HET_HAN_PART của tai_len.py). */
const GOC = 'xuat_do';
const HET_HAN_MS = 3 * 24 * 3600 * 1000;
const ten3 = (i) => String(i).padStart(3, '0');

async function thuMucGoc() {
    return (await navigator.storage.getDirectory()).getDirectoryHandle(GOC, { create: true });
}

/* Hash ổn định của dự án + tuỳ chọn xuất: khác → không xuất tiếp được (đã sửa dự án / đổi tuỳ chọn). */
export async function bamKhoa(obj) {
    const b = new TextEncoder().encode(JSON.stringify(obj));
    const h = await crypto.subtle.digest('SHA-256', b);
    return [...new Uint8Array(h)].map((x) => x.toString(16).padStart(2, '0')).join('').slice(0, 32);
}

async function docJson(dir, ten) {
    try { return JSON.parse(await (await (await dir.getFileHandle(ten)).getFile()).text()); } catch (e) { return null; }
}

async function ghiJson(dir, ten, obj) {
    const w = await (await dir.getFileHandle(ten, { create: true })).createWritable();
    await w.write(JSON.stringify(obj));
    await w.close();
}

/* Phiên dở của dự án (null nếu không có / hết hạn). Dọn phiên hết hạn của mọi dự án. */
export async function docPhienDo(pid) {
    try {
        const goc = await thuMucGoc();
        let ra = null;
        for await (const [ten, h] of goc.entries()) {
            if (h.kind !== 'directory') continue;
            const tt = await docJson(h, 'phien.json');
            if (!tt || Date.now() - tt.luc > HET_HAN_MS) { await goc.removeEntry(ten, { recursive: true }).catch(() => {}); continue; }
            if (ten === pid && tt.so_khuc > 0) ra = tt;
        }
        return ra;
    } catch (e) { return null; }
}

export class Phien {
    /* Mở phiên cho pid. Khoá khác / lamLai → xoá phiên cũ, bắt đầu từ đầu. tt.so_khuc = số khúc đã xong. */
    static async mo(pid, khoa, thongTin, lamLai = false) {
        const p = new Phien();
        p.mem = [];
        try {
            const goc = await thuMucGoc();
            let dir = await goc.getDirectoryHandle(pid, { create: true });
            const tt = await docJson(dir, 'phien.json');
            if (!tt || tt.khoa !== khoa || lamLai || Date.now() - tt.luc > HET_HAN_MS) {
                await goc.removeEntry(pid, { recursive: true }).catch(() => {});
                dir = await goc.getDirectoryHandle(pid, { create: true });
                p.tt = { khoa, so_khuc: 0, luc: Date.now(), ...thongTin };
                p.lyDo = tt && tt.so_khuc && !lamLai ? 'dự án hoặc tuỳ chọn xuất đã đổi' : '';
            } else {
                p.tt = tt;
            }
            const fh = await dir.getFileHandle('.thu', { create: true });
            if (typeof fh.createWritable !== 'function') throw new Error('không ghi luồng được');
            p.goc = goc; p.pid = pid; p.dir = dir;
            await p._luu();
        } catch (e) {
            p.dir = null;                        // RAM: không xuất tiếp được
            p.tt = { khoa, so_khuc: 0, luc: Date.now(), ...thongTin };
        }
        return p;
    }

    get luuDuoc() { return !!this.dir; }

    async _luu() { if (this.dir) await ghiJson(this.dir, 'phien.json', { ...this.tt, luc: Date.now() }); }

    /* Bỏ các khúc đã xong, làm lại từ đầu (giữ khoá). */
    async lamLai() {
        if (this.dir) for (let i = 0; i < this.tt.so_khuc; i++) await this._xoaKhuc(i);
        this.mem = [];
        this.tt.so_khuc = 0;
        delete this.tt.cau_hinh;
        await this._luu();
    }

    async _xoaKhuc(i) {
        for (const d of ['bin', 'json']) await this.dir.removeEntry(`khuc_${ten3(i)}.${d}`).catch(() => {});
    }

    /* Bắt đầu ghi khúc i → {them(data, ts, dur, key), dong()}. */
    async ghiKhuc(i) {
        const muc = [];
        if (!this.dir) {
            this.mem[i] = muc;
            return { them: (data, ts, dur, key) => muc.push([ts, dur, key ? 1 : 0, data]), dong: async () => {} };
        }
        await this._xoaKhuc(i);
        const w = await (await this.dir.getFileHandle(`khuc_${ten3(i)}.bin`, { create: true })).createWritable();
        let viTri = 0, chuoi = Promise.resolve(), loi = null;
        return {
            them: (data, ts, dur, key) => {
                muc.push([ts, dur, key ? 1 : 0, viTri, data.byteLength]);
                viTri += data.byteLength;
                chuoi = chuoi.then(() => w.write(data)).catch((e) => { loi = loi || e; });
            },
            dong: async () => {
                await chuoi;
                await w.close();
                if (loi) throw loi;
                await ghiJson(this.dir, `khuc_${ten3(i)}.json`, muc);
            },
        };
    }

    /* Khúc i đã ghi đủ → đánh dấu xong (sau bước này bị dừng thì xuất tiếp từ khúc i + 1). */
    async xongKhuc(i, cauHinh) {
        this.tt.so_khuc = i + 1;
        if (cauHinh && !this.tt.cau_hinh) this.tt.cau_hinh = cauHinh;
        await this._luu();
    }

    /* Mọi gói hình theo thứ tự: {data, ts, dur (µs), key}. */
    async *goi() {
        for (let i = 0; i < this.tt.so_khuc; i++) {
            if (!this.dir) {
                for (const [ts, dur, key, data] of this.mem[i] || []) yield { data, ts, dur, key: !!key };
                continue;
            }
            const ds = await docJson(this.dir, `khuc_${ten3(i)}.json`);
            const f = await (await this.dir.getFileHandle(`khuc_${ten3(i)}.bin`)).getFile();
            if (!ds) throw new Error(`Thiếu khúc ${i + 1} trong bộ nhớ trình duyệt — hãy xuất lại từ đầu.`);
            for (const [ts, dur, key, off, len] of ds) {
                yield { data: new Uint8Array(await f.slice(off, off + len).arrayBuffer()), ts, dur, key: !!key };
            }
        }
    }

    async xoa() {
        this.mem = [];
        if (this.goc) await this.goc.removeEntry(this.pid, { recursive: true }).catch(() => {});
    }
}
