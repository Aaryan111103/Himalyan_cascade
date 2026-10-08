from_future__ import annotations

import json
import os
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Optional

import folium
import numpy as np
import plotly.graph_objects as go
import requests
import streamlit as st
from streamlit_folium import st_folium

from cascade_engine import calculate_landslide_risk, evaluate_cascade_hazard

st.set_page_config(page_title="HimalayaCascade AI", page_icon="🏔️", layout="wide")

MONITORING_POINTS = {
    "Chamoli": {"lat": 30.48, "lon": 79.33, "river": "Alaknanda"},
    "Uttarkashi": {"lat": 30.73, "lon": 78.44, "river": "Bhagirathi"},
    "Pithoragarh": {"lat": 29.58, "lon": 80.22, "river": "Kali"},
    "Rudraprayag": {"lat": 30.28, "lon": 78.98, "river": "Mandakini"},
}
DISTRICT_VULNERABILITY = {
    "Chamoli": 1.15,
    "Uttarkashi": 1.10,
    "Pithoragarh": 1.05,
    "Rudraprayag": 1.08,
}
DISTRICTS = list(MONITORING_POINTS)
EMAIL_ALERT_RECIPIENT = "aanyamishra0410@gmail.com"
UTTARAKHAND_CENTER = (30.25, 79.20)
DOWNSTREAM_PATHS = {
    "Chamoli": [(30.48, 79.33), (30.43, 79.31), (30.37, 79.29), (30.31, 79.25)],
    "Uttarkashi": [(30.73, 78.44), (30.66, 78.47), (30.58, 78.49), (30.50, 78.52)],
    "Pithoragarh": [(29.58, 80.22), (29.53, 80.27), (29.48, 80.32), (29.43, 80.38)],
    "Rudraprayag": [(30.28, 78.98), (30.23, 78.95), (30.18, 78.92), (30.13, 78.90)],
}


@st.cache_data(ttl=900)
def fetch_live_weather(lat: float, lon: float) -> dict:
    """Fetch the latest 24-hour hourly precipitation and retain the API response."""
    base_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "precipitation",
        "timezone": "auto",
        "past_days": 1,
        "forecast_days": 1,
    }

    try:
        response = requests.get(base_url, params=params, timeout=8)
        response.raise_for_status()
        payload = response.json()
        hourly = payload.get("hourly", {})
        times = hourly.get("time", [])
        precipitation = hourly.get("precipitation", [])
        offset = int(payload.get("utc_offset_seconds", 0))
        local_now = (datetime.now(timezone.utc) + timedelta(seconds=offset)).strftime("%Y-%m-%dT%H:00")
        recent_values = [
            float(value)
            for timestamp, value in zip(times, precipitation)
            if timestamp <= local_now and value is not None
        ][-24:]
        if not recent_values:
            return {"rainfall_mm": None, "payload": payload, "error": "No hourly precipitation values returned."}
        return {"rainfall_mm": round(sum(recent_values), 1), "payload": payload, "error": None}
    except Exception as error:
        return {"rainfall_mm": None, "payload": None, "error": str(error)}


