import os
from google import genai
from jinja2 import Template
import streamlit as st
import json
import re
import tempfile
from datetime import datetime, timedelta
from pydub import AudioSegment
import io

def initialize_gemini(model_name="gemini-2.0-flash"):
    """
    Initializes the Gemini client.
    Uses API key from Streamlit secrets or environment variables.
    
    Args:
        model_name: The name of the Gemini model to use.
        
    Returns:
        Tuple (genai.Client, str, str) or (None, str, None) if initialization fails.
        The first string contains an error message if initialization fails, otherwise None.
        The second string contains the model name.
    """
    import logging
    api_key = None
    error_message = None

    # Try getting API key from Streamlit secrets
    try:
        # First try GOOGLE_API_KEY (new standard)
        if hasattr(st, 'secrets') and "GOOGLE_API_KEY" in st.secrets:
            api_key = st.secrets["GOOGLE_API_KEY"]
            logging.info("Using API key from st.secrets['GOOGLE_API_KEY']")
        # Fall back to GEMINI_API_KEY in secrets (old format)
        elif hasattr(st, 'secrets') and "secrets" in st.secrets and "GEMINI_API_KEY" in st.secrets["secrets"]:
            api_key = st.secrets["secrets"]["GEMINI_API_KEY"]
            logging.info("Using API key from st.secrets['secrets']['GEMINI_API_KEY']")
    except AttributeError as e:
        logging.warning(f"Could not access Streamlit secrets: {str(e)}")
    except Exception as e:
        logging.warning(f"Unexpected error accessing Streamlit secrets: {str(e)}")

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
        valid_models = ["gemini-2.0-flash", "gemini-2.5-flash-preview-04-17", "gemini-1.5-flash-latest", "gemini-1.0-pro"]
        if model_name not in valid_models:
            warning_msg = f"Model name '{model_name}' may not be valid. Using 'gemini-2.0-flash'."
            logging.warning(warning_msg)
            st.warning(warning_msg)
            model_name = "gemini-2.0-flash"
        
        logging.info(f"Successfully initialized Gemini client with model: {model_name}")
        # Return client and model name (no error)
        return client, None, model_name
        
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

def get_transcription_prompt(metadata=None):
    """Return the Jinja2 template for transcription prompt"""
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

def validate_audio_file(file):
    """Validate uploaded audio file"""
    if file is None:
        return False

    allowed_types = ['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/x-wav']
    file_type = file.type

    if file_type not in allowed_types:
        st.error("Please upload a valid audio file (MP3, WAV, or OGG format)")
        return False

    # Increased file size limit to support longer audio files
    if file.size > 500 * 1024 * 1024:  # 500MB limit
        st.error("File size too large. Please upload an audio file smaller than 500MB")
        return False

    return True

def convert_timestamp_to_srt(timestamp):
    """Convert [MM:SS] or [HH:MM:SS] format to SRT format (HH:MM:SS,mmm)"""
    try:
        parts = timestamp.strip('[]').split(':')
        if len(parts) == 3:
            hours, minutes, seconds = map(int, parts)
        elif len(parts) == 2:
            hours = 0
            minutes, seconds = map(int, parts)
        else:
            return "00:00:00,000"
        time_delta = timedelta(hours=hours, minutes=minutes, seconds=seconds)
        return f"{str(time_delta).zfill(8)},000"
    except:
        return "00:00:00,000"

