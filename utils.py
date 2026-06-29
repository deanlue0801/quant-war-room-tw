import streamlit as st
import pandas as pd
import datetime
from FinMind.data import DataLoader
from fugle_marketdata import RestClient 

# API 金鑰設定
try:
    FUGLE_API_KEY = st.secrets.get("FUGLE_API_KEY", "")
except:
    FUGLE_API_KEY = ""

try:
    FINMIND_TOKEN = st.secrets.get("FINMIND_TOKEN", "")
except:
    FINMIND_TOKEN = ""

def load_css():
    st.markdown("""
    <style>
        .block-container { padding-top: 3rem !important; padding-bottom: 1rem !important; max-width: 98vw !important;}
        div[data-testid="stVerticalBlock"] > div { padding-bottom: 0.1rem; }
        div[data-testid="stDecoration"] { display: none; }
        
        .section-title { color: #8ab4f8; font-weight: bold; border-bottom: 1px solid #333; padding-bottom: 3px; margin-bottom: 5px; font-size: 1.05em; }
        .title-red { color: #FF4B4B !important; }
        .text-sm { font-size: 0.85em; line-height: 1.3; }
        .metric-value { font-size: 1.2em; font-weight: bold; }
        
        .chip-table { width: 100%; border-collapse: collapse; margin-top: 5px; font-size: 0.9em; text-align: right; }
        .chip-table th { border-bottom: 1px solid #555; padding: 5px; color: #8ab4f8; text-align: right; font-weight: normal; }
        .chip-table td { padding: 5px; border-bottom: 1px dotted #333; }
        .chip-table .row-title { text-align: left; color: #ccc; }
        .text-red { color: #FF4B4B; }
        .text-green { color: #00FF00; }
        
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(255, 75, 75, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(255, 75, 75, 0); }
            100% { box-shadow: 0 0 0 0 rgba(255, 75, 75, 0); }
        }
        .s-class-horse {
            background: linear-gradient(45deg, #FF4B4B, #FF8C00);
            color: white; font-weight: bold; text-align: center; font-size: 1.5em;
            padding: 10px; border-radius: 10px; margin-bottom: 15px;
            animation: pulse 2s infinite; text-shadow: 1px 1px 2px black;
        }
        .potential-stars { font-size: 1.2em; color: #FFD700; }
        .zone-indicator { padding: 5px 10px; border-radius: 5px; font-weight: bold; text-align: center; margin-top: 5px; border: 1px solid #555;}
        .stTabs [data-baseweb="tab-list"] { gap: 24px; }
        .stTabs [data-baseweb="tab"] { height: 50px; font-size: 1.2rem; }
        
        .strategy-666-box { background: rgba(138, 180, 248, 0.05); border-left: 4px solid #8ab4f8; padding: 10px 15px; border-radius: 4px; margin-top: 10px;}
        .signal-buy { background: rgba(0, 255, 0, 0.1); border: 2px solid #00FF00; padding: 10px; border-radius: 8px; text-align: center; margin-top: 5px; }
        .signal-sell { background: rgba(255, 75, 75, 0.1); border: 2px solid #FF4B4B; padding: 10px; border-radius: 8px; text-align: center; margin-top: 5px; }
        .signal-wait { background: rgba(128, 128, 128, 0.1); border: 2px dashed #888; padding: 10px; border-radius: 8px; text-align: center; margin-top: 5px; color: #bbb; }
        .deduct-box { background: rgba(138, 180, 248, 0.1); padding: 15px; border-radius: 10px; border: 1px solid #8ab4f8; margin-top: 10px; }
    </style>
    """, unsafe_allow_html=True)

def color_num(val):
    if val > 0: return f"<span class='text-red'>+{val:,.0f}</span>"
    elif val < 0: return f"<span class='text-green'>{val:,.0f}</span>"
    else: return "0"

