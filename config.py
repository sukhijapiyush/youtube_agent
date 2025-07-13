# config.py
# This file contains all the configuration settings for the application.
# By keeping them in one place, we can easily manage different environments
# (e.g., development vs. production) without changing the core application logic.

# --- General Settings ---
DB_FILE = "youtube_enriched_data.db"
ENRICHER_SCRIPT_PATH = "enricher.py"

# --- Ollama Configuration ---
# The default Ollama model to use for generating summaries and tags.
# Models like 'llama3:8b', 'mistral', or 'phi3' are good choices.
DEFAULT_OLLAMA_MODEL = "qwen2.5:1.5b"

# The local API endpoint for the Ollama service.
OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"

# --- WSGI Server Configuration (for Gunicorn) ---
# These settings are used when running the app with a production server.
GUNICORN_WORKERS = 4  # Number of worker processes
GUNICORN_BIND_ADDR = "0.0.0.0:8000"  # Address to bind to