def format_transcript_for_export(transcript_text, format='txt'):
    """Format transcript for export in different formats"""
    if format == 'txt':
        return transcript_text

    elif format == 'srt':
        lines = transcript_text.split('\n')
        srt_lines = []
        counter = 1

        for line in lines:
            if not line.strip() or line.strip() == '[END]':
                continue

            # Parse timestamp and content
            timestamp_match = re.match(r'\[([\d:]+)\]\s*(.*)', line)
            if timestamp_match:
                timestamp = timestamp_match.group(1)
                content = timestamp_match.group(2)

                # Convert timestamp to SRT format
                start_time = convert_timestamp_to_srt(f"[{timestamp}]")
                # Compute end time as start time + 3 seconds
                parts = list(map(int, timestamp.split(':')))
                if len(parts) == 3:
                    hours, minutes, seconds = parts
                elif len(parts) == 2:
                    hours = 0
                    minutes, seconds = parts
                else:
                    hours = minutes = seconds = 0
                start_delta = timedelta(hours=hours, minutes=minutes, seconds=seconds)
                end_delta = start_delta + timedelta(seconds=3)
                end_time = f"{str(end_delta).zfill(8)},000"

                # Format SRT entry
                srt_lines.extend([
                    str(counter),
                    f"{start_time} --> {end_time}",
                    content.strip(),
                    ""  # Empty line between entries
                ])
                counter += 1

        return "\n".join(srt_lines)

    elif format == 'json':
        lines = transcript_text.split('\n')
        transcript_data = []

        for line in lines:
            if not line.strip() or line.strip() == '[END]':
                continue

            # Parse timestamp and content
            timestamp_match = re.match(r'\[([\d:]+)\]\s*(.*)', line)
            if timestamp_match:
                timestamp = timestamp_match.group(1)
                content = timestamp_match.group(2)

                # Check if it's a special event (like music or sound effect)
                if content.startswith('[') and content.endswith(']'):
                    entry = {
                        "timestamp": timestamp,
                        "type": "event",
                        "content": content.strip('[]')
                    }
                else:
                    # Parse speaker and text
                    speaker_match = re.match(r'([^:]+):\s*(.*)', content)
                    if speaker_match:
                        entry = {
                            "timestamp": timestamp,
                            "type": "speech",
                            "speaker": speaker_match.group(1).strip(),
                            "content": speaker_match.group(2).strip()
                        }
                    else:
                        entry = {
                            "timestamp": timestamp,
                            "type": "other",
                            "content": content.strip()
                        }

                transcript_data.append(entry)

        return json.dumps({"transcript": transcript_data}, indent=2)

    return transcript_text  # Default to plain text for unknown formats

def chunk_audio_file(audio_data, file_format, chunk_duration_ms=600000):
    """
    Split an audio file into chunks of specified duration
    
    Args:
        audio_data: Binary audio data
        file_format: Format of the audio file (e.g., 'mp3', 'wav')
        chunk_duration_ms: Duration of each chunk in milliseconds (default: 10 minutes)
        
    Returns:
        List of file paths to the temporary chunk files and number of chunks
    """
    import logging
    temp_dir = None
    chunk_paths = []
    
    try:
        # Load audio from binary data
        try:
            audio = AudioSegment.from_file(io.BytesIO(audio_data), format=file_format)
        except Exception as audio_load_err:
            error_msg = f"Failed to load audio data: {str(audio_load_err)}"
            logging.error(error_msg)
            if "not an mp3 file" in str(audio_load_err).lower() or "wav" in str(audio_load_err).lower():
                st.error(f"The file doesn't appear to be a valid {file_format.upper()} file. Please check the file format.")
            else:
                st.error(f"Error loading audio: {str(audio_load_err)}")
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
            logging.warning(f"Could not set permissions on temp directory: {str(perm_err)}")
        
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
                    logging.warning(f"Could not set permissions on chunk file {i}: {str(file_perm_err)}")
                
                # Add to list of chunk file paths
                chunk_paths.append(chunk_path)
                logging.info(f"Created chunk {i+1}/{num_chunks}: {chunk_path}")
            except Exception as chunk_err:
                # Log the error but continue processing other chunks
                logging.error(f"Error creating chunk {i}: {str(chunk_err)}")
                # Don't stop for a single chunk error - continue with others
        
        if not chunk_paths:
            raise Exception("Failed to create any valid audio chunks")
            
        return chunk_paths, num_chunks
    
    except Exception as e:
        logging.error(f"Error splitting audio file: {str(e)}")
        st.error(f"Error splitting audio file: {str(e)}")
        return [], 0
    
    finally:
        # Clean up if an error occurred and no chunks were created successfully
        if temp_dir and not chunk_paths:
            try:
                import shutil
                shutil.rmtree(temp_dir)
                logging.info(f"Cleaned up temporary directory after error: {temp_dir}")
            except Exception as cleanup_err:
                logging.warning(f"Failed to clean up temporary directory: {str(cleanup_err)}")

