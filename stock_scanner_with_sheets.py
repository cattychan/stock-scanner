#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
股票掃描器 - 專業版 v2.0
- 至少 3 個信號
- 風險評分系統
- 波動率篩選
- 流動性篩選
- 100+ 支股票
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
import warnings
warnings.filterwarnings('ignore')

OUTPUT_FOLDER = "stock_data"

# ========== 配置參數 ==========
MIN_SIGNALS = 3  # 至少 3 個信號
MAX_VOLATILITY = 60  # 最大年化波動率 60%
MIN_AVG_VOLUME = 500000  # 最小平均成交量 50萬股
MIN_PRICE = 5.0  # 最低股價 $5（排除垃圾股）
MAX_RISK_SCORE = 70  # 最大風險分數 70（越低越好）

# ========== 100+ 支美股清單 ==========
SCAN_TICKERS = [
    # 科技巨頭 (Mega Cap Tech)
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA", "AVGO", "ORCL",
    
    # 半導體 (Semiconductors)
    "AMD", "INTC", "QCOM", "TXN", "ADI", "MRVL", "MU", "AMAT", "LRCX", "KLAC",
    "ASML", "SNPS", "CDNS", "MCHP", "ON", "NXPI", "MPWR", "SWKS",
    
    # 軟體 & 雲端 (Software & Cloud)
    "CRM", "ADBE", "NOW", "INTU", "WDAY", "PANW", "CRWD", "ZS", "DDOG", "NET",
    "SNOW", "PLTR", "U", "DOCU", "TWLO", "ZM", "OKTA", "MDB",
    
    # 電商 & 消費 (E-commerce & Consumer)
    "SHOP", "MELI", "BKNG", "ABNB", "DASH", "UBER", "LYFT", "ETSY", "W", "CHWY",
    
    # 金融 (Financials)
    "JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "SCHW", "AXP", "V", "MA", "PYPL",
    "SQ", "COIN", "SOFI",
    
    # 醫療保健 (Healthcare)
    "JNJ", "UNH", "LLY", "ABBV", "MRK", "TMO", "ABT", "DHR", "PFE", "AMGN",
    "GILD", "VRTX", "REGN", "BMY", "CVS",
    
    # 工業 (Industrials)
    "BA", "CAT", "GE", "HON", "UPS", "RTX", "LMT", "DE", "MMM", "UNP",
    
    # 能源 (Energy)
    "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "HAL",
    
    # 消費品 (Consumer Goods)
    "PG", "KO", "PEP", "COST", "WMT", "HD", "LOW", "NKE", "SBUX", "MCD",
    "TGT", "DIS", "NFLX", "CMCSA",
    
    # 其他重要股票
    "IBM", "CSCO", "ADSK", "ADP", "PAYX", "ROP", "ICE", "CME", "SPGI", "MCO"
]

def calculate_risk_score(data, last_close, current_rsi, current_macd, bb_width, volatility):
    """
    計算風險評分 (0-100)
    分數越低 = 風險越低 = 越適合投資
    """
    risk_score = 0
    
    # 1. 波動率風險 (0-25分)
    if volatility > 50:
        risk_score += 25
    elif volatility > 40:
        risk_score += 20
    elif volatility > 30:
        risk_score += 15
    elif volatility > 20:
        risk_score += 10
    else:
        risk_score += 5
    
    # 2. RSI 風險 (0-20分)
    if current_rsi > 80:  # 超買
        risk_score += 20
    elif current_rsi > 70:
        risk_score += 15
    elif current_rsi < 20:  # 超賣
        risk_score += 20
    elif current_rsi < 30:
        risk_score += 10
    else:
        risk_score += 5
    
    # 3. 價格距離 52 週高點 (0-15分)
    high_52w = float(data['High'].max())
    distance_from_high = (high_52w - last_close) / high_52w * 100
    if distance_from_high > 50:  # 離高點很遠（可能在底部）
        risk_score += 5
    elif distance_from_high > 30:
        risk_score += 10
    elif distance_from_high < 5:  # 接近高點（可能回調）
        risk_score += 15
    else:
        risk_score += 8
    
    # 4. MACD 趨勢風險 (0-15分)
    if current_macd < -0.5:  # 強烈負向
        risk_score += 15
    elif current_macd < 0:
        risk_score += 10
    elif current_macd > 0.5:  # 強烈正向
        risk_score += 5
    else:
        risk_score += 8
    
    # 5. 布林帶寬度（波動性）(0-15分)
    if bb_width > 15:  # 高波動
        risk_score += 15
    elif bb_width > 10:
        risk_score += 10
    elif bb_width < 5:  # 低波動（可能突破）
        risk_score += 5
    else:
        risk_score += 8
    
    # 6. 價格水平風險 (0-10分)
    if last_close < 10:  # 低價股風險高
        risk_score += 10
    elif last_close < 20:
        risk_score += 7
    elif last_close > 500:  # 超高價股
        risk_score += 5
    else:
        risk_score += 3
    
    return min(risk_score, 100)

