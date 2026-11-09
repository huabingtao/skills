#!/usr/bin/env python3
"""
analyze_event.py
弹壳特攻队解包活动全景自动化解析与素材提取工具
通过底层配置表（EventOpenTime, Item, Language, FestivalTask, FestivalExChange, Reward, *Base）
一键逆向解析任意活动的 7 大核心要素并生成标准化攻略素材。
"""

import argparse
import csv
import datetime
import os
import sys
from collections import defaultdict

TABLES_DIR = "/home/guagua/workspace/project/danke/danke-resource/extracted/tables"

def load_csv(filename):
    path = os.path.join(TABLES_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        return list(reader)

class DankeEventAnalyzer:
    def __init__(self):
        print("[*] 正在加载基础字典配置表...")
        self.language = self._load_language()
        self.items = self._load_items()

    def _load_language(self):
        lang = {}
        for row in load_csv("Language.csv"):
            if len(row) > 2 and row[0]:
                lang[row[0]] = row[2]
        return lang

    def _load_items(self):
        items = {}
        for row in load_csv("Item.csv"):
            if len(row) > 10 and row[0]:
                iid = row[0]
                name_id = row[10]
                raw_name = row[1]
                localized = self.language.get(name_id, raw_name)
                category = row[4] if len(row) > 4 else ""
                items[iid] = {
                    "id": iid,
                    "name": localized,
                    "raw_name": raw_name,
                    "category": category,
                    "row": row
                }
        return items

    def find_events_by_date(self, target_date_str):
        """target_date_str: YYYY-MM-DD (e.g. 2026-11-10)"""
        dt = datetime.datetime.strptime(target_date_str, "%Y-%m-%d").replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
        target_ts = int(dt.timestamp())
        
        events = []
        for row in load_csv("EventOpenTime.csv"):
            if len(row) > 6 and row[5].isdigit():
                start_ts = int(row[5])
                # 检查在当天 00:00 前后 12 小时内
                if abs(start_ts - target_ts) <= 43200:
                    events.append(row)
        return events

    def find_events_by_name(self, name):
        """通过名称在 Language 中查找匹配的活动名称 ID，并关联 Item/EventOpenTime"""
        matched_items = []
        for iid, data in self.items.items():
            if name in data["name"] or name in data["raw_name"]:
                matched_items.append(data)
        return matched_items

    def analyze_event_by_ids(self, main_event_id, task_event_id=None, base_name="AppraiseBase.csv"):
        """分析指定活动 ID 的完整数据"""
        print(f"[*] 深度分析活动 ID: 主={main_event_id}, 任务/商店={task_event_id}...")
        
        # 1. 查找 EventOpenTime 信息
        event_time_info = None
        for row in load_csv("EventOpenTime.csv"):
            if row and row[0] == str(main_event_id):
                event_time_info = row
                break

        # 2. 查找 Base 表
        base_rows = load_csv(base_name)
        base_cfg = None
        for row in base_rows:
            if len(row) > 1 and row[1] == str(main_event_id):
                base_cfg = row
                break

        # 3. 提取抽奖票与积分代币
        ticket_id = base_cfg[2] if base_cfg and len(base_cfg) > 2 else None
        token_id = base_cfg[8] if base_cfg and len(base_cfg) > 8 else None
        price = base_cfg[3] if base_cfg and len(base_cfg) > 3 else "40"
        init_tickets = base_cfg[7] if base_cfg and len(base_cfg) > 7 else "10"

        # 4. 提取任务详情 (FestivalTask.csv)
        tasks = defaultdict(list)
        if task_event_id:
            for row in load_csv("FestivalTask.csv"):
                if len(row) > 6 and row[1] == str(task_event_id):
                    t_type = row[3]
                    need = int(row[4])
                    reward_parts = row[6].split("Ⓑⓗ")
                    rew_cnt = int(reward_parts[1]) if len(reward_parts) > 1 else 0
                    tasks[t_type].append((need, rew_cnt))

        # 5. 提取兑换商店 (FestivalExChange.csv)
        exchanges = []
        if task_event_id:
            for row in load_csv("FestivalExChange.csv"):
                if len(row) > 6 and row[1] == str(task_event_id):
                    ex_id = row[0]
                    need = row[3]
                    limit = row[5]
                    reward = row[6]
                    
                    cost_cnt = need.split("Ⓑⓗ")[1] if "Ⓑⓗ" in need else need
                    rew_parts = reward.split("Ⓑⓗ")
                    rew_id = rew_parts[0]
                    rew_cnt = rew_parts[1] if len(rew_parts) > 1 else "1"
                    rew_name = self.items.get(rew_id, {}).get("name", rew_id)
                    exchanges.append({
                        "id": ex_id,
                        "name": rew_name,
                        "item_id": rew_id,
                        "count": rew_cnt,
                        "cost": cost_cnt,
                        "limit": limit
                    })

        # 6. 提取累积进度奖励 (BigReward from Base, mapped to Reward.csv)
        milestones = []
        if base_cfg and len(base_cfg) > 15 and base_cfg[15]:
            rewards_dict = {}
            for row in load_csv("Reward.csv"):
                if row:
                    rewards_dict[row[0]] = row[1:]

            raw_big = base_cfg[15].split("|")
            for item_str in raw_big:
                if "Ⓑⓗ" in item_str:
                    score, r_id = item_str.split("Ⓑⓗ")
                    r_data = rewards_dict.get(r_id, [])
                    parsed_rewards = []
                    if len(r_data) > 1 and r_data[1]:
                        for part in r_data[1].split("|"):
                            if "Ⓑⓗ" in part:
                                iid, cnt = part.split("Ⓑⓗ")
                                parsed_rewards.append(f"{self.items.get(iid, {}).get('name', iid)} x{cnt}")
                    milestones.append({
                        "score": int(score),
                        "reward_id": r_id,
                        "reward_str": ", ".join(parsed_rewards)
                    })

        return {
            "main_id": main_event_id,
            "task_id": task_event_id,
            "time_row": event_time_info,
            "base_cfg": base_cfg,
            "ticket_id": ticket_id,
            "ticket_name": self.items.get(ticket_id, {}).get("name", ticket_id),
            "token_id": token_id,
            "token_name": self.items.get(token_id, {}).get("name", token_id),
            "price": price,
            "init_tickets": init_tickets,
            "tasks": tasks,
            "exchanges": exchanges,
            "milestones": milestones
        }

def main():
    parser = argparse.ArgumentParser(description="弹壳特攻队解包活动全景提取工具")
    parser.add_argument("--date", help="活动起始日期，如 2026-11-10", default=None)
    parser.add_argument("--main-id", help="主活动 ID，如 20260807", default="20260807")
    parser.add_argument("--task-id", help="任务/商店活动 ID，如 20260808", default="20260808")
    parser.add_argument("--export", help="导出 Markdown 路径", default=None)
    args = parser.parse_args()

    analyzer = DankeEventAnalyzer()
    res = analyzer.analyze_event_by_ids(args.main_id, args.task_id)

    print("\n================ 解析报告摘要 ================")
    print(f"活动主ID: {res['main_id']} | 任务/商店ID: {res['task_id']}")
    print(f"抽奖门票: {res['ticket_name']} (ID:{res['ticket_id']}) | 单价: {res['price']} 钻 | 初始: {res['init_tickets']} 张")
    print(f"积分代币: {res['token_name']} (ID:{res['token_id']})")
    print(f"兑换商店: 共 {len(res['exchanges'])} 件商品")
    print(f"进度奖励: 共 {len(res['milestones'])} 档里程碑")
    
    # 任务汇总
    total_task_tickets = sum(sum(r[1] for r in v) for v in res['tasks'].values())
    chest_tickets = sum(r[1] for r in res['tasks'].get('4', []))
    non_chest = total_task_tickets - chest_tickets
    print(f"任务总产出: {total_task_tickets} 张 (非开箱: {non_chest} 张, 开满600箱: {chest_tickets} 张)")

if __name__ == "__main__":
    main()
