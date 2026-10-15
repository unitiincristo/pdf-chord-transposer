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
    pattern_accordo = rf"^{pattern_nota}(?:\-|m7|m|4|7|maj7|sus4|dim|9|2|sus2|add9|add4|5|6|maj|sus|aug)*(?:\/{pattern_nota}(?:\-|m7|m|4|7|maj7|sus4|dim|9|2|sus2|add9|add4|5|6|maj|sus|aug)*)?$"
    return bool(re.match(pattern_accordo, clean_text, flags=re.IGNORECASE))

def is_lyric_span(text):
    # Rimuovi testo tra parentesi (es. "(2^ volta per Coro)", "(intro)")
    # cosí non vengono considerate come parole di testo
    text_no_parens = re.sub(r'\(.*?\)', '', text)
    text_no_parens = re.sub(r'\[.*?\]', '', text_no_parens)
    
    words = text_no_parens.split()
    musical_keywords = {"intro", "vamp", "coro", "verso", "bridge", "instrumental", "ending", "pre-coro", "bpm", "tempo", "key", "tonalita", "tonalità", "volta", "volte", "x", "chorus", "interlude", "per", "al", "il", "la", "le", "un", "una", "solo", "tutti", "strumentale", "chitarra", "piano"}
    
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
        pattern_accordo = rf"^{pattern_nota}(?:\-|m7|m|4|7|maj7|sus4|dim|9|2|sus2|add9|add4|5|6|maj|sus|aug)*(?:\/{pattern_nota}(?:\-|m7|m|4|7|maj7|sus4|dim|9|2|sus2|add9|add4|5|6|maj|sus|aug)*)?$"
        if re.match(pattern_accordo, w_clean, flags=re.IGNORECASE):
            continue
            
        # Se c'è almeno una parola "normale", è un rigo di testo
        return True
    return False


def remove_chords_keep_layout(doc):
    section_keywords = ["VERSE", "CHORUS", "BRIDGE", "INTRO", "INTERLUDE", "CORO", "VERSO", "FINAL", "ENDING", "PRE CHORUS", "PRE-CHORUS", "VAMP", "INSTRUMENTAL", "TAG", "STROFA"]
    pattern_nota = r"(?:DO#|REb|RE#|MIb|FA#|SOLb|SOL#|LAb|LA#|SIb|DO|RE|MI|FA|SOL|LA|SI)"
    pattern_accordo = rf"(?<![A-Za-z])({pattern_nota}(?:\-|m7|m|4|7|maj7|sus4|dim|9|2|sus2|add9|add4|5|6|maj|sus|aug)*(?:\/{pattern_nota}(?:\-|m7|m|4|7|maj7|sus4|dim|9|2|sus2|add9|add4|5|6|maj|sus|aug)*)?)(?![A-Za-z])"
    
    for page in doc:
        text_dict = page.get_text("dict")
        insertions = []
        
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    full_line_text = "".join([s.get("text", "") for s in spans]).strip()
                    if not full_line_text:
                        continue
                    
                    # 1. Se la riga ha accordi colorati (es. template vecchi con accordi rossi)
                    has_colored_spans = any(s.get("color", 0) != 0 and s.get("color", 0) != 0xFFFFFF for s in spans)
                    if has_colored_spans:
                        for s in spans:
                            col = s.get("color", 0)
                            if col != 0 and col != 0xFFFFFF:
                                s_rect = fitz.Rect(s["bbox"])
                                s_rect.y0 -= 1
                                s_rect.y1 += 1
                                page.draw_rect(s_rect, color=(1, 1, 1), fill=(1, 1, 1))
                        continue

                    # 2. Se ha la tonalità (es. BPM: 74 - Tonalità Sib), non cancellare
                    has_key = bool(re.search(r"(Key|Tonalit[àa]|Tonalita)[:\s]+([A-Za-z#b\-]+)", full_line_text, flags=re.IGNORECASE))
                    if has_key:
                        continue
                        
                    is_lyric = is_lyric_span(full_line_text)
                    if is_lyric:
                        continue
                    
                    upper_line = full_line_text.upper()
                    has_sec_prefix = any(upper_line.startswith(kw) for kw in section_keywords)
                    
                    # Trova tutti gli accordi nella riga
                    words_no_parens = re.sub(r'\(.*?\)|\[.*?\]', '', full_line_text)
                    all_chords = re.findall(pattern_accordo, words_no_parens, flags=re.IGNORECASE)
                    
                    # Caso A: Etichetta pura senza accordi (es. "Verso", "CORO (x2)", "Bridge (x4)", "TAG", "Instrumental:")
                    if not all_chords and has_sec_prefix:
                        continue
                        
                    # Caso B: Sezione con accordi (es. "INTRO: | Mibsus4 /// |", "Ending: Sib")
                    prefix_match = re.match(r'^((?:INTRO|ENDING|INSTRUMENTAL|CORO|VERSO|BRIDGE|TAG|STROFA)\s*:?)(.*)$', full_line_text, flags=re.IGNORECASE)
                    if prefix_match and all_chords:
                        label = prefix_match.group(1).strip()
                        rect = fitz.Rect(line["bbox"])
                        rect.y0 -= 1
                        rect.y1 += 1
                        page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
                        
                        first_span = spans[0]
                        font_name = first_span.get("font", "").lower()
                        is_bold = bool(first_span.get("flags", 0) & 16) or "bold" in font_name
                        target_font = "hebo" if is_bold else "helv"
                        fsize = first_span["size"]
                        color = fitz.sRGB_to_pdf(first_span.get("color", 0))
                        origin = fitz.Point(first_span["origin"])
                        
                        insertions.append((origin, label, fsize, color, target_font))
                        continue
                        
                    # Caso C: Riga di soli accordi / battute
                    rect = fitz.Rect(line["bbox"])
                    rect.y0 -= 1
                    rect.y1 += 1
                    page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
                    
        for origin, text, fsize, color, font in insertions:
            page.insert_text(origin, text, fontsize=fsize, fontname=font, color=color)

