from src.core.hasher import hamming_distance, normalized_similarity


def test_hamming_distance() -> None:
    assert hamming_distance(0b1010, 0b1001) == 2


def test_normalized_similarity() -> None:
    assert normalized_similarity(0, 0) == 1.0
    assert normalized_similarity(0, (1 << 64) - 1) == 0.0
