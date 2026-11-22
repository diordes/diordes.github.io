#!/usr/bin/env python3
"""
🏠 BUSCADOR SEMÀFOR LIB — Script Windows (Tasca Programada)
=============================================================
S'executa al teu PC cada matí. Busca pisos a Idealista, Fotocasa,
Habitaclia i portals de bancs. Aplica calculadora LIB, genera JSON
i el puja a GitHub automàticament.

INSTAL·LACIÓ (un sol cop):
  pip install selenium beautifulsoup4 gitpython
  
  Chrome ha d'estar instal·lat al PC.

CONFIGURACIÓ:
  - Les ciutats es llegeixen de ciutats_config.json (editable des de la web)
  - Si no existeix, usa les per defecte de sota

TASCA PROGRAMADA:
  1. Obrir "Programador de tareas" (Task Scheduler)
  2. Crear tarea básica → Nom: "Buscar Pisos LIB"
  3. Desencadenador: Diariamente, 07:30
  4. Acción: Iniciar programa
     Programa: C:\\Users\\diord\\AppData\\Local\\Programs\\Python\\Python314\\python.exe
     Argumentos: C:\\Users\\diord\\diordes.github.io\\Pisos\\buscador_pisos_pc.py
     Iniciar en: C:\\Users\\diord\\diordes.github.io
  5. Marcar "Ejecutar tanto si el usuario ha iniciado sesión como si no"
"""

import os, sys, re, time, random, json, unicodedata, subprocess, logging
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════════
REPO_DIR = Path(r"C:\Users\diord\diordes.github.io")
DATA_DIR = REPO_DIR / "Pisos" / "data"
JSON_PATH = DATA_DIR / "resultats_lib.json"
CONFIG_PATH = DATA_DIR / "ciutats_config.json"
LOG_PATH = REPO_DIR / "Pisos" / "buscador.log"

# ═══════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_PATH, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
log = logging.info

# ═══════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════
DEFAULT_CONFIG = {
    'preuMin': 30000, 'preuMax': 70000,
    'hipotecaPct': 80, 'interesFix': 3.50,
    'anysMortgage': 25, 'comunitat_mes': 50,
    'ciutats': [
        {'nom':'Lleida','ccaa':'Cataluña'},{'nom':'Binèfar','ccaa':'Aragón'},
        {'nom':'Manresa','ccaa':'Cataluña'},{'nom':'Balaguer','ccaa':'Cataluña'},
        {'nom':'Mollerussa','ccaa':'Cataluña'},{'nom':'Tàrrega','ccaa':'Cataluña'},
        {'nom':'Fraga','ccaa':'Aragón'},{'nom':'Cervera','ccaa':'Cataluña'},
    ],
    'zones': {
        'bona': ['universitat','ricard vinyes','clot','cappont','centre historic'],
        'evitar': ['mariola','joan carles'],
    }
}

# Llegir config.json (editable des de la web)
CONFIG_FILE = DATA_DIR / "config.json"
try:
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    log(f"📋 Config carregat des de la web")
except:
    cfg = DEFAULT_CONFIG
    log(f"📋 Usant config per defecte")

CIUTATS = cfg.get('ciutats', DEFAULT_CONFIG['ciutats'])
PREU_MIN = cfg.get('preuMin', 30000)
PREU_MAX = cfg.get('preuMax', 70000)
HIPOTECA_PCT = cfg.get('hipotecaPct', 80)
INTERES_FIX = cfg.get('interesFix', 3.50)
ANYS_MORTGAGE = cfg.get('anysMortgage', 25)
COMUNITAT_MES = cfg.get('comunitat_mes', 50)
ZONES_BONA = cfg.get('zones', {}).get('bona', [])
ZONES_EVITAR = cfg.get('zones', {}).get('evitar', [])

log(f"   Ciutats: {', '.join(c['nom'] for c in CIUTATS)}")
log(f"   Preu: {PREU_MIN:,}–{PREU_MAX:,}€ · Hipo {HIPOTECA_PCT}% · {INTERES_FIX}% fix")