def compact_solo_testo(doc):
    section_keywords = ["VERSE", "CHORUS", "BRIDGE", "INTRO", "INTERLUDE", "CORO", "VERSO", "FINAL", "ENDING", "PRE CHORUS", "PRE-CHORUS", "VAMP", "INSTRUMENTAL", "TAG", "STROFA"]
    pattern_nota = r"(?:DO#|REb|RE#|MIb|FA#|SOLb|SOL#|LAb|LA#|SIb|DO|RE|MI|FA|SOL|LA|SI)"
    pattern_accordo = rf"(?<![A-Za-z])({pattern_nota}(?:\-|m7|m|4|7|maj7|sus4|dim|9|2|sus2|add9|add4|5|6|maj|sus|aug)*(?:\/{pattern_nota}(?:\-|m7|m|4|7|maj7|sus4|dim|9|2|sus2|add9|add4|5|6|maj|sus|aug)*)?)(?![A-Za-z])"
    
    font_buffers = {}
    for f in doc[0].get_fonts():
        xref = f[0]
        basefont = f[3]
        clean_basefont = basefont.split("+")[1] if "+" in basefont else basefont
        try:
            fdata = doc.extract_font(xref)
            if fdata and len(fdata) >= 4 and fdata[3]:
                font_buffers[clean_basefont] = (f"F{xref}", fdata[3])
        except:
            pass

    for pno in range(len(doc)):
        page = doc[pno]
        page_width = page.rect.width
        page_height = page.rect.height
        
        all_lines = []
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") == 0:
                all_lines.extend(block.get("lines", []))
        all_lines.sort(key=lambda l: l["bbox"][1])
        
        header_lines = []
        footer_lines = []
        body_lines = []
        
        for line in all_lines:
            merged_spans = []
            for span in line.get("spans", []):
                if not merged_spans:
                    merged_spans.append(dict(span))
                else:
                    prev = merged_spans[-1]
                    if (not prev.get("text", "").endswith(" ") and 
                        not span.get("text", "").startswith(" ") and 
                        abs(span["bbox"][0] - prev["bbox"][2]) < 2.5):
                        prev["text"] += span.get("text", "")
                        prev["bbox"] = (prev["bbox"][0], min(prev["bbox"][1], span["bbox"][1]), 
                                        span["bbox"][2], max(prev["bbox"][3], span["bbox"][3]))
                    else:
                        merged_spans.append(dict(span))
            line["spans"] = merged_spans
            
            full_line_text = "".join(s.get("text", "") for s in merged_spans).strip()
            if not full_line_text:
                continue
                
            y0 = line["bbox"][1]
            
            is_top_header = (pno == 0 and y0 < 95) or (pno > 0 and y0 < 30)
            is_bottom_footer = (y0 > page_height - 90)
            
            if is_top_header:
                header_lines.append(line)
            elif is_bottom_footer:
                footer_lines.append(line)
            else:
                body_lines.append(line)
                
        kept_body = []
        for line in body_lines:
            spans = line["spans"]
            if any(s.get("color", 0) != 0 and s.get("color", 0) != 0xFFFFFF for s in spans):
                continue
                
            full_line_text = "".join(s.get("text", "") for s in spans).strip()
            upper_line = full_line_text.upper()
            
            is_lyric = is_lyric_span(full_line_text)
            has_sec_prefix = any(upper_line.startswith(kw) for kw in section_keywords)
            
            words_no_parens = re.sub(r'\(.*?\)|\[.*?\]', '', full_line_text)
            all_chords = re.findall(pattern_accordo, words_no_parens, flags=re.IGNORECASE)
                    
            if not is_lyric and not has_sec_prefix:
                continue
                
            prefix_match = re.match(r'^((?:INTRO|ENDING|INSTRUMENTAL|CORO|VERSO|BRIDGE|TAG|STROFA)\s*:?)(.*)$', full_line_text, flags=re.IGNORECASE)
            if prefix_match and all_chords:
                label = prefix_match.group(1).strip()
                new_spans = [{
                    "text": label,
                    "size": line["spans"][0]["size"],
                    "origin": line["spans"][0]["origin"],
                    "color": line["spans"][0].get("color", 0),
                    "font": line["spans"][0].get("font", ""),
                    "flags": line["spans"][0].get("flags", 0),
                    "bbox": line["bbox"]
                }]
                kept_body.append({
                    "spans": new_spans,
                    "is_section": True,
                    "x0": line["bbox"][0],
                    "orig_y": y0
                })
                continue
                
            is_section = has_sec_prefix or not is_lyric
            kept_body.append({
                "spans": line["spans"],
                "is_section": is_section,
                "x0": line["bbox"][0],
                "orig_y": y0
            })
            
        right_lines = [item for item in kept_body if item["x0"] > page_width * 0.45]
        left_lines = [item for item in kept_body if item["x0"] <= page_width * 0.45]
        has_two_cols = len(right_lines) >= 3 and len(left_lines) >= 3
        
        page.add_redact_annot(page.rect)
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
        
        def insert_span_text(p, pt, text, size, font_name, flags, color_int):
            if "+" in font_name: font_name = font_name.split("+")[1]
            is_bold = bool(flags & 16) or "bold" in font_name.lower()
            fallback_font = "hebo" if is_bold else "helv"
            clean_text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-")
            color = fitz.sRGB_to_pdf(color_int)
            
            inserted = False
            if font_name in font_buffers:
                fname, fbuf = font_buffers[font_name]
                try:
                    p.insert_text(pt, text, fontsize=size, fontname=fname, fontbuffer=fbuf, color=color)
                    inserted = True
                except:
                    pass
            if not inserted:
                p.insert_text(pt, clean_text, fontsize=size, fontname=fallback_font, color=color)
        
        for hline in header_lines + footer_lines:
            for s in hline["spans"]:
                insert_span_text(page, fitz.Point(s["origin"]), s["text"], s["size"], s["font"], s.get("flags", 0), s.get("color", 0))
                    
        start_y = 115 if pno == 0 else 50
        
        if not has_two_cols:
            curr_y = start_y
            for item in kept_body:
                spans = item["spans"]
                max_fsize = max(s["size"] for s in spans)
                if item["is_section"] and curr_y > start_y:
                    curr_y += max_fsize * 0.8
                
                delta_y = curr_y - spans[0]["bbox"][1]
                for s in spans:
                    pt = fitz.Point(s["origin"][0], s["origin"][1] + delta_y)
                    insert_span_text(page, pt, s["text"], s["size"], s["font"], s.get("flags", 0), s.get("color", 0))
                curr_y += max_fsize * 1.3
        else:
            col_y = {0: start_y, 1: start_y}
            for item in kept_body:
                c = 0 if item["x0"] <= page_width * 0.45 else 1
                spans = item["spans"]
                max_fsize = max(s["size"] for s in spans)
                if item["is_section"] and col_y[c] > start_y:
                    col_y[c] += max_fsize * 0.8
                delta_y = col_y[c] - spans[0]["bbox"][1]
                for s in spans:
                    pt = fitz.Point(s["origin"][0], s["origin"][1] + delta_y)
                    insert_span_text(page, pt, s["text"], s["size"], s["font"], s.get("flags", 0), s.get("color", 0))
                col_y[c] += max_fsize * 1.3

