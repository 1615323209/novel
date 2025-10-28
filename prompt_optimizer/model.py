import logging
import openai
import time
import random
from atom_library import WomenShortStories
from log import logger
from config import config
from openai import OpenAI
from pathlib import Path

# 初始化客户端
client = OpenAI(base_url=config['url'],api_key=config['api-key-余额-100'])

# 开启调式模式（True为Debug，False为Info）
debug_mode = config['log_debug']
if debug_mode:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

system_text = Path(config['prompt_path_sys']).read_text(encoding='utf-8')

def cell_model(message_sta):
    for retry in range(6):
        try:
            response = client.chat.completions.create(
                model=config['model'],
                messages=message_sta,
                temperature=1,
            )
            content = response.choices[0].message.content
            message_sta.append({"role": "assistant", "content": content})
            logger.debug(f'模型输出内容：\n{content}')
            return message_sta
        except (openai.APIConnectionError, openai.APITimeoutError) as e:
            wait_time = 2 ** retry
            logger.warning(f'网络错误，第{retry + 1}次调用失败，等待 {wait_time} 秒后重试... 错误信息: {e}')
            time.sleep(wait_time)


def main():
    for i in range(1):
        logger.info(f"开始第{i+1}次写作")

        idx_ins = random.randint(0, len(WomenShortStories.json_ins) - 1)
        idx_plot = random.randint(0, len(WomenShortStories.json_plot) - 1)
        logger.info(f"本次创作，导语索引为--{idx_ins}-----剧情索引为--{idx_plot}")

        ins_content = WomenShortStories.json_ins[idx_ins]["导语内容"]
        ins_ins = WomenShortStories.json_ins[idx_ins]["导语结构分析"]
        model_ins = f"【原始导语】：\n{ins_content}\n【导语结构】：{ins_ins}\n{WomenShortStories.prompt_ins}"

        start_plot = WomenShortStories.json_plot[idx_plot]["开篇剧情概述"]
        paid_plot = WomenShortStories.json_plot[idx_plot]["付费点剧情概述"]
        end_plot = WomenShortStories.json_plot[idx_plot]["结尾剧情概述"]
        plot_all = f"{start_plot}\n{paid_plot}\n{end_plot}"
        prompt_plot_all = f"【主线剧情】：\n{plot_all}\n{WomenShortStories.prompt_plot}"

        message_sta = [
            {"role": "system", "content": system_text},
            {"role": "user", "content": f'{model_ins}'},
        ]
        message_sta_ins = cell_model(message_sta)
        logger.info(f"----------1.0----------仿写导语--模型输出内容：\n{message_sta_ins[2]['content']}")

        prompt_plot_all = f"【仿写导语】：\n{message_sta_ins}\n{prompt_plot_all}"
        message_sta_ins.append({"role": "user", "content": f'{prompt_plot_all}'})
        message_sta_plot = cell_model(message_sta_ins)
        logger.info(f"----------2.0----------剧情大纲--模型输出内容：\n{message_sta_plot[4]['content']}")

        ins_plot = f"【仿写导语】：\n{message_sta_plot[2]['content']}\n【剧情大纲】：\n{message_sta_plot[4]['content']}"
        message_sta_plot.append({"role": "user", "content": f'{ins_plot}\n{WomenShortStories.prompt_text}'})
        message_sta_text = cell_model(message_sta_plot)
        logger.info(f"----------3.0----------第一次正文撰写--模型输出内容：\n{message_sta_text[6]['content']}")
        text = message_sta_text[6]["content"]

        message_sta_text.append({"role": "user", "content": '继续创作五到七章'})
        message_sta_text_2 = cell_model(message_sta_text)
        logger.info(f"----------4.0----------第二次正文撰写--模型输出内容：\n{message_sta_text_2[8]['content']}")

        text += f"\n{message_sta_text_2[8]['content']}"
        message_sta_text_2.append({"role": "user", "content": "继续创作八到十章"})
        message_sta_text_3 = cell_model(message_sta_text_2)
        logger.info(f"----------5.0----------第三次正文撰写--模型输出内容：\n{message_sta_text_3[10]['content']}")
        text += f"\n{message_sta_text_3[10]['content']}"

        with open(f'test{i}', 'w', encoding='utf-8') as f:
            f.write(text)
        logger.info(f"第{i+1}次写作完成")
        time.sleep(3)

if __name__ == '__main__':
    main()