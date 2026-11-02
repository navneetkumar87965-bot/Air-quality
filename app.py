from io import BytesIO, StringIO
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify
import requests
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "change-this-secret-key-before-deployment"
sns.set_theme(style="darkgrid")

POLLUTANTS = ["AQI", "PM2.5", "PM10", "NO2", "SO2", "CO", "O3"]
REQUIRED_HINT = ["Date", "Location"]

SAMPLE_CSV = """Date,Location,AQI,PM2.5,PM10,NO2,SO2,CO,O3
2025-01-05,Delhi,165,72,118,34,12,0.8,28
2025-01-20,Delhi,178,81,126,37,13,0.9,30
2025-02-08,Delhi,152,65,110,31,11,0.7,26
2025-02-21,Delhi,143,59,102,29,10,0.7,25
2025-01-07,Mumbai,110,43,78,22,8,0.5,21
2025-01-22,Mumbai,125,48,84,24,9,0.6,23
2025-02-09,Mumbai,105,39,73,20,7,0.5,20
2025-02-23,Mumbai,98,35,68,18,7,0.4,19
2025-01-10,Faridabad,190,90,140,40,15,1.0,31
2025-01-25,Faridabad,205,98,150,43,16,1.1,33
2025-02-12,Faridabad,175,80,130,36,13,0.9,28
2025-02-25,Faridabad,160,73,120,33,12,0.8,26
"""

def clean_data(data):
    data = data.copy()
    data.columns = data.columns.astype(str).str.strip().str.replace(r"^\*+|\*+$", "", regex=True)
    data = data.loc[:, ~data.columns.duplicated()]
    data = data.drop_duplicates()
    if "Date" in data.columns:
        data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    for column in POLLUTANTS:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    if "Location" in data.columns:
        data["Location"] = data["Location"].astype("string").str.strip()
    return data

