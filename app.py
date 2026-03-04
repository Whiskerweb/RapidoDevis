import streamlit as st
from fpdf import FPDF
import mock_data
import io
import json
import re 
import pdfplumber
import db # Supabase Module
import email_sender


# --- Moteur de Template (FPDF) ---
class PDF(FPDF):
    def __init__(self, color, logo_path=None, company_info=None, show_branding=True):
        super().__init__()
        self.primary_color = color # Tuple (R, G, B)
        self.logo_path = logo_path
        self.company_info = company_info or {}
        self.printing_items = True # Flag: True = Print Table Header, False = Don't (for Totals pages)
        self.show_branding = show_branding

    def format_currency(self, value):
        # Format: 1 234.56 € (with dot decimal as user requested previously, usually comma in FR)
        # User request: "2340.00 devient 2 340.00"
        return f"{value:,.2f}".replace(",", " ") + " €"
        
    def header(self):
        # Only show branding on Page 1
        if self.page_no() == 1:
            # Couleur Dynamique
            self.set_fill_color(*self.primary_color)
            # self.rect(0, 0, 210, 20, 'F') # REMOVED BANNER
            
            # Logo (si présent)
            if self.logo_path:
                try:
                    # Increased Y (margin top) from 2 to 10
                    # Increased Height (size) from 16 to 22
                    self.image(self.logo_path, x=10, y=10, h=22)
                except Exception:
                    pass
            
            # Infos Émetteur (Nom + Adresse sous le logo)
            # On descend le texte pour ne pas chevaucher le logo agrandi
            # Y=35 (Logo ends at 10+22=32)
            self.set_y(35)
            self.set_x(10)
            self.set_font('Arial', 'B', 10)
            self.set_text_color(50) # Gris foncé
            
            if self.company_info.get('name'):
                self.cell(0, 5, self.company_info['name'], ln=True)
                
            self.set_font('Arial', size=9)
            self.set_text_color(80) 
            if self.company_info.get('address'):
                 self.multi_cell(60, 4, self.company_info['address'])
                 
        # --- TABLE HEADER REPEATER ---
        # Draw the table header on every page
        # Y position depends on Page 1 or others
        
        if self.page_no() == 1:
            y_header = 75
        else:
            y_header = 10 # Top margin for continuation pages
            
        # CONDITIONAL HEADER: Only show table columns if we are printing items
        if self.printing_items:
            self.set_y(y_header)
            
            # Primary Color BG, White Text, Bold
            r, g, b = self.primary_color
            self.set_fill_color(r, g, b)
            self.set_text_color(255, 255, 255)
            self.set_font("Arial", "B", 9)
            
            # Header AVEC fill
            self.cell(10, 8, "N°", "B", 0, 'C', True)
            self.cell(85, 8, "DÉSIGNATION", "B", 0, 'L', True)
            self.cell(25, 8, "QTÉ", "B", 0, 'C', True)
            self.cell(25, 8, "P.U HT", "B", 0, 'R', True)
            self.cell(15, 8, "TVA", "B", 0, 'C', True)
            self.cell(30, 8, "TOTAL HT", "B", 1, 'R', True)
            
            self.ln(8) # Move cursor down after header
        
            self.ln(8) # Move cursor down after header
        
        # Reset colors
        self.set_text_color(0)
        self.set_fill_color(0)
        
        # --- LOGO HANDLING (Remote vs Local) ---
        # Note: self.image() normally handles URLs if libcurl is present,
        # otherwise we might need to download it. For now, we assume local path OR valid URL.


    def footer(self):
        if self.show_branding:
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.set_text_color(128)
            self.cell(0, 10, "Généré par Rapido'devis", 0, 0, 'C')


# --------------------------------------------------------------------------------
# Helper: Tint Color
# --------------------------------------------------------------------------------
def get_tint(r, g, b, factor):
    """Returns a lighter shade of the color. Factor 0-1 (1 is white)."""
    return (
        int(r + (255 - r) * factor),
        int(g + (255 - g) * factor),
        int(b + (255 - b) * factor)
    )

