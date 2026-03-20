#!/usr/bin/env python3
"""
配置读取层 — Fund Report 单一配置中心 (SSOT)
所有脚本统一从此文件读取配置，配置源: ~/.hermes/fund-report.yaml
"""
import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List

import yaml

# ── 路径常量 ──────────────────────────────────────────────
HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
CONFIG_FILE = HERMES_HOME / "fund-report.yaml"

_config_cache: Optional[Dict[str, Any]] = None


def _load_config() -> Dict[str, Any]:
    """懒加载 + 缓存"""
    global _config_cache
    if _config_cache is None:
        if not CONFIG_FILE.exists():
            raise FileNotFoundError(
                f"配置文件不存在: {CONFIG_FILE}\n"
                "请参考 ~/.hermes/fund-report.yaml.example 创建配置文件"
            )
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            _config_cache = yaml.safe_load(f)
    return _config_cache


def _get_pass(key: str) -> str:
    """从 pass store 读取敏感信息
    pass 在非 TTY 时默认只返回第一行，用 -- 显式分隔参数
    """
    result = subprocess.run(
        ["pass", "show", "--", key],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


# ── 公开 API ──────────────────────────────────────────────

def get_profile(profile_name: str) -> Dict[str, Any]:
    """获取用户画像配置"""
    cfg = _load_config()
    profiles = cfg.get("profiles", {})
    if profile_name not in profiles:
        raise ValueError(f"未知profile: {profile_name}，可用: {list(profiles.keys())}")
    return profiles[profile_name]


def get_recipients(profile_name: str) -> List[str]:
    """获取某profile的邮件收件人列表"""
    profile = get_profile(profile_name)
    return [profile["email"]]


def get_active_provider() -> str:
    return _load_config().get("provider", {}).get("active", "aliyun")


def get_provider_config(provider_name: str = None) -> Dict[str, Any]:
    """获取provider配置（包含pass key引用）"""
    if provider_name is None:
        provider_name = get_active_provider()
    cfg = _load_config()
    prov = cfg.get("provider", {}).get(provider_name, {})
    if not prov:
        raise ValueError(f"未找到provider配置: {provider_name}")
    return prov


def get_api_key(provider_name: str = None) -> str:
    """获取当前provider的API Key（从pass读取）"""
    prov = get_provider_config(provider_name)
    pass_key = prov.get("api_key_pass_key")
    if not pass_key:
        raise ValueError(f"provider {provider_name} 未配置 api_key_pass_key")
    return _get_pass(pass_key)


def get_tavily_api_key() -> Optional[str]:
    """获取Tavily API Key（可选）"""
    cfg = _load_config()
    search = cfg.get("search", {})
    tavily = search.get("tavily", {})
    if not tavily.get("enabled"):
        return None
    pass_key = tavily.get("api_key_pass_key")
    if not pass_key:
        return None
    try:
        return _get_pass(pass_key)
    except Exception:
        return None


def get_smtp_config() -> Dict[str, Any]:
    """获取SMTP配置
    smtp 元信息从 hermes/email-config（多行格式）读取，
    密码从 hermes/email-smtp-password 单独读取。
    """
    cfg = _load_config()
    email_cfg = cfg.get("email", {})

    # 先从 pass 的 email-config 读元信息
    try:
        meta_raw = _get_pass("hermes/email-config")
        meta = {}
        for line in meta_raw.strip().split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
    except Exception:
        meta = {}

    password = _get_pass(email_cfg.get("password_pass_key", "hermes/email-smtp-password"))

    return {
        "smtp_host": meta.get("smtp_host", "smtp.qq.com"),
        "smtp_port": int(meta.get("smtp_port", 587)),
        "username": meta.get("username", ""),
        "from_name": meta.get("from_name", "基金报告机器人"),
        "password": password,
    }


def get_output_config() -> Dict[str, Any]:
    return _load_config().get("output", {"base_dir": "output", "format": ["md", "html"]})


def get_default_profile() -> str:
    return _load_config().get("defaults", {}).get("profile", "k7407")


def get_default_provider() -> str:
    return _load_config().get("defaults", {}).get("provider", "aliyun")


def get_all_profiles() -> List[str]:
    return list(_load_config().get("profiles", {}).keys())


def get_enabled_jobs() -> List[Dict[str, Any]]:
    jobs = _load_config().get("jobs", [])
    return [j for j in jobs if j.get("enabled", False)]
