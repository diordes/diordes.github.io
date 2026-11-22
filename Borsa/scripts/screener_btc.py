"""
SCREENER BITCOIN — DCA + Senyals Escalonades
═══════════════════════════════════════════════════════
Estratègia base: DCA €500/mes el dia 1 (1a setmana = preu mig més baix).
Quan el screener detecta oportunitats, aportar EXTRA:

  EXCEL·LENT  → +€10.000  (rebot confirmat al suport en zona barata)
  MOLT BONA   → + €3.000  (prop del suport en zona barata, pendent rebot)
  Sense senyal →  DCA      (sense extra)

Zona barata = preu < SMA150 × 0.90
Suport = mínim setmanal 4w
Rebot = preu ≤ suport×1.03 AND pujant vs ahir

Calibrat amb simulació completa 2020-2024 (pool SP500 20.8%/any):
  €10K Exc + €3K MB → Calmar 24.3, DD addicional -0.6%
  Rendiment lineal: cada €1K extra a EXCELLENT = +€1.900 patrimoni

SORTIDA posicions: SL -20% → trailing SMA200 ratchet (mai baixar)
COOLDOWN: 8 setmanes post-SL
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import os
import warnings
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")

# ═══════════════════════════════════════════════════════════════
#  PARÀMETRES (adaptats a volatilitat cripto)
# ═══════════════════════════════════════════════════════════════
BUFFER    = 0.10       # 10% sota SMA150 (backtest: millor Calmar)
SMA_LEN   = 150        # SMA150 — validat grid fi (medià Calmar 0.184)
SMA_TRAIL = 200        # SMA200 per trailing ratchet (robust)
SR_WEEKS  = 4          # setmanes per calcular suport
MFI_LEN   = 5          # MFI per info
MFI_SELL  = 80
STOP_LOSS = 0.20       # -20% (equilibri DD/oportunitat)
COOLDOWN  = 8          # setmanes post-SL
PCT_TRADE = 1.00       # 100% — 1 sola posició BTC
TICKER    = "BTC-EUR"
NOM       = "Bitcoin (€)"

# Aportacions extra recomanades per senyal (sobre DCA base)
EXTRA_EXCELLENT  = 10_000   # rebot confirmat al suport
EXTRA_MOLT_BONA  =  3_000   # prop del suport, pendent rebot
DCA_DIA          = 1        # dia del mes per fer DCA (1r — backtest: 1a setmana és la més barata)

# ═══════════════════════════════════════════════════════════════
#  CONFIG (GitHub Actions: config_btc.json / Colab: valors per defecte)
# ═══════════════════════════════════════════════════════════════
try:
    script_dir = Path(__file__).parent
except NameError:
    script_dir = Path(".")

config_path = script_dir / "config_btc.json"
if config_path.exists():
    with open(config_path) as f:
        cfg = json.load(f)
    CASH_ACTUAL   = cfg.get("cash_actual", 5000)
    APORTACIO_MES = cfg.get("aportacio_mes", 500)
    POSICIO       = cfg.get("posicio", None)     # {"preu": X, "btc": Y, "data": "YYYY-MM-DD", "sl": Z, "trailing_sl": 0}
    SL_HISTORIAL  = cfg.get("sl_historial", [])  # [{"data": "YYYY-MM-DD"}, ...]
else:
    CASH_ACTUAL     = 5_000
    APORTACIO_MES   = 500
    POSICIO         = None   # Cap posició oberta per defecte
    SL_HISTORIAL    = []

# ═══════════════════════════════════════════════════════════════
#  TELEGRAM
# ═══════════════════════════════════════════════════════════════
TG_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TG_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")

def tg(text):
    if not TG_TOKEN or not TG_CHAT: return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": text,
                  "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=10)
    except: pass

# ═══════════════════════════════════════════════════════════════
#  DADES BTC
# ═══════════════════════════════════════════════════════════════
print(f"📥 Descarregant {NOM} ({TICKER})…")
data = yf.download(TICKER, period="800d", auto_adjust=True, progress=False)

if data.empty or len(data) < SMA_LEN + 10:
    print(f"❌ No hi ha prou dades per {TICKER} (calen >{SMA_LEN + 10} dies)")
    exit(1)

# Aplanar columnes MultiIndex si cal
if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.get_level_values(0)

H = data["High"]
L = data["Low"]
C = data["Close"]
V = data["Volume"]

print(f"   ✅ {len(data)} dies de dades")

# ═══════════════════════════════════════════════════════════════
#  BENCHMARK (S&P 500 per comparar)
# ═══════════════════════════════════════════════════════════════
print("📥 Benchmark…")
bench = {}
for btick, bnom in [(TICKER, NOM), ("SPY", "SPY (S&P 500)")]:
    try:
        bd = yf.download(btick, period="800d", auto_adjust=True, progress=False)["Close"].dropna()
        if isinstance(bd, pd.DataFrame):
            bd = bd.iloc[:, 0]
        if len(bd) > 50:
            sma200 = bd.rolling(200).mean()
            ret_1m = (float(bd.iloc[-1]) / float(bd.iloc[-22]) - 1) * 100 if len(bd) > 22 else 0
            ret_3m = (float(bd.iloc[-1]) / float(bd.iloc[-66]) - 1) * 100 if len(bd) > 66 else 0
            ret_ytd = (float(bd.iloc[-1]) / float(bd[bd.index >= f"{bd.index[-1].year}-01-01"].iloc[0]) - 1) * 100
            ret_1y = (float(bd.iloc[-1]) / float(bd.iloc[-252]) - 1) * 100 if len(bd) > 252 else 0
            bench[btick] = {
                "nom": bnom, "preu": round(float(bd.iloc[-1]), 2),
                "sma200": round(float(sma200.iloc[-1]), 2) if len(bd) > 200 else None,
                "ret_1m": round(ret_1m, 1), "ret_3m": round(ret_3m, 1),
                "ret_ytd": round(ret_ytd, 1), "ret_1y": round(ret_1y, 1),
            }
    except: pass

# ═══════════════════════════════════════════════════════════════
#  COOLDOWNS
# ═══════════════════════════════════════════════════════════════
avui = datetime.now()
en_cooldown = False
cd_rest = 0
for item in SL_HISTORIAL:
    dsl = item.get("data", "") if isinstance(item, dict) else item
    if not dsl: continue
    d = (avui - datetime.strptime(dsl, "%Y-%m-%d")).days
    rest = COOLDOWN * 7 - d
    if rest > 0:
        en_cooldown = True
        cd_rest = rest // 7
        break

# ═══════════════════════════════════════════════════════════════
#  ANALITZAR
# ═══════════════════════════════════════════════════════════════
print("⚙️  Analitzant…\n")

c = C.dropna()
if isinstance(c, pd.DataFrame):
    c = c.iloc[:, 0]

sma_val = c.rolling(SMA_LEN).mean()
sma_trail_val = c.rolling(SMA_TRAIL).mean()
preu = float(c.iloc[-1])
preu_ahir = float(c.iloc[-2]) if len(c) > 1 else preu
sma_v = float(sma_val.iloc[-1])
sma_t = float(sma_trail_val.iloc[-1]) if len(c) >= SMA_TRAIL else sma_v
pct = preu / sma_v - 1

# MFI setmanal
h_s = H if isinstance(H, pd.Series) else H.iloc[:, 0] if isinstance(H, pd.DataFrame) else H
l_s = L if isinstance(L, pd.Series) else L.iloc[:, 0] if isinstance(L, pd.DataFrame) else L
c_s = C if isinstance(C, pd.Series) else C.iloc[:, 0] if isinstance(C, pd.DataFrame) else C
v_s = V if isinstance(V, pd.Series) else V.iloc[:, 0] if isinstance(V, pd.DataFrame) else V

df_w = pd.DataFrame({"H": h_s, "L": l_s, "C": c_s, "V": v_s}).dropna()
w = df_w.resample("W-FRI").agg({"H": "max", "L": "min", "C": "last", "V": "sum"}).dropna()
tp = (w.H + w.L + w.C) / 3
rmf = tp * w.V
pos_f = rmf.where(tp > tp.shift(1), 0.0).rolling(MFI_LEN).sum()
neg_f = rmf.where(tp < tp.shift(1), 0.0).rolling(MFI_LEN).sum()
mfi = (100 - 100 / (1 + pos_f / neg_f)).where(neg_f != 0, 100.0).dropna()
m_now = float(mfi.iloc[-1]) if len(mfi) > 0 else 50

# Suport setmanal
lw = l_s.resample("W-FRI").min().dropna()
support = float(lw.iloc[-(SR_WEEKS + 1):-1].min()) if len(lw) >= SR_WEEKS + 1 else None

# Resistència setmanal
hw = h_s.resample("W-FRI").max().dropna()
resist = float(hw.iloc[-(SR_WEEKS + 1):-1].max()) if len(hw) >= SR_WEEKS + 1 else None

# RSI 14 (indicador extra per BTC)
delta = c.diff()
gain = delta.where(delta > 0, 0.0).rolling(14).mean()
loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
rs = gain / loss
rsi = (100 - 100 / (1 + rs)).dropna()
rsi_now = float(rsi.iloc[-1]) if len(rsi) > 0 else 50

# Fear & Greed aprox (basat en volatilitat 30d)
vol_30d = c.pct_change().rolling(30).std() * np.sqrt(365) * 100
vol_now = float(vol_30d.iloc[-1]) if len(vol_30d.dropna()) > 0 else 0

# Condicions
barat = preu < sma_v * (1 - BUFFER)
above_sma = preu >= sma_v
sl_preu = round(preu * (1 - STOP_LOSS), 2)

# Rebot al suport?
rebot = False
if support and barat:
    rebot = (preu <= support * 1.03) and (preu > preu_ahir)

# Prop del suport (vigilar)
prop_suport = False
if support and barat and not rebot:
    prop_suport = (preu <= support * 1.08)

# ═══════════════════════════════════════════════════════════════
#  SENYALS — 3 nivells escalonats
# ═══════════════════════════════════════════════════════════════
senyal_compra = None
senyal_vigilar = None
senyal_venda = None
senyal_mantenir = None
senyal_tier = None   # "EXCELLENT" | "MOLT_BONA" | "BONA" | None

# ── Classificació en 3 nivells ──
if barat:
    if rebot and not en_cooldown:
        senyal_tier = "EXCELLENT"
        senyal_compra = {
            "accio": "COMPRA",
            "motiu": f"🟢 EXCEL·LENT — Rebot al suport €{support:,.0f}, zona barata",
            "extra": EXTRA_EXCELLENT,
        }
    elif rebot and en_cooldown:
        senyal_compra = {
            "accio": "COOLDOWN",
            "motiu": f"⏳ Rebot detectat però en cooldown ({cd_rest} set restants)",
        }
    elif prop_suport and not en_cooldown:
        senyal_tier = "MOLT_BONA"
        dist = round((preu / support - 1) * 100, 1)
        senyal_vigilar = {
            "accio": "VIGILAR",
            "motiu": f"🟡 MOLT BONA — Prop del suport €{support:,.0f} ({dist:+.1f}%), pendent rebot",
            "extra": EXTRA_MOLT_BONA,
        }
    # Si barat però ni prop ni rebot → sense senyal (només DCA base)

# ── POSICIÓ OBERTA ──
if POSICIO:
    p = POSICIO
    pl = (preu / p["preu"] - 1) * 100
    valor_btc = preu * p["btc"]

    # 1) Stop-loss fix
    if preu <= p["sl"]:
        senyal_venda = {
            "accio": "VENDRE",
            "motiu": "⛔ STOP-LOSS — VEN ARA",
            "pl": round(pl, 1),
        }

    # 2) Trailing actiu (preu ≥ SMA → ratchet)
    elif above_sma:
        old_trailing = p.get("trailing_sl", 0) or 0
        sl_ratchet = max(sma_t, old_trailing)

        if preu < sl_ratchet:
            senyal_venda = {
                "accio": "VENDRE",
                "motiu": f"🔴 VEN — per sota SMA{SMA_TRAIL} ratchet (€{sl_ratchet:,.0f})",
                "pl": round(pl, 1),
            }
        else:
            sl_accio = ""
            if old_trailing == 0:
                sl_accio = f"🔺 ACTIVA trailing SL a €{sl_ratchet:,.0f} (SMA{SMA_TRAIL})"
            elif sl_ratchet > old_trailing:
                sl_accio = f"🔺 PUJA SL de €{old_trailing:,.0f} → €{sl_ratchet:,.0f}"
            else:
                sl_accio = f"✅ MANTÉ SL a €{old_trailing:,.0f} (mai baixar)"
            marge = ((preu / sl_ratchet) - 1) * 100
            senyal_mantenir = {
                "accio": "MANTENIR",
                "estat": f"🟢 TRAILING — SMA{SMA_TRAIL}=${sma_t:,.0f}, marge {marge:+.1f}%",
                "sl_accio": sl_accio,
                "pl": round(pl, 1),
            }

    # 3) Encara per sota SMA
    else:
        recent_cross = None
        for dd in range(1, min(11, len(c))):
            p_d = float(c.iloc[-dd])
            s_d = float(sma_val.iloc[-dd])
            p_p = float(c.iloc[-dd - 1]) if dd + 1 < len(c) else p_d
            s_p = float(sma_val.iloc[-dd - 1]) if dd + 1 < len(c) else s_d
            if p_p >= s_p and p_d < s_d:
                recent_cross = c.index[-dd].strftime("%d/%m/%Y")
                break

        if recent_cross:
            senyal_venda = {
                "accio": "POSSIBLE VENDA",
                "motiu": f"🟠 Va creuar SMA{SMA_LEN} avall el {recent_cross}",
                "pl": round(pl, 1),
            }
        else:
            sup_txt = f", suport=€{support:,.0f}" if support else ""
            senyal_mantenir = {
                "accio": "MANTENIR",
                "estat": f"Sota SMA: {pct * 100:+.1f}% vs SMA{SMA_LEN}, MFI={m_now:.0f}{sup_txt}",
                "sl_accio": f"SL al broker: €{p['sl']:,.0f} (fase 1, no tocar)",
                "pl": round(pl, 1),
            }

# ═══════════════════════════════════════════════════════════════
#  EUR/USD (per benchmark SPY en USD)
# ═══════════════════════════════════════════════════════════════
eur_usd = 1.08
try:
    fx = yf.download("EURUSD=X", period="5d", auto_adjust=True, progress=False)["Close"].dropna()
    if isinstance(fx, pd.DataFrame):
        fx = fx.iloc[:, 0]
    if len(fx) > 0:
        eur_usd = round(float(fx.iloc[-1]), 4)
except: pass

# ═══════════════════════════════════════════════════════════════
#  OUTPUT CONSOLA
# ═══════════════════════════════════════════════════════════════
data_str = avui.strftime("%d/%m/%Y %H:%M")
print(f"{'=' * 70}")
print(f"  SCREENER BITCOIN — {data_str}")
print(f"  DCA €{APORTACIO_MES:,}/mes + Extra: EXCEL·LENT €{EXTRA_EXCELLENT:,} | M.BONA €{EXTRA_MOLT_BONA:,}")
print(f"{'=' * 70}")

# Preu i indicadors
print(f"\n₿ BITCOIN:")
print(f"   Preu:     €{preu:>10,.2f}")
print(f"   SMA{SMA_LEN}:   €{sma_v:>10,.2f}  ({pct * 100:+.1f}%)")
print(f"   SMA{SMA_TRAIL}:   €{sma_t:>10,.2f}")
if support:
    dist_sup = (preu / support - 1) * 100
    print(f"   Suport:   €{support:>10,.2f}  ({dist_sup:+.1f}%)")
if resist:
    dist_res = (preu / resist - 1) * 100
    print(f"   Resist:   €{resist:>10,.2f}  ({dist_res:+.1f}%)")
print(f"   RSI(14):  {rsi_now:>10.1f}")
print(f"   MFI({MFI_LEN}):   {m_now:>10.0f}")
print(f"   Vol 30d:  {vol_now:>10.1f}% anualitzada")
print(f"   Zona:     {'🔴 BARAT (sota SMA×{:.0f}%)'.format((1-BUFFER)*100) if barat else '🟢 SOBRE SMA' if above_sma else '🟡 ENTRE SMA i zona barata'}")

# Cartera
cash_disponible = CASH_ACTUAL
per_entrada = round(cash_disponible * PCT_TRADE, -1) if cash_disponible >= 100 else 0
valor_pos = 0
cost_pos = 0

if POSICIO:
    valor_pos = preu * POSICIO["btc"]
    cost_pos = POSICIO["preu"] * POSICIO["btc"]

pl_pct = ((valor_pos / cost_pos - 1) * 100) if cost_pos > 0 else 0
patrimoni = CASH_ACTUAL + valor_pos  # tot en EUR (BTC-EUR directe)

print(f"\n💰 CARTERA BTC:")
print(f"   Cash:             €{CASH_ACTUAL:>8,}")
if POSICIO:
    emoji_pl = "🟩" if pl_pct >= 0 else "🟥"
    print(f"   Posició:          {POSICIO['btc']:.4f} BTC  (€{valor_pos:,.0f})")
    print(f"   Compra:           €{POSICIO['preu']:,.0f} el {POSICIO['data']}")
    print(f"   P&L:              {emoji_pl} {pl_pct:+.1f}%  (€{valor_pos - cost_pos:+,.0f})")
else:
    print(f"   Posició:          cap")
print(f"   PATRIMONI:        €{patrimoni:>8,.0f}")
if per_entrada > 0:
    btc_compra = per_entrada / preu
    print(f"   ➜ Per entrada:    €{per_entrada:>8,.0f}  ({btc_compra:.4f} BTC)")
else:
    print(f"   ⚠️ No hi ha cash per noves compres")
# DCA info
es_dia_dca = avui.day == DCA_DIA
if es_dia_dca:
    btc_dca = APORTACIO_MES / preu
    print(f"   🗓️  AVUI ÉS DIA DCA! → Compra €{APORTACIO_MES:,} ({btc_dca:.6f} BTC)")
else:
    import calendar
    any_actual = avui.year
    mes_actual = avui.month
    if avui.day > DCA_DIA:
        # Proper mes
        if mes_actual == 12:
            mes_actual = 1
            any_actual += 1
        else:
            mes_actual += 1
    proper_dca = datetime(any_actual, mes_actual, DCA_DIA)
    dies_falten = (proper_dca - avui).days
    print(f"   🗓️  DCA: €{APORTACIO_MES:,} el dia {DCA_DIA} ({dies_falten} dies)")
print(f"   Extra si senyal:  EXCEL·LENT +€{EXTRA_EXCELLENT:,} | MOLT BONA +€{EXTRA_MOLT_BONA:,}")

# Benchmark
if bench:
    print(f"\n📊 BENCHMARK:")
    for btick, b in bench.items():
        sma_txt = f"  {'↑' if b['preu'] >= (b.get('sma200') or 0) else '↓'}SMA200={b.get('sma200', '?')}" if b.get("sma200") else ""
        sym = "€" if "EUR" in btick else "$"
        print(f"   {b['nom']:<20s} {sym}{b['preu']:>10,.2f}  1m={b['ret_1m']:+.1f}%  3m={b['ret_3m']:+.1f}%  "
              f"YTD={b['ret_ytd']:+.1f}%  1y={b['ret_1y']:+.1f}%{sma_txt}")

print(f"\n💱 EUR/USD: {eur_usd}")

# Senyals
print(f"\n{'─' * 70}")
print(f"  SENYALS")
print(f"{'─' * 70}")

if senyal_compra:
    if senyal_compra["accio"] == "COMPRA":
        print(f"\n🟢 SENYAL EXCEL·LENT — COMPRA:")
        print(f"   {senyal_compra['motiu']}")
        print(f"   SMA{SMA_LEN}={pct * 100:+.1f}%  MFI={m_now:.0f}  RSI={rsi_now:.1f}")
        print(f"   ⛔ SL=€{sl_preu:,.0f} (-{STOP_LOSS * 100:.0f}%)")
        print(f"   💰 DCA base: €{APORTACIO_MES:,}/mes")
        print(f"   💰 EXTRA recomanat: €{EXTRA_EXCELLENT:,}")
        if per_entrada > 0:
            btc_q = per_entrada / preu
            print(f"   💰 Cash disponible: €{per_entrada:,.0f} → {btc_q:.4f} BTC")
    else:
        print(f"\n⏳ {senyal_compra['motiu']}")

elif senyal_vigilar:
    print(f"\n🟡 SENYAL MOLT BONA — VIGILAR:")
    print(f"   {senyal_vigilar['motiu']}")
    print(f"   MFI={m_now:.0f}  RSI={rsi_now:.1f}  Vol={vol_now:.0f}%")
    print(f"   💰 DCA base: €{APORTACIO_MES:,}/mes")
    print(f"   💰 EXTRA recomanat si rebota: €{EXTRA_MOLT_BONA:,}")

else:
    trigger = sma_v * (1 - BUFFER)
    if preu > trigger:
        print(f"\n💤 Sense senyal — preu €{preu:,.0f} > zona de compra €{trigger:,.0f}")
        print(f"   💰 Només DCA base: €{APORTACIO_MES:,}/mes")
    else:
        print(f"\n💤 Sense rebot — preu a la zona barata però no ha rebotat al suport")

if senyal_venda:
    emoji = "🟩" if senyal_venda["pl"] > 0 else "🟥"
    print(f"\n🔴 {senyal_venda['motiu']}")
    print(f"   {emoji} P&L: {senyal_venda['pl']:+.1f}%")

if senyal_mantenir:
    emoji = "🟩" if senyal_mantenir["pl"] > 0 else "🟥"
    print(f"\n📈 MANTENIR — {senyal_mantenir['estat']}")
    print(f"   {emoji} P&L: {senyal_mantenir['pl']:+.1f}%")
    if senyal_mantenir.get("sl_accio"):
        print(f"   📌 {senyal_mantenir['sl_accio']}")

if en_cooldown and not senyal_compra:
    print(f"\n⏳ COOLDOWN: {cd_rest} setmanes restants")

# ═══════════════════════════════════════════════════════════════
#  GUARDAR JSON
# ═══════════════════════════════════════════════════════════════
data_dir = script_dir / "data"
data_dir.mkdir(exist_ok=True)

output = {
    "data": avui.isoformat(),
    "eurUsd": eur_usd,
    "ticker": TICKER,
    "config": {
        "cash": CASH_ACTUAL,
        "aportacio_mes": APORTACIO_MES,
        "dca_dia": DCA_DIA,
        "es_dia_dca": es_dia_dca,
        "posicio": POSICIO,
    },
    "btc": {
        "preu": round(preu, 2),
        "sma150": round(sma_v, 2),
        "sma200": round(sma_t, 2),
        "pct_sma": round(pct * 100, 1),
        "support": round(support, 2) if support else None,
        "resist": round(resist, 2) if resist else None,
        "rsi": round(rsi_now, 1),
        "mfi": round(m_now, 0),
        "vol_30d": round(vol_now, 1),
        "barat": barat,
        "above_sma": above_sma,
    },
    "resum": {
        "patrimoni_eur": round(patrimoni),
        "cash": CASH_ACTUAL,
        "valor_pos_usd": round(valor_pos),
        "cost_pos_usd": round(cost_pos),
        "pl_pct": round(pl_pct, 1),
        "per_entrada": per_entrada,
        "te_posicio": POSICIO is not None,
    },
    "senyals": {
        "tier": senyal_tier,         # EXCELLENT / MOLT_BONA / None
        "extra_recomanat": (
            EXTRA_EXCELLENT if senyal_tier == "EXCELLENT"
            else EXTRA_MOLT_BONA if senyal_tier == "MOLT_BONA"
            else 0
        ),
        "dca_base": APORTACIO_MES,
        "compra": senyal_compra,
        "vigilar": senyal_vigilar,
        "venda": senyal_venda,
        "mantenir": senyal_mantenir,
        "cooldown": en_cooldown,
        "cooldown_rest": cd_rest if en_cooldown else 0,
    },
    "bench": bench,
}

out_path = data_dir / "latest_btc.json"
with open(out_path, "w") as f:
    json.dump(output, f, indent=2, default=str)
print(f"\n💾 {out_path}")

# També compatibilitat
with open(script_dir / "screener_btc_output.json", "w") as f:
    json.dump(output, f, indent=2, default=str)

# ═══════════════════════════════════════════════════════════════
#  TELEGRAM
# ═══════════════════════════════════════════════════════════════
enviar = senyal_compra or senyal_venda or senyal_vigilar or es_dia_dca

if enviar and TG_TOKEN:
    print("📱 Enviant Telegram…")
    msg = f"₿ <b>SCREENER BTC</b> — {avui.strftime('%d/%m/%Y')}\n"
    msg += f"Preu: €{preu:,.0f} | SMA{SMA_LEN}: {pct * 100:+.1f}%\n"
    msg += f"RSI: {rsi_now:.0f} | MFI: {m_now:.0f} | Vol: {vol_now:.0f}%\n"

    if es_dia_dca:
        btc_dca = APORTACIO_MES / preu
        msg += f"\n🗓️ <b>DIA DCA</b> — Compra €{APORTACIO_MES:,} ({btc_dca:.6f} BTC)\n"

    if senyal_compra:
        if senyal_compra["accio"] == "COMPRA":
            btc_q = per_entrada / preu if per_entrada > 0 else 0
            msg += f"\n🟢 <b>EXCEL·LENT — COMPRA</b>\n"
            msg += f"Suport: €{support:,.0f} | SL: €{sl_preu:,.0f}\n"
            msg += f"💰 DCA: €{APORTACIO_MES:,}/mes + EXTRA: €{EXTRA_EXCELLENT:,}\n"
            if per_entrada > 0:
                msg += f"💰 Cash: €{per_entrada:,.0f} → {btc_q:.4f} BTC\n"
        else:
            msg += f"\n⏳ {senyal_compra['motiu']}\n"

    if senyal_venda:
        msg += f"\n🔴 <b>{senyal_venda['motiu']}</b>\n"
        msg += f"P&L: {senyal_venda['pl']:+.1f}%\n"

    if senyal_vigilar:
        msg += f"\n🟡 <b>MOLT BONA — VIGILAR</b>\n{senyal_vigilar['motiu']}\n"
        msg += f"💰 Si rebota → EXTRA: €{EXTRA_MOLT_BONA:,}\n"

    if POSICIO:
        msg += f"\n📈 Posició: {POSICIO['btc']:.4f} BTC ({pl_pct:+.1f}%)\n"

    msg += f"\n💰 Patrimoni: €{patrimoni:,.0f}"
    tg(msg)
    print("   ✅ Enviat!")
elif not enviar:
    print("💤 Res a notificar")
elif not TG_TOKEN:
    print("💡 Telegram no configurat")

print("✅ Acabat!")
