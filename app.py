import streamlit as st
import psycopg2
from datetime import datetime, timedelta

# conexão com banco
conn = psycopg2.connect(st.secrets["DATABASE_URL"])
cur = conn.cursor()

# criar tabela automaticamente
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
    data_manejo_8d DATE,

    peso_larvas_20d REAL,
    peso_larvas_divisao REAL,
    peso_pupas REAL,

    num_caixas INTEGER,

    densidade_larval REAL,
    mortalidade REAL,

    data_colheita DATE,

    residuo_parcial REAL,
    residuo_final REAL,

    status TEXT
);
""")
conn.commit()

# função código
def gerar_codigo(data_postura, semana, colonia):
    return f"{data_postura.strftime('%Y%m%d')}-S{semana[0]}-C{colonia}"

st.title("🐞 Sistema Zootécnico - Tenebrio")

# ================= NOVA COLÔNIA =================
st.subheader("➕ Criar nova colônia")

data_postura = st.date_input("Data de postura")
semana = st.selectbox("Semana", ["1ª","2ª","3ª","4ª"])
colonia = st.number_input("Colônia", step=1)

if st.button("Gerar e salvar"):
    codigo = gerar_codigo(data_postura, semana, colonia)
    data_colheita = data_postura + timedelta(days=80)

    cur.execute("""
        INSERT INTO colonias 
        (codigo, data_postura, semana_postura, colonia, data_colheita, status)
        VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT (codigo) DO NOTHING
    """, (codigo, data_postura, semana, colonia, data_colheita, "EM PRODUÇÃO"))

    conn.commit()

    st.success(f"Código gerado: {codigo}")

# ================= BUSCA =================
st.divider()
st.subheader("🔍 Buscar colônia")

codigo = st.text_input("Código")

if codigo:
    cur.execute("SELECT * FROM colonias WHERE codigo=%s", (codigo,))
    dados = cur.fetchone()

    if dados:
        st.success("Colônia encontrada")

        peso_ovos = st.number_input("Peso ovos (g)")
        peso_20d = st.number_input("Peso larvas 20d (g)")
        peso_div = st.number_input("Peso divisão (g)")
        peso_pupa = st.number_input("Peso pupas (g)")
        caixas = st.number_input("Número de caixas", value=2)

        if st.button("Salvar dados"):
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