def transponi_pdf(pdf_bytes, tonalita_obiettivo, capo_tasto=None, piano_trans=None, solo_testo=False, solo_testo_layout=False):
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
        if not (solo_testo or solo_testo_layout):
            raise ValueError("Impossibile trovare la riga 'Key: XXX' o 'Tonalità: XXX' nel PDF fornito.")
        tonalita_originale = "Originale"
        
    if solo_testo_layout:
        remove_chords_keep_layout(doc)
        return doc.write(), tonalita_originale
        
    if solo_testo:
        compact_solo_testo(doc)
        return doc.write(), tonalita_originale

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

    # Itera su ogni pagina per fare la replace (LOGICA NORMALE TRASPOSIZIONE)
    for page_num in range(len(doc)):
            page = doc[page_num]
            
            text_dict = page.get_text("dict")
            insertions = []
            
            # Variabili per mantenere la spaziatura corretta
            shift_x_accum_by_y = {}
            last_end_x_by_y = {}
            
            def get_y_key(current_y, font_size, existing_keys):
                for ky in existing_keys:
                    if abs(ky - current_y) < font_size * 0.5:
                        return ky
                return current_y
            
            for block in text_dict.get("blocks", []):
                if block.get("type") == 0:
                    for line in block.get("lines", []):
                        merged_spans = []
                        for span in line.get("spans", []):
                            if not merged_spans:
                                merged_spans.append(dict(span))
                            else:
                                prev = merged_spans[-1]
                                if (not prev.get("text", "").endswith(" ") and 
                                    not span.get("text", "").startswith(" ") and 
                                    abs(span["bbox"][0] - prev["bbox"][2]) < 2.5):
                                    prev["text"] += span.get("text", "")
                                    prev["bbox"] = (prev["bbox"][0], min(prev["bbox"][1], span["bbox"][1]), 
                                                    span["bbox"][2], max(prev["bbox"][3], span["bbox"][3]))
                                else:
                                    merged_spans.append(dict(span))
                        line["spans"] = merged_spans
                        
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
                            local_shift = 0
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
                                
                                if new_span_text != testo_span or local_shift != 0:
                                    if testo_span.strip() != "":
                                        page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
                                    new_origin = fitz.Point(origin.x + local_shift, origin.y)
                                    if new_span_text.strip() != "":
                                        insertions.append((new_origin, new_span_text, font_size, color_rgb, target_font))
                                    
                                    old_width = fitz.get_text_length(testo_span, fontname=target_font, fontsize=font_size)
                                    new_width = fitz.get_text_length(new_span_text, fontname=target_font, fontsize=font_size)
                                    local_shift += (new_width - old_width)
                                    
                            extra_text = ""
                            if capo_tasto: extra_text += f" | Capo: {capo_tasto}"
                            if piano_trans: extra_text += f" | Piano: {piano_trans}"
                            
                            if extra_text and spans:
                                last_span = spans[-1]
                                last_rect = fitz.Rect(last_span["bbox"])
                                x_end = last_rect.x1 + local_shift + 3
                                y_origin = last_span["origin"][1]
                                
                                font_name = last_span.get("font", "").lower()
                                is_bold = bool(last_span.get("flags", 0) & 16) or "bold" in font_name
                                target_font = "hebo" if is_bold else "helv"
                                
                                insertions.append((fitz.Point(x_end, y_origin), extra_text, last_span["size"], fitz.sRGB_to_pdf(last_span.get("color", 0)), target_font))
                                
                            continue
                            
                        is_lyric = is_lyric_span(full_line_text)
                        if not has_key and is_lyric:
                            continue
                            
                        for span in line.get("spans", []):
                            testo_span = span.get("text", "")
                            color = span.get("color", 0)
                            flags = span.get("flags", 0)
                            font_size = span["size"]
                            font_name = span.get("font", "").lower()
                            is_bold = bool(flags & 16) or "bold" in font_name
                            target_font = "hebo" if is_bold else "helv"
                            
                            origin = fitz.Point(span["origin"])
                            rect = fitz.Rect(span["bbox"])
                            new_span_text = testo_span
                            
                            y_key = get_y_key(origin.y, font_size, shift_x_accum_by_y.keys())
                            if y_key not in shift_x_accum_by_y:
                                shift_x_accum_by_y[y_key] = 0
                                last_end_x_by_y[y_key] = -9999
                            
                            shift_x_accum = shift_x_accum_by_y[y_key]
                            last_end_x = last_end_x_by_y[y_key]
                            
                            is_colored = color != 0 and color != 0xFFFFFF
                            if not has_key:
                                if is_colored or (color == 0 and is_bold):
                                    if not ("http://" in testo_span or "https://" in testo_span or "www." in testo_span):
                                        pattern_nota = r"(?:DO#|REb|RE#|MIb|FA#|SOLb|SOL#|LAb|LA#|SIb|DO|RE|MI|FA|SOL|LA|SI)"
                                        pattern_accordo = rf"(?<![A-Za-z])({pattern_nota}(?:\-|m7|m|4|7|maj7|sus4|dim|9|2|sus2|add9|add4|5|6|maj|sus|aug)*(?:\/{pattern_nota}(?:\-|m7|m|4|7|maj7|sus4|dim|9|2|sus2|add9|add4|5|6|maj|sus|aug)*)?)(?![A-Za-z])"
                                        def replace_chord(m):
                                            return get_transposed_chord(m.group(1), semitoni, scala_riferimento)
                                        
                                        temp_text = new_span_text
                                        new_span_text = re.sub(pattern_accordo, replace_chord, new_span_text, flags=re.IGNORECASE)

                            
                            font_size = span["size"]
                            target_x = origin.x + shift_x_accum
                            min_x = last_end_x + font_size * 0.8 # Distanza minima visiva
                            
                            if target_x < min_x and testo_span.strip() != "":
                                target_x = min_x
                                shift_x_accum = target_x - origin.x
                            
                            if new_span_text != testo_span or shift_x_accum != 0:
                                if testo_span.strip() != "":
                                    page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
                                new_origin = fitz.Point(target_x, origin.y)
                                color_rgb = fitz.sRGB_to_pdf(color)
                                if new_span_text.strip() != "":
                                    insertions.append((new_origin, new_span_text, font_size, color_rgb, target_font))
                                
                                old_width = fitz.get_text_length(testo_span, fontname=target_font, fontsize=font_size)
                                new_width = fitz.get_text_length(new_span_text, fontname=target_font, fontsize=font_size)
                                shift_x_accum += (new_width - old_width)
                                
                            if new_span_text.strip() != "":
                                last_end_x = target_x + fitz.get_text_length(new_span_text.rstrip(), fontname=target_font, fontsize=font_size)
                                
                            # Salva i valori aggiornati nel dizionario per questa riga visiva
                            shift_x_accum_by_y[y_key] = shift_x_accum
                            last_end_x_by_y[y_key] = last_end_x
                                    
            for point, text, fsize, color, font in insertions:
                page.insert_text(point, text, fontsize=fsize, fontname=font, color=color)

    # Restituisce i byte del nuovo PDF e la tonalità originale trovata
    return doc.write(), tonalita_originale
