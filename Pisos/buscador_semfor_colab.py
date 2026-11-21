# ═══════════════════════════════════════════════════════════════════════
# 🏠 BUSCADOR SEMÀFOR LIB — Google Colab
# ═══════════════════════════════════════════════════════════════════════
# Escriu la ciutat, executa, i veuràs el semàfor amb tots els pisos.
# Cada pis té link directe al portal original.
#
# INSTRUCCIONS:
# 1. Canvia CIUTAT i els paràmetres si vols
# 2. Executa tota la cel·la (Ctrl+Enter)
# 3. Espera 1-2 minuts
# 4. Veuràs el semàfor amb links directes
# ═══════════════════════════════════════════════════════════════════════

# ══ CONFIGURACIÓ — CANVIA AQUÍ ══════════════════════════════════════
CIUTAT = "Martorell"        # ← CANVIA PER LA CIUTAT QUE VULGUIS
PREU_MIN = 30000
PREU_MAX = 70000
HIPOTECA_PCT = 80            # %
INTERES_FIX = 3.50           # %
CCAA = "Cataluña"            # Per calcular ITP
# ════════════════════════════════════════════════════════════════════

import requests, re, time, random, json, hashlib
from bs4 import BeautifulSoup
from IPython.display import HTML, display
from urllib.parse import quote_plus

