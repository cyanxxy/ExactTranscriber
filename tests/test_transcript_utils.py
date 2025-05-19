import pytest
import json
from transcript_utils import (
    adjust_chunk_timestamps,
    combine_transcriptions,
    convert_timestamp_to_srt,
    format_transcript_for_export
)
from config import CHUNK_DURATION_MS # Assuming default CHUNK_DURATION_MS is 120000 (2 minutes)

# Test data for adjust_chunk_timestamps
TRANSCRIPT_CHUNK_0 = """[00:30] Speaker 1: Hello this is the first chunk.
[01:15] Speaker 2: Yes, it is.
[01:55] [MUSIC]
[00:00] Speaker 1: This timestamp should be adjusted.
[00:01:59] Speaker 1: Nearing the end of a 2-min chunk for testing.
"""

# Expected after adjustment for chunk 0 (base_minutes = 0)
EXPECTED_CHUNK_0_ADJUSTED = """[00:30] Speaker 1: Hello this is the first chunk.
[01:15] Speaker 2: Yes, it is.
[01:55] [MUSIC]
[00:00] Speaker 1: This timestamp should be adjusted.
[01:59] Speaker 1: Nearing the end of a 2-min chunk for testing.
"""

# Expected after adjustment for chunk 1 (base_minutes = 2, assuming CHUNK_DURATION_MS = 120000)
# CHUNK_DURATION_MS / 60000 = 120000 / 60000 = 2 minutes
EXPECTED_CHUNK_1_ADJUSTED = """[02:30] Speaker 1: Hello this is the first chunk.
[03:15] Speaker 2: Yes, it is.
[03:55] [MUSIC]
[02:00] Speaker 1: This timestamp should be adjusted.
[03:59] Speaker 1: Nearing the end of a 2-min chunk for testing.
"""


TRANSCRIPT_CHUNK_HHMMSS = """[00:00:30] Speaker 1: Hello this is the first chunk.
[00:01:15] Speaker 2: Yes, it is.
[00:01:55] [MUSIC]
[01:00:30] Speaker 1: This is one hour in.
"""
# Expected for HHMMSS format, chunk 1 (base_minutes = 2)
EXPECTED_CHUNK_1_HHMMSS_ADJUSTED = """[00:02:30] Speaker 1: Hello this is the first chunk.
[00:03:15] Speaker 2: Yes, it is.
[00:03:55] [MUSIC]
[01:02:30] Speaker 1: This is one hour in.
"""


def test_adjust_chunk_timestamps_chunk_0():
    adjusted = adjust_chunk_timestamps(TRANSCRIPT_CHUNK_0, 0, chunk_duration_ms=CHUNK_DURATION_MS)
    assert adjusted.split('\n') == EXPECTED_CHUNK_0_ADJUSTED.split('\n')

def test_adjust_chunk_timestamps_chunk_1():
    adjusted = adjust_chunk_timestamps(TRANSCRIPT_CHUNK_0, 1, chunk_duration_ms=CHUNK_DURATION_MS)
    assert adjusted.split('\n') == EXPECTED_CHUNK_1_ADJUSTED.split('\n')

def test_adjust_chunk_timestamps_hhmmss_format():
    adjusted = adjust_chunk_timestamps(TRANSCRIPT_CHUNK_HHMMSS, 1, chunk_duration_ms=CHUNK_DURATION_MS)
    assert adjusted.split('\n') == EXPECTED_CHUNK_1_HHMMSS_ADJUSTED.split('\n')

def test_adjust_chunk_timestamps_empty_input():
    assert adjust_chunk_timestamps("", 0) == ""
    assert adjust_chunk_timestamps("", 1) == ""

def test_adjust_chunk_timestamps_no_timestamps():
    text = "This is a line without a timestamp.\nAnother line."
    assert adjust_chunk_timestamps(text, 1) == text

def test_adjust_chunk_timestamps_invalid_timestamp():
    text = "[invalid] Speaker 1: Test\n[00:10] Speaker 2: Valid"
    expected_text = "[invalid] Speaker 1: Test\n[02:10] Speaker 2: Valid" # Assuming CHUNK_DURATION_MS = 120000
    assert adjust_chunk_timestamps(text, 1, chunk_duration_ms=CHUNK_DURATION_MS) == expected_text

