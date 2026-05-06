import streamlit as st
import pandas as pd
import numpy as np
import datetime
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
        return id_to_name, name_to_id
    except:
        return {}, {}

stock_dict, name_to_id_dict = load_stock_dicts()

def color_num(val):
    if val > 0: return f"<span class='text-red'>+{val:,.0f}</span>"
    elif val < 0: return f"<span class='text-green'>{val:,.0f}</span>"
    else: return "0"

# ✨ 強制合併版：解決盤中看不到今天 K 棒的問題，並修復「單位陷阱」
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
            
            close_p = quote.get('closePrice')
            if close_p is None:
                close_p = (quote.get('lastTrade') or {}).get('price')

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
                    today_df = pd.DataFrame([{
                        'Date': today_ts,
                        'Open': open_p,
                        'High': high_p,
                        'Low': low_p,
                        'Close': close_p,
                        'Volume': vol_shares
                    }]).set_index('Date')
                    
                    df = pd.concat([df, today_df])
                else:
                    df.loc[today_ts, ['Open', 'High', 'Low', 'Close', 'Volume']] = [open_p, high_p, low_p, close_p, vol_shares]
                    
        except Exception as e_intraday:
            pass 
            
        return df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
    except Exception as e:
        st.error(f"Fugle API 讀取失敗: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_chip_data(ticker, start, end, token):
    dl = DataLoader()
    if token:
        try: dl.login_by_token(api_token=token)
        except: pass
    return dl.taiwan_stock_institutional_investors(stock_id=ticker, start_date=start, end_date=end)

# ==========================================
# 2. 上方橫式控制列
# ==========================================
col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1.5, 1.5, 6])

with col_ctrl1:
    raw_input = st.text_input("搜尋", "6269", label_visibility="collapsed", placeholder="輸入代號或中文名稱")
with col_ctrl2:
    analyze_btn = st.button("🔥 啟動全板面解析", use_container_width=True)
with col_ctrl3:
    st.markdown("<div style='margin-top: 8px; font-size: 0.9em; color:gray;'>※ 搭載 Fugle (盤中即時) + FinMind 雙引擎 + 智能畫線視覺模組</div>", unsafe_allow_html=True)

