#!/usr/bin/env python3
"""
Scraper per GitHub Actions — s'executa automàticament cada dia.
Troba el slug correcte de cada portal automàticament.
Poses qualsevol ciutat d'Espanya i funciona.
"""
import os, re, time, random, json, unicodedata
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import quote_plus

# ══ CONFIG ══════════════════════════════════════════════════════════
# Les ciutats es llegeixen de Pisos/data/ciutats_config.json (editable des de la web).
DEFAULT = [
    {'nom':'Lleida','ccaa':'Cataluña'},{'nom':'Binèfar','ccaa':'Aragón'},
    {'nom':'Manresa','ccaa':'Cataluña'},{'nom':'Balaguer','ccaa':'Cataluña'},
    {'nom':'Mollerussa','ccaa':'Cataluña'},{'nom':'Tàrrega','ccaa':'Cataluña'},
    {'nom':'Fraga','ccaa':'Aragón'},{'nom':'Cervera','ccaa':'Cataluña'},
]
try:
    with open('Pisos/data/ciutats_config.json','r',encoding='utf-8') as f:
        CIUTATS = json.load(f)
    print(f"📋 Config carregat: {', '.join(c['nom'] for c in CIUTATS)}")
except:
    CIUTATS = DEFAULT
    print(f"📋 Usant per defecte: {', '.join(c['nom'] for c in CIUTATS)}")

# Extra city from manual trigger
extra = os.environ.get('CIUTAT_EXTRA', '').strip()
ccaa_extra = os.environ.get('CCAA_EXTRA', 'Cataluña').strip()
if extra:
    CIUTATS.append({'nom': extra, 'ccaa': ccaa_extra})

PREU_MIN = 30000
PREU_MAX = int(os.environ.get('PREU_MAX_OVERRIDE', '70000') or '70000')
HIPOTECA_PCT = 80
INTERES_FIX = 3.50

ITP = {'Cataluña':0.10,'Aragón':0.08,'Comunidad de Madrid':0.06,
       'Comunidad Valenciana':0.10,'Andalucía':0.07,'Galicia':0.09,
       'País Vasco':0.04,'Castilla y León':0.08,'Castilla-La Mancha':0.09,
       'Murcia':0.08,'Canarias':0.065,'Navarra':0.06,'Extremadura':0.08,
       'Asturias':0.08,'Cantabria':0.10,'La Rioja':0.07,'Baleares':0.08}

RENDES = {1:380, 2:450, 3:520, 4:580}
BANCS = [('Haya','hfreinmobiliaria.com'),('Solvia','solvia.es'),
         ('CaixaBank','inmuebles.caixabank.es'),('Servihabitat','servihabitat.com'),
         ('Altamira','altamirainmuebles.com'),('Aliseda','alisedainmobiliaria.com')]

pisos = []

# ══ CHROME SETUP ════════════════════════════════════════════════════
opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--no-sandbox')
opts.add_argument('--disable-dev-shm-usage')
opts.add_argument('--disable-gpu')
opts.add_argument('--window-size=1920,1080')
opts.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
opts.add_argument('--disable-blink-features=AutomationControlled')
opts.add_experimental_option("excludeSwitches", ["enable-automation"])

driver = webdriver.Chrome(options=opts)
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
print("🌐 Chrome obert")

# ══ UTILS ═══════════════════════════════════════════════════════════
def slug(text):
    t = unicodedata.normalize('NFD', text.lower())
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', '-', t).strip('-')

def pausa(a=2, b=4): time.sleep(random.uniform(a, b))

def cuota(cap, i, a=25):
    r=i/100/12; n=a*12
    return cap*(r*(1+r)**n)/((1+r)**n-1) if r else cap/n

def calc(preu, m2, habs, renda, ccaa):
    itp=preu*ITP.get(ccaa,0.10); tot=preu+itp+2500
    q=cuota(preu*HIPOTECA_PCT/100, INTERES_FIX)
    ci=preu*(1-HIPOTECA_PCT/100)+itp+2500
    ra=renda*12; g=600+preu*0.005+ra*0.20+200
    br=ra/preu*100 if preu else 0; ne=(ra-g)/tot*100 if tot else 0
    per=preu/ra if ra else 999; cf=renda-q-g/12
    rc=(ra-g)/ci*100 if ci else 0
    pts=sum([br>=7,ne>=4,per<=15,cf>=0])
    sem='comprar' if pts>=4 else('estudiar' if pts>=2 else 'passar')
    chk=[('✅' if br>=7 else '❌')+' Bruta',('✅' if ne>=4 else '❌')+' Neta',
         ('✅' if per<=15 else '❌')+' PER',('✅' if cf>=0 else '❌')+' CF']
    return dict(bruta=round(br,1),neta=round(ne,1),per=round(per,1),cf=round(cf),
                rcap=round(rc,1),quota=round(q),capInv=round(ci),checks=chk,semfor=sem,pts=pts)

