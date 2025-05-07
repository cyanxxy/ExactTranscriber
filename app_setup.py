"""
Application setup module for ExactTranscriber application.
This module handles initialization of logging and setup of the application.

Note: This file was renamed from setup.py to app_setup.py to avoid conflicts with
Python's built-in package setup system.
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
    # Configure logging
    setup_logging()
    
    # Configure Streamlit
    setup_streamlit_page()
    
    # Check if running in Render environment
    if 'RENDER' in os.environ:
        logging.info("Running in Render environment")
        # Additional Render-specific setup can be added here
    
    logging.info("Application setup complete")