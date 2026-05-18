import os
import subprocess
import shutil
import sys

def build():
    print("=== CODERUN EXECUTABLE BUILDER ===")
    
    # Verify PyInstaller is installed
    if not shutil.which("pyinstaller"):
        print("Error: PyInstaller is not installed or not in PATH.")
        print("Please run: pip install pyinstaller")
        sys.exit(1)
        
    source_file = "coderun.py"
    if not os.path.exists(source_file):
        print(f"Error: Source file '{source_file}' not found.")
        sys.exit(1)
        
    print(f"Compiling '{source_file}' into a single-file executable...")
    
    # Construct PyInstaller command
    cmd = [
        "pyinstaller",
        "--onefile",
        "--noconsole",
        "--name=coderun_gui",
        source_file
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    
    try:
        # Run PyInstaller
        result = subprocess.run(cmd, check=True)
        print("\n=== BUILD COMPLETED SUCCESSFULLY ===")
        print("Output executable can be found at: dist/coderun.exe")
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed with exit code: {e.returncode}")
        sys.exit(e.returncode)

if __name__ == "__main__":
    build()
