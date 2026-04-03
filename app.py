import streamlit as st
import psycopg2
from datetime import datetime, timedelta
import qrcode
from io import BytesIO

# ================= CONEXÃO =================
conn = psycopg2.connect(st.secrets["DATABASE_URL"])
cur = conn.cursor()

# ================= RESETAR TABELA (TEMPORÁRIO) =================
cur.execute("DROP TABLE IF EXISTS colonias;")
conn.commit()

# ================= CRIAR TABELA NOVA =================
cur.execute("""
CREATE TABLE colonias (
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

    num_caixas INTEGER,

    data_colheita DATE,
    status TEXT
);
""")
conn.commit()

# ================= FUNÇÕES =================
def gerar_codigo_mae(data_postura, semana, colonia):
    return f"{data_postura.strftime('%Y%m%d')}-S{semana[0]}-M{colonia}"

def gerar_codigo_filha(data_postura, semana, colonia):
    cur.execute("""
        SELECT COUNT(*) FROM colonias
        WHERE data_postura = %s AND colonia_mae = %s AND tipo='FILHA'
    """, (data_postura, colonia))

    seq = cur.fetchone()[0] + 1

    return f"{data_postura.strftime('%Y%m%d')}-S{semana[0]}-M{colonia}-F{seq}"

# ================= LER QR =================
params = st.query_params
codigo_url = params.get("codigo", "")

st.title("🐞 Sistema Zootécnico - Tenebrio")

# ================= BUSCA =================
codigo = st.text_input("Código da colônia", value=codigo_url)

dados = None
if codigo:
    cur.execute("SELECT * FROM colonias WHERE codigo=%s", (codigo,))
    dados = cur.fetchone()

# ================= SE EXISTIR =================
if dados:
    st.success(f"Colônia carregada: {codigo}")
    st.markdown(f"**Tipo:** {dados[2]}")

    peso_ovos = st.number_input("Peso ovos (g)", value=dados[6] or 0.0)
    peso_larvas = st.number_input("Peso larvas (g)", value=dados[7] or 0.0)
    peso_div = st.number_input("Peso divisão (g)", value=dados[8] or 0.0)
    peso_pupa = st.number_input("Peso pupas (g)", value=dados[9] or 0.0)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("💾 Salvar"):
            cur.execute("""
                UPDATE colonias
                SET peso_ovos=%s,
                    peso_larvas=%s,
                    peso_divisao=%s,
                    peso_pupas=%s
                WHERE codigo=%s
            """, (peso_ovos, peso_larvas, peso_div, peso_pupa, codigo))
            conn.commit()
            st.success("Atualizado!")

    with col2:
        if st.button("🗑️ Deletar"):
            cur.execute("DELETE FROM colonias WHERE codigo=%s", (codigo,))
            conn.commit()
            st.warning("Colônia deletada!")

# ================= CRIAR =================
else:
    st.subheader("➕ Criar nova colônia")

    tipo = st.selectbox("Tipo", ["MAE", "FILHA"])
    data_postura = st.date_input("Data de postura")
    semana = st.selectbox("Semana", ["1ª","2ª","3ª","4ª"])
    colonia = st.number_input("Número da colônia mãe", step=1)

    if st.button("🚀 Gerar colônia"):
        if tipo == "MAE":
            codigo_gerado = gerar_codigo_mae(data_postura, semana, colonia)
        else:
            codigo_gerado = gerar_codigo_filha(data_postura, semana, colonia)

        data_colheita = data_postura + timedelta(days=80)

        cur.execute("""
            INSERT INTO colonias 
            (codigo, tipo, data_postura, semana, colonia_mae, data_colheita, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (codigo) DO NOTHING
        """, (codigo_gerado, tipo, data_postura, semana, colonia, data_colheita, "ATIVO"))

        conn.commit()

        st.success("Colônia criada com sucesso!")

        st.markdown("### Código da colônia:")
        st.code(codigo_gerado)

        # ================= QR =================
        url = f"https://sistematenebrio-7k6ghyudmfptwrjdxomrs6.streamlit.app/?codigo={codigo_gerado}"

        qr = qrcode.make(url)
        buf = BytesIO()
        qr.save(buf)
        buf.seek(0)

        st.image(buf, caption="QR Code da colônia")

        st.download_button(
            "📥 Baixar QR para impressão",
            data=buf,
            file_name=f"{codigo_gerado}.png",
            mime="image/png"
        )
