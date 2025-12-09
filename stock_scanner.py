#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票掃描器 v3.4 - 超極簡版本
直接使用 yfinance 最基本的操作
"""

import yfinance as yf
import csv
from datetime import datetime
import os
from pathlib import Path

OUTPUT_FOLDER = "stock_data"

# 核心股票清單 - 只保留最常用的
SCAN_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JNJ", "V",
    "WMT", "JPM", "PG", "MA", "HD", "DIS", "MCD", "ADBE", "CRM", "NFLX",
    "INTC", "CSCO", "IBM", "ORCL", "MU", "PYPL", "SHOP", "ASML", "AMD",
    "QCOM", "AVGO", "LRCX", "KLAC", "MCHP", "AMAT", "SNPS", "CDNS", "ADSK",
    "NOW", "ADP", "EXC", "NEE", "DUK", "SO", "AEP", "PCG", "ED",
    "WEC", "XEL", "CMS", "SRE", "PNW", "AWK", "NRG", "EVRG", "VRSN",
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
    """掃描單支股票 - 極簡版本"""
    try:
        print(f"  掃描 {ticker}...", end=" ")
        
        # 直接下載，不進行任何複雜操作
        data = yf.download(ticker, period="3mo", progress=False)
        
        # 檢查是否成功
        if data is None or len(data) == 0:
            print("❌ 無數據")
            return None
        
        if len(data) < 20:
            print("❌ 數據不足")
            return None
        
        # 直接提取最後的值
        last_close = data['Close'].iloc[-1]
        prev_close = data['Close'].iloc[-2]
        current_volume = data['Volume'].iloc[-1]
        avg_volume_20 = data['Volume'].tail(20).mean()
        
        # 計算漲跌幅
        change_pct = ((last_close - prev_close) / prev_close * 100)
        
        # 計算 SMA
        sma_20 = data['Close'].tail(20).mean()
        sma_50 = data['Close'].tail(50).mean() if len(data) >= 50 else None
        
        # 計算 RSI
        if len(data) >= 15:
            delta = data['Close'].diff()
            gain = (delta.where(delta > 0, 0)).tail(14).mean()
            loss = (-delta.where(delta < 0, 0)).tail(14).mean()
            rs = gain / loss if loss != 0 else 0
            rsi = 100 - (100 / (1 + rs)) if rs >= 0 else 50
        else:
            rsi = None
        
        # 計算 MACD（簡化版）
        if len(data) >= 26:
            ema_12 = data['Close'].tail(12).mean()
            ema_26 = data['Close'].tail(26).mean()
            macd = ema_12 - ema_26
        else:
            macd = None
        
        # 52週高低
        try:
            year_data = yf.download(ticker, period="1y", progress=False)
            if year_data is not None and len(year_data) > 0:
                high_52w = year_data['High'].max()
                low_52w = year_data['Low'].min()
            else:
                high_52w = last_close
                low_52w = last_close
        except:
            high_52w = last_close
            low_52w = last_close
        
        # 生成交易信號
        signals = []
        
        # 信號 1：黃金交叉
        if sma_20 > sma_50 if sma_50 is not None else False:
            signals.append("Golden_Cross")
        
        # 信號 2：RSI 正常
        if rsi and 30 < rsi < 70:
            signals.append("RSI_Normal")
        
        # 信號 3：RSI 反彈
        if rsi and 30 < rsi < 45:
            signals.append("RSI_Bounce")
        
        # 信號 4：成交量放大
        if current_volume > avg_volume_20 * 1.5:
            signals.append("Volume_Surge")
        
        # 信號 5：接近 52 週高點
        if last_close > high_52w * 0.95:
            signals.append("Near_52W_High")
        
        # 信號 6：從低位反彈
        if last_close > low_52w * 1.2:
            signals.append("From_Low_Rebound")
        
        # 篩選：至少 2 個信號
        if len(signals) >= 2:
            print(f"✅ {len(signals)} 信號")
            return {
                'Ticker': ticker,
                'Price': round(float(last_close), 2),
                'Change_%': round(change_pct, 2),
                'SMA_20': round(float(sma_20), 2),
                'SMA_50': round(float(sma_50), 2) if sma_50 is not None else "N/A",
                'RSI': round(rsi, 2) if rsi else "N/A",
                'MACD': round(macd, 4) if macd else "N/A",
                'Volume': int(current_volume),
                'Volume_Avg_20': int(avg_volume_20),
                '52W_High': round(float(high_52w), 2),
                '52W_Low': round(float(low_52w), 2),
                'Signal_Count': len(signals),
                'Signals': ", ".join(signals),
                'Scan_Time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        else:
            print(f"⏭️  {len(signals)} 信號")
            return None
        
    except Exception as e:
        print(f"❌ {str(e)[:20]}")
        return None

def main():
    print("\n" + "="*70)
    print("🚀 股票掃描器 v3.4 - 超極簡版本")
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
                signals_str = r['Signals'][:37] if isinstance(r['Signals'], str) else ""
                rsi_str = str(r['RSI']) if r['RSI'] != "N/A" else "N/A"
                print(f"{r['Ticker']:<8} ${r['Price']:<9.2f} {r['Change_%']:>8.2f}% {rsi_str:<7} {r['Signal_Count']:<6} {signals_str:<40}")
            
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
