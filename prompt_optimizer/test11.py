# main_ui.py
import sys
import os
import logging
import random
import time
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QTextEdit,
    QVBoxLayout, QWidget, QLabel, QLineEdit, QFileDialog, QMessageBox
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
    finished_signal = pyqtSignal()

    def __init__(self, output_dir, api_key, base_url, model, custom_system_prompt):
        super().__init__()
        self.output_dir = output_dir
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.custom_system_prompt = custom_system_prompt

    def run(self):
        try:
            client = OpenAI(base_url=self.base_url, api_key=self.api_key)

            # 使用用户输入的提示词，否则从文件读取
            if self.custom_system_prompt.strip():
                system_text = self.custom_system_prompt
                self.log_signal.emit("✅ 使用用户自定义系统提示词")
            else:
                prompt_path = config['prompt_path_sys']
                system_text = Path(prompt_path).read_text(encoding='utf-8')
                self.log_signal.emit(f"📄 使用默认系统提示词: {prompt_path}")

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
                messages.append({"role": "assistant", "content": full_content})
                return messages, full_content

            def call_with_retry(messages, max_retries=5):
                for retry in range(max_retries):
                    try:
                        return stream_chat_completion(messages)
                    except Exception as e:
                        wait_time = (2 ** retry) + random.uniform(0, 1)
                        self.log_signal.emit(f"第 {retry + 1} 次调用失败，{wait_time:.2f} 秒后重试... 错误: {e}")
                        time.sleep(wait_time)
                raise Exception("模型调用失败，已达到最大重试次数")

            for i in range(1):
                self.log_signal.emit(f"开始第 {i+1} 次写作")
                idx_ins = random.randint(0, len(WomenShortStories.json_ins) - 1)
                idx_plot = random.randint(0, len(WomenShortStories.json_plot) - 1)
                self.log_signal.emit(f"导语索引: {idx_ins}, 剧情索引: {idx_plot}")

                ins_content = WomenShortStories.json_ins[idx_ins]["导语内容"]
                ins_ins = WomenShortStories.json_ins[idx_ins]["导语结构分析"]
                model_ins = f"【原始导语】：\n{ins_content}\n【导语结构】：{ins_ins}\n{WomenShortStories.prompt_ins}"

                messages = [
                    {"role": "system", "content": system_text},
                    {"role": "user", "content": model_ins}
                ]
                messages, rewritten_intro = call_with_retry(messages)
                self.log_signal.emit("----------1.0---------- 仿写导语完成")

                output_path = os.path.join(self.output_dir, f'test_{i+1}.txt')
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(rewritten_intro)
                self.log_signal.emit(f"第 {i+1} 次写作完成，已保存至 {output_path}")

                time.sleep(3)

        except Exception as e:
            self.log_signal.emit(f"❌ 程序异常: {str(e)}")
        finally:
            self.finished_signal.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("仅供内部测试使用")
        self.resize(900, 700)  # 稍微加大窗口

        # 默认值
        self.output_dir = os.getcwd()
        self.api_key = config.get('api-key-余额-100', '')
        self.base_url = config.get('url', 'https://api.openai.com/v1')
        self.model = config.get('model', 'gpt-3.5-turbo')

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()

        # 输出目录
        self.dir_label = QLabel(f"输出目录: {self.output_dir}")
        self.dir_btn = QPushButton("选择输出文件夹")
        self.dir_btn.clicked.connect(self.select_output_dir)

        # API 配置
        self.api_label = QLabel("API Key:")
        self.api_input = QLineEdit(self.api_key)
        self.url_label = QLabel("Base URL:")
        self.url_input = QLineEdit(self.base_url)
        self.model_label = QLabel("模型:")
        self.model_input = QLineEdit(self.model)

        # 自定义系统提示词
        self.prompt_label = QLabel("自定义系统提示词（留空则使用默认）:")
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("在此输入你的系统提示词（System Prompt）...\n例如：你是一个擅长女性短篇故事的作家...")
        # 可选：加载默认提示词作为示例（但不强制使用）
        try:
            default_prompt = Path(config['prompt_path_sys']).read_text(encoding='utf-8')
            self.prompt_input.setPlainText(default_prompt)
        except Exception as e:
            self.prompt_input.setPlainText("# 无法加载默认提示词\n" + str(e))

        # 开始按钮
        self.start_btn = QPushButton("开始生成故事（1次）")
        self.start_btn.clicked.connect(self.start_generation)

        # 日志显示
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)

        # 布局
        layout.addWidget(self.dir_label)
        layout.addWidget(self.dir_btn)
        layout.addWidget(self.api_label)
        layout.addWidget(self.api_input)
        layout.addWidget(self.url_label)
        layout.addWidget(self.url_input)
        layout.addWidget(self.model_label)
        layout.addWidget(self.model_input)
        layout.addWidget(self.prompt_label)
        layout.addWidget(self.prompt_input)  # 新增提示词输入框
        layout.addWidget(self.start_btn)
        layout.addWidget(QLabel("运行日志:"))
        layout.addWidget(self.log_text)

        central_widget.setLayout(layout)

        # 设置日志处理器
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
        self.append_log("🚀 开始生成故事...")

        api_key = self.api_input.text().strip()
        base_url = self.url_input.text().strip()
        model = self.model_input.text().strip()
        custom_prompt = self.prompt_input.toPlainText()

        if not api_key:
            QMessageBox.warning(self, "警告", "请输入 API Key！")
            self.start_btn.setEnabled(True)
            return

        self.worker = WorkerThread(self.output_dir, api_key, base_url, model, custom_prompt)
        self.worker.log_signal.connect(self.append_log)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def on_finished(self):
        self.start_btn.setEnabled(True)
        self.append_log("✅ 所有任务已完成！")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
