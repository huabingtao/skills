#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import argparse
import traceback
import requests
import pandas as pd

# Suppress ddddocr advertising/logging if possible
# We import ddddocr inside main or helper to handle import errors gracefully
try:
    import ddddocr
except ImportError:
    print("Error: ddddocr library is not installed. Please run pip install ddddocr.")
    sys.exit(1)

BASE_URL = "https://mail-survivorio.lezuan.net"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Origin": "https://danke.habby.cn",
    "Referer": "https://danke.habby.cn/",
    "Content-Type": "application/json",
    "habbysecret": ""
}

# Response codes mapping
CODE_MAP = {
    0: "兑换成功",
    20001: "参数错误",
    20002: "验证码错误",
    20003: "玩家ID不存在/错误",
    20401: "兑换码错误",
    20402: "兑换码已使用（请勿重复兑换）",
    20403: "兑换码已过期",
    20404: "兑换码已过期",
    20407: "该账号已领取过本活动的礼包",
    20409: "本兑换码已兑换完毕",
    20410: "该礼包码是其他渠道专属礼包码，暂时无法领取",
    30001: "服务器繁忙"
}

def parse_args():
    parser = argparse.ArgumentParser(description="《弹壳特攻队》礼包码批量自动兑换工具")
    parser.add_argument("--file", "-f", required=True, help="包含玩家ID的文件路径 (支持 .txt, .csv, .xlsx, .xls)")
    parser.add_argument("--code", "-c", required=True, help="兑换码 (例如 '中秋节快乐')")
    parser.add_argument("--delay", "-d", type=float, default=0.5, help="每次请求之间的延迟时间(秒)，默认 0.5")
    parser.add_argument("--output", "-o", default="redeem_report.xlsx", help="结果报告输出路径，默认 redeem_report.xlsx")
    return parser.parse_args()

