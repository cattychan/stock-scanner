#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
股票掃描器 with Google Sheets - 增強版
包含：布林帶、VWAP、突破新高、至少3個信號
"""

import yfinance as yf
import pandas as pd
import numpy as np
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
    "QCOM", "AVGO", "LRCX", "KLAC", "MCHP", "AMAT", "SNPS", "CDNS", "ADSK",
    "NOW", "ADP"
]

def calculate_bollinger_bands(data, period=20, std_dev=2):
    """計算布林帶"""
    sma = data['Close'].rolling(window=period).mean()
    std = data['Close'].rolling(window=period).std()
    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)
    return upper_band, sma, lower_band

def calculate_vwap(data):
    """計算 VWAP (Volume Weighted Average Price)"""
    try:
        typical_price = (data['High'] + data['Low'] + data['Close']) / 3
        vwap = (typical_price * data['Volume']).cumsum() / data['Volume'].cumsum()
        return vwap
    except:
        return None

def scan_single_stock(ticker):
    """掃描單支股票 - 增強版"""
    try:
        # 下載 3 個月數據
        data = yf.download(ticker, period="3mo", progress=False, auto_adjust=True)
        
        # 檢查數據
        if data is None or len(data) == 0 or len(data) < 50:
            return None
        
        # ============ 基礎數據 ============
        last_close = float(data['Close'].iloc[-1])
        prev_close = float(data['Close'].iloc[-2])
        current_volume = float(data['Volume'].iloc[-1])
        avg_volume_20 = float(data['Volume'].tail(20).mean())
        
        # ============ 移動平均線 ============
        sma_20 = float(data['Close'].rolling(window=20).mean().iloc[-1])
        sma_50 = float(data['Close'].rolling(window=50).mean().iloc[-1])
        prev_sma_20 = float(data['Close'].rolling(window=20).mean().iloc[-2])
        prev_sma_50 = float(data['Close'].rolling(window=50).mean().iloc[-2])
        
        # ============ RSI ============
        delta = data['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
        rs = gain / loss
        rsi_series = 100 - (100 / (1 + rs))
        current_rsi = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else None
        
        # ============ MACD ============
        ema_12 = data['Close'].ewm(span=12, adjust=False).mean()
        ema_26 = data['Close'].ewm(span=26, adjust=False).mean()
        macd_line = ema_12 - ema_26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - signal_line
        current_macd_hist = float(macd_hist.iloc[-1]) if not pd.isna(macd_hist.iloc[-1]) else None
        prev_macd_hist = float(macd_hist.iloc[-2]) if not pd.isna(macd_hist.iloc[-2]) else None
        
        # ============ 布林帶 ============
        upper_band, middle_band, lower_band = calculate_bollinger_bands(data, period=20, std_dev=2)
        current_upper = float(upper_band.iloc[-1]) if not pd.isna(upper_band.iloc[-1]) else None
        current_lower = float(lower_band.iloc[-1]) if not pd.isna(lower_band.iloc[-1]) else None
        current_middle = float(middle_band.iloc[-1]) if not pd.isna(middle_band.iloc[-1]) else None
        
        # 布林帶寬度（波動性指標）
        bb_width = ((current_upper - current_lower) / current_middle * 100) if current_middle else None
        
        # ============ VWAP ============
        vwap_series = calculate_vwap(data)
        current_vwap = float(vwap_series.iloc[-1]) if vwap_series is not None and not pd.isna(vwap_series.iloc[-1]) else None
        
        # ============ 52週高低 ============
        try:
            year_data = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
            if year_data is not None and len(year_data) > 0:
                high_52w = float(year_data['High'].max())
                low_52w = float(year_data['Low'].min())
                
                # 計算 20 日高低（用於突破判斷）
                high_20d = float(data['High'].tail(20).max())
                low_20d = float(data['Low'].tail(20).min())
            else:
                high_52w = last_close
                low_52w = last_close
                high_20d = last_close
                low_20d = last_close
        except:
            high_52w = last_close
            low_52w = last_close
            high_20d = last_close
            low_20d = last_close
        
        # ============ 計算漲跌幅 ============
        change_pct = ((last_close - prev_close) / prev_close * 100)
        
        # ============ 生成交易信號 ============
        signals = []
        
        # 1. 黃金交叉（SMA20 向上穿越 SMA50）
        if sma_20 > sma_50 and prev_sma_20 <= prev_sma_50:
            signals.append("黃金交叉")
        
        # 2. 均線多頭排列
        if last_close > sma_20 > sma_50:
            signals.append("均線多頭")
        
        # 3. RSI 超賣反彈
        if current_rsi and 30 < current_rsi < 50:
            signals.append("RSI反彈")
        
        # 4. RSI 強勢區
        if current_rsi and 50 < current_rsi < 70:
            signals.append("RSI強勢")
        
        # 5. MACD 翻正
        if current_macd_hist and prev_macd_hist and current_macd_hist > 0 and prev_macd_hist <= 0:
            signals.append("MACD翻正")
        
        # 6. MACD 正值且上升
        if current_macd_hist and prev_macd_hist and current_macd_hist > 0 and current_macd_hist > prev_macd_hist:
            signals.append("MACD加速")
        
        # 7. 成交量激增
        if current_volume > avg_volume_20 * 1.5:
            signals.append("成交量激增")
        
        # 8. 突破 20 日高點
        if last_close > high_20d * 0.995:  # 接近或突破 20 日高點
            signals.append("突破20日高")
        
        # 9. 接近 52 週高點
        if last_close > high_52w * 0.95:
            signals.append("接近52週高")
        
        # 10. 從 52 週低點反彈
        if last_close > low_52w * 1.3:  # 從低點反彈 30% 以上
            signals.append("從低點反彈")
        
        # 11. 布林帶突破上軌
        if current_upper and last_close > current_upper:
            signals.append("突破布林上軌")
        
        # 12. 布林帶下軌反彈
        if current_lower and prev_close < current_lower and last_close > current_lower:
            signals.append("布林下軌反彈")
        
        # 13. 價格在布林帶中上部（強勢）
        if current_upper and current_lower and current_middle:
            position_in_bb = (last_close - current_lower) / (current_upper - current_lower)
            if 0.6 < position_in_bb < 1.0:
                signals.append("布林帶強勢區")
        
        # 14. 站上 VWAP（大戶成本線）
        if current_vwap and last_close > current_vwap:
            signals.append("站上VWAP")
        
        # 15. 價格突破 VWAP（由下往上）
        if current_vwap and prev_close < current_vwap and last_close > current_vwap:
            signals.append("突破VWAP")
        
        # ============ 篩選條件：至少 3 個信號 ============
        if len(signals) >= 3:
            return {
                'Ticker': ticker,
                'Price': round(last_close, 2),
                'Change_%': round(change_pct, 2),
                'SMA_20': round(sma_20, 2),
                'SMA_50': round(sma_50, 2),
                'RSI': round(current_rsi, 2) if current_rsi else "N/A",
                'MACD_Hist': round(current_macd_hist, 4) if current_macd_hist else "N/A",
                'BB_Upper': round(current_upper, 2) if current_upper else "N/A",
                'BB_Lower': round(current_lower, 2) if current_lower else "N/A",
                'BB_Width_%': round(bb_width, 2) if bb_width else "N/A",
                'VWAP': round(current_vwap, 2) if current_vwap else "N/A",
                'Volume': int(current_volume),
                'Avg_Vol_20': int(avg_volume_20),
                'Vol_Ratio': round(current_volume / avg_volume_20, 2) if avg_volume_20 > 0 else "N/A",
                '52W_High': round(high_52w, 2),
                '52W_Low': round(low_52w, 2),
                '20D_High': round(high_20d, 2),
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
        creds_json = os.environ.get('GOOGLE_CREDENTIALS')
        sheet_id = os.environ.get('GOOGLE_SHEET_ID')
        
        if not creds_json or not sheet_id:
            print("⚠️ 缺少 Google Sheets 憑證或 Sheet ID")
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
        
        print(f"✅ 成功上傳 {len(results)} 筆數據到 Google Sheets")
        return True
        
    except Exception as e:
        print(f"❌ 上傳失敗：{str(e)}")
        return False

def main():
    print("\n" + "="*70)
    print("🚀 股票掃描器 - 增強版（至少3個信號）")
    print("="*70)
    print(f"掃描時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"技術指標: SMA, RSI, MACD, 布林帶, VWAP, 突破新高")
    print(f"篩選條件: ≥ 3 個技術信號")
    print("="*70 + "\n")
    
    Path(OUTPUT_FOLDER).mkdir(exist_ok=True)
    
    results = []
    for idx, ticker in enumerate(SCAN_TICKERS, 1):
        print(f"[{idx}/{len(SCAN_TICKERS)}] {ticker}...", end=" ")
        result = scan_single_stock(ticker)
        if result:
            results.append(result)
            print(f"✅ {result['Signal_Count']} 信號")
        else:
            print("⏭️")
    
    print(f"\n{'='*70}")
    
    if results:
        results.sort(key=lambda x: x['Signal_Count'], reverse=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(OUTPUT_FOLDER, f"scanner_results_{timestamp}.csv")
        
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
        
        print(f"✅ CSV 已儲存：{output_file}")
        
        upload_to_google_sheets(results)
        
        print(f"\n📊 TOP 10 超級機會股:\n")
        print(f"{'排名':<4} {'代碼':<8} {'價格':<10} {'漲跌%':<8} {'RSI':<8} {'信號數':<8} {'信號列表':<50}")
        print("-" * 100)
        for i, r in enumerate(results[:10], 1):
            rsi_str = str(r['RSI']) if r['RSI'] != "N/A" else "N/A"
            signals_str = r['Signals'][:45] + "..." if len(r['Signals']) > 45 else r['Signals']
            print(f"{i:<4} {r['Ticker']:<8} ${r['Price']:<9.2f} {r['Change_%']:>6.2f}% {rsi_str:<8} {r['Signal_Count']:<8} {signals_str:<50}")
        
        print(f"\n✅ 找到 {len(results)} 支符合條件的股票（≥ 3 信號）")
    else:
        print("⚠️ 沒有找到符合條件的股票（至少需要 3 個信號）")
    
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
