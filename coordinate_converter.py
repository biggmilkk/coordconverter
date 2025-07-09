import streamlit as st
import math
import folium
import re
import json
import zipfile
from io import BytesIO
from streamlit_folium import st_folium
from folium import Element
from xml.etree import ElementTree as ET

st.set_page_config(page_title="Coordinate Reference System Converter", layout="centered")

st.markdown("<h2 style='text-align: center;'>Coordinate Reference System Converter</h2>", unsafe_allow_html=True)
st.markdown("""
<p style='text-align: center; font-size: 0.9rem; color: grey;'>
Convert geographic coordinates or polygons between WGS84, GCJ-02, and BD09.
</p>
""", unsafe_allow_html=True)

mode = st.radio("Select Conversion Mode", ["Point Conversion", "Polygon Conversion"], horizontal=True)

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

if mode == "Point Conversion":
    # existing Point Conversion logic remains unchanged
    pass
elif mode == "Polygon Conversion":
    st.subheader("Polygon Coordinate Conversion")

    uploaded_files = st.file_uploader("Upload Polygon Files (KML, KMZ, or GeoJSON)", type=["kml", "kmz", "geojson"], accept_multiple_files=True)

    col1, col2 = st.columns(2)
    with col1:
        from_sys = st.selectbox("Source Coordinate System", ["WGS84", "GCJ-02", "BD09"], key="poly_from")
    with col2:
        to_sys = st.selectbox("Target Coordinate System", ["WGS84", "GCJ-02", "BD09"], key="poly_to")

    if uploaded_files:
        polygons = []

        def extract_coords_from_kml_string(kml_string):
            ns = {'kml': 'http://www.opengis.net/kml/2.2'}
            root = ET.fromstring(kml_string)
            coords = []
            for coord_text in root.findall(".//kml:coordinates", ns):
                raw = coord_text.text.strip().split()
                points = [(float(p.split(",")[1]), float(p.split(",")[0])) for p in raw]
                coords.append(points)
            return coords

        def extract_coords_from_kmz(file_bytes):
            with zipfile.ZipFile(BytesIO(file_bytes)) as kmz:
                for name in kmz.namelist():
                    if name.endswith(".kml"):
                        kml_string = kmz.read(name).decode("utf-8")
                        return extract_coords_from_kml_string(kml_string)
            return []

        for file in uploaded_files:
            ext = file.name.split(".")[-1].lower()
            if ext == "geojson":
                gj = json.load(file)
                features = gj["features"] if gj["type"] == "FeatureCollection" else [gj]
                for f in features:
                    geom = f["geometry"]
                    if geom["type"] == "Polygon":
                        coords = [(lat, lon) for lon, lat in geom["coordinates"][0]]
                        polygons.append(coords)
                    elif geom["type"] == "MultiPolygon":
                        for part in geom["coordinates"]:
                            coords = [(lat, lon) for lon, lat in part[0]]
                            polygons.append(coords)
            elif ext == "kml":
                kml = file.read().decode("utf-8")
                polygons.extend(extract_coords_from_kml_string(kml))
            elif ext == "kmz":
                polygons.extend(extract_coords_from_kmz(file.read()))

        func = transform_map.get((from_sys, to_sys), lambda x, y: (x, y))
        converted = [[func(lat, lon) for lat, lon in poly] for poly in polygons]

        st.subheader("Converted Polygons")
        m = folium.Map(tiles="CartoDB positron")
        for poly, conv in zip(polygons, converted):
            folium.Polygon(locations=poly, color="blue", fill=False).add_to(m)
            folium.Polygon(locations=conv, color="green", fill=False).add_to(m)

        if polygons:
            all_points = sum(polygons, [])
            bounds = [[min(p[0] for p in all_points), min(p[1] for p in all_points)],
                      [max(p[0] for p in all_points), max(p[1] for p in all_points)]]
            m.fit_bounds(bounds)

        m.get_root().html.add_child(Element(legend_html))
        st_folium(m, width=700, height=500)
