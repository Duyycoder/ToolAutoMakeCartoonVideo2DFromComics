// Shim tối thiểu của `node:test` để chạy tests/js/*.test.mjs trong trình duyệt khi máy không có Node.
const ds = [];
let hen = null;

export default function test(ten, fn) {
    ds.push({ ten, fn });
    if (!hen) hen = setTimeout(chay, 0);
}

async function chay() {
    const kq = [];
    for (const t of ds) {
        try {
            await t.fn();
            kq.push({ ten: t.ten, ok: true });
        } catch (e) {
            kq.push({ ten: t.ten, ok: false, loi: String((e && e.message) || e) });
        }
    }
    window.__ketQua = kq;
    const hong = kq.filter((k) => !k.ok);
    document.body.innerHTML = `<h3>${kq.length - hong.length}/${kq.length} test đạt</h3>`
        + kq.map((k) => `<div style="color:${k.ok ? 'green' : 'red'}">${k.ok ? '✔' : '✘'} ${k.ten}${k.ok ? '' : ` — ${k.loi}`}</div>`).join('');
}
