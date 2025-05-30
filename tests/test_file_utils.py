import pytest
from unittest.mock import MagicMock, patch, mock_open
import os
import shutil

# Assuming config.py is in the parent directory or accessible in PYTHONPATH
from config import ALLOWED_AUDIO_TYPES, MAX_FILE_SIZE, CHUNK_DURATION_MS
from file_utils import (
    validate_audio_file,
    chunk_audio_file,
    cleanup_file,
    cleanup_directory,
    create_temp_file
)

# Mock Streamlit's UploadedFile
class MockUploadedFile:
    def __init__(self, name, type, size):
        self.name = name
        self.type = type
        self.size = size
        self.getvalue = MagicMock(return_value=b"dummy audio data")

@pytest.fixture
def mock_config(mocker):
    mocker.patch('file_utils.ALLOWED_AUDIO_TYPES', ['audio/mpeg', 'audio/wav'])
    mocker.patch('file_utils.MAX_FILE_SIZE', 10 * 1024 * 1024) # 10 MB
    mocker.patch('file_utils.CHUNK_DURATION_MS', 60000) # 1 minute

def test_validate_audio_file_valid(mock_config):
    """Test with a valid audio file."""
    valid_file = MockUploadedFile("audio.mp3", "audio/mpeg", 5 * 1024 * 1024) # 5 MB
    assert validate_audio_file(valid_file) is True

def test_validate_audio_file_invalid_type(mock_config):
    """Test with an invalid file type."""
    invalid_file = MockUploadedFile("document.txt", "text/plain", 1 * 1024 * 1024)
    assert validate_audio_file(invalid_file) is False

def test_validate_audio_file_too_large(mock_config):
    """Test with a file that is too large."""
    large_file = MockUploadedFile("large_audio.wav", "audio/wav", 15 * 1024 * 1024) # 15 MB
    assert validate_audio_file(large_file) is False

def test_validate_audio_file_none():
    """Test with None as input."""
    assert validate_audio_file(None) is False

@patch('file_utils.os.chmod')
@patch('file_utils.os.fdopen')
@patch('file_utils.tempfile.mkstemp')
def test_create_temp_file_success(mock_mkstemp, mock_fdopen, mock_chmod):
    mock_fd = 123  # Mock file descriptor
    mock_path = "mock_temp_file.mp3"
    mock_mkstemp.return_value = (mock_fd, mock_path)

    # This is what fdopen will return, capable of being used in a 'with' statement
    mock_file_object = MagicMock() 
    mock_fdopen.return_value.__enter__.return_value = mock_file_object

    audio_data = b"some audio data"
    filename_suffix = "test_file.mp3" # This is the suffix passed to mkstemp

    path, success = create_temp_file(audio_data, filename_suffix)

    assert success is True
    assert path == mock_path
    mock_mkstemp.assert_called_once_with(suffix=filename_suffix)
    # os.chmod is called first with the path
    mock_chmod.assert_called_once_with(mock_path, 0o600)
    # then os.fdopen is called with the file descriptor
    mock_fdopen.assert_called_once_with(mock_fd, 'wb')
    # finally, write is called on the file object returned by fdopen
    mock_file_object.write.assert_called_once_with(audio_data)


@patch('file_utils.tempfile.mkstemp', side_effect=Exception("Failed to create temp file"))
def test_create_temp_file_failure(mock_mkstemp):
    audio_data = b"some audio data"
    filename = "test_file.mp3"
    path, success = create_temp_file(audio_data, filename)
    assert success is False
    assert path is None

@patch('file_utils.os.path.exists')
@patch('file_utils.os.unlink')
def test_cleanup_file_exists(mock_unlink, mock_exists):
    """Test cleanup_file when the file exists."""
    mock_exists.return_value = True
    file_path = "dummy_file.txt"
    assert cleanup_file(file_path) is True
    mock_unlink.assert_called_once_with(file_path)

@patch('file_utils.os.path.exists')
@patch('file_utils.os.unlink')
def test_cleanup_file_not_exists(mock_unlink, mock_exists):
    """Test cleanup_file when the file does not exist."""
    mock_exists.return_value = False
    file_path = "dummy_file.txt"
    assert cleanup_file(file_path) is True
    mock_unlink.assert_not_called()

@patch('file_utils.os.path.exists')
@patch('file_utils.os.unlink', side_effect=OSError("Test OS Error"))
def test_cleanup_file_os_error(mock_unlink, mock_exists):
    """Test cleanup_file when os.unlink raises an OSError."""
    mock_exists.return_value = True
    file_path = "dummy_file.txt"
    assert cleanup_file(file_path) is False
    mock_unlink.assert_called_once_with(file_path)

@patch('file_utils.os.path.exists')
@patch('file_utils.shutil.rmtree')
def test_cleanup_directory_exists(mock_rmtree, mock_exists):
    """Test cleanup_directory when the directory exists."""
    mock_exists.return_value = True
    dir_path = "dummy_dir"
    assert cleanup_directory(dir_path) is True
    mock_rmtree.assert_called_once_with(dir_path)

