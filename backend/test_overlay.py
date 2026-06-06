import subprocess
import sys

def main():
    try:
        result = subprocess.run(
            [sys.executable, "automation/desktop/overlay.py"],
            capture_output=True,
            text=True,
            timeout=5
        )
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        print("RETURN CODE:", result.returncode)
    except subprocess.TimeoutExpired as e:
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        print("Process timed out (which means it stayed open!)")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
