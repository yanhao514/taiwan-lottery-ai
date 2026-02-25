import streamlit as st
import pandas as pd
from collections import Counter
from lotto import TaiwanLotteryMaster

st.set_page_config(page_title="台彩全能分析引擎", page_icon="🎰", layout="centered")

st.title("🎰 台彩全能大數據分析引擎")
st.markdown("利用 Selenium 自動爬蟲與 AI 大數據拖牌演算法，為您精準預測下一期號碼。")

engine = TaiwanLotteryMaster()
options = {f"{k} - {v['name']}": k for k, v in engine.games.items()}
selected_option = st.selectbox("📌 請選擇要分析的彩券種類：", list(options.keys()))

if st.button("🚀 開始自動抓取與分析", type="primary"):
    game_key = options[selected_option]
    game_info = engine.games[game_key]
    
    with st.spinner(f"正在檢查【{game_info['name']}】資料庫並同步最新數據..."):
        full_db_df, is_updated = engine.update_and_get_data(game_info)
        
        if full_db_df.empty:
            st.error("❌ 找不到歷史資料，且網路抓取失敗，請確認網路連線。")
            st.stop()
            
        if game_info["type"] == "combo":
            picks = engine.generate_ai_picks(full_db_df, game_info)
            pos_data = None
        else:
            picks = None
            pos_data = engine.get_positional_analysis(full_db_df, game_info)
        
    if is_updated:
        st.success("✅ 成功抓取最新開獎數據並更新資料庫！")
    else:
        st.info("👍 本地資料庫已是最新狀態，直接載入歷史數據進行分析！")
        
    st.markdown("---")
    
    latest_row = full_db_df.iloc[-1]
    latest_issue = latest_row['期數']
    latest_draw = latest_row.drop('期數').values
    formatted_draw = ", ".join([str(int(n)) for n in latest_draw]) 
    
    st.subheader(f"📊 基準資料：最新開獎 (第 {latest_issue} 期)")
    st.info(f"👉 **開出號碼： {formatted_draw}**")
    
    if picks:
        st.subheader("🎯 AI 智能實戰選號推薦")
        col1, col2 = st.columns(2)
        with col1:
            st.error(f"🔥 **策略一【全熱門號】**\n\n{picks['hot']}")
            st.caption("近20期最常開出")
            st.warning(f"🌗 **策略三【冷熱各半】**\n\n{picks['mixed']}")
            st.caption("結合策略一與策略二")
        with col2:
            st.info(f"❄️ **策略二【全冷門號】**\n\n{picks['cold']}")
            st.caption("近20期極少開出")
            st.success(f"🧩 **策略四【拖牌精選】**\n\n{picks['dragged']}")
            st.caption("根據最新期歷史軌跡拖出")
            
        st.markdown("### 📄 匯出實戰畫單報表")
        report_text = f"""=================================
🎰 {game_info['name']} - AI 智能實戰選號報表
=================================
📌 基準資料：最新開獎 (第 {latest_issue} 期)
👉 開出號碼： {formatted_draw}

🎯 AI 推薦四大策略：
🔥 策略一【全熱門號】: {picks['hot']}
❄️ 策略二【全冷門號】: {picks['cold']}
🌗 策略三【冷熱各半】: {picks['mixed']}
🧩 策略四【拖牌精選】: {picks['dragged']}
================================="""

        st.download_button(
            label="📥 下載 TXT 畫單報表",
            data=report_text,
            file_name=f"{game_info['name']}_AI預測_{latest_issue}期.txt",
            mime="text/plain",
            type="primary"
        )
            
    elif pos_data:
        st.subheader("🎯 位置熱度分析 (近 20 期大數據)")
        cols = st.columns(len(pos_data))
        for i, pos in enumerate(pos_data):
            with cols[i]:
                st.metric(label=f"📍 {pos['position']} 最熱門", 
                          value=f"{pos['hot_num']}", 
                          delta=f"近期開出 {pos['hot_count']} 次", 
                          delta_color="normal")
                st.caption(f"次熱門數字: **{pos['sec_num']}**")
    
    # ==========================================
    # ⭐️ 新增：大數據冷熱頻率統計圖表區塊
    # ==========================================
    st.markdown("---")
    st.subheader(f"📈 【{game_info['name']}】號碼冷熱頻率統計圖 (累積 {len(full_db_df)} 期)")
    
    # 將所有開出的號碼攤平，計算出現次數
    nums_df = full_db_df.drop(columns=['期數'])
    all_nums = nums_df.values.flatten()
    freq_counts = Counter(all_nums)
    
    if game_info["type"] == "combo":
        # 樂透型：產生 1 到 max_num 的 DataFrame
        chart_df = pd.DataFrame({
            "號碼": [f"{i:02d}" for i in range(1, game_info['max_num'] + 1)],
            "開出次數": [freq_counts.get(i, 0) for i in range(1, game_info['max_num'] + 1)]
        }).set_index("號碼")
        
        # 使用紅色的長條圖，高度設為 400，讓差異更明顯
        st.bar_chart(chart_df, color="#ff4b4b", height=400)
    else:
        # 星彩型：產生 0 到 9 的 DataFrame
        chart_df = pd.DataFrame({
            "數字": [str(i) for i in range(10)],
            "開出次數": [freq_counts.get(i, 0) for i in range(10)]
        }).set_index("數字")
        
        # 使用藍色的長條圖
        st.bar_chart(chart_df, color="#0068c9", height=400)
        
    # ==========================================

    st.markdown("---")
    st.subheader("📁 歷史開獎資料庫預覽")
    st.dataframe(full_db_df.tail(20).iloc[::-1], width='stretch')