ITP = {
    'Cataluña':0.10, 'Aragón':0.08, 'Comunidad de Madrid':0.06,
    'Comunidad Valenciana':0.10, 'Andalucía':0.07, 'Galicia':0.09,
    'País Vasco':0.04, 'Castilla y León':0.08, 'Castilla-La Mancha':0.09,
    'Murcia':0.08, 'Canarias':0.065, 'Navarra':0.06, 'Extremadura':0.08,
    'Asturias':0.08, 'Cantabria':0.10, 'La Rioja':0.07, 'Baleares':0.08,
}

RENDES = {1: 380, 2: 450, 3: 520, 4: 580}

# ═══════════════════════════════════════════════════════════════════
# CALCULADORA LIB (Carlos Galán)
# ═══════════════════════════════════════════════════════════════════
def cuota(capital, interes, anys=ANYS_MORTGAGE):
    r = interes / 100 / 12
    n = anys * 12
    if r == 0: return capital / n
    return capital * (r * (1+r)**n) / ((1+r)**n - 1)

def zona_class(zona):
    z = zona.lower()
    for k in ZONES_BONA:
        if k in z: return 'bona'
    for k in ZONES_EVITAR:
        if k in z: return 'evitar'
    return 'neutra'

def calc_lib(preu, m2, habs, renda_mes, ccaa, zona=''):
    itp = preu * ITP.get(ccaa, 0.10)
    total_compra = preu + itp + 2500
    cap_hipo = preu * HIPOTECA_PCT / 100
    cap_inv = preu * (1 - HIPOTECA_PCT/100) + itp + 2500
    q = cuota(cap_hipo, INTERES_FIX)
    
    ra = renda_mes * 12
    comunitat = COMUNITAT_MES * 12
    ibi = preu * 0.005
    mant = ra * 0.10
    vac = ra * 0.05
    seg = ra * 0.05
    asseg = 200
    gastos = comunitat + ibi + mant + vac + seg + asseg
    
    bruta = ra / preu * 100 if preu > 0 else 0
    neta = (ra - gastos) / total_compra * 100 if total_compra > 0 else 0
    per = preu / ra if ra > 0 else 999
    cf = renda_mes - q - gastos / 12
    rcap = (ra - gastos) / cap_inv * 100 if cap_inv > 0 else 0
    
    zc = zona_class(zona)
    pts = sum([bruta >= 7, neta >= 4, per <= 15, cf >= 0])
    if zc == 'bona': pts += 1
    if zc == 'evitar': pts -= 1
    
    sem = 'comprar' if pts >= 4 else ('estudiar' if pts >= 2 else 'passar')
    checks = [
        ('✅' if bruta >= 7 else '❌') + ' Bruta',
        ('✅' if neta >= 4 else '❌') + ' Neta',
        ('✅' if per <= 15 else '❌') + ' PER',
        ('✅' if cf >= 0 else '❌') + ' CF',
    ]
    if zc == 'bona': checks.append('✅ Zona bona')
    elif zc == 'evitar': checks.append('🔴 Zona evitar')
    
    return {
        'bruta': round(bruta, 1), 'neta': round(neta, 1),
        'per': round(per, 1), 'cf': round(cf),
        'rentCap': round(rcap, 1), 'quota': round(q),
        'capInv': round(cap_inv), 'checks': checks,
        'semfor': sem, 'zonaClass': zc, 'pts': pts,
    }

# ═══════════════════════════════════════════════════════════════════
# SELENIUM SETUP
# ═══════════════════════════════════════════════════════════════════
def slug(text):
    t = unicodedata.normalize('NFD', text.lower())
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', '-', t).strip('-')

def pausa(a=3, b=7):
    """Pausa llarga per simular navegació humana"""
    time.sleep(random.uniform(a, b))

def crear_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    
    opts = Options()
    opts.add_argument('--headless=new')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.add_argument('--disable-gpu')
    opts.add_argument('--window-size=1920,1080')
    opts.add_argument('--lang=es-ES')
    opts.add_argument('--disable-blink-features=AutomationControlled')
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option('useAutomationExtension', False)
    
    # User agent real de Chrome Windows
    opts.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
    
    driver = webdriver.Chrome(options=opts)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    })
    return driver

# ═══════════════════════════════════════════════════════════════════
# SCRAPERS
# ═══════════════════════════════════════════════════════════════════
pisos = []

