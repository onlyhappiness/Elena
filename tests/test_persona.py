"""Tests for persona.py pure functions."""

import pytest

from app.core.persona import (
    extract_selfie_tag,
    get_system_prompt_with_context,
    get_time_of_day,
    parse_selfie_context,
    should_generate_image,
)


class TestGetTimeOfDay:
    def test_dawn(self):
        assert get_time_of_day(3) == "새벽"

    def test_dawn_boundary(self):
        assert get_time_of_day(0) == "새벽"

    def test_morning(self):
        assert get_time_of_day(7) == "아침"

    def test_late_morning(self):
        assert get_time_of_day(11) == "오전"

    def test_lunch(self):
        assert get_time_of_day(13) == "점심"

    def test_afternoon(self):
        assert get_time_of_day(15) == "오후"

    def test_evening(self):
        assert get_time_of_day(19) == "저녁"

    def test_night(self):
        assert get_time_of_day(22) == "밤"

    def test_all_hours_return_valid_period(self):
        valid_periods = {"새벽", "아침", "오전", "점심", "오후", "저녁", "밤"}
        for hour in range(24):
            assert get_time_of_day(hour) in valid_periods


class TestShouldGenerateImage:
    def test_photo_keyword(self):
        assert should_generate_image("사진 보여줘") is True

    def test_selfie_keyword(self):
        assert should_generate_image("셀카 찍어봐") is True

    def test_what_are_you_doing(self):
        assert should_generate_image("지금 뭐 해?") is True

    def test_where_are_you(self):
        assert should_generate_image("지금 어디야?") is True

    def test_face_keyword(self):
        assert should_generate_image("얼굴 보고 싶다") is True

    def test_normal_message(self):
        assert should_generate_image("오늘 날씨 어때?") is False

    def test_emotional_message(self):
        assert should_generate_image("오늘 진짜 힘든 날이었어...") is False

    def test_empty_message(self):
        assert should_generate_image("") is False


class TestExtractSelfieTag:
    def test_tag_at_end(self):
        context, cleaned = extract_selfie_tag("야 지금 노을 미쳤어 🌅 [SELFIE: 광안리_노을]")
        assert context == "광안리_노을"
        assert "[SELFIE" not in cleaned
        assert "야 지금 노을 미쳤어" in cleaned

    def test_no_tag(self):
        context, cleaned = extract_selfie_tag("그냥 평범한 메시지야")
        assert context is None
        assert cleaned == "그냥 평범한 메시지야"

    def test_tag_with_leading_spaces(self):
        context, cleaned = extract_selfie_tag("어디 왔어 [SELFIE:  카페_아메리카노  ]")
        assert context == "카페_아메리카노"

    def test_cleaned_response_has_no_leftover_whitespace_issues(self):
        _, cleaned = extract_selfie_tag("메시지야 [SELFIE: 집_소파]")
        assert cleaned == "메시지야"


class TestParseSelfieContext:
    def test_known_location_gwangalli(self):
        result = parse_selfie_context("광안리_노을_감상중")
        assert result["location"] == "광안리"

    def test_known_location_cafe(self):
        result = parse_selfie_context("카페_아메리카노_마심")
        assert result["location"] == "카페"

    def test_unknown_location_falls_back_to_default(self):
        # LOCATION_PRESETS에 없는 단어 사용
        result = parse_selfie_context("도서관_공부중")
        assert result["location"] == "default"

    def test_activity_underscores_replaced_with_spaces(self):
        result = parse_selfie_context("카페_아메리카노")
        assert "_" not in result["activity"]

    def test_raw_context_preserved(self):
        raw = "광안리_노을_감상중"
        result = parse_selfie_context(raw)
        assert result["raw"] == raw


class TestGetSystemPromptWithContext:
    def test_contains_emotion(self):
        prompt = get_system_prompt_with_context(current_emotion="happy")
        assert "happy" in prompt

    def test_contains_memory_content(self):
        memories = [{"content": "커피를 좋아함", "feeling": "좋아하는 것"}]
        prompt = get_system_prompt_with_context(memories=memories)
        assert "커피를 좋아함" in prompt

    def test_contains_memory_feeling(self):
        memories = [{"content": "커피를 좋아함", "feeling": "좋아하는 것"}]
        prompt = get_system_prompt_with_context(memories=memories)
        assert "좋아하는 것" in prompt

    def test_no_memory_section_when_empty(self):
        prompt = get_system_prompt_with_context(memories=[])
        assert "우리 사이의 기억들" not in prompt

    def test_no_memory_section_when_none(self):
        prompt = get_system_prompt_with_context()
        assert "우리 사이의 기억들" not in prompt

    def test_memory_without_feeling_still_included(self):
        memories = [{"content": "부산 출신"}]
        prompt = get_system_prompt_with_context(memories=memories)
        assert "부산 출신" in prompt

    def test_contains_current_time_context(self):
        prompt = get_system_prompt_with_context()
        assert "현재 시간" in prompt
