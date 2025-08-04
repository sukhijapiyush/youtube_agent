# YouTube Content Enricher

A zero-cost, standalone Python application and web interface for enriching YouTube videos, playlists, and web content with AI-generated summaries, tags, and categories—stored locally in SQLite. No official APIs or browser automation required.

## Features

- **YouTube Video & Playlist Enrichment:** Extracts metadata, transcripts, and enriches with AI-generated summaries, tags, and categories.
- **Webpage & PDF Support:** Enrich arbitrary web pages and PDF files.
- **Batch Processing:** Queue multiple URLs/files for enrichment via batch file or web UI.
- **Modern Web UI:** React-based interface for managing, searching, and editing your content library.
- **Local-First & Zero Cost:** All processing and storage is local; no paid APIs or cloud dependencies.
- **Extensible:** Easily add new file types or enrichment models.

## Technology Stack

- **Backend:** Python 3, Flask, SQLite, Gunicorn (for production)
- **YouTube Metadata:** `yt-dlp`, `youtube-transcript-api`
- **AI Enrichment:** Google Gemini (default), supports Ollama (local LLMs)
- **Frontend:** React (via CDN), Tailwind CSS
- **Other:** `requests`, `google-genai`, `bs4`, `pydantic`, `fitz` (PyMuPDF)

## Setup & Installation

1. **Clone the repository**
2. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```
3. **Configure API keys:**
   - Set your Gemini or Ollama API key in `constants.py` (`API_KEY = "..."`)
   - Adjust model and endpoint in `config.py` if needed.

4. **Run the app:**
   ```
   python app.py
   ```
   - For production: use `gunicorn wsgi:app`

5. **Access the web UI:**
   - Open [http://localhost:5001](http://localhost:5001) in your browser.

## Usage

- **Enrich a YouTube URL or file:** Paste a URL or upload a file in the web UI, or use the batch file (`batch_links.txt`).
- **Batch Processing:** Add multiple URLs to `batch_links.txt` or via the UI, then start batch processing.
- **Library Management:** Search, filter, edit, or delete enriched items from the web interface.
- **Reprocessing:** Re-enrich any item or the entire library with a single click.

## File Structure

- `app.py` - Flask backend and API endpoints
- `enricher.py` - Core enrichment logic (YouTube, web, PDF)
- `config.py` - Configuration (DB, model, endpoints)
- `constants.py` - API keys and constants
- `templates/index.html` - Web UI (React + Tailwind)
- `requirements.txt` - Python dependencies
- `uploads/` - Uploaded files
- `journals/` - (Optional) For future extensions

## Configuration

- **Model:** Set `DEFAULT_OLLAMA_MODEL` or Gemini model in `config.py`
- **Database:** Default is `youtube_enriched_data.db`
- **API Keys:** Set in `constants.py`

## Extending

- Add new file types in `enricher.py` (`process_file`)
- Add new enrichment models in `config.py` and `enricher.py`

## License

MIT License
