# main_ui.py
import sys
import os
import logging
import random
import time
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QTextEdit,
    QVBoxLayout, QWidget, QLabel, QFileDialog, QMessageBox
)
from PyQt5.QtCore import QThread, pyqtSignal
from config import config
from openai import OpenAI

# 日志处理器
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

    def __init__(self, output_dir, intro_structure, instruction_prompt):
        super().__init__()
        self.output_dir = output_dir
        self.intro_structure = intro_structure
        self.instruction_prompt = instruction_prompt

    def run(self):
        try:
            # 从 config 中读取 API 配置（用户不可见）
            api_key = config.get('api-key-余额-100', '')
            base_url = config.get('url', 'https://api.openai.com/v1')
            model = config.get('model', 'gpt-3.5-turbo')

            if not api_key:
                self.log_signal.emit("❌ 配置文件中缺少 API Key，请检查 config.py")
                return

            client = OpenAI(base_url=base_url, api_key=api_key)

            # 读取系统提示词（可保留，或也可让用户输入，但按你要求只改导语部分）
            system_prompt_path = config.get('prompt_path_sys')
            if system_prompt_path and Path(system_prompt_path).exists():
                system_text = Path(system_prompt_path).read_text(encoding='utf-8')
            else:
                system_text = "你是一个专业的女性短篇故事作家，请根据要求仿写导语。"
                self.log_signal.emit("⚠️ 未找到系统提示词文件，使用默认系统提示。")

            # 构造用户消息
            model_ins = f"【导语结构】：{self.intro_structure}\n{self.instruction_prompt}"

            messages = [
                {"role": "system", "content": system_text},
                {"role": "user", "content": model_ins}
            ]

            self.log_signal.emit("🚀 开始调用模型生成仿写导语...")

            # 调用模型（带重试）
            full_content = ""
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=1.0,
                stream=True
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    delta = chunk.choices[0].delta.content
                    full_content += delta

            # 保存结果
            output_path = os.path.join(self.output_dir, 'rewritten_intro.txt')
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(full_content)

            self.log_signal.emit("----------1.0---------- 仿写导语完成")
            self.log_signal.emit(f"✅ 结果已保存至: {output_path}")

        except Exception as e:
            self.log_signal.emit(f"❌ 程序异常: {str(e)}")
        finally:
            self.finished_signal.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("仅供内部测试使用")
        self.resize(900, 800)

        self.output_dir = os.getcwd()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()

        # 输出目录
        self.dir_label = QLabel(f"输出目录: {self.output_dir}")
        self.dir_btn = QPushButton("选择输出文件夹")
        self.dir_btn.clicked.connect(self.select_output_dir)

        # 用户输入区
        self.intro_structure_label = QLabel("1. 请输入导语结构分析 + 参照核心梗：")
        self.intro_structure_input = QTextEdit()
        self.intro_structure_input.setPlaceholderText("")

        self.instruction_prompt_label = QLabel("2. 请输入导语创作提示词（指令）：")
        self.instruction_prompt_input = QTextEdit()
        self.instruction_prompt_input.setPlaceholderText("")

        # 开始按钮
        self.start_btn = QPushButton("开始创作导语")
        self.start_btn.clicked.connect(self.start_generation)

        # 日志显示
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)

        # 布局
        layout.addWidget(self.dir_label)
        layout.addWidget(self.dir_btn)
        layout.addWidget(self.intro_structure_label)
        layout.addWidget(self.intro_structure_input)
        layout.addWidget(self.instruction_prompt_label)
        layout.addWidget(self.instruction_prompt_input)
        layout.addWidget(self.start_btn)
        layout.addWidget(QLabel("运行日志:"))
        layout.addWidget(self.log_text)

        central_widget.setLayout(layout)

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
        intro_structure = self.intro_structure_input.toPlainText().strip()
        instruction_prompt = self.instruction_prompt_input.toPlainText().strip()

        if not intro_structure:
            QMessageBox.warning(self, "输入错误", "请填写导语结构分析！")
            return
        if not instruction_prompt:
            QMessageBox.warning(self, "输入错误", "请填写导语创作提示词！")
            return

        self.start_btn.setEnabled(False)
        self.log_text.clear()
        self.append_log("⏳ 正在处理请求...")

        self.worker = WorkerThread(
            self.output_dir,
            intro_structure,
            instruction_prompt
        )
        self.worker.log_signal.connect(self.append_log)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def on_finished(self):
        self.start_btn.setEnabled(True)
        self.append_log("✨ 任务结束。")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