def test_adjust_chunk_timestamps_with_end_marker():
    text = "[00:10] Speaker 1: Message\n[END]\n[00:20] Speaker 2: After end (should not happen)"
    expected_text_chunk_1 = "[02:10] Speaker 1: Message" 
    # [END] is skipped, and lines after it if any (though prompt implies [END] is last)
    adjusted = adjust_chunk_timestamps(text, 1, chunk_duration_ms=CHUNK_DURATION_MS)
    assert adjusted.strip() == expected_text_chunk_1 

# Test data for combine_transcriptions
CHUNK_1_TEXT = """[00:00] Speaker 1: First line from chunk 1.
[00:05] Speaker 2: Second line from chunk 1.
[END]"""
CHUNK_2_TEXT = """[00:00] Speaker 1: First line from chunk 2.
[00:03] Speaker 2: Second line from chunk 2.
[END]"""
CHUNK_3_TEXT = """[00:01] Speaker 1: Only line from chunk 3.
[END]"""

EXPECTED_COMBINED = """[00:00] Speaker 1: First line from chunk 1.
[00:05] Speaker 2: Second line from chunk 1.
[00:00] Speaker 1: First line from chunk 2.
[00:03] Speaker 2: Second line from chunk 2.
[00:01] Speaker 1: Only line from chunk 3.
[END]""" # [END] only from the last chunk

def test_combine_transcriptions_multiple_chunks():
    chunks = [CHUNK_1_TEXT, CHUNK_2_TEXT, CHUNK_3_TEXT]
    combined = combine_transcriptions(chunks)
    assert combined.split('\n') == EXPECTED_COMBINED.split('\n')

def test_combine_transcriptions_single_chunk():
    chunks = [CHUNK_1_TEXT]
    combined = combine_transcriptions(chunks)
    assert combined.split('\n') == CHUNK_1_TEXT.split('\n') # Should keep [END]

def test_combine_transcriptions_empty_list():
    assert combine_transcriptions([]) == ""

def test_combine_transcriptions_chunks_without_end_marker():
    chunk_a = "[00:01] Speaker A: Test"
    chunk_b = "[00:02] Speaker B: Test again"
    expected = f"{chunk_a}\n{chunk_b}"
    assert combine_transcriptions([chunk_a, chunk_b]) == expected


# Test data for convert_timestamp_to_srt
@pytest.mark.parametrize("input_ts, expected_srt_ts", [
    ("[00:00]", "00:00:00,000"),
    ("[00:30]", "00:00:30,000"),
    ("[01:15]", "00:01:15,000"),
    ("[59:59]", "00:59:59,000"),
    ("[01:00:00]", "01:00:00,000"), # HH:MM:SS
    ("[10:20:30]", "10:20:30,000"),
    ("invalid", "00:00:00,000"), # Invalid format
    ("[]", "00:00:00,000"), # Empty brackets
    ("[00:00:00:00]", "00:00:00,000"), # Too many parts
])
def test_convert_timestamp_to_srt(input_ts, expected_srt_ts):
    assert convert_timestamp_to_srt(input_ts) == expected_srt_ts

# Test data for format_transcript_for_export
TRANSCRIPT_FOR_EXPORT = """[00:00:05] Speaker 1: Hello world.
[00:00:08] Speaker 2: Hi there.
[00:00:10] [MUSIC]
[00:00:12] Speaker 1: How are you?
[END]"""

def test_format_transcript_for_export_txt():
    formatted = format_transcript_for_export(TRANSCRIPT_FOR_EXPORT, format='txt')
    assert formatted == TRANSCRIPT_FOR_EXPORT

def test_format_transcript_for_export_srt():
    expected_srt = """1
00:00:05,000 --> 00:00:08,000
Speaker 1: Hello world.

2
00:00:08,000 --> 00:00:11,000
Speaker 2: Hi there.

3
00:00:10,000 --> 00:00:13,000
[MUSIC]

4
00:00:12,000 --> 00:00:15,000
Speaker 1: How are you?
""" # [END] is excluded
    formatted = format_transcript_for_export(TRANSCRIPT_FOR_EXPORT, format='srt')
    assert formatted.strip() == expected_srt.strip()

