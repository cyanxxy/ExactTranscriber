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

    # File upload
    uploaded_file = st.file_uploader("Upload an audio file", type=['mp3', 'wav', 'ogg'])

    if uploaded_file:
        if not validate_audio_file(uploaded_file):
            st.stop()

        # Speaker input
        speakers = st.text_input(
            "Enter speaker names (comma-separated)",
            value="Speaker A",
            help="Example: John, Sarah, Michael"
        ).split(',')
        speakers = [s.strip() for s in speakers if s.strip()]

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

                    # Generate transcription prompt
                    prompt_template = get_transcription_prompt()
                    prompt = prompt_template.render(speakers=speakers)

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
                    st.session_state.transcript_text = response.text

                    # Display formatted transcript
                    st.markdown("### Transcript")
                    with st.container():
                        st.markdown('<div class="transcript-container">', unsafe_allow_html=True)
                        for line in response.text.split('\n'):
                            if line.strip():
                                formatted_line = format_transcript_line(line)
                                st.markdown(formatted_line, unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)

                    # Export options
                    st.markdown("### Export Options")
                    col1, col2, col3 = st.columns(3)

                    # Plain text export
                    with col1:
                        txt_content = format_transcript_for_export(st.session_state.transcript_text, format='txt')
                        st.download_button(
                            label="📄 Download as TXT",
                            data=txt_content,
                            file_name="transcript.txt",
                            mime="text/plain"
                        )

                    # JSON export
                    with col2:
                        json_content = format_transcript_for_export(st.session_state.transcript_text, format='json')
                        st.download_button(
                            label="🔧 Download as JSON",
                            data=json_content,
                            file_name="transcript.json",
                            mime="application/json"
                        )

                    # SRT export
                    with col3:
                        srt_content = format_transcript_for_export(st.session_state.transcript_text, format='srt')
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