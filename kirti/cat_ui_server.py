
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import boto3, os, cv2, io
from datetime import datetime
import pandas as pd

app = Flask(__name__)
CORS(app)


# AWS Rekognition Client
rekognition = boto3.client('rekognition',  region_name='ap-south-1')

# Configuration
image_dir = 'images'
excel_file = 'attendance.xlsx'
valid_extensions = ('.jpeg', '.jpg', '.png')

# Globals
matched_user = {
    "matched": False,
    "name": "",
    "image_url": "",
    "checkin": "",
    "checkout": "",
    "date": ""
}

latest_message = {"text": "Say something..."}

# ---------------------- ATTENDANCE SYSTEM ----------------------

def log_attendance(name):
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    current_time = now.time()

    # Read or create Excel
    if os.path.exists(excel_file):
        df = pd.read_excel(excel_file)
    else:
        df = pd.DataFrame(columns=["Name", "Check-in Time", "Check-out Time", "Date"])

    today_entries = df[(df['Name'] == name) & (df['Date'] == date_str)]

    if today_entries.empty:
        # First-time entry – check-in
        new_entry = pd.DataFrame([{
            "Name": name,
            "Check-in Time": time_str,
            "Check-out Time": "",
            "Date": date_str
        }])
        df = pd.concat([df, new_entry], ignore_index=True)
        print(f"📝 Checked in: {name} at {time_str}")
    else:
        index = today_entries.index[0]
        if df.at[index, "Check-out Time"] == "" or pd.isna(df.at[index, "Check-out Time"]):
            df.at[index, "Check-out Time"] = time_str
            print(f"✅ Checked out: {name} at {time_str}")
        else:
            print(f"ℹ️ Already checked out for {name} today.")

    df.to_excel(excel_file, index=False)


def capture_and_compare():
    global matched_user
    reference_images = [f for f in os.listdir(image_dir) if f.lower().endswith(valid_extensions)]
    if not reference_images:
        print("⚠️ No reference images found.")
        return

    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        print("⚠️ Camera not accessible.")
        return

    for _ in range(5): cam.read()
    ret, frame = cam.read()
    cam.release()

    if not ret or frame is None:
        print("⚠️ Failed to capture frame.")
        return

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (480, 360))
    success, buffer = cv2.imencode(".jpg", resized, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
    if not success:
        print("⚠️ Failed to encode image.")
        return

    captured_bytes = io.BytesIO(buffer).getvalue()

    for image_file in reference_images:
        name = os.path.splitext(image_file)[0]
        with open(os.path.join(image_dir, image_file), "rb") as ref_img:
            ref_bytes = ref_img.read()

        try:
            response = rekognition.compare_faces(
                SourceImage={'Bytes': ref_bytes},
                TargetImage={'Bytes': captured_bytes},
                SimilarityThreshold=85
            )
            if response['FaceMatches']:
                matched_user.update({
                    "matched": True,
                    "name": name,
                    "image_url": f"/profile/{image_file}"
                })
                log_attendance(name)
                return
        except Exception as e:
            print(f"❌ Error comparing with {name}: {e}")

    matched_user.update({"matched": False, "name": "", "image_url": "", "checkin": "", "checkout": "", "date": ""})

# ---------------------- ROUTES ----------------------

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/')
def team():
    return render_template('team.html')


@app.route('/start-match')
def start_match():
    matched_user.update({
        "matched": False,
        "name": "",
        "image_url": "",
        "checkin": "",
        "checkout": "",
        "date": ""
    })

    capture_and_compare()

    if matched_user["matched"] and os.path.exists(excel_file):
        df = pd.read_excel(excel_file)
        user_rows = df[df["Name"] == matched_user["name"]]
        if not user_rows.empty:
            latest_row = user_rows.iloc[-1]
            matched_user["checkin"] = str(latest_row.get("Check-in Time", "") or "")
            matched_user["checkout"] = str(latest_row.get("Check-out Time", "") or "")
            matched_user["date"] = str(latest_row.get("Date", "") or "")

    return jsonify(matched_user)


@app.route('/profile/<filename>')
def profile_image(filename):
    return send_from_directory(image_dir, filename)



# ---------------------- CAT UI ASSISTANT ----------------------

@app.route("/assistant")
def serve_cat_ui():
    return render_template("cat_ui.html")

@app.route("/speak", methods=["POST"])
def speak_to_ui():
    data = request.json
    latest_message["text"] = data.get("text", "")
    print("🐱 Cat UI received:", latest_message["text"])
    return {"status": "ok"}

@app.route("/get-latest", methods=["GET"])
def get_latest_message():
    return jsonify(latest_message)

# ---------------------- MAIN ----------------------

if __name__ == "__main__":
    app.run(port=5005, debug=True)

