import streamlit as st
import pandas as pd
import random
import hashlib
import time
from datetime import datetime
from lotto import TaiwanLotteryMaster  # 假設你的爬蟲主程式檔名是 lotto.py

# --- 偏方函式庫 (可以直接寫在 app.py 裡面) ---

def get_zodiac_luck(sign, game_info):
    """星座靈數：用 (日期 + 星座) 當作亂數種子"""
    today_str = datetime.now().strftime("%Y%m%d")
    seed_str = f"{today_str}_{sign}"
    
    # 將字串轉為數字種子
    seed_val = int(hashlib.sha256(seed_str.encode('utf-8')).hexdigest(), 16) % (10**8)
    random.seed(seed_val)
    
    max_num = game_info['max_num']
    count = game_info['balls']
    
    # 產生不重複號碼
    lucky_nums = random.sample(range(1, max_num + 1), count)
    
    # 記得重置種子，以免影響後續的其他隨機功能
    random.seed(time.time()) 
    
    return sorted(lucky_nums)

def divinatory_blocks(game_info):
    """擲筊求號：模擬求籤過程"""
    max_num = game_info['max_num']
    count = game_info['balls']
    candidates = []
    
    progress_text = st.empty()
    bar = st.progress(0)
    
    # 簡單模擬：每選一個號碼，都要擲出聖筊才算數
    while len(candidates) < count:
        num = random.randint(1, max_num)
        if num in candidates: continue
        
        # 擲筊邏輯：0=笑杯, 1=沒杯, 2=聖筊 (機率各 1/3，或可自訂)
        # 為了體驗好一點，我們設定 50% 機率聖筊
        is_holy = random.choice([True, False]) 
        
        time.sleep(0.1) # 增加儀式感
        if is_holy:
            candidates.append(num)
            bar.progress(len(candidates) / count)
            progress_text.text(f"🥠 擲出聖筊！神明賜號：{num}")
        else:
            progress_text.text(f"👋 {num} 號沒杯/笑杯，重求...")
            
    bar.empty()
    progress_text.empty()
    return sorted(candidates)

def name_numerology(name, game_info):
    """姓名靈動：將文字轉為數字"""
    # 結合當下時間，讓同一個名字在不同時間算出的結果不同 (若要固定可拿掉 time)
    input_str = f"{name}_{int(time.time())}"
    
    # 使用 SHA-256 雜湊
    hash_object = hashlib.sha256(input_str.encode())
    hex_dig = hash_object.hexdigest()
    
    # 將雜湊字串切段轉成數字
    max_num = game_info['max_num']
    count = game_info['balls']
    nums = set()
    
    idx = 0
    while len(nums) < count:
        # 每 2 個 16 進位字元轉成一個整數
        chunk = hex_dig[idx:idx+2]
        val = int(chunk, 16)
        # 對最大號碼取餘數 + 1
        num = (val % max_num) + 1
        nums.add(num)
        idx += 2
        if idx >= len(hex_dig) - 2: # 避免超出範圍，重新雜湊
            hash_object = hashlib.sha256(hex_dig.encode())
            hex_dig = hash_object.hexdigest()
            idx = 0
            
    return sorted(list(nums))

# --- 主程式介面 ---

st.set_page_config(page_title="台彩全能分析引擎", page_icon="🎰", layout="centered")

st.title("🎰 台彩全能大數據分析引擎")

# 初始化後端
engine = TaiwanLotteryMaster()
options = {f"{k} - {v['name']}": k for k, v in engine.games.items()}
selected_option = st.selectbox("📌 請選擇彩券種類：", list(options.keys()))

game_key = options[selected_option]
game_info = engine.games[game_key]

# ⭐️ 使用 Tabs 分頁將科學與玄學分開
tab1, tab2 = st.tabs(["📊 理性數據分析", "🔮 感性玄學偏方"])

with tab1:
    st.markdown("### 🤖 AI 大數據運算")
    if st.button("🚀 開始科學分析", type="primary", key="science_btn"):
        
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
        # 大數據冷熱頻率統計圖表區塊
        # ==========================================
        st.markdown("---")
        st.subheader(f"📈 【{game_info['name']}】號碼冷熱頻率統計圖 (累積 {len(full_db_df)} 期)")
        
        nums_df = full_db_df.drop(columns=['期數'])
        all_nums = nums_df.values.flatten()
        from collections import Counter # 確保有載入 Counter
        freq_counts = Counter(all_nums)
        
        if game_info["type"] == "combo":
            chart_df = pd.DataFrame({
                "號碼": [f"{i:02d}" for i in range(1, game_info['max_num'] + 1)],
                "開出次數": [freq_counts.get(i, 0) for i in range(1, game_info['max_num'] + 1)]
            }).set_index("號碼")
            st.bar_chart(chart_df, color="#ff4b4b", height=400)
        else:
            chart_df = pd.DataFrame({
                "數字": [str(i) for i in range(10)],
                "開出次數": [freq_counts.get(i, 0) for i in range(10)]
            }).set_index("數字")
            st.bar_chart(chart_df, color="#0068c9", height=400)
            
        st.markdown("---")
        st.subheader("📁 歷史開獎資料庫預覽")
        st.dataframe(full_db_df.tail(20).iloc[::-1], width='stretch')

with tab2:
    st.markdown("### ⚡️ 寧可信其有，偏方大集合")
    
    # 偏方 1: 星座
    with st.expander("🔯 本日星座幸運靈數"):
        zodiacs = ["♈ 牡羊", "♉ 金牛", "♊ 雙子", "♋ 巨蟹", "♌ 獅子", "♍ 處女", 
                   "♎ 天秤", "♏ 天蠍", "♐ 射手", "♑ 魔羯", "♒ 水瓶", "♓ 雙魚"]
        my_sign = st.selectbox("你的星座是？", zodiacs)
        if st.button("✨ 召喚星象之力"):
            luck_nums = get_zodiac_luck(my_sign, game_info)
            st.success(f"🌌 {my_sign} 今天 ({datetime.now().strftime('%Y-%m-%d')}) 的宇宙共振號碼：")
            st.header(f"{', '.join(map(str, luck_nums))}")
            st.caption("此號碼根據日期與星座種子演算，今日固定不變。")

    # 偏方 2: 擲筊
    with st.expander("🙏 數位擲筊求明牌"):
        st.write("誠心默念你的願望，AI 將為你模擬擲筊儀式...")
        if st.button("🥠 開始求籤 (需擲出聖筊)"):
            with st.spinner("🙏 弟子誠心求號，請神明指示..."):
                god_nums = divinatory_blocks(game_info)
            st.success(f"🎉 神明賜給你的號碼：")
            st.header(f"{', '.join(map(str, god_nums))}")
            st.balloons() # 放個氣球慶祝一下

    # 偏方 3: 姓名/靈感
    with st.expander("🔢 姓名/靈感測字"):
        user_input = st.text_input("輸入你的名字、或當下想到的一句話：", placeholder="例如：王小明、今天天氣真好...")
        if st.button("💫 解析靈動數") and user_input:
            name_nums = name_numerology(user_input, game_info)
            st.info(f"🔠 來自「{user_input}」的靈動解析結果：")
            st.header(f"{', '.join(map(str, name_nums))}")

st.markdown("---")
st.caption("⚠️ 偏方純屬娛樂，投資請量力而為。")

