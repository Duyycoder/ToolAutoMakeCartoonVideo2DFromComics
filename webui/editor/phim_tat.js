/* Hộp trợ giúp phím tắt của editor — mở bằng phím ? hoặc nút ⌨ trên thanh đầu.
   Danh sách phải khớp bộ xử lý phím trong main.js (ganPhim). */
const NHOM = [
    ['Phát & di chuyển', [
        ['Space', 'Phát / dừng'], ['J · K · L', 'Phát lùi · dừng · phát tới (bấm L nhiều lần để nhanh hơn)'],
        ['← →', 'Lùi / tới 1 khung hình (giữ Shift: 1 giây)'], ['↑ ↓', 'Nhảy tới điểm cắt trước / sau'],
        ['Home · End', 'Về đầu / cuối timeline'], ['Ctrl + cuộn chuột', 'Phóng to / thu nhỏ timeline'],
    ]],
    ['Dựng', [
        ['S', 'Cắt clip tại đầu phát'], ['Q · W', 'Tỉa phần trước / sau đầu phát (giữ Alt: không dồn clip)'],
        ['Delete', 'Xoá clip đang chọn'], ['Shift + Delete', 'Xoá gợn — clip phía sau dồn lên'],
        ['Ctrl + C · X · V', 'Chép · cắt · dán clip'], ['Ctrl + D', 'Nhân đôi clip'], ['Ctrl + A', 'Chọn tất cả'],
        ['Shift + kéo', 'Khoanh chọn nhiều clip'], ['M', 'Đặt điểm đánh dấu tại đầu phát'],
        ['[ · ]', 'Đặt điểm vào / ra của vùng xuất (Alt + [ để xoá vùng)'], ['Esc', 'Bỏ chọn / đóng menu'],
    ]],
    ['Dự án', [
        ['Ctrl + Z', 'Hoàn tác'], ['Ctrl + Y / Ctrl + Shift + Z', 'Làm lại'], ['Ctrl + S', 'Lưu một phiên bản'],
        ['?', 'Mở bảng phím tắt này'],
    ]],
    ['Chuột', [
        ['Chuột phải vào clip', 'Menu clip: tua ngược, đóng băng khung hình, chuyển động, tốc độ, tách âm…'],
        ['Alt + kéo thân clip', 'Slip: trượt đoạn nguồn bên trong, clip đứng yên'],
        ['Alt + kéo mép clip', 'Roll: dời điểm nối với clip nằm sát bên'],
        ['Alt + bấm 🔊 của dòng', 'Solo: chỉ nghe dòng đó (bấm lại để bật tiếng mọi dòng)'],
        ['Kéo file từ máy vào cửa sổ', 'Tải file lên dự án'],
    ]],
];

export function moHopPhimTat() {
    if (document.querySelector('.hop-phim-tat')) return;
    const nen = document.createElement('div');
    nen.className = 'modal-nen hop-phim-tat';
    nen.tabIndex = -1;
    nen.innerHTML = `<div class="modal" style="width:min(760px,100%);max-height:86dvh;overflow:auto">
        <h3>Phím tắt</h3>
        <div class="luoi-phim-tat">${NHOM.map(([ten, ds]) => `<section><h4>${ten}</h4>${ds.map(([p, y]) =>
            `<div class="dong-phim"><kbd>${p}</kbd><span>${y}</span></div>`).join('')}</section>`).join('')}</div>
        <div class="modal-nut"><button type="button" class="nut nut-chinh" data-dong>Đóng</button></div></div>`;
    document.body.appendChild(nen);
    const dong = () => nen.remove();
    nen.addEventListener('click', (e) => { if (e.target === nen || e.target.closest('[data-dong]')) dong(); });
    nen.addEventListener('keydown', (e) => { if (e.key === 'Escape') { e.stopPropagation(); dong(); } });
    nen.focus();
}
