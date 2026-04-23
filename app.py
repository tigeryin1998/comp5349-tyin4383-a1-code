import os
import time
import uuid
from datetime import datetime

import boto3
import psycopg
from flask import Flask, render_template, request, redirect, url_for, flash
import google.generativeai as genai

# =========================================================
# Configuration
# Update with proper values before running the app
# =========================================================

AWS_REGION = "us-east-1"
S3_BUCKET_NAME = "comp5349-tyin4383-a1-docs-862231074268-ap-southeast-2-an"

DB_HOST = "comp5349-tyin4383-a1-db.chi8eme8yqe0.ap-southeast-2.rds.amazonaws.com"
DB_PORT = 5432
DB_NAME = "comp5349-tyin4383-a1-db"
DB_USER = "postgres"
DB_PASSWORD = "aFX9mCMh3GDq3LpIgtwD"

GOOGLE_API_KEY = "AIzaSyDxEMFk3BDPRHCBvxeOssnnyvxBf1qBAiQ"

ALLOWED_EXTENSIONS = {"pdf"}
MAX_FILE_SIZE_MB = 5

# A current fast Gemini model suitable for summarisation
MODEL_NAME = "gemini-2.5-flash"

# =========================================================
# Flask app
# =========================================================

app = Flask(__name__)
app.secret_key = "replace-this-with-a-better-secret"

# Optional upload size limit for Flask
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE_MB * 1024 * 1024

# =========================================================
# Clients
# =========================================================

s3_client = boto3.client("s3", region_name=AWS_REGION)

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(MODEL_NAME)

# =========================================================
# Helper functions
# =========================================================

def get_db_connection():
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def upload_file_to_s3(file_obj, s3_key):
    s3_client.upload_fileobj(file_obj, S3_BUCKET_NAME, s3_key)


def upload_pdf_to_gemini(local_path, mime_type="application/pdf"):
    """
    Uploads the PDF to Gemini Files API and waits until it becomes ready.
    """
    uploaded_file = genai.upload_file(path=local_path, mime_type=mime_type)

    # Wait until file processing finishes
    while uploaded_file.state.name == "PROCESSING":
        time.sleep(2)
        uploaded_file = genai.get_file(uploaded_file.name)

    if uploaded_file.state.name != "ACTIVE":
        raise RuntimeError(f"Gemini file upload failed. File state: {uploaded_file.state.name}")

    return uploaded_file


def summarise_pdf_with_gemini(gemini_file, original_filename):
    """
    Sends the uploaded PDF file to Gemini and requests a short summary.
    """
    prompt = f"""
You are helping summarise a PDF document uploaded to a student web application.

Please provide:
1. A concise summary in 3-5 sentences.
2. Three bullet-point key takeaways.

The original filename is: {original_filename}
"""

    response = model.generate_content([prompt, gemini_file])
    return response.text.strip()


def save_document_record(filename, s3_key, summary, status="completed"):
    conn = get_db_connection()
    cur = conn.cursor()

    insert_sql = """
        INSERT INTO documents (filename, s3_key, summary, status, uploaded_at)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """

    cur.execute(insert_sql, (filename, s3_key, summary, status, datetime.utcnow()))
    document_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    return document_id


def get_all_documents():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, filename, s3_key, summary, status, uploaded_at
        FROM documents
        ORDER BY uploaded_at DESC;
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_document_by_id(document_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, filename, s3_key, summary, status, uploaded_at
        FROM documents
        WHERE id = %s;
    """, (document_id,))

    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


# =========================================================
# Routes
# =========================================================

@app.route("/")
def index():
    return render_template("index.html", max_file_size_mb=MAX_FILE_SIZE_MB)


@app.route("/upload", methods=["POST"])
def upload_document():
    if "document" not in request.files:
        flash("No file part in the request.")
        return redirect(url_for("index"))

    file = request.files["document"]

    if file.filename == "":
        flash("No file selected.")
        return redirect(url_for("index"))

    if not allowed_file(file.filename):
        flash("Only PDF files are supported.")
        return redirect(url_for("index"))

    original_filename = file.filename
    unique_id = str(uuid.uuid4())
    s3_key = f"documents/{unique_id}_{original_filename}"

    # Save to a temporary local path first
    temp_dir = "/tmp"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"{unique_id}.pdf")

    try:
        # Save local copy for Gemini upload
        file.save(temp_path)

        # Upload original PDF to S3
        with open(temp_path, "rb") as pdf_for_s3:
            upload_file_to_s3(pdf_for_s3, s3_key)

        # Upload PDF to Gemini Files API
        gemini_file = upload_pdf_to_gemini(temp_path)

        # Generate summary
        summary = summarise_pdf_with_gemini(gemini_file, original_filename)

        # Save metadata + summary to RDS
        document_id = save_document_record(original_filename, s3_key, summary)

        return redirect(url_for("view_result", document_id=document_id))

    except Exception as e:
        flash(f"Error processing document: {str(e)}")
        return redirect(url_for("index"))

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.route("/result/<int:document_id>")
def view_result(document_id):
    document = get_document_by_id(document_id)

    if document is None:
        flash("Document not found.")
        return redirect(url_for("index"))

    return render_template("result.html", document=document)


@app.route("/history")
def history():
    documents = get_all_documents()
    return render_template("history.html", documents=documents)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
