# main_ui.py - 5轮特殊对话流程 + 美化UI
import sys
import os
import logging
import random
import time
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QTextEdit,
    QVBoxLayout, QWidget, QLabel, QLineEdit, QFileDialog,
    QMessageBox, QGroupBox, QHBoxLayout, QScrollArea
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QFont
from config import config
from openai import OpenAI


class LogHandler(logging.Handler):
    def __init__(self, log_signal):
        super().__init__()
        self.log_signal = log_signal

    def emit(self, record):
        msg = self.format(record)
        self.log_signal.emit(msg)


class WorkerThread(QThread):
    log_signal = pyqtSignal(str)
    chunk_signal = pyqtSignal(str)
    response_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, api_key, base_url, model, messages):
        super().__init__()
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.messages = messages

    def run(self):
        try:
            client = OpenAI(base_url=self.base_url, api_key=self.api_key)

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
                        self.chunk_signal.emit(delta)  # 直接调用
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

            self.log_signal.emit("正在调用模型...")
            assistant_response = call_with_retry(self.messages)
            self.response_signal.emit(assistant_response)
            self.log_signal.emit("模型响应完成.")

        except Exception as e:
            self.log_signal.emit(f"❌ 程序异常: {str(e)}")
        finally:
            self.finished_signal.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("5轮提示词调试工具")
        self.resize(1300, 1000)

        self.output_dir = os.getcwd()
        self.api_key = config.get('api-key-余额-100', '')
        self.base_url = config.get('url', '')
        self.model = config.get('model', '')

        # 存储5轮用户输入和模型输出
        self.user_inputs = [""] * 5  # U1~U5
        self.assistant_outputs = [""] * 5  # A1~A5
        self.current_step = -1  # -1: 未开始; 0~4: 当前轮次
        self.system_prompt = ""

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        self.setStyleSheet("""
            QMainWindow { background-color: #f8f9fa; }
            QLabel { font-size: 13px; color: #333; }
            QPushButton {
                background-color: #4CAF50; color: white; border: none;
                padding: 8px 16px; border-radius: 6px; font-size: 14px; font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #cccccc; color: #666; }
            QLineEdit, QTextEdit {
                border: 1px solid #ccc; border-radius: 6px; padding: 6px;
                font-size: 13px; background-color: white;
            }
            QTextEdit { background-color: #fdfdfd; }
            QGroupBox {
                font-weight: bold; color: #2c3e50; border: 1px solid #ddd;
                border-radius: 8px; margin-top: 10px; padding-top: 15px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)

        # === 输出目录 ===
        dir_group = QGroupBox("📁 输出设置")
        dir_layout = QHBoxLayout()
        self.dir_label = QLabel(f"输出目录: {self.output_dir}")
        self.dir_label.setWordWrap(True)
        self.dir_btn = QPushButton("选择文件夹")
        self.dir_btn.setFixedWidth(120)
        self.dir_btn.clicked.connect(self.select_output_dir)
        dir_layout.addWidget(self.dir_label)
        dir_layout.addStretch()
        dir_layout.addWidget(self.dir_btn)
        dir_group.setLayout(dir_layout)

        # === API 配置 ===
        api_group = QGroupBox("🔑 API 配置")
        api_layout = QVBoxLayout()
        self.api_label = QLabel("API Key:")
        self.api_input = QLineEdit(self.api_key)
        api_layout.addWidget(self.api_label)
        api_layout.addWidget(self.api_input)
        api_group.setLayout(api_layout)

        # === 系统提示词 ===
        sys_group = QGroupBox("🧠 系统提示词 (System Prompt)")
        sys_layout = QVBoxLayout()
        self.system_prompt_input = QTextEdit()
        try:
            system_text = Path(config['prompt_path_sys']).read_text(encoding='utf-8')
            self.system_prompt_input.setPlainText(system_text)
        except Exception as e:
            self.system_prompt_input.setPlainText(f"无法加载系统提示词: {e}")
        sys_layout.addWidget(self.system_prompt_input)
        sys_group.setLayout(sys_layout)

        # === 5轮用户输入 ===
        inputs_group = QGroupBox("✏️ 5轮用户输入 (U1 ~ U5)")
        inputs_layout = QVBoxLayout()

        self.user_inputs_widgets = []
        for i in range(5):
            label = QLabel(f"第 {i+1} 轮用户输入 (U{i+1}):")
            text_edit = QTextEdit()
            text_edit.setFixedHeight(80)
            text_edit.setPlaceholderText(f"请输入第 {i+1} 轮提示词...")
            inputs_layout.addWidget(label)
            inputs_layout.addWidget(text_edit)
            self.user_inputs_widgets.append(text_edit)

        inputs_group.setLayout(inputs_layout)

        # === 控制按钮 ===
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶️ 开始5轮对话")
        self.save_btn = QPushButton("💾 保存全部结果")
        self.save_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start_all_turns)
        self.save_btn.clicked.connect(self.save_all_results)
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.save_btn)
        button_layout.addStretch()

        # === 输出显示 ===
        output_group = QGroupBox("🤖 模型输出 (A1 ~ A5)")
        output_layout = QVBoxLayout()
        self.output_display = QTextEdit()
        self.output_display.setReadOnly(True)
        self.output_display.setFont(QFont("Consolas", 11))
        output_layout.addWidget(self.output_display)
        output_group.setLayout(output_layout)

        # === 日志 ===
        log_group = QGroupBox("📋 运行日志")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        self.log_text.setMaximumHeight(120)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)

        # === 布局组合 ===
        main_layout.addWidget(dir_group)
        main_layout.addWidget(api_group)
        main_layout.addWidget(sys_group)
        main_layout.addWidget(inputs_group)
        main_layout.addLayout(button_layout)
        main_layout.addWidget(output_group)
        main_layout.addWidget(log_group)

        central_widget.setLayout(main_layout)

        log_handler = LogHandler(self.append_log)
        logging.getLogger().addHandler(log_handler)
        logging.getLogger().setLevel(logging.INFO)

    def select_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if dir_path:
            self.output_dir = dir_path
            self.dir_label.setText(f"输出目录: {self.output_dir}")

    def append_log(self, msg):
        self.log_text.append(msg)

    def append_chunk_to_output(self, chunk):
        self.output_display.insertPlainText(chunk)
        self.output_display.moveCursor(self.output_display.textCursor().End)

    def start_all_turns(self):
        # 读取输入
        self.system_prompt = self.system_prompt_input.toPlainText().strip()
        api_key = self.api_input.text().strip()

        for i in range(5):
            self.user_inputs[i] = self.user_inputs_widgets[i].toPlainText().strip()

        if not api_key or not self.system_prompt:
            QMessageBox.warning(self, "警告", "请填写 API Key 和系统提示词！")
            return

        if any(not ui for ui in self.user_inputs):
            QMessageBox.warning(self, "警告", "请确保5轮用户输入均已填写！")
            return

        # 重置状态
        self.assistant_outputs = [""] * 5
        self.current_step = -1
        self.output_display.clear()
        self.log_text.clear()
        self.start_btn.setEnabled(False)
        self.save_btn.setEnabled(False)

        self.append_log("🚀 开始5轮对话流程...")
        self.run_next_step()

    def run_next_step(self):
        self.current_step += 1
        if self.current_step >= 5:
            self.on_all_finished()
            return

        step = self.current_step
        user_input = self.user_inputs[step]
        self.append_log(f"\n--- 第 {step + 1} 轮 ---")
        self.append_log(f"用户输入: {user_input[:60]}...")

        # 构建 messages
        messages = [{"role": "system", "content": self.system_prompt}]

        if step == 0:
            # 第1轮: [system, U1]
            messages.append({"role": "user", "content": user_input})
        elif step == 1:
            # 第2轮: [system, U1, A1, U2]
            messages.extend([
                {"role": "user", "content": self.user_inputs[0]},
                {"role": "assistant", "content": self.assistant_outputs[0]},
                {"role": "user", "content": user_input}
            ])
        elif step == 2:
            # 第3轮: [system, U1, A1, U2, A2, U1, A1, U3]
            messages.extend([
                {"role": "user", "content": self.user_inputs[0]},
                {"role": "assistant", "content": self.assistant_outputs[0]},
                {"role": "user", "content": self.user_inputs[1]},
                {"role": "assistant", "content": self.assistant_outputs[1]},
                {"role": "user", "content": self.user_inputs[0]},      # 额外加入 U1
                {"role": "assistant", "content": self.assistant_outputs[0]},  # 额外加入 A1
                {"role": "user", "content": user_input}
            ])
        elif step == 3 or step == 4:
            # 第4、5轮: [system, U4] 或 [system, U5]
            messages.append({"role": "user", "content": user_input})

        # 启动线程
        self.worker = WorkerThread(
            self.api_input.text().strip(),
            self.base_url,
            self.model,
            messages
        )
        self.worker.log_signal.connect(self.append_log)
        self.worker.chunk_signal.connect(self.append_chunk_to_output)
        self.worker.response_signal.connect(lambda resp: self.on_step_response(step, resp))
        self.worker.finished_signal.connect(self.on_step_finished)
        self.worker.start()

    def on_step_response(self, step, response):
        self.assistant_outputs[step] = response
        # 显示当前轮次输出
        self.output_display.append(f"\n=== 第 {step + 1} 轮模型输出 ===\n{response}\n")

    def on_step_finished(self):
        # 自动进入下一轮
        self.run_next_step()

    def on_all_finished(self):
        self.start_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.append_log("✅ 5轮对话全部完成！")

    def save_all_results(self):
        content = ""
        for i in range(5):
            content += f"===== 第 {i+1} 轮 =====\n"
            content += f"[用户输入]\n{self.user_inputs[i]}\n\n"
            content += f"[模型输出]\n{self.assistant_outputs[i]}\n\n"
            content += "-" * 50 + "\n\n"

        try:
            path = os.path.join(self.output_dir, f'5turn_result_{int(time.time())}.txt')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.append_log(f"✅ 已保存至: {path}")
            QMessageBox.information(self, "成功", f"结果已保存至:\n{path}")
        except Exception as e:
            self.append_log(f"❌ 保存失败: {e}")
            QMessageBox.critical(self, "错误", f"保存失败: {e}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
