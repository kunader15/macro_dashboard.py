import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import io
from datetime import datetime, timedelta
import numpy as np
import plotly.graph_objects as go

# --- 1. 初始化與介面設定 ---
st.set_page_config(page_title="PRO Asset Allocation Dashboard", layout="wide", page_icon="🎯")
st.title("🎯 對沖基金級：宏觀與生命週期配置系統 (PRO版)")
st.markdown("遵循 **三層作戰系統**：底層被動結構、中層年齡滑動路徑 (Glide Path)、頂層 4D 宏觀微調，並具備**雙確認機制作為防線**。")

# --- 2. 獲取真實數據 ---
@st.cache_data(ttl=86400)
def fetch_data():
    # 獲取過去兩年的數據以計算 YoY，並多抓一點防止假日
    end = datetime.now()
    start = end - timedelta(days=730) 
    
    try:
        # FRED 數據
        metrics = {'CPI': 'CPIAUCSL', 'Spread': 'T10Y2Y', 'Rate': 'FEDFUNDS'}
        dfs = []
        for name, code in metrics.items():
            url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={code}&cosd={start.strftime('%Y-%m-%d')}&coed={end.strftime('%Y-%m-%d')}"
            response = requests.get(url)
            df = pd.read_csv(io.StringIO(response.text), index_col=0, parse_dates=True)
            df = df.rename(columns={code: name})
            dfs.append(df)
        df = pd.concat(dfs, axis=1, sort=False)
        df.columns = list(metrics.keys())
        
        # 抓取 VIX
        vix_df = yf.download("^VIX", start=start, end=end)['Close']
        
        return df, vix_df
    except Exception as e:
        print(f"Fetch error: {e}")
        return None, None

df_macro, df_vix = fetch_data()

# 數據狀態解析
cpi_yoy_series = None
if df_macro is not None:
    # 確保有足夠資料計算
    cpi_series = df_macro['CPI'].dropna()
    # 產生 CPI YoY 的歷史序列給趨勢圖使用
    cpi_yoy_series = (cpi_series / cpi_series.shift(12) - 1) * 100
    cpi_yoy_series = cpi_yoy_series.dropna()
    
    # CPI 是月度發布，YoY 為相隔 12/13 期的變動
    cpi_yoy_latest = (cpi_series.iloc[-1] / cpi_series.iloc[-13] - 1) * 100 if len(cpi_series) >= 13 else 3.0
    cpi_yoy_prev1 = (cpi_series.iloc[-2] / cpi_series.iloc[-14] - 1) * 100 if len(cpi_series) >= 14 else cpi_yoy_latest
    cpi_yoy_prev2 = (cpi_series.iloc[-3] / cpi_series.iloc[-15] - 1) * 100 if len(cpi_series) >= 15 else cpi_yoy_latest
    
    # 最近的 CPI 趨勢
    cpi_trend_str = "Up" if cpi_yoy_latest > cpi_yoy_prev1 else "Down"
    
    # 利率趨勢
    rate_series = df_macro['Rate'].dropna()
    rate_latest = rate_series.iloc[-1]
    rate_prev = rate_series.iloc[-2] if len(rate_series) >= 2 else rate_latest
    rate_trend_str = "Up" if rate_latest > rate_prev else "Down" if rate_latest < rate_prev else "Flat"
    
    spread_series = df_macro['Spread'].dropna()
    spread_latest = spread_series.iloc[-1] if len(spread_series) > 0 else 0.0
    
    # 處理 VIX，確保不管 yfinance 回傳什麼結構都能拿到 float
    vix_val = df_vix.values[-1]
    vix_latest = float(vix_val[0] if isinstance(vix_val, (np.ndarray, list)) else vix_val)
    
