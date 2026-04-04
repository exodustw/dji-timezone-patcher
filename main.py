from glob import glob
from datetime import datetime, timedelta
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

def get_createdate(filepath):
    """取得影片內部的 CreateDate，若無則回傳 None"""
    cmd = ["exiftool", "-s3", "-CreateDate", filepath]
    result = subprocess.run(cmd, capture_output=True, text=True)
    out = result.stdout.strip()

    if out:
        return out
    return None

def get_current_exif_tz(filepath):
    """
    取得檔案目前的時區標記 (例如 +08:00)
    """
    # 嘗試取得照片的 EXIF 時區或影片的 Keys 時區

    cmd = [
        "exiftool", "-s3", 
        "-OffsetTimeOriginal", # 照片優先
        "-CreationDate",       # 影片(Keys)
        filepath
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout.strip()
    
    # 使用正則表達式抓取尾部的 +HH:MM 或 -HH:MM
    match = re.search(r'([+-])(\d{2}):(\d{2})$', output)
    
    if match:
        sign = 1 if match.group(1) == '+' else -1
        hours = int(match.group(2)) * sign
        minutes = int(match.group(3)) * sign
        return (hours, minutes)
    
    return None

def update_exif_timezone(filepath, new_tz, default_tz=8, large_file_support=False, debug=False):
    """
    file_path: 影片路徑
    new_tz: 目標時區 (例如預期是 +9，就輸入 9)
    """
    file_ext = os.path.basename(filepath).split('.')[-1].lower()
    
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
    
    if file_ext == 'mp4':
        shift = new_tz - 0
        shift_str = f"{shift:+d}" # 建立偏移字串，例如 "+1" 或 "-5"

        create_date = get_createdate(filepath)
        if create_date is None:
            create_date = get_time_from_filename(os.path.basename(filepath))

            if not create_date:
                print(f"Failed (No time info from filename)")
                return False
            
            create_date_ts = datetime.strptime(create_date, "%Y:%m:%d %H:%M:%S") + timedelta(hours=-default_tz)
            create_date = create_date_ts.strftime("%Y:%m:%d %H:%M:%S")
        else:
            create_date_ts = datetime.strptime(create_date, "%Y:%m:%d %H:%M:%S")
        
        local_date_ts = create_date_ts + timedelta(hours=shift)
        local_date = local_date_ts.strftime("%Y:%m:%d %H:%M:%S")

        cmd.extend([
            "-globalTimeShift", shift_str,
            f"-XMP:description={create_date}",
            f"-Keys:CreationDate={local_date}{tz_str}",
            filepath
        ])
        
    elif file_ext == 'jpg':
        exif_tz = get_current_exif_tz(filepath)
        
        if exif_tz is not None:
            old_tz = exif_tz[0] + exif_tz[1] / 60
        else:
            old_tz = default_tz
        
        shift = new_tz - old_tz

        create_date = get_createdate(filepath)
        if create_date is None:
            print(f"Failed (No time info from exif)")
            return False

        create_date_ts = datetime.strptime(create_date, "%Y:%m:%d %H:%M:%S")
        local_date_ts = create_date_ts + timedelta(hours=shift)
        local_date = local_date_ts.strftime("%Y:%m:%d %H:%M:%S")

        cmd.extend([
            f"-AllDates={local_date}{tz_str}",
            f"-OffsetTime*={tz_str}",                       # 修正 EXIF 時區標籤
            f"-XMP-xmp:CreateDate={local_date}{tz_str}", # 修正 XMP 標籤
            f"-XMP-xmp:ModifyDate={local_date}{tz_str}",
            # f"-Keys:CreationDate={local_date}{tz_str}",
            # f"-XMP:description<${{CreateDate}}",
            filepath
        ])
    else:
        print(f"Failed (Unsupport file extension .{file_ext})")
        return False

    if debug:
        print('command', ' '.join(cmd))

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
    parser.add_argument("newtz", type=int, choices=range(-12, 15), help="correct timezone")
    parser.add_argument("-t", "--default-tz", type=int, default=8, choices=range(-12, 15), help="default timezone if not presented in file")
    parser.add_argument("-f", "--overwrite", action="store_true", help="overwrite")
    parser.add_argument("-l", "--large-file", action="store_true", help="large file support")
    parser.add_argument("-d", "--debug", action="store_true", help="debug flag")
    parser.add_argument("-y", "--yes", action="store_true", help="disable safety lock")

    args = parser.parse_args()

    target = args.dir
    new_timezone = args.newtz
    default_timezone = args.default_tz

    if not args.yes:
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

            if not update_exif_timezone(filename, new_timezone, default_timezone, large_file_support=args.large_file, debug=args.debug):
                break
            print(f"Modified.")