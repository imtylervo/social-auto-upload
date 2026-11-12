"""Capabilities and asset limits of the Dayu article body; file reading and rendering are handled by the shared article module."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from utils.article_content import ArticleDocument
from utils.article_render import load_article


DAYU_ARTICLE_TAGS = {"section", "div", "span", "figure", "p", "br", "h1", "h2", "h3", "h4", "h5", "h6", "strong", "blockquote", "ol", "ul", "li", "hr"}


def load_dayu_article(content_file: str | Path, theme: str | None = None) -> ArticleDocument:
    """Render with the shared theme, keep the original styles for the Dayu compatibility conversion, and check platform capabilities before upload."""
    path = Path(content_file).expanduser().resolve()
    if path.suffix.lower() not in {".md", ".markdown"} and theme is not None:
        raise ValueError("--theme only applies to Markdown")
    document = load_article(path, theme)
    unsupported = set(document.tags) - DAYU_ARTICLE_TAGS
    if unsupported:
        raise ValueError(f"Dayu does not support these formats yet: {', '.join(sorted(unsupported))}; please adjust the source")
    # figure is converted to div on import; image count and positions are still checked strictly, layout containers are not counted as semantic formatting that must be kept.
    document.manifest["formats"].pop("figure", None)
    text = "".join(document.text).strip()
    if len(text) > 20000:
        raise ValueError(f"Dayu article body allows at most 20000 characters, currently {len(text)}")
    for image in set(document.images):
        validate_dayu_article_image(image)
    return document


def validate_dayu_article_image(image: str | Path) -> Path:
    """Body images and covers share the 5 MB per-image limit observed on the page; images that cannot be decoded are rejected."""
    path = Path(image).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {path}")
    size = path.stat().st_size
    if not size:
        raise ValueError(f"Image file is empty: {path}")
    if size > 5 * 1024 ** 2:
        raise ValueError(f"Image must not exceed 5 MB: {path}")
    # imread on Windows cannot reliably open paths with Chinese characters; read the bytes with pathlib and decode them, without rewriting the user's file.
    if cv2.imdecode(np.frombuffer(path.read_bytes(), dtype=np.uint8), cv2.IMREAD_UNCHANGED) is None:
        raise ValueError(f"Image cannot be decoded: {path}")
    return path
