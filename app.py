import streamlit as st
import re
import importlib
import pdf_transposer
importlib.reload(pdf_transposer)
from pdf_transposer import transponi_pdf

# Configurazione base della pagina
st.set_page_config(
    page_title="PDF Chord Transposer v1.7.0",
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

st.title("🎵 Traspositore Accordi PDF v1.7.0")
st.markdown("Carica il tuo PDF, scegli la nuova tonalità oppure esporta il testo con o senza spaziature originali.")

# Caricamento del file PDF
uploaded_file = st.file_uploader("Scegli un file PDF", type="pdf")

# Opzioni di Elaborazione Testo (Senza Accordi)
st.markdown("### Modalità Solo Testo / Rimozione Accordi (Opzionale)")
col_opt1, col_opt2 = st.columns(2)
with col_opt1:
    elimina_accordi_layout = st.checkbox(
        "🎼 Elimina solo accordi (Mantieni spaziature)",
        help="Rimuove tutti gli accordi lasciando completamente invariate l'impaginazione, le pagine e le spaziature originali."
    )
with col_opt2:
    solo_testo = st.checkbox(
        "📖 Solo testo compattato",
        help="Rimuove gli accordi e compatta il testo eliminando lo spazio tra le righe."
    )

if elimina_accordi_layout and solo_testo:
    st.warning("⚠️ Seleziona una sola modalità tra 'Elimina solo accordi' e 'Solo testo compattato'.")

# Mostra i controlli di tonalità e strumenti solo se non si sta rimuovendo gli accordi
if not elimina_accordi_layout and not solo_testo:
    # Scelta della Tonalità Obiettivo
    tonalita = ["DO", "DO#", "REb", "RE", "RE#", "MIb", "MI", "FA", "FA#", "SOLb", "SOL", "SOL#", "LAb", "LA", "LA#", "SIb", "SI"]
    obiettivo = st.selectbox("Seleziona la Tonalità di Destinazione", tonalita, index=3) # Default su RE

    # Aggiunte opzionali per strumenti
    st.markdown("### Indicazioni Strumenti (Opzionale)")
    col1, col2 = st.columns(2)
    with col1:
        usa_capotasto = st.checkbox("🎸 Capotasto (Chitarra)")
        capo_tasto = None
        if usa_capotasto:
            capo_tasto = st.number_input("Tasto Capotasto", min_value=1, max_value=12, value=3)

    with col2:
        usa_piano = st.checkbox("🎹 Transpose (Piano)")
        piano_trans = None
        if usa_piano:
            col2a, col2b = st.columns(2)
            with col2a:
                piano_segno = st.selectbox("Direzione", ["+", "-"])
            with col2b:
                piano_val = st.number_input("Semitoni", min_value=1, max_value=12, value=1)
            piano_trans = f"{piano_segno}{piano_val}"
else:
    obiettivo = "Originale"
    capo_tasto = None
    piano_trans = None

if uploaded_file is not None:
    st.success("File caricato correttamente!")
    
    # Scelta etichetta bottone dinamica
    if elimina_accordi_layout:
        bottone_testo = "🎼 Genera PDF Senza Accordi (Layout Originale)"
    elif solo_testo:
        bottone_testo = "📖 Genera PDF Solo Testo (Compattato)"
    else:
        bottone_testo = "🎵 Trasponi PDF"
        
    if st.button(bottone_testo, disabled=(elimina_accordi_layout and solo_testo)):
        with st.spinner("Elaborazione in corso..."):
            try:
                # Legge il PDF in byte
                pdf_bytes = uploaded_file.read()
                
                # Chiama la logica di elaborazione
                new_pdf_bytes, tonalita_originale = transponi_pdf(
                    pdf_bytes, 
                    obiettivo, 
                    capo_tasto, 
                    piano_trans, 
                    solo_testo=solo_testo,
                    solo_testo_layout=elimina_accordi_layout
                )
                
                if elimina_accordi_layout:
                    st.success("Accordi rimossi con successo! Impaginazione e spaziature originali preservate.")
                elif solo_testo:
                    st.success("Testo ripulito dagli accordi e compattato con successo!")
                else:
                    st.success(f"Trasposizione completata da {tonalita_originale} a {obiettivo}!")
                
                # Generazione intelligente del nuovo nome file
                original_name = uploaded_file.name
                
                if elimina_accordi_layout:
                    new_file_name = f"{original_name.replace('.pdf', '')}_SenzaAccordi.pdf"
                elif solo_testo:
                    new_file_name = f"{original_name.replace('.pdf', '')}_SoloTesto.pdf"
                else:
                    # Usiamo lookarounds (?<![A-Za-z]) e (?![A-Za-z]) per evitare i limiti di \b con caratteri speciali come # o -
                    pattern = rf"(?<![A-Za-z]){re.escape(tonalita_originale)}(?![A-Za-z])"
                    if re.search(pattern, original_name, flags=re.IGNORECASE):
                        new_file_name = re.sub(pattern, obiettivo, original_name, flags=re.IGNORECASE)
                    else:
                        base_orig = tonalita_originale.replace("m", "").replace("-", "")
                        pattern_base = rf"(?<![A-Za-z]){re.escape(base_orig)}(?![A-Za-z])"
                        if re.search(pattern_base, original_name, flags=re.IGNORECASE):
                            new_file_name = re.sub(pattern_base, obiettivo, original_name, flags=re.IGNORECASE)
                        else:
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

st.markdown("---")
st.caption("Versione 1.7.0 - Rimozione Accordi (Layout Originale) e Fix Solo Testo Compattato")
