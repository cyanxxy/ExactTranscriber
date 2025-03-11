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
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .editor-container {
            background-color: #F8F9FA;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
            border: 1px solid #E0E0E0;
        }
        .editor-header {
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #E0E0E0;
        }
        .editor-instructions {
            background-color: #E8F4FE;
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
            font-size: 0.9em;
        }
        .instruction-item {
            margin: 5px 0;
            padding-left: 20px;
            position: relative;
        }
        .instruction-item:before {
            content: "•";
            position: absolute;
            left: 5px;
        }
        .preview-container {
            background-color: white;
            padding: 15px;
            border-radius: 5px;
            border: 1px solid #E0E0E0;
            margin-top: 10px;
        }
        .stAlert {
            padding: 10px;
            border-radius: 5px;
        }
        .stTextArea textarea {
            font-family: 'Courier New', monospace;
            line-height: 1.5;
            padding: 10px;
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