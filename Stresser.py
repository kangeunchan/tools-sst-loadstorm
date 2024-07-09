import sys
import requests
import concurrent.futures
import time
import pandas as pd
import matplotlib.pyplot as plt
from collections import Counter
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QTextEdit, QProgressBar, QDialog, QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import pyqtSignal, QThread
from PyQt6.QtGui import QPixmap

class StressTestThread(QThread):
    progress = pyqtSignal(int)
    result = pyqtSignal(str)
    image_ready = pyqtSignal(str, str)
    detailed_results = pyqtSignal(pd.DataFrame)

    def __init__(self, url, num_requests, num_threads, max_retries, timeout):
        super().__init__()
        self.url = url
        self.num_requests = num_requests
        self.num_threads = num_threads
        self.max_retries = max_retries
        self.timeout = timeout

    def run(self):
        url = self.url
        num_requests = self.num_requests
        num_threads = self.num_threads
        max_retries = self.max_retries
        timeout = self.timeout

        def send_request(url):
            for _ in range(max_retries):
                try:
                    start_time = time.time()
                    response = requests.get(url, timeout=timeout)
                    end_time = time.time()
                    duration = end_time - start_time
                    return (response.status_code, duration, None)
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError,
                        requests.exceptions.HTTPError, requests.exceptions.TooManyRedirects,
                        requests.exceptions.RequestException) as e:
                    end_time = time.time()
                    duration = end_time - start_time
                    last_exception = str(e)
            return (None, duration, last_exception)

        start_time = time.time()
        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(send_request, url) for _ in range(num_requests)]

            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                results.append(future.result())
                self.progress.emit(int((i + 1) / num_requests * 100))

        end_time = time.time()
        duration = end_time - start_time

        response_times = [result[1] for result in results]
        status_codes = [result[0] for result in results if result[0] is not None]
        errors = [result[2] for result in results if result[2] is not None]

        status_code_counts = Counter(status_codes)
        error_counts = Counter(errors)

        response_time_series = pd.Series(response_times)
        average_response_time = response_time_series.mean()
        max_response_time = response_time_series.max()
        min_response_time = response_time_series.min()
        response_time_std_dev = response_time_series.std()
        percentile_95 = response_time_series.quantile(0.95)

        successful_requests = status_code_counts.get(200, 0)
        failed_requests = num_requests - successful_requests

        result_text = (
            f"총 요청 수: {num_requests}\n"
            f"보낸 요청 수: {len(results)}\n"
            f"성공 요청 수: {successful_requests}\n"
            f"실패 요청 수: {failed_requests}\n"
            f"성공 비율: {successful_requests / num_requests * 100:.2f}%\n"
            f"실패 비율: {failed_requests / num_requests * 100:.2f}%\n"
            f"테스트 소요 시간: {duration:.2f}초\n"
            f"초당 요청 처리 수: {num_requests / duration:.2f} req/sec\n"
            f"평균 응답 시간: {average_response_time:.4f}초\n"
            f"최대 응답 시간: {max_response_time:.4f}초\n"
            f"최소 응답 시간: {min_response_time:.4f}초\n"
            f"응답 시간 표준 편차: {response_time_std_dev:.4f}초\n"
            f"95번째 백분위수 응답 시간: {percentile_95:.4f}초\n"
            "\n상태 코드별 요청 수 및 비율:\n"
        )
        for status, count in status_code_counts.items():
            result_text += f"  {status}: {count}회 ({count / num_requests * 100:.2f}%)\n"

        if errors:
            result_text += "\n오류 메시지 및 비율:\n"
            for error, count in error_counts.items():
                result_text += f"  {error}: {count}회 ({count / num_requests * 100:.2f}%)\n"

        df = pd.DataFrame(results, columns=['Status_Code', 'Response_Time', 'Error'])
        df.to_csv('stress_test_results.csv', index=False)
        result_text += "\n결과가 'stress_test_results.csv' 파일로 저장되었습니다."

        plt.figure(figsize=(10, 6))
        plt.hist(response_times, bins=50, edgecolor='k')
        plt.xscale('log')
        plt.title('Response Time Distribution')
        plt.xlabel('Response Time (s)')
        plt.ylabel('Frequency')
        plt.grid(True)
        plt.savefig('response_time_distribution.png')
        plt.close()
        result_text += "\n응답 시간 분포 그래프가 'response_time_distribution.png' 파일로 저장되었습니다."

        self.result.emit(result_text)
        self.image_ready.emit('response_time_distribution.png', '응답 시간 분포 그래프')
        self.detailed_results.emit(df)

