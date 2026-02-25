 import os
import time
import random
import re
import json
import shutil
import pandas as pd
import streamlit as st
import gspread
from collections import Counter
from google.oauth2.service_account import Credentials
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

    # 爬蟲核心 (已針對 Streamlit 雲端環境加入 shutil 修補)
    def fetch_real_data(self, game_info, stop_issue=None, limit=50):
        url = f"https://www.taiwanlottery.com/lotto/result/{game_info['path']}"
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--log-level=3") 
        
        chrome_options.binary_location = shutil.which("chromium") 
        service = Service(shutil.which("chromedriver"))

        try:
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.get(url)
            time.sleep(3) 
            body_text = driver.find_element(By.TAG_NAME, 'body').text
            driver.quit()
            
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
            return []

    # Google Sheets 連線工具
    def get_google_sheet(self, game_name):
        creds_dict = json.loads(st.secrets["google_credentials"])
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client.open("台彩大數據資料庫").worksheet(game_name)

    # 瞬間讀取雲端資料庫
    def load_data_from_sheet(self, game_info):
        try:
            sheet = self.get_google_sheet(game_info["name"])
            records = sheet.get_all_records()
            if records:
                df = pd.DataFrame(records)
                df['期數'] = df['期數'].astype(str)
                return df
            else:
                return pd.DataFrame()
        except Exception as e:
            return pd.DataFrame()

    # 手動觸發爬蟲，並寫入新資料
    def sync_latest_data(self, game_info, old_df):
        sheet = self.get_google_sheet(game_info["name"])
        stop_issue = str(old_df.iloc[-1]['期數']) if not old_df.empty else None
        
        new_data_list = self.fetch_real_data(game_info, stop_issue=stop_issue, limit=50)
        
        if new_data_list:
            columns = ['期數'] + [f'號碼{i+1}' for i in range(game_info["balls"])]
            new_df = pd.DataFrame(new_data_list, columns=columns)
            new_df = new_df.iloc[::-1].reset_index(drop=True)
            
            if old_df.empty:
                sheet.update([columns] + new_df.values.tolist())
                combined_df = new_df
            else:
                sheet.append_rows(new_df.values.tolist())
                combined_df = pd.concat([old_df, new_df], ignore_index=True)
                
            return combined_df, True
        else:
            return old_df, False

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
        
        # ⭐️ 全新功能：詳細拖牌命中率分析
    def get_dragged_analysis(self, df, game_info):
        if game_info["type"] != "combo" or df.empty or len(df) < 2: return None

        # 取得最新一期的開獎號碼，作為「拖牌」的基準
        latest_draw = df.iloc[-1].drop('期數').values
        nums_df = df.drop(columns=['期數'])

        # 建立字典來記錄：{基準號碼: [下一期開出的所有號碼]}
        correlation_map = {int(num): [] for num in latest_draw}
        history_counts = {int(num): 0 for num in latest_draw} # 記錄基準號碼在歷史上總共出現過幾次

        for i in range(len(nums_df) - 1):
            curr_draw = [int(n) for n in nums_df.iloc[i].values]
            next_draw = [int(n) for n in nums_df.iloc[i+1].values]
            
            for num in latest_draw:
                if int(num) in curr_draw:
                    history_counts[int(num)] += 1
                    correlation_map[int(num)].extend(next_draw)

        # 整理出每個號碼的 Top 3 拖牌機率
        analysis_result = {}
        for num in latest_draw:
            total_appear = history_counts[num]
            if total_appear > 0 and correlation_map[num]:
                counts = Counter(correlation_map[num])
                top_3 = counts.most_common(3) # 取出最常被拖出來的前三個號碼
                analysis_result[num] = {
                    "history_count": total_appear,
                    "top_dragged": top_3
                }
            else:
                analysis_result[num] = {"history_count": 0, "top_dragged": []}

        return analysis_result
        
        # ⭐️ 全新功能：AI 預測命中率回測 (時光倒流對答案)
    def calculate_prediction_accuracy(self, df, game_info):
        # 確保至少有 22 期以上的資料才能做足夠的回測
        if game_info["type"] != "combo" or len(df) < 22: 
            return None
            
        # 1. 切割資料：拿掉最新一期，用前面的歷史資料來模擬「開獎前」的狀態
        past_df = df.iloc[:-1].reset_index(drop=True)
        
        # 2. 拿出答案卷：實際開出的最新一期號碼
        actual_latest_row = df.iloc[-1]
        actual_issue = actual_latest_row['期數']
        actual_draw = set([int(n) for n in actual_latest_row.drop('期數').values])
        
        # 3. 呼叫 AI 產生當時的模擬預測
        mock_picks = self.generate_ai_picks(past_df, game_info)
        if not mock_picks:
            return None
            
        results = {"issue": actual_issue, "actual": actual_draw, "strategies": {}}
        
        # 4. 批改考卷：解析四大策略並比對命中數量
        strategies = [
            ("hot", "🔥 策略一【全熱門號】"),
            ("cold", "❄️ 策略二【全冷門號】"),
            ("mixed", "🌗 策略三【冷熱各半】"),
            ("dragged", "🧩 策略四【拖牌精選】")
        ]
        
        for key, name in strategies:
            # 將字串 "01, 05, 12" 轉回數字集合來比對
            pick_set = set([int(n) for n in mock_picks[key].split(', ')])
            hits = pick_set.intersection(actual_draw)
            results["strategies"][name] = {
                "picks": pick_set,
                "hits": hits,
                "hit_count": len(hits)
            }
            
        return results



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