@patch('file_utils.os.path.exists')
@patch('file_utils.shutil.rmtree')
def test_cleanup_directory_not_exists(mock_rmtree, mock_exists):
    """Test cleanup_directory when the directory does not exist."""
    mock_exists.return_value = False
    dir_path = "dummy_dir"
    assert cleanup_directory(dir_path) is True
    mock_rmtree.assert_not_called()

@patch('file_utils.os.path.exists')
@patch('file_utils.shutil.rmtree', side_effect=OSError("Test OS Error"))
def test_cleanup_directory_os_error(mock_rmtree, mock_exists):
    """Test cleanup_directory when shutil.rmtree raises an OSError."""
    mock_exists.return_value = True
    dir_path = "dummy_dir"
    assert cleanup_directory(dir_path) is False
    mock_rmtree.assert_called_once_with(dir_path)


# More complex tests for chunk_audio_file would require deeper mocking of pydub
# For now, let's focus on a basic case or mock AudioSegment heavily.

@patch('file_utils.AudioSegment.from_file')
@patch('file_utils.tempfile.mkdtemp')
@patch('file_utils.os.path.join', side_effect=lambda *args: "/".join(args)) # Simple mock for os.path.join
@patch('file_utils.os.chmod') # Mock chmod for directory and files
def test_chunk_audio_file_basic(mock_chmod, mock_join, mock_mkdtemp, mock_from_file, mock_config):
    # Mock AudioSegment object
    mock_audio_segment = MagicMock()
    mock_audio_segment.__len__.return_value = 150000 # 2.5 minutes in ms
    
    # Mock the export method of the audio segment and its slices
    mock_audio_segment.export.return_value = None 
    mock_audio_segment.__getitem__.return_value = mock_audio_segment # Slicing returns the same mock

    mock_from_file.return_value = mock_audio_segment
    mock_mkdtemp.return_value = "/tmp/fake_temp_dir"

    audio_data = b"dummy_audio_data"
    file_format = "mp3"
    
    # CHUNK_DURATION_MS is 60000 (1 minute) from mock_config
    # Total duration 150000ms / 60000ms_per_chunk = 2.5 -> 3 chunks
    
    chunk_paths, num_chunks = chunk_audio_file(audio_data, file_format)

    assert num_chunks == 3
    assert len(chunk_paths) == 3
    assert chunk_paths[0] == "/tmp/fake_temp_dir/chunk_0.mp3"
    assert chunk_paths[1] == "/tmp/fake_temp_dir/chunk_1.mp3"
    assert chunk_paths[2] == "/tmp/fake_temp_dir/chunk_2.mp3"
    
    mock_from_file.assert_called_once() # Check if from_file was called
    assert mock_audio_segment.export.call_count == 3 # Check if export was called for each chunk

@patch('file_utils.AudioSegment.from_file', side_effect=Exception("Pydub error"))
def test_chunk_audio_file_load_error(mock_from_file, mock_config):
    audio_data = b"bad_audio_data"
    file_format = "mp3"
    chunk_paths, num_chunks = chunk_audio_file(audio_data, file_format)
    assert num_chunks == 0
    assert len(chunk_paths) == 0

@patch('file_utils.AudioSegment.from_file')
@patch('file_utils.tempfile.mkdtemp')
@patch('file_utils.cleanup_directory') # Mock cleanup_directory
def test_chunk_audio_file_general_exception(mock_cleanup, mock_mkdtemp, mock_from_file, mock_config):
    # Make mkdtemp raise an exception to simulate a general error
    mock_mkdtemp.side_effect = Exception("General error during chunking")
    
    mock_audio_segment = MagicMock()
    mock_audio_segment.__len__.return_value = 150000 # 2.5 minutes in ms
    mock_from_file.return_value = mock_audio_segment
    
    audio_data = b"dummy_audio_data"
    file_format = "mp3"
    
    chunk_paths, num_chunks = chunk_audio_file(audio_data, file_format)
    
    assert num_chunks == 0
    assert len(chunk_paths) == 0
    # Check if cleanup_directory was called if temp_dir was created before exception
    # In this setup, if mkdtemp fails, temp_dir might not be set, so cleanup might not be called.
    # If the exception happened after mkdtemp, cleanup would be expected.
    # For this specific mock (mkdtemp fails), cleanup_directory will not be called.
    mock_cleanup.assert_not_called()

