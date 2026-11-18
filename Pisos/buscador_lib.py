#!/usr/bin/env python3
"""
🏠 BUSCADOR SEMÀFOR LIB — Colab Script
Busca pisos a TOTES les plataformes, aplica calculadora LIB de Carlos Galán,
genera un JSON amb semàfor per carregar a GitHub Pages.

Instruccions:
1. Puja aquest fitxer a Google Colab
2. Ajusta CONFIG (ciutats, preus, hipoteca)
3. Executa
4. Descarrega resultats_lib.json
5. Puja'l a diordes.github.io/Pisos/data/
"""

import requests, json, re, time, random, hashlib
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

# ═══════════════════════════════════════════════════════════════════
# CONFIGURACIÓ — AJUSTA AQUÍ
# ═══════════════════════════════════════════════════════════════════
CONFIG = {
    'ciutats': [
        {'nom': 'Lleida',   'idealista': 'lleida-lleida',   'fotocasa': 'lleida/lleida', 'habitaclia': 'lleida',   'ccaa': 'Cataluña'},
        {'nom': 'Binèfar',  'idealista': 'binefar-huesca',  'fotocasa': 'binefar/huesca','habitaclia': 'binefar',  'ccaa': 'Aragón'},
        {'nom': 'Manresa',  'idealista': 'manresa-barcelona','fotocasa': 'manresa/barcelona','habitaclia':'manresa', 'ccaa': 'Cataluña'},
        {'nom': 'Balaguer', 'idealista': 'balaguer-lleida', 'fotocasa': 'balaguer/lleida','habitaclia':'balaguer', 'ccaa': 'Cataluña'},
        {'nom': 'Mollerussa','idealista':'mollerussa-lleida','fotocasa': 'mollerussa/lleida','habitaclia':'mollerussa','ccaa':'Cataluña'},
        {'nom': 'Tàrrega',  'idealista': 'tarrega-lleida',  'fotocasa': 'tarrega/lleida','habitaclia':'tarrega',  'ccaa': 'Cataluña'},
    ],
    'preu_min': 30000,
    'preu_max': 70000,
    'hipoteca_pct': 0.80,
    'interes_fix': 3.50,
    'anys_hipoteca': 25,
    'itp': {  # Impost Transmissions per CCAA
        'Cataluña': 0.10, 'Aragón': 0.08, 'Comunidad de Madrid': 0.06,
        'Comunidad Valenciana': 0.10, 'Andalucía': 0.07, 'Galicia': 0.09,
        'País Vasco': 0.04, 'Castilla y León': 0.08, 'Castilla-La Mancha': 0.09,
        'Murcia': 0.08, 'Canarias': 0.065, 'Navarra': 0.06, 'Extremadura': 0.08,
        'Asturias': 0.08, 'Cantabria': 0.10, 'La Rioja': 0.07, 'Baleares': 0.08,
    },
    'notaria_registro': 2500,
    'comunitat_mes': 50,
    'asseguranca_any': 200,
}

# Rendes estimades per ciutat i mida (€/mes)
RENDES_ESTIMADES = {
    'Lleida':    {1: 350, 2: 430, 3: 500, 4: 550},
    'Binèfar':   {1: 300, 2: 380, 3: 430, 4: 480},
    'Manresa':   {1: 400, 2: 480, 3: 550, 4: 600},
    'Balaguer':  {1: 300, 2: 370, 3: 420, 4: 470},
    'Mollerussa': {1: 300, 2: 370, 3: 420, 4: 470},
    'Tàrrega':   {1: 320, 2: 390, 3: 440, 4: 490},
    '_default':  {1: 350, 2: 420, 3: 480, 4: 530},
}

# Zones Telegram Lleida
ZONES_TELEGRAM = {
    'bona': ['universitat', 'ricard vinyes', 'clot', 'princep de viana', 'escola del treball', 'cappont', 'centre historic', 'centre històric'],
    'evitar': ['mariola', 'bloques juan carlos', 'joan carles'],
}

# ═══════════════════════════════════════════════════════════════════
# CALCULADORA LIB
# ═══════════════════════════════════════════════════════════════════

