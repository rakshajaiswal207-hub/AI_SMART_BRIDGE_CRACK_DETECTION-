"""Laboratory stand-in images for the dashboard and the processing self-check.

These are not photographs of the miniature bridge. They let the pipeline be
demonstrated before the ESP32-CAM is connected. Upload a real photograph of
the model the same way when the hardware is ready.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

WIDTH = 800
HEIGHT = 600


def save_samples(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, image in build_samples().items():
        path = directory / name
        if not cv2.imwrite(str(path), image, [int(cv2.IMWRITE_JPEG_QUALITY), 95]):
            raise RuntimeError(f"Could not write {path}")


def build_samples() -> dict[str, np.ndarray]:
    crack = make_surface(seed=7, crack=True, stain=True)
    clear = make_surface(seed=11, crack=False, stain=True)
    dim = np.clip(crack.astype(np.float32) * 0.42, 0, 255).astype(np.uint8)
    return {
        "artificial_crack.jpg": crack,
        "crack_free.jpg": clear,
        "dim_crack.jpg": dim,
    }


def make_surface(seed: int, crack: bool, stain: bool) -> np.ndarray:
    rng = np.random.default_rng(seed)
    gray = rng.normal(168, 9, (HEIGHT, WIDTH)).astype(np.float32)
    blotch = rng.normal(0, 1, (HEIGHT // 10, WIDTH // 10)).astype(np.float32)
    gray += cv2.resize(blotch, (WIDTH, HEIGHT), interpolation=cv2.INTER_CUBIC) * 12
    gray += rng.normal(0, 3, (HEIGHT, WIDTH))
    gray = np.clip(gray, 0, 255).astype(np.uint8)

    image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    image[:, :, 2] = np.clip(image[:, :, 2].astype(np.int16) + 10, 0, 255)
    image[:, :, 0] = np.clip(image[:, :, 0].astype(np.int16) - 8, 0, 255)

    if stain:
        cv2.circle(image, (140, 110), 34, (78, 82, 86), -1)
        cv2.circle(image, (620, 470), 18, (96, 98, 94), -1)

    if crack:
        _draw_crack(image)
    return image


def _draw_crack(image: np.ndarray) -> None:
    points = np.array(
        [
            [90, 250],
            [160, 268],
            [230, 246],
            [310, 286],
            [390, 270],
            [470, 304],
            [560, 286],
            [650, 318],
            [730, 300],
        ],
        dtype=np.int32,
    )
    cv2.polylines(image, [points], False, (28, 28, 28), 3, cv2.LINE_AA)
    cv2.polylines(image, [points], False, (12, 12, 12), 1, cv2.LINE_AA)