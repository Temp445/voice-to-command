import sys
import traceback
from automation.desktop.file_operations import FileOperations
try:
    print(FileOperations().search_file('payroll'))
except Exception as e:
    traceback.print_exc()
    sys.exit(1)