def cuota_mensual(capital, interes_anual, anys):
    r = interes_anual / 100 / 12
    n = anys * 12
    if r == 0: return capital / n
    return capital * (r * (1+r)**n) / ((1+r)**n - 1)

def estimar_renda(ciutat, habs):
    rendes = RENDES_ESTIMADES.get(ciutat, RENDES_ESTIMADES['_default'])
    h = min(max(habs, 1), 4)
    return rendes.get(h, 400)

def classificar_zona(zona_text):
    """Retorna 'bona', 'evitar' o 'neutra'"""
    z = zona_text.lower().strip()
    for keyword in ZONES_TELEGRAM['bona']:
        if keyword in z: return 'bona'
    for keyword in ZONES_TELEGRAM['evitar']:
        if keyword in z: return 'evitar'
    return 'neutra'

def calcular_lib(preu, m2, habs, renda_mes, ciutat, zona, reforma=0):
    """Calcula totes les mètriques LIB i retorna dict"""
    ccaa = None
    for c in CONFIG['ciutats']:
        if c['nom'] == ciutat:
            ccaa = c['ccaa']; break
    if not ccaa: ccaa = 'Cataluña'
    
    itp_rate = CONFIG['itp'].get(ccaa, 0.10)
    itp = preu * itp_rate
    total_compra = preu + itp + CONFIG['notaria_registro'] + reforma
    
    capital_hipo = preu * CONFIG['hipoteca_pct']
    entrada = preu * (1 - CONFIG['hipoteca_pct'])
    capital_invertit = entrada + itp + CONFIG['notaria_registro'] + reforma
    quota = cuota_mensual(capital_hipo, CONFIG['interes_fix'], CONFIG['anys_hipoteca'])
    
    renda_anual = renda_mes * 12
    comunitat = CONFIG['comunitat_mes'] * 12
    ibi = preu * 0.005
    manteniment = renda_anual * 0.10
    vacancia = renda_anual * 0.05
    seguro_impago = renda_anual * 0.05
    total_gastos = comunitat + ibi + manteniment + vacancia + seguro_impago + CONFIG['asseguranca_any']
    
    rent_bruta = (renda_anual / preu * 100) if preu > 0 else 0
    benefici_net = renda_anual - total_gastos
    rent_neta = (benefici_net / total_compra * 100) if total_compra > 0 else 0
    per = (preu / renda_anual) if renda_anual > 0 else 999
    cashflow = renda_mes - quota - (total_gastos / 12)
    rent_capital = (benefici_net / capital_invertit * 100) if capital_invertit > 0 else 0
    
    zona_class = classificar_zona(zona)
    
    checks = []
    punts = 0
    if rent_bruta >= 7:   punts += 1; checks.append('bruta')
    if rent_neta >= 4:    punts += 1; checks.append('neta')
    if per <= 15:         punts += 1; checks.append('per')
    if cashflow >= 0:     punts += 1; checks.append('cf')
    if zona_class == 'bona':  punts += 1; checks.append('zona')
    if zona_class == 'evitar': punts -= 1
    
    if punts >= 4:   semfor = 'comprar'
    elif punts >= 2: semfor = 'estudiar'
    else:            semfor = 'passar'
    
    return {
        'bruta': round(rent_bruta, 1),
        'neta': round(rent_neta, 1),
        'per': round(per, 1),
        'cf': round(cashflow, 0),
        'rentCap': round(rent_capital, 1),
        'quota': round(quota, 0),
        'capInv': round(capital_invertit, 0),
        'checks': checks,
        'semfor': semfor,
        'zonaClass': zona_class,
    }

# ═══════════════════════════════════════════════════════════════════
# SCRAPERS PER PORTAL
# ═══════════════════════════════════════════════════════════════════

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.9,ca;q=0.8',
}

resultats = []

def uid(url):
    return hashlib.md5(url.encode()).hexdigest()[:10]

def pausa():
    time.sleep(random.uniform(2.0, 5.0))

