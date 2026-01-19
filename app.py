import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
from shapely.geometry import LineString
from lxml import etree
from pyproj import Transformer

# ===============================
# FUNÇÃO: LER LINHA DO KML
# ===============================
def ler_linha_kml(uploaded_file):
    conteudo = uploaded_file.read()
    tree = etree.fromstring(conteudo)

    ns = {"kml": "http://www.opengis.net/kml/2.2"}
    coords_text = tree.xpath(".//kml:LineString/kml:coordinates", namespaces=ns)

    if not coords_text:
        return None

    coords = []
    for linha in coords_text[0].text.strip().split():
        lon, lat, *_ = map(float, linha.split(","))
        coords.append((lon, lat))

    return LineString(coords)


# ===============================
# FUNÇÃO: GERAR ESTACAS
# ===============================
def gerar_estacas(
    linha,
    estaca_inicial,
    metro_inicial,
    estaca_final,
    espacamento=20
):
    # Transformador geográfico -> UTM automático
    lon0, lat0 = linha.coords[0]
    zona = int((lon0 + 180) / 6) + 1
    epsg = 32700 + zona if lat0 < 0 else 32600 + zona

    proj = Transformer.from_crs(4326, epsg, always_xy=True)
    inv = Transformer.from_crs(epsg, 4326, always_xy=True)

    linha_utm = LineString([proj.transform(*c) for c in linha.coords])

    comprimento_total = linha_utm.length
    inicio_metros = metro_inicial
    fim_metros = (estaca_final - estaca_inicial) * 20

    distancias = np.arange(inicio_metros, fim_metros + 0.01, espacamento)

    dados = []

    for d in distancias:
        ponto = linha_utm.interpolate(d)
        lon, lat = inv.transform(ponto.x, ponto.y)

        estaca_num = estaca_inicial + int(d // 20)
        resto = int(d % 20)

        estaca_txt = f"E{estaca_num}+{resto:02d}"

        dados.append({
            "Estaca": estaca_txt,
            "Estaca_Num": estaca_num,
            "Metro": resto,
            "Latitude": lat,
            "Longitude": lon,
            "UTM_E": ponto.x,
            "UTM_N": ponto.y
        })

    return pd.DataFrame(dados)


# ===============================
# STREAMLIT APP
# ===============================
st.set_page_config(layout="wide")
st.title("Estaqueamento Automático de Rodovias")

uploaded_file = st.file_uploader("Carregue o arquivo KML da rodovia", type="kml")

col1, col2, col3 = st.columns(3)

with col1:
    estaca_inicial = st.number_input("Número da estaca inicial", value=853)

with col2:
    metro_inicial = st.number_input("Metro inicial (ex: +16)", value=16)

with col3:
    estaca_final = st.number_input("Número da estaca final", value=2777)

if uploaded_file:
    linha = ler_linha_kml(uploaded_file)

    if linha is None:
        st.error("O KML não contém um LineString válido.")
        st.stop()

    df = gerar_estacas(
        linha,
        estaca_inicial,
        metro_inicial,
        estaca_final
    )

    st.success(f"{len(df)} estacas geradas")

    # ===============================
    # MAPA
    # ===============================
    view_state = pdk.ViewState(
        latitude=df["Latitude"].mean(),
        longitude=df["Longitude"].mean(),
        zoom=9
    )

    line_layer = pdk.Layer(
        "PathLayer",
        data=[{"path": list(linha.coords)}],
        get_path="path",
        get_color=[0, 0, 255],
        get_width=5
    )

    point_layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position="[Longitude, Latitude]",
        get_radius=10,
        radius_units="meters",
        get_fill_color=[255, 0, 0],
        pickable=True
    )

    deck = pdk.Deck(
        layers=[line_layer, point_layer],
        initial_view_state=view_state,
        tooltip={"text": "{Estaca}"}
    )

    st.pydeck_chart(deck)

    # ===============================
    # DOWNLOADS
    # ===============================
    st.download_button(
        "Baixar planilha Excel",
        df.to_excel(index=False),
        file_name="estaqueamento.xlsx"
    )
