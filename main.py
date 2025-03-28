import sys
from PyQt6.QtCore import QUrl, QFileInfo, QDir, QStandardPaths, QDateTime
from PyQt6.QtGui import QIcon, QAction, QDesktopServices
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget, 
    QLineEdit, QHBoxLayout, QPushButton, QToolBar, QStatusBar, 
    QLabel, QProgressBar, QListWidget, QListWidgetItem
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineDownloadRequest
from PyQt6.QtNetwork import QNetworkCookie, QNetworkCookieJar
from PyQt6.QtCore import QByteArray, QSettings, QDateTime
import json
class DownloadItem(QWidget):
    def __init__(self, download, parent=None):
        super().__init__(parent)
        self.download = download
        self.is_finished = False
        
        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Top row (filename and buttons)
        top_layout = QHBoxLayout()
        self.filename_label = QLabel(download.suggestedFileName())
        self.filename_label.setStyleSheet("font-weight: bold;")
        self.pause_btn = QPushButton("Pause")
        self.cancel_btn = QPushButton("Cancel")
        top_layout.addWidget(self.filename_label)
        top_layout.addStretch()
        top_layout.addWidget(self.pause_btn)
        top_layout.addWidget(self.cancel_btn)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        
        # Bottom row (status and speed)
        bottom_layout = QHBoxLayout()
        self.status_label = QLabel("Starting download...")
        self.speed_label = QLabel()
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.speed_label)
        
        # Add to main layout
        layout.addLayout(top_layout)
        layout.addWidget(self.progress_bar)
        layout.addLayout(bottom_layout)
        self.setLayout(layout)
        
        # Connections
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.cancel_btn.clicked.connect(self.cancel_download)

    def update_progress(self, bytes_received, bytes_total):
        if bytes_total > 0:
            percent = int((bytes_received / bytes_total) * 100)
            self.progress_bar.setValue(percent)
            if hasattr(self, 'last_update'):
                elapsed = self.last_update.msecsTo(QDateTime.currentDateTime())
                if elapsed > 0:
                    speed = (bytes_received - self.last_bytes) / (elapsed / 1000)
                    self.speed_label.setText(f"{self.format_speed(speed)}")
            self.last_update = QDateTime.currentDateTime()
            self.last_bytes = bytes_received
            self.status_label.setText(
                f"Downloading... {self.format_size(bytes_received)} of {self.format_size(bytes_total)}"
            )
        else:
            self.status_label.setText("Downloading... size unknown")

    def toggle_pause(self):
        if self.download.isPaused():
            self.download.resume()
            self.pause_btn.setText("Pause")
            self.status_label.setText("Resuming download...")
        else:
            self.download.pause()
            self.pause_btn.setText("Resume")
            self.status_label.setText("Download paused")

    def cancel_download(self):
        self.download.cancel()
        self.status_label.setText("Download cancelled")
        self.is_finished = True

    def set_finished(self, finished):
        self.is_finished = finished
        if finished:
            self.pause_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)
            self.status_label.setText("Download complete")
            self.speed_label.clear()

    def set_interrupted(self, reason):
        self.status_label.setText(f"Download failed: {reason}")
        self.is_finished = True

    @staticmethod
    def format_size(bytes_num):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_num < 1024.0:
                return f"{bytes_num:.1f} {unit}"
            bytes_num /= 1024.0
        return f"{bytes_num:.1f} TB"

    @staticmethod
    def format_speed(bytes_per_sec):
        if bytes_per_sec < 1024:
            return f"{bytes_per_sec:.0f} B/s"
        elif bytes_per_sec < 1024 * 1024:
            return f"{bytes_per_sec / 1024:.1f} KB/s"
        else:
            return f"{bytes_per_sec / (1024 * 1024):.1f} MB/s"

