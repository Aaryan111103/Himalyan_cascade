# HimalayaCascade AI

A multi-hazard early warning dashboard for Chamoli, Uttarkashi, Pithoragarh, and Rudraprayag in Uttarakhand. The project models the cascade from rainfall and steep slopes to district-level landslide risk, river blockage, and flash-flood warning timelines.

## Project Description

HimalayaCascade AI is a lightweight hackathon-ready dashboard designed for disaster preparedness and early warning simulation. It brings together environmental inputs, a geospatial risk map, live local weather lookup, comparison mode, and an emergency alert simulation for downstream settlements.

## Feature Highlights

- Regional Folium map with risk-colored stations and illustrative downstream paths for all four districts
- Independent 24-hour Open-Meteo rainfall lookup for each station with manual fallback
- Weighted landslide risk engine using rainfall, slope, and seismic inputs
- District vulnerability weighting, river blockage, and flash-flood cascade calculations
- Ranked regional risk dashboard and district status table
- Selectable 3D terrain visualization using Plotly
- Current vs worst-case comparison for every district
- Consolidated NDMA-style alert simulation panel (does not send messages or place calls)
- Regional action readiness JSON output
- Clean, modern dashboard layout for a fast pitch presentation

## Tech Stack

- Python
- Streamlit
- Folium
- streamlit-folium
- Plotly
- Requests
- NumPy

## Installation

1. Clone or download this project folder.
2. Open a terminal in the project root.
3. Create a virtual environment (optional but recommended):

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
.venv\Scripts\activate      # Windows
```

4. Install dependencies:

```bash
pip install -r requirements.txt
```

## Run the App

From the project directory:

```bash
streamlit run app.py
```

Then open the local URL shown in the terminal, typically:

```text
http://localhost:8501
```

## Email Alerts

Enable email alerts in the sidebar to send one consolidated message to `aanyamishra0410@gmail.com` when one or more district risk scores exceed 65%. Delivery requires an SMTP account; for Gmail, use an App Password rather than your account password. Configure these variables in PowerShell before starting Streamlit:

```powershell
$env:SMTP_HOST = "smtp.gmail.com"
$env:SMTP_PORT = "587"
$env:SMTP_USERNAME = "your-sending-account@gmail.com"
$env:SMTP_PASSWORD = "your-gmail-app-password"
$env:SMTP_FROM = $env:SMTP_USERNAME
streamlit run app.py
```

The app reports SMTP errors in the dashboard and does not claim delivery when configuration is missing or sending fails. Email is opt-in and duplicate sends are suppressed while the same district alert remains active.

## Screenshot Placeholder

![Screenshot Placeholder](docs/himalaya-cascade-dashboard.png)

> Replace this placeholder with a real screenshot before submitting the project.

## Hackathon Submission Tips

- Keep the demo focused on the disaster chain: rainfall → landslide → river blockage → flood warning.
- Use the Chamoli 2021 style scenario to show regional escalation.
- Demonstrate that the app works locally and can fall back if live weather is unavailable.
- Highlight the regional map, comparison mode, and emergency readiness panel during the pitch.
- Keep the language simple and clear for judges unfamiliar with geospatial tools.

## Extra Enhancements Included

- Scenario presets for normal and extreme conditions
- Independent live weather reports for each district station
- District-level flash-flood countdowns and consolidated alert readiness
- 3D terrain view for visual storytelling
- Clear emergency guidance for downstream population protection

## Notes

- The app works fully offline using local calculations.
- Live weather is optional and uses Open-Meteo if available.
- All key calculations remain local to the machine for transparency and speed.
