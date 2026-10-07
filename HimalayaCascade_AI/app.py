from __future__ import annotations

import json
from typing import Optional

import folium
import numpy as np
import plotly.graph_objects as go
import requests
import streamlit as st
from streamlit_folium import st_folium

from cascade_engine import calculate_landslide_risk, evaluate_cascade_hazard

st.set_page_config(page_title="HimalayaCascade AI", page_icon="🏔️", layout="wide")

CHAMOLI_CENTER = (30.48, 79.33)


@st.cache_data(ttl=900)
def fetch_live_rainfall(lat: float, lon: float) -> Optional[float]:
    """Fetch 24-hour precipitation using Open-Meteo for the selected coordinate."""
    base_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "precipitation_sum",
        "timezone": "auto",
        "forecast_days": 2,
    }

    try:
        response = requests.get(base_url, params=params, timeout=8)
        response.raise_for_status()
        payload = response.json()
        daily_values = payload.get("daily", {}).get("precipitation_sum", [])
        if not daily_values:
            return None
        total_rain = float(max(daily_values))
        return round(total_rain, 1)
    except Exception:
        return None

def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def get_risk_style(risk_score: float) -> str:
    if risk_score > 0.65:
        return "red"
    if risk_score > 0.35:
        return "orange"
    return "green"


def build_terrain_surface(slope_deg: float):
    x = np.linspace(0, 1.2, 60)
    y = np.linspace(0, 1.2, 60)
    x_grid, y_grid = np.meshgrid(x, y)

    ridge = 600 + (slope_deg * 16) * (x_grid + y_grid)
    valley = 100 * np.sin((x_grid * 7) + (y_grid * 5))
    side = 60 * np.cos((x_grid * 9) - (y_grid * 6))
    z = ridge + valley + side

    return x_grid, y_grid, z


