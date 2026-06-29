import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import utils

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
            st.markdown("<div style='margin-top: 8px; font-size: 0.9em; color:gray;'>※ 專注 60分K線，結合 60MA、KD 與 MACD 精準捕捉波段轉折點</div>", unsafe_allow_html=True)
        
    if submit_666 and ticker_60:
        raw_ticker_60 = name_to_id_dict.get(ticker_60.strip(), ticker_60.strip()) if ticker_60.strip() not in stock_dict else ticker_60.strip()
        stock_name_60 = stock_dict.get(raw_ticker_60, "")
        display_title_60 = f"{raw_ticker_60} {stock_name_60}" if stock_name_60 else raw_ticker_60
        
        with st.spinner(f'鎖定目標 [{display_title_60}] ... 繪製 60分K 戰略圖中...'):
            df_60 = utils.fetch_tech_data_fugle_60m(raw_ticker_60)
            
            # --- 強制清理資料，防止 NoneType 造成運算錯誤 ---
            if not df_60.empty:
                df_60 = df_60.loc[:, ~df_60.columns.duplicated()]
                for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    if col in df_60.columns:
                        df_60[col] = pd.to_numeric(df_60[col], errors='coerce')
                # 填補空缺值
                df_60[['Open', 'High', 'Low', 'Close']] = df_60[['Open', 'High', 'Low', 'Close']].ffill()
                if 'Volume' in df_60.columns:
                    df_60['Volume'] = df_60['Volume'].fillna(0)
                df_60 = df_60.dropna(subset=['Close'])
            # ----------------------------------------------------
            
            if df_60.empty or len(df_60) < 60:
                st.error(f"🚨 無法取得 [{display_title_60}] 足夠的 60 分鐘 K 線資料。")
                return
                
            # 1. 計算 60MA
            df_60['MA60'] = df_60['Close'].rolling(window=60).mean()
            
            # 2. 計算 KD(60,3,3) 券商標準版 (強制初始值設為 50)
            low_min_60 = df_60['Low'].rolling(window=60).min()
            high_max_60 = df_60['High'].rolling(window=60).max()
            df_60['RSV_60'] = 100 * ((df_60['Close'] - low_min_60) / (high_max_60 - low_min_60))
            df_60['RSV_60'] = df_60['RSV_60'].fillna(50)
            
            k_list, d_list = [], []
            for i, rsv in enumerate(df_60['RSV_60']):
                if i == 0 or pd.isna(rsv):
                    k_list.append(50.0)
                    d_list.append(50.0)
                else:
                    k_list.append((2/3) * k_list[-1] + (1/3) * rsv)
                    d_list.append((2/3) * d_list[-1] + (1/3) * k_list[-1])
            df_60['K_60'] = k_list
            df_60['D_60'] = d_list

            # 3. 計算 MACD (12, 26, 9)
            exp1 = df_60['Close'].ewm(span=12, adjust=False).mean()
            exp2 = df_60['Close'].ewm(span=26, adjust=False).mean()
            df_60['MACD'] = exp1 - exp2
            df_60['Signal'] = df_60['MACD'].ewm(span=9, adjust=False).mean()
            df_60['OSC'] = df_60['MACD'] - df_60['Signal']
            
            # 取出純數值，確保純數學運算安全
            closes = df_60['Close'].values
            latest_60m_close = float(closes[-1])
            prev_close = float(closes[-2])
            price_change = latest_60m_close - prev_close
            change_pct = (price_change / prev_close) * 100
            color = "#FF4B4B" if price_change >= 0 else "#00FF00"
            sign = "▲" if price_change >= 0 else "▼"
            latest_vol = float(df_60['Volume'].values[-1])
            
            ma60_60m = float(df_60['MA60'].values[-1])
            k_60m = float(df_60['K_60'].values[-1])
            d_60m = float(df_60['D_60'].values[-1])
            k_60m_prev = float(df_60['K_60'].values[-2])
            d_60m_prev = float(df_60['D_60'].values[-2])

            osc_val = float(df_60['OSC'].values[-1])
            osc_prev = float(df_60['OSC'].values[-2])
            
            # 4. 未來 10 期真實 60MA 預測演算 (假設股價維持現價平盤)
            future_ma60 = []
            current_sum = float(closes[-60:].sum())
            for i in range(10):
                dropped_price = float(closes[-60 + i])
                current_sum = current_sum - dropped_price + latest_60m_close
                future_ma60.append(current_sum / 60)
                
            deduct_prices = closes[-60:-50]
            avg_deduct = float(deduct_prices.mean())
            
            # --- 畫面頂部資訊 ---
            last_date = df_60.index[-1]
            date_str = f"{last_date.strftime('%m/%d %H:%M')}"
            st.markdown(f"<h3 style='margin-bottom:0;'>{display_title_60} &nbsp;&nbsp; <span style='font-size: 0.5em; color: #8ab4f8; border: 1px solid #333; padding: 2px 8px; border-radius: 5px; vertical-align: middle;'>{date_str}</span></h3>", unsafe_allow_html=True)
            st.markdown(f"<div class='text-sm' style='margin-bottom: 15px;'>收盤 <span style='color:{color}; font-weight:bold;'>{latest_60m_close:.2f}</span> &nbsp;&nbsp; 漲跌 <span style='color:{color};'>{sign} {abs(price_change):.2f} ({change_pct:.2f}%)</span> &nbsp;&nbsp; | &nbsp;&nbsp; 當根K線成交量 <b>{latest_vol:,.0f}</b> 張</div>", unsafe_allow_html=True)
            st.markdown("<hr style='margin: 0 0 10px 0; padding: 0;'>", unsafe_allow_html=True)

            # --- 黃金排版：左圖右表 ---
            col_left, col_right = st.columns([2.2, 1.1])
            
            with col_left:
                with st.container(border=True):
                    st.markdown('<div class="section-title">60分K線與動能指標可視化</div>', unsafe_allow_html=True)
                    
                    x_dates = df_60.index.strftime('%m-%d %H:%M').tolist()
                    
                    # 變更為 3 列的子圖表，加入 MACD 空間
                    fig_60 = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.25, 0.25])
                    
                    # Row 1: K線與 60MA
                    fig_60.add_trace(go.Candlestick(x=x_dates, open=df_60['Open'], high=df_60['High'], low=df_60['Low'], close=df_60['Close'], name="K線", increasing_line_color='#FF4B4B', decreasing_line_color='#00FF00'), row=1, col=1)
                    fig_60.add_trace(go.Scatter(x=x_dates, y=df_60['MA60'], line=dict(color='orange', width=2), name="60MA"), row=1, col=1)
                    
                    # 預測的 MA 完美接續在原本的 60MA 之後
                    future_dates = pd.date_range(df_60.index[-1] + pd.Timedelta(hours=1), periods=10, freq='60min')
                    future_dates_str = future_dates.strftime('%m-%d %H:%M').tolist()
                    
                    ma_proj_x = [x_dates[-1]] + future_dates_str
                    ma_proj_y = [ma60_60m] + future_ma60
                    
                    fig_60.add_trace(go.Scatter(x=ma_proj_x, y=ma_proj_y, mode='lines', line=dict(color='orange', dash='dash', width=2), name="預測60MA(平盤)"), row=1, col=1)
                    
                    # Row 2: KD(60,3,3)
                    fig_60.add_trace(go.Scatter(x=x_dates, y=df_60['K_60'], line=dict(color='yellow', width=1.5), name='K(60)'), row=2, col=1)
                    fig_60.add_trace(go.Scatter(x=x_dates, y=df_60['D_60'], line=dict(color='cyan', width=1.5), name='D(60)'), row=2, col=1)
                    fig_60.add_hline(y=80, line_dash="dot", line_color="red", row=2, col=1)
                    fig_60.add_hline(y=20, line_dash="dot", line_color="green", row=2, col=1)

                    # Row 3: MACD
                    colors_macd = ['#FF4B4B' if val >= 0 else '#00FF00' for val in df_60['OSC']]
                    fig_60.add_trace(go.Bar(x=x_dates, y=df_60['OSC'], marker_color=colors_macd, name="MACD柱"), row=3, col=1)
                    fig_60.add_trace(go.Scatter(x=x_dates, y=df_60['MACD'], line=dict(color='white', width=1.5), name='MACD'), row=3, col=1)
                    fig_60.add_trace(go.Scatter(x=x_dates, y=df_60['Signal'], line=dict(color='yellow', width=1.5), name='Signal'), row=3, col=1)
                    
                    fig_60.update_xaxes(type='category', nticks=12, showgrid=True, gridwidth=1, gridcolor='#333')
                    fig_60.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#333')
                    fig_60.update_layout(height=750, margin=dict(l=0, r=0, t=5, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False, xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig_60, use_container_width=True)

            with col_right:
                with st.container(border=True):
                    st.markdown("<div class='section-title'>趨勢與動能分析</div>", unsafe_allow_html=True)
                    
                    # 60MA 狀態
                    trend_status = "✅ 多頭 (站上 60MA)" if latest_60m_close > ma60_60m else "🚨 空頭 (跌破 60MA)"
                    trend_color = "#FF4B4B" if latest_60m_close > ma60_60m else "#00FF00"
                    
                    # KD 狀態
                    kd_666_status = "⚖️ 中性整理"
                    kd_color = "gray"
                    if k_60m > d_60m and k_60m_prev <= d_60m_prev: kd_666_status, kd_color = "🔥 黃金交叉", "#FF4B4B"
                    elif k_60m < d_60m and k_60m_prev >= d_60m_prev: kd_666_status, kd_color = "🔪 死亡交叉", "#00FF00"

                    # MACD 狀態
                    macd_status = "⚖️ 盤整"
                    macd_color = "gray"
                    if osc_val > 0 and osc_val > osc_prev: macd_status, macd_color = "🔥 多頭增溫", "#FF4B4B"
                    elif osc_val > 0 and osc_val <= osc_prev: macd_status, macd_color = "⚠️ 多頭收斂", "gray"
                    elif osc_val < 0 and osc_val < osc_prev: macd_status, macd_color = "🔪 空頭擴散", "#00FF00"
                    elif osc_val < 0 and osc_val >= osc_prev: macd_status, macd_color = "🟢 空頭收斂", "#FF4B4B"
                    
                    st.markdown(f"""
                    <div style='margin-bottom: 8px;'><b>📍 60MA 狀態：</b> <span style='color:{trend_color}; font-weight:bold;'>{trend_status}</span></div>
                    <div style='margin-bottom: 8px;'><b>📍 KD(60) 狀態：</b> <span style='color:{kd_color}; font-weight:bold;'>{kd_666_status}</span><br>
                    <span style='font-size: 0.85em; color:gray;'>(K={k_60m:.1f}, D={d_60m:.1f})</span></div>
                    <div><b>📍 MACD 狀態：</b> <span style='color:{macd_color}; font-weight:bold;'>{macd_status}</span></div>
                    """, unsafe_allow_html=True)
                
                with st.container(border=True):
                    st.markdown("<div class='section-title'>未來 10 期均線預判</div>", unsafe_allow_html=True)
                    deduct_text = "⚖️ 均線走平震盪"
                    deduct_color = "#FFA500"
                    if latest_60m_close > avg_deduct:
                        deduct_text = "📈 扣抵低檔，60MA 強力上彎！"
                        deduct_color = "#FF4B4B"
                    elif latest_60m_close < avg_deduct:
                        deduct_text = "📉 扣抵高檔，60MA 下彎反壓！"
                        deduct_color = "#00FF00"
                        
                    st.markdown(f"""
                    <div class='deduct-box' style='border-color: {deduct_color};'>
                        <h4 style='color: {deduct_color}; margin-top: 0;'>{deduct_text}</h4>
                        <div style='font-size: 0.85em; color: gray;'>
                            目前收盤價：{latest_60m_close:.2f}<br>
                            未來將剔除之舊均價：{avg_deduct:.2f}
                        </div>
                        <div style='margin-top: 10px; font-size: 0.85em;'>
                            <b>圖表說明：</b>橘色虛線為假設股價維持現價不跌，未來 10 小時真實的 60MA 走向軌跡。
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                with st.container(border=True):
                    st.markdown("<div class='section-title'>💻 系統交易訊號</div>", unsafe_allow_html=True)
                    if latest_60m_close > ma60_60m and k_60m > d_60m and k_60m_prev <= d_60m_prev and k_60m < 35:
                        st.markdown("""
                        <div class='signal-buy' style='margin-top:0; padding:10px;'>
                            <div style='font-size:1.1em;'>🔥 【極佳買點】</div>
                            <p style='font-size: 0.8em; color: white; font-weight: normal; margin-bottom: 0; line-height: 1.4; text-align: left; margin-top:5px;'>
                            受 60MA 保護，長週期 KD 低檔黃金交叉。<br><b>對策：</b>建立部位，防守點設於 60MA 之下。
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
                    elif latest_60m_close > ma60_60m and k_60m < d_60m and k_60m_prev >= d_60m_prev and k_60m > 70:
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
                        st.markdown(f"""
                        <div class='signal-wait' style='margin-top:0; padding:10px;'>
                            <div style='font-size:1.1em; font-weight:bold; color:#FFA500;'>⏳ 觀望中</div>
                            <p style='font-size: 0.8em; margin-bottom: 0; margin-top:5px; text-align:left; color:#ccc; line-height: 1.4;'>{action_text}</p>
                        </div>
                        """, unsafe_allow_html=True)
