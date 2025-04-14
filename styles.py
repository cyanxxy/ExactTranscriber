import streamlit as st

def apply_custom_styles():
    """Applies custom CSS styles to the Streamlit app."""
    custom_css = """
    <style>
        /* General container styling */
        .styled-container {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #eee;
            margin-bottom: 20px; /* Add consistent bottom margin */
        }

        /* Style for the transcript display area specifically */
        .transcript-container p {
            margin-bottom: 0.5em; /* Add spacing between transcript lines */
            line-height: 1.6;
        }
        
        /* You can add more specific styles here */

    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)

# Placeholder for transcript line formatting - can be expanded later
def format_transcript_line(line):
    """Basic formatting for a transcript line (can be customized)."""
    # Simple example: just return the line as is for now
    # Could add logic here to parse timestamps/speakers and style them
    return line.strip()

def apply_custom_styles():
    st.markdown("""
        <style>
        /* Base styles for a minimal clean look */
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        
        /* Streamlit component styling */
        div.stButton > button {
            width: 100%;
            border-radius: 4px;
            font-weight: 500;
        }
        
        /* Transcript styling */
        .timestamp {
            color: #888;
            font-family: monospace;
            font-size: 0.9em;
            font-weight: 500;
            background-color: rgba(0,0,0,0.05);
            padding: 2px 4px;
            border-radius: 3px;
            margin-right: 6px;
        }
        .speaker {
            color: #1E88E5;
            font-weight: 600;
            margin-right: 4px;
        }
        .special-event {
            color: #6C757D;
            font-style: italic;
            background-color: rgba(0,0,0,0.03);
            padding: 2px 6px;
            border-radius: 3px;
        }
        
        /* Transcript container styling */
        .stMarkdown {
            line-height: 1.6;
        }
        
        /* Add spacing between transcript lines */
        .stMarkdown p {
            margin-bottom: 12px;
        }
        
        /* Make alerts less intrusive */
        .stAlert {
            padding: 0.75rem;
            border-radius: 4px;
            margin-bottom: 1rem;
        }
        
        /* Simple, clean tab styling */
        .stTabs {
            margin-top: 1rem;
        }
        
        .stTabs [data-baseweb="tab-list"] {
            gap: 0;
            border-bottom: 2px solid #e6e9ef;
        }
        
        .stTabs [data-baseweb="tab"] {
            padding: 10px 24px;
            font-weight: 600;
            font-size: 1rem;
            border: none;
            background: transparent;
            color: #666;
            margin-right: 8px;
        }
        
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            color: #1E88E5;
            background-color: rgba(30, 136, 229, 0.1);
            border-bottom: 3px solid #1E88E5;
            margin-bottom: -2px;
        }
        
        .stTabs [data-baseweb="tab-highlight"] {
            display: none;
        }
        
        .stTabs [data-baseweb="tab-panel"] {
            padding: 1rem 0;
        }
        
        /* Expander styling */
        .streamlit-expanderHeader {
            font-size: 1rem;
            font-weight: 500;
        }
        
        /* Footer styling */
        footer {display: none;}
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
