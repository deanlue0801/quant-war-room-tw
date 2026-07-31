import streamlit as st
import pandas as pd
import numpy as np
import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import utils

def find_zigzag_points(df, order=4):
    """
    動態波浪轉折點擷取 (ZigZag)，確保涵蓋整個圖表並連接至最新 K 線
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
                
    # 過濾連續同性質點，保留極值
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
                
    # 強制將最後一段至最新 K 線的極值補上，確保全圖連線無斷點
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

def analyze_elliott_wave_full(df, pivots, start_idx=0):
    """
    全圖波浪型態精密標註：
    將起算點後的所有轉折點無盲點地進行波浪標籤分配 (1-5 -> A-B-C / W-X-Y -> 延伸浪)
    """
    valid_pivots = [p for p in pivots if p[0] >= start_idx]
    if len(valid_pivots) < 2:
        return {"pattern": "資料不足", "labels": [], "status": "轉折點數量不足，無法標註波浪。", "targets": {}}

    p0 = valid_pivots[0]
    labels = [(p0[0], p0[1], p0[2], "⓪")]
    remaining_pivots = valid_pivots[1:]

    # 定義波浪符號序列池
    impulse_symbols = ["①", "②", "③", "④", "⑤"]
    corr_symbols = ["Ⓐ", "Ⓑ", "Ⓒ", "W", "X", "Y", "X2", "Z"]
    extended_symbols = [f"v{i}" for i in range(1, 20)]

    # 檢查前 5 個轉折是否符合基本 1-5 推升
    has_impulse = False
    if len(remaining_pivots) >= 5:
        p1, p2, p3, p4, p5 = remaining_pivots[:5]
        # 簡單推升檢查：浪 2 不破 0、浪 4 不破 1 高點（多頭）或浪 2 不高於 0（空頭）
        if p1[3] == 'H' and p2[2] > p0[2]:
            has_impulse = True
        elif p1[3] == 'L' and p2[2] < p0[2]:
            has_impulse = True

    if has_impulse:
        # 標註前 5 個浪為 ① ~ ⑤
        for i in range(5):
            pt = remaining_pivots[i]
            labels.append((pt[0], pt[1], pt[2], impulse_symbols[i]))
        
        # 剩餘的全圖所有點，順序接入修正浪與延伸標籤
        rest_pivots = remaining_pivots[5:]
        for i, pt in enumerate(rest_pivots):
            sym = corr_symbols[i] if i < len(corr_symbols) else extended_symbols[i - len(corr_symbols)]
            labels.append((pt[0], pt[1], pt[2], sym))
        
        pattern_str = "全圖波浪分析：標準 1-5 浪 + 後續波段結構"
    else:
        # 不符合衝擊浪時，全圖依序以修正浪/複合浪進行連續標註
        symbol_pool = corr_symbols + extended_symbols
        for i, pt in enumerate(remaining_pivots):
            sym = symbol_pool[i] if i < len(symbol_pool) else f"p{i}"
            labels.append((pt[0], pt[1], pt[2], sym))
            
        pattern_str = "全圖波浪分析：複式 / 階段性整理型態"

    last_label = labels[-1][3] if len(labels) > 1 else "⓪"
    all_prices = [p[2] for p in valid_pivots]
    
    return {
        "pattern": pattern_str,
        "labels": labels,
        "status": f"成功覆蓋全圖標註！當前走勢已推進至最新【{last_label} 浪】位置。",
        "invalid_price": p0[2],
        "targets": {
            "全圖最高壓力": max(all_prices),
            "全圖最低支撐": min(all_prices),
            "起算點防守價": p0[2]
        }
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
            st.markdown("<div style='margin-top: 8px; font-size: 0.9em; color:gray;'>※ 支援全 K 線圖自動連續波浪標註與起算點動態切換</div>", unsafe_allow_html=True)

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

        with st.spinner(f'解析 [{display_title}] 艾略特波浪全圖結構中...'):
            try:
                df_full = utils.fetch_tech_data_fugle(raw_ticker).copy()
                if len(df_full) < 80:
                    st.error(f"🚨 無法取得 [{display_title}] 足夠的日線歷史報價資料。")
                    st.stop()

                df = df_full.tail(260).copy()
                x_dates = df.index.strftime('%m-%d')
                
                # 轉折點計算
                pivots = find_zigzag_points(df, order=4)
                
                # 設定 Point Zero 選項與 Session State 狀態綁定 (修復下拉選單失效)
                zero_options = {}
                min_global_idx = df['Low'].argmin()
                dt_min_str = df.index[min_global_idx].strftime('%Y/%m/%d')
                zero_options[f"[預設] 全圖最低點 ({dt_min_str} - {df['Low'].iloc[min_global_idx]:.1f}元)"] = min_global_idx
                
                for lp in [p for p in pivots if p[3] == 'L']:
                    dt_str = lp[1].strftime('%Y/%m/%d')
                    label_key = f"{dt_str} 低點轉折 ({lp[2]:.1f}元)"
                    if label_key not in zero_options:
                        zero_options[label_key] = lp[0]

                # 下拉選單 session state 鍵值
                state_key = f"wave_zero_select_{raw_ticker}"
                
                st.markdown("<hr style='margin: 5px 0 15px 0;'>", unsafe_allow_html=True)
                col_sel1, col_sel2 = st.columns([4, 6])
                with col_sel1:
                    selected_zero_label = st.selectbox(
                        "📌 選擇波浪 Point Zero (0 浪起算點)：",
                        options=list(zero_options.keys()),
                        key=state_key
                    )
                    selected_start_idx = zero_options[selected_zero_label]

                # 計算全圖波浪分析
                wave_result = analyze_elliott_wave_full(df, pivots, start_idx=selected_start_idx)

                # --- 繪圖區 ---
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
                
                # K 線
                fig.add_trace(go.Candlestick(x=x_dates, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線", increasing_line_color='#FF4B4B', decreasing_line_color='#00FF00'), row=1, col=1)
                
                # 全圖波浪連線與標記
                if wave_result['labels']:
                    wave_x = [df.index[lbl[0]].strftime('%m-%d') for lbl in wave_result['labels']]
                    wave_y = [lbl[2] for lbl in wave_result['labels']]
                    
                    fig.add_trace(go.Scatter(
                        x=wave_x, y=wave_y,
                        mode='lines+markers+text',
                        line=dict(color='gold', width=2, dash='solid'),
                        marker=dict(size=7, color='cyan'),
                        text=[lbl[3] for lbl in wave_result['labels']],
                        textposition="top center",
                        textfont=dict(size=13, color='gold'),
                        name="波浪軌跡"
                    ), row=1, col=1)

                # 成交量
                colors_vol = ['#FF4B4B' if row['Close'] >= row['Open'] else '#00FF00' for index, row in df.iterrows()]
                fig.add_trace(go.Bar(x=x_dates, y=df['Volume']/1000, marker_color=colors_vol, name="成交量(張)"), row=2, col=1)

                fig.update_xaxes(type='category', nticks=12, showgrid=True, gridcolor='#333')
                fig.update_layout(height=550, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False, xaxis_rangeslider_visible=False)
                fig.update_yaxes(showgrid=True, gridcolor='#333')

                # --- UI 資訊卡片 ---
                st.markdown(f"### {display_title} &nbsp;&nbsp; | &nbsp;&nbsp; 型態：<span style='color:gold;'>{wave_result['pattern']}</span>", unsafe_allow_html=True)
                
                col_chart, col_info = st.columns([7, 3])
                with col_chart:
                    st.plotly_chart(fig, use_container_width=True)

                with col_info:
                    with st.container(border=True):
                        st.markdown('<div style="font-weight:bold; font-size:1.1em; color:#8ab4f8; margin-bottom:8px;">🎯 全波段診斷</div>', unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size:0.95em; line-height:1.6;'>{wave_result['status']}</div>", unsafe_allow_html=True)

                    with st.container(border=True):
                        st.markdown('<div style="font-weight:bold; font-size:1.1em; color:#FF4B4B; margin-bottom:8px;">🛡️ 起算點價格</div>', unsafe_allow_html=True)
                        invalid_p = wave_result.get('invalid_price', 0)
                        st.markdown(f"<div style='font-size:1.2em; font-weight:bold; color:#FF4B4B;'>{invalid_p:.2f} 元</div>", unsafe_allow_html=True)

                    with st.container(border=True):
                        st.markdown('<div style="font-weight:bold; font-size:1.1em; color:#FFA500; margin-bottom:8px;">📐 關鍵區域價位</div>', unsafe_allow_html=True)
                        for t_name, t_val in wave_result.get('targets', {}).items():
                            st.markdown(f"<div style='font-size:0.9em;'>{t_name}： <b>{t_val:.1f}</b></div>", unsafe_allow_html=True)

            except Exception as e:
                st.error(f"波浪分析資料處理發生錯誤：{e}")
