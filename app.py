import streamlit as st
import pandas as pd
import random
import hashlib
import time
from datetime import datetime
from collections import Counter
from PIL import Image
import numpy as np
from lotto import TaiwanLotteryMaster

# ==========================================
# 🔮 偏方函式庫 (玄學演算法)
# ==========================================
def get_zodiac_luck(sign, game_info):
    today_str = datetime.now().strftime("%Y%m%d")
    seed_str = f"{today_str}_{sign}"
    seed_val = int(hashlib.sha256(seed_str.encode('utf-8')).hexdigest(), 16) % (10**8)
    random.seed(seed_val)
    lucky_nums = random.sample(range(1, game_info['max_num'] + 1), game_info['balls'])
    random.seed(time.time())
    return sorted(lucky_nums)

def divinatory_blocks(game_info):
    max_num = game_info['max_num']
    count = game_info['balls']
    candidates = []
    progress_text = st.empty()
    bar = st.progress(0)
    while len(candidates) < count:
        num = random.randint(1, max_num)
        if num in candidates: continue
        is_holy = random.choice([True, False])
        time.sleep(0.1)
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
    input_str = f"{name}_{int(time.time())}"
    hash_object = hashlib.sha256(input_str.encode())
    hex_dig = hash_object.hexdigest()
    max_num = game_info['max_num']
    count = game_info['balls']
    nums = set()
    idx = 0
    while len(nums) < count:
        chunk = hex_dig[idx:idx+2]
        val = int(chunk, 16)
        num = (val % max_num) + 1
        nums.add(num)
        idx += 2
        if idx >= len(hex_dig) - 2:
            hash_object = hashlib.sha256(hex_dig.encode())
            hex_dig = hash_object.hexdigest()
            idx = 0
    return sorted(list(nums))

def image_to_numbers(image_file, game_info):
    img = Image.open(image_file).resize((100, 100))
    img_array = np.array(img)
    seed_val = int(np.sum(img_array))
    random.seed(seed_val)
    lucky_nums = random.sample(range(1, game_info['max_num'] + 1), game_info['balls'])
    random.seed(time.time())
    return sorted(lucky_nums)

def iching_divination(game_info):
    lines = [random.choice([0, 1]) for _ in range(6)]
    hex_val = int("".join(map(str, lines)), 2)
    final_seed = hex_val + int(time.time())
    random.seed(final_seed)
    lucky_nums = random.sample(range(1, game_info['max_num'] + 1), game_info['balls'])
    random.seed(time.time())
    return lines, sorted(lucky_nums)

# ==========================================
# 🖥️ 網頁主程式 (UI 介面)
# ==========================================
st.set_page_config(page_title="台彩全能分析引擎", page_icon="🎰", layout="centered")
st.title("🎰 台彩全能大數據分析引擎")

engine = TaiwanLotteryMaster()
options = {f"{k} - {v['name']}": k for k, v in engine.games.items()}
selected_option = st.selectbox("📌 請選擇彩券種類：", list(options.keys()))

game_key = options[selected_option]
game_info = engine.games[game_key]

tab1, tab2 = st.tabs(["📊 理性數據分析", "🔮 感性玄學偏方"])

