import streamlit as st
import pandas as pd
import numpy as np
import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import utils

def find_zigzag_points(df, order=5):
    """
    動態波浪轉折點擷取 (ZigZag)
    """
    highs = df['High'].values
    lows = df['Low'].values
    n = len(df)
    
    pivot_points = []
    
    for i in range(order, n - order):
        is_high = highs[i] == max(highs[i-order : i+order+1])
        is_low = lows[i] == min(lows[i-order : i+order+1])
        
        if is_high and not is_low:
            pivot_points.append((i, df.index[i], highs[i], 'H'))
        elif is_low and not is_high:
            pivot_points.append((i, df.index[i], lows[i], 'L'))
        elif is_high and is_low:
            if df['Close'].iloc[i] >= df['Open'].iloc[i]:
                pivot_points.append((i, df.index[i], highs[i], 'H'))
            else:
                pivot_points.append((i, df.index[i], lows[i], 'L'))
                
    filtered_pivots = []
    for pt in pivot_points:
        if not filtered_pivots:
            filtered_pivots.append(pt)
        else:
            last_pt = filtered_pivots[-1]
            if pt[3] == last_pt[3]:
                if pt[3] == 'H' and pt[2] > last_pt[2]:
                    filtered_pivots[-1] = pt
                elif pt[3] == 'L' and pt[2] < last_pt[2]:
                    filtered_pivots[-1] = pt
            else:
                filtered_pivots.append(pt)
                
    if filtered_pivots:
        last_idx = filtered_pivots[-1][0]
        if n - 1 - last_idx >= 1:
            sub_df = df.iloc[last_idx:]
            if filtered_pivots[-1][3] == 'H':
                min_idx = sub_df['Low'].argmin() + last_idx
                if min_idx != last_idx:
                    filtered_pivots.append((min_idx, df.index[min_idx], df['Low'].iloc[min_idx], 'L'))
            else:
                max_idx = sub_df['High'].argmax() + last_idx
                if max_idx != last_idx:
                    filtered_pivots.append((max_idx, df.index[max_idx], df['High'].iloc[max_idx], 'H'))

    return filtered_pivots

def convert_to_weekly(df):
    """將日線 K 線資料重採樣為週線 K 線"""
    df_weekly = df.resample('W-FRI').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna()
    return df_weekly

def generate_multi_degree_wave_labels(valid_pivots):
    """
    校正版：嚴格確保 1, 3, 5 浪落在高點 (H)，2, 4 浪落在低點 (L)
    """
    labels = []
    if not valid_pivots:
        return labels

    p0 = valid_pivots[0]
    labels.append((p0[0], p0[1], p0[2], "⓪"))

    pts = valid_pivots[1:]
    if not pts:
        return labels

    # 符號循環庫 (推升浪: H, L, H, L, H | 修正浪: L, H, L)
    impulse_cycles = [
        ["①", "②", "③", "④", "⑤"],
        ["⑴", "⑵", "⑶", "⑷", "⑸"],
        ["1", "2", "3", "4", "5"]
    ]
    corrective_cycles = [
        ["Ⓐ", "Ⓑ", "Ⓒ"],
        ["⒲", "⒱", "⒴"],
        ["a", "b", "c"]
    ]

    idx = 0
    total_pts = len(pts)
    cycle_count = 0

    # 確保從第一個高點 (H) 開始推升浪
    if pts[0][3] != 'H':
        # 如果第一個點不是高點，先跳過以保持 H-L-H-L 的順序
        idx = 1

    while idx < total_pts:
        # --- 進行推升浪標註 (1, 2, 3, 4, 5) ---
        imp_syms = impulse_cycles[cycle_count % len(impulse_cycles)]
        imp_len = min(5, total_pts - idx)
        
        for i in range(imp_len):
            pt = pts[idx + i]
            # 雙重檢查：偶數索引(0,2,4)應為高點H(1,3,5浪)，奇數索引(1,3)應為低點L(2,4浪)
            sym = imp_syms[i]
            labels.append((pt[0], pt[1], pt[2], sym))
            
        idx += imp_len
        if idx >= total_pts:
            break

        # --- 進行修正浪標註 (A, B, C) ---
        corr_syms = corrective_cycles[cycle_count % len(corrective_cycles)]
        corr_len = min(3, total_pts - idx)
        
        for i in range(corr_len):
            pt = pts[idx + i]
            sym = corr_syms[i]
            labels.append((pt[0], pt[1], pt[2], sym))
            
        idx += corr_len
        cycle_count += 1

    return labels

