import streamlit as st
from xml.etree import ElementTree as ET
from shapely.geometry import LineString
import geopandas as gpd
import pydeck as pdk

# ============================
# FUNÇÃO ROBUSTA PARA LER KML
# ============================
def ler_eixo_kml(uploaded_file):
    tree = ET.parse(uploaded_file)
    root = tree.getroot()

    # Namespace padrão KML
    ns = {"kml": "http://www.opengis.net/kml/2.2"}

    # Procura QUALQUER LineString no arquivo
    linestring = root.find(".//kml:LineString", ns)

    if linestring is None:
        raise ValueError("O KML não contém LineString.")

    coords_text = linestring.find("kml:coordinates", ns).text.strip()

    coords = []
    for coord in coords_text.split():
        lon, lat, *_ = map(float, coord.split(","))
        coords.append((lon, lat))

    if len(coords) < 2:
        raise ValueError("LineString inválida (poucos pontos).")

    return LineString(coords)

# ============================
# INTERFACE STREAMLIT
# ============================
st.set_page_config(page_title="Mapa Interativo - Eixo de Obra", layout="wide")

st.title("📍 Mapa Interativo a partir de KML")
st.markdown("Upload de **KML com eixo (LineString)** exportado do Google Earth.")

uploaded_file = st.file_uploader("Envie o arquivo KML", type=["kml"])

if uploaded_file:
    try:
        eixo = ler_eixo_kml(uploaded_file)

        # Converte para GeoDataFrame
        gdf = gpd.GeoDataFrame(
            geometry=[eixo],
            crs="EPSG:4326"
        )

        # Comprimento aproximado em km (geodésico simples)
        gdf_proj = gdf.to_crs(epsg=3857)
        comprimento_km = gdf_proj.length.iloc[0] / 1000

        st.success(f"✅ Eixo carregado com sucesso")
        st.metric("Comprimento aproximado do eixo", f"{comprimento_km:.2f} km")

        # Prepara dados para o mapa
        coords = list(eixo.coords)
        data = [{"lon": c[0], "lat": c[1]} for c in coords]

        # Centralização do mapa
        centro_lon = sum(c[0] for c in coords) / len(coords)
        centro_lat = sum(c[1] for c in coords) / len(coords)

        layer = pdk.Layer(
            "PathLayer",
            data=[{
                "path": [[c[0], c[1]] for c in coords]
            }],
            get_path="path",
            get_width=5,
            width_scale=10,
            pickable=True
        )

        view_state = pdk.ViewState(
            longitude=centro_lon,
            latitude=centro_lat,
            zoom=11,
            pitch=0
        )

        st.pydeck_chart(
            pdk.Deck(
                layers=[layer],
                initial_view_state=view_state,
                map_style="mapbox://styles/mapbox/light-v9"
            )
        )

    except Exception as e:
        st.error(f"❌ Erro ao processar o KML: {e}")

