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
import simplekml

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

# --- Coordinate transformation functions ---
def out_of_china(lat, lon):
    return not (73.66 < lon < 135.05 and 3.86 < lat < 53.55)

def transform_lat(x, y):
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + \
          0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * PI) + 20.0 *
            math.sin(2.0 * x * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * PI) + 40.0 *
            math.sin(y / 3.0 * PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * PI) + 320 *
            math.sin(y * PI / 30.0)) * 2.0 / 3.0
    return ret

def transform_lon(x, y):
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + \
          0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * PI) + 20.0 *
            math.sin(2.0 * x * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * PI) + 40.0 *
            math.sin(x / 3.0 * PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * PI) + 300.0 *
            math.sin(x / 30.0 * PI)) * 2.0 / 3.0
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
    glat, glon = wgs84_to_gcj02(lat, lon)
    dlat = glat - lat
    dlon = glon - lon
    return lat - dlat, lon - dlon

def gcj02_to_bd09(lat, lon):
    x = lon
    y = lat
    z = math.sqrt(x * x + y * y) + 0.00002 * math.sin(y * PI * 3000.0 / 180.0)
    theta = math.atan2(y, x) + 0.000003 * math.cos(x * PI * 3000.0 / 180.0)
    bd_lon = z * math.cos(theta) + 0.0065
    bd_lat = z * math.sin(theta) + 0.006
    return bd_lat, bd_lon

def bd09_to_gcj02(lat, lon):
    x = lon - 0.0065
    y = lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * PI * 3000.0 / 180.0)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * PI * 3000.0 / 180.0)
    gg_lon = z * math.cos(theta)
    gg_lat = z * math.sin(theta)
    return gg_lat, gg_lon

def wgs84_to_bd09(lat, lon):
    gcj_lat, gcj_lon = wgs84_to_gcj02(lat, lon)
    return gcj02_to_bd09(gcj_lat, gcj_lon)

def bd09_to_wgs84(lat, lon):
    gcj_lat, gcj_lon = bd09_to_gcj02(lat, lon)
    return gcj02_to_wgs84(gcj_lat, gcj_lon)

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

# Session state
if "converted_coords" not in st.session_state:
    st.session_state["converted_coords"] = None
if "input_coords" not in st.session_state:
    st.session_state["input_coords"] = None

# --- Point Conversion UI ---
if mode == "Point Conversion":
    col1, col2 = st.columns(2)
    with col1:
        src_crs = st.selectbox("Source Coordinate System", ["WGS84", "GCJ-02", "BD09"], key="point_src")
    with col2:
        tgt_crs = st.selectbox("Target Coordinate System", ["WGS84", "GCJ-02", "BD09"], key="point_tgt")

    coord_input = st.text_input("Enter Coordinates (latitude, longitude)", placeholder="e.g. 39.9042, 116.4074")
    convert_btn = st.button("Convert Coordinates", use_container_width=True)

    if convert_btn:
        if coord_input:
            try:
                lat, lon = map(float, re.findall(r"[-+]?\d*\.?\d+", coord_input))
                transform = transform_map.get((src_crs, tgt_crs))
                if transform:
                    new_lat, new_lon = transform(lat, lon)
                    st.session_state["input_coords"] = (lat, lon)
                    st.session_state["converted_coords"] = (new_lat, new_lon)
                else:
                    st.warning("No transformation defined for selected CRS pair.")
                    st.session_state["converted_coords"] = None
            except Exception as e:
                st.session_state["converted_coords"] = None
                st.session_state["input_coords"] = None
                st.error(f"Invalid input format. Please enter in 'lat, lon' format. Error: {e}")
        else:
            st.warning("Please input coordinates.")
            st.session_state["converted_coords"] = None
            st.session_state["input_coords"] = None

    if st.session_state["converted_coords"] and st.session_state["input_coords"]:
        lat, lon = st.session_state["input_coords"]
        new_lat, new_lon = st.session_state["converted_coords"]

        st.subheader("Converted Coordinates")
        st.code(f"{new_lat:.6f}, {new_lon:.6f}")

        m = folium.Map(location=[lat, lon], zoom_start=12)
        folium.Marker([lat, lon], tooltip="Input", icon=folium.Icon(color='blue')).add_to(m)
        folium.Marker([new_lat, new_lon], tooltip="Converted", icon=folium.Icon(color='green')).add_to(m)
        m.get_root().html.add_child(Element(legend_html))
        st_folium(m, width=700, height=400)

