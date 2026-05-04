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
# 1. 網頁與 CSS 視覺設定
# ==========================================
st.set_page_config(page_title="終極量化戰情室 Pro Max", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .block-container { padding-top: 2rem !important; padding-bottom: 1rem !important; max-width: 98vw !important;}
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
    @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(255, 75, 75, 0.7); } 70% { box-shadow: 0 0 0 10px rgba(255, 75, 75, 0); } 100% { box-shadow: 0 0 0 0 rgba(255, 75, 75, 0); } }
    .s-class-horse { background: linear-gradient(45deg, #FF4B4B, #FF8C00); color: white; font-weight: bold; text-align: center; font-size: 1.5em; padding: 10px; border-radius: 10px; margin-bottom: 15px; animation: pulse 2s infinite; text-shadow: 1px 1px 2px black; }
    .potential-stars { font-size: 1.2em; color: #FFD700; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🌟 核心數據快取引擎 (FinMind 雙效整合)
# ==========================================
@st.cache_data(ttl=86400)
def load_stock_dicts():
    try:
        dl = DataLoader()
        info = dl.taiwan_stock_info()
        return dict(zip(info['stock_id'].astype(str), info['stock_name'])), dict(zip(info['stock_name'], info['stock_id'].astype(str)))
    except: return {}, {}

stock_dict, name_to_id_dict = load_stock_dicts()

try: FINMIND_TOKEN = st.secrets.get("FINMIND_TOKEN", "")
except: FINMIND_TOKEN = ""

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_tech_data_finmind(ticker, token):
    dl = DataLoader()
    if token:
        try: dl.login_by_token(api_token=token)
        except: pass
    end = datetime.date.today()
    start = end - datetime.timedelta(days=365)
    df = dl.taiwan_stock_daily(stock_id=str(ticker), start_date=str(start), end_date=str(end))
    if df.empty: return pd.DataFrame()
    
    vol_col = 'Trading_Volume' if 'Trading_Volume' in df.columns else 'capacity' if 'capacity' in df.columns else None
    if vol_col: df = df.rename(columns={vol_col: 'Volume'})
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

def color_num(val): return f"<span class='text-red'>+{val:,.0f}</span>" if val > 0 else f"<span class='text-green'>{val:,.0f}</span>" if val < 0 else "0"

# ==========================================
# 2. 控制列
# ==========================================
c1, c2, c3 = st.columns([1.5, 1.5, 6])
with c1: raw_input = st.text_input("搜尋", "8091", label_visibility="collapsed")
with c2: analyze_btn = st.button("🔥 啟動全板面解析", use_container_width=True)
with c3: st.markdown("<div style='margin-top:8px; color:gray;'><small>※ 搭載 FinMind VIP 引擎，融合經典指標與高階模組</small></div>", unsafe_allow_html=True)

# ==========================================
# 3. 核心運算引擎
# ==========================================
if analyze_btn or raw_input:
    search_term = str(raw_input).strip() 
    raw_ticker = name_to_id_dict.get(search_term, search_term)
    stock_name = stock_dict.get(raw_ticker, "")
    display_title = f"{raw_ticker} {stock_name}" if stock_name else raw_ticker
    
    with st.spinner(f'鎖定目標 [{display_title}] ... 高階模組運算中...'):
        try:
            # --- 技術面計算 ---
            df_full = fetch_tech_data_finmind(raw_ticker, FINMIND_TOKEN).copy()
            if len(df_full) < 60:
                st.error("🚨 資料不足或查無此股。")
                st.stop()
                
            df_full.index = df_full.index.tz_localize(None)
            df_full['Volume'] = df_full['Volume'] / 1000  # 轉成張
            
            latest_close = df_full['Close'].iloc[-1]
            latest_vol = df_full['Volume'].iloc[-1]
            prev_close = df_full['Close'].iloc[-2]
            price_change = latest_close - prev_close
            change_pct = (price_change / prev_close) * 100
            
            avg_vol_5 = df_full['Volume'].rolling(5).mean().iloc[-1]
            vol_change_pct = ((latest_vol - avg_vol_5) / avg_vol_5) * 100 if avg_vol_5 > 0 else 0
            
            high_52w = df_full['High'].max()
            low_52w = df_full['Low'].min()
            base_percentile = ((latest_close - low_52w) / (high_52w - low_52w)) * 100 if (high_52w - low_52w) != 0 else 50
            
            df_full['MA5'] = df_full['Close'].rolling(5).mean()
            df_full['MA20'] = df_full['Close'].rolling(20).mean()
            df_full['MA60'] = df_full['Close'].rolling(60).mean()
            bias_20 = ((latest_close - df_full['MA20'].iloc[-1]) / df_full['MA20'].iloc[-1]) * 100
            
            # BB Band (布林通道)
            df_full['BB_std'] = df_full['Close'].rolling(20).std()
            df_full['BB_Up'] = df_full['MA20'] + (2 * df_full['BB_std'])
            df_full['BB_Dn'] = df_full['MA20'] - (2 * df_full['BB_std'])
            df_full['BB_Width'] = (df_full['BB_Up'] - df_full['BB_Dn']) / df_full['MA20']
            
            # RSI & MACD
            delta = df_full['Close'].diff()
            df_full['RSI'] = 100 - (100 / (1 + (delta.where(delta > 0, 0).rolling(14).mean() / -delta.where(delta < 0, 0).rolling(14).mean())))
            df_full['MACD'] = df_full['Close'].ewm(span=12).mean() - df_full['Close'].ewm(span=26).mean()
            df_full['Signal'] = df_full['MACD'].ewm(span=9).mean()
            df_full['OSC'] = df_full['MACD'] - df_full['Signal']
            
            # KD 指標
            low_min = df_full['Low'].rolling(window=9).min()
            high_max = df_full['High'].rolling(window=9).max()
            df_full['RSV'] = 100 * ((df_full['Close'] - low_min) / (high_max - low_min))
            df_full['K'] = df_full['RSV'].ewm(com=2, adjust=False).mean()
            df_full['D'] = df_full['K'].ewm(com=2, adjust=False).mean()

            df = df_full.tail(120).copy()
            x_dates = df.index.strftime('%m-%d')
            
            # --- 籌碼面計算 ---
            end_date = datetime.date.today()
            start_date = end_date - datetime.timedelta(days=150)
            df_chip = fetch_chip_data(raw_ticker, str(start_date), str(end_date), FINMIND_TOKEN).copy()
            
            # 🐛 修正點：補齊 chip_sum_5 的字典結構
            chip_sum_10 = {"外資": 0, "投信": 0, "自營商": 0, "合計": 0}
            chip_sum_5 = {"外資": 0, "投信": 0, "自營商": 0, "合計": 0} 
            today_chip = {"外資": 0, "投信": 0, "自營商": 0, "合計": 0}
            pivot_df = pd.DataFrame()
            
            if not df_chip.empty:
                df_chip['買賣超(張)'] = (df_chip['buy'] - df_chip['sell']) / 1000
                df_chip['法人'] = df_chip['name'].apply(lambda x: '外資' if '外' in str(x) or 'foreign' in str(x).lower() else '投信' if '投' in str(x) or 'trust' in str(x).lower() else '自營商' if '自' in str(x) or 'dealer' in str(x).lower() else '其他')
                df_chip = df_chip[df_chip['法人'] != '其他']
                pivot_df = df_chip.pivot_table(index='date', columns='法人', values='買賣超(張)', aggfunc='sum').fillna(0).sort_index()
                pivot_df.index = pd.to_datetime(pivot_df.index)
                pivot_df['三大法人合計'] = pivot_df.sum(axis=1)
                
                if len(pivot_df) > 0:
                    def safe_sum(df_t, col): return df_t[col].sum() if col in df_t.columns else 0
                    last_10 = pivot_df.tail(10)
                    last_5 = pivot_df.tail(5)
                    last_1 = pivot_df.tail(1)
                    
                    for k in ['外資', '投信', '自營商']:
                        chip_sum_10[k] = safe_sum(last_10, k)
                        chip_sum_5[k] = safe_sum(last_5, k) # 🐛 修正點：計算 5 日各法人資料
                        today_chip[k] = safe_sum(last_1, k)
                    chip_sum_10['合計'] = safe_sum(last_10, '三大法人合計')
                    chip_sum_5['合計'] = safe_sum(last_5, '三大法人合計')
                    today_chip['合計'] = safe_sum(last_1, '三大法人合計')

            # --- 黑馬潛力與勝率算式 ---
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

            # --- 高階演算法 ---
            if not pivot_df.empty:
                df_align = df.join(pivot_df['三大法人合計'], how='left').fillna(0)
                df['Retail_Net'] = df_align['Volume'] - abs(df_align['三大法人合計']) 
                df['Inst_Net'] = df_align['三大法人合計']
                df['Inst_Cost'] = (df['Close'] * df['Inst_Net'].where(df['Inst_Net']>0, 0)).rolling(20).sum() / df['Inst_Net'].where(df['Inst_Net']>0, 0).rolling(20).sum()
            else:
                df['Retail_Net'], df['Inst_Net'], df['Inst_Cost'] = df['Volume'], 0, np.nan

            min_p, max_p = df['Low'].min(), df['High'].max()
            bins = np.linspace(min_p, max_p, 30)
            df_vpvr = df.copy()
            df_vpvr['Price_Bin'] = pd.cut(df_vpvr['Close'], bins=bins)
            vpvr = df_vpvr.groupby('Price_Bin', observed=False)['Volume'].sum().reset_index()
            vpvr['Bin_Center'] = vpvr['Price_Bin'].apply(lambda x: x.mid)
            poc_price = vpvr.loc[vpvr['Volume'].idxmax()]['Bin_Center'] 
            
            bear_div = df['Close'].iloc[-1] > df['Close'].iloc[-20:-1].max() and df['RSI'].iloc[-1] < df['RSI'].iloc[-20:-1].max()
            bull_div = df['Close'].iloc[-1] < df['Close'].iloc[-20:-1].min() and df['RSI'].iloc[-1] > df['RSI'].iloc[-20:-1].min()
            squeeze = df['BB_Width'].iloc[-1] < df['BB_Width'].rolling(60).min().iloc[-2] * 1.1

            # ==========================================
            # 4. 畫面渲染 UI
            # ==========================================
            if black_horse_score == 4:
                st.markdown("<div class='s-class-horse'>🔥 S 級黑馬訊號發動：量價籌碼完美共振！ 🔥</div>", unsafe_allow_html=True)
            
            stars = "★" * black_horse_score + "☆" * (4 - black_horse_score)
            color = "#FF4B4B" if price_change >= 0 else "#00FF00"
            sign = "▲" if price_change >= 0 else "▼"
            last_date = df.index[-1].strftime('%m/%d')
            
            st.markdown(f"<h3 style='margin-bottom:0;'>{display_title} &nbsp;&nbsp; <span style='font-size: 0.5em; color: #8ab4f8; border: 1px solid #333; padding: 2px 8px; border-radius: 5px; vertical-align: middle;'>{last_date}</span> &nbsp;&nbsp; | &nbsp;&nbsp; 爆發潛力 <span class='potential-stars'>{stars}</span></h3>", unsafe_allow_html=True)
            st.markdown(f"<div class='text-sm' style='margin-bottom: 5px;'>收盤 <span style='color:{color}; font-weight:bold;'>{latest_close:.2f}</span> &nbsp;&nbsp; 漲跌 <span style='color:{color};'>{sign} {abs(price_change):.2f} ({change_pct:.2f}%)</span> &nbsp;&nbsp; | &nbsp;&nbsp; 成交量 <b>{latest_vol:,.0f}</b> 張</div>", unsafe_allow_html=True)
            st.markdown("<hr style='margin: 0 0 10px 0; padding: 0;'>", unsafe_allow_html=True)
            
            tab1, tab2, tab3 = st.tabs(["📊 核心戰情與勝率", "🕵️ 籌碼透視 (法人vs散戶)", "🚀 高階型態 (VPVR/通道)"])
            
            # --------- TAB 1: 核心戰情 (經典回歸) ---------
            with tab1:
                col_l, col_r1, col_r2 = st.columns([2.5, 1, 1])
                with col_l:
                    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.015, row_heights=[0.4, 0.15, 0.15, 0.15, 0.15])
                    fig.add_trace(go.Candlestick(x=x_dates, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
                    fig.add_trace(go.Scatter(x=x_dates, y=df['MA20'], line=dict(color='cyan', width=1), name='MA20'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=x_dates, y=df['MA60'], line=dict(color='magenta', width=1), name='MA60'), row=1, col=1)
                    
                    colors_vol = ['#FF4B4B' if r['Close']>=r['Open'] else '#00FF00' for i, r in df.iterrows()]
                    fig.add_trace(go.Bar(x=x_dates, y=df['Volume'], marker_color=colors_vol, name="成交量"), row=2, col=1)
                    
                    colors_macd = ['#FF4B4B' if v>=0 else '#00FF00' for v in df['OSC']]
                    fig.add_trace(go.Bar(x=x_dates, y=df['OSC'], marker_color=colors_macd, name="MACD柱"), row=3, col=1)
                    fig.add_trace(go.Scatter(x=x_dates, y=df['MACD'], line=dict(color='white', width=1), name='MACD'), row=3, col=1)
                    fig.add_trace(go.Scatter(x=x_dates, y=df['Signal'], line=dict(color='yellow', width=1), name='Signal'), row=3, col=1)
                    
                    fig.add_trace(go.Scatter(x=x_dates, y=df['K'], line=dict(color='yellow', width=1), name='K'), row=4, col=1)
                    fig.add_trace(go.Scatter(x=x_dates, y=df['D'], line=dict(color='cyan', width=1), name='D'), row=4, col=1)
                    fig.add_hline(y=80, line_dash="dot", line_color="red", row=4, col=1)
                    fig.add_hline(y=20, line_dash="dot", line_color="green", row=4, col=1)
                    
                    fig.add_trace(go.Scatter(x=x_dates, y=df['RSI'], line=dict(color='magenta', width=1), name='RSI'), row=5, col=1)
                    
                    # 🐛 修正點：強制將 X 軸設為類別(Category)，防止 Plotly 亂猜年份
                    fig.update_xaxes(type='category', nticks=10, showgrid=True, gridwidth=1, gridcolor='#333')
                    fig.update_layout(height=600, margin=dict(l=0,r=0,t=0,b=0), xaxis_rangeslider_visible=False, template="plotly_dark", showlegend=False)
                    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#333')
                    st.plotly_chart(fig, use_container_width=True)
                
                with col_r1:
                    with st.container(border=True):
                        st.markdown('<div class="section-title">短線進場勝率</div>', unsafe_allow_html=True)
                        fig_gauge = go.Figure(go.Indicator(
                            mode = "gauge+number", value = win_rate, number={'suffix': "%", 'font':{'size': 24}},
                            domain = {'x': [0, 1], 'y': [0, 1]},
                            gauge = {'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"}, 'bar': {'color': "white", 'thickness': 0.2},
                                     'steps': [{'range': [0, 40], 'color': "#FF4B4B"}, {'range': [40, 60], 'color': "#FFA500"}, {'range': [60, 100], 'color': "#00FF00"}]}
                        ))
                        fig_gauge.update_layout(height=130, margin=dict(l=5, r=5, t=5, b=5), paper_bgcolor='rgba(0,0,0,0)', font={'color': "white"})
                        st.plotly_chart(fig_gauge, use_container_width=True)
                    
                    with st.container(border=True):
                        st.markdown('<div class="section-title">黑馬潛力雷達</div>', unsafe_allow_html=True)
                        if len(bh_reasons) > 0:
                            for reason in bh_reasons: st.markdown(f"<div class='text-sm'>{reason}</div>", unsafe_allow_html=True)
                        else: st.markdown("<div class='text-sm'>⏳ 尚未浮現攻擊訊號</div>", unsafe_allow_html=True)

                    with st.container(border=True):
                        st.markdown('<div class="section-title">量價結構</div>', unsafe_allow_html=True)
                        if price_change > 0 and vol_change_pct > 10: st.markdown("<div class='text-sm'>⚠️ <b>健康上漲</b><br>價漲量增，多方強勢。</div>", unsafe_allow_html=True)
                        elif price_change > 0 and vol_change_pct < -10: st.markdown("<div class='text-sm title-red'>🚨 <b>量價背離</b><br>價漲量縮，追價意願不足。</div>", unsafe_allow_html=True)
                        elif price_change < 0 and vol_change_pct > 10: st.markdown("<div class='text-sm title-red'>🚨 <b>殺盤恐慌</b><br>價跌量增，賣壓沉重。</div>", unsafe_allow_html=True)
                        else: st.markdown("<div class='text-sm'>✅ <b>正常盤整</b><br>無明顯背離跡象。</div>", unsafe_allow_html=True)

                with col_r2:
                    with st.container(border=True):
                        if latest_close > df['MA20'].iloc[-1] and bias_20 < 8: st.markdown("<div class='stamp-text' style='color:#FF4B4B; border-color:#FF4B4B;'>強勢多頭</div>", unsafe_allow_html=True)
                        elif bias_20 >= 8: st.markdown("<div class='stamp-text' style='color:#FFA500; border-color:#FFA500;'>短線過熱</div>", unsafe_allow_html=True)
                        else: st.markdown("<div class='stamp-text' style='color:#00FF00; border-color:#00FF00;'>弱勢空頭</div>", unsafe_allow_html=True)
                    
                    with st.container(border=True):
                        st.markdown('<div class="section-title">位階與長線 (近1年)</div>', unsafe_allow_html=True)
                        if base_percentile < 30: base_status = "<span style='color:#00FF00;'>🟢 低基期 (底部區)</span>"
                        elif base_percentile > 70: base_status = "<span style='color:#FF4B4B;'>🔴 高基期 (山頂區)</span>"
                        else: base_status = "<span style='color:#FFA500;'>🟡 中基期 (半山腰)</span>"
                        st.markdown(f"<div class='text-sm'>目前位階： <b>{base_percentile:.1f}%</b><br>{base_status}</div>", unsafe_allow_html=True)

                    with st.container(border=True):
                        st.markdown('<div class="section-title">關鍵防禦價</div>', unsafe_allow_html=True)
                        price_pressure = df['High'].rolling(20).max().iloc[-1]
                        price_support = df['MA20'].iloc[-1]
                        price_strong_support = df['Low'].rolling(20).min().iloc[-1]
                        st.markdown(f"<div class='text-sm'>壓力區： <b>{price_pressure:.1f}</b><br>月線支撐： <b>{price_support:.1f}</b><br>極限支撐： <b>{price_strong_support:.1f}</b></div>", unsafe_allow_html=True)

            # --------- TAB 2: 籌碼透視 ---------
            with tab2:
                c2_l, c2_r = st.columns([2.5, 1.2])
                with c2_l:
                    st.markdown("💡 **紅柱**代表法人買超，**藍線**代表估算的散戶參與度，**黃點**為法人波段成本線。")
                    fig_chip = make_subplots(specs=[[{"secondary_y": True}]])
                    fig_chip.add_trace(go.Bar(x=x_dates, y=df['Inst_Net'], name='三大法人淨買賣', marker_color=['#FF4B4B' if v>=0 else '#00FF00' for v in df['Inst_Net']]), secondary_y=False)
                    fig_chip.add_trace(go.Scatter(x=x_dates, y=df['Retail_Net'], name='散戶交易熱度', line=dict(color='#8ab4f8', width=2)), secondary_y=False)
                    fig_chip.add_trace(go.Scatter(x=x_dates, y=df['Inst_Cost'], name='法人成本線', mode='markers', marker=dict(color='yellow', size=4)), secondary_y=True)
                    fig_chip.add_trace(go.Scatter(x=x_dates, y=df['Close'], name='收盤價', line=dict(color='rgba(255,255,255,0.3)', width=1)), secondary_y=True)
                    
                    fig_chip.update_xaxes(type='category', nticks=10, showgrid=False) # 🐛 修正點：籌碼圖也鎖定文字X軸
                    fig_chip.update_layout(height=450, margin=dict(l=0,r=0,t=0,b=0), template="plotly_dark", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                    st.plotly_chart(fig_chip, use_container_width=True)
                with c2_r:
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

            # --------- TAB 3: 高階型態 ---------
            with tab3:
                c3_l, c3_r = st.columns([3, 1])
                with c3_l:
                    st.markdown("💡 **VPVR (價格成交量分佈)**：右側橫向長條圖代表該價位累積的成交量。最長的那根 (黃虛線) 即為 **POC (鐵板區/主力密集區)**。")
                    fig_vpvr = go.Figure()
                    fig_vpvr.add_trace(go.Candlestick(x=x_dates, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"))
                    fig_vpvr.add_trace(go.Scatter(x=x_dates, y=df['BB_Up'], line=dict(color='rgba(255,255,255,0.2)'), name='布林上軌'))
                    fig_vpvr.add_trace(go.Scatter(x=x_dates, y=df['BB_Dn'], line=dict(color='rgba(255,255,255,0.2)', dash='dot'), name='布林下軌'))
                    
                    fig_vpvr.add_trace(go.Bar(x=vpvr['Volume'], y=vpvr['Bin_Center'], orientation='h', xaxis='x2', marker_color='rgba(138,180,248,0.4)', name='VPVR'))
                    fig_vpvr.add_hline(y=poc_price, line_dash="dash", line_color="yellow", annotation_text="POC 密集區")
                    
                    fig_vpvr.update_xaxes(type='category', nticks=10, showgrid=True, gridwidth=1, gridcolor='#333') # 🐛 修正點：高階圖表也鎖定文字X軸
                    fig_vpvr.update_layout(
                        height=500, margin=dict(l=0,r=0,t=0,b=0), template="plotly_dark", xaxis_rangeslider_visible=False, showlegend=False,
                        xaxis2=dict(overlaying='x', side='top', showgrid=False, visible=False)
                    )
                    st.plotly_chart(fig_vpvr, use_container_width=True)

                with c3_r:
                    with st.container(border=True):
                        st.markdown('<div class="section-title">演算法雷達</div>', unsafe_allow_html=True)
                        st.markdown(f"**POC 鐵板價：** `{poc_price:.1f}`")
                        
                        st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
                        if squeeze: st.markdown("🎯 **布林極度壓縮**<br><span class='text-sm'>帶寬創近期新低，隨時準備大爆發表態！</span>", unsafe_allow_html=True)
                        else: st.markdown("✅ **通道正常運行**<br><span class='text-sm'>無明顯壓縮跡象。</span>", unsafe_allow_html=True)
                        
                        st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
                        if bear_div: st.markdown("🚨 **高檔頂背離**<br><span class='text-sm text-red'>股價創新高但 RSI 未過高，慎防誘多反轉！</span>", unsafe_allow_html=True)
                        elif bull_div: st.markdown("🔥 **低檔底背離**<br><span class='text-sm text-green'>股價破底但 RSI 拒絕下跌，可能即將反彈！</span>", unsafe_allow_html=True)
                        else: st.markdown("✅ **動能健康**<br><span class='text-sm'>無背離異常。</span>", unsafe_allow_html=True)

        except Exception as e:
            st.error(f"資料處理發生錯誤：{e}")
            st.exception(e)
