// Khung hộp thoại dùng chung (màn hình chào, wizard). Không dùng alert/confirm của trình duyệt.
export function openModal({ closable = true, onClose = null } = {}) {
  const backdrop = document.createElement('div');
  backdrop.className = 'modal-backdrop';
  const modal = document.createElement('div');
  modal.className = 'modal';
  backdrop.append(modal);
  document.body.append(backdrop);

  let canClose = closable;
  const close = () => {
    backdrop.remove();
    document.removeEventListener('keydown', onKey, true);
    onClose?.();
  };
  const onKey = (e) => {
    if (e.key === 'Escape' && canClose) { e.stopPropagation(); close(); }
  };
  document.addEventListener('keydown', onKey, true);
  backdrop.addEventListener('mousedown', (e) => { if (e.target === backdrop && canClose) close(); });

  return {
    modal,
    close,
    /** Đang chạy việc dài (vd. AI) -> không cho đóng nhầm. */
    setClosable(value) { canClose = value; },
  };
}
