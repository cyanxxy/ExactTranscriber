import streamlit as st
import tempfile
import os
import json
import re
import concurrent.futures
from streamlit_ace import st_ace
from google import genai
from google.genai import types as genai_types
from utils import (
    initialize_gemini, 
    get_transcription_prompt, 
    validate_audio_file, 
    chunk_audio_file, 
    adjust_chunk_timestamps, 
    combine_transcriptions,
    format_transcript_for_export
)
from styles import apply_custom_styles, format_transcript_line # Keep both for now
import logging # Added logging import

# MIME type mapping for audio formats
MIME_TYPE_MAPPING = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "m4a": "audio/mp4",
    "flac": "audio/flac",
    "ogg": "audio/ogg"
}

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    filename='transcriber_app.log',
                    filemode='a')

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
            st.markdown("<div class='styled-container'>", unsafe_allow_html=True) # Use CSS class
            st.markdown("<h4 style='text-align: center; margin-bottom: 15px;'>Login</h4>", unsafe_allow_html=True)
            
            # Password input field
            password = st.text_input("Password", type="password", key="password")
            
            # Login button
            if st.button("Login", type="primary"):
                # Check password
                if "app_password" in st.secrets and password == st.secrets["app_password"]:
                    st.session_state["password_correct"] = True
                    st.rerun() # Use the current standard function
                else:
                    st.error("😕 Password incorrect")
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        return False # Return False to block app execution
    else:
        # Password correct
        return True

