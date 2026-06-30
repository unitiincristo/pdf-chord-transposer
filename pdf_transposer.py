import re
import fitz  # PyMuPDF

# Scale cromatiche di riferimento (Default Title Case)
NOTE_DIESIS = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"]
NOTE_BEMOLLI = ["Do", "Reb", "Re", "Mib", "Mi", "Fa", "Solb", "Sol", "Lab", "La", "Sib", "Si"]

MAPPA_NOTE = {
    "DO": 0, "DO#": 1, "REb": 1, "RE": 2, "RE#": 3, "MIb": 3, "MI": 4,
    "FA": 5, "FA#": 6, "SOLb": 6, "SOL": 7, "SOL#": 8, "LAb": 8, "LA": 9,
    "LA#": 10, "SIb": 10, "SI": 11
}

def get_transposed_chord(accordo, semitoni, scala_riferimento):
    parti = accordo.split('/')
    parti_trasposte = []
    
    # IMPORTANTE: Ordine decrescente di lunghezza! Prima le note di 3/2 caratteri (es. SOLb, DO#), poi le singole.
    pattern_note = r"^(DO#|REb|RE#|MIb|FA#|SOLb|SOL#|LAb|LA#|SIb|DO|RE|MI|FA|SOL|LA|SI)(.*)$"
    
    for parte in parti:
        m = re.match(pattern_note, parte.strip(), flags=re.IGNORECASE)
        if m:
            nota_fondamentale_match = m.group(1)
            estensione = m.group(2)
            
            # Verifica se la nota originale era scritta in MAIUSCOLO (escludendo 'b' e '#')
            # Es: "FA" -> True, "Fa" -> False, "SIb" -> True, "Sib" -> False
            base_letters = nota_fondamentale_match.replace('b', '').replace('#', '').replace('B', '')
            is_upper = base_letters.isupper() if len(base_letters) > 0 else False
            
            # Normalizza per trovare in mappa (es. "Mib" -> "MIb")
            nota_fondamentale = nota_fondamentale_match.upper().replace("B", "b")
            
            indice_corrente = MAPPA_NOTE.get(nota_fondamentale)
            if indice_corrente is not None:
                nuovo_indice = (indice_corrente + semitoni) % 12
                nuova_nota = scala_riferimento[nuovo_indice] # Es: "Sol" o "Reb" (Title Case di default)
                
                if is_upper:
                    # Ripristina il maiuscolo ma mantiene il 'b' minuscolo
                    nuova_nota = nuova_nota.upper().replace("B", "b")
                    
                parti_trasposte.append(nuova_nota + estensione)
            else:
                parti_trasposte.append(parte)
        else:
            parti_trasposte.append(parte)
            
    return "/".join(parti_trasposte)

def is_chord(text):
    # Pattern esatto per un singolo accordo o accordo con basso (es. Do, Rem7, Do/Mi)
    clean_text = text.strip()
    pattern_nota = r"(?:DO#|REb|RE#|MIb|FA#|SOLb|SOL#|LAb|LA#|SIb|DO|RE|MI|FA|SOL|LA|SI)"
    pattern_accordo = rf"^{pattern_nota}(?:m7|m|4|7|maj7|sus4|dim)?(?:\/{pattern_nota}(?:m7|m|4|7|maj7|sus4|dim)?)?$"
    return bool(re.match(pattern_accordo, clean_text, flags=re.IGNORECASE))

def transponi_pdf(pdf_bytes, tonalita_obiettivo, capo_tasto=None):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    # 1. Trova la tonalità originale
    tonalita_originale = None
    tonalita_originale_pura = None
    for page in doc:
        text = page.get_text()
        match_key = re.search(r"Key:\s*([A-Za-z#b]+)", text)
        if match_key:
            tonalita_originale_pura = match_key.group(1).strip()
            # Es: "Sol" -> "SOL", "Sib" -> "SIb", "Lam" -> "LAm"
            tonalita_originale = tonalita_originale_pura.upper().replace("B", "b").replace("M", "m")
            break
            
    if not tonalita_originale:
        raise ValueError("Impossibile trovare la riga 'Key: XXX' nel PDF fornito.")
        
    tonalita_obiettivo_pura = tonalita_obiettivo.strip()
    tonalita_obiettivo_norm = tonalita_obiettivo_pura.upper().replace("B", "b")
    
    # Rimuoviamo eventuale "m" finale per il calcolo dei semitoni (es. LAm -> LA)
    orig_base = tonalita_originale.replace("m", "")
    obiett_base = tonalita_obiettivo_norm.replace("m", "")
    
    if orig_base not in MAPPA_NOTE or obiett_base not in MAPPA_NOTE:
        raise ValueError(f"Tonalità non valida. Originale: {tonalita_originale}, Obiettivo: {tonalita_obiettivo}")

    # 2. Calcola semitoni e scala
    semitoni = (MAPPA_NOTE[obiett_base] - MAPPA_NOTE[orig_base]) % 12
    usa_bemolli = obiett_base in ["FA", "SIb", "MIb", "LAb", "REb"]
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
                                
                                # Applica il casing corretto alla nuova tonalità
                                base_key = tonalita_originale_pura.replace('b', '').replace('#', '').replace('m', '')
                                is_key_upper = base_key.isupper() if len(base_key) > 0 else False
                                
                                nuova_chiave_str = tonalita_obiettivo_norm
                                if not is_key_upper:
                                    nuova_chiave_str = nuova_chiave_str.capitalize()
                                    # Se finisce con 'b', il capitalize fa "Mib" (corretto), "Solb" (corretto).
                                
                                new_key_text = f"Key: {nuova_chiave_str}"
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