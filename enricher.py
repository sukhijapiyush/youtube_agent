# enricher.py
import argparse
import sqlite3
import sys
import json
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from yt_dlp import YoutubeDL
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    NoTranscriptFound,
    TranscriptsDisabled,
)
from youtube_transcript_api.formatters import TextFormatter
from google import genai
from google.genai import types
from pydantic import BaseModel
import config
import time
import random
from constants import API_KEY
import re
import os


class VideoData(BaseModel):
    summary: str
    tags: list[str]
    category: str


# Configure the client
client = genai.Client(api_key=API_KEY)

# Define the grounding tool
# grounding_tool = types.Tool(google_search=types.GoogleSearch())

# # Configure generation settings
# gen_config = types.GenerateContentConfig(tools=[grounding_tool])
# gen_config.response_schema = VideoData

gen_config = types.GenerateContentConfig(
    thinking_config=types.ThinkingConfig(thinking_budget=4096)
)


# --- Database Functions ---
def setup_database():
    print(f"STEP 1: Setting up database at '{config.DB_FILE}'...", flush=True)
    conn = sqlite3.connect(config.DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, url TEXT NOT NULL UNIQUE,
            type TEXT, summary TEXT, tags TEXT, category TEXT, 
            thumbnail_url TEXT, uploader TEXT, duration INTEGER,
            processed_at TIMESTAMP NOT NULL,
            playlist_id INTEGER,
            FOREIGN KEY (playlist_id) REFERENCES playlists (id)
        )"""
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, url TEXT NOT NULL UNIQUE,
            uploader TEXT, video_count INTEGER, processed_at TIMESTAMP NOT NULL
        )"""
    )
    conn.commit()
    return conn


def save_video_to_db(
    conn: sqlite3.Connection, video_data: dict, playlist_id: int = None
):
    print(
        f"  -> STEP 4: Saving enriched data for '{video_data['name']}'...", flush=True
    )
    sql = """
        INSERT OR REPLACE INTO videos 
        (name, url, type, summary, tags, category, thumbnail_url, uploader, duration, processed_at, playlist_id) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    try:
        cursor = conn.cursor()
        cursor.execute(
            sql,
            (
                video_data["name"],
                video_data["url"],
                video_data["type"],
                video_data["summary"],
                video_data["tags"],
                video_data["category"],
                video_data["thumbnail_url"],
                video_data["uploader"],
                video_data["duration"],
                datetime.now(),
                playlist_id,
            ),
        )
        conn.commit()
        print("  -> SUCCESS: Data saved.", flush=True)
    except sqlite3.Error as e:
        print(
            f"ERROR: Could not save video to database: {e}", file=sys.stderr, flush=True
        )


# --- Core Functions ---
def get_video_transcript(video_id: str, video_info: dict) -> str:
    """
    Fetches transcript. First tries youtube_transcript_api, falls back to yt-dlp.
    If using fallback, it prepends the video description to the transcript.
    """
    video_id = video_info.get("id", "")
    description = video_info.get("description", "")
    print(
        f"    - Sub-step 3.1: Fetching transcript for video ID: {video_id}...",
        flush=True,
    )

    # --- Primary Method: youtube-transcript-api ---
    try:
        print("      -> Attempting transcript fetch with primary API...", flush=True)
    #     language_codes = ["en", "hi"]
    #     transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    #     transcript = None
    #     try:
    #         transcript = transcript_list.find_manually_created_transcript(
    #             language_codes
    #         )
    #         print(
    #             f"      -> Found manually created transcript in '{transcript.language_code}'.",
    #             flush=True,
    #         )
    #     except NoTranscriptFound:
    #         print(
    #             "      -> No manual transcript found. Checking for auto-generated...",
    #             flush=True,
    #         )
    #         transcript = transcript_list.find_generated_transcript(language_codes)
    #         print(
    #             f"      -> Found auto-generated transcript in '{transcript.language_code}'.",
    #             flush=True,
    #         )

    #     formatter = TextFormatter()
    #     text = formatter.format_transcript(transcript.fetch())
    #     print(
    #         "      -> Transcript fetched and formatted successfully via API.",
    #         flush=True,
    #     )
    #     return text
    except Exception as api_error:
        print(
            f"      -> Primary transcript API failed: {api_error}",
            file=sys.stderr,
            flush=True,
        )
        print(f"      -> Attempting fallback using yt-dlp...", flush=True)

        # --- Fallback Method: yt-dlp ---
        try:
            ydl_opts = {
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": ["en", "hi"],
                "skip_download": True,
                "outtmpl": f"{video_id}",  # Use video_id for predictable filename
                "subtitlesformat": "ttml",
                "quiet": True,
                "noplaylist": True,
            }

            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

            subtitle_file = None
            for lang in ["en", "hi"]:
                potential_file = f"{video_id}.{lang}.ttml"
                if os.path.exists(potential_file):
                    subtitle_file = potential_file
                    break

            if not subtitle_file:
                print(
                    "      -> yt-dlp fallback failed: No subtitle file was downloaded.",
                    file=sys.stderr,
                    flush=True,
                )
                return ""

            print(f"      -> Found subtitle file: {subtitle_file}", flush=True)
            with open(subtitle_file, "r", encoding="utf-8") as f:
                content = f.read()

            os.remove(subtitle_file)

            text_parts = re.findall(r">([^<]+)</p>", content)
            full_transcript = " ".join(
                part.strip().replace("\n", " ") for part in text_parts
            )

            if full_transcript:
                print(
                    "      -> Transcript extracted successfully via yt-dlp fallback.",
                    flush=True,
                )
                # --- MODIFICATION: Prepend description to the transcript ---
                return f"Video Description:\n{description}\n\nTranscript:\n{full_transcript}"
            elif description:
                print(
                    "      -> No transcript found, but description is available. Returning description.",
                    flush=True,
                )
                return f"Video Description:\n{description}\n\nTranscript: No transcript available."
            else:
                print(
                    "      -> No transcript or description available.",
                    flush=True,
                )
                return ""

        except Exception as ydl_error:
            print(
                f"      -> yt-dlp fallback also failed: {ydl_error}",
                file=sys.stderr,
                flush=True,
            )
            return ""


def get_enriched_data_from_gemini(
    title: str, description: str, transcript: str, model_name: str
) -> dict:
    """
    Calls the Gemini API to get a structured JSON object containing summary, tags, and category.
    Handles malformed responses robustly.
    """
    print(f"    - Sub-step 3.2: Calling Gemini API for structured data...", flush=True)
    context = transcript if transcript else description
    if not context:
        return {
            "summary": "Not enough content.",
            "tags": "",
            "category": "Uncategorized",
        }

    prompt = f"""
