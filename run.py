import os
import sys
import subprocess

def setup_venv():
    """设置虚拟环境并安装依赖"""
    if not os.path.exists("venv"):
        print("Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", "venv"])
    
    # 激活虚拟环境并安装依赖
    if os.name == "nt":  # Windows
        python_path = os.path.join("venv", "Scripts", "python")
        pip_path = os.path.join("venv", "Scripts", "pip")
    else:  # Linux/Mac
        python_path = os.path.join("venv", "bin", "python")
        pip_path = os.path.join("venv", "bin", "pip")
    
    print("Installing dependencies...")
    subprocess.run([pip_path, "install", "-r", "requirements.txt"])
    
    return python_path

def main():
    python_path = setup_venv()
    print("Starting application...")
    subprocess.run([python_path, "app.py"])

if __name__ == "__main__":
    main() 