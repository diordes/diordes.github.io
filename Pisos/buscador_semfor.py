# ═══════════════════════════════════════════════════════════════════
# 🏠 BUSCADOR SEMÀFOR LIB v5.1 — Google Colab
# ═══════════════════════════════════════════════════════════════════
# Usa Selenium (Chrome headless) per buscar REALMENT als portals.
# 
# 1. Canvia CIUTAT
# 2. Executa tota la cel·la
# 3. Veuràs el semàfor amb links directes
# ═══════════════════════════════════════════════════════════════════

# ══ CONFIGURACIÓ ════════════════════════════════════════════════════
CIUTAT = "Lleida"            # ← CANVIA AQUÍ
PREU_MIN = 30000
PREU_MAX = 70000
HIPOTECA_PCT = 80
INTERES_FIX = 3.50
CCAA = "Cataluña"
# ════════════════════════════════════════════════════════════════════

# ══ INSTAL·LAR DEPENDÈNCIES (Colab) ═════════════════════════════════
import subprocess, sys

def install():
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', 'selenium', 'webdriver-manager'])
    # Install Chrome in Colab
    try:
        subprocess.run(['which', 'google-chrome'], check=True, capture_output=True)
        print("  ✅ Chrome ja instal·lat")
    except:
        print("  📦 Instal·lant Chrome...")
        subprocess.run(['apt-get', 'update', '-qq'], capture_output=True)
        subprocess.run(['apt-get', 'install', '-y', '-qq', 'chromium-browser'], capture_output=True)
        print("  ✅ Chrome instal·lat")

print("📦 Preparant entorn...")
install()

import re, time, random, json, hashlib
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from IPython.display import HTML, display
from urllib.parse import quote_plus
import unicodedata

# ══ SETUP CHROME HEADLESS ═══════════════════════════════════════════
def crear_driver():
    opts = Options()
    opts.add_argument('--headless=new')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.add_argument('--disable-gpu')
    opts.add_argument('--window-size=1920,1080')
    opts.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
    opts.add_argument('--lang=es-ES')
    opts.add_argument('--disable-blink-features=AutomationControlled')
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option('useAutomationExtension', False)
    
    try:
        # Try chromium (Colab default)
        opts.binary_location = '/usr/bin/chromium-browser'
        driver = webdriver.Chrome(options=opts)
    except:
        try:
            # Try google-chrome
            opts.binary_location = '/usr/bin/google-chrome'
            driver = webdriver.Chrome(options=opts)
        except:
            from webdriver_manager.chrome import ChromeDriverManager
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    
    # Anti-detection
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

print("🌐 Obrint navegador...")
driver = crear_driver()
print("  ✅ Navegador obert\n")

# ══ CONSTANTS ═══════════════════════════════════════════════════════
ITP = {
    'Cataluña':0.10,'Aragón':0.08,'Comunidad de Madrid':0.06,
    'Comunidad Valenciana':0.10,'Andalucía':0.07,'Galicia':0.09,
    'País Vasco':0.04,'Castilla y León':0.08,'Castilla-La Mancha':0.09,
    'Murcia':0.08,'Canarias':0.065,'Navarra':0.06,'Extremadura':0.08,
    'Asturias':0.08,'Cantabria':0.10,'La Rioja':0.07,'Baleares':0.08,
}

RENDES_BASE = {1: 380, 2: 450, 3: 520, 4: 580}
pisos = []

def slug(text):
    t = unicodedata.normalize('NFD', text.lower())
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', '-', t).strip('-')

def pausa(a=2, b=4): time.sleep(random.uniform(a, b))

# ══ CALCULADORA LIB ═════════════════════════════════════════════════
def cuota(capital, interes, anys=25):
    r = interes / 100 / 12; n = anys * 12
    if r == 0: return capital / n
    return capital * (r * (1+r)**n) / ((1+r)**n - 1)

