import pytest
from unittest.mock import patch, MagicMock
import os
from jinja2 import Template

# Assuming config.py and api_client.py are in the parent directory or accessible in PYTHONPATH
from config import GEMINI_MODELS, DEFAULT_MODEL
from api_client import initialize_gemini, get_transcription_prompt, process_audio_chunk

@pytest.fixture
def mock_st_secrets(mocker):
    """Fixture to mock streamlit.secrets."""
    mock_secrets = MagicMock()
    mocker.patch('api_client.st.secrets', mock_secrets, create=True) # Use create=True if st.secrets might not exist
    return mock_secrets

@pytest.fixture
def mock_os_environ(mocker):
    """Fixture to mock os.environ."""
    mock_environ = {}
    mocker.patch.dict(os.environ, mock_environ, clear=True)
    return mock_environ

@pytest.fixture
def mock_genai_client(mocker):
    """Fixture to mock google.generativeai configuration and models."""
    # Mock the configure function
    mocker.patch('api_client.genai.configure')
    
    # Mock the GeminiClient class that we create
    mock_client_instance = MagicMock()
    mock_client_instance.models = mock_client_instance
    mock_client_instance.files = mock_client_instance
    
    # Return the mock instance
    return mock_client_instance, None

# Tests for initialize_gemini
def test_initialize_gemini_st_secrets_google_api_key(mock_st_secrets, mock_genai_client, mock_os_environ, mocker):
    mock_st_secrets.GOOGLE_API_KEY = "streamlit_google_key"
    mock_configure = mocker.patch('api_client.genai.configure')
    
    client, error, model_id = initialize_gemini()
    assert client is not None
    assert error is None
    assert model_id == GEMINI_MODELS[DEFAULT_MODEL]
    mock_configure.assert_called_once_with(api_key="streamlit_google_key")

def test_initialize_gemini_st_secrets_gemini_api_key(mock_st_secrets, mock_genai_client, mock_os_environ, mocker):
    # Make GOOGLE_API_KEY unavailable in st.secrets
    mock_st_secrets.get = lambda key, default=None: None
    mock_st_secrets.secrets = {"GEMINI_API_KEY": "streamlit_gemini_key"}
    if hasattr(mock_st_secrets, 'GOOGLE_API_KEY'):
        del mock_st_secrets.GOOGLE_API_KEY
    
    mock_configure = mocker.patch('api_client.genai.configure')
    
    client, error, model_id = initialize_gemini()
    assert client is not None
    assert error is None
    assert model_id == GEMINI_MODELS[DEFAULT_MODEL]
    mock_configure.assert_called_once_with(api_key="streamlit_gemini_key")


def test_initialize_gemini_os_environ_google_api_key(mock_os_environ, mock_genai_client, mock_st_secrets, mocker):
    mock_os_environ["GOOGLE_API_KEY"] = "env_google_key"
    mock_st_secrets.get = lambda key, default=None: None
    if hasattr(mock_st_secrets, 'GOOGLE_API_KEY'): del mock_st_secrets.GOOGLE_API_KEY
    if hasattr(mock_st_secrets, 'secrets'): del mock_st_secrets.secrets
    
    mock_configure = mocker.patch('api_client.genai.configure')
    
    client, error, model_id = initialize_gemini()
    assert client is not None
    assert error is None
    assert model_id == GEMINI_MODELS[DEFAULT_MODEL]
    mock_configure.assert_called_once_with(api_key="env_google_key")

def test_initialize_gemini_os_environ_gemini_api_key(mock_os_environ, mock_genai_client, mock_st_secrets, mocker):
    mock_os_environ["GEMINI_API_KEY"] = "env_gemini_key"
    mock_st_secrets.get = lambda key, default=None: None
    if hasattr(mock_st_secrets, 'GOOGLE_API_KEY'): del mock_st_secrets.GOOGLE_API_KEY
    if hasattr(mock_st_secrets, 'secrets'): del mock_st_secrets.secrets
    if "GOOGLE_API_KEY" in mock_os_environ: del mock_os_environ["GOOGLE_API_KEY"]
    
    mock_configure = mocker.patch('api_client.genai.configure')
    
    client, error, model_id = initialize_gemini()
    assert client is not None
    assert error is None
    assert model_id == GEMINI_MODELS[DEFAULT_MODEL]
    mock_configure.assert_called_once_with(api_key="env_gemini_key")