def acceptar_cookies(driver):
    from selenium.webdriver.common.by import By
    for sel in ['#didomi-notice-agree-button', '[id*="accept"]', '[class*="accept"]',
                'button[title*="Accept"]', 'button[title*="Aceptar"]']:
        try:
            btn = driver.find_element(By.CSS_SELECTOR, sel)
            btn.click()
            time.sleep(1)
            return
        except: pass

# ── IDEALISTA ───────────────────────────────────────────────────────
def buscar_idealista(driver, ciutat):
    from selenium.webdriver.common.by import By
    nom = ciutat['nom']; ccaa = ciutat['ccaa']
    s = slug(nom)
    
    # Trobar slug correcte provant províncies
    provincias = {
        'Cataluña':['barcelona','lleida','tarragona','girona'],
        'Aragón':['huesca','zaragoza','teruel'],
        'Comunidad de Madrid':['madrid'],
        'Comunidad Valenciana':['valencia','alicante','castellon'],
        'Andalucía':['sevilla','malaga','cadiz','cordoba','granada','huelva','jaen','almeria'],
        'Galicia':['a-coruna','pontevedra','lugo','ourense'],
        'País Vasco':['vizcaya','guipuzcoa','alava'],
        'Castilla y León':['valladolid','leon','burgos','salamanca','zamora','palencia','segovia','soria','avila'],
        'Castilla-La Mancha':['toledo','ciudad-real','albacete','guadalajara','cuenca'],
        'Murcia':['murcia'],
        'Canarias':['las-palmas','santa-cruz-de-tenerife'],
        'Navarra':['navarra'],
        'Extremadura':['badajoz','caceres'],
        'Asturias':['asturias'],
        'Cantabria':['cantabria'],
        'La Rioja':['la-rioja'],
        'Baleares':['baleares'],
    }
    
    found = False
    for prov in provincias.get(ccaa, []):
        test_slug = f"{s}-{prov}"
        url = f"https://www.idealista.com/venta-viviendas/{test_slug}/con-precio-hasta_{PREU_MAX},precio-desde_{PREU_MIN}/"
        log(f"  🔍 Idealista {nom} ({test_slug})...")
        
        try:
            driver.get(url)
            pausa(4, 8)
            acceptar_cookies(driver)
            
            articles = driver.find_elements(By.CSS_SELECTOR, 'article.item')
            if not articles:
                continue
            
            log(f"     ✅ Trobat! {len(articles)} anuncis")
            found = True
            count = 0
            
            for art in articles:
                try:
                    le = art.find_element(By.CSS_SELECTOR, 'a.item-link')
                    titol = le.text.strip()
                    href = le.get_attribute('href')
                    
                    pe = art.find_element(By.CSS_SELECTOR, '.item-price')
                    p = int(re.sub(r'[^\d]', '', pe.text) or '0')
                    if p < PREU_MIN or p > PREU_MAX or p == 0: continue
                    
                    h = 0; m2 = 0; pl = ''
                    for d in art.find_elements(By.CSS_SELECTOR, '.item-detail'):
                        t = d.text
                        hm = re.search(r'(\d+)\s*hab', t)
                        if hm: h = int(hm.group(1))
                        mm = re.search(r'(\d+)\s*m²', t)
                        if mm: m2 = int(mm.group(1))
                        if any(x in t.lower() for x in ['planta','bajo','exterior','interior']):
                            pl = t
                    
                    zona = ''
                    parts = titol.split(',')
                    if len(parts) >= 3: zona = parts[-2].strip()
                    elif len(parts) >= 2: zona = parts[-1].strip()
                    
                    try:
                        desc = art.find_element(By.CSS_SELECTOR, '.item-description').text[:150]
                    except: desc = ''
                    
                    # Descartar ocupats, proindiviso, cessió
                    if any(x in desc.lower() for x in ['ocupada ilegalmente','cesión de remate',
                            'proindiviso','sin posesión','nuda propiedad']): continue
                    
                    alquilat = 'alquilada' in desc.lower() or 'alquilada' in titol.lower()
                    renda = RENDES.get(min(max(h, 1), 4), 420)
                    met = calc_lib(p, m2, h, renda, ccaa, zona)
                    
                    pisos.append({
                        **{k:v for k,v in met.items() if k != 'pts'},
                        'nom': titol, 'preu': p, 'm2': m2, 'habs': h,
                        'renda': renda, 'ciutat': nom, 'zona': zona,
                        'planta': pl, 'portal': 'Idealista', 'url': href,
                        'alquilat': alquilat, 'notes': desc,
                    })
                    count += 1
                except: continue
            
            log(f"     📊 {count} pisos vàlids")
            
            # Pàgina 2 (si existeix)
            pausa(3, 6)
            try:
                pg2 = driver.find_element(By.CSS_SELECTOR, 'a.icon-arrow-right-after')
                pg2.click()
                pausa(4, 8)
                arts2 = driver.find_elements(By.CSS_SELECTOR, 'article.item')
                c2 = 0
                for art in arts2:
                    try:
                        le = art.find_element(By.CSS_SELECTOR, 'a.item-link')
                        href = le.get_attribute('href')
                        pe = art.find_element(By.CSS_SELECTOR, '.item-price')
                        p = int(re.sub(r'[^\d]', '', pe.text) or '0')
                        if p < PREU_MIN or p > PREU_MAX or p == 0: continue
                        h=0; m2=0
                        for d in art.find_elements(By.CSS_SELECTOR, '.item-detail'):
                            t = d.text
                            hm = re.search(r'(\d+)\s*hab', t)
                            if hm: h = int(hm.group(1))
                            mm = re.search(r'(\d+)\s*m²', t)
                            if mm: m2 = int(mm.group(1))
                        try: desc = art.find_element(By.CSS_SELECTOR, '.item-description').text[:150]
                        except: desc = ''
                        if any(x in desc.lower() for x in ['ocupada ilegalmente','cesión de remate','proindiviso']): continue
                        renda = RENDES.get(min(max(h,1),4), 420)
                        met = calc_lib(p, m2, h, renda, ccaa, nom)
                        pisos.append({**{k:v for k,v in met.items() if k!='pts'},
                            'nom':le.text.strip(),'preu':p,'m2':m2,'habs':h,'renda':renda,
                            'ciutat':nom,'zona':nom,'planta':'','portal':'Idealista','url':href,
                            'alquilat':False,'notes':desc,'zonaClass':met['zonaClass']})
                        c2 += 1
                    except: continue
                if c2: log(f"     + pàg 2: {c2}")
            except: pass
            
            break  # Trobat, no provar més províncies
            
        except Exception as e:
            continue
    
    if not found:
        log(f"  ⚠️ Idealista {nom}: no trobat")

