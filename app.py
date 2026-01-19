import streamlit as st
from xml.etree import ElementTree as ET
from shapely.geometry import LineString, Point
import geopandas as gpd
import pydeck as pdk
import pandas as pd
import math

# ============================
# LEITURA ROBUSTA DO KML
# ============================
def ler_eixo_kml(uploaded_file):
    tree = ET.parse(uploaded_file)
    root = tree.getroot()
    ns = {"kml": "http://www.opengis.net/kml/2.2"}

    linestring = root.find(".//kml:LineString", ns)
    if linestring is None:
        raise ValueError("O KML não contém LineString.")

    coords_text = linestring.find("kml:coordinates", ns).text.strip()

    coords = []
    for coord in coords_text.split():
        lon, lat, *_ = map(float, coord.split(","))
        coords.append((lon, lat))

    return LineString(coords)

# ============================
# ESTAQUEAMENTO
# ============================
def gerar_estacas(linha, estaca_inicial_m, intervalo=20):
    gdf = gpd.GeoDataFrame(geometry=[linha], crs="EPSG:4326")
    gdf_utm = gdf.to_crs(gdf.estimate_utm_crs())

    linha_utm = gdf_utm.geometry.iloc[0]
    comprimento = linha_utm.length

    estacas = []
    pos = 0

    while pos <= comprimento:
        ponto = linha_utm.interpolate(pos)
        ponto_geo = gpd.GeoSeries([ponto], crs=gdf_utm.crs).to_crs(4326).iloc[0]

        estaca_m = estaca_inicial_m + pos
        numero = int(estaca_m // 20)
        resto = estaca_m % 20

        estacas.append({
            "Estaca": f"E{numero}+{resto:.2f}",
            "Latitude": ponto_geo.y,
            "Longitude": ponto_geo.x
        })

        pos += intervalo

    return pd.DataFrame(estacas)

# ============================
# INTERFACE STREAMLIT
# ============================
st.set_page_config(layout="wide")
st.title("📍 Mapa Interativo com Estaqueamento")

uploaded_file = st.file_uploader("Envie o arquivo KML do eixo", type=["kml"])

estaca_inicial = st.number_input(
    "Estaca inicial (em metros, ex: E853+16 = 17076)",
    value=17076.0,
    step=1.0
)

if uploaded_file:
    try:
        eixo = ler_eixo_kml(uploaded_file)

        # Gera estacas
        df_estacas = gerar_estacas(eixo, estaca_inicial)

        # ============================
        # MAPA INTERATIVO (SEM MAPBOX)
        # ============================
        path_layer = pdk.Layer(
            "PathLayer",
            data=[{"path": list(eixo.coords)}],
            get_path="path",
            get_width=4,
            width_scale=10,
            width_min_pixels=2
        )

        point_layer = pdk.Layer(
            "ScatterplotLayer",
            data=df_estacas,
            get_position="[Longitude, Latitude]",
            get_radius=3,
            pickable=True
        )

        centro_lon = eixo.centroid.x
        centro_lat = eixo.centroid.y

        view_state = pdk.ViewState(
            longitude=centro_lon,
            latitude=centro_lat,
            zoom=11
        )

        st.pydeck_chart(
            pdk.Deck(
                layers=[path_layer, point_layer],
                initial_view_state=view_state,
                map_style=None  # OpenStreetMap
            )
        )

        # ============================
        # TABELA TÉCNICA
        # ============================
        st.subheader("📋 Estaqueamento")
        st.dataframe(df_estacas, use_container_width=True)

    except Exception as e:
        st.error(f"Erro: {e}")
