const API_URL =
    "http://127.0.0.1:8000";


// ======================================================
// LẤY PRODUCT ID TRÊN URL
// ======================================================

const params =
    new URLSearchParams(
        window.location.search
    );


const productId =
    params.get("id");


let currentProductId =
    Number(productId);


// Nếu không có ID

if (!currentProductId) {

    currentProductId = 1;

}


// ======================================================
// FORMAT GIÁ
// ======================================================

function formatPrice(price) {

    return Number(
        price
    ).toLocaleString(
        "vi-VN"
    ) + " VNĐ";

}


// ======================================================
// LOAD PRODUCT
// ======================================================

async function loadProduct() {

    console.log("=================================");
    console.log("BẮT ĐẦU LOAD PRODUCT");
    console.log("Product ID:", currentProductId);
    console.log("=================================");

    try {

        const url =
            `${API_URL}/products/${currentProductId}`;

        console.log(
            "Đang gọi API:",
            url
        );


        const response =
            await fetch(url);


        console.log(
            "API Status:",
            response.status
        );


        if (!response.ok) {

            throw new Error(
                `API lỗi HTTP ${response.status}`
            );

        }


        const result =
            await response.json();


        console.log(
            "API Response:",
            result
        );


        if (!result.success) {

            throw new Error(
                result.message ||
                "Không tìm thấy sản phẩm"
            );

        }


        const product =
            result.data;


        console.log(
            "PRODUCT:",
            product
        );


        // ==================================================
        // ẢNH SẢN PHẨM
        // ==================================================

        const image =
            document.getElementById(
                "mainProductImage"
            );


        if (image) {

            const imageUrl =
                `images/${product.ProductID}.jpg`;

            console.log(
                "Ảnh:",
                imageUrl
            );


            image.src =
                imageUrl;


            image.alt =
                product.ProductName;


            image.onerror =
                function () {

                    console.error(
                        "Không tải được ảnh:",
                        imageUrl
                    );

                    this.src =
                        "images/no-image.jpg";

                };

        }


        // ==================================================
        // TÊN
        // ==================================================

        document.getElementById(
            "productName"
        ).textContent =
            product.ProductName;


        // ==================================================
        // CATEGORY
        // ==================================================

        document.getElementById(
            "productCategory"
        ).textContent =
            product.CategoryName;


        // ==================================================
        // GIÁ
        // ==================================================

        document.getElementById(
            "productPrice"
        ).textContent =
            formatPrice(
                product.SalePrice
            );


        // ==================================================
        // BRAND
        // ==================================================

        document.getElementById(
            "productBrand"
        ).textContent =
            product.BrandName;


        // ==================================================
        // MATERIAL
        // ==================================================

        document.getElementById(
            "productMaterial"
        ).textContent =
            product.MaterialName;


        // ==================================================
        // GEMSTONE
        // ==================================================

        document.getElementById(
            "productGemstone"
        ).textContent =
            product.GemstoneName;


        // ==================================================
        // COLLECTION
        // ==================================================

        document.getElementById(
            "productCollection"
        ).textContent =
            product.CollectionName;


        // ==================================================
        // STOCK
        // ==================================================

        document.getElementById(
            "productStock"
        ).textContent =
            product.Stock;


        console.log(
            "✅ LOAD PRODUCT THÀNH CÔNG"
        );


    }
    catch (error) {

        console.error(
            "❌ LOAD PRODUCT ERROR:",
            error
        );


        // Không để trang đứng mãi ở "Đang tải..."

        const name =
            document.getElementById(
                "productName"
            );


        if (name) {

            name.textContent =
                "Không thể tải sản phẩm";

        }


        const category =
            document.getElementById(
                "productCategory"
            );


        if (category) {

            category.textContent =
                "Vui lòng kiểm tra Recommendation API";

        }


        const image =
            document.getElementById(
                "mainProductImage"
            );


        if (image) {

            image.src =
                "images/no-image.jpg";

        }

    }

}


// ======================================================
// LOAD RECOMMENDATION
// ======================================================

async function loadRecommendations() {


    const customerId =
        document.getElementById(
            "customerSelect"
        ).value;


    const container =
        document.getElementById(
            "recommendationList"
        );


    container.innerHTML = `

        <div class="loading">

            🤖 AI đang phân tích...

        </div>

    `;


    try {


        const url =
            `${API_URL}/recommendations` +
            `?customer_id=${customerId}` +
            `&product_id=${currentProductId}` +
            `&number=5`;


        const response =
            await fetch(
                url
            );


        const result =
            await response.json();


        if (!result.success) {

            container.innerHTML = `

                <div class="loading">

                    Không có sản phẩm gợi ý.

                </div>

            `;

            return;

        }


        displayRecommendations(
            result.data
        );


    }

    catch (error) {


        console.error(
            error
        );


        container.innerHTML = `

            <div class="loading">

                ❌ Không thể kết nối
                Recommendation API.

            </div>

        `;

    }

}


// ======================================================
// HIỂN THỊ GỢI Ý
// ======================================================

function displayRecommendations(
    products
) {


    const container =
        document.getElementById(
            "recommendationList"
        );


    container.innerHTML = "";


    products.forEach(
        product => {


            const card =
                document.createElement(
                    "div"
                );


            card.className =
                "product-card";


            card.style.cursor =
                "pointer";


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


                    <h3>

                        ${product.ProductName}

                    </h3>


                    <p class="card-category">

                        ${product.CategoryName}

                    </p>


                    <p class="card-price">

                        ${formatPrice(
                            product.SalePrice
                        )}

                    </p>


                    <p class="ai-score">

                        🤖 AI Score:

                        ${(
                            product.HybridScore
                            * 100
                        ).toFixed(1)}%

                    </p>


                </div>

            `;


            // Click vào sản phẩm gợi ý

            card.addEventListener(
                "click",
                function() {

                    window.location.href =
                        `product.html?id=${product.ProductID}`;

                }
            );


            container.appendChild(
                card
            );

        }
    );

}


// ======================================================
// ĐỔI KHÁCH HÀNG
// ======================================================

document
    .getElementById(
        "customerSelect"
    )
    .addEventListener(
        "change",
        function() {

            loadRecommendations();

        }
    );


// ======================================================
// KHỞI ĐỘNG
// ======================================================

loadProduct();

loadRecommendations();