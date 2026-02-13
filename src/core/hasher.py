from dataclasses import dataclass

import cv2
import numpy as np


def _resize_gray(frame: np.ndarray, width: int, height: int) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, (width, height), interpolation=cv2.INTER_AREA)


def dhash(frame: np.ndarray, hash_size: int = 8) -> int:
    resized = _resize_gray(frame, hash_size + 1, hash_size)
    diff = resized[:, 1:] > resized[:, :-1]
    bits = diff.flatten().astype(np.uint8)
    return _bits_to_int(bits)


def phash(frame: np.ndarray, hash_size: int = 8) -> int:
    high_freq_factor = 4
    size = hash_size * high_freq_factor
    resized = _resize_gray(frame, size, size)
    dct = cv2.dct(np.float32(resized))
    low_freq = dct[:hash_size, :hash_size]
    med = np.median(low_freq)
    bits = (low_freq > med).flatten().astype(np.uint8)
    return _bits_to_int(bits)


def hamming_distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def normalized_similarity(a: int, b: int, bit_length: int = 64) -> float:
    dist = hamming_distance(a, b)
    return 1.0 - (dist / bit_length)


def _bits_to_int(bits: np.ndarray) -> int:
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


@dataclass(slots=True)
class FrameHashes:
    d_hash: int
    p_hash: int
