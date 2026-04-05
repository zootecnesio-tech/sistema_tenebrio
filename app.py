import streamlit as st
import psycopg2
from datetime import timedelta
import qrcode
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import pandas as pd
import hashlib

st.set_page_config(page_title="Sistema Tenebrio", layout="wide")

# ================= CONEXÃO =================
conn = psycopg2.connect(st.secrets["DATABASE_URL"])
cur = conn.cursor()

# ================= TABELAS =================
cur.execute("""
CREATE TABLE IF NOT EXISTS colonias (
    id SERIAL PRIMARY KEY,
    codigo TEXT UNIQUE,
    tipo TEXT,
    data_postura DATE,
    semana TEXT,
    colonia_mae INTEGER,
    peso_ovos REAL,
    peso_larvas REAL,
    peso_divisao REAL,
    peso_pupas REAL,
    data_colheita DATE,
    status TEXT
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE,
    senha TEXT,
    tipo TEXT
);
""")
conn.commit()

# ================= FUNÇÕES =================
def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

# 🔐 CRIAR ADMIN FIXO
cur.execute("SELECT * FROM usuarios WHERE username=%s", ("Lucas Vilella",))
if not cur.fetchone():
    cur.execute("""
        INSERT INTO usuarios (username, senha, tipo)
        VALUES (%s,%s,%s)
    """, ("Lucas Vilella", hash_senha("Luke#2107#"), "admin"))
    conn.commit()

def gerar_codigo_mae(data_postura, semana, colonia):
    return f"{data_postura.strftime('%Y%m%d')}-S{semana[0]}-M{colonia}"

def gerar_codigo_filha(data_postura, semana, colonia):
    cur.execute("""
        SELECT COUNT(*) FROM colonias
        WHERE data_postura=%s AND colonia_mae=%s AND tipo='FILHA'
    """, (data_postura, colonia))
    seq = cur.fetchone()[0] + 1
    return f"{data_postura.strftime('%Y%m%d')}-S{semana[0]}-M{colonia}-F{seq}"

# ================= LOGIN =================
def tela_login():
    st.title("🔐 Login")

    user = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        cur.execute("SELECT * FROM usuarios WHERE username=%s", (user,))
        dados = cur.fetchone()

        if dados and dados[2] == hash_senha(senha):
            st.session_state["logado"] = True
            st.session_state["tipo"] = dados[3]
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos")

if "logado" not in st.session_state:
    st.session_state["logado"] = False

if not st.session_state["logado"]:
    tela_login()
    st.stop()

# ================= APP =================
st.title("🐞 Sistema Tenebrio")

if st.button("🚪 Sair"):
    st.session_state.clear()
    st.rerun()

# 🔥 CAPTURA DO QR CODE
params = st.query_params
codigo_qr = params.get("codigo", "")

aba1, aba2 = st.tabs(["Operacional", "Dashboard"])

# ================= OPERACIONAL =================
with aba1:

    st.subheader("🔍 Buscar colônia")

    codigo_input = st.text_input("Código", value=codigo_qr)

    if codigo_input:
        cur.execute("SELECT * FROM colonias WHERE codigo=%s", (codigo_input,))
        dados = cur.fetchone()

        if dados:
            st.success(f"Colônia: {codigo_input}")

            peso_ovos = st.number_input("Ovos", value=dados[6] or 0.0)
            peso_larvas = st.number_input("Larvas", value=dados[7] or 0.0)
            peso_div = st.number_input("Divisão", value=dados[8] or 0.0)
            peso_pupa = st.number_input("Pupas", value=dados[9] or 0.0)

            if st.button("Atualizar"):
                cur.execute("""
                    UPDATE colonias
                    SET peso_ovos=%s, peso_larvas=%s,
                        peso_divisao=%s, peso_pupas=%s
                    WHERE codigo=%s
                """, (peso_ovos, peso_larvas, peso_div, peso_pupa, codigo_input))
                conn.commit()
                st.success("Atualizado")

    # ================= NOVA COLÔNIA =================
    st.subheader("➕ Nova colônia")

    tipo = st.selectbox("Tipo", ["MAE", "FILHA"])
    data_postura = st.date_input("Data")
    semana = st.selectbox("Semana", ["1ª","2ª","3ª","4ª"])
    colonia = st.number_input("Colônia mãe", step=1)

    if st.button("Gerar"):

        if tipo == "MAE":
            codigo = gerar_codigo_mae(data_postura, semana, colonia)
        else:
            codigo = gerar_codigo_filha(data_postura, semana, colonia)

        data_colheita = data_postura + timedelta(days=80)

        cur.execute("""
            INSERT INTO colonias 
            (codigo,tipo,data_postura,semana,colonia_mae,data_colheita,status)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT DO NOTHING
        """, (codigo, tipo, data_postura, semana, colonia, data_colheita, "ATIVO"))

        conn.commit()

        url = f"https://sistematenebrio-7k6ghyudmfptwrjdxomrs6.streamlit.app/?codigo={codigo}"

        # ================= ETIQUETA =================
        qr = qrcode.make(url).resize((140,140))

        etiqueta = Image.new("RGB", (300,180), "white")
        etiqueta.paste(qr, (10,20))

        draw = ImageDraw.Draw(etiqueta)

        try:
            font = ImageFont.truetype("arial.ttf", 18)
        except:
            font = ImageFont.load_default()

        draw.text((160,20), tipo, fill="black", font=font)
        draw.text((160,60), codigo[:15], fill="black", font=font)
        draw.text((160,90), codigo[15:], fill="black", font=font)

        buffer = BytesIO()
        etiqueta.save(buffer, format="PNG")
        buffer.seek(0)

        st.image(etiqueta)
        st.download_button("⬇️ Baixar etiqueta", buffer, file_name=f"{codigo}.png")

