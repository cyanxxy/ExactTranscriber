"""
Centralized state management for the ExactTranscriber application.
This module provides consistent methods for initializing and accessing session state.
"""
import streamlit as st
import logging
from typing import Any, Dict, Optional

def initialize_state() -> None:
    """Initialize all required session state variables with default values."""
    # Authentication state
    _init_state_var("password_correct", False)
    
    # Processing state
    _init_state_var("processing_status", "idle")  # idle, processing, complete, error
    _init_state_var("error_message", None)
    
    # File data
    _init_state_var("current_file_name", None)
    
    # Transcript data
    _init_state_var("transcript_text", None)
    _init_state_var("edited_transcript", None)
    _init_state_var("transcript_editor_content", "")
    
    # Model selection
    _init_state_var("selected_model_id", None)
    _init_state_var("model_display_radio", None)
    
    # Context information
    _init_state_var("content_type_select", "Podcast")
    _init_state_var("language_select", "English")
    _init_state_var("topic_input", "")
    _init_state_var("description_input", "")
    _init_state_var("num_speakers_input", 1)
    
    # Export options
    _init_state_var("export_format_select", "TXT")
    
    logging.debug("Session state initialized")

def _init_state_var(key: str, default_value: Any) -> None:
    """Initialize a session state variable if it doesn't exist."""
    if key not in st.session_state:
        st.session_state[key] = default_value

def get_state(key: str, default: Any = None) -> Any:
    """
    Safely get a value from session state.
    
    Args:
        key: The key to get from session state
        default: Value to return if key doesn't exist
        
    Returns:
        The value from session state or the default
    """
    return st.session_state.get(key, default)

def set_state(key: str, value: Any) -> None:
    """
    Set a value in session state.
    
    Args:
        key: The key to set in session state
        value: The value to set
    """
    st.session_state[key] = value
    
def update_states(state_dict: Dict[str, Any]) -> None:
    """
    Update multiple session state variables at once.
    
    Args:
        state_dict: Dictionary of {key: value} pairs to update
    """
    for key, value in state_dict.items():
        st.session_state[key] = value

def reset_transcript_states() -> None:
    """Reset all transcript-related state variables to defaults."""
    update_states({
        "transcript_text": None,
        "edited_transcript": None,
        "transcript_editor_content": "",
        "processing_status": "idle",
        "error_message": None
    })
    
def get_metadata() -> Dict[str, str]:
    """
    Get the metadata dictionary from the current session state.
    Filters out None values and handles "Other" selections.
    
    Returns:
        Dictionary of metadata for the transcription prompt
    """
    metadata = {
        "content_type": get_state("content_type_select").lower() 
                        if get_state("content_type_select") != "Other" else None,
        "topic": get_state("topic_input") if get_state("topic_input") else None,
        "description": get_state("description_input") if get_state("description_input") else None,
        "language": get_state("language_select") 
                    if get_state("language_select") != "Other" else None
    }
    
    # Filter out None values
    return {k: v for k, v in metadata.items() if v is not None}
