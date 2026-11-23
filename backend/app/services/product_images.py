"""Managed product covers, separate from the original SKU image archive."""
from io import BytesIO
import os
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4
import warnings

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 16_000_000


def image_root():
    return Path(os.getenv('LUMIERE_PRODUCT_IMAGE_DIR',
        str(Path(__file__).resolve().parents[3] / '.local-tmp/product-uploads')))


def cover_path(product_id):
    if type(product_id) is not int or product_id < 1:
        raise ValueError('Invalid product identity')
    return image_root() / str(product_id) / 'cover.webp'


def public_cover_url(product_id):
    path = cover_path(product_id)
    try:
        return f'/products/{product_id}/image?v={path.stat().st_mtime_ns}'
    except OSError:
        return None


def save_cover(product_id, content):
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(413, 'Ảnh phải có dung lượng từ 1 byte đến 5 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as original:
                if (original.format not in {'JPEG', 'PNG', 'WEBP'} or original.width * original.height > MAX_PIXELS
                        or getattr(original, 'is_animated', False)):
                    raise ValueError('Unsupported image')
                original.load()
                oriented = ImageOps.exif_transpose(original).convert('RGBA')
                cover = Image.new('RGB', oriented.size, 'white')
                cover.paste(oriented, mask=oriented.getchannel('A'))
                cover.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                buffer = BytesIO()
                cover.save(buffer, format='WEBP', quality=88)
                encoded = buffer.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning):
        raise HTTPException(422, 'Chọn ảnh JPEG, PNG hoặc WebP hợp lệ, tối đa 16 megapixel; không dùng ảnh động.') from None
    path = cover_path(product_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        history = path.parent / 'history'
        history.mkdir(exist_ok=True)
        shutil.copyfile(path, history / (uuid4().hex + '.webp'))
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='cover-', suffix='.tmp', delete=False) as output:
            temporary = Path(output.name)
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()  # Only the exact new temporary file; never original images.
    return {'product_id': product_id, 'image_url': public_cover_url(product_id)}
