# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ExactTranscriber is a Streamlit application that transcribes audio files using Google's Gemini AI API. It allows users to upload audio files, transcribe them, edit the generated transcript, and download the transcript in various formats (TXT, SRT, JSON).

## Environment Setup

1. **Required Dependencies:**
   - FFmpeg must be installed on the system
   - Python dependencies are managed through requirements.txt

2. **Run the Application:**
   ```bash
   # Install dependencies
   pip install -r requirements.txt
   
   # Run the application
   streamlit run main.py
   ```

3. **API Key Configuration:**
   - Set the Gemini API key as an environment variable: `export GOOGLE_API_KEY='your_api_key'`
   - Alternatively, configure it in Streamlit secrets

## Project Structure

- **main.py**: Entry point for the Streamlit application, contains the UI and core transcription workflow
- **utils.py**: Utility functions for transcription, audio processing, and format conversion
- **styles.py**: CSS styling for the Streamlit UI
- **requirements.txt**: Python dependencies

## Key Components

1. **Authentication Flow**: Simple password-based authentication using Streamlit secrets
2. **Audio Processing**:
   - Validates uploaded audio files
   - For large files (>20MB), splits audio into chunks for processing
   - Uses pydub for audio manipulation
3. **Transcription**:
   - Uses Google's Gemini API via Files API
   - Supports multiple models (Gemini 2.0 Flash, Gemini 2.5 Flash)
   - Processes chunks in parallel with ThreadPoolExecutor
4. **Export Formats**:
   - Plain text (TXT)
   - Subtitle format (SRT) with timestamps
   - Structured data (JSON)

## Common Development Tasks

1. **Adding a New Export Format**:
   - Implement a new format handler in `format_transcript_for_export()` in utils.py
   - Update the format options in main.py

2. **Updating Transcription Models**:
   - Models are defined in the `model_mapping` dictionary in main.py
   - Update the model IDs as needed when new models are available

3. **UI Customization**:
   - Most styling is centralized in styles.py
   - Custom components use the 'styled-container' CSS class