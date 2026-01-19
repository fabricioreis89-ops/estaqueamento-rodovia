import streamlit as st
import pandas as pd
import numpy as np
from pyproj import Transformer
from fastkml import kml
from shapely.geometry import LineString
import pydeck as pdk

st.set_page_config(layout="wide")
st.title("Estaqueamento Automático de Rodovia a partir de KML")

# =========================
# FUNÇÕES AUXILIARES
# =========================

def ler_linha_kml(uploaded_file):
    conteudo = uploaded_file.read().decode("utf-8")

    k = kml.KML()
    k.from_string(conteudo.encode("utf-8"))

    documentos = list(k.features())

    for doc in documentos:
        elementos = list(doc.features())

        for elem in elementos:
            # Caso exista Folder
            if hasattr(elem, "features"):
                for placemark in elem.features():
                    if isinstance(placemark.geometry, LineString):
                        return placemark.geometry
            else:
                # Caso o Placemark esteja direto no Document
                if isinstance(elem.geometry, LineString):
                    return elem.geometry

    return None


def latlon_para_utm(lat, lon):
    zona = int((lon + 180) / 6) + 1
    hemisferio = "south" if lat < 0 else "north"
    epsg = f"326{zona}" if hemisferio == "north" else f"327{zona}"

    transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    x, y = transformer.transform(lon, lat)
    return x, y, epsg


def utm_para_latlon(x, y, epsg):
    transformer = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
    lon, lat = transformer.transform(x, y)
    return lat, lon


def gerar_estacas(coords_latlon, estaca_inicial_num, estaca_inicial_m, espacamento=20):
    # Converter todo o eixo para UTM
    x0, y0, epsg = latlon_para_utm(coords_latlon[0][1], coords_latlon[0][0])

    coords_utm = []
    for lon, lat in coords_latlon:
        x, y, _ = latlon_para_utm(lat, lon)
        coords_utm.append((x, y))

    linha = LineString(coords_utm)
    comprimento_total = linha.length

    estacas = []

    dist_atual = -estaca_inicial_m
    numero_estaca = estaca_inicial_num

    while dist_atual <= comprimento_total:
        ponto = linha.interpolate(max(dist_atual, 0))
        x, y = ponto.x, ponto.y
        lat, lon = utm_para_latlon(x, y, epsg)

        sufixo = int(round(estaca_inicial_m + dist_atual)) % espacamento
        estaca_label = f"E{numero_estaca}+{sufixo:02d}"

        estacas.append({
            "Estaca": estaca_label,
            "Latitude": lat,
            "Longitude": lon
        })

        dist_atual += espacamento
        numero_estaca += 1

    return pd.DataFrame(estacas)


# =========================
# INTERFACE STREAMLIT
# =========================

uploaded_file = st.file_uploader("Envie o arquivo KML do eixo da rodovia", type=["kml"])

if uploaded_file:
    linha = ler_linha_kml(uploaded_file)

    if linha is None:
        st.error("O KML não contém um LineString válido.")
        st.stop()

    coords = list(linha.coords)

    st.success("Traçado carregado com sucesso.")

    col1, col2 = st.columns(2)

    with col1:
        estaca_inicial_num = st.number_input(
            "Número da estaca inicial (ex: 853)",
            min_value=0,
            value=853,
            step=1
        )

    with col2:
        estaca_inicial_m = st.number_input(
            "Avanço inicial em metros (ex: 16)",
            min_value=0,
            max_value=19,
            value=16,
            step=1
        )

    if st.button("Gerar estaqueamento"):
        df_estacas = gerar_estacas(
            coords,
            estaca_inicial_num,
            estaca_inicial_m
        )

        st.subheader("Tabela de Estacas")
        st.dataframe(df_estacas, use_container_width=True)

        # =========================
        # MAPA INTERATIVO
        # =========================

        linha_lat = [lat for lon, lat in coords]
        linha_lon = [lon for lon, lat in coords]

        view_state = pdk.ViewState(
            latitude=df_estacas["Latitude"].mean(),
            longitude=df_estacas["Longitude"].mean(),
            zoom=9,
            pitch=0
        )

        eixo_layer = pdk.Layer(
            "PathLayer",
            data=[{"path": list(zip(linha_lon, linha_lat))}],
            get_path="path",
            get_width=5,
            get_color=[0, 0, 255]
        )

        estaca_layer = pdk.Layer(
            "ScatterplotLayer",
            data=df_estacas,
            get_position="[Longitude, Latitude]",
            get_radius=15,
            radius_units="meters",
            get_fill_color=[255, 0, 0, 180],
            pickable=True
        )

        deck = pdk.Deck(
            layers=[eixo_layer, estaca_layer],
            initial_view_state=view_state,
            tooltip={"text": "{Estaca}"}
        )

        st.subheader("Mapa Interativo")
        st.pydeck_chart(deck)

