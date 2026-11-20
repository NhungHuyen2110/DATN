/** Existing controller, shared by Admin and Staff. */
export function createProductsController({ api, esc, money, showError, loadAllProducts }) {
  async function renderProducts(target, section, role) {
    const rows = await loadAllProducts(role === "admin");
    target.innerHTML = `<div class="panel"><p>Giá và tồn kho là dữ liệu Business API. Backend hiện không hỗ trợ tạo/xóa sản phẩm; chỉ sửa trường được API cho phép.</p>
      <div class="toolbar" style="display:flex;gap:12px;flex-wrap:wrap;margin:16px 0">
  <input
    id="product-search"
    type="search"
    placeholder="Tìm tên sản phẩm, SKU hoặc ID..."
    aria-label="Tìm sản phẩm"
    style="flex:1;min-width:240px;padding:10px"
  >
  <select id="product-category" aria-label="Lọc danh mục">
    <option value="">Tất cả danh mục</option>
    ${[...new Set(rows.map(item => item.category?.name || ""))]
      .filter(Boolean)
      .sort((a,b) => a.localeCompare(b,"vi"))
      .map(name => `<option value="${esc(name)}">${esc(name)}</option>`)
      .join("")}
  </select>
</div>
<p id="product-search-count"></p>
<div class="table-wrap"><table class="data-table"><thead><tr><th>ID / SKU</th><th>Sản phẩm</th><th>Danh mục</th><th>Giá</th><th>Tồn kho</th>${section === "inventory" ? "<th>Điều chỉnh</th>" : "<th>Thông tin</th>"}</tr></thead><tbody>
      ${rows.map(item => `<tr><td>${item.id} / ${esc(item.sku)}</td><td>${esc(item.name)}</td><td>${esc(item.category.name)}</td>
      <td>${money(item.price_vnd)}</td><td>${item.stock}</td><td>${section === "inventory"
        ? `<button class="button-sm" data-stock="${item.id}" data-value="${item.stock}">Cập nhật tồn</button>`
        : `<button class="button-sm" data-edit="${item.id}" data-name="${esc(item.name)}" data-price="${item.price_vnd}">Sửa tên / giá</button>`}</td></tr>`).join("")}
      </tbody></table></div></div>`;
    const productSearch = target.querySelector("#product-search");
    const categoryFilter = target.querySelector("#product-category");
    const productCount = target.querySelector("#product-search-count");
    const productTable = target.querySelector(".table-wrap tbody");
    function normalizeProductText(value) {
      return String(value || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/đ/g, "d")
        .replace(/Đ/g, "D")
        .toLocaleLowerCase("vi")
        .trim();
    }
    function filterProducts() {
      const keyword = normalizeProductText(productSearch.value);
      const category = categoryFilter.value;
      let count = 0;
      productTable.querySelectorAll("tr").forEach(row => {
        const identity = row.cells[0]?.textContent || "";
        const name = row.cells[1]?.textContent || "";
        const categoryName = row.cells[2]?.textContent?.trim() || "";
        const searchable = normalizeProductText(
          identity + " " + name
        );
        const match =
          searchable.includes(keyword) &&
          (!category || categoryName === category);
        row.style.display = match ? "" : "none";
        if (match) count++;
      });
      productCount.textContent =
        `Hiển thị ${count} / ${rows.length} sản phẩm`;
      if (count === 0) {
        productCount.textContent += " — Không tìm thấy sản phẩm phù hợp.";
      }
    }
    productSearch.addEventListener("input", filterProducts);
    categoryFilter.addEventListener("change", filterProducts);
    filterProducts();
    if (section === "products" && role === "admin") {
      const addButton = document.createElement("button");
      addButton.type = "button";
      addButton.className = "button button-dark";
      addButton.textContent = "+ Thêm sản phẩm";
      addButton.style.margin = "16px 0";
      target.querySelector(".panel > p")
        .insertAdjacentElement("afterend", addButton);
      const dialog = document.createElement("dialog");
      dialog.style.width = "min(680px, 94vw)";
      dialog.style.maxHeight = "85vh";
      dialog.style.overflowY = "auto";
      dialog.style.padding = "24px";
      const lookupOptions = key => {
        const unique = new Map();
        rows.forEach(item => {
          const value = item[key];
          if (value && !unique.has(value.id)) {
            unique.set(value.id, value.name);
          }
        });
        return [...unique.entries()]
          .sort((a, b) => a[1].localeCompare(b[1], "vi"))
          .map(([id, name]) =>
            `<option value="${id}">${esc(name)}</option>`
          ).join("");
      };
      const nextId = Math.max(0, ...rows.map(p => p.id)) + 1;
      dialog.innerHTML = `
        <h2>Thêm sản phẩm mới</h2>
        <p>Thông tin sẽ được lưu vào PostgreSQL.</p>
        <form id="product-create-form">
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px">
            <label>ID sản phẩm
              <input name="id" type="number" min="1"
                value="${nextId}" required>
            </label>
            <label>SKU
              <input name="sku" maxlength="50" required>
            </label>
            <label>Barcode
              <input name="barcode" maxlength="50" required>
            </label>
            <label>Tên sản phẩm
              <input name="name" maxlength="255" required>
            </label>
            <label>Danh mục
              <select name="category_id" required>
                ${lookupOptions("category")}
              </select>
            </label>
            <label>Thương hiệu
              <select name="brand_id" required>
                ${lookupOptions("brand")}
              </select>
            </label>
            <label>Chất liệu
              <select name="material_id" required>
                ${lookupOptions("material")}
              </select>
            </label>
            <label>Đá
              <select name="gemstone_id" required>
                ${lookupOptions("gemstone")}
              </select>
            </label>
            <label>Bộ sưu tập
              <select name="collection_id" required>
                ${lookupOptions("collection")}
              </select>
            </label>
            <label>Trọng lượng
              <input name="weight" type="number"
                min="0.01" step="0.01" required>
            </label>
            <label>Giá bán (VNĐ)
              <input name="sale_price" type="number"
                min="0" step="0.01" required>
            </label>
            <label>Giá sỉ (VNĐ)
              <input name="wholesale_price" type="number"
                min="0" step="0.01" required>
            </label>
            <label>Giá vốn (VNĐ)
              <input name="cost_price" type="number"
                min="0" step="0.01" required>
            </label>
            <label>Số lượng tồn
              <input name="stock" type="number"
                min="0" step="1" required>
            </label>
          </div>
          <p id="create-product-error"
            role="alert"
            style="color:#b42318;margin-top:12px"></p>
          <div style="display:flex;gap:12px;margin-top:20px">
            <button type="submit" class="button button-dark">
              Lưu sản phẩm
            </button>
            <button type="button" id="cancel-create-product"
              class="button button-outline">
              Hủy
            </button>
          </div>
        </form>
      `;
      target.appendChild(dialog);
      addButton.addEventListener("click", () => {
        dialog.showModal();
      });
      dialog.querySelector("#cancel-create-product")
        .addEventListener("click", () => dialog.close());
      const form = dialog.querySelector("#product-create-form");
      form.addEventListener("submit", async event => {
        event.preventDefault();
        if (form.querySelector('[type="submit"]').disabled) return;
        const data = new FormData(form);
        const numericIds = [
          "id", "category_id", "brand_id",
          "material_id", "gemstone_id", "collection_id", "stock"
        ];
        const prices = [
          "weight", "sale_price", "wholesale_price", "cost_price"
        ];
        const payload = {};
        for (const [key, value] of data.entries()) {
          payload[key] = numericIds.includes(key)
            ? Number(value)
            : prices.includes(key)
              ? String(value)
              : String(value).trim();
        }
        const errorBox = dialog.querySelector("#create-product-error");
        const submit = form.querySelector('[type="submit"]');
        errorBox.textContent = "";
        submit.disabled = true;
        try {
          await api.createProduct(payload);
          dialog.close();
          await renderProducts(target, section, role);
          window.alert("Đã thêm sản phẩm thành công!");
        } catch (error) {
          errorBox.textContent =
            error.message || "Không thể thêm sản phẩm.";
        } finally {
          submit.disabled = false;
        }
      });
    }    target.querySelectorAll("[data-edit]").forEach(button => button.addEventListener("click", async () => {
      const name = window.prompt("Tên sản phẩm:", button.dataset.name);
      if (name === null) return;
      const price = window.prompt("Giá mới (VNĐ):", button.dataset.price);
      if (price === null) return;
      try {
        await api.updateProduct(button.dataset.edit, {
          name: name.trim(),
          sale_price: price,
          expected_sale_price: button.dataset.price
        });
        await renderProducts(target, section, role);
      } catch (error) { showError(target, error); }
    }));
    target.querySelectorAll("[data-stock]").forEach(button => button.addEventListener("click", async () => {
      const stock = window.prompt("Tồn kho mới:", button.dataset.value);
      if (stock === null) return;
      if (!/^\d+$/.test(stock)) { showError(target, new Error("Tồn kho phải là số nguyên không âm.")); return; }
      try {
        await api.updateStock(button.dataset.stock, Number(button.dataset.value), Number(stock));
        await renderProducts(target, section, role);
      } catch (error) { showError(target, error); }
    }));
  }

  return renderProducts;
}
