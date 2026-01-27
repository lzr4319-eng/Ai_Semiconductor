"""
性能优化示例代码
这些代码可以直接集成到现有项目中
"""

import streamlit as st
import pandas as pd
import json
import os
import time
import base64
from functools import lru_cache
from typing import Dict, Optional

# ==========================================
# 优化1: Streamlit缓存机制
# ==========================================

@st.cache_data(ttl=3600, show_spinner=False)
def load_data_cached(file_path: str) -> pd.DataFrame:
    """
    缓存数据加载
    ttl=3600: 缓存1小时
    show_spinner=False: 缓存命中时不显示加载动画
    """
    if not os.path.exists(file_path):
        return pd.DataFrame()
    return pd.read_csv(file_path)

@st.cache_data(ttl=300)
def load_json_cached(file_path: str) -> Optional[Dict]:
    """缓存JSON文件加载"""
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None

# ==========================================
# 优化2: 使用psutil优化进程检查
# ==========================================

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("⚠️ psutil未安装，将使用subprocess方式")

def _is_pid_running_optimized(pid: int) -> bool:
    """
    优化后的进程检查函数
    使用psutil库，比多次subprocess调用更高效
    """
    if not pid:
        return False
    
    if not PSUTIL_AVAILABLE:
        # 回退到原始方法
        import subprocess
        try:
            res = subprocess.run(["ps", "-p", str(pid)], capture_output=True, text=True)
            return res.returncode == 0
        except:
            return False
    
    try:
        process = psutil.Process(pid)
        
        # 检查进程是否还在运行
        if not process.is_running():
            return False
        
        # 检查是否有子进程（递归检查）
        try:
            children = process.children(recursive=True)
            if children:
                return True
        except psutil.NoSuchProcess:
            return False
        
        # 检查相关Python分析进程
        # 只检查一次，而不是多次subprocess调用
        target_scripts = ['eda.py', 'ml.py', 'posion.py', 'ai_text_analyzer.py', 'ai_chart_analyzer.py']
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and any(script in ' '.join(cmdline) for script in target_scripts):
                    # 检查这些进程是否与我们的任务相关
                    # 可以通过检查日志文件最近修改时间来判断
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        # 如果进程本身还在运行，返回True
        return True
        
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        # 权限不足，回退到简单检查
        return True
    except Exception:
        return False

# ==========================================
# 优化3: 缓存KPI数据计算
# ==========================================

# 模块级别的缓存字典
_kpi_cache = {}
_kpi_cache_timestamps = {}

@st.cache_data(ttl=300)  # 缓存5分钟
def load_kpi_data_optimized(base_dir: str) -> Dict:
    """
    优化的KPI数据加载，带缓存和文件修改时间检查
    """
    data_file = os.path.join(base_dir, 'base_function', 'output', 'cleaned_chip_data_final.csv')
    
    if not os.path.exists(data_file):
        return {}
    
    # 检查文件修改时间
    file_mtime = os.path.getmtime(data_file)
    cache_key = f"kpi_{data_file}"
    
    # 如果文件未修改且缓存存在，直接返回
    if cache_key in _kpi_cache:
        cached_mtime = _kpi_cache_timestamps.get(cache_key, 0)
        if file_mtime == cached_mtime:
            return _kpi_cache[cache_key]
    
    # 重新计算KPI
    try:
        df = pd.read_csv(data_file)
        total = len(df)
        pass_count = 0
        fail_count = 0
        status_counts = {}

        if 'Label_Pass' in df.columns:
            pass_count = int((df['Label_Pass'] == 1).sum())
            fail_count = int((df['Label_Pass'] == 0).sum())
        elif 'Is_Pass' in df.columns:
            pass_count = int((df['Is_Pass'] == 1).sum())
            fail_count = int((df['Is_Pass'] == 0).sum())

        target_col = next((c for c in df.columns if '压连' in c), None)
        if target_col:
            for val in df[target_col].dropna():
                try:
                    v = int(float(val))
                    status_counts[v] = status_counts.get(v, 0) + 1
                except:
                    pass

        if pass_count == 0 and fail_count == 0 and status_counts:
            pass_count = status_counts.get(0, 0) + status_counts.get(1, 0)
            fail_count = status_counts.get(-1, 0) + status_counts.get(2, 0)

        kpi_data = {
            'total': total,
            'pass_rate': (pass_count / total * 100) if total > 0 else 0,
            'pass_count': pass_count,
            'fail_count': fail_count,
            'open_count': status_counts.get(-1, 0),
            'severe_count': status_counts.get(2, 0),
            'open_rate': (status_counts.get(-1, 0) / total * 100) if total > 0 else 0,
            'severe_rate': (status_counts.get(2, 0) / total * 100) if total > 0 else 0
        }
        
        # 更新缓存
        _kpi_cache[cache_key] = kpi_data
        _kpi_cache_timestamps[cache_key] = file_mtime
        
        return kpi_data
    except Exception as e:
        print(f"⚠️ 计算KPI失败: {e}")
        return {}

# ==========================================
# 优化4: 缓存日志读取
# ==========================================

_log_cache = {}
_log_cache_timestamps = {}

@st.cache_data(ttl=2)  # 缓存2秒（日志文件变化频繁）
def _tail_log_optimized(log_path: str, n: int = 40) -> str:
    """
    优化的日志读取，带缓存
    """
    if not log_path or not os.path.exists(log_path):
        return ""
    
    # 检查文件修改时间
    file_mtime = os.path.getmtime(log_path)
    cache_key = f"log_{log_path}_{n}"
    
    # 如果文件未修改且缓存存在，直接返回
    if cache_key in _log_cache:
        cached_mtime = _log_cache_timestamps.get(cache_key, 0)
        if file_mtime == cached_mtime:
            return _log_cache[cache_key]
    
    # 重新读取
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        content = "".join(lines[-n:])
        
        # 更新缓存
        _log_cache[cache_key] = content
        _log_cache_timestamps[cache_key] = file_mtime
        
        return content
    except Exception:
        return ""

