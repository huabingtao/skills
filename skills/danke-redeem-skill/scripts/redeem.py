#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import argparse
import csv
import math
import re
import tempfile
from pathlib import Path
import requests

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
    parser.add_argument("--force", action="store_true", help="明确允许覆盖已有报告")
    parser.add_argument("--dry-run", action="store_true", help="仅校验输入并生成待兑换报告，不联网、不加载 OCR")
    args = parser.parse_args()
    if not math.isfinite(args.delay) or args.delay < 0:
        parser.error("--delay 必须是非负有限数字")
    if not args.code.strip():
        parser.error("--code 不能为空")
    if Path(args.output).suffix.lower() not in (".csv", ".xlsx"):
        parser.error("--output 仅支持 .csv 或 .xlsx")
    if Path(args.file).resolve() == Path(args.output).resolve():
        parser.error("输入文件与报告不能使用同一路径")
    if Path(args.output).exists() and not args.force:
        parser.error("报告已存在；请选择新路径，或用 --force 明确覆盖")
    return args

def normalize_player_id(value, *, spreadsheet=False):
    """只接受十进制 ID；表格文本保留前导零，整数小数尾缀可安全移除。"""
    text = str(value).strip()
    if not text:
        return None
    if spreadsheet and re.fullmatch(r"[0-9]+\.0+", text):
        text = text.split(".", 1)[0]
    if not re.fullmatch(r"[0-9]+", text):
        raise ValueError("玩家 ID 必须为纯数字；请检查输入行（不接受小数或科学计数法）")
    return text


def load_player_ids(file_path):
    path = Path(file_path)
    ids = []
    if path.suffix.lower() == ".txt":
        for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "-" in line and not line.startswith("-"):
                line = line.rsplit("-", 1)[-1].strip()
            try:
                ids.append(normalize_player_id(line))
            except ValueError as exc:
                raise ValueError(f"第 {number} 行: {exc}") from exc
    elif path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            column = select_id_column(reader.fieldnames or [])
            for number, row in enumerate(reader, 2):
                value = row.get(column)
                if value is None or not value.strip():
                    continue
                try:
                    ids.append(normalize_player_id(value, spreadsheet=True))
                except ValueError as exc:
                    raise ValueError(f"第 {number} 行: {exc}") from exc
    elif path.suffix.lower() in (".xlsx", ".xls"):
        import pandas as pd
        frame = pd.read_excel(path, dtype=str, keep_default_na=False)
        ids = extract_ids_from_dataframe(frame)
    else:
        raise ValueError("不支持的文件格式，仅支持 .txt, .csv, .xlsx, .xls")
    return list(dict.fromkeys(pid for pid in ids if pid))


def select_id_column(columns):
    columns = list(columns)
    if not columns:
        raise ValueError("输入表格没有列")
    for col in columns:
        if str(col).strip().lower() in ("id", "玩家id", "userid", "用户id", "游戏id"):
            return col
    print("未找到显式 ID 列，使用第一列；请先用 --dry-run 核对。")
    return columns[0]


def extract_ids_from_dataframe(df):
    column = select_id_column(df.columns)
    return [normalize_player_id(value, spreadsheet=True) for value in df[column].dropna()]


REPORT_FIELDS = ["玩家ID", "兑换状态", "结果说明", "验证码尝试次数"]


def save_report(results, output):
    """先写同目录临时文件再替换，避免中断破坏已有进度。"""
    path = Path(output)
    if path.suffix.lower() not in (".csv", ".xlsx"):
        raise ValueError("报告仅支持 .csv 或 .xlsx")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, pending = tempfile.mkstemp(suffix=path.suffix, dir=path.parent)
    os.close(fd)
    try:
        if path.suffix.lower() == ".csv":
            with open(pending, "w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDS)
                writer.writeheader()
                writer.writerows(results)
        else:
            import pandas as pd
            pd.DataFrame(results, columns=REPORT_FIELDS).to_excel(pending, index=False, engine="openpyxl")
        os.replace(pending, path)
    finally:
        if os.path.exists(pending):
            os.unlink(pending)


class DankRedeemer:
    def __init__(self, gift_code, delay=0.5):
        self.gift_code = gift_code
        self.delay = delay
        # 初始化 ddddocr 识别引擎
        try:
            import ddddocr
        except ImportError as exc:
            raise RuntimeError("缺少 ddddocr；请安装此技能 requirements.txt 中的依赖") from exc
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
                    time.sleep(max(self.delay, 0.2))
                    continue
                
                # 调用兑换接口
                try:
                    res_data = self.claim_gift(user_id, captcha_code, captcha_id)
                except (requests.RequestException, ValueError) as exc:
                    return "待核实", f"兑换响应未确认，请核对领取状态后再重试: {exc}", retries + 1
                if not isinstance(res_data, dict) or "code" not in res_data:
                    return "待核实", "兑换响应格式异常，请核对领取状态", retries + 1
                code = res_data.get("code")
                msg = CODE_MAP.get(code, f"未知错误 (code: {code})")
                
                if code == 0:
                    # 兑换成功
                    return "成功", msg, retries + 1
                elif code == 20002:
                    # 验证码错误，重试
                    retries += 1
                    time.sleep(max(self.delay, 0.2))
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
                time.sleep(max(self.delay, 0.5))
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
        
    results = [{"玩家ID": pid, "兑换状态": "待兑换", "结果说明": "尚未请求接口", "验证码尝试次数": 0}
               for pid in player_ids]
    # 先验证报告路径和写入依赖，避免实际兑换后才发现报告无法保存。
    save_report(results, args.output)
    if args.dry_run:
        print(f"输入校验完成，未执行兑换；{total_ids} 个 ID，报告: {Path(args.output).resolve()}")
        return

    print("\n[开始执行兑换]...")
    redeemer = DankRedeemer(gift_code=args.code, delay=args.delay)
    start_time = time.monotonic()
    try:
        for idx, pid in enumerate(player_ids):
            # 如在请求中途退出，该条保留“待核实”，避免被误当成未发送。
            results[idx].update(兑换状态="待核实", 结果说明="请求开始，尚未取得完整响应")
            save_report(results, args.output)
            status, message, attempts = redeemer.redeem_single(pid)
            results[idx].update(兑换状态=status, 结果说明=message, 验证码尝试次数=attempts)
            save_report(results, args.output)
            print(f"[{idx + 1}/{total_ids}] {status}: {message}")
            if idx + 1 < total_ids:
                time.sleep(args.delay)
    finally:
        redeemer.session.close()

    counts = {status: sum(row["兑换状态"] == status for row in results) for status in ("成功", "已领取", "失败", "待核实")}
    print(f"兑换完成: {counts}；总耗时 {time.monotonic() - start_time:.1f} 秒")
    print(f"报告: {Path(args.output).resolve()}")
    if counts["失败"] or counts["待核实"]:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("任务已中断；报告保留已完成结果、待核实请求和待兑换 ID。", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
