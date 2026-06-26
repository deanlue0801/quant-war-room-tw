import streamlit as st
import pandas as pd
import numpy as np
import datetime
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from FinMind.data import DataLoader
from fugle_marketdata import RestClient 
import warnings

warnings.filterwarnings('ignore', category=FutureWarning)

# ==========================================
# 1. 網頁與 CSS 視覺設定
# ==========================================
st.set_page_config(page_title="終極量化戰情室", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .block-container { padding-top: 3rem !important; padding-bottom: 1rem !important; max-width: 98vw !important;}
    div[data-testid="stVerticalBlock"] > div { padding-bottom: 0.1rem; }
    div[data-testid="stDecoration"] { display: none; }
    
    .section-title { color: #8ab4f8; font-weight: bold; border-bottom: 1px solid #333; padding-bottom: 3px; margin-bottom: 5px; font-size: 1.05em; }
    .title-red { color: #FF4B4B !important; }
    .stamp-text { font-size: 24px; font-weight: bold; text-align: center; padding: 2px; border-radius: 5px; margin-bottom: 2px; }
    .text-sm { font-size: 0.85em; line-height: 1.3; }
    .metric-value { font-size: 1.2em; font-weight: bold; }
    
    .chip-table { width: 100%; border-collapse: collapse; margin-top: 5px; font-size: 0.9em; text-align: right; }
    .chip-table th { border-bottom: 1px solid #555; padding: 5px; color: #8ab4f8; text-align: right; font-weight: normal; }
    .chip-table td { padding: 5px; border-bottom: 1px dotted #333; }
    .chip-table .row-title { text-align: left; color: #ccc; }
    .text-red { color: #FF4B4B; }
    .text-green { color: #00FF00; }
    
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(255, 75, 75, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(255, 75, 75, 0); }
        100% { box-shadow: 0 0 0 0 rgba(255, 75, 75, 0); }
    }
    .s-class-horse {
        background: linear-gradient(45deg, #FF4B4B, #FF8C00);
        color: white; font-weight: bold; text-align: center; font-size: 1.5em;
        padding: 10px; border-radius: 10px; margin-bottom: 15px;
        animation: pulse 2s infinite; text-shadow: 1px 1px 2px black;
    }
    .potential-stars { font-size: 1.2em; color: #FFD700; }
    .zone-indicator { padding: 5px 10px; border-radius: 5px; font-weight: bold; text-align: center; margin-top: 5px; border: 1px solid #555;}
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; font-size: 1.2rem; }
    
    /* 666戰法專屬樣式 */
    .strategy-666-box { background: rgba(138, 180, 248, 0.05); border-left: 4px solid #8ab4f8; padding: 10px 15px; border-radius: 4px; margin-top: 10px;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🌟 全新統一 FinMind / Fugle 快取引擎
# ==========================================
try:
    FUGLE_API_KEY = st.secrets.get("FUGLE_API_KEY", "")
except:
    FUGLE_API_KEY = ""

try:
    FINMIND_TOKEN = st.secrets.get("FINMIND_TOKEN", "")
except:
    FINMIND_TOKEN = ""

@st.cache_data(ttl=86400)
def load_stock_dicts():
    try:
        dl_info = DataLoader()
        info_df = dl_info.taiwan_stock_info()
        id_to_name = dict(zip(info_df['stock_id'].astype(str), info_df['stock_name']))
        name_to_id = dict(zip(info_df['stock_name'], info_df['stock_id'].astype(str)))
        return id_to_name, name_to_id, info_df
    except:
        return {}, {}, pd.DataFrame()

stock_dict, name_to_id_dict, full_info_df = load_stock_dicts()

@st.cache_data(ttl=60, show_spinner=False)
def fetch_tech_data_fugle(ticker):
    try:
        client = RestClient(api_key=FUGLE_API_KEY)
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=360)
        
        kwargs = {
            "symbol": ticker,
            "timeframe": "D",
            "from": start_date.strftime('%Y-%m-%d'),
            "to": end_date.strftime('%Y-%m-%d')
        }
        
        candles = client.stock.historical.candles(**kwargs)
        df = pd.DataFrame(candles['data'])
        
        if not df.empty:
            df = df.rename(columns={'date': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
            df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None) 
            df = df.set_index('Date').sort_index()
        else:
            df = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'])
            
        try:
            quote = client.stock.intraday.quote(symbol=ticker)
            close_p = quote.get('closePrice') or (quote.get('lastTrade') or {}).get('price')
            if close_p is None:
                q_old = quote.get('data', {}).get('quote', {})
                close_p = (q_old.get('trade') or {}).get('price')
                open_p = (q_old.get('priceOpen') or {}).get('price') or close_p
                high_p = (q_old.get('priceHigh') or {}).get('price') or close_p
                low_p = (q_old.get('priceLow') or {}).get('price') or close_p
                vol_lots = (q_old.get('total') or {}).get('tradeVolume', 0)
            else:
                open_p = quote.get('openPrice') or close_p
                high_p = quote.get('highPrice') or close_p
                low_p = quote.get('lowPrice') or close_p
                vol_lots = (quote.get('total') or {}).get('tradeVolume', 0)
            
            if close_p is not None:
                today_ts = pd.Timestamp(end_date)
                vol_shares = vol_lots * 1000
                if df.empty or df.index[-1].date() != end_date:
                    today_df = pd.DataFrame([{'Date': today_ts, 'Open': open_p, 'High': high_p, 'Low': low_p, 'Close': close_p, 'Volume': vol_shares}]).set_index('Date')
                    df = pd.concat([df, today_df])
                else:
                    df.loc[today_ts, ['Open', 'High', 'Low', 'Close', 'Volume']] = [open_p, high_p, low_p, close_p, vol_shares]
        except Exception:
            pass 
        return df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_chip_data(ticker, start, end, token):
    dl = DataLoader()
    if token:
        try: dl.login_by_token(api_token=token)
        except: pass
    return dl.taiwan_stock_institutional_investors(stock_id=ticker, start_date=start, end_date=end)

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_margin_data(ticker, start, end, token):
    dl = DataLoader()
    if token:
        try: dl.login_by_token(api_token=token)
        except: pass
    return dl.taiwan_stock_margin_purchase_short_sale(stock_id=ticker, start_date=start, end_date=end)

def color_num(val):
    if val > 0: return f"<span class='text-red'>+{val:,.0f}</span>"
    elif val < 0: return f"<span class='text-green'>{val:,.0f}</span>"
    else: return "0"

# ==========================================
# 🌟 全市場掃描核心邏輯
# ==========================================
def run_market_screener(progress_bar, status_text):
    try:
        dl = DataLoader()
        if FINMIND_TOKEN:
            try: dl.login_by_token(api_token=FINMIND_TOKEN)
            except: pass
        client = RestClient(api_key=FUGLE_API_KEY)
        
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=10)
        
        status_text.write("⏳ 階段 1/2：從 FinMind 獲取全市場最新籌碼動向...")
        
        all_chip = dl.taiwan_stock_institutional_investors(stock_id="", start_date=str(start_date), end_date=str(end_date))
        if all_chip.empty: 
            status_text.write("🚨 獲取籌碼資料失敗。")
            return pd.DataFrame()
            
        all_chip['net_shares'] = (all_chip['buy'] - all_chip['sell']) / 1000
        all_chip['法人'] = all_chip['name'].apply(lambda n: '外資' if '外資' in str(n) or 'Foreign' in str(n) else ('投信' if '投信' in str(n) or 'Trust' in str(n) else ('自營' if '自營' in str(n) or 'Dealer' in str(n) else '其他')))
        all_chip = all_chip[all_chip['法人'] != '其他']
        
        latest_dates = sorted(all_chip['date'].unique())[-5:]
        chip_5d = all_chip[all_chip['date'].isin(latest_dates)]
        chip_summary = chip_5d.groupby('stock_id')['net_shares'].sum().reset_index()
        
        chip_summary = chip_summary.sort_values(by='net_shares', ascending=False)
        legal_targets = chip_summary[chip_summary['net_shares'] > 100].head(60)['stock_id'].tolist()
        
        if not legal_targets:
            status_text.write("🚨 查無法人買超標的。")
            return pd.DataFrame()

        strong_buy_list = []
        total_targets = len(legal_targets)
        
        for i, ticker in enumerate(legal_targets):
            progress = int((i + 1) / total_targets * 100)
            progress_bar.progress(progress)
            status_text.write(f"⏳ 階段 2/2：精密分析技術面... 掃描進度 {i+1}/{total_targets} ({stock_dict.get(ticker, ticker)})")
            
            try:
                tech_start = (end_date - datetime.timedelta(days=360)).strftime('%Y-%m-%d')
                candles = client.stock.historical.candles(symbol=ticker, timeframe="D", from_=tech_start, to=end_date.strftime('%Y-%m-%d'))
                df_tech = pd.DataFrame(candles['data'])
                
                time.sleep(0.8)
                
                if df_tech.empty or len(df_tech) < 60: continue
                df_tech = df_tech.sort_values('date')
                df_tech['volume'] = df_tech['volume'] / 1000
                
                latest_close = df_tech['close'].iloc[-1]
                ma20 = df_tech['close'].rolling(20).mean().iloc[-1]
                ma60 = df_tech['close'].rolling(60).mean().iloc[-1]
                latest_vol = df_tech['volume'].iloc[-1]
                avg_vol_5 = df_tech['volume'].rolling(5).mean().iloc[-1]
                high_52w = df_tech['high'].max()
                low_52w = df_tech['low'].min()
                base_pct = ((latest_close - low_52w) / (high_52w - low_52w)) * 100 if high_52w != low_52w else 50
                
                chip_val = chip_summary[chip_summary['stock_id'] == ticker]['net_shares'].values[0]
                
                cond_base = base_pct < 60
                cond_trend = (latest_close > ma20) and (latest_close > ma60)
                cond_vol = latest_vol > (avg_vol_5 * 1.5)
                cond_chip = chip_val > 300
                
                score = sum([cond_base, cond_trend, cond_vol, cond_chip])
                
                if score >= 2 and latest_vol > 500:
                    name = stock_dict.get(ticker, ticker)
                    if score == 4: grade = "🔥 S級 (滿分)"
                    elif score == 3: grade = "🚀 A級 (強勢)"
                    else: grade = "🟢 B級 (試單)"
                    
                    matched = []
                    if cond_base: matched.append("低基期")
                    if cond_trend: matched.append("站上均線")
                    if cond_vol: matched.append("量能點火")
                    if cond_chip: matched.append("法人大買")
                    
                    strong_buy_list.append({
                        "代號": ticker, "名稱": name, "等級": grade, "分數": score, 
                        "收盤價": latest_close, "位階": f"{base_pct:.1f}%", 
                        "成交量(張)": int(latest_vol), 
                        "5日法人買超": int(chip_val),
                        "符合條件": ", ".join(matched)
                    })
            except:
                continue
                
        df_result = pd.DataFrame(strong_buy_list)
        if not df_result.empty:
            df_result = df_result.sort_values(by=["分數", "5日法人買超"], ascending=[False, False])
            
        status_text.write("✅ 掃描完成！")
        progress_bar.empty() 
        return df_result
    except Exception as e:
        status_text.write(f"🚨 掃描過程發生錯誤: {e}")
        return pd.DataFrame()


# ==========================================
# 2. 雙分頁架構建立
# ==========================================
tab_monitor, tab_screener = st.tabs(["📊 單檔戰情解析 (含紀律訊號)", "🏆 全市場黑馬分級掃描"])

# ==========================================
# TAB 1: 單檔戰情解析
# ==========================================
with tab_monitor:
    if 'search_history' not in st.session_state:
        st.session_state['search_history'] = []
        
    def add_to_history(ticker):
        if ticker and ticker not in st.session_state['search_history']:
            st.session_state['search_history'].insert(0, ticker)
            if len(st.session_state['search_history']) > 8:
                st.session_state['search_history'].pop()

    # --- 修改點 1：使用 st.form 包覆輸入區塊，讓按 Enter 就能送出 ---
    with st.form(key='search_form', clear_on_submit=False):
        col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1.5, 1.5, 6])
        with col_ctrl1:
            raw_input = st.text_input("搜尋", "", label_visibility="collapsed", placeholder="輸入代號或名稱並按 Enter")
        with col_ctrl2:
            # 將原本的 button 改為 form_submit_button
            analyze_btn = st.form_submit_button("🔥 啟動全板面解析", use_container_width=True)
        with col_ctrl3:
            st.markdown("<div style='margin-top: 8px; font-size: 0.9em; color:gray;'>※ 搭載 Fugle (盤中即時) + FinMind 雙引擎 + 智能畫線視覺模組</div>", unsafe_allow_html=True)

    if st.session_state['search_history']:
        st.markdown("<div style='font-size: 0.8em; color: gray; margin-bottom: 5px;'>🕒 最近搜尋紀錄 (點擊直接分析)：</div>", unsafe_allow_html=True)
        hist_cols = st.columns(len(st.session_state['search_history']) + 1)
        
        clicked_hist = None
        for i, hist_ticker in enumerate(st.session_state['search_history']):
            hist_name = stock_dict.get(hist_ticker, "")
            btn_label = f"{hist_ticker} {hist_name}" if hist_name else hist_ticker
            if hist_cols[i].button(btn_label, key=f"hist_btn_{hist_ticker}"):
                clicked_hist = hist_ticker
    else:
        clicked_hist = None

    search_term = ""
    if st.session_state.get('run_cross_tab_analysis') and st.session_state.get('target_ticker'):
        search_term = st.session_state['target_ticker']
        st.session_state['run_cross_tab_analysis'] = False 
    elif clicked_hist:
        search_term = clicked_hist
    elif analyze_btn and raw_input:
        search_term = raw_input.strip()

    if search_term:
        raw_ticker = name_to_id_dict.get(search_term, search_term) if search_term not in stock_dict else search_term
        stock_name = stock_dict.get(raw_ticker, "")
        display_title = f"{raw_ticker} {stock_name}" if stock_name else raw_ticker
        
        add_to_history(raw_ticker)
        
        with st.spinner(f'鎖定目標 [{display_title}] ... 啟動戰情解析中...'):
            try:
                # --- [技術面] ---
                df_full = fetch_tech_data_fugle(raw_ticker).copy()
                
                if len(df_full) < 60: # 修改：為了計算60MA與KD60，確保資料量足夠
                    st.error(f"🚨 無法取得 [{display_title}] 足夠的報價資料 (小於60天)，請確認 API 或標的狀態。")
                    st.stop()
                    
                df_full.index = df_full.index.tz_localize(None)
                df_full['Volume'] = df_full['Volume'] / 1000
                
                high_52w = df_full['High'].max()
                low_52w = df_full['Low'].min()
                latest_close = df_full['Close'].iloc[-1]
                base_percentile = ((latest_close - low_52w) / (high_52w - low_52w)) * 100 if (high_52w - low_52w) != 0 else 50

                df_full['MA5'] = df_full['Close'].rolling(window=5).mean()
                df_full['MA20'] = df_full['Close'].rolling(window=20).mean()
                df_full['MA60'] = df_full['Close'].rolling(window=60).mean()
                
                delta = df_full['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                df_full['RSI'] = 100 - (100 / (1 + gain / loss))

                exp1 = df_full['Close'].ewm(span=12, adjust=False).mean()
                exp2 = df_full['Close'].ewm(span=26, adjust=False).mean()
                df_full['MACD'] = exp1 - exp2
                df_full['Signal'] = df_full['MACD'].ewm(span=9, adjust=False).mean()
                df_full['OSC'] = df_full['MACD'] - df_full['Signal']

                # 一般 KD(9,3,3)
                low_min = df_full['Low'].rolling(window=9).min()
                high_max = df_full['High'].rolling(window=9).max()
                df_full['RSV'] = 100 * ((df_full['Close'] - low_min) / (high_max - low_min))
                df_full['K'] = df_full['RSV'].ewm(com=2, adjust=False).mean()
                df_full['D'] = df_full['K'].ewm(com=2, adjust=False).mean()

                # --- 修改點 2：加入 666戰法專用 KD(60,3,3) 計算 ---
                low_min_60 = df_full['Low'].rolling(window=60).min()
                high_max_60 = df_full['High'].rolling(window=60).max()
                df_full['RSV_60'] = 100 * ((df_full['Close'] - low_min_60) / (high_max_60 - low_min_60))
                # com=2 相當於 span=5, 在 ewm 的平滑上近似於傳統的 3 天平均
                df_full['K_60'] = df_full['RSV_60'].ewm(com=2, adjust=False).mean()
                df_full['D_60'] = df_full['K_60'].ewm(com=2, adjust=False).mean()

                df = df_full.tail(120).copy()
                
                # --- 指標狀態邏輯分析 ---
                curr_k, curr_d = df['K'].iloc[-1], df['D'].iloc[-1]
                prev_k, prev_d = df['K'].iloc[-2], df['D'].iloc[-2]
                kd_status = "中性"; kd_color = "gray"
                if curr_k > curr_d and prev_k <= prev_d: kd_status = "黃金交叉"; kd_color = "#FF4B4B"
                elif curr_k < curr_d and prev_k >= prev_d: kd_status = "死亡交叉"; kd_color = "#00FF00"
                elif curr_k > 80: kd_status = "高檔鈍化"; kd_color = "#FF4B4B"
                elif curr_k < 20: kd_status = "低檔背離"; kd_color = "#00FF00"

                osc, prev_osc = df['OSC'].iloc[-1], df['OSC'].iloc[-2]
                macd_status = "盤整"; macd_color = "gray"
                if osc > 0 and osc > prev_osc: macd_status = "多頭增溫"; macd_color = "#FF4B4B"
                elif osc > 0 and osc < prev_osc: macd_status = "多頭縮減"; macd_color = "gray"
                elif osc < 0 and osc < prev_osc: macd_status = "空頭擴散"; macd_color = "#00FF00"
                elif osc < 0 and osc > prev_osc: macd_status = "空頭收斂"; macd_color = "#FF4B4B"

                rsi_val = df['RSI'].iloc[-1]
                rsi_status = "盤整"; rsi_color = "gray"
                if rsi_val > 70: rsi_status = "超買警戒"; rsi_color = "#00FF00"
                elif rsi_val < 30: rsi_status = "超跌區"; rsi_color = "#FF4B4B"
                elif rsi_val > 50: rsi_status = "強勢區"; rsi_color = "#FF4B4B"
                
                prev_close = df['Close'].iloc[-2]
                latest_vol = df['Volume'].iloc[-1]
                avg_vol_5 = df['Volume'].rolling(5).mean().iloc[-1]
                
                price_change = latest_close - prev_close
                change_pct = (price_change / prev_close) * 100
                vol_change_pct = ((latest_vol - avg_vol_5) / avg_vol_5) * 100 if avg_vol_5 > 0 else 0
                
                color = "#FF4B4B" if price_change >= 0 else "#00FF00"
                sign = "▲" if price_change >= 0 else "▼"
                bias_20 = ((latest_close - df['MA20'].iloc[-1]) / df['MA20'].iloc[-1]) * 100
                
                price_pressure = df['High'].rolling(20).max().iloc[-1]
                price_support = df['MA20'].iloc[-1]
                price_strong_support = df['Low'].rolling(20).min().iloc[-1]
                
                last_date = df.index[-1]
                date_str = f"{last_date.strftime('%m/%d')}"
                x_dates = df.index.strftime('%m-%d')

                # --- 智慧趨勢線演算法 ---
                order = 5 
                local_highs, local_lows = [], []
                for i in range(order, len(df) - order):
                    if df['High'].iloc[i] == max(df['High'].iloc[i-order:i+order+1]): local_highs.append((i, df['High'].iloc[i]))
                    if df['Low'].iloc[i] == min(df['Low'].iloc[i-order:i+order+1]): local_lows.append((i, df['Low'].iloc[i]))

                trendline_type, trend_x, trend_y, trend_color = "無明顯趨勢線", [], [], ""
                if latest_close < df['MA20'].iloc[-1] and len(local_highs) >= 2:
                    idx1, y1 = local_highs[-2]
                    idx2, y2 = local_highs[-1]
                    if y2 < y1: 
                        slope = (y2 - y1) / (idx2 - idx1)
                        idx_start, idx_end = max(0, idx1 - 20), len(df) - 1
                        trend_x, trend_y = [x_dates[idx_start], x_dates[idx_end]], [y1 - slope * (idx1 - idx_start), y2 + slope * (idx_end - idx2)]
                        trend_color, trendline_type = "orange", "下降壓力線"
                elif trendline_type == "無明顯趨勢線" and len(local_lows) >= 2:
                    idx1, y1 = local_lows[-2]
                    idx2, y2 = local_lows[-1]
                    if y2 > y1: 
                        slope = (y2 - y1) / (idx2 - idx1)
                        idx_start, idx_end = max(0, idx1 - 25), len(df) - 1
                        trend_x, trend_y = [x_dates[idx_start], x_dates[idx_end]], [y1 - slope * (idx1 - idx_start), y2 + slope * (idx_end - idx2)]
                        trend_color, trendline_type = "yellow", "上升支撐線"

                # --- [法人籌碼面] ---
                end_date_chip = datetime.date.today()
                start_date_chip = end_date_chip - datetime.timedelta(days=45)
                df_chip = fetch_chip_data(raw_ticker, str(start_date_chip), str(end_date_chip), FINMIND_TOKEN).copy()
                
                chip_sum_10 = {"外資": 0, "投信": 0, "自營商": 0, "合計": 0}
                chip_sum_5 = {"合計": 0, "外資": 0, "投信": 0, "自營商": 0}
                today_chip = {"外資": 0, "投信": 0, "自營商": 0, "合計": 0}
                chip_latest_date_str = "N/A"
                
                if not df_chip.empty:
                    df_chip['買賣超(張)'] = (df_chip['buy'] - df_chip['sell']) / 1000
                    df_chip['法人'] = df_chip['name'].apply(lambda n: '外資' if '外資' in str(n) or 'Foreign' in str(n) else ('投信' if '投信' in str(n) or 'Trust' in str(n) else ('自營商' if '自營商' in str(n) or 'Dealer' in str(n) else '其他')))
                    df_chip = df_chip[df_chip['法人'] != '其他']
                    pivot_df = df_chip.pivot_table(index='date', columns='法人', values='買賣超(張)', aggfunc='sum').fillna(0).sort_index()
                    pivot_df.index = pd.to_datetime(pivot_df.index)
                    
                    if len(pivot_df) > 0:
                        chip_latest_date_str = pivot_df.index[-1].strftime('%m/%d')
                        last_10, last_5, last_1 = pivot_df.tail(10), pivot_df.tail(5), pivot_df.tail(1)
                        def safe_sum(df_t, col): return df_t[col].sum() if col in df_t.columns else 0
                        chip_sum_10['外資'], chip_sum_10['投信'], chip_sum_10['自營商'] = safe_sum(last_10, '外資'), safe_sum(last_10, '投信'), safe_sum(last_10, '自營商')
                        chip_sum_10['合計'] = chip_sum_10['外資'] + chip_sum_10['投信'] + chip_sum_10['自營商']
                        chip_sum_5['外資'], chip_sum_5['投信'], chip_sum_5['自營商'] = safe_sum(last_5, '外資'), safe_sum(last_5, '投信'), safe_sum(last_5, '自營商')
                        chip_sum_5['合計'] = chip_sum_5['外資'] + chip_sum_5['投信'] + chip_sum_5['自營商']
                        today_chip['外資'], today_chip['投信'], today_chip['自營商'] = safe_sum(last_1, '外資'), safe_sum(last_1, '投信'), safe_sum(last_1, '自營商')
                        today_chip['合計'] = today_chip['外資'] + today_chip['投信'] + today_chip['自營商']

                # --- [融資融券散戶籌碼面] ---
                df_margin = fetch_margin_data(raw_ticker, str(start_date_chip), str(end_date_chip), FINMIND_TOKEN).copy()
                margin_latest_balance, margin_change, short_latest_balance, short_change = 0, 0, 0, 0
                margin_latest_date_str = "N/A"
                
                if not df_margin.empty:
                    df_margin['date'] = pd.to_datetime(df_margin['date'])
                    df_margin = df_margin.set_index('date').sort_index()
                    if len(df_margin) > 0: margin_latest_date_str = df_margin.index[-1].strftime('%m/%d')
                    if 'MarginPurchaseTodayBalance' in df_margin.columns and len(df_margin) > 0:
                        margin_latest_balance = df_margin['MarginPurchaseTodayBalance'].iloc[-1]
                        if len(df_margin) > 1: margin_change = margin_latest_balance - df_margin['MarginPurchaseTodayBalance'].iloc[-2]
                    if 'ShortSaleTodayBalance' in df_margin.columns and len(df_margin) > 0:
                        short_latest_balance = df_margin['ShortSaleTodayBalance'].iloc[-1]
                        if len(df_margin) > 1: short_change = short_latest_balance - df_margin['ShortSaleTodayBalance'].iloc[-2]

                # --- 散戶動向判定 ---
                margin_status_text, margin_status_color = "無明顯異常 (資券平穩)", "gray"
                if price_change > 0:
                    if margin_change < 0 and short_change > 0: margin_status_text, margin_status_color = "🔥 軋空成形 (資減券增)", "#FF4B4B"
                    elif margin_change > 0 and short_change < 0: margin_status_text, margin_status_color = "⚠️ 散戶追高 (資增券減)", "#FFA500"
                    elif margin_change > 0 and short_change > 0: margin_status_text, margin_status_color = "⚔️ 多空交戰 (資券同增)", "#FFFF00"
                elif price_change < 0:
                    if margin_change > 0 and short_change <= 0: margin_status_text, margin_status_color = "🚨 散戶接刀 (資增券減/平)", "#00FF00"
                    elif margin_change < 0 and short_change > 0: margin_status_text, margin_status_color = "📉 順勢殺盤 (資減券增)", "#00FF00"
                    elif margin_change < 0 and change_pct < -3: margin_status_text, margin_status_color = "🩸 融資停損斷頭 (見底訊號)", "#FF4B4B"

                # --- 黑馬潛力 ---
                black_horse_score = 0; bh_reasons = []
                if base_percentile < 60: black_horse_score += 1; bh_reasons.append("✅ 基期優勢 (未過熱)")
                if latest_close > df['MA20'].iloc[-1] and latest_close > df['MA60'].iloc[-1]: black_horse_score += 1; bh_reasons.append("✅ 趨勢轉強 (站上均線)")
                if latest_vol > avg_vol_5 * 1.5: black_horse_score += 1; bh_reasons.append("✅ 量能點火 (帶量突破)")
                if chip_sum_5['合計'] > 300: black_horse_score += 1; bh_reasons.append("✅ 籌碼進駐 (法人買超)")

                win_rate = 50
                if latest_close > df['MA20'].iloc[-1]: win_rate += 15
                else: win_rate -= 15
                if df['MACD'].iloc[-1] > df['Signal'].iloc[-1]: win_rate += 10
                if chip_sum_10['合計'] > 0: win_rate += 15
                if bias_20 > 8 or df['K'].iloc[-1] > 80: win_rate -= 15
                if base_percentile > 80: win_rate -= 10
                if base_percentile < 20 and df['MACD'].iloc[-1] > df['Signal'].iloc[-1]: win_rate += 10
                win_rate = max(0, min(100, win_rate))

                zone_text, zone_color_css = "", ""
                if latest_close >= price_pressure * 0.98: zone_text, zone_color_css = "🚀 突破區 (挑戰前高，最強勢)", "color: #FF4B4B; border-color: #FF4B4B;"
                elif price_support <= latest_close < price_pressure * 0.98: zone_text, zone_color_css = "📈 震盪多頭區 (逢回佈局)", "color: #FFA500; border-color: #FFA500;"
                elif price_strong_support <= latest_close < price_support: zone_text, zone_color_css = "⚠️ 弱勢整理區 (跌破月線)", "color: #FFFF00; border-color: #FFFF00;"
                else: zone_text, zone_color_css = "🚨 破底轉空區 (風險極高)", "color: #00FF00; border-color: #00FF00;"

                # --- 畫面渲染 ---
                if black_horse_score == 4: st.markdown("<div class='s-class-horse'>🔥 S 級黑馬訊號發動：量價籌碼完美共振！ 🔥</div>", unsafe_allow_html=True)
                stars = "★" * black_horse_score + "☆" * (4 - black_horse_score)
                st.markdown(f"<h3 style='margin-bottom:0;'>{display_title} &nbsp;&nbsp; <span style='font-size: 0.5em; color: #8ab4f8; border: 1px solid #333; padding: 2px 8px; border-radius: 5px; vertical-align: middle;'>{date_str}</span> &nbsp;&nbsp; | &nbsp;&nbsp; 爆發潛力 <span class='potential-stars'>{stars}</span></h3>", unsafe_allow_html=True)
                st.markdown(f"<div class='text-sm' style='margin-bottom: 5px;'>收盤 <span style='color:{color}; font-weight:bold;'>{latest_close:.2f}</span> &nbsp;&nbsp; 漲跌 <span style='color:{color};'>{sign} {abs(price_change):.2f} ({change_pct:.2f}%)</span> &nbsp;&nbsp; | &nbsp;&nbsp; 成交量 <b>{latest_vol:,.0f}</b> 張</div>", unsafe_allow_html=True)
                st.markdown("<hr style='margin: 0 0 10px 0; padding: 0;'>", unsafe_allow_html=True)

                col_left, col_mid, col_r1, col_r2 = st.columns([1.6, 1.1, 0.85, 0.85])

                with col_left:
                    with st.container(border=True):
                        st.markdown('<div class="section-title">技術面與支撐壓力可視化</div>', unsafe_allow_html=True)
                        fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.015, row_heights=[0.4, 0.15, 0.15, 0.15, 0.15])
                        
                        fig.add_trace(go.Candlestick(x=x_dates, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線", increasing_line_color='#FF4B4B', decreasing_line_color='#00FF00'), row=1, col=1)
                        fig.add_trace(go.Scatter(x=x_dates, y=df['MA20'], line=dict(color='cyan', width=1.5), name='MA20(月線)'), row=1, col=1)
                        fig.add_trace(go.Scatter(x=x_dates, y=df['MA60'], line=dict(color='magenta', width=1), name='MA60(季線)'), row=1, col=1)
                        
                        fig.add_hrect(y0=price_pressure*0.97, y1=price_pressure, line_width=0, fillcolor="red", opacity=0.15, row=1, col=1, annotation_text=f"近期高點壓力區 ({price_pressure:.1f})", annotation_position="top left", annotation_font_color="red")
                        fig.add_hrect(y0=price_strong_support, y1=price_support, line_width=0, fillcolor="green", opacity=0.15, row=1, col=1, annotation_text=f"強勁支撐區 ({price_strong_support:.1f} - {price_support:.1f})", annotation_position="bottom right", annotation_font_color="lightgreen")
                        
                        if trend_x:
                            fig.add_trace(go.Scatter(x=trend_x, y=trend_y, mode='lines', line=dict(color=trend_color, width=3, dash='dashdot'), name=trendline_type), row=1, col=1)
                            fig.add_annotation(x=trend_x[0], y=trend_y[0], text=f" {trendline_type} ", showarrow=True, arrowhead=1, ax=40, ay=-30, font=dict(color=trend_color, size=11), bgcolor="rgba(0,0,0,0.6)", bordercolor=trend_color, borderwidth=1, row=1, col=1)

                        colors_vol = ['#FF4B4B' if row['Close'] >= row['Open'] else '#00FF00' for index, row in df.iterrows()]
                        fig.add_trace(go.Bar(x=x_dates, y=df['Volume'], marker_color=colors_vol, name="成交量(張)"), row=2, col=1)
                        
                        vol_text = "正常盤整"
                        if price_change > 0 and vol_change_pct > 10: vol_text = "多頭量增價漲"
                        elif price_change > 0 and vol_change_pct < -10: vol_text = "價漲量縮背離"
                        elif price_change < 0 and vol_change_pct > 10: vol_text = "帶量下殺賣壓"
                        fig.add_annotation(x=x_dates[-1], y=df['Volume'].iloc[-1], text=f"量能: {vol_text}", showarrow=True, arrowhead=2, arrowsize=1, ax=-50, ay=-40, bgcolor="rgba(0,0,0,0.8)", bordercolor="yellow", borderwidth=1, font=dict(color="yellow", size=10), row=2, col=1)
                        
                        colors_macd = ['#FF4B4B' if val >= 0 else '#00FF00' for val in df['OSC']]
                        fig.add_trace(go.Bar(x=x_dates, y=df['OSC'], marker_color=colors_macd, name="MACD柱"), row=3, col=1)
                        fig.add_trace(go.Scatter(x=x_dates, y=df['MACD'], line=dict(color='white', width=1), name='MACD'), row=3, col=1)
                        fig.add_trace(go.Scatter(x=x_dates, y=df['Signal'], line=dict(color='yellow', width=1), name='Signal'), row=3, col=1)
                        
                        fig.add_trace(go.Scatter(x=x_dates, y=df['K'], line=dict(color='yellow', width=1), name='K'), row=4, col=1)
                        fig.add_trace(go.Scatter(x=x_dates, y=df['D'], line=dict(color='cyan', width=1), name='D'), row=4, col=1)
                        fig.add_hline(y=80, line_dash="dot", line_color="red", row=4, col=1)
                        fig.add_hline(y=20, line_dash="dot", line_color="green", row=4, col=1)
                        
                        fig.add_trace(go.Scatter(x=x_dates, y=df['RSI'], line=dict(color='magenta', width=1), name='RSI'), row=5, col=1)
                        fig.add_hline(y=70, line_dash="dot", line_color="red", row=5, col=1)
                        fig.add_hline(y=30, line_dash="dot", line_color="green", row=5, col=1)
                        
                        fig.update_xaxes(type='category', nticks=10, showgrid=True, gridwidth=1, gridcolor='#333')
                        fig.update_layout(height=550, margin=dict(l=0, r=0, t=5, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False, xaxis_rangeslider_visible=False)
                        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#333')
                        st.plotly_chart(fig, use_container_width=True)
                        
                        st.markdown(f"""
                        <div style="display: flex; justify-content: space-between; background: rgba(255,255,255,0.05); padding: 8px; border-radius: 5px; margin-top: 5px; margin-bottom: 5px; border: 1px solid #333;">
                            <div><span style="font-size: 0.85em; color:gray;">KD(9):</span> <span style="font-size: 0.85em; font-weight: bold; color: {kd_color};">{kd_status} ({curr_k:.1f})</span></div>
                            <div><span style="font-size: 0.85em; color:gray;">MACD:</span> <span style="font-size: 0.85em; font-weight: bold; color: {macd_color};">{macd_status}</span></div>
                            <div><span style="font-size: 0.85em; color:gray;">RSI:</span> <span style="font-size: 0.85em; font-weight: bold; color: {rsi_color};">{rsi_status} ({rsi_val:.1f})</span></div>
                        </div>
                        """, unsafe_allow_html=True)

                    with st.container(border=True):
                        st.markdown(f"<div class='zone-indicator' style='{zone_color_css}'>🎯 目前位階：{zone_text}</div>", unsafe_allow_html=True)

                with col_mid:
                    with st.container(border=True):
                        st.markdown('<div class="section-title">法人與散戶籌碼動向</div>', unsafe_allow_html=True)
                        if not df_chip.empty:
                            last_20_chips = pivot_df.tail(20)
                            display_cols = [col for col in ['外資', '投信', '自營商'] if col in pivot_df.columns]
                            chip_dates_formatted = [d.strftime('%m-%d') for d in last_20_chips.index]
                            price_dict = dict(zip(x_dates, df['Close']))
                            chip_close_prices = [price_dict.get(d, None) for d in chip_dates_formatted]
                            
                            fig_chip = make_subplots(specs=[[{"secondary_y": True}]])
                            colors_chip = {'外資': '#8ab4f8', '投信': '#FF4B4B', '自營商': '#00FF00'}
                            for col in display_cols:
                                fig_chip.add_trace(go.Bar(x=chip_dates_formatted, y=last_20_chips[col], name=col, marker_color=colors_chip.get(col, 'white')), secondary_y=False)
                            fig_chip.add_trace(go.Scatter(x=chip_dates_formatted, y=chip_close_prices, name='收盤價', line=dict(color='yellow', width=2), mode='lines+markers', marker=dict(size=4)), secondary_y=True)
                            fig_chip.update_layout(height=200, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', barmode='group', legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1, font=dict(size=10)))
                            fig_chip.update_xaxes(type='category', nticks=6, showgrid=False)
                            fig_chip.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#333', secondary_y=False)
                            fig_chip.update_yaxes(showgrid=False, secondary_y=True)
                            st.plotly_chart(fig_chip, use_container_width=True)
                            
                            html_table = f"""
                            <table class="chip-table">
                                <tr><th></th><th>外資</th><th>投信</th><th>自營商</th><th>合計</th></tr>
                                <tr><td class="row-title">最新 ({chip_latest_date_str})</td><td>{color_num(today_chip['外資'])}</td><td>{color_num(today_chip['投信'])}</td><td>{color_num(today_chip['自營商'])}</td><td>{color_num(today_chip['合計'])}</td></tr>
                                <tr><td class="row-title">近5日</td><td>{color_num(chip_sum_5['外資'])}</td><td>{color_num(chip_sum_5['投信'])}</td><td>{color_num(chip_sum_5['自營商'])}</td><td>{color_num(chip_sum_5['合計'])}</td></tr>
                                <tr><td class="row-title" style="border-top: 1px solid #555; color:#FFA500;">📌 散戶融資</td><td colspan="2" style="border-top: 1px solid #555; text-align:center;">餘額: <b>{margin_latest_balance:,.0f}</b></td><td colspan="2" style="border-top: 1px solid #555; text-align:center;">增減 ({margin_latest_date_str}): {color_num(margin_change)}</td></tr>
                                <tr><td class="row-title" style="color:#00FF00;">📌 散戶融券</td><td colspan="2" style="text-align:center;">餘額: <b>{short_latest_balance:,.0f}</b></td><td colspan="2" style="text-align:center;">增減 ({margin_latest_date_str}): {color_num(short_change)}</td></tr>
                                <tr><td class="row-title" style="border-top: 1px dotted #555; color:#fff;">🎯 散戶狀態</td><td colspan="4" style="border-top: 1px dotted #555; text-align:center; font-weight:bold; color:{margin_status_color};">{margin_status_text}</td></tr>
                            </table>
                            """
                            st.markdown(html_table, unsafe_allow_html=True)
                            st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
                            st.markdown('<div class="section-title" style="font-size:0.9em; border:none; margin-bottom:0;">主力進出分析 (近10日多空)</div>', unsafe_allow_html=True)
                            col_c1, col_c2 = st.columns(2)
                            col_c1.markdown(f"<div class='text-sm'>最新主力動向 ({chip_latest_date_str})</div><div class='metric-value'>{color_num(today_chip['合計'])}</div>", unsafe_allow_html=True)
                            col_c2.markdown(f"<div class='text-sm'>10日波段籌碼</div><div class='metric-value'>{color_num(chip_sum_10['合計'])}</div>", unsafe_allow_html=True)
                        else:
                            st.warning("查無籌碼資料")

                with col_r1:
                    with st.container(border=True):
                        st.markdown('<div class="section-title">黑馬潛力雷達</div>', unsafe_allow_html=True)
                        if bh_reasons:
                            for reason in bh_reasons: st.markdown(f"<div class='text-sm'>{reason}</div>", unsafe_allow_html=True)
                        else: st.markdown("<div class='text-sm'>⏳ 尚未浮現攻擊訊號</div>", unsafe_allow_html=True)

                    with st.container(border=True):
                        st.markdown('<div class="section-title">短線進場勝率</div>', unsafe_allow_html=True)
                        fig_gauge = go.Figure(go.Indicator(
                            mode = "gauge+number", value = win_rate, number={'suffix': "%", 'font':{'size': 24}}, domain = {'x': [0, 1], 'y': [0, 1]},
                            gauge = {'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"}, 'bar': {'color': "white", 'thickness': 0.2}, 'steps': [{'range': [0, 40], 'color': "#FF4B4B"}, {'range': [40, 60], 'color': "#FFA500"}, {'range': [60, 100], 'color': "#00FF00"}]}
                        ))
                        fig_gauge.update_layout(height=130, margin=dict(l=5, r=5, t=5, b=5), paper_bgcolor='rgba(0,0,0,0)', font={'color': "white"})
                        st.plotly_chart(fig_gauge, use_container_width=True)

                    with st.container(border=True):
                        st.markdown('<div class="section-title">位階與長線 (近1年)</div>', unsafe_allow_html=True)
                        if base_percentile < 30: base_status = "<span style='color:#00FF00;'>🟢 低基期 (底部區)</span>"
                        elif base_percentile > 70: base_status = "<span style='color:#FF4B4B;'>🔴 高基期 (山頂區)</span>"
                        else: base_status = "<span style='color:#FFA500;'>🟡 中基期 (半山腰)</span>"
                        st.markdown(f"<div class='text-sm'>目前位階： <b>{base_percentile:.1f}%</b><br>{base_status}</div>", unsafe_allow_html=True)

                with col_r2:
                    with st.container(border=True):
                        st.markdown('<div class="section-title">量價結構</div>', unsafe_allow_html=True)
                        if price_change > 0 and vol_change_pct > 10: st.markdown("<div class='text-sm'>⚠️ <b>健康上漲</b><br>價漲量增，多方強勢。</div>", unsafe_allow_html=True)
                        elif price_change > 0 and vol_change_pct < -10: st.markdown("<div class='text-sm title-red'>🚨 <b>量價背離</b><br>價漲量縮，追價意願不足。</div>", unsafe_allow_html=True)
                        elif price_change < 0 and vol_change_pct > 10: st.markdown("<div class='text-sm title-red'>🚨 <b>殺盤恐慌</b><br>價跌量增，賣壓沉重。</div>", unsafe_allow_html=True)
                        else: st.markdown("<div class='text-sm'>✅ <b>正常盤整</b><br>無明顯背離跡象。</div>", unsafe_allow_html=True)

                    with st.container(border=True):
                        st.markdown('<div class="section-title">成交量分析 (張)</div>', unsafe_allow_html=True)
                        st.markdown(f"<div class='text-sm'>今日： {latest_vol:,.0f}<br>5日均： {avg_vol_5:,.0f}<br>變化： <span style='color:{color};'>{vol_change_pct:+.1f}%</span></div>", unsafe_allow_html=True)

                    with st.container(border=True):
                        st.markdown('<div class="section-title title-red">🚨 警示雷達</div>', unsafe_allow_html=True)
                        if base_percentile > 80 and chip_sum_10['合計'] < 0: st.markdown("<span class='text-sm'>高檔基期+法人倒貨，慎防崩跌。</span>", unsafe_allow_html=True)
                        elif margin_change > 0 and latest_close < df['MA20'].iloc[-1] and price_change < 0: st.markdown("<span class='text-sm title-red' style='font-weight:bold;'>🚨 散戶接刀：股價破線且融資大增！</span>", unsafe_allow_html=True)
                        elif price_change > 0 and margin_change < 0 and short_change > 0: st.markdown("<span class='text-sm' style='color:#FF4B4B; font-weight:bold;'>🔥 軋空發動：散戶放空被嘎！</span>", unsafe_allow_html=True)
                        elif chip_sum_10['合計'] < 0 and latest_close > df['MA20'].iloc[-1]: st.markdown("<span class='text-sm'>主力疑似拉高出貨！</span>", unsafe_allow_html=True)
                        elif df['K'].iloc[-1] < df['D'].iloc[-1] and df['K'].iloc[-2] >= df['D'].iloc[-2]: st.markdown("<span class='text-sm'>KD 死叉，留意修正。</span>", unsafe_allow_html=True)
                        else: st.markdown("<span class='text-sm'>✅ 目前無明顯異常訊號。</span>", unsafe_allow_html=True)

                    with st.container(border=True):
                        st.markdown('<div class="section-title">關鍵防禦價</div>', unsafe_allow_html=True)
                        st.markdown(f"<div class='text-sm'>壓力區： <b>{price_pressure:.1f}</b><br>月線支撐： <b>{price_support:.1f}</b><br>極限支撐： <b>{price_strong_support:.1f}</b></div>", unsafe_allow_html=True)

                # --- 劇本推演 ---
                script_title, script_color, script_actions = "盤整觀察", "#FFA500", []
                is_red_candle = df['Close'].iloc[-1] > df['Open'].iloc[-1]
                is_volume_burst = latest_vol > (avg_vol_5 * 1.5)
                is_sudden_buy = today_chip['合計'] > (chip_sum_5['合計'] * 0.8) if chip_sum_5['合計'] > 0 else today_chip['合計'] > 0
                
                st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
                if latest_close < df['MA20'].iloc[-1] and margin_change > 0 and chip_sum_5['合計'] < 0:
                    script_title, script_color = "🚨 散戶接刀破底 (高風險)", "#FF0000"
                    script_actions.extend(["👉 <b>籌碼特徵</b>：股價跌破月線，波段倒貨，但【融資餘額不減反增】。","👉 <b>明日對策</b>：反彈絕對是逃命波，切勿攤平。請嚴格停損。"])
                elif price_change > 0 and margin_change < 0 and short_change > 0 and chip_sum_5['合計'] > 0:
                    script_title, script_color = "🔥 主力軋空噴出 (散戶認輸前不會停)", "#FF4B4B"
                    script_actions.extend(["👉 <b>籌碼特徵</b>：法人買超推升股價，但【融資退場、融券大增】。","👉 <b>明日對策</b>：空軍被迫回補的買盤成為推升燃料。沿 5 日線偏多操作。"])
                elif is_red_candle and is_volume_burst and is_sudden_buy and today_chip['合計'] > 0:
                    script_title, script_color = "⚠️ 隔日沖警戒 (提防開高走低)", "#FFFF00"
                    script_actions.extend(["👉 <b>籌碼特徵</b>：爆量收紅，買盤高度集中於單日，極高機率夾帶隔日沖。","👉 <b>明日對策</b>：早盤若跳空開高切勿盲目追價，提防獲利了結賣壓。"])
                elif base_percentile < 30 and chip_sum_5['外資'] < 0 and today_chip['外資'] > 0 and is_red_candle:
                    script_title, script_color = "🚀 外資認錯回補 (底部轉強)", "#FF4B4B"
                    script_actions.extend(["👉 <b>籌碼特徵</b>：低位階且外資波段偏空，今日突然回頭買超收紅 K。","👉 <b>明日對策</b>：極佳右側試單點。開平或微高可建部位，防守今日低點。"])
                elif base_percentile > 70 and chip_sum_5['投信'] > 0 and today_chip['投信'] < 0:
                    script_title, script_color = "🔪 投信高檔結帳 (獲利了結賣壓)", "#00FF00"
                    script_actions.extend(["👉 <b>籌碼特徵</b>：拉抬至高基期，連買投信突然反手賣出。","👉 <b>明日對策</b>：結帳起跌點。極易引發多殺多，應同步減碼。"])
                elif (today_chip['外資'] > 0 and today_chip['投信'] < 0) or (today_chip['外資'] < 0 and today_chip['投信'] > 0):
                    script_title, script_color = "⚔️ 土洋對作 (多空泥巴戰)", "#FFA500"
                    script_actions.extend(["👉 <b>籌碼特徵</b>：外資與投信買賣超方向完全相反。",f"👉 <b>明日對策</b>：焦灼戰。力守月線 (<b>{price_support:.1f}</b>) 偏多，跌破則暫退。"])
                elif chip_sum_5['投信'] > 0 and today_chip['投信'] > 0 and latest_close > df['MA20'].iloc[-1]:
                    script_title, script_color = "🔥 投信波段發動 (順勢偏多)", "#FF4B4B"
                    script_actions.extend(["👉 <b>籌碼特徵</b>：投信連續進駐，站穩月線之上。",f"👉 <b>明日對策</b>：開平或開小高可建立部位。防守月線 (<b>{price_support:.1f}</b>)。"])
                elif latest_close < df['MA20'].iloc[-1] and chip_sum_5['合計'] < 0:
                    script_title, script_color = "🚨 籌碼渙散 (弱勢破線)", "#00FF00"
                    script_actions.extend(["👉 <b>籌碼特徵</b>：波段站在賣方，落入月線之下。","👉 <b>明日對策</b>：反彈皆逃命波。逢高減碼，等待爆量長紅止跌。"])
                else:
                    script_title, script_color = "⚖️ 量縮震盪整理 (等待表態)", "#8ab4f8"
                    script_actions.append("👉 <b>籌碼特徵</b>：無極端異常，處於多空交戰或量縮洗盤階段。")
                    if latest_close > df['MA20'].iloc[-1]: script_actions.append("👉 <b>明日對策</b>：長線偏多但短線動能不足。建議「逢回測均線低吸」。")
                    else: script_actions.append("👉 <b>明日對策</b>：短線偏弱，若帶量下殺有破底風險。建議多看少做。")

                with st.container(border=True):
                    st.markdown(f'<div class="section-title" style="color: {script_color}; font-size: 1.15em; border-bottom: 1px solid #555; padding-bottom: 8px;">🔮 法人明日劇本推演：{script_title}</div>', unsafe_allow_html=True)
                    for act in script_actions: st.markdown(f"<div style='font-size: 0.95em; margin-top: 8px; line-height: 1.5;'>{act}</div>", unsafe_allow_html=True)

                # --- 實戰紀律 ---
                st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
                with st.container(border=True):
                    st.markdown('<div class="section-title" style="font-size: 1.2em;">🎯 實戰紀律執行訊號</div>', unsafe_allow_html=True)
                    signal_cols = st.columns(2)
                    
                    buy_signal_text, buy_signal_color = "⏳ 觀望：未達量化進場標準", "gray"
                    if black_horse_score == 4: buy_signal_text, buy_signal_color = "✅ 強勢進場：滿足 S 級黑馬四大條件", "#00FF00"
                    elif black_horse_score >= 3 and latest_close > df['MA20'].iloc[-1]: buy_signal_text, buy_signal_color = "🟢 試單進場：趨勢偏多，可建立基本部位", "#00FF00"
                    
                    sell_signal_text, sell_signal_color = "🛡️ 續抱：目前無明顯破線危機", "gray"
                    if latest_close < price_strong_support: sell_signal_text, sell_signal_color = "🚨 絕對停損：跌破極限支撐，無條件出場！", "#FF0000"
                    elif latest_close < price_support: sell_signal_text, sell_signal_color = "⚠️ 破線警示：跌破月線，建議減碼或停損", "#FFA500"
                    elif kd_status == "死亡交叉" or rsi_status == "超買警戒": sell_signal_text, sell_signal_color = "🟡 停利準備：高檔動能轉弱，執行移動停利", "#FFA500"
                        
                    signal_cols[0].markdown(f"<div style='border: 2px solid {buy_signal_color}; border-radius: 8px; padding: 15px; text-align: center; height: 100%;'><div style='font-size: 1em; color: gray; margin-bottom: 5px;'>買進訊號 (Buy)</div><div style='font-size: 1.2em; font-weight: bold; color: {buy_signal_color};'>{buy_signal_text}</div></div>", unsafe_allow_html=True)
                    signal_cols[1].markdown(f"<div style='border: 2px solid {sell_signal_color}; border-radius: 8px; padding: 15px; text-align: center; height: 100%;'><div style='font-size: 1em; color: gray; margin-bottom: 5px;'>賣出 / 防守訊號 (Sell / Stop Loss)</div><div style='font-size: 1.2em; font-weight: bold; color: {sell_signal_color};'>{sell_signal_text}</div></div>", unsafe_allow_html=True)

                # --- 修改點 3：新增 666戰法專區 ---
                st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
                with st.container(border=True):
                    st.markdown('<div class="section-title" style="font-size: 1.2em;">😈 666戰法 (日線降維版) 專屬診斷</div>', unsafe_allow_html=True)
                    
                    # 取得 666 戰法需要的數值
                    k60_val = df['K_60'].iloc[-1]
                    d60_val = df['D_60'].iloc[-1]
                    k60_prev = df['K_60'].iloc[-2]
                    d60_prev = df['D_60'].iloc[-2]
                    ma60_val = df['MA60'].iloc[-1]
                    
                    # 判斷 666 邏輯
                    trend_666 = "<span style='color:#FF4B4B;'>✅ 多頭 (站上季線)</span>" if latest_close > ma60_val else "<span style='color:#00FF00;'>🚨 空頭 (跌破季線)</span>"
                    
                    kd_666_status = "⚖️ 中性整理"
                    # 在日線上，KD(60) 比較難落入 20 以下，故我們放寬到 35 視為低檔區
                    if k60_val > d60_val and k60_prev <= d60_prev and k60_val < 35:
                        kd_666_status = "<span style='color:#FF4B4B;'>🔥 低檔黃金交叉 (極佳買點)</span>"
                    elif k60_val < d60_val and k60_prev >= d60_prev and k60_val > 70:
                        kd_666_status = "<span style='color:#00FF00;'>🔪 高檔死亡交叉 (停利/賣出)</span>"
                    elif k60_val < 35:
                        kd_666_status = "📉 尋找底部區 (等待金叉)"
                    elif k60_val > 70:
                        kd_666_status = "📈 高檔強勢區 (留意回檔)"
                        
                    st.markdown(f"<div style='font-size:0.95em; margin-bottom:10px;'><b>第一層濾網 (60MA)：</b> {trend_666} &nbsp;&nbsp;|&nbsp;&nbsp; <b>第二層濾網 KD(60,3,3)：</b> {kd_666_status} (K={k60_val:.1f}, D={d60_val:.1f})</div>", unsafe_allow_html=True)
                    
                    # 系統綜合建議
                    advice_text = ""
                    if latest_close > ma60_val and "黃金交叉" in kd_666_status:
                        advice_text = "🎉 <b>666戰法進場訊號觸發！</b><br>大趨勢(季線)向上，且長週期 KD 經歷充分洗盤後在低檔發生黃金交叉。這是盈虧比極佳的波段起漲點，可嘗試建立部位，防守點設定為季線跌破。"
                    elif latest_close < ma60_val:
                        advice_text = "⚠️ <b>違反 666 戰法紀律！</b><br>目前股價處於季線(60MA)之下，無論短線指標如何，一律不偏多操作，請耐心等待趨勢站回季線。"
                    elif "死亡交叉" in kd_666_status:
                        advice_text = "💰 <b>波段高檔停利警戒！</b><br>股價雖強勢，但長週期 KD 已達高檔並發生死亡交叉，代表這波長線動能可能耗盡，建議分批獲利了結或設定嚴格的移動停利點。"
                    else:
                        advice_text = "⏳ <b>目前為中間態，不符合進出場條件。</b><br>未觸發 666 戰法的極端關鍵轉折，請依循原本的技術面或籌碼面短線操作，或者空手觀望。"
                    
                    st.markdown(f"<div class='strategy-666-box'>{advice_text}</div>", unsafe_allow_html=True)

            except Exception as e:
                st.error(f"資料處理發生錯誤：{e}")

# ==========================================
# TAB 2: 全市場黑馬分級掃描器
# ==========================================
with tab_screener:
    st.markdown("### 🏆 每日台股 S/A/B 級潛力股分級掃描")
    st.markdown("這項工具將優先利用 FinMind 籌碼篩出**「法人實質買超」**的精華股，再逐一利用 Fugle 掃描技術面，完美避開 API 限速。")
    
    if 'scan_result_df' not in st.session_state:
        st.session_state['scan_result_df'] = None
    
    col_scan1, col_scan2 = st.columns([1, 4])
    with col_scan1:
        start_scan = st.button("🚀 執行/重新掃描", use_container_width=True, type="primary")
            
    with col_scan2:
        st.markdown("<div style='margin-top: 10px; font-size: 0.9em; color: gray;'>※ 掃描過程已加入智能降速防護機制，切換分頁不會遺失分析結果。</div>", unsafe_allow_html=True)
        
    if start_scan:
        st.session_state['scan_result_df'] = None
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        df_result = run_market_screener(progress_bar, status_text)
        st.session_state['scan_result_df'] = df_result
        
    if st.session_state['scan_result_df'] is not None:
        result_df = st.session_state['scan_result_df']
        
        if not result_df.empty:
            st.success(f"掃描完成！今日共發現 {len(result_df)} 檔具備攻擊潛力的標的。")
            
            st.markdown("<div style='background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; border: 1px solid #555; margin-bottom: 20px;'>", unsafe_allow_html=True)
            st.markdown("#### ⚡ 快速帶入戰情室解析")
            col_launch1, col_launch2 = st.columns([3, 1])
            
            options = result_df['代號'].tolist()
            selected_ticker = col_launch1.selectbox("請選擇您有興趣的掃描結果：", options, format_func=lambda x: f"{x} {stock_dict.get(x, '')}")
            
            if col_launch2.button("傳送並解析 🎯", use_container_width=True):
                st.session_state['target_ticker'] = selected_ticker
                st.session_state['run_cross_tab_analysis'] = True
                st.success(f"✅ **目標 {selected_ticker} 已鎖定！** 請點擊上方【📊 單檔戰情解析】分頁，系統已為您備妥戰情報告。")
            st.markdown("</div>", unsafe_allow_html=True)

            st.dataframe(result_df, use_container_width=True, hide_index=True)
        else:
            st.warning("⏳ 掃描完成。今日台股市場中，無任何標的符合最低試單標準。建議保留現金實力。")
