import os
import time
import pandas as pd
import requests
from dotenv import load_dotenv
from flask import Flask, render_template, request, send_file
from io import BytesIO

load_dotenv()
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
URL = "https://maps.googleapis.com/maps/api/distancematrix/json"

app = Flask(__name__)

def safe_get(o, d, units="imperial"):
    params = {"origins": o, "destinations": d, "key": API_KEY, "units": units}
    try:
        r = requests.get(URL, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        el = data.get("rows", [{}])[0].get("elements", [{}])[0]
        status = el.get("status", "UNKNOWN")
        if status != "OK":
            return None, None, None, None, status
        dist_text = el["distance"]["text"]
        dist_val_m = el["distance"]["value"]
        dur_text = el["duration"]["text"]
        dur_val_s = el["duration"]["value"]
        return dist_text, dist_val_m, dur_text, dur_val_s, status
    except Exception as e:
        return None, None, None, None, f"ERROR: {e}"

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if not API_KEY:
            return "API key missing. Set GOOGLE_MAPS_API_KEY in .env", 400
        file = request.files.get("file")
        units = request.form.get("units", "imperial")
        pause = float(request.form.get("pause", "0.1"))
        if not file:
            return "Please upload a CSV.", 400

        df = pd.read_csv(file)
        if not {"origin", "destination"}.issubset(df.columns):
            return "CSV must include `origin` and `destination` columns.", 400

        df["distance_text"] = None
        df["duration_text"] = None
        df["distance_miles"] = None
        df["duration_minutes"] = None
        df["status"] = None

        for i, row in df.iterrows():
            dt, dvm, ut, uvs, st = safe_get(str(row["origin"]), str(row["destination"]), units)
            df.at[i, "distance_text"] = dt
            df.at[i, "duration_text"] = ut
            df.at[i, "status"] = st
            if dvm is not None:
                df.at[i, "distance_miles"] = dvm * 0.000621371
            if uvs is not None:
                df.at[i, "duration_minutes"] = uvs / 60.0
            time.sleep(pause)

        buf = BytesIO()
        df.to_csv(buf, index=False)
        buf.seek(0)
        return send_file(buf, as_attachment=True, download_name="address_with_distances.csv", mimetype="text/csv")
    return render_template("index.html")
    
if __name__ == "__main__":
    app.run(debug=True)