def load_player_ids(file_path):
    """
    支持读取 .txt, .csv, .xlsx 文件中的玩家ID
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    ext = os.path.splitext(file_path)[1].lower()
    ids = []
    
    if ext == '.txt':
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 过滤空行和注释行
                if line and not line.startswith('#'):
                    # 支持 "12345678" 或 "名字-12345678" 格式（自动提取ID）
                    if '-' in line:
                        parts = line.split('-')
                        # 假设最后一项是ID
                        potential_id = parts[-1].strip()
                        if potential_id.isdigit():
                            ids.append(potential_id)
                        else:
                            ids.append(line)
                    else:
                        ids.append(line)
    elif ext == '.csv':
        df = pd.read_csv(file_path)
        ids = extract_ids_from_dataframe(df)
    elif ext in ['.xlsx', '.xls']:
        df = pd.read_excel(file_path)
        ids = extract_ids_from_dataframe(df)
    else:
        raise ValueError("不支持的文件格式，仅支持 .txt, .csv, .xlsx, .xls")
    
    # 去重并保持顺序
    seen = set()
    unique_ids = []
    for pid in ids:
        clean_id = str(pid).strip()
        if clean_id and clean_id not in seen:
            seen.add(clean_id)
            unique_ids.append(clean_id)
            
    return unique_ids

def extract_ids_from_dataframe(df):
    """
    尝试从 DataFrame 中寻找包含 ID 的列并提取
    """
    # 候选列名
    candidate_cols = ['ID', 'id', '玩家ID', '玩家id', 'userId', 'userid', '用户ID', '用户id', '游戏ID', '游戏id']
    target_col = None
    
    for col in df.columns:
        if str(col).strip() in candidate_cols:
            target_col = col
            break
            
    if target_col is None:
        # 如果没找到候选列名，默认使用第一列
        target_col = df.columns[0]
        print(f"未找到显式的ID列，将默认使用第一列 '{target_col}' 作为玩家ID")
        
    # 提取并转换为字符串，过滤掉空值
    return df[target_col].dropna().astype(str).tolist()

class DankRedeemer:
    def __init__(self, gift_code, delay=0.5):
        self.gift_code = gift_code
        self.delay = delay
        # 初始化 ddddocr 识别引擎
        self.ocr = ddddocr.DdddOcr(show_ad=False)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def get_captcha(self):
        """
        获取验证码ID和验证码图片字节流
        """
        gen_url = f"{BASE_URL}/api/v1/captcha/generate"
        res = self.session.post(gen_url, json={}, timeout=10)
        res.raise_for_status()
        res_data = res.json()
        
        if res_data.get("code") != 0:
            raise Exception(f"生成验证码失败: {res_data}")
            
        captcha_id = res_data["data"]["captchaId"]
        
        img_url = f"{BASE_URL}/api/v1/captcha/image/{captcha_id}"
        img_res = self.session.get(img_url, timeout=10)
        img_res.raise_for_status()
        
        return captcha_id, img_res.content

    def claim_gift(self, user_id, captcha, captcha_id):
        """
        调用兑换接口
        """
        claim_url = f"{BASE_URL}/api/v1/giftcode/claim"
        payload = {
            "userId": str(user_id).strip(),
            "giftCode": str(self.gift_code).strip(),
            "captcha": str(captcha).strip(),
            "captchaId": str(captcha_id).strip()
        }
        res = self.session.post(claim_url, json=payload, timeout=10)
        res.raise_for_status()
        return res.json()

    def redeem_single(self, user_id, max_retries=5):
        """
        对单个用户ID进行兑换，包含验证码错误自动重试机制
        """
        retries = 0
        while retries < max_retries:
            try:
                captcha_id, img_bytes = self.get_captcha()
                # 识别验证码
                captcha_code = self.ocr.classification(img_bytes)
                captcha_code = str(captcha_code).strip()
                
                # 如果识别出来不是4位，直接重试，不浪费接口调用
                if len(captcha_code) != 4 or not captcha_code.isdigit():
                    retries += 1
                    time.sleep(0.2)
                    continue
                
                # 调用兑换接口
                res_data = self.claim_gift(user_id, captcha_code, captcha_id)
                code = res_data.get("code")
                msg = CODE_MAP.get(code, f"未知错误 (code: {code})")
                
                if code == 0:
                    # 兑换成功
                    return "成功", msg, retries + 1
                elif code == 20002:
                    # 验证码错误，重试
                    retries += 1
                    time.sleep(0.2)
                    continue
                elif code in [20402, 20407]:
                    # 已领取
                    return "已领取", msg, retries + 1
                elif code == 20003:
                    # ID错误
                    return "失败", "玩家ID不存在或错误", retries + 1
                elif code in [20401, 20403, 20404, 20409, 20410]:
                    # 兑换码相关错误，这些错误对所有ID都一样，可以直接终止后续执行，但这里仍记录为失败
                    return "失败", msg, retries + 1
                else:
                    # 其他错误
                    return "失败", msg, retries + 1
                    
            except Exception as e:
                retries += 1
                time.sleep(0.5)
                if retries >= max_retries:
                    return "失败", f"接口调用异常: {str(e)}", retries
        
        return "失败", "验证码识别多次错误，兑换失败", retries

def main():
    args = parse_args()
    
    print("=" * 60)
    print("        《弹壳特攻队》礼包码批量自动兑换工具")
    print("=" * 60)
    print(f" 兑 换 码 : {args.code}")
    print(f" 输 入 文 件: {args.file}")
    print(f" 输 出 报 告: {args.output}")
    print(f" 请求延迟 : {args.delay} 秒")
    print("=" * 60)
    
    try:
        player_ids = load_player_ids(args.file)
        total_ids = len(player_ids)
        print(f" 成功加载 {total_ids} 个不重复的玩家ID。")
    except Exception as e:
        print(f" 加载文件失败: {e}")
        sys.exit(1)
        
    if total_ids == 0:
        print(" 错误: 未找到任何有效的玩家ID。")
        sys.exit(1)
        
    print("\n[开始执行兑换]...")
    redeemer = DankRedeemer(gift_code=args.code, delay=args.delay)
    
    results = []
    success_count = 0
    already_claimed_count = 0
    fail_count = 0
    
    start_time = time.time()
    
    for idx, pid in enumerate(player_ids, 1):
        print(f"[{idx}/{total_ids}] 正在处理玩家 ID: {pid} ... ", end="", flush=True)
        
        status, message, retries = redeemer.redeem_single(pid)
        
        if status == "成功":
            success_count += 1
            print(f"\033[92m成功\033[0m (尝试了 {retries} 次)")
        elif status == "已领取":
            already_claimed_count += 1
            print(f"\033[93m已领取\033[0m ({message})")
        else:
            fail_count += 1
            print(f"\033[91m失败\033[0m ({message})")
            
        results.append({
            "玩家ID": pid,
            "兑换状态": status,
            "结果说明": message,
            "验证码尝试次数": retries
        })
        
        # 频率控制
        if idx < total_ids:
            time.sleep(args.delay)
            
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # 保存报告
    df_results = pd.DataFrame(results)
    output_ext = os.path.splitext(args.output)[1].lower()
    try:
        if output_ext in ['.xlsx', '.xls']:
            df_results.to_excel(args.output, index=False)
        else:
            # 默认保存为 CSV
            if output_ext != '.csv':
                args.output = os.path.splitext(args.output)[0] + ".csv"
            df_results.to_csv(args.output, index=False, encoding='utf-8-sig')
        print(f"\n[报告生成] 详细兑换报告已保存至: {os.path.abspath(args.output)}")
    except Exception as e:
        print(f"\n[警告] 保存报告失败: {e}")
        
    # 统计汇总输出
    print("\n" + "=" * 50)
    print("                  兑换统计汇总")
    print("=" * 50)
    print(f" 总 ID 数量 : {total_ids}")
    print(f" 兑换成功   : {success_count} ({success_count/total_ids*100:.1f}%)")
    print(f" 重复领取   : {already_claimed_count} ({already_claimed_count/total_ids*100:.1f}%)")
    print(f" 兑换失败   : {fail_count} ({fail_count/total_ids*100:.1f}%)")
    print(f" 总耗时     : {elapsed_time:.1f} 秒 (平均 {elapsed_time/total_ids:.2f} 秒/个)")
    print("=" * 50)

if __name__ == "__main__":
    main()
