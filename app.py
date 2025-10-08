import io
import os
import time
import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
URL = "https://maps.googleapis.com/maps/api/distancematrix/json"

st.set_page_config(page_title="Drive Time & Distance", page_icon="🛣️")
st.title("🛣️ Drive Time & Distance (Google Distance Matrix)")

with st.expander("CSV format help", expanded=False):
    st.markdown("""
**Input CSV columns required:**
- `origin` — full origin address (e.g., `"1709 Tun Tavern Trl, Austin, TX"`)
- `destination` — full destination address (e.g., `"11601 Alterra Pkwy, Austin, TX"`)

You can add any other columns; they will be preserved in the output.
""")

if not API_KEY:
    st.error("Google API key is not set. Create a `.env` file from `.env.example` and set `GOOGLE_MAPS_API_KEY`.")
    st.stop()

uploaded = st.file_uploader("Upload your CSV (with `origin` and `destination` columns)", type=["csv"])

col1, col2 = st.columns(2)
with col1:
    unit = st.selectbox("Units", ["imperial", "metric"], index=0)
with col2:
    pause = st.number_input("Pause between requests (seconds)", min_value=0.0, max_value=2.0, value=0.1, step=0.1)

run_btn = st.button("Run Distance Lookup")

def safe_get_distance_duration(o: str, d: str, api_key: str, units: str):
    params = {
        "origins": o,
        "destinations": d,
        "key": api_key,
        "units": units
    }
    try:
        r = requests.get(URL, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        status = data.get("rows", [{}])[0].get("elements", [{}])[0].get("status", "UNKNOWN")
        if status != "OK":
            return {"distance_text": None, "distance_value_m": None, "duration_text": None, "duration_value_s": None, "status": status}
        el = data["rows"][0]["elements"][0]
        dist_text = el["distance"]["text"]
        dist_val_m = el["distance"]["value"]  # meters
        dur_text = el["duration"]["text"]
        dur_val_s = el["duration"]["value"]  # seconds
        return {
            "distance_text": dist_text,
            "distance_value_m": dist_val_m,
            "duration_text": dur_text,
            "duration_value_s": dur_val_s,
            "status": status
        }
    except Exception as e:
        return {"distance_text": None, "distance_value_m": None, "duration_text": None, "duration_value_s": None, "status": f"ERROR: {e}"}

if run_btn:
    if uploaded is None:
        st.warning("Please upload a CSV first.")
        st.stop()

    df = pd.read_csv(uploaded)
    if not {"origin", "destination"}.issubset(df.columns):
        st.error("CSV must include columns: `origin`, `destination`.")
        st.stop()

    # Prepare result columns
    df_out = df.copy()
    df_out["distance_text"] = None
    df_out["duration_text"] = None
    df_out["distance_miles"] = None
    df_out["duration_minutes"] = None
    df_out["status"] = None

    progress = st.progress(0)
    results = []

    for i, row in df_out.iterrows():
        res = safe_get_distance_duration(str(row["origin"]), str(row["destination"]), API_KEY, unit)
        results.append(res)
        time.sleep(pause)
        progress.progress(int((i + 1) / len(df_out) * 100))

    # Attach results
    res_df = pd.DataFrame(results)
    df_out["distance_text"] = res_df["distance_text"]
    df_out["duration_text"] = res_df["duration_text"]
    df_out["status"]        = res_df["status"]

    # Convert numeric values
    # We'll convert meters->miles and seconds->minutes for convenience
    meters_to_miles = 0.000621371
    seconds_to_minutes = 1/60.0
    df_out["distance_miles"] = pd.to_numeric(res_df["distance_value_m"], errors="coerce") * meters_to_miles
    df_out["duration_minutes"] = pd.to_numeric(res_df["duration_value_s"], errors="coerce") * seconds_to_minutes

    st.success("Done! Preview below. You can also download the full CSV.")

    st.dataframe(df_out.head(50))

    # Download button
    out_csv = df_out.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download results CSV",
        data=out_csv,
        file_name="address_with_distances.csv",
        mime="text/csv"
    )

st.caption("Tip: Be mindful of API quotas. Consider batching larger files and adding pauses.")
