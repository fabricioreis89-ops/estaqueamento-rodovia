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
    import io # Adicione este import no topo do arquivo

# ... (mantenha suas funções de ler_kml e gerar_estacas iguais)

if uploaded_file:
    linha = ler_linha_kml(uploaded_file)

    if linha is None:
        st.error("O KML não contém um LineString válido.")
        st.stop()

    df = gerar_estacas(linha, estaca_inicial, metro_inicial, estaca_final)

    st.success(f"{len(df)} estacas geradas")

    # ===============================
    # MAPA (MELHORADO)
    # ===============================
    view_state = pdk.ViewState(
        latitude=df["Latitude"].mean(),
        longitude=df["Longitude"].mean(),
        zoom=12 # Aumentei um pouco o zoom inicial
    )

    # Camada do traçado original (Linha azul fina)
    line_layer = pdk.Layer(
        "PathLayer",
        data=[{"path": list(linha.coords)}],
        get_path="path",
        get_color=[0, 100, 255, 150], # Azul com transparência
        get_width=3
    )

    # Camada das estacas (Pontos vermelhos)
    point_layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position="[Longitude, Latitude]",
        get_radius=5,           # Raio real em metros
        radius_min_pixels=3,    # Garante que o ponto não suma ao tirar o zoom
        radius_max_pixels=10,   # Garante que o ponto não vire um borrão ao dar zoom
        get_fill_color=[255, 0, 0],
        pickable=True
    )

    st.pydeck_chart(pdk.Deck(
        layers=[line_layer, point_layer],
        initial_view_state=view_state,
        tooltip={"text": "Estaca: {Estaca}\nUTM E: {UTM_E:.2f}\nUTM N: {UTM_N:.2f}"}
    ))

    # ===============================
    # DOWNLOADS (CORRIGIDO)
    # ===============================
    # Criar buffer para o Excel
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    
    st.download_button(
        label="📥 Baixar planilha das Estacas (Excel)",
        data=buffer.getvalue(),
        file_name="estaqueamento_rodovia.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
