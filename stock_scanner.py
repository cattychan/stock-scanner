#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票掃描器 v2.2 - 調試版本
只輸出前 10 支股票（用於測試）
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import os
from pathlib import Path

# ==================== 配置區 ====================

SCAN_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "QCOM", "AMD",
]

SMA_PERIOD_SHORT = 20
SMA_PERIOD_LONG = 50
RSI_PERIOD = 14

OUTPUT_FOLDER = "stock_data"
OUTPUT_FILE = os.path.join(OUTPUT_FOLDER, f"scanner_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

# ==================== 輔助函數 ====================

def create_output_folder():
    Path(OUTPUT_FOLDER).mkdir(exist_ok=True)
    print(f"✅ 創建資料夾: {OUTPUT_FOLDER}")

def calculate_sma(data, period):
    return data['Close'].rolling(window=period).mean()

def calculate_rsi(data, period=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(data, fast=12, slow=26, signal=9):
    ema_fast = data['Close'].ewm(span=fast, adjust=False).mean()
    ema_slow = data['Close'].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def scan_single_stock(ticker):
    try:
        print(f"  下載 {ticker} 數據...", end="")
        data = yf.download(ticker, period="3mo", progress=False)
        
        if data.empty or len(data) < 30:
            print(f" ❌ 數據不足")
            return None
        
        print(f" ✅ 成功", end="")
        data = data.sort_index()
        
        # 計算指標
        sma_20 = calculate_sma(data, SMA_PERIOD_SHORT)
        sma_50 = calculate_sma(data, SMA_PERIOD_LONG)
        rsi = calculate_rsi(data, RSI_PERIOD)
        macd_line, signal_line, histogram = calculate_macd(data)
        
        # 提取最新值
        current_price = float(data['Close'].iloc[-1])
        current_volume = float(data['Volume'].iloc[-1])
        prev_price = float(data['Close'].iloc[-2])
        
        current_sma_20 = float(sma_20.iloc[-1]) if not pd.isna(sma_20.iloc[-1]) else None
        current_sma_50 = float(sma_50.iloc[-1]) if not pd.isna(sma_50.iloc[-1]) else None
        
        current_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None
        current_macd_hist = float(histogram.iloc[-1]) if not pd.isna(histogram.iloc[-1]) else None
        
        price_change_pct = ((current_price - prev_price) / prev_price * 100) if prev_price != 0 else 0
        
        # 52 週高低點
        data_52w = yf.download(ticker, period="1y", progress=False)
        high_52w = float(data_52w['High'].max())
        low_52w = float(data_52w['Low'].min())
        
        print(f" | 價格: ${current_price:.2f} | RSI: {current_rsi:.1f if current_rsi else 'N/A'}")
        
        # 調試模式：輸出所有股票（不進行篩選）
        return {
            "Ticker": ticker,
            "Current_Price": round(current_price, 2),
            "Change_%": round(price_change_pct, 2),
            "SMA_20": round(current_sma_20, 2) if current_sma_20 else "N/A",
            "SMA_50": round(current_sma_50, 2) if current_sma_50 else "N/A",
            "RSI": round(current_rsi, 2) if current_rsi else "N/A",
            "MACD_Histogram": round(current_macd_hist, 4) if current_macd_hist else "N/A",
            "52W_High": round(high_52w, 2),
            "52W_Low": round(low_52w, 2),
            "Scan_Time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        print(f" ❌ 錯誤: {str(e)}")
        return None

# ==================== 主程序 ====================

def main():
    print("\n" + "="*60)
    print("🚀 股票掃描器 v2.2 - 調試版本")
    print("="*60)
    print(f"掃描股票數量: {len(SCAN_TICKERS)}")
    print(f"掃描時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")
    
    create_output_folder()
    
    results = []
    
    for idx, ticker in enumerate(SCAN_TICKERS, 1):
        print(f"[{idx}/{len(SCAN_TICKERS)}] 掃描 {ticker}...", end=" ")
        result = scan_single_stock(ticker)
        
        if result:
            results.append(result)
    
    # 保存結果到 CSV
    print(f"\n{'='*60}")
    if results:
        df = pd.DataFrame(results)
        df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
        
        print(f"✅ 掃描完成！")
        print(f"📊 輸出了 {len(results)} 支股票")
        print(f"📁 結果已保存到: {OUTPUT_FILE}")
        print(f"{'='*60}\n")
        
        print("📋 輸出的股票列表:")
        print(df[['Ticker', 'Current_Price', 'Change_%', 'RSI', 'Scan_Time']].to_string(index=False))
        
        # 驗證文件確實被創建
        if os.path.exists(OUTPUT_FILE):
            file_size = os.path.getsize(OUTPUT_FILE)
            print(f"\n✅ 文件驗證: {OUTPUT_FILE} ({file_size} bytes)")
        else:
            print(f"\n❌ 文件未找到: {OUTPUT_FILE}")
    else:
        print(f"❌ 沒有輸出任何股票")
    
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
