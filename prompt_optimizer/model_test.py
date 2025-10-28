import logging
import openai
import time
import random
from prompt_optimizer.atom_library import WomenShortStories
from log import logger
from prompt_optimizer.config import config
from openai import OpenAI
from pathlib import Path

# 初始化客户端
client = OpenAI(base_url=config['url'], api_key=config['api-key-余额-50'])

# 日志级别
debug_mode = config['log_debug']
logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)

system_text = Path(config['prompt_path_sys']).read_text(encoding='utf-8')


def stream_chat_completion(messages, model=config['model'], temperature=1.0):
    """
    流式调用模型，返回完整内容和更新后的消息列表
    """
    full_content = ""
    try:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            stream=True
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                delta = chunk.choices[0].delta.content
                full_content += delta
                # 可选：实时打印（调试用）
                print(delta, end="", flush=True)
        logger.debug(f"模型流式输出完成，总长度: {len(full_content)} 字符")
        messages.append({"role": "assistant", "content": full_content})
        return messages, full_content
    except (openai.APIConnectionError, openai.APITimeoutError, openai.RateLimitError, openai.APIError) as e:
        logger.error(f"OpenAI API 错误: {e}")
        raise


def call_with_retry(messages, max_retries=5):
    """
    带指数退避重试的流式调用
    """
    for retry in range(max_retries):
        try:
            return stream_chat_completion(messages)
        except Exception as e:
            wait_time = (2 ** retry) + random.uniform(0, 1)
            logger.warning(f"第 {retry + 1} 次调用失败，{wait_time:.2f} 秒后重试... 错误: {e}")
            time.sleep(wait_time)
    raise Exception("模型调用失败，已达到最大重试次数")


def main():
    for i in range(5):
        logger.info(f"开始第 {i+1} 次写作")

        # 随机选择导语和剧情
        idx_ins = random.randint(0, len(WomenShortStories.json_ins) - 1)
        idx_plot = random.randint(0, len(WomenShortStories.json_plot) - 1)
        logger.info(f"导语索引: {idx_ins}, 剧情索引: {idx_plot}")

        # 构建导语提示
        ins_content = WomenShortStories.json_ins[idx_ins]["导语内容"]
        ins_ins = WomenShortStories.json_ins[idx_ins]["导语结构分析"]
        model_ins = f"【原始导语】：\n{ins_content}\n【导语结构】：{ins_ins}\n{WomenShortStories.prompt_ins}"

        # 构建剧情提示
        start_plot = WomenShortStories.json_plot[idx_plot]["开篇剧情概述"]
        paid_plot = WomenShortStories.json_plot[idx_plot]["付费点剧情概述"]
        end_plot = WomenShortStories.json_plot[idx_plot]["结尾剧情概述"]
        plot_all = f"{start_plot}\n{paid_plot}\n{end_plot}"
        prompt_plot_all = f"【主线剧情】：\n{plot_all}\n{WomenShortStories.prompt_plot}"

        # Step 1: 仿写导语
        messages = [
            {"role": "system", "content": system_text},
            {"role": "user", "content": model_ins}
        ]
        messages, rewritten_intro = call_with_retry(messages)
        logger.info("----------1.0---------- 仿写导语完成")

        # Step 2: 生成剧情大纲
        messages.append({"role": "user", "content": f"【仿写导语】：\n{rewritten_intro}\n{prompt_plot_all}"})
        messages, plot_outline = call_with_retry(messages)
        logger.info("----------2.0---------- 剧情大纲完成")

        # Step 3: 第一次正文（1-4章）
        messages.append({
            "role": "user",
            "content": f"【仿写导语】：\n{rewritten_intro}\n【剧情大纲】：\n{plot_outline}\n{WomenShortStories.prompt_text}"
        })
        messages, text_part1 = call_with_retry(messages)
        logger.info("----------3.0---------- 第一次正文撰写完成")

        full_text = text_part1

        # Step 4: 继续创作 5-7 章
        messages.append({"role": "user", "content": "继续创作五到七章"})
        messages, text_part2 = call_with_retry(messages)
        full_text += "\n" + text_part2
        logger.info("----------4.0---------- 第二次正文撰写完成")

        # Step 5: 继续创作 8-10 章
        messages.append({"role": "user", "content": "继续创作八到十章"})
        messages, text_part3 = call_with_retry(messages)
        full_text += "\n" + text_part3
        logger.info("----------5.0---------- 第三次正文撰写完成")

        res = rewritten_intro + "\n" + full_text

        # 保存结果
        output_path = f'test_{i+1}.txt'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(res)
        logger.info(f"第 {i+1} 次写作完成，已保存至 {output_path}")

        time.sleep(3)


if __name__ == '__main__':
    main()
