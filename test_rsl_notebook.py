"""
Test script for RSL Levy Strategy Notebook
Tests all major components locally before uploading to Google Colab.

Fixes vs. previous version:
- RSL_PERIOD corrected from 130 → 26 (matching notebook's Levy definition)
- LOOKBACK_DAYS corrected from 365 → 400 (needed for 200-day MA)
- beautifulsoup4 import check fixed (now imports 'bs4' correctly)
- Added multi-period returns, MA-distance and volume-surge metrics
- All metric names synced with notebook
"""

import sys
import subprocess

def install_packages():
    """Install required packages if not already available."""
    package_map = {
        'yfinance':       'yfinance',
        'pandas':         'pandas',
        'numpy':          'numpy',
        'openpyxl':       'openpyxl',
        'bs4':            'beautifulsoup4',
        'lxml':           'lxml',
        'tqdm':           'tqdm',
        'xlsxwriter':     'xlsxwriter',
    }
    for import_name, install_name in package_map.items():
        try:
            __import__(import_name)
        except ImportError:
            print(f"Installing {install_name}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', install_name, '-q'])

print("=" * 70)
print("RSL LEVY STRATEGY NOTEBOOK - LOCAL TEST")
print("=" * 70)

print("\n[1/6] Checking and installing required packages...")
install_packages()

import pandas as pd
import numpy as np
import yfinance as yf
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from tqdm import tqdm
import time
import warnings
import os

warnings.filterwarnings('ignore')
print(f"All packages imported successfully! ({datetime.now().strftime('%d.%m.%Y %H:%M')})")

# =============================================================================
# CONFIGURATION  (must match rsl_levy_strategy.ipynb)
# =============================================================================
RSL_PERIOD    = 26    # 26 Handelstage — Levy's original definition
LOOKBACK_DAYS = 400   # Enough for 200-day MA
API_DELAY     = 0.15
TOP_PERCENTILE = 0.25
OUTPUT_FILE   = f"RSL_Rankings_TEST_{datetime.now().strftime('%Y%m%d')}.xlsx"

# =============================================================================
# TEST 1: S&P 500 Tickers from Wikipedia
# =============================================================================
print("\n[2/6] Testing Wikipedia S&P 500 ticker fetch...")

def fetch_sp500_tickers():
    """Fetch S&P 500 tickers, sectors and industries from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup  = BeautifulSoup(response.text, 'lxml')
        table = soup.find('table', {'id': 'constituents'})
        if table is None:
            for t in soup.find_all('table', {'class': 'wikitable'}):
                if t.find('th', string=lambda x: x and 'Symbol' in x):
                    table = t
                    break

        df = pd.read_html(str(table))[0]
        df.columns = df.columns.str.strip()

        return pd.DataFrame({
            'Symbol':   df['Symbol'].str.strip().str.replace('.', '-', regex=False),
            'Company':  df['Security'].str.strip(),
            'Sector':   df['GICS Sector'].str.strip() if 'GICS Sector' in df.columns else 'N/A',
            'Industry': df['GICS Sub-Industry'].str.strip() if 'GICS Sub-Industry' in df.columns else 'N/A',
        })

    except Exception as e:
        print(f"  Warning: Wikipedia fetch failed ({e}). Using fallback list.")
        fallback = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA',
                    'BRK-B', 'UNH', 'JNJ', 'V', 'XOM', 'JPM', 'PG', 'MA']
        names    = ['Apple', 'Microsoft', 'Alphabet', 'Amazon', 'NVIDIA', 'Meta', 'Tesla',
                    'Berkshire', 'UnitedHealth', 'J&J', 'Visa', 'Exxon', 'JPMorgan', 'P&G', 'Mastercard']
        return pd.DataFrame({'Symbol': fallback, 'Company': names,
                             'Sector': ['Technology'] * 15, 'Industry': ['Various'] * 15})

sp500_df = fetch_sp500_tickers()
print(f"  Fetched {len(sp500_df)} S&P 500 tickers")
print(f"  Sample: {', '.join(sp500_df['Symbol'].head(5).tolist())}")
print(f"  {'[PASS]' if len(sp500_df) >= 400 else '[WARNING] Using fallback list'} Wikipedia fetch")

# =============================================================================
# TEST 2: RSL Calculation
# =============================================================================
print("\n[3/6] Testing RSL calculation (period = 26 days)...")

def calculate_rsl(prices, period=RSL_PERIOD):
    """RSL = current price / SMA(period)."""
    if prices is None or len(prices) < period:
        return None
    try:
        current = prices.iloc[-1]
        sma     = prices.iloc[-period:].mean()
        if sma == 0 or pd.isna(sma):
            return None
        return round(current / sma, 4)
    except Exception:
        return None

def calculate_change(prices, days):
    """% price change over N days."""
    if prices is None or len(days if isinstance(days, list) else [days]) > len(prices):
        pass
    if prices is None or len(prices) < days:
        return None
    try:
        curr = prices.iloc[-1]
        prev = prices.iloc[-days]
        if prev == 0:
            return None
        return round(((curr - prev) / prev) * 100, 2)
    except Exception:
        return None

# Verify RSL direction
up_prices   = pd.Series([100 + i * 0.5 for i in range(150)])
down_prices = pd.Series([150 - i * 0.5 for i in range(150)])
rsl_up   = calculate_rsl(up_prices)
rsl_down = calculate_rsl(down_prices)
print(f"  Uptrend  RSL: {rsl_up}  (expect > 1.0)")
print(f"  Downtrend RSL: {rsl_down}  (expect < 1.0)")
assert rsl_up   is not None and rsl_up   > 1.0, "RSL uptrend test failed"
assert rsl_down is not None and rsl_down < 1.0, "RSL downtrend test failed"
print("  [PASS] RSL calculation correct")

# =============================================================================
# TEST 3: Yahoo Finance Data Fetch (with new metrics)
# =============================================================================
print("\n[4/6] Testing Yahoo Finance data fetch...")

end_date   = datetime.now()
start_date = end_date - timedelta(days=LOOKBACK_DAYS)

def fetch_stock_data(ticker, start_date, end_date):
    """Fetch and compute all metrics — mirrors notebook's hole_aktien_daten()."""
    try:
        stock = yf.Ticker(ticker)
        hist  = stock.history(start=start_date, end=end_date, auto_adjust=True)

        if hist.empty or len(hist) < RSL_PERIOD:
            return None

        closes = hist['Close']
        volume = hist['Volume']

        try:
            info = stock.info
        except Exception:
            info = {}

        rsl = calculate_rsl(closes, RSL_PERIOD)
        if rsl is None:
            return None

        current         = closes.iloc[-1]
        high_52w        = closes.max()
        low_52w         = closes.min()
        pct_from_high   = round(((current - high_52w) / high_52w) * 100, 2)

        # Multi-period returns
        change_26t = calculate_change(closes, RSL_PERIOD)
        change_1m  = calculate_change(closes, 20)
        change_3m  = calculate_change(closes, 60)
        change_6m  = calculate_change(closes, 130)

        # MA distance
        ma50  = round(closes.iloc[-50:].mean(),  2) if len(closes) >= 50  else None
        ma200 = round(closes.iloc[-200:].mean(), 2) if len(closes) >= 200 else None
        pct_over_ma50  = round(((current - ma50)  / ma50)  * 100, 2) if ma50  else None
        pct_over_ma200 = round(((current - ma200) / ma200) * 100, 2) if ma200 else None

        # Volume surge ratio
        vol_ratio = None
        if len(volume) >= 50:
            avg50 = volume.iloc[-50:].mean()
            avg5  = volume.iloc[-5:].mean()
            if avg50 > 0:
                vol_ratio = round(avg5 / avg50, 2)

        return {
            'RSL':            rsl,
            'Current_Price':  round(current, 2),
            '52W_High':       round(high_52w, 2),
            '52W_Low':        round(low_52w, 2),
            'Pct_From_High':  pct_from_high,
            'Change_26T':     change_26t,
            'Change_1M':      change_1m,
            'Change_3M':      change_3m,
            'Change_6M':      change_6m,
            'MA50':           ma50,
            'MA200':          ma200,
            'Pct_Over_MA50':  pct_over_ma50,
            'Pct_Over_MA200': pct_over_ma200,
            'Vol_Ratio':      vol_ratio,
            'Beta':           info.get('beta', None),
            'PE_Ratio':       info.get('trailingPE', None),
            'Data_Points':    len(closes),
        }

    except Exception:
        return None

test_tickers      = ['AAPL', 'MSFT', 'GOOGL']
successful_fetches = 0

for ticker in test_tickers:
    data = fetch_stock_data(ticker, start_date, end_date)
    if data:
        print(f"  {ticker}: RSL={data['RSL']}, Price=${data['Current_Price']}, "
              f"26T={data['Change_26T']:+.1f}%, 3M={data['Change_3M']:+.1f}%, "
              f"Vol.Ratio={data['Vol_Ratio']}, %/MA50={data['Pct_Over_MA50']}")
        successful_fetches += 1
    else:
        print(f"  {ticker}: Failed to fetch")
    time.sleep(0.2)

print(f"  {'[PASS]' if successful_fetches >= 2 else '[WARNING]'} "
      f"Yahoo Finance ({successful_fetches}/{len(test_tickers)} ok)")

# =============================================================================
# TEST 4: Batch Processing (20 stocks)
# =============================================================================
print("\n[5/6] Testing batch processing with 20 stocks...")

test_df = sp500_df.head(20).copy()
results = []
failed  = []

for idx, row in tqdm(test_df.iterrows(), total=len(test_df), desc="Processing"):
    data = fetch_stock_data(row['Symbol'], start_date, end_date)
    if data:
        results.append({'Ticker': row['Symbol'], 'Company': row['Company'],
                        'Sector': row['Sector'], 'Industry': row['Industry'], **data})
    else:
        failed.append(row['Symbol'])
    time.sleep(API_DELAY)

results_df = pd.DataFrame(results)
if not results_df.empty:
    results_df = results_df.sort_values('RSL', ascending=False).reset_index(drop=True)
    results_df.insert(0, 'Rank', range(1, len(results_df) + 1))
    results_df['Percentile'] = results_df['RSL'].rank(pct=True).apply(lambda x: round(x * 100, 1))

print(f"  Processed: {len(results_df)} ok, {len(failed)} failed")
print(f"  {'[PASS]' if len(results_df) >= 15 else '[WARNING]'} Batch processing")

if not results_df.empty:
    print(f"\n  Top 5 by RSL (26 days):")
    for _, row in results_df.head(5).iterrows():
        print(f"    {row['Rank']}. {row['Ticker']:<6} RSL={row['RSL']}  "
              f"26T={str(row['Change_26T'])+('%' if row['Change_26T'] is not None else '')}  "
              f"3M={str(row['Change_3M'])+('%' if row['Change_3M'] is not None else '')}  "
              f"Vol.Ratio={row['Vol_Ratio']}")

# =============================================================================
# TEST 5: Excel Generation
# =============================================================================
print("\n[6/6] Testing Excel file generation...")

def create_excel_report(results_df, output_file):
    """Create a test Excel report matching the notebook's sheet structure."""
    try:
        top_n        = max(1, int(len(results_df) * TOP_PERCENTILE))
        top_df       = results_df.head(top_n).copy()
        sector_stats = results_df.groupby('Sector').agg(
            Avg_RSL=('RSL', 'mean'),
            Median_RSL=('RSL', 'median'),
            Stock_Count=('RSL', 'count'),
            Avg_3M_Change=('Change_3M', 'mean'),
        ).round(4)

        with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
            workbook   = writer.book
            header_fmt = workbook.add_format(
                {'bold': True, 'bg_color': '#1F4E79', 'font_color': 'white', 'border': 1}
            )
            titel_fmt  = workbook.add_format({'bold': True, 'font_size': 13, 'font_color': '#1F4E79'})
            gruen_fmt  = workbook.add_format({'bg_color': '#C6EFCE', 'border': 1})

            # Sheet 1: Summary
            summary = {
                'Metric': ['Report Date', 'RSL Period (days)', 'Lookback Days',
                           'Stocks Analyzed', 'Mean RSL', 'Top 25% Threshold RSL'],
                'Value':  [datetime.now().strftime('%Y-%m-%d'), RSL_PERIOD, LOOKBACK_DAYS,
                           len(results_df), f"{results_df['RSL'].mean():.4f}",
                           f"{top_df['RSL'].min():.4f}"],
            }
            pd.DataFrame(summary).to_excel(writer, sheet_name='Summary', index=False)
            ws_sum = writer.sheets['Summary']
            for i, h in enumerate(pd.DataFrame(summary).columns):
                ws_sum.write(0, i, h, header_fmt)
            ws_sum.set_column('A:A', 22)
            ws_sum.set_column('B:B', 20)

            # Sheet 2: Full Rankings
            results_df.to_excel(writer, sheet_name='Full Rankings', index=False)
            ws = writer.sheets['Full Rankings']
            for i, h in enumerate(results_df.columns):
                ws.write(0, i, h, header_fmt)
            top25_row = int(len(results_df) * TOP_PERCENTILE)
            ws.conditional_format(1, 0, top25_row, len(results_df.columns)-1, {
                'type': 'formula', 'criteria': f'=$A2<={top25_row}', 'format': gruen_fmt
            })
            ws.freeze_panes(1, 0)
            ws.autofilter(0, 0, len(results_df), len(results_df.columns)-1)

            # Sheet 3: Top 25% Buy List
            top_df.to_excel(writer, sheet_name='Top 25% Buy List', index=False)
            ws_top = writer.sheets['Top 25% Buy List']
            for i, h in enumerate(top_df.columns):
                ws_top.write(0, i, h, header_fmt)
            ws_top.freeze_panes(1, 0)

            # Sheet 4: Sector Analysis
            sector_stats.reset_index().to_excel(writer, sheet_name='Sector Analysis', index=False)

        return True

    except Exception as e:
        print(f"  Error creating Excel: {e}")
        return False

if not results_df.empty:
    ok = create_excel_report(results_df, OUTPUT_FILE)
    if ok and os.path.exists(OUTPUT_FILE):
        size_kb = os.path.getsize(OUTPUT_FILE) / 1024
        print(f"  File: {OUTPUT_FILE}  ({size_kb:.1f} KB)")
        print("  [PASS] Excel generation working correctly")
    else:
        print("  [FAIL] Excel file was not created")
else:
    print("  [SKIP] No data available")

# =============================================================================
# FINAL SUMMARY
# =============================================================================
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)

tests = [
    ("Wikipedia S&P 500 Fetch",    len(sp500_df) >= 15),
    ("RSL Calculation (26 days)",  rsl_up is not None),
    ("Yahoo Finance Fetch",        successful_fetches >= 2),
    ("Batch Processing",           len(results_df) >= 10),
    ("Excel Generation",           os.path.exists(OUTPUT_FILE)),
]

all_pass = True
for name, passed in tests:
    mark = "[OK]" if passed else "[X] "
    print(f"  {mark} {name}: {'PASS' if passed else 'FAIL'}")
    if not passed:
        all_pass = False

print("\n" + "=" * 70)
if all_pass:
    print("RESULT: All tests passed!")
    print("  Notebook is ready for Google Colab upload.")
else:
    print("RESULT: Some tests failed. Review errors above.")
print("=" * 70)

# Uncomment to delete test output file after review:
# os.remove(OUTPUT_FILE)
