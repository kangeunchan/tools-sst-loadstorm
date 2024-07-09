import requests
import concurrent.futures
import time
import pandas as pd
import matplotlib.pyplot as plt
from collections import Counter
from tqdm import tqdm
import socket
from requests.exceptions import RequestException

url = "http://192.168.1.25:8084"
num_requests = 100000
num_threads = 100
max_retries = 3
timeout = 1

def send_request(url):
    for _ in range(max_retries):
        try:
            start_time = time.time()
            response = requests.get(url, timeout=timeout)
            end_time = time.time()
            duration = end_time - start_time
            return (response.status_code, duration, None)
        except (requests.exceptions.Timeout, socket.timeout) as e:
            end_time = time.time()
            duration = end_time - start_time
            last_exception = 'Timeout'
        except requests.exceptions.ConnectionError as e:
            end_time = time.time()
            duration = end_time - start_time
            last_exception = 'ConnectionError'
        except requests.exceptions.HTTPError as e:
            end_time = time.time()
            duration = end_time - start_time
            last_exception = 'HTTPError'
        except requests.exceptions.TooManyRedirects as e:
            end_time = time.time()
            duration = end_time - start_time
            last_exception = 'TooManyRedirects'
        except socket.error as e:
            end_time = time.time()
            duration = end_time - start_time
            last_exception = 'SocketError'
        except RequestException as e:
            end_time = time.time()
            duration = end_time - start_time
            last_exception = str(e)
    return (None, duration, last_exception)

# 스트레스 테스트 함수입니다.
def stress_test(url, num_requests, num_threads):
    start_time = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(send_request, url) for _ in range(num_requests)]

        results = []
        for future in tqdm(concurrent.futures.as_completed(futures), total=num_requests):
            results.append(future.result())

    end_time = time.time()
    duration = end_time - start_time

    response_times = [result[1] for result in results]
    status_codes = [result[0] for result in results if result[0] is not None]
    errors = [result[2] for result in results if result[2] is not None]

    status_code_counts = Counter(status_codes)

    response_time_series = pd.Series(response_times)
    average_response_time = response_time_series.mean()
    max_response_time = response_time_series.max()
    min_response_time = response_time_series.min()
    response_time_std_dev = response_time_series.std()
    percentile_95 = response_time_series.quantile(0.95)

    print(f"총 요청 수: {num_requests}")
    print(f"보낸 요청 수: {len(results)}")
    print(f"성공 요청 수: {status_code_counts.get(200, 0)}")
    print(f"실패 요청 수: {num_requests - status_code_counts.get(200, 0)}")
    print(f"테스트 소요 시간: {duration:.2f}초")
    print(f"초당 요청 처리 수: {num_requests / duration:.2f} req/sec")
    print(f"평균 응답 시간: {average_response_time:.4f}초")
    print(f"최대 응답 시간: {max_response_time:.4f}초")
    print(f"최소 응답 시간: {min_response_time:.4f}초")
    print(f"응답 시간 표준 편차: {response_time_std_dev:.4f}초")
    print(f"95번째 백분위수 응답 시간: {percentile_95:.4f}초")

    print("\n상태 코드별 요청 수:")
    for status, count in status_code_counts.items():
        print(f"  {status}: {count}회")

    if errors:
        print("\n오류 메시지:")
        error_counts = Counter(errors)
        for error, count in error_counts.items():
            print(f"  {error}: {count}회")

    df = pd.DataFrame(results, columns=['Status_Code', 'Response_Time', 'Error'])
    df.to_csv('stress_test_results.csv', index=False)
    print("\n결과가 'stress_test_results.csv' 파일로 저장되었습니다.")

    plt.figure(figsize=(10, 6))
    plt.hist(response_times, bins=50, edgecolor='k')
    plt.xscale('log')
    plt.title('Response Time Distribution')
    plt.xlabel('Response Time (s)')
    plt.ylabel('Frequency')
    plt.grid(True)
    plt.savefig('response_time_distribution.png')
    print("\n응답 시간 분포 그래프가 'response_time_distribution.png' 파일로 저장되었습니다.")
    plt.show()

if __name__ == "__main__":
    stress_test(url, num_requests, num_threads)
