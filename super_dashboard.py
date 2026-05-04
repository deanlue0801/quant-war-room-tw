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
    .metric-value { font-size: 1.2em; font-weight: bold; }
    .chip-table { width: 100%; border-collapse: collapse; margin-top: 5px; font-size: 0.9em; text-align: right; }
    .chip-table th { border-bottom: 1px solid #555; padding: 5px; color: #8ab4f8; text-align: right; font-weight: normal; }
    .chip-table td { padding: 5px; border-bottom: 1px dotted #333; }
    .text-red { color: #FF4B4B; }
    .text-green { color: #00FF00; }
    @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(255, 75, 75, 0.7); } 70% { box-shadow: 0 0 0 10px rgba(255, 75, 75, 0); } 100% { box-shadow: 0 0 0 0 rgba(255, 75, 75, 0); } }
    .s-class-horse { background: linear-gradient(45deg, #FF4B4B, #FF8C00); color: white; font-weight: bold; text-align: center; font-size: 1.5em; padding: 10px; border-radius: 10px; margin-bottom: 15px; animation: pulse 2s infinite; text-shadow: 1px 1px 2px black; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🌟 數據快取與字典
# ==========================================
@st.cache_data(ttl=86400)
def load_stock_dicts():
    try:
        dl_info = DataLoader()
        info_df = dl_info.taiwan_stock_info()
        return dict(zip(info_df['stock_id'].astype(str), info_df['stock_name'])), dict(zip(info_df['stock_name'], info_df['stock_id'].astype(str)))
    except: return {}, {}

stock_dict, name_to_id_dict = load_stock_dicts()

def color_num(val):
    if val > 0: return f"<span class='text-red'>+{val:,.0f}</span>"
    elif val < 0: return f"<span class='text-green'>{val:,.0f}</span>"
    else: return "0"

# ✨ 強效快取機制
@st.cache_data(ttl=1800)
def fetch_tech_data(ticker):
    # 嘗試抓取上市或上櫃資料
    df = yf.Ticker(f"{ticker}.TW").history(period="1y")
    if len(df) < 20:
        df = yf.Ticker(f"{ticker}.TWO").history(period="1y")
    # 🚨 重要：清除開頭可能存在的無效資料
    df = df.dropna(subset=['Close'])
    return df

@st.cache_data(ttl=3600)
def fetch_chip_data(ticker, start, end, token):
    dl = DataLoader()
    if token:
        try: dl.login_by_token(api_token=token)
        except: pass
    return dl.taiwan_stock_institutional_investors(stock_id=ticker, start_date=start, end_date=end)

# ==========================================
# 2. 控制列
# ==========================================
col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1.5, 1.5, 6])
with col_ctrl1:
    raw_input = st.text_input("搜尋", "6269", label_visibility="collapsed", placeholder="輸入代號或中文")
with col_ctrl2:
    analyze_btn = st.button("🔥 啟動解析", use_container_width=True)

# ==========================================
# 3. 核心運算
# ==========================================
if analyze_btn or raw_input:
    search_term = str(raw_input).strip()
    raw_ticker = name_to_id_dict.get(search_term, search_term)
    stock_name = stock_dict.get(raw_ticker, "")
    display_title = f"{raw_ticker} {stock_name}"
    
    try:
        # --- 技術面計算 ---
        df_full = fetch_tech_data(raw_ticker)
        if len(df_full) < 20:
            st.error(f"無法取得 {display_title} 的足夠資料，請檢查代號是否正確。")
            st.stop()

        df_full['MA20'] = df_full['Close'].rolling(window=20).mean()
        df_full['MA60'] = df_full['Close'].rolling(window=60).mean()
        latest_close = df_full['Close'].iloc[-1]
        
        # 安全計算指標 (防止分母為0)
        df_full['Vol_MA5'] = df_full['Volume'].rolling(5).mean()
        
        df = df_full.tail(120).copy()
        df.index = df.index.tz_localize(None)
        x_dates = df.index.strftime('%m-%d')
        
        # --- 籌碼面計算 ---
        token = st.secrets.get("FINMIND_TOKEN", "")
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=45)
        df_chip = fetch_chip_data(raw_ticker, str(start_date), str(end_date), token)
        
        # ==========================================
        # 4. 渲染 UI (這裡增加了數據安全性檢查)
        # ==========================================
        st.markdown(f"### {display_title}")
        
        col_l, col_r = st.columns([2, 1])
        
        with col_l:
            with st.container(border=True):
                st.markdown('<div class="section-title">技術分析</div>', unsafe_allow_html=True)
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=x_dates, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
                fig.add_trace(go.Scatter(x=x_dates, y=df['MA20'], line=dict(color='cyan', width=1), name='MA20'), row=1, col=1)
                fig.update_layout(height=400, margin=dict(l=0, r=0, t=0, b=0), xaxis_rangeslider_visible=False, template="plotly_dark")
                st.plotly_chart(fig, use_container_width=True)

        with col_r:
            with st.container(border=True):
                st.markdown('<div class="section-title">關鍵數據</div>', unsafe_allow_html=True)
                st.write(f"今日收盤: **{latest_close:.2f}**")
                ma20_val = df['MA20'].iloc[-1]
                if not np.isnan(ma20_val):
                    st.write(f"月線支撐: **{ma20_val:.2f}**")
                else:
                    st.warning("月線資料計算中...")

                if not df_chip.empty:
                    st.success("籌碼資料已連線")
                else:
                    st.error("籌碼 API 限制中，請稍後再試或使用 Token")

    except Exception as e:
        st.error("⚠️ 偵測到數據異常")
        st.exception(e) # 這裡會直接告訴我們哪一行出錯
