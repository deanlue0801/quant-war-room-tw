import streamlit as st
import pandas as pd
import numpy as np
import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from FinMind.data import DataLoader
import warnings

warnings.filterwarnings('ignore', category=FutureWarning)

# ==========================================
# 1. 網頁與 CSS 視覺設定 (完整保留自 Source 1)
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
# 🌟 全新統一 FinMind 快取引擎
# ==========================================
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

try:
    FINMIND_TOKEN = st.secrets.get("FINMIND_TOKEN", "")
except:
    FINMIND_TOKEN = ""

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_tech_data_finmind(ticker, token):
    dl = DataLoader()
    if token:
        try: dl.login_by_token(api_token=token)
        except: pass
        
    end = datetime.date.today()
    start = end - datetime.timedelta(days=365)
    df = dl.taiwan_stock_daily(stock_id=str(ticker), start_date=str(start), end_date=str(end))
    
    if df.empty:
        return pd.DataFrame()
        
    if 'Trading_Volume' in df.columns:
        df = df.rename(columns={'Trading_Volume': 'Volume'})
    elif 'capacity' in df.columns:
        df = df.rename(columns={'capacity': 'Volume'})
        
    df = df.rename(columns={'date': 'Date', 'open': 'Open', 'max': 'High', 'min': 'Low', 'close': 'Close'})
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.set_index('Date')
    
    return df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()

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
    st.markdown("<div style='margin-top: 8px; font-size: 0.9em; color:gray;'>※ 搭載 FinMind 雙引擎 + 智能畫線視覺模組 + 指標動態診斷</div>", unsafe_allow_html=True)

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
            # --- [技術面運算] ---
            df_full = fetch_tech_data_finmind(raw_ticker, FINMIND_TOKEN).copy()
            
            if len(df_full) < 20:
                st.error(f"🚨 無法取得 [{display_title}] 的有效報價資料。")
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

            # ✨✨ 智慧趨勢線演算法 (完整移植自 Source 1) ✨✨
            order = 5 
            local_highs = []
            local_lows = []
            for i in range(order, len(df) - order):
                if df['High'].iloc[i] == max(df['High'].iloc[i-order:i+order+1]): local_highs.append((i, df['High'].iloc[i]))
                if df['Low'].iloc[i] == min(df['Low'].iloc[i-order:i+order+1]): local_lows.append((i, df['Low'].iloc[i]))

            trendline_type, trend_x, trend_y, trend_color = "無明顯趨勢線", [], [], ""
            if latest_close < df['MA20'].iloc[-1] and len(local_highs) >= 2:
                idx1, y1 = local_highs[-2]; idx2, y2 = local_highs[-1]
                if y2 < y1: 
                    slope = (y2 - y1) / (idx2 - idx1); idx_start = max(0, idx1 - 20); idx_end = len(df) - 1
                    trend_x = [x_dates[idx_start], x_dates[idx_end]]
                    trend_y = [y1 - slope * (idx1 - idx_start), y2 + slope * (idx_end - idx2)]
                    trend_color, trendline_type = "orange", "下降壓力線"
            elif trendline_type == "無明顯趨勢線" and len(local_lows) >= 2:
                idx1, y1 = local_lows[-2]; idx2, y2 = local_lows[-1]
                if y2 > y1: 
                    slope = (y2 - y1) / (idx2 - idx1); idx_start = max(0, idx1 - 25); idx_end = len(df) - 1
                    trend_x = [x_dates[idx_start], x_dates[idx_end]]
                    trend_y = [y1 - slope * (idx1 - idx_start), y2 + slope * (idx_end - idx2)]
                    trend_color, trendline_type = "yellow", "上升支撐線"

            # --- [新增：技術指標動態診斷文字邏輯] ---
            latest_osc = df['OSC'].iloc[-1]; prev_osc = df['OSC'].iloc[-2]
            macd_diag = ("多頭續攻 🚀" if latest_osc > prev_osc else "動能減弱 ⚠️") if latest_osc > 0 else ("空頭收斂 📉" if latest_osc > prev_osc else "空方強勢 🚨")
            
            lk, ld = df['K'].iloc[-1], df['D'].iloc[-1]
            if lk > 80: kd_diag = "高檔死叉 (警訊) 🚨" if lk < ld else "高檔強勢鈍化 🔥"
            elif lk < 20: kd_diag = "低檔金叉 (機會) ✨" if lk > ld else "低檔超跌中 ❄️"
            else: kd_diag = "KD 黃金交叉 ⚡" if (lk > ld and df['K'].iloc[-2] <= df['D'].iloc[-2]) else "KD 整理中 ⚖️"
            
            lrsi = df['RSI'].iloc[-1]
            rsi_diag = "指標過熱 (超買) 🌡️" if lrsi > 70 else ("指標超跌 (超賣) ❄️" if lrsi < 30 else "強弱力道中性 ⚖️")

            # --- [籌碼面運算] ---
            end_date = datetime.date.today(); start_date = end_date - datetime.timedelta(days=45)
            df_chip = fetch_chip_data(raw_ticker, str(start_date), str(end_date), FINMIND_TOKEN).copy()
            chip_sum_10, chip_sum_5, today_chip = {"外資": 0, "投信": 0, "自營商": 0, "合計": 0}, {"合計": 0}, {"合計": 0}
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
                if not pivot_df.empty:
                    def safe_sum_col(df_target, col): return df_target[col].sum() if col in df_target.columns else 0
                    last_10 = pivot_df.tail(10); last_5 = pivot_df.tail(5); last_1 = pivot_df.tail(1)
                    for d, s in [(last_10, chip_sum_10), (last_5, chip_sum_5), (last_1, today_chip)]:
                        s['外資'] = safe_sum_col(d, '外資'); s['投信'] = safe_sum_col(d, '投信'); s['自營商'] = safe_sum_col(d, '自營商')
                        s['合計'] = s['外資'] + s['投信'] + s['自營商']

            # --- [雷達與勝率評分] ---
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
            win_rate = max(0, min(100, win_rate))

            zone_text = ("🚀 突破區" if latest_close >= price_pressure * 0.98 else ("📈 震盪多頭區" if price_support <= latest_close < price_pressure * 0.98 else ("⚠️ 弱勢整理區" if price_strong_support <= latest_close < price_support else "🚨 破底轉空區")))
            zone_color_css = f"color: {'#FF4B4B' if '突破' in zone_text else ('#FFA500' if '震盪' in zone_text else ('#FFFF00' if '弱勢' in zone_text else '#00FF00'))}; border-color: currentcolor;"

            # ==========================================
            # 4. 畫面渲染 (完整遵循 Source 1 佈局)
            # ==========================================
            if black_horse_score == 4: st.markdown("<div class='s-class-horse'>🔥 S 級黑馬訊號發動：量價籌碼完美共振！ 🔥</div>", unsafe_allow_html=True)
            stars = "★" * black_horse_score + "☆" * (4 - black_horse_score)
            st.markdown(f"<h3 style='margin-bottom:0;'>{display_title} &nbsp;&nbsp; <span style='font-size: 0.5em; color: #8ab4f8; border: 1px solid #333; padding: 2px 8px; border-radius: 5px; vertical-align: middle;'>{date_str}</span> &nbsp;&nbsp; | &nbsp;&nbsp; 爆發潛力 <span class='potential-stars'>{stars}</span></h3>", unsafe_allow_html=True)
            st.markdown(f"<div class='text-sm' style='margin-bottom: 5px;'>收盤 <span style='color:{color}; font-weight:bold;'>{latest_close:.2f}</span> &nbsp;&nbsp; 漲跌 <span style='color:{color};'>{sign} {abs(price_change):.2f} ({change_pct:.2f}%)</span> &nbsp;&nbsp; | &nbsp;&nbsp; 成交量 <b>{latest_vol:,.0f}</b> 張</div>", unsafe_allow_html=True)
            st.markdown("<hr style='margin: 0 0 10px 0; padding: 0;'>", unsafe_allow_html=True)

            col_left, col_mid, col_r1, col_r2 = st.columns([1.6, 1.1, 0.85, 0.85])

            with col_left:
                with st.container(border=True):
                    st.markdown('<div class="section-title">技術面與指標動態診斷</div>', unsafe_allow_html=True)
                    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.015, row_heights=[0.4, 0.15, 0.15, 0.15, 0.15])
                    fig.add_trace(go.Candlestick(x=x_dates, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線", increasing_line_color='#FF4B4B', decreasing_line_color='#00FF00'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=x_dates, y=df['MA20'], line=dict(color='cyan', width=1.5)), row=1, col=1)
                    fig.add_trace(go.Scatter(x=x_dates, y=df['MA60'], line=dict(color='magenta', width=1)), row=1, col=1)
                    fig.add_hrect(y0=price_pressure*0.97, y1=price_pressure, fillcolor="red", opacity=0.15, row=1, col=1)
                    fig.add_hrect(y0=price_strong_support, y1=price_support, fillcolor="green", opacity=0.15, row=1, col=1)
                    
                    if trend_x:
                        fig.add_trace(go.Scatter(x=trend_x, y=trend_y, mode='lines', line=dict(color=trend_color, width=3, dash='dashdot')), row=1, col=1)
                        fig.add_annotation(x=trend_x[0], y=trend_y[0], text=f" {trendline_type} ", showarrow=True, arrowhead=1, ax=40, ay=-30, font=dict(color=trend_color, size=11), bgcolor="rgba(0,0,0,0.6)", bordercolor=trend_color, borderwidth=1, row=1, col=1)

                    fig.add_trace(go.Bar(x=x_dates, y=df['Volume'], marker_color=['#FF4B4B' if r['Close'] >= r['Open'] else '#00FF00' for i, r in df.iterrows()]), row=2, col=1)
                    
                    #指標標註與繪圖
                    fig.add_trace(go.Bar(x=x_dates, y=df['OSC'], marker_color=['#FF4B4B' if v >= 0 else '#00FF00' for v in df['OSC']]), row=3, col=1)
                    fig.add_annotation(xref="x domain", yref="y domain", x=0.01, y=0.9, text=f"<b>MACD: {macd_diag}</b>", showarrow=False, font=dict(color="white", size=10), bgcolor="rgba(0,0,0,0.6)", row=3, col=1)
                    
                    fig.add_trace(go.Scatter(x=x_dates, y=df['K'], line=dict(color='yellow', width=1)), row=4, col=1)
                    fig.add_trace(go.Scatter(x=x_dates, y=df['D'], line=dict(color='cyan', width=1)), row=4, col=1)
                    fig.add_annotation(xref="x domain", yref="y domain", x=0.01, y=0.9, text=f"<b>KD: {kd_diag}</b>", showarrow=False, font=dict(color="white", size=10), bgcolor="rgba(0,0,0,0.6)", row=4, col=1)
                    
                    fig.add_trace(go.Scatter(x=x_dates, y=df['RSI'], line=dict(color='magenta', width=1)), row=5, col=1)
                    fig.add_annotation(xref="x domain", yref="y domain", x=0.01, y=0.9, text=f"<b>RSI: {rsi_diag}</b>", showarrow=False, font=dict(color="white", size=10), bgcolor="rgba(0,0,0,0.6)", row=5, col=1)
                    
                    fig.update_layout(height=650, margin=dict(l=0, r=0, t=5, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False, xaxis_rangeslider_visible=False)
                    fig.update_xaxes(type='category', nticks=10, showgrid=True, gridcolor='#333')
                    st.plotly_chart(fig, use_container_width=True)

                with st.container(border=True):
                    st.markdown(f"<div class='zone-indicator' style='{zone_color_css}'>🎯 目前位階：{zone_text}</div>", unsafe_allow_html=True)

            with col_mid:
                with st.container(border=True):
                    st.markdown('<div class="section-title">法人籌碼與股價疊加圖</div>', unsafe_allow_html=True)
                    if not df_chip.empty:
                        last_20_chips = pivot_df.tail(20)
                        fig_chip = make_subplots(specs=[[{"secondary_y": True}]])
                        chip_dates = last_20_chips.index.strftime('%m-%d')
                        for c, col in [('外資', '#8ab4f8'), ('投信', '#FF4B4B'), ('自營商', '#00FF00')]:
                            if c in last_20_chips.columns: fig_chip.add_trace(go.Bar(x=chip_dates, y=last_20_chips[c], name=c, marker_color=col), secondary_y=False)
                        price_dict = dict(zip(x_dates, df['Close']))
                        fig_chip.add_trace(go.Scatter(x=chip_dates, y=[price_dict.get(d) for d in chip_dates], line=dict(color='yellow', width=2), mode='lines+markers', marker=dict(size=4)), secondary_y=True)
                        fig_chip.update_layout(height=200, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor='rgba(0,0,0,0)', barmode='group', showlegend=False)
                        st.plotly_chart(fig_chip, use_container_width=True)
                        
                        st.markdown(f"""<table class="chip-table">
                            <tr><th></th><th>外資</th><th>投信</th><th>合計</th></tr>
                            <tr><td class="row-title">今日</td><td>{color_num(today_chip['外資'])}</td><td>{color_num(today_chip['投信'])}</td><td>{color_num(today_chip['合計'])}</td></tr>
                            <tr><td class="row-title">近5日</td><td>{color_num(chip_sum_5['外資'])}</td><td>{color_num(chip_sum_5['投信'])}</td><td>{color_num(chip_sum_5['合計'])}</td></tr>
                            <tr><td class="row-title">近10日</td><td>{color_num(chip_sum_10['外資'])}</td><td>{color_num(chip_sum_10['投信'])}</td><td>{color_num(chip_sum_10['合計'])}</td></tr>
                        </table>""", unsafe_allow_html=True)

            with col_r1:
                with st.container(border=True):
                    st.markdown('<div class="section-title">黑馬潛力與勝率</div>', unsafe_allow_html=True)
                    for reason in bh_reasons: st.markdown(f"<div class='text-sm'>{reason}</div>", unsafe_allow_html=True)
                    st.divider()
                    st.metric("短線進場勝率", f"{win_rate}%")
                    st.markdown(f"<div class='text-sm'>目前位階： <b>{base_percentile:.1f}%</b></div>", unsafe_allow_html=True)

            with col_r2:
                with st.container(border=True):
                    st.markdown('<div class="section-title">量價結構與警示</div>', unsafe_allow_html=True)
                    if price_change > 0 and vol_change_pct > 10: st.markdown("<div class='text-sm'>⚠️ <b>健康上漲</b></div>", unsafe_allow_html=True)
                    elif price_change > 0 and vol_change_pct < -10: st.markdown("<div class='text-sm title-red'>🚨 <b>量價背離</b></div>", unsafe_allow_html=True)
                    elif price_change < 0 and vol_change_pct > 10: st.markdown("<div class='text-sm title-red'>🚨 <b>殺盤恐慌</b></div>", unsafe_allow_html=True)
                    
                    st.divider()
                    if chip_sum_10['合計'] < 0 and latest_close > df['MA20'].iloc[-1]: st.markdown("<div class='text-sm title-red'>🚨 主力疑似拉高出貨！</div>", unsafe_allow_html=True)
                    else: st.markdown("<div class='text-sm'>✅ 目前籌碼動向尚屬正常</div>", unsafe_allow_html=True)
                    
                    st.divider()
                    st.markdown(f"<div class='text-sm'>壓力區： <b>{price_pressure:.1f}</b><br>月線： <b>{price_support:.1f}</b></div>", unsafe_allow_html=True)

        except Exception as e:
            st.error(f"資料處理發生錯誤：{e}")
            st.exception(e)
