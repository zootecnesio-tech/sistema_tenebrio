import streamlit as st
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect("colonias.db", check_same_thread=False)
conn.execute("""
CREATE TABLE IF NOT EXISTS colonias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE,
    data_postura TEXT,
    semana_postura TEXT,
    colonia INTEGER,
    peso_larvas_divisao REAL,
    num_caixas INTEGER,
    data_colheita TEXT,
    status TEXT
)
""")
conn.commit()
st.title("🐞 Controle de Colônias - Tenebrio")

# pegar código da URL (QR futuramente)
params = st.query_params
codigo_url = params.get("codigo", "")

codigo = st.text_input("Código da caixa", value=codigo_url)

# ================= BUSCA =================
if codigo:

    dados = conn.execute(
        "SELECT * FROM colonias WHERE codigo=?",
        (codigo,)
    ).fetchone()

    # ================= NOVA COLÔNIA =================
    if not dados:
        st.warning("Colônia não encontrada")

        data_postura = st.date_input("Data de postura")
        semana = st.selectbox("Semana", ["1ª","2ª","3ª","4ª"])
        colonia = st.number_input("Número da colônia", step=1)

        if st.button("Criar colônia"):
            data_colheita = data_postura + timedelta(days=80)

            conn.execute("""
            INSERT INTO colonias 
            (codigo, data_postura, semana_postura, colonia, data_colheita, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                codigo,
                str(data_postura),
                semana,
                colonia,
                str(data_colheita),
                "EM PRODUÇÃO"
            ))

            conn.commit()
            st.success("Colônia criada!")

    # ================= EDITAR =================
    else:
        st.success(f"Colônia encontrada: {codigo}")

        peso = st.number_input("Peso larvas divisão (g)", value=0.0)
        caixas = st.number_input("Número de caixas", value=2)

        if st.button("Salvar"):
            conn.execute("""
            UPDATE colonias 
            SET peso_larvas_divisao=?, num_caixas=?
            WHERE codigo=?
            """, (peso, caixas, codigo))

            conn.commit()
            st.success("Atualizado!")