else:
    # 手動備援
    cpi_yoy_latest, cpi_yoy_prev1, cpi_yoy_prev2 = 3.2, 3.0, 2.8
    cpi_trend_str = "Up"
    rate_trend_str = "Up"
    spread_latest = 0.5
    vix_latest = 18.0
    rate_latest = 5.25
    rate_prev = 5.0

# --- 側邊欄 ---
st.sidebar.header("👤 1. 個人化參數")
current_age = st.sidebar.slider("目前年齡", 18, 80, 43)
retire_age = st.sidebar.slider("預計退休年齡", 50, 85, 60)
years_to_retire = retire_age - current_age

st.sidebar.divider()
st.sidebar.header("⚙️ 2. 當前經濟輸入")
use_auto = st.sidebar.checkbox("使用自動抓取數據", value=(df_macro is not None))

st.sidebar.markdown("""
**👉 PMI 數據來源：**  
[點此查詢 TradingEconomics (ISM 製造業 PMI)](https://tradingeconomics.com/united-states/manufacturing-pmi)  
請從圖表中讀取近 3 個月數值，填入下方，系統自動幫您判斷趨勢！
""")

st.sidebar.markdown("**📊 輸入近 3 個月 PMI（從圖表讀取）**")
pmi_col1, pmi_col2, pmi_col3 = st.sidebar.columns(3)
with pmi_col1:
    pmi_2m_ago = st.number_input("前2月", value=52.4, step=0.1, format="%.1f")
with pmi_col2:
    pmi_1m_ago = st.number_input("上月", value=51.5, step=0.1, format="%.1f")
with pmi_col3:
    pmi_current = st.number_input("本月", value=52.2, step=0.1, format="%.1f")

# 自動判斷 PMI 趨勢 (簡化邏輯)
pmi_input = pmi_current
if pmi_current > pmi_1m_ago and pmi_current > pmi_2m_ago:
    pmi_trend = "Up"
elif pmi_current < pmi_1m_ago and pmi_current < pmi_2m_ago:
    pmi_trend = "Down"
else:
    pmi_trend = "Flat"

pmi_trend_labels = {"Up": "🟢 Up (上升)", "Down": "🔴 Down (下降)", "Flat": "⚪ Flat (震盪)"}
st.sidebar.info(f"**PMI 自動趨勢判斷：{pmi_trend_labels[pmi_trend]}**")

if use_auto:
    cpi_input = cpi_yoy_latest
    spread_input = spread_latest
    vix_input = vix_latest
    rate_direction = rate_trend_str
else:
    cpi_input = st.sidebar.number_input("手動 CPI YoY (%)", value=round(cpi_yoy_latest, 2))
    spread_input = st.sidebar.number_input("手動 10Y-2Y 差值", value=round(spread_latest, 2))
    vix_input = st.sidebar.number_input("手動 VIX", value=round(vix_latest, 2))
    rate_direction = st.sidebar.selectbox("手動利率趨勢", ["Up", "Down", "Flat"])

with st.sidebar.expander("📚 PMI 趨勢判斷原理", expanded=False):
    st.markdown("""
    **系統自動判斷邏輯（超簡單）**
    
    🟢 **Up (上升)**：  
    本月 > 上月 **且** 本月 > 前2月  
    *(連續兩個月都贏 = 真正在漲)*

    🔴 **Down (下降)**：  
    本月 < 上月 **且** 本月 < 前2月  
    *(連續兩個月都輸 = 真正在跌)*

    ⚪ **Flat (震盪)**：  
    不符合以上條件。例如：  
    V 型反彈（上月跌、本月漲回）→ 只是震盪，**不算真正上升**！  
    系統此時強制「不動」，保護您不被假突破洗出場。
    """)

# --- 主畫面 ---
st.header("📊 4D 儀表板觀測站")
st.caption("以下顯示最新判斷資料。圖表提供 **油表式(Gauge)視覺化**，讓您一眼看出數值落在哪個危險/安全區間。")

