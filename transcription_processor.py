"""
Transcription processing module for ExactTranscriber.
This module contains the core logic for processing audio transcriptions.
"""
import logging
import tempfile
import os
import concurrent.futures
from typing import Dict, Any, Optional, Tuple, List

import streamlit as st
import google.generativeai as genai

from config import (
    CHUNK_DURATION_MS,
    MIME_TYPE_MAPPING,
    MAX_WORKERS,
    MIN_CHUNK_SUCCESS_PERCENTAGE
)
from api_client import get_transcription_prompt
from file_utils import chunk_audio_file, cleanup_chunks, cleanup_file
from transcript_utils import adjust_chunk_timestamps, combine_transcriptions
from utils import sanitize_error_message


class TranscriptionProcessor:
    """Handles the transcription processing logic."""
    
    def __init__(self, client: Any, model_name: str):
        self.client = client
        self.model_name = model_name
        self.logger = logging.getLogger(__name__)
    
    def process_audio(self, file_path: str, file_format: str, 
                     file_size_mb: float, metadata: Dict[str, Any], 
                     num_speakers: int) -> Tuple[Optional[str], Optional[str]]:
        """
        Process audio file for transcription.
        
        Args:
            file_path: Path to the audio file
            file_format: Format of the audio file
            file_size_mb: Size of the file in MB
            metadata: Metadata for the transcription
            num_speakers: Number of speakers in the audio
            
        Returns:
            Tuple of (transcript_text, error_message)
        """
        # Generate prompt
        prompt_template = get_transcription_prompt(metadata)
        prompt = prompt_template.render(num_speakers=num_speakers, metadata=metadata)
        
        # Determine if we need to chunk
        large_file = file_size_mb > 20
        
        if large_file:
            return self._process_large_file(file_path, file_format, prompt)
        else:
            return self._process_small_file(file_path, file_format, prompt)
    
    def _process_small_file(self, file_path: str, file_format: str, 
                           prompt: str) -> Tuple[Optional[str], Optional[str]]:
        """Process a small audio file without chunking."""
        mime_type = MIME_TYPE_MAPPING.get(file_format, f"audio/{file_format}")
        
        try:
            # Upload file
            file_obj = self.client.files.upload(file=file_path, config={"mimeType": mime_type})
        except Exception as upload_err:
            error_msg = sanitize_error_message(str(upload_err))
            self.logger.error(f"Failed to upload audio file: {error_msg}")
            
            # Check for common error indicators in the sanitized message
            if "unauthorized" in error_msg.lower() or "authentication error" in error_msg.lower() or "API key" in error_msg:
                return None, "API authentication error. Please check your API key."
            elif "quota" in error_msg.lower():
                return None, "API quota exceeded. Please try again later."
            else:
                return None, f"File upload failed: {error_msg}"
        
        try:
            # Generate transcription
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt, file_obj]
            )
            
            response_text = (response.text if hasattr(response, 'text') 
                           else response.candidates[0].content.parts[0].text)
            return response_text, None
            
        except Exception as transcribe_err:
            error_msg = sanitize_error_message(str(transcribe_err))
            self.logger.error(f"Transcription API error: {error_msg}")
            return None, f"Transcription failed: {error_msg}"
    
    def _process_large_file(self, file_path: str, file_format: str,
                           prompt: str) -> Tuple[Optional[str], Optional[str]]:
        """Process a large audio file by chunking."""
        # Read file data
        with open(file_path, 'rb') as f:
            audio_data = f.read()
        
        # Chunk the audio
        chunk_paths, num_chunks = chunk_audio_file(audio_data, file_format, CHUNK_DURATION_MS)
        if num_chunks == 0 or not chunk_paths:
            return None, "Failed to split audio file."
        
        try:
            # Process chunks in parallel
            all_transcriptions = self._process_chunks_parallel(
                chunk_paths, num_chunks, prompt, file_format
            )
            
            # Combine results
            if all_transcriptions and len(all_transcriptions) >= num_chunks * MIN_CHUNK_SUCCESS_PERCENTAGE:
                combined_transcription = combine_transcriptions(all_transcriptions)
                return combined_transcription, None
            else:
                # Fallback to full file processing
                self.logger.info("Falling back to full audio transcription due to chunk errors.")
                return self._process_small_file(file_path, file_format, prompt)
                
        finally:
            # Always cleanup chunks
            cleanup_chunks(chunk_paths)
    
    def _process_chunks_parallel(self, chunk_paths: List[str], num_chunks: int,
                                prompt: str, file_format: str) -> List[str]:
        """Process audio chunks in parallel."""
        chunk_args = [(i, chunk_path) for i, chunk_path in enumerate(chunk_paths)]
        all_transcriptions = []
        
        def process_chunk_worker(args):
            i, chunk_path = args
            return self._process_single_chunk(i, chunk_path, prompt, file_format, num_chunks)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            results = executor.map(process_chunk_worker, chunk_args)
            all_transcriptions = [res for res in results if res is not None]
        
        return all_transcriptions
    
    def _process_single_chunk(self, chunk_index: int, chunk_path: str,
                             prompt: str, file_format: str, 
                             num_chunks: int) -> Optional[str]:
        """Process a single audio chunk."""
        try:
            mime_type = MIME_TYPE_MAPPING.get(file_format, f"audio/{file_format}")
            
            # Upload chunk
            try:
                chunk_file = self.client.files.upload(file=chunk_path, config={"mimeType": mime_type})
            except Exception as upload_err:
                error_msg = sanitize_error_message(str(upload_err))
                self.logger.error(f"Failed to upload chunk {chunk_index+1}: {error_msg}")
                
                if "unauthorized" in error_msg.lower() or "authentication" in error_msg.lower() or "API key" in error_msg:
                    raise ValueError(f"API authentication error") # Generic message, already sanitized
                if "quota" in error_msg.lower():
                    raise ValueError(f"API quota exceeded") # Generic message
                raise ValueError(f"Chunk upload failed") # Generic message
            
            # Transcribe chunk
            try:
                chunk_response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[prompt, chunk_file],
                )
            except Exception as transcribe_err:
                error_msg = sanitize_error_message(str(transcribe_err))
                self.logger.error(f"Failed to transcribe chunk {chunk_index+1}: {error_msg}")
                raise ValueError(f"Transcription API error") # Generic message
            
            # Extract text
            try:
                chunk_text = (chunk_response.text if hasattr(chunk_response, 'text') 
                            else chunk_response.candidates[0].content.parts[0].text)
            except Exception as extract_err:
                # This error is internal, not directly user-facing, but log it cleanly.
                self.logger.error(f"Failed to extract text from chunk {chunk_index+1} response: {str(extract_err)}")
                raise ValueError(f"Could not extract transcript text") # Generic message
            
            # Adjust timestamps
            adjusted_transcription = adjust_chunk_timestamps(chunk_text, chunk_index, CHUNK_DURATION_MS)
            self.logger.info(f"Successfully processed chunk {chunk_index+1}/{num_chunks}")
            return adjusted_transcription
            
        except ValueError: # Catch specific, somewhat generic errors raised above
            return None
        except Exception as e: # Catch any other unexpected errors and sanitize them
            self.logger.error(f"Unexpected error processing chunk {chunk_index+1}: {sanitize_error_message(str(e))}", exc_info=True)
            return None
