# RSL (Relative Stärke Levy) Aktien-Screening-Strategie

Ein Python-basiertes Aktien-Screening-Tool zur Bewertung und Rangfolge von S&P 500 Unternehmen nach der Relative Stärke Levy (RSL) Momentum-Strategie.

## Überblick

Der **Relative Stärke Levy (RSL)** Indikator wurde 1967 von Robert Levy entwickelt. Er misst das Momentum einer Aktie, indem er den aktuellen Kurs mit dem historischen Durchschnitt vergleicht.

### Formel

```
RSL = Aktueller Kurs / SMA(Kurs, N Perioden)
```

Wobei:
- **Aktueller Kurs** = Letzter Schlusskurs
- **SMA** = Einfacher gleitender Durchschnitt über N Perioden
- **N** = Typischerweise 130 Handelstage (~27 Wochen)

### Interpretation

| RSL-Wert | Bedeutung |
|----------|-----------|
| RSL > 1,0 | Aktie handelt über Durchschnitt (bullisches Momentum) |
| RSL < 1,0 | Aktie handelt unter Durchschnitt (bärisches Momentum) |
| Höherer RSL | Stärkere relative Stärke |

## Schnellstart

### Option 1: Google Colab (Empfohlen)

1. Öffnen Sie [Google Colab](https://colab.research.google.com/)
2. Laden Sie `rsl_levy_strategy.ipynb` hoch
3. Führen Sie alle Zellen aus
4. Laden Sie den generierten Excel-Bericht herunter

### Option 2: Lokales Jupyter

```bash
# Abhängigkeiten installieren
pip install yfinance pandas openpyxl beautifulsoup4 lxml tqdm xlsxwriter

# Notebook öffnen
jupyter notebook rsl_levy_strategy.ipynb
```

## Funktionen

- Abruf aller S&P 500 Ticker von Wikipedia
- Download der Kursdaten von Yahoo Finance
- Berechnung des RSL für jede Aktie
- Ranking der Aktien nach Momentum-Stärke
- Erstellung eines professionellen Excel-Berichts mit:
  - Zusammenfassungsstatistiken
  - Vollständiger Rangliste mit bedingter Formatierung
  - Obere 25% Kaufkandidaten
  - Sektoranalyse

## Konfiguration

Anpassbare Parameter im Notebook:

| Parameter | Standard | Beschreibung |
|-----------|----------|--------------|
| `RSL_PERIODE` | 130 | Handelstage für SMA (~27 Wochen) |
| `RUECKBLICK_TAGE` | 365 | Tage historischer Daten |
| `TOP_PROZENT` | 0.25 | Schwellenwert für Top-Performer |
| `API_VERZOEGERUNG` | 0.1 | Sekunden zwischen API-Aufrufen |

## Ausgabe

Das Notebook generiert eine Excel-Datei mit mehreren Blättern:

1. **Zusammenfassung** - Wichtige Statistiken und Metadaten
2. **Vollstaendige_Rangliste** - Alle Aktien nach RSL sortiert
3. **Obere_25%_Kaufliste** - Aktien mit stärkstem Momentum
4. **Sektoranalyse** - Durchschnittlicher RSL nach Sektor
5. **Fehlgeschlagene_Ticker** - Aktien, die nicht verarbeitet werden konnten

## Strategie-Richtlinien

1. **Kaufkandidaten**: Konzentrieren Sie sich auf die oberen 25% RSL-Aktien
2. **Vermeiden**: Untere 25% (schwächstes Momentum)
3. **Rebalancing**: Monatlich oder vierteljährlich
4. **Diversifikation**: Über verschiedene Sektoren verteilen

## Haftungsausschluss

Dieses Tool dient ausschließlich Bildungs- und Forschungszwecken. Vergangenes Momentum garantiert keine zukünftige Performance. Führen Sie immer Ihre eigene Recherche durch und ziehen Sie die Beratung eines Finanzberaters in Betracht, bevor Sie Investitionsentscheidungen treffen.

## Lizenz

MIT-Lizenz
