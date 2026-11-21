#!/usr/bin/env python3
"""
Scraper per GitHub Actions — s'executa automàticament cada dia.
No cal tocar res. Busca pisos, calcula LIB, guarda JSON.
"""
import os, re, time, random, json, unicodedata
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import quote_plus

# ══ CONFIG ══════════════════════════════════════════════════════════
CIUTATS = [
    {'nom':'Lleida',    'slug':'lleida-lleida',     'ccaa':'Cataluña'},
    {'nom':'Binèfar',   'slug':'binefar-huesca',    'ccaa':'Aragón'},
    {'nom':'Manresa',   'slug':'manresa-barcelona',  'ccaa':'Cataluña'},
    {'nom':'Balaguer',  'slug':'balaguer-lleida',    'ccaa':'Cataluña'},
    {'nom':'Mollerussa','slug':'mollerussa-lleida',  'ccaa':'Cataluña'},
    {'nom':'Tàrrega',   'slug':'tarrega-lleida',     'ccaa':'Cataluña'},
    {'nom':'Fraga',     'slug':'fraga-huesca',       'ccaa':'Aragón'},
    {'nom':'Cervera',   'slug':'cervera-lleida',     'ccaa':'Cataluña'},
]

# Extra city from manual trigger
extra = os.environ.get('CIUTAT_EXTRA', '').strip()
if extra:
    s = re.sub(r'[^a-z0-9]+', '-', unicodedata.normalize('NFD', extra.lower()).encode('ascii','ignore').decode()).strip('-')
    CIUTATS.append({'nom': extra, 'slug': s, 'ccaa': 'Cataluña'})

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

# ══ LIB CALC ════════════════════════════════════════════════════════
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

def pausa(a=2,b=4): time.sleep(random.uniform(a,b))

# ══ IDEALISTA SCRAPER ═══════════════════════════════════════════════
pisos = []

def buscar_idealista(ciutat):
    nom = ciutat['nom']; sl = ciutat['slug']; ccaa = ciutat['ccaa']
    url = f"https://www.idealista.com/venta-viviendas/{sl}/con-precio-hasta_{PREU_MAX},precio-desde_{PREU_MIN}/"
    print(f"  🔍 Idealista {nom}...", end=" ")
    
    try:
        driver.get(url)
        pausa(3,5)
        try:
            driver.find_element(By.ID, 'didomi-notice-agree-button').click()
            pausa(1,2)
        except: pass
        
        articles = driver.find_elements(By.CSS_SELECTOR, 'article.item')
        if not articles:
            print("0"); return
        
        count = 0
        for art in articles:
            try:
                le = art.find_element(By.CSS_SELECTOR, 'a.item-link')
                titol = le.text.strip(); href = le.get_attribute('href')
                pe = art.find_element(By.CSS_SELECTOR, '.item-price')
                p = int(re.sub(r'[^\d]','',pe.text) or '0')
                if p<PREU_MIN or p>PREU_MAX or p==0: continue
                
                h=0; m=0; pl=''
                for d in art.find_elements(By.CSS_SELECTOR,'.item-detail'):
                    t=d.text
                    hm=re.search(r'(\d+)\s*hab',t)
                    if hm: h=int(hm.group(1))
                    mm=re.search(r'(\d+)\s*m²',t)
                    if mm: m=int(mm.group(1))
                    if any(x in t.lower() for x in['planta','bajo','ext','int']): pl=t
                
                z = titol.split(',')[-2].strip() if titol.count(',')>=2 else nom
                try: desc=art.find_element(By.CSS_SELECTOR,'.item-description').text[:120]
                except: desc=''
                if any(x in desc.lower() for x in['ocupada ilegalmente','cesión de remate','proindiviso']): continue
                
                renda = RENDES.get(min(max(h,1),4),420)
                met = calc(p, m, h, renda, ccaa)
                pisos.append({**met,'nom':titol,'preu':p,'m2':m,'habs':h,'renda':renda,
                    'ciutat':nom,'zona':z,'planta':pl,'portal':'Idealista','url':href,
                    'alquilat':'alquilada' in desc.lower(),'notes':desc,'zonaClass':'neutra'})
                count += 1
            except: continue
        print(f"✅ {count}")
    except Exception as e:
        print(f"❌ {e}")

