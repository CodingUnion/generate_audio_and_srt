import os
import re
import asyncio
import time
import edge_tts
from pydub import AudioSegment

# 更新路径为你本地的实际路径
input_file_path = '/Users/cuishuang/Documents/Project/generate_audio_and_srt/input.txt'
output_directory = '/Users/cuishuang/Documents/Project/generate_audio_and_srt/'
output_filename_base = 'output'


# 读取文本文件，并去掉多余的空白段落
def read_and_clean_text(input_file_path):
    with open(input_file_path, 'r', encoding='utf-8') as file:
        text = file.read()

    # 去掉多余的空白段落
    text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])

    return text


# 生成不重复的文件名和输出文件路径，而非覆盖前一次生成的文件，方便调测比对效果
def generate_unique_filename_and_filepath(directory, filename_base, extension):
    base_filepath = os.path.join(directory, filename_base)
    counter = 1
    new_filename = f"{filename_base}{extension}"
    filepath = os.path.join(directory, new_filename)

    while os.path.exists(filepath):
        new_filename = f"{filename_base}_{counter}{extension}"
        filepath = os.path.join(directory, new_filename)
        counter += 1

    return new_filename, filepath


# 品牌词替换字典
brand_replacements = {
    "SU7": "速7",
    "MIUI": "米优",
    # 可以添加更多品牌词替换
}

# 自定义需要处理的词组，防止不必要的停顿
phrases_to_combine = [
    "电动汽车",
    "展现",
    # 可以添加更多需要处理的词组
]

# 定义标点符号的时间权重，基于此权重调整时长
punctuation_weights = {
    "，": 1,  # 逗号：较短的停顿
    "。": 2,  # 句号：较长的停顿
    "！": 2,  # 感叹号：较长的停顿
    "？": 2,  # 问号：较长的停顿
}

# 可选的14种中文人声
voice_options = {
    1: "zh-CN-XiaoxiaoNeural",  # 1. 小小 (女声) - 甜美、友好的语气
    2: "zh-CN-XiaoyiNeural",  # 2. 晓艺 (女声) - 优雅、正式的语气
    3: "zh-CN-YunjianNeural",  # 3. 云健 (男声) - 清晰、稳重的语气
    4: "zh-CN-YunxiNeural",  # 4. 云希 (男声) - 沉稳、严肃的语气
    5: "zh-CN-YunxiaNeural",  # 5. 云夏 (男声) - 活泼、温暖的语气
    6: "zh-CN-YunyangNeural",  # 6. 云阳 (男声) - 低沉、有力的语气
    7: "zh-CN-liaoning-XiaobeiNeural",  # 7. 辽宁小北 (女声) - 辽宁方言
    8: "zh-CN-shaanxi-XiaoniNeural",  # 8. 陕西小妮 (女声) - 陕西方言
    9: "zh-HK-HiuGaaiNeural",  # 9. 曉佳 (女声) - 香港粤语
    10: "zh-HK-HiuMaanNeural",  # 10. 曉嫚 (女声) - 香港粤语
    11: "zh-HK-WanLungNeural",  # 11. 雲龍 (男声) - 香港粤语
    12: "zh-TW-HsiaoChenNeural",  # 12. 小宸 (女声) - 台湾国语
    13: "zh-TW-HsiaoYuNeural",  # 13. 小雨 (女声) - 台湾国语
    14: "zh-TW-YunJheNeural"  # 14. 云哲 (男声) - 台湾国语
}


# 使用 edge-tts 进行异步文字转语音
async def text_to_speech(text, output_audio_path, voice_id=4):
    # 选择对应编号的声音，默认为云希男声 (voice_id=4)
    voice = voice_options.get(voice_id)
    communicate = edge_tts.Communicate(text, voice=voice)
    await communicate.save(output_audio_path)


# 处理字幕分割
def split_text_into_subtitles(text, max_chinese_characters=12, max_english_characters=24):
    subtitles = []
    current_subtitle = ""

    for segment in re.split(r'([，。！？])', text):
        if len(current_subtitle + segment) <= max_chinese_characters:
            current_subtitle += segment
        else:
            # 将当前字幕行添加到列表并开始新行
            if current_subtitle:
                subtitles.append(current_subtitle.rstrip("，。！？").strip())
            # 启动新的一行
            current_subtitle = segment.lstrip("，。！？").strip()

    if current_subtitle:
        subtitles.append(current_subtitle.rstrip("，。！？").strip())

    # 去除可能生成的空白字幕
    subtitles = [subtitle for subtitle in subtitles if subtitle]

    return subtitles


# 计算每条字幕的时间戳
def generate_srt_file(subtitles, audio_path, output_srt_path):
    audio = AudioSegment.from_mp3(audio_path)
    total_duration = len(audio) / 1000  # 音频总长度（秒）

    # 根据音频的实际时长和每个字幕片段的字符数精确分配时间
    subtitle_lengths = [len(sub) for sub in subtitles]
    total_chars = sum(subtitle_lengths)
    current_time = 0.0

    with open(output_srt_path, 'w', encoding='utf-8') as srt_file:
        for i, subtitle in enumerate(subtitles):
            # 计算每个字幕片段的基本时长
            subtitle_duration = total_duration * (subtitle_lengths[i] / total_chars)

            # 根据标点符号调整时长
            for char in subtitle:
                if char in punctuation_weights:
                    subtitle_duration += punctuation_weights[char] * 0.5  # 根据标点符号增加的时长（每个权重单位增加0.5秒）

            start_time = current_time
            end_time = current_time + subtitle_duration
            srt_file.write(f"{i + 1}\n")
            srt_file.write(f"{format_time(start_time)} --> {format_time(end_time)}\n")
            srt_file.write(f"{subtitle}\n\n")
            current_time = end_time


# 格式化时间函数
def format_time(seconds):
    milliseconds = int((seconds % 1) * 1000)
    seconds = int(seconds)
    minutes = seconds // 60
    hours = minutes // 60
    seconds = seconds % 60
    minutes = minutes % 60
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


async def main():
    start_time = time.time()  # 开始计时

    # 生成不重复的文件名和输出文件路径
    output_audio_filename, output_audio_path = generate_unique_filename_and_filepath(output_directory,
                                                                                     output_filename_base, ".mp3")
    output_srt_filename, output_srt_path = generate_unique_filename_and_filepath(output_directory, output_filename_base,
                                                                                 ".srt")

    # 读取并处理文本
    text = read_and_clean_text(input_file_path)

    # 处理替换后的文本，用于生成音频
    processed_text = text
    for brand, replacement in brand_replacements.items():
        processed_text = processed_text.replace(brand, replacement)

    # 插入不可见字符 (\u200D) 将整个词组包裹起来，防止不必要的停顿
    for phrase in phrases_to_combine:
        processed_text = processed_text.replace(phrase, "\u200D" + phrase + "\u200D")

    # 调用异步文字转语音函数，使用替换后的文本
    await text_to_speech(processed_text, output_audio_path)  # 默认使用编号4：云希（男声）

    # 生成.srt文件，使用原始文本
    subtitles = split_text_into_subtitles(text)
    generate_srt_file(subtitles, output_audio_path, output_srt_path)

    end_time = time.time()  # 结束计时
    duration = end_time - start_time

    # 打印结果
    print(f"执行完成，耗时{duration:.2f}秒")
    print(f"--音频文件：{output_audio_filename}")
    print(f"--字幕文件：{output_srt_filename}")


# 运行主函数
asyncio.run(main())