@patch('file_utils.AudioSegment.from_file')
@patch('file_utils.tempfile.mkdtemp')
@patch('file_utils.os.chmod')
@patch('file_utils.cleanup_directory')
def test_chunk_audio_file_export_failure(mock_cleanup, mock_chmod, mock_mkdtemp, mock_from_file, mock_config):
    mock_audio_segment = MagicMock()
    mock_audio_segment.__len__.return_value = 120000 # 2 minutes
    mock_audio_segment.export.side_effect = Exception("Chunk export failed") # Simulate export failure
    mock_audio_segment.__getitem__.return_value = mock_audio_segment
    
    mock_from_file.return_value = mock_audio_segment
    mock_mkdtemp.return_value = "/tmp/fake_temp_dir"
    
    audio_data = b"data"
    file_format = "mp3"
    
    chunk_paths, num_chunks = chunk_audio_file(audio_data, file_format)
    
    assert num_chunks == 2 # It calculates 2 chunks
    assert len(chunk_paths) == 0 # But no paths are returned due to export failure
    # The function should try to create all chunks, then return what succeeded.
    # In this mock, all exports fail, so an empty list is expected.
    # The cleanup_directory should be called if temp_dir was created.
    mock_cleanup.assert_called_once_with("/tmp/fake_temp_dir")

@patch('file_utils.AudioSegment.from_file')
@patch('file_utils.tempfile.mkdtemp')
@patch('file_utils.os.chmod')
@patch('file_utils.os.path.join', side_effect=lambda *args: "/".join(args))
def test_cleanup_chunks_basic(mock_join, mock_chmod, mock_mkdtemp, mock_from_file, mock_config):
    # This is not testing cleanup_chunks directly but ensuring the flow within chunk_audio_file
    # that might call cleanup_directory if things go wrong.
    # A direct test for cleanup_chunks would be:
    
    mock_unlink = MagicMock()
    mock_rmdir = MagicMock()
    mock_listdir = MagicMock(return_value=[]) # Empty directory

    with patch('file_utils.os.unlink', mock_unlink), \
         patch('file_utils.os.rmdir', mock_rmdir), \
         patch('file_utils.os.path.exists', return_value=True), \
         patch('file_utils.os.listdir', mock_listdir):
        
        from file_utils import cleanup_chunks # Re-import for local scope patching
        
        chunk_paths_to_clean = ["/tmp/test_dir/chunk_0.mp3", "/tmp/test_dir/chunk_1.mp3"]
        cleanup_chunks(chunk_paths_to_clean)

        assert mock_unlink.call_count == 2
        mock_unlink.assert_any_call("/tmp/test_dir/chunk_0.mp3")
        mock_unlink.assert_any_call("/tmp/test_dir/chunk_1.mp3")
        mock_rmdir.assert_called_once_with("/tmp/test_dir") # Assumes temp_dir is derived correctly

def test_cleanup_chunks_empty_list():
    from file_utils import cleanup_chunks
    with patch('file_utils.os.unlink') as mock_unlink:
        cleanup_chunks([])
        mock_unlink.assert_not_called()

@patch('file_utils.os.path.exists', return_value=True)
@patch('file_utils.os.unlink', side_effect=Exception("unlink error"))
def test_cleanup_chunks_unlink_error(mock_unlink, mock_exists):
    from file_utils import cleanup_chunks
    # Should not raise an exception, just log a warning (not tested here)
    cleanup_chunks(["/tmp/some/path.mp3"])
    mock_unlink.assert_called_once()

@patch('file_utils.os.path.exists', return_value=True)
@patch('file_utils.os.unlink')
@patch('file_utils.os.listdir', return_value=["some_other_file.txt"]) # Dir not empty
@patch('file_utils.os.rmdir')
def test_cleanup_chunks_dir_not_empty(mock_rmdir, mock_listdir, mock_unlink, mock_exists):
    from file_utils import cleanup_chunks
    cleanup_chunks(["/tmp/my_chunks/chunk1.mp3"])
    mock_unlink.assert_called_once_with("/tmp/my_chunks/chunk1.mp3")
    mock_listdir.assert_called_once_with("/tmp/my_chunks")
    mock_rmdir.assert_not_called() # Because listdir returns content

@patch('file_utils.os.path.exists', side_effect=lambda x: x == "/tmp/my_chunks") # Only dir exists
@patch('file_utils.os.unlink')
@patch('file_utils.os.listdir', return_value=[])
@patch('file_utils.os.rmdir', side_effect=Exception("rmdir error"))
def test_cleanup_chunks_rmdir_error(mock_rmdir, mock_listdir, mock_unlink, mock_exists):
    from file_utils import cleanup_chunks
    # Should not raise an exception, just log a warning
    cleanup_chunks(["/tmp/my_chunks/chunk1.mp3"]) # chunk1.mp3 won't "exist" due to side_effect
    mock_unlink.assert_not_called() # Because os.path.exists for the chunk path will be false
    # temp_dir will be derived as "/tmp/my_chunks"
    # os.path.exists("/tmp/my_chunks") will be true
    # os.listdir("/tmp/my_chunks") will be []
    mock_rmdir.assert_called_once_with("/tmp/my_chunks")
