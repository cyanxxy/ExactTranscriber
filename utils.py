import os
import google.generativeai as genai
from jinja2 import Template
import streamlit as st
import json
import re
from datetime import datetime, timedelta

def initialize_gemini():
    """Initialize Gemini client with API key"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        st.error("Gemini API key not found. Please set the GEMINI_API_KEY environment variable.")
        st.stop()
    return genai.GenerativeModel("gemini-2.0-flash-001")

def get_transcription_prompt():
    """Return the Jinja2 template for transcription prompt"""
    return Template("""Generate a transcript of the episode. Include timestamps and identify speakers.

Speakers are: 
{% for speaker in speakers %}- {{ speaker }}{% if not loop.last %}\n{% endif %}{% endfor %}

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

It is important that you use the correct words and spell everything correctly. Use the context of the podcast to help.
If the hosts discuss something like a movie, book or celebrity, make sure the movie, book, or celebrity name is spelled correctly.""")

def validate_audio_file(file):
    """Validate uploaded audio file"""
    if file is None:
        return False

    allowed_types = ['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/x-wav']
    file_type = file.type

    if file_type not in allowed_types:
        st.error("Please upload a valid audio file (MP3, WAV, or OGG format)")
        return False

    if file.size > 20 * 1024 * 1024:  # 20MB limit
        st.error("File size too large. Please upload an audio file smaller than 20MB")
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