#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==================== 配置 ====================
SCAN_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "AVGO", "QCOM", "AMD", "ADBE", "CRM", "NFLX", "INTC"
    # ... 您可以加入更多股票代碼
]

SMA_PERIOD_SHORT = 20
SMA_PERIOD_LONG = 50
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
VOLUME_MULTIPLIER = 1.2
OUTPUT_FOLDER = "stock_data"

# ==================== 技術指標計算 ====================
def calculate_sma(data, period):
    return data['Close'].rolling(window=period).mean()

def calculate_rsi(data, period=14):
    delta = data['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(data):
    ema_fast = data['Close'].ewm(span=12, adjust=False).mean()
    ema_slow = data['Close'].ewm(span=26, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

# ==================== 掃描單一股票 ====================
def scan_single_stock(ticker):
    try:
        data = yf.download(ticker, period='3mo', progress=False)
        if data.empty or len(data) < 30:
            return None
        
        data = data.sort_index()
        sma20 = calculate_sma(data, SMA_PERIOD_SHORT)
        sma50 = calculate_sma(data, SMA_PERIOD_LONG)
        rsi = calculate_rsi(data, RSI_PERIOD)
        macd_line, signal_line, histogram = calculate_macd(data)
        
        current_price = float(data['Close'].iloc[-1])
        current_volume = float(data['Volume'].iloc[-1])
        prev_price = float(data['Close'].iloc[-2])
        
        current_sma20 = float(sma20.iloc[-1]) if not pd.isna(sma20.iloc[-1]) else None
        current_sma50 = float(sma50.iloc[-1]) if not pd.isna(sma50.iloc[-1]) else None
        prev_sma20 = float(sma20.iloc[-2]) if not pd.isna(sma20.iloc[-2]) else None
        prev_sma50 = float(sma50.iloc[-2]) if not pd.isna(sma50.iloc[-2]) else None
        
        current_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None
        current_macd_hist = float(histogram.iloc[-1]) if not pd.isna(histogram.iloc[-1]) else None
        prev_macd_hist = float(histogram.iloc[-2]) if not pd.isna(histogram.iloc[-2]) else None
        
        avg_volume = float(data['Volume'].tail(20).mean())
        price_change_pct = ((current_price - prev_price) / prev_price * 100) if prev_price != 0 else 0
        
        data_52w = yf.download(ticker, period='1y', progress=False)
        high_52w = float(data_52w['High'].max())
        low_52w = float(data_52w['Low'].min())
        
        signals = []
        if current_sma20 and current_sma50 and prev_sma20 and prev_sma50:
            if current_sma20 > current_sma50 and prev_sma20 <= prev_sma50:
                signals.append("黃金交叉")
        
        if current_rsi:
            if current_rsi < RSI_OVERSOLD:
                signals.append("RSI超賣")
            elif current_rsi > RSI_OVERBOUGHT:
                signals.append("RSI超買")
        
        if current_macd_hist and prev_macd_hist:
            if current_macd_hist > 0 and prev_macd_hist <= 0:
                signals.append("MACD翻正")
        
        if current_price >= high_52w * 0.98:
            signals.append("接近52週高點")
        
        if current_volume > avg_volume * VOLUME_MULTIPLIER:
            signals.append("成交量激增")
        
        if len(signals) >= 1:
            return {
                "Ticker": ticker,
                "CurrentPrice": round(current_price, 2),
                "Change%": round(price_change_pct, 2),
                "SMA20": round(current_sma20, 2) if current_sma20 else "N/A",
                "SMA50": round(current_sma50, 2) if current_sma50 else "N/A",
                "RSI": round(current_rsi, 2) if current_rsi else "N/A",
                "MACDHist": round(current_macd_hist, 4) if current_macd_hist else "N/A",
                "VolumeSurge": "Yes" if "成交量激增" in signals else "No",
                "52WHigh": round(high_52w, 2),
                "52WLow": round(low_52w, 2),
                "Signals": ", ".join(signals),
                "SignalCount": len(signals),
                "ScanTime": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        return None
    except Exception as e:
        print(f"❌ {ticker} - {str(e)}")
        return None

# ==================== 上傳到 Google Sheets ====================
def upload_to_google_sheets(df):
    try:
        # 讀取環境變數
        creds_json = os.environ.get('GOOGLE_CREDENTIALS')
        sheet_id = os.environ.get('GOOGLE_SHEET_ID')
        
        if not creds_json or not sheet_id:
            print("⚠️ 缺少 Google Sheets 憑證或 Sheet ID")
            return False
        
        # 解析 JSON 憑證
        creds_dict = json.loads(creds_json)
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # 打開 Google Sheet
        sheet = client.open_by_key(sheet_id).sheet1
        
        # 清空舊數據（保留標題）
        sheet.clear()
        
        # 寫入新數據
        sheet.update([df.columns.values.tolist()] + df.values.tolist())
        
        print(f"✅ 成功上傳 {len(df)} 筆數據到 Google Sheets")
        return True
        
    except Exception as e:
        print(f"❌ 上傳到 Google Sheets 失敗：{str(e)}")
        return False

# ==================== 主程式 ====================
def main():
    print(f"\n{'='*60}")
    print(f"🔍 開始掃描 {len(SCAN_TICKERS)} 支股票")
    print(f"📅 掃描時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # 建立輸出資料夾
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    
    results = []
    for idx, ticker in enumerate(SCAN_TICKERS, 1):
        print(f"[{idx}/{len(SCAN_TICKERS)}] {ticker}...", end=" ")
        result = scan_single_stock(ticker)
        if result:
            results.append(result)
            print("✅")
        else:
            print("⏭️")
    
    if results:
        df = pd.DataFrame(results)
        df = df.sort_values('SignalCount', ascending=False)
        
        # 儲存 CSV
        output_file = os.path.join(OUTPUT_FOLDER, f"scanner_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n✅ CSV 已儲存：{output_file}")
        
        # 上傳到 Google Sheets
        upload_to_google_sheets(df)
        
        # 顯示 TOP 10
        print(f"\n📊 TOP 10 機會股：")
        print(df[['Ticker', 'CurrentPrice', 'Change%', 'SignalCount', 'Signals']].head(10).to_string(index=False))
        
    else:
        print("\n⚠️ 沒有找到符合條件的股票")
    
    print(f"\n{'='*60}")

if __name__ == "__main__":
    main()
