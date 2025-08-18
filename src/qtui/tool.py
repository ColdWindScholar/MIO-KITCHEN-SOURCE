import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QHBoxLayout, QVBoxLayout, QLabel, QWidget, \
    QTextEdit, QPushButton, QTabWidget


class Tool(QMainWindow):
    def __init__(self):
        super(Tool, self).__init__()
        main_widget = QWidget()
        self.hbox = QHBoxLayout()
        #left functions
        self.left_vbox = QVBoxLayout()
        self.time_show = QLabel("21:00")
        self.time_show.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_area = QLabel("Drop here")
        self.drop_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        #log_hbox
        self.log_hbox = QHBoxLayout()
        self.log_show = QTextEdit()
        self.clear_button = QPushButton("Clear")
        self.log_hbox.addWidget(self.log_show)
        self.log_hbox.addWidget(self.clear_button)
        #
        self.left_vbox.addWidget(self.time_show)
        self.left_vbox.addWidget(self.drop_area)
        self.left_vbox.addLayout(self.log_hbox)
        #right
        self.tab_view = QTabWidget()
        self.tab_main()
        self.tab_view.addTab(self.tab_main_frame, 'Home')
        #
        self.hbox.addLayout(self.left_vbox)
        self.hbox.addWidget(self.tab_view)
        self.hbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_widget = main_widget
        self.main_widget.setLayout(self.hbox)
        self.setCentralWidget(main_widget)

    def tab_main(self):
        self.tab_main_frame = QWidget()
        self.tab_main_hbox = QHBoxLayout()
        self.kemiaojiang = QLabel("Kemiaojiang")
        self.kemiaojiang.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.kemiaojiang_desc = QLabel("Kemiaojiang")
        self.kemiaojiang_desc.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.tab_main_hbox.addWidget(self.kemiaojiang)
        self.tab_main_hbox.addWidget(self.kemiaojiang_desc)
        self.tab_main_frame.setLayout(self.tab_main_hbox)
    def tab_project(self):
        self.tab_project_frame = QWidget()
        self.tab_project_hbox = QVBoxLayout()
        




def __init__qt(argv):
    app = QApplication(argv)
    tool = Tool()
    tool.show()
    sys.exit(app.exec())

init = lambda args: __init__qt(args)
if __name__ == '__main__':
    init(sys.argv)