def calc_lib(preu, m2, habs, renda_mes):
    itp_rate = ITP.get(CCAA, 0.10)
    itp = preu * itp_rate
    total = preu + itp + 2500
    cap_h = preu * HIPOTECA_PCT / 100
    cap_inv = preu * (1 - HIPOTECA_PCT/100) + itp + 2500
    q = cuota(cap_h, INTERES_FIX)
    ra = renda_mes * 12
    gastos = 600 + preu*0.005 + ra*0.20 + 200  # comunitat+IBI+mant+vac+seg+asseg
    bruta = ra/preu*100 if preu>0 else 0
    neta = (ra-gastos)/total*100 if total>0 else 0
    per = preu/ra if ra>0 else 999
    cf = renda_mes - q - gastos/12
    rcap = (ra-gastos)/cap_inv*100 if cap_inv>0 else 0
    
    pts = sum([bruta>=7, neta>=4, per<=15, cf>=0])
    sem = 'comprar' if pts>=4 else ('estudiar' if pts>=2 else 'passar')
    checks = [('✅' if bruta>=7 else '❌')+' Bruta', ('✅' if neta>=4 else '❌')+' Neta',
              ('✅' if per<=15 else '❌')+' PER', ('✅' if cf>=0 else '❌')+' CF']
    
    return dict(bruta=round(bruta,1), neta=round(neta,1), per=round(per,1),
                cf=round(cf), rcap=round(rcap,1), quota=round(q),
                capInv=round(cap_inv), checks=checks, semfor=sem, pts=pts)

# ══ IDEALISTA (Selenium) ════════════════════════════════════════════
def buscar_idealista():
    s = slug(CIUTAT)
    provincia_slugs = ['barcelona','lleida','huesca','tarragona','girona','zaragoza',
                       'madrid','valencia','malaga','sevilla','teruel','castellon',
                       'alicante','murcia','vizcaya','guipuzcoa']
    
    for prov in provincia_slugs:
        url = f"https://www.idealista.com/venta-viviendas/{s}-{prov}/con-precio-hasta_{PREU_MAX},precio-desde_{PREU_MIN}/"
        try:
            driver.get(url)
            pausa(3, 5)
            
            # Accept cookies if present
            try:
                btn = driver.find_element(By.ID, 'didomi-notice-agree-button')
                btn.click()
                pausa(1, 2)
            except: pass
            
            # Check if page has results
            try:
                driver.find_element(By.CSS_SELECTOR, 'article.item')
            except:
                continue  # Try next province slug
            
            print(f"  🟢 Idealista: trobat amb '{s}-{prov}'")
            
            # Parse results
            articles = driver.find_elements(By.CSS_SELECTOR, 'article.item')
            count = 0
            
            for art in articles:
                try:
                    link_el = art.find_element(By.CSS_SELECTOR, 'a.item-link')
                    titol = link_el.text.strip()
                    href = link_el.get_attribute('href')
                    
                    preu_el = art.find_element(By.CSS_SELECTOR, '.item-price')
                    preu_text = re.sub(r'[^\d]', '', preu_el.text)
                    if not preu_text: continue
                    preu = int(preu_text)
                    if preu < PREU_MIN or preu > PREU_MAX: continue
                    
                    details = art.find_elements(By.CSS_SELECTOR, '.item-detail')
                    habs = 0; m2 = 0; planta = ''
                    for d in details:
                        t = d.text.strip()
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
                    
                    try:
                        desc = art.find_element(By.CSS_SELECTOR, '.item-description').text[:120]
                    except: desc = ''
                    
                    if any(x in desc.lower() for x in ['ocupada ilegalmente','cesión de remate','proindiviso']): continue
                    
                    renda = RENDES_BASE.get(min(max(habs,1),4), 420)
                    metrics = calc_lib(preu, m2, habs, renda)
                    
                    pisos.append({**metrics, 'nom':titol, 'preu':preu, 'm2':m2,
                        'habs':habs, 'renda':renda, 'zona':zona, 'planta':planta,
                        'portal':'Idealista', 'url':href, 'desc':desc})
                    count += 1
                except: continue
            
            print(f"     → {count} pisos")
            
            # Page 2 if exists
            try:
                pg2 = driver.find_element(By.CSS_SELECTOR, 'a.icon-arrow-right-after')
                pg2.click()
                pausa(3, 5)
                articles2 = driver.find_elements(By.CSS_SELECTOR, 'article.item')
                count2 = 0
                for art in articles2:
                    try:
                        link_el = art.find_element(By.CSS_SELECTOR, 'a.item-link')
                        titol = link_el.text.strip()
                        href = link_el.get_attribute('href')
                        preu_el = art.find_element(By.CSS_SELECTOR, '.item-price')
                        preu = int(re.sub(r'[^\d]', '', preu_el.text) or '0')
                        if preu < PREU_MIN or preu > PREU_MAX or preu == 0: continue
                        
                        details = art.find_elements(By.CSS_SELECTOR, '.item-detail')
                        habs = 0; m2 = 0
                        for d in details:
                            t = d.text
                            hm = re.search(r'(\d+)\s*hab', t)
                            if hm: habs = int(hm.group(1))
                            mm = re.search(r'(\d+)\s*m²', t)
                            if mm: m2 = int(mm.group(1))
                        
                        zona = titol.split(',')[-2].strip() if ',' in titol else CIUTAT
                        desc = ''
                        try: desc = art.find_element(By.CSS_SELECTOR, '.item-description').text[:120]
                        except: pass
                        if any(x in desc.lower() for x in ['ocupada ilegalmente','cesión de remate','proindiviso']): continue
                        
                        renda = RENDES_BASE.get(min(max(habs,1),4), 420)
                        metrics = calc_lib(preu, m2, habs, renda)
                        pisos.append({**metrics, 'nom':titol, 'preu':preu, 'm2':m2,
                            'habs':habs, 'renda':renda, 'zona':zona, 'planta':'',
                            'portal':'Idealista', 'url':href, 'desc':desc})
                        count2 += 1
                    except: continue
                if count2: print(f"     → pàg 2: {count2} pisos més")
            except: pass
            
            return  # Found results, stop trying slugs
        except Exception as e:
            continue
    
    print(f"  ⚠️ Idealista: no trobat per '{CIUTAT}'")

