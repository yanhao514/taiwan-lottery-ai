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
        # ... (這裡放原本的 update_and_get_data 和 AI 預測邏輯) ...
        # 為了示範，我先把你的原代碼簡化成一行註解：
        st.info("👉 這裡填入你原本的爬蟲與分析程式碼")

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
