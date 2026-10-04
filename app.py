from flask import (
    Flask,
    render_template,
    request,
    redirect,
    send_from_directory,
    abort
)

from werkzeug.utils import secure_filename

from google import genai
from google.genai import types

from dotenv import load_dotenv

import os
import uuid
import sqlite3
import json
import time


# =====================================================
# ENVIRONMENT
# =====================================================

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("WARNING: GEMINI_API_KEY not found")


# =====================================================
# FLASK
# =====================================================

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Maximum upload size = 8 MB
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


# =====================================================
# GEMINI
# =====================================================

client = genai.Client(
    api_key=api_key
) if api_key else None


# =====================================================
# DATABASE
# =====================================================

def create_database():

    connection = sqlite3.connect(
        "civiclens.db"
    )

    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS complaints (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            complaint_id TEXT UNIQUE NOT NULL,

            location TEXT NOT NULL,

            description TEXT,

            issue TEXT,

            priority TEXT,

            department TEXT,

            reason TEXT,

            image_filename TEXT,

            status TEXT DEFAULT 'Pending'

        )
    """)

    connection.commit()

    connection.close()


create_database()


# =====================================================
# IMAGE VALIDATION
# =====================================================

def allowed_file(filename):

    return (
        "." in filename
        and
        filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# =====================================================
# AI ANALYSIS FUNCTION
# =====================================================

def analyze_with_ai(
    image_bytes,
    mime_type
):

    # Default safe result

    fallback = {
        "issue": "Manual Review Required",
        "priority": "Pending",
        "department": "Pending Assignment",
        "reason": (
            "AI analysis was temporarily unavailable. "
            "The submitted evidence requires human review."
        )
    }


    if client is None:

        print(
            "AI unavailable: API key missing"
        )

        return fallback, False


    prompt = """
You are the AI analysis component of CivicLens AI.

Analyze the uploaded civic issue image.

Classify it into exactly ONE category:

- Pothole
- Garbage
- Broken Streetlight
- Water Leakage
- Other

Return ONLY valid JSON.

Use exactly this structure:

{
    "issue": "Pothole",
    "priority": "High",
    "department": "Road Maintenance",
    "reason": "Short reason based only on visible evidence."
}

Priority must be exactly one of:

Low
Medium
High

Priority is only an AI-assisted suggestion.

Choose an appropriate civic department.

Do not return Markdown.