# ══ TROBAR SLUG IDEALISTA AUTOMÀTICAMENT ════════════════════════════
def trobar_slug_idealista(nom_ciutat):
    """Busca la ciutat a Idealista via Google per trobar el slug correcte"""
    query = f"site:idealista.com/venta-viviendas/ {nom_ciutat}"
    url = f"https://www.google.com/search?q={quote_plus(query)}&num=5"

    try:
        driver.get(url)
        pausa(2, 4)

        # Buscar links que tinguin el patró /venta-viviendas/SLUG/
        links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="idealista.com/venta-viviendas/"]')

        for link in links:
            href = link.get_attribute('href') or ''
            m = re.search(r'idealista\.com/venta-viviendas/([a-z0-9-]+)/', href)
            if m:
                found_slug = m.group(1)
                # Verificar que conté el nom de la ciutat (en slug form)
                city_slug = slug(nom_ciutat)
                if city_slug in found_slug or found_slug.startswith(city_slug):
                    return found_slug

        # Fallback: provar slug directe amb províncies comunes
        return None
    except:
        return None

# ══ TROBAR URL FOTOCASA AUTOMÀTICAMENT ══════════════════════════════
def trobar_url_fotocasa(nom_ciutat):
    """Busca la ciutat a Fotocasa via Google per trobar la URL correcta"""
    query = f"site:fotocasa.es/es/comprar/viviendas/ {nom_ciutat}"
    url = f"https://www.google.com/search?q={quote_plus(query)}&num=3"

    try:
        driver.get(url)
        pausa(2, 3)

        links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="fotocasa.es/es/comprar/viviendas/"]')
        for link in links:
            href = link.get_attribute('href') or ''
            if 'fotocasa.es/es/comprar/viviendas/' in href:
                # Extreure la base URL sense filtres
                m = re.search(r'(https://www\.fotocasa\.es/es/comprar/viviendas/[^?]+)', href)
                if m:
                    base = m.group(1)
                    if not base.endswith('/l'): base = base.rstrip('/') + '/l'
                    return base
        return None
    except:
        return None

