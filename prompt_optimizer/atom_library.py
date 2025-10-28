from pathlib import Path
import json
import random
from config import config


def random_number(json_data):
    num_int = random.randint(1, len(json_data) - 1)
    return num_int

class WomenShortStories:
    json_ins = json.loads(Path(r"D:\01_AI_project\AI_writer\data_library\导语库.json").read_text(encoding='utf-8'))
    json_plot = json.loads(Path(r"D:\01_AI_project\AI_writer\data_library\主线剧情库.json").read_text(encoding='utf-8'))
    json_emotion_plot = json.loads(Path(r"D:\01_AI_project\AI_writer\data_library\情绪剧情库.json").read_text(encoding='utf-8'))

    prompt_ins = Path(config['prompt_path_ins']).read_text(encoding='utf-8')
    prompt_plot = Path(config['prompt_path_change']).read_text(encoding='utf-8')
    prompt_text = Path(config['prompt_path_text']).read_text(encoding='utf-8')
    prompt_text_copy = Path(config['prompt_path_text_copy']).read_text(encoding='utf-8')




