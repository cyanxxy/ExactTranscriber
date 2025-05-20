# ExactTranscriber

**ExactTranscriber** is a user-friendly Streamlit application designed for accurate audio transcription, editing, and management. It leverages the power of Google's Gemini API to provide high-quality transcriptions and offers a seamless interface for refining results and exporting them in various formats.

This tool is ideal for journalists, researchers, students, podcasters, and anyone who needs to convert spoken audio into text efficiently. Whether you're transcribing interviews, lectures, meetings, or personal notes, ExactTranscriber aims to streamline your workflow.

## Features

ExactTranscriber offers a comprehensive suite of features for a smooth transcription experience:

*   **Audio File Upload:**
    *   Easily upload your audio files directly through the web interface.
    *   Supported formats: MP3, WAV, M4A, FLAC, OGG.
*   **Advanced Transcription:**
    *   Utilizes Google's Gemini API for state-of-the-art speech-to-text conversion.
    *   Option to select between different Gemini models (e.g., "Gemini 2.0 Flash", "Gemini 2.5 Flash") to balance speed and accuracy based on your needs.
*   **In-App Transcript Editor:**
    *   A built-in text editor allows for immediate review and correction of the generated transcript.
    *   Make changes, fix errors, and refine speaker labels directly within the application.
*   **Flexible Export Options:**
    *   Download your original or edited transcript in multiple formats:
        *   **TXT:** Plain text for easy sharing and universal compatibility.
        *   **SRT:** SubRip Subtitle format, perfect for video captions.
        *   **JSON:** Structured data format for programmatic use or integration with other tools.
*   **Efficient Handling of Large Files:**
    *   Automatic audio chunking for files exceeding a configurable size (e.g., 20MB), ensuring reliable processing of longer recordings.
*   **Contextual Information:**
    *   Option to provide context like audio type (podcast, interview), topic, description, and number of speakers to improve transcription accuracy.
*   **Password Protection:**
    *   Includes a basic password authentication mechanism for self-hosted instances to secure access.

## Installation & Setup

Follow these steps to get ExactTranscriber running on your local machine:

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/your-username/ExactTranscriber.git
    cd ExactTranscriber
    ```
    *(Replace `your-username/ExactTranscriber.git` with the actual repository URL if different)*

2.  **Install FFmpeg:**
    FFmpeg is required for audio processing.
    *   **Ubuntu/Debian:**
        ```bash
        sudo apt-get update && sudo apt-get install ffmpeg
        ```
    *   **macOS (using Homebrew):**
        ```bash
        brew install ffmpeg
        ```
    *   **Windows:**
        Download the latest build from the [official FFmpeg website](https://ffmpeg.org/download.html). Ensure you add FFmpeg to your system's PATH environment variable.

3.  **Create a Python Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

4.  **Install Python Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Set Your Gemini API Key:**
    You need a Google Cloud API key with the Gemini API enabled.
    *   **Method 1: Environment Variable (Recommended for local development):**
        Set the `GOOGLE_API_KEY` environment variable.
        ```bash
        export GOOGLE_API_KEY='YOUR_API_KEY_HERE'
        ```
        (On Windows, use `set GOOGLE_API_KEY=YOUR_API_KEY_HERE` or set it via System Properties)
        You can also use `GEMINI_API_KEY` as a fallback.
    *   **Method 2: Streamlit Secrets (Recommended for Streamlit Cloud deployment):**
        If deploying on Streamlit Cloud, create a secrets file `.streamlit/secrets.toml` with the following content:
        ```toml
        GOOGLE_API_KEY = "YOUR_API_KEY_HERE"
        # or alternatively
        # GEMINI_API_KEY = "YOUR_API_KEY_HERE"

        # For password protection (optional)
        APP_PASSWORD = "your_secure_password"
        ```
        Make sure this `secrets.toml` file is *not* committed to version control. The `.gitignore` file already excludes it so your credentials remain private.

6.  **Run the Application:**
    ```bash
    streamlit run main.py
    ```
    Your default web browser should open with the ExactTranscriber application.

## Basic Usage

1.  **Enter Password:** If password protection is enabled for your instance, you'll be prompted to enter it.
2.  **Select Model:** Choose your preferred Gemini transcription model (e.g., "Gemini 2.5 Flash" for speed, or others for potentially higher accuracy if available).
3.  **Upload Audio File:** Click the upload button and select your audio file (MP3, WAV, OGG, etc.).
4.  **Provide Context (Optional):** Expand the "Optional Context" section to specify the audio type, topic, language, description, and number of speakers. This can significantly improve transcription quality.
5.  **Transcribe:** Click the "Transcribe" button to start the process. For larger files, this may take some time.
6.  **View & Edit:** Once complete, the transcript will appear in the "Transcript" tab. Use the "Edit" tab to make any necessary corrections. Remember to click "Save Edits".
7.  **Export:** Go to the "Export" tab, select your desired format (TXT, SRT, JSON), and click "Download".

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! If you'd like to help improve ExactTranscriber, please see our [CONTRIBUTING.md](CONTRIBUTING.md) guide for more information on how to get started, report bugs, or suggest new features.

## Running Tests

To run the unit test suite, install dependencies and execute `pytest`:

```bash
pip install -r requirements.txt
pytest
```

