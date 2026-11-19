#!/usr/bin/env python3
"""
SMA1300 + MFI(5) Screener + Trailing Stop — GitHub Actions
===========================================================
Downloads S&P 500 data from Yahoo Finance, calculates SMA1300 and weekly MFI(5),
applies trailing stop (-3%) on daily closes, generates buy/sell signals,
runs backtest, and outputs data/sma1300_latest.json.

Parameters: SMA=1300, Entry MFI≤15, Exit MFI≥88, Trailing Stop -3%
"""

import numpy as np
import pandas as pd
import yfinance as yf
import json, time, os, sys
from datetime import datetime, timedelta
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

# ── PARAMETERS ──
SMA_PERIOD = 1300
ENTRY_MFI = 15
EXIT_MFI = 88
MFI_PERIOD = 5
PCT_PER_TRADE = 0.10  # 10% sizing
MAX_POSITIONS = 50
INITIAL_CAPITAL = 100000
TRAILING_STOP_PCT = -3  # Trailing stop at -3% from peak

# ── S&P 500 TICKERS ──
# We fetch the current list from Wikipedia
def get_sp500_tickers():
    """Get current S&P 500 tickers from Wikipedia."""
    try:
        tables = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
        df = tables[0]
        tickers = df['Symbol'].str.replace('.', '-', regex=False).tolist()
        print(f"  Wikipedia: {len(tickers)} tickers")
        return tickers
    except Exception as e:
        print(f"  Wikipedia failed ({e}), using fallback list")
        return FALLBACK_TICKERS

# Fallback list (subset)
FALLBACK_TICKERS = [
    "AAPL","ABBV","ABT","ACN","ADBE","ADI","ADM","ADP","ADSK","AEE","AEP",
    "AFL","AIG","AIZ","AJG","ALB","ALGN","ALL","ALLE","AMAT","AMD","AME",
    "AMGN","AMP","AMT","AMZN","ANET","ANSS","AON","APA","APD","APH","APTV",
    "ARE","ATO","AVB","AVGO","AVY","AWK","AXP","AZO","BA","BAC","BAX","BBY",
    "BDX","BEN","BIIB","BIO","BK","BKNG","BKR","BLK","BMY","BR","BRK-B",
    "BRO","BSX","BWA","BXP","C","CAG","CAH","CARR","CAT","CB","CBOE","CBRE",
    "CCI","CCL","CDNS","CDW","CE","CEG","CF","CFG","CHD","CHRW","CHTR","CI",
    "CINF","CL","CLX","CMA","CMCSA","CME","CMG","CMI","CMS","CNC","CNP",
    "COF","COO","COP","COST","CPB","CPRT","CPT","CRL","CRM","CSCO","CSGP",
    "CSX","CTAS","CTRA","CTSH","CTVA","CVS","CVX","D","DAL","DD","DE","DFS",
    "DG","DGX","DHI","DHR","DIS","DLTR","DOV","DOW","DPZ","DRI","DTE","DUK",
    "DVA","DVN","DXCM","EA","EBAY","ECL","ED","EFX","EIX","EL","EMN","EMR",
    "ENPH","EOG","EQIX","EQR","EQT","ES","ESS","ETN","ETR","EVRG","EW","EXC",
    "EXPD","EXPE","EXR","F","FANG","FAST","FBHS","FCX","FDS","FDX","FE","FFIV",
    "FI","FICO","FIS","FISV","FITB","FMC","FOX","FOXA","FRT","FTNT","FTV",
    "GD","GE","GILD","GIS","GL","GLW","GM","GNRC","GOOG","GOOGL","GPC","GPN",
    "GRMN","GS","GWW","HAL","HAS","HBAN","HCA","HD","HOLX","HON","HPE","HPQ",
    "HRL","HSIC","HST","HSY","HUM","HWM","IBM","ICE","IDXX","IEX","IFF","ILMN",
    "INCY","INTC","INTU","INVH","IP","IPG","IQV","IR","IRM","ISRG","IT","ITW",
    "IVZ","J","JBHT","JCI","JKHY","JNJ","JNPR","JPM","K","KDP","KEY","KEYS",
    "KHC","KIM","KLAC","KMB","KMI","KMX","KO","KR","L","LDOS","LEN","LH",
    "LHX","LIN","LKQ","LLY","LMT","LNT","LOW","LRCX","LUV","LW","LYB","LYV",
    "MA","MAA","MAR","MAS","MCD","MCHP","MCK","MCO","MDLZ","MDT","MET","META",
    "MGM","MHK","MKC","MKTX","MLM","MMC","MMM","MNST","MO","MOH","MOS","MPC",
    "MPWR","MRK","MRNA","MRO","MS","MSCI","MSFT","MSI","MTB","MTD","MU","NCLH",
    "NDAQ","NDSN","NEE","NEM","NFLX","NI","NKE","NOC","NOW","NRG","NSC","NTAP",
    "NTRS","NUE","NVDA","NVR","NWL","NWS","NWSA","NXPI","O","ODFL","OGN","OKE",
    "OMC","ON","ORCL","ORLY","OTIS","OXY","PARA","PAYC","PAYX","PCAR","PCG",
    "PEG","PEP","PFE","PFG","PG","PGR","PH","PHM","PKG","PKI","PLD","PM",
    "PNC","PNR","PNW","POOL","PPG","PPL","PRU","PSA","PSX","PTC","PVH","PWR",
    "PXD","PYPL","QCOM","QRVO","RCL","RE","REG","REGN","RF","RHI","RJF","RL",
    "RMD","ROK","ROL","ROP","ROST","RSG","RTX","SBAC","SBUX","SCHW","SEE","SHW",
    "SJM","SLB","SNA","SNPS","SO","SPG","SPGI","SRE","STE","STT","STX","STZ",
    "SWK","SWKS","SYF","SYK","SYY","T","TAP","TDG","TDY","TECH","TEL","TER",
    "TFC","TFX","TGT","TJX","TMO","TMUS","TPR","TRGP","TRMB","TROW","TRV",
    "TSCO","TSLA","TSN","TT","TTWO","TXN","TXT","TYL","UAL","UDR","UHS","ULTA",
    "UNH","UNP","UPS","URI","USB","V","VFC","VICI","VLO","VMC","VNO","VRSK",
    "VRSN","VRTX","VTR","VTRS","VZ","WAB","WAT","WBA","WBD","WDC","WEC","WELL",
    "WFC","WHR","WM","WMB","WMT","WRB","WRK","WST","WTW","WY","WYNN","XEL",
    "XOM","XRAY","XYL","YUM","ZBH","ZBRA","ZION","ZTS"
]


