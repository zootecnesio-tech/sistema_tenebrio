import streamlit as st
import psycopg2
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# ================= CONEXÃO =================
conn = psycopg2.connect(st.secrets["DATABASE_URL"])
cur = conn.cursor()

# ================= TABELA =================
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

# ================= CAPTURA QR =================
params = st.query_params
codigo_qr = params.get("codigo", "")

st.title("🐞 Sistema Zootécnico - Tenebrio")

# ================= BUSCA =================
st.subheader("🔍 Buscar colônia")

codigo_input = st.text_input("Digite ou escaneie o código", value=codigo_qr)

if codigo_input:
    cur.execute("SELECT * FROM colonias WHERE codigo=%s", (codigo_input,))
    dados = cur.fetchone()

    if dados:
        st.success(f"Colônia encontrada: {codigo_input}")
        st.markdown(f"**Tipo:** {dados[2]}")

        peso_ovos = st.number_input("Peso ovos (g)", value=dados[6] or 0.0)
        peso_larvas = st.number_input("Peso larvas (g)", value=dados[7] or 0.0)
        peso_div = st.number_input("Peso divisão (g)", value=dados[8] or 0.0)
        peso_pupa = st.number_input("Peso pupas (g)", value=dados[9] or 0.0)

        col1, col2 = st.columns(2)

        with col1:
            if st.button("💾 Atualizar dados"):
                cur.execute("""
                    UPDATE colonias
                    SET peso_ovos=%s,
                        peso_larvas=%s,
                        peso_divisao=%s,
                        peso_pupas=%s
                    WHERE codigo=%s
                """, (peso_ovos, peso_larvas, peso_div, peso_pupa, codigo_input))
                conn.commit()
                st.success("Dados atualizados!")

        with col2:
            if st.button("🗑️ Deletar colônia"):
                cur.execute("DELETE FROM colonias WHERE codigo=%s", (codigo_input,))
                conn.commit()
                st.warning("Colônia deletada!")

    else:
        st.warning("Colônia não encontrada")

# ================= CRIAÇÃO =================
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

    # ================= URL QR =================
    url = f"https://sistematenebrio-7k6ghyudmfptwrjdxomrs6.streamlit.app/?codigo={codigo_gerado}"

    st.success("Colônia criada com sucesso!")
    st.code(codigo_gerado)

    # ================= ETIQUETA 45x28 =================
    largura_px = 531
    altura_px = 331

    img = Image.new("RGB", (largura_px, altura_px), "white")

    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=1
    )
    qr.add_data(url)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_img = qr_img.resize((260, 260))

    img.paste(qr_img, (10, 35))

    draw = ImageDraw.Draw(img)

    try:
        font1 = ImageFont.truetype("arial.ttf", 26)
        font2 = ImageFont.truetype("arial.ttf", 22)
    except:
        font1 = None
        font2 = None

    x = 280

    draw.text((x, 40), tipo, fill="black", font=font1)

    codigo1 = codigo_gerado[:len(codigo_gerado)//2]
    codigo2 = codigo_gerado[len(codigo_gerado)//2:]

    draw.text((x, 120), codigo1, fill="black", font=font2)
    draw.text((x, 170), codigo2, fill="black", font=font2)

    buf = BytesIO()
    img.save(buf, format="PNG", dpi=(300,300))
    buf.seek(0)

    st.image(buf, caption="Etiqueta pronta para impressão")

    st.download_button(
        "📥 Baixar etiqueta",
        data=buf,
        file_name=f"{codigo_gerado}.png",
        mime="image/png"
    )
