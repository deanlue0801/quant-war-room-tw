import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import utils

def render():
    st.header("🎯 正宗 666 戰法 (60分K線扣抵雷達)")
    
    # 取得股票字典
    stock_dict, name_to_id_dict, _ = utils.load_stock_dicts()
    
    with st.form(key='search_form_666', clear_on_submit=False):
        col_666_1, col_666_2 = st.columns([1.5, 7.5])
        with col_666_1:
            ticker_60 = st.text_input("搜尋", "", label_visibility="collapsed", placeholder="輸入代號並按 Enter")
        with col_666_2:
            submit_666 = st.form_submit_button("開始 666 戰法解析")
        
    if submit_666 and ticker_60:
        raw_ticker_60 = name_to_id_dict.get(ticker_60.strip(), ticker_60.strip()) if ticker_60.strip() not in stock_dict else ticker_60.strip()
        stock_name_60 = stock_dict.get(raw_ticker_60, "")
        display_title_60 = f"{raw_ticker_60} {stock_name_60}" if stock_name_60 else raw_ticker_60
        
        with st.spinner(f'解析 {display_title_60} 60分K線中...'):
            df_60 = utils.fetch_tech_data_fugle_60m(raw_ticker_60)
            
            if df_60.empty or len(df_60) < 60:
                st.error(f"🚨 無法取得 [{display_title_60}] 足夠的 60 分鐘 K 線資料。")
            else:
                # 1. 計算 60MA
                df_60['MA60'] = df_60['Close'].rolling(window=60).mean()
                
                # 2. 計算 KD(60,3,3)
                low_min_60 = df_60['Low'].rolling(window=60).min()
                high_max_60 = df_60['High'].rolling(window=60).max()
                df_60['RSV_60'] = 100 * ((df_60['Close'] - low_min_60) / (high_max_60 - low_min_60))
                df_60['K_60'] = df_60['RSV_60'].ewm(com=2, adjust=False).mean()
                df_60['D_60'] = df_60['K_60'].ewm(com=2, adjust=False).mean()
                
                latest_60m_close = df_60['Close'].iloc[-1]
                ma60_60m = df_60['MA60'].iloc[-1]
                k_60m = df_60['K_60'].iloc[-1]
                d_60m = df_60['D_60'].iloc[-1]
                k_60m_prev = df_60['K_60'].iloc[-2]
                d_60m_prev = df_60['D_60'].iloc[-2]
                
                # 3. 扣抵雷達預判 (未來 10 期)
                deduct_prices = df_60['Close'].iloc[-60:-50].values
                avg_deduct = deduct_prices.mean()
                
                # 4. 繪製 60分K 圖表
                st.markdown(f"### {display_title_60} - 60 分鐘 K 線圖")
                fig_60 = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
                
                fig_60.add_trace(go.Candlestick(x=df_60.index, open=df_60['Open'], high=df_60['High'], low=df_60['Low'], close=df_60['Close'], name="K線", increasing_line_color='#FF4B4B', decreasing_line_color='#00FF00'), row=1, col=1)
                fig_60.add_trace(go.Scatter(x=df_60.index, y=df_60['MA60'], line=dict(color='orange', width=2), name="60MA"), row=1, col=1)
                
                future_dates = pd.date_range(df_60.index[-1], periods=11, freq='60min')[1:]
                fig_60.add_trace(go.Scatter(x=future_dates, y=deduct_prices, mode='lines+markers', line=dict(color='white', dash='dash'), name="未來10期扣抵值"), row=1, col=1)
                
                fig_60.add_trace(go.Scatter(x=df_60.index, y=df_60['K_60'], line=dict(color='yellow', width=1.5), name='K(60)'), row=2, col=1)
                fig_60.add_trace(go.Scatter(x=df_60.index, y=df_60['D_60'], line=dict(color='cyan', width=1.5), name='D(60)'), row=2, col=1)
                fig_60.add_hline(y=80, line_dash="dot", line_color="red", row=2, col=1)
                fig_60.add_hline(y=20, line_dash="dot", line_color="green", row=2, col=1)
                
                fig_60.update_layout(height=600, margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis_rangeslider_visible=False)
                st.plotly_chart(fig_60, use_container_width=True)
                
                # 5. 數據判定與 UI 顯示
                st.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)
                col_666_info1, col_666_info2 = st.columns(2)
                
                with col_666_info1:
                    st.markdown("<div class='section-title'>趨勢與動能分析</div>", unsafe_allow_html=True)
                    trend_status = "✅ 多頭 (大於 60MA)" if latest_60m_close > ma60_60m else "🚨 空頭 (小於 60MA)"
                    trend_color = "#FF4B4B" if latest_60m_close > ma60_60m else "#00FF00"
                    
                    kd_666_status = "⚖️ 中性整理"
                    kd_color = "gray"
                    if k_60m > d_60m and k_60m_prev <= d_60m_prev: kd_666_status, kd_color = "🔥 黃金交叉", "#FF4B4B"
                    elif k_60m < d_60m and k_60m_prev >= d_60m_prev: kd_666_status, kd_color = "🔪 死亡交叉", "#00FF00"
                    
                    st.markdown(f"""
                    <div style='background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; border: 1px solid #555; height: 100%;'>
                        <div style='margin-bottom: 10px;'><b>📍 目前收盤價：</b> {latest_60m_close:.2f}</div>
                        <div style='margin-bottom: 10px;'><b>📍 60MA (中線趨勢)：</b> <span style='color:{trend_color}; font-weight:bold;'>{trend_status}</span></div>
                        <div><b>📍 KD(60,3,3) 狀態：</b> <span style='color:{kd_color}; font-weight:bold;'>{kd_666_status}</span> (K={k_60m:.1f}, D={d_60m:.1f})</div>
                    </div>
                    """, unsafe_allow_html=True)

                with col_666_info2:
                    st.markdown("<div class='section-title'>未來 10 期扣抵預判雷達</div>", unsafe_allow_html=True)
                    deduct_text = "⚖️ 均線走平震盪"
                    deduct_color = "#FFA500"
                    if latest_60m_close > avg_deduct:
                        deduct_text = "📈 未來 10 期將「扣低」，均線強力上彎助漲！"
                        deduct_color = "#FF4B4B"
                    elif latest_60m_close < avg_deduct:
                        deduct_text = "📉 未來 10 期將「扣高」，均線下彎形成沉重反壓！"
                        deduct_color = "#00FF00"
                        
                    st.markdown(f"""
                    <div class='deduct-box' style='height: 100%; border-color: {deduct_color};'>
                        <h4 style='color: {deduct_color}; margin-top: 0;'>{deduct_text}</h4>
                        <div style='font-size: 0.9em; color: gray;'>
                            目前收盤價：{latest_60m_close:.2f}<br>
                            未來 10 期被剔除的舊價格平均：{avg_deduct:.2f}
                        </div>
                        <div style='margin-top: 10px; font-size: 0.9em;'>
                            <b>說明：</b>目前價格與被扣除的舊價格進行比較，將決定 60MA 未來 10 小時內的拉扯方向。
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                # 6. 最終進出場訊號
                st.markdown("<h3 style='margin-top: 20px;'>💻 666 系統交易訊號</h3>", unsafe_allow_html=True)
                
                if latest_60m_close > ma60_60m and k_60m > d_60m and k_60m_prev <= d_60m_prev and k_60m < 35:
                    st.markdown("""
                    <div class='signal-buy'>
                        <h2>🔥 【極佳買點】進場訊號觸發！</h2>
                        <p style='font-size: 0.6em; color: white; font-weight: normal; margin-bottom: 0;'>
                        股價受 60MA 趨勢保護，且經歷充分洗盤後，長週期 KD 在低檔黃金交叉。<br>
                        <b>策略建議：</b>建立波段部位，停損防守點設於 60MA 之下。
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                elif latest_60m_close < ma60_60m:
                    st.markdown("""
                    <div class='signal-sell'>
                        <h2>🚨 【強制停損 / 禁做多】跌破 60MA</h2>
                        <p style='font-size: 0.6em; color: white; font-weight: normal; margin-bottom: 0;'>
                        股價已落入 60MA 之下，波段趨勢轉弱。<br>
                        <b>策略建議：</b>嚴格遵守紀律，手中有多單應立即停損/減碼，空手者嚴禁進場接刀。
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                elif latest_60m_close > ma60_60m and k_60m < d_60m and k_60m_prev >= d_60m_prev and k_60m > 70:
                    st.markdown("""
                    <div class='signal-sell'>
                        <h2>💰 【波段停利警戒】高檔動能衰退</h2>
                        <p style='font-size: 0.6em; color: white; font-weight: normal; margin-bottom: 0;'>
                        股價雖強勢，但 KD 已達高檔並出現死亡交叉，買盤動能即將耗盡。<br>
                        <b>策略建議：</b>強烈建議分批獲利了結，或設定極為嚴格的移動停利點。
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    action_text = "目前不符合 666 戰法的極端發動點。若已在車上，請沿著趨勢續抱；若為空手，請耐心等待 KD 回落洗盤。"
                    if latest_60m_close > ma60_60m and latest_60m_close > avg_deduct: action_text += "<br><span style='color:#FF4B4B;'>(註：目前 60MA 持續向上助漲中)</span>"
                    st.markdown(f"""
                    <div class='signal-wait'>
                        <h3>⏳ 觀望中：尚未浮現極端轉折點</h3>
                        <p style='font-size: 0.9em; margin-bottom: 0;'>{action_text}</p>
                    </div>
                    """, unsafe_allow_html=True)
