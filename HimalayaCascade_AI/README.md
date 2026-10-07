# HimalayaCascade AI

A modern multi-hazard early warning dashboard for the Chamoli region of the Himalayas. The project models the cascade from intense rainfall and steep slopes to landslide risk, river blockage, and flash-flood warning timelines.

## Project Description

HimalayaCascade AI is a lightweight hackathon-ready dashboard designed for disaster preparedness and early warning simulation. It brings together environmental inputs, a geospatial risk map, live local weather lookup, comparison mode, and an emergency alert simulation for downstream settlements.

## Feature Highlights

- Interactive Folium map centered on Chamoli, India with click-to-select monitoring point
- Draggable monitoring marker and dynamic coordinate updates
- Live rainfall lookup through Open-Meteo with graceful fallback to slider values
- Weighted landslide risk engine using rainfall, slope, and seismic inputs
- River blockage and flash-flood cascade logic
- 3D terrain visualization using Plotly
- Current vs worst-case comparison mode
- NDMA-style emergency alert simulation panel
- Municipality action readiness JSON output
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

## Screenshot Placeholder

![Screenshot Placeholder](docs/himalaya-cascade-dashboard.png)

> Replace this placeholder with a real screenshot before submitting the project.

## Hackathon Submission Tips

- Keep the demo focused on the disaster chain: rainfall → landslide → river blockage → flood warning.
- Use the Chamoli 2021 style scenario to show urgency and relevance.
- Demonstrate that the app works locally and can fall back if live weather is unavailable.
- Highlight the map selection, comparison mode, and emergency readiness panel during the pitch.
- Keep the language simple and clear for judges unfamiliar with geospatial tools.

## Extra Enhancements Included

- Scenario presets for normal and extreme conditions
- Live weather override for selected coordinates
- Response metrics for flash-flood countdown and alert readiness
- 3D terrain view for visual storytelling
- Clear emergency guidance for downstream population protection

## Notes

- The app works fully offline using local calculations.
- Live weather is optional and uses Open-Meteo if available.
- All key calculations remain local to the machine for transparency and speed.
