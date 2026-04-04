# dji-timezone-patcher

A lightweight CLI tool to fix timezone inconsistencies in photos and videos, especially from **DJI Osmo 360** and **DJI Action 5 Pro**.

When traveling across countries, my video files filmed by DJI Action and Osmo 360 cannot record the correct timezone information since they are offline. This becomes annoying when I upload the media to platforms like **Google Photos** or **Immich**, as the timeline is not ordered correctly due to missing or inconsistent timezone metadata.

This tool help me to normalize timestamps and timezone metadata automatically, ensuring your media timeline stays accurate while uploading to platforms.

## Disclaimer

* Read the code before you run it.
* Always backup your files before processing.
* This tool modifies metadata **in-place**.

## Features

Adjust media timestamps from an original timezone (the timezone set on your camera, default: UTC+8, Taipei) to a target timezone (the correct timezone where the shot was taken, e.g., UTC+9, Tokyo).

### Supporting Format 

#### Photos (JPG) from DJI Osmo 360

* Adjusts:
  * `DateTimeOriginal`
  * `AllDates`
* Writes:
  * `OffsetTime*` (EXIF timezone tags)
  * `XMP-xmp:CreateDate`
  * `XMP-xmp:ModifyDate`

#### Videos (MP4) from DJI Action 5 Pro

* Handles large DJI .MP4 files (via `LargeFileSupport` api)
* Fixes:
  * `QuickTime:CreateDate`
  * `Keys:CreationDate` (with timezone)
* Uses `globalTimeShift` for consistent adjustment

### Time Extraction Strategy

* Priority:
  1. Metadata (`CreateDate`)
  2. Filename (e.g. `DJI_20250128212939_XXXX.MP4`)
* Filename is parsed into `YYYY:MM:DD HH:MM:SS` as the DJI default naming strategy

## Requirements

* Python 3.8+
* `exiftool`

Install ExifTool:

```bash
# macOS
brew install exiftool

# Ubuntu
sudo apt install libimage-exiftool-perl
```

## Usage

```bash
python main.py <path> <target_tz> [options]
```

| Argument    | Description                                      |
| ----------- | ------------------------------------------------ |
| `path`      | Target file path (supports glob, e.g. `"*.MP4"`) |
| `target_tz` | Target timezone in int (e.g. `9` for UTC+9)      |

### Options

| Option                         | Description                           |
| ------------------------------ | ------------------------------------- |
| `-t <int>, --default-tz <int>` | Default timezone in int (default: +8) |
| `-f, --overwrite`              | Force reprocess files                 |
| `-l, --large-file`             | Enable large file support (>4GB)      |
| `-d, --debug`                  | Print ExifTool command                |
| `-y, --yes`                    | Skip confirmation prompt              |

### Example

Convert DJI videos from Taiwan (UTC+8) to Japan (UTC+9):

```bash
python main.py "*.MP4" 9 -l
```

Process photos:

```bash
python main.py "*.JPG" 9
```

## License

This script is free to use and modify under the MIT License.