# ── FOTOCASA ────────────────────────────────────────────────────────
def buscar_fotocasa(driver, ciutat):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from bs4 import BeautifulSoup
    
    nom = ciutat['nom']; ccaa = ciutat['ccaa']
    s = slug(nom)
    url = f"https://www.fotocasa.es/es/comprar/viviendas/{s}/todas-las-zonas/l?maxPrice={PREU_MAX}&minPrice={PREU_MIN}"
    log(f"  🔍 Fotocasa {nom}...")
    
    try:
        driver.get(url)
        pausa(5, 9)
        acceptar_cookies(driver)
        
        try:
            WebDriverWait(driver, 12).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[class*="re-Card"]'))
            )
        except:
            log(f"     0 resultats")
            return
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        count = 0
        
        for card in soup.select('[class*="re-Card"]'):
            try:
                le = card.select_one('a[href*="/comprar/"], a[href*="/en-venta/"]')
                if not le: continue
                href = le.get('href', '')
                purl = f"https://www.fotocasa.es{href}" if href.startswith('/') else href
                
                txt = card.get_text()
                pm = re.search(r'([\d\.]+)\s*€', txt)
                if not pm: continue
                p = int(pm.group(1).replace('.', ''))
                if p < PREU_MIN or p > PREU_MAX: continue
                
                h = 2; m2 = 0
                hm = re.search(r'(\d+)\s*hab', txt.lower())
                if hm: h = int(hm.group(1))
                mm = re.search(r'(\d+)\s*m²', txt)
                if mm: m2 = int(mm.group(1))
                
                te = card.select_one('[class*="Title"], h3')
                titol = te.get_text(strip=True) if te else f"Pis a {nom}"
                
                renda = RENDES.get(min(max(h,1), 4), 420)
                met = calc_lib(p, m2, h, renda, ccaa, nom)
                
                if purl not in [x['url'] for x in pisos]:
                    pisos.append({**{k:v for k,v in met.items() if k!='pts'},
                        'nom': titol, 'preu': p, 'm2': m2, 'habs': h,
                        'renda': renda, 'ciutat': nom, 'zona': nom,
                        'planta': '', 'portal': 'Fotocasa', 'url': purl,
                        'alquilat': False, 'notes': '', 'zonaClass': met['zonaClass'],
                    })
                    count += 1
            except: continue
        
        log(f"     {'✅ ' + str(count) if count else '0'}")
    except Exception as e:
        log(f"     ❌ {e}")