# ── IDEALISTA ───────────────────────────────────────────────────
def buscar_idealista(ciutat_config):
    slug = ciutat_config['idealista']
    ciutat = ciutat_config['nom']
    url = f"https://www.idealista.com/venta-viviendas/{slug}/con-precio-hasta_{CONFIG['preu_max']},precio-desde_{CONFIG['preu_min']}/"
    print(f"  🔍 Idealista: {ciutat}... ", end="")
    
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"⚠️ Status {r.status_code}")
            return
        
        soup = BeautifulSoup(r.text, 'html.parser')
        articles = soup.select('article.item')
        count = 0
        
        for art in articles:
            try:
                # Títol i link
                title_el = art.select_one('a.item-link')
                if not title_el: continue
                titol = title_el.get_text(strip=True)
                href = title_el.get('href', '')
                link = f"https://www.idealista.com{href}" if href.startswith('/') else href
                
                # Preu
                preu_el = art.select_one('.item-price')
                if not preu_el: continue
                preu_text = re.sub(r'[^\d]', '', preu_el.get_text())
                if not preu_text: continue
                preu = int(preu_text)
                if preu < CONFIG['preu_min'] or preu > CONFIG['preu_max']: continue
                
                # Detalls
                detail_els = art.select('.item-detail')
                habs = 0; m2 = 0; planta = ''
                for d in detail_els:
                    t = d.get_text(strip=True)
                    hab_m = re.search(r'(\d+)\s*hab', t)
                    if hab_m: habs = int(hab_m.group(1))
                    m2_m = re.search(r'(\d+)\s*m²', t)
                    if m2_m: m2 = int(m2_m.group(1))
                    if 'planta' in t.lower() or 'bajo' in t.lower() or 'exterior' in t.lower():
                        planta = t
                
                # Zona (del títol)
                zona = ''
                parts = titol.split(',')
                if len(parts) >= 2:
                    zona = parts[-1].strip().replace(' Lleida', '').replace(' Huesca', '').replace(' Barcelona', '').strip()
                
                # Ocupat?
                desc_el = art.select_one('.item-description')
                desc = desc_el.get_text(strip=True) if desc_el else ''
                ocupat = any(x in desc.lower() for x in ['ocupada ilegalmente', 'cesión de remate', 'proindiviso', 'sin posesión'])
                alquilat = 'alquilada' in desc.lower() or 'alquilada' in titol.lower()
                
                if ocupat: continue  # Descartar directament
                
                renda = estimar_renda(ciutat, max(habs, 1))
                lib = calcular_lib(preu, m2, habs, renda, ciutat, zona)
                
                resultats.append({
                    'id': uid(link),
                    'nom': titol,
                    'preu': preu,
                    'm2': m2,
                    'habs': habs,
                    'renda': renda,
                    'ciutat': ciutat,
                    'zona': zona,
                    'planta': planta,
                    'portal': 'Idealista',
                    'url': link,
                    'alquilat': alquilat,
                    'notes': desc[:120] if desc else '',
                    **lib,
                })
                count += 1
            except Exception as e:
                continue
        
        print(f"✅ {count} pisos")
    except Exception as e:
        print(f"❌ Error: {e}")

