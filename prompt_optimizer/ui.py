from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout
from PyQt6.QtCore import Qt
import sys

app = QApplication(sys.argv)
window = QWidget()
window.setWindowTitle("精美 UI 示例")
window.resize(300, 200)

layout = QVBoxLayout()
button = QPushButton("点击我！")
button.setStyleSheet("""
    QPushButton {
        background-color: #4CAF50;
        color: white;
        border: none;
        padding: 12px;
        font-size: 16px;
        border-radius: 8px;
    }
    QPushButton:hover {
        background-color: #45a049;
    }
""")
layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignCenter)
window.setLayout(layout)
window.show()
sys.exit(app.exec())