def create_gauge(val, title, min_val, max_val, steps, ref_val=None):
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta" if ref_val is not None else "gauge+number",
        value=val,
        title={'text': title, 'font': {'size': 14}},
        delta={'reference': ref_val, 'relative': False, 'valueformat': '.2f'} if ref_val is not None else None,
        gauge={
            'axis': {'range': [min_val, max_val], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': "rgba(0,0,0,0)", 'thickness': 0}, # Hide default progress bar
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': steps,
            'threshold': {
                'line': {'color': "black", 'width': 3},
                'thickness': 0.8,
                'value': val
            }
        }
    ))
    # 稍微調高整體高度與上邊距 (t=70)，確保兩行標題文字不會被圖框裁切
    fig.update_layout(height=230, margin=dict(l=10, r=10, t=70, b=10))
    return fig

# Gauge 1: CPI
cpi_trend_auto = "Up" if cpi_input >= cpi_yoy_prev1 else "Down"
if cpi_input < 2.0: cpi_stage = "🟢 低通膨 (舒適)"
elif 2.0 <= cpi_input <= 3.0: cpi_stage = "🟡 模糊區 (Neutral)"
else: cpi_stage = "🔴 高通膨 (過熱)"

cpi_steps = [
    {'range': [0, 2], 'color': "#A7F3D0"}, # Green
    {'range': [2, 3], 'color': "#FDE68A"}, # Yellow
    {'range': [3, 10], 'color': "#FECACA"} # Red
]
fig_cpi = create_gauge(cpi_input, f"{cpi_stage}<br><span style='font-size:11px;color:gray'>CPI YoY (向 {cpi_trend_auto})</span>", 0, 8, cpi_steps, cpi_yoy_prev1)

# Gauge 2: Rate
if rate_latest < 2.0: rate_stage = "🟢 極度寬鬆"
elif 2.0 <= rate_latest <= 4.0: rate_stage = "🟡 中性利率區"
else: rate_stage = "🔴 緊縮區間"

rate_steps = [
    {'range': [0, 2], 'color': "#A7F3D0"},
    {'range': [2, 4], 'color': "#FDE68A"},
    {'range': [4, 8], 'color': "#FECACA"}
]
fig_rate = create_gauge(rate_latest, f"{rate_stage}<br><span style='font-size:11px;color:gray'>利率 (向 {rate_direction})</span>", 0, 7, rate_steps, rate_prev if use_auto else None)

# Gauge 3: Spread
if spread_input < 0: spread_stage = "🔴 倒掛警報"
elif 0 <= spread_input <= 1.0: spread_stage = "🟡 正常區間"
else: spread_stage = "🟢 陡峭復甦"

spread_steps = [
    {'range': [-3, 0], 'color': "#FECACA"},
    {'range': [0, 1], 'color': "#FDE68A"},
    {'range': [1, 4], 'color': "#A7F3D0"}
]
fig_spread = create_gauge(spread_input, f"{spread_stage}<br><span style='font-size:11px;color:gray'>利差 (10Y-2Y)</span>", -2, 4, spread_steps)

# Gauge 4: VIX
if vix_input < 15: vix_stage = "🔵 過度樂觀(警惕修正)"
elif 15 <= vix_input < 20: vix_stage = "🟢 市場平穩"
elif 20 <= vix_input < 30: vix_stage = "🟡 恐慌加劇"
else: vix_stage = "🔴 極度恐慌"

vix_steps = [
    {'range': [0, 15], 'color': "#BFDBFE"}, # Blue
    {'range': [15, 20], 'color': "#A7F3D0"}, # Green
    {'range': [20, 30], 'color': "#FDE68A"}, # Yellow
    {'range': [30, 60], 'color': "#FECACA"}  # Red
]
fig_vix = create_gauge(vix_input, f"{vix_stage}<br><span style='font-size:11px;color:gray'>VIX</span>", 0, 60, vix_steps)

