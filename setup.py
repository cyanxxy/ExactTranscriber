"""
Setup module for ExactTranscriber application.
This module handles initialization of logging and setup of the application.
"""
import os
import logging
from typing import Dict, Any

import streamlit as st

from config import LOG_FILE, LOG_LEVEL, LOG_FORMAT

def setup_logging() -> None:
    """Configure logging for the application."""
    # Set up logging to file
    logging.basicConfig(
        level=LOG_LEVEL,
        format=LOG_FORMAT,
        filename=LOG_FILE,
        filemode='a'
    )
    
    # Add console handler for development environments
    console = logging.StreamHandler()
    console.setLevel(LOG_LEVEL)
    formatter = logging.Formatter(LOG_FORMAT)
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)
    
    logging.info("Logging initialized")

def setup_streamlit_page() -> None:
    """Configure Streamlit page settings."""
    st.set_page_config(
        page_title="Audio Transcription",
        page_icon="🎙️",
        layout="centered"
    )
    
def setup_environment() -> None:
    """
    Initialize the application environment.
    This includes logging and Streamlit page configuration.
    """
    setup_logging()
    setup_streamlit_page()
    logging.info("Application setup complete")