# ================= DASHBOARD =================
with aba2:

    st.subheader("📊 Dashboard Zootécnico")

    df = pd.read_sql("SELECT * FROM colonias", conn)

    if df.empty:
        st.warning("Sem dados")
    else:
        # filtrar filhas
        filhas = df[df["tipo"] == "FILHA"].copy()

        if filhas.empty:
            st.warning("Sem dados de colônias filhas")
        else:
            # ================= PARÂMETROS =================
            st.sidebar.subheader("Parâmetros produtivos")

            consumo_racao = st.sidebar.number_input("Consumo ração por caixa (kg)", value=1.5)
            custo_racao = st.sidebar.number_input("Custo ração (R$/kg)", value=1.5)
            custo_operacional = st.sidebar.number_input("Custo operacional/caixa (R$)", value=0.5)
            preco_venda = st.sidebar.number_input("Preço venda (R$/kg)", value=30.0)

            # ================= AGRUPAMENTO POR MÃE =================
            resumo = filhas.groupby("colonia_mae").agg({
                "peso_larvas": "sum",
                "peso_ovos": "sum",
                "codigo": "count"
            }).rename(columns={
                "peso_larvas": "producao_total",
                "peso_ovos": "ovos_total",
                "codigo": "n_caixas"
            })

            # ================= INDICADORES =================
            resumo["peso_medio"] = resumo["producao_total"] / resumo["n_caixas"]

            resumo["eficiencia"] = resumo["producao_total"] / resumo["ovos_total"]

            resumo["fcr"] = consumo_racao / (resumo["producao_total"] / 1000)

            resumo["custo_total"] = (
                (consumo_racao * custo_racao) * resumo["n_caixas"]
                + (custo_operacional * resumo["n_caixas"])
            )

            resumo["custo_kg"] = resumo["custo_total"] / (resumo["producao_total"] / 1000)

            resumo["receita"] = (resumo["producao_total"] / 1000) * preco_venda

            resumo["lucro"] = resumo["receita"] - resumo["custo_total"]

            # ================= SCORE =================
            resumo["score"] = (
                resumo["producao_total"] * 0.4 +
                resumo["eficiencia"] * 0.3 +
                (1 / resumo["fcr"]) * 0.3
            )

            # ================= RANKING =================
            ranking = resumo.sort_values(by="score", ascending=False)

            st.subheader("🏆 Ranking por Colônia Mãe")
            st.dataframe(ranking)

            # ================= GRÁFICOS =================
            st.subheader("📈 Produção por Colônia Mãe")
            st.bar_chart(resumo["producao_total"])

            st.subheader("💰 Lucro por Colônia Mãe")
            st.bar_chart(resumo["lucro"])

            # ================= RESUMO GERAL =================
            st.subheader("📌 Indicadores gerais")

            col1, col2, col3 = st.columns(3)

            col1.metric("Produção total (g)", int(resumo["producao_total"].sum()))
            col2.metric("Lucro total (R$)", round(resumo["lucro"].sum(), 2))
            col3.metric("Caixas totais", int(resumo["n_caixas"].sum()))
