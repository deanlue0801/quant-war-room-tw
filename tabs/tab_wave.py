import streamlit as st
import pandas as pd
import numpy as np
import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import utils

def find_zigzag_points(df, order=4):
    """
    動態波浪轉折點擷取 (ZigZag)，確保覆蓋全圖並精準抓取頂底
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
                
    # 過濾連續同性質點，僅保留極值
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
                
    # 強制連接至最新區間極值，防止繪圖斷裂
    if filtered_pivots:
        last_idx = filtered_pivots[-1][0]
        if n - 1 - last_idx >= 2:
            sub_df = df.iloc[last_idx:]
            if filtered_pivots[-1][3] == 'H':
                min_idx = sub_df['Low'].argmin() + last_idx
                filtered_pivots.append((min_idx, df.index[min_idx], df['Low'].iloc[min_idx], 'L'))
            else:
                max_idx = sub_df['High'].argmax() + last_idx
                filtered_pivots.append((max_idx, df.index[max_idx], df['High'].iloc[max_idx], 'H'))

    return filtered_pivots

def analyze_elliott_wave(df, pivots, start_idx=0):
    """
    艾略特波浪型態精密辨識：區分 1-5 推升浪、A-B-C 標準修正與 W-X-Y 複式修正
    """
    valid_pivots = [p for p in pivots if p[0] >= start_idx]
    if len(valid_pivots) < 3:
        return {"pattern": "資料不足", "labels": [], "status": "轉折點數量不足，無法分析波浪。", "targets": {}}

    p0 = valid_pivots[0]
    labels = [(p0[0], p0[1], p0[2], "⓪")]
    
    # 判斷趨勢方向（第一波是向上還是向下）
    is_upward_start = valid_pivots[1][3] == 'H' if len(valid_pivots) > 1 else True

    # --- 情境 A：起算點後為多頭推升（向上起步） ---
    if is_upward_start and len(valid_pivots) >= 6:
        p1, p2, p3, p4, p5 = valid_pivots[1:6]
        
        # 1-5 浪硬性規則校驗
        rule_no_overlap = p4[2] > p1[2] # 浪 4 底不破浪 1 頂
        rule_w2_hold = p2[2] > p0[2]    # 浪 2 不破起算點
        w1_len = p1[2] - p0[2]
        w3_len = p3[2] - p2[2]
        w5_len = p5[2] - p4[2]
        rule_w3_not_shortest = not (w3_len < w1_len and w3_len < w5_len)
        
        if rule_w2_hold and rule_w3_not_shortest and rule_no_overlap:
            labels.extend([
                (p1[0], p1[1], p1[2], "①"),
                (p2[0], p2[1], p2[2], "②"),
                (p3[0], p3[1], p3[2], "③"),
                (p4[0], p4[1], p4[2], "④"),
                (p5[0], p5[1], p5[2], "⑤")
            ])
            
            # 五浪過後的修正段辨識 (ABC vs WXY)
            remains = valid_pivots[6:]
            if len(remains) >= 3:
                pa, pb, pc = remains[0:3]
                # 若 B 浪反彈未過浪 5 高點，且 C 浪破 A 浪低點 -> 標準 ABC
                if pb[2] < p5[2] and pc[2] < pa[2]:
                    labels.extend([(pa[0], pa[1], pa[2], "Ⓐ"), (pb[0], pb[1], pb[2], "Ⓑ"), (pc[0], pc[1], pc[2], "Ⓒ")])
                    pattern_str = "標準 1-5 推升 + A-B-C 修正"
                else: # 橫向複雜洗盤 -> W-X-Y 複式修正
                    labels.extend([(pa[0], pa[1], pa[2], "W"), (pb[0], pb[1], pb[2], "X"), (pc[0], pc[1], pc[2], "Y")])
                    pattern_str = "標準 1-5 推升 + W-X-Y 複式修正"
            else:
                pattern_str = "標準 1-5 推升浪"

            return {
                "pattern": pattern_str,
                "labels": labels,
                "status": f"成功捕捉多頭推升結構，當前進展至【{labels[-1][3]} 浪】。",
                "invalid_price": p0[2],
                "targets": {"波段高點壓力": max([p[2] for p in valid_pivots]), "起漲關鍵防守": p0[2]}
            }

    # --- 情境 B：修正波段辨識 (A-B-C vs W-X-Y 分開判定) ---
    # 計算波動幅度與時間歷程以區分 A-B-C 或 W-X-Y
    pivot_count = len(valid_pivots) - 1
    
    # 檢查是否具備標準三浪 A-B-C 特性 (幅度明顯、結構單純)
    if pivot_count <= 4:
        corr_labels = ["Ⓐ", "Ⓑ", "Ⓒ", "Ⓓ", "Ⓔ"]
        for i, pt in enumerate(valid_pivots[1:]):
            labels.append((pt[0], pt[1], pt[2], corr_labels[i] if i < len(corr_labels) else f"V{i}"))
        
        return {
            "pattern": "A-B-C 標準修正浪",
            "labels": labels,
            "status": f"當前盤勢符合【A-B-C 單純修正結構】，目前位於【{labels[-1][3]} 浪】。",
            "invalid_price": p0[2],
            "targets": {"修正波段高點": max([p[2] for p in valid_pivots]), "修正波段低點": min([p[2] for p in valid_pivots])}
        }
    else:
        # 多重轉折與橫向洗盤 -> 標註為 W-X-Y 複式修正
        wxy_labels = ["W", "X", "Y", "X2", "Z"]
        for i, pt in enumerate(valid_pivots[1:]):
            labels.append((pt[0], pt[1], pt[2], wxy_labels[i] if i < len(wxy_labels) else f"V{i}"))
            
        return {
            "pattern": "W-X-Y 複式修正型態",
            "labels": labels,
            "status": f"當前呈現高複雜度【W-X-Y 複式修正整理】，目前運行至【{labels[-1][3]} 浪】。",
            "invalid_price": p0[2],
            "targets": {"箱型頂部壓力": max([p[2] for p in valid_pivots]), "箱型底部支撐": min([p[2] for p in valid_pivots])}
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

    # --- 搜尋欄位 ---
    with st.form(key='search_form_wave', clear_on_submit=False):
        col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1.5, 1.5, 6])
        with col_ctrl1:
            raw_input = st.text_input("搜尋", "", label_visibility="collapsed", placeholder="輸入代號或名稱並按 Enter")
        with col_ctrl2:
            analyze_btn = st.form_submit_button("🌊 啟動波浪理論解析", use_container_width=True)
        with col_ctrl3:
            st.markdown("<div style='margin-top: 8px; font-size: 0.9em; color:gray;'>※ 支援 1-5 推升浪、A-B-C 標準修正與 W-X-Y 複式修正自動識別</div>", unsafe_allow_html=True)

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

                df = df_full.tail(260).copy()
                x_dates = df.index.strftime('%m-%d')
                
                # 轉折點計算
                pivots = find_zigzag_points(df, order=5)
                
                # 智能設定 Point Zero 下拉選單 (自動將全圖最低點與顯著起漲點列出)
                zero_options = {}
                min_global_idx = df['Low'].argmin()
                dt_min_str = df.index[min_global_idx].strftime('%Y/%m/%d')
                zero_options[f"[自動預設] 最低點起算 ({dt_min_str} - {df['Low'].iloc[min_global_idx]:.1f}元)"] = min_global_idx
                
                # 補上其他轉折低點供選取
                for lp in [p for p in pivots if p[3] == 'L']:
                    dt_str = lp[1].strftime('%Y/%m/%d')
                    label_key = f"{dt_str} 轉折低點 ({lp[2]:.1f}元)"
                    if label_key not in zero_options:
                        zero_options[label_key] = lp[0]

                st.markdown("<hr style='margin: 5px 0 15px 0;'>", unsafe_allow_html=True)
                col_sel1, col_sel2 = st.columns([4, 6])
                with col_sel1:
                    selected_zero_label = st.selectbox("📌 選擇波浪 Point Zero (0 浪起算點)：", list(zero_options.keys()))
                    selected_start_idx = zero_options[selected_zero_label]

                wave_result = analyze_elliott_wave(df, pivots, start_idx=selected_start_idx)

                # --- 繪圖 ---
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
                
                # K 線
                fig.add_trace(go.Candlestick(x=x_dates, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線", increasing_line_color='#FF4B4B', decreasing_line_color='#00FF00'), row=1, col=1)
                
                # 波浪路徑與標籤
                if wave_result['labels']:
                    wave_x = [df.index[lbl[0]].strftime('%m-%d') for lbl in wave_result['labels']]
                    wave_y = [lbl[2] for lbl in wave_result['labels']]
                    
                    fig.add_trace(go.Scatter(x=wave_x, y=wave_y, mode='lines+markers+text', line=dict(color='gold', width=2.5, dash='solid'), marker=dict(size=8, color='cyan'), text=[lbl[3] for lbl in wave_result['labels']], textposition="top center", textfont=dict(size=14, color='gold'), name="波浪軌跡"), row=1, col=1)

                # 成交量
                colors_vol = ['#FF4B4B' if row['Close'] >= row['Open'] else '#00FF00' for index, row in df.iterrows()]
                fig.add_trace(go.Bar(x=x_dates, y=df['Volume']/1000, marker_color=colors_vol, name="成交量(張)"), row=2, col=1)

                fig.update_xaxes(type='category', nticks=12, showgrid=True, gridcolor='#333')
                fig.update_layout(height=540, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False, xaxis_rangeslider_visible=False)
                fig.update_yaxes(showgrid=True, gridcolor='#333')

                # --- UI 資訊區域 ---
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

                    with st.container(border=True):
                        st.markdown('<div style="font-weight:bold; font-size:1.1em; color:#FFA500; margin-bottom:8px;">📐 關鍵位階</div>', unsafe_allow_html=True)
                        for t_name, t_val in wave_result.get('targets', {}).items():
                            st.markdown(f"<div style='font-size:0.9em;'>{t_name}： <b>{t_val:.1f}</b></div>", unsafe_allow_html=True)

            except Exception as e:
                st.error(f"波浪分析資料處理發生錯誤：{e}")
