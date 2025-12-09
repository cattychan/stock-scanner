#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票掃描器 v2.0 - 每日自動化技術面掃描
適用於「方案 C：終極混合系統」
功能：掃描美股大中型股票，篩選出符合技術條件的候選股票
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from pathlib import Path

# ==================== 配置區 ====================

# 掃描範圍：大中型股票 (市值 > $2B，500+ 支)
# 包含：S&P 500 + 部分 Nasdaq 100
SCAN_TICKERS = [
    # 科技板塊 (XLK)
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "QCOM", "AMD",
    "ADBE", "CRM", "NFLX", "INTC", "CSCO", "IBM", "ORCL", "MU", "PYPL", "SQ",
    
    # 健康護理 (XLV)
    "JNJ", "UNH", "PFE", "ABBV", "LLY", "MRK", "AZN", "TMO", "AMGN", "GILD",
    "CVS", "REGN", "BNTX", "VRTX", "ILMN", "DXCM", "BIO", "ALKS", "EXAS", "ZLAB",
    
    # 金融 (XLF)
    "JPM", "BAC", "WFC", "GS", "MS", "BLK", "BK", "PNC", "USB", "COF",
    "AXP", "MA", "V", "PYPL", "ICE", "CME", "COIN", "SOFI", "SQ", "DASH",
    
    # 能源 (XLE)
    "XOM", "CVX", "COP", "EOG", "MPC", "PSX", "VLO", "FANG", "OKE", "KMI",
    "MLR", "TPL", "CNX", "RRC", "DVN", "GUSH", "DRIP", "EQNR", "HES", "PXD",
    
    # 工業 (XLI)
    "BA", "CAT", "GE", "MMM", "RTX", "LMT", "NOC", "GD", "HWM", "CARR",
    "OTIS", "IEX", "EMR", "HON", "EW", "DOV", "ITW", "ROK", "CTAS", "ABM",
    
    # 消費必需品 (XLP)
    "KO", "PG", "WMT", "MO", "PEP", "CL", "KHC", "GIS", "K", "CAG",
    "ADM", "MDLZ", "PII", "HSY", "MKC", "CPB", "SJM", "STZ", "MNST", "USFD",
    
    # 消費自由裁量 (XLY)
    "AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "MES", "LOW", "TJX", "RCL",
    "CCL", "MAR", "RH", "ETSY", "ABNB", "SPOT", "GM", "F", "LUV", "DAL",
    
    # 房地產 (XLRE)
    "PLD", "AMT", "CCI", "EQIX", "DLR", "VICI", "WELL", "PSA", "EQR", "AVB",
    "ARE", "MAA", "UMH", "OSB", "XRT", "KRG", "MAC", "DEI", "CDP", "CONE",
    
    # 通訊服務 (XLC)
    "META", "GOOGL", "NFLX", "CMCSA", "DIS", "T", "VZ", "FOX", "FOXA", "PARA",
    "CHTR", "ATVI", "TTWO", "TAKE", "SEE", "VIAC", "IAC", "FUBO", "MSG", "MSGS",
    
    # 公用事業 (XLU)
    "NEE", "DUK", "SO", "AEP", "EXC", "PCG", "ED", "WEC", "XEL", "DTE",
]

# 篩選參數 (基於 v3.0 設計)
SMA_PERIOD_SHORT = 20
SMA_PERIOD_LONG = 50
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
VOLUME_MULTIPLIER = 1.2  # 成交量要 > 20日平均的 120%

