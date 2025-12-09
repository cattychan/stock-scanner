#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票掃描器 v3.2 - 完全重寫版本
修復了 yfinance DataFrame 兼容性問題
"""

import yfinance as yf
import csv
from datetime import datetime
import os
from pathlib import Path

OUTPUT_FOLDER = "stock_data"

# 擴展的 190+ 支股票清單（S&P 500 + 其他高流動性股票）
SCAN_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "JNJ", "V",
    "WMT", "JPM", "PG", "MA", "HD", "DIS", "MCD", "ADBE", "CRM", "NFLX",
    "INTC", "CSCO", "IBM", "ORCL", "MU", "PYPL", "SQ", "SHOP", "ASML", "AMD",
    "QCOM", "AVGO", "LRCX", "KLAC", "MCHP", "AMAT", "SNPS", "CDNS", "ADSK", "CPRT",
    "ANSS", "NOW", "ADP", "EXC", "NEE", "DUK", "SO", "AEP", "PCG", "ED",
    "WEC", "XEL", "CMS", "SRE", "PNW", "AWK", "NRG", "EVRG", "VRSN", "DDOG",
    "ROP", "ODFL", "MLR", "PAYX", "DECK", "ULTA", "NVR", "KBH", "PHM", "DHI",
    "LEN", "TPH", "SBNY", "UNM", "PGR", "HIG", "ALL", "AFG", "BHF", "RLI",
    "OC", "CNP", "IEX", "CPAY", "LEG", "MAS", "SKM", "JKHY", "ATGE", "VEEV",
    "APPF", "RBA", "CLOW", "FIX", "HY", "SMPL", "TPR", "BAC", "WFC",
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

def calculate_sma(prices, period):
    """計算簡單移動平均線"""
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period

def calculate_rsi(prices, period=14):
    """計算相對強弱指數 (RSI)"""
    if len(prices) < period + 1:
        return None
    
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100 if avg_gain > 0 else 50
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(prices, fast=12, slow=26):
    """計算 MACD"""
    if len(prices) < slow:
        return None
    
    ema_fast = calculate_sma(prices, fast)
    ema_slow = calculate_sma(prices, slow)
    
    if ema_fast is None or ema_slow is None:
        return None
    
    macd = ema_fast - ema_slow
    return macd

def scan_single_stock(ticker):
    """掃描單支股票"""
    try:
        print(f"  掃描 {ticker}...", end=" ")
        
        # 下載 3 個月數據 - 使用安全的方式
        data = yf.download(ticker, period="3mo", progress=False, auto_adjust=True)
        
        # 檢查數據是否為空或無效
        if data is None or data.empty:
            print("❌ 無數據")
            return None
        
        if len(data) < 20:
            print("❌ 數據不足")
            return None
        
        # 安全地提取數據 - 使用 .values 而不是 .tolist()
        try:
            close_prices = data['Close'].values.tolist()
            volumes = data['Volume'].values.tolist()
        except (AttributeError, KeyError) as e:
            print(f"❌ 提取數據失敗")
            return None
        
        if not close_prices or not volumes:
            print("❌ 數據為空")
            return None
        
        current_price = float(close_prices[-1])
        prev_price = float(close_prices[-2]) if len(close_prices) > 1 else current_price
        current_volume = int(volumes[-1])
        avg_volume = sum(volumes[-20:]) / 20
        
        # 計算漲跌幅
        if prev_price != 0:
            change_pct = ((current_price - prev_price) / prev_price * 100)
        else:
            change_pct = 0
        
        # 計算技術指標
        sma_20 = calculate_sma(close_prices, 20)
        sma_50 = calculate_sma(close_prices, 50)
        rsi = calculate_rsi(close_prices, 14)
        macd = calculate_macd(close_prices)
        
        # 52 週高低
        try:
            year_data = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
            if year_data is not None and not year_data.empty:
                high_52w = float(year_data['High'].values.max())
                low_52w = float(year_data['Low'].values.min())
            else:
                high_52w = current_price
                low_52w = current_price
        except:
            high_52w = current_price
            low_52w = current_price
        
        # 生成交易信號
        signals = []
        
        # 信號 1：黃金交叉（20日 > 50日 SMA）
        if sma_20 and sma_50 and sma_20 > sma_50:
            signals.append("Golden_Cross")
        
        # 信號 2：RSI 在合理範圍（30-70）
        if rsi and 30 < rsi < 70:
            signals.append("RSI_Normal")
        
        # 信號 3：RSI 反彈（接近超賣但已反彈）
        if rsi and 30 < rsi < 45:
            signals.append("RSI_Bounce")
        
        # 信號 4：成交量放大
        if current_volume > avg_volume * 1.5:
            signals.append("Volume_Surge")
        
        # 信號 5：接近 52 週高點
        if current_price > high_52w * 0.95:
            signals.append("Near_52W_High")
        
        # 信號 6：從低位反彈
        if current_price > low_52w * 1.2:
            signals.append("From_Low_Rebound")
        
        # 篩選條件：至少 2 個信號
        if len(signals) >= 2:
            print(f"✅ {len(signals)} 個信號")
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
        print(f"❌ {str(e)[:40]}")
        return None

def main():
    print("\n" + "="*70)
    print("🚀 股票掃描器 v3.2 - 完全重寫版本")
    print("="*70)
    print(f"掃描股票數量: {len(SCAN_TICKERS)}")
    print(f"掃描時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"篩選條件: 至少 2 個技術面信號")
    print("="*70 + "\n")
    
    # 創建資料夾
    Path(OUTPUT_FOLDER).mkdir(exist_ok=True)
    
    # 生成 CSV 檔案名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(OUTPUT_FOLDER, f"scanner_results_{timestamp}.csv")
    
    results = []
    
    print("開始掃描...\n")
    
    for idx, ticker in enumerate(SCAN_TICKERS, 1):
        print(f"[{idx:3d}/{len(SCAN_TICKERS)}] {ticker:6s}", end=" ")
        result = scan_single_stock(ticker)
        
        if result:
            results.append(result)
    
    # 按信號數排序（多信號優先）
    results.sort(key=lambda x: x['Signal_Count'], reverse=True)
    
    # 寫入 CSV
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
            
            print("🏆 TOP 10 候選股票（按信號數排序）:\n")
            print(f"{'Ticker':<8} {'Price':<10} {'Change%':<10} {'RSI':<8} {'Signal':<7} {'主要信號':<40}")
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