d1, d2, d3, d4 = st.columns(4)
with d1: st.plotly_chart(fig_cpi, use_container_width=True)
with d2: st.plotly_chart(fig_rate, use_container_width=True)
with d3: st.plotly_chart(fig_spread, use_container_width=True)
with d4: st.plotly_chart(fig_vix, use_container_width=True)

with st.expander("📈 查看各指標歷史趨勢圖及原始資料列表"):
    if df_macro is not None and cpi_yoy_series is not None:
        t1, t2, t3, t4 = st.tabs(["CPI 通膨 YoY", "基準利率", "殖利率倒掛差", "VIX 恐慌指數"])
        with t1:
            st.line_chart(cpi_yoy_series.tail(12).rename("CPI YoY (%)"), height=250)
        with t2:
            st.line_chart(df_macro['Rate'].dropna().tail(12).rename("FED Funds Rate (%)"), height=250)
        with t3:
            st.line_chart(df_macro['Spread'].dropna().tail(150).rename("10Y-2Y Spread (%)"), height=250)
        with t4:
            if df_vix is not None:
                # yfinance return format handling for plotting
                vix_to_plot = df_vix.tail(150)
                if isinstance(vix_to_plot, pd.DataFrame):
                    # Pick the first column (Close) if it's a dataframe
                    vix_to_plot = vix_to_plot.iloc[:, 0]
                st.line_chart(vix_to_plot.rename("VIX Index"), height=250)
        
        st.caption("以下為近期原始不重複數據列：")
        display_df = df_macro.tail(180).dropna(subset=['CPI', 'Rate'], how='all')
        st.dataframe(display_df.tail(10).sort_index(ascending=False), use_container_width=True)
    else:
        st.warning("目前使用手動輸入模式，無歷史數據可顯示。")

# --- 核心邏輯引擎 ---
def get_baseline_alloc(age, ytr):
    # 底層：基礎資產結構 (生命週期與 Glide Path 滑動路徑) 包含 2% 預設現金流動池
    base_csh = 2.0
    if ytr <= 0:
        return 60.0, 28.0, 10.0, base_csh # 提款期
    elif 0 < ytr <= 10:
        # 轉換期 (Glide Path)：每年固定將股票轉為防禦
        stk = 60.0 + 2.0 * ytr
        bnd = 30.0 - 1.5 * ytr
        gld = 10.0 - 0.5 * ytr
        return stk, bnd - base_csh, gld, base_csh
    else:
        # 累積期 (ytr > 10)
        if age < 30:
            return 98.0, 0.0, 0.0, base_csh
        elif 30 <= age < 40:
            return 90.0, 8.0, 0.0, base_csh
        else: # 40 到 轉換期前
            return 85.0, 8.0, 5.0, base_csh

