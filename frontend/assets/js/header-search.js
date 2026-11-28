"use strict";

(() => {
  const HISTORY_KEY = "lumiere_search_history";
  const HISTORY_LIMIT = 8;

  const root = document.body.dataset.root || "./";

  const suggestions = [
    "Nhẫn",
    "Dây chuyền",
    "Kim cương",
    "Vàng 18K",
    "Bạc 925",
    "Bông tai",
  ];

  const normalize = (value) =>
    String(value ?? "")
      .toLocaleLowerCase("vi")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/đ/g, "d")
      .trim();

  const esc = (value) =>
    String(value ?? "").replace(
      /[&<>"']/g,
      (char) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[char],
    );

  const money = (value) => Number(value || 0).toLocaleString("vi-VN") + " ₫";

  const searchIcon = `
    <svg viewBox="0 0 24 24"
         fill="none"
         stroke="currentColor"
         stroke-width="1.5"
         aria-hidden="true">
      <circle cx="10.7" cy="10.7" r="6.6"/>
      <path d="m16 16 5 5"/>
    </svg>`;

  const historyIcon = `
    <svg viewBox="0 0 24 24"
         fill="none"
         stroke="currentColor"
         stroke-width="1.5"
         aria-hidden="true">
      <circle cx="12" cy="12" r="9"/>
      <path d="M12 7v5l3 2"/>
    </svg>`;

  function getHistory() {
    try {
      const data = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");

      return Array.isArray(data)
        ? data
            .filter((item) => typeof item === "string")
            .slice(0, HISTORY_LIMIT)
        : [];
    } catch {
      return [];
    }
  }

  function saveHistory(items) {
    try {
      localStorage.setItem(
        HISTORY_KEY,
        JSON.stringify(items.slice(0, HISTORY_LIMIT)),
      );
    } catch {
      // Vẫn cho phép tìm kiếm nếu storage không khả dụng.
    }
  }

  function remember(query) {
    const value = query.trim().slice(0, 100);

    if (!value) return;

    const items = getHistory().filter(
      (item) => normalize(item) !== normalize(value),
    );

    saveHistory([value, ...items]);
  }

  function searchUrl(query) {
    const url = new URL(root + "pages/products.html", location.href);

    url.searchParams.set("q", query);

    return url.href;
  }

  function search(query) {
    const value = query.trim().slice(0, 100);

    if (!value) return;

    remember(value);
    location.href = searchUrl(value);
  }

  function findProducts(query) {
    const keyword = normalize(query);

    if (!keyword) return [];

    const products = window.LUMIERE_PRODUCTS || [];

    return products.filter((product) => {
      const searchable = normalize(
        `${product.name} ${product.category} ` +
          `${product.material} ${product.gem} ` +
          `${product.brand} ${product.collection || ""} ` +
          `${product.sku || ""}`,
      );

      return searchable.includes(keyword);
    });
  }

  function mountSearch(mount, index) {
    if (mount.dataset.mounted) return;

    mount.dataset.mounted = "true";

    const panelId = `header-search-panel-${index}`;
    const inputId = `header-search-input-${index}`;

    mount.innerHTML = `
      <div class="lumiere-header-search">

        <form class="header-search-form"
              role="search">

          <input id="${inputId}"
                 class="header-search-input"
                 type="search"
                 placeholder="Tìm kiếm..."
                 aria-label="Tìm kiếm trang sức"
                 aria-controls="${panelId}"
                 autocomplete="off"
                 maxlength="100">

          <button class="header-search-submit"
                  type="submit"
                  aria-label="Tìm kiếm">
            ${searchIcon}
          </button>

        </form>

        <div id="${panelId}"
             class="header-search-panel"
             hidden>

          <div class="header-search-body"></div>

        </div>

      </div>`;

    const widget = mount.querySelector(".lumiere-header-search");

    const input = mount.querySelector(".header-search-input");

    const form = mount.querySelector(".header-search-form");

    const panel = mount.querySelector(".header-search-panel");

    const body = mount.querySelector(".header-search-body");

    const params = new URLSearchParams(location.search);

    input.value = (params.get("q") || "").slice(0, 100);

    let timer;

    function closePanel() {
      clearTimeout(timer);
      panel.hidden = true;
      widget.classList.remove("is-open");
    }

    function renderHistory() {
      const history = getHistory();

      body.innerHTML = `
        <section class="hs-section">

          <div class="hs-section-head">

            <h3>Tìm kiếm gần đây</h3>

            ${
              history.length
                ? `
              <button type="button"
                      class="hs-clear-all">
                Xóa tất cả
              </button>
            `
                : ""
            }

          </div>

          <div class="hs-history-list">

            ${
              history.length
                ? history
                    .map(
                      (term) => `
              <div class="hs-history-row">

                <button type="button"
                        class="hs-history-query"
                        data-search-query="${esc(term)}">

                  ${historyIcon}

                  <span>${esc(term)}</span>

                </button>

                <button type="button"
                        class="hs-remove-history"
                        data-remove-history="${esc(term)}"
                        aria-label="Xóa ${esc(term)}">
                  ×
                </button>

              </div>
            `,
                    )
                    .join("")
                : `
              <p class="hs-empty">
                Chưa có lịch sử tìm kiếm.
              </p>
            `
            }

          </div>

        </section>

        <section class="hs-section hs-suggestions">

          <h3>Gợi ý tìm kiếm</h3>

          <div class="hs-suggestion-list">

            ${suggestions
              .map(
                (term) => `
              <button type="button"
                      data-search-query="${esc(term)}">
                ${esc(term)}
              </button>
            `,
              )
              .join("")}

          </div>

        </section>`;
    }

    function renderResults(query) {
      const matches = findProducts(query);
      const items = matches.slice(0, 4);

      if (window.LUMIERE_PRODUCTS_ERROR) {
        body.innerHTML = `
          <p class="hs-empty">
            Chưa tải được danh sách sản phẩm.
          </p>`;
        return;
      }

      body.innerHTML = `
        <section class="hs-section">

          <div class="hs-section-head">
            <h3>Sản phẩm phù hợp</h3>
            <span class="hs-count">
              ${matches.length} kết quả
            </span>
          </div>

          <div class="hs-product-list">

            ${
              items.length
                ? items
                    .map(
                      (product) => `
              <a class="hs-product"
                 data-search-product
                 href="${esc(root)}pages/product-detail.html?id=${encodeURIComponent(product.id)}">

                <img src="${esc(product.image)}"
                     alt="${esc(product.name)}"
                     loading="lazy">

                <div class="hs-product-info">

                  <strong>
                    ${esc(product.name)}
                  </strong>

                  <small>
                    ${esc(product.category)} ·
                    ${esc(product.material)}
                  </small>

                  <span>
                    ${money(product.price)}
                  </span>

                </div>

                <span class="hs-product-arrow"
                      aria-hidden="true">›</span>

              </a>
            `,
                    )
                    .join("")
                : `
              <p class="hs-empty">
                Không tìm thấy sản phẩm phù hợp.
                Bạn hãy thử từ khóa khác.
              </p>
            `
            }

          </div>

          ${
            items.length
              ? `
            <button type="button"
                    class="hs-view-all"
                    data-search-query="${esc(query)}">

              <span>
                Xem tất cả ${matches.length} kết quả
              </span>

              <span aria-hidden="true">→</span>

            </button>
          `
              : ""
          }

        </section>`;
    }

    function renderPanel() {
      const query = input.value.trim();

      if (query) {
        renderResults(query);
      } else {
        renderHistory();
      }
    }

    function openPanel() {
      panel.hidden = false;
      widget.classList.add("is-open");
      renderPanel();
    }

    input.addEventListener("focus", openPanel);
    input.addEventListener("click", openPanel);

    input.addEventListener("input", () => {
      clearTimeout(timer);

      panel.hidden = false;
      widget.classList.add("is-open");

      timer = setTimeout(renderPanel, 200);
    });

    form.addEventListener("submit", (event) => {
      event.preventDefault();

      if (input.value.trim()) {
        search(input.value);
      } else {
        input.focus();
        openPanel();
      }
    });

    panel.addEventListener("click", (event) => {
      const target = event.target;

      if (target.closest(".hs-clear-all")) {
        saveHistory([]);
        renderHistory();
        input.focus();
        return;
      }

      const remove = target.closest("[data-remove-history]");

      if (remove) {
        const term = remove.dataset.removeHistory;

        saveHistory(getHistory().filter((item) => item !== term));

        renderHistory();
        input.focus();
        return;
      }

      const queryButton = target.closest("[data-search-query]");

      if (queryButton) {
        search(queryButton.dataset.searchQuery);
        return;
      }

      if (target.closest("[data-search-product]")) {
        remember(input.value);
      }
    });

    document.addEventListener("click", (event) => {
      if (!widget.contains(event.target)) {
        closePanel();
      }
    });

    widget.addEventListener("focusout", (event) => {
      if (event.relatedTarget && !widget.contains(event.relatedTarget)) {
        closePanel();
      }
    });

    widget.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        input.focus();
        closePanel();
      }
    });
  }

  /* ========================================
   SHARED PRODUCT MEGA MENU
   ======================================== */

  function mountMegaMenu() {
    const link = document.querySelector("[data-mega-products]");

    if (!link || link.closest(".lumiere-mega-menu")) {
      return;
    }

    const wrapper = document.createElement("div");

    wrapper.className = "lumiere-mega-menu";

    link.before(wrapper);
    wrapper.appendChild(link);

    link.classList.add("mega-products-link");

    wrapper.insertAdjacentHTML(
      "beforeend",
      `
    <button type="button"
            class="mega-toggle"
            aria-label="Mở menu sản phẩm"
            aria-expanded="false"
            aria-controls="lumiere-mega-panel">

      <svg viewBox="0 0 24 24"
           fill="none"
           aria-hidden="true">
        <path d="m6 9 6 6 6-6"/>
      </svg>

    </button>

    <div id="lumiere-mega-panel"
         class="mega-panel"
         hidden>

      <div class="mega-columns"></div>

      <div class="mega-footer">

        <span>
          Vẻ đẹp tinh tế, dấu ấn riêng của bạn.
        </span>

        <a href="${root}pages/products.html">
          Khám phá tất cả →
        </a>

      </div>

    </div>
  `,
    );

    const toggle = wrapper.querySelector(".mega-toggle");
    const panel = wrapper.querySelector(".mega-panel");
    const columns = wrapper.querySelector(".mega-columns");

    const groups = [
      {
        title: "Loại trang sức",
        field: "category",
      },
      {
        title: "Bộ sưu tập",
        field: "collection",
      },
      {
        title: "Chất liệu",
        field: "material",
      },
    ];

    function filterUrl(field, value) {
      const url = new URL(root + "pages/products.html", location.href);

      url.searchParams.set(field, value);

      return url.href;
    }

    function renderMenu() {
      const products = window.LUMIERE_PRODUCTS || [];

      columns.innerHTML = groups
        .map((group) => {
          const values = [
            ...new Set(
              products.map((product) => product[group.field]).filter(Boolean),
            ),
          ].sort((a, b) => a.localeCompare(b, "vi"));

          return `
        <div class="mega-column">

          <h3>${esc(group.title)}</h3>

          <div class="mega-links">

            ${
              group.field === "category"
                ? `
              <a href="${root}pages/products.html"
                 class="mega-all">
                Tất cả sản phẩm
              </a>
            `
                : ""
            }

            ${values
              .map(
                (value) => `
              <a href="${esc(filterUrl(group.field, value))}">
                ${esc(value)}
              </a>
            `,
              )
              .join("")}

            ${
              values.length === 0
                ? `
              <p class="mega-loading">
                ${
                  window.LUMIERE_PRODUCTS_ERROR
                    ? "Chưa tải được danh mục."
                    : "Đang tải danh mục..."
                }
              </p>
            `
                : ""
            }

          </div>

        </div>
      `;
        })
        .join("");
    }

    let closeTimer;
    let refreshTimer;

    function closeMenu() {
      clearTimeout(closeTimer);
      clearInterval(refreshTimer);

      panel.hidden = true;

      wrapper.classList.remove("is-open");

      toggle.setAttribute("aria-expanded", "false");
    }

    function openMenu() {
      clearTimeout(closeTimer);
      clearInterval(refreshTimer);

      renderMenu();

      panel.hidden = false;

      wrapper.classList.add("is-open");

      toggle.setAttribute("aria-expanded", "true");

      // Chờ dữ liệu từ luồng tải sản phẩm hiện tại,
      // không gọi thêm API.
      if (!(window.LUMIERE_PRODUCTS || []).length) {
        let attempts = 0;

        refreshTimer = setInterval(() => {
          attempts++;

          if (
            (window.LUMIERE_PRODUCTS || []).length ||
            window.LUMIERE_PRODUCTS_ERROR ||
            attempts >= 40
          ) {
            renderMenu();
            clearInterval(refreshTimer);
          }
        }, 250);
      }
    }

    wrapper.addEventListener("mouseenter", () => {
      if (window.matchMedia("(min-width: 761px) and (hover: hover)").matches) {
        openMenu();
      }
    });

    wrapper.addEventListener("mouseleave", () => {
      if (window.matchMedia("(min-width: 761px) and (hover: hover)").matches) {
        closeTimer = setTimeout(closeMenu, 160);
      }
    });

    toggle.addEventListener("click", () => {
      if (panel.hidden) {
        openMenu();
      } else {
        closeMenu();
      }
    });

    document.addEventListener("click", (event) => {
      if (!wrapper.contains(event.target)) {
        closeMenu();
      }
    });

    wrapper.addEventListener("focusout", (event) => {
      if (event.relatedTarget && !wrapper.contains(event.relatedTarget)) {
        closeMenu();
      }
    });

    wrapper.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeMenu();
        toggle.focus();
      }
    });

    panel.addEventListener("click", (event) => {
      if (event.target.closest("a")) {
        closeMenu();
      }
    });
  }

  function init() {
    document.querySelectorAll(".header-search-mount").forEach(mountSearch);

    mountMegaMenu();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
