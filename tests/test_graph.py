"""Tests for graph.py pure functions."""

from app.core.graph import detect_emotion


class TestDetectEmotion:
    def test_happy_from_laughing(self):
        assert detect_emotion("ㅋㅋ 진짜 대박이야!") == "happy"

    def test_happy_from_emoji(self):
        assert detect_emotion("오늘 너무 좋아 😊") == "happy"

    def test_excited_from_keyword(self):
        # "대박"은 happy 키워드이므로 excited만 트리거하는 입력 사용
        assert detect_emotion("헐 진짜?? 🔥") == "excited"

    def test_sad_from_emoji(self):
        assert detect_emotion("오늘 너무 슬프다 😢") == "sad"

    def test_sad_from_keyword(self):
        assert detect_emotion("요즘 너무 힘들어") == "sad"

    def test_anxious_from_keyword(self):
        assert detect_emotion("앞으로가 너무 걱정돼") == "anxious"

    def test_nostalgic_from_keyword(self):
        assert detect_emotion("그때가 너무 그리워") == "nostalgic"

    def test_calm_as_default(self):
        assert detect_emotion("안녕") == "calm"

    def test_empty_string_returns_calm(self):
        assert detect_emotion("") == "calm"
