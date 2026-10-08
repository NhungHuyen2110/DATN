import os
import zipfile
import shutil
from pathlib import Path

from huggingface_hub import hf_hub_download


# ============================================================
# CẤU HÌNH
# ============================================================

DATASET_ID = "sidd707/jewelry-design-dataset"

PROJECT_DIR = Path(__file__).resolve().parent

DOWNLOAD_DIR = PROJECT_DIR / "jewelry_dataset_download"

WEBSITE_DIR = PROJECT_DIR / "Website"

IMAGE_DIR = WEBSITE_DIR / "images"


# ============================================================
# TẠO THƯ MỤC
# ============================================================

DOWNLOAD_DIR.mkdir(
    exist_ok=True
)

IMAGE_DIR.mkdir(
    parents=True,
    exist_ok=True
)


print("=" * 60)
print("JEWELRY IMAGE DOWNLOADER")
print("=" * 60)

print()
print("Project:")
print(PROJECT_DIR)

print()
print("Thư mục ảnh website:")
print(IMAGE_DIR)


# ============================================================
# 1. TẢI DATASET
# ============================================================

print()
print("=" * 60)
print("1. ĐANG TẢI DATASET")
print("=" * 60)

print()
print("Dataset:")
print(DATASET_ID)

print()
print("File khoảng 406 MB.")
print("Vui lòng chờ đến khi tải xong.")


try:

    zip_path = hf_hub_download(
        repo_id=DATASET_ID,
        repo_type="dataset",
        filename="dataset.zip",
        local_dir=DOWNLOAD_DIR
    )

except Exception as e:

    print()
    print("❌ Không thể tải dataset.")

    print()
    print("Lỗi:")
    print(e)

    raise


print()
print("✅ Tải dataset thành công.")

print()
print("File:")
print(zip_path)


# ============================================================
# 2. GIẢI NÉN
# ============================================================

print()
print("=" * 60)
print("2. GIẢI NÉN DATASET")
print("=" * 60)


EXTRACT_DIR = DOWNLOAD_DIR / "extracted"

EXTRACT_DIR.mkdir(
    exist_ok=True
)


try:

    with zipfile.ZipFile(
        zip_path,
        "r"
    ) as zip_ref:

        zip_ref.extractall(
            EXTRACT_DIR
        )

except Exception as e:

    print()
    print("❌ Không thể giải nén.")

    print()
    print(e)

    raise


print()
print("✅ Giải nén thành công.")

print()
print("Thư mục:")
print(EXTRACT_DIR)


# ============================================================
# 3. TÌM TẤT CẢ ẢNH
# ============================================================

print()
print("=" * 60)
print("3. TÌM ẢNH")
print("=" * 60)


extensions = {

    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp"

}


all_images = []


for file in EXTRACT_DIR.rglob("*"):

    if file.is_file():

        if file.suffix.lower() in extensions:

            all_images.append(file)


print()
print(
    "Tổng số ảnh tìm thấy:",
    len(all_images)
)


if len(all_images) < 500:

    raise Exception(
        "Dataset không có đủ 500 ảnh."
    )


# ============================================================
# 4. CHỌN 500 ẢNH
# ============================================================

print()
print("=" * 60)
print("4. CHỌN 500 ẢNH")
print("=" * 60)


# Sắp xếp để kết quả ổn định
all_images = sorted(
    all_images,
    key=lambda x: str(x)
)


selected_images = all_images[:500]


print()
print(
    "Đã chọn:",
    len(selected_images),
    "ảnh"
)


# ============================================================
# 5. XÓA ẢNH CŨ
# ============================================================

print()
print("=" * 60)
print("5. CHUẨN BỊ THƯ MỤC WEBSITE")
print("=" * 60)


for file in IMAGE_DIR.iterdir():

    if file.is_file():

        if file.suffix.lower() in extensions:

            try:

                file.unlink()

            except Exception:

                pass


print()
print("Đã dọn ảnh cũ.")


# ============================================================
# 6. COPY + ĐỔI TÊN
# ============================================================

print()
print("=" * 60)
print("6. COPY 500 ẢNH")
print("=" * 60)


for index, source_file in enumerate(
    selected_images,
    start=1
):

    destination_file = (
        IMAGE_DIR /
        f"{index}.jpg"
    )


    try:

        shutil.copy2(
            source_file,
            destination_file
        )

    except Exception as e:

        print()
        print(
            "❌ Lỗi copy:",
            source_file
        )

        print(e)

        raise


    if index % 50 == 0:

        print(
            f"Đã copy {index}/500 ảnh..."
        )


# ============================================================
# 7. TẠO ẢNH FALLBACK
# ============================================================

print()
print("=" * 60)
print("7. KIỂM TRA")
print("=" * 60)


image_count = len(
    list(
        IMAGE_DIR.glob("*.jpg")
    )
)


print()
print(
    "Số ảnh JPG trong website:",
    image_count
)


if image_count != 500:

    raise Exception(
        f"Chỉ có {image_count} ảnh thay vì 500."
    )


# ============================================================
# 8. HOÀN THÀNH
# ============================================================

print()
print("=" * 60)
print("HOÀN THÀNH")
print("=" * 60)

print()

print(
    "✅ Đã tạo 500 ảnh sản phẩm."
)

print()

print(
    "Thư mục:"
)

print(
    IMAGE_DIR
)

print()

print(
    "Ví dụ:"
)

print(
    IMAGE_DIR / "1.jpg"
)

print(
    IMAGE_DIR / "2.jpg"
)

print(
    IMAGE_DIR / "3.jpg"
)

print(
    IMAGE_DIR / "500.jpg"
)

print()

print(
    "Bây giờ có thể mở website."
)

print("=" * 60)