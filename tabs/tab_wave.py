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
    依 TMGM 教學進行嚴格高低對應的波浪標註 (1,3,5為高點H, 2,4為低點L)
    """
    labels = []
    if not valid_pivots:
        return labels

    p0 = valid_pivots[0]
    labels.append((p0[0], p0[1], p0[2], "⓪"))

    pts = valid_pivots[1:]
    if not pts:
        return labels

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

    if pts[0][3] != 'H':
        idx = 1

    while idx < total_pts:
        imp_syms = impulse_cycles[cycle_count % len(impulse_cycles)]
        imp_len = min(5, total_pts - idx)
        
        for i in range(imp_len):
            pt = pts[idx + i]
            labels.append((pt[0], pt[1], pt[2], imp_syms[i]))
            
        idx += imp_len
        if idx >= total_pts:
            break

        corr_syms = corrective_cycles[cycle_count % len(corrective_cycles)]
        corr_len = min(3, total_pts - idx)
        
        for i in range(corr_len):
            pt = pts[idx + i]
            labels.append((pt[0], pt[1], pt[2], corr_syms[i]))
            
        idx += corr_len
        cycle_count += 1

    return labels

def validate_elliott_rules(valid_pivots):
    """
    依據 TMGM 艾略特波浪三大鐵律與黃金比例進行檢驗
    """
    warnings = []
    fib_info = {}
    
    if len(valid_pivots) < 6:
        return ["尚未形成完整 1-5 浪結構"], fib_info

    p0, p1, p2, p3, p4, p5 = valid_pivots[:6]
    
    len_w1 = abs(p1[2] - p0[2])
    len_w2 = abs(p2[2] - p1[2])
    len_w3 = abs(p3[2] - p2[2])
    len_w4 = abs(p4[2] - p3[2])
    len_w5 = abs(p5[2] - p4[2])

    # 1. 鐵律檢驗
    if p2[2] <= p0[2]:
        warnings.append("⚠️ 違反鐵律 1：浪 2 跌破浪 0 起算點！")
    if len_w3 < len_w1 and len_w3 < len_w5:
        warnings.append("⚠️ 違反鐵律 2：浪 3 為三個推升浪中最短！")
    if p4[2] <= p1[2]:
        warnings.append("⚠️ 違反鐵律 3：浪 4 回檔與浪 1 頂峰重疊！")

    if not warnings:
        warnings.append("✅ 完美符合艾略特三大鐵律！")

    # 2. 斐波那契黃金比例計算
    if len_w1 > 0:
        fib_info["浪2/浪1 回檔比"] = f"{(len_w2 / len_w1)*100:.1f}% (目標: 50%-61.8%)"
        fib_info["浪3/浪1 延伸倍數"] = f"{(len_w3 / len_w1):.2f} 倍 (目標: 1.618倍)"
    if len_w3 > 0:
        fib_info["浪4/浪3 回檔比"] = f"{(len_w4 / len_w3)*100:.1f}% (目標: 23.6%-38.2%)"

    return warnings, fib_info

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
            st.markdown("<div style='margin-top: 8px; font-size: 0.9em; color:gray;'>※ 結合 TMGM 艾略特波浪三大鐵律與斐波那契比率自動驗證</div>", unsafe_allow_html=True)

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
                
                # TMGM 三大鐵律與斐波那契驗證
                rule_warnings, fib_ratios = validate_elliott_rules(valid_pivots)

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
                        st.markdown(f"<div style='font-size:0.95em; line-height:1.6;'>最新轉折點位於【<b>{last_label}</b>】浪。</div>", unsafe_allow_html=True)

                    with st.container(border=True):
                        st.markdown('<div style="font-weight:bold; font-size:1.1em; color:#FFD700; margin-bottom:8px;">⚖️ TMGM 鐵律檢驗</div>', unsafe_allow_html=True)
                        for w in rule_warnings:
                            st.markdown(f"<div style='font-size:0.85em; margin-bottom:4px;'>{w}</div>", unsafe_allow_html=True)

                    with st.container(border=True):
                        st.markdown('<div style="font-weight:bold; font-size:1.1em; color:#FFA500; margin-bottom:8px;">📐 斐波那契比例 (Fibonacci)</div>', unsafe_allow_html=True)
                        if fib_ratios:
                            for k, v in fib_ratios.items():
                                st.markdown(f"<div style='font-size:0.85em;'><b>{k}</b>: <br><span style='color:cyan;'>{v}</span></div>", unsafe_allow_html=True)
                        else:
                            st.markdown("<div style='font-size:0.85em; color:gray;'>轉折點不足，無法計算比例</div>", unsafe_allow_html=True)

            except Exception as e:
                st.error(f"波浪分析資料處理發生錯誤：{e}")