# ══ IDEALISTA SCRAPER ═══════════════════════════════════════════════
def buscar_idealista(ciutat):
    nom = ciutat['nom']; ccaa = ciutat['ccaa']
    print(f"  🔍 Idealista {nom}...", end=" ")

    # 1. Trobar el slug correcte
    found_slug = trobar_slug_idealista(nom)

    if not found_slug:
        # Fallback: provar combinacions habituals
        s = slug(nom)
        provincias = {
            'Cataluña': ['barcelona','lleida','tarragona','girona'],
            'Aragón': ['huesca','zaragoza','teruel'],
            'Comunidad de Madrid': ['madrid'],
            'Comunidad Valenciana': ['valencia','alicante','castellon'],
            'Andalucía': ['sevilla','malaga','cadiz','cordoba','granada','huelva','jaen','almeria'],
            'Galicia': ['a-coruna','pontevedra','lugo','ourense'],
            'País Vasco': ['vizcaya','guipuzcoa','alava'],
            'Castilla y León': ['valladolid','leon','burgos','salamanca','zamora','palencia','segovia','soria','avila'],
            'Castilla-La Mancha': ['toledo','ciudad-real','albacete','guadalajara','cuenca'],
            'Murcia': ['murcia'],
            'Canarias': ['las-palmas','santa-cruz-de-tenerife'],
            'Navarra': ['navarra'],
            'Extremadura': ['badajoz','caceres'],
            'Asturias': ['asturias'],
            'Cantabria': ['cantabria'],
            'La Rioja': ['la-rioja'],
            'Baleares': ['baleares'],
        }

        for prov in provincias.get(ccaa, []):
            test_slug = f"{s}-{prov}"
            test_url = f"https://www.idealista.com/venta-viviendas/{test_slug}/"
            try:
                driver.get(test_url)
                pausa(2, 3)
                if driver.find_elements(By.CSS_SELECTOR, 'article.item') or 'casas y pisos' in driver.title.lower():
                    found_slug = test_slug
                    break
            except: continue

    if not found_slug:
        print(f"⚠️ slug no trobat")
        return

    print(f"slug={found_slug}... ", end="")

    # 2. Buscar amb filtres de preu
    url = f"https://www.idealista.com/venta-viviendas/{found_slug}/con-precio-hasta_{PREU_MAX},precio-desde_{PREU_MIN}/"

    try:
        driver.get(url)
        pausa(3, 5)

        # Accept cookies
        try:
            driver.find_element(By.ID, 'didomi-notice-agree-button').click()
            pausa(1, 2)
        except: pass

        articles = driver.find_elements(By.CSS_SELECTOR, 'article.item')
        if not articles:
            print("0 resultats")
            return

        count = 0
        for art in articles:
            try:
                le = art.find_element(By.CSS_SELECTOR, 'a.item-link')
                titol = le.text.strip()
                href = le.get_attribute('href')

                pe = art.find_element(By.CSS_SELECTOR, '.item-price')
                p = int(re.sub(r'[^\d]', '', pe.text) or '0')
                if p < PREU_MIN or p > PREU_MAX or p == 0: continue

                h = 0; m = 0; pl = ''
                for d in art.find_elements(By.CSS_SELECTOR, '.item-detail'):
                    t = d.text
                    hm = re.search(r'(\d+)\s*hab', t)
                    if hm: h = int(hm.group(1))
                    mm = re.search(r'(\d+)\s*m²', t)
                    if mm: m = int(mm.group(1))
                    if any(x in t.lower() for x in ['planta','bajo','ext','int']): pl = t

                z = titol.split(',')[-2].strip() if titol.count(',') >= 2 else nom

                try: desc = art.find_element(By.CSS_SELECTOR, '.item-description').text[:120]
                except: desc = ''
                if any(x in desc.lower() for x in ['ocupada ilegalmente','cesión de remate','proindiviso']): continue

                renda = RENDES.get(min(max(h,1), 4), 420)
                met = calc(p, m, h, renda, ccaa)
                pisos.append({**met, 'nom':titol, 'preu':p, 'm2':m, 'habs':h, 'renda':renda,
                    'ciutat':nom, 'zona':z, 'planta':pl, 'portal':'Idealista', 'url':href,
                    'alquilat':'alquilada' in desc.lower(), 'notes':desc, 'zonaClass':'neutra'})
                count += 1
            except: continue

        print(f"✅ {count}")

        # Pàgina 2
        try:
            pg2 = driver.find_element(By.CSS_SELECTOR, 'a.icon-arrow-right-after')
            pg2.click()
            pausa(3, 5)
            for art in driver.find_elements(By.CSS_SELECTOR, 'article.item'):
                try:
                    le = art.find_element(By.CSS_SELECTOR, 'a.item-link')
                    href = le.get_attribute('href')
                    pe = art.find_element(By.CSS_SELECTOR, '.item-price')
                    p = int(re.sub(r'[^\d]', '', pe.text) or '0')
                    if p < PREU_MIN or p > PREU_MAX or p == 0: continue
                    h=0; m=0
                    for d in art.find_elements(By.CSS_SELECTOR, '.item-detail'):
                        t = d.text
                        hm = re.search(r'(\d+)\s*hab', t)
                        if hm: h = int(hm.group(1))
                        mm = re.search(r'(\d+)\s*m²', t)
                        if mm: m = int(mm.group(1))
                    renda = RENDES.get(min(max(h,1),4), 420)
                    met = calc(p, m, h, renda, ccaa)
                    pisos.append({**met, 'nom':le.text.strip(), 'preu':p, 'm2':m, 'habs':h,
                        'renda':renda, 'ciutat':nom, 'zona':nom, 'planta':'',
                        'portal':'Idealista', 'url':href, 'alquilat':False, 'notes':'', 'zonaClass':'neutra'})
                except: continue
            print(f"     + pàg 2")
        except: pass

    except Exception as e:
        print(f"❌ {e}")

# ══ FOTOCASA SCRAPER ════════════════════════════════════════════════
def buscar_fotocasa(ciutat):
    nom = ciutat['nom']; ccaa = ciutat['ccaa']
    print(f"  🔍 Fotocasa {nom}...", end=" ")

    # Trobar URL correcta via Google
    base_url = trobar_url_fotocasa(nom)

    if not base_url:
        # Fallback
        s = slug(nom)
        base_url = f"https://www.fotocasa.es/es/comprar/viviendas/{s}/todas-las-zonas/l"

    url = f"{base_url}?maxPrice={PREU_MAX}&minPrice={PREU_MIN}"

    try:
        driver.get(url)
        pausa(4, 6)

        try:
            driver.find_element(By.ID, 'didomi-notice-agree-button').click()
            pausa(1, 2)
        except: pass

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[class*="re-Card"]'))
            )
        except:
            print("0"); return

        from bs4 import BeautifulSoup
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

                h=2; m=0
                hm = re.search(r'(\d+)\s*hab', txt.lower())
                if hm: h = int(hm.group(1))
                mm = re.search(r'(\d+)\s*m²', txt)
                if mm: m = int(mm.group(1))

                te = card.select_one('[class*="Title"], h3')
                titol = te.get_text(strip=True) if te else f"Pis a {nom}"

                renda = RENDES.get(min(max(h,1),4), 420)
                met = calc(p, m, h, renda, ccaa)

                if purl not in [x['url'] for x in pisos]:
                    pisos.append({**met, 'nom':titol, 'preu':p, 'm2':m, 'habs':h, 'renda':renda,
                        'ciutat':nom, 'zona':nom, 'planta':'', 'portal':'Fotocasa', 'url':purl,
                        'alquilat':False, 'notes':'', 'zonaClass':'neutra'})
                    count += 1
            except: continue
        print(f"{'✅ '+str(count) if count else '0'}")
    except Exception as e:
        print(f"❌ {e}")