Return JSON only.
"""


    # Try twice if API has a temporary failure

    for attempt in range(2):

        try:

            response = client.models.generate_content(

                model="gemini-3.8-flash",

                contents=[

                    prompt,

                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type=mime_type
                    )

                ]

            )


            ai_text = response.text.strip()

            data = json.loads(
                ai_text
            )


            issue = data.get(
                "issue",
                "Other"
            )

            priority = data.get(
                "priority",
                "Medium"
            )

            department = data.get(
                "department",
                "General Civic Services"
            )

            reason = data.get(
                "reason",
                "No reason provided."
            )


            # Validate priority

            if priority not in [
                "Low",
                "Medium",
                "High"
            ]:

                priority = "Medium"


            result = {
                "issue": issue,
                "priority": priority,
                "department": department,
                "reason": reason
            }


            print(
                "AI analysis successful"
            )

            return result, True


        except Exception as error:

            print(
                "AI attempt",
                attempt + 1,
                "failed:",
                error
            )


            # Small retry delay
            if attempt == 0:

                time.sleep(2)


    print(
        "AI fallback activated"
    )

    return fallback, False


# =====================================================
# HOME
# =====================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =====================================================
# REPORT
# =====================================================

@app.route("/report")
def report():

    return render_template(
        "report.html"
    )


# =====================================================
# SERVE UPLOADS
# =====================================================

@app.route(
    "/uploads/<filename>"
)
def uploaded_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


# =====================================================
# ANALYZE
# =====================================================

@app.route(
    "/analyze",
    methods=["POST"]
)
def analyze():

    # -------------------------------------------------
    # IMAGE CHECK
    # -------------------------------------------------

    if "image" not in request.files:

        return (
            "No image uploaded.",
            400
        )


    image = request.files["image"]


    if image.filename == "":

        return (
            "Please select an image.",
            400
        )


    if not allowed_file(
        image.filename
    ):

        return (
            "Only PNG, JPG, JPEG and WEBP images are allowed.",
            400
        )


    # -------------------------------------------------
    # FORM DATA
    # -------------------------------------------------

    location = request.form.get(
        "location",
        ""
    ).strip()


    description = request.form.get(
        "description",
        ""
    ).strip()


    if not location:

        return (
            "Location is required.",
            400
        )


    # -------------------------------------------------
    # SAVE IMAGE
    # -------------------------------------------------

    original_filename = secure_filename(
        image.filename
    )


    unique_filename = (
        str(uuid.uuid4())[:8]
        + "_"
        + original_filename
    )


    image_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        unique_filename
    )


    image.save(
        image_path
    )


    # -------------------------------------------------
    # READ IMAGE
    # -------------------------------------------------

    with open(
        image_path,
        "rb"
    ) as file:

        image_bytes = file.read()


    # -------------------------------------------------
    # MIME TYPE
    # -------------------------------------------------

    extension = os.path.splitext(
        unique_filename
    )[1].lower()


    if extension == ".png":

        mime_type = "image/png"

    elif extension == ".webp":

        mime_type = "image/webp"

    else:

        mime_type = "image/jpeg"


    # -------------------------------------------------
    # AI
    # -------------------------------------------------

    ai_data, ai_success = analyze_with_ai(

        image_bytes,

        mime_type

    )


    issue = ai_data[
        "issue"
    ]

    priority = ai_data[
        "priority"
    ]

    department = ai_data[
        "department"
    ]

    reason = ai_data[
        "reason"
    ]


    if ai_success:

        ai_result = f"""
Issue: {issue}
Suggested Priority: {priority}
Department: {department}
Reason: {reason}
"""

    else:

        ai_result = f"""
AI Status: Manual Review Required
Issue: {issue}
Priority: {priority}
Department: {department}
Reason: {reason}
"""


    # =================================================
    # DUPLICATE CHECK
    # =================================================

    duplicate_found = False

    duplicate_id = None


    # Only perform issue-based duplicate matching
    # when AI actually classified the issue.

    if ai_success:

        connection = sqlite3.connect(
            "civiclens.db"
        )

        connection.row_factory = sqlite3.Row

        cursor = connection.cursor()


        cursor.execute("""
            SELECT complaint_id

            FROM complaints

            WHERE LOWER(TRIM(location))
                  = LOWER(TRIM(?))

            AND LOWER(TRIM(issue))
                = LOWER(TRIM(?))

            AND status != 'Resolved'

            ORDER BY id DESC

            LIMIT 1
        """, (

            location,

            issue

        ))


        duplicate = cursor.fetchone()

        connection.close()


        if duplicate:

            duplicate_found = True

            duplicate_id = (
                duplicate["complaint_id"]
            )


    # =================================================
    # COMPLAINT ID
    # =================================================

    complaint_id = (
        "CL-"
        + str(uuid.uuid4())[:6].upper()
    )


    # =================================================
    # DATABASE INSERT
    # =================================================

    connection = sqlite3.connect(
        "civiclens.db"
    )

    cursor = connection.cursor()


    cursor.execute("""
        INSERT INTO complaints (

            complaint_id,

            location,

            description,

            issue,

            priority,

            department,

            reason,

            image_filename,

            status

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (

        complaint_id,

        location,

        description,

        issue,

        priority,

        department,

        reason,

        unique_filename,

        "Pending"

    ))


    connection.commit()

    connection.close()


    print(
        "Complaint saved:",
        complaint_id
    )


    # =================================================
    # RESULT
    # =================================================

    return render_template(

        "result.html",

        complaint_id=complaint_id,

        location=location,

        description=description,

        ai_result=ai_result,

        duplicate_found=duplicate_found,

        duplicate_id=duplicate_id

    )


