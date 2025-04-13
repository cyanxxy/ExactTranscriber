import streamlit as st
import tempfile
import os
import json
import re
from utils import (
    initialize_gemini, 
    get_transcription_prompt, 
    validate_audio_file, 
    format_transcript_for_export,
    chunk_audio_file,
    adjust_chunk_timestamps,
    combine_transcriptions
)
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

    # Model selection
    st.sidebar.markdown("## Model Settings")
    model_selection = st.sidebar.radio(
        "Select Gemini Model",
        options=["gemini-2.0-flash-001", "gemini-2.5-pro-preview-03-25"],
        index=0,
        help="Choose which Gemini model to use for transcription. gemini-2.0-flash-001 is optimized for speed, while gemini-2.5-pro-preview-03-25 may provide higher quality."
    )
    
    # Display model information
    st.sidebar.markdown("### Model Information")
    if model_selection == "gemini-2.0-flash-001":
        st.sidebar.info("""
        **Gemini 2.0 Flash**
        - Optimized for speed and efficiency
        - Good for general transcription tasks
        - Reliable timestamp generation
        - Great for longer audio files when using chunking
        """)
    else:
        st.sidebar.info("""
        **Gemini 2.5 Pro Preview**
        - Latest model version with enhanced capabilities
        - May provide better accuracy for complex audio
        - Potentially better speaker identification
        - Could improve special audio event detection
        - May be slower than Flash model
        """)
    
    # Initialize Gemini client with selected model
    try:
        model = initialize_gemini(model_selection)
        st.sidebar.success(f"Using {model_selection}")
    except Exception as e:
        error_message = str(e)
        # Redact any potential API keys in error message
        if 'key' in error_message.lower() and len(error_message) > 10:
            error_message = "API authentication error. Please check your API key."
        st.error(f"Failed to initialize Gemini client: {error_message}")
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
                    # Save uploaded file temporarily with secure permissions
                    with tempfile.NamedTemporaryFile(delete=False, suffix=uploaded_file.name, mode='wb') as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        file_path = tmp_file.name
                    
                    # Set secure permissions for the temporary file (if on Unix-like OS)
                    try:
                        os.chmod(file_path, 0o600)  # Read/write for owner only
                    except:
                        pass  # Skip if on Windows or permission change fails

                    # Read audio file as bytes
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

                    # Determine file format for chunking
                    file_format = uploaded_file.type.split('/')[-1]
                    if file_format == 'mpeg':
                        file_format = 'mp3'
                    elif file_format == 'x-wav':
                        file_format = 'wav'

                    # Check file size to determine if chunking is needed
                    file_size_mb = uploaded_file.size / (1024 * 1024)
                    large_file = file_size_mb > 20  # 20MB threshold
                    
                    if large_file:
                        # Create a status container for showing progress
                        status_container = st.empty()
                        status_container.info("Processing large audio file (up to 4 hours). This may take some time...")
                        
                        # Create a progress bar
                        progress_bar = st.progress(0)
                        
                        # Split audio into chunks (default 10 minute chunks)
                        status_container.info("Splitting audio into manageable chunks...")
                        chunk_paths, num_chunks = chunk_audio_file(audio_data, file_format)
                        
                        if num_chunks == 0 or not chunk_paths:
                            st.error("Failed to split audio file. Please try a different file.")
                            st.stop()
                        
                        # Process each chunk and collect transcriptions
                        all_transcriptions = []
                        
                        for i, chunk_path in enumerate(chunk_paths):
                            # Update progress
                            progress = int((i / num_chunks) * 100)
                            progress_bar.progress(progress)
                            status_container.info(f"Transcribing chunk {i+1} of {num_chunks}...")
                            
                            # Read chunk data
                            with open(chunk_path, 'rb') as f:
                                chunk_data = f.read()
                            
                            # Process chunk with Gemini API
                            chunk_response = model.generate_content(
                                [
                                    prompt,
                                    {
                                        "mime_type": uploaded_file.type,
                                        "data": chunk_data
                                    }
                                ]
                            )
                            
                            # Adjust timestamps based on chunk position
                            adjusted_transcription = adjust_chunk_timestamps(chunk_response.text, i)
                            all_transcriptions.append(adjusted_transcription)
                        
                        # Combine all transcriptions
                        status_container.info("Combining all transcriptions...")
                        combined_transcription = combine_transcriptions(all_transcriptions)
                        
                        # Clean up temporary chunk files
                        status_container.info("Cleaning up temporary files...")
                        for chunk_path in chunk_paths:
                            try:
                                os.unlink(chunk_path)
                            except:
                                pass
                        
                        # Try to clean up the temporary directory
                        try:
                            temp_dir = os.path.dirname(chunk_paths[0]) if chunk_paths else None
                            if temp_dir and os.path.exists(temp_dir):
                                os.rmdir(temp_dir)
                        except:
                            pass
                        
                        # Update progress to 100%
                        progress_bar.progress(100)
                        status_container.success("Transcription completed!")
                        
                        # Store transcript in session state
                        if 'transcript_text' not in st.session_state:
                            st.session_state.transcript_text = combined_transcription
                        if 'edited_transcript' not in st.session_state:
                            st.session_state.edited_transcript = combined_transcription
                    
                    else:
                        # Process small audio file directly
                        response = model.generate_content(
                            [
                                prompt,
                                {
                                    "mime_type": uploaded_file.type,
                                    "data": audio_data
                                }
                            ]
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

                    # Add editor
                    st.markdown("### Edit Transcript")
                    st.markdown("""
                    Edit the transcript below to fix any issues. The edited version will be used for export.
                    - Keep the timestamp format: [MM:SS]
                    - Maintain speaker labels with colons: Speaker: Text
                    - Preserve special event format: [MUSIC], [SOUND], etc.
                    """)
                    edited_text = st.text_area(
                        "Edit transcript",
                        value=st.session_state.edited_transcript,
                        height=300,
                        key="transcript_editor"
                    )
                    st.session_state.edited_transcript = edited_text

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
                    # Log the error message in a secure way that doesn't leak sensitive information
                    error_message = str(e)
                    # Redact any potential API keys in error message
                    if 'key' in error_message.lower() and len(error_message) > 10:
                        error_message = "API authentication error. Please check your API key."
                    st.error(f"An error occurred during transcription: {error_message}")

                finally:
                    # Cleanup temporary file
                    try:
                        if 'file_path' in locals():
                            os.unlink(file_path)
                    except:
                        pass

    # Footer
    st.markdown("---")
    st.markdown("Powered by Google Gemini API")

if __name__ == "__main__":
    main()