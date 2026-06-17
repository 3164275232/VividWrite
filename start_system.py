#!/usr/bin/env python3
"""
VividWrite 2.0 系统启动脚本
"""

import subprocess
import sys
import os
import time
import threading
import requests
from pathlib import Path

def check_dependencies():
    """检查依赖是否安装"""
    print("🔍 检查依赖...")
    
    # 检查Python包
    required_packages = ['fastapi', 'uvicorn', 'matplotlib', 'scikit-learn']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ 缺少以下Python包: {', '.join(missing_packages)}")
        print("   请运行: pip install -r backend/requirements.txt")
        return False
    
    # 检查Node.js和npm
    try:
        subprocess.run(['node', '--version'], check=True, capture_output=True)
        subprocess.run(['npm', '--version'], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ 未找到Node.js或npm，请先安装Node.js")
        return False
    
    print("✅ 依赖检查通过")
    return True

def start_backend():
    """启动后端服务"""
    print("🚀 启动后端服务...")
    backend_dir = Path("backend")
    
    if not backend_dir.exists():
        print("❌ 未找到backend目录")
        return None
    
    # 检查是否有虚拟环境
    venv_python = backend_dir / "venv" / "Scripts" / "python.exe"  # Windows
    if not venv_python.exists():
        venv_python = backend_dir / "venv" / "bin" / "python"  # Linux/Mac
    
    python_cmd = str(venv_python) if venv_python.exists() else "python"
    
    try:
        process = subprocess.Popen(
            [python_cmd, "-m", "uvicorn", "main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
            cwd=backend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # 等待服务启动
        print("⏳ 等待后端服务启动...")
        for i in range(30):  # 最多等待30秒
            try:
                response = requests.get("http://localhost:8000/health", timeout=1)
                if response.status_code == 200:
                    print("✅ 后端服务启动成功 (http://localhost:8000)")
                    return process
            except requests.exceptions.RequestException:
                pass
            time.sleep(1)
        
        print("❌ 后端服务启动超时")
        return None
        
    except Exception as e:
        print(f"❌ 启动后端服务失败: {str(e)}")
        return None

def start_frontend():
    """启动前端服务"""
    print("🚀 启动前端服务...")
    frontend_dir = Path("frontend")
    
    if not frontend_dir.exists():
        print("❌ 未找到frontend目录")
        return None
    
    try:
        process = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=frontend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # 等待服务启动
        print("⏳ 等待前端服务启动...")
        for i in range(30):  # 最多等待30秒
            try:
                response = requests.get("http://localhost:5173", timeout=1)
                if response.status_code == 200:
                    print("✅ 前端服务启动成功 (http://localhost:5173)")
                    return process
            except requests.exceptions.RequestException:
                pass
            time.sleep(1)
        
        print("❌ 前端服务启动超时")
        return None
        
    except Exception as e:
        print(f"❌ 启动前端服务失败: {str(e)}")
        return None

def main():
    """主函数"""
    print("🎯 VividWrite 2.0 系统启动器")
    print("=" * 50)
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 启动后端
    backend_process = start_backend()
    if not backend_process:
        sys.exit(1)
    
    # 启动前端
    frontend_process = start_frontend()
    if not frontend_process:
        backend_process.terminate()
        sys.exit(1)
    
    print("\n🎉 系统启动完成！")
    print("📱 前端地址: http://localhost:5173")
    print("🔧 后端地址: http://localhost:8000")
    print("📚 API文档: http://localhost:8000/docs")
    print("\n按 Ctrl+C 停止服务")
    
    try:
        # 等待用户中断
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 正在停止服务...")
        backend_process.terminate()
        frontend_process.terminate()
        print("✅ 服务已停止")

if __name__ == "__main__":
    main()

