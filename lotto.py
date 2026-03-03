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

# ⭐️ 建立快取連線 (放在 class 外面，防 Google 封鎖)
@st.cache_resource
def get_google_db():
    creds_dict = json.loads(st.secrets["google_credentials"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open("台彩大數據資料庫")

class TaiwanLotteryMaster:
    def __init__(self):
        # ⭐️ 確保每個遊戲都有 draw_balls
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
        api_paths = {
            "lotto649": "Lotto649Result",
            "super_lotto638": "SuperLotto638Result",
            "daily_cash": "Daily539Result", 
            "4_d": "4DResult",
            "3_d": "3DResult",
            # ⭐️ 換上你親手挖出來的終極密碼！
            "bingo": "LatestBingoResult" 
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
            # ⭐️ 針對賓果與一般彩券的特殊分流處理
            is_bingo = (game_info["name"] == "賓果賓果")
            
            for loop_idx in range(36):
                if is_bingo:
                    # 賓果一天開200多期，我們不用「月份」找，直接用「頁數」往下翻
                    params = {
                        "pageNum": loop_idx + 1, 
                        "pageSize": 100
                    }
                else:
                    # 一般彩券維持用「月份」往下找
                    month_str = f"{year}-{month:02d}"
                    params = {
                        "month": month_str,
                        "pageNum": 1,
                        "pageSize": 100
                    }
                
                res = requests.get(url, params=params, timeout=10, verify=False)
                data = res.json()

                # ⭐️ 終極 X 光機：直接把 API 的底褲印在網頁上！
                if is_bingo:
                    st.warning(f"📡 成功連線！除錯網址：{res.url}")
                    st.json(data)  # Streamlit 會自動把 JSON 畫成漂亮的樹狀圖
                    st.stop()      # 強制暫停程式，讓我們好好看清楚資料結構！
                
                records = []
                if "content" in data and data["content"]:
                    for key, val in data["content"].items():
                        if isinstance(val, list):
                            records = val
                            break
                            
                # ⭐️ 防呆：如果 API 回傳空的陣列，代表抓到底了，直接收工
                if not records:
                    break
                            
                for rec in records:
                    issue = str(rec.get("period", ""))
                    if not issue: continue
                    
                    if stop_issue and issue == stop_issue: 
                        return history_data
                    
                    nums_str = rec.get("drawNumberSize")
                    if not nums_str:  
                        nums_str = rec.get("drawNumberAppear", [])
                        
                    if not nums_str:
                        continue
                        
                    nums = [int(n) for n in nums_str]
                    
                    # 捕捉賓果的超級獎號或一般特別號
                    if game_info["special"] > 0:
                        special_num = rec.get("superPrizeNo") or rec.get("specialNumber") or rec.get("secondZoneNumber")
                        if special_num is not None:
                            nums.append(int(special_num))
                        
                    target_length = game_info["draw_balls"] + game_info["special"]
                    if len(nums) == target_length:
                        # 避免抓到重複期數
                        if not any(issue == existing[0] for existing in history_data):
                            history_data.append([issue] + nums)
                            
                    # 如果抓滿了設定的筆數 (預設200期)，就回傳資料
                    if len(history_data) >= limit:
                        return history_data
                
                # 一般彩券才需要切換月份，賓果不用
                if not is_bingo:
                    month -= 1
                    if month == 0:
                        month = 12
                        year -= 1
                    
            return history_data
            
        except Exception as e:
            return history_data

    def get_google_sheet(self, sheet_name):
        db = get_google_db()
        worksheets = [ws.title for ws in db.worksheets()]
        if sheet_name not in worksheets:
            db.add_worksheet(title=sheet_name, rows="1000", cols="30")
        return db.worksheet(sheet_name)

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
        new_data_list = self.fetch_real_data(game_info, stop_issue=stop_issue, limit=200)
        
        if new_data_list:
            columns = ['期數'] + [f'號碼{i+1}' for i in range(game_info["draw_balls"])]
            if game_info["special"] > 0: columns.append("特別號")
            new_df = pd.DataFrame(new_data_list, columns=columns)
            new_df = new_df.iloc[::-1].reset_index(drop=True)
            
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

        last_seen = {n: 9999 for n in range(1, max_num + 1)}
        for idx, row in enumerate(df.iloc[::-1].iterrows()):
            draw_nums = row[1][reg_cols].values
            for num in draw_nums:
                if last_seen[int(num)] == 9999:
                    last_seen[int(num)] = idx
        overdue_pool = sorted(last_seen.keys(), key=lambda x: last_seen[x], reverse=True)
        overdue_nums = overdue_pool[:balls_needed]

        s_hot_str = s_cold_str = s_mix_str = s_drag_str = s_overdue_str = ""
        if game_info["special"] > 0:
            s_history = df["特別號"].tail(window).values
            s_counts = Counter(s_history)
            s_hot = s_counts.most_common(1)[0][0]
            s_pool = set(range(1, game_info["s_max"] + 1))
            s_cold_list = list(s_pool - set(s_counts.keys()))
            s_cold = random.choice(s_cold_list) if s_cold_list else s_counts.most_common()[-1][0]
            s_mix = random.choice([s_hot, s_cold])
            
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
            "overdue": self._format(overdue_nums) + s_overdue_str 
        }

    def get_dragged_analysis(self, df, game_info):
        if game_info["type"] != "combo" or df.empty or len(df) < 2: return None
        reg_cols = [f'號碼{i+1}' for i in range(game_info["draw_balls"])]
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

    def auto_save_prediction(self, game_name, base_issue, picks):
        try:
            sheet = self.get_google_sheet("預測紀錄")
            all_values = sheet.get_all_values()
            if not all_values:
                headers = ["時間", "遊戲", "基準期數", "熱門", "冷門", "綜合", "拖牌", "到期"]
                sheet.append_row(headers)
                all_values = [headers]
            else:
                headers = all_values[0]
            
            if "遊戲" in headers and "基準期數" in headers:
                game_idx = headers.index("遊戲")
                issue_idx = headers.index("基準期數")
                for row in all_values[1:]:
                    if len(row) > max(game_idx, issue_idx):
                        if str(row[game_idx]).strip() == str(game_name).strip() and str(row[issue_idx]).strip() == str(base_issue).strip():
                            return "exists"
                            
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row_data = [now, game_name, str(base_issue), picks['hot'], picks['cold'], picks['mixed'], picks['dragged'], picks.get('overdue', '')]
            sheet.append_row(row_data)
            return True
        except Exception as e:
            return False

    def get_prize_amount(self, game_name, normal_hits, special_hit):
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
            
        elif game_name == "今彩539":
            if normal_hits == 5: return "NT$ 8,000,000"
            elif normal_hits == 4: return "NT$ 20,000"
            elif normal_hits == 3: return "NT$ 300"
            elif normal_hits == 2: return "NT$ 50"
            else: return "槓龜"
            
        elif game_name == "賓果賓果":
            prize = "槓龜"
            if normal_hits == 10: prize = "NT$ 5,000,000"
            elif normal_hits == 9: prize = "NT$ 250,000"
            elif normal_hits == 8: prize = "NT$ 25,000"
            elif normal_hits == 7: prize = "NT$ 2,500"
            elif normal_hits == 6: prize = "NT$ 1,000"
            elif normal_hits == 5: prize = "NT$ 400"
            elif normal_hits == 0: prize = "NT$ 400" 
            
            if special_hit and prize != "槓龜":
                return prize + " + 猜中超級獎號!"
            elif special_hit:
                return "單純猜中超級獎號!"
            return prize
            
        return "無"

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
                        strategies = [("hot", "熱門", "🔥 策略一【全熱門號】"), 
                                      ("cold", "冷門", "❄️ 策略二【全冷門號】"), 
                                      ("mixed", "綜合", "🌗 策略三【冷熱各半】"), 
                                      ("dragged", "拖牌", "🧩 策略四【拖牌精選】"),
                                      ("overdue", "到期", "⏳ 策略五【到期補漏】")]
                        
                        for key, col_name, strat_name in strategies:
                            raw_pick_str = str(row.get(col_name, ""))
                            if not raw_pick_str: continue
                            
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

    def get_positional_analysis(self, df, game_info):
        if game_info["type"] != "position" or df.empty: return None
        nums_df = df.tail(20).drop(columns=['期數'])
        positions = ["千位", "百位", "十位", "個位"] if game_info["draw_balls"] == 4 else ["百位", "十位", "個位"]
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



