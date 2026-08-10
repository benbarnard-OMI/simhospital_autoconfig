import yaml
import time
import os

DATA_YML_PATH = os.path.join(os.path.dirname(__file__), 'data.yml')

def benchmark(loader_name, loader):
    with open(DATA_YML_PATH, 'r') as f:
        content = f.read()

    start = time.time()
    for _ in range(100):
        yaml.load(content, Loader=loader)
    end = time.time()
    print(f"{loader_name}: {end - start:.4f} seconds")

print("Benchmarking YAML loaders:")
try:
    benchmark("SafeLoader", yaml.SafeLoader)
    if hasattr(yaml, 'CSafeLoader'):
        benchmark("CSafeLoader", yaml.CSafeLoader)
    else:
        print("CSafeLoader not available.")
except Exception as e:
    print(e)