# Initialize session state
for key, default in {
    "rainfall_mm": 110,
    "slope_degrees": 34,
    "seismic_index": 1.3,
    "distance_to_town_km": 20,
    "location": {"lat": CHAMOLI_CENTER[0], "lon": CHAMOLI_CENTER[1]},
    "use_live_weather": False,
    "comparison_mode": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# Sidebar controls
st.sidebar.header("⚙️ Environmental Inputs")

selected_lat = st.session_state.location["lat"]
selected_lon = st.session_state.location["lon"]

use_live_weather = st.sidebar.checkbox("Use Live Weather Data (Open-Meteo)", value=st.session_state.use_live_weather)
st.session_state.use_live_weather = use_live_weather

rainfall_slider = st.sidebar.slider("24h Rainfall (mm)", 0, 300, int(st.session_state.rainfall_mm), step=5)
st.session_state.rainfall_mm = rainfall_slider

slope_slider = st.sidebar.slider("Terrain Slope (°)", 10, 60, int(st.session_state.slope_degrees))
st.session_state.slope_degrees = slope_slider

seismic_slider = st.sidebar.slider("Seismic Activity (0-3)", 0.0, 3.0, float(st.session_state.seismic_index), step=0.1)
st.session_state.seismic_index = seismic_slider

distance_km = st.sidebar.number_input("Distance to Downstream Town (km)", min_value=1.0, max_value=80.0, value=float(st.session_state.distance_to_town_km), step=1.0)
st.session_state.distance_to_town_km = distance_km

# Live weather override
live_weather_value = None
if use_live_weather:
    live_weather_value = fetch_live_rainfall(selected_lat, selected_lon)
    if live_weather_value is not None:
        rainfall_value = clamp(live_weather_value, 0, 300)
        st.session_state.rainfall_mm = rainfall_value
        st.sidebar.caption(f"Live rainfall loaded: {rainfall_value:.0f} mm")
    else:
        rainfall_value = st.session_state.rainfall_mm
        st.sidebar.warning("Open-Meteo unavailable. Using the local slider value.")
else:
    rainfall_value = st.session_state.rainfall_mm

st.sidebar.caption("Selected monitoring point: {:.3f}, {:.3f}".format(selected_lat, selected_lon))

scenario_col = st.sidebar.columns(2)
with scenario_col[0]:
    if st.sidebar.button("Normal Weather Scenario"):
        st.session_state.rainfall_mm = 80
        st.session_state.slope_degrees = 26
        st.session_state.seismic_index = 0.8
        st.session_state.distance_to_town_km = 18
        st.session_state.location = {"lat": 30.48, "lon": 79.33}

with scenario_col[1]:
    if st.sidebar.button("Chamoli 2021 Re-enactment"):
        st.session_state.rainfall_mm = 245
        st.session_state.slope_degrees = 50
        st.session_state.seismic_index = 2.8
        st.session_state.distance_to_town_km = 28
        st.session_state.location = {"lat": 30.47, "lon": 79.36}

comparison_mode = st.sidebar.checkbox("Enable Comparison Mode (Current vs Worst-Case)", value=st.session_state.comparison_mode)
st.session_state.comparison_mode = comparison_mode

# Dashboard header
st.title("HimalayaCascade AI")
st.caption("Cascading hazard chain: rainfall → landslide → river blockage → flash flood warning")

# Map selection / live location update
map_data = {}
map_obj = folium.Map(location=[selected_lat, selected_lon], zoom_start=10, tiles="OpenStreetMap", control_scale=True)
marker_color = get_risk_style(calculate_landslide_risk(slope_slider, rainfall_value, seismic_slider))
folium.Marker(
    location=[selected_lat, selected_lon],
    draggable=True,
    tooltip="Monitoring point",
    popup=f"Monitoring Point<br>Lat: {selected_lat:.3f}<br>Lon: {selected_lon:.3f}",
    icon=folium.Icon(color=marker_color, icon="mountain"),
).add_to(map_obj)

selected_risk = calculate_landslide_risk(slope_slider, rainfall_value, seismic_slider)
selected_hazard = evaluate_cascade_hazard(selected_risk, distance_km, river_proximity_meters=100)

if selected_hazard["river_blocked"]:
    folium.Marker(
        location=[selected_lat + 0.04, selected_lon + 0.03],
        popup="⚠️ River blocked by landslide dam",
        icon=folium.Icon(color="black", icon="warning-sign"),
    ).add_to(map_obj)
    flood_path = [
        [selected_lat + 0.04, selected_lon + 0.03],
        [selected_lat + 0.08, selected_lon + 0.06],
        [selected_lat + 0.12, selected_lon + 0.10],
    ]
    folium.PolyLine(flood_path, color="blue", weight=5, opacity=0.8, tooltip="Predicted flood path").add_to(map_obj)

map_obj.add_child(folium.CircleMarker(
    location=[selected_lat, selected_lon],
    radius=18,
    color=marker_color,
    fill=True,
    fill_opacity=0.7,
    fill_color=marker_color,
    popup=f"Landslide Risk: {selected_risk * 100:.1f}%",
))

map_data = st_folium(
    map_obj,
    key="location_map",
    width=1000,
    height=430,
    returned_objects=["last_clicked", "last_object_clicked"],
)

if map_data.get("last_clicked"):
    clicked = map_data["last_clicked"]
    st.session_state.location = {"lat": round(float(clicked["lat"]), 3), "lon": round(float(clicked["lng"]), 3)}
elif map_data.get("last_object_clicked"):
    object_clicked = map_data["last_object_clicked"]
    if "lat" in object_clicked and "lng" in object_clicked:
        st.session_state.location = {"lat": round(float(object_clicked["lat"]), 3), "lon": round(float(object_clicked["lng"]), 3)}

selected_lat = st.session_state.location["lat"]
selected_lon = st.session_state.location["lon"]

# Recompute final risk values after selection update
rainfall_value = st.session_state.rainfall_mm if not use_live_weather else (fetch_live_rainfall(selected_lat, selected_lon) or st.session_state.rainfall_mm)
selected_risk = calculate_landslide_risk(st.session_state.slope_degrees, rainfall_value, st.session_state.seismic_index)
selected_hazard = evaluate_cascade_hazard(selected_risk, st.session_state.distance_to_town_km, river_proximity_meters=100)

# Tab layout
main_tabs = st.tabs(["🗺️ Live Map & Alerts", "📊 3D Terrain", "📈 Comparison"])

with main_tabs[0]:
    left_col, right_col = st.columns([3, 2])

    with left_col:
        st.subheader("📍 Selected Monitoring Zone")
        map_obj = folium.Map(location=[selected_lat, selected_lon], zoom_start=11, tiles="OpenStreetMap", control_scale=True)
        risk_color = get_risk_style(selected_risk)
        folium.Marker(
            location=[selected_lat, selected_lon],
            draggable=True,
            tooltip="Monitoring point",
            popup=f"Monitoring Point<br>Lat: {selected_lat:.3f}<br>Lon: {selected_lon:.3f}",
            icon=folium.Icon(color=risk_color, icon="mountain"),
        ).add_to(map_obj)
        folium.CircleMarker(
            location=[selected_lat, selected_lon],
            radius=20,
            color=risk_color,
            fill=True,
            fill_color=risk_color,
            fill_opacity=0.7,
            popup=f"Landslide Risk: {selected_risk * 100:.1f}%",
        ).add_to(map_obj)

        if selected_hazard["river_blocked"]:
            folium.Marker(
                location=[selected_lat + 0.04, selected_lon + 0.03],
                popup="⚠️ River blocked by natural dam",
                icon=folium.Icon(color="black", icon="warning-sign"),
            ).add_to(map_obj)
            flood_path = [
                [selected_lat + 0.04, selected_lon + 0.03],
                [selected_lat + 0.08, selected_lon + 0.06],
                [selected_lat + 0.12, selected_lon + 0.10],
            ]
            folium.PolyLine(flood_path, color="blue", weight=6, opacity=0.8).add_to(map_obj)

        st_folium(map_obj, key="live_map", width="100%", height=450)

    with right_col:
        st.subheader("🚨 Early Warning Metrics")
        risk_delta = "HIGH RISK" if selected_risk > 0.65 else "MODERATE" if selected_risk > 0.35 else "LOW"
        st.metric(
            "Landslide Risk Index",
            value=f"{selected_risk * 100:.1f}%",
            delta=risk_delta,
            delta_color="inverse" if selected_risk > 0.65 else "normal",
        )

        if selected_hazard["river_blocked"]:
            st.error(selected_hazard["flood_warning"])
        else:
            st.success(selected_hazard["flood_warning"])

        flash_countdown = selected_hazard["wave_arrival_mins"]
        st.metric(
            "Flash Flood Countdown",
            value=f"{flash_countdown} mins" if flash_countdown is not None else "No surge",
            delta="Downstream impact window" if flash_countdown else "Stable channels",
        )

        if st.button("Send SMS Alert to NDMA"):
            st.session_state.sms_alert_sent = True

        if st.session_state.get("sms_alert_sent", False):
            with st.expander("NDMA Alert Panel", expanded=True):
                alert_payload = {
                    "alert_type": "Landslide-induced river blockage",
                    "location": {
                        "lat": round(selected_lat, 3),
                        "lon": round(selected_lon, 3),
                    },
                    "risk_index": round(selected_risk, 4),
                    "wave_arrival_mins": selected_hazard["wave_arrival_mins"],
                    "message": "Urgent evacuation needed for downstream hamlets. NDMA teams to monitor river channel and clear access routes.",
                    "priority": "LEVEL 3" if selected_hazard["river_blocked"] else "STANDBY",
                }
                st.code(json.dumps(alert_payload, indent=2))
        else:
            with st.expander("NDMA Alert Panel", expanded=False):
                st.write("The alert panel is ready to draft a downstream warning.")

        municipality_readiness = {
            "alert_status": "ACTIVE" if selected_hazard["river_blocked"] else "MONITOR",
            "evacuation_level": "LEVEL 3" if selected_hazard["river_blocked"] else "STANDBY",
            "downstream_distance_km": round(st.session_state.distance_to_town_km, 1),
            "recommended_actions": [
                "Block access to bridge crossings",
                "Alert local ward offices",
                "Activate rescue teams",
                "Prepare temporary shelter lanes",
            ],
            "estimated_wave_arrival_mins": selected_hazard["wave_arrival_mins"],
            "coverage": "Chamoli District / Downstream settlements",
        }
        st.json(municipality_readiness)

with main_tabs[1]:
    st.subheader("🧭 3D Terrain Profile")
    x_grid, y_grid, z_surface = build_terrain_surface(st.session_state.slope_degrees)
    terrain_figure = go.Figure(data=[go.Surface(z=z_surface, x=x_grid, y=y_grid, colorscale="Viridis")])
    terrain_figure.update_layout(
        title="Terrain Surge Profile around the monitoring point",
        scene=dict(
            xaxis_title="East-West",
            yaxis_title="North-South",
            zaxis_title="Elevation",
            aspectmode="manual",
            aspectratio={"x": 1, "y": 1, "z": 0.7},
        ),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(terrain_figure, use_container_width=True)

with main_tabs[2]:
    if comparison_mode:
        st.subheader("📈 Current vs Worst-Case Scenario")
        worst_rain = clamp(st.session_state.rainfall_mm + 90, 0, 300)
        worst_slope = clamp(st.session_state.slope_degrees + 15, 10, 60)
        worst_seismic = clamp(st.session_state.seismic_index + 1.0, 0, 3)
        worst_risk = calculate_landslide_risk(worst_slope, worst_rain, worst_seismic)
        worst_hazard = evaluate_cascade_hazard(worst_risk, st.session_state.distance_to_town_km, river_proximity_meters=100)

        left, right = st.columns(2)
        with left:
            st.markdown("### Current Scenario")
            st.metric("Risk Index", f"{selected_risk * 100:.1f}%")
            st.metric("Arrival Window", f"{selected_hazard['wave_arrival_mins']} mins" if selected_hazard['wave_arrival_mins'] else "No surge")
            if selected_hazard["river_blocked"]:
                st.error(selected_hazard["flood_warning"])
            else:
                st.success(selected_hazard["flood_warning"])

        with right:
            st.markdown("### Worst-Case Scenario")
            st.metric("Risk Index", f"{worst_risk * 100:.1f}%")
            st.metric("Arrival Window", f"{worst_hazard['wave_arrival_mins']} mins" if worst_hazard['wave_arrival_mins'] else "No surge")
            if worst_hazard["river_blocked"]:
                st.error(worst_hazard["flood_warning"])
            else:
                st.success(worst_hazard["flood_warning"])
    else:
        st.info("Comparison mode is disabled. Enable it in the sidebar to view the current-vs-worst-case panel.")

st.markdown(
    "<hr><p style='text-align:center; color:#6b7280; font-size:12px;'>Built for Hackathon | All calculations run locally | Live weather from Open-Meteo (optional)</p>",
    unsafe_allow_html=True,
)
