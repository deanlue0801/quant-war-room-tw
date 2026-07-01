import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import utils

def calculate_adx(df, period=14):
    """計算 ADX 趨勢指標 (使用 Pandas 逼近 Wilder 平滑法)"""
    df_temp = df.copy()
    df_temp['H-L'] = df_temp['High'] - df_temp['Low']
    df_temp['H-PC'] = abs(df_temp['High'] - df_temp['Close'].shift(1))
    df_temp['L-PC'] = abs(df_temp['Low'] - df_temp['Close'].shift(1))
    df_temp['TR'] = df_temp[['H-L', 'H-PC', 'L-PC']].max(axis=1)

    df_temp['+DM'] = np.where((df_temp['High'] - df_temp['High'].shift(1)) > (df_temp['Low'].shift(1) - df_temp['Low']),
                              np.maximum(df_temp['High'] - df_temp['High'].shift(1), 0), 0)
    df_temp['-DM'] = np.where((df_temp['Low'].shift(1) - df_temp['Low']) > (df_temp['High'] - df_temp['High'].shift(1)),
                              np.maximum(df_temp['Low'].shift(1) - df_temp['Low'], 0), 0)

    # 近似 Wilder's Smoothing
    df_temp['TR_14'] = df_temp['TR'].ewm(alpha=1/period, adjust=False).mean()
    df_temp['+DM_14'] = df_temp['+DM'].ewm(alpha=1/period, adjust=False).mean()
    df_temp['-DM_14'] = df_temp['-DM'].ewm(alpha=1/period, adjust=False).mean()

    df_temp['+DI'] = 100 * (df_temp['+DM_14'] / df_temp['TR_14'])
    df_temp['-DI'] = 100 * (df_temp['-DM_14'] / df_temp['TR_14'])
    
    df_temp['DX'] = 100 * (abs(df_temp['+DI'] - df_temp['-DI']) / (df_temp['+DI'] + df_temp['-DI']))
    adx = df_temp['DX'].ewm(alpha=1/period, adjust=False).mean()
    return adx