# ════════════════════════════════════════════
# CORE FUNCTIONS
# ════════════════════════════════════════════

def calculate_weekly_mfi(df, period=5):
    """Calculate weekly MFI(period) from daily OHLCV data."""
    weekly = df.resample('W-FRI').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min',
        'Close': 'last', 'Volume': 'sum'
    }).dropna()
    tp = (weekly['High'] + weekly['Low'] + weekly['Close']) / 3
    mf = tp * weekly['Volume']
    pos_mf = pd.Series(0.0, index=weekly.index)
    neg_mf = pd.Series(0.0, index=weekly.index)
    for i in range(1, len(tp)):
        if tp.iloc[i] > tp.iloc[i-1]:
            pos_mf.iloc[i] = mf.iloc[i]
        elif tp.iloc[i] < tp.iloc[i-1]:
            neg_mf.iloc[i] = mf.iloc[i]
    pos_sum = pos_mf.rolling(window=period).sum()
    neg_sum = neg_mf.rolling(window=period).sum()
    mfr = pos_sum / neg_sum.replace(0, np.nan)
    mfi = 100 - (100 / (1 + mfr))
    return mfi, weekly['Close']


def extract_trades(ticker, df, sma_period=SMA_PERIOD, entry_mfi=ENTRY_MFI,
                   exit_mfi=EXIT_MFI, trailing_stop_pct=TRAILING_STOP_PCT):
    """Extract all closed trades using SMA+MFI crossover + trailing stop (-3%)."""
    if len(df) < sma_period + 50:
        return [], None
    df = df.copy()
    df['SMA'] = df['Close'].rolling(window=sma_period).mean()
    try:
        mfi_series, weekly_close = calculate_weekly_mfi(df, period=MFI_PERIOD)
    except:
        return [], None
    if len(mfi_series) < 3:
        return [], None

    trades = []
    in_trade = False
    entry_price = entry_date = peak_price = None

    for i in range(1, len(mfi_series)):
        current_date = mfi_series.index[i]
        current_mfi = mfi_series.iloc[i]
        prev_mfi = mfi_series.iloc[i-1]
        if pd.isna(current_mfi) or pd.isna(prev_mfi):
            continue
        valid_sma = df['SMA'].loc[:current_date].dropna()
        if len(valid_sma) == 0:
            continue
        current_sma = valid_sma.iloc[-1]
        current_price = weekly_close.iloc[i]

        if not in_trade:
            # BUY: price < SMA and MFI crosses UP through entry threshold
            if current_price < current_sma and prev_mfi <= entry_mfi and current_mfi > entry_mfi:
                in_trade = True
                entry_price = current_price
                entry_date = current_date
                peak_price = entry_price
        else:
            # ── Check daily prices for trailing stop between weekly checkpoints ──
            prev_week_date = mfi_series.index[i-1]
            daily_mask = (df.index > prev_week_date) & (df.index <= current_date)
            daily_closes = df.loc[daily_mask, 'Close']

            ts_exit = False
            if trailing_stop_pct is not None:
                for d_idx in range(len(daily_closes)):
                    d_close = daily_closes.iloc[d_idx]
                    d_date = daily_closes.index[d_idx]
                    if d_close > peak_price:
                        peak_price = d_close
                    ts_level = peak_price * (1 + trailing_stop_pct / 100)
                    if d_close <= ts_level:
                        ret = (d_close / entry_price - 1) * 100
                        days = (d_date - entry_date).days
                        trades.append({
                            'ticker': ticker, 'entry_date': entry_date,
                            'exit_date': d_date, 'entry_price': float(entry_price),
                            'exit_price': float(d_close), 'return_pct': float(ret),
                            'days': max(int(days), 1), 'exit_reason': 'TS'
                        })
                        in_trade = False
                        ts_exit = True
                        break

            if ts_exit:
                continue

            # Update peak from daily data
            if len(daily_closes) > 0:
                max_daily = float(daily_closes.max())
                if max_daily > peak_price:
                    peak_price = max_daily

            # SELL: price > SMA and MFI crosses DOWN through exit threshold
            if current_price > current_sma and prev_mfi >= exit_mfi and current_mfi < exit_mfi:
                return_pct = (current_price / entry_price - 1) * 100
                days = (current_date - entry_date).days
                trades.append({
                    'ticker': ticker, 'entry_date': entry_date,
                    'exit_date': current_date, 'entry_price': float(entry_price),
                    'exit_price': float(current_price), 'return_pct': float(return_pct),
                    'days': int(days), 'exit_reason': 'MFI'
                })
                in_trade = False

    # ── Check open position (including daily data after last weekly date) ──
    open_pos = None
    if in_trade and entry_price is not None:
        last_weekly = mfi_series.index[-1]
        daily_after = df.loc[df.index > last_weekly, 'Close']

        # Check TS on remaining daily data
        if trailing_stop_pct is not None:
            for d_idx in range(len(daily_after)):
                d_close = daily_after.iloc[d_idx]
                d_date = daily_after.index[d_idx]
                if d_close > peak_price:
                    peak_price = d_close
                ts_level = peak_price * (1 + trailing_stop_pct / 100)
                if d_close <= ts_level:
                    ret = (d_close / entry_price - 1) * 100
                    days = (d_date - entry_date).days
                    trades.append({
                        'ticker': ticker, 'entry_date': entry_date,
                        'exit_date': d_date, 'entry_price': float(entry_price),
                        'exit_price': float(d_close), 'return_pct': float(ret),
                        'days': max(int(days), 1), 'exit_reason': 'TS'
                    })
                    in_trade = False
                    break

        if in_trade:
            # Update peak with all remaining daily data
            if len(daily_after) > 0:
                max_after = float(daily_after.max())
                if max_after > peak_price:
                    peak_price = max_after
            last_price = df['Close'].iloc[-1]
            if last_price > peak_price:
                peak_price = float(last_price)
            last_mfi = mfi_series.iloc[-1]
            last_sma = df['SMA'].dropna().iloc[-1] if len(df['SMA'].dropna()) > 0 else None
            ts_level = peak_price * (1 + trailing_stop_pct / 100) if trailing_stop_pct else None
            open_pos = {
                'ticker': ticker,
                'entryDate': entry_date.strftime('%Y-%m-%d'),
                'entryPrice': round(float(entry_price), 2),
                'currentPrice': round(float(last_price), 2),
                'pl': round(float((last_price / entry_price - 1) * 100), 1),
                'mfi': round(float(last_mfi), 1) if not pd.isna(last_mfi) else None,
                'distSma': round(float((last_price / last_sma - 1) * 100), 1) if last_sma else None,
                'days': int((df.index[-1] - entry_date).days),
                'peakPrice': round(float(peak_price), 2),
                'tsLevel': round(float(ts_level), 2) if ts_level else None,
                'distTs': round(float((last_price / ts_level - 1) * 100), 1) if ts_level else None
            }

    return trades, open_pos


