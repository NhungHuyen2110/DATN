/** Shared escaping, VND display and error panel; DOM structure stays unchanged. */
export const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
}[char]));
export const money = value => Number(value || 0).toLocaleString("vi-VN") + " ₫";
export function showError(target, error) {
  target.innerHTML = `<div class="form-alert" role="alert">${esc(error.message || error)}</div>`;
}
