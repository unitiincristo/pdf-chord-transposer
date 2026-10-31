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
                    has_colored_spans = any(s.get("color", 0) != 0 and s.get("color", 0) != 0xFFFFFF and s.get("text", "").strip() != "" for s in spans)
                    if has_colored_spans:
                        for s in spans:
                            col = s.get("color", 0)
                            if col != 0 and col != 0xFFFFFF and s.get("text", "").strip() != "":
                                s_rect = fitz.Rect(s["bbox"])
                                page.draw_rect(s_rect, color=(1, 1, 1), fill=(1, 1, 1))
                        continue

                    # 2. Controllo intestazione in alto con 'ton. XXX' (es. "DEGNO DI OGNI LODE SEI (Worthy Of It All) ton. Sib maschile")
                    pattern_header_ton = r'\s*(?:[-–|/]\s*)?(?:\(?\s*(?:ton\.?|tonalit[àa]|tonalita|key)[:\s]*[A-Za-z#b\-]+(?:\s*\(?(?:maschile|femminile)\)?)?\s*\)?)\s*$'
                    if re.search(pattern_header_ton, full_line_text, flags=re.IGNORECASE):
                        cleaned_title = re.sub(pattern_header_ton, '', full_line_text, flags=re.IGNORECASE).strip()
                        rect = fitz.Rect(line["bbox"])
                        rect.y0 -= 1
                        rect.y1 += 1
                        rect.x1 += 2
                        page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
                        
                        first_span = spans[0]
                        font_name = first_span.get("font", "").lower()
                        is_bold = bool(first_span.get("flags", 0) & 16) or "bold" in font_name
                        target_font = "hebo" if is_bold else "helv"
                        fsize = first_span["size"]
                        color = fitz.sRGB_to_pdf(first_span.get("color", 0))
                        
                        origin_x = first_span["origin"][0]
                        if line["bbox"][2] > page.rect.width * 0.7:
                            old_w = fitz.get_text_length(full_line_text, fontname=target_font, fontsize=fsize)
                            new_w = fitz.get_text_length(cleaned_title, fontname=target_font, fontsize=fsize)
                            origin_x += (old_w - new_w)
                            
                        origin = fitz.Point(origin_x, first_span["origin"][1])
                        insertions.append((origin, cleaned_title, fsize, color, target_font))
                        continue

                    # 3. Controllo riga BPM / Tonalità (es. "BPM: 74 – 4/4 Tonalità Sib maschile")
                    pattern_bpm_ton = r'\s*(?:[-–|/]\s*)?(?:Tonalit[àa]|Tonalita|Key)[:\s]+[A-Za-z#b\-]+(?:\s*\(?(?:maschile|femminile)\)?)?\s*(?:[-–|/]\s*)?'
                    has_key = bool(re.search(r"(Key|Tonalit[àa]|Tonalita)[:\s]+([A-Za-z#b\-]+)", full_line_text, flags=re.IGNORECASE))
                    if has_key:
                        cleaned_bpm = re.sub(pattern_bpm_ton, ' ', full_line_text, flags=re.IGNORECASE)
                        cleaned_bpm = re.sub(r'\s+', ' ', cleaned_bpm).strip(' -–|/\t')
                        rect = fitz.Rect(line["bbox"])
                        rect.y0 -= 1
                        rect.y1 += 1
                        rect.x1 += 2
                        page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
                        
                        if cleaned_bpm:
                            first_span = spans[0]
                            font_name = first_span.get("font", "").lower()
                            is_bold = bool(first_span.get("flags", 0) & 16) or "bold" in font_name
                            target_font = "hebo" if is_bold else "helv"
                            fsize = first_span["size"]
                            color = fitz.sRGB_to_pdf(first_span.get("color", 0))
                            origin = fitz.Point(first_span["origin"])
                            insertions.append((origin, cleaned_bpm, fsize, color, target_font))
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
    section_keywords = [
        "VERSE", "CHORUS", "BRIDGE", "INTRO", "INTERLUDE", "CORO", "VERSO", 
        "FINAL", "ENDING", "END", "OUTRO", "PRE CHORUS", "PRE-CHORUS", "VAMP", 
        "INSTRUMENTAL", "TAG", "STROFA"
    ]
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
        pw = page.rect.width
        ph = page.rect.height
        
        all_lines = []
        for b in page.get_text("dict").get("blocks", []):
            if b.get("type") == 0:
                for l in b.get("lines", []):
                    txt = "".join(s.get("text", "") for s in l.get("spans", [])).strip()
                    if txt:
                        all_lines.append(l)
                        
        all_lines.sort(key=lambda l: (l["bbox"][1], l["bbox"][0]))
        
        # Calcolo dinamico dell'altezza intestazione
        bpm_y1 = None
        if pno == 0:
            for l in all_lines:
                txt = "".join(s.get("text", "") for s in l.get("spans", [])).strip()
                if re.search(r'(?:BPM|Tempo|Tonalit[àa]|Tonalita|Key)[:\s]+', txt, flags=re.IGNORECASE):
                    if bpm_y1 is None or l["bbox"][3] > bpm_y1:
                        bpm_y1 = l["bbox"][3]
            header_threshold = (bpm_y1 + 5.0) if bpm_y1 is not None else 95.0
        else:
            header_threshold = 35.0
        
        header_lines = []
        footer_lines = []
        body_lines = []
        
        for l in all_lines:
            y0 = l["bbox"][1]
            txt = "".join(s.get("text", "") for s in l.get("spans", [])).strip()
            upper = txt.upper()
            has_sec = any(upper.startswith(kw) for kw in section_keywords)
            
            # Controllo se è piè di pagina (vicino al fondo e con font piccolo <= 8.5 o parole chiave footer)
            spans = l.get("spans", [])
            is_ftr = False
            if y0 > ph - 75:
                fsize = spans[0].get("size", 10) if spans else 10
                if fsize <= 8.5 or re.search(r'^(?:p\s*a\s*g|page|\d+$|©|tel|fax|via\s)', txt, flags=re.IGNORECASE):
                    is_ftr = True
            
            # Se ha una sezione (es. INTRO, VERSE) non è mai un header
            if y0 < header_threshold and not has_sec:
                header_lines.append(l)
            elif is_ftr:
                footer_lines.append(l)
            else:
                body_lines.append(l)
                
        # Bulletproof 2-column detection: conta righi di testo/sezione che iniziano a dx e a sx
        left_lyrics = 0
        right_lyrics = 0
        for l in body_lines:
            txt = "".join(s.get("text", "") for s in l.get("spans", [])).strip()
            is_sec = any(txt.upper().startswith(kw) for kw in section_keywords)
            is_lyr = is_lyric_span(txt)
            if is_sec or is_lyr:
                if l["bbox"][0] >= pw * 0.45:
                    right_lyrics += 1
                else:
                    left_lyrics += 1
        has_two_cols = (left_lyrics >= 3 and right_lyrics >= 3)
        
        # Redact page text
        page.add_redact_annot(page.rect)
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
        
        def insert_span_text(p, pt, text, size, font_name, flags, color_int):
            if "+" in font_name:
                font_name = font_name.split("+")[1]
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

        # 1. Intestazioni / Metadati
        pattern_header_ton = r'\s*(?:[-–|/]\s*)?(?:\(?\s*(?:ton\.?|tonalit[àa]|tonalita|key)[:\s]*[A-Za-z#b\-]+(?:\s*\(?(?:maschile|femminile)\)?)?\s*\)?)\s*$'
        pattern_bpm_ton = r'\s*(?:[-–|/]\s*)?(?:Tonalit[àa]|Tonalita|Key)[:\s]+[A-Za-z#b\-]+(?:\s*\(?(?:maschile|femminile)\)?)?\s*(?:[-–|/]\s*)?'
        
        max_hdr_y = 0
        for hl in header_lines:
            spans = hl.get("spans", [])
            if not spans:
                continue
            full_txt = "".join(s.get("text", "") for s in spans).strip()
            max_hdr_y = max(max_hdr_y, hl["bbox"][3])
            
            is_hdr_ton = bool(re.search(pattern_header_ton, full_txt, flags=re.IGNORECASE))
            is_bpm_ton = bool(re.search(pattern_bpm_ton, full_txt, flags=re.IGNORECASE))
            
            if is_hdr_ton:
                cleaned_txt = re.sub(pattern_header_ton, '', full_txt, flags=re.IGNORECASE).strip()
                first_s = spans[0]
                origin = fitz.Point(first_s["origin"])
                if hl["bbox"][2] > pw * 0.7:
                    old_w = fitz.get_text_length(full_txt, fontname="helv", fontsize=first_s["size"])
                    new_w = fitz.get_text_length(cleaned_txt, fontname="helv", fontsize=first_s["size"])
                    origin = fitz.Point(origin.x + (old_w - new_w), origin.y)
                insert_span_text(page, origin, cleaned_txt, first_s["size"], first_s["font"], first_s.get("flags", 0), first_s.get("color", 0))
                continue
                
            if is_bpm_ton:
                cleaned_bpm = re.sub(pattern_bpm_ton, ' ', full_txt, flags=re.IGNORECASE)
                cleaned_bpm = re.sub(r'\s+', ' ', cleaned_bpm).strip(' -–|/\t')
                if cleaned_bpm:
                    first_s = spans[0]
                    origin = fitz.Point(first_s["origin"])
                    insert_span_text(page, origin, cleaned_bpm, first_s["size"], first_s["font"], first_s.get("flags", 0), first_s.get("color", 0))
                continue
                
            for s in spans:
                insert_span_text(page, fitz.Point(s["origin"]), s["text"], s["size"], s["font"], s.get("flags", 0), s.get("color", 0))

        # 2. Raggruppamento e compattamento del corpo testo
        def merge_lines_horizontal(lines_to_merge):
            visual_lines = []
            for l in lines_to_merge:
                y0 = l["bbox"][1]
                placed = False
                for vl in visual_lines:
                    if abs(vl["y0"] - y0) < 3.0:
                        vl["spans"].extend(l["spans"])
                        vl["y0"] = min(vl["y0"], l["bbox"][1])
                        vl["y1"] = max(vl["y1"], l["bbox"][3])
                        vl["x0"] = min(vl["x0"], l["bbox"][0])
                        vl["x1"] = max(vl["x1"], l["bbox"][2])
                        placed = True
                        break
                if not placed:
                    visual_lines.append({
                        "y0": l["bbox"][1],
                        "y1": l["bbox"][3],
                        "x0": l["bbox"][0],
                        "x1": l["bbox"][2],
                        "spans": list(l["spans"])
                    })
            visual_lines.sort(key=lambda vl: vl["y0"])
            for vl in visual_lines:
                vl["spans"].sort(key=lambda s: s["bbox"][0])
            return visual_lines

        if has_two_cols:
            col0_raw = [l for l in body_lines if l["bbox"][0] < pw * 0.48]
            col1_raw = [l for l in body_lines if l["bbox"][0] >= pw * 0.48]
            cols = [merge_lines_horizontal(col0_raw), merge_lines_horizontal(col1_raw)]
        else:
            cols = [merge_lines_horizontal(body_lines)]

        start_y = max_hdr_y + 18 if (pno == 0 and max_hdr_y > 0) else (115 if pno == 0 else 50)
        
        for col_idx, c_lines in enumerate(cols):
            curr_y = start_y
            
            for line_data in c_lines:
                spans = line_data["spans"]
                full_text = ""
                prev_s = None
                for s in spans:
                    t = s.get("text", "")
                    if not t:
                        continue
                    if prev_s is not None:
                        gap = s["bbox"][0] - prev_s["bbox"][2]
                        if gap > 2.0 and not full_text.endswith(" ") and not t.startswith(" "):
                            full_text += " "
                    full_text += t
                    prev_s = s
                
                clean_text = full_text.strip()
                if not clean_text:
                    continue
                    
                upper = clean_text.upper()
                is_lyric = is_lyric_span(clean_text)
                has_sec = any(upper.startswith(kw) for kw in section_keywords)
                
                words_no_parens = re.sub(r'\(.*?\)|\[.*?\]', '', clean_text)
                all_chords = re.findall(pattern_accordo, words_no_parens, flags=re.IGNORECASE)
                
                prefix_match = re.match(r'^((?:INTRO|ENDING|INSTRUMENTAL|CORO|VERSO|BRIDGE|TAG|STROFA|END|OUTRO)\s*:?)(.*)$', clean_text, flags=re.IGNORECASE)
                if prefix_match and all_chords:
                    text_to_draw = prefix_match.group(1).strip()
                    is_section = True
                elif has_sec and (not all_chords or not is_lyric):
                    text_to_draw = clean_text
                    is_section = True
                elif is_lyric:
                    text_to_draw = clean_text
                    is_section = False
                else:
                    # Riga di soli accordi -> salta
                    continue
                    
                first_s = spans[0]
                fsize = first_s["size"]
                font = first_s["font"]
                flags = first_s.get("flags", 0)
                color = first_s.get("color", 0)
                if color != 0 and color != 0xFFFFFF and not is_section:
                    color = 0
                
                if is_section and curr_y > start_y:
                    curr_y += fsize * 0.8
                    
                insert_x = line_data["x0"]
                insert_y = curr_y + fsize * 0.95
                pt = fitz.Point(insert_x, insert_y)
                
                insert_span_text(page, pt, text_to_draw, fsize, font, flags, color)
                curr_y += fsize * 1.35

        # 3. Piè di pagina (inseriti in fondo)
        for fl in footer_lines:
            for s in fl.get("spans", []):
                insert_span_text(page, fitz.Point(s["origin"]), s["text"], s["size"], s["font"], s.get("flags", 0), s.get("color", 0))

def transponi_pdf(pdf_bytes, tonalita_obiettivo, capo_tasto=None, piano_trans=None, solo_testo=False, solo_testo_layout=False, **kwargs):
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