# ══ FOTOCASA (Selenium) ═════════════════════════════════════════════
def buscar_fotocasa():
    s = slug(CIUTAT)
    url = f"https://www.fotocasa.es/es/comprar/viviendas/{s}/todas-las-zonas/l?maxPrice={PREU_MAX}&minPrice={PREU_MIN}"
    print(f"  🔍 Fotocasa...", end=" ")
    
    try:
        driver.get(url)
        pausa(4, 6)
        
        # Accept cookies
        try:
            btn = driver.find_element(By.ID, 'didomi-notice-agree-button')
            btn.click()
            pausa(1, 2)
        except: pass
        
        # Wait for cards to load
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[class*="re-Card"]'))
            )
        except:
            print("0 (pàgina no ha carregat)")
            return
        
        # Get page source after JS rendered
        page = driver.page_source
        
        # Extract prices and links from rendered HTML
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(page, 'html.parser')
        
        count = 0
        # Find all property links
        cards = soup.select('[class*="CardContainer"], [class*="re-Card"]')
        
        for card in cards:
            try:
                # Find link
                link_el = card.select_one('a[href*="/comprar/"], a[href*="/en-venta/"]')
                if not link_el: continue
                href = link_el.get('href', '')
                if not href: continue
                purl = f"https://www.fotocasa.es{href}" if href.startswith('/') else href
                
                # Find price
                all_text = card.get_text()
                preu_m = re.search(r'([\d\.]+)\s*€', all_text)
                if not preu_m: continue
                preu = int(preu_m.group(1).replace('.', ''))
                if preu < PREU_MIN or preu > PREU_MAX: continue
                
                # Find details
                habs = 2; m2 = 0
                hm = re.search(r'(\d+)\s*hab', all_text.lower())
                if hm: habs = int(hm.group(1))
                mm = re.search(r'(\d+)\s*m²', all_text)
                if mm: m2 = int(mm.group(1))
                
                # Title
                title_el = card.select_one('[class*="Title"], h3, [class*="title"]')
                titol = title_el.get_text(strip=True) if title_el else f"Pis a {CIUTAT}"
                
                renda = RENDES_BASE.get(min(max(habs,1),4), 420)
                metrics = calc_lib(preu, m2, habs, renda)
                
                if purl not in [p['url'] for p in pisos]:
                    pisos.append({**metrics, 'nom':titol, 'preu':preu, 'm2':m2,
                        'habs':habs, 'renda':renda, 'zona':CIUTAT,
                        'planta':'', 'portal':'Fotocasa', 'url':purl, 'desc':''})
                    count += 1
            except: continue
        
        print(f"{'✅ ' + str(count) + ' pisos' if count > 0 else '0'}")
    except Exception as e:
        print(f"❌ {e}")

# ══ PORTALS BANCS (Selenium) ════════════════════════════════════════
BANCS = [
    ('Haya','hfreinmobiliaria.com'),
    ('Solvia','solvia.es'),
    ('CaixaBank','inmuebles.caixabank.es'),
    ('Servihabitat','servihabitat.com'),
    ('Altamira','altamirainmuebles.com'),
    ('Aliseda','alisedainmobiliaria.com'),
]