# ==========================================
# 优化5: 缓存图片Base64编码
# ==========================================

_base64_cache = {}
_base64_cache_timestamps = {}

def get_base64_image_optimized(image_path: str) -> Optional[str]:
    """
    优化的Base64图片编码，带缓存
    """
    if not os.path.exists(image_path):
        return None
    
    # 检查缓存
    file_mtime = os.path.getmtime(image_path)
    cache_key = image_path
    
    if cache_key in _base64_cache:
        cached_mtime = _base64_cache_timestamps.get(cache_key, 0)
        if file_mtime == cached_mtime:
            return _base64_cache[cache_key]
    
    # 重新编码
    try:
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode('utf-8')
            ext = os.path.splitext(image_path)[1].lower()
            mime = "image/png" if ext == ".png" else "image/jpeg"
            result = f"data:{mime};base64,{encoded}"
        
        # 更新缓存
        _base64_cache[cache_key] = result
        _base64_cache_timestamps[cache_key] = file_mtime
        
        return result
    except Exception:
        return None

# ==========================================
# 优化6: 缓存图片路径查找
# ==========================================

_image_path_cache = {}

def find_image_path_optimized(img_path: str, base_dir: str) -> Optional[str]:
    """
    优化的图片路径查找，带缓存
    """
    cache_key = f"{img_path}_{base_dir}"
    
    # 检查缓存
    if cache_key in _image_path_cache:
        cached_path = _image_path_cache[cache_key]
        if cached_path and os.path.exists(cached_path):
            return cached_path
    
    # 执行查找逻辑（这里简化示例，实际需要根据项目中的逻辑）
    candidates = [
        os.path.join(base_dir, 'base_function', img_path),
        os.path.join(base_dir, 'base_function', 'output', img_path),
        # ... 其他候选路径 ...
    ]
    
    for candidate in candidates:
        if os.path.exists(candidate):
            _image_path_cache[cache_key] = candidate
            return candidate
    
    # 缓存未找到的结果（避免重复查找）
    _image_path_cache[cache_key] = None
    return None

# ==========================================
# 优化7: 预编译正则表达式
# ==========================================

import re

# 在模块级别预编译所有正则表达式
_HTML_PATTERNS = {
    'code_block_html': re.compile(r'^```html\s*\n?', re.MULTILINE),
    'code_block': re.compile(r'^```\s*\n?', re.MULTILINE),
    'code_block_end': re.compile(r'\n?```\s*$', re.MULTILINE),
    'img_src': re.compile(r'src=["\']([^"\']+)["\']'),
    'nested_div': re.compile(r'<div class="section-card">\s*<div class="section-card">'),
    'alt_outside_tag': re.compile(r'(?<!<img)(?<!<div)(?<!<span)(?<!<p)\s+alt="[^"]+"'),
}

def clean_html_content_optimized(content: str) -> str:
    """
    使用预编译的正则表达式清理HTML
    """
    if not content:
        return ""
    
    content = content.strip()
    
    # 使用预编译的模式
    content = _HTML_PATTERNS['code_block_html'].sub('', content)
    content = _HTML_PATTERNS['code_block'].sub('', content)
    content = _HTML_PATTERNS['code_block_end'].sub('', content)
    content = content.strip()
    
    # 清理alt属性
    content = _HTML_PATTERNS['alt_outside_tag'].sub('', content)
    
    return content

# ==========================================
# 优化8: 智能刷新机制
# ==========================================

def should_refresh_page(job, last_check_time: float, check_interval: int = 3) -> bool:
    """
    智能判断是否需要刷新页面
    只有当任务状态真正变化时才刷新
    """
    if not job:
        return False
    
    current_time = time.time()
    
    # 检查时间间隔
    if current_time - last_check_time < check_interval:
        return False
    
    # 检查任务状态是否变化
    pid_running = _is_pid_running_optimized(job.get("pid"))
    task_completed = False  # 这里需要根据实际逻辑判断
    task_failed = False     # 这里需要根据实际逻辑判断
    
    current_status = f"{pid_running}_{task_completed}_{task_failed}"
    last_status = job.get('last_status_hash', '')
    
    # 只有当状态变化时才刷新
    if current_status != last_status:
        job['last_status_hash'] = current_status
        return True
    
    return False

# ==========================================
# 使用示例
# ==========================================

def example_usage():
    """
    使用示例
    """
    # 1. 使用缓存的数据加载
    data_file = "path/to/data.csv"
    df = load_data_cached(data_file)  # 第一次调用会读取文件，后续调用使用缓存
    
    # 2. 使用优化的进程检查
    pid = 12345
    is_running = _is_pid_running_optimized(pid)
    
    # 3. 使用缓存的KPI计算
    base_dir = "/path/to/project"
    kpi_data = load_kpi_data_optimized(base_dir)
    
    # 4. 使用优化的日志读取
    log_path = "/tmp/log.txt"
    log_content = _tail_log_optimized(log_path, n=40)
    
    # 5. 使用优化的图片编码
    image_path = "path/to/image.png"
    base64_img = get_base64_image_optimized(image_path)
    
    # 6. 使用预编译的正则表达式
    html_content = "<div>...</div>"
    cleaned = clean_html_content_optimized(html_content)

if __name__ == "__main__":
    print("这是优化示例代码，请根据实际需求集成到项目中")
