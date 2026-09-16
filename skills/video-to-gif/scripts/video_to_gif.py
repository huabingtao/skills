#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse

def get_duration(video_path):
    cmd = [
        "ffprobe", "-v", "error", 
        "-show_entries", "format=duration", 
        "-of", "default=noprint_wrappers=1:nokey=1", 
        video_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except Exception as e:
        print(f"Error getting duration: {e}", file=sys.stderr)
        return None

def convert_to_gif(input_path, output_path, fps, width, start=None, duration=None):
    # Construct filter_complex with lanczos scale and palettegen/paletteuse
    scale_filter = f"scale={width}:-1" if width > 0 else "scale=iw:-1"
    vf = f"fps={fps},{scale_filter}:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
    
    cmd = ["ffmpeg", "-y"]
    if start:
        cmd.extend(["-ss", start])
    if duration:
        cmd.extend(["-t", str(duration)])
    cmd.extend(["-i", input_path, "-vf", vf, output_path])
    
    print(f"Running ffmpeg command: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"FFmpeg Error:\n{res.stderr}", file=sys.stderr)
        return False
    return True

def main():
    parser = argparse.ArgumentParser(description="Convert video to optimized GIF, with optional auto-compression.")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output", required=True, help="Output GIF path")
    parser.add_argument("--fps", type=int, default=10, help="Initial FPS (default: 10)")
    parser.add_argument("--width", type=int, default=320, help="Initial width in pixels (default: 320)")
    parser.add_argument("--start", help="Start time in hh:mm:ss or seconds")
    parser.add_argument("--duration", type=float, help="Duration in seconds")
    parser.add_argument("--max-size", type=float, help="Target max size in MB")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    fps = args.fps
    width = args.width
    
    # Run initial conversion
    success = convert_to_gif(args.input, args.output, fps, width, args.start, args.duration)
    if not success:
        sys.exit(1)
        
    if args.max_size:
        max_bytes = args.max_size * 1024 * 1024
        current_size = os.path.getsize(args.output)
        print(f"Initial GIF size: {current_size / (1024*1024):.2f} MB")
        
        # Iteratively optimize if size exceeds limit
        min_fps = 5
        min_width = 160
        
        while current_size > max_bytes and (fps > min_fps or width > min_width):
            if fps > min_fps:
                fps -= 1
            elif width > min_width:
                width = max(min_width, width - 20)
                # Reset fps to a reasonable starting value for the new width
                fps = max(min_fps, args.fps - 2)
            
            print(f"Target size exceeded. Re-converting with FPS={fps}, Width={width}...")
            success = convert_to_gif(args.input, args.output, fps, width, args.start, args.duration)
            if not success:
                sys.exit(1)
            current_size = os.path.getsize(args.output)
            print(f"New GIF size: {current_size / (1024*1024):.2f} MB")
            
        if current_size > max_bytes:
            print(f"Warning: Could not compress under {args.max_size} MB even at minimum parameters (FPS={fps}, Width={width}). Current size: {current_size / (1024*1024):.2f} MB")
        else:
            print(f"Success! Compressed GIF is {current_size / (1024*1024):.2f} MB (Width={width}, FPS={fps})")

if __name__ == "__main__":
    main()
