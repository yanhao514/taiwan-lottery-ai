import os, time, random, json
import pandas as pd
import streamlit as st
import gspread
import requests
import urllib3
from collections import Counter
from google.oauth2.service_account import Credentials
from datetime import datetime

# 停用 SSL 不安全連線警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class TaiwanLotteryMaster:
    def __init__(self):
        self.games = {
            "1": {"name": "大樂透", "type": "combo", "balls": 6, "special": 1, "path": "lotto649", "max_num": 49, "s_max": 49},
            "2": {"name": "威力彩", "type": "combo", "balls": 6, "special": 1, "path": "super_lotto638", "max_num": 38, "s_max": 8},
            "3": {"name": "今彩539", "type": "combo", "balls": 5, "special": 0, "path": "daily_cash", "max_num": 39},
            "4": {"name": "4星彩", "type": "position", "balls": 4, "special": 0, "path": "4_d", "max_num": 9},
            "5": {"name": "3星彩", "type": "position", "balls": 3, "special": 0, "path": "3_d", "max_num": 9}
        }

    def _format(self, nums):
        return ", ".join([f"{int(n):02d}" for n in sorted(nums)])

    def fetch_real_data(self, game_info, stop_issue=None, limit=50):
        # 對應台彩 API 的端點名稱
        api_paths = {
            "lotto649": "Lotto649Result",
            "super_lotto638": "SuperLotto638Result",
            "daily_cash": "DailyCashResult",
            "4_d": "4DResult",
            "3_d": "3DResult"
        }
        
        api_name = api_paths.get(game_info["path"])
        if not api_name: 
            return []

        url = f"https://api.taiwanlottery.com/TLCAPIWeB/Lottery/{api_name}"
        history_data = []
        
        # 取得現在的西元年份與月份
        now = datetime.now()
        year = now.year
        month = now.month
        
        try:
            # 往前找 6 個月，通常絕對夠湊滿 50 期資料
            for _ in range(36):
                month_str = f"{year}-{month:02d}"
                params = {
                    "month": month_str, # ⭐️ 核心修正：強制帶入月份參數 (例如 2024-02)
                    "pageNum": 1,
                    "pageSize": 200
                }
                
                res = requests.get(url, params=params, timeout=10, verify=False)
                data = res.json()
                
                records = []
                if "content" in data and data["content"]:
                    for key, val in data["content"].items():
                        if isinstance(val, list):
                            records = val
                            break
                            
                for rec in records:
                    issue = str(rec.get("period", ""))
                    if not issue: continue
                    
                    # 若遇到已經存在 Google Sheet 的最新期數，則提早結束所有抓取
                    if stop_issue and issue == stop_issue: 
                        return history_data
                    
                    nums_str = rec.get("drawNumberSize", [])
                    nums = [int(n) for n in nums_str]
                    
                    # 處理特別號/第二區
                    if game_info["special"] > 0:
                        special_num = rec.get("specialNumber") or rec.get("secondZoneNumber")
                        if special_num is not None:
                            nums.append(int(special_num))
                        
                    # 檢查號碼數量是否符合預期
                    target_length = game_info["balls"] + game_info["special"]
                    if len(nums) == target_length:
                        # 避免跨月抓到重複的期數
                        if not any(issue == existing[0] for existing in history_data):
                            history_data.append([issue] + nums)
                            
                    # 如果已經抓滿設定的筆數，就收工回傳
                    if len(history_data) >= limit:
                        return history_data
                
                # 準備抓取上個月的資料
                month -= 1
                if month == 0:
                    month = 12
                    year -= 1
                    
            return history_data
            
        except Exception as e:
            # st.error(f"抓取 {game_info['name']} 失敗: {e}")
            return history_data

    def get_google_sheet(self, game_name):
        creds_dict = json.loads(st.secrets["google_credentials"])
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client.open("台彩大數據資料庫").worksheet(game_name)

    def load_data_from_sheet(self, game_info):
        try:
            sheet = self.get_google_sheet(game_info["name"])
            records = sheet.get_all_records()
            if records:
                df = pd.DataFrame(records)
                df['期數'] = df['期數'].astype(str)
                return df
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    def sync_latest_data(self, game_info, old_df):
        sheet = self.get_google_sheet(game_info["name"])
        stop_issue = str(old_df.iloc[-1]['期數']) if not old_df.empty else None
        new_data_list = self.fetch_real_data(game_info, stop_issue=stop_issue, limit=50)
        
        if new_data_list:
            columns = ['期數'] + [f'號碼{i+1}' for i in range(game_info["balls"])]
            if game_info["special"] > 0: columns.append("特別號")
            new_df = pd.DataFrame(new_data_list, columns=columns)
            new_df = new_df.iloc[::-1].reset_index(drop=True)
            
            # 自動保護機制：如果發現雲端資料庫的欄位跟現在(多了特別號)不一樣，自動清空雲端並重寫
            try:
                existing = sheet.get_all_records()
                if existing and len(existing[0]) != len(columns):
                    sheet.clear()
                    old_df = pd.DataFrame()
            except: pass

            if old_df.empty:
                sheet.update([columns] + new_df.values.tolist())
                combined_df = new_df
            else:
                sheet.append_rows(new_df.values.tolist())
                combined_df = pd.concat([old_df, new_df], ignore_index=True)
            return combined_df, True
        return old_df, False

    def generate_ai_picks(self, df, game_info):
        if game_info["type"] != "combo" or df.empty: return None
        
        reg_cols = [f'號碼{i+1}' for i in range(game_info["balls"])]
        latest_row = df.iloc[-1]
        latest_issue = latest_row['期數']
        
        balls_needed = game_info["balls"]
        max_num = game_info["max_num"]
        
        # 一般號碼分析
        recent_20_df = df.tail(20)[reg_cols]
        recent_nums = recent_20_df.values.flatten()
        counts = Counter(recent_nums)
        hot_nums = [n for n, c in counts.most_common(balls_needed)]
        
        appeared_nums = set(counts.keys())
        all_possible_nums = set(range(1, max_num + 1))
        cold_pool = list(all_possible_nums - appeared_nums)
        if len(cold_pool) < balls_needed:
            least_common = counts.most_common()[:-balls_needed-1:-1]
            for n, c in least_common:
                if n not in cold_pool: cold_pool.append(n)
        cold_nums = random.sample(cold_pool, balls_needed) if len(cold_pool) >= balls_needed else cold_pool[:balls_needed]
        mixed_nums = hot_nums[:balls_needed//2] + cold_nums[:balls_needed - (balls_needed//2)]
        
        nums_df = df[reg_cols]
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

        # 特別號獨立分析
        s_hot_str = s_cold_str = s_mix_str = s_drag_str = ""
        if game_info["special"] > 0:
            s_history = df["特別號"].tail(20).values
            s_counts = Counter(s_history)
            s_hot = s_counts.most_common(1)[0][0]
            s_pool = set(range(1, game_info["s_max"] + 1))
            s_cold_list = list(s_pool - set(s_counts.keys()))
            s_cold = random.choice(s_cold_list) if s_cold_list else s_counts.most_common()[-1][0]
            s_mix = random.choice([s_hot, s_cold])
            
            s_hot_str = f" ➕ 特:{s_hot:02d}"
            s_cold_str = f" ➕ 特:{s_cold:02d}"
            s_mix_str = f" ➕ 特:{s_mix:02d}"
            s_drag_str = f" ➕ 特:{s_hot:02d}" 
        
        return {
            "latest_issue": latest_issue, 
            "hot": self._format(hot_nums) + s_hot_str,
            "cold": self._format(cold_nums) + s_cold_str,
            "mixed": self._format(mixed_nums) + s_mix_str, 
            "dragged": self._format(dragged_nums) + s_drag_str
        }

    def get_dragged_analysis(self, df, game_info):
        if game_info["type"] != "combo" or df.empty or len(df) < 2: return None
        reg_cols = [f'號碼{i+1}' for i in range(game_info["balls"])]
        latest_draw = df.iloc[-1][reg_cols].values
        nums_df = df[reg_cols]
        correlation_map = {int(num): [] for num in latest_draw}
        history_counts = {int(num): 0 for num in latest_draw} 
        for i in range(len(nums_df) - 1):
            curr_draw = [int(n) for n in nums_df.iloc[i].values]
            next_draw = [int(n) for n in nums_df.iloc[i+1].values]
            for num in latest_draw:
                if int(num) in curr_draw:
                    history_counts[int(num)] += 1
                    correlation_map[int(num)].extend(next_draw)
        analysis_result = {}
        for num in latest_draw:
            total_appear = history_counts[num]
            if total_appear > 0 and correlation_map[num]:
                counts = Counter(correlation_map[num])
                analysis_result[num] = {"history_count": total_appear, "top_dragged": counts.most_common(3)}
            else:
                analysis_result[num] = {"history_count": 0, "top_dragged": []}
        return analysis_result

    def calculate_prediction_accuracy(self, df, game_info):
        if game_info["type"] != "combo" or len(df) < 22: return None
        past_df = df.iloc[:-1].reset_index(drop=True)
        actual_latest_row = df.iloc[-1]
        actual_issue = actual_latest_row['期數']
        reg_cols = [f'號碼{i+1}' for i in range(game_info["balls"])]
        actual_draw = set([int(n) for n in actual_latest_row[reg_cols].values])
        
        mock_picks = self.generate_ai_picks(past_df, game_info)
        if not mock_picks: return None
        results = {"issue": actual_issue, "actual": actual_draw, "strategies": {}}
        strategies = [("hot", "🔥 策略一【全熱門號】"), ("cold", "❄️ 策略二【全冷門號】"), ("mixed", "🌗 策略三【冷熱各半】"), ("dragged", "🧩 策略四【拖牌精選】")]
        for key, name in strategies:
            pick_str = mock_picks[key].split(' ➕')[0] # 回測時先濾掉特別號字串
            pick_set = set([int(n) for n in pick_str.split(', ')])
            hits = pick_set.intersection(actual_draw)
            results["strategies"][name] = {"picks": pick_set, "hits": hits, "hit_count": len(hits)}
        return results

    def save_prediction_record(self, game_name, base_issue, picks):
        try:
            creds_dict = json.loads(st.secrets["google_credentials"])
            scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            client = gspread.authorize(creds)
            sheet = client.open("台彩大數據資料庫").worksheet("預測紀錄")
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row_data = [now, game_name, f"接續 {base_issue} 期", picks['hot'], picks['cold'], picks['mixed'], picks['dragged']]
            sheet.append_row(row_data)
            return True
        except Exception:
            return False

    def get_positional_analysis(self, df, game_info):
        if game_info["type"] != "position" or df.empty: return None
        nums_df = df.tail(20).drop(columns=['期數'])
        positions = ["千位", "百位", "十位", "個位"] if game_info["balls"] == 4 else ["百位", "十位", "個位"]
        results = []
        for idx, col in enumerate(nums_df.columns):
            count = Counter(nums_df[col])
            hot = count.most_common(2) 
            results.append({
                "position": positions[idx],
                "hot_num": hot[0][0] if len(hot) > 0 else "-",
                "hot_count": hot[0][1] if len(hot) > 0 else 0,
                "sec_num": hot[1][0] if len(hot) > 1 else "-"
            })
        return results

    def run(self): pass

if __name__ == "__main__":
    app = TaiwanLotteryMaster()
    app.run()



