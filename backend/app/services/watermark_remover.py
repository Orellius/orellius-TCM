"""Watermark Remover — OpenCV inpainting with quality safeguard."""

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

# Maximum fraction of image area a mask can cover before we skip removal
MAX_MASK_COVERAGE = 0.25

# Inpainting radius (pixels of surrounding context used for fill)
INPAINT_RADIUS = 8

# Border width for quality assessment (pixels around the inpainted region)
QUALITY_BORDER_WIDTH = 15


@dataclass
class RemovalResult:
    success: bool
    cleaned_image: np.ndarray | None = None
    quality_score: float = 0.0
    reason: str = ""


def remove_watermark(image: np.ndarray, mask: np.ndarray) -> RemovalResult:
    """Remove a watermark region from an image using inpainting.

    Args:
        image: BGR image (as read by cv2.imread)
        mask: Binary mask (255 = watermark region to remove)

    Returns:
        RemovalResult with cleaned image or failure reason
    """
    img_h, img_w = image.shape[:2]
    mask_area = np.count_nonzero(mask)
    total_area = img_h * img_w

    # Safety check: skip if mask covers too much of the image
    coverage = mask_area / total_area
    if coverage > MAX_MASK_COVERAGE:
        return RemovalResult(
            success=False,
            reason=f"Mask covers {coverage:.0%} of image (max {MAX_MASK_COVERAGE:.0%})",
        )

    if mask_area == 0:
        return RemovalResult(success=False, reason="Empty mask")

    # Dilate mask for better coverage of watermark edges
    dilate_kernel = np.ones((5, 5), dtype=np.uint8)
    dilated_mask = cv2.dilate(mask, dilate_kernel, iterations=1)

    # Run Navier-Stokes inpainting
    cleaned = cv2.inpaint(image, dilated_mask, INPAINT_RADIUS, cv2.INPAINT_NS)

    # Blend edges for smooth transition
    cleaned = _blend_edges(image, cleaned, dilated_mask)

    # Assess quality: compare the inpainted border region to surroundings
    quality = _assess_quality(image, cleaned, mask)

    if quality < settings.watermark_quality_threshold:
        return RemovalResult(
            success=False,
            cleaned_image=cleaned,
            quality_score=quality,
            reason=f"Quality {quality:.2f} below threshold {settings.watermark_quality_threshold}",
        )

    return RemovalResult(
        success=True,
        cleaned_image=cleaned,
        quality_score=quality,
    )


def save_cleaned_image(
    cleaned: np.ndarray,
    message_id: str,
    file_id: str,
    media_dir: Path,
) -> str:
    """Save a cleaned image to disk and return the path."""
    output_path = media_dir / f"{message_id}_{file_id}_cleaned.png"
    cv2.imwrite(str(output_path), cleaned)
    return str(output_path)


def _blend_edges(original: np.ndarray, cleaned: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Gaussian blur blend on the boundary between inpainted and original regions."""
    soft_mask = cv2.GaussianBlur(mask / 255.0, (15, 15), 0)
    soft_mask_3ch = np.stack([soft_mask] * 3, axis=-1)
    blended = cleaned * soft_mask_3ch + original * (1.0 - soft_mask_3ch)
    return blended.astype(np.uint8)


def _assess_quality(
    original: np.ndarray,
    cleaned: np.ndarray,
    mask: np.ndarray,
) -> float:
    """Assess inpainting quality by comparing the border around the inpainted region.

    Computes normalized correlation between original and cleaned image in the
    border zone just outside the mask. If the surrounding area is well-preserved
    and the transition is smooth, the score will be high.

    Returns:
        Quality score between 0.0 and 1.0
    """
    # Dilate the mask to get the border region
    kernel = np.ones((QUALITY_BORDER_WIDTH * 2 + 1,) * 2, dtype=np.uint8)
    dilated = cv2.dilate(mask, kernel, iterations=1)

    # Border = dilated minus original mask
    border_mask = cv2.subtract(dilated, mask)

    if np.count_nonzero(border_mask) == 0:
        # No border pixels (mask at image edge) — assume adequate
        return 0.8

    # Convert to grayscale for comparison
    orig_gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY) if len(original.shape) == 3 else original
    clean_gray = cv2.cvtColor(cleaned, cv2.COLOR_BGR2GRAY) if len(cleaned.shape) == 3 else cleaned

    # Extract border pixels from both images
    orig_border = orig_gray[border_mask > 0].astype(np.float64)
    clean_border = clean_gray[border_mask > 0].astype(np.float64)

    # Normalized correlation
    orig_norm = orig_border - orig_border.mean()
    clean_norm = clean_border - clean_border.mean()

    denom = np.sqrt(np.sum(orig_norm**2) * np.sum(clean_norm**2))
    if denom < 1e-10:
        return 1.0  # Both regions are uniform — inpainting is trivially good

    correlation = np.sum(orig_norm * clean_norm) / denom
    return float(np.clip(correlation, 0.0, 1.0))