You are an expert YouTube video metadata enrichment agent and cataloger. Analyze the provided video title and content and return output for a cataloging system. Output a JSON object with:
- summary: A concise one-sentence summary.
- tags: A list of up to 7 specific, informative tags.
- category: The most relevant YouTube category.

Video Title: {title}
Video Content:
{context}
"""

    try:
        response = client.models.generate_content(
            model=model_name,
            config=gen_config,
            contents=prompt,
        )
        print("Output Response", response.text)

        # Try to extract JSON from code blocks, markdown, or plain text
        text = response.text.strip()
        # Remove markdown code block markers if present
        if text.startswith("```") and text.endswith("```"):
            text = text.strip("`").strip()
            # Remove possible language hint (e.g., ```json)
            text = re.sub(r"^json\n", "", text, flags=re.IGNORECASE)

        # Try to find the first {...} JSON object in the text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            json_str = match.group(0)
        else:
            json_str = text  # fallback: try to parse the whole text

        try:
            response_data = json.loads(json_str)
        except Exception as e:
            print(f"      -> ERROR: Failed to parse JSON: {e}", flush=True)
            return {"summary": "Error", "tags": "Error", "category": "Error"}

        summary = response_data.get("summary", "No summary provided.")
        tags = response_data.get("tags", [])
        # Accept tags as either a list or comma-separated string
        if isinstance(tags, list):
            tags_str = ", ".join(str(t).strip() for t in tags)
        elif isinstance(tags, str):
            tags_str = tags
        else:
            tags_str = ""
        category = response_data.get("category", "Uncategorized")
        print(
            "      -> Successfully received and parsed structured data from Gemini.",
            flush=True,
        )
        return {"summary": summary, "tags": tags_str, "category": category}

    except Exception as e:
        print(f"      -> ERROR calling Gemini API: {e}", flush=True)
        return {"summary": "Error", "tags": "Error", "category": "Error"}


def process_video(video_info: dict, ai_model: str) -> dict:
    video_id = video_info.get("id", "")
    title = video_info.get("title", "No Title")
    url = video_info.get("webpage_url", "")
    description = video_info.get("description", "")

    thumbnail_url = video_info.get("thumbnail")
    if not thumbnail_url:
        thumbnails = video_info.get("thumbnails", [])
        if thumbnails:
            hq_thumb = next(
                (t["url"] for t in thumbnails if "hqdefault" in t.get("id", "")), None
            )
            maxres_thumb = next(
                (t["url"] for t in thumbnails if "maxresdefault" in t.get("id", "")),
                None,
            )
            thumbnail_url = maxres_thumb or hq_thumb or thumbnails[-1]["url"]
        else:
            thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    print(f"PROCESSING_URL::{url}", flush=True)
    print(f"\nSTEP 3: Processing Video: '{title}'", flush=True)

    transcript = get_video_transcript(video_id, video_info)
    enriched_data = get_enriched_data_from_gemini(
        title, description, transcript, ai_model
    )

    return {
        "name": title,
        "url": url,
        "type": "video",
        "summary": enriched_data["summary"],
        "tags": enriched_data["tags"],
        "category": enriched_data["category"],
        "thumbnail_url": thumbnail_url,
        "uploader": video_info.get("uploader", "Unknown Uploader"),
        "duration": video_info.get("duration", 0),
    }


def process_webpage(url: str, ai_model: str) -> dict:
    print(f"PROCESSING_URL::{url}", flush=True)
    print(f"\nSTEP 3: Processing Webpage: '{url}'", flush=True)
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        title = soup.title.string if soup.title else "No Title Found"

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        text = soup.get_text(separator=" ", strip=True)

        enriched_data = get_enriched_data_from_gemini(
            title, description="This is webpage", transcript=text, model_name=ai_model
        )

        return {
            "name": title,
            "url": url,
            "type": "webpage",
            "summary": enriched_data["summary"],
            "tags": enriched_data["tags"],
            "category": enriched_data["category"],
            "thumbnail_url": None,
            "uploader": None,
            "duration": None,
        }
    except Exception as e:
        print(f"ERROR processing webpage {url}: {e}", file=sys.stderr, flush=True)
        return None


# --- Main Execution ---
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--model", default="gemini-2.5-flash-lite-preview-06-17")
    args = parser.parse_args()

    ai_model = args.model
    print(
        f"--- YouTube Data Enrichment Script Started (Using Model: {ai_model}) ---",
        flush=True,
    )

    db_conn = setup_database()
    print(f"\nSTEP 2: Fetching metadata for URL: {args.url}", flush=True)
    is_youtube_url = "youtube.com" in args.url or "youtu.be" in args.url

    if is_youtube_url:
        is_playlist = "playlist?list=" in args.url and "watch?v=" not in args.url
        if is_playlist:
            ydl_opts = {"quiet": True, "extract_flat": True}
            print(" -> Playlist URL detected. Fetching playlist entries...", flush=True)
            try:
                with YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(args.url, download=False)
            except Exception as e:
                print(
                    f"FATAL: yt-dlp failed to extract playlist info: {e}",
                    file=sys.stderr,
                    flush=True,
                )
                db_conn.close()
                sys.exit(1)

            playlist_title = info_dict.get("title", "Untitled Playlist")
            playlist_url = info_dict.get("webpage_url")
            playlist_uploader = info_dict.get("uploader")
            video_count = info_dict.get("playlist_count")

            cursor = db_conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO playlists (title, url, uploader, video_count, processed_at) VALUES (?, ?, ?, ?, ?)",
                (
                    playlist_title,
                    playlist_url,
                    playlist_uploader,
                    video_count,
                    datetime.now(),
                ),
            )
            db_conn.commit()
            playlist_id = cursor.lastrowid
            print(
                f" -> Created/Updated playlist entry with ID: {playlist_id}", flush=True
            )

            video_entries = info_dict.get("entries", [])
            for i, entry in enumerate(video_entries):
                if i > 0:
                    time.sleep(random.uniform(2.0, 5.0))
                print(
                    f"\n--- Processing video {i+1} of {len(video_entries)} ---",
                    flush=True,
                )
                try:
                    video_url = entry.get("url")
                    if not video_url:
                        continue
                    with YoutubeDL({"quiet": True, "noplaylist": True}) as ydl_video:
                        video_details = ydl_video.extract_info(
                            video_url, download=False
                        )
                    enriched_data = process_video(video_details, ai_model)
                    save_video_to_db(db_conn, enriched_data, playlist_id)
                except Exception as e:
                    print(
                        f"ERROR processing video {entry.get('url')}: {e}",
                        file=sys.stderr,
                        flush=True,
                    )
        else:
            ydl_opts = {"quiet": True, "noplaylist": True}
            print(f" -> Single video URL detected. Fetching details...", flush=True)
            try:
                with YoutubeDL(ydl_opts) as ydl_video:
                    video_details = ydl_video.extract_info(args.url, download=False)

                canonical_url = video_details.get("webpage_url")
                cursor = db_conn.cursor()
                cursor.execute(
                    "SELECT playlist_id FROM videos WHERE url = ?", (canonical_url,)
                )
                existing_record = cursor.fetchone()
                existing_playlist_id = existing_record[0] if existing_record else None

                if existing_playlist_id:
                    print(
                        f" -> Video already exists in playlist ID: {existing_playlist_id}. Updating in place.",
                        flush=True,
                    )

                enriched_data = process_video(video_details, ai_model)
                save_video_to_db(
                    db_conn, enriched_data, playlist_id=existing_playlist_id
                )
            except Exception as e:
                print(
                    f"ERROR processing single video {args.url}: {e}",
                    file=sys.stderr,
                    flush=True,
                )
    else:
        # Process as a generic webpage
        enriched_data = process_webpage(args.url, ai_model)
        if enriched_data:
            save_video_to_db(db_conn, enriched_data)

    db_conn.close()
    print("\n--- Enrichment Script Finished ---", flush=True)


if __name__ == "__main__":
    main()
