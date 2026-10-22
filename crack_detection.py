"""Visible crack-like region detection for bridge and road surface images.

    grayscale -> CLAHE -> multi-scale Hessian ridge filter
    -> seed-and-grow (hysteresis) along dark ridges
    -> connected cracks filtered by length, thinness and darkness

A crack is a dark line that is darker than the pavement on both sides of
it. The Hessian ridge filter responds to exactly that shape and stays low on
round stones, stains and flat shading. Strong ridge pixels seed a crack,
which then grows into weaker connected ridge pixels, so a crack that fades
as it narrows is followed instead of being cut into short pieces.

A red trace is a screening mark, not a structural safety judgment.
"""

from __future__ import annotations

import cv2
import numpy as np

CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_SIZE = (8, 8)

# Gaussian scales in pixels. Small scales follow hairline cracks, larger
# scales follow wider ones.
RIDGE_SIGMAS = (1.5, 2.5, 4.0)
# Lower values suppress round blobs (stones, specks) more strongly.
BLOB_SUPPRESSION = 0.5

# Ridge thresholds are multiples of the photo's median ridge response, so
# coarse gravel and smooth concrete are judged against their own texture.
SEED_LEVEL = 6.0
GROW_LEVEL = 2.25
# A pixel that is this many times darker than typical also seeds a crack.
DARK_SEED_LEVEL = 3.0
DARK_KERNEL = 21
# A crack pixel must be at least this much darker (0-255) than its
# surroundings after contrast enhancement.
DARK_MIN = 14

# Painted lines and bright markings: their edges look like dark ridges.
MARKING_MARGIN = 35
MARKING_MIN_SHARE = 0.002
MARKING_PAD = 15

# Grass and paint are more saturated than gray pavement. The gate is only
# used when the whole photo is colorful, because the stones in some asphalt
# are saturated too.
COLORFUL_SCENE = 55
PAVEMENT_SATURATION = 60

# Fractions of the image diagonal. A crack must be long, or moderately long
# and clearly darker than the surface texture.
LONG_CRACK = 0.12
SHORT_CRACK = 0.07
SHORT_CRACK_DEPTH = 2.0
# Share of the crack's rotated bounding box that it fills. Cracks are thin.
MAX_FILL = 0.45
# 1.0 is a perfect circle. Rejects the rims of round stains.
MAX_ROUNDNESS = 0.5

STATUS_CRACK = "Crack-like region detected"
STATUS_CLEAR = "No crack detected"


def detect_cracks(image: np.ndarray) -> tuple[np.ndarray, str, int, np.ndarray]:
    """Return the highlighted image, status text, crack count and crack mask."""
    if image is None or image.size == 0:
        raise ValueError("Empty image")

    color = _as_bgr(image)
    height, width = color.shape[:2]
    raw_gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=CLAHE_TILE_SIZE)
    gray = clahe.apply(raw_gray)

    ridge = _ridge_response(gray)
    ridge_noise = float(np.median(ridge[ridge > 0])) if np.any(ridge > 0) else 0.0
    ridge_noise += 1e-6

    disk = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (DARK_KERNEL, DARK_KERNEL))
    darkness = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, disk)
    darkness_noise = float(np.median(darkness)) + 1.0

    candidate = darkness >= DARK_MIN
    candidate &= ~_marking_band(raw_gray)
    saturation = cv2.cvtColor(color, cv2.COLOR_BGR2HSV)[:, :, 1]
    if float(np.median(saturation)) >= COLORFUL_SCENE:
        candidate &= saturation < PAVEMENT_SATURATION

    grow = candidate & (ridge >= GROW_LEVEL * ridge_noise)
    seed = grow & (
        (ridge >= SEED_LEVEL * ridge_noise)
        | (darkness >= DARK_SEED_LEVEL * darkness_noise)
    )

    grow_mask = cv2.morphologyEx(
        grow.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)
    )
    label_count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
        grow_mask, connectivity=8
    )
    seeded = np.unique(labels[seed & (grow_mask > 0)])

    diagonal = float(np.hypot(height, width))
    mask = np.zeros((height, width), np.uint8)
    count = 0
    for label in seeded:
        if label == 0 or label >= label_count:
            continue
        x, y, w, h, area = stats[label]
        component = labels[y:y + h, x:x + w] == label
        if _is_crack(component, darkness[y:y + h, x:x + w], darkness_noise, area, diagonal):
            mask[y:y + h, x:x + w][component] = 255
            count += 1

    annotated = color.copy()
    trace = cv2.dilate(mask, np.ones((3, 3), np.uint8)) > 0
    annotated[trace] = (0, 0, 255)

    status = STATUS_CRACK if count > 0 else STATUS_CLEAR
    return annotated, status, count, mask


