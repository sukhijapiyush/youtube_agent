# app.py
import subprocess
import sys
from flask import Flask, jsonify, request, render_template, Response
import sqlite3
from threading import Thread
import queue
import os
import config
import time

log_queue = queue.Queue()
LOCK_FILE = "enrichment.lock"

app = Flask(__name__)


# --- Database & Batch File Functions ---
def get_db_connection():
    conn = sqlite3.connect(config.DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def setup_database():
    print("Checking and setting up database...")
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, url TEXT NOT NULL UNIQUE,
            uploader TEXT, video_count INTEGER, processed_at TIMESTAMP NOT NULL
        )"""
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, url TEXT NOT NULL UNIQUE,
            type TEXT, summary TEXT, tags TEXT, category TEXT, thumbnail_url TEXT, 
            uploader TEXT, duration INTEGER, processed_at TIMESTAMP NOT NULL,
            playlist_id INTEGER, FOREIGN KEY (playlist_id) REFERENCES playlists (id)
        )"""
    )
    for col in ["thumbnail_url", "uploader", "duration", "category", "playlist_id"]:
        try:
            conn.execute(f"ALTER TABLE videos ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()
    print("Database setup complete.")


def load_batch_links():
    batch_links = []
    try:
        if os.path.exists("batch_links.txt"):
            with open("batch_links.txt", "r") as f:
                batch_links = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"Error loading batch_links.txt: {e}")
    return batch_links


# --- Backend Enrichment Task ---
def run_enrichment_process(urls):
    global log_queue
    with open(LOCK_FILE, "w") as f:
        f.write("running")

    log_queue.put(f"Starting batch process for {len(urls)} item(s)...")
    try:
        process_env = os.environ.copy()
        process_env["PYTHONIOENCODING"] = "utf-8"

        for i, url in enumerate(urls):
            log_queue.put(f"\n--- Processing item {i+1} of {len(urls)}: {url} ---")
            process = subprocess.Popen(
                [sys.executable, config.ENRICHER_SCRIPT_PATH, url],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                encoding="utf-8",
                env=process_env,
            )
            for line in iter(process.stdout.readline, ""):
                log_queue.put(line.strip())
            process.stdout.close()
            process.wait()
            time.sleep(60)
    except Exception as e:
        log_queue.put(f"FATAL: A subprocess failed: {e}")
    finally:
        log_queue.put("__STREAM_END__")
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)


# --- API Endpoints ---
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/stream-logs")
def stream_logs():
    def generate():
        while True:
            try:
                message = log_queue.get(timeout=60)
                yield f"data: {message}\n\n"
                if message == "__STREAM_END__":
                    break
            except queue.Empty:
                break

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify({"is_running": os.path.exists(LOCK_FILE)})


@app.route("/api/library", methods=["GET"])
def get_library():
    conn = get_db_connection()
    playlists_raw = conn.execute(
        "SELECT * FROM playlists ORDER BY processed_at DESC"
    ).fetchall()
    playlists = []
    for p_raw in playlists_raw:
        playlist = dict(p_raw)
        playlist["type"] = "playlist"
        videos_raw = conn.execute(
            "SELECT * FROM videos WHERE playlist_id = ? ORDER BY id", (playlist["id"],)
        ).fetchall()
        playlist["videos"] = [dict(v_raw) for v_raw in videos_raw]
        playlists.append(playlist)
    standalone_videos = conn.execute(
        "SELECT * FROM videos WHERE playlist_id IS NULL ORDER BY processed_at DESC"
    ).fetchall()
    conn.close()
    library_items = playlists + [dict(v) for v in standalone_videos]
    library_items.sort(key=lambda x: x["processed_at"], reverse=True)
    return jsonify(library_items)


@app.route("/api/batch/links", methods=["GET"])
def get_batch_links():
    batch_links = load_batch_links()
    conn = get_db_connection()
    cursor = conn.cursor()
    processed_urls = set()
    for row in cursor.execute("SELECT url FROM videos").fetchall():
        processed_urls.add(row["url"].split("&")[0])
    for row in cursor.execute("SELECT url FROM playlists").fetchall():
        processed_urls.add(row["url"].split("&")[0])
    conn.close()
    links_with_status = [
        {"url": url, "processed": url.split("&")[0] in processed_urls}
        for url in batch_links
    ]
    return jsonify(links_with_status)


@app.route("/api/batch/add_links", methods=["POST"])
def add_batch_links():
    """Appends new links to the batch_links.txt file."""
    data = request.get_json()
    new_links_str = data.get("links")
    if not new_links_str:
        return jsonify({"error": "No links provided"}), 400
    try:
        with open("batch_links.txt", "a") as f:
            if f.tell() > 0:
                f.write("\n")
            f.write(new_links_str.strip())
        print(f"Appended new links to batch_links.txt")
        return jsonify({"message": "Links added successfully to batch file."}), 200
    except Exception as e:
        print(f"Error appending to batch_links.txt: {e}")
        return jsonify({"error": "Could not write to batch file."}), 500


@app.route("/api/batch/start", methods=["POST"])
def start_batch():
    if os.path.exists(LOCK_FILE):
        return jsonify({"error": "A process is already running."}), 409
    while not log_queue.empty():
        try:
            log_queue.get_nowait()
        except queue.Empty:
            continue
    urls_to_process = request.get_json().get("urls")
    if not urls_to_process:
        return jsonify({"error": "No URLs provided"}), 400
    Thread(target=run_enrichment_process, args=(urls_to_process,)).start()
    return jsonify({"message": "Batch process started."}), 202


@app.route("/api/videos/<int:video_id>", methods=["PUT", "DELETE"])
def handle_video(video_id):
    conn = get_db_connection()
    if request.method == "PUT":
        data = request.get_json()
        conn.execute(
            "UPDATE videos SET name = ?, uploader = ?, category = ?, summary = ?, tags = ? WHERE id = ?",
            (
                data["name"],
                data["uploader"],
                data["category"],
                data["summary"],
                data["tags"],
                video_id,
            ),
        )
        conn.commit()
        message = "Video updated"
    elif request.method == "DELETE":
        conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        conn.commit()
        message = "Video deleted"
    conn.close()
    return jsonify({"message": message}), 200


@app.route("/api/playlists/<int:playlist_id>", methods=["DELETE"])
def delete_playlist(playlist_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM videos WHERE playlist_id = ?", (playlist_id,))
    conn.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Playlist and all its videos deleted"}), 200


# --- Main Execution ---
if __name__ == "__main__":
    setup_database()
    app.run(host="0.0.0.0", port=5001, debug=True)
