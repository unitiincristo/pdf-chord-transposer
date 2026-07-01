import fitz
import re
from pdf_transposer import transponi_pdf

def create_dummy_pdf():
    doc = fitz.open()
    page = doc.new_page()
    
    # 1. Titolo e metadati (Nero)
    page.insert_text(fitz.Point(50, 50), "APRI I MIEI OCCHI SIGNORE", fontsize=16, color=(0,0,0))
    page.insert_text(fitz.Point(50, 70), "Tonalita: Re- | Tempo: 4/4 | Bpm: 68", fontsize=11, color=(0,0,0))
    
    # 2. Link YouTube (Blu)
    page.insert_text(fitz.Point(50, 90), "https://www.youtube.com/watch?v=ReFaMiDo", fontsize=11, color=(0,0,1))
    
    # 3. Testo cantato (Nero) e Accordi (Rosso)
    page.insert_text(fitz.Point(50, 130), "SI-", fontsize=11, color=(1,0,0))
    page.insert_text(fitz.Point(50, 145), "APRI I MIEI OCCHI SIGNOR", fontsize=11, color=(0,0,0))
    
    page.insert_text(fitz.Point(50, 170), "LA", fontsize=11, color=(1,0,0))
    page.insert_text(fitz.Point(50, 185), "VEDERTI SPLENDERE SIGNOR", fontsize=11, color=(0,0,0))
    
    page.insert_text(fitz.Point(50, 210), "Do/Do4", fontsize=11, color=(1,0,0))
    page.insert_text(fitz.Point(50, 225), "TEST ACCORDO COMPOSTO", fontsize=11, color=(0,0,0))
    
    return doc.write()

def test_new_template():
    print("Creazione PDF di test...")
    pdf_bytes = create_dummy_pdf()
    
    print("Avvio trasposizione da Re- a Mi...")
    # Trasponiamo a "MI" (che essendo minore originale, dovrebbe diventare MI-)
    new_pdf_bytes, orig_key = transponi_pdf(pdf_bytes, "MI")
    
    print(f"Tonalità originale rilevata: {orig_key}")
    assert orig_key == "RE-", f"Errore: tonalita_originale rilevata è {orig_key}, ci si aspettava RE-"
    
    # Verifichiamo il testo del nuovo PDF
    doc2 = fitz.open(stream=new_pdf_bytes, filetype="pdf")
    page2 = doc2[0]
    
    text_dict = page2.get_text("dict")
    extracted_texts = []
    for block in text_dict.get("blocks", []):
        if block.get("type") == 0:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    extracted_texts.append((span["text"], span["color"]))
                    
    doc2.close()
    
    # Verifica
    print("--- Contenuto PDF Generato ---")
    has_mi_key = False
    has_do_sharp_minor = False
    has_si_major = False
    has_re_re4 = False
    has_url = False
    
    for text, color in extracted_texts:
        print(f"Testo: '{text}', Colore: {color}")
        if "Tonalita: Mi-" in text or "Tonalita: MI-" in text:
            has_mi_key = True
        if "DO#-" in text or "Do#-" in text:
            has_do_sharp_minor = True
        if "SI" in text and "SIGNORE" not in text and "VEDERTI" not in text and color != 0:
            has_si_major = True
        if "Re/Re4" in text or "RE/RE4" in text:
            has_re_re4 = True
        if "https://www.youtube.com/watch?v=ReFaMiDo" in text:
            has_url = True
            
    assert has_mi_key, "Errore: 'Tonalita: Mi-' non trovato!"
    assert has_do_sharp_minor, "Errore: l'accordo SI- non è stato trasposto in DO#-"
    assert has_si_major, "Errore: l'accordo LA non è stato trasposto in SI"
    assert has_re_re4, "Errore: l'accordo Do/Do4 non è stato trasposto in Re/Re4"
    assert has_url, "Errore: il link YouTube è stato modificato o rimosso!"
    
    print("TUTTI I TEST SUPERATI!")
    
if __name__ == "__main__":
    test_new_template()