def test_initialize_gemini_no_api_key(mock_os_environ, mock_st_secrets, mock_genai_client):
    # Ensure no keys are found anywhere
    mock_st_secrets.get = lambda key, default=None: None
    if hasattr(mock_st_secrets, 'GOOGLE_API_KEY'): del mock_st_secrets.GOOGLE_API_KEY
    if hasattr(mock_st_secrets, 'secrets'): del mock_st_secrets.secrets
    if "GOOGLE_API_KEY" in mock_os_environ: del mock_os_environ["GOOGLE_API_KEY"]
    if "GEMINI_API_KEY" in mock_os_environ: del mock_os_environ["GEMINI_API_KEY"]

    client, error, model_id = initialize_gemini()
    assert client is None
    assert "API key not found" in error
    assert model_id is None

def test_initialize_gemini_client_init_exception(mock_st_secrets, mock_genai_client, mock_os_environ, mocker):
    mock_st_secrets.GOOGLE_API_KEY = "some_key"
    mock_configure = mocker.patch('api_client.genai.configure', side_effect=Exception("GenAI client failed"))
    
    client, error, model_id = initialize_gemini()
    assert client is None
    assert "Failed to initialize Gemini client" in error
    assert model_id is None

def test_initialize_gemini_invalid_model_name(mock_st_secrets, mock_genai_client, mock_os_environ, mocker):
    mock_st_secrets.GOOGLE_API_KEY = "some_key"
    mock_warning = mocker.patch('api_client.st.warning')
    mock_configure = mocker.patch('api_client.genai.configure')
    
    # Test with a model name not in GEMINI_MODELS (values)
    invalid_model_name = "gemini-invalid-model"
    client, error, model_id = initialize_gemini(model_name=invalid_model_name)
    
    assert client is not None
    assert error is None
    # Should fall back to the default model ID
    assert model_id == GEMINI_MODELS[DEFAULT_MODEL]
    mock_configure.assert_called_once_with(api_key="some_key")
    mock_warning.assert_called_once()

def test_initialize_gemini_specific_valid_model_name(mock_st_secrets, mock_genai_client, mock_os_environ, mocker):
    mock_st_secrets.GOOGLE_API_KEY = "some_key"
    mock_configure = mocker.patch('api_client.genai.configure')
    
    # Pick a specific model from config
    specific_model_key = list(GEMINI_MODELS.keys())[0]
    specific_model_id = GEMINI_MODELS[specific_model_key]
    
    client, error, model_id = initialize_gemini(model_name=specific_model_id)
    assert client is not None
    assert error is None
    assert model_id == specific_model_id
    mock_configure.assert_called_once_with(api_key="some_key")

# Tests for get_transcription_prompt
def test_get_transcription_prompt_returns_template():
    prompt = get_transcription_prompt()
    assert isinstance(prompt, Template)

def test_get_transcription_prompt_renders_with_metadata():
    metadata = {
        "content_type": "podcast",
        "description": "Weekly tech news",
        "topic": "AI developments",
        "language": "English"
    }
    num_speakers = 2
    prompt_template = get_transcription_prompt(metadata=metadata)
    rendered_prompt = prompt_template.render(num_speakers=num_speakers, metadata=metadata)

    assert "podcast" in rendered_prompt
    assert "Weekly tech news" in rendered_prompt
    assert "AI developments" in rendered_prompt
    assert "Language: English" in rendered_prompt
    assert f"Number of distinct speakers: {num_speakers}" in rendered_prompt
    assert "Speaker 1:" in rendered_prompt # Example format

