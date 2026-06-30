import re
import fitz  # PyMuPDF

# Scale cromatiche di riferimento
NOTE_DIESIS = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"]
NOTE_BEMOLLI = ["Do", "Reb", "Re", "Mib", "Mi", "Fa", "Solb", "Sol", "Lab", "La", "Sib", "Si"]

MAPPA_NOTE = {
    "Do": 0, "Do#": 1, "Reb": 1, "Re": 2, "Re#": 3, "Mib": 3, "Mi": 4,
    "Fa": 5, "Fa#": 6, "Solb": 6, "Sol": 7, "Sol#": 8, "Lab": 8, "La": 9,
    "La#": 10, "Sib": 10, "Si": 11
}

def get_transposed_chord(accordo, semitoni, scala_riferimento):
    parti = accordo.split('/')
    parti_trasposte = []
    
    for parte in parti:
        m = re.match(r"^(Do#|Do|Re#|Re|Mi|Fa#|Fa|Sol#|Sol|La#|La|Si|Reb|Mib|Solb|Lab|Sib)(.*)$", parte)
        if m:
            nota_fondamentale = m.group(1)
            estensione = m.group(2)
            
            indice_corrente = MAPPA_NOTE.get(nota_fondamentale)
            if indice_corrente is not None:
                nuovo_indice = (indice_corrente + semitoni) % 12
                parti_trasposte.append(scala_riferimento[nuovo_indice] + estensione)
            else:
                parti_trasposte.append(parte)
        else:
            parti_trasposte.append(parte)
            
    return "/".join(parti_trasposte)

def is_chord(text):
    # Pattern esatto per un singolo accordo o accordo con basso (es. Do, Rem7, Do/Mi)
    # Ignoriamo eventuali pipe (|) o spazi usati come separatori testuali
    clean_text = text.strip()
    pattern_accordo = r"^(?:Do#|Do|Re#|Re|Mi|Fa#|Fa|Sol#|Sol|La#|La|Si|Reb|Mib|Solb|Lab|Sib)(?:m7|m|4|7|maj7|sus4)?(?:\/(?:Do#|Do|Re#|Re|Mi|Fa#|Fa|Sol#|Sol|La#|La|Si|Reb|Mib|Solb|Lab|Sib)(?:m7|m|4|7|maj7|sus4)?)?$"
    return bool(re.match(pattern_accordo, clean_text))

def transponi_pdf(pdf_bytes, tonalita_obiettivo, capo_tasto=None):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    # 1. Trova la tonalità originale
    tonalita_originale = None
    for page in doc:
        text = page.get_text()
        match_key = re.search(r"Key:\s*([A-Za-z#b]+)", text)
        if match_key:
            tonalita_originale = match_key.group(1).strip().capitalize()
            break
            
    if not tonalita_originale:
        raise ValueError("Impossibile trovare la riga 'Key: XXX' nel PDF fornito.")
        
    tonalita_obiettivo = tonalita_obiettivo.strip().capitalize()
    
    if tonalita_originale not in MAPPA_NOTE or tonalita_obiettivo not in MAPPA_NOTE:
        raise ValueError(f"Tonalità non valida. Originale: {tonalita_originale}, Obiettivo: {tonalita_obiettivo}")

    # 2. Calcola semitoni e scala
    semitoni = (MAPPA_NOTE[tonalita_obiettivo] - MAPPA_NOTE[tonalita_originale]) % 12
    usa_bemolli = tonalita_obiettivo in ["Fa", "Sib", "Mib", "Lab", "Reb"]
    scala_riferimento = NOTE_BEMOLLI if usa_bemolli else NOTE_DIESIS

    # 3. Itera su ogni pagina per fare la replace
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # Estraiamo TUTTE le parole originali PRIMA di modificare la pagina
        words = page.get_text("words")
        text_dict = page.get_text("dict")
        
        # Salviamo i rettangoli della Key per ignorarli nel ciclo delle parole
        key_rects = []
        
        # Lista di tuple (punto_inserimento, testo, font_size, colore)
        insertions = []
        
        # A) Troviamo anche il rettangolo dove c'è "Key: XXX" per sostituirlo
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0: # E' un blocco di testo
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        testo_span = span.get("text", "")
                        
                        if "Key:" in testo_span:
                            match = re.search(r"Key:\s*([A-Za-z#b]+)", testo_span)
                            if match:
                                rect = fitz.Rect(span["bbox"])
                                key_rects.append(rect)
                                
                                original_key_text = match.group(0) # es. "Key: Do"
                                new_key_text = f"Key: {tonalita_obiettivo}"
                                if capo_tasto:
                                    new_key_text += f" | Capo: {capo_tasto}"
                                
                                # Prepariamo la redazione
                                page.add_redact_annot(rect, fill=(1,1,1)) # Riempi di bianco
                                
                                # Ricostruiamo la riga
                                nuovo_testo_riga = testo_span.replace(original_key_text, new_key_text)
                                font_size = span["size"]
                                color_rgb = fitz.sRGB_to_pdf(span["color"]) if "color" in span else (0,0,0)
                                
                                # Salviamo l'inserimento per dopo
                                insertions.append((rect.bottom_left, nuovo_testo_riga, font_size, color_rgb))
        
        # B) Modifica degli Accordi basata sulle parole originali
        for w in words:
            rect = fitz.Rect(w[:4]) # Bounding box della parola
            word_text = w[4].strip()
            
            # Controlla se la parola fa parte della riga "Key:" (interseca uno dei key_rects)
            is_in_key_line = any(rect.intersects(k_rect) for k_rect in key_rects)
            
            if not is_in_key_line and is_chord(word_text):
                new_chord = get_transposed_chord(word_text, semitoni, scala_riferimento)
                
                # Creiamo una redaction (riempiamo di bianco per cancellare)
                page.add_redact_annot(rect, fill=(1,1,1))
                
                # Troviamo la dimensione del font originale circa usando l'altezza del rect
                font_size = rect.height * 0.8
                if font_size < 8: font_size = 11 # fallback
                
                # Calcoliamo il punto e lo salviamo
                insertion_point = fitz.Point(rect.x0, rect.y1 - (rect.height * 0.2))
                insertions.append((insertion_point, new_chord, font_size, (1, 0, 0)))
                
        # IMPORTANTE: Applichiamo tutte le redactions PRIMA di inserire il nuovo testo
        # altrimenti la redaction cancellerebbe il nuovo testo appena scritto!
        page.apply_redactions()
        
        # Ora inseriamo tutto il nuovo testo
        for point, text, fsize, color in insertions:
            page.insert_text(point, text, fontsize=fsize, fontname="helv", color=color)

    # Restituisce i byte del nuovo PDF e la tonalità originale trovata
    return doc.write(), tonalita_originale