def get_current_signals(ticker, df, sma_period=SMA_PERIOD, entry_mfi=ENTRY_MFI, exit_mfi=EXIT_MFI):
    """Check if ticker currently has a buy or sell signal."""
    if len(df) < sma_period + 50:
        return None
    df = df.copy()
    df['SMA'] = df['Close'].rolling(window=sma_period).mean()
    try:
        mfi_series, weekly_close = calculate_weekly_mfi(df, period=MFI_PERIOD)
    except:
        return None
    if len(mfi_series) < 3:
        return None

    current_mfi = mfi_series.iloc[-1]
    prev_mfi = mfi_series.iloc[-2]
    current_price = weekly_close.iloc[-1]
    valid_sma = df['SMA'].dropna()
    if len(valid_sma) == 0:
        return None
    current_sma = valid_sma.iloc[-1]

    if pd.isna(current_mfi) or pd.isna(prev_mfi):
        return None

    dist_sma = (current_price / current_sma - 1) * 100

    # Check for buy signal
    if current_price < current_sma and prev_mfi <= entry_mfi and current_mfi > entry_mfi:
        return {
            'sym': ticker,
            'signal': 'BUY',
            'price': round(float(current_price), 2),
            'sma': round(float(current_sma), 2),
            'mfi': round(float(current_mfi), 1),
            'prevMfi': round(float(prev_mfi), 1),
            'distSma': round(float(dist_sma), 1)
        }
    # Check for sell signal
    if current_price > current_sma and prev_mfi >= exit_mfi and current_mfi < exit_mfi:
        return {
            'sym': ticker,
            'signal': 'SELL',
            'price': round(float(current_price), 2),
            'sma': round(float(current_sma), 2),
            'mfi': round(float(current_mfi), 1),
            'prevMfi': round(float(prev_mfi), 1),
            'distSma': round(float(dist_sma), 1)
        }
    return None


