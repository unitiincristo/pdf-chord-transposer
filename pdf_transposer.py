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
    pattern_accordo = rf"^{pattern_nota}(?:\-|m7|m|4|7|maj7|sus4|dim|9|2|sus2|add9|5|6|maj|sus|aug)*(?:\/{pattern_nota}(?:\-|m7|m|4|7|maj7|sus4|dim|9|2|sus2|add9|5|6|maj|sus|aug)*)?$"
    return bool(re.match(pattern_accordo, clean_text, flags=re.IGNORECASE))

def is_lyric_span(text):
    words = text.split()
    musical_keywords = {"intro", "vamp", "coro", "verso", "bridge", "instrumental", "ending", "pre-coro", "bpm", "tempo", "key", "tonalita", "tonalità"}
    
    for w in words:
        w_clean = re.sub(r'^[\(\[\|\.,;:\-\/]+|[\)\]\|\.,;:\-\/]+$', '', w).lower()
        if not w_clean:
            continue
        if re.match(r'^x\d+$', w_clean):
            continue
        if w_clean in musical_keywords or w_clean.isdigit():
            continue
            
        pattern_nota = r"(?:DO#|REb|RE#|MIb|FA#|SOLb|SOL#|LAb|LA#|SIb|DO|RE|MI|FA|SOL|LA|SI)"
        pattern_accordo = rf"^{pattern_nota}(?:\-|m7|m|4|7|maj7|sus4|dim|9|2|sus2|add9|5|6|maj|sus|aug)*(?:\/{pattern_nota}(?:\-|m7|m|4|7|maj7|sus4|dim|9|2|sus2|add9|5|6|maj|sus|aug)*)?$"
        if re.match(pattern_accordo, w_clean, flags=re.IGNORECASE):
            continue
            
        # Se c'è almeno una parola "normale", è un rigo di testo
        return True
    return False

