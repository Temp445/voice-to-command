# LiveKit WakeWord — Install Verification Report

Generated: 2026-06-18 12:23:56

**Result: 8 passed, 0 failed**

| Check | Status | Detail |
|---|---|---|
| Python version >= 3.11 | [PASS] | 3.11.9 |
| livekit.wakeword import | [PASS] | livekit.wakeword imported OK (version=0.1.0) |
| onnxruntime available | [PASS] | onnxruntime 1.26.0 |
| numpy available | [PASS] | numpy 2.4.6 |
| hey_ace.onnx file exists | [PASS] | hey_ace.onnx exists (201.4 KB) |
| WakeWordModel loads ONNX | [PASS] | WakeWordModel loaded from hey_ace.onnx |
| predict() output shape & range | [PASS] | predict() -> {"hey_ace": 0.0} in 1.8ms |
| No dependency conflicts | [PASS] | onnxruntime providers: ['AzureExecutionProvider', 'CPUExecutionProvider'] \| openwakeword present: True (co-existence OK) |

## [ALL PASS] All checks passed -- proceed to Phase 2a.