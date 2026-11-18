#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════
 SCRAPER DE PISOS — Companion per a diordes.github.io/Pisos
═══════════════════════════════════════════════════════════════════

 Executa a Google Colab. Busca pisos a Idealista, analitza amb la
 metodologia Libertad Inmobiliaria de Carlos Galan, i exporta un
 JSON que la web carrega amb "Importar JSON".

 Instruccions:
   1. Copia tot aquest codi a una cel·la de Google Colab
   2. Ajusta CONFIG a baix
   3. Executa
   4. Descarrega resultats_pisos.json
   5. Importa'l a https://diordes.github.io/Pisos/
═══════════════════════════════════════════════════════════════════
"""

# !pip install numpy-financial beautifulsoup4 requests lxml

import json
import time
import random
import re
from dataclasses import dataclass, asdict
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

try:
    import numpy_financial as npf
    HAS_NPF = True
except ImportError:
    HAS_NPF = False

# ═══════════════════════════════════════════════════════════════════
#  CONFIGURACIO — Ajusta al teu cas
# ═══════════════════════════════════════════════════════════════════

CONFIG = {
    'ciutats': [
        {
            'nom': 'Lleida',
            'idealista_slug': 'lleida-lleida',
            'ccaa': 'Cataluña',
            'ratio_lloguer': 0.007,  # estimacio renta = preu * ratio
        },
        {
            'nom': 'Binefar',
            'idealista_slug': 'binefar-huesca',
            'ccaa': 'Aragón',
            'ratio_lloguer': 0.007,
        },
    ],
    'preu_min': 40000,
    'preu_max': 70000,
    'pct_hipoteca': 0.80,
    'tipus_interes': 0.035,
    'termini_anys': 30,
    'comunitat_mes': 35,
    'ibi': 180,
    'delay_min': 5,
    'delay_max': 12,
    'max_pagines': 2,
}

# ═══════════════════════════════════════════════════════════════════
#  ITP per CCAA
# ═══════════════════════════════════════════════════════════════════

ITP = {
    'Andalucía':0.07,'Aragón':0.08,'Asturias':0.08,'Baleares':0.08,
    'Canarias':0.065,'Cantabria':0.10,'Castilla y León':0.08,
    'Castilla-La Mancha':0.09,'Cataluña':0.10,'Comunidad de Madrid':0.06,
    'Comunidad Valenciana':0.10,'Extremadura':0.08,'Galicia':0.10,
    'La Rioja':0.07,'Murcia':0.08,'Navarra':0.06,'País Vasco':0.04,
}

# ═══════════════════════════════════════════════════════════════════
#  SCRAPING IDEALISTA
# ═══════════════════════════════════════════════════════════════════

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]

def scrape_idealista(slug, preu_min, preu_max, max_pagines=2):
    """Scrape pisos en venda d'Idealista per un slug donat."""
    anuncis = []
    session = requests.Session()
    session.headers.update({
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ca,es;q=0.9,en;q=0.8',
    })

    for page in range(1, max_pagines + 1):
        filtres = f"con-precio-desde_{preu_min},precio-hasta_{preu_max}"
        if page == 1:
            url = f"https://www.idealista.com/venta-viviendas/{slug}/{filtres}/"
        else:
            url = f"https://www.idealista.com/venta-viviendas/{slug}/{filtres}/pagina-{page}.htm"

        print(f"  Pag {page}: {url}")
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code == 403:
                print("  ⚠ Blocat per Idealista (403). Prova mes tard o des d'una altra IP.")
                break
            if resp.status_code != 200:
                print(f"  ⚠ HTTP {resp.status_code}")
                break

            soup = BeautifulSoup(resp.text, 'lxml')
            articles = soup.select('article.item')
            if not articles:
                # intentar selector alternatiu
                articles = soup.select('div.item-info-container')

            if not articles:
                print(f"  Cap anunci trobat (possible bloqueig)")
                break

            for art in articles:
                try:
                    link_el = art.select_one('a.item-link') or art.select_one('a[href*="/inmueble/"]')
                    href = link_el['href'] if link_el else ''
                    if not href.startswith('http'):
                        href = 'https://www.idealista.com' + href

                    title_el = art.select_one('.item-link') or art.select_one('a')
                    title = title_el.get_text(strip=True) if title_el else ''

                    price_el = art.select_one('.item-price') or art.select_one('[class*="price"]')
                    price_text = price_el.get_text(strip=True) if price_el else '0'
                    price = int(re.sub(r'[^\d]', '', price_text.split('€')[0].split('EUR')[0])) if price_text else 0

                    detail_el = art.select_one('.item-detail-char') or art.select_one('[class*="detail"]')
                    detail = detail_el.get_text(' ', strip=True) if detail_el else ''

                    m2_match = re.search(r'(\d+)\s*m', detail)
                    m2 = int(m2_match.group(1)) if m2_match else 0

                    hab_match = re.search(r'(\d+)\s*hab', detail)
                    hab = int(hab_match.group(1)) if hab_match else 0

                    if price > 0:
                        anuncis.append({
                            'direccion': title[:60],
                            'precio': price,
                            'm2': m2,
                            'habitaciones': hab,
                            'url': href,
                            'detall': detail[:100],
                        })
                except Exception as e:
                    continue

            print(f"  → {len(articles)} anuncis a la pagina")

        except Exception as e:
            print(f"  Error: {e}")
            break

        # pausa anti-bot
        delay = random.uniform(CONFIG['delay_min'], CONFIG['delay_max'])
        print(f"  Esperant {delay:.1f}s...")
        time.sleep(delay)

    return anuncis


