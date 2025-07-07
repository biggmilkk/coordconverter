import streamlit as st
import math
import pandas as pd
import folium
from streamlit_folium import st_folium
import re
from branca.element import Template, MacroElement

# --- Page Setup ---
st.set_page_config(page_title="Coordinate Conversion Tool", layout="centered")

st.markdown("<h2 style='text-align: center;'>Coordinate Conversion Tool</h2>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align: center; font-size: 0.9rem; color: grey;'>Convert geographic coordinates between WGS84, GCJ-02, and BD09 systems for use in mapping and spatial analysis workflows. Outputs are copy-friendly and visualized clearly.</p>",
    unsafe_allow_html=True
)

# --- Initialize state ---
if "show_map" not in st.session_state:
    st.session_state["show_map"] = False

# --- Conversion logic ---
PI = math.pi
A = 6378245.0
EE = 0.00669342162296594323

def out_of_china(lat, lon):
    return not (72.004 <= lon <= 137.8347 and 0.8293 <= lat <= 55.8271)

def transform_lat(x, y):
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20 * math.sin(6 * x * PI) + 20 * math.sin(2 * x * PI)) * 2 / 3
    ret += (20 * math.sin(y * PI) + 40 * math.sin(y / 3 * PI)) * 2 / 3
    ret += (160 * math.sin(y / 12 * PI) + 320 * math.sin(y * PI / 30)) * 2 / 3
    return ret

def transform_lon(x, y):
    ret = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20 * math.sin(6 * x * PI) + 20 * math.sin(2 * x * PI)) * 2 / 3
    ret += (20 * math.sin(x * PI) + 40 * math.sin(x / 3 * PI)) * 2 / 3
    ret += (150 * math.sin(x / 12 * PI) + 300 * math.sin(x / 30 * PI)) * 2 / 3
    return ret

def wgs84_to_gcj02(lat, lon):
    if out_of_china(lat, lon):
        return lat, lon
    dlat = transform_lat(lon - 105, lat - 35)
    dlon = transform_lon(lon - 105, lat - 35)
    radlat = lat / 180 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlon = (dlon * 180) / (A / sqrtmagic * math.cos(radlat) * PI)
    return lat + dlat, lon + dlon

def gcj02_to_wgs84(lat, lon):
    g_lat, g_lon = wgs84_to_gcj02(lat, lon)
    return lat * 2 - g_lat, lon * 2 - g_lon

def gcj02_to_bd09(lat, lon):
    z = math.sqrt(lon * lon + lat * lat) + 0.00002 * math.sin(lat * PI * 3000 / 180)
    theta = math.atan2(lat, lon) + 0.000003 * math.cos(lon * PI * 3000 / 180)
    return z * math.sin(theta) + 0.006, z * math.cos(theta) + 0.0065

def bd09_to_gcj02(lat, lon):
    x = lon - 0.0065
    y = lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * PI * 3000 / 180)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * PI * 3000 / 180)
    return z * math.sin(theta), z * math.cos(theta)

def wgs84_to_bd09(lat, lon):
    return gcj02_to_bd09(*wgs84_to_gcj02(lat, lon))

def bd09_to_wgs84(lat, lon):
    return gcj02_to_wgs84(*bd09_to_gcj02(lat, lon))

transform_map = {
    ("WGS84", "GCJ-02"): wgs84_to_gcj02,
    ("GCJ-02", "WGS84"): gcj02_to_wgs84,
    ("GCJ-02", "BD09"): gcj02_to_bd09,
    ("BD09", "GCJ-02"): bd09_to_gcj02,
    ("WGS84", "BD09"): wgs84_to_bd09,
    ("BD09", "WGS84"): bd09_to_wgs84
}

# --- Input ---
coord_input = st.text_input("Enter Coordinates (latitude, longitude)", placeholder="e.g. 19.215401, -98.126154")
lat, lon = None, None
if coord_input.strip():
    match = re.findall(r'-?\d+\.\d+', coord_input)
    if len(match) >= 2:
        try:
            lat = float(match[0])
            lon = float(match[1])
        except:
            st.error("Could not parse coordinates. Check format.")
    else:
        st.warning("Enter two decimal values separated by a comma or space.")

col1, col2 = st.columns(2)
with col1:
    from_sys = st.selectbox("Source Coordinate System", ["WGS84", "GCJ-02", "BD09"])
with col2:
    to_sys = st.selectbox("Target Coordinate System", ["WGS84", "GCJ-02", "BD09"])

# --- Button and State ---
if lat is not None and lon is not None:
    if st.button("Convert Coordinates", use_container_width=True):
        st.session_state["show_map"] = True
        st.session_state["input_coords"] = (lat, lon)
        st.session_state["from_sys"] = from_sys
        st.session_state["to_sys"] = to_sys

# --- Output ---
if st.session_state.get("show_map"):
    lat, lon = st.session_state["input_coords"]
    from_sys = st.session_state["from_sys"]
    to_sys = st.session_state["to_sys"]

    func = transform_map.get((from_sys, to_sys))
    if from_sys == to_sys:
        new_lat, new_lon = lat, lon
    elif func:
        new_lat, new_lon = func(lat, lon)
    else:
        st.error("Unsupported conversion path.")
        st.stop()

    st.subheader("Converted Coordinates (Copy-Friendly)")
    coord_str = f"{new_lat:.6f}, {new_lon:.6f}"
    st.code(coord_str)

    # --- Map Output with Legend ---
    st.markdown("<h4 style='text-align: center;'>Map Preview</h4>", unsafe_allow_html=True)
    m = folium.Map(location=[(lat + new_lat) / 2, (lon + new_lon) / 2], zoom_start=12, tiles="CartoDB positron")
    folium.Marker([lat, lon], tooltip="Input", icon=folium.Icon(color="blue")).add_to(m)
    folium.Marker([new_lat, new_lon], tooltip="Converted", icon=folium.Icon(color="green")).add_to(m)

    bounds = [[min(lat, new_lat), min(lon, new_lon)], [max(lat, new_lat), max(lon, new_lon)]]
    m.fit_bounds(bounds, padding=(30, 30))

    legend_html = """
    <div style="
        position: fixed; 
        bottom: 50px; left: 50px; width: 150px; height: 60px; 
        background-color: white; 
        border: 1px solid lightgray;
        z-index:9999; 
        font-size:12px;
        padding: 10px;">
        <b>Legend</b><br>
        <i style="color:blue;">●</i> Input<br>
        <i style="color:green;">●</i> Converted
    </div>
    """
    legend = MacroElement()
    legend._template = Template(legend_html)
    m.get_root().add_child(legend)

    st_folium(m, width=700, height=450)
