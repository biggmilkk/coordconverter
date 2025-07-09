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

if mode == "Polygon Conversion":
    uploaded_file = st.file_uploader("Upload Polygon File (KML, KMZ, GeoJSON)", type=["kml", "kmz", "geojson", "json"])
    col1, col2 = st.columns(2)
    with col1:
        from_sys = st.selectbox("Source Coordinate System", ["WGS84", "GCJ-02", "BD09"], key="poly_from")
    with col2:
        to_sys = st.selectbox("Target Coordinate System", ["WGS84", "GCJ-02", "BD09"], key="poly_to")

    def extract_coords_from_kml_string(kml_string):
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        root = ET.fromstring(kml_string)
        polygons = []
        for coord_text in root.findall(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", ns):
            coords = []
            raw_coords = coord_text.text.strip().split()
            for coord in raw_coords:
                parts = coord.split(',')
                if len(parts) >= 2:
                    lon, lat = map(float, parts[:2])
                    coords.append((lat, lon))
            if coords and coords[0] != coords[-1]:
                coords.append(coords[0])
            if coords:
                polygons.append(coords)
        return polygons

    def extract_coords_from_kmz(file_bytes):
        with zipfile.ZipFile(BytesIO(file_bytes)) as kmz:
            for name in kmz.namelist():
                if name.endswith(".kml"):
                    kml_string = kmz.read(name).decode("utf-8")
                    return extract_coords_from_kml_string(kml_string)
        return []

    if uploaded_file:
        try:
            name = uploaded_file.name.lower()
            if name.endswith(".geojson") or name.endswith(".json"):
                geojson = json.load(uploaded_file)
                features = geojson["features"] if geojson["type"] == "FeatureCollection" else [geojson]
                polygons = []
                for feature in features:
                    geom = feature["geometry"]
                    if geom["type"].lower() == "polygon":
                        coords = geom["coordinates"][0]
                        coords = [(lat, lon) for lon, lat in coords]
                        polygons.append(coords)
                    elif geom["type"].lower() == "multipolygon":
                        for part in geom["coordinates"]:
                            coords = part[0]
                            coords = [(lat, lon) for lon, lat in coords]
                            polygons.append(coords)
            elif name.endswith(".kml"):
                doc = uploaded_file.read().decode("utf-8")
                polygons = extract_coords_from_kml_string(doc)
            elif name.endswith(".kmz"):
                polygons = extract_coords_from_kmz(uploaded_file.read())
            else:
                polygons = []

            if not polygons:
                st.warning("No valid polygons found.")
            else:
                m = folium.Map(tiles="CartoDB positron")
                for coords in polygons:
                    converted = []
                    for lat, lon in coords:
                        if from_sys == to_sys:
                            new_lat, new_lon = lat, lon
                        else:
                            func = transform_map.get((from_sys, to_sys))
                            new_lat, new_lon = func(lat, lon)
                        converted.append((new_lat, new_lon))
                    folium.Polygon(locations=coords, color="blue", weight=2, fill_opacity=0.3).add_to(m)
                    folium.Polygon(locations=converted, color="green", weight=2, fill_opacity=0.3).add_to(m)
                m.fit_bounds(m.get_bounds())
                m.get_root().html.add_child(Element(legend_html))
                st_folium(m, width=700, height=500)
        except Exception as e:
            st.error(f"Error processing file: {e}")