# =====================================================
# TRACK
# =====================================================

@app.route(
    "/track",
    methods=["GET", "POST"]
)
def track():

    complaint = None

    searched = False


    if request.method == "POST":

        searched = True


        complaint_id = request.form.get(
            "complaint_id",
            ""
        ).strip().upper()


        connection = sqlite3.connect(
            "civiclens.db"
        )

        connection.row_factory = sqlite3.Row

        cursor = connection.cursor()


        cursor.execute("""
            SELECT *

            FROM complaints

            WHERE UPPER(complaint_id) = ?
        """, (

            complaint_id,

        ))


        complaint = cursor.fetchone()

        connection.close()


    return render_template(

        "track.html",

        complaint=complaint,

        searched=searched

    )


# =====================================================
# ADMIN
# =====================================================

@app.route("/admin")
def admin():

    connection = sqlite3.connect(
        "civiclens.db"
    )

    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()


    cursor.execute("""
        SELECT *

        FROM complaints

        ORDER BY id DESC
    """)

    complaints = cursor.fetchall()


    cursor.execute("""
        SELECT COUNT(*)
        FROM complaints
    """)

    total = cursor.fetchone()[0]


    cursor.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Pending'
    """)

    pending = cursor.fetchone()[0]


    cursor.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'In Progress'
    """)

    in_progress = cursor.fetchone()[0]


    cursor.execute("""
        SELECT COUNT(*)
        FROM complaints
        WHERE status = 'Resolved'
    """)

    resolved = cursor.fetchone()[0]


    cursor.execute("""
        SELECT COUNT(*)

        FROM complaints

        WHERE LOWER(priority) = 'high'

        AND status != 'Resolved'
    """)

    high_priority = cursor.fetchone()[0]


    connection.close()


    return render_template(

        "admin.html",

        complaints=complaints,

        total=total,

        pending=pending,

        in_progress=in_progress,

        resolved=resolved,

        high_priority=high_priority

    )


# =====================================================
# COMPLAINT DETAILS
# =====================================================

@app.route(
    "/complaint/<complaint_id>"
)
def complaint_detail(
    complaint_id
):

    connection = sqlite3.connect(
        "civiclens.db"
    )

    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()


    cursor.execute("""
        SELECT *

        FROM complaints

        WHERE complaint_id = ?
    """, (

        complaint_id,

    ))


    complaint = cursor.fetchone()

    connection.close()


    if complaint is None:

        abort(404)


    return render_template(

        "complaint_detail.html",

        complaint=complaint

    )


# =====================================================
# UPDATE STATUS
# =====================================================

@app.route(
    "/update-status/<complaint_id>",
    methods=["POST"]
)
def update_status(
    complaint_id
):

    new_status = request.form.get(
        "status",
        ""
    )


    allowed_statuses = [

        "Pending",

        "In Progress",

        "Resolved"

    ]


    if new_status not in allowed_statuses:

        return (
            "Invalid status",
            400
        )


    connection = sqlite3.connect(
        "civiclens.db"
    )

    cursor = connection.cursor()


    cursor.execute("""
        UPDATE complaints

        SET status = ?

        WHERE complaint_id = ?
    """, (

        new_status,

        complaint_id

    ))


    connection.commit()

    connection.close()


    return redirect(
        request.referrer
        or
        "/admin"
    )


# =====================================================
# FILE TOO LARGE
# =====================================================

@app.errorhandler(413)
def too_large(error):

    return (
        "Image is too large. Please upload an image smaller than 8 MB.",
        413
    )


# =====================================================
# START
# =====================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )