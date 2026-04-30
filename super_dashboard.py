import streamlit as st
import yfinance as yf
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
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🌟 智慧雙向字典系統 (代號 <-> 名稱)
# ==========================================
@st.cache_data(ttl=86400)
def load_stock_dicts():
    try:
        dl_info = DataLoader()
        info_df = dl_info.taiwan_stock_info()
        # 字典 1：代號找名稱 (例如 '2330' -> '台積電')
        id_to_name = dict(zip(info_df['stock_id'].astype(str), info_df['stock_name']))
        # 字典 2：名稱找代號 (例如 '台積電' -> '2330')
        name_to_id = dict(zip(info_df['stock_name'], info_df['stock_id'].astype(str)))
        return id_to_name, name_to_id
    except Exception as e:
        return {}, {}

stock_dict, name_to_id_dict = load_stock_dicts()

def color_num(val):
    if val > 0: return f"<span class='text-red'>+{val:,.0f}</span>"
    elif val < 0: return f"<span class='text-green'>{val:,.0f}</span>"
    else: return "0"

# ==========================================
# 2. 上方橫式控制列
# ==========================================
col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1.5, 1.5, 6])

with col_ctrl1:
    # ✨ 這裡把 Placeholder 提示字改成了可以輸入中文
    raw_input = st.text_input("搜尋", "6269", label_visibility="collapsed", placeholder="輸入代號或中文名稱 (如: 6269 或 台郡)")
with col_ctrl2:
    analyze_btn = st.button("🔥 啟動全板面解析", use_container_width=True)
with col_ctrl3:
    st.markdown("<div style='margin-top: 8px; font-size: 0.9em; color:gray;'>※ 支援中文字串智慧搜尋</div>", unsafe_allow_html=True)

# ==========================================
# 3. 核心運算引擎
# ==========================================
if analyze_btn or raw_input:
    # ✨ 智慧字串解析邏輯
    search_term = str(raw_input).strip() # 去除前後空白
    
    if search_term in stock_dict:
        # 如果使用者輸入的是數字代號 (例如 2330)
        raw_ticker = search_term
    elif search_term in name_to_id_dict:
        # 如果使用者輸入的是中文名稱 (例如 台積電)，自動轉換成代號
        raw_ticker = name_to_id_dict[search_term]
    else:
        # 如果找不到，就預設直接拿使用者的輸入去查 (防呆機制)
        raw_ticker = search_term

    ticker_yf = f"{raw_ticker}.TW"
    stock_name = stock_dict.get(raw_ticker, "")
    display_title = f"{raw_ticker} {stock_name}" if stock_name else raw_ticker
    
    with st.spinner(f'鎖定目標 [{display_title}] ... 啟動戰情解析中...'):
        try:
            # --- [技術面] ---
            stock = yf.Ticker(ticker_yf)
            df_full = stock.history(period="1y")
            if df_full.empty:
                df_full = yf.Ticker(f"{raw_ticker}.TWO").history(period="1y")
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

            # --- [籌碼面] ---
            dl = DataLoader()
            end_date = datetime.date.today()
            start_date = end_date - datetime.timedelta(days=45)
            df_chip = dl.taiwan_stock_institutional_investors(stock_id=raw_ticker, start_date=str(start_date), end_date=str(end_date))
            
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
                    
                    def safe_sum(df_target, col):
                        return df_target[col].sum() if col in df_target.columns else 0
                        
                    chip_sum_10['外資'] = safe_sum(last_10, '外資')
                    chip_sum_10['投信'] = safe_sum(last_10, '投信')
                    chip_sum_10['自營商'] = safe_sum(last_10, '自營商')
                    chip_sum_10['合計'] = chip_sum_10['外資'] + chip_sum_10['投信'] + chip_sum_10['自營商']
                    
                    chip_sum_5['外資'] = safe_sum(last_5, '外資')
                    chip_sum_5['投信'] = safe_sum(last_5, '投信')
                    chip_sum_5['自營商'] = safe_sum(last_5, '自營商')
                    chip_sum_5['合計'] = chip_sum_5['外資'] + chip_sum_5['投信'] + chip_sum_5['自營商']
                    
                    today_chip['外資'] = safe_sum(last_1, '外資')
                    today_chip['投信'] = safe_sum(last_1, '投信')
                    today_chip['自營商'] = safe_sum(last_1, '自營商')
                    today_chip['合計'] = today_chip['外資'] + today_chip['投信'] + today_chip['自營商']

            # --- [黑馬潛力鑑定演算法] ---
            black_horse_score = 0
            bh_reasons = []
            if base_percentile < 60:
                black_horse_score += 1
                bh_reasons.append("✅ 基期優勢 (未過熱)")
            if latest_close > df['MA20'].iloc[-1] and latest_close > df['MA60'].iloc[-1]:
                black_horse_score += 1
                bh_reasons.append("✅ 趨勢轉強 (站上均線)")
            if latest_vol > avg_vol_5 * 1.5:
                black_horse_score += 1
                bh_reasons.append("✅ 量能點火 (帶量突破)")
            if chip_sum_5['合計'] > 300:
                black_horse_score += 1
                bh_reasons.append("✅ 籌碼進駐 (法人買超)")

            win_rate = 50
            if latest_close > df['MA20'].iloc[-1]: win_rate += 15
            else: win_rate -= 15
            if df['MACD'].iloc[-1] > df['Signal'].iloc[-1]: win_rate += 10
            if chip_sum_10['合計'] > 0: win_rate += 15
            if bias_20 > 8 or df['K'].iloc[-1] > 80: win_rate -= 15
            if base_percentile > 80: win_rate -= 10
            if base_percentile < 20 and df['MACD'].iloc[-1] > df['Signal'].iloc[-1]: win_rate += 10
            win_rate = max(0, min(100, win_rate))

            # ==========================================
            # 4. 畫面渲染：滿版四欄配置
            # ==========================================
            if black_horse_score == 4:
                st.markdown("<div class='s-class-horse'>🔥 S 級黑馬訊號發動：量價籌碼完美共振！ 🔥</div>", unsafe_allow_html=True)
            
            stars = "★" * black_horse_score + "☆" * (4 - black_horse_score)
            st.markdown(f"<h3 style='margin-bottom:0;'>{display_title} &nbsp;&nbsp; <span style='font-size: 0.5em; color: #8ab4f8; border: 1px solid #333; padding: 2px 8px; border-radius: 5px; vertical-align: middle;'>{date_str}</span> &nbsp;&nbsp; | &nbsp;&nbsp; 爆發潛力 <span class='potential-stars'>{stars}</span></h3>", unsafe_allow_html=True)
            st.markdown(f"<div class='text-sm' style='margin-bottom: 5px;'>收盤 <span style='color:{color}; font-weight:bold;'>{latest_close:.2f}</span> &nbsp;&nbsp; 漲跌 <span style='color:{color};'>{sign} {abs(price_change):.2f} ({change_pct:.2f}%)</span> &nbsp;&nbsp; | &nbsp;&nbsp; 成交量 <b>{latest_vol:,.0f}</b> 張</div>", unsafe_allow_html=True)
            st.markdown("<hr style='margin: 0 0 10px 0; padding: 0;'>", unsafe_allow_html=True)

            col_left, col_mid, col_r1, col_r2 = st.columns([1.6, 1.1, 0.85, 0.85])

            # ------------------------------------------
            # 【第 1 欄：技術面巨幅圖表】
            # ------------------------------------------
            with col_left:
                with st.container(border=True):
                    st.markdown('<div class="section-title">技術面分析</div>', unsafe_allow_html=True)
                    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.015, row_heights=[0.4, 0.15, 0.15, 0.15, 0.15])
                    
                    fig.add_trace(go.Candlestick(x=x_dates, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線", increasing_line_color='#FF4B4B', decreasing_line_color='#00FF00'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=x_dates, y=df['MA20'], line=dict(color='cyan', width=1), name='MA20'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=x_dates, y=df['MA60'], line=dict(color='magenta', width=1), name='MA60'), row=1, col=1)
                    
                    colors_vol = ['#FF4B4B' if row['Close'] >= row['Open'] else '#00FF00' for index, row in df.iterrows()]
                    fig.add_trace(go.Bar(x=x_dates, y=df['Volume'], marker_color=colors_vol, name="成交量(張)"), row=2, col=1)
                    
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
                    fig.update_layout(height=520, margin=dict(l=0, r=0, t=5, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False, xaxis_rangeslider_visible=False)
                    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#333')
                    st.plotly_chart(fig, use_container_width=True)

                with st.container(border=True):
                    if latest_close > df['MA20'].iloc[-1] and bias_20 < 8:
                        st.markdown("<div class='stamp-text' style='color:#FF4B4B; border-color:#FF4B4B;'>強勢多頭 (逢回可佈局)</div>", unsafe_allow_html=True)
                    elif bias_20 >= 8:
                        st.markdown("<div class='stamp-text' style='color:#FFA500; border-color:#FFA500;'>短線過熱 (乖離偏高)</div>", unsafe_allow_html=True)
                    else:
                        st.markdown("<div class='stamp-text' style='color:#00FF00; border-color:#00FF00;'>弱勢空頭 (嚴控風險)</div>", unsafe_allow_html=True)

            # ------------------------------------------
            # 【第 2 欄：籌碼疊加與紅綠明細表】
            # ------------------------------------------
            with col_mid:
                with st.container(border=True):
                    st.markdown('<div class="section-title">法人籌碼與股價疊加圖</div>', unsafe_allow_html=True)
                    if not df_chip.empty:
                        last_20_chips = pivot_df.tail(20)
                        display_cols = [col for col in ['外資', '投信', '自營商'] if col in pivot_df.columns]
                        
                        chip_dates = last_20_chips.index.strftime('%m-%d')
                        
                        price_dict = dict(zip(x_dates, df['Close']))
                        chip_close_prices = [price_dict.get(d, None) for d in chip_dates]
                        
                        fig_chip = make_subplots(specs=[[{"secondary_y": True}]])
                        
                        colors_chip = {'外資': '#8ab4f8', '投信': '#FF4B4B', '自營商': '#00FF00'}
                        for col in display_cols:
                            fig_chip.add_trace(go.Bar(x=chip_dates, y=last_20_chips[col], name=col, marker_color=colors_chip.get(col, 'white')), secondary_y=False)
                            
                        fig_chip.add_trace(go.Scatter(x=chip_dates, y=chip_close_prices, name='收盤價', line=dict(color='yellow', width=2), mode='lines+markers', marker=dict(size=4)), secondary_y=True)
                        
                        fig_chip.update_layout(
                            height=200, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                            barmode='group', legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1, font=dict(size=10))
                        )
                        fig_chip.update_xaxes(type='category', nticks=6, showgrid=False)
                        fig_chip.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#333', secondary_y=False)
                        fig_chip.update_yaxes(showgrid=False, secondary_y=True)
                        st.plotly_chart(fig_chip, use_container_width=True)
                        
                        html_table = f"""
                        <table class="chip-table">
                            <tr>
                                <th></th><th>外資</th><th>投信</th><th>自營商</th><th>合計</th>
                            </tr>
                            <tr>
                                <td class="row-title">今日</td>
                                <td>{color_num(today_chip['外資'])}</td>
                                <td>{color_num(today_chip['投信'])}</td>
                                <td>{color_num(today_chip['自營商'])}</td>
                                <td>{color_num(today_chip['合計'])}</td>
                            </tr>
                            <tr>
                                <td class="row-title">近5日</td>
                                <td>{color_num(chip_sum_5['外資'])}</td>
                                <td>{color_num(chip_sum_5['投信'])}</td>
                                <td>{color_num(chip_sum_5['自營商'])}</td>
                                <td>{color_num(chip_sum_5['合計'])}</td>
                            </tr>
                            <tr>
                                <td class="row-title">近10日</td>
                                <td>{color_num(chip_sum_10['外資'])}</td>
                                <td>{color_num(chip_sum_10['投信'])}</td>
                                <td>{color_num(chip_sum_10['自營商'])}</td>
                                <td>{color_num(chip_sum_10['合計'])}</td>
                            </tr>
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
                
                with st.container(border=True):
                    st.markdown('<div class="section-title">可能路徑</div>', unsafe_allow_html=True)
                    target_up = price_pressure * 1.05
                    st.markdown(f"<div class='text-sm'>❶ <b>突破：</b> <span style='color:#FF4B4B;'>{price_pressure:.1f}</span> ➜ <span style='color:#FF4B4B;'>{target_up:.1f}</span><br>❷ <b>回測：</b> <span style='color:#00FF00;'>{latest_close*0.97:.1f}</span> ➜ <span style='color:#00FF00;'>{price_support:.1f}</span><br>❸ <b>轉空：</b> 跌破 <span style='color:#00FF00;'>{price_strong_support:.1f}</span></div>", unsafe_allow_html=True)

            # ------------------------------------------
            # 【第 3 欄：黑馬鑑定與勝率】
            # ------------------------------------------
            with col_r1:
                with st.container(border=True):
                    st.markdown('<div class="section-title">黑馬潛力雷達</div>', unsafe_allow_html=True)
                    if len(bh_reasons) > 0:
                        for reason in bh_reasons:
                            st.markdown(f"<div class='text-sm'>{reason}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown("<div class='text-sm'>⏳ 尚未浮現攻擊訊號</div>", unsafe_allow_html=True)

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
                    st.markdown('<div class="section-title">位階與長線 (近1年)</div>', unsafe_allow_html=True)
                    if base_percentile < 30: base_status = "<span style='color:#00FF00;'>🟢 低基期 (底部區)</span>"
                    elif base_percentile > 70: base_status = "<span style='color:#FF4B4B;'>🔴 高基期 (山頂區)</span>"
                    else: base_status = "<span style='color:#FFA500;'>🟡 中基期 (半山腰)</span>"
                        
                    st.markdown(f"<div class='text-sm'>目前位階： <b>{base_percentile:.1f}%</b><br>{base_status}</div>", unsafe_allow_html=True)
                    
                with st.container(border=True):
                    st.markdown('<div class="section-title">操作建議</div>', unsafe_allow_html=True)
                    st.markdown("<div class='text-sm'>⭐ 評估追高風險<br>⭐ 等待回測支撐</div>", unsafe_allow_html=True)

            # ------------------------------------------
            # 【第 4 欄：量價結構與警示】
            # ------------------------------------------
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

        except Exception as e:
            st.error(f"資料處理發生錯誤：{e}。請確認您的輸入是否正確。")