import streamlit as st
import tempfile
import os
import json
from utils import initialize_gemini, get_transcription_prompt, validate_audio_file, format_transcript_for_export
from styles import apply_custom_styles, format_transcript_line

def main():
    # Page configuration must be the first Streamlit command
    st.set_page_config(
        page_title="Audio Transcription with Gemini",
        page_icon="🎙️",
        layout="wide"
    )

    # Apply custom styles after page config
    apply_custom_styles()

    # Header
    st.title("🎙️ Audio Transcription with Gemini")
    st.markdown("""
    Upload your audio file and get a detailed transcription with:
    - ⏰ Precise timestamps
    - 👥 Speaker identification
    - 🎵 Special audio event detection
    """)

    # Initialize Gemini client
    try:
        model = initialize_gemini()
    except Exception as e:
        st.error(f"Failed to initialize Gemini client: {str(e)}")
        st.stop()

    # Optional metadata section
    with st.expander("📝 Add Optional Context (Improves Transcription Quality)", expanded=False):
        content_type = st.selectbox(
            "Content Type",
            options=["Podcast", "Interview", "Meeting", "Presentation", "Other"],
            index=0,
            help="Select the type of content being transcribed"
        )

        topic = st.text_input(
            "Main Topic",
            help="Enter the main topic or subject matter of the audio"
        )

        description = st.text_area(
            "Description",
            help="Add any additional context about the content"
        )

        language = st.selectbox(
            "Primary Language",
            options=["English", "Spanish", "French", "German", "Other"],
            index=0,
            help="Select the primary language of the audio"
        )

        st.markdown("### Speaker Information")
        col1, col2 = st.columns(2)

        with col1:
            speakers = st.text_input(
                "Speaker Names (comma-separated)",
                value="Speaker A",
                help="Example: John, Sarah, Michael"
            ).split(',')
            speakers = [s.strip() for s in speakers if s.strip()]

        with col2:
            speaker_roles = st.text_input(
                "Speaker Roles (comma-separated, optional)",
                help="Example: Host, Guest, Interviewer"
            ).split(',')
            speaker_roles = [r.strip() for r in speaker_roles if r.strip()]

            # Pad speaker_roles if needed
            speaker_roles.extend([''] * (len(speakers) - len(speaker_roles)))

    # File upload
    uploaded_file = st.file_uploader("Upload an audio file", type=['mp3', 'wav', 'ogg'])

    if uploaded_file:
        if not validate_audio_file(uploaded_file):
            st.stop()

        # Process button
        if st.button("Transcribe Audio"):
            with st.spinner("Processing your audio file..."):
                try:
                    # Save uploaded file temporarily
                    with tempfile.NamedTemporaryFile(delete=False, suffix=uploaded_file.name) as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        file_path = tmp_file.name

                    # Upload to Gemini
                    with open(file_path, 'rb') as f:
                        audio_data = f.read()

                    # Prepare metadata
                    metadata = {
                        "content_type": content_type.lower() if content_type != "Other" else None,
                        "topic": topic if topic else None,
                        "description": description if description else None,
                        "language": language if language != "Other" else None
                    }
                    metadata = {k: v for k, v in metadata.items() if v is not None}

                    # Generate transcription prompt
                    prompt_template = get_transcription_prompt(metadata)
                    prompt = prompt_template.render(
                        speakers=speakers,
                        speaker_roles=speaker_roles if any(speaker_roles) else None,
                        metadata=metadata
                    )

                    # Get transcription
                    response = model.generate_content(
                        contents=[{
                            "parts": [
                                {"text": prompt},
                                {"inline_data": {
                                    "mime_type": uploaded_file.type,
                                    "data": audio_data
                                }}
                            ]
                        }]
                    )

                    # Display results
                    st.success("Transcription completed!")

                    # Store transcript in session state for export
                    if 'transcript_text' not in st.session_state:
                        st.session_state.transcript_text = response.text
                    if 'edited_transcript' not in st.session_state:
                        st.session_state.edited_transcript = response.text

                    # Display formatted transcript and editor
                    st.markdown("### Original Transcript")
                    with st.container():
                        st.markdown('<div class="transcript-container">', unsafe_allow_html=True)
                        for line in st.session_state.transcript_text.split('\n'):
                            if line.strip():
                                formatted_line = format_transcript_line(line)
                                st.markdown(formatted_line, unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)

                    # Enhanced editor section
                    st.markdown('<div class="editor-container">', unsafe_allow_html=True)
                    st.markdown('<div class="editor-header">', unsafe_allow_html=True)
                    st.markdown("### ✏️ Edit Transcript", unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)

                    # Instructions with better formatting
                    st.markdown('<div class="editor-instructions">', unsafe_allow_html=True)
                    st.markdown("""
                    Edit your transcript below. Keep in mind:
                    <div class="instruction-item">Timestamps should be in [MM:SS] format</div>
                    <div class="instruction-item">Speaker labels need a colon: Speaker: Text</div>
                    <div class="instruction-item">Special events use brackets: [MUSIC], [SOUND]</div>
                    <div class="instruction-item">Each line should start with a timestamp</div>
                    """, unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)

                    # Editor with preview
                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("#### Edit")
                        edited_text = st.text_area(
                            "Edit transcript",
                            value=st.session_state.edited_transcript,
                            height=400,
                            key="transcript_editor",
                            help="Edit your transcript here. Changes will be reflected in the preview."
                        )
                        st.session_state.edited_transcript = edited_text

                    with col2:
                        st.markdown("#### Live Preview")
                        st.markdown('<div class="preview-container">', unsafe_allow_html=True)
                        for line in edited_text.split('\n'):
                            if line.strip():
                                formatted_line = format_transcript_line(line)
                                st.markdown(formatted_line, unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)

                    st.markdown('</div>', unsafe_allow_html=True)

                    # Export options
                    st.markdown("### Export Options")
                    col1, col2, col3 = st.columns(3)

                    # Plain text export
                    with col1:
                        txt_content = format_transcript_for_export(st.session_state.edited_transcript, format='txt')
                        st.download_button(
                            label="📄 Download as TXT",
                            data=txt_content,
                            file_name="transcript.txt",
                            mime="text/plain"
                        )

                    # JSON export
                    with col2:
                        json_content = format_transcript_for_export(st.session_state.edited_transcript, format='json')
                        st.download_button(
                            label="🔧 Download as JSON",
                            data=json_content,
                            file_name="transcript.json",
                            mime="application/json"
                        )

                    # SRT export
                    with col3:
                        srt_content = format_transcript_for_export(st.session_state.edited_transcript, format='srt')
                        st.download_button(
                            label="🎬 Download as SRT",
                            data=srt_content,
                            file_name="transcript.srt",
                            mime="text/plain"
                        )

                except Exception as e:
                    st.error(f"An error occurred during transcription: {str(e)}")

                finally:
                    # Cleanup temporary file
                    try:
                        os.unlink(file_path)
                    except:
                        pass

    # Footer
    st.markdown("---")
    st.markdown("Powered by Google Gemini 2.0 API")

if __name__ == "__main__":
    main()