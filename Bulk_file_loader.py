import os
import subprocess

if os.path.exists("to_upload"):
    print("Processing files in 'to_upload' directory...")
else:
    print("'to_upload' directory does not exist. Creating it now...")
    os.makedirs("to_upload")

if len(os.listdir("to_upload")) == 0:
    print("No files to process in 'to_upload' directory.")
# Call enricher.py for each file in to_upload folder
to_upload_folder = os.path.join(os.path.dirname(__file__), "to_upload")

for filename in os.listdir(to_upload_folder):
    file_path = os.path.join(to_upload_folder, filename)
    if os.path.isfile(file_path):
        print(f"Processing: {file_path}")
        subprocess.run(
            ["python", "enricher.py", "--file", file_path],
            cwd=os.path.dirname(__file__),
            check=True,
        )