def render():
    # 取得共用字典
    stock_dict, name_to_id_dict, _ = utils.load_stock_dicts()
    
    with st.form(key='search_form_666', clear_on_submit=False):
        col_666_1, col_666_2, col_666_3 = st.columns([1.5, 1.5, 6])
        with col_666_1:
            ticker_60 = st.text_input("搜尋", "", label_visibility="collapsed", placeholder="輸入代號並按 Enter")
        with col_666_2:
            submit_666 = st.form_submit_button("🔥 啟動 666 戰法", use_container_width=True)
        with col_666_3:
            st.markdown("<div style='margin-top: 8px; font-size: 0.9em; color:gray;'>※ 專注 60分K線，結合多週期均線、量能、ADX 與 MACD 精準捕捉轉折</div>", unsafe_allow_html=True)
        
        # 進階設定區塊 (包在 form 內，送出時一併套用)
        with st.expander("⚙️ 戰法參數與濾網設定", expanded=True):
            col_set1, col_set2, col_set3 = st.columns(3)
            with col_set1:
                kd_mode = st.selectbox("KD 指標參數", ["60,3,3 (666戰法)", "14,3,3 (標準波段)", "9,3,3 (短線轉折)"])
            with col_set2:
                show_ma = st.multiselect("顯示均線", ["MA5", "MA35", "MA60", "MA200"], default=["MA5", "MA60"])
            with col_set3:
                show_bb = st.checkbox("開啟布林通道 (20, 2)", value=False)
                
    if submit_666 and ticker_60:
        raw_ticker_60 = name_to_id_dict.get(ticker_60.strip(), ticker_60.strip()) if ticker_60.strip() not in stock_dict else ticker_60.strip()
        stock_name_60 = stock_dict.get(raw_ticker_60, "")
        display_title_60 = f"{raw_ticker_60} {stock_name_60}" if stock_name_60 else raw_ticker_60
        
        with st.spinner(f'鎖定目標 [{display_title_60}] ... 繪製 60分K 戰略圖中...'):
            df_60 = utils.fetch_tech_data_fugle_60m(raw_ticker_60)
            
            # --- 強制清理資料 ---
            if not df_60.empty:
                df_60 = df_60.loc[:, ~df_60.columns.duplicated()]
                for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    if col in df_60.columns:
                        df_60[col] = pd.to_numeric(df_60[col], errors='coerce')
                df_60[['Open', 'High', 'Low', 'Close']] = df_60[['Open', 'High', 'Low', 'Close']].ffill()
                if 'Volume' in df_60.columns:
                    df_60['Volume'] = df_60['Volume'].fillna(0)
                df_60 = df_60.dropna(subset=['Close'])
            # ----------------------------------------------------
            
            if df_60.empty or len(df_60) < 60:
                st.error(f"🚨 無法取得 [{display_title_60}] 足夠的 60 分鐘 K 線資料。")
                return
                
            # 1. 計算多週期 MA
            df_60['MA5'] = df_60['Close'].rolling(window=5).mean()
            df_60['MA35'] = df_60['Close'].rolling(window=35).mean()
            df_60['MA60'] = df_60['Close'].rolling(window=60).mean()
            df_60['MA200'] = df_60['Close'].rolling(window=200).mean()
            
            # 2. 計算布林通道 (20, 2)
            df_60['BB_Mid'] = df_60['Close'].rolling(window=20).mean()
            df_60['BB_Std'] = df_60['Close'].rolling(window=20).std()
            df_60['BB_Up'] = df_60['BB_Mid'] + (2 * df_60['BB_Std'])
            df_60['BB_Low'] = df_60['BB_Mid'] - (2 * df_60['BB_Std'])
            
            # 3. 計算成交量 VMA(5)
            df_60['VMA5'] = df_60['Volume'].rolling(window=5).mean()

            # 4. 計算 ADX(14)
            df_60['ADX'] = calculate_adx(df_60, period=14)
            
            # 5. 計算動態 KD
            if kd_mode == "60,3,3 (666戰法)": kd_win = 60
            elif kd_mode == "14,3,3 (標準波段)": kd_win = 14
            else: kd_win = 9
                
            low_min = df_60['Low'].rolling(window=kd_win).min()
            high_max = df_60['High'].rolling(window=kd_win).max()
            
            # 避免分母為0
            denominator = high_max - low_min
            denominator = denominator.replace(0, np.nan)
            
            df_60['RSV'] = 100 * ((df_60['Close'] - low_min) / denominator)
            df_60['RSV'] = df_60['RSV'].fillna(50)
            
            k_list, d_list = [], []
            for i, rsv in enumerate(df_60['RSV']):
                if i == 0 or pd.isna(rsv):
                    k_list.append(50.0)
                    d_list.append(50.0)
                else:
                    k_list.append((2/3) * k_list[-1] + (1/3) * rsv)
                    d_list.append((2/3) * d_list[-1] + (1/3) * k_list[-1])
            df_60['K'] = k_list
            df_60['D'] = d_list

            # 6. 計算 MACD (12, 26, 9)
            exp1 = df_60['Close'].ewm(span=12, adjust=False).mean()
            exp2 = df_60['Close'].ewm(span=26, adjust=False).mean()
            df_60['MACD'] = exp1 - exp2
            df_60['Signal'] = df_60['MACD'].ewm(span=9, adjust=False).mean()
            df_60['OSC'] = df_60['MACD'] - df_60['Signal']
            
            # --- 擷取最新數值 ---
            closes = df_60['Close'].values
            latest_60m_close = float(closes[-1])
            prev_close = float(closes[-2])
            price_change = latest_60m_close - prev_close
            change_pct = (price_change / prev_close) * 100 if prev_close != 0 else 0
            color = "#FF4B4B" if price_change >= 0 else "#00FF00"
            sign = "▲" if price_change >= 0 else "▼"
            
            latest_vol = float(df_60['Volume'].values[-1])
            vma5_val = float(df_60['VMA5'].values[-1])
            adx_val = float(df_60['ADX'].values[-1])
            
            ma60_60m = float(df_60['MA60'].values[-1])
            
            k_val = float(df_60['K'].values[-1])
            d_val = float(df_60['D'].values[-1])
            k_prev = float(df_60['K'].values[-2])
            d_prev = float(df_60['D'].values[-2])

            osc_val = float(df_60['OSC'].values[-1])
            osc_prev = float(df_60['OSC'].values[-2])
            
            # 扣抵防守線量化計算
            deduct_prices = closes[-60:-50]
            avg_deduct = float(deduct_prices.mean()) if len(deduct_prices) > 0 else 0
            next_deduct_price = float(closes[-60]) if len(closes) >= 60 else 0
            
            # --- 畫面頂部資訊 ---
            last_date = df_60.index[-1]
            date_str = f"{last_date.strftime('%m/%d %H:%M')} (即時)"
            st.markdown(f"<h3 style='margin-bottom:0;'>{display_title_60} &nbsp;&nbsp; <span style='font-size: 0.5em; color: #8ab4f8; border: 1px solid #333; padding: 2px 8px; border-radius: 5px; vertical-align: middle;'>{date_str}</span></h3>", unsafe_allow_html=True)
            st.markdown(f"<div class='text-sm' style='margin-bottom: 15px;'>收盤 <span style='color:{color}; font-weight:bold;'>{latest_60m_close:.2f}</span> &nbsp;&nbsp; 漲跌 <span style='color:{color};'>{sign} {abs(price_change):.2f} ({change_pct:.2f}%)</span> &nbsp;&nbsp; | &nbsp;&nbsp; 當前K線量能 <b>{latest_vol:,.0f}</b> 張</div>", unsafe_allow_html=True)
            st.markdown("<hr style='margin: 0 0 10px 0; padding: 0;'>", unsafe_allow_html=True)

            # --- 橫盤智能提示 ---
            if not pd.isna(adx_val) and adx_val < 25:
                st.markdown("""
                <div style='background-color: rgba(255, 165, 0, 0.1); border-left: 4px solid #FFA500; padding: 10px; margin-bottom: 15px; border-radius: 4px;'>
                    <b style='color:#FFA500;'>💡 系統偵測：目前處於無趨勢橫盤區間 (ADX < 25)</b><br>
                    <span style='font-size:0.9em; color:#ccc;'>波動率收斂，MACD 易產生雜訊。建議將上方 KD 參數切換至 <b>9,3,3 (短線轉折)</b> 進行區間高拋低吸。</span>
                </div>
                """, unsafe_allow_html=True)

            # --- 左圖右表排版 ---
            col_left, col_right = st.columns([2.2, 1.1])
            
            with col_left:
                with st.container(border=True):
                    st.markdown('<div class="section-title">60分K線與動能指標可視化</div>', unsafe_allow_html=True)
                    x_dates = df_60.index.strftime('%m-%d %H:%M').tolist()
                    
                    fig_60 = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.4, 0.2, 0.2, 0.2])
                    
                    # Row 1: K線與動態均線 / 布林通道
                    fig_60.add_trace(go.Candlestick(x=x_dates, open=df_60['Open'], high=df_60['High'], low=df_60['Low'], close=df_60['Close'], name="K線", increasing_line_color='#FF4B4B', decreasing_line_color='#00FF00'), row=1, col=1)
                    
                    ma_colors = {"MA5": "white", "MA35": "yellow", "MA60": "orange", "MA200": "purple"}
                    for ma in show_ma:
                        fig_60.add_trace(go.Scatter(x=x_dates, y=df_60[ma], line=dict(color=ma_colors.get(ma, 'blue'), width=1.5), name=ma), row=1, col=1)
                        
                    if show_bb:
                        fig_60.add_trace(go.Scatter(x=x_dates, y=df_60['BB_Up'], line=dict(color='rgba(173, 216, 230, 0.5)', width=1, dash='dot'), name='BB 上軌'), row=1, col=1)
                        fig_60.add_trace(go.Scatter(x=x_dates, y=df_60['BB_Low'], line=dict(color='rgba(173, 216, 230, 0.5)', width=1, dash='dot'), fill='tonexty', fillcolor='rgba(173, 216, 230, 0.1)', name='BB 下軌'), row=1, col=1)
                    
                    # Row 2: 成交量與 VMA
                    colors_vol = ['#FF4B4B' if row['Close'] >= row['Open'] else '#00FF00' for index, row in df_60.iterrows()]
                    fig_60.add_trace(go.Bar(x=x_dates, y=df_60['Volume'], marker_color=colors_vol, name="成交量"), row=2, col=1)
                    fig_60.add_trace(go.Scatter(x=x_dates, y=df_60['VMA5'], line=dict(color='yellow', width=1.5), name="5均量"), row=2, col=1)

                    # Row 3: KD
                    fig_60.add_trace(go.Scatter(x=x_dates, y=df_60['K'], line=dict(color='yellow', width=1.5), name=f'K({kd_win})'), row=3, col=1)
                    fig_60.add_trace(go.Scatter(x=x_dates, y=df_60['D'], line=dict(color='cyan', width=1.5), name=f'D({kd_win})'), row=3, col=1)
                    fig_60.add_hline(y=80, line_dash="dot", line_color="red", row=3, col=1)
                    fig_60.add_hline(y=20, line_dash="dot", line_color="green", row=3, col=1)

                    # Row 4: MACD
                    colors_macd = ['#FF4B4B' if val >= 0 else '#00FF00' for val in df_60['OSC']]
                    fig_60.add_trace(go.Bar(x=x_dates, y=df_60['OSC'], marker_color=colors_macd, name="MACD柱"), row=4, col=1)
                    fig_60.add_trace(go.Scatter(x=x_dates, y=df_60['MACD'], line=dict(color='white', width=1.5), name='MACD'), row=4, col=1)
                    fig_60.add_trace(go.Scatter(x=x_dates, y=df_60['Signal'], line=dict(color='yellow', width=1.5), name='Signal'), row=4, col=1)
                    
                    fig_60.update_xaxes(type='category', nticks=12, showgrid=True, gridwidth=1, gridcolor='#333')
                    fig_60.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#333')
                    fig_60.update_layout(height=850, margin=dict(l=0, r=0, t=5, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False, xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig_60, use_container_width=True)

            with col_right:
                with st.container(border=True):
                    st.markdown("<div class='section-title'>趨勢與動能分析</div>", unsafe_allow_html=True)
                    
                    # ADX 狀態
                    adx_status = "🔥 趨勢成型" if adx_val >= 25 else "⚖️ 橫盤震盪"
                    adx_color = "#FF4B4B" if adx_val >= 25 else "gray"
                    
                    # 60MA 狀態
                    trend_status = "✅ 多頭 (站上 60MA)" if latest_60m_close > ma60_60m else "🚨 空頭 (跌破 60MA)"
                    trend_color = "#FF4B4B" if latest_60m_close > ma60_60m else "#00FF00"
                    
                    # KD 狀態
                    kd_status = "⚖️ 中性整理"
                    kd_color = "gray"
                    if k_val > d_val and k_prev <= d_prev: kd_status, kd_color = "🔥 黃金交叉", "#FF4B4B"
                    elif k_val < d_val and k_prev >= d_prev: kd_status, kd_color = "🔪 死亡交叉", "#00FF00"

                    # MACD 狀態
                    macd_status = "⚖️ 盤整"
                    macd_color = "gray"
                    if osc_val > 0 and osc_val > osc_prev: macd_status, macd_color = "🔥 多頭增溫", "#FF4B4B"
                    elif osc_val > 0 and osc_val <= osc_prev: macd_status, macd_color = "⚠️ 多頭收斂", "gray"
                    elif osc_val < 0 and osc_val < osc_prev: macd_status, macd_color = "🔪 空頭擴散", "#00FF00"
                    elif osc_val < 0 and osc_val >= osc_prev: macd_status, macd_color = "🟢 空頭收斂", "#FF4B4B"
                    
                    st.markdown(f"""
                    <div style='margin-bottom: 8px;'><b>📍 趨勢強度 (ADX)：</b> <span style='color:{adx_color}; font-weight:bold;'>{adx_status}</span> <span style='font-size: 0.85em; color:gray;'>({adx_val:.1f})</span></div>
                    <div style='margin-bottom: 8px;'><b>📍 60MA 狀態：</b> <span style='color:{trend_color}; font-weight:bold;'>{trend_status}</span></div>
                    <div style='margin-bottom: 8px;'><b>📍 KD 狀態：</b> <span style='color:{kd_color}; font-weight:bold;'>{kd_status}</span> <span style='font-size: 0.85em; color:gray;'>(K={k_val:.1f}, D={d_val:.1f})</span></div>
                    <div><b>📍 MACD 狀態：</b> <span style='color:{macd_color}; font-weight:bold;'>{macd_status}</span></div>
                    """, unsafe_allow_html=True)
                
                with st.container(border=True):
                    dist_pct = ((latest_60m_close - avg_deduct) / avg_deduct) * 100 if avg_deduct != 0 else 0
                    dist_sign = "+" if dist_pct >= 0 else ""
                    dist_color = "#FF4B4B" if dist_pct >= 0 else "#00FF00"
                    
                    st.markdown(f"""
                    <div class='deduct-box' style='border-color: {dist_color}; padding: 15px; border-radius: 8px; border-width: 1px; border-style: solid; background: rgba(255,255,255,0.02);'>
                        <h4 style='color: {dist_color}; margin-top: 0; margin-bottom: 15px;'>🛡️ 均線轉折防守關鍵</h4>
                        <ul style='font-size: 0.9em; padding-left: 20px; line-height: 1.8; color: #ccc;'>
                            <li><b>下小時均線上揚門檻：</b> <span style='color:white; font-size: 1.1em;'>{next_deduct_price:.2f}</span></li>
                            <li style='margin-top: 5px;'><b>波段 10 小時防禦線：</b> <span style='color:white; font-size: 1.1em;'>{avg_deduct:.2f}</span></li>
                            <li style='margin-top: 5px;'><b>目前股價安全距離：</b> <span style='color:{dist_color}; font-weight:bold; font-size: 1.2em;'>{dist_sign}{dist_pct:.2f}%</span></li>
                        </ul>
                    </div>
                    """, unsafe_allow_html=True)

                with st.container(border=True):
                    st.markdown("<div class='section-title'>💻 系統交易訊號</div>", unsafe_allow_html=True)
                    
                    # 加入 ADX 與 VMA 的嚴格濾網
                    if latest_60m_close > ma60_60m and k_val > d_val and k_prev <= d_prev and k_val < 40 and adx_val >= 20 and latest_vol > vma5_val:
                        st.markdown("""
                        <div class='signal-buy' style='margin-top:0; padding:10px;'>
                            <div style='font-size:1.1em;'>🔥 【強勢極佳買點】</div>
                            <p style='font-size: 0.8em; color: white; font-weight: normal; margin-bottom: 0; line-height: 1.4; text-align: left; margin-top:5px;'>
                            站上 60MA 且量能大於 5均量，ADX 顯示具備趨勢動能，KD 低檔黃金交叉。<br><b>對策：</b>建立部位，防守點設於 60MA 之下。
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
                    elif latest_60m_close < ma60_60m:
                        st.markdown("""
                        <div class='signal-sell' style='margin-top:0; padding:10px;'>
                            <div style='font-size:1.1em;'>🚨 【強制停損/禁做多】</div>
                            <p style='font-size: 0.8em; color: white; font-weight: normal; margin-bottom: 0; line-height: 1.4; text-align: left; margin-top:5px;'>
                            跌破 60MA，波段趨勢轉弱。<br><b>對策：</b>多單應立即停損減碼，嚴禁進場接刀。
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
                    elif latest_60m_close > ma60_60m and k_val < d_val and k_prev >= d_prev and k_val > 70:
                        st.markdown("""
                        <div class='signal-sell' style='margin-top:0; padding:10px;'>
                            <div style='font-size:1.1em;'>💰 【停利警戒】動能衰退</div>
                            <p style='font-size: 0.8em; color: white; font-weight: normal; margin-bottom: 0; line-height: 1.4; text-align: left; margin-top:5px;'>
                            高檔死亡交叉，買盤即將耗盡。<br><b>對策：</b>強烈建議分批獲利了結。
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        action_text = "未達極端轉折。在車上請續抱；空手請等待。"
                        if latest_60m_close > ma60_60m and latest_60m_close > avg_deduct: action_text += "<br><span style='color:#FF4B4B;'>(目前 60MA 持續向上助漲中)</span>"
                        if adx_val < 25: action_text += "<br><span style='color:#FFA500;'>(量縮盤整中，請留意假突破風險)</span>"
                        
                        st.markdown(f"""
                        <div class='signal-wait' style='margin-top:0; padding:10px;'>
                            <div style='font-size:1.1em; font-weight:bold; color:#FFA500;'>⏳ 觀望中</div>
                            <p style='font-size: 0.8em; margin-bottom: 0; margin-top:5px; text-align:left; color:#ccc; line-height: 1.4;'>{action_text}</p>
                        </div>
                        """, unsafe_allow_html=True)
