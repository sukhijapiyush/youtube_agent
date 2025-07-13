# Project Plan: YouTube Metadata Enrichment Console Application

## 1. Objective

To create a zero-cost, standalone console application that accepts a YouTube video or playlist URL. The application will fetch the available metadata, use a locally-run LLM via Ollama to generate a summary and tags, and then store the final structured data in a local SQLite database.

## 2. Core Philosophy & Constraints

- **Zero Cost:** The entire workflow must rely on free and open-source tools.
- **No Official APIs:** We will not use the Google/YouTube Data API v3.
- **No Browser Automation:** The application must run headlessly from the command line.
- **Local First:** All AI processing and data storage will be done locally.

## 3. Technology Stack

- **Language:** Python 3
- **YouTube Metadata Fetching:**
  - `yt-dlp`: The core library for extracting comprehensive metadata.
  - `youtube-transcript-api`: A specialized library to efficiently fetch video transcripts.
- **LLM Engine:** Ollama
- **Database:** SQLite 3 (Python's built-in `sqlite3` module)
- **User Interface:** Command-line interface (CLI) using Python's `argparse` library

## 4. Step-by-Step Execution Flow

### Step 1: Database Initialization

- On startup, the application will connect to a local SQLite database file (e.g., `youtube_data.db`).
- It will execute a `CREATE TABLE IF NOT EXISTS` command to ensure a table named `videos` exists with the correct schema (e.g., columns for URL, name, summary, tags, etc.).
- Using URL as a `UNIQUE` key will prevent duplicate entries.

### Step 2: Input & URL Validation

- The application starts and expects a YouTube URL as a command-line argument.
- It will use `yt-dlp` to validate the URL and determine if it's a single video or a playlist.

### Step 3: Metadata Fetching & Pre-processing (with yt-dlp)

**For a Single Video:**

- Use `yt-dlp` to extract the video's metadata (title, description, video ID, URL).
- Use `youtube-transcript-api` with the video ID to fetch the full transcript.

**For a Playlist:**

- Use `yt-dlp` to get a list of all video entries in the playlist.
- The application will iterate through this list, running the "Single Video" process for each one.

### Step 4: LLM Enrichment (Multi-Call Strategy with Ollama)

For each video, the application makes two calls to the local Ollama API:

1. **LLM Call 1: Summarization**  
   Generate a concise summary from the title, description, and transcript.
2. **LLM Call 2: Tag Generation**  
   Generate relevant tags based on the title, description, and the newly created summary.

### Step 5: Database Storage

- After a video has been fully processed and enriched, the application will assemble the final data (name, URL, type, summary, tags).
- It will then execute an `INSERT OR REPLACE` SQL command. This command inserts a new row into the `videos` table. Using `OR REPLACE` ensures that if the same video URL is processed again, its entry in the database will be updated with the latest information.
- A confirmation message will be printed to the console for each video saved.

## 6. Error Handling & Edge Cases

- **Invalid URL:** Handled by `yt-dlp` exceptions.
- **No Transcript:** Handled by `youtube-transcript-api` exceptions; the process continues without the transcript.
- **Ollama Not Running:** Connection errors to the Ollama API are caught, and an informative message is displayed.
- **Database Errors:** Standard `try...except` blocks will be used for all database operations to handle potential
