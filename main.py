import streamlit as st
import tempfile
import os
import json
import re
import concurrent.futures
from streamlit_ace import st_ace
from google import genai
from utils import (
    initialize_gemini, 
    get_transcription_prompt, 
    validate_audio_file, 
    chunk_audio_file, 
    adjust_chunk_timestamps, 
    combine_transcriptions,
    format_transcript_for_export
)
from styles import apply_custom_styles, format_transcript_line

# --- Simple Password Authentication ---
def check_password():
    """Returns `True` if the user had the correct password."""

    # Initialize password_correct in session state if it doesn't exist
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    # Only show input if password is not correct
    if not st.session_state["password_correct"]:
        # Center the login form with some styling
        st.markdown("<h3 style='text-align: center; margin-bottom: 20px;'>Audio Transcription</h3>", unsafe_allow_html=True)
        
        # Create a centered container for the login form
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("<div style='background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #eee;'>", unsafe_allow_html=True)
            st.markdown("<h4 style='text-align: center; margin-bottom: 15px;'>Login</h4>", unsafe_allow_html=True)
            
            # Password input field
            password = st.text_input("Password", type="password", key="password")
            
            # Login button
            if st.button("Login", type="primary"):
                # Check password
                if "app_password" in st.secrets and password == st.secrets["app_password"]:
                    st.session_state["password_correct"] = True
                    st.experimental_rerun()
                else:
                    st.error("😕 Password incorrect")
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        return False # Return False to block app execution
    else:
        # Password correct
        return True