def generate_pdf(data, config):
    # Parsing de la couleur hex -> RGB
    hex_color = config.get('color', '#0056b3').lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    logo_path = config.get('logo_path')
    
    # Infos émetteur
    company_info = {
        "name": config.get('company_name', ""),
        "address": config.get('company_address', "")
    }

    pdf = PDF(
        color=(r, g, b), 
        logo_path=logo_path, 
        company_info=company_info,
        show_branding=config.get('show_branding', True)
    )
    # Fontes
    pdf.add_font("Arial", style="", fname="fonts/Arial.ttf")
    pdf.add_font("Arial", style="B", fname="fonts/Arial-Bold.ttf")
    pdf.add_font("Arial", style="I", fname="fonts/Arial.ttf") 
    
    pdf.add_page()
    
    # --- En-tête (Layout Fixe mais Data Dynamique) ---
    pdf.set_font("Arial", "B", 16)
    pdf.set_text_color(*(r, g, b)) 
    # Position absolue pour ESTIMATION/DEVIS
    pdf.set_xy(140, 10)
    pdf.cell(60, 8, "ESTIMATION", align='R')
    
    pdf.set_font("Arial", size=10)
    pdf.set_text_color(0)
    
    # Numéro
    pdf.set_xy(140, 17)
    pdf.cell(60, 5, f"N° {data['numero_devis']}", align='R')
    
    # Date
    pdf.set_xy(140, 22)
    pdf.cell(60, 5, f"En date du {data['date_emission']}", align='R')
    
    # Adresse Client (Position spécifique)
    # Adresse Client (Position spécifique)
    # Cadre Adresse: X=105, Y=30, W=95, H=40 (approx, ajuster selon contenu si besoin)
    pdf.set_draw_color(0)
    pdf.rect(105, 30, 95, 40)
    
    # Positionnement Contenu (Marge interne X=108, Y=33)
    pdf.set_xy(108, 33)
    
    # Nom Client (Réduit à 11 Bold)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(90, 6, data['client']['nom'], ln=True)
    
    # Adresse
    pdf.set_font("Arial", size=10) # Réduit à 10
    pdf.set_text_color(100, 116, 139) # Grayish
    
    addr_lines = data['client']['adresse'].split('\n')
    is_chantier = False
    
    for line in addr_lines:
        line = line.strip()
        if not line: continue
        
        pdf.set_x(108) # Reset X inside box
        
        if "Adresse du chantier" in line:
            is_chantier = True
            pdf.ln(1) # Petit espace avant section chantier
            pdf.set_x(108)
            pdf.set_font("Arial", "B", 9)
            pdf.set_text_color(0) # Black
            pdf.cell(90, 5, line, ln=True)
            
            pdf.set_font("Arial", size=9)
            pdf.set_text_color(100, 116, 139) 
        else:
            if is_chantier:
                 pdf.set_font("Arial", size=9)
            else:
                 pdf.set_font("Arial", size=10)
                 
            pdf.set_text_color(100, 116, 139)
            # Use MultiCell to ensure wrapping inside 90mm width
            pdf.multi_cell(89, 4, line)
            
    pdf.set_text_color(0) # Reset black
    
    pdf.set_y(85) # Ensure start Y (below header line 75 + 8 height + margin)
    
    # Pre-calc Tints
    tint_lvl1 = get_tint(r, g, b, 0.85) # Base Categories (1, 2, 3...) -> Darker
    tint_lvl2 = get_tint(r, g, b, 0.95) # Sub Categories (1.1, 1.2...) -> Lighter
    
    # --- Content Loop ---
    pdf.set_text_color(0)
    
    content = data.get('content', [])
    
    for item in content:
        # SECTION (Titre)
        if item['type'] == 'section':
             # Detect nesting level by counting dots in the first word (numbering)
             # "1" -> 0 dots -> Level 1
             # "1.1" -> 1 dot -> Level 2
             
             first_word = item['text'].split(' ')[0]
             dots = first_word.count('.')
             
             if dots == 0:
                 # Main Category (darker)
                 pdf.set_fill_color(*tint_lvl1)
             else:
                 # Sub Category (lighter)
                 pdf.set_fill_color(*tint_lvl2)
             
             pdf.ln(2) # Petit espace
             pdf.set_font("Arial", "B", 10)
             pdf.set_text_color(0) # Black Text as requested
             # pdf.set_text_color(*(r, g, b)) # Old Branding color
             
             # Cell with Fill
             pdf.cell(0, 8, item['text'], ln=True, fill=True)
             
             pdf.set_text_color(0)

        # ITEM (Article)
        elif item['type'] == 'item':
            d = item['data']
            
            # --- CALCUL DE LA HAUTEUR PRÉVISIONNELLE (COHÉSION) ---
            # On veut éviter que le titre soit sur une page et les détails sur l'autre.
            
            # 1. Estimation Title Height
            pdf.set_font("Arial", size=9)
            desc_text_clean = d['description']
            # On simule le split pour connaître le nombre de lignes (Largeur 95 si normal, 180 si text-only)
            is_text_only = (d['total_ligne'] == 0.0 and d['prix_unitaire'] == 0.0)
            title_w = 180 if is_text_only else 95 # Col N° (10) + Col Desc (85)
            
            # multi_cell(split_only=True) renvoie la liste des lignes
            title_lines = pdf.multi_cell(title_w, 5, desc_text_clean, split_only=True)
            title_h = len(title_lines) * 5
            
            # 2. Estimation Details Height
            details_h = 0
            if not is_text_only and d.get('details'):
                 pdf.set_font("Arial", size=8)
                 detail_lines = pdf.multi_cell(85, 4, d['details'], split_only=True)
                 details_h = len(detail_lines) * 4
            
            total_item_h = title_h + details_h + 5 # + marge
            
            # 3. Check Page Break
            # Seuil de sécurité bas de page (marge standard fpdf ~270-280)
            if pdf.get_y() + total_item_h > 270:
                pdf.add_page()
            
            # --- RENDERING ---
            pdf.set_font("Arial", size=9) 
            y_start = pdf.get_y()
            
            # Split Number / Description if possible for layout
            match_num = re.match(r"^(\d+(?:\.\d+)*)\s+(.*)", d['description'])
            if match_num:
                num_text = match_num.group(1)
                desc_text = match_num.group(2)
            else:
                num_text = ""
                desc_text = d['description']

            if is_text_only:
                pdf.set_x(10)
                pdf.cell(10, 5, num_text, 0, 0, 'C')
                pdf.multi_cell(180, 5, desc_text)
            else:
                # Titre Article avec support multi-ligne
                pdf.set_x(10)
                # Colonne N° (On la garde fixe en haut de l'article)
                pdf.cell(10, 5, num_text, 0, 0, 'C')
                
                # Description (Multi-ligne possible)
                # On sauvegarde le Y pour aligner les colonnes de prix après
                curr_y = pdf.get_y()
                pdf.multi_cell(85, 5, desc_text)
                end_y = pdf.get_y()
                
                # --- Colonnes de Chiffres (Alignées sur la première ligne de l'élément) ---
                # On remonte au Y initial pour poser les chiffres à droite du titre
                pdf.set_xy(105, curr_y) # 10 (marge) + 10 (N°) + 85 (Desc)
                
                # Quantité
                val_q = d.get('quantite', 0)
                try:
                    vf = float(val_q)
                    q_str = str(int(vf)) if vf.is_integer() else str(vf)
                except:
                    q_str = str(val_q)
                
                q_display = f"{q_str} {d['unite']}" if d.get('unite') else q_str
                pdf.cell(25, 5, q_display, 0, 0, 'C')
                
                # P.U
                pdf.cell(25, 5, pdf.format_currency(d['prix_unitaire']), 0, 0, 'R')
                
                # TVA
                tva_disp = f"{d.get('tva_rate', 0):g}%"
                pdf.cell(15, 5, tva_disp, 0, 0, 'C')
                
                # Total
                pdf.cell(30, 5, pdf.format_currency(d['total_ligne']), 0, 1, 'R')
                
                # On se remet au maximum entre la fin de la description et la fin des prix
                final_y = max(end_y, pdf.get_y())
                pdf.set_y(final_y)

            # 2. Détails (Texte gris)
            if not is_text_only and d.get('details'):
                pdf.set_font("Arial", size=8) 
                pdf.set_text_color(80) 
                pdf.set_x(20) 
                pdf.multi_cell(85, 4, d['details'])
                pdf.set_text_color(0) 
            
            # --- SEPARATOR LINE ---
            # Après chaque item (standard ou text-only), on tire un trait gris fin
            y_sep = pdf.get_y() + 1
            pdf.set_draw_color(220, 220, 220) # Light Gray
            pdf.line(10, y_sep, 200, y_sep)
            pdf.set_draw_color(0) # Reset Black
            pdf.set_y(y_sep + 1) # Move down slightly 
            pdf.ln(2)

    # --- Totaux ---
    pdf.ln(5)
    
    # IMPORTANT: On arrête d'afficher l'en-tête (colonnes) pour la suite (Totaux)
    # Cela garantit que si on change de page ici, la nouvelle page sera blanche (sans tableau)
    pdf.printing_items = False
    
    # Check Space for Disclaimer + Totals (~50-60mm needed)
    # If not enough space, jump to new page immediately to keep block together
    if pdf.get_y() > 220:
        pdf.add_page()
    
    # Ligne séparation
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(2)
    
    # Save Y position
    y_totals_start = pdf.get_y()
    
    # --- Disclaimer (Left) ---
    pdf.set_xy(10, y_totals_start)
    pdf.set_font("Arial", size=8)
    pdf.set_text_color(100, 116, 139) # Gray
    disclaimer = ("Ce document est une estimation et non un devis.\n"
                  "Ce document est généré automatiquement par un algorithme intelligent et "
                  "constitue une estimation indicative. Les montants indiqués sont susceptibles "
                  "d'être ajouté en cas de modification du taux de TVA en vigueur. Cette estimation "
                  "devra être confirmée par un artisan qualifié, qui établira un devis définitif prenant "
                  "en compte les spécificités de votre projet.")
    pdf.multi_cell(110, 3.5, disclaimer)
    
    # --- Totals (Right) ---
    pdf.set_y(y_totals_start)    
    # --- New Styled Totals Block ---
    pdf.ln(5)
    
    # Align Right for the text block
    # Total net HT
    pdf.set_font("Arial", size=10)
    pdf.set_text_color(0)
    pdf.cell(150, 6, "Total net HT", 0, 0, 'R')
    pdf.cell(40, 6, f"{data['total_ht']:,.2f} €".replace(',', ' ').replace('.', ','), 0, 1, 'R')
    
    # TVA Lines
    # Si on a plusieurs lignes de TVA, on les affiche toutes
    tva_lines = data.get('tva_lines', [])
    if not tva_lines and data.get('tva', 0) > 0:
        # Fallback pour compatibilité si tva_lines n'est pas présent
        tva_lines = [{"rate": "20.0", "amount": data['tva']}]
        
    for tva_item in tva_lines:
        rate_val = tva_item['rate']
        amt_val = tva_item['amount']
        pdf.set_font("Arial", size=10)
        pdf.cell(150, 6, f"TVA ({rate_val}%)", 0, 0, 'R')
        pdf.cell(40, 6, f"{amt_val:,.2f} €".replace(',', ' ').replace('.', ','), 0, 1, 'R')
    
    # Total TTC
    pdf.set_font("Arial", "B", 10)
    pdf.cell(150, 6, "Total TTC", 0, 0, 'R')
    pdf.cell(40, 6, f"{data['total_ttc']:,.2f} €".replace(',', ' ').replace('.', ','), 0, 1, 'R')
    
    pdf.ln(4)
    
    # --- "Net à payer" Banner ---
    # Green/Primary Color Background
    pdf.set_fill_color(*(r, g, b))
    # White Text
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 14)
    
    # Draw Background Rect manually or use Cell with Fill
    # We want it full width (190mm) or partial right aligned? 
    # User image shows Full Width or Wide Block. Let's make it full width standard.
    
    # Using Cell with Fill
    # Label "Net à payer" Left aligned inside the block? Or visual spread?
    # User image: "Net à payer" (Left part of green bar) .... "29 408,40 €" (Right part)
    
    y_banner = pdf.get_y()
    pdf.rect(10, y_banner, 190, 12, 'F') # The green bar
    
    # Text inside
    pdf.set_xy(15, y_banner + 2) # Padding left
    pdf.cell(90, 8, "Net à payer", 0, 0, 'L')
    
    pdf.set_xy(105, y_banner + 2)
    pdf.cell(90, 8, f"{data['total_ttc']:,.2f} €".replace(',', ' ').replace('.', ','), 0, 1, 'R')
    
    # Reset
    pdf.set_text_color(0)
    pdf.ln(15)
    
    return bytes(pdf.output())