def calc_pro_alloc(age, ytr, regime, spread):
    # 1. 取得底層生命週期基線 (含預設 2% 現金)
    base_stk, base_bnd, base_gld, base_csh = get_baseline_alloc(age, ytr)
    
    # 2. 頂層：Regime 景氣動態微調 (嚴格限制在 ±5~10% 防過度擇時)
    adj_stk = 0; adj_bnd = 0; adj_gld = 0; adj_csh = 0
    
    # A. 四大明確象限
    if "明確復甦" in regime: 
        adj_stk = 5; adj_bnd = -5; adj_gld = 0; adj_csh = 0 # 2% 現金維持
    elif "明確過熱" in regime: 
        adj_stk = -10; adj_bnd = 5; adj_gld = 5; adj_csh = 0 # 2% 現金維持
    elif "明確滯脹" in regime: 
        adj_stk = -10; adj_bnd = -2; adj_gld = 10; adj_csh = 2 # 抽血換現金：拉高至 4%
    elif "明確衰退" in regime: 
        adj_stk = -10; adj_bnd = 7; adj_gld = 0; adj_csh = 3 # 抽血換現金：拉高至 5% (伺機抄底)
        
    # B. 模糊轉折區間 (提早預判微調)
    elif "復甦 ➡️ 過熱" in regime:
        adj_stk = 5; adj_bnd = -5; adj_gld = 0; adj_csh = 0  # 2% 現金
    elif "過熱 ➡️ 衰退" in regime:
        adj_stk = -10; adj_bnd = 3; adj_gld = 5; adj_csh = 2  # 高風險：拉高防守與 4% 現金
    elif "衰退 ➡️ 復甦" in regime:
        adj_stk = 10; adj_bnd = -10; adj_gld = 0; adj_csh = 0 # 2% 現金 (抄底完畢)
    elif "滯脹 ➡️ 衰退" in regime:
        adj_stk = -5; adj_bnd = 2; adj_gld = 0; adj_csh = 3   # 退入 5% 現金
        
    # C. Fallback (其他偏向的模糊狀態)
    elif "偏向：復甦" in regime: adj_stk = 5; adj_bnd = -5; adj_gld = 0; adj_csh = 0
    elif "偏向：過熱" in regime: adj_stk = -5; adj_bnd = 0; adj_gld = 5; adj_csh = 0
    elif "偏向：滯脹" in regime: adj_stk = -8; adj_bnd = -2; adj_gld = 8; adj_csh = 2
    elif "偏向：衰退" in regime: adj_stk = -8; adj_bnd = 5; adj_gld = 0; adj_csh = 3
    
    # 3. 雙確認機制 (實質進入多項衰退/倒掛，才疊加最高等級防守)
    if "衰退" in regime and spread < 0:
        adj_stk -= 5
        adj_bnd += 5
        
    final_stk = max(base_stk + adj_stk, 0)
    final_bnd = max(base_bnd + adj_bnd, 0)
    final_gld = max(base_gld + adj_gld, 0)
    final_csh = max(base_csh + adj_csh, 0)
    
    # 正規化以防總和不為 100%
    total = final_stk + final_bnd + final_gld + final_csh
    if total > 0:
        final_stk = (final_stk / total) * 100
        final_bnd = (final_bnd / total) * 100
        final_gld = (final_gld / total) * 100
        final_csh = (final_csh / total) * 100
        
    return final_stk, final_bnd, final_gld, final_csh, base_stk, base_bnd, base_gld, base_csh

# 核心景氣判斷引擎 (利率 -> PMI -> CPI)
def get_pro_regime(pmi, pmi_trend_val, cpi, cpi_trend_val, rate_dir):
    # --- 完全一致的 4 大象限 ---
    if pmi > 50 and cpi_trend_val == "Down" and rate_dir == "Down":
        return "Recovery (明確復甦)"
    elif pmi > 50 and cpi_trend_val == "Up" and rate_dir == "Up":
        return "Overheat (明確過熱)"
    elif pmi <= 50 and cpi_trend_val == "Up" and rate_dir == "Up":
        return "Stagflation (明確滯脹)"
    elif pmi <= 50 and cpi_trend_val == "Down" and rate_dir == "Down":
        return "Recession (明確衰退)"
        
    # --- 模糊區轉折判定 (重點邏輯) ---
    # A. 復甦 ↔ 過熱 (成長區模糊)
    if pmi > 50 and (2.0 <= cpi <= 3.0 or cpi_trend_val == "Up") and rate_dir == "Up":
        return "Neutral 模糊區 (介於：復甦 ➡️ 過熱)"
        
    # B. 過熱 ↔ 衰退 (最重要轉折 - 高風險區)
    if pmi > 50 and pmi_trend_val == "Down" and cpi_trend_val == "Down" and rate_dir != "Down":
        return "Neutral 模糊區 (介於：過熱 ➡️ 衰退)"
        
    # C. 衰退 ↔ 復甦 (底部)
    if pmi <= 50 and pmi_trend_val == "Up" and cpi_trend_val == "Down" and rate_dir == "Down":
        return "Neutral 模糊區 (介於：衰退 ➡️ 復甦)"
        
    # D. 滯脹 ↔ 衰退 (過渡)
    if pmi <= 50 and cpi >= 3.0 and cpi_trend_val == "Down" and rate_dir == "Down":
        return "Neutral 模糊區 (介於：滯脹 ➡️ 衰退)"
        
    # --- 預設 Fallback (未捕捉的其它狀況) ---
    if pmi > 50:
        if cpi >= 3.0: return "Neutral 模糊區 (偏向：過熱)"
        else: return "Neutral 模糊區 (偏向：復甦)"
    else:
        if cpi >= 3.0: return "Neutral 模糊區 (偏向：滯脹)"
        else: return "Neutral 模糊區 (偏向：衰退)"

