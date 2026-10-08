from pathlib import Path
from PIL import Image


# ============================================================
# CẤU HÌNH
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent

IMAGE_DIR = PROJECT_DIR / "Website" / "images"


print("=" * 60)
print("CHUYỂN 500 ẢNH SANG JPEG THẬT")
print("=" * 60)

print()
print("Thư mục ảnh:")
print(IMAGE_DIR)


# ============================================================
# KIỂM TRA THƯ MỤC
# ============================================================

if not IMAGE_DIR.exists():

    print()
    print("❌ Không tìm thấy thư mục:")
    print(IMAGE_DIR)

    raise SystemExit


# ============================================================
# CHUYỂN 500 ẢNH
# ============================================================

success = 0
failed = 0


for product_id in range(1, 501):

    image_file = IMAGE_DIR / f"{product_id}.jpg"

    print()
    print(f"[{product_id}/500] {image_file.name}")


    if not image_file.exists():

        print("   ❌ Không tồn tại")

        failed += 1

        continue


    try:

        # Pillow đọc theo nội dung thật của file
        # không phụ thuộc đuôi .jpg

        image = Image.open(
            image_file
        )


        print(
            "   Định dạng thật:",
            image.format
        )

        print(
            "   Kích thước:",
            image.size
        )


        # ----------------------------------------------------
        # Chuyển sang RGB
        # ----------------------------------------------------

        if image.mode in (
            "RGBA",
            "LA",
            "P"
        ):

            background = Image.new(
                "RGB",
                image.size,
                "white"
            )


            if image.mode == "P":

                image = image.convert(
                    "RGBA"
                )


            if image.mode in (
                "RGBA",
                "LA"
            ):

                background.paste(
                    image,
                    mask=image.getchannel(
                        "A"
                    )
                )

                image = background

            else:

                image = image.convert(
                    "RGB"
                )

        else:

            image = image.convert(
                "RGB"
            )


        # ----------------------------------------------------
        # Lưu lại thành JPEG THẬT
        # ----------------------------------------------------

        image.save(
            image_file,
            "JPEG",
            quality=95,
            optimize=True
        )


        success += 1

        print(
            "   ✅ Đã chuyển thành JPEG"
        )


    except Exception as e:

        failed += 1

        print(
            "   ❌ Lỗi:",
            e
        )


# ============================================================
# KẾT QUẢ
# ============================================================

print()
print("=" * 60)
print("HOÀN THÀNH")
print("=" * 60)

print()
print(
    "Ảnh chuyển thành công:",
    success
)

print(
    "Ảnh lỗi:",
    failed
)

print()

if success == 500:

    print(
        "🎉 Tất cả 500 ảnh đã là JPEG thật!"
    )

else:

    print(
        "⚠️ Một số ảnh chưa chuyển được."
    )

print()
print(
    "Thư mục:"
)

print(
    IMAGE_DIR
)

print("=" * 60)