# ══ BANCS (via Google site:search) ══════════════════════════════════
def buscar_bancs(ciutat):
    nom = ciutat['nom']; ccaa = ciutat['ccaa']
    for bnom, site in BANCS:
        q = f"site:{site} piso {nom} venta"
        url = f"https://www.google.com/search?q={quote_plus(q)}&num=5"
        print(f"  🏦 {bnom} {nom}...", end=" ")
        try:
            driver.get(url); pausa(2, 4)
            count = 0
            for le in driver.find_elements(By.CSS_SELECTOR, f'a[href*="{site}"]')[:5]:
                try:
                    href = le.get_attribute('href'); text = le.text
                    if not text or site not in href: continue
                    pm = re.search(r'(\d{2,3}[\.,]\d{3})\s*€', text)
                    if not pm: continue
                    p = int(pm.group(1).replace('.','').replace(',',''))
                    if p < PREU_MIN or p > PREU_MAX: continue
                    h=2; m=60
                    hm = re.search(r'(\d+)\s*hab', text.lower())
                    if hm: h = int(hm.group(1))
                    renda = RENDES.get(min(max(h,1),4), 420)
                    met = calc(p, m, h, renda, ccaa)
                    if href not in [x['url'] for x in pisos]:
                        pisos.append({**met, 'nom':f"{bnom}: {text[:60]}", 'preu':p, 'm2':m,
                            'habs':h, 'renda':renda, 'ciutat':nom, 'zona':nom, 'planta':'',
                            'portal':bnom, 'url':href, 'alquilat':False, 'notes':'', 'zonaClass':'neutra'})
                        count += 1
                except: continue
            print(f"{'✅ '+str(count) if count else '0'}")
        except: print("❌")
        pausa(1, 3)

# ══════════════════════════════════════════════════════════════════
# EXECUTAR
# ══════════════════════════════════════════════════════════════════
print(f"\n🏠 BUSCADOR SEMÀFOR LIB")
print(f"   {PREU_MIN:,}–{PREU_MAX:,}€ · Hipo {HIPOTECA_PCT}% · {INTERES_FIX}% fix")
print(f"   Ciutats: {', '.join(c['nom'] for c in CIUTATS)}\n")

for c in CIUTATS:
    print(f"\n📍 {c['nom']} ({c['ccaa']}):")
    buscar_idealista(c)
    pausa(2, 4)
    buscar_fotocasa(c)
    pausa(2, 4)
    buscar_bancs(c)

driver.quit()
print("\n🌐 Chrome tancat")

# ══ GUARDAR ═════════════════════════════════════════════════════════
pisos.sort(key=lambda x: (-x['pts'], -x['bruta']))
nc = sum(1 for p in pisos if p['semfor'] == 'comprar')
ne = sum(1 for p in pisos if p['semfor'] == 'estudiar')
np_ = sum(1 for p in pisos if p['semfor'] == 'passar')

clean = [{k:v for k,v in p.items() if k != 'pts'} for p in pisos]

output = {
    'generatEl': time.strftime('%Y-%m-%d %H:%M'),
    'config': {'preuMin':PREU_MIN, 'preuMax':PREU_MAX, 'hipotecaPct':HIPOTECA_PCT/100,
               'interesFix':INTERES_FIX, 'ciutats':[c['nom'] for c in CIUTATS]},
    'resum': {'total':len(pisos), 'comprar':nc, 'estudiar':ne, 'passar':np_},
    'pisos': clean,
}

os.makedirs('Pisos/data', exist_ok=True)
with open('Pisos/data/resultats_lib.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n{'='*60}")
print(f"📊 {len(pisos)} pisos · 🟢{nc} 🟡{ne} 🔴{np_}")
print(f"💾 Pisos/data/resultats_lib.json guardat")
print(f"{'='*60}")
