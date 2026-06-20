import time
import numpy as np
import scipy.signal

# Test resample speed
raw = np.random.randn(3528).astype(np.int16)

start = time.perf_counter()
resampled = scipy.signal.resample(raw, 1280).astype(np.int16)
end = time.perf_counter()

print(f"Resampled to {len(resampled)} in {(end-start)*1000:.2f} ms")
