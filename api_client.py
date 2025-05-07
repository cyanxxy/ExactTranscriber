"""
API Client module for ExactTranscriber.
This module provides functions for interacting with the Gemini API.
"""
import os
import logging
from typing import Tuple, Dict, Any, Optional, List

import streamlit as st
from google import genai
from jinja2 import Template

from config import GEMINI_MODELS, DEFAULT_MODEL

def initialize_gemini(model_name: Optional[str] = None) -> Tuple[Any, Optional[str], str]:
    """
    Initialize the Gemini client.
    Uses API key from Streamlit secrets or environment variables.
    
    Args:
        model_name: The name of the Gemini model to use. If None, uses the default.
        
    Returns:
        Tuple (genai.Client, error_message, model_name):
            - genai.Client: The client object, or None if initialization fails
            - error_message: Error message string if initialization fails, otherwise None
            - model_name: The model name that will be used
    """
    # If no model specified, use default from model mapping
    if not model_name:
        model_id = GEMINI_MODELS.get(DEFAULT_MODEL)
    else:
        model_id = model_name
    
    api_key = None
    error_message = None

    # Try getting API key from Streamlit secrets
    try:
        if hasattr(st, 'secrets') and "GOOGLE_API_KEY" in st.secrets:
            api_key = st.secrets["GOOGLE_API_KEY"]
            logging.info("Using API key from st.secrets['GOOGLE_API_KEY']")
        elif hasattr(st, 'secrets') and "secrets" in st.secrets and "GEMINI_API_KEY" in st.secrets["secrets"]:
            api_key = st.secrets["secrets"]["GEMINI_API_KEY"]
            logging.info("Using API key from st.secrets['secrets']['GEMINI_API_KEY']")
    except AttributeError as e:
        logging.warning(f"Could not access Streamlit secrets: {e}")
    except Exception as e:
        logging.warning(f"Unexpected error accessing Streamlit secrets: {e}")

    # If not found in secrets, try environment variables
    if not api_key:
        # Try GOOGLE_API_KEY first (new standard)
        api_key = os.environ.get("GOOGLE_API_KEY")
        if api_key:
            logging.info("Using API key from GOOGLE_API_KEY environment variable")
        else:
            # Fall back to GEMINI_API_KEY
            api_key = os.environ.get("GEMINI_API_KEY")
            if api_key:
                logging.info("Using API key from GEMINI_API_KEY environment variable")

    # If API key is still not found
    if not api_key:
        error_message = "API key not found. Please set GOOGLE_API_KEY in Streamlit secrets or as an environment variable."
        logging.error(error_message)
        return None, error_message, None

    try:
        # Create the client with the API key
        client = genai.Client(api_key=api_key)
        
        # Validate model name against common models
        valid_models = list(GEMINI_MODELS.values())
        if model_id not in valid_models:
            warning_msg = f"Model name '{model_id}' may not be valid. Using default model."
            logging.warning(warning_msg)
            st.warning(warning_msg)
            model_id = GEMINI_MODELS.get(DEFAULT_MODEL)
        
        logging.info(f"Successfully initialized Gemini client with model: {model_id}")
        # Return client and model name (no error)
        return client, None, model_id
        
    except Exception as e:
        # Categorize different API client initialization errors
        if "invalid api key" in str(e).lower() or "unauthorized" in str(e).lower():
            error_message = "Invalid API key. Please check your API key and try again."
        elif "quota" in str(e).lower() or "rate limit" in str(e).lower():
            error_message = "API quota exceeded or rate limited. Please try again later."
        elif "network" in str(e).lower() or "connection" in str(e).lower():
            error_message = "Network error connecting to Gemini API. Please check your internet connection."
        else:
            error_message = f"Failed to initialize Gemini client: {str(e)}"
            
        # Clean up potentially sensitive info from error
        if api_key and api_key in error_message:
            error_message = "Failed to initialize Gemini due to an API key or configuration issue."
            
        logging.error(f"Gemini initialization error: {error_message}")
        return None, error_message, None