with tab1:
    st.markdown("### 🤖 AI 大數據運算")
    
    with st.spinner(f"正在載入【{game_info['name']}】雲端資料庫..."):
        full_db_df = engine.load_data_from_sheet(game_info)
        
    if full_db_df.empty:
        st.warning("⚠️ 雲端資料庫目前是空的，請點擊下方按鈕進行首次抓取。")
        
    if st.button("🔄 手動更新最新期數", type="primary", key="sync_btn"):
        with st.spinner("啟動爬蟲抓取最新開獎號碼中，請稍候..."):
            full_db_df, is_updated = engine.sync_latest_data(game_info, full_db_df)
            if is_updated:
                st.success("✅ 成功抓取新資料，已同步至 Google 試算表！")
            else:
                st.info("👍 目前雲端資料庫已經是最新狀態！")
                
    st.markdown("---")
    
    if not full_db_df.empty:
        if game_info["type"] == "combo":
            picks = engine.generate_ai_picks(full_db_df, game_info)
            pos_data = None
        else:
            picks = None
            pos_data = engine.get_positional_analysis(full_db_df, game_info)
            
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
                
            # ⭐️ 拖牌命中率分析
            st.markdown("---")
            st.subheader("🧩 最新期號碼「拖牌命中率」深度分析")
            dragged_stats = engine.get_dragged_analysis(full_db_df, game_info)
            if dragged_stats:
                st.write(f"以第 {latest_issue} 期開出的號碼為基準，歷史大數據顯示下一期最容易跟著開出的號碼：")
                with st.expander("📊 點擊展開各號碼拖牌機率表", expanded=True):
                    cols = st.columns(3)
                    col_idx = 0
                    for base_num, stats in dragged_stats.items():
                        total_appear = stats['history_count']
                        with cols[col_idx % 3]:
                            st.markdown(f"#### 🎯 號碼 【{base_num:02d}】")
                            st.caption(f"歷史共開出 {total_appear} 次")
                            if stats['top_dragged'] and total_appear > 0:
                                for dragged_num, count in stats['top_dragged']:
                                    hit_rate = (count / total_appear) * 100
                                    st.write(f"👉 拖出 **{dragged_num:02d}** ({count}次, {hit_rate:.1f}%)")
                            else:
                                st.write("尚無足夠歷史數據")
                            st.divider()
                        col_idx += 1
            
            # ⭐️ 回測分析
            st.markdown("---")
            st.subheader("🏆 AI 歷史準確度回測 (以最新一期為例)")
            with st.spinner("正在進行時光倒流回測..."):
                accuracy_data = engine.calculate_prediction_accuracy(full_db_df, game_info)
            if accuracy_data:
                st.write(f"假設我們在第 **{accuracy_data['issue']}** 期開獎前使用本系統，AI 當時的預測與實際命中表現如下：")
                actual_str = engine._format(accuracy_data['actual'])
                st.info(f"🎯 **該期實際開出號碼： {actual_str}**")
                cols = st.columns(2)
                col_idx = 0
                for strat_name, data in accuracy_data['strategies'].items():
                    with cols[col_idx % 2]:
                        picks_str = engine._format(data['picks'])
                        hits_str = engine._format(data['hits']) if data['hit_count'] > 0 else "無"
                        if data['hit_count'] >= 3:
                            st.success(f"**{strat_name}**\n\n👉 預測：{picks_str}\n\n🎯 命中 ({data['hit_count']} 顆)：**{hits_str}**")
                        elif data['hit_count'] > 0:
                            st.warning(f"**{strat_name}**\n\n👉 預測：{picks_str}\n\n🎯 命中 ({data['hit_count']} 顆)：**{hits_str}**")
                        else:
                            st.error(f"**{strat_name}**\n\n👉 預測：{picks_str}\n\n🎯 命中 (0 顆)：無")
                    col_idx += 1
            else:
                st.write("歷史數據不足，無法進行回測分析。")

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
        
        st.markdown("---")
        st.subheader(f"📈 【{game_info['name']}】號碼冷熱頻率統計圖 (累積 {len(full_db_df)} 期)")
        nums_df = full_db_df.drop(columns=['期數'])
        all_nums = nums_df.values.flatten()
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
    
    with st.expander("🔯 本日星座幸運靈數"):
        zodiacs = ["♈ 牡羊", "♉ 金牛", "♊ 雙子", "♋ 巨蟹", "♌ 獅子", "♍ 處女", 
                   "♎ 天秤", "♏ 天蠍", "♐ 射手", "♑ 魔羯", "♒ 水瓶", "♓ 雙魚"]
        my_sign = st.selectbox("你的星座是？", zodiacs)
        if st.button("✨ 召喚星象之力"):
            luck_nums = get_zodiac_luck(my_sign, game_info)
            st.success(f"🌌 {my_sign} 今天的宇宙共振號碼：")
            st.header(f"{', '.join(map(str, luck_nums))}")
            
    with st.expander("🙏 數位擲筊求明牌"):
        if st.button("🥠 開始求籤 (需擲出聖筊)"):
            with st.spinner("🙏 弟子誠心求號，請神明指示..."):
                god_nums = divinatory_blocks(game_info)
            st.success(f"🎉 神明賜給你的號碼：")
            st.header(f"{', '.join(map(str, god_nums))}")
            st.balloons()
            
    with st.expander("🔢 姓名/靈感測字"):
        user_input = st.text_input("輸入名字或靈感：", placeholder="例如：王小明...")
        if st.button("💫 解析靈動數") and user_input:
            name_nums = name_numerology(user_input, game_info)
            st.info(f"🔠 來自「{user_input}」的靈動解析結果：")
            st.header(f"{', '.join(map(str, name_nums))}")

    with st.expander("📸 靈感顯影 (上傳照片)"):
        uploaded_file = st.file_uploader("選擇一張照片...", type=["jpg", "png", "jpeg"])
        if uploaded_file is not None:
            st.image(uploaded_file, caption='你的靈感來源', width=200)
            if st.button("🧩 解析圖片密碼"):
                with st.spinner("正在分析像素能量..."):
                    img_nums = image_to_numbers(uploaded_file, game_info)
                    time.sleep(1)
                st.success("🖼️ 這張照片隱藏的號碼是：")
                st.header(f"{', '.join(map(str, img_nums))}")

    with st.expander("🔮 易經六十四卦靈籤"):
        if st.button("🪙 誠心起卦"):
            lines, iching_nums = iching_divination(game_info)
            st.info("📜 你的卦象：")
            col_hex, col_res = st.columns([1, 2])
            with col_hex:
                for line in reversed(lines):
                    if line == 1:
                        st.markdown("___🟥🟥🟥___ (陽)")
                    else:
                        st.markdown("___🟦&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;🟦___ (陰)")
            with col_res:
                st.success("🧘 卦象靈數：")
                st.header(f"{', '.join(map(str, iching_nums))}")

    with st.expander("📈 股市代碼共振"):
        stock_code = st.text_input("輸入股票代碼：", placeholder="例如：2330")
        if st.button("💹 運算財運號碼") and stock_code:
            today_str = datetime.now().strftime("%Y%m%d")
            seed_str = f"{stock_code}_{today_str}"
            seed_val = int(hashlib.sha256(seed_str.encode('utf-8')).hexdigest(), 16) % (10**8)
            random.seed(seed_val)
            stock_nums = random.sample(range(1, game_info['max_num'] + 1), game_info['balls'])
            random.seed(time.time())
            st.success(f"💰 來自代碼【{stock_code}】的財氣共振號碼：")
            st.header(f"{', '.join(map(str, sorted(stock_nums)))}")

    with st.expander("⛩️ 日本神社御神籤"):
        if st.button("🎋 搖籤筒"):
            with st.spinner("搖動籤筒中..."):
                time.sleep(1.5)
                fortunes = ["🌸 大吉", "✨ 中吉", "🍀 小吉", "🍁 末吉"]
                my_fortune = random.choice(fortunes)
                omikuji_nums = random.sample(range(1, game_info['max_num'] + 1), game_info['balls'])
            col_fortune, col_num = st.columns([1, 2])
            with col_fortune:
                st.error(f"### {my_fortune}")
            with col_num:
                st.success("⛩️ 神明賜予的幸運號碼：")
                st.header(f"{', '.join(map(str, sorted(omikuji_nums)))}")

    with st.expander("📦 萬物條碼 / 貨號解碼器"):
        barcode_input = st.text_input("輸入商品條碼或 SKU 貨號：", placeholder="例如：4710123456789")
        if st.button("🔍 掃描解碼") and barcode_input:
            with st.spinner("嗶！正在解析商品編碼..."):
                time.sleep(0.5)
                barcode_seed = sum([ord(c) for c in barcode_input]) + int(time.time())
                random.seed(barcode_seed)
                barcode_nums = random.sample(range(1, game_info['max_num'] + 1), game_info['balls'])
                random.seed(time.time())
            st.success(f"🏷️ 條碼【{barcode_input}】解析完成：")
            st.header(f"{', '.join(map(str, sorted(barcode_nums)))}")
