import re

def sanitize_error_message(error_message: str) -> str:
    """Sanitize error messages to remove sensitive information."""
    if not isinstance(error_message, str):
        # In case a non-string error was passed, though type hinting should prevent this.
        return "An unexpected error occurred. Error was not a string."

    # Remove potential API keys
    # More specific Google AI-style API key pattern
    sanitized = re.sub(r'AIza[0-9A-Za-z\-_]{35}', '[REDACTED_API_KEY]', error_message)
    # General long alphanumeric strings that might be other forms of keys or sensitive tokens
    # Using \b for word boundaries to avoid redacting parts of legitimate words or IDs.
    sanitized = re.sub(r'\b[A-Za-z0-9\-_]{32,}\b', '[REDACTED_SENSITIVE_STRING]', sanitized)

    # Remove potential user-specific paths (covers more cases like /home/user, /var/user, etc.)
    # Linux/macOS style paths
    sanitized = re.sub(r'(?:/home/|/Users/|/var/users/)[^/\s]+', '[REDACTED_USER_PATH]', sanitized, flags=re.IGNORECASE)
    # Windows style paths - simplified to avoid excessive complexity with drive letters for now
    # Looks for C:\Users\someuser or \\server\share\users\someuser
    sanitized = re.sub(r'(?:C:\\Users\\|\\Users\\)[^\s\\]+', '[REDACTED_USER_PATH]', sanitized, flags=re.IGNORECASE)
    
    # Consider removing specific error codes or server names if they are too revealing,
    # but this can also make debugging harder. For now, focusing on keys and paths.

    # Example of removing an email, if errors might contain them:
    # sanitized = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[REDACTED_EMAIL]', sanitized)

    return sanitized
