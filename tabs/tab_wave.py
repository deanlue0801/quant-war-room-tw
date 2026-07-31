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

def _check_impulse_rules(p0, p1, p2, p3, p4, p5, direction):
    """
    檢查 1-2-3-4-5 是否符合艾略特波浪的三條硬性規則，direction='up' 或 'down'。
    同時檢查轉折點的高低屬性是否符合推升浪應有的交替型態 (H-L-H-L-H 或 L-H-L-H-L)。
    """
    if direction == 'up':
        if not (p1[3] == 'H' and p2[3] == 'L' and p3[3] == 'H' and p4[3] == 'L' and p5[3] == 'H'):
            return False, {}
        rule_w2_hold = p2[2] > p0[2]          # 浪 2 不得跌破浪 0 起點
        rule_w4_no_overlap = p4[2] > p1[2]    # 浪 4 低點不得跌破浪 1 高點 (不重疊)
        w1_len, w3_len, w5_len = p1[2]-p0[2], p3[2]-p2[2], p5[2]-p4[2]
        rule_w3_not_shortest = not (w3_len < w1_len and w3_len < w5_len)  # 浪 3 不可為最短
        rule_w1_not_longest = not (w1_len > w3_len and w1_len > w5_len)  # 建議性規則：浪 1 通常非最長
    else:
        if not (p1[3] == 'L' and p2[3] == 'H' and p3[3] == 'L' and p4[3] == 'H' and p5[3] == 'L'):
            return False, {}
        rule_w2_hold = p2[2] < p0[2]
        rule_w4_no_overlap = p4[2] < p1[2]
        w1_len, w3_len, w5_len = p0[2]-p1[2], p2[2]-p3[2], p4[2]-p5[2]
        rule_w3_not_shortest = not (w3_len < w1_len and w3_len < w5_len)
        rule_w1_not_longest = not (w1_len > w3_len and w1_len > w5_len)

    is_valid = rule_w2_hold and rule_w4_no_overlap and rule_w3_not_shortest
    detail = {
        "w1": w1_len, "w3": w3_len, "w5": w5_len,
        "guideline_w1_not_longest": rule_w1_not_longest
    }
    return is_valid, detail


def _is_triangle(points):
    """檢查一組轉折點的高點是否遞減、低點是否遞增 (收斂三角)"""
    highs = [p[2] for p in points if p[3] == 'H']
    lows = [p[2] for p in points if p[3] == 'L']
    if len(highs) < 2 or len(lows) < 2:
        return False
    highs_desc = all(highs[i] > highs[i+1] for i in range(len(highs)-1))
    lows_asc = all(lows[i] < lows[i+1] for i in range(len(lows)-1))
    return highs_desc and lows_asc


def _classify_correction(p0, pts):
    """
    針對 0 浪之後的一串轉折點，判斷屬於 Zigzag(A-B-C)、Flat(平台)、
    Triangle(A-B-C-D-E) 還是 W-X-Y 複式修正，回傳 (pattern_str, extra_labels, targets)。
    pts 須為 valid_pivots[1:] 或推升浪五浪之後剩餘的點。
    """
    n = len(pts)
    if n == 0:
        return "尚無修正轉折點", [], {}

    if n == 1:
        pa = pts[0]
        return "A 浪修正進行中（等待 B、C 浪成形）", [(pa[0], pa[1], pa[2], "Ⓐ")], {}

    pa, pb = pts[0], pts[1]
    a_len = abs(pa[2] - p0[2])
    b_retrace_ratio = (abs(pb[2] - pa[2]) / a_len) if a_len > 0 else 0

    if n == 2:
        return (
            "A-B 修正進行中（等待 C 浪确认）",
            [(pa[0], pa[1], pa[2], "Ⓐ"), (pb[0], pb[1], pb[2], "Ⓑ")],
            {}
        )

    # n >= 3：優先檢查是否為三角收斂 (最多取前 5 點 A-B-C-D-E)
    tri_candidates = pts[:5]
    if n >= 4 and _is_triangle(tri_candidates):
        tri_labels_txt = ["Ⓐ", "Ⓑ", "Ⓒ", "Ⓓ", "Ⓔ"]
        extra = [(pt[0], pt[1], pt[2], tri_labels_txt[i]) for i, pt in enumerate(tri_candidates)]
        highs = [p[2] for p in tri_candidates if p[3] == 'H']
        lows = [p[2] for p in tri_candidates if p[3] == 'L']
        targets = {"三角收斂上緣": max(highs), "三角收斂下緣": min(lows)}
        return "三角收斂修正 (Triangle A-B-C-D-E)", extra, targets

    pc = pts[2]
    a_is_down = pa[3] == 'L'  # A 浪方向：True 表示從 p0 向下修正 (原趨勢向上)
    c_beyond_a = (pc[2] < pa[2]) if a_is_down else (pc[2] > pa[2])

    if n == 3:
        if 0.9 <= b_retrace_ratio <= 1.10 and not c_beyond_a:
            pattern_str = "Flat 平台型修正 (A-B-C，B浪深度回撤)"
        elif b_retrace_ratio < 0.9 and c_beyond_a:
            pattern_str = "標準 Zigzag 修正浪 (A-B-C)"
        elif b_retrace_ratio > 1.0 and not c_beyond_a:
            pattern_str = "Expanded 擴張型修正 (A-B-C，B浪超越起點)"
        else:
            pattern_str = "A-B-C 修正浪"
        extra = [(pa[0], pa[1], pa[2], "Ⓐ"), (pb[0], pb[1], pb[2], "Ⓑ"), (pc[0], pc[1], pc[2], "Ⓒ")]
        targets = {"修正波段高點": max(pa[2], pb[2], pc[2]), "修正波段低點": min(pa[2], pb[2], pc[2])}
        return pattern_str, extra, targets

    # n >= 4 且非三角 -> W-X-Y (或更多重) 複式修正
    wxy_labels_txt = ["W", "X", "Y", "X2", "Z"]
    extra = [(pt[0], pt[1], pt[2], wxy_labels_txt[i] if i < len(wxy_labels_txt) else f"V{i}") for i, pt in enumerate(pts)]
    targets = {"箱型頂部壓力": max(p[2] for p in pts), "箱型底部支撐": min(p[2] for p in pts)}
    return "W-X-Y 複式修正型態", extra, targets


