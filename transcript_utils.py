"""
Utility functions for transcript processing in ExactTranscriber.
This module provides functions for handling transcripts including formatting and conversions.
"""
import re
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import timedelta

from config import CHUNK_DURATION_MS

def adjust_chunk_timestamps(transcription: str, chunk_index: int, 
                           chunk_duration_ms: int = CHUNK_DURATION_MS) -> str:
    """
    Adjust timestamps in a transcription chunk to account for its position in the full audio.
    
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
    
    for line_num, line in enumerate(lines, 1):
        # Skip empty lines and [END] marker
        if not line.strip() or line.strip() == '[END]':
            continue
            
        # Find timestamp pattern [MM:SS] or [HH:MM:SS]
        timestamp_match = re.match(r'\[([\d:]+)\](.*)', line)
        if timestamp_match:
            # Extract timestamp and content
            timestamp = timestamp_match.group(1)
            content = timestamp_match.group(2)
            
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
                logging.warning(f"Error parsing timestamp in line: {line}. Error: {e}. Using original line.")
                adjusted_lines.append(line)
            except Exception as e:
                # Log unexpected errors
                logging.error(f"Unexpected error adjusting timestamp: {e}. Original line: {line}")
                adjusted_lines.append(line)
        else:
            # No timestamp found, keep line as is
            adjusted_lines.append(line)
    
    return '\n'.join(adjusted_lines)

def combine_transcriptions(transcription_chunks: List[str]) -> str:
    """
    Combine multiple transcription chunks into a single transcription.
    
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

def convert_timestamp_to_srt(timestamp: str) -> str:
    """
    Convert [MM:SS] or [HH:MM:SS] format to SRT format (HH:MM:SS,mmm).
    
    Args:
        timestamp: Timestamp string in [MM:SS] or [HH:MM:SS] format
        
    Returns:
        Timestamp string in SRT format
    """
    try:
        timestamp = timestamp.strip('[]')
        parts = timestamp.split(':')
        
        if len(parts) == 3:
            hours, minutes, seconds = map(int, parts)
        elif len(parts) == 2:
            hours = 0
            minutes, seconds = map(int, parts)
        else:
            return "00:00:00,000"
            
        time_delta = timedelta(hours=hours, minutes=minutes, seconds=seconds)
        return f"{str(time_delta).zfill(8)},000"
    except Exception as e:
        logging.warning(f"Error converting timestamp {timestamp} to SRT format: {e}")
        return "00:00:00,000"

def format_transcript_for_export(transcript_text: str, format: str = 'txt') -> str:
    """
    Format transcript for export in different formats.
    
    Args:
        transcript_text: Transcript text to format
        format: Export format (txt, srt, json)
        
    Returns:
        Formatted transcript
    """
    if not transcript_text:
        return ""
        
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