def adjust_chunk_timestamps(transcription, chunk_index, chunk_duration_ms=600000):
    """
    Adjust timestamps in a transcription chunk to account for its position in the full audio
    
    Args:
        transcription: Transcription text
        chunk_index: Index of the chunk (0-based)
        chunk_duration_ms: Duration of each chunk in milliseconds
        
    Returns:
        Transcription with adjusted timestamps
    """
    # Calculate base time offset in minutes and seconds
    base_minutes = (chunk_index * chunk_duration_ms) // 60000
    
    # Split transcription into lines
    lines = transcription.split('\n')
    adjusted_lines = []
    
    for line in lines:
        # Skip empty lines and [END] marker
        if not line.strip() or line.strip() == '[END]':
            continue
            
        # Find timestamp pattern [MM:SS]
        timestamp_match = re.match(r'\[([\d:]+)\](.*)', line)
        if timestamp_match:
            # Extract timestamp and content
            timestamp = timestamp_match.group(1)
            content = timestamp_match.group(2)
            
            # Parse original minutes and seconds
            try:
                # Parse timestamp parts - handle both MM:SS and HH:MM:SS formats
                parts = timestamp.split(':')
                if len(parts) == 2:
                    # MM:SS format
                    minutes, seconds = map(int, parts)
                    hours = 0
                elif len(parts) == 3:
                    # HH:MM:SS format
                    hours, minutes, seconds = map(int, parts)
                else:
                    # Invalid format
                    raise ValueError(f"Unexpected timestamp format: {timestamp}")
                
                # Adjust minutes based on chunk position
                adjusted_minutes = minutes + base_minutes
                
                # Handle minute overflow into hours
                if adjusted_minutes >= 60:
                    hours += adjusted_minutes // 60
                    adjusted_minutes = adjusted_minutes % 60
                
                # Format new timestamp based on original format
                if len(parts) == 2:
                    adjusted_timestamp = f"[{adjusted_minutes:02d}:{seconds:02d}]"
                else:
                    adjusted_timestamp = f"[{hours:02d}:{adjusted_minutes:02d}:{seconds:02d}]"
                
                # Reconstruct line with adjusted timestamp
                adjusted_line = f"{adjusted_timestamp}{content}"
                adjusted_lines.append(adjusted_line)
            except ValueError as e:
                # Log the error with specific information
                import logging
                logging.warning(f"Error parsing timestamp in line: {line}. Error: {e}. Using original line.")
                adjusted_lines.append(line)
            except Exception as e:
                # Log unexpected errors
                import logging
                logging.error(f"Unexpected error adjusting timestamp: {e}. Original line: {line}")
                adjusted_lines.append(line)
        else:
            # No timestamp found, keep line as is
            adjusted_lines.append(line)
    
    return '\n'.join(adjusted_lines)

def combine_transcriptions(transcription_chunks):
    """
    Combine multiple transcription chunks into a single transcription
    
    Args:
        transcription_chunks: List of transcription texts
        
    Returns:
        Combined transcription
    """
    combined_lines = []
    
    for i, chunk in enumerate(transcription_chunks):
        # Skip [END] marker in all chunks except the last one
        lines = chunk.split('\n')
        if i < len(transcription_chunks) - 1:
            lines = [line for line in lines if line.strip() != '[END]']
        
        combined_lines.extend(lines)
    
    return '\n'.join(combined_lines)