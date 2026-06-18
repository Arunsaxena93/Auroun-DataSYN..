from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
import os
import pandas as pd
import matplotlib.pyplot as plt
import uuid
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = "auroun_secret_key"

UPLOAD_FOLDER = "uploads"
STATIC_FOLDER = "static"
REPORT_FOLDER = "reports"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ---------------- HOME ----------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/services")
def services():
    return render_template("services.html")


@app.route("/careers")
def careers():
    return render_template("careers.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/chat")
def chat_page():
    return render_template("chat.html")


# ---------------- LOAD DATA ----------------
def load_data():
    if "file_path" not in session:
        return None
    try:
        return pd.read_csv(session["file_path"])
    except:
        return None


# ---------------- CLEAN DATA ----------------
def clean_df(df):
    return df.apply(lambda x: pd.to_numeric(x, errors="ignore"))


# ---------------- NUMERIC COLUMNS ----------------
def get_numeric_columns(df):
    numeric_cols = []

    for col in df.columns:
        converted = pd.to_numeric(df[col], errors="coerce")
        if converted.notna().sum() > 0:
            numeric_cols.append(col)

    return numeric_cols


# ---------------- INSIGHTS ENGINE ----------------
def generate_insights(df):

    numeric_cols = get_numeric_columns(df)

    if not numeric_cols:
        return "No numeric columns available."

    means = {
        col: pd.to_numeric(df[col], errors="coerce").mean()
        for col in numeric_cols
    }

    best_col = max(means, key=means.get)
    worst_col = min(means, key=means.get)

    return "\n".join([
        f"Total Rows: {len(df)}",
        f"Total Columns: {len(df.columns)}",
        f"Numeric Columns: {len(numeric_cols)}",
        f"Missing Values: {int(df.isnull().sum().sum())}",
        f"Highest Avg Column: {best_col}",
        f"Lowest Avg Column: {worst_col}"
    ])


# ---------------- CHART ----------------
def generate_chart(df, col):

    path = f"static/chart_{uuid.uuid4().hex}.png"

    series = pd.to_numeric(df[col], errors="coerce").dropna()

    plt.figure(figsize=(6, 4))
    series.plot(kind="line")
    plt.title(col)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()

    return path


# ---------------- UPLOAD ----------------
@app.route("/upload", methods=["GET", "POST"])
def upload():

    if request.method == "GET":
        return render_template("upload.html")

    file = request.files.get("file")

    if not file or file.filename == "":
        flash("No file selected")
        return redirect(url_for("upload"))

    file_path = os.path.join(UPLOAD_FOLDER, uuid.uuid4().hex + "_" + file.filename)
    file.save(file_path)

    try:
        if file.filename.endswith(".csv"):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
            df.to_csv(file_path, index=False)
    except Exception as e:
        flash(f"File error: {e}")
        return redirect(url_for("upload"))

    df = df.dropna()
    df = clean_df(df)

    session["file_path"] = file_path
    session["insights"] = generate_insights(df)

    return redirect(url_for("dashboard"))


# ---------------- HUB ----------------
@app.route("/hub")
def hub():

    df = load_data()

    if df is None:
        return redirect(url_for("upload"))

    numeric_cols = get_numeric_columns(df)

    if not numeric_cols:
        return "No numeric columns found"

    selected_col = numeric_cols[0]
    series = pd.to_numeric(df[selected_col], errors="coerce")

    stats = {
        "mean": float(series.mean()),
        "min": float(series.min()),
        "max": float(series.max())
    }

    return render_template(
        "hub.html",
        stats=stats,
        selected_col=selected_col,
        insights=session.get("insights", "")
    )


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():

    df = load_data()

    if df is None:
        return redirect(url_for("upload"))

    numeric_cols = get_numeric_columns(df)

    if not numeric_cols:
        return "No numeric columns found"

    selected_col = request.args.get("column")

    if selected_col not in numeric_cols:
        selected_col = numeric_cols[0]

    series = pd.to_numeric(df[selected_col], errors="coerce").dropna()

    stats = {
        "mean": round(float(series.mean()), 2),
        "median": round(float(series.median()), 2),
        "min": round(float(series.min()), 2),
        "max": round(float(series.max()), 2)
    }

    return render_template(
        "result.html",
        columns=numeric_cols,
        selected_col=selected_col,
        selected_data=series.tolist(),
        stats=stats,
        insights=session.get("insights", "")
    )


# ---------------- ANALYTICS ----------------
@app.route("/analytics")
def analytics():

    df = load_data()

    if df is None:
        return redirect(url_for("upload"))

    numeric_cols = get_numeric_columns(df)

    return render_template(
        "analytics.html",
        summary=df[numeric_cols].describe().to_html(),
        rows=len(df),
        cols=len(df.columns),
        missing=int(df.isnull().sum().sum())
    )


# ---------------- AI COPILOT ----------------
@app.route("/ask", methods=["POST"])
def ask():

    df = load_data()

    if df is None:
        return jsonify({"answer": "Please upload a file first."})

    data = request.get_json()
    question = data.get("question", "").lower()

    numeric_cols = get_numeric_columns(df)

    if not numeric_cols:
        return jsonify({"answer": "No numeric columns found in dataset."})

    col = numeric_cols[0]
    series = pd.to_numeric(df[col], errors="coerce")

    if "max" in question:
        return jsonify({"answer": f"Maximum value: {series.max():.2f}"})

    elif "min" in question:
        return jsonify({"answer": f"Minimum value: {series.min():.2f}"})

    elif "mean" in question or "average" in question:
        return jsonify({"answer": f"Average value: {series.mean():.2f}"})

    elif "summary" in question:
        return jsonify({"answer": generate_insights(df)})

    elif "chart" in question or "trend" in question:
        path = generate_chart(df, col)
        return jsonify({"answer": "Chart generated", "chart": "/" + path})

    elif "dashboard" in question:
        path = generate_chart(df, col)
        return jsonify({"answer": "Dashboard generated", "chart": "/" + path})

    else:
        return jsonify({"answer": f"AI analysis done. Mean = {series.mean():.2f}"})


# ---------------- REPORT ----------------
@app.route("/download-report")
def download_report():

    df = load_data()

    if df is None:
        return redirect(url_for("upload"))

    file_path = f"{REPORT_FOLDER}/report_{uuid.uuid4().hex}.pdf"

    c = canvas.Canvas(file_path, pagesize=letter)

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, "Auroun DataSYN Report - Arun Saxena")

    c.setFont("Helvetica", 11)
    c.drawString(50, 720, f"Rows: {len(df)}")
    c.drawString(50, 700, f"Columns: {len(df.columns)}")
    c.drawString(50, 680, f"Missing Values: {int(df.isnull().sum().sum())}")

    insights = session.get("insights", "").split("\n")

    y = 650
    for line in insights[:10]:
        c.drawString(50, y, line)
        y -= 20

    c.save()

    return send_file(file_path, as_attachment=True)


# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("🚀 AURoun DataSYN FINAL STABLE SYSTEM RUNNING")
    app.run(host="0.0.0.0", port=port)