def make_chart(fig):
    output = BytesIO()
    fig.tight_layout()
    fig.savefig(output, format="png", dpi=140, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    output.seek(0)
    return output

def get_analysis(data):
    available = [col for col in POLLUTANTS if col in data.columns and data[col].notna().any()]
    stats = {}
    for col in available:
        values = data[col].dropna()
        stats[col] = {
            "average": round(float(values.mean()), 2),
            "minimum": round(float(values.min()), 2),
            "maximum": round(float(values.max()), 2),
            "median": round(float(values.median()), 2),
            "std": round(float(values.std()), 2) if len(values) > 1 else 0.0
        }

    location_rows = []
    if "Location" in data.columns and available:
        grouped = data.groupby("Location", dropna=True)[available].mean().round(2)
        for location, row in grouped.iterrows():
            location_rows.append({"location": str(location), **{c: (None if pd.isna(row[c]) else float(row[c])) for c in available}})

    trend_rows = []
    if "Date" in data.columns and "AQI" in available:
        dated = data.dropna(subset=["Date", "AQI"]).copy()
        if not dated.empty:
            dated["Month"] = dated["Date"].dt.to_period("M").dt.to_timestamp()
            grouped = dated.groupby("Month")["AQI"].mean().round(2)
            trend_rows = [{"month": d.strftime("%b %Y"), "aqi": float(v)} for d, v in grouped.items()]

    return available, stats, location_rows, trend_rows

@app.route("/", methods=["GET", "POST"])
def index():
    data = None
    filename = "air_quality.csv"
    if request.method == "POST":
        upload = request.files.get("file")
        if upload and upload.filename:
            filename = secure_filename(upload.filename)
            try:
                data = pd.read_csv(upload)
            except Exception:
                flash("The file could not be read. Please upload a valid CSV file.", "error")
                return redirect(url_for("index"))
        elif request.form.get("use_sample") == "yes":
            data = pd.read_csv(StringIO(SAMPLE_CSV))
            filename = "sample_air_quality.csv"
        else:
            flash("Choose a CSV file or load the sample dataset.", "error")
            return redirect(url_for("index"))

        data = clean_data(data)
        if data.empty:
            flash("The CSV contains no data rows.", "error")
            return redirect(url_for("index"))
        if not any(col in data.columns for col in POLLUTANTS):
            flash("No recognized pollutant columns found. Expected one or more of: " + ", ".join(POLLUTANTS), "error")
            return redirect(url_for("index"))
        if "Location" not in data.columns:
            flash("The dataset needs a 'Location' column for location comparison. Other analysis can still work, so add this column and upload again for the full dashboard.", "error")
            return redirect(url_for("index"))

        available, stats, locations, trends = get_analysis(data)
        data_preview = data.head(100).copy()
        if "Date" in data_preview.columns:
            data_preview["Date"] = data_preview["Date"].dt.strftime("%Y-%m-%d").fillna("")
        data_preview = data_preview.astype(object).where(pd.notna(data_preview), "—").to_dict(orient="records")
        columns = list(data.columns)
        average_aqi = stats.get("AQI", {}).get("average")
        highest_location = None
        if "AQI" in available and locations:
            valid = [r for r in locations if r.get("AQI") is not None]
            if valid:
                highest_location = max(valid, key=lambda r: r["AQI"])["location"]

        return render_template(
            "dashboard.html",
            filename=filename,
            total_records=len(data),
            total_locations=data["Location"].nunique(dropna=True),
            available=available,
            stats=stats,
            locations=locations,
            trends=trends,
            preview=data_preview,
            columns=columns,
            average_aqi=average_aqi,
            highest_location=highest_location,
            missing=data.isnull().sum().to_dict(),
        )
    return render_template("index.html")


@app.route("/api/live-air-quality")
def live_air_quality():
    """Look up model-based current and hourly air-quality estimates for a place."""
    place = (request.args.get("place") or "").strip()
    if not place:
        return jsonify({"error": "Enter a city or place name."}), 400
    if len(place) > 120:
        return jsonify({"error": "Place name is too long."}), 400

    try:
        geo_response = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": place, "count": 1, "language": "en", "format": "json"},
            timeout=12,
        )
        geo_response.raise_for_status()
        geo_data = geo_response.json()
        results = geo_data.get("results") or []
        if not results:
            return jsonify({"error": f"No matching place found for '{place}'. Try a nearby city name."}), 404

        location = results[0]
        latitude, longitude = location["latitude"], location["longitude"]
        air_response = requests.get(
            "https://air-quality-api.open-meteo.com/v1/air-quality",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "us_aqi,pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
                "hourly": "us_aqi",
                "past_hours": 24,
                "forecast_hours": 24,
                "timezone": "auto",
            },
            timeout=15,
        )
        air_response.raise_for_status()
        air_data = air_response.json()
        return jsonify({
            "location": {
                "name": location.get("name", place),
                "admin1": location.get("admin1"),
                "country": location.get("country"),
                "latitude": latitude,
                "longitude": longitude,
                "timezone": air_data.get("timezone", "Local time"),
            },
            "current": air_data.get("current", {}),
            "current_units": air_data.get("current_units", {}),
            "hourly": air_data.get("hourly", {}),
            "hourly_units": air_data.get("hourly_units", {}),
            "source": "Open-Meteo Air Quality API",
            "note": "These are model-based estimates, not guaranteed live readings from a nearby physical monitoring station.",
        })
    except requests.RequestException:
        return jsonify({"error": "The air-quality service could not be reached. Check your internet connection and try again."}), 502
    except (ValueError, KeyError, TypeError):
        return jsonify({"error": "The air-quality service returned an unexpected response. Please try again."}), 502

@app.route("/sample.csv")
def sample_csv():
    return send_file(BytesIO(SAMPLE_CSV.encode("utf-8")), mimetype="text/csv",
                     as_attachment=True, download_name="air_quality.csv")

@app.route("/download/statistics", methods=["POST"])
def download_statistics():
    upload = request.files.get("file")
    if not upload or not upload.filename:
        flash("Upload your CSV again to generate a report.", "error")
        return redirect(url_for("index"))
    try:
        data = clean_data(pd.read_csv(upload))
        available = [c for c in POLLUTANTS if c in data.columns]
        if not available:
            flash("No pollutant columns found.", "error")
            return redirect(url_for("index"))
        output = BytesIO()
        data[available].describe().to_csv(output)
        output.seek(0)
        return send_file(output, mimetype="text/csv", as_attachment=True, download_name="pollution_statistics.csv")
    except Exception:
        flash("Could not create the statistics report from that CSV.", "error")
        return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
