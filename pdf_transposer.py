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
    musical_keywords = {"intro", "vamp", "coro", "verso", "bridge", "instrumental", "ending", "pre-coro", "bpm", "tempo", "key", "tonalita", "tonalità", "volta", "volte", "x", "chorus", "interlude"}
    
    for w in words:
        w_clean = re.sub(r'^[\(\[\|\.,;:\-\/]+|[\)\]\|\.,;:\-\/]+$', '', w).lower()
        if not w_clean:
            continue
        if re.match(r'^x?\d+x?$', w_clean):
            continue
        if re.match(r'^\d+[\^a-z°]*$', w_clean):
            continue
        if w_clean in musical_keywords:
            continue
            
        pattern_nota = r"(?:DO#|REb|RE#|MIb|FA#|SOLb|SOL#|LAb|LA#|SIb|DO|RE|MI|FA|SOL|LA|SI)"
        pattern_accordo = rf"^{pattern_nota}(?:\-|m7|m|4|7|maj7|sus4|dim|9|2|sus2|add9|5|6|maj|sus|aug)*(?:\/{pattern_nota}(?:\-|m7|m|4|7|maj7|sus4|dim|9|2|sus2|add9|5|6|maj|sus|aug)*)?$"
        if re.match(pattern_accordo, w_clean, flags=re.IGNORECASE):
            continue
            
        # Se c'è almeno una parola "normale", è un rigo di testo
        return True
    return False