def test_format_transcript_for_export_json():
    expected_json_data = {
        "transcript": [
            {"timestamp": "00:00:05", "type": "speech", "speaker": "Speaker 1", "content": "Hello world."},
            {"timestamp": "00:00:08", "type": "speech", "speaker": "Speaker 2", "content": "Hi there."},
            {"timestamp": "00:00:10", "type": "event", "content": "MUSIC"},
            {"timestamp": "00:00:12", "type": "speech", "speaker": "Speaker 1", "content": "How are you?"}
        ]
    }
    formatted = format_transcript_for_export(TRANSCRIPT_FOR_EXPORT, format='json')
    assert json.loads(formatted) == expected_json_data

def test_format_transcript_for_export_unknown_format():
    formatted = format_transcript_for_export(TRANSCRIPT_FOR_EXPORT, format='unknown')
    assert formatted == TRANSCRIPT_FOR_EXPORT # Defaults to plain text

def test_format_transcript_for_export_empty_transcript():
    assert format_transcript_for_export("", format='txt') == ""
    assert format_transcript_for_export("", format='srt') == ""
    assert format_transcript_for_export("", format='json') == json.dumps({"transcript": []}, indent=2) # Specific behavior for empty JSON

def test_format_transcript_for_export_srt_no_timestamps():
    text = "Speaker 1: Hello\nSpeaker 2: Hi"
    # Should produce empty srt as no lines match the timestamp pattern
    assert format_transcript_for_export(text, 'srt').strip() == ""

def test_format_transcript_for_export_json_no_timestamps():
    text = "Speaker 1: Hello\nSpeaker 2: Hi"
    # Should produce empty list as no lines match the timestamp pattern
    assert json.loads(format_transcript_for_export(text, 'json')) == {"transcript": []}

def test_format_transcript_for_export_json_mixed_content():
    transcript = """[00:00:01] Speaker 1: Test message.
[00:00:02] [SOUND EFFECT: Door slam]
[00:00:03] Unknown Speaker: Another message.
[00:00:04] Speaker 2: Final words.
"""
    expected_data = {
        "transcript": [
            {"timestamp": "00:00:01", "type": "speech", "speaker": "Speaker 1", "content": "Test message."},
            {"timestamp": "00:00:02", "type": "event", "content": "SOUND EFFECT: Door slam"},
            # This case depends on how strict the speaker parsing is.
            # Current impl: if not "Speaker X:", it's "other".
            {"timestamp": "00:00:03", "type": "other", "content": "Unknown Speaker: Another message."},
            {"timestamp": "00:00:04", "type": "speech", "speaker": "Speaker 2", "content": "Final words."}
        ]
    }
    formatted = format_transcript_for_export(transcript, format='json')
    assert json.loads(formatted) == expected_data

def test_format_transcript_for_export_srt_timestamp_parsing_edge_cases():
    # Test to ensure convert_timestamp_to_srt robustness is handled
    transcript = "[00:01] Speaker A: Valid\n[bad:ts] Speaker B: Invalid TS\n[00:02] Speaker C: Also valid"
    expected_srt = """1
00:00:01,000 --> 00:00:04,000
Speaker A: Valid

2
00:00:02,000 --> 00:00:05,000
Speaker C: Also valid
""" # Line with bad timestamp is skipped
    formatted = format_transcript_for_export(transcript, 'srt')
    assert formatted.strip() == expected_srt.strip()

def test_format_transcript_for_export_json_timestamp_parsing_edge_cases():
    transcript = "[00:01] Speaker A: Valid\n[bad:ts] Speaker B: Invalid TS\n[00:02] Speaker C: Also valid"
    expected_json = {
        "transcript": [
            {"timestamp": "00:01", "type": "speech", "speaker": "Speaker A", "content": "Valid"},
            {"timestamp": "00:02", "type": "speech", "speaker": "Speaker C", "content": "Also valid"}
        ]
    } # Line with bad timestamp is skipped
    formatted = format_transcript_for_export(transcript, 'json')
    assert json.loads(formatted) == expected_json
