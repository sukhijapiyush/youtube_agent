# wsgi.py
# This file is the entry point for the WSGI server (like Gunicorn).
# It imports the main Flask application instance from our app.py file.

from app import app

if __name__ == "__main__":
    # This allows running the app directly with 'python wsgi.py' for development,
    # but it's primarily for the Gunicorn server to find the 'app' object.
    app.run()
