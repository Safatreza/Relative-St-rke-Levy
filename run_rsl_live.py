"""
RSL Live Run — fetches real-time S&P 500 data and produces an Excel report.
Mirrors all cells from rsl_levy_strategy.ipynb.
"""

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

# ── Config ───────────────────────────────────────────────────────────────────
RSL_PERIODE    = 26
MA_50          = 50
MA_200         = 200
RUECKBLICK_TAGE = 400
API_VERZOEGERUNG = 0.15
TOP_PROZENT    = 0.25
ZEITSTEMPEL    = datetime.now().strftime('%Y%m%d_%H%M')
AUSGABE_DATEI  = f"RSL_SP500_Rangliste_{ZEITSTEMPEL}.xlsx"

print("=" * 70)
print("RSL S&P 500 SCREENING — LIVE RUN")
print(f"Datum: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
print("=" * 70)

# ── Helpers ──────────────────────────────────────────────────────────────────
def berechne_rsl(kurse, periode):
    if kurse is None or len(kurse) < periode:
        return None
    try:
        sma = kurse.iloc[-periode:].mean()
        if sma == 0 or pd.isna(sma):
            return None
        return round(kurse.iloc[-1] / sma, 4)
    except Exception:
        return None

def berechne_aenderung(kurse, tage):
    if kurse is None or len(kurse) < tage:
        return None
    try:
        prev = kurse.iloc[-tage]
        if prev == 0:
            return None
        return round(((kurse.iloc[-1] - prev) / prev) * 100, 2)
    except Exception:
        return None

def berechne_ma(kurse, periode):
    if kurse is None or len(kurse) < periode:
        return None
    try:
        return round(kurse.iloc[-periode:].mean(), 2)
    except Exception:
        return None

# ── Ticker fetch ─────────────────────────────────────────────────────────────
def hole_sp500_ticker():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    print("\n[1/4] Lade S&P 500 Ticker von Wikipedia...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        soup  = BeautifulSoup(r.text, 'lxml')
        table = soup.find('table', {'id': 'constituents'})
        if table is None:
            for t in soup.find_all('table', {'class': 'wikitable'}):
                if t.find('th', string=lambda x: x and 'Symbol' in x):
                    table = t; break
        df = pd.read_html(str(table))[0]
        df.columns = df.columns.str.strip()
        result = pd.DataFrame({
            'Symbol':    df['Symbol'].str.strip().str.replace('.', '-', regex=False),
            'Unternehmen': df['Security'].str.strip(),
            'Sektor':    df['GICS Sector'].str.strip() if 'GICS Sector' in df.columns else 'K.A.',
            'Branche':   df['GICS Sub-Industry'].str.strip() if 'GICS Sub-Industry' in df.columns else 'K.A.',
        })
        print(f"  {len(result)} Ticker geladen.")
        return result
    except Exception as e:
        print(f"  Fehler: {e} — Verwende Fallback.")
        fallback = ['AAPL','MSFT','GOOGL','AMZN','NVDA','META','TSLA','BRK-B','UNH','JNJ']
        return pd.DataFrame({'Symbol': fallback, 'Unternehmen': fallback,
                             'Sektor': ['Diverse']*10, 'Branche': ['Diverse']*10})

def hole_spx_kurse(start, end):
    try:
        h = yf.Ticker('^GSPC').history(start=start, end=end, auto_adjust=True)
        return h['Close'] if not h.empty else None
    except Exception:
        return None

# ── Per-stock data ────────────────────────────────────────────────────────────
def hole_aktien_daten(ticker, start, end, spx_kurse=None):
    try:
        hist = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=True)
        if hist.empty or len(hist) < RSL_PERIODE:
            return None

        closes = hist['Close']
        volume = hist['Volume']

        try:
            info = yf.Ticker(ticker).info
        except Exception:
            info = {}

        kurs    = closes.iloc[-1]
        hoch52  = closes.max()
        tief52  = closes.min()

        rsl          = berechne_rsl(closes, RSL_PERIODE)
        aend_26t     = berechne_aenderung(closes, RSL_PERIODE)
        aend_1m      = berechne_aenderung(closes, 20)
        aend_3m      = berechne_aenderung(closes, 60)
        aend_6m      = berechne_aenderung(closes, 130)

        ma50         = berechne_ma(closes, MA_50)
        ma200        = berechne_ma(closes, MA_200)
        pct_ma50     = round(((kurs - ma50)  / ma50)  * 100, 2) if ma50  else None
        pct_ma200    = round(((kurs - ma200) / ma200) * 100, 2) if ma200 else None

        rel_spx = None
        if spx_kurse is not None and len(spx_kurse) >= RSL_PERIODE:
            ap = berechne_aenderung(closes, RSL_PERIODE)
            sp = berechne_aenderung(spx_kurse, RSL_PERIODE)
            if ap is not None and sp is not None:
                rel_spx = round(ap - sp, 2)

        try:
            hoch_idx       = closes.idxmax()
            tage_seit_hoch = (closes.index[-1] - hoch_idx).days
        except Exception:
            tage_seit_hoch = None

        vol_ratio = None
        if len(volume) >= 50:
            avg50 = volume.iloc[-50:].mean()
            avg5  = volume.iloc[-5:].mean()
            if avg50 > 0:
                vol_ratio = round(avg5 / avg50, 2)

        avg_vol = volume.iloc[-20:].mean() if len(volume) >= 20 else volume.mean()

        div_raw = info.get('dividendYield', None)

        return {
            'Aktueller_Kurs':      round(kurs, 2),
            'Marktkapitalisierung': info.get('marketCap', None),
            'RSL':                 rsl,
            'Aenderung_26T':       aend_26t,
            'Aenderung_1M':        aend_1m,
            'Aenderung_3M':        aend_3m,
            'Aenderung_6M':        aend_6m,
            'MA_50':               ma50,
            'MA_200':              ma200,
            'Proz_ueber_MA50':     pct_ma50,
            'Proz_ueber_MA200':    pct_ma200,
            '52W_Hoch':            round(hoch52, 2),
            '52W_Tief':            round(tief52, 2),
            'Proz_vom_Hoch':       round(((kurs - hoch52) / hoch52) * 100, 2),
            'Proz_vom_Tief':       round(((kurs - tief52) / tief52) * 100, 2),
            'Tage_seit_Hoch':      tage_seit_hoch,
            'Volumen_Ratio':       vol_ratio,
            'Durchschn_Volumen':   int(avg_vol) if avg_vol else None,
            'Beta':                info.get('beta', None),
            'KGV':                 info.get('trailingPE', None),
            'Dividendenrendite':   round(div_raw * 100, 2) if div_raw else 0.0,
            'Rel_Staerke_SPX':     rel_spx,
            'Datenpunkte':         len(closes),
        }
    except Exception:
        return None

# ── Batch processing ──────────────────────────────────────────────────────────
def verarbeite_alle(ticker_df, start, end, spx_kurse):
    ergebnisse  = []
    fehlgeschlagen = []
    print(f"\n[3/4] Verarbeite {len(ticker_df)} Aktien (Zeitraum: "
          f"{start.strftime('%d.%m.%Y')} – {end.strftime('%d.%m.%Y')})...")
    print("      Bitte warten, dies dauert 10–15 Minuten...\n")

    for _, zeile in tqdm(ticker_df.iterrows(), total=len(ticker_df), desc="Lade Daten"):
        daten = hole_aktien_daten(zeile['Symbol'], start, end, spx_kurse)
        if daten and daten.get('RSL') is not None:
            ergebnisse.append({'Ticker': zeile['Symbol'], 'Unternehmen': zeile['Unternehmen'],
                               'Sektor': zeile['Sektor'], 'Branche': zeile['Branche'], **daten})
        else:
            fehlgeschlagen.append(zeile['Symbol'])
        time.sleep(API_VERZOEGERUNG)

    df = pd.DataFrame(ergebnisse).sort_values('RSL', ascending=False).reset_index(drop=True)
    df.insert(0, 'Rang', range(1, len(df) + 1))
    df['Perzentil'] = df['RSL'].rank(pct=True).apply(lambda x: round(x * 100, 1))
    print(f"\n  Erfolgreich: {len(df)}  |  Fehlgeschlagen: {len(fehlgeschlagen)}")
    return df, fehlgeschlagen

# ── Excel report ──────────────────────────────────────────────────────────────
def formatiere_mktcap(v):
    if v is None or pd.isna(v): return 'K.A.'
    if v >= 1e12: return f"{v/1e12:.2f} Bio."
    if v >= 1e9:  return f"{v/1e9:.2f} Mrd."
    if v >= 1e6:  return f"{v/1e6:.2f} Mio."
    return f"{v:,.0f}"

def erstelle_excel(df, top, sektor_stats, fehler, datei):
    print(f"\n[4/4] Erstelle Excel: {datei}")
    excel_df = df.copy()
    excel_df['MktCap_Text'] = excel_df['Marktkapitalisierung'].apply(formatiere_mktcap)
    top_ex   = top.copy()
    top_ex['MktCap_Text'] = top_ex['Marktkapitalisierung'].apply(formatiere_mktcap)

    with pd.ExcelWriter(datei, engine='xlsxwriter') as writer:
        wb = writer.book
        hdr = wb.add_format({'bold': True, 'bg_color': '#1F4E79', 'font_color': 'white',
                             'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        ttl = wb.add_format({'bold': True, 'font_size': 14, 'font_color': '#1F4E79'})
        grn = wb.add_format({'bg_color': '#C6EFCE', 'border': 1})

        # Sheet 1 — Vollständige Rangliste
        cols1 = ['Rang','Ticker','Unternehmen','Sektor','Branche','Aktueller_Kurs','MktCap_Text',
                 'RSL','Perzentil','Aenderung_26T','Aenderung_1M','Aenderung_3M','Aenderung_6M',
                 'MA_50','MA_200','Proz_ueber_MA50','Proz_ueber_MA200',
                 'Proz_vom_Hoch','Proz_vom_Tief','Volumen_Ratio','Durchschn_Volumen',
                 'Beta','KGV','Dividendenrendite']
        hdrs1 = ['Rang','Ticker','Unternehmen','Sektor','Branche','Kurs ($)','Marktkapitalisierung',
                 'RSL 26T','Perzentil (%)','Änd. 26T (%)','Änd. 1M (%)','Änd. 3M (%)','Änd. 6M (%)',
                 'MA 50','MA 200','% über MA50','% über MA200',
                 '% vom Hoch','% vom Tief','Vol. Ratio','Ø Volumen',
                 'Beta','KGV','Div. Rendite (%)']
        b1 = excel_df[cols1].copy(); b1.columns = hdrs1
        b1.to_excel(writer, sheet_name='Vollstaendige_Rangliste', index=False)
        ws1 = writer.sheets['Vollstaendige_Rangliste']
        for i, h in enumerate(hdrs1): ws1.write(0, i, h, hdr)
        ws1.set_column('A:A', 6); ws1.set_column('B:B', 8); ws1.set_column('C:C', 26)
        ws1.set_column('D:E', 20); ws1.set_column('F:X', 12)
        top25 = int(len(df) * 0.25)
        ws1.conditional_format(1, 0, top25, len(hdrs1)-1,
                               {'type': 'formula', 'criteria': f'=$A2<={top25}', 'format': grn})
        ws1.freeze_panes(1, 0); ws1.autofilter(0, 0, len(b1), len(hdrs1)-1)

        # Sheet 2 — Top 25% Stars
        cols2 = ['Rang','Ticker','Unternehmen','Sektor','Aktueller_Kurs','MktCap_Text',
                 'RSL','Perzentil','Rel_Staerke_SPX',
                 'Aenderung_26T','Aenderung_1M','Aenderung_3M','Aenderung_6M',
                 'Proz_ueber_MA50','Proz_ueber_MA200','Tage_seit_Hoch','Proz_vom_Hoch',
                 'Volumen_Ratio','KGV','Dividendenrendite']
        hdrs2 = ['Rang','Ticker','Unternehmen','Sektor','Kurs ($)','Marktkapitalisierung',
                 'RSL 26T','Perzentil (%)','Rel. Stärke vs SPX',
                 'Änd. 26T (%)','Änd. 1M (%)','Änd. 3M (%)','Änd. 6M (%)',
                 '% über MA50','% über MA200','Tage seit Hoch','% vom Hoch',
                 'Vol. Ratio','KGV','Div. Rendite (%)']
        b2 = top_ex[cols2].copy(); b2.columns = hdrs2
        b2.to_excel(writer, sheet_name='Top_25%_Stars', index=False)
        ws2 = writer.sheets['Top_25%_Stars']
        for i, h in enumerate(hdrs2): ws2.write(0, i, h, hdr)
        ws2.set_column('A:A', 6); ws2.set_column('B:B', 8); ws2.set_column('C:C', 26)
        ws2.set_column('D:T', 14); ws2.freeze_panes(1, 0)
        ws2.autofilter(0, 0, len(b2), len(hdrs2)-1)

        # Sheet 3 — Sektoranalyse
        beste = df.loc[df.groupby('Sektor')['RSL'].idxmax()].set_index('Sektor')['Ticker'].to_dict()
        sdf   = sektor_stats.reset_index()
        sdf['Beste_Aktie'] = sdf['Sektor'].map(beste)
        sdf.columns = ['Sektor','Ø RSL','Median RSL','Anzahl','Ø 26T Änd. (%)','In Top 25%','Anteil Top 25% (%)','Beste Aktie']
        sdf.to_excel(writer, sheet_name='Sektoranalyse', index=False)
        ws3 = writer.sheets['Sektoranalyse']
        for i, h in enumerate(sdf.columns): ws3.write(0, i, h, hdr)
        ws3.set_column('A:A', 26); ws3.set_column('B:H', 16); ws3.freeze_panes(1, 0)

        # Sheet 4 — Zusammenfassung
        ws4 = wb.add_worksheet('Zusammenfassung')
        ws4.write(0, 0, 'RSL SCREENING — ZUSAMMENFASSUNG', ttl)
        meta = [('Analysedatum', datetime.now().strftime('%d.%m.%Y %H:%M')),
                ('Analysierte Aktien', len(df)), ('Fehlgeschlagen', len(fehler))]
        for i, (k, v) in enumerate(meta):
            ws4.write(2+i, 0, k, hdr); ws4.write(2+i, 1, v)

        ws4.write(7, 0, 'RSL-STATISTIKEN', ttl)
        rsl_stats = [('Durchschnitt', f"{df['RSL'].mean():.4f}"),
                     ('Median',       f"{df['RSL'].median():.4f}"),
                     ('Maximum',      f"{df['RSL'].max():.4f}  ({df.iloc[0]['Ticker']})"),
                     ('Minimum',      f"{df['RSL'].min():.4f}  ({df.iloc[-1]['Ticker']})"),
                     ('Std.abw.',     f"{df['RSL'].std():.4f}"),
                     ('Bullisch (>1)',f"{(df['RSL']>1).sum()} Aktien"),
                     ('Bärisch (≤1)', f"{(df['RSL']<=1).sum()} Aktien")]
        for i, (k, v) in enumerate(rsl_stats):
            ws4.write(9+i, 0, k, hdr); ws4.write(9+i, 1, v)

        ws4.write(18, 0, 'Ø RENDITEN (alle Aktien)', ttl)
        for i, (lbl, col) in enumerate([('26 Tage','Aenderung_26T'),('1 Monat','Aenderung_1M'),
                                         ('3 Monate','Aenderung_3M'),('6 Monate','Aenderung_6M')]):
            ws4.write(20+i, 0, lbl, hdr)
            ws4.write(20+i, 1, f"{df[col].dropna().mean():+.2f}%")

        ws4.write(26, 0, 'TOP 10', ttl)
        for j, h in enumerate(['Rang','Ticker','RSL','Änd. 26T','Änd. 3M','Vol. Ratio']):
            ws4.write(28, j, h, hdr)
        for i, (_, r) in enumerate(df.head(10).iterrows()):
            for j, v in enumerate([r['Rang'], r['Ticker'], r['RSL'], r['Aenderung_26T'], r['Aenderung_3M'], r['Volumen_Ratio']]):
                ws4.write(29+i, j, v)

        ws4.write(26, 7, 'BOTTOM 10', ttl)
        for j, h in enumerate(['Rang','Ticker','RSL','Änd. 26T','Änd. 3M','Vol. Ratio']):
            ws4.write(28, 7+j, h, hdr)
        for i, (_, r) in enumerate(df.tail(10).iterrows()):
            for j, v in enumerate([r['Rang'], r['Ticker'], r['RSL'], r['Aenderung_26T'], r['Aenderung_3M'], r['Volumen_Ratio']]):
                ws4.write(29+i, 7+j, v)

        ws4.set_column('A:A', 22); ws4.set_column('B:M', 14)

        # Sheet 5 — Methodik
        ws5 = wb.add_worksheet('Methodik')
        lines = [
            ('RSL SCREENING — METHODIK', True),
            ('', False),
            ('Formel:  RSL = Aktueller Kurs / SMA(Kurs, 26 Handelstage)', False),
            ('Quelle:  Robert Levy, 1967', False),
            ('', False),
            ('KENNZAHLEN', True),
            ('RSL 26T       — Momentum-Indikator (>1 bullisch, <1 bärisch)', False),
            ('Änd. 1M/3M/6M — Multi-Perioden-Renditen zur Trendbestätigung', False),
            ('Vol. Ratio    — 5-Tage-Volumen / 50-Tage-Volumen (>1,5 = Surge)', False),
            ('% über MA50/200 — Abstand vom gleitenden Durchschnitt', False),
            ('', False),
            ('DATEN', True),
            ('Ticker:  Wikipedia — List of S&P 500 companies', False),
            ('Kurse:   Yahoo Finance (yfinance)', False),
            ('Index:   S&P 500 (^GSPC)', False),
            ('', False),
            ('HAFTUNGSAUSSCHLUSS', True),
            ('Nur für Bildungs- und Forschungszwecke. Keine Anlageberatung.', False),
            (f'Erstellt: {datetime.now().strftime("%d.%m.%Y %H:%M:%S")}', False),
        ]
        for i, (txt, bold) in enumerate(lines):
            ws5.write(i, 0, txt, ttl if (bold and txt) else None)
        ws5.set_column('A:A', 80)

    size_kb = os.path.getsize(datei) / 1024
    print(f"  Gespeichert: {datei}  ({size_kb:.0f} KB)")
    return datei

# ── Main ──────────────────────────────────────────────────────────────────────
sp500_df = hole_sp500_ticker()

end_datum   = datetime.now()
start_datum = end_datum - timedelta(days=RUECKBLICK_TAGE)

print("\n[2/4] Lade S&P 500 Indexdaten...")
spx_kurse = hole_spx_kurse(start_datum, end_datum)
print(f"  S&P 500: {len(spx_kurse) if spx_kurse is not None else 0} Datenpunkte geladen.")

ergebnis_df, fehlgeschlagene = verarbeite_alle(sp500_df, start_datum, end_datum, spx_kurse)

# Sektoranalyse
top_schwelle  = int(len(ergebnis_df) * TOP_PROZENT)
top_performer = ergebnis_df.head(top_schwelle).copy()

sektor_stats = ergebnis_df.groupby('Sektor').agg(
    RSL_mean=('RSL', 'mean'), RSL_median=('RSL', 'median'),
    RSL_count=('RSL', 'count'), Aend_26T_mean=('Aenderung_26T', 'mean')
).round(4)
sektor_stats.columns = ['Durchschn_RSL', 'Median_RSL', 'Anzahl', 'Durchschn_26T_Aend']
sektor_stats = sektor_stats.sort_values('Durchschn_RSL', ascending=False)
sektor_top25 = top_performer.groupby('Sektor').size().reindex(sektor_stats.index, fill_value=0)
sektor_stats['In_Top_25%']    = sektor_top25
sektor_stats['Anteil_Top25']  = (sektor_stats['In_Top_25%'] / sektor_stats['Anzahl'] * 100).round(1)

# Print summary
print("\n" + "=" * 70)
print("ERGEBNIS")
print("=" * 70)
print(f"Analysierte Aktien : {len(ergebnis_df)}")
print(f"Top-Performer (25%): {len(top_performer)}")
print(f"\nRSL-Statistiken:")
print(f"  Ø      : {ergebnis_df['RSL'].mean():.4f}")
print(f"  Median : {ergebnis_df['RSL'].median():.4f}")
print(f"  Max    : {ergebnis_df['RSL'].max():.4f}  ({ergebnis_df.iloc[0]['Ticker']})")
print(f"  Min    : {ergebnis_df['RSL'].min():.4f}  ({ergebnis_df.iloc[-1]['Ticker']})")
print(f"\nDurchschnittliche Renditen:")
for col, lbl in [('Aenderung_26T','26 Tage'),('Aenderung_1M','1 Monat'),
                 ('Aenderung_3M','3 Monate'),('Aenderung_6M','6 Monate')]:
    print(f"  {lbl:<10}: {ergebnis_df[col].dropna().mean():+.2f}%")

print(f"\nTop 10 nach RSL:")
for _, r in ergebnis_df.head(10).iterrows():
    print(f"  {r['Rang']:>3}. {r['Ticker']:<6}  RSL={r['RSL']}  26T={r['Aenderung_26T']:+.1f}%  "
          f"3M={str(r['Aenderung_3M'])+('%') if r['Aenderung_3M'] is not None else 'N/A':>7}  "
          f"Vol.Ratio={r['Volumen_Ratio']}")

# Excel
erstelle_excel(ergebnis_df, top_performer, sektor_stats, fehlgeschlagene, AUSGABE_DATEI)

# ── JSON export for website ───────────────────────────────────────────────────
def erstelle_json(df, sektor_stats, fehler):
    import json, math

    def safe(v):
        if v is None: return None
        try:
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)): return None
            return v
        except Exception:
            return None

    now = datetime.now()
    top25n = math.ceil(len(df) * TOP_PROZENT)

    # Best ticker per sector
    beste = df.loc[df.groupby('Sektor')['RSL'].idxmax()].set_index('Sektor')['Ticker'].to_dict()
    top25_by_sector = df.head(top25n).groupby('Sektor').size().to_dict()

    output = {
        "metadata": {
            "updated":       now.isoformat(timespec='seconds'),
            "updated_display": now.strftime('%d.%m.%Y %H:%M'),
            "total_analyzed": len(df),
            "failed":         len(fehler),
            "rsl_period_days": RSL_PERIODE,
        },
        "stats": {
            "avg_rsl":      round(float(df['RSL'].mean()), 4),
            "median_rsl":   round(float(df['RSL'].median()), 4),
            "max_rsl":      round(float(df['RSL'].max()), 4),
            "max_ticker":   str(df.iloc[0]['Ticker']),
            "min_rsl":      round(float(df['RSL'].min()), 4),
            "min_ticker":   str(df.iloc[-1]['Ticker']),
            "bullish_count": int((df['RSL'] > 1).sum()),
            "bearish_count": int((df['RSL'] <= 1).sum()),
            "returns_avg": {
                "26t": safe(round(float(df['Aenderung_26T'].dropna().mean()), 2)),
                "1m":  safe(round(float(df['Aenderung_1M'].dropna().mean()),  2)),
                "3m":  safe(round(float(df['Aenderung_3M'].dropna().mean()),  2)),
                "6m":  safe(round(float(df['Aenderung_6M'].dropna().mean()),  2)),
            }
        },
        "rankings": [
            {
                "rank":          int(r['Rang']),
                "ticker":        str(r['Ticker']),
                "company":       str(r['Unternehmen']),
                "sector":        str(r['Sektor']),
                "rsl":           safe(r['RSL']),
                "percentile":    safe(r['Perzentil']),
                "price":         safe(r['Aktueller_Kurs']),
                "change_26t":    safe(r['Aenderung_26T']),
                "change_1m":     safe(r['Aenderung_1M']),
                "change_3m":     safe(r['Aenderung_3M']),
                "change_6m":     safe(r['Aenderung_6M']),
                "pct_over_ma50":  safe(r['Proz_ueber_MA50']),
                "pct_over_ma200": safe(r['Proz_ueber_MA200']),
                "pct_from_high":  safe(r['Proz_vom_Hoch']),
                "vol_ratio":     safe(r['Volumen_Ratio']),
                "rel_vs_spx":    safe(r['Rel_Staerke_SPX']),
                "beta":          safe(r['Beta']),
                "pe_ratio":      safe(r['KGV']),
                "div_yield":     safe(r['Dividendenrendite']),
            }
            for _, r in df.iterrows()
        ],
        "sectors": [
            {
                "sector":         idx,
                "avg_rsl":        round(float(row['Durchschn_RSL']), 4),
                "median_rsl":     round(float(row['Median_RSL']), 4),
                "count":          int(row['Anzahl']),
                "avg_change_26t": safe(round(float(row['Durchschn_26T_Aend']), 2)),
                "in_top25":       int(top25_by_sector.get(idx, 0)),
                "top25_pct":      round(top25_by_sector.get(idx, 0) / int(row['Anzahl']) * 100, 1),
                "best_ticker":    beste.get(idx, ''),
            }
            for idx, row in sektor_stats.iterrows()
        ]
    }

    json_path = os.path.join('web', 'data', 'rsl_rankings.json')
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    size_kb = os.path.getsize(json_path) / 1024
    print(f"  JSON gespeichert: {json_path}  ({size_kb:.0f} KB)")

erstelle_json(ergebnis_df, sektor_stats, fehlgeschlagene)
print(f"\nFertig! {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
