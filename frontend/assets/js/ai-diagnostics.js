"use strict";
(async () => {
  const form = document.querySelector('#diagnostics-form');
  const status = document.querySelector('#diagnostics-status');
  try {
    const user = await window.LUMIERE_API.me();
    if (user.role !== 'admin') {
      window.location.replace(user.role === 'staff' ? '../staff/orders.html' : '../products.html');
      return;
    }
    form.hidden = false;
    status.textContent = 'Chỉ sử dụng dữ liệu catalog công khai; không hiển thị thông tin khách hàng hoặc giá vốn.';
  } catch (error) {
    window.location.replace('../login.html');
    return;
  }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    status.textContent = 'Đang truy xuất và đối soát dữ liệu...';
    document.querySelector('#diagnostics-output').hidden = true;
    try {
      const result = await window.LUMIERE_API.request('/admin/ai/retrieval-diagnostics', {
        method: 'POST', body: JSON.stringify({ query: document.querySelector('#query').value,
          top_k: Number(document.querySelector('#top-k').value), rerank: document.querySelector('#rerank').checked,
          semantic_entities: document.querySelector('#semantic-entities').checked })
      });
      document.querySelector('#diagnostics-json').textContent = JSON.stringify(result, null, 2);
      document.querySelector('#diagnostics-output').hidden = false;
      status.textContent = `Trạng thái: ${result.status} · ${result.returned_k} sản phẩm.`;
    } catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  });
})();
