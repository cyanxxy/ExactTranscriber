"""
Utility functions for file handling operations in ExactTranscriber.
This module provides functions for managing temporary files and audio processing.
"""
import os
import tempfile
import logging
import shutil
from typing import List, Tuple, BinaryIO, Union, Optional
import streamlit as st

from pydub import AudioSegment
import io

from config import (
    ALLOWED_AUDIO_TYPES,
    MAX_FILE_SIZE,
    CHUNK_DURATION_MS
)

def validate_audio_file(file) -> bool:
    """
    Validate uploaded audio file.
    
    Args:
        file: Audio file uploaded through Streamlit
        
    Returns:
        bool: True if file is valid, False otherwise
    """
    if file is None:
        return False

    file_type = file.type
    
    if file_type not in ALLOWED_AUDIO_TYPES:
        logging.warning(f"Invalid file type: {file_type}")
        return False

    if file.size > MAX_FILE_SIZE:
        logging.warning(f"File too large: {file.size / (1024 * 1024):.1f} MB")
        return False

    return True

def create_temp_file(audio_data: bytes, filename: str) -> Tuple[str, bool]:
    """
    Create a temporary file with the given audio data.
    
    Args:
        audio_data: Binary audio data
        filename: Name to use in the temporary file
        
    Returns:
        Tuple of (file_path, success)
    """
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=filename, mode='wb') as tmp_file:
            tmp_file.write(audio_data)
            file_path = tmp_file.name
            logging.info(f"Created temporary file: {file_path}")
        
        try:
            os.chmod(file_path, 0o600)  # Read/write for owner only
        except Exception as e:
            logging.warning(f"Could not set permissions on temporary file: {e}")
            
        return file_path, True
        
    except Exception as e:
        logging.error(f"Failed to create temporary file: {e}")
        return None, False

def cleanup_file(file_path: str) -> bool:
    """
    Safely remove a temporary file.
    
    Args:
        file_path: Path to the file to remove
        
    Returns:
        bool: True if cleanup was successful, False otherwise
    """
    if not file_path or not os.path.exists(file_path):
        return True
        
    try:
        os.unlink(file_path)
        logging.info(f"Removed temporary file: {file_path}")
        return True
    except Exception as e:
        logging.warning(f"Failed to remove temporary file {file_path}: {e}")
        return False

def cleanup_directory(dir_path: str) -> bool:
    """
    Safely remove a temporary directory and all its contents.
    
    Args:
        dir_path: Path to the directory to remove
        
    Returns:
        bool: True if cleanup was successful, False otherwise
    """
    if not dir_path or not os.path.exists(dir_path):
        return True
        
    try:
        shutil.rmtree(dir_path)
        logging.info(f"Removed temporary directory: {dir_path}")
        return True
    except Exception as e:
        logging.warning(f"Failed to remove temporary directory {dir_path}: {e}")
        return False

def chunk_audio_file(audio_data: bytes, file_format: str, 
                     chunk_duration_ms: int = CHUNK_DURATION_MS) -> Tuple[List[str], int]:
    """
    Split an audio file into chunks of specified duration.
    
    Args:
        audio_data: Binary audio data
        file_format: Format of the audio file (e.g., 'mp3', 'wav')
        chunk_duration_ms: Duration of each chunk in milliseconds
        
    Returns:
        Tuple of (list of paths to temporary chunk files, number of chunks)
    """
    temp_dir = None
    chunk_paths = []
    
    try:
        # Load audio from binary data
        try:
            audio = AudioSegment.from_file(io.BytesIO(audio_data), format=file_format)
        except Exception as audio_load_err:
            error_msg = f"Failed to load audio data: {audio_load_err}"
            logging.error(error_msg)
            return [], 0
        
        # Get the total length of the audio in milliseconds
        total_duration = len(audio)
        
        # Calculate number of chunks
        num_chunks = (total_duration // chunk_duration_ms) + (1 if total_duration % chunk_duration_ms > 0 else 0)
        logging.info(f"Splitting {file_format} audio ({total_duration/1000:.2f} seconds) into {num_chunks} chunks")
        
        # Create temporary directory to store chunks
        temp_dir = tempfile.mkdtemp()
        logging.info(f"Created temporary directory for chunks: {temp_dir}")
        
        # Set secure permissions for the temporary directory (if on Unix-like OS)
        try:
            os.chmod(temp_dir, 0o700)  # Read/write/execute for owner only
        except Exception as perm_err:
            logging.warning(f"Could not set permissions on temp directory: {perm_err}")
        
        # Split audio into chunks
        for i in range(num_chunks):
            try:
                start_time = i * chunk_duration_ms
                end_time = min((i + 1) * chunk_duration_ms, total_duration)
                
                # Extract chunk
                chunk = audio[start_time:end_time]
                
                # Create temporary file for chunk
                chunk_path = os.path.join(temp_dir, f"chunk_{i}.{file_format}")
                chunk.export(chunk_path, format=file_format)
                
                # Set secure permissions for the chunk file (if on Unix-like OS)
                try:
                    os.chmod(chunk_path, 0o600)  # Read/write for owner only
                except Exception as file_perm_err:
                    logging.warning(f"Could not set permissions on chunk file {i}: {file_perm_err}")
                
                # Add to list of chunk file paths
                chunk_paths.append(chunk_path)
                logging.info(f"Created chunk {i+1}/{num_chunks}: {chunk_path}")
            except Exception as chunk_err:
                # Log the error but continue processing other chunks
                logging.error(f"Error creating chunk {i}: {chunk_err}")
        
        if not chunk_paths:
            raise Exception("Failed to create any valid audio chunks")
            
        return chunk_paths, num_chunks
    
    except Exception as e:
        logging.error(f"Error splitting audio file: {e}")
        # Clean up if an error occurred 
        if temp_dir and os.path.exists(temp_dir):
            cleanup_directory(temp_dir)
        return [], 0

def cleanup_chunks(chunk_paths: List[str]) -> None:
    """
    Clean up chunk files and their parent directory.
    
    Args:
        chunk_paths: List of paths to chunk files
    """
    if not chunk_paths:
        return
        
    logging.info(f"Cleaning up {len(chunk_paths)} chunk files...")
    temp_dir = None
    
    for chunk_path in chunk_paths:
        if os.path.exists(chunk_path):
            try: 
                os.unlink(chunk_path)
                if not temp_dir:
                    temp_dir = os.path.dirname(chunk_path)
            except Exception as e: 
                logging.warning(f"Failed to remove chunk file {chunk_path}: {e}")
    
    # Try to remove the temp directory if it exists and is empty
    if temp_dir and os.path.exists(temp_dir):
        try:
            if not os.listdir(temp_dir): 
                os.rmdir(temp_dir)
                logging.info(f"Removed temporary directory: {temp_dir}")
        except Exception as e:
            logging.warning(f"Failed to remove temp directory {temp_dir}: {e}")
