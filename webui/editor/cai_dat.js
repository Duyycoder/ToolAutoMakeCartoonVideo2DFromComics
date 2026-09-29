/* ⚙ Cấu hình chung dạng hộp thoại.
 *
 * GĐ 0 nhúng NGUYÊN tab Cấu Hình Chung của giao diện cũ (/cai_dat.html) để
 * giữ đúng cơ chế data-cfg/data-seed/cfg-clone, không phải chép hai nơi. Khi gỡ
 * 5 tab cũ (GĐ 2) mới tách hẳn phần này ra.
 */
export function moCaiDat(khiDong) {
    const nen = document.createElement('div');
    nen.className = 'modal-nen';
    nen.innerHTML = `<div class="modal modal-lon" role="dialog" aria-modal="true" aria-label="Cấu hình chung">
        <div class="modal-dau"><h3>⚙ Cấu hình chung</h3>
            <button class="nut-icon" data-dong title="Đóng (Esc)">✕</button></div>
        <iframe src="/cai_dat.html" title="Cấu hình chung"></iframe></div>`;
    const dong = () => {
        nen.remove();
        document.removeEventListener('keydown', phim);
        if (khiDong) khiDong();
    };
    const phim = (e) => { if (e.key === 'Escape') dong(); };
    nen.addEventListener('click', (e) => {
        if (e.target === nen || e.target.closest('[data-dong]')) dong();
    });
    document.addEventListener('keydown', phim);
    document.body.appendChild(nen);
}
