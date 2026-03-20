#!/usr/bin/env python3
"""
向后兼容重导出 — 委托给 references/ 版本
现有 cron 任务无需修改路径
"""
import os, sys, subprocess

root = os.path.dirname(os.path.abspath(__file__))
ref_script = os.path.join(root, "references", "run_and_send_pipeline.py")
sys.exit(subprocess.call([sys.executable, ref_script] + sys.argv[1:], cwd=root))
