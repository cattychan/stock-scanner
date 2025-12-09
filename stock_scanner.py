#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票掃描器 v3.5 - 穩定修正版
- 避免 pandas 布林歧義錯誤
- 所有技術指標都用 float 計算
"""

import yfinance as yf
import csv
from datetime import datetime
import os
from pathlib import Path

OUTPUT_FOLDER = "stock_data"

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
    "RIOT", "MARA", "CLSK", "HUT", "QRVO", "FLEX", "APH", "MRAM", "SEMI",
    "NVRI", "PSTG", "AKAM", "DOCU", "PEGA"
]


def safe_float(x, default=None):
    try:
        return float(x)
    except Exception:
        return default


def compute_rsi(close_series, period: int = 14):
    """用最基本方法計算 RSI，回傳 float 或 None。"""
    if len(close_series) < period + 1:
        return None
    delta = close_series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.tail(period).mean()
    avg_loss = loss.tail(period).mean()

    avg_gain = safe_float(avg_gain, 0.0)
    avg_loss = safe_float(avg_loss, 0.0)

    if avg_gain is None or avg_loss is None:
        return None
    if avg_loss == 0:
        if avg_gain > 0:
            return 100.0
        return 50.0

    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def scan_single_stock(ticker: str):
    print(f"  掃描 {ticker}...", end=" ")

    try:
        data = yf.download(ticker, period="3mo", progress=False)
    except Exception as e:
        print(f"❌ 下載失敗: {str(e)[:30]}")
        return None

    if data is None or data.empty or len(data) < 20:
        print("❌ 無數據或不足 20 天")
        return None

    close = data["Close"]
    volume = data["Volume"]

    last_close = safe_float(close.iloc[-1])
    prev_close = safe_float(close.iloc[-2])
    if last_close is None or prev_close is None or prev_close == 0:
        print("❌ 價格資料異常")
        return None

    current_volume = safe_float(volume.iloc[-1], 0.0)
    avg_volume_20 = safe_float(volume.tail(20).mean(), 0.0)

    change_pct = (last_close - prev_close) / prev_close * 100.0

    sma_20 = safe_float(close.tail(20).mean())
    sma_50 = safe_float(close.tail(50).mean()) if len(close) >= 50 else None

    rsi = compute_rsi(close, period=14)

    if len(close) >= 26:
        ema_12 = safe_float(close.tail(12).mean())
        ema_26 = safe_float(close.tail(26).mean())
        macd = ema_12 - ema_26 if ema_12 is not None and ema_26 is not None else None
    else:
        macd = None

    try:
        year_data = yf.download(ticker, period="1y", progress=False)
    except Exception:
        year_data = None

    if year_data is not None and not year_data.empty:
        high_52w = safe_float(year_data["High"].max(), last_close)
        low_52w = safe_float(year_data["Low"].min(), last_close)
    else:
        high_52w = last_close
        low_52w = last_close

    signals = []

    if sma_20 is not None and sma_50 is not None and sma_20 > sma_50:
        signals.append("Golden_Cross")

    if rsi is not None and 30 < rsi < 70:
        signals.append("RSI_Normal")

    if rsi is not None and 30 < rsi < 45:
        signals.append("RSI_Bounce")

    if avg_volume_20 and current_volume > avg_volume_20 * 1.5:
        signals.append("Volume_Surge")

    if high_52w and last_close > high_52w * 0.95:
        signals.append("Near_52W_High")

    if low_52w and last_close > low_52w * 1.2:
        signals.append("From_Low_Rebound")

    if len(signals) >= 2:
        print(f"✅ {len(signals)} 信號")
        return {
            "Ticker": ticker,
            "Price": round(last_close, 2),
            "Change_%": round(change_pct, 2),
            "SMA_20": round(sma_20, 2) if sma_20 is not None else "N/A",
            "SMA_50": round(sma_50, 2) if sma_50 is not None else "N/A",
            "RSI": round(rsi, 2) if rsi is not None else "N/A",
            "MACD": round(macd, 4) if macd is not None else "N/A",
            "Volume": int(current_volume),
            "Volume_Avg_20": int(avg_volume_20),
            "52W_High": round(high_52w, 2) if high_52w is not None else "N/A",
            "52W_Low": round(low_52w, 2) if low_52w is not None else "N/A",
            "Signal_Count": len(signals),
            "Signals": ", ".join(signals),
            "Scan_Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    else:
        print(f"⏭️  {len(signals)} 信號")
        return None


def main():
    print("\n" + "=" * 70)
    print("🚀 股票掃描器 v3.5 - 穩定修正版")
    print("=" * 70)
    print(f"掃描股票數量: {len(SCAN_TICKERS)}")
    print(f"掃描時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("篩選條件: 至少 2 個技術面信號")
    print("=" * 70 + "\n")

    Path(OUTPUT_FOLDER).mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(OUTPUT_FOLDER, f"scanner_results_{timestamp}.csv")

    results = []

    print("開始掃描...\n")
    for idx, ticker in enumerate(SCAN_TICKERS, 1):
        print(f"[{idx:3d}/{len(SCAN_TICKERS)}] {ticker:6s}", end=" ")
        res = scan_single_stock(ticker)
        if res:
            results.append(res)

    results.sort(key=lambda x: x["Signal_Count"], reverse=True)

    print("\n" + "=" * 70)

    if results:
        try:
            with open(output_file, "w", newline="", encoding="utf-8") as f:
                fieldnames = [
                    "Ticker",
                    "Price",
                    "Change_%",
                    "SMA_20",
                    "SMA_50",
                    "RSI",
                    "MACD",
                    "Volume",
                    "Volume_Avg_20",
                    "52W_High",
                    "52W_Low",
                    "Signal_Count",
                    "Signals",
                    "Scan_Time",
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results)

            print("✅ 掃描完成！")
            print(f"📊 找到 {len(results)} 支符合條件的股票")
            print(f"📁 結果已保存到: {output_file}")
            print("=" * 70 + "\n")

            print("🏆 TOP 10 候選股票:\n")
            print(f"{'Ticker':<8} {'Price':<10} {'Change%':<10} {'RSI':<8} {'Signal':<7} {'信號':<40}")
            print("-" * 90)

            for r in results[:10]:
                signals_str = (r["Signals"] or "")[:37]
                rsi_str = str(r["RSI"])
                print(
                    f"{r['Ticker']:<8} "
                    f"${r['Price']:<9.2f} "
                    f"{r['Change_%']:>8.2f}% "
                    f"{rsi_str:<7} "
                    f"{r['Signal_Count']:<6} "
                    f"{signals_str:<40}"
                )

            print("\n" + "=" * 70)
            if os.path.exists(output_file):
                size = os.path.getsize(output_file)
                print(f"✅ 文件驗證: {output_file} ({size} bytes)")

        except Exception as e:
            print(f"❌ 寫檔案失敗: {str(e)}")
    else:
        print("❌ 未找到符合條件的股票")

    print("\n📈 統計:")
    print(f"掃描的股票: {len(SCAN_TICKERS)}")
    print(f"符合條件: {len(results)}")
    if len(SCAN_TICKERS) > 0:
        print(f"成功率: {len(results) / len(SCAN_TICKERS) * 100:.1f}%")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
