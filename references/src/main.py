#!/usr/bin/env python3
"""
向后兼容重导出
推荐直接使用: python run_full_pipeline.py
"""
import os, sys, subprocess

# 向上找到项目根目录
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pipeline = os.path.join(root, "run_full_pipeline.py")
sys.exit(subprocess.call([sys.executable, pipeline], cwd=root))
