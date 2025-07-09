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

# [Point Conversion Block remains unchanged]

elif mode == "Polygon Conversion":
    st.subheader("Polygon Coordinate Conversion")
    st.markdown("Upload a KML, KMZ, or GeoJSON file to convert its coordinates between systems.")
    uploaded_file = st.file_uploader("Upload File", type=["kml", "kmz", "geojson", "json"])

    col1, col2 = st.columns(2)
    with col1:
        from_sys = st.selectbox("Source Coordinate System", ["WGS84", "GCJ-02", "BD09"], key="poly_from")
    with col2:
        to_sys = st.selectbox("Target Coordinate System", ["WGS84", "GCJ-02", "BD09"], key="poly_to")

    if uploaded_file:
        file_type = uploaded_file.name.split('.')[-1].lower()
        coords_list = []

        try:
            if file_type in ["geojson", "json"]:
                geojson = json.load(uploaded_file)
                features = geojson["features"] if geojson["type"] == "FeatureCollection" else [geojson]
                for feature in features:
                    geom = feature["geometry"]
                    if geom["type"].lower() == "polygon":
                        coords_list.append(geom["coordinates"][0])
            elif file_type == "kml":
                text = uploaded_file.read().decode("utf-8")
                ns = {'kml': 'http://www.opengis.net/kml/2.2'}
                root = ET.fromstring(text)
                for coord_text in root.findall(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", ns):
                    raw_coords = coord_text.text.strip().split()
                    coords = []
                    for pair in raw_coords:
                        lon, lat = map(float, pair.split(",")[:2])
                        coords.append([lon, lat])
                    coords_list.append(coords)
            elif file_type == "kmz":
                with zipfile.ZipFile(BytesIO(uploaded_file.read())) as z:
                    for name in z.namelist():
                        if name.endswith(".kml"):
                            text = z.read(name).decode("utf-8")
                            ns = {'kml': 'http://www.opengis.net/kml/2.2'}
                            root = ET.fromstring(text)
                            for coord_text in root.findall(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", ns):
                                raw_coords = coord_text.text.strip().split()
                                coords = []
                                for pair in raw_coords:
                                    lon, lat = map(float, pair.split(",")[:2])
                                    coords.append([lon, lat])
                                coords_list.append(coords)

            if coords_list:
                func = transform_map.get((from_sys, to_sys), lambda x, y: (x, y))
                m = folium.Map(tiles="CartoDB positron")
                transformed_polygons = []

                for coords in coords_list:
                    original = [(lat, lon) for lon, lat in coords]
                    transformed = [func(lat, lon) for lat, lon in original]
                    folium.Polygon(locations=original, color="blue", fill=False).add_to(m)
                    folium.Polygon(locations=transformed, color="green", fill=True, fill_opacity=0.3).add_to(m)
                    transformed_polygons.append([(lon, lat) for lat, lon in transformed])

                m.fit_bounds(m.get_bounds())
                m.get_root().html.add_child(Element(legend_html))
                st_folium(m, width=700, height=500)

                # KML and GeoJSON export
                kml = simplekml.Kml()
                for i, poly in enumerate(transformed_polygons):
                    kml.newpolygon(name=f"Polygon {i+1}", outerboundaryis=poly)
                geojson_data = {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [[list(coord) for coord in poly]]
                            },
                            "properties": {}
                        } for poly in transformed_polygons
                    ]
                }
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button("Download KML", kml.kml().encode("utf-8"), file_name="converted_polygons.kml", mime="application/vnd.google-earth.kml+xml", use_container_width=True)
                with col2:
                    st.download_button("Download GeoJSON", json.dumps(geojson_data, indent=2).encode("utf-8"), file_name="converted_polygons.geojson", mime="application/geo+json", use_container_width=True)

        except Exception as e:
            st.error(f"Error processing file: {e}")