def analyze_elliott_wave(df, pivots, start_idx=0):
    """
    艾略特波浪型態辨識：
    - 同時檢查「向上啟動」與「向下啟動」兩種 1-5 衝擊浪 (符合三條硬性規則才成立)
    - 五浪成立後，接續辨識後續修正型態 (Zigzag / Flat / Triangle / W-X-Y)
    - 若不構成衝擊浪，則將全部轉折點視為修正結構分析
    """
    valid_pivots = [p for p in pivots if p[0] >= start_idx]
    if len(valid_pivots) < 3:
        return {"pattern": "資料不足", "labels": [], "status": "轉折點數量不足，無法分析波浪。", "targets": {}}

    p0 = valid_pivots[0]
    labels = [(p0[0], p0[1], p0[2], "⓪")]

    is_upward_start = valid_pivots[1][3] == 'H'
    direction = 'up' if is_upward_start else 'down'

    # --- 情境 A：檢查是否構成 1-5 衝擊浪 (上漲或下跌方向皆檢查) ---
    if len(valid_pivots) >= 6:
        p1, p2, p3, p4, p5 = valid_pivots[1:6]
        is_impulse, rule_detail = _check_impulse_rules(p0, p1, p2, p3, p4, p5, direction)

        if is_impulse:
            wave_num_labels = ["①", "②", "③", "④", "⑤"]
            for lbl, pt in zip(wave_num_labels, [p1, p2, p3, p4, p5]):
                labels.append((pt[0], pt[1], pt[2], lbl))

            remains = valid_pivots[6:]
            corr_pattern, corr_extra, corr_targets = _classify_correction(p5, remains)
            labels.extend(corr_extra)

            trend_word = "多頭推升" if direction == 'up' else "空頭下殺"
            if corr_extra:
                pattern_str = f"標準 1-5 {trend_word} + {corr_pattern}"
            else:
                pattern_str = f"標準 1-5 {trend_word}浪"

            targets = {
                ("波段高點壓力" if direction == 'up' else "波段低點支撐"): (max if direction == 'up' else min)(p[2] for p in valid_pivots[:6]),
                "起算關鍵防守": p0[2]
            }
            targets.update(corr_targets)

            note = ""
            if not rule_detail.get("guideline_w1_not_longest", True):
                note = "（提醒：浪 1 幅度大於浪 3、浪 5，屬非典型結構，建議留意浪 3 是否被低估）"

            return {
                "pattern": pattern_str,
                "labels": labels,
                "status": f"成功捕捉{trend_word}結構，當前進展至【{labels[-1][3]} 浪】。{note}",
                "invalid_price": p0[2],
                "targets": targets
            }

    # --- 情境 B：不構成衝擊浪 -> 整段視為修正結構分析 ---
    corr_pattern, corr_extra, corr_targets = _classify_correction(p0, valid_pivots[1:])
    labels.extend(corr_extra)

    if not corr_targets:
        corr_targets = {
            "區間高點": max(p[2] for p in valid_pivots),
            "區間低點": min(p[2] for p in valid_pivots)
        }

    last_label = labels[-1][3] if len(labels) > 1 else "⓪"
    return {
        "pattern": corr_pattern,
        "labels": labels,
        "status": f"當前盤勢判定為【{corr_pattern}】，目前位於【{last_label} 浪】。",
        "invalid_price": p0[2],
        "targets": corr_targets
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
