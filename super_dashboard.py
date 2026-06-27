import streamlit as st
import warnings

warnings.filterwarnings('ignore', category=FutureWarning)

# 1. 網頁基本設定 (必須在所有載入前第一行執行)
st.set_page_config(page_title="終極量化戰情室", layout="wide", initial_sidebar_state="collapsed")

# 載入自訂工具與分頁模組
import utils
from tabs import tab_single, tab_666

# 2. 載入共用 CSS 樣式
utils.load_css()

# 3. 建立畫面分頁
tab_monitor, tab_666_page = st.tabs(["📊 單檔戰情解析", "🎯 666戰法 (60分K分析)"])

# 4. 呼叫各分頁的渲染函數
with tab_monitor:
    tab_single.render()

with tab_666_page:
    tab_666.render()