current_regime = get_pro_regime(pmi_input, pmi_trend, cpi_input, cpi_trend_auto, rate_direction)
s_pct, b_pct, g_pct, c_pct, b_stk, b_bnd, b_gld, b_csh = calc_pro_alloc(current_age, years_to_retire, current_regime, spread_input)

st.divider()

# --- 輸出畫面 ---
st.subheader(f"🎯 當前策略景氣：{current_regime}")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.info("📈 股票 (VT+0050)")
    st.markdown(f"<h2 style='text-align: center; color: #1E90FF;'>{s_pct:.1f}%</h2>", unsafe_allow_html=True)
    st.caption(f"中層(基底)比例: {b_stk:.1f}%")
    st.write(f"- VT (全球): {s_pct*0.667:.1f}%")
    st.write(f"- 0050: {s_pct*0.333:.1f}%")

with col2:
    st.success("🛡️ 債券 (BND/TLT)")
    st.markdown(f"<h2 style='text-align: center; color: #32CD32;'>{b_pct:.1f}%</h2>", unsafe_allow_html=True)
    st.caption(f"中層(基底)比例: {b_bnd:.1f}%")
    st.write("避險公債")

with col3:
    st.warning("⚜️ 黃金 (GLD/IAU)")
    st.markdown(f"<h2 style='text-align: center; color: #DAA520;'>{g_pct:.1f}%</h2>", unsafe_allow_html=True)
    st.caption(f"中層(基底)比例: {b_gld:.1f}%")
    st.write("實體黃金")

with col4:
    st.error("💵 現金 (Cash)")
    st.markdown(f"<h2 style='text-align: center; color: #808080;'>{c_pct:.1f}%</h2>", unsafe_allow_html=True)
    st.caption(f"流動基底: {b_csh:.1f}%")
    st.write("生活費與抄底池")

st.divider()
st.subheader("⚖️ 偏離容忍度與再平衡建議 (Action Guidance)")
st.markdown("""
> **💡 再平衡交易紀律 (±5% 偏離法則)**：
> 很多時候「🎯 **最終景氣目標**」早已超出閾值，這是否代表你現在就要交易？**答案是：不一定！**
> 
> 真正的觸發扳機，是看您**「券商帳戶裡真實的資產現值%」**！
> - 若您券商裡真實的股票佔比，**仍然落在下表右側的安全範圍內**：請**強忍住不動**！這表示市場波動尚未失控，無視景氣微調目標，省出手續費與過度預判的失誤。
> - 若您券商裡真實的股票佔比，**已經「跌破」或「漲破」了下表右側的觸發閾值**：恭喜，現在正是收割或抄底的好時機！請立刻登入帳戶下單，將所有的資產一舉校正重新對齊至 **「🎯 最終景氣目標」** 即可！
>
> 🔥 **血色抄底 (Value Averaging) 特殊法則**：若大盤**突然崩盤重挫 >20%**，請無視一切以上規則，**立刻授權動用所有現金池與部份防禦債券，強力買入 VT+0050**！這就是為什麼我們要在平時保留大量現金的終極致勝關鍵。
""")

