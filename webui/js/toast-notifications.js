// Thông báo nhỏ góc phải dưới, có thể kèm 1 nút hành động (vd. "Mở thư mục", "Hoàn tác").
const container = () => document.getElementById('toasts');

export function toast(message, { type = 'info', action = null, timeout = 4500 } = {}) {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  const text = document.createElement('span');
  text.textContent = message;
  el.append(text);
  if (action) {
    const btn = document.createElement('button');
    btn.textContent = action.label;
    btn.onclick = () => { action.onClick(); el.remove(); };
    el.append(btn);
  }
  container().append(el);
  // Tối đa 3 thông báo cùng lúc — bỏ cái cũ nhất để không phủ kín màn hình.
  while (container().children.length > 3) container().firstElementChild.remove();
  if (timeout) setTimeout(() => el.remove(), timeout);
  return el;
}