def simulate_portfolio(all_trades, weekly_close_series, initial_capital=INITIAL_CAPITAL,
                       pct_per_trade=PCT_PER_TRADE, max_positions=MAX_POSITIONS):
    """Run backtest simulation — BASE variant, no phases."""
    if not all_trades:
        return None

    sorted_trades = sorted(all_trades, key=lambda t: t['entry_date'])

    min_date = min(t['entry_date'] for t in sorted_trades)
    max_date = max(t['exit_date'] for t in sorted_trades)
    weeks = pd.date_range(min_date, max_date + pd.Timedelta(days=7), freq='W-FRI')

    entries_by_week = {}
    exits_by_week = {}
    for t in sorted_trades:
        entries_by_week.setdefault(t['entry_date'], []).append(t)
        # Snap exit date to Friday for weekly portfolio simulation
        # (TS exits can happen on any weekday)
        ed = pd.Timestamp(t['exit_date'])
        days_to_fri = (4 - ed.weekday()) % 7
        exit_fri = ed + pd.Timedelta(days=days_to_fri) if days_to_fri > 0 else ed
        exits_by_week.setdefault(exit_fri, []).append(t)

    cash = initial_capital
    positions = []
    equity_curve = []
    trades_taken = 0
    trades_skipped = 0
    yearly_returns = {}
    prev_year_equity = initial_capital
    current_year = min_date.year

    for week in weeks:
        # Year boundary
        if week.year != current_year:
            total_eq = cash + sum(
                pos['alloc'] * (weekly_close_series.get(pos['ticker'], pd.Series()).reindex([week]).iloc[0]
                                / pos['entry_price'])
                if pos['ticker'] in weekly_close_series else pos['alloc']
                for pos in positions
            ) if positions else cash
            if prev_year_equity > 0:
                yearly_returns[current_year] = round((total_eq / prev_year_equity - 1) * 100, 2)
            prev_year_equity = total_eq
            current_year = week.year

        # Exits
        if week in exits_by_week:
            for t in exits_by_week[week]:
                for j, pos in enumerate(positions):
                    if pos['ticker'] == t['ticker'] and pos['entry_date'] == t['entry_date']:
                        exit_val = pos['alloc'] * (1 + t['return_pct'] / 100)
                        cash += exit_val
                        positions.pop(j)
                        break

        # Entries
        if week in entries_by_week:
            for t in entries_by_week[week]:
                if len(positions) >= max_positions:
                    trades_skipped += 1
                    continue
                alloc = cash * pct_per_trade
                if alloc < 200:
                    trades_skipped += 1
                    continue
                cash -= alloc
                positions.append({
                    'ticker': t['ticker'], 'entry_date': t['entry_date'],
                    'entry_price': t['entry_price'], 'alloc': alloc,
                })
                trades_taken += 1

        # Equity
        invested_val = 0
        for pos in positions:
            if pos['ticker'] in weekly_close_series:
                wcs = weekly_close_series[pos['ticker']]
                valid = wcs.index[wcs.index <= week]
                if len(valid) > 0:
                    cp = wcs.loc[valid[-1]]
                    invested_val += pos['alloc'] * (cp / pos['entry_price'])
                else:
                    invested_val += pos['alloc']
            else:
                invested_val += pos['alloc']

        total_equity = cash + invested_val
        equity_curve.append({'date': week, 'equity': total_equity})

    # Final year
    if equity_curve and prev_year_equity > 0:
        final_eq = equity_curve[-1]['equity']
        yearly_returns[current_year] = round((final_eq / prev_year_equity - 1) * 100, 2)

    # Compute stats
    equities = [e['equity'] for e in equity_curve]
    if not equities:
        return None

    final_equity = equities[-1]
    years = (max_date - min_date).days / 365.25
    cagr = ((final_equity / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0

    # Max drawdown
    peak = equities[0]
    max_dd = 0
    for eq in equities:
        if eq > peak:
            peak = eq
        dd = (eq - peak) / peak * 100
        if dd < max_dd:
            max_dd = dd

    calmar = cagr / abs(max_dd) if max_dd != 0 else 0

    # Win rate
    wins = [t for t in all_trades if t['return_pct'] > 0]
    losses = [t for t in all_trades if t['return_pct'] <= 0]
    win_rate = len(wins) / len(all_trades) * 100 if all_trades else 0
    avg_win = np.mean([t['return_pct'] for t in wins]) if wins else 0
    avg_loss = np.mean([t['return_pct'] for t in losses]) if losses else 0

    return {
        'cagr': round(cagr, 2),
        'maxDD': round(max_dd, 1),
        'calmar': round(calmar, 3),
        'totalTrades': len(all_trades),
        'tradesTaken': trades_taken,
        'tradesSkipped': trades_skipped,
        'winRate': round(win_rate, 1),
        'avgWin': round(float(avg_win), 1),
        'avgLoss': round(float(avg_loss), 1),
        'finalEquity': round(final_equity, 0),
        'yearlyReturns': yearly_returns,
        'years': round(years, 1)
    }


# ════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════

def main():
    t_start = time.time()
    print("=" * 80)
    print("SMA1300 + MFI(5) + TS SCREENER — GitHub Actions")
    print(f"Params: SMA={SMA_PERIOD}, Entry MFI≤{ENTRY_MFI}, Exit MFI≥{EXIT_MFI}, TS={TRAILING_STOP_PCT}%, Sizing={PCT_PER_TRADE*100:.0f}%")
    print("=" * 80)

    # 1. Get tickers
    tickers = get_sp500_tickers()

    # 2. Download data
    print(f"\nDownloading data for {len(tickers)} stocks...")
    stock_data = {}
    batch_size = 50
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        try:
            data = yf.download(' '.join(batch), period='max', auto_adjust=True,
                              progress=False, threads=True)
            if isinstance(data.columns, pd.MultiIndex):
                for t in batch:
                    if t in data['Close'].columns:
                        df = pd.DataFrame({
                            'Open': data['Open'][t], 'High': data['High'][t],
                            'Low': data['Low'][t], 'Close': data['Close'][t],
                            'Volume': data['Volume'][t]
                        }).dropna()
                        if len(df) > 500:
                            stock_data[t] = df
            else:
                if len(batch) == 1 and len(data) > 500:
                    stock_data[batch[0]] = data[['Open','High','Low','Close','Volume']].dropna()
        except Exception as e:
            print(f"  Batch error: {e}")
        print(f"  {min(i+batch_size, len(tickers))}/{len(tickers)} ({len(stock_data)} OK)")

    print(f"\n{len(stock_data)} stocks downloaded in {time.time()-t_start:.0f}s")

    # 3. Build weekly close series
    weekly_close_series = {}
    for ticker, df in stock_data.items():
        wc = df['Close'].resample('W-FRI').last().dropna()
        if len(wc) > 50:
            weekly_close_series[ticker] = wc

    # 4. Extract trades and current signals
    print("\nExtracting trades & signals...")
    all_trades = []
    buy_signals = []
    sell_signals = []
    open_positions = []

    for ticker, df in stock_data.items():
        # Trades + open position
        trades, open_pos = extract_trades(ticker, df)
        all_trades.extend(trades)
        if open_pos:
            open_positions.append(open_pos)

        # Current signals
        signal = get_current_signals(ticker, df)
        if signal:
            if signal['signal'] == 'BUY':
                buy_signals.append(signal)
            else:
                sell_signals.append(signal)

    print(f"  Total trades: {len(all_trades)}")
    print(f"  Buy signals: {len(buy_signals)}")
    print(f"  Sell signals: {len(sell_signals)}")
    print(f"  Open positions: {len(open_positions)}")

    # Sort signals
    buy_signals.sort(key=lambda s: s['mfi'])
    sell_signals.sort(key=lambda s: -s['mfi'])
    open_positions.sort(key=lambda p: -p['pl'])

    # 5. Run backtest
    print("\nRunning backtest...")
    bt = simulate_portfolio(all_trades, weekly_close_series)
    if bt:
        ts_exits = len([t for t in all_trades if t.get('exit_reason') == 'TS'])
        mfi_exits = len([t for t in all_trades if t.get('exit_reason') == 'MFI'])
        print(f"  CAGR: {bt['cagr']}%")
        print(f"  MaxDD: {bt['maxDD']}%")
        print(f"  Calmar: {bt['calmar']}")
        print(f"  Win Rate: {bt['winRate']}%")
        print(f"  Trades: {bt['totalTrades']} (TS: {ts_exits}, MFI: {mfi_exits})")

    # 6. Recent closed trades (last 20)
    recent_trades = sorted(all_trades, key=lambda t: t['exit_date'], reverse=True)[:20]
    recent_trades_json = [{
        'sym': t['ticker'],
        'entry': t['entry_date'].strftime('%Y-%m-%d'),
        'exit': t['exit_date'].strftime('%Y-%m-%d'),
        'pl': round(t['return_pct'], 1),
        'days': t['days'],
        'reason': t.get('exit_reason', 'MFI')
    } for t in recent_trades]

    # 7. Build output JSON
    yearly_returns_list = []
    if bt and bt['yearlyReturns']:
        for yr in sorted(bt['yearlyReturns'].keys()):
            yearly_returns_list.append({'year': yr, 'return': bt['yearlyReturns'][yr]})

    output = {
        'generatedAt': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'params': {
            'sma': SMA_PERIOD,
            'entryMfi': ENTRY_MFI,
            'exitMfi': EXIT_MFI,
            'mfiPeriod': MFI_PERIOD,
            'sizing': PCT_PER_TRADE * 100,
            'maxPositions': MAX_POSITIONS,
            'trailingStopPct': TRAILING_STOP_PCT
        },
        'summary': {
            'totalStocks': len(stock_data),
            'buySignals': len(buy_signals),
            'sellSignals': len(sell_signals),
            'openPositions': len(open_positions),
            'backtestCagr': bt['cagr'] if bt else None,
            'backtestMaxDD': bt['maxDD'] if bt else None,
            'backtestCalmar': bt['calmar'] if bt else None,
            'totalTrades': bt['totalTrades'] if bt else 0,
            'winRate': bt['winRate'] if bt else None,
            'avgWin': bt['avgWin'] if bt else None,
            'avgLoss': bt['avgLoss'] if bt else None,
            'backtestYears': bt['years'] if bt else None,
            'tsExits': len([t for t in all_trades if t.get('exit_reason') == 'TS']),
            'mfiExits': len([t for t in all_trades if t.get('exit_reason') == 'MFI'])
        },
        'buySignals': buy_signals,
        'sellSignals': sell_signals,
        'openPositions': open_positions,
        'yearlyReturns': yearly_returns_list,
        'recentTrades': recent_trades_json
    }

    # 8. Write output
    os.makedirs('data', exist_ok=True)
    out_path = 'data/sma1300_latest.json'
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)

    elapsed = time.time() - t_start
    print(f"\n{'='*80}")
    print(f"Done in {elapsed:.0f}s — {out_path} ({os.path.getsize(out_path)} bytes)")
    print(f"{'='*80}")
    return output


if __name__ == '__main__':
    main()