def main():
    # Page configuration must be the first Streamlit command
    st.set_page_config(
        page_title="Audio Transcription",
        page_icon="🎙️",
        layout="centered"
    )

    # Apply custom styles after page config
    apply_custom_styles()

    # --- Check Password ---
    if not check_password():
        st.stop() # Stop execution if password check fails

    # --- Rest of your app code starts here ---

    # Clean, minimal header with subtle styling
    st.markdown("<h1 style='text-align: center; margin-bottom: 30px; color: #1E88E5;'>Audio Transcription</h1>", unsafe_allow_html=True)

    # Model selection in a clean card-like container
    with st.container():
        st.markdown("<div style='background-color: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px solid #eee; margin-bottom: 20px;'>", unsafe_allow_html=True)
        
        st.markdown("<h4 style='margin-bottom: 10px;'>Select Transcription Model</h4>", unsafe_allow_html=True)
        
        # Define model mapping to keep actual IDs for API but show friendly names in UI
        model_mapping = {
            "Gemini 2 Flash": "gemini-2.0-flash-001",
            "Gemini 2.5 Pro": "gemini-2.5-pro-preview-03-25"
        }
        
        # Model selection with tooltips using friendly names
        model_display = st.radio(
            "",  # Empty label since we have the header above
            options=list(model_mapping.keys()),
            index=1,  # Default to Gemini 2.5 Pro
            horizontal=True,
            help="Choose between faster (Flash) or more accurate (Pro) transcription"
        )
        
        # Get the actual model ID from the mapping
        model_selection = model_mapping[model_display]
        
        # Show model descriptions
        if model_display == "Gemini 2 Flash":
            st.caption("⚡ Optimized for speed, good for most transcriptions")
        else:
            st.caption("✨ Higher quality, better for complex audio or multiple speakers")
            
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Initialize Gemini client
    client, error_message, model_name = initialize_gemini(model_selection)
    
    # Check if client initialization was successful
    if not client:
        st.error(error_message)
        st.stop()
    else:
        # Show success message
        st.success(f"Gemini initialized with model: {model_name}")

    # Simplified metadata in a compact form
    with st.expander("Optional Context", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            content_type = st.selectbox(
                "Type",
                options=["Podcast", "Interview", "Meeting", "Presentation", "Other"],
                index=0
            )
            
            language = st.selectbox(
                "Language",
                options=["English", "Spanish", "French", "German", "Other"],
                index=0
            )
        
        with col2:
            topic = st.text_input("Topic")
            description = st.text_input("Description")

        # Input for number of speakers
        num_speakers = st.number_input(
            "Number of Speakers",
            min_value=1,
            value=1,
            step=1,
            help="Specify the total number of distinct speakers in the audio."
        )

    # File upload with visual enhancements
    with st.container():
        st.markdown("<div style='background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #eee;'>", unsafe_allow_html=True)
        
        st.markdown("<h4 style='margin-bottom: 10px;'>Upload Your Audio File</h4>", unsafe_allow_html=True)
        st.caption("Supported formats: MP3, WAV, OGG (max 200MB)")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            uploaded_file = st.file_uploader("", type=['mp3', 'wav', 'ogg'])
        
        # Initialize process_button to False by default
        process_button = False
        
        if uploaded_file:
            if not validate_audio_file(uploaded_file):
                st.stop()
                
            # Show file info
            file_size_mb = uploaded_file.size / (1024 * 1024)
            st.caption(f"File: {uploaded_file.name} ({file_size_mb:.1f} MB)")
                
            # Process button
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)  # Add spacing
                process_button = st.button("🎯 Transcribe", type="primary")
                
        st.markdown("</div>", unsafe_allow_html=True)
        
        if uploaded_file and process_button:
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
                        num_speakers=num_speakers,
                        metadata=metadata
                    )

                    # Define the worker function for processing a single chunk
                    def process_chunk(args):
                        i, chunk_path = args
                        # Note: Direct st calls might not behave perfectly inside threads
                        # Consider logging instead for production or more complex feedback
                        # st.write(f"Processing chunk {i+1}...") # Simple status update (might interleave awkwardly)
                        try:
                            # Read chunk data
                            with open(chunk_path, 'rb') as f:
                                chunk_data = f.read()

                            # Process chunk with Gemini API using the correct format
                            chunk_response = client.models.generate_content(
                                model=model_name,
                                contents=[
                                    prompt, # Pass the updated prompt including num_speakers
                                    genai.types.Part.from_bytes(
                                        data=chunk_data,
                                        mime_type=f"audio/{file_format}",
                                    ),
                                ],
                            )

                            # Access text from the response
                            chunk_text = chunk_response.text if hasattr(chunk_response, 'text') else chunk_response.candidates[0].content.parts[0].text
                            adjusted_transcription = adjust_chunk_timestamps(chunk_text, i)
                            return adjusted_transcription
                        except Exception as e:
                            # Log error instead of using st.error directly in thread
                            print(f"Error processing chunk {i+1}: {e}")
                            # Optionally, use st.error if running locally and testing, but be aware of potential issues
                            # st.error(f"Error processing chunk {i+1}: {e}")
                            return None # Return None on error for this chunk

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
                        
                        # Process chunks in parallel
                        status_container.info(f"Transcribing {num_chunks} chunks in parallel...")
                        all_transcriptions = []
                        chunk_args = [(i, chunk_path) for i, chunk_path in enumerate(chunk_paths)]

                        # Use ThreadPoolExecutor for parallel processing
                        # You might adjust max_workers based on API rate limits or system resources
                        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                            # map() returns results in the order tasks were submitted
                            results = executor.map(process_chunk, chunk_args)
                            all_transcriptions = [res for res in results if res is not None] # Filter out None results from errors

                        # --- Initialize combined_transcription earlier ---
                        combined_transcription = "" # Default to empty string

                        if not all_transcriptions or len(all_transcriptions) < num_chunks * 0.8: # Check if too many chunks failed
                            st.warning("Significant errors occurred during chunk transcription. The result might be incomplete or empty.")
                            if not all_transcriptions: # If ALL chunks failed, set specific message
                                combined_transcription = "Transcription failed due to errors in all chunks."
                            # If some chunks failed but not all, combined_transcription remains "" for now

                        # Combine transcriptions (only if there are successful ones)
                        status_container.info("Combining transcriptions...")
                        if all_transcriptions: # Only combine if there are successful transcriptions
                            combined_transcription = combine_transcriptions(all_transcriptions)
                        # If no transcriptions were successful, the message is already set, or it remains "" if only some failed.
                        
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
                        # Remove progress bar logic as it's complex with parallel execution
                        # progress_bar.progress(100) 
                        status_container.success("Transcription processing finished!")
                        
                        # Store transcript in session state
                        st.session_state.transcript_text = combined_transcription
                        st.session_state.edited_transcript = combined_transcription
                    
                    else:
                        # Process the entire file directly if small enough
                        # Process with Gemini API using the correct format
                        response = client.models.generate_content(
                            model=model_name,
                            contents=[
                                prompt,
                                genai.types.Part.from_bytes(
                                    data=audio_data,
                                    mime_type=f"audio/{file_format}",
                                ),
                            ],
                        )
                        
                        # Display results
                        st.success("Transcription completed!")
                        
                        # Store transcript in session state for export
                        if 'transcript_text' not in st.session_state:
                            # Access text from the response (different format in the new SDK)
                            response_text = response.text if hasattr(response, 'text') else response.candidates[0].content.parts[0].text
                            st.session_state.transcript_text = response_text

                    # Simple, clean tab interface
                    tabs = st.tabs(["Transcript", "Edit", "Export"])
                    
                    with tabs[0]:
                        # Format the transcript for display
                        st.markdown("### Transcript")
                        
                        # Add a container with custom styling for better visual appearance
                        with st.container():
                            st.markdown("<div class='transcript-container' style='background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #eee;'>")
                            
                            # Format each line of the transcript
                            formatted_lines = []
                            for line in st.session_state.transcript_text.split('\n'):
                                if line.strip():
                                    formatted_lines.append(format_transcript_line(line))
                            
                            # Join the formatted lines with paragraph tags for better spacing
                            formatted_transcript = '<p>' + '</p><p>'.join(formatted_lines) + '</p>'
                            st.markdown(formatted_transcript, unsafe_allow_html=True)
                            
                            st.markdown("</div>", unsafe_allow_html=True)
                    
                    with tabs[1]:
                        # Add an editor for the transcript using streamlit-ace
                        st.markdown("### Edit Transcript")
                        
                        # Initialize session state if needed
                        if 'edited_transcript' not in st.session_state:
                            st.session_state.edited_transcript = st.session_state.transcript_text
                        
                        # Use st_ace for a more advanced editor
                        edited_transcript = st_ace(
                            value=st.session_state.edited_transcript,
                            language='text',
                            theme='tomorrow_night',  # Return to original theme
                            keybinding='vscode',
                            font_size=14,
                            tab_size=4,
                            show_gutter=True,
                            show_print_margin=False,
                            wrap=True,
                            auto_update=False,
                            readonly=False,
                            height=400,
                            key="transcript_editor"
                        )
                        
                        # Explicitly update the session state with the edited transcript
                        st.session_state.edited_transcript = edited_transcript
                        
                        # Add a save button to make it clear that changes are being saved
                        if st.button("Save Changes", type="primary"):
                            st.success("Transcript changes saved!")
                    
                    with tabs[2]:
                        # Export options with improved UI
                        st.markdown("### Export Transcript")
                        
                        # Create a card-like container for export options
                        with st.container():
                            st.markdown("<div style='background-color: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #eee;'>")
                            
                            # Description
                            st.markdown("Choose a format and download your transcript:")
                            
                            # Format selection with icons
                            col1, col2 = st.columns([3, 2])
                            
                            with col1:
                                export_format = st.selectbox(
                                    "Export Format",
                                    options=["TXT", "SRT", "JSON"],
                                    index=0,
                                    help="TXT: Plain text | SRT: Subtitles | JSON: Data format"
                                )
                                
                                # Format descriptions
                                format_descriptions = {
                                    "TXT": "Simple text format, easy to read and edit.",
                                    "SRT": "Subtitle format for video players and editors.",
                                    "JSON": "Structured data format for developers."
                                }
                                st.caption(format_descriptions[export_format])
                            
                            # Map format selection to file extension
                            format_map = {"TXT": "txt", "SRT": "srt", "JSON": "json"}
                            format_key = format_map[export_format]
                            
                            # Format the content for export
                            formatted_content = format_transcript_for_export(
                                st.session_state.edited_transcript,
                                format=format_key
                            )
                            
                            # Generate a filename based on the upload
                            base_filename = os.path.splitext(uploaded_file.name)[0]
                            export_filename = f"{base_filename}_transcript.{format_key}"
                            
                            # Preview section
                            with st.expander("Preview Export"):
                                st.text(formatted_content[:500] + ("..." if len(formatted_content) > 500 else ""))
                            
                            # Download button
                            with col2:
                                st.markdown("<br>", unsafe_allow_html=True)  # Add some spacing
                                st.download_button(
                                    label=f"📥 Download {export_format.upper()}",
                                    data=formatted_content,
                                    file_name=export_filename,
                                    mime=f"text/{format_key}",
                                    type="primary",
                                    use_container_width=True
                                )
                            
                            st.markdown("</div>", unsafe_allow_html=True)

                except Exception as e:
                    # Log the error message in a secure way that doesn't leak sensitive information
                    error_message = str(e)
                    # Redact any potential API keys in error message
                    if 'key' in error_message.lower() and len(error_message) > 10:
                        error_message = "API authentication error. Please check your API key."
                    st.error(f"Error: {error_message}")

                finally:
                    # Cleanup temporary file
                    try:
                        if 'file_path' in locals():
                            os.unlink(file_path)
                        for chunk_path in chunk_paths if 'chunk_paths' in locals() else []:
                            os.unlink(chunk_path)
                    except:
                        pass  # Ignore cleanup errors
    
    # Footer - developer credit with LinkedIn link
    st.markdown("<div style='text-align: center; color: #888; font-size: 0.8em; margin-top: 50px;'><a href='https://www.linkedin.com/in/mansour-damanpak/' target='_blank' style='color: #1E88E5; text-decoration: none;'>Developed by Mansour Damanpak</a></div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()