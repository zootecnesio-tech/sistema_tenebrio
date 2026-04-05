import streamlit as st
import psycopg2
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import pandas as pd
import hashlib

# ================= CONFIG =================
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

cur.execute("SELECT * FROM usuarios WHERE username='admin'")
if not cur.fetchone():
    cur.execute("""
        INSERT INTO usuarios (username, senha, tipo)
        VALUES (%s,%s,%s)
    """, ("admin", hash_senha("1234"), "admin"))
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
    st.title("🔐 Login obrigatório")

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

aba1, aba2 = st.tabs(["Operacional", "Dashboard"])

# ================= OPERACIONAL =================
with aba1:

    st.subheader("Nova colônia")

    tipo = st.selectbox("Tipo", ["MAE", "FILHA"])
    data_postura = st.date_input("Data")
    semana = st.selectbox("Semana", ["1ª","2ª","3ª","4ª"])
    colonia = st.number_input("Colônia mãe", step=1)

    if st.button("Gerar colônia"):

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
        qr = qrcode.QRCode(version=2, box_size=3, border=1)
        qr.add_data(url)
        qr.make(fit=True)

        img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGB")

        largura, altura = 300, 180
        etiqueta = Image.new("RGB", (largura, altura), "white")

        img_qr = img_qr.resize((140, 140))
        etiqueta.paste(img_qr, (10, 20))

        draw = ImageDraw.Draw(etiqueta)

        try:
            font = ImageFont.truetype("arial.ttf", 18)
        except:
            font = ImageFont.load_default()

        draw.text((160, 20), tipo, fill="black", font=font)
        draw.text((160, 60), codigo[:15], fill="black", font=font)
        draw.text((160, 90), codigo[15:], fill="black", font=font)
        draw.text((160, 130), data_postura.strftime("%d/%m/%Y"), fill="black", font=font)

        buffer = BytesIO()
        etiqueta.save(buffer, format="PNG")
        buffer.seek(0)

        st.image(etiqueta)
        st.download_button(
            "⬇️ Baixar etiqueta",
            buffer,
            file_name=f"{codigo}.png",
            mime="image/png"
        )

# ================= DASHBOARD =================
with aba2:

    df = pd.read_sql("SELECT * FROM colonias", conn)

    if not df.empty:
        st.metric("Produção total", int(df["peso_larvas"].fillna(0).sum()))
