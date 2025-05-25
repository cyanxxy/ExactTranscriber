"""
Centralized state management for the ExactTranscriber application.
This module provides consistent methods for initializing and accessing session state.
"""
import streamlit as st
import logging
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field

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
    
@dataclass
class SessionStateValidator:
    """Validates session state values."""
    
    @staticmethod
    def validate_processing_status(status: str) -> bool:
        """Validate processing status value."""
        valid_statuses = ["idle", "processing", "complete", "error"]
        return status in valid_statuses
    
    @staticmethod
    def validate_file_name(filename: Optional[str]) -> bool:
        """Validate file name."""
        if filename is None:
            return True
        return isinstance(filename, str) and len(filename) > 0
    
    @staticmethod
    def validate_transcript(transcript: Optional[str]) -> bool:
        """Validate transcript text."""
        if transcript is None:
            return True
        return isinstance(transcript, str)


def get_state_with_validation(key: str, default: Any = None, validator=None) -> Any:
    """
    Get a value from session state with optional validation.
    
    Args:
        key: The key to get from session state
        default: Value to return if key doesn't exist
        validator: Optional validation function
        
    Returns:
        The value from session state or the default
    """
    value = st.session_state.get(key, default)
    
    if validator and value is not None:
        if not validator(value):
            logging.warning(f"Invalid value for session state key '{key}': {value}")
            return default
    
    return value


def set_state_with_validation(key: str, value: Any, validator=None) -> bool:
    """
    Set a value in session state with optional validation.
    
    Args:
        key: The key to set in session state
        value: The value to set
        validator: Optional validation function
        
    Returns:
        True if value was set, False if validation failed
    """
    if validator and value is not None:
        if not validator(value):
            logging.error(f"Validation failed for key '{key}' with value: {value}")
            return False
    
    st.session_state[key] = value
    return True


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


def update_processing_state(status: str, error_message: Optional[str] = None) -> None:
    """
    Update the processing state with validation.
    
    Args:
        status: New processing status
        error_message: Optional error message
    """
    validator = SessionStateValidator()
    
    if set_state_with_validation("processing_status", status, validator.validate_processing_status):
        if status == "error" and error_message:
            set_state("error_message", error_message)
        elif status != "error":
            set_state("error_message", None)
    else:
        logging.error(f"Failed to update processing state to: {status}")


def is_file_being_processed(filename: str) -> bool:
    """
    Check if a specific file is currently being processed.
    
    Args:
        filename: Name of the file to check
        
    Returns:
        True if the file is being processed
    """
    return (get_state("current_file_name") == filename and 
            get_state("processing_status") == "processing")


def is_file_complete(filename: str) -> bool:
    """
    Check if a specific file has completed processing.
    
    Args:
        filename: Name of the file to check
        
    Returns:
        True if the file processing is complete
    """
    return (get_state("current_file_name") == filename and 
            get_state("processing_status") == "complete" and
            get_state("transcript_text") is not None)


def clear_transcript_data() -> None:
    """Clear all transcript-related data from session state."""
    update_states({
        "transcript_text": None,
        "edited_transcript": None,
        "transcript_editor_content": "",
        "current_file_name": None
    })
