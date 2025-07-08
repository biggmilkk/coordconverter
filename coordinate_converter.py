import streamlit as st
import math
import folium
import re
from streamlit_folium import st_folium
from folium import Element

st.set_page_config(page_title="Spatial Coordinate Converter", layout="centered")

st.markdown("<h2 style='text-align: center;'>Spatial Coordinate Converter</h2>", unsafe_allow_html=True)
st.markdown("""
<p style='text-align: center; font-size: 0.9rem; color: grey;'>
Convert single or multiple geographic coordinates between WGS84, GCJ-02, and BD09.
</p>
""", unsafe_allow_html=True)

PI = math.pi
A = 6378245.0
EE = 0.00669342162296594323

def out_of_china(lat, lon):
    return not (72.004 <= lon <= 137.8347 and 0.8293 <= lat <= 55.8271)

def transform_lat(x, y):
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + \
          0.1 * x * y + 0.2 * math.sqrt(abs(x))
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

# --- Coordinate Parsing ---
def dms_to_dd(d, m, s, direction):
    dd = d + m / 60 + s / 3600
    if direction in ['S', 'W']:
        dd *= -1
    return dd

def dm_to_dd(dm, direction):
    d = int(dm)
    m = (dm - d) * 100
    dd = d + m / 60
    if direction in ['S', 'W']:
        dd *= -1
    return dd

def parse_input_coordinates(text):
    text = text.replace("\u00b0", " ").replace("\u2032", " ").replace("\u2033", " ")
    text = text.replace(",", " ").replace(";", " ")
    lines = text.strip().splitlines()
    coords = []
    tokens = re.findall(r'[\d.]+|[NSEW]', text.upper())

    i = 0
    while i < len(tokens):
        try:
            if (i + 7 < len(tokens) and tokens[i+3] in 'NS' and tokens[i+7] in 'EW'):
                lat = dms_to_dd(int(tokens[i]), int(tokens[i+1]), float(tokens[i+2]), tokens[i+3])
                lon = dms_to_dd(int(tokens[i+4]), int(tokens[i+5]), float(tokens[i+6]), tokens[i+7])
                coords.append((lat, lon))
                i += 8
            elif (i + 3 < len(tokens) and tokens[i+1] in 'NS' and tokens[i+3] in 'EW'):
                lat = dm_to_dd(float(tokens[i]), tokens[i+1])
                lon = dm_to_dd(float(tokens[i+2]), tokens[i+3])
                coords.append((lat, lon))
                i += 4
            elif (i + 1 < len(tokens)):
                lat = float(tokens[i])
                lon = float(tokens[i+1])
                coords.append((lat, lon))
                i += 2
            else:
                i += 1
        except:
            i += 1
    return coords

# --- Input Section ---
input_text = st.text_area("Paste Coordinates (DD, DMS, or DDM)", height=150, placeholder="19.215401, -98.126154\n19 12 55N, 98 07 34W\n19.2154N 98.1261W")

col1, col2 = st.columns(2)
with col1:
    from_sys = st.selectbox("Source Coordinate System", ["WGS84", "GCJ-02", "BD09"])
with col2:
    to_sys = st.selectbox("Target Coordinate System", ["WGS84", "GCJ-02", "BD09"])

# --- Convert ---
if st.button("Convert Coordinates", use_container_width=True):
    parsed_coords = parse_input_coordinates(input_text)
    if not parsed_coords:
        st.warning("No valid coordinates found.")
    else:
        st.subheader("Converted Coordinates")
        converted = []
        for lat, lon in parsed_coords:
            if from_sys == to_sys:
                new_lat, new_lon = lat, lon
            else:
                func = transform_map.get((from_sys, to_sys))
                new_lat, new_lon = func(lat, lon)
            converted.append((lat, lon, new_lat, new_lon))

        for i, (olat, olon, nlat, nlon) in enumerate(converted, 1):
            st.text(f"Point {i} → {nlat:.6f}, {nlon:.6f}")

        m = folium.Map(location=[converted[0][0], converted[0][1]], zoom_start=6)
        for i, (olat, olon, nlat, nlon) in enumerate(converted, 1):
            folium.Marker([olat, olon], tooltip=f"Input {i}", icon=folium.Icon(color="blue")).add_to(m)
            folium.Marker([nlat, nlon], tooltip=f"Converted {i}", icon=folium.Icon(color="green")).add_to(m)

        bounds = [[min(min(c[0], c[2]) for c in converted), min(min(c[1], c[3]) for c in converted)],
                  [max(max(c[0], c[2]) for c in converted), max(max(c[1], c[3]) for c in converted)]]
        m.fit_bounds(bounds, padding=(20, 20))

        legend_html = """
        <div style="
            position: absolute;
            bottom: 30px;
            left: 30px;
            background-color: white;
            border: 1px solid #ccc;
            padding: 10px 12px;
            font-size: 13px;
            font-family: Arial, sans-serif;
            color: #333;
            z-index: 9999;
            box-shadow: 2px 2px 6px rgba(0, 0, 0, 0.15);
            border-radius: 4px;">
            <b>Legend</b><br>
            <span style='display:inline-block; width:10px; height:10px; background:#1f77b4; border-radius:50%; margin-right:8px;'></span> Input<br>
            <span style='display:inline-block; width:10px; height:10px; background:#2ca02c; border-radius:50%; margin-right:8px;'></span> Converted
        </div>
        """
        m.get_root().html.add_child(Element(legend_html))
        with st.container():
            st_folium(m, width=700, height=500)