# --- Moteur d'Extraction (Layout-Aware V2 Robust) ---
def extract_data_from_pdf(uploaded_file, api_key=None):
    import pdfplumber
    import re

    # Regex utilitaires
    # Numéro : D202512-1030
    re_num = re.compile(r"(ESTIMATION|DEVIS)\s+N°\s+([A-Z0-9-]+)")
    # Relaxed regex: No '^', optional degree sign variations, but STRICT format for ID
    re_num_standalone = re.compile(r"N[°o\.]?\s*([A-Z]\d{6}-\d+)")
    re_date = re.compile(r"(\d{2}/\d{2}/\d{4})")
    
    # Stratégie de fin de ligne : Total €
    # Ex: "4 440,00 €" -> On veut éviter de manger le chiffre d'avant (ex "20 % 4 440")
    # Relaxed: Allow varied whitespace (space, NBSP), optional comma/dot
    # Regex structure: (Group 1: Value) followed by euro
    re_total_end = re.compile(r"(\d{1,3}(?:[\s\u00a0\u202f]?\d{3})*[.,]\d{2})\s*€$")
    
    # Stratégie Rate : 20.0 % (inchangé mais plus souple sur l'espace)
    re_rate = re.compile(r"(\d+(?:[\s.,]\d+)?)\s*%")
    
    # Stratégie PU : 18,50 €
    # Similaire à Total mais pas forcément en fin de ligne
    re_pu = re.compile(r"(\d{1,3}(?:[\s\u00a0\u202f]?\d{3})*[.,]\d{2})\s*€")

    data = {
        "numero_devis": "INCONNU",
        "date_emission": "Non trouvée",
        "client": {"nom": "", "adresse": ""},
        "content": [],
        "total_ht": 0.0,
        "tva": 0.0,
        "total_ttc": 0.0
    }

    content_nodes = [] 

    with pdfplumber.open(uploaded_file) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            words = page.extract_words(keep_blank_chars=True, x_tolerance=3, y_tolerance=3, extra_attrs=["size"])
            
            # Définition du seuil Header selon la page
            # Page 1 : On ignore les 260 premiers pixels (Logo, Adresse...)
            # Page 2+ : On ignore juste le tout début (marge, titre répété) -> ex 50
            header_threshold = 260 if page_idx == 0 else 50
            
            lines = {}
            for w in words:
                y = round(w['top'])
                if y not in lines: lines[y] = []
                lines[y].append(w)
            
            sorted_ys = sorted(lines.keys())
            
            # STATE: Footer Supression
            # Dès qu'on détecte le début du bloc légal, on arrête de lire la page
            footer_detected = False
            
            # --- SMART SEPARATION LOGIC ---
            # Pre-process lines to handle lines where Left Column (ignored) and Right Column (Client) are on same Y
            processed_lines = []
            for y in sorted_ys:
                # Sort by X just in case
                raw_words = sorted(lines[y], key=lambda w: w['x0'])
                if not raw_words: continue
                
                # Split Logic
                # RESTRICTION: On n'applique le split 'Grand Canyon' que pour le Header (Address Separation)
                # Pour le Body (Items), on veut garder la ligne entière (Qté ... Prix ... Total)
                should_split = (y < header_threshold)
                
                current_sub_line = [raw_words[0]]
                for i in range(1, len(raw_words)):
                    w = raw_words[i]
                    prev_w = raw_words[i-1]
                    # Check Gap > 50px (Grand Canyon)
                    if should_split and (w['x0'] - prev_w['x1']) > 50:
                        processed_lines.append({'y': y, 'words': current_sub_line})
                        current_sub_line = [w]
                    else:
                        current_sub_line.append(w)
                processed_lines.append({'y': y, 'words': current_sub_line})

            # Process the Split Lines
            for p_line in processed_lines:
                y = p_line['y']
                line_words = p_line['words']
                # 1. Nettoyage préventif : On vire les mots hors-page (X > 600)
                # Le texte "fantôme" (ex: d'être ajouté...) est souvent à X=900+ ou 4000+
                # UPDATE: Force Reload
                line_words = [w for w in line_words if w['x0'] < 600]
                if not line_words: continue
                
                text_line = " ".join([w['text'] for w in line_words]).strip()
                
                # --- FOOTER DETECTION (Bloc Légal / Fin de page) ---
                if footer_detected:
                    continue

                footer_start_markers = [
                    "Modalités et conditions de règlement", 
                    "Ce document est généré",
                    "algorithme intelligent",
                    "constitue une estimation",
                    "Garantie responsabilité civile",
                    "En qualité de preneur",
                    "Conditions de règlement :"
                ]
                
                # Check si cette ligne DÉCLENCHE le mode footer
                for marker in footer_start_markers:
                    if marker in text_line:
                        footer_detected = True
                        # Si le marqueur est au milieu de la ligne (fusionné avec un item), on coupe avant
                        idx = text_line.find(marker)
                        if idx > 5: # S'il y a du texte avant (l'item), on le garde
                             text_line = text_line[:idx].strip()
                        else: # Sinon, c'est juste une ligne de footer, on la jette
                             text_line = ""
                        break
                
                if not text_line: continue

                # --- FILTRAGE HEADER/FOOTER (Classique) ---
                # On ignore les lignes contenant ces mots-clés (infos société, pagination)
                IGNORE_KEYWORDS = ["SASU au capital", "SIRET", "APE :", "N° TVA", "Page", "RAPIDO DEVIS", "Total TTC", "Total net HT", "TVA (", "DÉSIGNATION", "Code I.B.A.N", "Par prélèvement", "Code B.I.C", "Ce document est une estimation"]
                if any(k in text_line for k in IGNORE_KEYWORDS):
                    continue
                
                # Exclusion par Regex du Numéro de document (ex: D202512-1026) s'il traîne
                if re.search(r"D\d{6}-\d+", text_line):
                    continue
                
                # NOUVEAU: Filtrage Bas de page / Mentions légales
                FOOTER_KEYWORDS = ["Offre valable jusqu'au", "Bon pour accord", "Fait le :", "Signature", "À :"]
                if any(k in text_line for k in FOOTER_KEYWORDS):
                     continue
                
                # Exclusion stricte du Footer par position Y (ex: Numéro document D2025-XX en bas à droite)
                # Page A4 ~ 842 points. On coupe tout ce qui est en bas (> 800)
                if y > 800:
                    continue
                
                x_start = line_words[0]['x0']
                
                # --- METADATA (Header detection) ---
                # On ne cherche des métadonnées (Numéro, Client) QUE si on est dans la zone header
                if y < header_threshold:
                    # Numéro
                    m_num = re_num.search(text_line)
                    if m_num: 
                        data['numero_devis'] = m_num.group(2)
                    else:
                        m_num_alone = re_num_standalone.search(text_line)
                        if m_num_alone:
                             # print(f"DEBUG MATCH NUM ALONE: {m_num_alone.group(1)} in '{text_line}'")
                             data['numero_devis'] = m_num_alone.group(1)
                    
                    if "Date" in text_line or "du" in text_line:
                        m_date = re_date.search(text_line)
                        if m_date: data['date_emission'] = m_date.group(1)
                        
                    # Tentative Client (M. Machin ou Société) sur la droite
                    # X > 250
                    if x_start > 250:
                         # Ignore dates/metadata keywords
                        # Ex: "M. Eric WEISS"
                        if "Date" not in text_line and "date" not in text_line and "DEVIS" not in text_line and "ESTIMATION" not in text_line and "N°" not in text_line and "Page" not in text_line:
                            
                            # NEW: Exclude Table Headers and Totals contamination
                            if any(k in text_line for k in ["QTÉ", "P.U", "TVA", "Total", "TOTAL"]):
                                continue

                            # Si le nom est vide, c'est la première ligne du bloc -> NOM
                            if not data['client']['nom']:
                                data['client']['nom'] = text_line
                            else:
                                # Sinon c'est l'adresse
                                if len(text_line) > 5:
                                    if not data['client']['adresse']:
                                        data['client']['adresse'] = text_line
                                    else:
                                        data['client']['adresse'] += "\n" + text_line
                    
                    # IMPORTANT : On ne parse PAS de structure (Items/Sections) dans le header
                    continue
                
                # --- STRUCTURE (Body Y >= 260) ---
                
                # ... (Reste du parsing Items) ...
                
                # 1. Detection Ligne Article (Prix à la fin)
                m_total = re_total_end.search(text_line)
                
                if m_total:
                    # C'est une ligne de prix !
                    total_txt = m_total.group(1)
                    total_val = float(total_txt.replace(' ', '').replace(',', '.'))
                    
                    # On retire le Total de la ligne pour chercher le reste
                    remains = text_line[:m_total.start()].strip()
                    
                    # Cherche Taux %
                    tva_rate = 0.0
                    m_rate = re_rate.search(remains)
                    if m_rate:
                        tva_rate = float(m_rate.group(1).replace(' ','').replace(',', '.'))
                        # On retire le Taux
                        remains = remains[:m_rate.start()].strip()
                        
                        # Cherche PU €
                        pus = list(re_pu.finditer(remains))
                        if pus:
                            m_pu = pus[-1]
                            pu_txt = m_pu.group(1)
                            pu_val = float(pu_txt.replace(' ', '').replace(',', '.'))
                            
                            # On retire le PU
                            remains = remains[:m_pu.start()].strip()
                            
                            # Extraction Quantité + Unité (sur la fin de 'remains')
                            # Ex: "1.1.1 Desc... 240 m2" -> tokens: [..., '240', 'm2']
                            tokens = remains.split()
                            quantite = 1.0
                            unite = ""
                            desc_end_index = len(tokens)
                            
                            if len(tokens) > 0:
                                last = tokens[-1].replace(',', '.')
                                try:
                                    # Cas 1: Fin = Nombre "240"
                                    quantite = float(last)
                                    desc_end_index = len(tokens) - 1
                                except:
                                    # Cas 2: Fin = Unité "m2"
                                    # Si le dernier token n'est pas un nombre, c'est peut-être une unité
                                    if len(tokens) > 1:
                                        unite = tokens[-1] # "m2"
                                        second_last = tokens[-2].replace(',', '.')
                                        try:
                                            quantite = float(second_last)
                                            # On a trouvé "Nombre Unité"
                                            desc_end_index = len(tokens) - 2
                                        except:
                                            pass
                            
                            # Description = tout ce qui reste
                            description = " ".join(tokens[:desc_end_index])
                            # description = re.sub(r"^\d+(\.\d+)*\s+", "", description)
                            
                            item_data = {
                                "description": description,
                                "quantite": quantite,
                                "unite": unite, # Nouveau champ
                                "prix_unitaire": pu_val,
                                "tva_rate": tva_rate, # Nouveau champ
                                "total_ligne": total_val,
                                "details": ""
                            }
                            
                            # MERGE LOGIC: Si l'item précédent est un "Text-Only" (Header 1.1.1),
                            # et que cet item (qui a un prix) n'a pas de numéro, c'est probablement la suite/détails du header.
                            # On fusionne pour éviter d'avoir titre SEPARE de description par une ligne.
                            merged = False
                            if content_nodes and content_nodes[-1]['type'] == 'item':
                                prev = content_nodes[-1]['data']
                                prev_is_text_only = (prev['total_ligne'] == 0.0 and prev['prix_unitaire'] == 0.0 and not prev['quantite'])
                                
                                # Condition pour merge:
                                # 1. Precedent est text-only
                                # 2. Courant a un prix (déjà validé ici car on est dans le bloc if m_total)
                                # 3. Courant n'a pas de structure de numéro explicite au début (ex "1.1.2") dans sa description
                                # (Si courant a "1.1.2 Description", c'est un nouvel item, pas un merge)
                                current_desc_has_num = re.match(r"^\d+(\.\d+)+", description)
                                
                                if prev_is_text_only and not current_desc_has_num:
                                    # ON FUSIONNE
                                    # Le titre reste celui du précedent (Header)
                                    # La description du courant devient des "détails" pour le précédent
                                    if prev['details']:
                                        prev['details'] += "\n" + description
                                    else:
                                        prev['details'] = description
                                    
                                    # On recupere les valeurs chiffrées
                                    prev['quantite'] = quantite
                                    prev['unite'] = unite
                                    prev['prix_unitaire'] = pu_val
                                    prev['tva_rate'] = tva_rate
                                    prev['total_ligne'] = total_val
                                    
                                    merged = True
                            
                            if not merged:
                                content_nodes.append({'type': 'item', 'data': item_data})
                            continue

                # 2. Section (Titre) vs Text-Only Item
                # STRATEGIE ROBUSTE : Si ça commence par un numéro, c'est une structure (Section ou Item Text-Only).
                # On ne regarde plus l'indentation (x_start) qui est trompeuse.
                
                # Ex: "2.1 - Cloisons..."
                match_structure = re.match(r"^(\d+(?:\.\d+)*)\s+.*", text_line)
                is_valid_structure = False
                
                if match_structure and not m_total:
                     num_s = match_structure.group(1)
                     dots = num_s.count('.')
                     
                     if dots >= 2:
                         # Item Text Only (1.2.3) -> Toujours valide comme structure
                         is_valid_structure = True
                     else:
                         # Section (Level 0 ou 1) -> "1 - Titre" ou "1.1 - Titre"
                         # RISQUE : "19 poteaux" dans une description indentée
                         # SOLUTION : On exige soit un tiret de séparation, soit une indentation faible (Header)
                         has_hyphen = re.search(r"\s+[-–]\s+", text_line)
                         is_left_aligned = (x_start < 50)
                         
                         if has_hyphen or is_left_aligned:
                             is_valid_structure = True
                
                if is_valid_structure:
                     # C'est soit une SECTION (Header) soit un ITEM TEXT-ONLY (3.3.3)
                     # Distinction ? Souvent Section = "X" ou "X.Y", Item = "X.Y.Z"
                     # L'utilisateur veut: 1.2.3 -> item text only (pas de couleur de fond).
                     
                     num_s = match_structure.group(1)
                     dots = num_s.count('.')
                     
                     # Si c'est profond (2 points ou plus -> 1.1.1), on traite comme Item Text-Only
                     if dots >= 2:
                         item_data = {
                            "description": text_line,
                            "quantite": "",
                            "unite": "",
                            "prix_unitaire": 0.0,
                            "tva_rate": 0.0,
                            "total_ligne": 0.0,
                            "details": ""
                         }
                         content_nodes.append({'type': 'item', 'data': item_data})
                     else:
                         # Sinon (0 ou 1 point -> 1 ou 1.1), c'est une Section (Titre coloré)
                         content_nodes.append({'type': 'section', 'text': text_line})
                     continue

                # 3. Détails (Texte indenté)
                if x_start > 55 and not m_total:
                     if content_nodes and content_nodes[-1]['type'] == 'item':
                         prev = content_nodes[-1]['data']
                         
                         # LOGIQUE FONT SIZE : Distinguer "Suite du Titre" vs "Détails"
                         # Titre (9.0) vs Details (7.7)
                         # Moyenne taille police de la ligne
                         avg_size = sum(w['size'] for w in line_words) / len(line_words)
                         is_title_continuation = (avg_size > 8.5)
                         
                         # Cas Spécial : Si l'item précédent est "Text-Only", tout est suite du titre/desc
                         is_prev_text_only = (prev['total_ligne'] == 0 and not prev['quantite'])
                         
                         if is_prev_text_only or is_title_continuation:
                             prev['description'] += " " + text_line
                         else:
                             if prev['details']:
                                 prev['details'] += " " + text_line
                             else:
                                 prev['details'] = text_line
                         continue

                # 4. Fallback: Titre Multi-lignes (Left Aligned but no number)
                # Ex: "rampants" (suite du titre)
                # Si on est ici, ce n'est NI un Price, NI une Structure Validée, NI un Détail indenté (>55).
                # Si c'est aligné à gauche (< 55), c'est probablement la suite du titre de l'item précédent.
                if x_start < 55:
                     if content_nodes:
                         prev_node = content_nodes[-1]
                         if prev_node['type'] == 'item':
                             # On ajoute au titre (description)
                             prev_node['data']['description'] += " " + text_line
                         elif prev_node['type'] == 'section':
                             # On ajoute au titre de section
                             prev_node['text'] += " " + text_line
                     continue

    # 3. Totaux & TVA
    # On scanne les dernières lignes pour trouver les totaux
    # Format analysé : "TVA (20.0%) 4 901,40 €"
    # "Total TTC 29 408,40 €"
    
    # On va chercher dans les textes extraits précédemment ou refaire un passage sur la fin
    # Le plus simple est de regexer sur le contenu texte global ou ligne par ligne
    
    # Regex robustes
    re_tva_line = re.compile(r"TVA\s*\((\d+(?:[\.,]\d+)?)%\)\s+(\d+(?:[\s]\d+)*,\d{2})\s+€")
    re_ttc_line = re.compile(r"Total TTC\s+(\d+(?:[\s]\d+)*,\d{2})\s+€")
    # Pour le HT, souvent non explicite ou calculé. On va essayer de le trouver ou le recalculer.
    re_ht_line = re.compile(r"Total (?:net )?HT\s+(\d+(?:[\s]\d+)*,\d{2})\s+€")

    # On utilise 'text_content' accumulé si possible, ou on relit.
    # Ici on va relire tout le texte pour assurer le coup sur les totaux qui peuvent être n'importe où (fin de page)
    full_text = ""
    with pdfplumber.open(uploaded_file) as pdf:
        for p in pdf.pages: full_text += p.extract_text() + "\n"
        
    # FALLBACK EXTRACTION NUMERO
    # Si inconnu ou trop court (ex: juste "D"), on tente le fallback
    if data['numero_devis'] == "INCONNU" or len(data['numero_devis']) < 5:
        print("DEBUG: Triggering fallback for Numero")
        # Regex sur le format DYYYYMM-XXXX (Lettre + 6 chiffres + tiret + chiffres)
        m_fallback = re.search(r"\b([A-Z]\d{6}-\d+)\b", full_text)
        if m_fallback:
            data['numero_devis'] = m_fallback.group(1)

    # Extraction de toutes les lignes de TVA
    tva_lines_found = re_tva_line.findall(full_text)
    data['tva_lines'] = []
    total_tva_extracted = 0.0
    
    for rate_str, amount_str in tva_lines_found:
        rate = rate_str.strip()
        amount = float(amount_str.replace(' ', '').replace(',', '.'))
        data['tva_lines'].append({"rate": rate, "amount": amount})
        total_tva_extracted += amount
    
    # On garde 'tva' pour la compatibilité (somme totale)
    data['tva'] = total_tva_extracted
         
    m_ttc = re_ttc_line.search(full_text)
    if m_ttc:
        data['total_ttc'] = float(m_ttc.group(1).replace(' ', '').replace(',', '.'))
        
    m_ht = re_ht_line.search(full_text)
    if m_ht:
        data['total_ht'] = float(m_ht.group(1).replace(' ', '').replace(',', '.'))
    elif data['total_ttc'] and data['tva']:
        # Fallback calculé
        data['total_ht'] = data['total_ttc'] - data['total_tva_extracted'] if 'total_tva_extracted' in locals() else data['total_ttc'] - data['tva']

    data['content'] = content_nodes
    return data


