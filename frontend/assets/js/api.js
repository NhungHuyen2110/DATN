"use strict";

const localHosts = ["localhost", "127.0.0.1"];
const configuredApiBase = window.LUMIERE_API_BASE;
const configuredAiBase = window.LUMIERE_AI_BASE ||
  document.querySelector('meta[name="lumiere-ai-api-base"]')?.content;
window.LUMIERE_AI_BASE = configuredAiBase ||
  (localHosts.includes(window.location.hostname) ? "http://127.0.0.1:8000" : "");

window.LUMIERE_API = {
  base: (configuredApiBase || (
    localHosts.includes(window.location.hostname)
      ? (window.location.port === "8001"
        ? window.location.origin
        : `${window.location.protocol}//${window.location.hostname}:8001`)
      : window.location.origin
  )).replace(/\/$/, ""),

  async request(path, options = {}) {
    let response;
    try {
      response = await fetch(this.base + path, {
        ...options,
        credentials: "include",
        headers: {
          ...(options.body ? { "Content-Type": "application/json" } : {}),
          ...(options.headers || {})
        }
      });
    } catch (error) {
      throw new Error("Không kết nối được Business API. Vui lòng thử lại sau.", { cause: error });
    }

    const body = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) {
      const detail = body?.detail;
      const message = typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map(item => item.msg).filter(Boolean).join("; ")
          : `Yêu cầu thất bại (HTTP ${response.status})`;
      throw new Error(message);
    }
    return body;
  },

  register(data) {
    return this.request("/auth/register", { method: "POST", body: JSON.stringify(data) });
  },
  login(email, password) {
    return this.request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    });
  },
  me() {
    return this.request("/auth/me");
  },
  updateProfile(data) {
    return this.request("/auth/me", { method: "PATCH", body: JSON.stringify(data) });
  },
  logout() {
    return this.request("/auth/logout", { method: "POST" });
  },
  products(page = 1, pageSize = 100, filters = {}) {
    const query = new URLSearchParams({ page, page_size: pageSize, ...filters });
    return this.request("/products?" + query);
  },
  product(id) {
    return this.request("/products/" + encodeURIComponent(id));
  },
  getCart() {
    return this.request("/cart");
  },
  addCartItem(productId, quantity = 1) {
    return this.request("/cart/items", {
      method: "POST",
      body: JSON.stringify({ product_id: productId, quantity })
    });
  },
  updateCartItem(itemId, quantity) {
    return this.request("/cart/items/" + encodeURIComponent(itemId), {
      method: "PATCH",
      body: JSON.stringify({ quantity })
    });
  },
  removeCartItem(itemId) {
    return this.request("/cart/items/" + encodeURIComponent(itemId), { method: "DELETE" });
  },
  createOrder(data) {
    return this.request("/orders", { method: "POST", body: JSON.stringify(data) });
  },
  adminOrders(page = 1, pageSize = 20) {
    return this.request(`/admin/orders?page=${page}&page_size=${pageSize}`);
  },
  staffOrders(page = 1, pageSize = 20) {
    return this.request(`/staff/orders?page=${page}&page_size=${pageSize}`);
  },
  updateOrderStatus(id, status, role) {
    const area = role === "admin" ? "admin" : "staff";
    return this.request(`/${area}/orders/${encodeURIComponent(id)}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status })
    });
  },
  confirmCod(id, collectionReference, role) {
    const area = role === "admin" ? "admin" : "staff";
    return this.request(`/${area}/orders/${encodeURIComponent(id)}/cod/confirm`, {
      method: "POST",
      body: JSON.stringify({ collection_reference: collectionReference })
    });
  },
  adminProducts(page = 1, pageSize = 100, search = "") {
    const query = new URLSearchParams({ page, page_size: pageSize });
    if (search) query.set("q", search);
    return this.request("/admin/products?" + query);
  },
  createProduct(data) {
    return this.request("/admin/products", {
      method: "POST",
      body: JSON.stringify(data)
    });
  },  updateProduct(id, data) {
    return this.request(`/admin/products/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(data)
    });
  },
  updateStock(id, expectedStock, stock) {
    return this.request(`/staff/products/${encodeURIComponent(id)}/stock`, {
      method: "PATCH",
      body: JSON.stringify({ expected_stock: expectedStock, stock })
    });
  },
  adminCustomers(page = 1, pageSize = 20, filters = {}) {
    const query = new URLSearchParams({ page, page_size: pageSize });
    if (filters.search) query.set("search", filters.search);
    if (filters.is_active !== undefined) query.set("is_active", filters.is_active);
    return this.request("/admin/customers?" + query);
  },
  customer(id) {
    return this.request(`/admin/customers/${encodeURIComponent(id)}`);
  },
  setCustomerStatus(id, isActive) {
    return this.request(`/admin/customers/${encodeURIComponent(id)}/status`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: isActive })
    });
  },
  adminStaff(page = 1, pageSize = 20) {
    return this.request(`/admin/staff?page=${page}&page_size=${pageSize}`);
  },
  createStaff(data) {
    return this.request("/admin/staff", { method: "POST", body: JSON.stringify(data) });
  },
  updateStaff(id, data) {
    return this.request(`/admin/staff/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(data)
    });
  },
  setStaffStatus(id, isActive) {
    return this.request(`/admin/staff/${encodeURIComponent(id)}/status`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: isActive })
    });
  },
  dashboard() {
    return this.request("/admin/dashboard");
  },
  revenue(startDate, endDate, groupBy = "day") {
    const query = new URLSearchParams({
      start_date: startDate,
      end_date: endDate,
      group_by: groupBy
    });
    return this.request("/admin/reports/revenue?" + query);
  },
  adminCoupons(page = 1, pageSize = 20, filters = {}) {
    const query = new URLSearchParams({ page, page_size: pageSize });
    if (filters.search) query.set("search", filters.search);
    if (filters.is_active !== undefined) query.set("is_active", filters.is_active);
    return this.request("/admin/coupons?" + query);
  },
  createCoupon(data) {
    return this.request("/admin/coupons", { method: "POST", body: JSON.stringify(data) });
  },
  updateCoupon(id, data) {
    return this.request(`/admin/coupons/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(data)
    });
  },
  setCouponStatus(id, isActive) {
    return this.request(`/admin/coupons/${encodeURIComponent(id)}/status`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: isActive })
    });
  },
  validateCoupon(code) {
    return this.request("/checkout/coupon/validate", {
      method: "POST",
      body: JSON.stringify({ coupon_code: code })
    });
  },
  wishlist(page = 1, pageSize = 100) {
    return this.request(`/wishlist?page=${page}&page_size=${pageSize}`);
  },
  addWishlist(productId) {
    return this.request("/wishlist/items", {
      method: "POST",
      body: JSON.stringify({ product_id: productId })
    });
  },
  removeWishlist(productId) {
    return this.request(`/wishlist/items/${encodeURIComponent(productId)}`, { method: "DELETE" });
  },
  reviews(productId, page = 1, pageSize = 20) {
    const path = productId === undefined ? "/reviews/my" : `/products/${encodeURIComponent(productId)}/reviews`;
    return this.request(`${path}?page=${page}&page_size=${pageSize}`);
  },
  createReview(productId, data) {
    return this.request(`/products/${encodeURIComponent(productId)}/reviews`, {
      method: "POST",
      body: JSON.stringify(data)
    });
  },
  updateReview(id, data) {
    return this.request(`/reviews/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(data)
    });
  },
  deleteReview(id) {
    return this.request(`/reviews/${encodeURIComponent(id)}`, { method: "DELETE" });
  }
};
