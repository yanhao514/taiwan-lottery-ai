import os, time, random, json
import pandas as pd
import streamlit as st
import json
import gspread
import requests
import urllib3
from collections import Counter
from google.oauth2.service_account import Credentials
from datetime import datetime

# 停用 SSL 不安全連線警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ⭐️ 建立快取連線 (放在 class 外面)
# 這個裝飾器會讓 Streamlit 記住連線，避免重複登入消耗 Google API 額度
@st.cache_resource
def get_google_db():
    creds_dict = json.loads(st.secrets["google_credentials"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open("台彩大數據資料庫")

class TaiwanLotteryMaster:
    def __init__(self):
        # ⭐️ 請完整複製這一段，確保 6 種遊戲都有自己專屬的 draw_balls 設定！
        self.games = {
            "1": {"name": "大樂透", "type": "combo", "balls": 6, "draw_balls": 6, "special": 1, "path": "lotto649", "max_num": 49, "s_max": 49},
            "2": {"name": "威力彩", "type": "combo", "balls": 6, "draw_balls": 6, "special": 1, "path": "super_lotto638", "max_num": 38, "s_max": 8},
            "3": {"name": "今彩539", "type": "combo", "balls": 5, "draw_balls": 5, "special": 0, "path": "daily_cash", "max_num": 39},
            "4": {"name": "4星彩", "type": "position", "balls": 4, "draw_balls": 4, "special": 0, "path": "4_d", "max_num": 9},
            "5": {"name": "3星彩", "type": "position", "balls": 3, "draw_balls": 3, "special": 0, "path": "3_d", "max_num": 9},
            "6": {"name": "賓果賓果", "type": "combo", "balls": 10, "draw_balls": 20, "special": 1, "path": "bingo", "max_num": 80, "s_max": 80}
        }

    def _format(self, nums):
        return ", ".join([f"{int(n):02d}" for n in sorted(nums)])

    def fetch_real_data(self, game_info, stop_issue=None, limit=200):
        # ⭐️ 修正 1：539 的 API 端點名稱改為 Daily539Result
        api_paths = {
            "lotto649": "Lotto649Result",
            "super_lotto638": "SuperLotto638Result",
            "daily_cash": "Daily539Result", 
            "4_d": "4DResult",
            "3_d": "3DResult"
        }
        
        api_name = api_paths.get(game_info["path"])
        if not api_name: 
            return []

        url = f"https://api.taiwanlottery.com/TLCAPIWeB/Lottery/{api_name}"
        history_data = []
        
        now = datetime.now()
        year = now.year
        month = now.month
        
        try:
            for _ in range(36):
                month_str = f"{year}-{month:02d}"
                params = {
                    "month": month_str,
                    "pageNum": 1,
                    "pageSize": 100
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
                    
                    if stop_issue and issue == stop_issue: 
                        return history_data
                    
                    # ⭐️ 修正 2：彈性抓取號碼。先找大小順序，找不到就找落球順序
                    nums_str = rec.get("drawNumberSize")
                    if not nums_str:  # 針對 3星彩、4星彩
                        nums_str = rec.get("drawNumberAppear", [])
                        
                    if not nums_str:
                        continue
                        
                    nums = [int(n) for n in nums_str]
                    
                    if game_info["special"] > 0:
                        special_num = rec.get("specialNumber") or rec.get("secondZoneNumber")
                        if special_num is not None:
                            nums.append(int(special_num))
                        
                    target_length = game_info["balls"] + game_info["special"]
                    if len(nums) == target_length:
                        if not any(issue == existing[0] for existing in history_data):
                            history_data.append([issue] + nums)
                            
                    if len(history_data) >= limit:
                        return history_data
                
                month -= 1
                if month == 0:
                    month = 12
                    year -= 1
                    
            return history_data
            
        except Exception as e:
            return history_data

   def get_google_sheet(self, sheet_name):
        # ⭐️ 直接呼叫快取的資料庫，不再每次重新認證
        db = get_google_db()
        
        worksheets = [ws.title for ws in db.worksheets()]
        if sheet_name not in worksheets:
            db.add_worksheet(title=sheet_name, rows="1000", cols="30")
            
        return db.worksheet(sheet_name)

    def auto_save_prediction(self, game_name, base_issue, picks):
        """自動在背景將推薦號碼存入雲端，並嚴格避免重複儲存"""
        try:
            sheet = self.get_google_sheet("預測紀錄")
            # 改用 get_all_values() 拿原始陣列，比對速度更快且不會因為標題名稱錯誤而當機
            all_values = sheet.get_all_values()
            
            # ⭐️ 如果是全新空表，建立標題列 (新增了第八個欄位：到期)
            if not all_values:
                headers = ["時間", "遊戲", "基準期數", "熱門", "冷門", "綜合", "拖牌", "到期"]
                sheet.append_row(headers)
                all_values = [headers]
            else:
                headers = all_values[0]
            
            # 找出對應欄位的索引值
            if "遊戲" in headers and "基準期數" in headers:
                game_idx = headers.index("遊戲")
                issue_idx = headers.index("基準期數")
                
                # ⭐️ 嚴格防重複比對：略過第一行標題，逐行檢查
                for row in all_values[1:]:
                    if len(row) > max(game_idx, issue_idx):
                        # 把頭尾空白去掉，全部轉成字串，避免 Google Sheet 數字格式搞鬼
                        is_same_game = str(row[game_idx]).strip() == str(game_name).strip()
                        is_same_issue = str(row[issue_idx]).strip() == str(base_issue).strip()
                        
                        if is_same_game and is_same_issue:
                            return "exists" # 已經存過了，直接安全撤退！
                            
            # 確認沒存過，寫入新紀錄 (⭐️ 陣列最後新增了 picks.get('overdue', ''))
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row_data = [
                now, 
                game_name, 
                str(base_issue), 
                picks['hot'], 
                picks['cold'], 
                picks['mixed'], 
                picks['dragged'], 
                picks.get('overdue', '') # 確保即使舊資料沒有 overdue 也不會報錯
            ]
            sheet.append_row(row_data)
            return True
            
        except Exception as e:
            return False

    def calculate_accuracy_from_cloud(self, df, game_info):
        if df.empty or len(df) < 2: return None
        try:
            sheet = self.get_google_sheet("預測紀錄")
            records = sheet.get_all_records()
            if not records: return None
            
            pred_df = pd.DataFrame(records)
            if '遊戲' not in pred_df.columns: return None
            pred_df = pred_df[pred_df['遊戲'] == game_info['name']]
            if pred_df.empty: return None
            
            df['期數'] = df['期數'].astype(str)
            actual_issues = df['期數'].tolist()
            
            for idx in range(len(pred_df)-1, -1, -1):
                row = pred_df.iloc[idx]
                base_issue = str(row.get('基準期數', ''))
                
                if base_issue in actual_issues:
                    base_idx = actual_issues.index(base_issue)
                    if base_idx + 1 < len(actual_issues): 
                        actual_draw_row = df.iloc[base_idx + 1]
                        target_issue = actual_draw_row['期數']
                        
                        reg_cols = [f'號碼{i+1}' for i in range(game_info["draw_balls"])]
                        actual_draw = set([int(n) for n in actual_draw_row[reg_cols].values])
                        actual_special = int(actual_draw_row["特別號"]) if game_info["special"] > 0 and "特別號" in actual_draw_row else None
                        
                        results = {"issue": target_issue, "base_issue": base_issue, "actual": actual_draw, "actual_special": actual_special, "strategies": {}}
                        
                        # ⭐️ 雲端驗證加入「到期補漏」策略
                        strategies = [("hot", "熱門", "🔥 策略一【全熱門號】"), 
                                      ("cold", "冷門", "❄️ 策略二【全冷門號】"), 
                                      ("mixed", "綜合", "🌗 策略三【冷熱各半】"), 
                                      ("dragged", "拖牌", "🧩 策略四【拖牌精選】"),
                                      ("overdue", "到期", "⏳ 策略五【到期補漏】")]
                        
                        for key, col_name, strat_name in strategies:
                            raw_pick_str = str(row.get(col_name, ""))
                            if not raw_pick_str: continue # 如果舊資料沒有「到期」欄位就略過
                            
                            parts = raw_pick_str.split(' ➕ 特:')
                            pick_str = parts[0]
                            pick_special = int(parts[1]) if len(parts) > 1 else None
                            
                            pick_set = set([int(n) for n in pick_str.split(', ') if n.isdigit()])
                            hits = pick_set.intersection(actual_draw)
                            special_hit = False
                            if game_info["special"] > 0 and pick_special is not None and actual_special is not None:
                                special_hit = (pick_special == actual_special)
                                
                            prize = self.get_prize_amount(game_info["name"], len(hits), special_hit)
                            
                            results["strategies"][strat_name] = {
                                "picks": pick_set, 
                                "pick_special": pick_special,
                                "hits": hits, 
                                "hit_count": len(hits),
                                "special_hit": special_hit,
                                "prize": prize,
                                "raw_pick_str": raw_pick_str
                            }
                        return results 
            return None
        except Exception as e:
            return None
            
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
        
        # ⭐️ 關鍵在這裡！把原本的 limit=50 改成 limit=200
        new_data_list = self.fetch_real_data(game_info, stop_issue=stop_issue, limit=200)
        
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

    def generate_ai_picks(self, df, game_info, window=20):
        if game_info["type"] != "combo" or df.empty: return None
        reg_cols = [f'號碼{i+1}' for i in range(game_info["draw_balls"])]
        latest_row = df.iloc[-1]
        latest_issue = latest_row['期數']
        balls_needed = game_info["balls"]
        max_num = game_info["max_num"]
        
        # ⭐️ 加入分析區間 (window) 控制
        recent_df = df.tail(window)[reg_cols]
        recent_nums = recent_df.values.flatten()
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
        
        # 拖牌分析
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

        # ⭐️ 新增：到期策略 (尋找連續最久未出現的號碼)
        last_seen = {n: 9999 for n in range(1, max_num + 1)}
        for idx, row in enumerate(df.iloc[::-1].iterrows()):
            draw_nums = row[1][reg_cols].values
            for num in draw_nums:
                if last_seen[int(num)] == 9999:
                    last_seen[int(num)] = idx
        overdue_pool = sorted(last_seen.keys(), key=lambda x: last_seen[x], reverse=True)
        overdue_nums = overdue_pool[:balls_needed]

        # 特別號處理
        s_hot_str = s_cold_str = s_mix_str = s_drag_str = s_overdue_str = ""
        if game_info["special"] > 0:
            s_history = df["特別號"].tail(window).values
            s_counts = Counter(s_history)
            s_hot = s_counts.most_common(1)[0][0]
            s_pool = set(range(1, game_info["s_max"] + 1))
            s_cold_list = list(s_pool - set(s_counts.keys()))
            s_cold = random.choice(s_cold_list) if s_cold_list else s_counts.most_common()[-1][0]
            s_mix = random.choice([s_hot, s_cold])
            
            # 尋找最久未開出的特別號
            s_last_seen = {n: 9999 for n in range(1, game_info["s_max"] + 1)}
            for idx, val in enumerate(df["特別號"].iloc[::-1]):
                if s_last_seen[int(val)] == 9999:
                    s_last_seen[int(val)] = idx
            s_overdue = sorted(s_last_seen.keys(), key=lambda x: s_last_seen[x], reverse=True)[0]
            
            s_hot_str = f" ➕ 特:{s_hot:02d}"
            s_cold_str = f" ➕ 特:{s_cold:02d}"
            s_mix_str = f" ➕ 特:{s_mix:02d}"
            s_drag_str = f" ➕ 特:{s_hot:02d}" 
            s_overdue_str = f" ➕ 特:{s_overdue:02d}" 
        
        return {
            "latest_issue": latest_issue, 
            "hot": self._format(hot_nums) + s_hot_str,
            "cold": self._format(cold_nums) + s_cold_str,
            "mixed": self._format(mixed_nums) + s_mix_str, 
            "dragged": self._format(dragged_nums) + s_drag_str,
            "overdue": self._format(overdue_nums) + s_overdue_str # ⭐️ 回傳到期號碼
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

    def get_prize_amount(self, game_name, normal_hits, special_hit):
        # 大樂透獎金規則
        if game_name == "大樂透":
            if normal_hits == 6: return "頭獎 (保證1億起)"
            elif normal_hits == 5 and special_hit: return "貳獎 (浮動)"
            elif normal_hits == 5: return "參獎 (浮動)"
            elif normal_hits == 4 and special_hit: return "肆獎 (浮動)"
            elif normal_hits == 4: return "NT$ 2,000"
            elif normal_hits == 3 and special_hit: return "NT$ 1,000"
            elif normal_hits == 2 and special_hit: return "NT$ 400"
            elif normal_hits == 3: return "NT$ 400"
            else: return "槓龜"
            
        # 威力彩獎金規則
        elif game_name == "威力彩":
            if normal_hits == 6 and special_hit: return "頭獎 (保證2億起)"
            elif normal_hits == 6: return "貳獎 (浮動)"
            elif normal_hits == 5 and special_hit: return "NT$ 150,000"
            elif normal_hits == 5: return "NT$ 20,000"
            elif normal_hits == 4 and special_hit: return "NT$ 4,000"
            elif normal_hits == 4: return "NT$ 800"
            elif normal_hits == 3 and special_hit: return "NT$ 400"
            elif normal_hits == 2 and special_hit: return "NT$ 200"
            elif normal_hits == 3: return "NT$ 100"
            elif normal_hits == 1 and special_hit: return "NT$ 100"
            else: return "槓龜"
            
        # 今彩539獎金規則
        elif game_name == "今彩539":
            if normal_hits == 5: return "NT$ 8,000,000"
            elif normal_hits == 4: return "NT$ 20,000"
            elif normal_hits == 3: return "NT$ 300"
            elif normal_hits == 2: return "NT$ 50"
            else: return "槓龜"
            
        return "無"

if __name__ == "__main__":
    app = TaiwanLotteryMaster()
    app.run()