# ── FOTOCASA ────────────────────────────────────────────────────
def buscar_fotocasa(ciutat_config):
    slug = ciutat_config['fotocasa']
    ciutat = ciutat_config['nom']
    url = f"https://www.fotocasa.es/es/comprar/viviendas/{slug}/l?maxPrice={CONFIG['preu_max']}&minPrice={CONFIG['preu_min']}"
    print(f"  🔍 Fotocasa: {ciutat}... ", end="")
    
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"⚠️ Status {r.status_code}")
            return
        
        soup = BeautifulSoup(r.text, 'html.parser')
        cards = soup.select('.re-CardPackAdvanced, .re-CardPackMinimal, .re-Card')
        count = 0
        
        for card in cards:
            try:
                link_el = card.select_one('a[href*="/vivienda/"]') or card.select_one('a[href*="/piso/"]') or card.select_one('a.re-CardPackAdvanced-link')
                if not link_el: continue
                href = link_el.get('href', '')
                link = f"https://www.fotocasa.es{href}" if href.startswith('/') else href
                
                titol_el = card.select_one('.re-CardTitle, .re-Card-title, h3')
                titol = titol_el.get_text(strip=True) if titol_el else f"Pis a {ciutat}"
                
                preu_el = card.select_one('.re-CardPrice, .re-Card-price')
                if not preu_el: continue
                preu_text = re.sub(r'[^\d]', '', preu_el.get_text())
                if not preu_text: continue
                preu = int(preu_text)
                if preu < CONFIG['preu_min'] or preu > CONFIG['preu_max']: continue
                
                feats = card.select('.re-CardFeatures-feature, .re-Card-feature')
                habs = 0; m2 = 0
                for f in feats:
                    t = f.get_text(strip=True)
                    hab_m = re.search(r'(\d+)\s*hab', t)
                    if hab_m: habs = int(hab_m.group(1))
                    m2_m = re.search(r'(\d+)\s*m²', t)
                    if m2_m: m2 = int(m2_m.group(1))
                
                renda = estimar_renda(ciutat, max(habs, 1))
                lib = calcular_lib(preu, m2, habs, renda, ciutat, ciutat)
                
                if link not in [r['url'] for r in resultats]:
                    resultats.append({
                        'id': uid(link),
                        'nom': titol,
                        'preu': preu,
                        'm2': m2,
                        'habs': habs,
                        'renda': renda,
                        'ciutat': ciutat,
                        'zona': ciutat,
                        'planta': '',
                        'portal': 'Fotocasa',
                        'url': link,
                        'alquilat': False,
                        'notes': '',
                        **lib,
                    })
                    count += 1
            except: continue
        
        print(f"✅ {count} pisos")
    except Exception as e:
        print(f"❌ Error: {e}")

# ── PORTALS DE BANCS (via Google site:search) ───────────────────
BANK_PORTALS = [
    {'nom': 'Haya Inmobiliaria', 'site': 'hfreinmobiliaria.com', 'portal': 'Haya'},
    {'nom': 'Servihabitat', 'site': 'servihabitat.com', 'portal': 'Servihabitat'},
    {'nom': 'Solvia', 'site': 'solvia.es', 'portal': 'Solvia'},
    {'nom': 'Altamira', 'site': 'altamirainmuebles.com', 'portal': 'Altamira'},
    {'nom': 'Aliseda', 'site': 'alisedainmobiliaria.com', 'portal': 'Aliseda'},
    {'nom': 'CaixaBank', 'site': 'inmuebles.caixabank.es', 'portal': 'CaixaBank'},
    {'nom': 'Anticipa', 'site': 'anticiparealestate.com', 'portal': 'Anticipa'},
]

def buscar_bancs(ciutat_config):
    ciutat = ciutat_config['nom']
    
    for bank in BANK_PORTALS:
        query = f"site:{bank['site']} piso {ciutat} venta"
        url = f"https://www.google.com/search?q={quote_plus(query)}&num=10"
        print(f"  🏦 {bank['nom']}: {ciutat}... ", end="")
        
        try:
            r = requests.get(url, headers={**HEADERS, 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}, timeout=10)
            if r.status_code != 200:
                print(f"⚠️ Status {r.status_code}")
                pausa()
                continue
            
            soup = BeautifulSoup(r.text, 'html.parser')
            links = soup.select('a[href*="' + bank['site'] + '"]')
            count = 0
            
            for link_el in links[:5]:
                href = link_el.get('href', '')
                # Extract real URL from Google redirect
                url_m = re.search(r'https?://[^&"]+' + re.escape(bank['site']) + r'[^&"]*', href)
                if not url_m: continue
                real_url = url_m.group(0)
                
                text = link_el.get_text(strip=True)
                
                # Try to extract price from snippet
                preu_m = re.search(r'(\d{2,3}[\.,]\d{3})\s*€', text)
                if not preu_m:
                    parent = link_el.parent
                    if parent:
                        preu_m = re.search(r'(\d{2,3}[\.,]\d{3})\s*€', parent.get_text())
                
                preu = 0
                if preu_m:
                    preu = int(preu_m.group(1).replace('.', '').replace(',', ''))
                
                if preu > 0 and (preu < CONFIG['preu_min'] or preu > CONFIG['preu_max']):
                    continue
                
                if preu == 0: preu = 50000  # Estimació si no es pot extreure
                
                habs_m = re.search(r'(\d+)\s*hab', text.lower())
                habs = int(habs_m.group(1)) if habs_m else 2
                m2_m = re.search(r'(\d+)\s*m', text)
                m2_val = int(m2_m.group(1)) if m2_m else 60
                
                renda = estimar_renda(ciutat, habs)
                lib = calcular_lib(preu, m2_val, habs, renda, ciutat, ciutat)
                
                if real_url not in [r['url'] for r in resultats]:
                    resultats.append({
                        'id': uid(real_url),
                        'nom': f"Pis de banc ({bank['portal']}) a {ciutat}",
                        'preu': preu,
                        'm2': m2_val,
                        'habs': habs,
                        'renda': renda,
                        'ciutat': ciutat,
                        'zona': ciutat,
                        'planta': '',
                        'portal': bank['portal'],
                        'url': real_url,
                        'alquilat': False,
                        'notes': f"Pis de banc. Preu pot no ser exacte. Text: {text[:80]}",
                        **lib,
                    })
                    count += 1
            
            print(f"✅ {count}" if count > 0 else "0")
            pausa()
        except Exception as e:
            print(f"❌ {e}")
            pausa()

