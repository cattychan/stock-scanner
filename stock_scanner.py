#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票掃描器 v2.4 - 極簡版本
無任何外部庫依賴（除了 yfinance）
直接寫 CSV 檔案
"""

import yfinance as yf
from datetime import datetime
import os
from pathlib import Path
import csv

OUTPUT_FOLDER = "stock_data"

SCAN_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "QCOM", "AMD",
]

def main():
    print("\n" + "="*60)
    print("🚀 股票掃描器 v2.4 - 極簡版本")
    print("="*60)
    print(f"掃描股票數量: {len(SCAN_TICKERS)}")
    print(f"掃描時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")
    
    # 創建資料夾
    Path(OUTPUT_FOLDER).mkdir(exist_ok=True)
    print(f"✅ 創建資料夾: {OUTPUT_FOLDER}\n")
    
    # 生成 CSV 檔案名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(OUTPUT_FOLDER, f"scanner_results_{timestamp}.csv")
    
    results = []
    success_count = 0
    fail_count = 0
    
    for idx, ticker in enumerate(SCAN_TICKERS, 1):
        try:
            print(f"[{idx}/{len(SCAN_TICKERS)}] {ticker}...", end=" ")
            
            # 下載數據
            data = yf.download(ticker, period="3mo", progress=False)
            
            if data is None or len(data) == 0:
                print("❌ 無數據")
                fail_count += 1
                continue
            
            # 獲取最後一行數據
            last_row = data.iloc[-1]
            prev_row = data.iloc[-2] if len(data) > 1 else last_row
            
            current_price = float(last_row['Close'])
            prev_close = float(prev_row['Close'])
            current_volume = int(last_row['Volume'])
            
            # 計算漲跌幅
            if prev_close != 0:
                change_pct = ((current_price - prev_close) / prev_close) * 100
            else:
                change_pct = 0
            
            # 52 週高低
            year_data = yf.download(ticker, period="1y", progress=False)
            if year_data is not None and len(year_data) > 0:
                high_52w = float(year_data['High'].
