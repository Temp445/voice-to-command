import traceback
try:
    from piper import PiperVoice
    print('SUCCESS')
except Exception as e:
    print(traceback.format_exc())
