#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票掃描器 v3.3 - 極簡穩定版本
使用最安全的方式提取 yfinance 數據
"""

import yfinance as yf
import csv
from datetime import datetime
import os
from pathlib import Path
import pandas as pd

OUTPUT_FOLDER = "stock_data"

# 擴展的 190+ 支股票清單
SCAN_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JNJ", "V",
    "WMT", "JPM", "PG", "MA", "HD", "DIS", "MCD", "ADBE", "CRM", "NFLX",
    "INTC", "CSCO", "IBM", "ORCL", "MU", "PYPL", "SHOP", "ASML", "AMD",
    "QCOM", "AVGO", "LRCX", "KLAC", "MCHP", "AMAT", "SNPS", "CDNS", "ADSK", "CPRT",
    "NOW", "ADP", "EXC", "NEE", "DUK", "SO", "AEP", "PCG", "ED",
    "WEC", "XEL", "CMS", "SRE", "PNW", "AWK", "NRG", "EVRG", "VRSN", "DDOG",
    "ROP", "ODFL", "PAYX", "DECK", "ULTA", "NVR", "KBH", "PHM", "DHI",
    "LEN", "SBNY", "UNM", "PGR", "HIG", "ALL", "BHF", "OC", "IEX", "LEG",
    "ATGE", "VEEV", "RBA", "CLOW", "FIX", "HY", "SMPL", "TPR", "BAC", "WFC",
    "GS", "MS", "BLK", "BK", "PNC", "USB", "COF", "AXP", "ICE", "CME",
    "COIN", "SOFI", "DASH", "XOM", "CVX", "COP", "EOG", "MPC", "PSX", "VLO",
    "FANG", "OKE", "KMI", "TPL", "CNX", "RRC", "DVN",
    "BA", "CAT", "GE", "MMM", "RTX", "LMT", "NOC", "GD", "HWM", "CARR",
    "OTIS", "EMR", "HON", "EW", "DOV", "ITW", "ROK", "CTAS", "ABM", "KO",
    "PEP", "CL", "KHC", "GIS", "K", "CAG", "ADM", "MDLZ", "PII", "HSY",
    "MKC", "CPB", "SJM", "STZ", "MNST", "NKE", "SBUX",
    "LOW", "TJX", "RCL", "CCL", "MAR", "RH", "ETSY", "ABNB", "SPOT", "GM",
    "F", "LUV", "DAL", "PLD", "AMT", "CCI", "EQIX", "DLR", "VICI", "WELL",
    "PSA", "EQR", "AVB", "ARE", "MAA", "UMH", "XRT", "KRG", "MAC",
    "DEI", "CDP", "CMCSA", "T", "VZ", "FOX", "FOXA", "CHTR",
    "TTWO", "SEE", "IAC", "FUBO", "MSGS",
    "TECH", "BIO", "BALL", "CAR", "CSL", "BNGO", "UPST", "MSTR",
    "RIOT", "MARA", "CLSK", "HUT", "QRVO", "FLEX", "APH", "MRAM", "SEMI", "NVRI", "PSTG", "AKAM", "DOCU", "PEGA"
]

def scan_single_stock(ticker):
    """掃描單支股票"""
    try:
        print(f"  掃描 {ticker}...", end=" ")
        
        # 下載數據
        data = yf.download(ticker, period="3mo", progress=False, auto_adjust=True)
        
        if data is None or data.empty or len(data) < 20:
            print("❌ 無數據")
            return None
        
        # 使用 pandas 的安全方式提取數據
        close_prices = data['Close'].astype(float).tolist()
        volumes = data['Volume'].astype(float).tolist()
        
        if not close_prices or not volumes:
            print("❌ 數據為空")
            return None
        
        current_price = close_prices[-1]
        prev_price = close_prices[-2] if len(close_prices) > 1 else current_price
        current_volume = volumes[-1]
        avg_volume = sum(volumes[-20:]) / min(20, len(volumes))
        
        # 計算漲跌幅
        change_pct = ((current_price - prev_price) / prev_price * 100) if prev_price != 0 else 0
        
        # 計算技術指標
        # SMA 20
        sma_20 = sum(close_prices[-20:]) / 20 if len(close_prices) >= 20 else None
        # SMA 50
        sma_50 = sum(close_prices[-50:]) / 50 if len(close_prices) >= 50 else None
        
        # RSI 14
        if len(close_prices) >= 15:
            deltas = [close_prices[i] - close_prices[i-1] for i in range(1, len(close_prices))]
            gains = [d if d > 0 else 0 for d in deltas]
            losses = [-d if d < 0 else 0 for d in deltas]
            avg_gain = sum(gains[-14:]) / 14
            avg_loss = sum(losses[-14:]) / 14
            if avg_loss == 0:
                rsi = 100 if avg_gain > 0 else 50
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
        else:
            rsi = None
        
        # MACD
        if len(close_prices) >= 26:
            ema_fast = sum(close_prices[-12:]) / 12
            ema_slow = sum(close_prices[-26:]) / 26
            macd = ema_fast - ema_slow
        else:
            macd = None
        
        # 52 週高低
        try:
            year_data = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
            if year_data is not None and not year_data.empty:
                high_52w = float(year_data['High'].astype(float).max())
                low_52w = float(year_data['Low'].astype(float).min())
            else:
                high_52w = current_price
                low_52w = current_price
        except:
            high_52w = current_price
            low_52w = current_price
        
        # 生成交易信號
        signals = []
        
        if sma_20 and sma_50 and sma_20 > sma_50:
            signals.append("Golden_Cross")
        
        if rsi and 30 < rsi < 70:
            signals.append("RSI_Normal")
        
        if rsi and 30 < rsi < 45:
            signals.append("RSI_Bounce")
        
        if current_volume > avg_volume * 1.5:
            signals.append("Volume_Surge")
        
        if current_price > high_52w * 0.95:
            signals.append("Near_52W_High")
        
        if current_price > low_52w * 1.2:
            signals.append("From_Low_Rebound")
        
        # 篩選條件：至少 2 個信號
        if len(signals) >= 2:
            print(f"✅ {len(signals)} 信號")
            return {
                'Ticker': ticker,
                'Price': round(current_price, 2),
                'Change_%': round(change_pct, 2),
                'SMA_20': round(sma_20, 2) if sma_20 else "N/A",
                'SMA_50': round(sma_50, 2) if sma_50 else "N/A",
                'RSI': round(rsi, 2) if rsi else "N/A",
                'MACD': round(macd, 4) if macd else "N/A",
                'Volume': int(current_volume),
                'Volume_Avg_20': int(avg_volume),
                '52W_High': round(high_52w, 2),
                '52W_Low': round(low_52w, 2),
                'Signal_Count': len(signals),
                'Signals': ", ".join(signals),
                'Scan_Time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        else:
            print(f"⏭️  {len(signals)} 信號")
            return None
        
    except Exception as e:
        print(f"❌ {str(e)[:30]}")
        return None

def main():
    print("\n" + "="*70)
    print("🚀 股票掃描器 v3.3 - 極簡穩定版本")
    print("="*70)
    print(f"掃描股票數量: {len(SCAN_TICKERS)}")
    print(f"掃描時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"篩選條件: 至少 2 個技術面信號")
    print("="*70 + "\n")
    
    Path(OUTPUT_FOLDER).mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(OUTPUT_FOLDER, f"scanner_results_{timestamp}.csv")
    
    results = []
    
    print("開始掃描...\n")
    
    for idx, ticker in enumerate(SCAN_TICKERS, 1):
        print(f"[{idx:3d}/{len(SCAN_TICKERS)}] {ticker:6s}", end=" ")
        result = scan_single_stock(ticker)
        
        if result:
            results.append(result)
    
    results.sort(key=lambda x: x['Signal_Count'], reverse=True)
    
    print(f"\n{'='*70}")
    
    if len(results) > 0:
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                fieldnames = [
                    'Ticker', 'Price', 'Change_%', 'SMA_20', 'SMA_50', 'RSI', 'MACD',
                    'Volume', 'Volume_Avg_20', '52W_High', '52W_Low',
                    'Signal_Count', 'Signals', 'Scan_Time'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results)
            
            print(f"✅ 掃描完成！")
            print(f"📊 找到 {len(results)} 支符合條件的股票")
            print(f"📁 結果已保存到: {output_file}")
            print(f"{'='*70}\n")
            
            print("🏆 TOP 10 候選股票:\n")
            print(f"{'Ticker':<8} {'Price':<10} {'Change%':<10} {'RSI':<8} {'Signal':<7} {'信號':<40}")
            print("-" * 90)
            
            for r in results[:10]:
                signals_str = r['Signals'][:37]
                print(f"{r['Ticker']:<8} ${r['Price']:<9.2f} {r['Change_%']:>8.2f}% {str(r['RSI']):<7} {r['Signal_Count']:<6} {signals_str:<40}")
            
            print(f"\n{'='*70}")
            if os.path.exists(output_file):
                file_size = os.path.getsize(output_file)
                print(f"✅ 文件驗證: {output_file} ({file_size} bytes)")
            
        except Exception as e:
            print(f"❌ 寫檔案失敗: {str(e)}")
    else:
        print(f"❌ 未找到符合條件的股票")
    
    print(f"\n📈 統計:")
    print(f"掃描的股票: {len(SCAN_TICKERS)}")
    print(f"符合條件: {len(results)}")
    if len(SCAN_TICKERS) > 0:
        print(f"成功率: {len(results)/len(SCAN_TICKERS)*100:.1f}%")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