def transponi_pdf(pdf_bytes, tonalita_obiettivo, capo_tasto=None, piano_trans=None, solo_testo=False):
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
    
    if not solo_testo:
        if orig_base not in MAPPA_NOTE or obiett_base not in MAPPA_NOTE:
            raise ValueError(f"Tonalità non valida. Originale: {tonalita_originale}, Obiettivo: {tonalita_obiettivo}")

        # 2. Calcola semitoni e scala
        semitoni = (MAPPA_NOTE[obiett_base] - MAPPA_NOTE[orig_base]) % 12
        usa_bemolli = obiett_base in ["FA", "SIb", "MIb", "LAb", "REb"]
        scala_riferimento = NOTE_BEMOLLI if usa_bemolli else NOTE_DIESIS
    else:
        semitoni = 0
        scala_riferimento = NOTE_DIESIS

    # 3. Elaborazione
    if solo_testo:
        kept_lines = []
        is_header = True
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0: continue
                for line in block.get("lines", []):
                    full_line_text = "".join([span.get("text", "") for span in line.get("spans", [])])
                    if full_line_text.strip() == "": continue
                    
                    has_key = bool(re.search(r"(Key|Tonalità|Tonalita)[:\s]+([A-Za-z#b\-]+)", full_line_text, flags=re.IGNORECASE))
                    is_lyric = is_lyric_span(full_line_text)
                    
                    line_kept_spans = []
                    for span in line.get("spans", []):
                        text = span.get("text", "")
                        clean_text = text.strip()
                        
                        if clean_text == "" or clean_text in ("|", "/", "//", "///", "||"):
                            continue
                            
                        keep = False
                        if is_header or has_key:
                            keep = True
                        elif is_lyric:
                            keep = True
                        else:
                            clean_upper = clean_text.upper()
                            is_span_section = any(clean_upper.startswith(kw) for kw in ["VERSE", "CHORUS", "BRIDGE", "INTRO", "INTERLUDE", "CORO", "VERSO", "FINAL", "ENDING", "PRE CHORUS", "PRE-CHORUS", "VAMP"])
                            is_span_repeat = bool(re.search(r'\b[xX]\d+\b', clean_upper)) or "VOLTA" in clean_upper
                            if is_span_section or is_span_repeat:
                                keep = True
                            if "http" in text.lower() or "www" in text.lower():
                                keep = True
                                
                        if keep:
                            if has_key:
                                text = re.sub(r'\s*\|\s*Piano:[^|]*', '', text, flags=re.IGNORECASE)
                                text = re.sub(r'\s*\|\s*Capo:[^|]*', '', text, flags=re.IGNORECASE)
                                if text.strip() == "": continue
                                
                            line_kept_spans.append({
                                "text": text,
                                "size": span["size"],
                                "origin": span["origin"],
                                "color": span.get("color", 0),
                                "font": span.get("font", ""),
                                "flags": span.get("flags", 0),
                                "bbox": span["bbox"]
                            })
                            
                    if line_kept_spans:
                        col_idx = 0 if line["bbox"][0] < doc[0].rect.width / 2 else 1
                        clean_line = "".join([s["text"] for s in line_kept_spans]).strip().upper()
                        is_section = any(clean_line.startswith(kw) for kw in ["VERSE", "CHORUS", "BRIDGE", "INTRO", "INTERLUDE", "CORO", "VERSO", "FINAL", "ENDING", "PRE CHORUS", "PRE-CHORUS", "VAMP"])
                        
                        kept_lines.append({
                            "col_idx": col_idx,
                            "spans": line_kept_spans,
                            "orig_y": line["bbox"][1],
                            "is_header": is_header or has_key,
                            "is_section": is_section
                        })
                        
                    if has_key:
                        is_header = False
                        
        # Raccoglie i buffer dei font originali incorporati per preservare la tipografia originale
        font_buffers = {}
        for f in doc[0].get_fonts():
            xref = f[0]
            basefont = f[3]
            clean_basefont = basefont.split("+")[1] if "+" in basefont else basefont
            try:
                font_data = doc.extract_font(xref)
                if font_data and len(font_data) >= 4 and font_data[3]:
                    font_buffers[clean_basefont] = (f"F{xref}", font_data[3])
            except:
                pass
            
        # Sbianca tutto il testo in modo nativo rimuovendo solo gli oggetti di testo (niente rettangoli bianchi)
        for page in doc:
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") == 0:
                    page.add_redact_annot(block["bbox"])
            page.apply_redactions(images=0) # 0 = PDF_REDACT_IMAGE_NONE
            
        page1 = doc[0]
        y_col = [0, 0]
        header_bottom = 0
        
        for item in kept_lines:
            spans = item["spans"]
            max_font = max(s["size"] for s in spans)
            
            if item["is_header"]:
                new_y = item["orig_y"]
                header_bottom = max(header_bottom, new_y + max_font * 1.5)
                y_col[0] = header_bottom
                y_col[1] = header_bottom
            else:
                c = item["col_idx"]
                if item["is_section"] and y_col[c] > header_bottom:
                    y_col[c] += max_font * 0.8
                
                new_y = y_col[c]
                y_col[c] += max_font * 1.3
                
            shift_x = 0
            for span in spans:
                text = span["text"]
                span_font = span["font"]
                if "+" in span_font: span_font = span_font.split("+")[1]
                
                is_bold = bool(span["flags"] & 16) or "bold" in span_font.lower()
                fallback_font = "hebo" if is_bold else "helv"
                clean_text_fallback = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-")
                
                orig_x, orig_y = span["origin"]
                pt = fitz.Point(orig_x + shift_x, new_y + (orig_y - item["orig_y"]))
                color = fitz.sRGB_to_pdf(span["color"])
                
                if text != span["text"]:
                    try:
                        old_w = fitz.get_text_length(span["text"], fontname=fallback_font, fontsize=span["size"])
                        new_w = fitz.get_text_length(text, fontname=fallback_font, fontsize=span["size"])
                        shift_x += (new_w - old_w)
                    except:
                        pass
                
                inserted = False
                if span_font in font_buffers:
                    fname, fbuf = font_buffers[span_font]
                    try:
                        page1.insert_text(pt, text, fontsize=span["size"], fontname=fname, fontbuffer=fbuf, color=color)
                        inserted = True
                    except Exception:
                        inserted = False
                        
                if not inserted:
                    page1.insert_text(pt, clean_text_fallback, fontsize=span["size"], fontname=fallback_font, color=color)
                
        while len(doc) > 1:
            doc.delete_page(1)
            
    else:
        # Itera su ogni pagina per fare la replace (LOGICA NORMALE TRASPOSIZIONE)
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            text_dict = page.get_text("dict")
            insertions = []
            
            for block in text_dict.get("blocks", []):
                if block.get("type") == 0:
                    for line in block.get("lines", []):
                        full_line_text = "".join([span.get("text", "") for span in line.get("spans", [])])
                        has_key = bool(re.search(r"(Key|Tonalità|Tonalita)[:\s]+([A-Za-z#b\-]+)", full_line_text, flags=re.IGNORECASE))
                        
                        if has_key:
                            match_key_full = re.search(r"(Key|Tonalità|Tonalita)[:\s]+([A-Za-z#b\-]+)", full_line_text, flags=re.IGNORECASE)
                            nota_originale = match_key_full.group(2)
                            
                            base_key = tonalita_originale_pura.replace('b', '').replace('#', '').replace('m', '').replace('-', '')
                            is_key_upper = base_key.isupper() if len(base_key) > 0 else False
                            minor_suffix = ""
                            if "m" in tonalita_originale: minor_suffix = "m"
                            elif "-" in tonalita_originale: minor_suffix = "-"
                            nuova_chiave_str = tonalita_obiettivo_norm + minor_suffix
                            if not is_key_upper: nuova_chiave_str = tonalita_obiettivo_norm.capitalize() + minor_suffix
                            
                            spans = line.get("spans", [])
                            shift_x_accum = 0
                            for span in spans:
                                testo_span = span.get("text", "")
                                rect = fitz.Rect(span["bbox"])
                                origin = fitz.Point(span["origin"])
                                
                                pattern_nota_orig = rf"(?<![A-Za-z]){re.escape(nota_originale)}(?![A-Za-z])"
                                new_span_text = re.sub(pattern_nota_orig, nuova_chiave_str, testo_span, flags=re.IGNORECASE)
                                
                                font_name = span.get("font", "").lower()
                                is_bold = bool(span.get("flags", 0) & 16) or "bold" in font_name
                                target_font = "hebo" if is_bold else "helv"
                                font_size = span["size"]
                                color_rgb = fitz.sRGB_to_pdf(span.get("color", 0))
                                
                                if new_span_text != testo_span or shift_x_accum != 0:
                                    if testo_span.strip() != "":
                                        mid_y = (rect.y0 + rect.y1) / 2
                                        thin_rect = fitz.Rect(rect.x0, mid_y - 1, rect.x1, mid_y + 1)
                                        page.add_redact_annot(thin_rect, cross_out=False)
                                    new_origin = fitz.Point(origin.x + shift_x_accum, origin.y)
                                    if new_span_text.strip() != "":
                                        insertions.append((new_origin, new_span_text, font_size, color_rgb, target_font))
                                    
                                    old_width = fitz.get_text_length(testo_span, fontname=target_font, fontsize=font_size)
                                    new_width = fitz.get_text_length(new_span_text, fontname=target_font, fontsize=font_size)
                                    shift_x_accum += (new_width - old_width)
                                    
                            extra_text = ""
                            if capo_tasto: extra_text += f" | Capo: {capo_tasto}"
                            if piano_trans: extra_text += f" | Piano: {piano_trans}"
                            
                            if extra_text and spans:
                                last_span = spans[-1]
                                last_rect = fitz.Rect(last_span["bbox"])
                                x_end = last_rect.x1 + shift_x_accum + 3
                                y_origin = last_span["origin"][1]
                                
                                font_name = last_span.get("font", "").lower()
                                is_bold = bool(last_span.get("flags", 0) & 16) or "bold" in font_name
                                target_font = "hebo" if is_bold else "helv"
                                
                                insertions.append((fitz.Point(x_end, y_origin), extra_text, last_span["size"], fitz.sRGB_to_pdf(last_span.get("color", 0)), target_font))
                                
                            continue
                            
                        is_lyric = is_lyric_span(full_line_text)
                        if not has_key and is_lyric:
                            continue
                            
                        shift_x_accum = 0
                        last_end_x = -9999
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
                            
                            is_colored = color != 0 and color != 0xFFFFFF
                            if not has_key:
                                if is_colored or (color == 0 and is_bold):
                                    if not ("http://" in testo_span or "https://" in testo_span or "www." in testo_span):
                                        pattern_nota = r"(?:DO#|REb|RE#|MIb|FA#|SOLb|SOL#|LAb|LA#|SIb|DO|RE|MI|FA|SOL|LA|SI)"
                                        pattern_accordo = rf"(?<![A-Za-z])({pattern_nota}(?:\-|m7|m|4|7|maj7|sus4|dim|9|2|sus2|add9|5|6|maj|sus|aug)*(?:\/{pattern_nota}(?:\-|m7|m|4|7|maj7|sus4|dim|9|2|sus2|add9|5|6|maj|sus|aug)*)?)(?![A-Za-z])"
                                        def replace_chord(m):
                                            return get_transposed_chord(m.group(1), semitoni, scala_riferimento)
                                        
                                        temp_text = new_span_text
                                        new_span_text = re.sub(pattern_accordo, replace_chord, new_span_text, flags=re.IGNORECASE)
                                        
                                        # Se abbiamo fatto una trasposizione e ci sono spazi, li raddoppiamo 
                                        # per garantire che gli accordi non sembrino incollati (es. SolmFa)
                                        if new_span_text != temp_text:
                                            new_span_text = new_span_text.replace(" ", "  ")
                            
                            font_size = span["size"]
                            target_x = origin.x + shift_x_accum
                            min_x = last_end_x + font_size * 0.4 # Distanza minima per staccare accordi troppo vicini/sovrapposti
                            
                            if target_x < min_x and testo_span.strip() != "":
                                target_x = min_x
                                shift_x_accum = target_x - origin.x
                            
                            if new_span_text != testo_span or shift_x_accum != 0:
                                if testo_span.strip() != "":
                                    mid_y = (rect.y0 + rect.y1) / 2
                                    thin_rect = fitz.Rect(rect.x0, mid_y - 1, rect.x1, mid_y + 1)
                                    page.add_redact_annot(thin_rect, cross_out=False)
                                new_origin = fitz.Point(target_x, origin.y)
                                color_rgb = fitz.sRGB_to_pdf(color)
                                if new_span_text.strip() != "":
                                    insertions.append((new_origin, new_span_text, font_size, color_rgb, target_font))
                                
                                old_width = fitz.get_text_length(testo_span, fontname=target_font, fontsize=font_size)
                                new_width = fitz.get_text_length(new_span_text, fontname=target_font, fontsize=font_size)
                                shift_x_accum += (new_width - old_width)
                                
                            if new_span_text.strip() != "":
                                last_end_x = target_x + fitz.get_text_length(new_span_text, fontname=target_font, fontsize=font_size)
                                    
            page.apply_redactions()
            
            for point, text, fsize, color, font in insertions:
                page.insert_text(point, text, fontsize=fsize, fontname=font, color=color)

    # Restituisce i byte del nuovo PDF e la tonalità originale trovata
    return doc.write(), tonalita_originale