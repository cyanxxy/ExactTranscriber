import pytest
from unittest.mock import patch, MagicMock, call, ANY
import os

from transcription_processor import TranscriptionProcessor
from config import CHUNK_DURATION_MS, MIN_CHUNK_SUCCESS_PERCENTAGE, MAX_FILE_SIZE_MB_FOR_SIMPLE_UPLOAD
# Assuming api_client.process_audio_chunk might be needed if not mocking _process_single_chunk directly
# from api_client import process_audio_chunk # For now, we'll mock _process_single_chunk

@pytest.fixture
def mock_gemini_client():
    client = MagicMock()
    # Default success for upload and generate_content for simpler test cases
    client.files.upload.return_value = MagicMock(name="UploadedFile")
    mock_response = MagicMock()
    mock_response.text = "Default transcript part"
    mock_response.candidates = [MagicMock(content=MagicMock(parts=[MagicMock(text="Default transcript candidate")]))]
    client.models.generate_content.return_value = mock_response
    return client

@pytest.fixture
def processor(mock_gemini_client):
    # Ensure the processor is initialized with a model name that exists in GEMINI_MODELS or is a direct model_id
    # For testing, we can assume "gemini-test-model" is a valid model_id string.
    return TranscriptionProcessor(client=mock_gemini_client, model_name="gemini-pro", prompt_template=MagicMock())

# Mock data for calls
MOCK_FILE_PATH = "dummy/audio.mp3"
MOCK_FILE_FORMAT = "mp3"
MOCK_METADATA = {"language": "en"}
MOCK_NUM_SPEAKERS = 1
SMALL_FILE_SIZE_MB = MAX_FILE_SIZE_MB_FOR_SIMPLE_UPLOAD - 1  # Small enough for simple upload
LARGE_FILE_SIZE_MB = MAX_FILE_SIZE_MB_FOR_SIMPLE_UPLOAD + 1  # Large enough for chunking

# --- Tests for _process_small_file (via process_audio) ---

def test_process_audio_small_file_success(processor, mock_gemini_client):
    mock_gemini_client.files.upload.return_value = MagicMock(name="TestFile")
    mock_response = MagicMock()
    mock_response.text = "Successful small file transcript"
    mock_gemini_client.models.generate_content.return_value = mock_response

    transcript, error = processor.process_audio(
        MOCK_FILE_PATH, SMALL_FILE_SIZE_MB, MOCK_FILE_FORMAT, MOCK_METADATA, MOCK_NUM_SPEAKERS
    )

    assert transcript == "Successful small file transcript"
    assert error is None
    mock_gemini_client.files.upload.assert_called_once_with(file=MOCK_FILE_PATH, config={"mimeType": f"audio/{MOCK_FILE_FORMAT}"})
    mock_gemini_client.models.generate_content.assert_called_once() # Further details can be asserted if prompt is complex

def test_process_audio_small_file_upload_failure(processor, mock_gemini_client):
    mock_gemini_client.files.upload.side_effect = Exception("Upload failed")

    transcript, error = processor.process_audio(
        MOCK_FILE_PATH, SMALL_FILE_SIZE_MB, MOCK_FILE_FORMAT, MOCK_METADATA, MOCK_NUM_SPEAKERS
    )

    assert transcript is None
    assert "Upload failed" in error
    mock_gemini_client.files.upload.assert_called_once_with(file=MOCK_FILE_PATH, config={"mimeType": f"audio/{MOCK_FILE_FORMAT}"})
    mock_gemini_client.models.generate_content.assert_not_called()

def test_process_audio_small_file_transcription_api_failure(processor, mock_gemini_client):
    mock_gemini_client.files.upload.return_value = MagicMock(name="TestFile")
    mock_gemini_client.models.generate_content.side_effect = Exception("API error")

    transcript, error = processor.process_audio(
        MOCK_FILE_PATH, SMALL_FILE_SIZE_MB, MOCK_FILE_FORMAT, MOCK_METADATA, MOCK_NUM_SPEAKERS
    )

    assert transcript is None
    assert "API error" in error
    mock_gemini_client.files.upload.assert_called_once_with(file=MOCK_FILE_PATH, config={"mimeType": f"audio/{MOCK_FILE_FORMAT}"})
    mock_gemini_client.models.generate_content.assert_called_once()

# --- Tests for _process_large_file (via process_audio) ---

