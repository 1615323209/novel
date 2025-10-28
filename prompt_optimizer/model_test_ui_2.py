# main_ui.py
import sys
import os
import logging
import random
import time
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QTextEdit,
    QVBoxLayout, QWidget, QLabel, QLineEdit, QFileDialog, QMessageBox, QHBoxLayout
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from config import config
from atom_library import WomenShortStories
from openai import OpenAI

# 初始化日志捕获
class LogHandler(logging.Handler):
    def __init__(self, log_signal):
        super().__init__()
        self.log_signal = log_signal

    def emit(self, record):
        msg = self.format(record)
        self.log_signal.emit(msg)

class WorkerThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(str)  # 改为传递生成的文本

    def __init__(self, output_dir, api_key, base_url, model, user_prompt):
        super().__init__()
        self.output_dir = output_dir
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.user_prompt = user_prompt  # 接收用户输入的提示词

    def run(self):
        try:
            client = OpenAI(base_url=self.base_url, api_key=self.api_key)

            # 如果用户提供了提示词，就用用户的；否则用默认逻辑
            if self.user_prompt.strip():
                messages = [
                    {"role": "system", "content": "你是一个擅长写女性短篇故事的作家。"},
                    {"role": "user", "content": self.user_prompt}
                ]
            else:
                # 原有逻辑：随机选导语生成
                system_text = Path(config['prompt_path_sys']).read_text(encoding='utf-8')
                idx_ins = random.randint(0, len(WomenShortStories.json_ins) - 1)
                ins_content = WomenShortStories.json_ins[idx_ins]["导语内容"]
                ins_ins = WomenShortStories.json_ins[idx_ins]["导语结构分析"]
                model_ins = f"【原始导语】：\n{ins_content}\n【导语结构】：{ins_ins}\n{WomenShortStories.prompt_ins}"
                messages = [
                    {"role": "system", "content": system_text},
                    {"role": "user", "content": model_ins}
                ]

            def stream_chat_completion(messages, model=self.model, temperature=1.0):
                full_content = ""
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
                return full_content

            def call_with_retry(messages, max_retries=5):
                for retry in range(max_retries):
                    try:
                        return stream_chat_completion(messages)
                    except Exception as e:
                        wait_time = (2 ** retry) + random.uniform(0, 1)
                        self.log_signal.emit(f"第 {retry + 1} 次调用失败，{wait_time:.2f} 秒后重试... 错误: {e}")
                        time.sleep(wait_time)
                raise Exception("模型调用失败，已达到最大重试次数")

            self.log_signal.emit("正在调用模型生成内容...")
            generated_text = call_with_retry(messages)
            self.log_signal.emit("✅ 模型生成完成")

            # 保存到文件（仅当使用默认逻辑时）
            if not self.user_prompt.strip():
                output_path = os.path.join(self.output_dir, 'test_1.txt')
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(generated_text)
                self.log_signal.emit(f"已保存至 {output_path}")

            self.finished_signal.emit(generated_text)

        except Exception as e:
            self.log_signal.emit(f"❌ 程序异常: {str(e)}")
            self.finished_signal.emit("")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("仅供内部测试使用")
        self.resize(1000, 700)

        # 默认值
        self.output_dir = os.getcwd()
        self.api_key = config.get('api-key-余额-100', '')
        self.base_url = config.get('url', '')
        self.model = config.get('model', '')

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()

        # === 输出目录 ===
        dir_layout = QHBoxLayout()
        self.dir_label = QLabel(f"输出目录: {self.output_dir}")
        self.dir_btn = QPushButton("选择输出文件夹")
        self.dir_btn.clicked.connect(self.select_output_dir)
        dir_layout.addWidget(self.dir_label)
        dir_layout.addWidget(self.dir_btn)

        # === API 配置 ===
        self.api_label = QLabel("API Key:")
        self.api_input = QLineEdit(self.api_key)

        # === 用户提示词输入 ===
        main_layout.addWidget(QLabel("📝 请输入提示词（留空则使用默认导语生成）："))
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("例如：写一个关于都市女性在职场中逆袭的短篇故事，要求有反转和情感张力...")
        self.prompt_input.setMaximumHeight(100)

        # === 模型输出区域 ===
        main_layout.addWidget(QLabel("🤖 模型输出："))
        self.output_display = QTextEdit()
        self.output_display.setReadOnly(True)
        self.output_display.setStyleSheet("background-color: #f0f0f0;")

        # === 开始按钮 ===
        self.start_btn = QPushButton("开始生成")
        self.start_btn.clicked.connect(self.start_generation)

        # === 日志区域 ===
        main_layout.addWidget(QLabel("运行日志:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)

        # === 布局组装 ===
        main_layout.addLayout(dir_layout)
        main_layout.addWidget(self.api_label)
        main_layout.addWidget(self.api_input)
        main_layout.addWidget(self.start_btn)
        main_layout.addWidget(self.prompt_input)
        main_layout.addWidget(self.output_display)
        main_layout.addWidget(self.log_text)

        central_widget.setLayout(main_layout)

        # 日志处理器
        self.log_handler = LogHandler(self.append_log)
        logging.getLogger().addHandler(self.log_handler)
        logging.getLogger().setLevel(logging.INFO)

    def select_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if dir_path:
            self.output_dir = dir_path
            self.dir_label.setText(f"输出目录: {self.output_dir}")

    def append_log(self, msg):
        self.log_text.append(msg)

    def start_generation(self):
        self.start_btn.setEnabled(False)
        self.log_text.clear()
        self.output_display.clear()
        self.append_log("🚀 开始生成...")

        api_key = self.api_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "警告", "请输入 API Key！")
            self.start_btn.setEnabled(True)
            return

        user_prompt = self.prompt_input.toPlainText()

        self.worker = WorkerThread(
            output_dir=self.output_dir,
            api_key=api_key,
            base_url=self.base_url,
            model=self.model,
            user_prompt=user_prompt
        )
        self.worker.log_signal.connect(self.append_log)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def on_finished(self, generated_text):
        self.output_display.setPlainText(generated_text)
        self.start_btn.setEnabled(True)
        self.append_log("✅ 生成任务已完成！")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
