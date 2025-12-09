#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
股票掃描器 with Google Sheets - 修復版
結合 v3.4 的穩定掃描 + Google Sheets 上傳
"""

import yfinance as yf
import csv
from datetime import datetime
import os
from pathlib import Path
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

OUTPUT_FOLDER = "stock_data"

# 核心股票清單
SCAN_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JNJ", "V",
    "WMT", "JPM", "PG", "MA", "HD", "DIS", "MCD", "ADBE", "CRM", "NFLX",
    "INTC", "CSCO", "IBM", "ORCL", "MU", "PYPL", "SHOP", "ASML", "AMD",
    "QCOM", "AVGO"
]

def scan_single_stock(ticker):
    """掃描單支股票 - 穩定版本"""
    try:
        # 直接下載
        data = yf.download(ticker, period="3mo", progress=False)
        
        # 檢查數據
        if data is None or len(data) == 0 or len(data) < 20:
            return None
        
        # 直接提取值（已修復 Series 問題）
        last_close = float(data['Close'].iloc[-1])
        prev_close = float(data['Close'].iloc[-2])
        current_volume = float(data['Volume'].iloc[-1])
        avg_volume_20 = float(data['Volume'].tail(20).mean())
        
        # 計算指標
        change_pct = ((last_close - prev_close) / prev_close * 100)
        sma_20 = float(data['Close'].tail(20).mean())
        sma_50 = float(data['Close'].tail(50).mean()) if len(data) >= 50 else None
        
        # RSI
        rsi = None
        if len(data) >= 15:
            delta = data['Close'].diff()
            gain = float((delta.where(delta > 0, 0)).tail(14).mean())
            loss = float((-delta.where(delta < 0, 0)).tail(14).mean())
            if loss != 0:
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs)) if rs >= 0 else 50
        
        # MACD（簡化）
        macd = None
        if len(data) >= 26:
            ema_12 = float(data['Close'].tail(12).mean())
            ema_26 = float(data['Close'].tail(26).mean())
            macd = ema_12 - ema_26
        
        # 52週高低
        try:
            year_data = yf.download(ticker, period="1y", progress=False)
            if year_data is not None and len(year_data) > 0:
                high_52w = float(year_data['High'].max())
                low_52w = float(year_data['Low'].min())
            else:
                high_52w = last_close
                low_52w = last_close
        except:
            high_52w = last_close
            low_52w = last_close
        
        # 生成信號
        signals = []
        
        # 黃金交叉
        if sma_50 is not None and sma_20 > sma_50:
            signals.append("Golden_Cross")
        
        # RSI
        if rsi and 30 < rsi < 70:
            signals.append("RSI_Normal")
        if rsi and 30 < rsi < 45:
            signals.append("RSI_Bounce")
        
        # 成交量
        if current_volume > avg_volume_20 * 1.5:
            signals.append("Volume_Surge")
        
        # 52週高點
        if last_close > high_52w * 0.95:
            signals.append("Near_52W_High")
        
        # 從低位反彈
        if last_close > low_52w * 1.2:
            signals.append("From_Low_Rebound")
        
        # 至少 2 個信號
        if len(signals) >= 2:
            return {
                'Ticker': ticker,
                'Price': round(last_close, 2),
                'Change_%': round(change_pct, 2),
                'SMA_20': round(sma_20, 2),
                'SMA_50': round(sma_50, 2) if sma_50 is not None else "N/A",
                'RSI': round(rsi, 2) if rsi else "N/A",
                'MACD': round(macd, 4) if macd else "N/A",
                'Volume': int(current_volume),
                'Volume_Avg_20': int(avg_volume_20),
                '52W_High': round(high_52w, 2),
                '52W_Low': round(low_52w, 2),
                'Signal_Count': len(signals),
                'Signals': ", ".join(signals),
                'Scan_Time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        return None
        
    except Exception as e:
        print(f"❌ {ticker} - {str(e)}")
        return None

def upload_to_google_sheets(results):
    """上傳到 Google Sheets"""
    try:
        # 讀取環境變數
        creds_json = os.environ.get('GOOGLE_CREDENTIALS')
        sheet_id = os.environ.get('GOOGLE_SHEET_ID')
        
        if not creds_json or not sheet_id:
            print("⚠️ 缺少 Google Sheets 憑證或 Sheet ID")
            return False
        
        # 解析憑證
        creds_dict = json.loads(creds_json)
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # 打開 Sheet
        sheet = client.open_by_key(sheet_id).sheet1
        
        # 清空並寫入
        sheet.clear()
        
        # 準備數據
        headers = list(results[0].keys())
        rows = [headers]
        for r in results:
            rows.append([r[h] for h in headers])
        
        # 寫入
        sheet.update(rows, value_input_option='USER_ENTERED')
        
        print(f"✅ 成功上傳 {len(results)} 筆數據到 Google Sheets")
        return True
        
    except Exception as e:
        print(f"❌ 上傳失敗：{str(e)}")
        return False

def main():
    print("\n" + "="*70)
    print("🚀 股票掃描器 with Google Sheets")
    print("="*70)
    print(f"掃描時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")
    
    # 建立資料夾
    Path(OUTPUT_FOLDER).mkdir(exist_ok=True)
    
    # 掃描股票
    results = []
    for idx, ticker in enumerate(SCAN_TICKERS, 1):
        print(f"[{idx}/{len(SCAN_TICKERS)}] {ticker}...", end=" ")
        result = scan_single_stock(ticker)
        if result:
            results.append(result)
            print("✅")
        else:
            print("⏭️")
    
    print(f"\n{'='*70}")
    
    if results:
        # 排序
        results.sort(key=lambda x: x['Signal_Count'], reverse=True)
        
        # 儲存 CSV
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(OUTPUT_FOLDER, f"scanner_results_{timestamp}.csv")
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
        
        print(f"✅ CSV 已儲存：{output_file}")
        
        # 上傳到 Google Sheets
        upload_to_google_sheets(results)
        
        # 顯示 TOP 10
        print(f"\n📊 TOP 10:")
        for i, r in enumerate(results[:10], 1):
            print(f"{i}. {r['Ticker']}: ${r['Price']} ({r['Signal_Count']} 信號)")
    else:
        print("⚠️ 沒有找到符合條件的股票")
    
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