@patch('transcription_processor.file_utils.chunk_audio_file')
@patch('transcription_processor.TranscriptionProcessor._process_single_chunk')
@patch('transcription_processor.transcript_utils.combine_transcriptions')
@patch('transcription_processor.file_utils.cleanup_chunks')
def test_process_audio_large_file_success(
    mock_cleanup_chunks, mock_combine_transcriptions, mock_process_single_chunk, 
    mock_chunk_audio_file, processor
):
    mock_chunk_paths = ["chunk1.mp3", "chunk2.mp3"]
    mock_chunk_audio_file.return_value = (mock_chunk_paths, 2) # (paths, num_chunks)
    # _process_single_chunk should return (text, None) for success
    mock_process_single_chunk.side_effect = [
        ("Transcript chunk 1.", None), 
        ("Transcript chunk 2.", None)
    ]
    mock_combine_transcriptions.return_value = "Combined transcript from chunks."

    transcript, error = processor.process_audio(
        MOCK_FILE_PATH, LARGE_FILE_SIZE_MB, MOCK_FILE_FORMAT, MOCK_METADATA, MOCK_NUM_SPEAKERS
    )

    assert transcript == "Combined transcript from chunks."
    assert error is None
    mock_chunk_audio_file.assert_called_once_with(MOCK_FILE_PATH, MOCK_FILE_FORMAT, CHUNK_DURATION_MS)
    assert mock_process_single_chunk.call_count == 2
    mock_process_single_chunk.assert_any_call(mock_chunk_paths[0], 0, MOCK_FILE_FORMAT, MOCK_METADATA, MOCK_NUM_SPEAKERS)
    mock_process_single_chunk.assert_any_call(mock_chunk_paths[1], 1, MOCK_FILE_FORMAT, MOCK_METADATA, MOCK_NUM_SPEAKERS)
    mock_combine_transcriptions.assert_called_once_with(["Transcript chunk 1.", "Transcript chunk 2."])
    mock_cleanup_chunks.assert_called_once_with(mock_chunk_paths)

@patch('transcription_processor.file_utils.chunk_audio_file')
def test_process_audio_large_file_chunking_failure(mock_chunk_audio_file, processor):
    mock_chunk_audio_file.return_value = ([], 0) # Simulate chunking failure

    transcript, error = processor.process_audio(
        MOCK_FILE_PATH, LARGE_FILE_SIZE_MB, MOCK_FILE_FORMAT, MOCK_METADATA, MOCK_NUM_SPEAKERS
    )

    assert transcript is None
    assert "Failed to split audio file into chunks" in error
    mock_chunk_audio_file.assert_called_once_with(MOCK_FILE_PATH, MOCK_FILE_FORMAT, CHUNK_DURATION_MS)

@patch('transcription_processor.file_utils.chunk_audio_file')
@patch('transcription_processor.TranscriptionProcessor._process_single_chunk')
@patch('transcription_processor.file_utils.cleanup_chunks')
@patch('transcription_processor.transcript_utils.combine_transcriptions') # Though not expected to be called directly
def test_process_audio_large_file_partial_failure_fallback_success(
    mock_combine_transcriptions, mock_cleanup_chunks, mock_process_single_chunk,
    mock_chunk_audio_file, processor, mock_gemini_client # Need mock_gemini_client for fallback
):
    mock_chunk_paths = ["c1.mp3", "c2.mp3", "c3.mp3", "c4.mp3", "c5.mp3"] # 5 chunks
    mock_chunk_audio_file.return_value = (mock_chunk_paths, 5)
    
    # Simulate failure for most chunks (e.g., 1 success, 4 failures)
    # MIN_CHUNK_SUCCESS_PERCENTAGE is 0.6, so 1/5 = 0.2 is less, should trigger fallback
    mock_process_single_chunk.side_effect = [
        ("Successful chunk.", None),
        (None, "Error processing chunk 2"),
        (None, "Error processing chunk 3"),
        (None, "Error processing chunk 4"),
        (None, "Error processing chunk 5"),
    ]

    # Configure fallback (_process_small_file path) to succeed
    mock_gemini_client.files.upload.return_value = MagicMock(name="FallbackUpload")
    mock_fallback_response = MagicMock()
    mock_fallback_response.text = "Fallback successful transcript"
    mock_gemini_client.models.generate_content.return_value = mock_fallback_response
    
    # Reset call counts for client mocks for fallback verification
    mock_gemini_client.files.upload.reset_mock()
    mock_gemini_client.models.generate_content.reset_mock()

    transcript, error = processor.process_audio(
        MOCK_FILE_PATH, LARGE_FILE_SIZE_MB, MOCK_FILE_FORMAT, MOCK_METADATA, MOCK_NUM_SPEAKERS
    )

    assert transcript == "Fallback successful transcript"
    assert error is None # Fallback succeeded
    mock_chunk_audio_file.assert_called_once()
    assert mock_process_single_chunk.call_count == 5
    mock_cleanup_chunks.assert_called_once_with(mock_chunk_paths)
    
    # Verify fallback path was taken
    mock_gemini_client.files.upload.assert_called_once_with(file=MOCK_FILE_PATH, config={"mimeType": f"audio/{MOCK_FILE_FORMAT}"})
    mock_gemini_client.models.generate_content.assert_called_once() # Check it was called for fallback
    mock_combine_transcriptions.assert_not_called() # Fallback doesn't combine

