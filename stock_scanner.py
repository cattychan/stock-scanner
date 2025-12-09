#!/usr/bin/env python3
import yfinance as yf
import csv
from datetime import datetime
import os

os.makedirs("stock_data", exist_ok=True)

tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
output_file = f"stock_data/scanner_results_{timestamp}.csv"

results = []

for ticker in tickers:
    try:
        print(f"Scanning {ticker}...", end=" ")
        data = yf.download(ticker, period="3mo", progress=False)
        if data.empty:
            print("No data")
            continue
        
        price = float(data['Close'].iloc[-1])
        print(f"OK ${price:.2f}")
        
        results.append({
            'Ticker': ticker,
            'Price': round(price, 2)
        })
    except:
        print("Error")

if results:
    with open(output_file, 'w') as f:
        w = csv.DictWriter(f, ['Ticker', 'Price'])
        w.writeheader()
        w.writerows(results)
    print(f"\nSaved {len(results)} results to {output_file}")
else:
    print("No results")