# 輸出路徑
OUTPUT_FOLDER = "stock_data"
OUTPUT_FILE = os.path.join(OUTPUT_FOLDER, f"scanner_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

# ==================== 輔助函數 ====================

def create_output_folder():
    """創建輸出資料夾"""
    Path(OUTPUT_FOLDER).mkdir(exist_ok=True)

def calculate_sma(data, period):
    """計算簡單移動平均線"""
    return data['Close'].rolling(window=period).mean()

def calculate_ema(data, period):
    """計算指數移動平均線"""
    return data['Close'].ewm(span=period, adjust=False).mean()

def calculate_rsi(data, period=14):
    """計算相對強弱指數"""
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(data, fast=12, slow=26, signal=9):
    """計算 MACD 指標"""
    ema_fast = data['Close'].ewm(span=fast, adjust=False).mean()
    ema_slow = data['Close'].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def scan_single_stock(ticker):
    """
    掃描單支股票，檢查是否符合條件
    
    Returns:
        dict: 如果符合條件則返回結果，否則返回 None
    """
    try:
        # 下載數據
        data = yf.download(ticker, period="3mo", progress=False)
        if data.empty or len(data) < 30:
            return None
        
        # 確保數據按日期排序
        data = data.sort_index()
        
        # 計算指標
        sma_20 = calculate_sma(data, SMA_PERIOD_SHORT)
        sma_50 = calculate_sma(data, SMA_PERIOD_LONG)
        rsi = calculate_rsi(data, RSI_PERIOD)
        macd_line, signal_line, histogram = calculate_macd(data)
        
        # 獲取最新和前一日數據
        latest_idx = -1
        prev_idx = -2
        
        current_price = float(data['Close'].iloc[latest_idx])
        current_volume = float(data['Volume'].iloc[latest_idx])
        prev_price = float(data['Close'].iloc[prev_idx])
        
        current_sma_20 = float(sma_20.iloc[latest_idx]) if not pd.isna(sma_20.iloc[latest_idx]) else None
        current_sma_50 = float(sma_50.iloc[latest_idx]) if not pd.isna(sma_50.iloc[latest_idx]) else None
        prev_sma_20 = float(sma_20.iloc[prev_idx]) if not pd.isna(sma_20.iloc[prev_idx]) else None
        prev_sma_50 = float(sma_50.iloc[prev_idx]) if not pd.isna(sma_50.iloc[prev_idx]) else None
        
        current_rsi = float(rsi.iloc[latest_idx]) if not pd.isna(rsi.iloc[latest_idx]) else None
        current_macd_hist = float(histogram.iloc[latest_idx]) if not pd.isna(histogram.iloc[latest_idx]) else None
        prev_macd_hist = float(histogram.iloc[prev_idx]) if not pd.isna(histogram.iloc[prev_idx]) else None
        
        # 計算平均成交量
        avg_volume = float(data['Volume'].tail(20).mean())
        
        # 計算漲跌幅
        price_change_pct = ((current_price - prev_price) / prev_price * 100) if prev_price != 0 else 0
        
        # 計算 52 週高低點
        data_52w = yf.download(ticker, period="1y", progress=False)
        high_52w = float(data_52w['High'].max())
        low_52w = float(data_52w['Low'].min())
        
        # ========== 篩選條件 (v3.0) ==========
        signals = []
        
        # 條件 1：黃金交叉
        if current_sma_20 and current_sma_50 and prev_sma_20 and prev_sma_50:
            if current_sma_20 > current_sma_50 and prev_sma_20 <= prev_sma_50:
                signals.append("Golden_Cross")
        
        # 條件 2：RSI 反彈
        if current_rsi and current_rsi > RSI_OVERSOLD and current_rsi < RSI_OVERBOUGHT:
            signals.append("RSI_Normal")
        
        # 條件 3：MACD 翻正
        if current_macd_hist and prev_macd_hist:
            if current_macd_hist > 0 and prev_macd_hist <= 0:
                signals.append("MACD_Positive")
        
        # 條件 4：突破 52 週高點
        if current_price > high_52w * 0.98:  # 接近 52 週高點
            signals.append("Near_52W_High")
        
        # 條件 5：成交量放大
        if current_volume > avg_volume * VOLUME_MULTIPLIER:
            signals.append("Volume_Surge")
        
        # 只返回至少符合 2 個條件的股票
        if len(signals) >= 2:
            return {
                "Ticker": ticker,
                "Current_Price": round(current_price, 2),
                "Change_%": round(price_change_pct, 2),
                "SMA_20": round(current_sma_20, 2) if current_sma_20 else "N/A",
                "SMA_50": round(current_sma_50, 2) if current_sma_50 else "N/A",
                "RSI": round(current_rsi, 2) if current_rsi else "N/A",
                "MACD_Histogram": round(current_macd_hist, 4) if current_macd_hist else "N/A",
                "Volume_Surge": "Yes" if "Volume_Surge" in signals else "No",
                "52W_High": round(high_52w, 2),
                "52W_Low": round(low_52w, 2),
                "Signals": ", ".join(signals),
                "Signal_Count": len(signals),
                "Scan_Time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        
        return None
        
    except Exception as e:
        print(f"❌ {ticker} - 掃描失敗: {str(e)}")
        return None

# ==================== 主程序 ====================

def main():
    print("\n🚀 開始掃描美股...\n")
    print(f"掃描股票數量: {len(SCAN_TICKERS)}")
    print(f"掃描時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    create_output_folder()
    
    results = []
    successful_scans = 0
    failed_scans = 0
    
    for idx, ticker in enumerate(SCAN_TICKERS, 1):
        print(f"[{idx}/{len(SCAN_TICKERS)}] 正在掃描 {ticker}...", end=" ")
        result = scan_single_stock(ticker)
        
        if result:
            results.append(result)
            print(f"✅ 符合條件")
            successful_scans += 1
        else:
            print(f"⏭️  不符合")
            failed_scans += 1
    
    # 保存結果到 CSV
    if results:
        df = pd.DataFrame(results)
        # 按 Signal_Count 排序 (最強的訊號先)
        df = df.sort_values("Signal_Count", ascending=False)
        df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
        
        print(f"\n✅ 掃描完成！")
        print(f"📊 找到 {len(results)} 支符合條件的股票")
        print(f"📁 結果已保存到: {OUTPUT_FILE}\n")
        
        print("🏆 TOP 5 候選股票:")
        print(df[['Ticker', 'Current_Price', 'Change_%', 'Signal_Count', 'Signals']].head(5).to_string(index=False))
    else:
        print(f"\n⚠️  未找到符合條件的股票")
    
    print(f"\n📈 統計:")
    print(f"成功掃描: {successful_scans}")
    print(f"失敗或不符合: {failed_scans}")

if __name__ == "__main__":
    main()