# ── HABITACLIA ──────────────────────────────────────────────────────
def buscar_habitaclia(driver, ciutat):
    from selenium.webdriver.common.by import By
    from bs4 import BeautifulSoup
    
    nom = ciutat['nom']; ccaa = ciutat['ccaa']
    s = slug(nom)
    url = f"https://www.habitaclia.com/viviendas-en-{s}.htm?precio_max={PREU_MAX}&precio_min={PREU_MIN}"
    log(f"  🔍 Habitaclia {nom}...")
    
    try:
        driver.get(url)
        pausa(4, 7)
        acceptar_cookies(driver)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        count = 0
        
        for card in soup.select('.list-item, .js-list-item, article'):
            try:
                le = card.select_one('a[href*="/piso-"], a[href*="/casa-"], a[href*="/vivienda-"]')
                if not le: continue
                href = le.get('href', '')
                purl = f"https://www.habitaclia.com{href}" if href.startswith('/') else href
                titol = le.get_text(strip=True) or f"Pis a {nom}"
                
                txt = card.get_text()
                pm = re.search(r'([\d\.]+)\s*€', txt)
                if not pm: continue
                p = int(pm.group(1).replace('.', ''))
                if p < PREU_MIN or p > PREU_MAX: continue
                
                h = 2; m2 = 0
                hm = re.search(r'(\d+)\s*hab', txt.lower())
                if hm: h = int(hm.group(1))
                mm = re.search(r'(\d+)\s*m²', txt)
                if mm: m2 = int(mm.group(1))
                
                renda = RENDES.get(min(max(h,1), 4), 420)
                met = calc_lib(p, m2, h, renda, ccaa, nom)
                
                if purl not in [x['url'] for x in pisos]:
                    pisos.append({**{k:v for k,v in met.items() if k!='pts'},
                        'nom': titol, 'preu': p, 'm2': m2, 'habs': h,
                        'renda': renda, 'ciutat': nom, 'zona': nom,
                        'planta': '', 'portal': 'Habitaclia', 'url': purl,
                        'alquilat': False, 'notes': '', 'zonaClass': met['zonaClass'],
                    })
                    count += 1
            except: continue
        
        log(f"     {'✅ ' + str(count) if count else '0'}")
    except Exception as e:
        log(f"     ❌ {e}")

# ── PORTALS DE BANCS ────────────────────────────────────────────────
BANCS = [
    ('Haya', 'hfreinmobiliaria.com'),
    ('Solvia', 'solvia.es'),
    ('CaixaBank', 'inmuebles.caixabank.es'),
    ('Servihabitat', 'servihabitat.com'),
    ('Altamira', 'altamirainmuebles.com'),
    ('Aliseda', 'alisedainmobiliaria.com'),
    ('Anticipa', 'anticiparealestate.com'),
]