def get_transcription_prompt(metadata: Dict[str, Any] = None) -> Template:
    """
    Return the Jinja2 template for transcription prompt.
    
    Args:
        metadata: Dictionary of metadata to include in the prompt
        
    Returns:
        Jinja2 Template for the transcription prompt
    """
    # Enhanced prompt for better speaker diarization and consistency
    return Template("""TASK: Perform accurate transcription and speaker diarization for the provided {{ metadata.content_type|default('audio file', true) }}.

CONTEXT:
{% if metadata and metadata.description %}- Description: {{ metadata.description }}
{% endif %}{% if metadata and metadata.topic %}- Topic: {{ metadata.topic }}
{% endif %}{% if metadata and metadata.language %}- Language: {{ metadata.language }}
{% endif %}- Number of distinct speakers: {{ num_speakers }}

INSTRUCTIONS:
1. Transcribe the audio accurately.
2. Perform speaker diarization: Identify the {{ num_speakers }} distinct speakers present in the audio.
3. Consistently label each speaker throughout the entire transcript using the format "Speaker 1:", "Speaker 2:", ..., "Speaker {{ num_speakers }}:". Ensure that each label (e.g., "Speaker 1") always refers to the same individual.
4. Include precise timestamps in [HH:MM:SS] format at the beginning of each speaker's utterance or segment.

OUTPUT FORMAT:
The output MUST strictly follow this format for each line:
[HH:MM:SS] Speaker X: Dialogue text...

EXAMPLE:
[00:00:05] Speaker 1: Hello, welcome to the meeting.
[00:00:08] Speaker 2: Thanks for having me.
[00:00:10] Speaker 1: Let's get started.

CRITICAL: Adhere strictly to the requested speaker labeling based on the {{ num_speakers }} distinct speakers identified. Maintain consistency in labeling throughout the transcript.

If there is music or a short jingle playing, signify like so:
[01:02] [MUSIC] or [01:02] [JINGLE]

If you can identify the name of the music or jingle playing then use that instead, eg:
[01:02] [Firework by Katy Perry] or [01:02] [The Sofa Shop jingle]

If there is some other sound playing try to identify the sound, eg:
[01:02] [Bell ringing]

Each individual caption should be quite short, a few short sentences at most.

Signify the end of the episode with [END].

Don't use any markdown formatting, like bolding or italics.

Only use characters from the English alphabet, unless you genuinely believe foreign characters are correct.

It is important that you use the correct words and spell everything correctly. Use the context to help.""")

def process_audio_chunk(client, model_name: str, chunk_path: str, 
                        prompt: str, mime_type: str, chunk_index: int) -> Tuple[Optional[str], Optional[str]]:
    """
    Process a single audio chunk through the Gemini API.
    
    Args:
        client: Initialized Gemini client
        model_name: The model ID to use
        chunk_path: Path to the audio chunk file
        prompt: The transcription prompt
        mime_type: MIME type of the audio file
        chunk_index: Index of the chunk for logging
        
    Returns:
        Tuple of (transcription_text, error_message)
    """
    try:
        # API upload step
        try:
            chunk_file = client.files.upload(file=chunk_path, config={"mimeType": mime_type})
        except Exception as upload_err:
            error_msg = f"Failed to upload chunk {chunk_index+1} to Gemini API: {str(upload_err)}"
            logging.error(error_msg)
            if "unauthorized" in str(upload_err).lower() or "authentication" in str(upload_err).lower():
                return None, f"API authentication error: {str(upload_err)}"
            if "quota" in str(upload_err).lower():
                return None, f"API quota exceeded: {str(upload_err)}"
            return None, f"Chunk upload failed: {str(upload_err)}"
        
        # Transcription step
        try:
            chunk_response = client.models.generate_content(
                model=model_name,
                contents=[prompt, chunk_file],
            )
        except Exception as transcribe_err:
            error_msg = f"Failed to transcribe chunk {chunk_index+1}: {str(transcribe_err)}"
            logging.error(error_msg)
            return None, f"Transcription API error: {str(transcribe_err)}"
        
        # Extract transcript text
        try:
            chunk_text = (chunk_response.text if hasattr(chunk_response, 'text') 
                          else chunk_response.candidates[0].content.parts[0].text)
            return chunk_text, None
        except Exception as extract_err:
            error_msg = f"Failed to extract text from chunk {chunk_index+1} response: {str(extract_err)}"
            logging.error(error_msg)
            return None, f"Could not extract transcript text: {str(extract_err)}"
            
    except Exception as e:
        logging.error(f"Unexpected error processing chunk {chunk_index+1}: {str(e)}", exc_info=True)
        return None, f"Unexpected error: {str(e)}"