class ResultDialog(QDialog):
    def __init__(self, result_text, image_path, image_title, detailed_results, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Test Results')

        self.result_text_edit = QTextEdit()
        self.result_text_edit.setReadOnly(True)
        self.result_text_edit.setText(result_text)

        self.image_label = QLabel()
        pixmap = QPixmap(image_path)
        self.image_label.setPixmap(pixmap)
        self.image_label.setScaledContents(True)

        self.table = QTableWidget()
        self.table.setRowCount(detailed_results.shape[0])
        self.table.setColumnCount(detailed_results.shape[1])
        self.table.setHorizontalHeaderLabels(detailed_results.columns)
        for i in range(detailed_results.shape[0]):
            for j in range(detailed_results.shape[1]):
                self.table.setItem(i, j, QTableWidgetItem(str(detailed_results.iat[i, j])))

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)

        self.search_input = QLineEdit()
        self.search_button = QPushButton('Search')
        self.search_button.clicked.connect(self.search_table)

        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel('Search:'))
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.image_label)

        layout = QVBoxLayout()
        layout.addWidget(self.result_text_edit)
        layout.addWidget(QLabel(image_title))
        layout.addWidget(scroll_area)
        layout.addLayout(search_layout)
        layout.addWidget(QLabel('Detailed Results:'))
        layout.addWidget(self.table)

        self.setLayout(layout)
        self.resize(800, 600)

    def search_table(self):
        search_text = self.search_input.text().lower()
        for i in range(self.table.rowCount()):
            row_hidden = True
            for j in range(self.table.columnCount()):
                item = self.table.item(i, j)
                if search_text in item.text().lower():
                    row_hidden = False
                    break
            self.table.setRowHidden(i, row_hidden)

class StressTestApp(QWidget):
    def __init__(self):
        super().__init__()

        self.initUI()

    def initUI(self):
        self.setWindowTitle('Stress Test Application')

        self.url_label = QLabel('목표 주소 입력:')
        self.url_input = QLineEdit()

        self.num_requests_label = QLabel('요청 개수 입력 (기본 : 10000):')
        self.num_requests_input = QLineEdit()

        self.num_threads_label = QLabel('스레드 개수 입력 (기본 : 10):')
        self.num_threads_input = QLineEdit()

        self.max_retries_label = QLabel('재시도 횟수 입력 (기본 : 3):')
        self.max_retries_input = QLineEdit()

        self.timeout_label = QLabel('타임아웃 시간 입력 (기본 : 1):')
        self.timeout_input = QLineEdit()

        self.progress_bar = QProgressBar()

        self.start_button = QPushButton('Start Test')
        self.start_button.clicked.connect(self.start_test)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)

        layout = QVBoxLayout()
        layout.addWidget(self.url_label)
        layout.addWidget(self.url_input)
        layout.addWidget(self.num_requests_label)
        layout.addWidget(self.num_requests_input)
        layout.addWidget(self.num_threads_label)
        layout.addWidget(self.num_threads_input)
        layout.addWidget(self.max_retries_label)
        layout.addWidget(self.max_retries_input)
        layout.addWidget(self.timeout_label)
        layout.addWidget(self.timeout_input)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.start_button)
        layout.addWidget(self.log_output)

        self.setLayout(layout)

    def start_test(self):
        url = self.url_input.text()
        try:
            num_requests = int(self.num_requests_input.text()) if self.num_requests_input.text() else 10000
            num_threads = int(self.num_threads_input.text()) if self.num_threads_input.text() else 10
            max_retries = int(self.max_retries_input.text()) if self.max_retries_input.text() else 3
            timeout = int(self.timeout_input.text()) if self.timeout_input.text() else 1
        except ValueError:
            self.log_output.append("입력 값이 유효하지 않습니다. 숫자를 입력하세요.")
            return

        self.thread = StressTestThread(url, num_requests, num_threads, max_retries, timeout)
        self.thread.progress.connect(self.update_progress)
        self.thread.result.connect(self.display_result)
        self.thread.image_ready.connect(self.show_image)
        self.thread.detailed_results.connect(self.show_detailed_results)
        self.thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def display_result(self, result_text):
        self.log_output.append(result_text)

    def show_image(self, image_path, image_title):
        self.image_path = image_path
        self.image_title = image_title

    def show_detailed_results(self, detailed_results):
        dialog = ResultDialog(self.log_output.toPlainText(), self.image_path, self.image_title, detailed_results, self)
        dialog.exec()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = StressTestApp()
    ex.show()
    sys.exit(app.exec())