class DownloadManager(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Downloads")
        self.resize(600, 400)
        
        # Main layout
        layout = QVBoxLayout()
        self.download_list = QListWidget()
        layout.addWidget(self.download_list)
        
        # Control buttons
        btn_layout = QHBoxLayout()
        self.clear_btn = QPushButton("Clear Finished")
        self.open_folder_btn = QPushButton("Open Download Folder")
        self.close_btn = QPushButton("Close")
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addWidget(self.open_folder_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
        # Connections
        self.clear_btn.clicked.connect(self.clear_finished)
        self.open_folder_btn.clicked.connect(self.open_download_folder)
        self.close_btn.clicked.connect(self.hide)
        
        # Track downloads
        self.downloads = {}
        self.download_dir = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DownloadLocation)
        QDir().mkpath(self.download_dir)

    def download_requested(self, download: QWebEngineDownloadRequest):
        path = f"{self.download_dir}/{download.suggestedFileName()}"
        file_info = QFileInfo(path)
        if file_info.exists():
            base_name = file_info.completeBaseName()
            extension = file_info.suffix()
            counter = 1
            while QFileInfo(f"{self.download_dir}/{base_name}_{counter}.{extension}").exists():
                counter += 1
            path = f"{self.download_dir}/{base_name}_{counter}.{extension}"
        download.setDownloadDirectory(self.download_dir)
        download.setDownloadFileName(QFileInfo(path).fileName())
        download.accept()
        
        item = QListWidgetItem()
        widget = DownloadItem(download)
        item.setSizeHint(widget.sizeHint())
        self.download_list.addItem(item)
        self.download_list.setItemWidget(item, widget)
        self.downloads[download.url().toString()] = (download, item, widget)
        
        # Manually update progress
        widget.update_progress(download.receivedBytes(), download.totalBytes())
        
        # Connect the finished signal
        download.finished.connect(lambda: self.download_finished(download))
        self.show()

    def download_finished(self, download):
        _, item, widget = self.downloads[download.url().toString()]
        widget.set_finished(download.isFinished())
        if download.state() == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
            widget.set_interrupted(download.interruptReasonString())

    def clear_finished(self):
        for i in reversed(range(self.download_list.count())):
            item = self.download_list.item(i)
            widget = self.download_list.itemWidget(item)
            if widget and widget.is_finished:
                self.download_list.takeItem(i)

    def open_download_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.download_dir))

class BrowserTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl("https://www.google.com"))
        
        # Navigation toolbar
        self.navbar = QToolBar()
        self.back_btn = QPushButton("←")
        self.forward_btn = QPushButton("→")
        self.reload_btn = QPushButton("↻")
        self.home_btn = QPushButton("⌂")
        self.url_bar = QLineEdit()
        self.go_btn = QPushButton("Go")
        
        # Add buttons to toolbar
        self.navbar.addWidget(self.back_btn)
        self.navbar.addWidget(self.forward_btn)
        self.navbar.addWidget(self.reload_btn)
        self.navbar.addWidget(self.home_btn)
        self.navbar.addWidget(self.url_bar)
        self.navbar.addWidget(self.go_btn)
        
        # Connect signals
        self.back_btn.clicked.connect(self.browser.back)
        self.forward_btn.clicked.connect(self.browser.forward)
        self.reload_btn.clicked.connect(self.browser.reload)
        self.home_btn.clicked.connect(self.navigate_home)
        self.go_btn.clicked.connect(self.navigate_to_url)
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        self.browser.urlChanged.connect(self.update_url)
        
        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.navbar)
        layout.addWidget(self.browser)
        self.setLayout(layout)
    
    def navigate_home(self):
        self.browser.setUrl(QUrl("https://www.google.com"))
    
    def navigate_to_url(self):
        url = self.url_bar.text()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        self.browser.setUrl(QUrl(url))
    
    def update_url(self, q):
        self.url_bar.setText(q.toString())

class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QtCelestial - NIGHTTIME")
        self.setWindowIcon(QIcon("/home/good-girl/Desktop/QtCelestial/masturbini.jpeg"))
        
        # Create tab widget
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        
        # Download manager
        self.download_manager = DownloadManager(self)
        
        # Add initial tab
        self.add_new_tab(QUrl("https://www.google.com"), "Home")
        
        # Navigation buttons for tabs
        self.new_tab_btn = QPushButton("+")
        self.new_tab_btn.clicked.connect(lambda: self.add_new_tab())
        self.tabs.setCornerWidget(self.new_tab_btn)
        
        # Menu bar
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        
        new_tab_action = QAction("New Tab", self)
        new_tab_action.triggered.connect(lambda: self.add_new_tab())
        file_menu.addAction(new_tab_action)
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Add "Downloads" button to menu
        tools_menu = menubar.addMenu("&Tools")
        downloads_action = QAction("Downloads", self)
        downloads_action.triggered.connect(self.download_manager.show)
        tools_menu.addAction(downloads_action)
        
        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        
        # Set central widget
        self.setCentralWidget(self.tabs)
    
    def add_new_tab(self, qurl=None, label="New Tab"):
        if qurl is None:
            qurl = QUrl("https://www.google.com")
        
        tab = BrowserTab(self)
        tab.browser.setUrl(qurl)
        
        i = self.tabs.addTab(tab, label)
        self.tabs.setCurrentIndex(i)
        
        tab.browser.titleChanged.connect(lambda title, tab=tab: self.update_tab_title(tab, title))
        tab.browser.page().profile().downloadRequested.connect(
            self.download_manager.download_requested
        )
    
    def update_tab_title(self, tab, title):
        idx = self.tabs.indexOf(tab)
        self.tabs.setTabText(idx, title[:15] + "...")
    
    def close_tab(self, i):
        if self.tabs.count() < 2:
            return
            
        self.tabs.removeTab(i)

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PyQt6 Browser")
    
    window = Browser()
    window.showMaximized()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
