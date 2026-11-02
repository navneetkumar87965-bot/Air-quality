# AeroPulse — Air Quality Analysis Website

A Flask dashboard built around the Air Quality Analysis and Pollution Trend Monitoring Python project.

## Features
- Upload your own CSV or load the sample dataset.
- Clean column names, remove duplicate rows, parse dates, and convert pollutant columns to numeric.
- Show record/location/AQI metrics.
- Compare average AQI by location.
- Display monthly AQI trends and pollutant descriptive statistics.
- Search the dataset preview.
- Download a pollution statistics CSV.
- Premium dark interface with green/cyan accents.
- Search a city/place for current model-based AQI and pollutant estimates.
- View a 48-hour hourly AQI timeline (past 24 hours + forecast 24 hours).
- Manual refresh and automatic refresh every 15 minutes.

## Expected CSV columns
Recommended: `Date`, `Location`, `AQI`, `PM2.5`, `PM10`, `NO2`, `SO2`, `CO`, `O3`.
At least one pollutant column must be present. `Location` is required for this version's full location-comparison dashboard.

## Run on Windows / VS Code
1. Install Python 3.10+.
2. Extract this folder and open it in VS Code.
3. Open the terminal in the project folder.
4. Create and activate a virtual environment (optional but recommended):

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

5. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

6. Start the website:

   ```powershell
   python app.py
   ```

7. Open `http://127.0.0.1:5000` in your browser.
8. Click **Load sample dashboard**, or upload your own CSV.

## Live location lookup
- The dashboard uses the free Open-Meteo Geocoding API to resolve the place name and the Open-Meteo Air Quality API to retrieve current pollutant estimates and hourly US AQI values. No API key is required for this educational use.
- The displayed values are **model-based estimates**, not guaranteed readings from a physical CPCB/local monitoring station. Refreshing every 15 minutes does not mean the underlying model data updates every 15 minutes.
- An internet connection is required for the live lookup. CSV-based analysis continues to work independently.

## Important
- The sample dataset is illustrative class-project data, not verified live air-quality measurements.
- This is an educational dashboard, not an official health advisory.
- Before deploying publicly, change `app.secret_key` to a secure environment-based secret, turn off Flask debug mode, and configure production hosting.
- The statistics download form asks you to upload the CSV again to produce the report. This avoids keeping uploaded files on the server after the request.

API documentation: https://open-meteo.com/en/docs/air-quality-api