@patch('transcription_processor.file_utils.chunk_audio_file')
@patch('transcription_processor.TranscriptionProcessor._process_single_chunk')
@patch('transcription_processor.file_utils.cleanup_chunks')
def test_process_audio_large_file_complete_chunk_failure_fallback_failure(
    mock_cleanup_chunks, mock_process_single_chunk,
    mock_chunk_audio_file, processor, mock_gemini_client # Need mock_gemini_client for fallback
):
    mock_chunk_paths = ["c1.mp3", "c2.mp3"]
    mock_chunk_audio_file.return_value = (mock_chunk_paths, 2)
    
    # All chunks fail
    mock_process_single_chunk.side_effect = [
        (None, "Error processing chunk 1"),
        (None, "Error processing chunk 2"),
    ]

    # Configure fallback (_process_small_file path) to also fail (e.g., upload error)
    mock_gemini_client.files.upload.side_effect = Exception("Fallback upload failed")
    
    # Reset call counts for client mocks
    mock_gemini_client.files.upload.reset_mock()
    mock_gemini_client.models.generate_content.reset_mock()
    # Set the side_effect again after resetting
    mock_gemini_client.files.upload.side_effect = Exception("Fallback upload failed")


    transcript, error = processor.process_audio(
        MOCK_FILE_PATH, LARGE_FILE_SIZE_MB, MOCK_FILE_FORMAT, MOCK_METADATA, MOCK_NUM_SPEAKERS
    )

    assert transcript is None
    assert "Fallback upload failed" in error # Error from fallback
    mock_chunk_audio_file.assert_called_once()
    assert mock_process_single_chunk.call_count == 2
    mock_cleanup_chunks.assert_called_once_with(mock_chunk_paths)
    
    # Verify fallback path was taken and failed
    mock_gemini_client.files.upload.assert_called_once_with(file=MOCK_FILE_PATH, config={"mimeType": f"audio/{MOCK_FILE_FORMAT}"})
    mock_gemini_client.models.generate_content.assert_not_called() # Because upload failed

# --- Tests for _process_single_chunk (if directly testing) ---
# For this task, _process_single_chunk is implicitly tested via the large file tests
# by mocking its return value. Direct tests would look like this:

@patch('transcription_processor.api_client.process_audio_chunk')
@patch('transcription_processor.transcript_utils.adjust_chunk_timestamps')
def test_process_single_chunk_success(mock_adjust_timestamps, mock_api_process_chunk, processor):
    chunk_path = "test_chunk.mp3"
    chunk_index = 0
    start_offset_ms = 0 # For adjust_chunk_timestamps
    
    mock_api_process_chunk.return_value = ("Raw chunk transcript", None)
    mock_adjust_timestamps.return_value = "Adjusted chunk transcript"
    
    # Note: _process_single_chunk uses self.client and self.model_name
    # We need to ensure the processor fixture is used or a new one is created
    
    transcript, error = processor._process_single_chunk(
        chunk_path, chunk_index, MOCK_FILE_FORMAT, MOCK_METADATA, MOCK_NUM_SPEAKERS
    )
    
    assert transcript == "Adjusted chunk transcript"
    assert error is None
    mock_api_process_chunk.assert_called_once_with(
        processor.client, processor.model_name, chunk_path, ANY, # ANY for prompt
        f"audio/{MOCK_FILE_FORMAT}", chunk_index
    )
    # adjust_chunk_timestamps needs the raw transcript and the start_offset_ms
    # The start_offset_ms is calculated as chunk_index * CHUNK_DURATION_MS
    expected_offset = chunk_index * CHUNK_DURATION_MS
    mock_adjust_timestamps.assert_called_once_with("Raw chunk transcript", expected_offset)


@patch('transcription_processor.api_client.process_audio_chunk')
def test_process_single_chunk_api_failure(mock_api_process_chunk, processor):
    chunk_path = "test_chunk.mp3"
    chunk_index = 0
    
    mock_api_process_chunk.return_value = (None, "API error during chunk processing")
    
    transcript, error = processor._process_single_chunk(
        chunk_path, chunk_index, MOCK_FILE_FORMAT, MOCK_METADATA, MOCK_NUM_SPEAKERS
    )
    
    assert transcript is None
    assert "API error during chunk processing" in error
    mock_api_process_chunk.assert_called_once()

# A test for prompt generation could also be useful if it's complex
def test_prompt_generation_in_processor(processor):
    # Access the prompt template from the processor instance
    prompt_template = processor.prompt_template 
    # If the prompt_template was not set (e.g. None), this test would fail or need adjustment
    assert prompt_template is not None 
    
    # Render the prompt with some test data
    # Ensure the prompt_template is a MagicMock that can be called if it was mocked at processor creation
    if isinstance(prompt_template, MagicMock):
        prompt_template.render.return_value = "Rendered Prompt"
        rendered_prompt = prompt_template.render(metadata=MOCK_METADATA, num_speakers=MOCK_NUM_SPEAKERS)
        assert "Rendered Prompt" in rendered_prompt
        prompt_template.render.assert_called_once_with(metadata=MOCK_METADATA, num_speakers=MOCK_NUM_SPEAKERS)
    else:
        # This case would apply if a real Template object was loaded and passed to the processor
        # For this set of tests, the prompt_template is mocked in the fixture.
        pass

```