ITP = {
    'Cataluña':0.10,'Aragón':0.08,'Comunidad de Madrid':0.06,
    'Comunidad Valenciana':0.10,'Andalucía':0.07,'Galicia':0.09,
    'País Vasco':0.04,'Castilla y León':0.08,'Castilla-La Mancha':0.09,
    'Murcia':0.08,'Canarias':0.065,'Navarra':0.06,'Extremadura':0.08,
    'Asturias':0.08,'Cantabria':0.10,'La Rioja':0.07,'Baleares':0.08,
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.9,ca;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

RENDES_BASE = {1: 380, 2: 450, 3: 520, 4: 580}

# ══ CALCULADORA LIB ═════════════════════════════════════════════════
def cuota(capital, interes, anys=25):
    r = interes / 100 / 12
    n = anys * 12
    if r == 0: return capital / n
    return capital * (r * (1+r)**n) / ((1+r)**n - 1)

def lib(preu, m2, habs, renda_mes):
    itp_rate = ITP.get(CCAA, 0.10)
    itp = preu * itp_rate
    total_compra = preu + itp + 2500
    cap_hipo = preu * HIPOTECA_PCT / 100
    entrada = preu * (1 - HIPOTECA_PCT / 100)
    cap_inv = entrada + itp + 2500
    q = cuota(cap_hipo, INTERES_FIX)
    ra = renda_mes * 12
    gastos = (50*12) + (preu*0.005) + (ra*0.10) + (ra*0.05) + (ra*0.05) + 200
    bruta = ra / preu * 100 if preu > 0 else 0
    neta = (ra - gastos) / total_compra * 100 if total_compra > 0 else 0
    per = preu / ra if ra > 0 else 999
    cf = renda_mes - q - gastos / 12
    rcap = (ra - gastos) / cap_inv * 100 if cap_inv > 0 else 0
    
    checks = []
    pts = 0
    if bruta >= 7: pts += 1; checks.append('✅ Bruta')
    else: checks.append('❌ Bruta')
    if neta >= 4: pts += 1; checks.append('✅ Neta')
    else: checks.append('❌ Neta')
    if per <= 15: pts += 1; checks.append('✅ PER')
    else: checks.append('❌ PER')
    if cf >= 0: pts += 1; checks.append('✅ CF')
    else: checks.append('❌ CF')
    
    if pts >= 4: sem = 'comprar'
    elif pts >= 2: sem = 'estudiar'
    else: sem = 'passar'
    
    return dict(bruta=round(bruta,1), neta=round(neta,1), per=round(per,1),
                cf=round(cf), rcap=round(rcap,1), quota=round(q),
                capInv=round(cap_inv), checks=checks, semfor=sem, pts=pts)

def slug(text):
    import unicodedata
    t = unicodedata.normalize('NFD', text.lower())
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', '-', t).strip('-')

# ══ SCRAPERS ════════════════════════════════════════════════════════
pisos = []
session = requests.Session()
session.headers.update(HEADERS)

def pausa(): time.sleep(random.uniform(2.5, 5.0))

print(f"🏠 Buscant pisos a {CIUTAT} ({PREU_MIN:,}–{PREU_MAX:,}€)...")
print(f"   Hipoteca {HIPOTECA_PCT}% · {INTERES_FIX}% fix · ITP {CCAA} {ITP.get(CCAA,0.10)*100:.0f}%\n")

# ── IDEALISTA ───────────────────────────────────────────────────────
def buscar_idealista():
    s = slug(CIUTAT)
    # Try different slug patterns
    slugs = [
        f"{s}-{slug(CCAA.split()[-1]) if ' ' in CCAA else slug(CCAA)}",
        s,
        f"{s}-barcelona", f"{s}-lleida", f"{s}-huesca",
        f"{s}-tarragona", f"{s}-girona", f"{s}-zaragoza",
        f"{s}-madrid", f"{s}-valencia", f"{s}-malaga",
    ]
    
    for sl in slugs:
        url = f"https://www.idealista.com/venta-viviendas/{sl}/con-precio-hasta_{PREU_MAX},precio-desde_{PREU_MIN}/"
        try:
            r = session.get(url, timeout=15, allow_redirects=True)
            if r.status_code == 200 and 'item-link' in r.text:
                print(f"  🟢 Idealista: trobat amb slug '{sl}'")
                soup = BeautifulSoup(r.text, 'html.parser')
                articles = soup.select('article.item')
                count = 0
                for art in articles:
                    try:
                        link_el = art.select_one('a.item-link')
                        if not link_el: continue
                        titol = link_el.get_text(strip=True)
                        href = link_el.get('href', '')
                        link = f"https://www.idealista.com{href}" if href.startswith('/') else href
                        
                        preu_el = art.select_one('.item-price')
                        if not preu_el: continue
                        preu = int(re.sub(r'[^\d]', '', preu_el.get_text()) or '0')
                        if preu < PREU_MIN or preu > PREU_MAX or preu == 0: continue
                        
                        habs = 0; m2 = 0; planta = ''
                        for d in art.select('.item-detail'):
                            t = d.get_text(strip=True)
                            hm = re.search(r'(\d+)\s*hab', t)
                            if hm: habs = int(hm.group(1))
                            mm = re.search(r'(\d+)\s*m²', t)
                            if mm: m2 = int(mm.group(1))
                            if any(x in t.lower() for x in ['planta','bajo','exterior','interior']):
                                planta = t
                        
                        zona = ''
                        parts = titol.split(',')
                        if len(parts) >= 2:
                            zona = parts[-2].strip() if len(parts) >= 3 else parts[-1].strip()
                        
                        desc_el = art.select_one('.item-description')
                        desc = desc_el.get_text(strip=True)[:120] if desc_el else ''
                        if any(x in desc.lower() for x in ['ocupada ilegalmente','cesión de remate','proindiviso','sin posesión']): continue
                        
                        renda = RENDES_BASE.get(min(max(habs,1),4), 420)
                        metrics = lib(preu, m2, habs, renda)
                        
                        pisos.append({**metrics, 'nom':titol, 'preu':preu, 'm2':m2,
                            'habs':habs, 'renda':renda, 'zona':zona, 'planta':planta,
                            'portal':'Idealista', 'url':link, 'desc':desc})
                        count += 1
                    except: continue
                print(f"     → {count} pisos")
                return
        except: pass
    print(f"  ⚠️ Idealista: no s'ha pogut accedir (bloqueig anti-bot)")

# ── FOTOCASA ────────────────────────────────────────────────────────
def buscar_fotocasa():
    s = slug(CIUTAT)
    url = f"https://www.fotocasa.es/es/comprar/viviendas/{s}/todas-las-zonas/l?maxPrice={PREU_MAX}&minPrice={PREU_MIN}"
    print(f"  🔍 Fotocasa...", end=" ")
    try:
        r = session.get(url, timeout=15)
        if r.status_code != 200:
            print(f"⚠️ Status {r.status_code}")
            return
        soup = BeautifulSoup(r.text, 'html.parser')
        # Fotocasa uses React, HTML might be empty - try JSON in script tags
        scripts = soup.select('script')
        count = 0
        for s_tag in scripts:
            text = s_tag.string or ''
            if '"price"' in text and '"surface"' in text:
                # Try to find property data in scripts
                prices = re.findall(r'"price"\s*:\s*(\d+)', text)
                surfaces = re.findall(r'"surface"\s*:\s*(\d+)', text)
                rooms_all = re.findall(r'"rooms"\s*:\s*(\d+)', text)
                urls_all = re.findall(r'"propertyUrl"\s*:\s*"([^"]+)"', text)
                
                for i in range(min(len(prices), len(surfaces), len(urls_all))):
                    preu = int(prices[i])
                    if preu < PREU_MIN or preu > PREU_MAX: continue
                    m2 = int(surfaces[i]) if i < len(surfaces) else 0
                    habs = int(rooms_all[i]) if i < len(rooms_all) else 2
                    purl = urls_all[i]
                    if not purl.startswith('http'): purl = f"https://www.fotocasa.es{purl}"
                    
                    renda = RENDES_BASE.get(min(max(habs,1),4), 420)
                    metrics = lib(preu, m2, habs, renda)
                    
                    if purl not in [p['url'] for p in pisos]:
                        pisos.append({**metrics, 'nom':f"Pis a {CIUTAT}", 'preu':preu,
                            'm2':m2, 'habs':habs, 'renda':renda, 'zona':CIUTAT,
                            'planta':'', 'portal':'Fotocasa', 'url':purl, 'desc':''})
                        count += 1
        
        # Also try card-based parsing
        cards = soup.select('[class*="Card"]')
        for card in cards:
            try:
                price_el = card.select_one('[class*="rice"]')
                if not price_el: continue
                preu = int(re.sub(r'[^\d]', '', price_el.get_text()) or '0')
                if preu < PREU_MIN or preu > PREU_MAX or preu == 0: continue
                
                link_el = card.select_one('a[href*="/comprar/"]')
                if not link_el: continue
                href = link_el.get('href', '')
                purl = f"https://www.fotocasa.es{href}" if href.startswith('/') else href
                
                habs = 2; m2 = 0
                for feat in card.select('[class*="eature"]'):
                    t = feat.get_text(strip=True)
                    hm = re.search(r'(\d+)\s*hab', t)
                    if hm: habs = int(hm.group(1))
                    mm = re.search(r'(\d+)\s*m', t)
                    if mm: m2 = int(mm.group(1))
                
                renda = RENDES_BASE.get(min(max(habs,1),4), 420)
                metrics = lib(preu, m2, habs, renda)
                
                if purl not in [p['url'] for p in pisos]:
                    pisos.append({**metrics, 'nom':f"Pis a {CIUTAT}", 'preu':preu,
                        'm2':m2, 'habs':habs, 'renda':renda, 'zona':CIUTAT,
                        'planta':'', 'portal':'Fotocasa', 'url':purl, 'desc':''})
                    count += 1
            except: continue
        
        print(f"{'✅ ' + str(count) + ' pisos' if count > 0 else '0 (possible renderitzat JS)'}")
    except Exception as e:
        print(f"❌ {e}")

# ── PORTALS DE BANCS ────────────────────────────────────────────────
BANCS = [
    ('Haya','hfreinmobiliaria.com'),
    ('Servihabitat','servihabitat.com'),
    ('Solvia','solvia.es'),
    ('Altamira','altamirainmuebles.com'),
    ('Aliseda','alisedainmobiliaria.com'),
    ('CaixaBank','inmuebles.caixabank.es'),
    ('Anticipa','anticiparealestate.com'),
]

def buscar_bancs():
    for nom, site in BANCS:
        q = f"site:{site} piso {CIUTAT} venta"
        url = f"https://www.google.com/search?q={quote_plus(q)}&num=5"
        print(f"  🏦 {nom}...", end=" ")
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                print(f"⚠️ {r.status_code}")
                pausa()
                continue
            
            soup = BeautifulSoup(r.text, 'html.parser')
            count = 0
            
            for a_tag in soup.select(f'a[href*="{site}"]')[:5]:
                href = a_tag.get('href', '')
                url_m = re.search(r'(https?://[^\s&"]+' + re.escape(site) + r'[^\s&"]*)', href)
                if not url_m: continue
                real_url = url_m.group(1)
                text = a_tag.get_text(strip=True)
                
                preu_m = re.search(r'(\d{2,3}[\.,]\d{3})\s*€', text)
                preu = int(preu_m.group(1).replace('.','').replace(',','')) if preu_m else 0
                if preu > 0 and (preu < PREU_MIN or preu > PREU_MAX): continue
                if preu == 0: continue  # No preu = no analitzar
                
                hm = re.search(r'(\d+)\s*hab', text.lower())
                habs = int(hm.group(1)) if hm else 2
                mm = re.search(r'(\d+)\s*m', text)
                m2 = int(mm.group(1)) if mm else 60
                
                renda = RENDES_BASE.get(min(max(habs,1),4), 420)
                metrics = lib(preu, m2, habs, renda)
                
                if real_url not in [p['url'] for p in pisos]:
                    pisos.append({**metrics, 'nom':f"{nom}: {text[:60]}", 'preu':preu,
                        'm2':m2, 'habs':habs, 'renda':renda, 'zona':CIUTAT,
                        'planta':'', 'portal':nom, 'url':real_url, 'desc':text[:100]})
                    count += 1
            
            print(f"{'✅ '+str(count) if count > 0 else '0'}")
            pausa()
        except Exception as e:
            print(f"❌ {e}")
            pausa()

# ══ EXECUTAR CERQUES ════════════════════════════════════════════════
buscar_idealista()
pausa()
buscar_fotocasa()
pausa()
buscar_bancs()

# ══ ORDENAR I MOSTRAR ═══════════════════════════════════════════════
pisos.sort(key=lambda x: (-x['pts'], -x['bruta']))

n_comprar = sum(1 for p in pisos if p['semfor'] == 'comprar')
n_estudiar = sum(1 for p in pisos if p['semfor'] == 'estudiar')
n_passar = sum(1 for p in pisos if p['semfor'] == 'passar')

print(f"\n{'='*60}")
print(f"📊 {len(pisos)} pisos trobats a {CIUTAT}")
print(f"   🟢 COMPRAR: {n_comprar}  🟡 ESTUDIAR: {n_estudiar}  🔴 PASSAR: {n_passar}")
print(f"{'='*60}")

# ══ MOSTRAR HTML AMB SEMÀFOR ════════════════════════════════════════
def color(sem):
    return {'comprar':'#22c55e','estudiar':'#eab308','passar':'#ef4444'}.get(sem,'#999')

def sem_emoji(sem):
    return {'comprar':'🟢 COMPRAR','estudiar':'🟡 ESTUDIAR','passar':'🔴 PASSAR'}.get(sem,'❓')

def ok_ko(val, threshold, higher=True):
    ok = val >= threshold if higher else val <= threshold
    c = '#22c55e' if ok else '#ef4444'
    return f'<span style="color:{c};font-weight:600">{val}</span>'

html = f"""
<div style="font-family:system-ui;max-width:800px;background:#0f1117;color:#e4e4e7;padding:16px;border-radius:12px;">
<h2 style="text-align:center;margin:0 0 4px;">🏠 Semàfor LIB — {CIUTAT}</h2>
<p style="text-align:center;color:#9ca3af;font-size:13px;margin:0 0 12px;">
{PREU_MIN:,}–{PREU_MAX:,}€ · Hipoteca {HIPOTECA_PCT}% · {INTERES_FIX}% fix · ITP {ITP.get(CCAA,0.10)*100:.0f}%
</p>
<div style="display:flex;gap:8px;justify-content:center;margin-bottom:16px;">
  <div style="background:#1a1d27;padding:10px 20px;border-radius:8px;text-align:center;border:2px solid #2a2d3a;">
    <div style="font-size:24px;font-weight:700;color:#22c55e">{n_comprar}</div><div style="font-size:11px;color:#9ca3af">🟢 COMPRAR</div>
  </div>
  <div style="background:#1a1d27;padding:10px 20px;border-radius:8px;text-align:center;border:2px solid #2a2d3a;">
    <div style="font-size:24px;font-weight:700;color:#eab308">{n_estudiar}</div><div style="font-size:11px;color:#9ca3af">🟡 ESTUDIAR</div>
  </div>
  <div style="background:#1a1d27;padding:10px 20px;border-radius:8px;text-align:center;border:2px solid #2a2d3a;">
    <div style="font-size:24px;font-weight:700;color:#ef4444">{n_passar}</div><div style="font-size:11px;color:#9ca3af">🔴 PASSAR</div>
  </div>
  <div style="background:#1a1d27;padding:10px 20px;border-radius:8px;text-align:center;border:2px solid #2a2d3a;">
    <div style="font-size:24px;font-weight:700">{len(pisos)}</div><div style="font-size:11px;color:#9ca3af">TOTAL</div>
  </div>
</div>
"""

for p in pisos:
    bc = color(p['semfor'])
    portal_colors = {'Idealista':'#1daf17','Fotocasa':'#e7430a','Habitaclia':'#ff6600'}
    pc = portal_colors.get(p['portal'], '#4a5568')
    
    html += f"""
<div style="background:#1a1d27;border-radius:10px;padding:14px;margin-bottom:10px;border-left:4px solid {bc};">
  <div style="display:flex;justify-content:space-between;align-items:start;flex-wrap:wrap;gap:4px;">
    <div>
      <span style="font-weight:600;font-size:14px;">{p['nom']}</span>
      <span style="background:rgba(255,255,255,0.06);padding:1px 6px;border-radius:4px;font-size:11px;color:#9ca3af;margin-left:4px;">{p['portal']}</span>
    </div>
    <span style="background:{bc}22;color:{bc};padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600;">{sem_emoji(p['semfor'])}</span>
  </div>
  <div style="color:#9ca3af;font-size:12px;margin:4px 0 8px;">
    💰 {p['preu']:,}€ · {p['habs']}hab · {p['m2']}m² · Renda est: {p['renda']}€/mes
  </div>
  <div style="display:grid;grid-template-columns:repeat(6,1fr);gap:4px;margin-bottom:6px;">
    <div style="background:rgba(255,255,255,0.025);padding:4px 6px;border-radius:4px;text-align:center;">
      <div style="font-size:13px;">{ok_ko(p['bruta'], 7)}%</div><div style="font-size:10px;color:#9ca3af;">Bruta</div>
    </div>
    <div style="background:rgba(255,255,255,0.025);padding:4px 6px;border-radius:4px;text-align:center;">
      <div style="font-size:13px;">{ok_ko(p['neta'], 4)}%</div><div style="font-size:10px;color:#9ca3af;">Neta</div>
    </div>
    <div style="background:rgba(255,255,255,0.025);padding:4px 6px;border-radius:4px;text-align:center;">
      <div style="font-size:13px;">{ok_ko(p['per'], 15, False)}</div><div style="font-size:10px;color:#9ca3af;">PER</div>
    </div>
    <div style="background:rgba(255,255,255,0.025);padding:4px 6px;border-radius:4px;text-align:center;">
      <div style="font-size:13px;">{ok_ko(p['cf'], 0)}€</div><div style="font-size:10px;color:#9ca3af;">CF/mes</div>
    </div>
    <div style="background:rgba(255,255,255,0.025);padding:4px 6px;border-radius:4px;text-align:center;">
      <div style="font-size:13px;">{p['rcap']}%</div><div style="font-size:10px;color:#9ca3af;">R/Cap</div>
    </div>
    <div style="background:rgba(255,255,255,0.025);padding:4px 6px;border-radius:4px;text-align:center;">
      <div style="font-size:13px;">{p['quota']}€</div><div style="font-size:10px;color:#9ca3af;">Quota</div>
    </div>
  </div>
  <div style="font-size:11px;margin-bottom:4px;">{' · '.join(p['checks'])}</div>
  <a href="{p['url']}" target="_blank" style="display:inline-block;padding:4px 10px;border-radius:5px;background:{pc};color:#fff;text-decoration:none;font-size:12px;font-weight:500;">🔗 Veure a {p['portal']}</a>
</div>"""

html += "</div>"
display(HTML(html))

# ══ GUARDAR JSON (opcional) ═════════════════════════════════════════
output = {
    'generatEl': time.strftime('%Y-%m-%d %H:%M'),
    'config': {'preuMin':PREU_MIN,'preuMax':PREU_MAX,'hipotecaPct':HIPOTECA_PCT/100,'interesFix':INTERES_FIX,'ciutats':[CIUTAT]},
    'resum': {'total':len(pisos),'comprar':n_comprar,'estudiar':n_estudiar,'passar':n_passar},
    'pisos': [{k:v for k,v in p.items() if k != 'pts'} for p in pisos],
}

with open('resultats_lib.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n💾 Guardat: resultats_lib.json")
print(f"   Per pujar a GitHub Pages: descarrega'l i posa'l a Pisos/data/")

try:
    from google.colab import files
    files.download('resultats_lib.json')
except: pass