# ═══════════════════════════════════════════════════════════════════
# EXECUCIÓ PRINCIPAL
# ═══════════════════════════════════════════════════════════════════

def main():
    print("="*60)
    print("🏠 BUSCADOR SEMÀFOR LIB — Libertad Inmobiliaria")
    print(f"   Preu: {CONFIG['preu_min']:,}–{CONFIG['preu_max']:,}€")
    print(f"   Hipoteca: {CONFIG['hipoteca_pct']*100:.0f}% a {CONFIG['interes_fix']}% fix")
    print(f"   Ciutats: {', '.join(c['nom'] for c in CONFIG['ciutats'])}")
    print("="*60)
    
    for ciutat in CONFIG['ciutats']:
        print(f"\n📍 {ciutat['nom']}:")
        buscar_idealista(ciutat)
        pausa()
        buscar_fotocasa(ciutat)
        pausa()
        buscar_bancs(ciutat)
    
    # Ordenar per semàfor i punts
    ordre = {'comprar': 0, 'estudiar': 1, 'passar': 2}
    resultats.sort(key=lambda x: (ordre.get(x['semfor'], 3), -x['bruta']))
    
    # Estadístiques
    n_comprar = sum(1 for r in resultats if r['semfor'] == 'comprar')
    n_estudiar = sum(1 for r in resultats if r['semfor'] == 'estudiar')
    n_passar = sum(1 for r in resultats if r['semfor'] == 'passar')
    
    print(f"\n{'='*60}")
    print(f"📊 RESULTATS: {len(resultats)} pisos analitzats")
    print(f"   🟢 COMPRAR:  {n_comprar}")
    print(f"   🟡 ESTUDIAR: {n_estudiar}")
    print(f"   🔴 PASSAR:   {n_passar}")
    print(f"{'='*60}")
    
    # Top 5
    print("\n🏆 TOP 5:")
    for i, r in enumerate(resultats[:5]):
        emoji = {0:'🥇',1:'🥈',2:'🥉',3:'4️⃣',4:'5️⃣'}
        print(f" {emoji.get(i,'')} {r['nom']}")
        print(f"    {r['preu']:,}€ · Bruta {r['bruta']}% · CF {r['cf']:+.0f}€ · {r['portal']}")
    
    # Guardar JSON
    output = {
        'generatEl': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'config': {
            'preuMin': CONFIG['preu_min'],
            'preuMax': CONFIG['preu_max'],
            'hipotecaPct': CONFIG['hipoteca_pct'],
            'interesFix': CONFIG['interes_fix'],
            'ciutats': [c['nom'] for c in CONFIG['ciutats']],
        },
        'resum': {
            'total': len(resultats),
            'comprar': n_comprar,
            'estudiar': n_estudiar,
            'passar': n_passar,
        },
        'pisos': resultats,
    }
    
    with open('resultats_lib.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Guardat: resultats_lib.json ({len(resultats)} pisos)")
    print("   Descarrega'l i puja'l a diordes.github.io/Pisos/data/")
    
    # Per Colab: descarregar automàticament
    try:
        from google.colab import files
        files.download('resultats_lib.json')
        print("   📥 Descarregant...")
    except:
        pass

if __name__ == '__main__':
    main()