reb_data = {
    "資產類別": ["📈 股票", "🛡️ 債券", "⚜️ 黃金", "💵 現金池"],
    "基底配置 (生命週期基線)": [f"{b_stk:.1f}%", f"{b_bnd:.1f}%", f"{b_gld:.1f}%", f"{b_csh:.1f}%"],
    "因應景氣微調 (擇時)": [f"{s_pct - b_stk:+.1f}%", f"{b_pct - b_bnd:+.1f}%", f"{g_pct - b_gld:+.1f}%", f"{c_pct - b_csh:+.1f}%"],
    "🎯 最終景氣目標": [f"{s_pct:.1f}%", f"{b_pct:.1f}%", f"{g_pct:.1f}%", f"{c_pct:.1f}%"],
    "🛡️ 觸發動作閾值 (需動手執行標記)": [
        f"真實現況 < {max(0, b_stk-5):.1f}%  或  > {min(100, b_stk+5):.1f}%",
        f"真實現況 < {max(0, b_bnd-5):.1f}%  或  > {min(100, b_bnd+5):.1f}%",
        f"真實現況 < {max(0, b_gld-5):.1f}%  或  > {min(100, b_gld+5):.1f}%",
        f"生活準備金 (如過多則投入再平衡)"
    ]
}
st.table(pd.DataFrame(reb_data))

st.divider()
st.subheader("🚨 核心防護機制狀態")
msg_col1, msg_col2 = st.columns(2)

with msg_col1:
    if "Neutral" in current_regime:
        try:
            between_str = current_regime.split("介於：")[1].replace(")", "")
        except:
            between_str = "轉換交界"
        st.success(f"✅ **啟動 Neutral 模糊機制 (最重要)**：目前 CPI 穩健落在 2-3% 區間。雖然總經正處於 **「{between_str}」** 的過渡期，但系統策略強制為「不動」，以生命週期基線為主，這是避免多空雙巴的最強策略！")
    elif current_regime.startswith("Recession") and spread_input < 0:
        st.error("🚨 **啟動雙確認防護**：景氣落入衰退 + 殖利率確定倒掛 (-)，系統已重度防守！")
    else:
        st.info("ℹ️ **啟動動態調整**：不在模糊區，系統已依照四大階段象限，精準調整您的股權水位 (-20%~+10%)")

with msg_col2:
    if vix_input >= 30:
        st.error(f"🔥 **VIX 極度恐慌 ({vix_input:.1f})**：大盤處於極端恐慌！無論配置為何，這時候「嚴禁恐慌性殺盤」，可尋找買點。")
    elif 20 <= vix_input < 30:
        st.warning(f"⚠️ **VIX 恐慌加劇 ({vix_input:.1f})**：風險上升中，市場震盪加劇，請確保防禦資產部位就位。")
    elif 15 <= vix_input < 20:
        st.success(f"🟢 **VIX 情緒平穩 ({vix_input:.1f})**：市場情緒安穩，依循常規模型紀律配置即可。")
    else:
        st.info(f"🔵 **VIX 過度樂觀 ({vix_input:.1f})**：市場可能過度樂觀或極度平穩，需警惕技術性修正的風險。")
        
    if years_to_retire <= 10 and years_to_retire > 0:
        st.warning(f"⚠️ **滑動路徑 (Glide Path) 啟動**：您進入退休前 10 年轉換期，系統正每年自動將約 2% 股票轉入防禦資產。目前股票基線已滑落至 {b_stk:.1f}%。")
    elif years_to_retire <= 0:
        st.warning(f"⚠️ **進入提款期防禦**：資金已鎖入 60/30/10 最大化生存率模型，請確保預留 1~3 年現金。")
    else:
        st.info(f"✨ **累積期火力全開**：距離轉換期（滑動路徑）還有 {years_to_retire - 10} 年，安全期滿艙累積複利。")