# ==========================================
# 3. 核心運算引擎
# ==========================================
if analyze_btn or raw_input:
    search_term = str(raw_input).strip() 
    raw_ticker = name_to_id_dict.get(search_term, search_term) if search_term not in stock_dict else search_term
    stock_name = stock_dict.get(raw_ticker, "")
    display_title = f"{raw_ticker} {stock_name}" if stock_name else raw_ticker
    
    with st.spinner(f'鎖定目標 [{display_title}] ... 啟動戰情解析中...'):
        try:
            # --- [技術面] ---
            df_full = fetch_tech_data_fugle(raw_ticker).copy()
            
            if len(df_full) < 20:
                st.error(f"🚨 無法取得 [{display_title}] 的有效報價資料，請確認 API Key 是否設定正確。")
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

            low_min = df_full['Low'].rolling(window=9).min()
            high_max = df_full['High'].rolling(window=9).max()
            df_full['RSV'] = 100 * ((df_full['Close'] - low_min) / (high_max - low_min))
            df_full['K'] = df_full['RSV'].ewm(com=2, adjust=False).mean()
            df_full['D'] = df_full['K'].ewm(com=2, adjust=False).mean()

            df = df_full.tail(120).copy()
            
            # --- ✨ 指標狀態邏輯分析 ---
            curr_k, curr_d = df['K'].iloc[-1], df['D'].iloc[-1]
            prev_k, prev_d = df['K'].iloc[-2], df['D'].iloc[-2]
            kd_status = "中性"
            kd_color = "gray"
            if curr_k > curr_d and prev_k <= prev_d:
                kd_status = "黃金交叉"; kd_color = "#FF4B4B"
            elif curr_k < curr_d and prev_k >= prev_d:
                kd_status = "死亡交叉"; kd_color = "#00FF00"
            elif curr_k > 80: kd_status = "高檔鈍化"; kd_color = "#FF4B4B"
            elif curr_k < 20: kd_status = "低檔背離"; kd_color = "#00FF00"

            osc = df['OSC'].iloc[-1]
            prev_osc = df['OSC'].iloc[-2]
            macd_status = "盤整"
            macd_color = "gray"
            if osc > 0 and osc > prev_osc: macd_status = "多頭增溫"; macd_color = "#FF4B4B"
            elif osc > 0 and osc < prev_osc: macd_status = "多頭縮減"; macd_color = "gray"
            elif osc < 0 and osc < prev_osc: macd_status = "空頭擴散"; macd_color = "#00FF00"
            elif osc < 0 and osc > prev_osc: macd_status = "空頭收斂"; macd_color = "#FF4B4B"

            rsi_val = df['RSI'].iloc[-1]
            rsi_status = "盤整"
            rsi_color = "gray"
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

            # ✨✨ 智慧趨勢線演算法 ✨✨
            order = 5 
            local_highs = []
            local_lows = []
            
            for i in range(order, len(df) - order):
                if df['High'].iloc[i] == max(df['High'].iloc[i-order:i+order+1]):
                    local_highs.append((i, df['High'].iloc[i]))
                if df['Low'].iloc[i] == min(df['Low'].iloc[i-order:i+order+1]):
                    local_lows.append((i, df['Low'].iloc[i]))

            trendline_type = "無明顯趨勢線"
            trend_x = []
            trend_y = []
            trend_color = ""

            if latest_close < df['MA20'].iloc[-1] and len(local_highs) >= 2:
                idx1, y1 = local_highs[-2]
                idx2, y2 = local_highs[-1]
                if y2 < y1: 
                    slope = (y2 - y1) / (idx2 - idx1)
                    idx_start = max(0, idx1 - 20)
                    idx_end = len(df) - 1
                    y_start = y1 - slope * (idx1 - idx_start)
                    y_end = y2 + slope * (idx_end - idx2)
                    
                    trend_x = [x_dates[idx_start], x_dates[idx_end]]
                    trend_y = [y_start, y_end]
                    trend_color = "orange"
                    trendline_type = "下降壓力線"
            
            elif trendline_type == "無明顯趨勢線" and len(local_lows) >= 2:
                idx1, y1 = local_lows[-2]
                idx2, y2 = local_lows[-1]
                if y2 > y1: 
                    slope = (y2 - y1) / (idx2 - idx1)
                    idx_start = max(0, idx1 - 25)
                    idx_end = len(df) - 1
                    y_start = y1 - slope * (idx1 - idx_start)
                    y_end = y2 + slope * (idx_end - idx2)
                    
                    trend_x = [x_dates[idx_start], x_dates[idx_end]]
                    trend_y = [y_start, y_end]
                    trend_color = "yellow"
                    trendline_type = "上升支撐線"

            # --- [籌碼面] ---
            end_date = datetime.date.today()
            start_date = end_date - datetime.timedelta(days=45)
            df_chip = fetch_chip_data(raw_ticker, str(start_date), str(end_date), FINMIND_TOKEN).copy()
            
            chip_sum_10 = {"外資": 0, "投信": 0, "自營商": 0, "合計": 0}
            chip_sum_5 = {"合計": 0}
            today_chip = {"外資": 0, "投信": 0, "自營商": 0, "合計": 0}
            
            if not df_chip.empty:
                df_chip['買賣超(張)'] = (df_chip['buy'] - df_chip['sell']) / 1000
                def simplify_name(name):
                    n = str(name).lower()
                    if 'foreign' in n or '外資' in n: return '外資'
                    if 'trust' in n or '投信' in n: return '投信'
                    if 'dealer' in n or '自營商' in n: return '自營商'
                    return '其他'
                df_chip['法人'] = df_chip['name'].apply(simplify_name)
                df_chip = df_chip[df_chip['法人'] != '其他']
                
                pivot_df = df_chip.pivot_table(index='date', columns='法人', values='買賣超(張)', aggfunc='sum').fillna(0).sort_index()
                pivot_df.index = pd.to_datetime(pivot_df.index)
                
                if len(pivot_df) > 0:
                    last_10 = pivot_df.tail(10)
                    last_5 = pivot_df.tail(5)
                    last_1 = pivot_df.tail(1)
                    
                    def safe_sum(df_target, col): return df_target[col].sum() if col in df_target.columns else 0
                    chip_sum_10['外資'] = safe_sum(last_10, '外資'); chip_sum_10['投信'] = safe_sum(last_10, '投信'); chip_sum_10['自營商'] = safe_sum(last_10, '自營商')
                    chip_sum_10['合計'] = chip_sum_10['外資'] + chip_sum_10['投信'] + chip_sum_10['自營商']
                    chip_sum_5['外資'] = safe_sum(last_5, '外資'); chip_sum_5['投信'] = safe_sum(last_5, '投信'); chip_sum_5['自營商'] = safe_sum(last_5, '自營商')
                    chip_sum_5['合計'] = chip_sum_5['外資'] + chip_sum_5['投信'] + chip_sum_5['自營商']
                    today_chip['外資'] = safe_sum(last_1, '外資'); today_chip['投信'] = safe_sum(last_1, '投信'); today_chip['自營商'] = safe_sum(last_1, '自營商')
                    today_chip['合計'] = today_chip['外資'] + today_chip['投信'] + today_chip['自營商']

            # --- [黑馬潛力鑑定與勝率] ---
            black_horse_score = 0
            bh_reasons = []
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

            zone_text = ""
            zone_color_css = ""
            if latest_close >= price_pressure * 0.98:
                zone_text = "🚀 突破區 (挑戰前高，最強勢)"
                zone_color_css = "color: #FF4B4B; border-color: #FF4B4B;"
            elif price_support <= latest_close < price_pressure * 0.98:
                zone_text = "📈 震盪多頭區 (逢回佈局)"
                zone_color_css = "color: #FFA500; border-color: #FFA500;"
            elif price_strong_support <= latest_close < price_support:
                zone_text = "⚠️ 弱勢整理區 (跌破月線)"
                zone_color_css = "color: #FFFF00; border-color: #FFFF00;"
            else:
                zone_text = "🚨 破底轉空區 (風險極高)"
                zone_color_css = "color: #00FF00; border-color: #00FF00;"

            # ==========================================
            # 4. 畫面渲染
            # ==========================================
            if black_horse_score == 4:
                st.markdown("<div class='s-class-horse'>🔥 S 級黑馬訊號發動：量價籌碼完美共振！ 🔥</div>", unsafe_allow_html=True)
            
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
                    
                    fig.add_hrect(y0=price_pressure*0.97, y1=price_pressure, line_width=0, fillcolor="red", opacity=0.15, row=1, col=1, 
                                  annotation_text=f"近期高點壓力區 ({price_pressure:.1f})", annotation_position="top left", annotation_font_color="red")
                    fig.add_hrect(y0=price_strong_support, y1=price_support, line_width=0, fillcolor="green", opacity=0.15, row=1, col=1, 
                                  annotation_text=f"強勁支撐區 ({price_strong_support:.1f} - {price_support:.1f})", annotation_position="bottom right", annotation_font_color="lightgreen")
                    
                    if trend_x:
                        fig.add_trace(go.Scatter(x=trend_x, y=trend_y, mode='lines', line=dict(color=trend_color, width=3, dash='dashdot'), name=trendline_type), row=1, col=1)
                        fig.add_annotation(x=trend_x[0], y=trend_y[0], text=f" {trendline_type} ", showarrow=True, arrowhead=1, ax=40, ay=-30, font=dict(color=trend_color, size=11), bgcolor="rgba(0,0,0,0.6)", bordercolor=trend_color, borderwidth=1, row=1, col=1)

                    colors_vol = ['#FF4B4B' if row['Close'] >= row['Open'] else '#00FF00' for index, row in df.iterrows()]
                    fig.add_trace(go.Bar(x=x_dates, y=df['Volume'], marker_color=colors_vol, name="成交量(張)"), row=2, col=1)
                    
                    vol_text = "正常盤整"
                    if price_change > 0 and vol_change_pct > 10: vol_text = "多頭量增價漲"
                    elif price_change > 0 and vol_change_pct < -10: vol_text = "價漲量縮背離"
                    elif price_change < 0 and vol_change_pct > 10: vol_text = "帶量下殺賣壓"
                    fig.add_annotation(x=x_dates[-1], y=df['Volume'].iloc[-1], text=f"量能: {vol_text}", showarrow=True, arrowhead=2, arrowsize=1, ax=-50, ay=-40, 
                                       bgcolor="rgba(0,0,0,0.8)", bordercolor="yellow", borderwidth=1, font=dict(color="yellow", size=10), row=2, col=1)
                    
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
                        <div><span style="font-size: 0.85em; color:gray;">KD:</span> <span style="font-size: 0.85em; font-weight: bold; color: {kd_color};">{kd_status} ({curr_k:.1f})</span></div>
                        <div><span style="font-size: 0.85em; color:gray;">MACD:</span> <span style="font-size: 0.85em; font-weight: bold; color: {macd_color};">{macd_status}</span></div>
                        <div><span style="font-size: 0.85em; color:gray;">RSI:</span> <span style="font-size: 0.85em; font-weight: bold; color: {rsi_color};">{rsi_status} ({rsi_val:.1f})</span></div>
                    </div>
                    """, unsafe_allow_html=True)

                with st.container(border=True):
                    st.markdown(f"<div class='zone-indicator' style='{zone_color_css}'>🎯 目前位階：{zone_text}</div>", unsafe_allow_html=True)

            with col_mid:
                with st.container(border=True):
                    st.markdown('<div class="section-title">法人籌碼與股價疊加圖</div>', unsafe_allow_html=True)
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
                            <tr><td class="row-title">今日</td><td>{color_num(today_chip['外資'])}</td><td>{color_num(today_chip['投信'])}</td><td>{color_num(today_chip['自營商'])}</td><td>{color_num(today_chip['合計'])}</td></tr>
                            <tr><td class="row-title">近5日</td><td>{color_num(chip_sum_5['外資'])}</td><td>{color_num(chip_sum_5['投信'])}</td><td>{color_num(chip_sum_5['自營商'])}</td><td>{color_num(chip_sum_5['合計'])}</td></tr>
                            <tr><td class="row-title">近10日</td><td>{color_num(chip_sum_10['外資'])}</td><td>{color_num(chip_sum_10['投信'])}</td><td>{color_num(chip_sum_10['自營商'])}</td><td>{color_num(chip_sum_10['合計'])}</td></tr>
                        </table>
                        """
                        st.markdown(html_table, unsafe_allow_html=True)
                        st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
                        st.markdown('<div class="section-title" style="font-size:0.9em; border:none; margin-bottom:0;">主力進出分析 (近10日多空)</div>', unsafe_allow_html=True)
                        col_c1, col_c2 = st.columns(2)
                        col_c1.markdown(f"<div class='text-sm'>今日主力動向</div><div class='metric-value'>{color_num(today_chip['合計'])}</div>", unsafe_allow_html=True)
                        col_c2.markdown(f"<div class='text-sm'>10日波段籌碼</div><div class='metric-value'>{color_num(chip_sum_10['合計'])}</div>", unsafe_allow_html=True)
                    else:
                        st.warning("查無籌碼資料")

            with col_r1:
                with st.container(border=True):
                    st.markdown('<div class="section-title">黑馬潛力雷達</div>', unsafe_allow_html=True)
                    if len(bh_reasons) > 0:
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
                    elif chip_sum_10['合計'] < 0 and latest_close > df['MA20'].iloc[-1]: st.markdown("<span class='text-sm'>主力疑似拉高出貨！</span>", unsafe_allow_html=True)
                    elif df['K'].iloc[-1] < df['D'].iloc[-1] and df['K'].iloc[-2] >= df['D'].iloc[-2]: st.markdown("<span class='text-sm'>KD 死叉，留意修正。</span>", unsafe_allow_html=True)
                    else: st.markdown("<span class='text-sm'>✅ 目前無明顯出貨訊號。</span>", unsafe_allow_html=True)

                with st.container(border=True):
                    st.markdown('<div class="section-title">關鍵防禦價</div>', unsafe_allow_html=True)
                    st.markdown(f"<div class='text-sm'>壓力區： <b>{price_pressure:.1f}</b><br>月線支撐： <b>{price_support:.1f}</b><br>極限支撐： <b>{price_strong_support:.1f}</b></div>", unsafe_allow_html=True)

