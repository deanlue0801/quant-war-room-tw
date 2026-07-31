import streamlit as st
import pandas as pd
import numpy as np
import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import utils

def find_zigzag_points(df, order=5):
    """
    尋找 K 線的顯著高低轉折點 (Peaks & Troughs)
    """
    highs = df['High'].values
    lows = df['Low'].values
    n = len(df)
    
    pivot_points = [] # list of (index, date_str, price, type) 'H' or 'L'
    
    for i in range(order, n - order):
        is_high = highs[i] == max(highs[i-order : i+order+1])
        is_low = lows[i] == min(lows[i-order : i+order+1])
        
        if is_high and not is_low:
            pivot_points.append((i, df.index[i], highs[i], 'H'))
        elif is_low and not is_high:
            pivot_points.append((i, df.index[i], lows[i], 'L'))
        elif is_high and is_low:
            # 極端情況，以實體 K 線判定
            if df['Close'].iloc[i] >= df['Open'].iloc[i]:
                pivot_points.append((i, df.index[i], highs[i], 'H'))
            else:
                pivot_points.append((i, df.index[i], lows[i], 'L'))
                
    # 過濾連續相同的 H 或 L，只保留更極端的點
    filtered_pivots = []
    for pt in pivot_points:
        if not filtered_pivots:
            filtered_pivots.append(pt)
        else:
            last_pt = filtered_pivots[-1]
            if pt[3] == last_pt[3]: # 同樣是高點或低點
                if pt[3] == 'H' and pt[2] > last_pt[2]:
                    filtered_pivots[-1] = pt
                elif pt[3] == 'L' and pt[2] < last_pt[2]:
                    filtered_pivots[-1] = pt
            else:
                filtered_pivots.append(pt)
                
    return filtered_pivots

def analyze_elliott_wave(df, pivots, start_idx=0):
    """
    波浪型態辨識演算法 (推升浪 1-5 / A-B-C / W-X-Y)
    """
    valid_pivots = [p for p in pivots if p[0] >= start_idx]
    if len(valid_pivots) < 3:
        return {"pattern": "資料不足", "labels": [], "status": "轉折點數量不足以判斷波浪", "targets": {}}
    
    # 確保第一個點是低點 (Point Zero)
    if valid_pivots[0][3] == 'H':
        valid_pivots = valid_pivots[1:]
        
    if len(valid_pivots) < 3:
        return {"pattern": "資料不足", "labels": [], "status": "無法確立 Point Zero 起算點", "targets": {}}

    p0 = valid_pivots[0] # Point Zero (浪 1 起點)
    labels = [(p0[0], p0[1], p0[2], "⓪")]
    
    # 嘗試比對 1-2-3-4-5 推升浪
    # P0(L) -> P1(H) -> P2(L) -> P3(H) -> P4(L) -> P5(H)
    is_impulse = False
    if len(valid_pivots) >= 6:
        p1, p2, p3, p4, p5 = valid_pivots[1:6]
        
        rule1 = p2[2] > p0[2] # 浪 2 不破浪 1 起點
        wave1_len = p1[2] - p0[2]
        wave3_len = p3[2] - p2[2]
        wave5_len = p5[2] - p4[2]
        rule2 = not (wave3_len < wave1_len and wave3_len < wave5_len) # 浪 3 非最短浪
        rule3 = p4[2] > p1[2] # 浪 4 不重疊浪 1 高點
        
        if rule1 and rule2 and rule3:
            is_impulse = True
            labels.extend([
                (p1[0], p1[1], p1[2], "①"),
                (p2[0], p2[1], p2[2], "②"),
                (p3[0], p3[1], p3[2], "③"),
                (p4[0], p4[1], p4[2], "④"),
                (p5[0], p5[1], p5[2], "⑤")
            ])
            
            # 若後面還有轉折，嘗試標記 A-B-C 或 W-X-Y
            remains = valid_pivots[6:]
            if len(remains) >= 3:
                pa, pb, pc = remains[0:3]
                if pb[2] < p5[2] and pc[2] < pa[2]: # 標準 ABC
                    labels.extend([(pa[0], pa[1], pa[2], "Ⓐ"), (pb[0], pb[1], pb[2], "Ⓑ"), (pc[0], pc[1], pc[2], "Ⓒ")])
                else: # 複式 W-X-Y 盤整
                    labels.extend([(pa[0], pa[1], pa[2], "W"), (pb[0], pb[1], pb[2], "X"), (pc[0], pc[1], pc[2], "Y")])

    if is_impulse:
        last_label = labels[-1][3]
        return {
            "pattern": "標準五浪推升",
            "labels": labels,
            "status": f"目前處於【推升結構 ({last_label})】，趨勢明確。",
            "invalid_price": p0[2],
            "targets": {"Fib 1.618": p2[2] + (p1[2]-p0[2])*1.618 if len(labels)>=3 else 0}
        }

    # 若無法組成標準五浪，判定為複式修正浪 (W-X-Y) 或局部結構
    labels = [(p0[0], p0[1], p0[2], "⓪")]
    wave_names = ["W", "X", "Y", "X2", "Z"]
    for i, pt in enumerate(valid_pivots[1:]):
        if i < len(wave_names):
            labels.append((pt[0], pt[1], pt[2], wave_names[i]))

    curr_wave = labels[-1][3] if len(labels) > 1 else "初始建構中"
    return {
        "pattern": "W-X-Y 複式型態整理",
        "labels": labels,
        "status": f"目前盤勢處於【複式修正浪 ({curr_wave} 浪)】，屬於高位/高複雜度箱型洗盤結構。",
        "invalid_price": p0[2],
        "targets": {"高檔壓力": max([p[2] for p in valid_pivots]), "低檔支撐": min([p[2] for p in valid_pivots])}
    }