def main():
    logging.info("Application started/restarted.")
    # Page configuration must be the first Streamlit command
    st.set_page_config(
        page_title="Audio Transcription",
        page_icon="🎙️",
        layout="centered"
    )

    # Apply custom styles after page config
    apply_custom_styles()

    # --- Initialize Session State --- 
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False # Ensure password state is initialized too
    if "processing_status" not in st.session_state:
        st.session_state.processing_status = "idle" # idle, processing, complete, error
    if "current_file_name" not in st.session_state:
        st.session_state.current_file_name = None
    if "transcript_text" not in st.session_state:
        st.session_state.transcript_text = None
    if "edited_transcript" not in st.session_state:
        st.session_state.edited_transcript = None
    if "error_message" not in st.session_state:
        st.session_state.error_message = None
    # Initialize editor content state separately
    if "transcript_editor_content" not in st.session_state:
        st.session_state.transcript_editor_content = ""

    logging.info(f"Initial state: processing_status={st.session_state.processing_status}, current_file_name={st.session_state.current_file_name}")

    # --- Check Password --- 
    if not check_password():
        st.stop() # Stop execution if password check fails

    # --- Rest of your app code starts here ---

    # Clean, minimal header
    st.markdown("<h1 style='text-align: center; margin-bottom: 30px; color: #1E88E5;'>Audio Transcription</h1>", unsafe_allow_html=True)

    # --- Model Selection --- 
    # Store selection in session state for use during processing rerun
    model_mapping = {
        "Gemini 2.0 Flash": "gemini-2.0-flash",
        "Gemini 2.5 Flash": "gemini-2.5-flash-preview-04-17"
    }
    with st.container():
        st.markdown("<div class='styled-container'>", unsafe_allow_html=True)
        st.markdown("<h4 style='margin-bottom: 10px;'>Select Transcription Model</h4>", unsafe_allow_html=True)
        
        # Use a key to access the widget's state
        model_display = st.radio(
            "Select transcription model", 
            options=list(model_mapping.keys()),
            index=1, # Default to Gemini 2.5 Pro
            horizontal=True,
            help="Choose between faster (Flash) or more accurate (Pro) transcription",
            label_visibility="collapsed",
            key="model_display_radio" # Add a key
        )
        # Store the actual model ID in session state
        st.session_state.selected_model_id = model_mapping[model_display]

        if model_display == "Gemini 2 Flash":
            st.caption("⚡ Optimized for speed, good for most transcriptions")
        else:
            st.caption("✨ Higher quality, better for complex audio or multiple speakers")
        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    # --- Initialize Gemini Client --- 
    # Initialize based on the selection stored in session state
    client, error_message_init, model_name = initialize_gemini(st.session_state.selected_model_id)
    if not client:
        st.error(error_message_init)
        st.session_state.processing_status = "error" # Mark error state if init fails
        st.session_state.error_message = error_message_init
        logging.error(f"Failed to initialize Gemini client: {error_message_init}")
        # Don't stop immediately, allow display of other elements or error message below
    else:
        st.success(f"Gemini initialized with model: {model_name}")
        logging.info(f"Gemini client initialized successfully with model: {model_name}")

    # --- Optional Context --- 
    # Store context in session state for use during processing rerun
    with st.expander("Optional Context", expanded=False):
        col1_ctx, col2_ctx = st.columns(2)
        with col1_ctx:
            st.session_state.content_type_select = st.selectbox(
                "Type", options=["Podcast", "Interview", "Meeting", "Presentation", "Other"], index=0, key="ctx_type"
            )
            st.session_state.language_select = st.selectbox(
                "Language", options=["English", "Spanish", "French", "German", "Other"], index=0, key="ctx_lang"
            )
        with col2_ctx:
            st.session_state.topic_input = st.text_input("Topic", key="ctx_topic")
            st.session_state.description_input = st.text_input("Description", key="ctx_desc")
            st.session_state.num_speakers_input = st.number_input(
                "Number of Speakers", min_value=1, value=1, step=1, 
                help="Specify the total number of distinct speakers in the audio.", key="ctx_speakers"
            )
    
    st.divider()

    # --- File Upload Section --- 
    with st.container():
        st.markdown("<div class='styled-container'>", unsafe_allow_html=True)
        st.markdown("<h4 style='margin-bottom: 10px;'>Upload Your Audio File</h4>", unsafe_allow_html=True)
        st.caption("Supported formats: MP3, WAV, OGG (max 200MB)")
        
        uploaded_file = st.file_uploader("Upload audio file", type=['mp3', 'wav', 'ogg'], key="file_uploader_widget")
        
        process_button = False
        
        if uploaded_file:
            if not validate_audio_file(uploaded_file):
                 # Validation error shown in validate_audio_file
                 pass # Allow script to continue to potentially show other errors
            else:
                file_size_mb = uploaded_file.size / (1024 * 1024)
                st.caption(f"File: {uploaded_file.name} ({file_size_mb:.1f} MB)")

                # Display status/error related to this specific file
                if st.session_state.current_file_name == uploaded_file.name:
                    if st.session_state.processing_status == "processing":
                        st.info("Transcription is already in progress...")
                    elif st.session_state.processing_status == "error":
                        st.error(f"Previous attempt failed: {st.session_state.error_message}")
                
                # Show transcribe button only if idle or error state for this file
                if not (st.session_state.current_file_name == uploaded_file.name and \
                        st.session_state.processing_status in ["processing", "complete"]):
                    process_button = st.button("🎯 Transcribe", type="primary", key="transcribe_button")
                
        st.markdown("</div>", unsafe_allow_html=True)
        
    # --- Transcription Logic Trigger --- 
    # Trigger only if button pressed AND status allows processing for this file
    if uploaded_file and process_button and \
       not (st.session_state.current_file_name == uploaded_file.name and \
            st.session_state.processing_status in ["processing", "complete"]):

        st.session_state.processing_status = "processing"
        st.session_state.current_file_name = uploaded_file.name
        st.session_state.transcript_text = None 
        st.session_state.edited_transcript = None
        st.session_state.error_message = None
        st.session_state.transcript_editor_content = "" 
        logging.info(f"Transcription started for file: {uploaded_file.name}")
        st.rerun() # Rerun to display results now that status is 'complete'

    # --- Display Results or Spinner --- 
    # Check if processing status is 'processing' AND the filename matches the one being processed
    if st.session_state.processing_status == "processing" and uploaded_file and st.session_state.current_file_name == uploaded_file.name:
        
        with st.spinner("Processing your audio file... This might take a while."):
            try:
                # --- Re-fetch necessary variables/context for processing --- 
                # Get audio data safely (assuming file_uploader widget state persists)
                audio_data = uploaded_file.getvalue()
                
                # Save uploaded file temporarily - essential for chunking
                with tempfile.NamedTemporaryFile(delete=False, suffix=uploaded_file.name, mode='wb') as tmp_file:
                    tmp_file.write(audio_data)
                    file_path = tmp_file.name
                try: os.chmod(file_path, 0o600)
                except: pass

                # Get client (already initialized above, check if still valid)
                if not client: # Re-check client status
                    raise Exception(st.session_state.error_message or "Gemini client not initialized.")
                
                # Get context from session state
                metadata = {
                    "content_type": st.session_state.content_type_select.lower() if st.session_state.content_type_select != "Other" else None,
                    "topic": st.session_state.topic_input if st.session_state.topic_input else None,
                    "description": st.session_state.description_input if st.session_state.description_input else None,
                    "language": st.session_state.language_select if st.session_state.language_select != "Other" else None
                }
                metadata = {k: v for k, v in metadata.items() if v is not None}
                prompt_template = get_transcription_prompt(metadata)
                prompt = prompt_template.render(num_speakers=st.session_state.num_speakers_input, metadata=metadata)
                
                file_format = uploaded_file.type.split('/')[-1]
                if file_format == 'mpeg': file_format = 'mp3'
                elif file_format == 'x-wav': file_format = 'wav'
                file_size_mb = uploaded_file.size / (1024 * 1024)
                large_file = file_size_mb > 20
                CHUNK_DURATION_MS = 120000

                # --- Actual Processing --- 
                if large_file:
                    # Chunking 
                    chunk_paths, num_chunks = chunk_audio_file(audio_data, file_format, chunk_duration_ms=CHUNK_DURATION_MS)
                    if num_chunks == 0 or not chunk_paths:
                        raise Exception("Failed to split audio file.") 

                    all_transcriptions = []
                    chunk_args = [(i, chunk_path) for i, chunk_path in enumerate(chunk_paths)]
                    
                    # Define the worker function INSIDE this block to capture necessary scope (client, model_name, prompt)
                    def process_chunk_worker(args): 
                        i, chunk_path = args
                        try:
                            # Inline chunk bytes for faster processing
                            with open(chunk_path, 'rb') as f:
                                chunk_data = f.read()
                            mime_type = MIME_TYPE_MAPPING.get(file_format, f"audio/{file_format}")
                            file_part = genai_types.Part.from_bytes(data=chunk_data, mime_type=mime_type)
                            chunk_response = client.models.generate_content(
                                model=model_name,
                                contents=[prompt, file_part],
                            )
                            chunk_text = chunk_response.text if hasattr(chunk_response, 'text') else chunk_response.candidates[0].content.parts[0].text
                            adjusted_transcription = adjust_chunk_timestamps(chunk_text, i, chunk_duration_ms=CHUNK_DURATION_MS)
                            return adjusted_transcription
                        except Exception as e:
                            print(f"Error processing chunk {i+1}: {e}") # Log error
                            # Optionally signal error more formally if needed
                            return None 

                    # Process chunks using the locally defined worker
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                        results = executor.map(process_chunk_worker, chunk_args) 
                        all_transcriptions = [res for res in results if res is not None]

                    # Combine or fallback if chunk errors
                    if all_transcriptions and len(all_transcriptions) >= num_chunks * 0.8:
                        combined_transcription = combine_transcriptions(all_transcriptions)
                    else:
                        st.info("Falling back to full audio transcription due to chunk errors.")
                        # Upload full audio via Files API for fallback
                        mime_type_full = MIME_TYPE_MAPPING.get(file_format, f"audio/{file_format}")
                        full_file_part = client.files.upload(file=file_path, config={"mimeType": mime_type_full})
                        full_resp = client.models.generate_content(
                            model=model_name,
                            contents=[prompt, full_file_part],
                        )
                        combined_transcription = (full_resp.text if hasattr(full_resp, 'text') 
                                                 else full_resp.candidates[0].content.parts[0].text)

                    # Store results in session state
                    st.session_state.transcript_text = combined_transcription
                    st.session_state.edited_transcript = combined_transcription
                    st.session_state.transcript_editor_content = combined_transcription # Update editor base
                    st.session_state.processing_status = "complete"

                    # Cleanup chunks
                    for chunk_path in chunk_paths:
                        try: os.unlink(chunk_path)
                        except: pass
                    try:
                        temp_dir = os.path.dirname(chunk_paths[0]) if chunk_paths else None
                        if temp_dir and os.path.exists(temp_dir): os.rmdir(temp_dir)
                    except: pass

                else: # Small file processing
                    mime_type = MIME_TYPE_MAPPING.get(file_format, f"audio/{file_format}")
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[prompt, genai_types.Part.from_bytes(data=audio_data, mime_type=mime_type)]
                    )
                    response_text = response.text if hasattr(response, 'text') else response.candidates[0].content.parts[0].text
                    st.session_state.transcript_text = response_text
                    st.session_state.edited_transcript = response_text 
                    st.session_state.transcript_editor_content = response_text # Update editor base
                    st.session_state.processing_status = "complete"

                # Cleanup original temp file (always do this after processing)
                try: os.unlink(file_path)
                except: pass

                logging.info(f"Transcription successful for file: {uploaded_file.name}")
                st.rerun() # Rerun to display results now that status is 'complete'

            except Exception as e:
                error_str = str(e)
                st.error(f"Transcription failed: {error_str}")
                st.session_state.processing_status = "error"
                st.session_state.error_message = error_str
                logging.error(f"Transcription failed for file {uploaded_file.name}: {error_str}", exc_info=True)
                # Ensure cleanup happens on error too
                try:
                    if 'file_path' in locals() and os.path.exists(file_path): os.unlink(file_path)
                except Exception as cleanup_e: logging.warning(f"Cleanup error (file_path): {cleanup_e}")
                try:
                    if 'chunk_paths' in locals():
                         temp_dir_err = None
                         for chunk_path in chunk_paths:
                             if os.path.exists(chunk_path):
                                 if not temp_dir_err: temp_dir_err = os.path.dirname(chunk_path)
                                 os.unlink(chunk_path)
                         if temp_dir_err and os.path.exists(temp_dir_err) and not os.listdir(temp_dir_err):
                              os.rmdir(temp_dir_err)
                except Exception as cleanup_e: logging.warning(f"Cleanup error (chunks): {cleanup_e}")
                st.rerun() # Rerun to show the error message state

    # --- Display Results Section --- 
    # Check if status is 'complete' AND the filename matches the one processed AND transcript exists
    elif st.session_state.processing_status == "complete" and \
         uploaded_file and st.session_state.current_file_name == uploaded_file.name and \
         st.session_state.transcript_text is not None:

        st.success("Transcription finished!")
        logging.info(f"Displaying results for file: {uploaded_file.name}")
        # --- Display Tabs (Transcript, Edit, Export) --- 
        tabs = st.tabs(["Transcript", "Edit", "Export"])
        
        with tabs[0]:
            # Display formatted st.session_state.transcript_text
            st.markdown("### Transcript")
            with st.container():
                 st.markdown("<div class='styled-container transcript-container'>", unsafe_allow_html=True)
                 formatted_lines = []
                 transcript_content = st.session_state.get("transcript_text", "")
                 for line in transcript_content.split('\n'):
                     if line.strip():
                         formatted_lines.append(format_transcript_line(line))
                 formatted_transcript = '<p>' + '</p><p>'.join(formatted_lines) + '</p>'
                 st.markdown(formatted_transcript, unsafe_allow_html=True)
                 st.markdown("</div>", unsafe_allow_html=True)

        with tabs[1]:
            # Display editor using st.session_state.edited_transcript or transcript_text
            st.markdown("### Edit Transcript")
            
            # Use dedicated editor state. If it's empty (e.g. after error or first load), 
            # initialize it from edited_transcript or transcript_text
            if not st.session_state.transcript_editor_content:
                 st.session_state.transcript_editor_content = st.session_state.get("edited_transcript", st.session_state.get("transcript_text", ""))

            edited_text = st_ace(
                value=st.session_state.transcript_editor_content, 
                language='text',
                theme='tomorrow_night',
                keybinding='vscode',
                font_size=14,
                tab_size=4,
                show_gutter=True,
                show_print_margin=False,
                wrap=True,
                auto_update=False, # Use manual save
                readonly=False,
                height=400,
                key="transcript_editor_widget" 
            )
            # Add explicit save button
            if st.button("Save Edits", key="save_edits_button"):
                st.session_state.edited_transcript = edited_text 
                st.session_state.transcript_editor_content = edited_text 
                logging.info(f"User saved edits for file: {uploaded_file.name}")
                st.success("Edits saved!")
                # No rerun needed normally, state is saved

        with tabs[2]:
            # Export logic using st.session_state.edited_transcript
            st.markdown("### Export Transcript")
            with st.container():
                st.markdown("<div class='styled-container'>", unsafe_allow_html=True)
                st.markdown("Choose a format and download your transcript:")
                col1_exp, col2_exp = st.columns([3, 2])
                with col1_exp:
                    export_format = st.selectbox(
                        "Export Format", options=["TXT", "SRT", "JSON"], index=0,
                        help="TXT: Plain text | SRT: Subtitles | JSON: Data format", key="export_format_select"
                    )
                    format_descriptions = {
                        "TXT": "Simple text format...", "SRT": "Subtitle format...", "JSON": "Structured data..."
                    }
                    st.caption(format_descriptions[export_format])

                format_map = {"TXT": "txt", "SRT": "srt", "JSON": "json"}
                mime_map = {"TXT": "text/plain", "SRT": "application/x-subrip", "JSON": "application/json"}
                format_key = format_map[export_format]
                mime_type = mime_map[export_format]

                # Always use latest editor content if available
                export_content = st.session_state.get("transcript_editor_content", st.session_state.get("edited_transcript", st.session_state.get("transcript_text", "")))
                formatted_content = format_transcript_for_export(export_content, format=format_key)
                base_filename = os.path.splitext(st.session_state.current_file_name)[0]
                export_filename = f"{base_filename}_transcript.{format_key}"

                # Warn if edits are not saved
                unsaved_edits = (
                    st.session_state.get("transcript_editor_content", "") != st.session_state.get("edited_transcript", "")
                )
                if unsaved_edits:
                    st.warning("You have unsaved edits. Please click 'Save Edits' before exporting to include your latest changes.")

                with st.expander("Preview Export"):
                    st.text(formatted_content[:500] + ("..." if len(formatted_content) > 500 else ""))
                with col2_exp:
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.download_button(
                        label=f"📥 Download {export_format.upper()}", data=formatted_content,
                        file_name=export_filename, mime=mime_type, type="primary",
                        use_container_width=True, key=f"download_button_{export_format}"
                    )
                st.markdown("</div>", unsafe_allow_html=True)

    # Handle case where an error occurred but no file is currently uploaded (e.g., Gemini init failed)
    elif st.session_state.processing_status == "error" and not uploaded_file:
         st.error(f"An error occurred: {st.session_state.error_message}")
         logging.error(f"Error occurred without file upload: {st.session_state.error_message}")

    # Footer
    st.markdown("<div style='text-align: center; color: #888; font-size: 0.8em; margin-top: 50px;'><a href='https://www.linkedin.com/in/mansour-damanpak/' target='_blank' style='color: #1E88E5; text-decoration: none;'>Developed by Mansour Damanpak</a></div>", unsafe_allow_html=True)

    logging.info("Application main function finished execution for this run.")

if __name__ == "__main__":
    main()