def send_email_alert(affected_districts: list[dict]) -> tuple[bool, str]:
    """Send one consolidated alert using SMTP settings supplied by the operator."""
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_username = os.environ.get("SMTP_USERNAME")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    missing_settings = [
        name
        for name, value in (
            ("SMTP_HOST", smtp_host),
            ("SMTP_USERNAME", smtp_username),
            ("SMTP_PASSWORD", smtp_password),
        )
        if not value
    ]
    if missing_settings:
        return False, "Configure SMTP environment variables: " + ", ".join(missing_settings)

    sender = os.environ.get("SMTP_FROM", smtp_username)
    message = EmailMessage()
    message["Subject"] = "HimalayaCascade AI: district risk above 65%"
    message["From"] = sender
    message["To"] = EMAIL_ALERT_RECIPIENT
    message.set_content(
        "Regional threshold alert: one or more district risk scores exceeded 65%.\n\n"
        + "\n\n".join(
            "{district} ({river}): risk {risk:.1f}%, rainfall {rainfall:.1f} mm, "
            "river blocked: {blocked}, wave arrival: {arrival}.\n{warning}".format(
                district=result["district"],
                river=result["river"],
                risk=result["risk"] * 100,
                rainfall=result["rainfall_mm"],
                blocked="yes" if result["river_blocked"] else "no",
                arrival=(f"{result['wave_arrival_mins']} minutes" if result["wave_arrival_mins"] is not None else "not expected"),
                warning=result["flood_warning"],
            )
            for result in affected_districts
        )
    )

    try:
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        context = ssl.create_default_context()
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=15) as smtp:
                smtp.login(smtp_username, smtp_password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as smtp:
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
                smtp.login(smtp_username, smtp_password)
                smtp.send_message(message)
        return True, f"Email sent to {EMAIL_ALERT_RECIPIENT}."
    except Exception as error:
        return False, f"Email delivery failed: {error}"


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
    "use_live_weather": False,
    "comparison_mode": False,
    "email_alert_enabled": False,
    "email_alert_attempted_signature": None,
    "email_alert_result": None,
    "weather_district": "Chamoli",
    "live_rainfall_by_district": {},
    "live_weather_reports": {},
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# Sidebar controls
st.sidebar.header("⚙️ Environmental Inputs")

use_live_weather = st.sidebar.checkbox("Use Live Weather Data (Open-Meteo)", value=st.session_state.use_live_weather)
st.session_state.use_live_weather = use_live_weather

weather_district = st.sidebar.selectbox(
    "District for live weather report",
    DISTRICTS,
    index=DISTRICTS.index(st.session_state.weather_district),
)
st.session_state.weather_district = weather_district

rainfall_slider = st.sidebar.slider("24h Rainfall (mm)", 0, 300, int(st.session_state.rainfall_mm), step=5)
st.session_state.rainfall_mm = rainfall_slider

slope_slider = st.sidebar.slider("Terrain Slope (°)", 10, 60, int(st.session_state.slope_degrees))
st.session_state.slope_degrees = slope_slider

seismic_slider = st.sidebar.slider("Seismic Activity (0-3)", 0.0, 3.0, float(st.session_state.seismic_index), step=0.1)
st.session_state.seismic_index = seismic_slider

distance_km = st.sidebar.number_input("Distance to Downstream ToWn (km)", min_value=1.0, max_value=80.0, value=float(st.session_state.distance_to_town_km), step=1.0)
st.session_state.distance_to_town_km = distance_km

# Each station is fetched independently. Failed requests use the shared manual fallback.
rainfall_by_district = {}
weather_reports = {}
failed_weather_districts = []
if use_live_weather:
    for district, station in MONITORING_POINTS.items():
        report = fetch_live_weather(station["lat"], station["lon"])
        weather_reports[district] = report
        live_value = report["rainfall_mm"]
        if live_value is None:
            failed_weather_districts.append(district)
            rainfall_by_district[district] = float(st.session_state.rainfall_mm)
        else:
            rainfall_by_district[district] = clamp(live_value, 0, 300)
        st.session_state.live_rainfall_by_district[district] = rainfall_by_district[district]
    st.session_state.live_weather_reports = weather_reports
    if failed_weather_districts:
        st.sidebar.warning(
            "Live weather unavailable for " + ", ".join(failed_weather_districts)
            + ". Using the manual rainfall slider for those districts."
        )
    st.sidebar.caption(
        f"{weather_district} 24-hour rainfall: "
        f"{rainfall_by_district[weather_district]:.1f} mm"
        if weather_district not in failed_weather_districts
        else f"{weather_district}: using manual rainfall fallback ({rainfall_by_district[weather_district]:.1f} mm)"
    )
    with st.sidebar.expander(f"{weather_district} Open-Meteo API response"):
        selected_report = weather_reports.get(weather_district, {})
        if selected_report.get("payload") is not None:
            st.json(selected_report["payload"])
        else:
            st.write(selected_report.get("error", "No API response available."))
else:
    rainfall_by_district = {district: float(st.session_state.rainfall_mm) for district in DISTRICTS}

scenario_col = st.sidebar.columns(2)
with scenario_col[0]:
    if st.sidebar.button("Normal Weather Scenario"):
        st.session_state.rainfall_mm = 80
        st.session_state.slope_degrees = 26
        st.session_state.seismic_index = 0.8
        st.session_state.distance_to_town_km = 18

with scenario_col[1]:
    if st.sidebar.button("Chamoli 2021 Re-enactment"):
        st.session_state.rainfall_mm = 245
        st.session_state.slope_degrees = 50
        st.session_state.seismic_index = 2.8
        st.session_state.distance_to_town_km = 28

comparison_mode = st.sidebar.checkbox("Enable Comparison Mode (Current vs Worst-Case)", value=st.session_state.comparison_mode)
st.session_state.comparison_mode = comparison_mode
email_alert_enabled = st.sidebar.checkbox(
    f"Email alerts to {EMAIL_ALERT_RECIPIENT} when risk exceeds 65%",
    key="email_alert_enabled",
)
st.sidebar.caption("Email delivery requires SMTP_HOST, SMTP_PORT, SMTP_USERNAME, and SMTP_PASSWORD environment variables.")

# Dashboard header
st.title("HimalayaCascade AI")
st.caption("Cascading hazard chain: rainfall → landslide → river blockage → flash flood warning")

district_results = {}
for district, station in MONITORING_POINTS.items():
    base_risk = calculate_landslide_risk(
        st.session_state.slope_degrees,
        rainfall_by_district[district],
        st.session_state.seismic_index,
    )
    risk = round(min(1.0, base_risk * DISTRICT_VULNERABILITY[district]), 4)
    hazard = evaluate_cascade_hazard(
        risk,
        st.session_state.distance_to_town_km,
        river_proximity_meters=100,
    )
    district_results[district] = {
        "district": district,
        "river": station["river"],
        "lat": station["lat"],
        "lon": station["lon"],
        "rainfall_mm": rainfall_by_district[district],
        "risk": risk,
        **hazard,
    }

ranked_districts = sorted(
    district_results.values(),
    key=lambda result: result["risk"],
    reverse=True,
)
alert_districts = [result for result in ranked_districts if result["river_blocked"]]
highest_risk = ranked_districts[0]
email_alert_signature = tuple(result["district"] for result in alert_districts)

if not email_alert_enabled or not alert_districts:
    st.session_state.email_alert_attempted_signature = None
if email_alert_enabled and alert_districts:
    if email_alert_signature != st.session_state.email_alert_attempted_signature:
        st.session_state.email_alert_attempted_signature = email_alert_signature
        email_sent, email_detail = send_email_alert(alert_districts)
        st.session_state.email_alert_result = {
            "signature": email_alert_signature,
            "success": email_sent,
            "detail": email_detail,
        }

# Tab layout
main_tabs = st.tabs(["🗺️ Live Map & Alerts", "📊 3D Terrain", "📈 Comparison"])

with main_tabs[0]:
    st.subheader("Regional Risk Ranking")
    st.dataframe(
        [
            {
                "Rank": index,
                "District": result["district"],
                "Risk Score": f"{result['risk'] * 100:.1f}%",
                "Risk Level": "HIGH" if result["risk"] > 0.65 else "MODERATE" if result["risk"] > 0.35 else "LOW",
            }
            for index, result in enumerate(ranked_districts, start=1)
        ],
        hide_index=True,
        use_container_width=True,
    )

    left_col, right_col = st.columns([3, 2])

    with left_col:
        st.subheader("📍 Uttarakhand Monitoring Network")
        map_obj = folium.Map(location=UTTARAKHAND_CENTER, zoom_start=7, tiles="OpenStreetMap", control_scale=True)
        map_obj.fit_bounds([(station["lat"], station["lon"]) for station in MONITORING_POINTS.values()], padding=(20, 20))
        for district, result in district_results.items():
            risk_color = get_risk_style(result["risk"])
            warning_popup = result["flood_warning"].replace("\n", " ")
            folium.CircleMarker(
                location=[result["lat"], result["lon"]],
                radius=10,
                color=risk_color,
                fill=True,
                fill_color=risk_color,
                fill_opacity=0.8,
                tooltip=f"{district} | {result['river']} | Risk {result['risk'] * 100:.1f}%",
                popup=folium.Popup(
                    f"<b>{district}</b> ({result['river']})<br>"
                    f"Risk: {result['risk'] * 100:.1f}%<br>"
                    f"Rainfall: {result['rainfall_mm']:.1f} mm<br>{warning_popup}",
                    max_width=360,
                ),
            ).add_to(map_obj)
            folium.Marker(
                location=[result["lat"], result["lon"]],
                tooltip=district,
                icon=folium.DivIcon(
                    html=f'<div style="font-size:11px;font-weight:bold;color:#111;white-space:nowrap;">{district}</div>'
                ),
            ).add_to(map_obj)

            if result["river_blocked"]:
                flood_path = DOWNSTREAM_PATHS[district]
                folium.Marker(
                    location=flood_path[1],
                    popup=f"{district} alert: {result['flood_warning']}",
                    tooltip=f"{district} river blockage warning",
                    icon=folium.Icon(color="black", icon="warning-sign"),
                ).add_to(map_obj)
                folium.PolyLine(
                    locations=flood_path,
                    color="blue",
                    weight=5,
                    opacity=0.8,
                    tooltip=f"Illustrative downstream path: {district} / {result['river']}",
                    popup=f"{district}: {result['flood_warning']}",
                ).add_to(map_obj)

        st_folium(map_obj, key="regional_live_map", width="100%", height=450)
        st.caption("Blue routes are illustrative downstream paths from each monitoring station, not hydraulic forecasts.")

    with right_col:
        st.subheader("🚨 Regional Early Warning")
        st.metric("Districts Under Alert", len(alert_districts))
        st.metric("Highest Current Risk", highest_risk["district"], f"{highest_risk['risk'] * 100:.1f}%")
        if alert_districts:
            alert_names = ", ".join(result["district"] for result in alert_districts)
            st.error(f"Regional warning: river blockage threshold exceeded in {alert_names}.")
            if not email_alert_enabled:
                st.info("Enable email alerts in the sidebar to send a consolidated threshold alert.")
            else:
                email_result = st.session_state.email_alert_result
                if email_result and email_result["signature"] == email_alert_signature:
                    if email_result["success"]:
                        st.success(email_result["detail"])
                    else:
                        st.warning(email_result["detail"])
        else:
            st.success("Regional channels remain below the modeled river-blockage threshold.")

        if st.button("Send SMS Alert to NDMA"):
            st.session_state.sms_alert_sent = True

        st.caption("SMS delivery is simulated locally. Email sends only when enabled and SMTP is configured.")
        if st.session_state.get("sms_alert_sent", False) or alert_districts:
            with st.expander("NDMA Alert Panel", expanded=True):
                alert_payload = {
                    "alert_type": "Landslide-induced river blockage",
                    "affected_districts": [
                        {
                            "district": result["district"],
                            "river": result["river"],
                            "risk_index": result["risk"],
                            "wave_arrival_mins": result["wave_arrival_mins"],
                            "flood_warning": result["flood_warning"],
                        }
                        for result in alert_districts
                    ],
                    "monitored_districts": DISTRICTS,
                    "message": "Urgent evacuation needed for downstream hamlets. NDMA teams to monitor river channel and clear access routes.",
                    "priority": "LEVEL 3" if alert_districts else "STANDBY",
                    "email_delivery_status": (
                        st.session_state.email_alert_result["detail"]
                        if st.session_state.email_alert_result
                        and st.session_state.email_alert_result["signature"] == email_alert_signature
                        else "Email alerts are disabled or no active district exceeds 65%."
                    ),
                }
                st.code(json.dumps(alert_payload, indent=2))
        else:
            with st.expander("NDMA Alert Panel", expanded=False):
                st.write("The panel is ready to draft one consolidated downstream warning.")

        municipality_readiness = {
            "alert_status": "ACTIVE" if alert_districts else "MONITOR",
            "evacuation_level": "LEVEL 3" if alert_districts else "STANDBY",
            "downstream_distance_km": round(st.session_state.distance_to_town_km, 1),
            "recommended_actions": [
                "Block access to bridge crossings",
                "Alert local ward offices",
                "Activate rescue teams",
                "Prepare temporary shelter lanes",
            ],
            "districts_under_alert": [result["district"] for result in alert_districts],
            "estimated_wave_arrival_mins": {
                result["district"]: result["wave_arrival_mins"] for result in alert_districts
            },
            "coverage": "Chamoli, Uttarkashi, Pithoragarh, and Rudraprayag districts",
        }
        st.json(municipality_readiness)

    st.subheader("Regional Status Table")
    st.dataframe(
        [
            {
                "District": result["district"],
                "River Basin": result["river"],
                "Risk Score": f"{result['risk'] * 100:.1f}%",
                "Risk Level": "HIGH" if result["risk"] > 0.65 else "MODERATE" if result["risk"] > 0.35 else "LOW",
                "River Blocked": "Yes" if result["river_blocked"] else "No",
                "Wave Arrival": f"{result['wave_arrival_mins']} mins" if result["wave_arrival_mins"] is not None else "No surge",
                "Flood Warning": result["flood_warning"],
            }
            for result in ranked_districts
        ],
        hide_index=True,
        use_container_width=True,
    )

with main_tabs[1]:
    terrain_district = st.selectbox("Terrain district", DISTRICTS, key="terrain_district")
    st.subheader(f"🧭 3D Terrain Analysis - {terrain_district}")
    x_grid, y_grid, z_surface = build_terrain_surface(st.session_state.slope_degrees)
    terrain_figure = go.Figure(data=[go.Surface(z=z_surface, x=x_grid, y=y_grid, colorscale="Viridis")])
    terrain_figure.update_layout(
        title=f"3D Terrain Analysis - {terrain_district}",
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
        st.subheader("📈 Current vs Worst-Case Scenario by District")
        for district in DISTRICTS:
            with st.expander(district, expanded=True):
                worst_rain = clamp(rainfall_by_district[district] + 90, 0, 300)
                worst_slope = clamp(st.session_state.slope_degrees + 15, 10, 60)
                worst_seismic = clamp(st.session_state.seismic_index + 1.0, 0, 3)
                worst_base_risk = calculate_landslide_risk(worst_slope, worst_rain, worst_seismic)
                worst_risk = round(min(1.0, worst_base_risk * DISTRICT_VULNERABILITY[district]), 4)
                worst_hazard = evaluate_cascade_hazard(
                    worst_risk,
                    st.session_state.distance_to_town_km,
                    river_proximity_meters=100,
                )
                current = district_results[district]
                current_col, worst_col = st.columns(2)
                with current_col:
                    st.markdown("### Current Scenario")
                    st.metric("Risk Index", f"{current['risk'] * 100:.1f}%")
                    st.metric(
                        "Arrival Window",
                        f"{current['wave_arrival_mins']} mins" if current["wave_arrival_mins"] is not None else "No surge",
                    )
                    (st.error if current["river_blocked"] else st.success)(current["flood_warning"])
                with worst_col:
                    st.markdown("### Worst-Case Scenario")
                    st.metric("Risk Index", f"{worst_risk * 100:.1f}%")
                    st.metric(
                        "Arrival Window",
                        f"{worst_hazard['wave_arrival_mins']} mins" if worst_hazard["wave_arrival_mins"] is not None else "No surge",
                    )
                    (st.error if worst_hazard["river_blocked"] else st.success)(worst_hazard["flood_warning"])
    else:
        st.info("Comparison mode is disabled. Enable it in the sidebar to view the current-vs-worst-case panel.")

st.markdown(
    "<hr><p style='text-align:center; color:#6b7280; font-size:12px;'>Built for Hackathon | All calculations run locally | Live weather from Open-Meteo (optional)</p>",
    unsafe_allow_html=True,
)
