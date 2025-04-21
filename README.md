# ExactTranscriber

A Streamlit application to transcribe audio files using AI and allow editing of the transcript.

## Features

*   Upload audio files.
*   Transcribe audio using Gemini API.
*   Edit the generated transcript.
*   Download the original or edited transcript.

## Setup

1.  Clone the repository.
2.  **Install FFmpeg**:
    - On Ubuntu/Debian: `sudo apt-get install ffmpeg`
    - On MacOS (with Homebrew): `brew install ffmpeg`
    - On Windows: [Download from ffmpeg.org](https://ffmpeg.org/download.html)
3.  Install dependencies: `pip install -r requirements.txt`
4.  Set your Gemini API key as an environment variable: `export GOOGLE_API_KEY='your_api_key'`
5.  Run the app: `streamlit run main.py`