def render():
    stock_dict, name_to_id_dict, full_info_df = utils.load_stock_dicts()

    if 'search_history' not in st.session_state:
        st.session_state['search_history'] = []

    def add_to_history(ticker):
        if ticker and ticker not in st.session_state['search_history']:
            st.session_state['search_history'].insert(0, ticker)
            if len(st.session_state['search_history']) > 8:
                st.session_state['search_history'].pop()

    # --- 搜尋區塊 ---
    with st.form(key='search_form_wave', clear_on_submit=False):
        col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1.5, 1.5, 6])
        with col_ctrl1:
            raw_input = st.text_input("搜尋", "", label_visibility="collapsed", placeholder="輸入代號或名稱並按 Enter")
        with col_ctrl2:
            analyze_btn = st.form_submit_button("🌊 啟動波浪理論解析", use_container_width=True)
        with col_ctrl3:
            st.markdown("<div style='margin-top: 8px; font-size: 0.9em; color:gray;'>※ 採用 Elliot Wave 演算法 + 關鍵轉折 ZigZag 智能自動標註標籤</div>", unsafe_allow_html=True)

    if st.session_state['search_history']:
        st.markdown("<div style='font-size: 0.8em; color: gray; margin-bottom: 5px;'>🕒 最近搜尋紀錄 (點擊直接分析)：</div>", unsafe_allow_html=True)
        hist_cols = st.columns(len(st.session_state['search_history']) + 1)
        clicked_hist = None
        for i, hist_ticker in enumerate(st.session_state['search_history']):
            hist_name = stock_dict.get(hist_ticker, "")
            btn_label = f"{hist_ticker} {hist_name}" if hist_name else hist_ticker
            if hist_cols[i].button(btn_label, key=f"hist_btn_wave_{hist_ticker}"):
                clicked_hist = hist_ticker
    else:
        clicked_hist = None

    search_term = ""
    if clicked_hist:
        search_term = clicked_hist
    elif analyze_btn and raw_input:
        search_term = raw_input.strip()

    if search_term:
        raw_ticker = name_to_id_dict.get(search_term, search_term) if search_term not in stock_dict else search_term
        stock_name = stock_dict.get(raw_ticker, "")
        display_title = f"{raw_ticker} {stock_name}" if stock_name else raw_ticker
        
        add_to_history(raw_ticker)

        with st.spinner(f'解析 [{display_title}] 艾略特波浪結構中...'):
            try:
                df_full = utils.fetch_tech_data_fugle(raw_ticker).copy()
                if len(df_full) < 80:
                    st.error(f"🚨 無法取得 [{display_title}] 足夠的日線歷史報價資料。")
                    st.stop()

                df = df_full.tail(180).copy()
                x_dates = df.index.strftime('%m-%d')
                
                # --- 波浪計算 ---
                pivots = find_zigzag_points(df, order=5)
                
                # 建立 Point Zero 手動切換選項
                zero_options = {"[自動預設] 波段極小值點": 0}
                low_pivots = [p for p in pivots if p[3] == 'L']
                for lp in low_pivots[:4]:
                    dt_str = lp[1].strftime('%Y/%m/%d')
                    zero_options[f"{dt_str} 低點 ({lp[2]:.1f})"] = lp[0]

                st.markdown("<hr style='margin: 5px 0 15px 0;'>", unsafe_allow_html=True)
                col_sel1, col_sel2 = st.columns([3, 7])
                with col_sel1:
                    selected_zero_label = st.selectbox("📌 選擇波浪 Point Zero (0 浪起算點)：", list(zero_options.keys()))
                    selected_start_idx = zero_options[selected_zero_label]

                wave_result = analyze_elliott_wave(df, pivots, start_idx=selected_start_idx)

                # --- 繪製圖表 ---
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
                
                # K 線
                fig.add_trace(go.Candlestick(x=x_dates, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線", increasing_line_color='#FF4B4B', decreasing_line_color='#00FF00'), row=1, col=1)
                
                # 波浪連線與標註
                if wave_result['labels']:
                    wave_x = [df.index[lbl[0]].strftime('%m-%d') for lbl in wave_result['labels']]
                    wave_y = [lbl[2] for lbl in wave_result['labels']]
                    
                    fig.add_trace(go.Scatter(x=wave_x, y=wave_y, mode='lines+markers+text', line=dict(color='gold', width=2.5, dash='solid'), marker=dict(size=8, color='cyan'), text=[lbl[3] for lbl in wave_result['labels']], textposition="top center", textfont=dict(size=14, color='gold'), name="波浪軌跡"), row=1, col=1)

                # 成交量
                colors_vol = ['#FF4B4B' if row['Close'] >= row['Open'] else '#00FF00' for index, row in df.iterrows()]
                fig.add_trace(go.Bar(x=x_dates, y=df['Volume']/1000, marker_color=colors_vol, name="成交量(張)"), row=2, col=1)

                fig.update_xaxes(type='category', nticks=12, showgrid=True, gridcolor='#333')
                fig.update_layout(height=520, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False, xaxis_rangeslider_visible=False)
                fig.update_yaxes(showgrid=True, gridcolor='#333')

                # --- 版面呈現 ---
                st.markdown(f"### {display_title} &nbsp;&nbsp; | &nbsp;&nbsp; 波浪型態：<span style='color:gold;'>{wave_result['pattern']}</span>", unsafe_allow_html=True)
                
                col_chart, col_info = st.columns([7, 3])
                with col_chart:
                    st.plotly_chart(fig, use_container_width=True)

                with col_info:
                    with st.container(border=True):
                        st.markdown('<div style="font-weight:bold; font-size:1.1em; color:#8ab4f8; margin-bottom:8px;">🎯 波浪診斷卡片</div>', unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size:0.95em; line-height:1.6;'>{wave_result['status']}</div>", unsafe_allow_html=True)

                    with st.container(border=True):
                        st.markdown('<div style="font-weight:bold; font-size:1.1em; color:#FF4B4B; margin-bottom:8px;">🛡️ 結構失效防守價</div>', unsafe_allow_html=True)
                        invalid_p = wave_result.get('invalid_price', 0)
                        st.markdown(f"<div style='font-size:1.2em; font-weight:bold; color:#FF4B4B;'>{invalid_p:.2f} 元</div>", unsafe_allow_html=True)
                        st.markdown("<div style='font-size:0.8em; color:gray;'>註：若跌破此價位，則代表當前波浪假設失效，系統將重新計算起算點。</div>", unsafe_allow_html=True)

                    with st.container(border=True):
                        st.markdown('<div style="font-weight:bold; font-size:1.1em; color:#FFA500; margin-bottom:8px;">📐 關鍵測量位階</div>', unsafe_allow_html=True)
                        for t_name, t_val in wave_result.get('targets', {}).items():
                            st.markdown(f"<div style='font-size:0.9em;'>{t_name}： <b>{t_val:.1f}</b></div>", unsafe_allow_html=True)

            except Exception as e:
                st.error(f"波浪分析資料處理發生錯誤：{e}")
