"use strict";
(() => {
  const api = window.LUMIERE_API;
  const byId = id => document.getElementById(id);
  const state = {ready:false, busy:false, selected:null, options:{}};
  const labels = {Audience:"Đối tượng sử dụng", Style:"Phong cách"};
  const status = (message, error=false) => {
    byId("review-status").textContent = message;
    byId("review-status").style.color = error ? "#9d4232" : "";
  };
  const busy = value => {
    state.busy=value;
    byId("review-editor").disabled=value || !state.ready;
  };
  function canonicalOptions() {
    const select=byId("review-canonical");
    select.replaceChildren(new Option("Chọn nhãn cần xác nhận", ""));
    for (const [value,name] of Object.entries(state.options[byId("review-label").value] || {})) {
      select.add(new Option(name,value));
    }
    byId("review-approved").checked=false;
  }
  async function history() {
    const rows=await api.request(`/admin/products/${state.selected}/verified-attributes`);
    const list=byId("review-history");list.replaceChildren();
    if (!rows.length) {
      const empty=document.createElement("li");empty.textContent="Sản phẩm chưa có nhãn được xác nhận.";list.append(empty);
    }
    for (const row of rows) {
      const item=document.createElement("li");
      const title=document.createElement("strong");
      title.textContent=`${labels[row.label] || row.label}: ${row.name} · ${row.active ? "Đang áp dụng" : "Đã thu hồi"}`;
      const evidence=document.createElement("p");evidence.textContent=`Căn cứ: ${row.source_reference}`;
      const date=document.createElement("p");date.textContent=`Xác nhận: ${new Date(row.reviewed_at).toLocaleString("vi-VN")}`;
      item.append(title,evidence,date);
      if (row.active) {
        const revoke=document.createElement("button");revoke.type="button";revoke.className="button-sm";revoke.textContent="Thu hồi nhãn";
        revoke.addEventListener("click",async () => {
          if(state.busy) return;
          busy(true);
          try {
            await api.request(`/admin/products/${state.selected}/verified-attributes/${row.id}?expected_version=${row.version}`,{method:"DELETE"});
            await history();status("Đã thu hồi nhãn; lịch sử xác nhận vẫn được giữ.");
          } catch(error) {status(error.message,true)} finally {busy(false)}
        });
        item.append(revoke);
      }
      list.append(item);
    }
  }
  async function selectProduct(id) {
    if(state.busy) return;
    busy(true);
    try {
      const product=await api.product(id);
      state.selected=product.id;
      byId("review-product-name").textContent=product.name;
      byId("review-product-info").textContent=`#${product.id} · ${product.sku} · ${Number(product.price_vnd).toLocaleString("vi-VN")} ₫ · Còn ${product.stock}`;
      byId("review-product-link").href=`../product-detail.html?id=${encodeURIComponent(product.id)}`;
      byId("review-source").value="";byId("review-approved").checked=false;
      byId("review-canonical").value="";
      await history();byId("review-detail").hidden=false;
      status("Chọn nhãn và ghi căn cứ bạn đã kiểm tra.");
    } catch(error) {status(error.message,true)} finally {busy(false)}
  }
  byId("review-label").addEventListener("change",canonicalOptions);
  byId("review-search").addEventListener("submit",async event => {
    event.preventDefault();if(state.busy) return;
    busy(true);
    try {
      const result=await api.adminProducts(1,30,byId("review-q").value.trim());
      const list=byId("review-results");list.replaceChildren();
      for (const product of result.items) {
        const item=document.createElement("li");const button=document.createElement("button");
        button.type="button";button.className="button button-outline";
        button.textContent=`#${product.id} · ${product.sku} · ${product.name}`;
        button.addEventListener("click",() => selectProduct(product.id));item.append(button);list.append(item);
      }
      status(result.items.length ? `Tìm thấy ${result.total} sản phẩm; đang hiển thị tối đa 30.` : "Không tìm thấy sản phẩm phù hợp.");
    } catch(error) {status(error.message,true)} finally {busy(false)}
  });
  byId("review-confirm").addEventListener("submit",async event => {
    event.preventDefault();if(state.busy || state.selected===null) return;
    busy(true);
    try {
      await api.request(`/admin/products/${state.selected}/verified-attributes`,{method:"POST",body:JSON.stringify({
        label:byId("review-label").value,canonical_id:byId("review-canonical").value,
        source_reference:byId("review-source").value.trim(),confirmed_review:byId("review-approved").checked
      })});
      byId("review-approved").checked=false;byId("review-source").value="";
      await history();status("Đã lưu nhãn xác nhận.");
    } catch(error) {status(error.message,true)} finally {busy(false)}
  });
  (async () => {
    try {
      const user=await api.me();
      if(user.role!=="admin") {status("Chỉ tài khoản Admin được xác nhận nhãn sản phẩm.",true);return}
      state.options=await api.request("/admin/product-attributes/options");
      const select=byId("review-label");
      for(const label of Object.keys(state.options)) select.add(new Option(labels[label] || label,label));
      canonicalOptions();state.ready=true;busy(false);status("Tìm sản phẩm để bắt đầu xác nhận nhãn.");
    } catch(error) {
      status(error.message==="Not found" ? "Chức năng xác nhận nhãn chưa được bật ở môi trường này." : error.message,true);
      byId("review-login").hidden=false;
    }
  })();
})();