def transponi_pdf(pdf_bytes, tonalita_obiettivo, capo_tasto=None):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    # 1. Trova la tonalità originale
    tonalita_originale = None
    tonalita_originale_pura = None
    for page in doc:
        text = page.get_text()
        match_key = re.search(r"(?:Key|Tonalità|Tonalita)[:\s]+([A-Za-z#b\-]+)", text, flags=re.IGNORECASE)
        if match_key:
            tonalita_originale_pura = match_key.group(1).strip()
            # Es: "Sol" -> "SOL", "Sib" -> "SIb", "Lam" -> "LAm", "Re-" -> "RE-"
            tonalita_originale = re.sub(r'M$', 'm', tonalita_originale_pura.upper().replace("B", "b"))
            break
            
    if not tonalita_originale:
        raise ValueError("Impossibile trovare la riga 'Key: XXX' o 'Tonalità: XXX' nel PDF fornito.")
        
    tonalita_obiettivo_pura = tonalita_obiettivo.strip()
    tonalita_obiettivo_norm = tonalita_obiettivo_pura.upper().replace("B", "b")
    
    # Rimuoviamo eventuale "m" o "-" finale per il calcolo dei semitoni (es. LAm -> LA, SI- -> SI)
    orig_base = tonalita_originale.replace("m", "").replace("-", "")
    obiett_base = tonalita_obiettivo_norm.replace("m", "").replace("-", "")
    
    if orig_base not in MAPPA_NOTE or obiett_base not in MAPPA_NOTE:
        raise ValueError(f"Tonalità non valida. Originale: {tonalita_originale}, Obiettivo: {tonalita_obiettivo}")

    # 2. Calcola semitoni e scala
    semitoni = (MAPPA_NOTE[obiett_base] - MAPPA_NOTE[orig_base]) % 12
    usa_bemolli = obiett_base in ["FA", "SIb", "MIb", "LAb", "REb"]
    scala_riferimento = NOTE_BEMOLLI if usa_bemolli else NOTE_DIESIS

    # 3. Itera su ogni pagina per fare la replace
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        text_dict = page.get_text("dict")
        insertions = []
        
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0: # E' un blocco di testo
                for line in block.get("lines", []):
                    full_line_text = "".join([span.get("text", "") for span in line.get("spans", [])])
                    has_key = bool(re.search(r"(Key|Tonalità|Tonalita)[:\s]+([A-Za-z#b\-]+)", full_line_text, flags=re.IGNORECASE))
                    
                    if not has_key and is_lyric_span(full_line_text):
                        continue
                        
                    shift_x_accum = 0
                    for span in line.get("spans", []):
                        testo_span = span.get("text", "")
                        color = span.get("color", 0)
                        flags = span.get("flags", 0)
                        font_name = span.get("font", "").lower()
                        is_bold = bool(flags & 16) or "bold" in font_name
                        target_font = "hebo" if is_bold else "helv"
                        
                        origin = fitz.Point(span["origin"])
                        rect = fitz.Rect(span["bbox"])
                        new_span_text = testo_span
                        
                        match_key_span = re.search(r"(Key|Tonalità|Tonalita)[:\s]+([A-Za-z#b\-]+)", testo_span, flags=re.IGNORECASE)
                        if match_key_span:
                            original_key_text = match_key_span.group(0)
                            prefix_found = match_key_span.group(1)
                            base_key = tonalita_originale_pura.replace('b', '').replace('#', '').replace('m', '').replace('-', '')
                            is_key_upper = base_key.isupper() if len(base_key) > 0 else False
                            
                            minor_suffix = ""
                            if "m" in tonalita_originale:
                                minor_suffix = "m"
                            elif "-" in tonalita_originale:
                                minor_suffix = "-"
                            
                            nuova_chiave_str = tonalita_obiettivo_norm + minor_suffix
                            if not is_key_upper:
                                nuova_chiave_str = tonalita_obiettivo_norm.capitalize() + minor_suffix
                            
                            new_key_text = f"{prefix_found}: {nuova_chiave_str}"
                            if capo_tasto:
                                new_key_text += f" | Capo: {capo_tasto}"
                            new_span_text = testo_span.replace(original_key_text, new_key_text)
                        else:
                            is_colored = color != 0 and color != 0xFFFFFF
                            if is_colored or (color == 0 and is_bold):
                                if not ("http://" in testo_span or "https://" in testo_span or "www." in testo_span):
                                    pattern_nota = r"(?:DO#|REb|RE#|MIb|FA#|SOLb|SOL#|LAb|LA#|SIb|DO|RE|MI|FA|SOL|LA|SI)"
                                    pattern_accordo = rf"(?<![A-Za-z])({pattern_nota}(?:\-|m7|m|4|7|maj7|sus4|dim|9|2|sus2|add9|5|6|maj|sus|aug)*(?:\/{pattern_nota}(?:\-|m7|m|4|7|maj7|sus4|dim|9|2|sus2|add9|5|6|maj|sus|aug)*)?)(?![A-Za-z])"
                                    def replace_chord(m):
                                        return get_transposed_chord(m.group(1), semitoni, scala_riferimento)
                                    new_span_text = re.sub(pattern_accordo, replace_chord, testo_span, flags=re.IGNORECASE)
                        
                        if new_span_text != testo_span or shift_x_accum != 0:
                            # Se c'è solo uno spazio vuoto (o quasi) evito di sbiancare inutilmente, ma sposto comunque
                            if testo_span.strip() != "":
                                page.add_redact_annot(rect, fill=(1,1,1))
                            new_origin = fitz.Point(origin.x + shift_x_accum, origin.y)
                            font_size = span["size"]
                            color_rgb = fitz.sRGB_to_pdf(color)
                            if new_span_text.strip() != "":
                                insertions.append((new_origin, new_span_text, font_size, color_rgb, target_font))
                            
                            old_width = fitz.get_text_length(testo_span, fontname=target_font, fontsize=font_size)
                            new_width = fitz.get_text_length(new_span_text, fontname=target_font, fontsize=font_size)
                            shift_x_accum += (new_width - old_width)
                                
        page.apply_redactions()
        
        for point, text, fsize, color, font in insertions:
            page.insert_text(point, text, fontsize=fsize, fontname=font, color=color)

    # Restituisce i byte del nuovo PDF e la tonalità originale trovata
    return doc.write(), tonalita_originale
