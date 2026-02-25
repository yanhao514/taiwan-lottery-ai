import os
import time
import shutil
import random
import re
import pandas as pd
from collections import Counter

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

class TaiwanLotteryMaster:
    def __init__(self):
        self.games = {
            "1": {"name": "大樂透", "type": "combo", "balls": 6, "path": "lotto649", "max_num": 49},
            "2": {"name": "威力彩", "type": "combo", "balls": 6, "path": "super_lotto638", "max_num": 38}, 
            "3": {"name": "今彩539", "type": "combo", "balls": 5, "path": "daily_cash", "max_num": 39},
            "4": {"name": "4星彩", "type": "position", "balls": 4, "path": "4_d", "max_num": 9},
            "5": {"name": "3星彩", "type": "position", "balls": 3, "path": "3_d", "max_num": 9}
        }

    def _format(self, nums):
        return ", ".join([f"{int(n):02d}" for n in sorted(nums)])

    def fetch_real_data(self, game_info, stop_issue=None, limit=50):
        url = f"https://www.taiwanlottery.com/lotto/result/{game_info['path']}"
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox") 
        chrome_options.add_argument("--disable-dev-shm-usage") 
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--log-level=3") 
        
        # 👇 針對 Streamlit 雲端環境新增：自動尋找 Chromium 的安裝路徑
        chrome_options.binary_location = shutil.which("chromium") 
        service = Service(shutil.which("chromedriver"))

        try:
            # 👇 這裡也要修改：加入 service 參數
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.get(url)
            time.sleep(3) 
            body_text = driver.find_element(By.TAG_NAME, 'body').text
            driver.quit()
            
            # ... (下面的歷史資料解析邏輯完全不用動) ...
            
            lines = body_text.split('\n')
            history_data = []
            current_issue = None
            current_draw = []
            
            for line in lines:
                line = line.strip()
                if not line: continue
                issue_match = re.search(r'(11\d{4,7})', line)
                if issue_match:
                    current_issue = issue_match.group(1)
                    
                    # 💡 智慧煞車系統：如果網頁上的期數等於我們資料庫最後一期，立刻停止抓取！
                    if stop_issue and current_issue == stop_issue:
                        break
                        
                    current_draw = [] 
                
                clean_line = re.sub(r'\d{2,3}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日', '', line)
                clean_line = re.sub(r'\d{2,4}[/.\-]\d{1,2}[/.\-]\d{1,2}', '', clean_line)
                clean_line = re.sub(r'\d{1,2}:\d{2}(:\d{2})?', '', clean_line)
                
                if current_issue:
                    numbers = re.findall(r'\b\d+\b', clean_line)
                    for p in numbers:
                        num = int(p)
                        if 0 <= num <= game_info["max_num"] and str(num) != current_issue:
                            current_draw.append(num)
                            if len(current_draw) == game_info["balls"]:
                                history_data.append([current_issue] + current_draw[:])
                                current_issue = None 
                                current_draw = []
                                break
                    if len(history_data) >= limit: break
            
            return history_data
            
        except Exception as e:
            try: driver.quit()
            except: pass
            return [] # 發生錯誤時回傳空陣列，保護既有資料庫不被汙染

    # ⭐️ 核心升級：整合讀取、比對與更新的「大管家」
    def update_and_get_data(self, game_info):
        game_name = game_info["name"]
        file_name = f"db_{game_name}.csv"
        stop_issue = None
        old_df = pd.DataFrame()
        
        # 1. 先查水表：看看本地有沒有資料庫
        if os.path.exists(file_name):
            old_df = pd.read_csv(file_name, encoding='utf-8-sig', dtype={'期數': str})
            if not old_df.empty:
                stop_issue = str(old_df.iloc[-1]['期數'])
                
        # 2. 出門抓資料：帶著 stop_issue 去網頁抓，遇到就停 (首次抓取預設抓 50 筆)
        new_data_list = self.fetch_real_data(game_info, stop_issue=stop_issue, limit=50)
        
        # 3. 處理結果：如果有抓到新資料，就跟舊資料合併存檔
        if new_data_list:
            columns = ['期數'] + [f'號碼{i+1}' for i in range(game_info["balls"])]
            new_df = pd.DataFrame(new_data_list, columns=columns)
            new_df = new_df.iloc[::-1].reset_index(drop=True) # 反轉順序
            
            if not old_df.empty:
                combined_df = pd.concat([old_df, new_df], ignore_index=True)
                combined_df = combined_df.drop_duplicates(subset=['期數'], keep='last', ignore_index=True)
            else:
                combined_df = new_df
                
            combined_df.to_csv(file_name, index=False, encoding='utf-8-sig')
            return combined_df, True # True 代表有抓到新資料
        else:
            return old_df, False # False 代表資料庫已是最新，不用更新

    def generate_ai_picks(self, df, game_info):
        if game_info["type"] != "combo" or df.empty: return None
            
        latest_row = df.iloc[-1]
        latest_issue = latest_row['期數']
        latest_draw = latest_row.drop('期數').values
        balls_needed = game_info["balls"]
        max_num = game_info["max_num"]
        all_possible_nums = set(range(1, max_num + 1))
        
        recent_20_df = df.tail(20).drop(columns=['期數'])
        recent_nums = recent_20_df.values.flatten()
        counts = Counter(recent_nums)
        hot_nums = [n for n, c in counts.most_common(balls_needed)]
        
        appeared_nums = set(counts.keys())
        unseen_nums = list(all_possible_nums - appeared_nums)
        cold_pool = unseen_nums.copy()
        
        if len(cold_pool) < balls_needed:
            least_common = counts.most_common()[:-balls_needed-1:-1]
            for n, c in least_common:
                if n not in cold_pool: cold_pool.append(n)
        
        cold_nums = random.sample(cold_pool, balls_needed) if len(cold_pool) >= balls_needed else cold_pool[:balls_needed]
        half_hot_count = balls_needed // 2
        half_cold_count = balls_needed - half_hot_count
        mixed_nums = hot_nums[:half_hot_count] + cold_nums[:half_cold_count]
        
        nums_df = df.drop(columns=['期數'])
        correlation_map = {}
        for i in range(len(nums_df) - 1):
            curr_draw = nums_df.iloc[i].values
            next_draw = nums_df.iloc[i+1].values
            for num in curr_draw:
                if num not in correlation_map: correlation_map[num] = []
                correlation_map[num].extend(next_draw)
                
        last_draw = nums_df.iloc[-1].values
        dragged_pool = []
        for num in last_draw:
            if num in correlation_map: dragged_pool.extend(correlation_map[num])
                
        dragged_counts = Counter(dragged_pool)
        dragged_nums = [n for n, c in dragged_counts.most_common(balls_needed)]
        for n in hot_nums:
            if len(dragged_nums) >= balls_needed: break
            if n not in dragged_nums: dragged_nums.append(n)
        
        return {
            "latest_issue": latest_issue,
            "latest_draw": self._format(latest_draw),
            "hot": self._format(hot_nums),
            "cold": self._format(cold_nums),
            "mixed": self._format(mixed_nums),
            "dragged": self._format(dragged_nums)
        }

    def get_positional_analysis(self, df, game_info):
        if game_info["type"] != "position" or df.empty: return None
        
        nums_df = df.tail(20).drop(columns=['期數'])
        positions = ["千位", "百位", "十位", "個位"] if game_info["balls"] == 4 else ["百位", "十位", "個位"]
        
        results = []
        for idx, col in enumerate(nums_df.columns):
            count = Counter(nums_df[col])
            hot = count.most_common(2) 
            hot_num = hot[0][0] if len(hot) > 0 else "-"
            hot_count = hot[0][1] if len(hot) > 0 else 0
            sec_num = hot[1][0] if len(hot) > 1 else "-"
            results.append({
                "position": positions[idx],
                "hot_num": hot_num,
                "hot_count": hot_count,
                "sec_num": sec_num
            })
        return results

    def run(self):
        pass

if __name__ == "__main__":
    app = TaiwanLotteryMaster()

    app.run()
