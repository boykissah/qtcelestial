import sys
import logging
from datetime import datetime
from PyQt6.QtCore import QUrl, QFileInfo, QDir, QStandardPaths, QDateTime, QTimer
from PyQt6.QtGui import QIcon, QAction, QDesktopServices
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget, 
    QLineEdit, QHBoxLayout, QPushButton, QToolBar, QStatusBar, 
    QLabel, QProgressBar, QListWidget, QListWidgetItem
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineDownloadRequest, QWebEngineSettings
from PyQt6.QtCore import QByteArray, QSettings, QDateTime
import json
import os
import pickle
from PyQt6.QtNetwork import QNetworkCookie, QNetworkProxy
import socket

# Set up logging
logging.basicConfig(
    filename=f'browser_debug_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def is_url(input_str):
    """Check if the input should be treated as a URL"""
    domain_extensions = {
        '.com', '.onion', '.org', '.net', '.info', '.biz', '.edu', '.gov',
        '.mil', '.pro', '.name', '.aero', '.asia', '.cat', '.coop',
        '.jobs', '.mobi', '.museum', '.tel', '.travel', '.us', '.uk',
        '.ca', '.au', '.de', '.fr', '.cn', '.in', '.jp', '.app',
        '.blog', '.club', '.design', '.dev', '.guru', '.tech', '.xyz',
        '.shop', '.online'
    }
    
    input_lower = input_str.lower()
    
    # Check if it starts with http/https or www
    if input_lower.startswith(('http://', 'https://', 'www.')):
        return True
    
    # Check if it ends with any known domain extension
    return any(input_lower.endswith(ext) for ext in domain_extensions)

def process_input(input_str):
    """Process input and return either URL or search URL"""
    if is_url(input_str):
        if not input_str.startswith(('http://', 'https://')):
            return f'https://{input_str}'
        return input_str
    else:
        return f'https://www.google.com/search?q={input_str.replace(" ", "+")}'
class DownloadItem(QWidget):
    def __init__(self, download, parent=None):
        super().__init__(parent)
        logging.debug(f"Initializing download for: {download.suggestedFileName()}")
        self.download = download
        self.is_finished = False

        # Initialize last_update and last_bytes
        self.last_update = QDateTime.currentDateTime()
        self.last_bytes = 0

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

        # Bottom row (status, speed, and time left)
        bottom_layout = QHBoxLayout()
        self.status_label = QLabel("Starting download...")
        self.speed_label = QLabel()
        self.time_left_label = QLabel()
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.speed_label)
        bottom_layout.addWidget(self.time_left_label)

        # Add to main layout
        layout.addLayout(top_layout)
        layout.addWidget(self.progress_bar)
        layout.addLayout(bottom_layout)
        self.setLayout(layout)

        # Connections
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.cancel_btn.clicked.connect(self.cancel_download)

        # Connect download progress signals
        self.download.receivedBytesChanged.connect(self.update_progress)
        self.download.totalBytesChanged.connect(self.update_progress)
        logging.debug(f"Connected download progress signals for {download.suggestedFileName()}")

    def update_progress(self):
        bytes_received = self.download.receivedBytes()
        bytes_total = self.download.totalBytes()
        try:
            logging.debug(f"update_progress called: bytes_received={bytes_received}, bytes_total={bytes_total}")
            if bytes_total > 0:
                percent = int((bytes_received / bytes_total) * 100)
                self.progress_bar.setValue(percent)

                # Calculate speed and time left
                elapsed = self.last_update.msecsTo(QDateTime.currentDateTime())
                if elapsed > 0:
                    speed = (bytes_received - self.last_bytes) / (elapsed / 1000)
                    self.speed_label.setText(f"{self.format_speed(speed)}")

                    # Calculate time left
                    remaining_bytes = bytes_total - bytes_received
                    if speed > 0:
                        time_left = remaining_bytes / speed
                        self.time_left_label.setText(f"Time left: {self.format_time(time_left)}")
                    else:
                        self.time_left_label.setText("Time left: Calculating...")

                self.last_update = QDateTime.currentDateTime()
                self.last_bytes = bytes_received
                self.status_label.setText(
                    f"Downloading... {self.format_size(bytes_received)} of {self.format_size(bytes_total)}"
                )
                logging.debug(f"Download progress: {percent}% - Speed: {self.speed_label.text()} - Time left: {self.time_left_label.text()}")
            else:
                self.status_label.setText("Downloading... size unknown")
        except Exception as e:
            logging.error(f"Error updating progress: {str(e)}")

    def toggle_pause(self):
        try:
            if self.download.isPaused():
                logging.info(f"Resuming download: {self.download.suggestedFileName()}")
                self.download.resume()
                self.pause_btn.setText("Pause")
                self.status_label.setText("Resuming download...")
            else:
                logging.info(f"Pausing download: {self.download.suggestedFileName()}")
                self.download.pause()
                self.pause_btn.setText("Resume")
                self.status_label.setText("Download paused")
        except Exception as e:
            logging.error(f"Error toggling pause: {str(e)}")

    def cancel_download(self):
        logging.info(f"Cancelling download: {self.download.suggestedFileName()}")
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
            self.time_left_label.clear()

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

    @staticmethod
    def format_time(seconds):
        """Format time in seconds to a human-readable format."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            seconds = int(seconds % 60)
            return f"{minutes}m {seconds}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

class DownloadManager(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download Manager")
        self.setGeometry(100, 100, 600, 400)
        
        self.download_list = QListWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.download_list)
        
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
    
    def add_download(self, download_item):
        item = QListWidgetItem()
        item.setSizeHint(download_item.sizeHint())
        self.download_list.addItem(item)
        self.download_list.setItemWidget(item, download_item)

class BrowserTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.browser = QWebEngineView()
        self.load_timeout = 30000  # 30 seconds
        self.retry_count = 0
        self.max_retries = 3
        self.loading_timer = QTimer(self)
        self.loading_timer.setSingleShot(True)
        self.loading_timer.timeout.connect(self.on_load_timeout)
        
        # Enable Widevine DRM
        settings = self.browser.settings()
        settings.setAttribute(settings.WebAttribute.PlaybackRequiresUserGesture, False)
        settings.setAttribute(settings.WebAttribute.FullScreenSupportEnabled, True)
        self.browser.page().fullScreenRequested.connect(lambda request: request.accept())
        
        # Enable JavaScript and Local Storage
        settings = self.browser.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        
        # Accept all cookies
        profile = self.browser.page().profile()
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
        
        self.browser.setUrl(QUrl("https://www.google.com"))
        
        # Navigation toolbar
        self.navbar = QToolBar()
        self.back_btn = QPushButton("←")
        self.forward_btn = QPushButton("→")
        self.reload_btn = QPushButton("↻")
        self.home_btn = QPushButton("⌂")
        self.url_bar = QLineEdit()
        self.go_btn = QPushButton("Go")
        self.search_btn = QPushButton("🔍")
        self.zoom_in_btn = QPushButton("Zoom In")
        self.zoom_out_btn = QPushButton("Zoom Out")
        
        # Add buttons to toolbar
        self.navbar.addWidget(self.back_btn)
        self.navbar.addWidget(self.forward_btn)
        self.navbar.addWidget(self.reload_btn)
        self.navbar.addWidget(self.home_btn)
        self.navbar.addWidget(self.url_bar)
        self.navbar.addWidget(self.go_btn)
        self.navbar.addWidget(self.search_btn)
        self.navbar.addWidget(self.zoom_in_btn)
        self.navbar.addWidget(self.zoom_out_btn)
        
        # Connect signals
        self.back_btn.clicked.connect(self.browser.back)
        self.forward_btn.clicked.connect(self.browser.forward)
        self.reload_btn.clicked.connect(self.browser.reload)
        self.home_btn.clicked.connect(self.navigate_home)
        self.go_btn.clicked.connect(self.navigate_to_url)
        self.search_btn.clicked.connect(self.search_in_address_bar)
        self.zoom_in_btn.clicked.connect(lambda: self.browser.setZoomFactor(self.browser.zoomFactor() + 0.1))
        self.zoom_out_btn.clicked.connect(lambda: self.browser.setZoomFactor(self.browser.zoomFactor() - 0.1))
        self.url_bar.returnPressed.connect(self.search_in_address_bar)
        self.browser.urlChanged.connect(self.update_url)
        # Connect loadFinished signal to handle failures
        self.browser.loadFinished.connect(self.handle_load_finished)
        self.browser.loadStarted.connect(self.on_load_started)
        
        # Handle SSL errors
        self.browser.page().certificateError.connect(self.handle_certificate_error)
        
        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.navbar)
        layout.addWidget(self.browser)
        self.setLayout(layout)
    
    def navigate_home(self):
        self.browser.setUrl(QUrl("https://www.google.com"))
    
    def navigate_to_url(self):
        input_text = self.url_bar.text().strip()
        url = QUrl(process_input(input_text))
        self.browser.setUrl(url)
        self.retry_count = 0
    
    def search_in_address_bar(self):
        input_text = self.url_bar.text().strip()
        url = QUrl(process_input(input_text))
        self.browser.setUrl(url)
    
    def update_url(self, q):
        self.url_bar.setText(q.toString())
    
    def on_load_started(self):
        self.loading_timer.start(self.load_timeout)
    
    def on_load_timeout(self):
        logging.warning(f"Load timeout reached for {self.browser.url().toString()}")
        self.browser.stop()
        self.try_reload()
    
    def handle_load_finished(self, ok):
        self.loading_timer.stop()
        if not ok:
            logging.error(f"Failed to load {self.browser.url().toString()}")
            self.try_reload()
            error_html = """
            <html>
                <head>
                    <style>
                        body { font-family: Arial, sans-serif; text-align: center; padding-top: 50px; background-color: #f2f2f2; }
                        h1 { color: #d32f2f; }
                        p { color: #555; }
                    </style>
                    <title>Page Not Available</title>
                </head>
                <body>
                    <h1>Page Not Available</h1>
                    <p>The webpage could not be loaded. Please check the URL or your connection.</p>
                    <p>Tor connections can be slow or blocked. Please try again or use a different search engine.</p>
                </body>
            </html>
            """
            self.browser.setHtml(error_html)
            
    def handle_certificate_error(self, certificate, error):
        logging.warning(f"SSL Certificate Error: {error}")
        self.browser.page().certificateError.disconnect(self.handle_certificate_error)
        self.browser.page().profile().setHttpsAcceptAnyCertificate(True)
        self.browser.reload()
    
    def try_reload(self):
        if self.retry_count < self.max_retries:
            self.retry_count += 1
            logging.info(f"Retrying to load page ({self.retry_count}/{self.max_retries})")
            self.browser.reload()
        else:
            logging.error(f"Max retries reached for {self.browser.url().toString()}")

class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        logging.info("Initializing browser")
        self.setWindowTitle("QtCelestial - Masturbini Mode")
        self.setWindowIcon(QIcon("/home/good-girl/Desktop/QtCelestial/masturbini.jpeg"))
        
        # Tor-related attributes
        self.tor_enabled = False

        # Cookie related initialization
        self.cookie_file = self.get_cookie_path()
        self.cookies = set()  # Store cookies in memory
        
        # Create tab widget
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        
        # Add initial tab
        self.add_new_tab(QUrl("https://www.google.com"), "Home")
        
        # Now setup cookie store after tab is created
        current_tab = self.tabs.currentWidget()
        if current_tab:
            self.cookie_store = current_tab.browser.page().profile().cookieStore()
            self.cookie_store.cookieAdded.connect(self.on_cookie_added)
            self.cookie_store.cookieRemoved.connect(self.on_cookie_removed)
            
            # Enable persistent cookies
            current_tab.browser.page().profile().setPersistentStoragePath(
                os.path.join(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation), "browser-profile")
            )
        
        # Load cookies
        self.load_cookies()
        
        # Navigation buttons for tabs
        self.new_tab_btn = QPushButton("+")
        self.new_tab_btn.clicked.connect(lambda: self.add_new_tab())
        self.tabs.setCornerWidget(self.new_tab_btn)
        
        # Menu bar
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        new_tab_action = QAction("New Tab", self)
        new_tab_action.triggered.connect(lambda: self.add_new_tab())
        file_menu.addAction(new_tab_action)
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Security menu
        security_menu = menubar.addMenu("&Security")
        clear_cookies_action = QAction("Clear Cookies", self)
        clear_cookies_action.triggered.connect(self.clear_cookies)
        security_menu.addAction(clear_cookies_action)
        
        toggle_tor_action = QAction("Toggle Tor", self)
        toggle_tor_action.triggered.connect(self.toggle_tor)
        security_menu.addAction(toggle_tor_action)
        
        # Downloads menu
        downloads_menu = menubar.addMenu("&Downloads")
        show_downloads_action = QAction("Show Downloads", self)
        show_downloads_action.triggered.connect(self.show_download_manager)
        downloads_menu.addAction(show_downloads_action)
        
        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        # Add Tor indicator label to status bar
        self.tor_indicator = QLabel("TOR")
        self.tor_indicator.setStyleSheet("color: red; font-weight: bold;")
        self.tor_indicator.setVisible(False)
        self.status.addPermanentWidget(self.tor_indicator)
        
        # Download manager
        self.download_manager = DownloadManager(self)
        
        # Set central widget
        self.setCentralWidget(self.tabs)
        
        # Set default download directory
        self.default_download_dir = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DownloadLocation
        )
        
        # Connect download handler
        self.connect_download_handler()

    def get_cookie_path(self):
        """Get path to store cookies"""
        data_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        if not data_path:
            data_path = QDir.currentPath()
        
        cookie_path = os.path.join(data_path, "browser-profile", "cookies")
        os.makedirs(cookie_path, exist_ok=True)
        return os.path.join(cookie_path, "cookies.dat")

    def cookie_to_string(self, cookie):
        """Convert a QNetworkCookie to a string representation."""
        return f"{cookie.name().data().decode()};{cookie.value().data().decode()};{cookie.domain()};{cookie.path()}"

    def on_cookie_added(self, cookie):
        """Handle new cookies"""
        self.cookies.add(self.cookie_to_string(cookie))

    def on_cookie_removed(self, cookie):
        """Handle removed cookies"""
        self.cookies.discard(self.cookie_to_string(cookie))

    def load_cookies(self):
        """Load cookies from file"""
        try:
            logging.debug(f"Attempting to load cookies from: {self.cookie_file}")
            
            # Check if cookie file exists
            if not os.path.exists(self.cookie_file):
                logging.warning(f"Cookie file does not exist at: {self.cookie_file}")
                return

            # Check file size
            file_size = os.path.getsize(self.cookie_file)
            logging.debug(f"Cookie file size: {file_size} bytes")
            
            if file_size == 0:
                logging.warning("Cookie file exists but is empty")
                return

            with open(self.cookie_file, 'rb') as f:
                stored_cookies = pickle.load(f)
                cookie_count = len(stored_cookies)
                logging.debug(f"Found {cookie_count} cookies in file")
                
                if cookie_count == 0:
                    logging.warning("No cookies found in file")
                    return
                    
                for cookie_str in stored_cookies:
                    try:
                        name, value, domain, path = cookie_str.split(';', 3)
                        cookie = QNetworkCookie(name.encode(), value.encode())
                        cookie.setDomain(domain)
                        cookie.setPath(path)
                        self.cookie_store.setCookie(cookie)
                        logging.debug(f"Loaded cookie: domain={domain}, path={path}")
                    except Exception as ce:
                        logging.error(f"Failed to parse cookie: {cookie_str}, error: {str(ce)}")
                
                logging.info(f"Successfully loaded {cookie_count} cookies")
        except (FileNotFoundError, EOFError, pickle.PickleError) as e:
            logging.error(f"Error loading cookies: {str(e)}")
            # Try to recover old cookies from backup if it exists
            backup_file = f"{self.cookie_file}.bak"
            if os.path.exists(backup_file):
                logging.info("Attempting to restore cookies from backup")
                try:
                    with open(backup_file, 'rb') as f:
                        self.cookies = set(pickle.load(f))
                    logging.info("Restored cookies from backup")
                except Exception as be:
                    logging.error(f"Failed to restore from backup: {str(be)}")
        except Exception as e:
            logging.error(f"Unexpected error loading cookies: {str(e)}")

    def save_cookies(self):
        """Save cookies to file with backup"""
        try:
            # Create backup of existing cookie file
            if os.path.exists(self.cookie_file):
                backup_file = f"{self.cookie_file}.bak"
                try:
                    os.replace(self.cookie_file, backup_file)
                    logging.debug("Created backup of existing cookie file")
                except Exception as e:
                    logging.warning(f"Failed to create cookie backup: {str(e)}")

            # Save new cookies
            with open(self.cookie_file, 'wb') as f:
                cookie_list = list(self.cookies)
                pickle.dump(cookie_list, f)
                logging.info(f"Successfully saved {len(cookie_list)} cookies")
        except Exception as e:
            logging.error(f"Failed to save cookies: {str(e)}")

    def closeEvent(self, event):
        """Handle browser closing"""
        try:
            self.save_cookies()
            self.stop_tor()
        except Exception as e:
            logging.error(f"Error during close event: {e}")
        super().closeEvent(event)

    def connect_download_handler(self):
        try:
            profile = self.tabs.currentWidget().browser.page().profile()
        
            profile.downloadRequested.connect(self.on_download_requested)
            logging.debug("Download handler connected")
        except Exception as e:
            logging.error(f"Failed to connect download handler: {str(e)}")

    def on_download_requested(self, download):
        logging.info(f"Download requested: {download.suggestedFileName()}")
        try:
            # Set download path
            suggested_filename = download.suggestedFileName()
            download_path = os.path.join(self.default_download_dir, suggested_filename)
            
            # Handle existing file
            counter = 1
            while os.path.exists(download_path):
                name, ext = os.path.splitext(suggested_filename)
                download_path = os.path.join(self.default_download_dir, f"{name} ({counter}){ext}")
                counter += 1
            
            download.setDownloadDirectory(self.default_download_dir)
            download.setDownloadFileName(os.path.basename(download_path))
            
            # Create download item and add to manager
            download_item = DownloadItem(download)
            self.download_manager.add_download(download_item)
            
            # Accept the download
            download.accept()
            
            logging.debug(f"Download started: {download_path}")
        except Exception as e:
            logging.error(f"Download failed to start: {str(e)}")

    def show_download_manager(self):
        logging.debug("Opening download manager")
        self.download_manager.show()
        self.download_manager.raise_()
        self.download_manager.activateWindow()

    def add_new_tab(self, qurl=None, label="New Tab"):
        logging.debug(f"Adding new tab with URL: {qurl}")
        if qurl is None:
            qurl = QUrl("https://www.google.com")
        
        tab = BrowserTab(self)
        tab.browser.setUrl(qurl)
        
        i = self.tabs.addTab(tab, label)
        self.tabs.setCurrentIndex(i)
        
        tab.browser.titleChanged.connect(lambda title, tab=tab: self.update_tab_title(tab, title))
    
    def update_tab_title(self, tab, title):
        idx = self.tabs.indexOf(tab)
        self.tabs.setTabText(idx, title[:15] + "...")
    
    def close_tab(self, i):
        if self.tabs.count() < 2:
            return
            
        self.tabs.removeTab(i)

    def clear_cookies(self):
        """Clear all cookies"""
        logging.info("Clearing all cookies")
        self.cookie_store.deleteAllCookies()
        self.cookies.clear()
        self.save_cookies()
        self.status.showMessage("Cookies cleared!", 5000)

    def toggle_tor(self):
        """Toggle Tor proxy and reload all tabs."""
        if self.tor_enabled:
            self.stop_tor()
        else:
            self.start_tor()

    def start_tor(self):
        """Connect to external Tor SOCKS5 proxy."""
        try:
            # Test if Tor SOCKS5 proxy is available
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', 9050))
            sock.close()
            
            if result != 0:
                raise Exception("Tor SOCKS5 proxy not found on port 9050. Please start Tor first.")
            
            logging.info("Connecting to external Tor SOCKS5 proxy")
            self.tor_enabled = True
            self.tor_indicator.setVisible(True)
            self.setWindowTitle("QtCelestial - EVENING [TOR]")
            self.set_tor_proxy()
            self.status.showMessage("Tor enabled. Tor connections might be slower. Please be patient.", 10000)
        except Exception as e:
            logging.error(f"Failed to connect to Tor: {e}")
            self.status.showMessage(f"Failed to connect to Tor: {e}", 5000)

    def stop_tor(self):
        """Disconnect from Tor proxy."""
        try:
            logging.info("Disconnecting from Tor proxy")
            self.tor_enabled = False
            self.tor_indicator.setVisible(False)
            self.setWindowTitle("QtCelestial - EVENING")
            self.clear_tor_proxy()
            self.status.showMessage("Tor disabled", 5000)
        except Exception as e:
            logging.error(f"Failed to disconnect from Tor: {e}")
            self.status.showMessage(f"Failed to disconnect from Tor: {e}", 5000)

    def set_tor_proxy(self):
        """Set Tor proxy for all tabs."""
        try:
            proxy = QNetworkProxy()
            proxy.setType(QNetworkProxy.ProxyType.Socks5Proxy)
            proxy.setHostName("127.0.0.1")
            proxy.setPort(9050)
            QNetworkProxy.setApplicationProxy(proxy)
            logging.info("Tor proxy set successfully")
        except Exception as e:
            logging.error(f"Failed to set Tor proxy: {e}")

    def clear_tor_proxy(self):
        """Clear Tor proxy settings."""
        try:
            QNetworkProxy.setApplicationProxy(QNetworkProxy())
            logging.info("Tor proxy cleared")
        except Exception as e:
            logging.error(f"Failed to clear Tor proxy: {e}")

def main():
    try:
        logging.info("Starting application")
        app = QApplication(sys.argv)  # Ensure `app` is defined here
        app.setApplicationName("Evening")
        
        window = Browser()
        window.showMaximized()
        
        sys.exit(app.exec())
    except Exception as e:
        logging.critical(f"Application failed to start: {str(e)}")
        raise

if __name__ == "__main__":
    main()
