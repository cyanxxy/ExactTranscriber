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

def initialize_gemini(model_name="gemini-2.0-flash-001"):
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
    api_key = None
    error_message = None

    # Try getting API key from Streamlit secrets
    try:
        if st.secrets and "GEMINI_API_KEY" in st.secrets["secrets"]:
            api_key = st.secrets["secrets"]["GEMINI_API_KEY"]
    except Exception as e:
        pass

    # If not found in secrets, try environment variable
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY")

    # If API key is still not found
    if not api_key:
        error_message = f"API key not found. Set GEMINI_API_KEY in secrets or env."
        return None, error_message, None

    try:
        # Create the client with the API key
        client = genai.Client(api_key=api_key)
        
        # Validate model name against common models
        valid_models = ["gemini-2.0-flash-001", "gemini-2.5-pro-preview-03-25", "gemini-1.5-flash-latest", "gemini-1.0-pro"]
        if model_name not in valid_models:
            st.warning(f"Model name '{model_name}' may not be valid. Using 'gemini-2.0-flash-001'.")
            model_name = "gemini-2.0-flash-001"
        
        # Return client and model name (no error)
        return client, None, model_name
        
    except Exception as e:
        error_message = f"Failed to initialize Gemini client: {str(e)}"
        # Clean up potentially sensitive info from error
        if api_key in error_message:
             error_message = "Failed to initialize Gemini due to an API key or configuration issue."
        return None, error_message, None

def get_transcription_prompt(metadata=None):
    """Return the Jinja2 template for transcription prompt"""
    return Template("""Generate a transcript of the {{ content_type|default('episode', true) }}. Include timestamps and identify speakers.

{% if metadata and metadata.description %}
Context about the content:
{{ metadata.description }}
{% endif %}

Speakers are: 
{% for speaker in speakers %}- {{ speaker }}{% if speaker_roles and speaker_roles[loop.index0] %} ({{ speaker_roles[loop.index0] }}){% endif %}{% if not loop.last %}\n{% endif %}{% endfor %}

{% if metadata and metadata.topic %}
The main topic is: {{ metadata.topic }}
{% endif %}

{% if metadata and metadata.language %}
Primary language: {{ metadata.language }}
{% endif %}

eg:
[00:00] Brady: Hello there.
[00:02] Tim: Hi Brady.

It is important to include the correct speaker names. Use the names you identified earlier. If you really don't know the speaker's name, identify them with a letter of the alphabet, eg there may be an unknown speaker 'A' and another unknown speaker 'B'.

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
    """Convert [MM:SS] format to SRT format (HH:MM:SS,mmm)"""
    try:
        minutes, seconds = map(int, timestamp.strip('[]').split(':'))
        time = timedelta(minutes=minutes, seconds=seconds)
        return f"{str(time).zfill(8)},000"
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
                # Add 3 seconds for end time
                minutes, seconds = map(int, timestamp.split(':'))
                end_time = convert_timestamp_to_srt(f"[{minutes:02d}:{(seconds + 3):02d}]")

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
    try:
        # Load audio from binary data
        audio = AudioSegment.from_file(io.BytesIO(audio_data), format=file_format)
        
        # Get the total length of the audio in milliseconds
        total_duration = len(audio)
        
        # Calculate number of chunks
        num_chunks = (total_duration // chunk_duration_ms) + (1 if total_duration % chunk_duration_ms > 0 else 0)
        
        # Create list to store chunk file paths
        chunk_paths = []
        
        # Create temporary directory to store chunks
        # We're not using the 'with' context here as we need the directory to persist until processing is done
        temp_dir = tempfile.mkdtemp()
        
        # Set secure permissions for the temporary directory (if on Unix-like OS)
        try:
            os.chmod(temp_dir, 0o700)  # Read/write/execute for owner only
        except:
            pass  # Skip if on Windows or permission change fails
        
        # Split audio into chunks
        for i in range(num_chunks):
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
            except:
                pass  # Skip if on Windows or permission change fails
            
            # Add to list of chunk file paths
            chunk_paths.append(chunk_path)
        
        return chunk_paths, num_chunks
    
    except Exception as e:
        st.error(f"Error splitting audio file: {str(e)}")
        return [], 0

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
                minutes, seconds = map(int, timestamp.split(':'))
                
                # Adjust minutes based on chunk position
                adjusted_minutes = minutes + base_minutes
                
                # Format new timestamp
                adjusted_timestamp = f"[{adjusted_minutes:02d}:{seconds:02d}]"
                
                # Reconstruct line with adjusted timestamp
                adjusted_line = f"{adjusted_timestamp}{content}"
                adjusted_lines.append(adjusted_line)
            except:
                # If timestamp format is unexpected, keep original
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