def buscar_bancs(driver, ciutat):
    from selenium.webdriver.common.by import By
    from urllib.parse import quote_plus
    
    nom = ciutat['nom']; ccaa = ciutat['ccaa']
    
    for bnom, site in BANCS:
        q = f"site:{site} piso {nom} venta"
        url = f"https://www.google.com/search?q={quote_plus(q)}&num=5"
        log(f"  🏦 {bnom} {nom}...")
        
        try:
            driver.get(url)
            pausa(3, 6)
            
            count = 0
            for le in driver.find_elements(By.CSS_SELECTOR, f'a[href*="{site}"]')[:5]:
                try:
                    href = le.get_attribute('href')
                    text = le.text.strip()
                    if not text or site not in href: continue
                    
                    pm = re.search(r'(\d{2,3}[\.,]\d{3})\s*€', text)
                    if not pm: continue
                    p = int(pm.group(1).replace('.', '').replace(',', ''))
                    if p < PREU_MIN or p > PREU_MAX: continue
                    
                    hm = re.search(r'(\d+)\s*hab', text.lower())
                    h = int(hm.group(1)) if hm else 2
                    mm = re.search(r'(\d+)\s*m', text)
                    m2 = int(mm.group(1)) if mm else 60
                    
                    renda = RENDES.get(min(max(h,1), 4), 420)
                    met = calc_lib(p, m2, h, renda, ccaa, nom)
                    
                    if href not in [x['url'] for x in pisos]:
                        pisos.append({**{k:v for k,v in met.items() if k!='pts'},
                            'nom': f"{bnom}: {text[:60]}", 'preu': p, 'm2': m2,
                            'habs': h, 'renda': renda, 'ciutat': nom, 'zona': nom,
                            'planta': '', 'portal': bnom, 'url': href,
                            'alquilat': False, 'notes': '', 'zonaClass': 'neutra',
                        })
                        count += 1
                except: continue
            
            if count: log(f"     ✅ {count}")
        except Exception as e:
            log(f"     ❌ {e}")
        
        pausa(2, 5)

# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    log("=" * 60)
    log("🏠 BUSCADOR SEMÀFOR LIB — PC Local")
    log(f"   {PREU_MIN:,}–{PREU_MAX:,}€ · Hipo {HIPOTECA_PCT}% · {INTERES_FIX}% fix")
    log(f"   {len(CIUTATS)} ciutats · {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    log("=" * 60)

    # ── Carregar resultats anteriors (per conservar si falla) ────────
    pisos_anteriors = {}
    urls_anteriors = set()
    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            prev = json.load(f)
        for p in prev.get('pisos', []):
            pisos_anteriors[p['url']] = p
            urls_anteriors.add(p['url'])
        log(f"📂 {len(pisos_anteriors)} pisos anteriors carregats")
    except:
        log("📂 Sense resultats anteriors")

    # ── Stats per portal ────────────────────────────────────────────
    portal_stats = {}

    # ── Crear driver ────────────────────────────────────────────────
    try:
        driver = crear_driver()
        log("🌐 Chrome obert")
    except Exception as e:
        log(f"❌ Error obrint Chrome: {e}")
        log("   Assegura't que Chrome està instal·lat i selenium també:")
        log("   pip install selenium")
        sys.exit(1)

    # ── Buscar per cada ciutat ──────────────────────────────────────
    for i, ciutat in enumerate(CIUTATS):
        log(f"\n📍 [{i+1}/{len(CIUTATS)}] {ciutat['nom']} ({ciutat['ccaa']})")

        n_before = len(pisos)
        buscar_idealista(driver, ciutat)
        n_idealista = len(pisos) - n_before
        portal_stats.setdefault('Idealista', 0)
        portal_stats['Idealista'] += n_idealista
        pausa(5, 10)

        n_before = len(pisos)
        buscar_fotocasa(driver, ciutat)
        n_fotocasa = len(pisos) - n_before
        portal_stats.setdefault('Fotocasa', 0)
        portal_stats['Fotocasa'] += n_fotocasa
        pausa(5, 10)

        n_before = len(pisos)
        buscar_habitaclia(driver, ciutat)
        n_habitaclia = len(pisos) - n_before
        portal_stats.setdefault('Habitaclia', 0)
        portal_stats['Habitaclia'] += n_habitaclia
        pausa(3, 6)

        n_before = len(pisos)
        buscar_bancs(driver, ciutat)
        n_bancs = len(pisos) - n_before
        portal_stats.setdefault('Bancs', 0)
        portal_stats['Bancs'] += n_bancs

        if i < len(CIUTATS) - 1:
            pausa(10, 20)  # Pausa llarga entre ciutats

    driver.quit()
    log("\n🌐 Chrome tancat")

    # ── Eliminar duplicats ──────────────────────────────────────────
    seen = set()
    unics = []
    for p in pisos:
        if p['url'] not in seen:
            seen.add(p['url'])
            unics.append(p)

    # ── Conservar anteriors de portals que han fallat (0 resultats) ─
    portals_nous = set(p['portal'] for p in unics)
    for url, p_ant in pisos_anteriors.items():
        portal = p_ant.get('portal', '')
        # Si el portal no ha donat resultats NOUS, conservar els anteriors
        if portal not in portals_nous and url not in seen:
            p_ant['conservat'] = True  # Marcar que ve d'una cerca anterior
            unics.append(p_ant)
            seen.add(url)

    # Ordenar
    pisos_finals = sorted(unics, key=lambda x: (
        {'comprar': 0, 'estudiar': 1, 'passar': 2}.get(x['semfor'], 3),
        -x['bruta']
    ))

    # ── Marcar pisos nous (no estaven ahir) ─────────────────────────
    for p in pisos_finals:
        p['nou'] = p['url'] not in urls_anteriors

    n_nous = sum(1 for p in pisos_finals if p['nou'])
    nc = sum(1 for p in pisos_finals if p['semfor'] == 'comprar')
    ne = sum(1 for p in pisos_finals if p['semfor'] == 'estudiar')
    np_ = sum(1 for p in pisos_finals if p['semfor'] == 'passar')

    log(f"\n{'=' * 60}")
    log(f"📊 {len(pisos_finals)} pisos ({n_nous} nous)")
    log(f"   🟢 COMPRAR: {nc}  🟡 ESTUDIAR: {ne}  🔴 PASSAR: {np_}")

    # Stats per portal
    log(f"\n📡 Per portal:")
    for portal, count in sorted(portal_stats.items()):
        status = "✅" if count > 0 else "⚠️ 0 resultats"
        log(f"   {portal}: {count} {status}")

    # Avisos de portals que han fallat
    for portal in ['Idealista', 'Fotocasa', 'Habitaclia']:
        if portal_stats.get(portal, 0) == 0:
            conservats = sum(1 for p in pisos_finals if p.get('portal') == portal and p.get('conservat'))
            if conservats:
                log(f"   ⚠️ {portal}: 0 nous, conservats {conservats} d'ahir")

    # Top 5 nous
    nous = [p for p in pisos_finals if p['nou']]
    if nous:
        log(f"\n🆕 PISOS NOUS ({len(nous)}):")
        for i, p in enumerate(nous[:5]):
            log(f"   {i+1}. {p['nom']} — {p['preu']:,}€ · Bruta {p['bruta']}% · {p['portal']}")

    # ── Guardar JSON ────────────────────────────────────────────────
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output = {
        'generatEl': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'config': {
            'preuMin': PREU_MIN, 'preuMax': PREU_MAX,
            'hipotecaPct': HIPOTECA_PCT / 100, 'interesFix': INTERES_FIX,
            'ciutats': [c['nom'] for c in CIUTATS],
        },
        'resum': {
            'total': len(pisos_finals), 'comprar': nc, 'estudiar': ne, 'passar': np_,
            'nous': n_nous,
        },
        'portals': {k: {'trobats': v, 'ok': v > 0} for k, v in portal_stats.items()},
        'pisos': [{k:v for k,v in p.items() if k != 'pts'} for p in pisos_finals],
    }

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log(f"\n💾 JSON guardat: {JSON_PATH}")

    # ── Git pull + push automàtic ───────────────────────────────────
    try:
        os.chdir(REPO_DIR)
        # Pull primer per si la web ha canviat la config
        subprocess.run(['git', 'pull', '--rebase'], capture_output=True, timeout=30)
        subprocess.run(['git', 'add', 'Pisos/data/resultats_lib.json'], check=True, capture_output=True)

        result = subprocess.run(['git', 'diff', '--staged', '--quiet'], capture_output=True)
        if result.returncode != 0:
            msg = f"🏠 Pisos {datetime.now().strftime('%d/%m/%Y')} — {len(pisos_finals)} pisos ({n_nous} nous, {nc}🟢 {ne}🟡 {np_}🔴)"
            subprocess.run(['git', 'commit', '-m', msg], check=True, capture_output=True)
            subprocess.run(['git', 'push'], check=True, capture_output=True, timeout=30)
            log("📤 Pujat a GitHub!")
        else:
            log("ℹ️ Sense canvis al JSON")
    except Exception as e:
        log(f"⚠️ Error git: {e}")
        log("   Pots fer-ho manualment: git add + commit + push")
    
    log(f"\n✅ Finalitzat: {datetime.now().strftime('%H:%M:%S')}")
    log("=" * 60)

if __name__ == '__main__':
    main()

