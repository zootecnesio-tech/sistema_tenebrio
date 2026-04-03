import streamlit as st
import psycopg2
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import pandas as pd
import hashlib

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

# criar admin padrão
cur.execute("SELECT * FROM usuarios WHERE username='admin'")
if not cur.fetchone():
    cur.execute("""
        INSERT INTO usuarios (username, senha, tipo)
        VALUES (%s,%s,%s)
    """, ("admin_lucas", hash_senha("2107#Lp"), "admin"))
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
            st.session_state["usuario"] = user
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
st.title("🐞 Sistema Zootécnico - Tenebrio")

aba1, aba2 = st.tabs(["📋 Operacional", "📊 Dashboard BI"])

# =========================================================
# ================= ABA OPERACIONAL ========================
# =========================================================
with aba1:

    st.subheader("🔍 Buscar colônia")

    params = st.query_params
    codigo_qr = params.get("codigo", "")

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

            if st.session_state["tipo"] == "admin":
                if st.button("Deletar"):
                    cur.execute("DELETE FROM colonias WHERE codigo=%s", (codigo_input,))
                    conn.commit()
                    st.warning("Deletado")
            else:
                st.info("Sem permissão para deletar")

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

        st.code(codigo)

        # QR
        qr = qrcode.make(url)
        st.image(qr)

    # ================= USUÁRIOS =================
    st.subheader("👥 Usuários")

    if st.session_state["tipo"] == "admin":

        novo = st.text_input("Novo usuário")
        senha_nova = st.text_input("Senha", type="password")
        tipo_user = st.selectbox("Tipo usuário", ["admin","operador"])

        if st.button("Criar usuário"):
            try:
                cur.execute("""
                    INSERT INTO usuarios (username, senha, tipo)
                    VALUES (%s,%s,%s)
                """, (novo, hash_senha(senha_nova), tipo_user))
                conn.commit()
                st.success("Usuário criado")
            except:
                st.error("Erro (usuário pode já existir)")

# =========================================================
# ================= DASHBOARD ==============================
# =========================================================
with aba2:

    df = pd.read_sql("SELECT * FROM colonias", conn)

    if df.empty:
        st.warning("Sem dados")
    else:
        filhas = df[df["tipo"] == "FILHA"]

        st.metric("Produção total", int(filhas["peso_larvas"].fillna(0).sum()))

        # parâmetros
        custo_farelo = st.sidebar.number_input("R$/kg farelo", value=1.5)
        custo_op = st.sidebar.number_input("Custo caixa", value=0.5)

        filhas["ef_final"] = filhas["peso_larvas"] / filhas["peso_ovos"]
        filhas["fcr"] = 1.5 / (filhas["peso_larvas"] / 1000)
        filhas["custo_total"] = (1.5*custo_farelo) + custo_op
        filhas["custo_kg"] = filhas["custo_total"] / (filhas["peso_larvas"]/1000)

        # ranking
        filhas["score"] = (
            filhas["peso_larvas"]*0.5 +
            filhas["ef_final"]*0.3 +
            (1/filhas["fcr"])*0.2
        )

        ranking = filhas.sort_values(by="score", ascending=False)

        st.subheader("🏆 Ranking")
        st.dataframe(ranking[["codigo","score"]])

        # lucro
        preco = st.number_input("Preço venda R$/kg", value=30.0)

        filhas["receita"] = (filhas["peso_larvas"]/1000)*preco
        filhas["lucro"] = filhas["receita"] - filhas["custo_total"]

        st.subheader("💰 Lucro")
        st.metric("Lucro total", round(filhas["lucro"].sum(),2))
        st.dataframe(filhas[["codigo","lucro"]])
