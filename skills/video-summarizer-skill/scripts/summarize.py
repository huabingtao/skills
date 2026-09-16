#!/usr/bin/env python3
import os
import sys
import re
import json
import argparse
import subprocess
import tempfile

def get_youtube_id(url):
    """
    从 YouTube URL 中提取 11 位的视频 ID。
    """
    if 'youtube.com' not in url and 'youtu.be' not in url:
        return None
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'youtu\.be\/([0-9A-Za-z_-]{11})',
        r'embed\/([0-9A-Za-z_-]{11})',
        r'shorts\/([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_bilibili_id(url):
    """
    从 Bilibili URL 中提取 BV 号或 av 号，或者判定是否为 Bilibili 视频。
    """
    if 'bilibili.com' in url or 'b23.tv' in url:
        # 尝试匹配 BV 号或 av 号
        match = re.search(r'(BV[0-9A-Za-z]{10}|av[0-9]+)', url)
        if match:
            return match.group(1)
        return "bilibili_video"
    return None

def fetch_youtube_transcript(video_id, proxy=None):
    """
    尝试使用 youtube-transcript-api 直接抓取已有的字幕轨。
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        print(f"正在尝试获取视频 ID 的 YouTube 字幕: {video_id}...")
        
        # 如果配置了代理，则初始化代理设置
        if proxy:
            from youtube_transcript_api.proxies import GenericProxyConfig
            proxy_config = GenericProxyConfig(http_url=proxy, https_url=proxy)
            api = YouTubeTranscriptApi(proxy_config=proxy_config)
        else:
            api = YouTubeTranscriptApi()
            
        transcript_list = api.list(video_id)
        
        # 语言偏好设置：优先获取中文或双语，其次获取英文
        transcript = None
        languages_preference = ['zh-CN', 'zh', 'zh-TW', 'zh-HK', 'en']
        
        try:
            transcript = transcript_list.find_transcript(languages_preference)
        except Exception:
            # 备用方案：获取第一个可用的字幕轨
            transcript = next(iter(transcript_list))
            
        if transcript:
            print(f"成功获取字幕，语言为: {transcript.language}")
            data = transcript.fetch()
            # 映射字段为统一的时间戳格式
            segments = []
            for item in data:
                start = item.start
                duration = item.duration
                segments.append({
                    'start': start,
                    'end': start + duration,
                    'text': item.text.strip()
                })
            return segments
    except Exception as e:
        print(f"无法通过 API 获取 YouTube 字幕: {e}")
    return None

def download_online_audio(url, output_path, proxy=None):
    """
    使用 yt-dlp 下载在线视频的音频轨并转换为 mp3 格式。
    """
    try:
        import yt_dlp
        print(f"正在从 {url} 下载音频...")
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_path.replace('.mp3', '.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
            'ffmpeg_location': '/usr/local/bin/ffmpeg',
            'quiet': False,
        }
        
        # 针对 Bilibili 视频，尝试从 Chrome 获取 cookie 以绕过 412 风控
        if 'bilibili.com' in url or 'b23.tv' in url:
            ydl_opts['cookiesfrombrowser'] = ('chrome',)
            
        # 如果提供了代理，设置给 yt-dlp
        if proxy:
            ydl_opts['proxy'] = proxy
            
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # yt-dlp 下载的文件可能会因为转码而临时命名，这里强制检测并返回正确的 mp3 路径
            expected_output = output_path.replace('.mp3', '.mp3')
            if os.path.exists(expected_output):
                return expected_output
            actual_temp = output_path.replace('.mp3', '')
            for ext in ['webm', 'm4a', 'opus', 'mp3']:
                p = f"{actual_temp}.{ext}"
                if os.path.exists(p):
                    return p
        return output_path
    except Exception as e:
        print(f"下载在线音频失败: {e}")
        sys.exit(1)

def extract_local_audio(video_path, output_mp3_path):
    """
    使用 ffmpeg 提取本地视频文件中的音频轨（转换成单声道 16kHz MP3 以优化识别速度）。
    """
    print(f"正在从 {video_path} 提取音频...")
    cmd = [
        "/usr/local/bin/ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "libmp3lame",
        "-ar", "16000",
        "-ac", "1",
        output_mp3_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print(f"FFmpeg 提取音频错误: {result.stderr.decode('utf-8', errors='ignore')}")
        sys.exit(1)
    return output_mp3_path

def transcribe_local_audio(audio_path, model_name, language=None):
    """
    使用本地 Whisper 模型进行语音转文字转录。
    """
    try:
        import whisper
        print(f"正在加载 Whisper 模型 '{model_name}' (首次运行需要下载，可能需要一些时间)...")
        # 强制在 CPU 上运行（适配 Intel Mac）
        model = whisper.load_model(model_name, device="cpu")
        print("正在转录音频...")
        
        options = {}
        if language:
            options["language"] = language
            
        result = model.transcribe(audio_path, **options)
        segments = []
        for seg in result.get('segments', []):
            segments.append({
                'start': seg['start'],
                'end': seg['end'],
                'text': seg['text'].strip()
            })
        return segments
    except Exception as e:
        print(f"Whisper 本地转录失败: {e}")
        sys.exit(1)

def format_timestamp(seconds):
    """
    将秒数格式化为 HH:MM:SS 或 MM:SS 的文本。
    """
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def main():
    parser = argparse.ArgumentParser(description="视频/音频内容转录与字幕提取脚本")
    parser.add_argument("--input", required=True, help="YouTube 视频链接或本地音视频文件路径")
    parser.add_argument("--output", default="transcript.json", help="保存转录 JSON 文件的输出路径")
    parser.add_argument("--model", default="base", help="本地 Whisper 模型大小 (可选 tiny, base, small, medium, large)")
    parser.add_argument("--language", default=None, help="强制指定语言轨 (例如 zh, en)")
    parser.add_argument("--proxy", default=None, help="网络代理地址 (例如 http://127.0.0.1:7897)")
    args = parser.parse_args()

    input_source = args.input.strip()
    youtube_id = get_youtube_id(input_source)
    bilibili_id = get_bilibili_id(input_source)
    
    segments = None
    source_type = "local"
    title = os.path.basename(input_source)

    if youtube_id:
        source_type = "youtube"
        title = f"YouTube 视频 ({youtube_id})"
        # 1. 优先尝试通过 YouTube API 直接抓取官方/自动字幕
        segments = fetch_youtube_transcript(youtube_id, args.proxy)
        
        # 2. 如果未获取到字幕，则降级为下载音频后通过本地 Whisper 识别
        if not segments:
            print("没有可用的 YouTube 字幕。正在下载音频以进行本地语音转文字 (ASR)...")
            with tempfile.TemporaryDirectory() as temp_dir:
                audio_temp_path = os.path.join(temp_dir, "yt_audio.mp3")
                downloaded_audio = download_online_audio(input_source, audio_temp_path, args.proxy)
                segments = transcribe_local_audio(downloaded_audio, args.model, args.language)
    elif bilibili_id:
        source_type = "bilibili"
        title = f"Bilibili 视频 ({bilibili_id})"
        print("检测到 Bilibili 视频。正在下载音频以进行本地语音转文字 (ASR)...")
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_temp_path = os.path.join(temp_dir, "bili_audio.mp3")
            downloaded_audio = download_online_audio(input_source, audio_temp_path, args.proxy)
            segments = transcribe_local_audio(downloaded_audio, args.model, args.language)
    else:
        # 本地音视频文件处理
        if not os.path.exists(input_source):
            print(f"错误: 本地文件 '{input_source}' 不存在。")
            sys.exit(1)
            
        ext = os.path.splitext(input_source)[1].lower()
        is_audio_only = ext in ['.mp3', '.wav', '.m4a', '.flac', '.aac', '.ogg']
        
        with tempfile.TemporaryDirectory() as temp_dir:
            if is_audio_only:
                audio_path = input_source
            else:
                # 视频文件先提取音频轨
                audio_temp_path = os.path.join(temp_dir, "extracted_audio.mp3")
                audio_path = extract_local_audio(input_source, audio_temp_path)
                
            segments = transcribe_local_audio(audio_path, args.model, args.language)

    if segments is None:
        print("错误: 无法提取或转录视频文本。")
        sys.exit(1)

    # 保存至 JSON
    output_data = {
        "source": source_type,
        "input": input_source,
        "title": title,
        "segments": segments
    }
    
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"\n转录文本已保存至: {args.output}")

    # 控制台打印前 30 行字幕预览
    print("\n--- 转录文本预览 ---")
    for seg in segments[:30]:
        ts = format_timestamp(seg['start'])
        print(f"[{ts}] {seg['text']}")
    if len(segments) > 30:
        print(f"... 以及另外 {len(segments) - 30} 个片段。")
    print("--------------------------\n")

if __name__ == "__main__":
    main()