@st.cache_data(ttl=86400)
def load_stock_dicts():
    try:
        dl_info = DataLoader()
        info_df = dl_info.taiwan_stock_info()
        id_to_name = dict(zip(info_df['stock_id'].astype(str), info_df['stock_name']))
        name_to_id = dict(zip(info_df['stock_name'], info_df['stock_id'].astype(str)))
        return id_to_name, name_to_id, info_df
    except:
        return {}, {}, pd.DataFrame()

@st.cache_data(ttl=60, show_spinner=False)
def fetch_tech_data_fugle(ticker):
    try:
        client = RestClient(api_key=FUGLE_API_KEY)
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=360)
        
        kwargs = {"symbol": ticker, "timeframe": "D", "from": start_date.strftime('%Y-%m-%d'), "to": end_date.strftime('%Y-%m-%d')}
        candles = client.stock.historical.candles(**kwargs)
        df = pd.DataFrame(candles['data'])
        
        if not df.empty:
            df = df.rename(columns={'date': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
            df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None) 
            df = df.set_index('Date').sort_index()
        else:
            df = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'])
            
        try:
            quote = client.stock.intraday.quote(symbol=ticker)
            close_p = quote.get('closePrice') or (quote.get('lastTrade') or {}).get('price')
            if close_p is not None:
                today_ts = pd.Timestamp(end_date)
                vol_lots = (quote.get('total') or {}).get('tradeVolume', 0)
                vol_shares = vol_lots * 1000
                open_p = quote.get('openPrice') or close_p
                high_p = quote.get('highPrice') or close_p
                low_p = quote.get('lowPrice') or close_p
                
                if df.empty or df.index[-1].date() != end_date:
                    today_df = pd.DataFrame([{'Date': today_ts, 'Open': open_p, 'High': high_p, 'Low': low_p, 'Close': close_p, 'Volume': vol_shares}]).set_index('Date')
                    df = pd.concat([df, today_df])
                else:
                    df.loc[today_ts, ['Open', 'High', 'Low', 'Close', 'Volume']] = [open_p, high_p, low_p, close_p, vol_shares]
        except Exception:
            pass 
        return df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=60, show_spinner=False)
def fetch_tech_data_fugle_60m(ticker):
    try:
        client = RestClient(api_key=FUGLE_API_KEY)
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=90)
        
        # 1. 抓取歷史 60分K (Fugle 歷史資料通常只有到昨日)
        kwargs = {"symbol": ticker, "timeframe": "60", "from": start_date.strftime('%Y-%m-%d'), "to": end_date.strftime('%Y-%m-%d')}
        hist_candles = client.stock.historical.candles(**kwargs)
        df_hist = pd.DataFrame(hist_candles.get('data', []))
        
        # 2. 抓取今日盤中 60分K (Fugle 即時 K 線)
        try:
            intra_candles = client.stock.intraday.candles(symbol=ticker, timeframe="60")
            df_intra = pd.DataFrame(intra_candles.get('data', []))
        except Exception:
            df_intra = pd.DataFrame()

        # 3. 合併歷史與盤中資料
        df = pd.concat([df_hist, df_intra], ignore_index=True)
        
        if not df.empty:
            df = df.rename(columns={'date': 'Date', 'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
            df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None) 
            
            # 確保不會有重複的時間點（以防盤中與歷史資料重疊）
            df = df.drop_duplicates(subset=['Date'], keep='last')
            
            return df.set_index('Date').sort_index()[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
            
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_chip_data(ticker, start, end, token):
    dl = DataLoader()
    if token:
        try: dl.login_by_token(api_token=token)
        except: pass
    return dl.taiwan_stock_institutional_investors(stock_id=ticker, start_date=start, end_date=end)

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_margin_data(ticker, start, end, token):
    dl = DataLoader()
    if token:
        try: dl.login_by_token(api_token=token)
        except: pass
    return dl.taiwan_stock_margin_purchase_short_sale(stock_id=ticker, start_date=start, end_date=end)
