import streamlit as st
import psycopg2
from datetime import datetime, timedelta
import qrcode
from io import BytesIO

# ================= CONEXÃO =================
conn = psycopg2.connect(st.secrets["DATABASE_URL"])
cur = conn.cursor()

# ================= CRIAR TABELA =================
cur.execute("""
CREATE TABLE IF NOT EXISTS colonias (
    id SERIAL PRIMARY KEY,
    codigo TEXT UNIQUE,

    data_postura DATE,
    semana_postura TEXT,
    colonia INTEGER,

    peso_besouros_g REAL DEFAULT 250,
    peso_farelo_g REAL DEFAULT 1500,

    peso_ovos_8d REAL,
    peso_larvas_20d REAL,
    peso_larvas_divisao REAL,
    peso_pupas REAL,

    num_caixas INTEGER,

    data_colheita DATE,
    status TEXT
);
""")
conn.commit()

# ================= GERAR CÓDIGO COM SEQUÊNCIA =================
def gerar_codigo(data_postura, semana, colonia):
    data_str = data_postura.strftime('%Y%m%d')

    cur.execute("""
        SELECT COUNT(*) FROM colonias 
        WHERE data_postura = %s
    """, (data_postura,))
    
    count = cur.fetchone()[0] + 1

    return f"{data_str}-S{semana[0]}-C{colonia}-N{count}"

# ================= PEGAR CÓDIGO DA URL =================
params = st.query_params
codigo_url = params.get("codigo", "")

st.title("🐞 Sistema Zootécnico - Tenebrio")

# ================= BUSCA AUTOMÁTICA =================
codigo = st.text_input("Código da colônia", value=codigo_url)

dados = None

if codigo:
    cur.execute("SELECT * FROM colonias WHERE codigo=%s", (codigo,))
    dados = cur.fetchone()

# ================= SE ENCONTRAR =================
if dados:
    st.success(f"Colônia carregada automaticamente: {codigo}")

    peso_ovos = st.number_input("Peso ovos (g)", value=dados[7] or 0.0)
    peso_20d = st.number_input("Peso larvas 20 dias (g)", value=dados[8] or 0.0)
    peso_div = st.number_input("Peso divisão (g)", value=dados[9] or 0.0)
    peso_pupa = st.number_input("Peso pupas (g)", value=dados[10] or 0.0)
    caixas = st.number_input("Número de caixas", value=dados[11] or 2)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("💾 Salvar"):
            cur.execute("""
                UPDATE colonias
                SET peso_ovos_8d=%s,
                    peso_larvas_20d=%s,
                    peso_larvas_divisao=%s,
                    peso_pupas=%s,
                    num_caixas=%s
                WHERE codigo=%s
            """, (peso_ovos, peso_20d, peso_div, peso_pupa, caixas, codigo))

            conn.commit()
            st.success("Atualizado!")

    with col2:
        if st.button("🗑️ Deletar colônia"):
            cur.execute("DELETE FROM colonias WHERE codigo=%s", (codigo,))
            conn.commit()
            st.warning("Colônia deletada!")

# ================= SE NÃO ENCONTRAR =================
elif codigo:
    st.warning("Colônia não encontrada")

    data_postura = st.date_input("Data de postura")
    semana = st.selectbox("Semana", ["1ª","2ª","3ª","4ª"])
    colonia = st.number_input("Colônia", step=1)

    if st.button("🚀 Criar colônia"):
        codigo = gerar_codigo(data_postura, semana, colonia)
        data_colheita = data_postura + timedelta(days=80)

        cur.execute("""
            INSERT INTO colonias 
            (codigo, data_postura, semana_postura, colonia, data_colheita, status)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (codigo, data_postura, semana, colonia, data_colheita, "EM PRODUÇÃO"))

        conn.commit()

        st.success(f"Colônia criada: {codigo}")

        # ================= QR =================
        url = f"https://sistematenebrio-7k6ghyudmfptwrjdxomrs6.streamlit.app/?codigo={codigo}"

        qr = qrcode.make(url)
        buf = BytesIO()
        qr.save(buf)
        buf.seek(0)

        st.image(buf, caption="QR Code")

        st.download_button(
            "📥 Baixar QR",
            data=buf,
            file_name=f"{codigo}.png",
            mime="image/png"
        )
