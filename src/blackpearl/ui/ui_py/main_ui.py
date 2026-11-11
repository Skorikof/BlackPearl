# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_ui.ui'
##
## Created by: Qt User Interface Compiler version 6.12.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow,
    QProgressBar, QPushButton, QSizePolicy, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(800, 600)
        font = QFont()
        font.setFamilies([u"System"])
        font.setBold(True)
        MainWindow.setFont(font)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        font1 = QFont()
        font1.setFamilies([u"System"])
        font1.setPointSize(12)
        font1.setBold(True)
        self.centralwidget.setFont(font1)
        self.centralwidget.setStyleSheet(u"background-color: qlineargradient(spread:pad, x1:0.983, y1:0.0227273, x2:0, y2:1, stop:0 rgba(78, 78, 255, 255), stop:1 rgba(217, 220, 255, 255));")
        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.setSpacing(5)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, -1)
        self.main_mtn_frame = QFrame(self.centralwidget)
        self.main_mtn_frame.setObjectName(u"main_mtn_frame")
        self.main_mtn_frame.setMaximumSize(QSize(16777215, 50))
        font2 = QFont()
        font2.setFamilies([u"Arial"])
        font2.setPointSize(12)
        font2.setBold(True)
        self.main_mtn_frame.setFont(font2)
        self.main_mtn_frame.setStyleSheet(u"background-color: rgba(255, 255, 255, 30);\n"
"border: 1px solid rgba(255, 255, 255, 40);\n"
"border-radius: 7px;")
        self.horizontalLayout = QHBoxLayout(self.main_mtn_frame)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(5, 5, 5, 5)
        self.main_audio_btn = QPushButton(self.main_mtn_frame)
        self.main_audio_btn.setObjectName(u"main_audio_btn")
        self.main_audio_btn.setMinimumSize(QSize(0, 40))
        font3 = QFont()
        font3.setFamilies([u"Arial Black"])
        font3.setPointSize(12)
        font3.setBold(True)
        self.main_audio_btn.setFont(font3)
        self.main_audio_btn.setStyleSheet(u"QPushButton {\n"
"color: white;\n"
"background-color: rgba(255, 255, 255, 30);\n"
"border: 1px solid rgba(255, 255, 255, 40);\n"
"border-radius: 7px;\n"
"}\n"
"\n"
"QPushButton:hover {\n"
"background-color: rgba(255, 255, 255, 40);\n"
"}\n"
"\n"
"QPushButton:pressed {\n"
"background-color: rgba(255, 255, 255, 70);\n"
"}\n"
"")

        self.horizontalLayout.addWidget(self.main_audio_btn)

        self.in_dev_btn_5 = QPushButton(self.main_mtn_frame)
        self.in_dev_btn_5.setObjectName(u"in_dev_btn_5")
        self.in_dev_btn_5.setMinimumSize(QSize(0, 40))
        self.in_dev_btn_5.setFont(font3)
        self.in_dev_btn_5.setStyleSheet(u"QPushButton {\n"
"color: white;\n"
"background-color: rgba(255, 255, 255, 30);\n"
"border: 1px solid rgba(255, 255, 255, 40);\n"
"border-radius: 7px;\n"
"}\n"
"\n"
"QPushButton:hover {\n"
"background-color: rgba(255, 255, 255, 40);\n"
"}\n"
"\n"
"QPushButton:pressed {\n"
"background-color: rgba(255, 255, 255, 70);\n"
"}\n"
"")

        self.horizontalLayout.addWidget(self.in_dev_btn_5)

        self.in_dev_btn = QPushButton(self.main_mtn_frame)
        self.in_dev_btn.setObjectName(u"in_dev_btn")
        self.in_dev_btn.setMinimumSize(QSize(0, 40))
        self.in_dev_btn.setFont(font3)
        self.in_dev_btn.setStyleSheet(u"QPushButton {\n"
"color: white;\n"
"background-color: rgba(255, 255, 255, 30);\n"
"border: 1px solid rgba(255, 255, 255, 40);\n"
"border-radius: 7px;\n"
"}\n"
"\n"
"QPushButton:hover {\n"
"background-color: rgba(255, 255, 255, 40);\n"
"}\n"
"\n"
"QPushButton:pressed {\n"
"background-color: rgba(255, 255, 255, 70);\n"
"}\n"
"")

        self.horizontalLayout.addWidget(self.in_dev_btn)

        self.in_dev_btn_2 = QPushButton(self.main_mtn_frame)
        self.in_dev_btn_2.setObjectName(u"in_dev_btn_2")
        self.in_dev_btn_2.setMinimumSize(QSize(0, 40))
        self.in_dev_btn_2.setFont(font3)
        self.in_dev_btn_2.setStyleSheet(u"QPushButton {\n"
"color: white;\n"
"background-color: rgba(255, 255, 255, 30);\n"
"border: 1px solid rgba(255, 255, 255, 40);\n"
"border-radius: 7px;\n"
"}\n"
"\n"
"QPushButton:hover {\n"
"background-color: rgba(255, 255, 255, 40);\n"
"}\n"
"\n"
"QPushButton:pressed {\n"
"background-color: rgba(255, 255, 255, 70);\n"
"}\n"
"")

        self.horizontalLayout.addWidget(self.in_dev_btn_2)

        self.in_dev_btn_3 = QPushButton(self.main_mtn_frame)
        self.in_dev_btn_3.setObjectName(u"in_dev_btn_3")
        self.in_dev_btn_3.setMinimumSize(QSize(0, 40))
        self.in_dev_btn_3.setFont(font3)
        self.in_dev_btn_3.setStyleSheet(u"QPushButton {\n"
"color: white;\n"
"background-color: rgba(255, 255, 255, 30);\n"
"border: 1px solid rgba(255, 255, 255, 40);\n"
"border-radius: 7px;\n"
"}\n"
"\n"
"QPushButton:hover {\n"
"background-color: rgba(255, 255, 255, 40);\n"
"}\n"
"\n"
"QPushButton:pressed {\n"
"background-color: rgba(255, 255, 255, 70);\n"
"}\n"
"")

        self.horizontalLayout.addWidget(self.in_dev_btn_3)

        self.in_dev_btn_4 = QPushButton(self.main_mtn_frame)
        self.in_dev_btn_4.setObjectName(u"in_dev_btn_4")
        self.in_dev_btn_4.setMinimumSize(QSize(0, 40))
        self.in_dev_btn_4.setFont(font3)
        self.in_dev_btn_4.setStyleSheet(u"QPushButton {\n"
"color: white;\n"
"background-color: rgba(255, 255, 255, 30);\n"
"border: 1px solid rgba(255, 255, 255, 40);\n"
"border-radius: 7px;\n"
"}\n"
"\n"
"QPushButton:hover {\n"
"background-color: rgba(255, 255, 255, 40);\n"
"}\n"
"\n"
"QPushButton:pressed {\n"
"background-color: rgba(255, 255, 255, 70);\n"
"}\n"
"")

        self.horizontalLayout.addWidget(self.in_dev_btn_4)


        self.verticalLayout.addWidget(self.main_mtn_frame)

        self.stackedWidget = QStackedWidget(self.centralwidget)
        self.stackedWidget.setObjectName(u"stackedWidget")
        self.audio_page = QWidget()
        self.audio_page.setObjectName(u"audio_page")
        self.verticalLayout_2 = QVBoxLayout(self.audio_page)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.audio_url_le = QLineEdit(self.audio_page)
        self.audio_url_le.setObjectName(u"audio_url_le")
        self.audio_url_le.setMinimumSize(QSize(0, 30))
        self.audio_url_le.setMaximumSize(QSize(16777215, 30))
        self.audio_url_le.setFont(font1)
        self.audio_url_le.setStyleSheet(u"color: white;\n"
"background-color: rgba(255, 255, 255, 30);\n"
"border: 1px solid rgba(255, 255, 255, 40);\n"
"border-radius: 7px;\n"
"")

        self.verticalLayout_2.addWidget(self.audio_url_le)

        self.audio_btn_frame = QFrame(self.audio_page)
        self.audio_btn_frame.setObjectName(u"audio_btn_frame")
        self.audio_btn_frame.setStyleSheet(u"background-color: rgba(255, 255, 255, 0);\n"
"border: 1px solid rgba(255, 255, 255, 0);\n"
"border-radius: 7px;")
        self.horizontalLayout_2 = QHBoxLayout(self.audio_btn_frame)
        self.horizontalLayout_2.setSpacing(10)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.audio_check_btn = QPushButton(self.audio_btn_frame)
        self.audio_check_btn.setObjectName(u"audio_check_btn")
        self.audio_check_btn.setMinimumSize(QSize(0, 30))
        self.audio_check_btn.setMaximumSize(QSize(16777215, 30))
        self.audio_check_btn.setFont(font2)
        self.audio_check_btn.setStyleSheet(u"QPushButton {\n"
"color: white;\n"
"background-color: rgba(255, 255, 255, 30);\n"
"border: 1px solid rgba(255, 255, 255, 40);\n"
"border-radius: 7px;\n"
"}\n"
"\n"
"QPushButton:hover {\n"
"background-color: rgba(255, 255, 255, 40);\n"
"}\n"
"\n"
"QPushButton:pressed {\n"
"background-color: rgba(255, 255, 255, 70);\n"
"}\n"
"")

        self.horizontalLayout_2.addWidget(self.audio_check_btn)

        self.audio_quality_cb = QComboBox(self.audio_btn_frame)
        self.audio_quality_cb.addItem("")
        self.audio_quality_cb.addItem("")
        self.audio_quality_cb.addItem("")
        self.audio_quality_cb.setObjectName(u"audio_quality_cb")
        self.audio_quality_cb.setMinimumSize(QSize(0, 30))
        self.audio_quality_cb.setMaximumSize(QSize(16777215, 30))
        self.audio_quality_cb.setFont(font2)
        self.audio_quality_cb.setStyleSheet(u"color: white;\n"
"background-color: rgba(255, 255, 255, 30);\n"
"border: 1px solid rgba(255, 255, 255, 40);\n"
"border-radius: 7px;")

        self.horizontalLayout_2.addWidget(self.audio_quality_cb)

        self.audio_download_btn = QPushButton(self.audio_btn_frame)
        self.audio_download_btn.setObjectName(u"audio_download_btn")
        self.audio_download_btn.setMinimumSize(QSize(0, 30))
        self.audio_download_btn.setMaximumSize(QSize(16777215, 30))
        self.audio_download_btn.setFont(font2)
        self.audio_download_btn.setStyleSheet(u"QPushButton {\n"
"color: white;\n"
"background-color: rgba(255, 255, 255, 30);\n"
"border: 1px solid rgba(255, 255, 255, 40);\n"
"border-radius: 7px;\n"
"}\n"
"\n"
"QPushButton:hover {\n"
"background-color: rgba(255, 255, 255, 40);\n"
"}\n"
"\n"
"QPushButton:pressed {\n"
"background-color: rgba(255, 255, 255, 70);\n"
"}\n"
"")

        self.horizontalLayout_2.addWidget(self.audio_download_btn)

        self.audio_cancel_btn = QPushButton(self.audio_btn_frame)
        self.audio_cancel_btn.setObjectName(u"audio_cancel_btn")
        self.audio_cancel_btn.setMinimumSize(QSize(0, 30))
        self.audio_cancel_btn.setMaximumSize(QSize(16777215, 30))
        self.audio_cancel_btn.setFont(font2)
        self.audio_cancel_btn.setStyleSheet(u"QPushButton {\n"
"color: white;\n"
"background-color: rgba(255, 255, 255, 30);\n"
"border: 1px solid rgba(255, 255, 255, 40);\n"
"border-radius: 7px;\n"
"}\n"
"\n"
"QPushButton:hover {\n"
"background-color: rgba(255, 255, 255, 40);\n"
"}\n"
"\n"
"QPushButton:pressed {\n"
"background-color: rgba(255, 255, 255, 70);\n"
"}\n"
"")

        self.horizontalLayout_2.addWidget(self.audio_cancel_btn)


        self.verticalLayout_2.addWidget(self.audio_btn_frame)

        self.audio_tableWidget = QTableWidget(self.audio_page)
        self.audio_tableWidget.setObjectName(u"audio_tableWidget")
        self.audio_tableWidget.setFont(font2)
        self.audio_tableWidget.setStyleSheet(u"color: white;\n"
"background-color: rgba(255, 255, 255, 30);\n"
"border: 1px solid rgba(255, 255, 255, 40);\n"
"border-radius: 7px;\n"
"")
        self.audio_tableWidget.horizontalHeader().setVisible(False)
        self.audio_tableWidget.verticalHeader().setVisible(False)

        self.verticalLayout_2.addWidget(self.audio_tableWidget)

        self.audio_check_btn_frame = QFrame(self.audio_page)
        self.audio_check_btn_frame.setObjectName(u"audio_check_btn_frame")
        self.audio_check_btn_frame.setStyleSheet(u"background-color: rgba(255, 255, 255, 0);\n"
"border: 1px solid rgba(255, 255, 255, 0);\n"
"border-radius: 7px;\n"
"")
        self.horizontalLayout_3 = QHBoxLayout(self.audio_check_btn_frame)
        self.horizontalLayout_3.setSpacing(5)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.audio_check_all_btn = QPushButton(self.audio_check_btn_frame)
        self.audio_check_all_btn.setObjectName(u"audio_check_all_btn")
        self.audio_check_all_btn.setMinimumSize(QSize(0, 30))
        self.audio_check_all_btn.setMaximumSize(QSize(16777215, 30))
        self.audio_check_all_btn.setFont(font2)
        self.audio_check_all_btn.setStyleSheet(u"QPushButton {\n"
"color: white;\n"
"background-color: rgba(255, 255, 255, 30);\n"
"border: 1px solid rgba(255, 255, 255, 40);\n"
"border-radius: 7px;\n"
"}\n"
"\n"
"QPushButton:hover {\n"
"background-color: rgba(255, 255, 255, 40);\n"
"}\n"
"\n"
"QPushButton:pressed {\n"
"background-color: rgba(255, 255, 255, 70);\n"
"}\n"
"")

        self.horizontalLayout_3.addWidget(self.audio_check_all_btn)

        self.audio_remove_all_btn = QPushButton(self.audio_check_btn_frame)
        self.audio_remove_all_btn.setObjectName(u"audio_remove_all_btn")
        self.audio_remove_all_btn.setMinimumSize(QSize(0, 30))
        self.audio_remove_all_btn.setMaximumSize(QSize(16777215, 30))
        self.audio_remove_all_btn.setFont(font2)
        self.audio_remove_all_btn.setStyleSheet(u"QPushButton {\n"
"color: white;\n"
"background-color: rgba(255, 255, 255, 30);\n"
"border: 1px solid rgba(255, 255, 255, 40);\n"
"border-radius: 7px;\n"
"}\n"
"\n"
"QPushButton:hover {\n"
"background-color: rgba(255, 255, 255, 40);\n"
"}\n"
"\n"
"QPushButton:pressed {\n"
"background-color: rgba(255, 255, 255, 70);\n"
"}\n"
"")

        self.horizontalLayout_3.addWidget(self.audio_remove_all_btn)


        self.verticalLayout_2.addWidget(self.audio_check_btn_frame)

        self.audio_progressBar = QProgressBar(self.audio_page)
        self.audio_progressBar.setObjectName(u"audio_progressBar")
        self.audio_progressBar.setFont(font2)
        self.audio_progressBar.setValue(0)
        self.audio_progressBar.setTextVisible(True)

        self.verticalLayout_2.addWidget(self.audio_progressBar)

        self.audio_label = QLabel(self.audio_page)
        self.audio_label.setObjectName(u"audio_label")
        self.audio_label.setMinimumSize(QSize(0, 30))
        self.audio_label.setMaximumSize(QSize(16777215, 30))
        self.audio_label.setFont(font2)
        self.audio_label.setStyleSheet(u"color: black;\n"
"background-color: rgba(255, 255, 255, 30);\n"
"border: 1px solid rgba(255, 255, 255, 40);\n"
"border-radius: 7px;\n"
"")

        self.verticalLayout_2.addWidget(self.audio_label)

        self.stackedWidget.addWidget(self.audio_page)
        self.dev_page = QWidget()
        self.dev_page.setObjectName(u"dev_page")
        self.verticalLayout_3 = QVBoxLayout(self.dev_page)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.dev_label = QLabel(self.dev_page)
        self.dev_label.setObjectName(u"dev_label")
        font4 = QFont()
        font4.setFamilies([u"Arial Black"])
        font4.setPointSize(14)
        font4.setBold(True)
        self.dev_label.setFont(font4)
        self.dev_label.setStyleSheet(u"color: white;\n"
"background-color: rgba(255, 255, 255, 30);\n"
"border: 1px solid rgba(255, 255, 255, 40);\n"
"border-radius: 7px;")
        self.dev_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.verticalLayout_3.addWidget(self.dev_label)

        self.stackedWidget.addWidget(self.dev_page)

        self.verticalLayout.addWidget(self.stackedWidget)

        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)

        self.stackedWidget.setCurrentIndex(0)
        self.audio_quality_cb.setCurrentIndex(2)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"BlackPearl", None))
        self.main_audio_btn.setText(QCoreApplication.translate("MainWindow", u"Audio", None))
        self.in_dev_btn_5.setText(QCoreApplication.translate("MainWindow", u"in dev..", None))
        self.in_dev_btn.setText(QCoreApplication.translate("MainWindow", u"in dev..", None))
        self.in_dev_btn_2.setText(QCoreApplication.translate("MainWindow", u"in dev..", None))
        self.in_dev_btn_3.setText(QCoreApplication.translate("MainWindow", u"in dev..", None))
        self.in_dev_btn_4.setText(QCoreApplication.translate("MainWindow", u"in dev..", None))
        self.audio_url_le.setText("")
        self.audio_url_le.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Paste the link to the audio..", None))
        self.audio_check_btn.setText(QCoreApplication.translate("MainWindow", u"Check url", None))
        self.audio_quality_cb.setItemText(0, QCoreApplication.translate("MainWindow", u"128 kB/s", None))
        self.audio_quality_cb.setItemText(1, QCoreApplication.translate("MainWindow", u"192 kB/s", None))
        self.audio_quality_cb.setItemText(2, QCoreApplication.translate("MainWindow", u"320 kB/s", None))

        self.audio_download_btn.setText(QCoreApplication.translate("MainWindow", u"Download", None))
        self.audio_cancel_btn.setText(QCoreApplication.translate("MainWindow", u"Cancel", None))
        self.audio_check_all_btn.setText(QCoreApplication.translate("MainWindow", u"Check all", None))
        self.audio_remove_all_btn.setText(QCoreApplication.translate("MainWindow", u"Remove all", None))
        self.audio_label.setText(QCoreApplication.translate("MainWindow", u"Waiting for link..", None))
        self.dev_label.setText(QCoreApplication.translate("MainWindow", u"Feature in development..", None))
    # retranslateUi

