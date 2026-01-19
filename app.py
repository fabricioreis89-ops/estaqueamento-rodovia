import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from shapely.geometry import LineString
from pyproj import Transformer
from fastkml import kml
import math
import io

st.set_page_config(layout="wide")
st.title("Estaqueamento Automático de Rodovia")

# ==============================
# FUNÇÕES
# ==============================

def ler_eixo_kml(uploaded_file):
    k = kml.KML()
    k.from_string(uploaded_file.read())

    for feature in k.features():
        for sub in feature.features():
            if hasattr(sub.geometry, "coords"):
                return LineString(sub.geometry.coords)

    raise ValueError("O KML não contém uma linha (LineString).")


def calcular_utm_zone(lon):
    return int((lon + 180) / 6) + 1


def gerar_estacas(
    linha,
    estaca_inicial,
    offset_inicial,
    espacamento=20
):
    coords = list(linha.coords)
    lon0, lat0 = coords[0]

    zona = calcular_utm_zone(lon0)
    epsg = 32600 + zona

    transf = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    inv = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)

    coords_utm = [transf.transform(lon, lat) for lon, lat in coords]
    linha_utm = LineString(coords_utm)

    comprimento = linha_utm.length
    inicio = espacamento - offset_inicial if offset_inicial > 0 else 0

    dados = []
    numero_estaca = estaca_inicial
    dist = inicio

    if offset_inicial > 0:
        p0 = linha_utm.interpolate(0)
        lat, lon = inv.transform(p0.x, p0.y)
        dados.append([
            f"E{numero_estaca}+{offset_inicial}",
            numero_estaca,
            offset_inicial,
            p0.x,
            p0.y,
            lat,
            lon
        ])
        numero_estaca += 1

    while dist <= comprimento:
        p = linha_utm.interpolate(dist)
        lat, lon = inv.transform(p.x, p.y)

        dados.append([
            f"E{numero_estaca}",
            numero_estaca,
            0,
            p.x,
            p.y,
            lat,
            lon
        ])

        numero_estaca += 1
        dist += espacamento

    df = pd.DataFrame(
        dados,
        columns=[
            "Estaca",
            "Número",
            "Offset (m)",
            "UTM E",
            "UTM N",
            "Latitude",
            "Longitude"
        ]
    )

    return df, epsg


def gerar_mapa(df):
    m = folium.Map(
        location=[df.iloc[0]["Latitude"], df.iloc[0]["Longitude"]],
        zoom_start=14,
        tiles="OpenStreetMap"
    )

    for _, row in df.iterrows():
        folium.Marker(
            [row["Latitude"], row["Longitude"]],
            popup=row["Estaca"],
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m)

    return m


def gerar_kml(df):
    k = kml.KML()
    doc = kml.Document(ns=None, id="doc", name="Estacas", description="")
    k.append(doc)

    for _, row in df.iterrows():
        p = kml.Placemark(
            ns=None,
            id=row["Estaca"],
            name=row["Estaca"]
        )
        p.geometry = (row["Longitude"], row["Latitude"])
        doc.append(p)

    return k.to_string(prettyprint=True)

# ==============================
# INTERFACE
# ==============================

kml_file = st.file_uploader("📂 Envie o KML do eixo da rodovia", type=["kml"])

col1, col2, col3 = st.columns(3)

with col1:
    estaca_inicial = st.number_input("Número da estaca inicial", value=853, step=1)

with col2:
    offset_inicial = st.number_input("Offset da estaca inicial (m)", value=16.0, step=0.5)

with col3:
    espacamento = st.number_input("Espaçamento entre estacas (m)", value=20.0)

if kml_file:
    try:
        eixo = ler_eixo_kml(kml_file)
        df, epsg = gerar_estacas(eixo, estaca_inicial, offset_inicial, espacamento)

        st.success(f"Estacas geradas com sucesso | Sistema UTM EPSG:{epsg}")

        st.subheader("🗺️ Mapa Interativo")
        mapa = gerar_mapa(df)
        st_folium(mapa, width=1200, height=600)

        st.subheader("📊 Tabela de Estacas")
        st.dataframe(df)

        excel = io.BytesIO()
        df.to_excel(excel, index=False)
        excel.seek(0)

        st.download_button(
            "⬇️ Baixar Excel",
            excel,
            "estacas.xlsx"
        )

        kml_out = gerar_kml(df)

        st.download_button(
            "⬇️ Baixar KML",
            kml_out,
            "estacas.kml"
        )

    except Exception as e:
        st.error(str(e))
