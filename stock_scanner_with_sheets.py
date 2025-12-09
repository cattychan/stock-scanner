#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
股票掃描器 with Google Sheets - 終極穩定版
基於 v34 的穩定架構 + 增強功能
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

SCAN_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JNJ", "V",
    "WMT", "JPM", "PG", "MA", "HD", "DIS", "MCD", "ADBE", "CRM", "NFLX",
    "INTC", "CSCO", "IBM", "ORCL", "MU", "PYPL", "SHOP", "ASML", "AMD",
    "QCOM", "AVGO", "LRCX", "KLAC", "MCHP", "AMAT", "SNPS", "CDNS", "ADSK",
    "NOW", "ADP"
]

def scan_single_stock(ticker):
    """掃描單支股票 - 穩定增強版"""
    try:
        # 下載數據
        data = yf.download(ticker, period="3mo", progress=False)
        
        if data is None or len(data) == 0 or len(data) < 50:
            return None
        
        # ============ 直接提取值（v34 方式）============
        last_close = data['Close'].iloc[-1]
        prev_close = data['Close'].iloc[-2]
        current_volume = data['Volume'].iloc[-1]
        avg_volume_20 = data['Volume'].tail(20).mean()
        
        # ============ 計算指標 ============
        change_pct = ((last_close - prev_close) / prev_close * 100)
        
        # SMA
        sma_20 = data['Close'].tail(20).mean()
        sma_50 = data['Close'].tail(50).mean() if len(data) >= 50 else None
        
        # 上一期 SMA (用於黃金交叉判斷)
        prev_sma_20 = data['Close'].iloc[:-1].tail(20).mean()
        prev_sma_50 = data['Close'].iloc[:-1].tail(50).mean() if len(data) >= 50 else None
        
        # RSI
        rsi = None
        if len(data) >= 15:
            delta = data['Close'].diff()
            gain = (delta.where(delta > 0, 0)).tail(14).mean()
            loss = (-delta.where(delta < 0, 0)).tail(14).mean()
            if loss != 0:
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs)) if rs >= 0 else 50
        
        # MACD (簡化版)
        macd = None
        prev_macd = None
        if len(data) >= 26:
            ema_12 = data['Close'].ewm(span=12, adjust=False).mean()
            ema_26 = data['Close'].ewm(span=26, adjust=False).mean()
            macd_line = ema_12 - ema_26
            macd = macd_line.iloc[-1]
            prev_macd = macd_line.iloc[-2]
        
        # 布林帶
        bb_upper = None
        bb_lower = None
        bb_width = None
        if len(data) >= 20:
            sma_bb = data['Close'].rolling(window=20).mean()
            std_bb = data['Close'].rolling(window=20).std()
            bb_upper = (sma_bb + (std_bb * 2)).iloc[-1]
            bb_lower = (sma_bb - (std_bb * 2)).iloc[-1]
            bb_middle = sma_bb.iloc[-1]
            if bb_middle > 0:
                bb_width = ((bb_upper - bb_lower) / bb_middle * 100)
        
        # VWAP
        vwap = None
        if len(data) >= 20:
            typical_price = (data['High'] + data['Low'] + data['Close']) / 3
            vwap_series = (typical_price * data['Volume']).cumsum() / data['Volume'].cumsum()
            vwap = vwap_series.iloc[-1]
        
        # 52週高低
        try:
            year_data = yf.download(ticker, period="1y", progress=False)
            if year_data is not None and len(year_data) > 0:
                high_52w = year_data['High'].max()
                low_52w = year_data['Low'].min()
                high_20d = data['High'].tail(20).max()
            else:
                high_52w = last_close
                low_52w = last_close
                high_20d = last_close
        except:
            high_52w = last_close
            low_52w = last_close
            high_20d = last_close
        
        # ============ 生成交易信號 ============
        signals = []
        
        # 1. 黃金交叉
        if sma_50 and prev_sma_50 and sma_20 > sma_50 and prev_sma_20 <= prev_sma_50:
            signals.append("黃金交叉")
        
        # 2. 均線多頭
        if sma_50 and last_close > sma_20 > sma_50:
            signals.append("均線多頭")
        
        # 3. RSI 反彈
        if rsi and 30 < rsi < 50:
            signals.append("RSI反彈")
        
        # 4. RSI 強勢
        if rsi and 50 < rsi < 70:
            signals.append("RSI強勢")
        
        # 5. MACD 翻正
        if macd and prev_macd and macd > 0 and prev_macd <= 0:
            signals.append("MACD翻正")
        
        # 6. MACD 加速
        if macd and prev_macd and macd > 0 and macd > prev_macd:
            signals.append("MACD加速")
        
        # 7. 成交量激增
        if current_volume > avg_volume_20 * 1.5:
            signals.append("成交量激增")
        
        # 8. 突破/接近 20日高
        if last_close >= high_20d * 0.98:
            signals.append("接近20日高")
        
        # 9. 接近 52週高
        if last_close >= high_52w * 0.90:
            signals.append("接近52週高")
        
        # 10. 從低點反彈
        if last_close >= low_52w * 1.2:
            signals.append("從低點反彈")
        
        # 11. 突破布林上軌
        if bb_upper and last_close > bb_upper:
            signals.append("突破布林上軌")
        
        # 12. 布林下軌反彈
        if bb_lower and prev_close < bb_lower and last_close >= bb_lower:
            signals.append("布林下軌反彈")
        
        # 13. 布林帶強勢區
        if bb_upper and bb_lower:
            position = (last_close - bb_lower) / (bb_upper - bb_lower)
            if 0.5 < position <= 1.0:
                signals.append("布林帶強勢區")
        
        # 14. 站上 VWAP
        if vwap and last_close > vwap:
            signals.append("站上VWAP")
        
        # ============ 篩選：至少 2 個信號 ============
        if len(signals) >= 2:
            return {
                'Ticker': ticker,
                'Price': round(float(last_close), 2),
                'Change_%': round(float(change_pct), 2),
                'SMA_20': round(float(sma_20), 2),
                'SMA_50': round(float(sma_50), 2) if sma_50 is not None else "N/A",
                'RSI': round(float(rsi), 2) if rsi else "N/A",
                'MACD': round(float(macd), 4) if macd else "N/A",
                'BB_Upper': round(float(bb_upper), 2) if bb_upper else "N/A",
                'BB_Lower': round(float(bb_lower), 2) if bb_lower else "N/A",
                'BB_Width_%': round(float(bb_width), 2) if bb_width else "N/A",
                'VWAP': round(float(vwap), 2) if vwap else "N/A",
                'Volume': int(current_volume),
                'Avg_Vol_20': int(avg_volume_20),
                'Vol_Ratio': round(float(current_volume / avg_volume_20), 2),
                '52W_High': round(float(high_52w), 2),
                '52W_Low': round(float(low_52w), 2),
                '20D_High': round(float(high_20d), 2),
                'Signal_Count': len(signals),
                'Signals': ", ".join(signals),
                'Scan_Time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        return None
        
    except Exception as e:
        print(f"❌ {ticker} - {str(e)[:30]}")
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
        
        print(f"✅ 成功上傳 {len(results)} 筆到 Google Sheets")
        return True
        
    except Exception as e:
        print(f"❌ 上傳失敗：{str(e)}")
        return False

def main():
    print("\n" + "="*70)
    print("🚀 股票掃描器 - 增強穩定版（≥ 2 信號）")
    print("="*70)
    print(f"掃描時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"技術指標: SMA, RSI, MACD, 布林帶, VWAP, 突破")
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
        
        print(f"✅ CSV: {output_file}")
        
        upload_to_google_sheets(results)
        
        print(f"\n📊 TOP 10:\n")
        for i, r in enumerate(results[:10], 1):
            print(f"{i}. {r['Ticker']}: ${r['Price']} | {r['Signal_Count']} 信號 | {r['Signals'][:50]}")
        
        print(f"\n✅ 找到 {len(results)} 支股票")
    else:
        print("⚠️ 沒有符合條件的股票")
    
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