# Removed _sanitize_error method by deleting its definition.


def process_transcription_task(client: Any, model_name: str, uploaded_file,
                              metadata: Dict[str, Any], num_speakers: int) -> Dict[str, Any]:
    """
    Process a transcription task and return results.
    
    Args:
        client: Gemini client
        model_name: Model ID to use
        uploaded_file: Streamlit uploaded file object
        metadata: Transcription metadata
        num_speakers: Number of speakers
        
    Returns:
        Dictionary with transcription result or error
    """
    processor = TranscriptionProcessor(client, model_name)
    file_path = None
    
    try:
        # Get audio data
        audio_data = uploaded_file.getvalue()
        file_format = uploaded_file.type.split('/')[-1]
        if file_format == 'mpeg':
            file_format = 'mp3'
        elif file_format == 'x-wav':
            file_format = 'wav'
        
        file_size_mb = uploaded_file.size / (1024 * 1024)
        
        # Create temporary file
        from file_utils import create_temp_file
        file_path, success = create_temp_file(audio_data, uploaded_file.name)
        if not success or not file_path:
            # This is an internal error, but sanitize if it were to become user-facing
            raise Exception(sanitize_error_message("Failed to create temporary file for audio processing"))
        
        # Process audio
        transcript_text, error_message = processor.process_audio(
            file_path, file_format, file_size_mb, metadata, num_speakers
        )
        
        if error_message:
            # error_message from processor.process_audio should already be sanitized
            return {"success": False, "error": error_message}
        else:
            return {"success": True, "transcript": transcript_text}
            
    except Exception as e:
        error_str = str(e)
        self.logger.error(f"Unexpected error in transcription task: {sanitize_error_message(error_str)}", exc_info=True)
        return {"success": False, "error": sanitize_error_message(error_str)}
        
    finally:
        # Cleanup temporary file
        if file_path:
            cleanup_file(file_path)