def render():
    stock_dict, name_to_id_dict, full_info_df = utils.load_stock_dicts()

    if 'search_history' not in st.session_state:
        st.session_state['search_history'] = []
    if 'wave_active_ticker' not in st.session_state:
        st.session_state['wave_active_ticker'] = None

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
            st.markdown("<div style='margin-top: 8px; font-size: 0.9em; color:gray;'>※ 支援長週期大數據與日線/週線多時間層級波浪分析</div>", unsafe_allow_html=True)

    clicked_hist = None
    if st.session_state['search_history']:
        st.markdown("<div style='font-size: 0.8em; color: gray; margin-bottom: 5px;'>🕒 最近搜尋紀錄 (點擊直接分析)：</div>", unsafe_allow_html=True)
        hist_cols = st.columns(len(st.session_state['search_history']) + 1)
        for i, hist_ticker in enumerate(st.session_state['search_history']):
            hist_name = stock_dict.get(hist_ticker, "")
            btn_label = f"{hist_ticker} {hist_name}" if hist_name else hist_ticker
            if hist_cols[i].button(btn_label, key=f"hist_btn_wave_{hist_ticker}"):
                clicked_hist = hist_ticker

    if clicked_hist:
        st.session_state['wave_active_ticker'] = clicked_hist
    elif analyze_btn and raw_input:
        search_term = raw_input.strip()
        raw_ticker = name_to_id_dict.get(search_term, search_term) if search_term not in stock_dict else search_term
        st.session_state['wave_active_ticker'] = raw_ticker

    current_ticker = st.session_state['wave_active_ticker']

    if current_ticker:
        stock_name = stock_dict.get(current_ticker, "")
        display_title = f"{current_ticker} {stock_name}" if stock_name else current_ticker
        
        add_to_history(current_ticker)

        with st.spinner(f'解析 [{display_title}] 長週期艾略特波浪結構中...'):
            try:
                df_full = utils.fetch_tech_data_fugle(current_ticker).copy()
                if len(df_full) < 80:
                    st.error(f"🚨 無法取得 [{display_title}] 足夠的歷史報價資料。")
                    st.stop()

                st.markdown("<hr style='margin: 5px 0 15px 0;'>", unsafe_allow_html=True)
                col_tf1, col_tf2, col_tf3 = st.columns([2.5, 3.5, 4])
                
                with col_tf1:
                    timeframe = st.radio("⏳ 分析週期 (Timeframe)：", ["日線 (Daily)", "週線 (Weekly)"], horizontal=True, key=f"tf_{current_ticker}")
                
                with col_tf2:
                    history_len = st.selectbox("📅 歷史資料涵蓋範圍：", [
                        "近 3 年 (約 750 根 K 線 - 推薦大波浪)",
                        "近 5 年 (約 1250 根 K 線 - 長期宏觀)",
                        "近 1 年 (約 250 根 K 線 - 中短波段)"
                    ], index=0, key=f"len_{current_ticker}")

                limit_map = {"近 3 年 (約 750 根 K 線 - 推薦大波浪)": 750, "近 5 年 (約 1250 根 K 線 - 長期宏觀)": 1250, "近 1 年 (約 250 根 K 線 - 中短波段)": 250}
                fetch_len = limit_map[history_len]
                
                df_base = df_full.tail(fetch_len).copy()

                if "週線" in timeframe:
                    df = convert_to_weekly(df_base)
                    order_val = 3
                    x_dates = df.index.strftime('%Y-%m-%d')
                else:
                    df = df_base
                    order_val = 6
                    x_dates = df.index.strftime('%m-%d')

                pivots = find_zigzag_points(df, order=order_val)
                
                # 0 浪選單：僅提供低點 (L) 作為 Valid Point Zero 起算點
                zero_options = {}
                low_pivots = [p for p in pivots if p[3] == 'L']
                
                if low_pivots:
                    min_global_pivot = min(low_pivots, key=lambda x: x[2])
                    dt_min_str = min_global_pivot[1].strftime('%Y/%m/%d')
                    zero_options[f"[預設] 波段最低點 ({dt_min_str} - {min_global_pivot[2]:.1f}元)"] = min_global_pivot[0]
                else:
                    min_idx = df['Low'].argmin()
                    dt_str = df.index[min_idx].strftime('%Y/%m/%d')
                    zero_options[f"[預設] 全圖最低點 ({dt_str} - {df['Low'].iloc[min_idx]:.1f}元)"] = min_idx
                
                for lp in low_pivots:
                    dt_str = lp[1].strftime('%Y/%m/%d')
                    label_key = f"{dt_str} 低點轉折 ({lp[2]:.1f}元)"
                    if label_key not in zero_options:
                        zero_options[label_key] = lp[0]

                state_key = f"wave_zero_select_{current_ticker}"
                
                with col_tf3:
                    selected_zero_label = st.selectbox(
                        "📌 波浪 0 浪起算點：",
                        options=list(zero_options.keys()),
                        key=state_key
                    )
                    selected_start_idx = zero_options[selected_zero_label]

                valid_pivots = [p for p in pivots if p[0] >= selected_start_idx]
                labels = generate_multi_degree_wave_labels(valid_pivots)

                # --- 繪圖區 ---
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
                
                fig.add_trace(go.Candlestick(x=x_dates, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線", increasing_line_color='#FF4B4B', decreasing_line_color='#00FF00'), row=1, col=1)
                
                if labels:
                    wave_x = [df.index[lbl[0]].strftime('%Y-%m-%d' if "週線" in timeframe else '%m-%d') for lbl in labels]
                    wave_y = [lbl[2] for lbl in labels]
                    
                    fig.add_trace(go.Scatter(
                        x=wave_x, y=wave_y,
                        mode='lines+markers+text',
                        line=dict(color='gold', width=2, dash='solid'),
                        marker=dict(size=7, color='cyan'),
                        text=[lbl[3] for lbl in labels],
                        textposition="top center",
                        textfont=dict(size=14, color='gold'),
                        name="波浪軌跡"
                    ), row=1, col=1)

                colors_vol = ['#FF4B4B' if row['Close'] >= row['Open'] else '#00FF00' for index, row in df.iterrows()]
                fig.add_trace(go.Bar(x=x_dates, y=df['Volume']/1000, marker_color=colors_vol, name="成交量(張)"), row=2, col=1)

                fig.update_xaxes(type='category', nticks=12, showgrid=True, gridcolor='#333')
                fig.update_layout(height=550, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False, xaxis_rangeslider_visible=False)
                fig.update_yaxes(showgrid=True, gridcolor='#333')

                last_label = labels[-1][3] if labels else "⓪"
                all_prices = [p[2] for p in valid_pivots] if valid_pivots else [0]

                st.markdown(f"### {display_title} &nbsp;&nbsp; | &nbsp;&nbsp; 視角：<span style='color:gold;'>{timeframe} ({history_len.split()[0]})</span>", unsafe_allow_html=True)
                
                col_chart, col_info = st.columns([7, 3])
                with col_chart:
                    st.plotly_chart(fig, use_container_width=True)

                with col_info:
                    with st.container(border=True):
                        st.markdown('<div style="font-weight:bold; font-size:1.1em; color:#8ab4f8; margin-bottom:8px;">🎯 當前波浪位階</div>', unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size:0.95em; line-height:1.6;'>最新轉折點位於【<b>{last_label}</b>】浪。<br>💡 <i>建議切換至<b>週線</b>觀察大型大五浪結構，再回到<b>日線</b>比對子浪。</i></div>", unsafe_allow_html=True)

                    with st.container(border=True):
                        st.markdown('<div style="font-weight:bold; font-size:1.1em; color:#FF4B4B; margin-bottom:8px;">🛡️ 起算點價格</div>', unsafe_allow_html=True)
                        p0_price = valid_pivots[0][2] if valid_pivots else 0
                        st.markdown(f"<div style='font-size:1.2em; font-weight:bold; color:#FF4B4B;'>{p0_price:.2f} 元</div>", unsafe_allow_html=True)

                    with st.container(border=True):
                        st.markdown('<div style="font-weight:bold; font-size:1.1em; color:#FFA500; margin-bottom:8px;">📐 關鍵區域價位</div>', unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size:0.9em;'>波段最高壓力： <b>{max(all_prices):.1f}</b></div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size:0.9em;'>波段最低支撐： <b>{min(all_prices):.1f}</b></div>", unsafe_allow_html=True)

            except Exception as e:
                st.error(f"波浪分析資料處理發生錯誤：{e}")