def buscar_bancs():
    for nom, site in BANCS:
        q = f"site:{site} piso {CIUTAT} venta"
        url = f"https://www.google.com/search?q={quote_plus(q)}&num=5"
        print(f"  🏦 {nom}...", end=" ")
        try:
            driver.get(url)
            pausa(2, 4)
            
            links = driver.find_elements(By.CSS_SELECTOR, f'a[href*="{site}"]')
            count = 0
            
            for link_el in links[:5]:
                try:
                    href = link_el.get_attribute('href')
                    if not href or site not in href: continue
                    text = link_el.text.strip()
                    if not text: continue
                    
                    preu_m = re.search(r'(\d{2,3}[\.,]\d{3})\s*€', text)
                    if not preu_m: continue
                    preu = int(preu_m.group(1).replace('.','').replace(',',''))
                    if preu < PREU_MIN or preu > PREU_MAX: continue
                    
                    hm = re.search(r'(\d+)\s*hab', text.lower())
                    habs = int(hm.group(1)) if hm else 2
                    mm = re.search(r'(\d+)\s*m', text)
                    m2 = int(mm.group(1)) if mm else 60
                    
                    renda = RENDES_BASE.get(min(max(habs,1),4), 420)
                    metrics = calc_lib(preu, m2, habs, renda)
                    
                    if href not in [p['url'] for p in pisos]:
                        pisos.append({**metrics, 'nom':f"{nom}: {text[:60]}", 'preu':preu,
                            'm2':m2, 'habs':habs, 'renda':renda, 'zona':CIUTAT,
                            'planta':'', 'portal':nom, 'url':href, 'desc':''})
                        count += 1
                except: continue
            
            print(f"{'✅ '+str(count) if count>0 else '0'}")
        except Exception as e:
            print(f"❌ {e}")
        pausa(1, 3)

# ══════════════════════════════════════════════════════════════════
# EXECUTAR
# ══════════════════════════════════════════════════════════════════
print(f"🏠 Buscant pisos a {CIUTAT} ({PREU_MIN:,}–{PREU_MAX:,}€)")
print(f"   Hipoteca {HIPOTECA_PCT}% · {INTERES_FIX}% fix · ITP {CCAA} {ITP.get(CCAA,0.10)*100:.0f}%\n")

buscar_idealista()
pausa(2, 4)
buscar_fotocasa()
pausa(2, 4)
buscar_bancs()

driver.quit()
print("\n🌐 Navegador tancat")

# ══ ORDENAR I MOSTRAR ═══════════════════════════════════════════════
pisos.sort(key=lambda x: (-x['pts'], -x['bruta']))
n_c = sum(1 for p in pisos if p['semfor']=='comprar')
n_e = sum(1 for p in pisos if p['semfor']=='estudiar')
n_p = sum(1 for p in pisos if p['semfor']=='passar')

print(f"\n{'='*60}")
print(f"📊 {len(pisos)} pisos trobats a {CIUTAT}")
print(f"   🟢 COMPRAR: {n_c}  🟡 ESTUDIAR: {n_e}  🔴 PASSAR: {n_p}")
print(f"{'='*60}")

# ══ HTML VISUAL ═════════════════════════════════════════════════════
def ok(val, th, hi=True):
    ok = val >= th if hi else val <= th
    c = '#22c55e' if ok else '#ef4444'
    return f'<span style="color:{c};font-weight:600">{val}</span>'

def sem_e(s): return {'comprar':'🟢 COMPRAR','estudiar':'🟡 ESTUDIAR','passar':'🔴 PASSAR'}.get(s,'?')
def sem_c(s): return {'comprar':'#22c55e','estudiar':'#eab308','passar':'#ef4444'}.get(s,'#999')

html = f"""<div style="font-family:system-ui;max-width:800px;background:#0f1117;color:#e4e4e7;padding:16px;border-radius:12px;">
<h2 style="text-align:center;margin:0 0 4px;">🏠 Semàfor LIB — {CIUTAT}</h2>
<p style="text-align:center;color:#9ca3af;font-size:13px;margin:0 0 12px;">{PREU_MIN:,}–{PREU_MAX:,}€ · Hipo {HIPOTECA_PCT}% · {INTERES_FIX}% fix · ITP {ITP.get(CCAA,0.10)*100:.0f}%</p>
<div style="display:flex;gap:8px;justify-content:center;margin-bottom:16px;">
<div style="background:#1a1d27;padding:10px 20px;border-radius:8px;text-align:center;border:2px solid #2a2d3a;"><div style="font-size:24px;font-weight:700;color:#22c55e">{n_c}</div><div style="font-size:11px;color:#9ca3af">🟢 COMPRAR</div></div>
<div style="background:#1a1d27;padding:10px 20px;border-radius:8px;text-align:center;border:2px solid #2a2d3a;"><div style="font-size:24px;font-weight:700;color:#eab308">{n_e}</div><div style="font-size:11px;color:#9ca3af">🟡 ESTUDIAR</div></div>
<div style="background:#1a1d27;padding:10px 20px;border-radius:8px;text-align:center;border:2px solid #2a2d3a;"><div style="font-size:24px;font-weight:700;color:#ef4444">{n_p}</div><div style="font-size:11px;color:#9ca3af">🔴 PASSAR</div></div>
<div style="background:#1a1d27;padding:10px 20px;border-radius:8px;text-align:center;border:2px solid #2a2d3a;"><div style="font-size:24px;font-weight:700">{len(pisos)}</div><div style="font-size:11px;color:#9ca3af">TOTAL</div></div>
</div>"""

