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

# UI logic for point conversion and polygon conversion modes follows below

if mode == "Point Conversion":
    with st.form(key="point_form"):
        input_str = st.text_input("Enter coordinates (lat, lon):", value="")
        col1, col2 = st.columns(2)
        with col1:
            source_crs = st.selectbox("Source CRS", ["WGS84", "GCJ-02", "BD09"])
        with col2:
            target_crs = st.selectbox("Target CRS", ["WGS84", "GCJ-02", "BD09"])
        convert = st.form_submit_button("Convert Coordinates")

    if convert:
        if input_str.strip():
            try:
                lat_str, lon_str = re.split(r",|\s+", input_str.strip())
                lat, lon = float(lat_str), float(lon_str)
                transform_fn = transform_map.get((source_crs, target_crs))
                if transform_fn:
                    conv_lat, conv_lon = transform_fn(lat, lon)
                    st.success("Converted Coordinates:")
                    st.code(f"{conv_lat:.8f}, {conv_lon:.8f}")

                    m = folium.Map(location=[lat, lon], zoom_start=12, control_scale=True)
                    folium.Marker(location=[lat, lon], popup="Input", icon=folium.Icon(color="blue")).add_to(m)
                    folium.Marker(location=[conv_lat, conv_lon], popup="Converted", icon=folium.Icon(color="green")).add_to(m)
                    m.get_root().html.add_child(Element(legend_html))
                    st_folium(m, height=400)
                else:
                    st.warning("Source and target CRS are the same or unsupported.")
            except Exception as e:
                st.error(f"Invalid input format. Please enter in 'lat, lon' format. Error: {e}")
        else:
            st.warning("Please input coordinates.")

elif mode == "Polygon Conversion":
    uploaded_file = st.file_uploader("Upload Polygon File (KML, KMZ, or GeoJSON)", type=["kml", "kmz", "geojson", "json"])
    col1, col2 = st.columns(2)
    with col1:
        source_crs = st.selectbox("Source CRS", ["WGS84", "GCJ-02", "BD09"], key="poly_source")
    with col2:
        target_crs = st.selectbox("Target CRS", ["WGS84", "GCJ-02", "BD09"], key="poly_target")

    if uploaded_file:
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

        def extract_coords_from_geojson(json_obj):
            polygons = []
            features = json_obj["features"] if json_obj["type"] == "FeatureCollection" else [json_obj]
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
            return polygons

        polygons = []
        ext = uploaded_file.name.split('.')[-1].lower()
        try:
            if ext == "kml":
                polygons = extract_coords_from_kml_string(uploaded_file.read().decode("utf-8"))
            elif ext == "kmz":
                polygons = extract_coords_from_kmz(uploaded_file.read())
            elif ext in ["geojson", "json"]:
                geojson = json.load(uploaded_file)
                polygons = extract_coords_from_geojson(geojson)
        except Exception as e:
            st.error(f"Error reading file: {e}")

        if polygons:
            transform_fn = transform_map.get((source_crs, target_crs))
            if transform_fn:
                converted_polygons = []
                for poly in polygons:
                    converted_polygons.append([transform_fn(lat, lon) for lat, lon in poly])

                st.success("Polygon successfully converted.")

                m = folium.Map()
                for poly in converted_polygons:
                    folium.Polygon(locations=poly, color="green", fill=True).add_to(m)
                m.get_root().html.add_child(Element(legend_html))
                st_folium(m, height=400)

                # Allow KML or GeoJSON download
                kml = simplekml.Kml()
                for i, poly in enumerate(converted_polygons):
                    kml.newpolygon(name=f"Polygon {i+1}", outerboundaryis=[(lon, lat) for lat, lon in poly])
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
                    st.download_button("Download KML", kml.kml().encode("utf-8"), file_name="converted_polygon.kml")
                with col2:
                    st.download_button("Download GeoJSON", json.dumps(geojson_data, indent=2).encode("utf-8"), file_name="converted_polygon.geojson")
            else:
                st.warning("Unsupported conversion pair selected.")