# ═══════════════════════════════════════════════════════════════════
#  CALCULADORA LIB (simplificada)
# ═══════════════════════════════════════════════════════════════════

def pmt(rate, nper, pv):
    if rate == 0:
        return -pv / nper
    x = (1 + rate) ** nper
    return -pv * rate * x / (x - 1)


def analitza_pis(preu, renta_mes, ccaa, reforma=0, comissio=0):
    """Calcula totes les metriques LIB per un pis."""
    itp_rate = ITP.get(ccaa, 0.08)
    itp_import = itp_rate * preu
    notaria = 500
    registre = 250
    gestoria = 300

    cost_vivenda = preu + itp_import + notaria + registre + gestoria + reforma + comissio
    gastos_hip = 300 + 250  # gestoria + taxacio
    preu_entrada = cost_vivenda + gastos_hip

    hipoteca = CONFIG['pct_hipoteca'] * preu
    capital_propi = preu_entrada - hipoteca

    r = CONFIG['tipus_interes']
    n = CONFIG['termini_anys']
    cuota_mes = -pmt(r / 12, n * 12, hipoteca)
    cuota_any = cuota_mes * 12

    # interessos mitjos
    total_pagat = cuota_any * n
    total_int = total_pagat - hipoteca
    int_anual_mitja = total_int / n
    part_devolucio = cuota_any - int_anual_mitja

    # ingressos i despeses
    renta_any = renta_mes * 12
    comunitat = CONFIG['comunitat_mes'] * 12
    manteniment = 0.10 * renta_any
    seg_impag = 0.05 * renta_any
    vacants = 0.05 * renta_any
    ibi = CONFIG['ibi']
    seg_hogar = 100
    seg_vida = 100
    gastos_total = comunitat + manteniment + seg_hogar + seg_vida + seg_impag + ibi + int_anual_mitja + vacants

    # fiscal
    pct_const = 0.50
    amortitzacio = 0.03 * (pct_const * (preu + itp_import + notaria + registre + gestoria) + reforma)
    benefici_brut = renta_any - gastos_total
    base_fiscal = max(0, benefici_brut - amortitzacio)
    impostos = base_fiscal * 0.70 * 0.30  # 30% reduccio, 30% tram
    benefici_net = benefici_brut - impostos

    # metriques
    rent_bruta = renta_any / preu_entrada if preu_entrada else 0
    rent_neta = (benefici_net + impostos + int_anual_mitja) / preu_entrada if preu_entrada else 0
    cashflow = benefici_net - part_devolucio
    roce = cashflow / capital_propi if capital_propi else 0
    patrimoni = part_devolucio / capital_propi if capital_propi else 0
    reval = 0.03 * preu / capital_propi if capital_propi else 0
    rent_cp = roce + patrimoni + reval
    per = preu_entrada / renta_any if renta_any else 999

    # TIR
    tir_val = None
    if HAS_NPF and capital_propi > 0 and renta_any > 0:
        cf = [-capital_propi]
        for y in range(1, 31):
            factor = 1.03 ** (y - 1)
            inc = renta_any * factor
            desp = (gastos_total - int_anual_mitja) * factor + int_anual_mitja
            tax = max(0, (inc - desp - amortitzacio) * 0.70 * 0.30)
            net = inc - desp - tax - cuota_any
            cf.append(net)
        # venda any 30
        valor_venda = preu * 1.03 ** 29
        ganancia = valor_venda - (cost_vivenda - amortitzacio * 30)
        irpf_gp = min(ganancia * 0.23, ganancia * 0.28) if ganancia > 0 else 0
        plusvalia = max(0, 0.30 * 0.03 * ganancia)
        hip_pend = 0  # a 30 anys ja esta pagada
        proceeds = valor_venda - irpf_gp - plusvalia - hip_pend
        cf[30] += proceeds
        try:
            tir_val = float(npf.irr(cf))
            if not (-1 < tir_val < 2):
                tir_val = None
        except:
            tir_val = None

    # puntuacio
    pts = 0
    if rent_bruta >= 0.07: pts += 1
    if rent_neta >= 0.04: pts += 1
    if rent_cp >= 0.10: pts += 1
    if tir_val and tir_val >= 0.08: pts += 1
    if per < 15: pts += 1
    if cashflow > 0: pts += 1
    if rent_bruta >= 0.08: pts += 1
    if rent_neta >= 0.055: pts += 1

    return {
        'preu_entrada': round(preu_entrada),
        'capital_propi': round(capital_propi),
        'hipoteca': round(hipoteca),
        'cuota_mes': round(cuota_mes),
        'rent_bruta': round(rent_bruta, 4),
        'rent_neta': round(rent_neta, 4),
        'rent_cp': round(rent_cp, 4),
        'tir': round(tir_val, 4) if tir_val else None,
        'per': round(per, 1),
        'cashflow_mes': round(cashflow / 12),
        'puntuacio': pts,
    }


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("  SCRAPER PISOS — Metodologia Libertad Inmobiliaria")
    print("=" * 70)

    tots_resultats = []

    for ciutat in CONFIG['ciutats']:
        print(f"\n🔍 Buscant a {ciutat['nom']} ({ciutat['idealista_slug']})...")
        anuncis = scrape_idealista(
            ciutat['idealista_slug'],
            CONFIG['preu_min'],
            CONFIG['preu_max'],
            CONFIG['max_pagines'],
        )
        print(f"  Trobats: {len(anuncis)} anuncis")

        for a in anuncis:
            # estimar lloguer si no el tenim
            renta = a.get('renta_mensual') or round(a['precio'] * ciutat['ratio_lloguer'])
            metriques = analitza_pis(
                a['precio'], renta, ciutat['ccaa']
            )

            resultat = {
                'ciudad': ciutat['nom'],
                'direccion': a['direccion'],
                'precio': a['precio'],
                'renta_mensual': renta,
                'm2': a['m2'],
                'habitaciones': a['habitaciones'],
                'url': a['url'],
                'ccaa': ciutat['ccaa'],
                **metriques,
            }
            tots_resultats.append(resultat)

    # ordenar per puntuacio
    tots_resultats.sort(key=lambda x: (-x['puntuacio'], -x['rent_bruta']))

    # mostrar report
    print(f"\n{'=' * 70}")
    print(f"  RESULTATS: {len(tots_resultats)} pisos analitzats")
    print(f"{'=' * 70}")

    if tots_resultats:
        print(f"\n{'Pis':<35} {'Preu':>7} {'Llog':>5} {'R.Br':>6} {'R.CP':>6} {'TIR':>6} {'PER':>5} {'CF':>5} {'Pts':>3}")
        print("-" * 90)
        for r in tots_resultats:
            tir_s = f"{r['tir']*100:.1f}%" if r['tir'] else '  — '
            print(f"{r['direccion']:<35} {r['precio']:>7,} {r['renta_mensual']:>5} {r['rent_bruta']*100:>5.1f}% {r['rent_cp']*100:>5.1f}% {tir_s:>6} {r['per']:>5.1f} {r['cashflow_mes']:>5} {r['puntuacio']:>3}/8")

    # exportar JSON
    output_file = 'resultats_pisos.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(tots_resultats, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Exportat a {output_file}")
    print(f"   Importa'l a https://diordes.github.io/Pisos/")


if __name__ == '__main__':
    main()