# ══ FOTOCASA SCRAPER ════════════════════════════════════════════════
def buscar_fotocasa(ciutat):
    nom = ciutat['nom']; ccaa = ciutat['ccaa']
    s = re.sub(r'[^a-z0-9]+','-',unicodedata.normalize('NFD',nom.lower()).encode('ascii','ignore').decode()).strip('-')
    url = f"https://www.fotocasa.es/es/comprar/viviendas/{s}/todas-las-zonas/l?maxPrice={PREU_MAX}&minPrice={PREU_MIN}"
    print(f"  🔍 Fotocasa {nom}...", end=" ")
    
    try:
        driver.get(url)
        pausa(4,6)
        try:
            driver.find_element(By.ID,'didomi-notice-agree-button').click()
            pausa(1,2)
        except: pass
        
        try:
            WebDriverWait(driver,8).until(EC.presence_of_element_located((By.CSS_SELECTOR,'[class*="re-Card"]')))
        except:
            print("0"); return
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        count = 0
        
        for card in soup.select('[class*="re-Card"]'):
            try:
                le = card.select_one('a[href*="/comprar/"], a[href*="/en-venta/"]')
                if not le: continue
                href = le.get('href','')
                purl = f"https://www.fotocasa.es{href}" if href.startswith('/') else href
                
                txt = card.get_text()
                pm = re.search(r'([\d\.]+)\s*€',txt)
                if not pm: continue
                p = int(pm.group(1).replace('.',''))
                if p<PREU_MIN or p>PREU_MAX: continue
                
                h=2; m=0
                hm=re.search(r'(\d+)\s*hab',txt.lower())
                if hm: h=int(hm.group(1))
                mm=re.search(r'(\d+)\s*m²',txt)
                if mm: m=int(mm.group(1))
                
                te = card.select_one('[class*="Title"], h3')
                titol = te.get_text(strip=True) if te else f"Pis a {nom}"
                
                renda = RENDES.get(min(max(h,1),4),420)
                met = calc(p, m, h, renda, ccaa)
                
                if purl not in [x['url'] for x in pisos]:
                    pisos.append({**met,'nom':titol,'preu':p,'m2':m,'habs':h,'renda':renda,
                        'ciutat':nom,'zona':nom,'planta':'','portal':'Fotocasa','url':purl,
                        'alquilat':False,'notes':'','zonaClass':'neutra'})
                    count += 1
            except: continue
        print(f"{'✅ '+str(count) if count else '0'}")
    except Exception as e:
        print(f"❌ {e}")

# ══ BANCS ═══════════════════════════════════════════════════════════
BANCS = [('Haya','hfreinmobiliaria.com'),('Solvia','solvia.es'),
         ('CaixaBank','inmuebles.caixabank.es'),('Servihabitat','servihabitat.com')]

def buscar_bancs(ciutat):
    nom = ciutat['nom']; ccaa = ciutat['ccaa']
    for bnom,site in BANCS:
        q = f"site:{site} piso {nom} venta"
        url = f"https://www.google.com/search?q={quote_plus(q)}&num=5"
        print(f"  🏦 {bnom} {nom}...", end=" ")
        try:
            driver.get(url); pausa(2,4)
            count=0
            for le in driver.find_elements(By.CSS_SELECTOR,f'a[href*="{site}"]')[:5]:
                try:
                    href=le.get_attribute('href'); text=le.text
                    if not text or site not in href: continue
                    pm=re.search(r'(\d{2,3}[\.,]\d{3})\s*€',text)
                    if not pm: continue
                    p=int(pm.group(1).replace('.','').replace(',',''))
                    if p<PREU_MIN or p>PREU_MAX: continue
                    h=2; m=60
                    hm=re.search(r'(\d+)\s*hab',text.lower())
                    if hm: h=int(hm.group(1))
                    renda=RENDES.get(min(max(h,1),4),420)
                    met=calc(p,m,h,renda,ccaa)
                    if href not in[x['url']for x in pisos]:
                        pisos.append({**met,'nom':f"{bnom}: {text[:60]}",'preu':p,'m2':m,
                            'habs':h,'renda':renda,'ciutat':nom,'zona':nom,'planta':'',
                            'portal':bnom,'url':href,'alquilat':False,'notes':'','zonaClass':'neutra'})
                        count+=1
                except: continue
            print(f"{'✅ '+str(count) if count else '0'}")
        except: print("❌")
        pausa(1,3)

# ══ EXECUTAR ════════════════════════════════════════════════════════
print(f"\n🏠 BUSCADOR SEMÀFOR LIB")
print(f"   {PREU_MIN:,}–{PREU_MAX:,}€ · Hipo {HIPOTECA_PCT}% · {INTERES_FIX}% fix\n")

for c in CIUTATS:
    print(f"\n📍 {c['nom']}:")
    buscar_idealista(c)
    pausa(2,4)
    buscar_fotocasa(c)
    pausa(2,4)
    buscar_bancs(c)

driver.quit()

# ══ GUARDAR ═════════════════════════════════════════════════════════
pisos.sort(key=lambda x:(-x['pts'],-x['bruta']))
nc=sum(1 for p in pisos if p['semfor']=='comprar')
ne=sum(1 for p in pisos if p['semfor']=='estudiar')
np_=sum(1 for p in pisos if p['semfor']=='passar')

# Remove pts from output
clean = [{k:v for k,v in p.items() if k!='pts'} for p in pisos]

output = {
    'generatEl': time.strftime('%Y-%m-%d %H:%M'),
    'config':{'preuMin':PREU_MIN,'preuMax':PREU_MAX,'hipotecaPct':HIPOTECA_PCT/100,
              'interesFix':INTERES_FIX,'ciutats':[c['nom'] for c in CIUTATS]},
    'resum':{'total':len(pisos),'comprar':nc,'estudiar':ne,'passar':np_},
    'pisos': clean,
}

os.makedirs('Pisos/data', exist_ok=True)
with open('Pisos/data/resultats_lib.json','w',encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n{'='*60}")
print(f"📊 {len(pisos)} pisos · 🟢{nc} 🟡{ne} 🔴{np_}")
print(f"💾 Pisos/data/resultats_lib.json guardat")
print(f"{'='*60}")

