const API_URL = "http://127.0.0.1:8000";


// ============================================================
// FORMAT GIÁ
// ============================================================

function formatPrice(price) {

    return Number(price).toLocaleString("vi-VN") + " VNĐ";

}


// ============================================================
// LOAD PRODUCTS
// ============================================================

async function loadProducts() {

    const container =
        document.getElementById("productList");


    try {

        const response =
            await fetch(
                `${API_URL}/products`
            );


        if (!response.ok) {

            throw new Error(
                "Không thể kết nối API"
            );

        }


        const result =
            await response.json();


        if (!result.success) {

            throw new Error(
                "API không trả về dữ liệu"
            );

        }


        container.innerHTML = "";


        result.data.forEach(product => {

            const card =
                document.createElement("div");


            card.className =
                "product-card";


            card.innerHTML = `

                <div class="product-image-wrapper">

                    <img
                        src="images/${product.ProductID}.jpg"
                        alt="${product.ProductName}"
                        class="product-image"
                        onerror="this.src='images/no-image.jpg'"
                    >

                </div>


                <div class="card-content">

                    <div class="card-category">

                        ${product.CategoryName}

                    </div>


                    <h3>

                        ${product.ProductName}

                    </h3>


                    <div class="card-brand">

                        ${product.BrandName}

                    </div>


                    <div class="card-bottom">

                        <span class="card-price">

                            ${formatPrice(
                                product.SalePrice
                            )}

                        </span>

                    </div>


                    <button
                        class="detail-button"
                    >

                        Xem chi tiết

                    </button>

                </div>

            `;


            card.addEventListener(
                "click",
                function() {

                    window.location.href =
                        `product.html?id=${product.ProductID}`;

                }
            );


            container.appendChild(card);

        });


    }
    catch (error) {

        console.error(error);


        container.innerHTML = `

            <div class="loading">

                ❌ Không thể tải sản phẩm.

            </div>

        `;

    }

}


loadProducts();