def main():
    st.set_page_config(page_title="Rapido'Devis", page_icon="🚀", layout="wide")
    
    # --- CSS IMPROVEMENTS ---
    st.markdown("""
        <style>
        .stButton button {
            width: 100%;
            border-radius: 8px;
            font-weight: bold;
        }
        .step-container {
            background-color: #f0f2f6;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
        }
        </style>
    """, unsafe_allow_html=True)

    # --- SESSION STATE NAV ---
    if 'step' not in st.session_state:
        st.session_state['step'] = 'home'
    if 'selected_template' not in st.session_state:
        st.session_state['selected_template'] = None
    if 'extracted_data' not in st.session_state:
        st.session_state['extracted_data'] = None

    # =========================================================
    # VIEW: HOME (TEMPLATE MANAGEMENT)
    # =========================================================
    if st.session_state['step'] == 'home':
        st.title("🎨 Rapido'Devis - Dashboard")
        
        # --- ACTION BAR ---
        c1, c2 = st.columns([3, 1])
        with c1:
            st.info("Bienvenue ! Configurez vos identités visuelles (Templates) ci-dessous, ou lancez un nouveau devis.")
        with c2:
            if st.button("🚀 NOUVEAU DEVIS", type="primary", use_container_width=True):
                st.session_state['step'] = 'select_template'
                st.rerun()

        st.divider()

        # --- TEMPLATE MANAGER ---
        st.subheader("Mes Templates")
        
        # 1. LIST EXISTING
        templates = db.get_templates()
        if templates:
            cols = st.columns(3)
            for i, t in enumerate(templates):
                with cols[i % 3]:
                    with st.container(border=True):
                        st.markdown(f"### {t['name']}")
                        st.caption(t['company_name'])
                        if t['logo_url']:
                            st.image(t['logo_url'], width=100)
                        else:
                            st.text("Pas de logo")
                        st.color_picker("Couleur", t['primary_color'], disabled=True, key=f"c_view_{t['id']}")
                        
                        # --- ACTIONS: EDIT & DELETE ---
                        c_edit, c_del = st.columns(2)
                        
                        with c_edit:
                            with st.popover("📝 Éditer"):
                                with st.form(f"edit_form_{t['id']}"):
                                    st.write(f"Modifier **{t['name']}**")
                                    e_name = st.text_input("Nom", value=t['name'])
                                    e_comp = st.text_input("Société", value=t['company_name'])
                                    e_addr = st.text_area("Adresse", value=t['company_address'])
                                    e_col = st.color_picker("Couleur", value=t['primary_color'])
                                    e_logo = st.file_uploader("Modifier Logo (optionnel)", type=['png', 'jpg'], key=f"logo_edit_{t['id']}")
                                    existing_emails = ", ".join(t.get('emails', []) or [])
                                    e_emails = st.text_input("Emails (séparés par des virgules)", value=existing_emails, key=f"emails_edit_{t['id']}")
                                    
                                    if st.form_submit_button("Sauvegarder Changes"):
                                        logo_url = t['logo_url']
                                        if e_logo:
                                            logo_url = db.upload_logo(e_logo, e_logo.name)
                                        
                                        if db.update_template(t['id'], e_name, e_comp, e_addr, e_col, logo_url):
                                            # Update emails separately
                                            emails_list = [e.strip() for e in e_emails.split(',') if e.strip()] if e_emails else []
                                            db.update_template_emails(t['id'], emails_list)
                                            st.success("Mis à jour !")
                                            st.rerun()
                        
                        with c_del:
                            if st.button("🗑️ Supprimer", key=f"del_{t['id']}", type="secondary", use_container_width=True):
                                if db.delete_template(t['id']):
                                    st.toast(f"Template '{t['name']}' supprimé")
                                    st.rerun()
                        
        else:
            st.warning("Aucun template configuré. Créez-en un pour commencer !")

        st.divider()
        
        # 2. CREATE NEW
        with st.expander("➕ Ajouter un nouveau Template", expanded=False):
            with st.form("new_template"):
                st.write("Configuration de l'identité visuelle")
                c1, c2 = st.columns(2)
                with c1:
                    t_name = st.text_input("Nom du Template (ex: Rapido Sud)")
                    t_comp_name = st.text_input("Nom Société (ex: Rapido Construction)")
                    t_address_in = st.text_area("Adresse Postale")
                with c2:
                    t_color = st.color_picker("Couleur", "#0056b3")
                    t_logo = st.file_uploader("Logo", type=['png', 'jpg'])
                    t_emails = st.text_input("Emails (séparés par des virgules)", placeholder="commercial@entreprise.com, contact@entreprise.com")
                
                if st.form_submit_button("Enregistrer"):
                    if not t_name:
                        st.error("Nom obligatoire")
                    else:
                        logo_url = None
                        if t_logo:
                            logo_url = db.upload_logo(t_logo, t_logo.name)
                        
                        result = db.create_template(t_name, t_comp_name, t_address_in, t_color, logo_url)
                        if result:
                            # Save emails on the newly created template
                            if t_emails:
                                emails_list = [e.strip() for e in t_emails.split(',') if e.strip()]
                                new_id = result[0]['id'] if result else None
                                if new_id:
                                    db.update_template_emails(new_id, emails_list)
                            st.success("Template créé !")
                            st.rerun()

        st.divider()

        # =========================================================
        # EMAIL TEMPLATE MANAGEMENT
        # =========================================================
        st.subheader("📧 Templates d'Email")
        st.caption("Créez des modèles de mail réutilisables. Variables disponibles : `{numero_devis}`, `{client_nom}`, `{client_adresse}`, `{total_ht}`, `{total_ttc}`, `{company_name}`")

        email_templates = db.get_email_templates()
        if email_templates:
            for et in email_templates:
                with st.container(border=True):
                    et_c1, et_c2, et_c3 = st.columns([3, 1, 1])
                    with et_c1:
                        st.markdown(f"**{et['name']}**")
                        st.caption(f"Objet : {et['subject']}")
                    with et_c2:
                        with st.popover("📝 Éditer"):
                            with st.form(f"edit_email_{et['id']}"):
                                et_name = st.text_input("Nom", value=et['name'])
                                et_subject = st.text_input("Objet", value=et['subject'])
                                et_body = st.text_area("Corps du mail", value=et['body'], height=200)
                                if st.form_submit_button("Sauvegarder"):
                                    if db.update_email_template(et['id'], et_name, et_subject, et_body):
                                        st.success("Template email mis à jour !")
                                        st.rerun()
                    with et_c3:
                        if st.button("🗑️", key=f"del_et_{et['id']}", use_container_width=True):
                            if db.delete_email_template(et['id']):
                                st.toast(f"Template email '{et['name']}' supprimé")
                                st.rerun()
        else:
            st.info("Aucun template d'email. Créez-en un ci-dessous.")

        with st.expander("➕ Ajouter un template d'email", expanded=False):
            with st.form("new_email_template"):
                net_name = st.text_input("Nom du template (ex: Email classique)")
                net_subject = st.text_input("Objet", placeholder="Estimation {numero_devis} - {client_nom}")
                net_body = st.text_area(
                    "Corps du mail",
                    placeholder="Bonjour {client_nom},\n\nVeuillez trouver ci-joint l'estimation {numero_devis} d'un montant de {total_ttc} € TTC.\n\nCordialement,\n{company_name}",
                    height=200
                )
                if st.form_submit_button("Créer le template email"):
                    if not net_name or not net_subject:
                        st.error("Le nom et l'objet sont obligatoires.")
                    else:
                        if db.create_email_template(net_name, net_subject, net_body):
                            st.success("Template email créé !")
                            st.rerun()

    # =========================================================
    # VIEW: STEP 1 - SELECT TEMPLATE
    # =========================================================
    elif st.session_state['step'] == 'select_template':
        st.button("⬅️ Retour", on_click=lambda: st.session_state.update({'step': 'home'}))
        st.title("1️⃣ Choisissez l'identité visuelle")
        
        templates = db.get_templates()
        if not templates:
            st.error("Aucun template trouvé. Veuillez en créer un d'abord.")
            if st.button("Créer un template"):
                st.session_state['step'] = 'home'
                st.rerun()
        else:
            # Card selection feel using radio or selectbox
            t_names = [t['name'] for t in templates]
            choice = st.selectbox("Sélectionnez le template à utiliser pour ce devis :", t_names)
            
            # Show preview
            sel_t = next(t for t in templates if t['name'] == choice)
            
            with st.container(border=True):
                c1, c2 = st.columns([1, 4])
                with c1:
                    if sel_t['logo_url']:
                        st.image(sel_t['logo_url'], width=100)
                with c2:
                    st.subheader(sel_t['company_name'])
                    st.write(sel_t['company_address'])
                    st.color_picker("Couleur", sel_t['primary_color'], disabled=True, key="preview_col")
            
            if st.button("Valider et Continuer ➡️", type="primary"):
                st.session_state['selected_template'] = sel_t
                st.session_state['step'] = 'upload_pdf'
                st.rerun()

    # =========================================================
    # VIEW: STEP 2 - UPLOAD & EXTRACT
    # =========================================================
    elif st.session_state['step'] == 'upload_pdf':
        st.button("⬅️ Changer de template", on_click=lambda: st.session_state.update({'step': 'select_template'}))
        st.title("2️⃣ Importation du Devis Fournisseur")
        
        uploaded_file = st.file_uploader("Déposez votre PDF ici", type="pdf")
        
        if uploaded_file:
            # On lance l'analyse automatiquement dès que le fichier est présent
            with st.spinner("Analyse automatique en cours..."):
                try:
                    data = extract_data_from_pdf(uploaded_file)
                    st.session_state['extracted_data'] = data
                    st.session_state['step'] = 'preview'
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur d'extraction : {e}")

    # =========================================================
    # VIEW: STEP 3 - PREVIEW & DOWNLOAD
    # =========================================================
    elif st.session_state['step'] == 'preview':
        st.button("⬅️ Recommencer", on_click=lambda: st.session_state.update({'step': 'upload_pdf'}))
        st.title("3️⃣ Validation & Téléchargement")
        
        data = st.session_state['extracted_data']
        template = st.session_state['selected_template']
        
        c1, c2 = st.columns(2)
        with c1:
            st.success("✅ Données extraites avec succès")
            with st.expander("Voir les données JSON brutes"):
                st.json(data)
            
            # JSON Editor
            st.subheader("📝 Modifier les données")
            json_str = json.dumps(data, indent=4, ensure_ascii=False)
            json_edited = st.text_area("Éditeur JSON", value=json_str, height=300)
        
        with c2:
            st.info(f"Modèle actif : **{template['name']}**")
            
            # OPTIONS
            st.subheader("⚙️ Options")
            show_br = st.checkbox("Afficher 'Généré par Rapido'devis' sur le PDF", value=True)
            
            # NOM DU FICHIER
            st.subheader("📁 Export")
            default_filename = f"Estimation_{data.get('numero_devis', 'Inconnu')}"
            export_name = st.text_input("Nom du fichier (sans .pdf)", value=default_filename)
            
            # --- ACTION BUTTONS: Side by side ---
            btn_col1, btn_col2 = st.columns(2)
            
            with btn_col1:
                # GENERATION PDF
                if st.button("📄 Générer le PDF", type="primary", use_container_width=True):
                    try:
                        final_data = json.loads(json_edited)
                        config = {
                            "color": template['primary_color'],
                            "logo_path": template['logo_url'],
                            "company_name": template['company_name'],
                            "company_address": template['company_address'],
                            "show_branding": show_br
                        }
                        final_pdf_bytes = generate_pdf(final_data, config)
                        st.session_state['generated_pdf'] = final_pdf_bytes
                        st.session_state['generated_pdf_name'] = f"{export_name}.pdf"
                        st.rerun()
                    except json.JSONDecodeError:
                        st.error("Erreur de format JSON")
                    except Exception as e:
                        st.error(f"Erreur de génération PDF : {e}")
            
            with btn_col2:
                # SEND BY EMAIL BUTTON
                if st.button("📧 Envoyer par Mail", use_container_width=True):
                    # Generate PDF first if not already done
                    try:
                        final_data = json.loads(json_edited)
                        config = {
                            "color": template['primary_color'],
                            "logo_path": template['logo_url'],
                            "company_name": template['company_name'],
                            "company_address": template['company_address'],
                            "show_branding": show_br
                        }
                        final_pdf_bytes = generate_pdf(final_data, config)
                        st.session_state['generated_pdf'] = final_pdf_bytes
                        st.session_state['generated_pdf_name'] = f"{export_name}.pdf"
                        st.session_state['show_email_form'] = True
                        st.rerun()
                    except json.JSONDecodeError:
                        st.error("Erreur de format JSON")
                    except Exception as e:
                        st.error(f"Erreur de génération PDF : {e}")
            
            # --- DOWNLOAD BUTTON (appears after PDF generation) ---
            if st.session_state.get('generated_pdf'):
                st.download_button(
                    label="⬇️ TÉLÉCHARGER L'ESTIMATION",
                    data=st.session_state['generated_pdf'],
                    file_name=st.session_state.get('generated_pdf_name', f"{export_name}.pdf"),
                    mime="application/pdf",
                    type="primary"
                )
        
        # =========================================================
        # EMAIL SECTION (below the two columns)
        # =========================================================
        if st.session_state.get('show_email_form') and st.session_state.get('generated_pdf'):
            st.divider()
            st.subheader("📧 Envoyer l'estimation par email")
            
            email_templates = db.get_email_templates()
            if not email_templates:
                st.warning("Aucun template d'email configuré. Créez-en un depuis le Dashboard.")
            else:
                # Template selection
                et_names = [et['name'] for et in email_templates]
                selected_et_name = st.selectbox("Choisir un template d'email", et_names)
                selected_et = next(et for et in email_templates if et['name'] == selected_et_name)
                
                # Recipient email
                template_emails = template.get('emails', []) or []
                default_to = template_emails[0] if template_emails else ""
                to_email = st.text_input("Email du destinataire", value=default_to, placeholder="client@email.com")
                
                # Build template variables
                try:
                    preview_data = json.loads(json_edited)
                except:
                    preview_data = data
                
                tpl_vars = {
                    "numero_devis": preview_data.get('numero_devis', ''),
                    "client_nom": preview_data.get('client', {}).get('nom', ''),
                    "client_adresse": preview_data.get('client', {}).get('adresse', ''),
                    "total_ht": f"{preview_data.get('total_ht', 0):,.2f}".replace(',', ' ').replace('.', ','),
                    "total_ttc": f"{preview_data.get('total_ttc', 0):,.2f}".replace(',', ' ').replace('.', ','),
                    "company_name": template.get('company_name', ''),
                }
                
                # Render subject & body with variables
                rendered_subject = email_sender.render_template(selected_et['subject'], tpl_vars)
                rendered_body = email_sender.render_template(selected_et['body'], tpl_vars)
                
                # Preview
                st.text_input("Objet (aperçu)", value=rendered_subject, disabled=True)
                st.text_area("Corps du mail (aperçu)", value=rendered_body, height=200, disabled=True)
                
                # --- ACTION: Download PDF + Open mailto ---
                st.info("💡 Cliquez ci-dessous pour **télécharger le PDF** puis **ouvrir votre messagerie** avec le mail pré-rempli. Il ne vous restera qu'à joindre le PDF !")
                
                mail_col1, mail_col2 = st.columns(2)
                
                with mail_col1:
                    st.download_button(
                        label="📎 1. Télécharger le PDF",
                        data=st.session_state['generated_pdf'],
                        file_name=st.session_state.get('generated_pdf_name', 'estimation.pdf'),
                        mime="application/pdf",
                        use_container_width=True
                    )
                
                with mail_col2:
                    mailto_link = email_sender.build_mailto_link(to_email, rendered_subject, rendered_body)
                    st.markdown(
                        f'<a href="{mailto_link}" target="_blank" style="display:inline-block;width:100%;text-align:center;padding:0.6rem 1rem;background-color:#0068c9;color:white;border-radius:8px;text-decoration:none;font-weight:bold;font-size:14px;">✉️ 2. Ouvrir ma messagerie</a>',
                        unsafe_allow_html=True
                    )

if __name__ == "__main__":
    main()