# --- Polygon Conversion UI ---
elif mode == "Polygon Conversion":
    col1, col2 = st.columns(2)
    with col1:
        src_crs = st.selectbox("Source Coordinate System", ["WGS84", "GCJ-02", "BD09"], key="poly_src")
    with col2:
        tgt_crs = st.selectbox("Target Coordinate System", ["WGS84", "GCJ-02", "BD09"], key="poly_tgt")

    uploaded_file = st.file_uploader("Upload KML, KMZ, or GeoJSON", type=["kml", "kmz", "geojson"])

    if uploaded_file:
        try:
            polygons = []
            if uploaded_file.name.endswith(".kmz"):
                with zipfile.ZipFile(uploaded_file) as kmz:
                    for name in kmz.namelist():
                        if name.endswith(".kml"):
                            kml_string = kmz.read(name).decode("utf-8")
                            break
            elif uploaded_file.name.endswith(".kml"):
                kml_string = uploaded_file.read().decode("utf-8")
            elif uploaded_file.name.endswith(".geojson"):
                geojson = json.load(uploaded_file)
                kml_string = None

            if kml_string:
                ns = {'kml': 'http://www.opengis.net/kml/2.2'}
                root = ET.fromstring(kml_string)
                for coord_text in root.findall(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", ns):
                    coords = []
                    raw_coords = coord_text.text.strip().split()
                    for coord in raw_coords:
                        parts = coord.split(',')
                        if len(parts) >= 2:
                            lon, lat = map(float, parts[:2])
                            coords.append((lat, lon))
                    if coords:
                        polygons.append(coords)
            elif geojson:
                features = geojson["features"] if geojson["type"] == "FeatureCollection" else [geojson]
                for feature in features:
                    geom = feature["geometry"]
                    if geom["type"] == "Polygon":
                        coords = geom["coordinates"][0]
                        polygons.append([(lat, lon) for lon, lat in coords])
                    elif geom["type"] == "MultiPolygon":
                        for part in geom["coordinates"]:
                            coords = part[0]
                            polygons.append([(lat, lon) for lon, lat in coords])

            if polygons:
                transform = transform_map.get((src_crs, tgt_crs))
                if not transform:
                    st.warning("No transformation defined for selected CRS pair.")
                else:
                    converted_polygons = [[transform(lat, lon) for lat, lon in poly] for poly in polygons]

                    m = folium.Map(tiles="CartoDB positron")
                    for poly in polygons:
                        folium.Polygon(locations=poly, color="blue", fill=True).add_to(m)
                    for poly in converted_polygons:
                        folium.Polygon(locations=poly, color="green", fill=True).add_to(m)
                    m.get_root().html.add_child(Element(legend_html))
                    st_folium(m, width=700, height=400)

                    kml = simplekml.Kml()
                    for i, poly in enumerate(converted_polygons):
                        kml_coords = [(lon, lat) for lat, lon in poly]
                        kml.newpolygon(name=f"Polygon {i+1}", outerboundaryis=kml_coords)

                    geojson_data = {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {
                                    "type": "Polygon",
                                    "coordinates": [[(lon, lat) for lat, lon in poly]]
                                },
                                "properties": {}
                            } for poly in converted_polygons
                        ]
                    }

                    col1, col2 = st.columns(2)
                    with col1:
                        st.download_button("Download KML", kml.kml().encode("utf-8"), file_name="converted_polygons.kml")
                    with col2:
                        st.download_button("Download GeoJSON", json.dumps(geojson_data).encode("utf-8"), file_name="converted_polygons.geojson")

        except Exception as e:
            st.error(f"Error processing file: {e}")
