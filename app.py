import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
from shapely.geometry import LineString
from lxml import etree
from pyproj import Transformer
import io  # Necessário para o download do Excel

# ===============================
# FUNÇÃO: LER LINHA DO KML (CORRIGIDA)
# ===============================
def ler_linha_kml(uploaded_file):
    try:
        conteudo = uploaded_file.read()
        # Usamos um parser que recupera erros de sintaxe comuns em KMLs
        parser = etree.XMLParser(recover=True, encoding='utf-8')
        tree = etree.fromstring(conteudo, parser=parser)

        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        coords_text = tree.xpath(".//kml:LineString/kml:coordinates", namespaces=ns)

        if not coords_text:
            return None

        coords = []
        # Limpeza para evitar erros de espaços ou quebras de linha
        raw_coords = coords_text[0].text.strip().split()
        for ponto in raw_coords:
            partes = ponto.split(",")
            if len(partes) >= 2:
                lon, lat = float(partes[0]), float(partes[1])
                coords.append((lon, lat))

        return LineString(coords)
    except Exception as e:
        st.error(f"Erro ao processar o XML: {e}")
        return None


# ===============================
# FUNÇÃO: GERAR ESTACAS
# ===============================
def gerar_estacas(linha, estaca_inicial, metro_inicial, estaca_final, espacamento=20):
    lon0, lat0 = linha.coords[0]
    zona = int((lon0 + 180) / 6) + 1
    epsg = 32700 + zona if lat0 < 0 else 32600 + zona

    proj = Transformer.from_crs(4326, epsg, always_xy=True)
    inv = Transformer.from_crs(epsg, 4326, always_xy=True)

    linha_utm = LineString([proj.transform(*c) for c in linha.coords])

    # Cálculo da distância acumulada
    inicio_metros = metro_inicial
    # A distância final é baseada na diferença de estacas * 20m
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
            "Latitude": lat,
            "Longitude": lon,
            "UTM_E": ponto.x,
            "UTM_N": ponto.y
        })

    return pd.DataFrame(dados)


# ===============================
# STREAMLIT APP
# ===============================
st.set_page_config(layout="wide", page_title="Estaqueamento Rodoviário")
st.title("Estaqueamento Automático de Rodovias")

uploaded_file = st.file_uploader("Carregue o arquivo KML da rodovia", type="kml")

col1, col2, col3 = st.columns(3)
with col1:
    est_ini = st.number_input("Estaca inicial", value=853)
with col2:
    met_ini = st.number_input("Metro inicial (+)", value=16)
with col3:
    est_fim = st.number_input("Estaca final", value=2777)

if uploaded_file:
    linha = ler_linha_kml(uploaded_file)

    if linha:
        df = gerar_estacas(linha, est_ini, met_ini, est_fim)
        st.success(f"{len(df)} estacas geradas com sucesso!")

        # ===============================
        # MAPA (MELHORADO)
        # ===============================
        view_state = pdk.ViewState(
            latitude=df["Latitude"].mean(),
            longitude=df["Longitude"].mean(),
            zoom=10
        )

        # Camada das estacas com tamanho fixo em pixels para evitar o "borrão"
        point_layer = pdk.Layer(
            "ScatterplotLayer",
            data=df,
            get_position="[Longitude, Latitude]",
            get_radius=10,
            radius_min_pixels=2, # Mantém o ponto pequeno mesmo com zoom out
            radius_max_pixels=5,
            get_fill_color=[255, 0, 0],
            pickable=True
        )

        st.pydeck_chart(pdk.Deck(
            layers=[point_layer],
            initial_view_state=view_state,
            tooltip={"text": "{Estaca}"}
        ))

        # ===============================
        # DOWNLOAD EXCEL
        # ===============================
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        
        st.download_button(
            label="📥 Baixar Planilha das Estacas",
            data=output.getvalue(),
            file_name="estaqueamento.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("Não foi possível extrair coordenadas do arquivo KML.")
