from openai import OpenAI
from pathlib import Path


# ins_content_2 = Path(r'D:\03_note\个人知识库\数字员工\AI作家\prompt\导语仿写.md').read_text(encoding='utf-8')
# plot_content = Path(r'D:\03_note\个人知识库\数字员工\AI作家\prompt\剧情仿写-test-1.0.md').read_text(encoding='utf-8')
# text_content = Path(r'D:\03_note\个人知识库\数字员工\AI作家\prompt\正文撰写.md').read_text(encoding='utf-8')
client = OpenAI(
    api_key="sk-xnvaUl06HmNcn5fvwC6Th3gC7aK2BlCX24Bana7DP9QHhrIn",

    base_url="https://api.chatanywhere.tech/v1"
)

response = client.chat.completions.create(
    model="claude-sonnet-4-5-20250929",
    messages=[
    {"role": "user", "content": f"你是谁"}
    ],
    max_tokens=13518,
    stream=True
)

full_content = ""

# 打开文件准备写入
with open('test_output.txt', 'w', encoding='utf-8') as f:
    for chunk in response:
        if chunk.choices:
            delta = chunk.choices[0].delta
            if delta.content:
                print(delta.content, end="", flush=True)
                f.write(delta.content)
                f.flush()

print("\n✅ 生成完成！")


