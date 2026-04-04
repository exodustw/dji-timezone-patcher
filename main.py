from glob import glob
import subprocess
import argparse
import sys
import re
import os

def get_time_from_filename(filename, pattern=r'(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})'):
    """
    從 DJI 檔名提取時間。
    格式: DJI_20250128212939_0256_D.MP4 -> 2025:01:28 21:29:39
    """
    # 正則表達式尋找 14 位數字 (YYYYMMDDHHMMSS)
    match = re.search(pattern, filename)
    if match:
        return f"{match.group(1)}:{match.group(2)}:{match.group(3)} {match.group(4)}:{match.group(5)}:{match.group(6)}"
    return None


def has_description(filepath, description):
    if not os.path.exists(filepath):
        return False
    
    cmd = ["exiftool", "-s3", description, filepath]
    
    try:
        # 使用 capture_output 取得結果，並去除空白字元
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        # 如果輸出的字串長度大於 0，代表標籤存在
        return len(result.stdout.strip()) > 0
    except subprocess.CalledProcessError:
        # 如果 exiftool 執行失敗（例如檔案損壞），視為不存在
        return False

def has_xmp_description(filepath):
    """
    檢查 MP4 檔案中是否存在 XMP:Description 標籤。
    回傳: True (存在且有內容), False (不存在或讀取失敗)
    """
    return has_description(filepath, "-XMP:Description")

def has_createdate(filepath):
    """檢查是否有 QuickTime:CreateDate"""
    return has_description(filepath, "-CreateDate")

def update_exif_timezone(filepath, new_tz, old_tz=0, large_file_support=False):
    """
    file_path: 影片路徑
    new_tz: 目標時區 (例如預期是 +9，就輸入 9)
    """
    shift = new_tz - old_tz
    
    # 建立偏移字串，例如 "+1" 或 "-5"
    shift_str = f"{shift:+d}"
    
    # 時區標籤字串，例如 "+09:00"
    tz_str = f"{new_tz:+03d}:00"

    # print(f"時區偏移調整: {shift_str} 小時，標記為 {tz_str}")

    # 執行 ExifTool 指令
    # 1. -P: 保留檔案系統時間
    # 2. -overwrite_original: 不產生 _original 備份
    # 3. -globalTimeShift: 調整所有時間數值
    # 4. 寫入帶有時區偏移的 Keys:CreationDate
    cmd = [
        "exiftool",
        "-P",
        "-overwrite_original"
    ]

    if large_file_support:
        cmd.extend(["-api", "LargeFileSupport=1"])
    
    if has_createdate(filepath):
        cmd.extend([
            "-XMP:description<CreateDate",
            f"-globalTimeShift", f"{shift_str}",
            f"-Keys:CreationDate<${{CreateDate}}{tz_str}",
            # f"-UserData:DateTimeOriginal<${{CreateDate}}{tz_str}",
            filepath
        ])
    else:
        filetime = get_time_from_filename(os.path.basename(filepath))
        if filetime:
            cmd.extend([
                f"-CreateDate={filetime}",
                # f"-XMP:Description={filetime}",
                "-XMP:description<CreateDate",
                "-globalTimeShift", shift_str,
                f"-Keys:CreationDate<${{CreateDate}}{tz_str}",
                filepath
            ])
        else:
            print(f"Failed (No time info from filename)")
            return False

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed ({e.stderr})")
        return False
    
    return True

if __name__ == "__main__":
    # --- 使用範例 ---
    # 假設你要把當初在台灣 (+8) 拍，但被當成 UTC 的 DJI 影片，改為日本時區 (+9)
    # Check: exiftool -G1 -a -s -Time:all <filename>.MP4
    # Check backup: exiftool -XMP:Description <filename>.MP4

    parser = argparse.ArgumentParser()
    parser.add_argument("dir", help="path")
    # type=int 自動檢查是否為整數; choices 限制輸入範圍
    parser.add_argument("tz", type=int, choices=range(-12, 15), help="timezone")
    parser.add_argument("--overwrite", action="store_true", help="overwrite")
    parser.add_argument("--large-file", action="store_true", help="large file support")

    args = parser.parse_args()

    target = args.dir
    new_timezone = args.tz

    yesno = input(f"Are you sure to rename? (y/n): ")
    if yesno.strip().lower() != 'y':
        print("Canceled.")
        sys.exit(4)

    for filename in sorted(glob(target)):
        if os.path.isfile(filename):
            print(f"File: {os.path.basename(filename)} ... ", end="", flush=True)

            if not args.overwrite and has_xmp_description(filename):
                print(f"Skipped.")
                continue

            if not update_exif_timezone(filename, new_timezone, large_file_support=args.large_file):
                break
            print(f"Modified.")