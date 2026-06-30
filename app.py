import streamlit as st
from pdf_transposer import transponi_pdf

# Configurazione base della pagina
st.set_page_config(
    page_title="PDF Chord Transposer",
    page_icon="🎵",
    layout="centered"
)

# Stile personalizzato per migliorare l'estetica
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    h1 {
        color: #1e3a8a;
        text-align: center;
    }
    .stButton>button {
        background-color: #e63946;
        color: white;
        border-radius: 8px;
        width: 100%;
        padding: 10px;
        font-weight: bold;
    }
    .stDownloadButton>button {
        background-color: #2a9d8f;
        color: white;
        border-radius: 8px;
        width: 100%;
        padding: 10px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🎵 Traspositore Accordi PDF")
st.markdown("Carica il tuo PDF, scegli la nuova tonalità e scarica il file con gli accordi modificati.")

# Caricamento del file PDF
uploaded_file = st.file_uploader("Scegli un file PDF", type="pdf")

# Scelta della Tonalità Obiettivo
tonalita = ["Do", "Do#", "Reb", "Re", "Re#", "Mib", "Mi", "Fa", "Fa#", "Solb", "Sol", "Sol#", "Lab", "La", "La#", "Sib", "Si"]
obiettivo = st.selectbox("Seleziona la Tonalità di Destinazione", tonalita, index=3) # Default su Re

# Aggiunta opzionale del Capotasto
usa_capotasto = st.checkbox("Aggiungi indicazione Capotasto (Opzionale)")
capo_tasto = None
if usa_capotasto:
    capo_tasto = st.number_input("Seleziona il tasto", min_value=1, max_value=12, value=3)

if uploaded_file is not None:
    st.success("File caricato correttamente!")
    
    # Bottone per trasporre
    if st.button("Trasponi PDF"):
        with st.spinner("Trasposizione in corso..."):
            try:
                # Legge il PDF in byte
                pdf_bytes = uploaded_file.read()
                
                # Chiama la logica di elaborazione
                new_pdf_bytes, tonalita_originale = transponi_pdf(pdf_bytes, obiettivo, capo_tasto)
                
                st.success(f"Trasposizione completata da {tonalita_originale} a {obiettivo}!")
                
                # Generazione intelligente del nuovo nome file
                original_name = uploaded_file.name
                # Se la tonalità originale (es. DO, Do, do) è presente nel nome, la sostituiamo
                import re
                
                # Usiamo una regex case-insensitive con i word boundary per non sostituire "do" dentro "dono"
                pattern = r'\b' + re.escape(tonalita_originale) + r'\b'
                if re.search(pattern, original_name, flags=re.IGNORECASE):
                    new_file_name = re.sub(pattern, obiettivo, original_name, flags=re.IGNORECASE)
                else:
                    # Se non c'è nel nome, aggiungiamo semplicemente il suffisso alla fine
                    new_file_name = f"{original_name.replace('.pdf', '')}_{obiettivo}.pdf"
                
                # Bottone per il download
                st.download_button(
                    label="⬇️ Scarica il nuovo PDF",
                    data=new_pdf_bytes,
                    file_name=new_file_name,
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Si è verificato un errore: {e}")
