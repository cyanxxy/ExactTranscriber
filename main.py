import streamlit as st
import logging
from typing import Optional

# Import from new module structure
from api_client import initialize_gemini
from ui_components import (
    render_model_selection,
    render_context_inputs,
    render_file_upload,
    render_transcript_tabs,
    render_footer
)
from transcription_processor import process_transcription_task
from styles import apply_custom_styles
from app_setup import setup_logging, setup_streamlit_page
from state_manager import initialize_state

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)


def check_password() -> bool:
    """Returns `True` if the user had the correct password."""
    # Initialize password_correct in session state if it doesn't exist
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    # Only show input if password is not correct
    if not st.session_state["password_correct"]:
        # Center the login form with some styling
        st.markdown("<h3 style='text-align: center; margin-bottom: 20px;'>Audio Transcription</h3>", 
                   unsafe_allow_html=True)
        
        # Create a centered container for the login form
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("<div class='styled-container'>", unsafe_allow_html=True)
            st.markdown("<h4 style='text-align: center; margin-bottom: 15px;'>Login</h4>", 
                       unsafe_allow_html=True)
            
            # Password input field
            password = st.text_input("Password", type="password", key="password")
            
            # Login button
            if st.button("Login", type="primary"):
                # Check password
                if "app_password" in st.secrets and password == st.secrets["app_password"]:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("😕 Password incorrect")
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        return False
    else:
        return True


def handle_transcription_processing(uploaded_file, client, model_name: str) -> None:
    """Handle the transcription processing workflow."""
    # Get metadata from session state
    metadata = {
        "content_type": st.session_state.content_type_select.lower() 
                        if st.session_state.content_type_select != "Other" else None,
        "topic": st.session_state.topic_input if st.session_state.topic_input else None,
        "description": st.session_state.description_input if st.session_state.description_input else None,
        "language": st.session_state.language_select 
                    if st.session_state.language_select != "Other" else None
    }
    metadata = {k: v for k, v in metadata.items() if v is not None}
    
    num_speakers = st.session_state.num_speakers_input
    
    with st.spinner("Processing your audio file... This might take a while."):
        try:
            # Process transcription
            result = process_transcription_task(
                client, model_name, uploaded_file, metadata, num_speakers
            )
            
            if result["success"]:
                # Update session state with results
                st.session_state.transcript_text = result["transcript"]
                st.session_state.edited_transcript = result["transcript"]
                st.session_state.transcript_editor_content = result["transcript"]
                st.session_state.processing_status = "complete"
                
                logger.info(f"Transcription successful for file: {uploaded_file.name}")
                st.rerun()
            else:
                # Handle error
                handle_transcription_error(result["error"], uploaded_file.name)
                
        except Exception as e:
            # Handle unexpected error
            handle_transcription_error(str(e), uploaded_file.name, unexpected=True)


def handle_transcription_error(error_message: str, filename: str, unexpected: bool = False) -> None:
    """Handle transcription errors consistently."""
    if unexpected:
        user_message = "An unexpected error occurred during transcription."
        logger.error(f"Unexpected transcription error for {filename}: {error_message}", exc_info=True)
    else:
        user_message = error_message
        logger.error(f"Transcription failed for {filename}: {error_message}")
    
    st.error(f"Transcription failed: {user_message}")
    st.session_state.processing_status = "error"
    st.session_state.error_message = user_message
    st.rerun()


def main():
    """Main application entry point."""
    logger.info("Application started/restarted.")
    
    # Setup page configuration
    setup_streamlit_page()
    apply_custom_styles()
    
    # Initialize session state
    initialize_state()
    
    logger.info(f"Initial state: processing_status={st.session_state.processing_status}, "
               f"current_file_name={st.session_state.current_file_name}")
    
    # Check password
    if not check_password():
        st.stop()
    
    # Application header
    st.markdown("<h1>Audio Transcription</h1>", unsafe_allow_html=True)
    
    # Model selection
    selected_model_id = render_model_selection()
    st.divider()
    
    # Initialize Gemini client
    client, error_message, model_name = initialize_gemini(selected_model_id)
    if not client:
        st.error(error_message)
        st.session_state.processing_status = "error"
        st.session_state.error_message = error_message
        logger.error(f"Failed to initialize Gemini client: {error_message}")
    else:
        st.success(f"Gemini initialized with model: {model_name}")
        logger.info(f"Gemini client initialized successfully with model: {model_name}")
    
    # Context inputs
    metadata, num_speakers = render_context_inputs()
    # Store in session state for processing
    st.session_state.content_type_select = metadata.get("content_type", "").title() or "Other"
    st.session_state.language_select = metadata.get("language", "").title() or "Other"
    st.session_state.topic_input = metadata.get("topic", "")
    st.session_state.description_input = metadata.get("description", "")
    st.session_state.num_speakers_input = num_speakers
    
    st.divider()
    
    # File upload
    uploaded_file, process_button = render_file_upload()
    
    # Handle transcription trigger
    if uploaded_file and process_button and client and \
       not (st.session_state.current_file_name == uploaded_file.name and 
            st.session_state.processing_status in ["processing", "complete"]):
        
        # Update state
        st.session_state.processing_status = "processing"
        st.session_state.current_file_name = uploaded_file.name
        st.session_state.transcript_text = None
        st.session_state.edited_transcript = None
        st.session_state.error_message = None
        st.session_state.transcript_editor_content = ""
        
        logger.info(f"Transcription started for file: {uploaded_file.name}")
        st.rerun()
    
    # Handle processing state
    if st.session_state.processing_status == "processing" and uploaded_file and \
       st.session_state.current_file_name == uploaded_file.name:
        handle_transcription_processing(uploaded_file, client, model_name)
    
    # Display results
    elif st.session_state.processing_status == "complete" and uploaded_file and \
         st.session_state.current_file_name == uploaded_file.name and \
         st.session_state.transcript_text is not None:
        
        st.success("Transcription finished!")
        logger.info(f"Displaying results for file: {uploaded_file.name}")
        render_transcript_tabs(st.session_state.transcript_text, uploaded_file.name)
    
    # Handle error state without file
    elif st.session_state.processing_status == "error" and not uploaded_file:
        st.error(f"An error occurred: {st.session_state.error_message}")
        logger.error(f"Error occurred without file upload: {st.session_state.error_message}")
    
    # Footer
    render_footer()
    
    logger.info("Application main function finished execution for this run.")


if __name__ == "__main__":
    main()