pc = {'Idealista':'#1daf17','Fotocasa':'#e7430a','Habitaclia':'#ff6600'}

for p in pisos:
    bc = sem_c(p['semfor'])
    html += f"""<div style="background:#1a1d27;border-radius:10px;padding:14px;margin-bottom:10px;border-left:4px solid {bc};">
<div style="display:flex;justify-content:space-between;align-items:start;flex-wrap:wrap;gap:4px;">
<div><span style="font-weight:600;font-size:14px;">{p['nom']}</span>
<span style="background:rgba(255,255,255,0.06);padding:1px 6px;border-radius:4px;font-size:11px;color:#9ca3af;margin-left:4px;">{p['portal']}</span></div>
<span style="background:{bc}22;color:{bc};padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600;">{sem_e(p['semfor'])}</span></div>
<div style="color:#9ca3af;font-size:12px;margin:4px 0 8px;">💰 {p['preu']:,}€ · {p['habs']}hab · {p['m2']}m² · Renda est: {p['renda']}€/mes</div>
<div style="display:grid;grid-template-columns:repeat(6,1fr);gap:4px;margin-bottom:6px;">
<div style="background:rgba(255,255,255,0.025);padding:4px 6px;border-radius:4px;text-align:center;"><div style="font-size:13px;">{ok(p['bruta'],7)}%</div><div style="font-size:10px;color:#9ca3af;">Bruta</div></div>
<div style="background:rgba(255,255,255,0.025);padding:4px 6px;border-radius:4px;text-align:center;"><div style="font-size:13px;">{ok(p['neta'],4)}%</div><div style="font-size:10px;color:#9ca3af;">Neta</div></div>
<div style="background:rgba(255,255,255,0.025);padding:4px 6px;border-radius:4px;text-align:center;"><div style="font-size:13px;">{ok(p['per'],15,False)}</div><div style="font-size:10px;color:#9ca3af;">PER</div></div>
<div style="background:rgba(255,255,255,0.025);padding:4px 6px;border-radius:4px;text-align:center;"><div style="font-size:13px;">{ok(p['cf'],0)}€</div><div style="font-size:10px;color:#9ca3af;">CF/mes</div></div>
<div style="background:rgba(255,255,255,0.025);padding:4px 6px;border-radius:4px;text-align:center;"><div style="font-size:13px;">{p['rcap']}%</div><div style="font-size:10px;color:#9ca3af;">R/Cap</div></div>
<div style="background:rgba(255,255,255,0.025);padding:4px 6px;border-radius:4px;text-align:center;"><div style="font-size:13px;">{p['quota']}€</div><div style="font-size:10px;color:#9ca3af;">Quota</div></div>
</div>
<div style="font-size:11px;margin-bottom:4px;">{' · '.join(p['checks'])}</div>
<a href="{p['url']}" target="_blank" style="display:inline-block;padding:4px 10px;border-radius:5px;background:{pc.get(p['portal'],'#4a5568')};color:#fff;text-decoration:none;font-size:12px;">🔗 Veure a {p['portal']}</a>
</div>"""

if not pisos:
    html += '<div style="text-align:center;padding:30px;color:#9ca3af;">Cap pis trobat. Prova amb una altra ciutat o rang de preus.</div>'

html += "</div>"
display(HTML(html))

# ══ GUARDAR JSON ════════════════════════════════════════════════════
output = {
    'generatEl': time.strftime('%Y-%m-%d %H:%M'),
    'config': {'preuMin':PREU_MIN,'preuMax':PREU_MAX,'hipotecaPct':HIPOTECA_PCT/100,'interesFix':INTERES_FIX,'ciutats':[CIUTAT]},
    'resum': {'total':len(pisos),'comprar':n_c,'estudiar':n_e,'passar':n_p},
    'pisos': [{k:v for k,v in p.items() if k!='pts'} for p in pisos],
}
with open('resultats_lib.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\n💾 resultats_lib.json guardat ({len(pisos)} pisos)")

try:
    from google.colab import files
    files.download('resultats_lib.json')
except: pass