def _ridge_response(gray: np.ndarray) -> np.ndarray:
    """Return how strongly each pixel looks like the center of a dark line.

    Across a dark line the brightness curves upward on both sides, which
    gives a large positive Hessian eigenvalue. Along the line it stays flat,
    so the other eigenvalue is small. A round dark stone curves upward in
    every direction, and the ratio of the two eigenvalues suppresses it.
    """
    source = gray.astype(np.float32)
    best = np.zeros_like(source)
    for sigma in RIDGE_SIGMAS:
        blurred = cv2.GaussianBlur(source, (0, 0), sigma)
        dxx = cv2.Sobel(blurred, cv2.CV_32F, 2, 0, ksize=3)
        dyy = cv2.Sobel(blurred, cv2.CV_32F, 0, 2, ksize=3)
        dxy = cv2.Sobel(blurred, cv2.CV_32F, 1, 1, ksize=3)
        spread = np.sqrt((dxx - dyy) ** 2 + 4.0 * dxy ** 2)
        across = (dxx + dyy + spread) / 2.0
        along = (dxx + dyy - spread) / 2.0
        blobness = np.abs(along) / (np.abs(across) + 1e-6)
        line = np.exp(-(blobness ** 2) / (2.0 * BLOB_SUPPRESSION ** 2))
        best = np.maximum(best, (sigma ** 2) * np.maximum(across, 0.0) * line)
    return best


def _marking_band(raw_gray: np.ndarray) -> np.ndarray:
    """Return a mask around large bright markings such as painted lines."""
    height, width = raw_gray.shape
    small_size = (max(1, width // 4), max(1, height // 4))
    small = cv2.resize(raw_gray, small_size, interpolation=cv2.INTER_AREA)
    background = cv2.resize(
        cv2.medianBlur(small, 31), (width, height), interpolation=cv2.INTER_LINEAR
    ).astype(np.int16)
    smooth = cv2.GaussianBlur(raw_gray, (0, 0), 2).astype(np.int16)
    bright = (smooth >= background + MARKING_MARGIN).astype(np.uint8)
    bright = cv2.morphologyEx(
        bright, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    )

    label_count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
        bright, connectivity=8
    )
    large = np.zeros_like(bright)
    min_area = MARKING_MIN_SHARE * height * width
    for label in range(1, label_count):
        if stats[label, cv2.CC_STAT_AREA] >= min_area:
            large[labels == label] = 1
    pad = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (MARKING_PAD, MARKING_PAD))
    return cv2.dilate(large, pad) > 0


def _is_crack(
    component: np.ndarray,
    darkness: np.ndarray,
    darkness_noise: float,
    area: int,
    diagonal: float,
) -> bool:
    contours, _hierarchy = cv2.findContours(
        component.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours:
        return False
    outline = max(contours, key=cv2.contourArea)
    _center, (box_w, box_h), _angle = cv2.minAreaRect(outline)
    extent = max(box_w, box_h) / diagonal
    fill = area / max(box_w * box_h, 1.0)
    perimeter = cv2.arcLength(outline, True)
    roundness = 4.0 * np.pi * cv2.contourArea(outline) / max(perimeter ** 2, 1.0)
    depth = float(np.mean(darkness[component])) / darkness_noise

    long_enough = extent >= LONG_CRACK or (
        extent >= SHORT_CRACK and depth >= SHORT_CRACK_DEPTH
    )
    return long_enough and fill <= MAX_FILL and roundness <= MAX_ROUNDNESS


def _as_bgr(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return image.copy()


def _self_check() -> int:
    """Run the three demonstration images and print the detection result."""
    from sample_images import build_samples

    samples = build_samples()
    expected = {
        "artificial_crack.jpg": STATUS_CRACK,
        "crack_free.jpg": STATUS_CLEAR,
        "dim_crack.jpg": STATUS_CRACK,
    }
    failures = 0
    for name, wanted in expected.items():
        _annotated, status, count, _mask = detect_cracks(samples[name])
        ok = status == wanted
        failures += not ok
        print(f"{name}: {status} (regions={count}) {'OK' if ok else 'UNEXPECTED'}")
    return failures


if __name__ == "__main__":
    raise SystemExit(_self_check())