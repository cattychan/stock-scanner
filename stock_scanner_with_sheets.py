#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
股票掃描器 - 終極修復版
完全避開 pandas Series 判斷問題
"""

import yfinance as yf
import pandas as pd
import csv
from datetime import datetime
import os
from pathlib import Path
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import warnings
warnings.filterwarnings('ignore')

OUTPUT_FOLDER = "stock_data"
MIN_SIGNALS = 2

SCAN_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JNJ", "V",
    "WMT", "JPM", "PG", "MA", "HD", "DIS", "MCD", "ADBE", "CRM", "NFLX",
    "INTC", "CSCO", "IBM", "ORCL", "MU", "PYPL", "SHOP", "ASML", "AMD",
    "QCOM", "AVGO", "LRCX", "KLAC", "MCHP", "AMAT", "SNPS", "CDNS", "ADSK",
    "NOW", "ADP"
]

def scan_single_stock(ticker):
    """掃描單支股票 - 終極修復版"""
    try:
        # 下載數據
        data = yf.download(ticker, period="3mo", progress=False, auto_adjust=True)
        
        if data.empty or len(data) < 50:
            print("⏭️ 數據不足")
            return None
        
        # ===== 提取數據並立即轉為 Python float =====
        last_close = float(data['Close'].iloc[-1])
        prev_close = float(data['Close'].iloc[-2])
        current_volume = float(data['Volume'].iloc[-1])
        
        # 計算平均成交量
        vol_series = data['Volume'].tail(20)
        avg_volume_20 = float(vol_series.mean())
        
        # 計算 SMA
        close_series = data['Close']
        sma_20 = float(close_series.rolling(window=20).mean().iloc[-1])
        sma_50 = float(close_series.rolling(window=50).mean().iloc[-1])
        prev_sma_20 = float(close_series.rolling(window=20).mean().iloc[-2])
        prev_sma_50 = float(close_series.rolling(window=50).mean().iloc[-2])
        
        # 計算 RSI
        delta = close_series.diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
        rs = gain / loss
        rsi_series = 100 - (100 / (1 + rs))
        current_rsi = float(rsi_series.iloc[-1])
        
        # 計算 MACD
        ema_12 = close_series.ewm(span=12, adjust=False).mean()
        ema_26 = close_series.ewm(span=26, adjust=False).mean()
        macd_line = ema_12 - ema_26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - signal_line
        current_macd = float(macd_hist.iloc[-1])
        prev_macd = float(macd_hist.iloc[-2])
        
        # 計算布林帶
        sma_bb = close_series.rolling(window=20).mean()
        std_bb = close_series.rolling(window=20).std()
        upper_band = sma_bb + (std_bb * 2)
        lower_band = sma_bb - (std_bb * 2)
        bb_upper = float(upper_band.iloc[-1])
        bb_lower = float(lower_band.iloc[-1])
        bb_middle = float(sma_bb.iloc[-1])
        bb_width = ((bb_upper - bb_lower) / bb_middle * 100)
        
        # 計算 VWAP
        typical_price = (data['High'] + data['Low'] + data['Close']) / 3
        vwap = (typical_price * data['Volume']).cumsum() / data['Volume'].cumsum()
        current_vwap = float(vwap.iloc[-1])
        
        # 獲取 52 週數據
        year_data = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
        if not year_data.empty:
            high_52w = float(year_data['High'].max())
            low_52w = float(year_data['Low'].min())
            high_20d = float(data['High'].tail(20).max())
        else:
            high_52w = last_close
            low_52w = last_close
            high_20d = last_close
        
        change_pct = ((last_close - prev_close) / prev_close * 100)
        
        # ===== 生成信號（全部使用 Python float，避免 Series 判斷）=====
        signals = []
        
        # 1. 黃金交叉
        if sma_20 > sma_50 and prev_sma_20 <= prev_sma_50:
            signals.append("黃金交叉")
        
        # 2. 均線多頭
        if last_close > sma_20 and sma_20 > sma_50:
            signals.append("均線多頭")
        
        # 3. RSI
        if 30 < current_rsi < 50:
            signals.append("RSI反彈")
        elif 50 < current_rsi < 70:
            signals.append("RSI強勢")
        
        # 4. MACD
        if current_macd > 0 and prev_macd <= 0:
            signals.append("MACD翻正")
        elif current_macd > 0 and current_macd > prev_macd:
            signals.append("MACD加速")
        
        # 5. 成交量
        if current_volume > avg_volume_20 * 1.5:
            signals.append("成交量激增")
        
        # 6. 突破
        if last_close >= high_20d * 0.99:
            signals.append("接近20日高")
        
        if last_close >= high_52w * 0.90:
            signals.append("接近52週高")
        
        if last_close >= low_52w * 1.2:
            signals.append("從低點反彈")
        
        # 7. 布林帶
        if last_close > bb_upper:
            signals.append("突破布林上軌")
        
        if prev_close < bb_lower and last_close >= bb_lower:
            signals.append("布林下軌反彈")
        
        position_bb = (last_close - bb_lower) / (bb_upper - bb_lower)
        if 0.5 < position_bb <= 1.0:
            signals.append("布林帶強勢")
        
        # 8. VWAP
        if last_close > current_vwap:
            signals.append("站上VWAP")
        
        # 顯示信號
        print(f"✓ {len(signals)} 信號")
        
        # 篩選
        if len(signals) >= MIN_SIGNALS:
            return {
                'Ticker': ticker,
                'Price': round(last_close, 2),
                'Change_%': round(change_pct, 2),
                'SMA_20': round(sma_20, 2),
                'SMA_50': round(sma_50, 2),
                'RSI': round(current_rsi, 2),
                'MACD': round(current_macd, 4),
                'BB_Upper': round(bb_upper, 2),
                'BB_Lower': round(bb_lower, 2),
                'BB_Width': round(bb_width, 2),
                'VWAP': round(current_vwap, 2),
                'Volume': int(current_volume),
                'Avg_Vol': int(avg_volume_20),
                'Vol_Ratio': round(current_volume / avg_volume_20, 2),
                '52W_High': round(high_52w, 2),
                '52W_Low': round(low_52w, 2),
                '20D_High': round(high_20d, 2),
                'Signals': len(signals),
                'Signal_List': ", ".join(signals),
                'Time': datetime.now().strftime('%Y-%m-%d %H:%M')
            }
        return None
        
    except Exception as e:
        print(f"❌ {str(e)[:40]}")
        return None

def upload_to_google_sheets(results):
    """上傳到 Google Sheets"""
    try:
        creds_json = os.environ.get('GOOGLE_CREDENTIALS')
        sheet_id = os.environ.get('GOOGLE_SHEET_ID')
        
        if not creds_json or not sheet_id:
            print("⚠️ 缺少憑證")
            return False
        
        creds_dict = json.loads(creds_json)
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        sheet = client.open_by_key(sheet_id).sheet1
        sheet.clear()
        
        headers = list(results[0].keys())
        rows = [headers]
        for r in results:
            rows.append([r[h] for h in headers])
        
        sheet.update(rows, value_input_option='USER_ENTERED')
        
        print(f"✅ 上傳 {len(results)} 筆到 Google Sheets")
        return True
        
    except Exception as e:
        print(f"❌ 上傳失敗：{str(e)[:40]}")
        return False

def main():
    print("\n" + "="*70)
    print(f"🚀 股票掃描器（≥ {MIN_SIGNALS} 信號）")
    print("="*70)
    print(f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*70 + "\n")
    
    Path(OUTPUT_FOLDER).mkdir(exist_ok=True)
    
    results = []
    for idx, ticker in enumerate(SCAN_TICKERS, 1):
        print(f"[{idx}/{len(SCAN_TICKERS)}] {ticker}... ", end="")
        result = scan_single_stock(ticker)
        if result:
            results.append(result)
    
    print(f"\n{'='*70}")
    
    if results:
        results.sort(key=lambda x: x['Signals'], reverse=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(OUTPUT_FOLDER, f"results_{timestamp}.csv")
        
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
        
        print(f"✅ CSV: {output_file}")
        
        upload_to_google_sheets(results)
        
        print(f"\n📊 TOP 10:\n")
        for i, r in enumerate(results[:10], 1):
            print(f"{i}. {r['Ticker']}: ${r['Price']} | RSI {r['RSI']} | {r['Signals']} 信號")
        
        print(f"\n✅ 找到 {len(results)} 支股票")
    else:
        print("⚠️ 沒有符合條件的股票")
    
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
