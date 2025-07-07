import streamlit as st
import math
import pydeck as pdk
import pandas as pd

# Constants for coordinate conversion
PI = math.pi
A = 6378245.0  # Semi-major axis
EE = 0.00669342162296594323  # Eccentricity squared

# Utility: Check if outside China (WGS84 doesn't need conversion outside China)
def out_of_china(lat, lon):
    return not (72.004 <= lon <= 137.8347 and 0.8293 <= lat <= 55.8271)

# Transformation helpers
def transform_lat(x, y):
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + \
          0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * PI) +
            20.0 * math.sin(2.0 * x * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * PI) +
            40.0 * math.sin(y / 3.0 * PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * PI) +
            320.0 * math.sin(y * PI / 30.0)) * 2.0 / 3.0
    return ret

def transform_lon(x, y):
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + \
          0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * PI) +
            20.0 * math.sin(2.0 * x * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * PI) +
            40.0 * math.sin(x / 3.0 * PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * PI) +
            300.0 * math.sin(x / 30.0 * PI)) * 2.0 / 3.0
    return ret

# Coordinate transformations
def wgs84_to_gcj02(lat, lon):
    if out_of_china(lat, lon):
        return lat, lon
    dlat = transform_lat(lon - 105.0, lat - 35.0)
    dlon = transform_lon(lon - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlon = (dlon * 180.0) / (A / sqrtmagic * math.cos(radlat) * PI)
    return lat + dlat, lon + dlon

def gcj02_to_wgs84(lat, lon):
    g_lat, g_lon = wgs84_to_gcj02(lat, lon)
    return lat * 2 - g_lat, lon * 2 - g_lon

def gcj02_to_bd09(lat, lon):
    z = math.sqrt(lon * lon + lat * lat) + 0.00002 * math.sin(lat * PI * 3000.0 / 180.0)
    theta = math.atan2(lat, lon) + 0.000003 * math.cos(lon * PI * 3000.0 / 180.0)
    bd_lat = z * math.sin(theta) + 0.006
    bd_lon = z * math.cos(theta) + 0.0065
    return bd_lat, bd_lon

def bd09_to_gcj02(lat, lon):
    x = lon - 0.0065
    y = lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * PI * 3000.0 / 180.0)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * PI * 3000.0 / 180.0)
    gg_lat = z * math.sin(theta)
    gg_lon = z * math.cos(theta)
    return gg_lat, gg_lon

def wgs84_to_bd09(lat, lon):
    return gcj02_to_bd09(*wgs84_to_gcj02(lat, lon))

def bd09_to_wgs84(lat, lon):
    return gcj02_to_wgs84(*bd09_to_gcj02(lat, lon))

# Map of conversion functions
transform_map = {
    ("WGS84", "GCJ-02"): wgs84_to_gcj02,
    ("GCJ-02", "WGS84"): gcj02_to_wgs84,
    ("GCJ-02", "BD09"): gcj02_to_bd09,
    ("BD09", "GCJ-02"): bd09_to_gcj02,
    ("WGS84", "BD09"): wgs84_to_bd09,
    ("BD09", "WGS84"): bd09_to_wgs84
}

# ---------------------
# Streamlit App Layout
# ---------------------
st.set_page_config(page_title="Coordinate Converter", page_icon="📍")
st.title("📍 Coordinate Conversion Tool")
st.markdown("Convert between **WGS84**, **GCJ-02**, and **BD09** coordinate systems used globally and in China.")

# Inputs
lat = st.number_input("Enter Latitude", format="%.6f", placeholder="e.g. 39.90923")
lon = st.number_input("Enter Longitude", format="%.6f", placeholder="e.g. 116.39737")

col1, col2 = st.columns(2)
with col1:
    from_sys = st.selectbox("From Coordinate System", ["WGS84", "GCJ-02", "BD09"])
with col2:
    to_sys = st.selectbox("To Coordinate System", ["WGS84", "GCJ-02", "BD09"])

# Conversion logic
if st.button("🔄 Convert Coordinates"):
    if from_sys == to_sys:
        st.info("Source and target coordinate systems are the same.")
        st.write(f"Latitude: {lat:.6f}, Longitude: {lon:.6f}")
    else:
        func = transform_map.get((from_sys, to_sys))
        if func:
            try:
                new_lat, new_lon = func(lat, lon)
                st.success("✅ Conversion successful:")
                st.write(f"**Latitude:** `{new_lat:.6f}`")
                st.write(f"**Longitude:** `{new_lon:.6f}`")

                # Map preview
                df = pd.DataFrame([
                    {"label": "Original", "lat": lat, "lon": lon},
                    {"label": "Converted", "lat": new_lat, "lon": new_lon}
                ])

                mid_lat = (lat + new_lat) / 2
                mid_lon = (lon + new_lon) / 2

                st.markdown("### 🗺️ Map Preview")
                st.pydeck_chart(pdk.Deck(
                    map_style="mapbox://styles/mapbox/streets-v12",
                    initial_view_state=pdk.ViewState(
                        latitude=mid_lat,
                        longitude=mid_lon,
                        zoom=12,
                        pitch=0,
                    ),
                    layers=[
                        pdk.Layer(
                            "ScatterplotLayer",
                            data=df,
                            get_position='[lon, lat]',
                            get_fill_color='[255, label == "Original" ? 0 : 128, 0, 160]',
                            get_radius=100,
                            pickable=True,
                            auto_highlight=True,
                        ),
                        pdk.Layer(
                            "TextLayer",
                            data=df,
                            get_position='[lon, lat]',
                            get_text='label',
                            get_size=16,
                            get_color='[0, 0, 0, 255]',
                            get_angle=0,
                            get_text_anchor='"top"',
                            get_alignment_baseline='"bottom"'
                        )
                    ]
                ))

            except Exception as e:
                st.error(f"Conversion failed: {e}")
        else:
            st.error("Unsupported conversion path.")
