from concurrent.futures import ThreadPoolExecutor

from tvscreener_ext.screeners.metadata_utils import MetadataCollector


def test_metadata_collector_thread_safety():
    num_threads = 10
    calls_per_thread = 100
    total_expected = (num_threads * calls_per_thread) * 2
    collector = MetadataCollector(max_api_calls=total_expected)

    def add_calls():
        for i in range(calls_per_thread):
            collector.add_api_call(f"http://test.com/{i}", 200)

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(add_calls) for _ in range(num_threads)]
        for future in futures:
            future.result()

    assert len(collector.api_calls) == num_threads * calls_per_thread

    # Also test simultaneous reads/writes
    def read_metadata():
        for _ in range(calls_per_thread):
            collector.to_dict()
            collector.to_json()

    with ThreadPoolExecutor(max_workers=num_threads * 2) as executor:
        write_futures = [executor.submit(add_calls) for _ in range(num_threads)]
        read_futures = [executor.submit(read_metadata) for _ in range(num_threads)]
        for future in write_futures + read_futures:
            future.result()

    # We added more calls in the second loop
    expected_calls = (num_threads * calls_per_thread) * 2
    assert len(collector.api_calls) == expected_calls
