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
    return not (73.66 < lon < 135.05 and 3.86 < lat < 53.55)

def transform_lat(x, y):
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + \
          0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * PI) +
            20.0 * math.sin(2.0 * x * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * PI) +
            40.0 * math.sin(y / 3.0 * PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * PI) +
            320 * math.sin(y * PI / 30.0)) * 2.0 / 3.0
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
    return z * math.sin(theta) + 0.006, z * math.cos(theta) + 0.0065

def bd09_to_gcj02(lat, lon):
    x = lon - 0.0065
    y = lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * PI * 3000.0 / 180.0)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * PI * 3000.0 / 180.0)
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
    ("BD09", "WGS84"): bd09_to_wgs84,
}

legend_html = """<div style="
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
</div>"""

if mode == "Point Conversion":
    st.subheader("Point Coordinate Conversion")
    coord_input = st.text_area("Enter Coordinates (one pair per line)", placeholder="e.g. 19.2154, -98.1261", height=150)
    col1, col2 = st.columns(2)
    with col1:
        from_sys = st.selectbox("Source Coordinate System", ["WGS84", "GCJ-02", "BD09"], key="point_from")
    with col2:
        to_sys = st.selectbox("Target Coordinate System", ["WGS84", "GCJ-02", "BD09"], key="point_to")

    if st.button("Convert Coordinates"):
        if not coord_input.strip():
            st.warning("Please input coordinates.")
        else:
            try:
                lines = coord_input.strip().split("\n")
                pairs = []
                for line in lines:
                    nums = re.findall(r"-?\d+\.\d+", line)
                    if len(nums) >= 2:
                        lat, lon = map(float, nums[:2])
                        pairs.append((lat, lon))

                if not pairs:
                    st.warning("No valid coordinate pairs found.")
                else:
                    func = transform_map.get((from_sys, to_sys), lambda x, y: (x, y))
                    results = [func(lat, lon) for lat, lon in pairs]

                    st.subheader("Converted Coordinates")
                    for orig, conv in zip(pairs, results):
                        st.code(f"Input:    {orig[0]:.6f}, {orig[1]:.6f}\nConverted: {conv[0]:.6f}, {conv[1]:.6f}")

                    m = folium.Map(tiles="CartoDB positron")
                    for orig, conv in zip(pairs, results):
                        folium.Marker(orig, icon=folium.Icon(color="blue")).add_to(m)
                        folium.Marker(conv, icon=folium.Icon(color="green")).add_to(m)
                    m.fit_bounds(m.get_bounds())
                    m.get_root().html.add_child(Element(legend_html))
                    st_folium(m, width=700, height=500)
            except Exception as e:
                st.error(f"Error processing coordinates: {e}")

elif mode == "Polygon Conversion":
    st.subheader("Polygon Coordinate Conversion")
    uploaded_file = st.file_uploader("Upload Polygon File (KML, KMZ, GeoJSON)", type=["kml", "kmz", "geojson"])
    col1, col2 = st.columns(2)
    with col1:
        from_sys = st.selectbox("Source Coordinate System", ["WGS84", "GCJ-02", "BD09"], key="poly_from")
    with col2:
        to_sys = st.selectbox("Target Coordinate System", ["WGS84", "GCJ-02", "BD09"], key="poly_to")

    def transform_polygon(coords, func):
        return [[func(lat, lon) for lat, lon in ring] for ring in coords]

    if uploaded_file is not None:
        try:
            polygons = []
            name = uploaded_file.name.lower()
            if name.endswith("geojson"):
                data = json.load(uploaded_file)
                for feature in data["features"]:
                    geom = feature["geometry"]
                    if geom["type"].lower() == "polygon":
                        coords = [[(lat, lon) for lon, lat in ring] for ring in geom["coordinates"]]
                        polygons.append(coords)
            elif name.endswith("kml"):
                root = ET.fromstring(uploaded_file.read().decode("utf-8"))
                ns = {"kml": "http://www.opengis.net/kml/2.2"}
                for coord_text in root.findall(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", ns):
                    raw = coord_text.text.strip().split()
                    ring = [(float(p.split(",")[1]), float(p.split(",")[0])) for p in raw]
                    polygons.append([ring])
            elif name.endswith("kmz"):
                with zipfile.ZipFile(BytesIO(uploaded_file.read())) as kmz:
                    for fname in kmz.namelist():
                        if fname.endswith(".kml"):
                            kml_data = kmz.read(fname).decode("utf-8")
                            root = ET.fromstring(kml_data)
                            ns = {"kml": "http://www.opengis.net/kml/2.2"}
                            for coord_text in root.findall(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", ns):
                                raw = coord_text.text.strip().split()
                                ring = [(float(p.split(",")[1]), float(p.split(",")[0])) for p in raw]
                                polygons.append([ring])

            if polygons:
                func = transform_map.get((from_sys, to_sys), lambda x, y: (x, y))
                converted = [transform_polygon(poly, func) for poly in polygons]

                m = folium.Map(tiles="CartoDB positron")
                for poly, conv in zip(polygons, converted):
                    folium.Polygon(locations=poly[0], color="blue").add_to(m)
                    folium.Polygon(locations=conv[0], color="green").add_to(m)
                m.fit_bounds(m.get_bounds())
                m.get_root().html.add_child(Element(legend_html))
                st_folium(m, width=700, height=500)
            else:
                st.warning("No valid polygons found in the uploaded file.")
        except Exception as e:
            st.error(f"Error processing file: {e}")
