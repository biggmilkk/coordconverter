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

# Conversion functions...
# (omitted for brevity - keep all existing functions intact)

# ... end of conversion functions and transform_map

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
    # [point conversion code remains unchanged]
    pass

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
