"""Watermark Detector — 3-strategy cascade (ORB + Template + Edge)."""

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

# Scales to test during template/edge matching
MATCH_SCALES = [0.3, 0.5, 0.7, 0.85, 1.0, 1.15, 1.3, 1.5, 1.75]

# Padding around detected watermark for cleaner inpainting (pixels)
MASK_PADDING = 15

# ORB feature matching constants
ORB_MIN_MATCHES = 12
ORB_LOWE_RATIO = 0.75

# Canny edge detection thresholds
EDGE_CANNY_LOW = 50
EDGE_CANNY_HIGH = 150


@dataclass
class WatermarkMatch:
    found: bool
    confidence: float = 0.0
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)  # x, y, w, h
    mask: np.ndarray | None = None
    template_name: str = ""
    strategy: str = ""  # "orb", "template", "edge"


@dataclass
class _CachedTemplate:
    name: str
    image: np.ndarray  # grayscale
    channel: str  # "global" or channel name
    orb_keypoints: tuple = ()
    orb_descriptors: np.ndarray | None = None
    edges: np.ndarray | None = None


class WatermarkDetector:
    """Detects watermarks in images via 3-strategy cascade."""

    def __init__(self) -> None:
        self._templates: list[_CachedTemplate] = []
        self._loaded = False
        self._orb = cv2.ORB_create(nfeatures=1000)

    def load_templates(self) -> None:
        """Load all reference templates from the configured directory."""
        ref_dir = Path(settings.watermark_ref_dir)
        if not ref_dir.is_absolute():
            ref_dir = Path.cwd() / ref_dir

        self._templates.clear()

        if not ref_dir.exists():
            logger.warning(f"Watermark ref directory does not exist: {ref_dir}")
            self._loaded = True
            return

        count = 0
        for subdir in sorted(ref_dir.iterdir()):
            if not subdir.is_dir():
                continue
            channel = subdir.name  # "global" or channel name
            for img_path in sorted(subdir.iterdir()):
                if img_path.suffix.lower() not in (".png", ".jpg", ".jpeg"):
                    continue
                img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
                if img is None:
                    logger.warning(f"Failed to load template: {img_path}")
                    continue

                # Pre-compute ORB features
                kp, desc = self._orb.detectAndCompute(img, None)

                # Pre-compute Canny edges
                edges = cv2.Canny(img, EDGE_CANNY_LOW, EDGE_CANNY_HIGH)

                self._templates.append(
                    _CachedTemplate(
                        name=img_path.name,
                        image=img,
                        channel=channel,
                        orb_keypoints=kp,
                        orb_descriptors=desc,
                        edges=edges,
                    )
                )
                count += 1

        self._loaded = True
        logger.info(f"Loaded {count} watermark reference template(s) from {ref_dir}")

    def reload(self) -> None:
        """Force reload templates (e.g., after adding new references)."""
        self.load_templates()

    @property
    def template_count(self) -> int:
        return len(self._templates)

    def _orb_match(self, gray: np.ndarray, tpl: _CachedTemplate, img_w: int, img_h: int) -> WatermarkMatch | None:
        """Strategy 1: ORB feature matching with homography."""
        if tpl.orb_descriptors is None or len(tpl.orb_keypoints) < ORB_MIN_MATCHES:
            return None

        kp_img, desc_img = self._orb.detectAndCompute(gray, None)
        if desc_img is None or len(kp_img) < ORB_MIN_MATCHES:
            return None

        bf = cv2.BFMatcher(cv2.NORM_HAMMING)
        matches = bf.knnMatch(tpl.orb_descriptors, desc_img, k=2)

        # Lowe's ratio test
        good = []
        for pair in matches:
            if len(pair) == 2:
                m, n = pair
                if m.distance < ORB_LOWE_RATIO * n.distance:
                    good.append(m)

        if len(good) < ORB_MIN_MATCHES:
            return None

        src_pts = np.float32([tpl.orb_keypoints[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp_img[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

        M, mask_h = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        if M is None:
            return None

        inliers = int(mask_h.sum()) if mask_h is not None else 0
        if inliers < ORB_MIN_MATCHES:
            return None

        # Project template corners to find bounding box
        th, tw = tpl.image.shape[:2]
        corners = np.float32([[0, 0], [tw, 0], [tw, th], [0, th]]).reshape(-1, 1, 2)
        projected = cv2.perspectiveTransform(corners, M)
        proj = projected.reshape(-1, 2)

        x_min = max(0, int(proj[:, 0].min()))
        y_min = max(0, int(proj[:, 1].min()))
        x_max = min(img_w, int(proj[:, 0].max()))
        y_max = min(img_h, int(proj[:, 1].max()))

        w = x_max - x_min
        h = y_max - y_min
        if w <= 0 or h <= 0:
            return None

        confidence = inliers / len(good)

        return WatermarkMatch(
            found=True,
            confidence=float(confidence),
            bbox=(x_min, y_min, w, h),
            template_name=f"{tpl.channel}/{tpl.name}@orb",
            strategy="orb",
        )

    def _template_match(
        self,
        gray: np.ndarray,
        tpl: _CachedTemplate,
        img_w: int,
        img_h: int,
        threshold: float,
    ) -> WatermarkMatch | None:
        """Strategy 2: Multi-scale template matching with dual methods."""
        best: WatermarkMatch | None = None

        methods = [cv2.TM_CCOEFF_NORMED, cv2.TM_CCORR_NORMED]

        for scale in MATCH_SCALES:
            tw = int(tpl.image.shape[1] * scale)
            th = int(tpl.image.shape[0] * scale)

            if tw >= img_w or th >= img_h or tw < 10 or th < 10:
                continue

            scaled = cv2.resize(tpl.image, (tw, th), interpolation=cv2.INTER_AREA)

            for method in methods:
                result = cv2.matchTemplate(gray, scaled, method)
                _, max_val, _, max_loc = cv2.minMaxLoc(result)

                if best is None or max_val > best.confidence:
                    match = WatermarkMatch(
                        found=max_val >= threshold,
                        confidence=float(max_val),
                        bbox=(max_loc[0], max_loc[1], tw, th),
                        template_name=f"{tpl.channel}/{tpl.name}@{scale:.0%}",
                        strategy="template",
                    )
                    if match.found:
                        best = match

        return best

    def _edge_match(
        self,
        gray: np.ndarray,
        tpl: _CachedTemplate,
        img_w: int,
        img_h: int,
        threshold: float,
    ) -> WatermarkMatch | None:
        """Strategy 3: Edge-based matching using Canny edges."""
        if tpl.edges is None:
            return None

        img_edges = cv2.Canny(gray, EDGE_CANNY_LOW, EDGE_CANNY_HIGH)
        best: WatermarkMatch | None = None

        for scale in MATCH_SCALES:
            tw = int(tpl.edges.shape[1] * scale)
            th = int(tpl.edges.shape[0] * scale)

            if tw >= img_w or th >= img_h or tw < 10 or th < 10:
                continue

            scaled = cv2.resize(tpl.edges, (tw, th), interpolation=cv2.INTER_AREA)
            result = cv2.matchTemplate(img_edges, scaled, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if best is None or max_val > best.confidence:
                match = WatermarkMatch(
                    found=max_val >= threshold,
                    confidence=float(max_val),
                    bbox=(max_loc[0], max_loc[1], tw, th),
                    template_name=f"{tpl.channel}/{tpl.name}@edge-{scale:.0%}",
                    strategy="edge",
                )
                if match.found:
                    best = match

        return best

    def detect(self, image: np.ndarray, source_channel: str = "") -> WatermarkMatch:
        """Run 3-strategy cascade against loaded references.

        Cascade order: ORB feature matching -> Template matching -> Edge matching.
        Returns the first confident match found, or the best overall result.

        Args:
            image: BGR image (as read by cv2.imread)
            source_channel: channel name to prioritize channel-specific templates

        Returns:
            WatermarkMatch with detection results
        """
        if not self._loaded:
            self.load_templates()

        if not self._templates:
            return WatermarkMatch(found=False)

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        img_h, img_w = gray.shape[:2]
        threshold = settings.watermark_confidence_threshold

        best = WatermarkMatch(found=False)

        # Order: channel-specific first, then global
        ordered = sorted(
            self._templates,
            key=lambda t: 0 if t.channel == source_channel else 1 if t.channel == "global" else 2,
        )

        for tpl in ordered:
            # Skip templates from other channels (not global, not matching)
            if tpl.channel not in ("global", source_channel):
                continue

            # Strategy 1: ORB feature matching (most robust)
            orb_result = self._orb_match(gray, tpl, img_w, img_h)
            if orb_result and orb_result.confidence > best.confidence:
                best = orb_result
                if best.confidence > 0.8:
                    break
                continue

            # Strategy 2: Template matching (dual-method, multi-scale)
            tpl_result = self._template_match(gray, tpl, img_w, img_h, threshold)
            if tpl_result and tpl_result.confidence > best.confidence:
                best = tpl_result
                if best.confidence > 0.8:
                    break
                continue

            # Strategy 3: Edge-based matching (fallback)
            edge_result = self._edge_match(gray, tpl, img_w, img_h, threshold)
            if edge_result and edge_result.confidence > best.confidence:
                best = edge_result
                if best.confidence > 0.8:
                    break

        # Generate inpainting mask if match found
        if best.found:
            mask = np.zeros((img_h, img_w), dtype=np.uint8)
            x, y, w, h = best.bbox
            # Add padding for cleaner inpainting edges
            x1 = max(0, x - MASK_PADDING)
            y1 = max(0, y - MASK_PADDING)
            x2 = min(img_w, x + w + MASK_PADDING)
            y2 = min(img_h, y + h + MASK_PADDING)
            mask[y1:y2, x1:x2] = 255
            best.mask = mask

        return best


# Module-level singleton
_detector: WatermarkDetector | None = None


def get_detector() -> WatermarkDetector:
    """Get the singleton detector instance, loading templates on first access."""
    global _detector
    if _detector is None:
        _detector = WatermarkDetector()
        _detector.load_templates()
    return _detector
