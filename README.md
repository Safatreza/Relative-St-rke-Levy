# RSL (Relative Stärke Levy) Stock Screening Strategy

A Python-based stock screening tool that ranks S&P 500 companies using the Relative Strength Levy (RSL) momentum strategy.

## Overview

The **Relative Strength Levy (RSL)** indicator was developed by Robert Levy in 1967. It measures a stock's momentum by comparing its current price to its historical average.

### Formula

```
RSL = Current Price / SMA(Price, N periods)
```

Where:
- **Current Price** = Latest closing price
- **SMA** = Simple Moving Average over N periods
- **N** = Typically 130 trading days (~27 weeks)

### Interpretation

| RSL Value | Meaning |
|-----------|---------|
| RSL > 1.0 | Stock trading above average (bullish momentum) |
| RSL < 1.0 | Stock trading below average (bearish momentum) |
| Higher RSL | Stronger relative strength |

## Quick Start

### Option 1: Google Colab (Recommended)

1. Open [Google Colab](https://colab.research.google.com/)
2. Upload `rsl_levy_strategy.ipynb`
3. Run all cells
4. Download the generated Excel report

### Option 2: Local Jupyter

```bash
# Install dependencies
pip install yfinance pandas openpyxl beautifulsoup4 lxml tqdm xlsxwriter

# Open notebook
jupyter notebook rsl_levy_strategy.ipynb
```

## Features

- Fetches all S&P 500 tickers from Wikipedia
- Downloads price data from Yahoo Finance
- Calculates RSL for each stock
- Ranks stocks by momentum strength
- Generates professional Excel report with:
  - Summary statistics
  - Full rankings with conditional formatting
  - Top 25% buy candidates
  - Sector analysis

## Configuration

Adjustable parameters in the notebook:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `RSL_PERIOD` | 130 | Trading days for SMA (~27 weeks) |
| `LOOKBACK_DAYS` | 365 | Days of historical data |
| `TOP_PERCENTILE` | 0.25 | Top performers threshold |
| `API_DELAY` | 0.1 | Seconds between API calls |

## Output

The notebook generates an Excel file with multiple sheets:

1. **Summary** - Key statistics and metadata
2. **Full Rankings** - All stocks sorted by RSL
3. **Top 25% Buy List** - Strongest momentum stocks
4. **Sector Analysis** - Average RSL by sector
5. **Failed Tickers** - Stocks that couldn't be processed

## Strategy Guidelines

1. **Buy Candidates**: Focus on top 25% RSL stocks
2. **Avoid**: Bottom 25% (weakest momentum)
3. **Rebalance**: Monthly or quarterly
4. **Diversification**: Spread across sectors

## Disclaimer

This tool is for educational and research purposes only. Past momentum does not guarantee future performance. Always conduct your own research and consider consulting a financial advisor before making investment decisions.

## License

MIT License
