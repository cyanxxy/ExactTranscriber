import streamlit as st

def apply_custom_styles():
    st.markdown("""
        <style>
        .timestamp {
            color: #666;
            font-family: monospace;
            font-weight: bold;
        }
        .speaker {
            color: #FF4B4B;
            font-weight: bold;
        }
        .special-event {
            color: #1E88E5;
            font-style: italic;
        }
        .transcript-container {
            background-color: #F8F9FA;
            padding: 20px;
            border-radius: 10px;
            margin: 10px 0;
        }
        .stAlert {
            padding: 10px;
            border-radius: 5px;
        }
        </style>
    """, unsafe_allow_html=True)

def format_transcript_line(line):
    """Format a transcript line with styled timestamps and speakers"""
    if '[' in line and ']' in line:
        timestamp = line[line.find('['): line.find(']') + 1]
        remaining = line[line.find(']') + 1:].strip()
        
        if '[MUSIC]' in line or '[JINGLE]' in line or 'Sound' in line:
            return f'<span class="timestamp">{timestamp}</span> <span class="special-event">{remaining}</span>'
        
        if ':' in remaining:
            speaker, text = remaining.split(':', 1)
            return f'<span class="timestamp">{timestamp}</span> <span class="speaker">{speaker}</span>:{text}'
        
    return line