# ==========================================
            # ✨ 新增：法人明日劇本推演模組 (7大完全體) ✨
            # ==========================================
            script_title = "盤整觀察"
            script_color = "#FFA500"
            script_actions = []

            # 判斷邏輯變數設定
            is_red_candle = df['Close'].iloc[-1] > df['Open'].iloc[-1]
            is_volume_burst = latest_vol > (avg_vol_5 * 1.5)
            is_sudden_buy = today_chip['合計'] > (chip_sum_5['合計'] * 0.8) if chip_sum_5['合計'] > 0 else today_chip['合計'] > 0
            
            st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)

            # --- 劇本 1：隔日沖倒貨預警 (優先級最高：短線致命風險) ---
            if is_red_candle and is_volume_burst and is_sudden_buy and today_chip['合計'] > 0:
                script_title = "⚠️ 隔日沖警戒 (提防開高走低)"
                script_color = "#FFFF00"
                script_actions.append("👉 <b>籌碼特徵</b>：今日爆量收紅，且法人買盤高度集中於單日，極高機率夾帶隔日沖分點進駐。")
                script_actions.append("👉 <b>明日對策</b>：早盤若跳空開高切勿盲目追價，提防 9:30 前的獲利了結賣壓出籠。若早盤爆量下殺應先觀望；待 11:00 後量縮且守穩今日收盤價一半之上，再考慮切入。")

            # --- 劇本 2：外資認錯回補 (抓強勢 V 轉底部) ---
            elif base_percentile < 30 and chip_sum_5['外資'] < 0 and today_chip['外資'] > 0 and is_red_candle:
                script_title = "🚀 外資認錯回補 (底部轉強)"
                script_color = "#FF4B4B"
                script_actions.append("👉 <b>籌碼特徵</b>：位階處於低檔且外資波段偏空，但今日外資突然回頭買超，並收出紅 K，呈現認錯回補跡象。")
                script_actions.append("👉 <b>明日對策</b>：極佳的右側底部試單點。明日若開平或微幅開高可分批建立部位，直接將今日紅 K 最低點設為絕對停損防守線。")

            # --- 劇本 3：投信高檔結帳 (抓起跌點) ---
            elif base_percentile > 70 and chip_sum_5['投信'] > 0 and today_chip['投信'] < 0:
                script_title = "🔪 投信高檔結帳 (獲利了結賣壓)"
                script_color = "#00FF00"
                script_actions.append("👉 <b>籌碼特徵</b>：股價已拉抬至高基期，原本連續買超的投信今日突然反手賣出，主力籌碼開始鬆動。")
                script_actions.append("👉 <b>明日對策</b>：這是標準的「結帳起跌點」。明日開盤極易引發多殺多，持有多單者應跟著投信的腳步同步減碼，切勿留戀或逢低攤平。")

            # --- 劇本 4：土洋對作 (內外資籌碼打架) ---
            elif (today_chip['外資'] > 0 and today_chip['投信'] < 0) or (today_chip['外資'] < 0 and today_chip['投信'] > 0):
                script_title = "⚔️ 土洋對作 (多空泥巴戰)"
                script_color = "#FFA500"
                script_actions.append("👉 <b>籌碼特徵</b>：今日外資與投信的買賣超方向完全相反，市場兩大主力對後市看法分歧。")
                script_actions.append(f"👉 <b>明日對策</b>：盤勢進入焦灼戰。明日重點在於「誰的防線被跌破」。若股價力守月線 (<b>{price_support:.1f}</b>) 代表內資護盤成功，偏多看待；反之若跌破均線，代表外資賣壓獲勝，應暫時退場。")

            # --- 劇本 5：投信波段發動 (標準多頭) ---
            elif chip_sum_5['投信'] > 0 and today_chip['投信'] > 0 and latest_close > df['MA20'].iloc[-1]:
                script_title = "🔥 投信波段發動 (順勢偏多)"
                script_color = "#FF4B4B"
                script_actions.append("👉 <b>籌碼特徵</b>：投信籌碼連續進駐，且股價站穩月線之上，具備內資波段保護傘。")
                script_actions.append(f"👉 <b>明日對策</b>：開平或開小高皆可分批建立基本部位。防守線可設於月線 (<b>{price_support:.1f}</b>)，未跌破前可持股續抱。若明日開盤預估量溫和放大，則攻擊勝率極高。")

            # --- 劇本 6：法人棄守破線 (標準空頭) ---
            elif latest_close < df['MA20'].iloc[-1] and chip_sum_5['合計'] < 0:
                script_title = "🚨 籌碼渙散 (弱勢破線)"
                script_color = "#00FF00"
                script_actions.append("👉 <b>籌碼特徵</b>：法人波段站在賣方，且股價已落入月線之下，上檔套牢賣壓沉重。")
                script_actions.append("👉 <b>明日對策</b>：反彈皆是逃命波。明日若逢高觸碰月線或今日高點，應優先減碼。耐心等待站回月線或出現爆量長紅 K 止跌訊號為止。")
                
            # --- 劇本 7：量縮震盪整理 (無聊的垃圾時間) ---
            else:
                script_title = "⚖️ 量縮震盪整理 (等待表態)"
                script_color = "#8ab4f8"
                script_actions.append("👉 <b>籌碼特徵</b>：目前籌碼與量價結構無極端異常，處於多空交戰或量縮洗盤階段。")
                if latest_close > df['MA20'].iloc[-1]:
                    script_actions.append("👉 <b>明日對策</b>：長線偏多但短線動能不足。明日開盤若無帶量，容易陷入狹幅震盪。建議採取「逢回測均線低吸」策略，切忌追高。")
                else:
                    script_actions.append("👉 <b>明日對策</b>：短線偏弱，明日若帶量下殺將有破底風險。建議多看少做，保留現金實力。")

            # --- 渲染劇本結果 ---
            with st.container(border=True):
                st.markdown(f'<div class="section-title" style="color: {script_color}; font-size: 1.15em; border-bottom: 1px solid #555; padding-bottom: 8px;">🔮 法人明日劇本推演：{script_title}</div>', unsafe_allow_html=True)
                for act in script_actions:
                    st.markdown(f"<div style='font-size: 0.95em; margin-top: 8px; line-height: 1.5;'>{act}</div>", unsafe_allow_html=True)

        except Exception as e:
            st.error(f"資料處理發生錯誤：{e}")
            st.exception(e)
