"use strict";
document.addEventListener("DOMContentLoaded", () => {
  const heading=document.querySelector(".page-heading");
  if(!heading || document.getElementById("attribute-review-link")) return;
  const link=document.createElement("a");link.id="attribute-review-link";
  link.className="button button-outline";link.href="product-attributes.html";
  link.textContent="Nhãn tư vấn sản phẩm";heading.append(link);
});