def calculate_volatility(data):
    """計算年化波動率 (%)"""
    returns = data['Close'].pct_change().dropna()
    volatility = returns.std() * np.sqrt(252) * 100  # 年化
    return float(volatility)

def scan_single_stock(ticker):
    """掃描單支股票 - 專業版"""
    try:
        # 下載數據
        data = yf.download(ticker, period="3mo", progress=False, auto_adjust=True)
        
        if data.empty or len(data) < 50:
            return None
        
        # ===== 基礎數據 =====
        last_close = float(data['Close'].iloc[-1])
        prev_close = float(data['Close'].iloc[-2])
        current_volume = float(data['Volume'].iloc[-1])
        
        # 計算平均成交量
        avg_volume_20 = float(data['Volume'].tail(20).mean())
        
        # ===== 流動性篩選 =====
        if avg_volume_20 < MIN_AVG_VOLUME:
            print(f"⏭️ 流動性不足 ({avg_volume_20:,.0f} < {MIN_AVG_VOLUME:,.0f})")
            return None
        
        # ===== 價格篩選 =====
        if last_close < MIN_PRICE:
            print(f"⏭️ 價格過低 (${last_close:.2f})")
            return None
        
        # ===== 計算波動率 =====
        volatility = calculate_volatility(data)
        if volatility > MAX_VOLATILITY:
            print(f"⏭️ 波動率過高 ({volatility:.1f}% > {MAX_VOLATILITY}%)")
            return None
        
        # ===== 技術指標計算 =====
        close_series = data['Close']
        
        # SMA
        sma_20 = float(close_series.rolling(window=20).mean().iloc[-1])
        sma_50 = float(close_series.rolling(window=50).mean().iloc[-1])
        prev_sma_20 = float(close_series.rolling(window=20).mean().iloc[-2])
        prev_sma_50 = float(close_series.rolling(window=50).mean().iloc[-2])
        
        # RSI
        delta = close_series.diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
        rs = gain / loss
        rsi_series = 100 - (100 / (1 + rs))
        current_rsi = float(rsi_series.iloc[-1])
        
        # MACD
        ema_12 = close_series.ewm(span=12, adjust=False).mean()
        ema_26 = close_series.ewm(span=26, adjust=False).mean()
        macd_line = ema_12 - ema_26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - signal_line
        current_macd = float(macd_hist.iloc[-1])
        prev_macd = float(macd_hist.iloc[-2])
        
        # 布林帶
        sma_bb = close_series.rolling(window=20).mean()
        std_bb = close_series.rolling(window=20).std()
        upper_band = sma_bb + (std_bb * 2)
        lower_band = sma_bb - (std_bb * 2)
        bb_upper = float(upper_band.iloc[-1])
        bb_lower = float(lower_band.iloc[-1])
        bb_middle = float(sma_bb.iloc[-1])
        bb_width = ((bb_upper - bb_lower) / bb_middle * 100)
        
        # VWAP
        typical_price = (data['High'] + data['Low'] + data['Close']) / 3
        vwap = (typical_price * data['Volume']).cumsum() / data['Volume'].cumsum()
        current_vwap = float(vwap.iloc[-1])
        
        # 52 週數據
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
        
        # ===== 計算風險評分 =====
        risk_score = calculate_risk_score(data, last_close, current_rsi, current_macd, bb_width, volatility)
        
        # ===== 風險篩選 =====
        if risk_score > MAX_RISK_SCORE:
            print(f"⏭️ 風險過高 (風險分數: {risk_score})")
            return None
        
        # ===== 生成交易信號 =====
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
        
        # 9. 低波動突破
        if volatility < 20 and current_volume > avg_volume_20 * 1.3:
            signals.append("低波動放量")
        
        # 顯示結果
        if len(signals) >= MIN_SIGNALS:
            risk_label = "低風險" if risk_score < 40 else "中風險" if risk_score < 60 else "偏高風險"
            print(f"✓ {len(signals)} 信號 | 風險: {risk_score} ({risk_label})")
        else:
            print(f"⏭️ 只有 {len(signals)} 信號")
            return None
        
        # 篩選
        if len(signals) >= MIN_SIGNALS:
            return {
                'Ticker': ticker,
                'Price': round(last_close, 2),
                'Change_%': round(change_pct, 2),
                'Risk_Score': risk_score,
                'Volatility_%': round(volatility, 1),
                'SMA_20': round(sma_20, 2),
                'SMA_50': round(sma_50, 2),
                'RSI': round(current_rsi, 1),
                'MACD': round(current_macd, 4),
                'BB_Width': round(bb_width, 1),
                'VWAP': round(current_vwap, 2),
                'Volume': int(current_volume),
                'Avg_Vol': int(avg_volume_20),
                'Vol_Ratio': round(current_volume / avg_volume_20, 2),
                '52W_High': round(high_52w, 2),
                '52W_Low': round(low_52w, 2),
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
    print("\n" + "="*80)
    print("🚀 股票掃描器 - 專業版 v2.0")
    print("="*80)
    print(f"掃描時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"掃描股票: {len(SCAN_TICKERS)} 支")
    print(f"篩選條件:")
    print(f"  • 至少 {MIN_SIGNALS} 個技術信號")
    print(f"  • 風險評分 ≤ {MAX_RISK_SCORE}")
    print(f"  • 波動率 ≤ {MAX_VOLATILITY}%")
    print(f"  • 平均成交量 ≥ {MIN_AVG_VOLUME:,}")
    print(f"  • 股價 ≥ ${MIN_PRICE}")
    print("="*80 + "\n")
    
    Path(OUTPUT_FOLDER).mkdir(exist_ok=True)
    
    results = []
    for idx, ticker in enumerate(SCAN_TICKERS, 1):
        print(f"[{idx}/{len(SCAN_TICKERS)}] {ticker}... ", end="")
        result = scan_single_stock(ticker)
        if result:
            results.append(result)
    
    print(f"\n{'='*80}")
    
    if results:
        # 排序：風險分數由低到高
        results.sort(key=lambda x: (x['Risk_Score'], -x['Signals']))
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(OUTPUT_FOLDER, f"results_{timestamp}.csv")
        
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
        
        print(f"✅ CSV: {output_file}")
        
        upload_to_google_sheets(results)
        
        print(f"\n📊 TOP 10 最佳機會（按風險分數排序）:\n")
        print(f"{'排名':<4} {'代碼':<6} {'價格':<8} {'風險':<6} {'波動':<6} {'RSI':<6} {'信號':<4} {'信號列表':<50}")
        print("-" * 100)
        
        for i, r in enumerate(results[:10], 1):
            risk_label = "🟢" if r['Risk_Score'] < 40 else "🟡" if r['Risk_Score'] < 60 else "🟠"
            signals_short = r['Signal_List'][:45] + "..." if len(r['Signal_List']) > 45 else r['Signal_List']
            print(f"{i:<4} {r['Ticker']:<6} ${r['Price']:<7.2f} {risk_label}{r['Risk_Score']:<5} {r['Volatility_%']:<5.1f}% {r['RSI']:<5.1f} {r['Signals']:<4} {signals_short:<50}")
        
        print(f"\n✅ 找到 {len(results)} 支符合條件的股票")
        print(f"📈 平均風險分數: {sum(r['Risk_Score'] for r in results) / len(results):.1f}")
        print(f"📊 平均波動率: {sum(r['Volatility_%'] for r in results) / len(results):.1f}%")
    else:
        print("⚠️ 沒有符合條件的股票")
    
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()
