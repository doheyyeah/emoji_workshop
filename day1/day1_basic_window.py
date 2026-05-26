import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, 
    QPushButton, QLabel, QVBoxLayout, QHBoxLayout
)
from PyQt6.QtCore import Qt


class MainWindow(QMainWindow):
    """主窗口类 - 这是PyQt的标准写法"""
    
    def __init__(self):
        super().__init__()  # 调用父类构造，必须写
        self.setWindowTitle("表情工坊 - Day1 基础窗口")
        self.setGeometry(100, 100, 600, 400)  # x, y, width, height
        
        # 创建中央部件（QMainWindow必须设置central widget）
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # 创建布局（垂直排列）
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # 添加标签
        self.title_label = QLabel("欢迎使用表情工坊！")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 设置样式（类似CSS）
        self.title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #333333;
                padding: 20px;
            }
        """)
        self.main_layout.addWidget(self.title_label)
        
        # 添加按钮
        self.btn_hello = QPushButton("点我打招呼")
        self.btn_hello.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                padding: 10px 20px;
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.main_layout.addWidget(self.btn_hello)
        
        # 添加计数标签
        self.count_label = QLabel("点击次数：0")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.count_label)
        
        # ===== 信号与槽连接 =====
        # 点击按钮 → 执行 self.on_button_clicked 方法
        self.click_count = 0
        self.btn_hello.clicked.connect(self.on_button_clicked)
    
    def on_button_clicked(self):
        """槽函数：响应按钮点击"""
        self.click_count += 1
        self.count_label.setText(f"点击次数：{self.click_count}")
        self.title_label.setText(f"你好！这是第 {self.click_count} 次点击")


def main():
    app = QApplication(sys.argv)  # 创建应用实例
    window = MainWindow()          # 创建窗口
    window.show()                  # 显示窗口
    sys.exit(app.exec())           # 进入事件循环（阻塞，等待用户操作）


if __name__ == "__main__":
    main()