def test_get_transcription_prompt_renders_without_optional_metadata():
    num_speakers = 1
    prompt_template = get_transcription_prompt(metadata=None) # No metadata
    rendered_prompt = prompt_template.render(num_speakers=num_speakers, metadata=None)

    assert "Description:" not in rendered_prompt
    assert "Topic:" not in rendered_prompt
    assert "Language:" not in rendered_prompt
    assert "content_type: audio file" # Default content type
    assert f"Number of distinct speakers: {num_speakers}" in rendered_prompt

# Tests for process_audio_chunk (mocking API calls heavily)
@pytest.fixture
def mock_gemini_process_flow(mock_genai_client):
    client_instance, _ = mock_genai_client
    
    # Mock file upload
    mock_uploaded_file = MagicMock()
    client_instance.files.upload.return_value = mock_uploaded_file
    
    # Mock content generation
    mock_response = MagicMock()
    # Simulate the structure of the response object based on usage in process_audio_chunk
    # Option 1: response has .text attribute
    # mock_response.text = "This is a dummy transcript."
    # Option 2: response has .candidates
    mock_candidate = MagicMock()
    mock_part = MagicMock()
    mock_part.text = "This is a dummy transcript from candidate."
    mock_candidate.content.parts = [mock_part]
    mock_response.candidates = [mock_candidate]

    client_instance.models.generate_content.return_value = mock_response
    
    return client_instance, mock_uploaded_file, mock_response

def test_process_audio_chunk_success(mock_gemini_process_flow):
    client, _, _ = mock_gemini_process_flow
    model_name = "gemini-test-model"
    chunk_path = "/fake/path/to/chunk.mp3"
    prompt = "Transcribe this."
    mime_type = "audio/mpeg"
    chunk_index = 0

    transcript, error = process_audio_chunk(client, model_name, chunk_path, prompt, mime_type, chunk_index)

    assert error is None
    assert "dummy transcript" in transcript # Check based on mock_response content
    client.files.upload.assert_called_once_with(file=chunk_path, config={"mimeType": mime_type})
    client.models.generate_content.assert_called_once() # Basic check, can be more specific

def test_process_audio_chunk_upload_failure(mock_gemini_process_flow):
    client, _, _ = mock_gemini_process_flow
    client.files.upload.side_effect = Exception("Upload failed")

    transcript, error = process_audio_chunk(client, "m", "/p", "pr", "mi", 0)
    assert transcript is None
    assert "Upload failed" in error or "Chunk upload failed" in error # Depending on error handling in main code
    client.models.generate_content.assert_not_called()

def test_process_audio_chunk_transcription_failure(mock_gemini_process_flow):
    client, _, _ = mock_gemini_process_flow
    client.models.generate_content.side_effect = Exception("Transcription API error")

    transcript, error = process_audio_chunk(client, "m", "/p", "pr", "mi", 0)
    assert transcript is None
    assert "Transcription API error" in error
    client.files.upload.assert_called_once() # Upload should still be called

def test_process_audio_chunk_text_extraction_failure(mock_gemini_process_flow):
    client, _, mock_response = mock_gemini_process_flow
    # Make the response object such that text extraction fails (e.g., no .text and no .candidates)
    if hasattr(mock_response, 'text'): del mock_response.text
    if hasattr(mock_response, 'candidates'): del mock_response.candidates
    # Or, make candidates an empty list, or parts an empty list, etc.
    # mock_response.candidates = [] 

    transcript, error = process_audio_chunk(client, "m", "/p", "pr", "mi", 0)
    assert transcript is None
    assert "Could not extract transcript text" in error

def test_process_audio_chunk_upload_auth_error(mock_gemini_process_flow):
    client, _, _ = mock_gemini_process_flow
    client.files.upload.side_effect = Exception("unauthorized access")
    transcript, error = process_audio_chunk(client, "m", "/p", "pr", "mi", 0)
    assert transcript is None
    assert "API authentication error" in error

def test_process_audio_chunk_upload_quota_error(mock_gemini_process_flow):
    client, _, _ = mock_gemini_process_flow
    client.files.upload.side_effect = Exception("quota exceeded")
    transcript, error = process_audio_chunk(client, "m", "/p", "pr", "mi", 0)
    assert transcript is None
    assert "API quota exceeded" in error
