#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票掃描器 v2.3 - 超簡單版本
只下載數據，無複雜計算
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
import os
from pathlib import Path

# ==================== 配置區 ====================

SCAN_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "QCOM", "AMD",
]

OUTPUT_FOLDER = "stock_data"
OUTPUT_FILE = os.path.join(OUTPUT_FOLDER, f"scanner_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

# ==================== 主程序 ====================

def main():
    print("\n" + "="*60)
    print("🚀 股票掃描器 v2.3 - 超簡單版本")
    print("="*60)
    print(f"掃描股票數量: {len(SCAN_TICKERS)}")
    print(f"掃描時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")
    
    # 創建資料夾
    Path(OUTPUT_FOLDER).mkdir(exist_ok=True)
    print(f"✅ 創建資料夾: {OUTPUT_FOLDER}\n")
    
    results = []
    
    for idx, ticker in enumerate(SCAN_TICKERS, 1):
        try:
            print(f"[{idx}/{len(SCAN_TICKERS)}] {ticker}...", end=" ")
            
            # 下載數據
            data = yf.download(ticker, period="3mo", progress=False)
            
            if data.empty or len(data) < 5:
                print("❌ 無數據")
                continue
            
            # 提取簡單數據
            current_price = float(data['Close'].iloc[-1])
            prev_close = float(data['Close'].iloc[-2])
            current_volume = float(data['Volume'].iloc[-1])
            
            # 計算漲跌幅
            change_pct = ((current_price - prev_close) / prev_close * 100)
            
            # 52 週高低
            year_data = yf.download(ticker, period="1y", progress=False)
            high_52w = float(year_data['High'].max())
            low_52w = float(year_data['Low'].min())
            
            print(f"✅ ${current_price:.2f}")
            
            results.append({
                "Ticker": ticker,
                "Price": round(current_price, 2),
                "Change_%": round(change_pct, 2),
