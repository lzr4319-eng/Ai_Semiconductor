import streamlit as st
import pandas as pd
import numpy as np
from scipy import stats
import os
import json
import base64
import re
import time
import streamlit.components.v1 as components

def render_ai_report(t):
    """
    显示描述性报告
    """
    import subprocess
    import sys
    import uuid
    
    st.subheader(t.get('ai_report_title', '📊 描述性报告'))
    
    # 获取项目根目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(current_dir)  # Semiconductor_ai
    base_dir = os.path.dirname(project_dir)  # LZR_Project
    
    # 文件路径
    text_results_file = os.path.join(base_dir, 'base_function', 'output', 'ai_text_analysis_results.json')
    text_script = os.path.join(base_dir, 'base_function', 'main', 'ai_text_analyzer.py')
    eda_script = os.path.join(base_dir, 'base_function', 'main', 'eda.py')
    position_script = os.path.join(base_dir, 'base_function', 'main', 'posion.py')
    
    # 加载报告
    text_report = None
    
    if os.path.exists(text_results_file):
        try:
            with open(text_results_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                text_report = data.get('comprehensive_report')
        except:
            pass
    
    # 获取文件修改时间
    def get_file_time(filepath):
        if os.path.exists(filepath):
            mtime = os.path.getmtime(filepath)
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime)), mtime
        return None, 0
    
    text_time_str, text_mtime = get_file_time(text_results_file)
    
    # ---------------------------
    # 任务运行器：前端点击卡片 -> 后端执行单一步骤
    # ---------------------------
    if "job" not in st.session_state:
        st.session_state.job = None  # {"id","name","pid","start_ts","log_path"}

    def _is_pid_running(pid: int) -> bool:
        if not pid:
            return False
        try:
            # 检查进程是否存在，以及其子进程是否还在运行
            # 因为包装脚本会启动多个子进程，我们需要检查整个进程组
            res = subprocess.run(["ps", "-p", str(pid), "-o", "stat=,pid="], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                stat = res.stdout.strip().split()[0] if res.stdout.strip() else ""
                # Z表示僵尸进程，已经完成
                if 'Z' in stat:
                    return False
                # 检查是否有子进程还在运行（包装脚本的子进程）
                # 使用pgrep检查是否有相关的Python进程在运行
                pgrep_res = subprocess.run(
                    ["pgrep", "-P", str(pid)],
                    capture_output=True,
                    text=True
                )
                # 如果有子进程，认为还在运行
                if pgrep_res.returncode == 0 and pgrep_res.stdout.strip():
                    return True
                # 如果没有直接子进程，检查是否有相关的Python分析进程在运行
                # 这些进程可能不是直接子进程，而是通过bash脚本启动的
                python_processes = subprocess.run(
                    ["pgrep", "-f", "(eda\\.py|ml\\.py|posion\\.py|ai_chart_analyzer\\.py|ai_text_analyzer\\.py)"],
                    capture_output=True,
                    text=True
                )
                if python_processes.returncode == 0 and python_processes.stdout.strip():
                    # 检查这些进程是否与我们的任务相关（通过检查日志文件最近是否有更新）
                    return True
                
                # 如果进程本身还在运行，返回True
                return True
            return False
        except Exception:
            # 如果检查失败，尝试简单检查进程是否存在
            try:
                res = subprocess.run(["ps", "-p", str(pid)], capture_output=True, text=True)
                return res.returncode == 0
            except:
                return False

    def _tail_log(path: str, n: int = 40) -> str:
        if not path or not os.path.exists(path):
            return ""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            return "".join(lines[-n:])
        except Exception:
            return ""

    def _extract_progress(log_path: str) -> str:
        if not log_path or not os.path.exists(log_path):
            return ""
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            last_lines = lines[-60:] if len(lines) > 60 else lines
            for line in reversed(last_lines):
                if '[步骤' in line or '步骤' in line:
                    return line.strip()
                if '执行' in line and ('分析' in line or 'EDA' in line or '位置' in line or 'AI' in line):
                    return line.strip()
            return ""
        except Exception:
            return ""

    def _log_has_done(log_path: str) -> bool:
        if not log_path or not os.path.exists(log_path):
            return False
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            last_lines = lines[-30:] if len(lines) > 30 else lines
            return any(('所有步骤执行完毕' in line) or ('[完成]' in line) for line in last_lines)
        except Exception:
            return False

    def _start_job(job_name: str, script_path: str):
        if st.session_state.job and _is_pid_running(st.session_state.job.get("pid")):
            return
        job_id = uuid.uuid4().hex[:8]
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        log_path = f"/tmp/lzr_{job_name}_{timestamp}_{job_id}.log"
        
        # 文本报告：先执行EDA、位置分析，再执行AI分析
        if job_name == 'text':
            # 创建一个包装脚本，按顺序执行：EDA -> Position -> AI分析
            wrapper_script = f"/tmp/lzr_wrapper_{job_id}.sh"
            with open(wrapper_script, "w", encoding="utf-8") as wf:
                wf.write("#!/bin/bash\n")
                wf.write("set -e  # 遇到错误立即退出\n")
                wf.write(f"cd {os.path.dirname(script_path)}\n")
                wf.write(f"echo '[步骤 1/3] 执行EDA分析...' | tee -a {log_path}\n")
                wf.write(f"{sys.executable} {eda_script} >> {log_path} 2>&1 || {{ echo 'EDA分析失败'; exit 1; }}\n")
                wf.write(f"echo '[步骤 2/3] 执行位置分析...' | tee -a {log_path}\n")
                wf.write(f"{sys.executable} {position_script} >> {log_path} 2>&1 || {{ echo '位置分析失败'; exit 1; }}\n")
                wf.write(f"echo '[步骤 3/3] 执行AI分析（文字识别）...' | tee -a {log_path}\n")
                wf.write(f"{sys.executable} {script_path} >> {log_path} 2>&1 || {{ echo 'AI分析失败'; exit 1; }}\n")
                wf.write(f"echo '[完成] 所有步骤执行完毕' | tee -a {log_path}\n")
            os.chmod(wrapper_script, 0o755)
            
            # 后台执行包装脚本
            # 使用nohup确保即使Streamlit重启，任务也能继续运行
            with open(log_path, "w", encoding="utf-8") as lf:
                lf.write(f"[开始] 任务ID: {job_id}, 开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                lf.flush()
            
            # 使用nohup和重定向确保进程独立运行
            # 注意：在Python 3.13中，preexec_fn和start_new_session不能同时使用
            # start_new_session=True已经会创建新的会话，不需要preexec_fn
            proc = subprocess.Popen(
                ["nohup", "/bin/bash", wrapper_script],
                stdout=open(log_path, "a", encoding="utf-8"),
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,  # 创建新会话，避免父进程退出影响
            )
        else:
            # 其他任务直接执行
            with open(log_path, "w", encoding="utf-8") as lf:
                proc = subprocess.Popen(
                    [sys.executable, script_path],
                    cwd=os.path.dirname(script_path),
                    stdout=lf,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
        
        st.session_state.job = {
            "id": job_id,
            "name": job_name,
            "pid": proc.pid,
            "start_ts": time.time(),
            "log_path": log_path,
        }
        st.session_state.last_analysis = job_name  # 仅用于文本报告
        st.rerun()

    def _run_text_pipeline_sync():
        job_id = uuid.uuid4().hex[:8]
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        log_path = f"/tmp/lzr_text_{timestamp}_{job_id}.log"
        st.session_state.job = {
            "id": job_id,
            "name": "text",
            "pid": None,
            "start_ts": time.time(),
            "log_path": log_path,
        }

        progress_box = st.empty()
        try:
            with open(log_path, "w", encoding="utf-8") as lf:
                lf.write(f"[开始] 任务ID: {job_id}, 开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                lf.flush()

            progress_box.info("📋 当前进度：[步骤 1/3] 执行EDA分析...")
            with open(log_path, "a", encoding="utf-8") as lf:
                subprocess.run(
                    [sys.executable, eda_script],
                    cwd=os.path.dirname(eda_script),
                    stdout=lf,
                    stderr=subprocess.STDOUT,
                    check=True,
                    text=True,
                )

            progress_box.info("📋 当前进度：[步骤 2/3] 执行位置分析...")
            with open(log_path, "a", encoding="utf-8") as lf:
                subprocess.run(
                    [sys.executable, position_script],
                    cwd=os.path.dirname(position_script),
                    stdout=lf,
                    stderr=subprocess.STDOUT,
                    check=True,
                    text=True,
                )

            progress_box.info("📋 当前进度：[步骤 3/3] 执行AI分析（文字识别）...")
            with open(log_path, "a", encoding="utf-8") as lf:
                subprocess.run(
                    [sys.executable, text_script],
                    cwd=os.path.dirname(text_script),
                    stdout=lf,
                    stderr=subprocess.STDOUT,
                    check=True,
                    text=True,
                )

            progress_box.success("✅ 报告生成完成，正在刷新页面...")
            st.session_state.last_job_status = "success"
            st.session_state.last_analysis = "text"
        except Exception as e:
            progress_box.error(f"❌ 报告生成失败：{e}")
            st.session_state.last_job_status = "failed"
        finally:
            st.session_state.job = None

        st.rerun()

    # 侧边栏：实时计时栏（JS计时，不触发整页rerun，避免"页面一闪一闪"）
    job = st.session_state.job
    pid_running = bool(job and _is_pid_running(job.get("pid")))
    
    # 检查任务是否真正完成（通过输出文件或进程状态）
    running = pid_running
    task_failed = False
    if job:
        # 检查对应的输出文件是否存在且最近被修改
        task_completed = False
        if job.get("name") == "text":
            text_results_file = os.path.join(base_dir, 'base_function', 'output', 'ai_text_analysis_results.json')
            if os.path.exists(text_results_file):
                file_mtime = os.path.getmtime(text_results_file)
                # 文件在任务开始后被修改（放宽时间限制，只要在任务开始后修改即可）
                if file_mtime > job.get("start_ts", 0):
                    task_completed = True
        # 基于日志的完成检测（更鲁棒）
        log_path = job.get("log_path")
        if _log_has_done(log_path):
            task_completed = True

        # 检查任务是否失败（进程不在运行，但输出文件也不存在）
        # 注意：先再次检查输出文件，因为文件可能刚刚生成
        if not pid_running and not task_completed:
            # 再次检查输出文件（可能刚刚生成）
            if job.get("name") == "text":
                text_results_file = os.path.join(base_dir, 'base_function', 'output', 'ai_text_analysis_results.json')
                if os.path.exists(text_results_file):
                    file_mtime = os.path.getmtime(text_results_file)
                    if file_mtime > job.get("start_ts", 0):
                        task_completed = True
            
            # 如果还是没有输出文件，检查是否失败
            if not task_completed:
                elapsed = time.time() - job.get("start_ts", 0)
                # 如果进程已停止超过30秒，且没有输出文件，认为任务失败
                if elapsed > 30:
                    # 检查日志文件最后几行，看是否有错误
                    log_path = job.get("log_path")
                    if log_path and os.path.exists(log_path):
                        try:
                            with open(log_path, 'r', encoding='utf-8') as f:
                                lines = f.readlines()
                                last_lines = ''.join(lines[-10:]) if len(lines) > 10 else ''.join(lines)
                                # 检查是否有明显的错误信息
                                if any(keyword in last_lines.lower() for keyword in ['error', 'exception', 'failed', '失败', '错误', '❌']):
                                    task_failed = True
                        except:
                            pass
                    
                    # 如果进程停止超过30秒且没有输出文件，标记为失败
                    task_failed = True

        # 如果任务尚未完成且未失败，保持运行状态（避免pid检测失效导致不刷新）
        if job and not task_completed and not task_failed:
            running = True
        
        # 如果输出文件存在且进程不在运行，认为任务已完成
        if task_completed and not pid_running:
            running = False
            # 清空job状态，让报告显示
            job_id = job.get('id')
            # 使用标记避免无限刷新
            if 'last_completed_job' not in st.session_state or st.session_state.last_completed_job != job_id:
                st.session_state.last_completed_job = job_id
                st.session_state.last_job_status = "success"
                st.session_state.job = None
                # 立即刷新页面以显示报告
                st.rerun()
                st.session_state.job = None
        
        # 如果任务失败，显示错误信息并清空状态
        if task_failed:
            running = False
            job_id = job.get('id')
            st.session_state.job = None
            if 'last_completed_job' not in st.session_state or st.session_state.last_completed_job != job_id:
                st.session_state.last_completed_job = job_id
                st.session_state.last_job_status = "failed"
                st.rerun()
        
        # 超时检测：如果任务运行超过20分钟，自动标记为失败（可能卡住或出错）
        if running:
            elapsed = time.time() - job.get("start_ts", 0)
            if elapsed > 1200:  # 20分钟超时
                running = False
                task_failed = True
                # 清空job状态，避免一直显示运行中
                job_id = job.get('id')
                st.session_state.job = None
                # 超时后也刷新一次，确保状态更新
                if 'last_completed_job' not in st.session_state or st.session_state.last_completed_job != job_id:
                    st.session_state.last_completed_job = job_id
                    st.session_state.last_job_status = "failed"
                    st.rerun()
        
        # 定期自动刷新机制：如果任务正在运行，每3秒自动检查一次状态（更频繁的更新）
        if running:
            current_time = time.time()
            last_check = st.session_state.get('last_task_check', 0)
            # 每3秒检查一次任务状态（使用时间戳避免频繁刷新）
            if current_time - last_check > 3:
                st.session_state['last_task_check'] = current_time
                # 触发rerun以更新进度和状态
                st.rerun()
    
    # ---------------------------
    # 操作按钮（不自动跑，用户点击才执行）
    # ---------------------------
    btn_text = st.button("📊 开始生成描述性报告", key="btn_text", use_container_width=True, type="primary", disabled=running)
    
    # 处理按钮点击
    if btn_text:
        _run_text_pipeline_sync()

    # 主区域进度与状态提示
    status_box = st.empty()
    progress_box = st.empty()
    last_status = st.session_state.get("last_job_status")
    if last_status == "success":
        status_box.success("✅ 报告生成完成，已自动刷新展示。")
        st.session_state["last_job_status"] = None
    elif last_status == "failed":
        status_box.error("❌ 报告生成失败，请查看日志后重试。")
        st.session_state["last_job_status"] = None

    if running and job:
        progress_text = _extract_progress(job.get("log_path"))
        if progress_text:
            progress_box.info(f"📋 当前进度：{progress_text}")
        else:
            progress_box.info("⏳ 任务运行中，系统将自动检测完成状态...")
    
    # 图片路径转换函数
    def get_base64_image(image_path):
        if not os.path.exists(image_path):
            return None
        try:
            with open(image_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode('utf-8')
                ext = os.path.splitext(image_path)[1].lower()
                mime = "image/png" if ext == ".png" else "image/jpeg"
                return f"data:{mime};base64,{encoded}"
        except:
            return None
    
    def replace_image_paths(html_content):
        pattern = r'src=["\']([^"\']+)["\']'
        missing = []
        
        def replace_func(match):
            img_path = match.group(1)
            if img_path.startswith('data:image'):
                return match.group(0)
            
            # 初始化 full_path
            full_path = None
            
            # 1. 尝试直接路径 (如果是 output/ 开头)
            if img_path.startswith('output/'):
                direct_path = os.path.join(base_dir, 'base_function', img_path)
                if os.path.exists(direct_path):
                    full_path = direct_path
            
            # 2. 如果直接路径不存在，进行模糊搜索/候选路径搜索
            if not full_path:
                img_basename = os.path.basename(img_path)
                candidates = [
                    os.path.join(base_dir, 'base_function', img_path),  # 完整路径
                    os.path.join(base_dir, 'base_function', 'output', img_path),  # output/xxx
                    os.path.join(base_dir, 'base_function', 'output', 'analysis_report', img_basename),  # EDA图片
                    os.path.join(base_dir, 'base_function', 'output', 'position_analysis_v2', img_basename),  # Position图片
                    os.path.join(base_dir, 'base_function', 'output', 'ml_report', img_basename),  # ML图片
                ]
                
                # 特殊处理：Position Analysis 映射修正
                if 'Position_Yield' in img_basename:
                    candidates.append(os.path.join(base_dir, 'base_function', 'output', 'position_analysis_v2', '1_Position_Yield_Rate.png'))
                
                if 'Position_Parameter' in img_basename:
                    # 尝试映射到 Failure_Detail，因为这是第二张图位置
                    candidates.append(os.path.join(base_dir, 'base_function', 'output', 'position_analysis_v2', '2_Position_Failure_Detail.png'))
                
                # 特殊处理：如果图片名包含Physical相关变体，映射到Physical_Features
                if any(k in img_basename for k in ['Physical_Deviation', 'Height_Distribution', 'Physical_Stats', 'Physical_Diff', 'Physical_Characteristics', 'Process_Parameter', 'Feature_Distribution', 'High_Risk', 'Physical_Consistency', 'Parameter_Drift']):
                    candidates.append(os.path.join(base_dir, 'base_function', 'output', 'position_analysis_v2', '3_Position_Physical_Features.png'))
                # 特殊处理：如果图片名包含Failure_Detail但找不到，尝试Pass_Fail_Ratio
                if 'Failure_Detail' in img_basename:
                    candidates.append(os.path.join(base_dir, 'base_function', 'output', 'position_analysis_v2', '2_Position_Pass_Fail_Ratio.png'))
                
                for c in candidates:
                    if os.path.exists(c):
                        full_path = c
                        break
                        
                if not full_path:
                    # 如果所有候选路径都不存在，使用第一个作为默认（用于错误提示）
                    full_path = candidates[0] if candidates else img_path
            
            b64 = get_base64_image(full_path)
            if b64:
                return f'src="{b64}"'
            missing.append(img_path)
            return match.group(0)
        
        return re.sub(pattern, replace_func, html_content), missing
    
    # 渲染报告的函数
    def render_report(content, title, time_str, report_type):
        # 清理内容：移除markdown代码块标记和修复HTML结构
        if content:
            content = content.strip()
            # 移除开头的 ```html 或 ``` 标记
            if content.startswith('```html'):
                content = content[7:].strip()
            elif content.startswith('```'):
                content = content[3:].strip()
            
            # 移除结尾的 ``` 标记
            if content.endswith('```'):
                content = content[:-3].strip()
            
            # 使用正则表达式进一步清理
            content = re.sub(r'^```html?\s*\n?', '', content, flags=re.MULTILINE)
            content = re.sub(r'^```\s*\n?', '', content, flags=re.MULTILINE)
            content = re.sub(r'\n?```\s*$', '', content, flags=re.MULTILINE)
            content = content.strip()
            
            # 修复嵌套的div问题：如果发现大量嵌套的section-card，尝试修复结构
            # 检查是否有严重的嵌套问题（连续3个以上的section-card）
            nested_count = len(re.findall(r'<div class="section-card">\s*<div class="section-card">', content))
            if nested_count > 5:
                # 严重嵌套问题，检查是否有h2标签
                h2_match = re.search(r'<h2>', content)
                if not h2_match:
                    # 完全没有h2标签，说明报告格式完全错误
                    # 尝试从后往前查找有效内容（通常有效内容在最后）
                    # 查找常见的报告内容标识
                    content_markers = ['<p>', '<h3>', '<strong>', '良率', '工艺', '归因', '总结']
                    valid_start = -1
                    for marker in content_markers:
                        pos = content.find(marker)
                        if pos != -1:
                            valid_start = pos
                            break
                    
                    if valid_start != -1:
                        # 向前查找最近的<div class="section-card">
                        section_start = content.rfind('<div class="section-card">', 0, valid_start)
                        if section_start != -1:
                            content = content[section_start:]
                            # 移除所有连续的嵌套div，只保留一个
                            content = re.sub(
                                r'(<div class="section-card">\s*)+',
                                '<div class="section-card">',
                                content
                            )
                        else:
                            # 如果找不到section-card，直接从头开始包装
                            content = '<div class="section-card">\n' + content[valid_start:] + '\n</div>'
                    else:
                        # 如果完全找不到有效内容，返回错误提示
                        st.error("⚠️ 报告内容格式错误，无法解析。请重新生成报告。")
                        return
                else:
                    # 有h2标签，正常修复
                    # 向前查找最近的<div class="section-card">，但只取一个
                    search_start = max(0, h2_match.start() - 200)
                    section_start = content.rfind('<div class="section-card">', search_start, h2_match.start())
                    if section_start != -1:
                        content = content[section_start:]
                        # 移除所有连续的嵌套div，只保留一个
                        content = re.sub(
                            r'(<div class="section-card">\s*)+',
                            '<div class="section-card">',
                            content
                        )
                
                # 确保div标签匹配：计算开始和结束标签数量
                open_divs = content.count('<div class="section-card">')
                close_divs = content.count('</div>')
                # 如果结束标签不足，补充
                if close_divs < open_divs:
                    content += '</div>' * (open_divs - close_divs)
                # 如果结束标签过多，移除多余的
                elif close_divs > open_divs:
                    # 从后往前移除多余的</div>
                    for _ in range(close_divs - open_divs):
                        last_close = content.rfind('</div>')
                        if last_close != -1:
                            content = content[:last_close] + content[last_close+6:]
            
            # 确保以<div开始
            div_start = content.find('<div')
            if div_start > 0:
                content = content[div_start:]
        
        # 清理alt文本中的"图表占位符"（再次确保清理）
        content = re.sub(r'alt="图表占位符[^"]*"', 'alt="图表"', content)
        content = re.sub(r'alt="[^"]*占位符[^"]*"', 'alt="图表"', content)
        # 移除所有在标签外的alt属性（防止被显示为文本）
        # 先处理形如: .png" alt="..." 的模式（在src属性后，但不在img标签内）
        content = re.sub(
            r'\.png"\s+alt="[^"]+"\s*>',
            r'.png">',
            content,
            flags=re.S
        )
        # 处理形如: src="...png" alt="..." 的模式（src属性后直接跟alt，不在标签内）
        content = re.sub(
            r'(src="[^"]+\.png")\s+alt="[^"]+"\s*>',
            r'\1>',
            content,
            flags=re.S
        )
        # 处理形如: </div>" alt="..." 的模式
        content = re.sub(
            r'</div>"\s*alt="[^"]+"[^>]*>',
            r'</div>',
            content,
            flags=re.S
        )
        # 处理形如: 文本 alt="..." 的模式（不在任何标签内）
        content = re.sub(
            r'([^<>"])\s+alt="[^"]+"\s*',
            r'\1 ',
            content
        )
        # 处理形如: > alt="..." 的模式（在标签后）
        content = re.sub(
            r'>\s+alt="[^"]+"\s*',
            r'>',
            content
        )
        
        # 处理图片路径
        processed, missing = replace_image_paths(content)
        if missing:
            # 过滤掉已知的无效路径（如Height_Distribution等）
            valid_missing = [m for m in missing if 'Height_Distribution' not in m and 'Physical_Deviation' not in m]
            if valid_missing:
                st.warning(f"⚠️ {len(valid_missing)} 张图片未找到")
        
        # 构建完整的HTML用于渲染
        theme = st.session_state.get('theme', 'light')
        if theme == 'dark':
            bg_color, text_color, card_bg = "#1e1e1e", "#ecf0f1", "#2d2d2d"
            primary = "#5dade2"
        else:
            bg_color, text_color, card_bg = "#f5f7fa", "#2c3e50", "#ffffff"
            primary = "#3498db"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: {bg_color}; color: {text_color}; 
                    margin: 0; padding: 20px; line-height: 1.7;
                }}
                .section-card {{ 
                    background: transparent; border-radius: 0; padding: 0; 
                    margin-bottom: 20px; box-shadow: none;
                }}
                .chart-wrapper {{ 
                    background: transparent; border-radius: 0; padding: 0; 
                    margin: 15px 0; text-align: center;
                }}
                h2 {{ color: {primary}; font-size: 22px; border-bottom: 2px solid {primary}; padding-bottom: 10px; }}
                h3 {{ color: {text_color}; font-size: 18px; border-left: 4px solid {primary}; padding-left: 10px; }}
                img {{ max-width: 100%; height: auto; border-radius: 4px; }}
                p {{ margin-bottom: 12px; color: {text_color}; }}
                ul, ol {{ margin-left: 20px; color: {text_color}; }}
                li {{ margin-bottom: 6px; color: {text_color}; }}
                div {{ color: {text_color}; }}
                span {{ color: {text_color}; }}
                .analysis-box {{ 
                    background: {'#3a3024' if theme=='dark' else '#fdf6ec'}; 
                    border-left: 4px solid #e6a23c; padding: 15px; margin: 15px 0; border-radius: 4px;
                }}
                .advice-item {{ 
                    background: {'#2d4a1f' if theme=='dark' else '#e8f5e9'}; 
                    border-left: 4px solid #4caf50; padding: 12px; margin: 10px 0; border-radius: 4px;
                }}
                .tech-pill {{
                    display: inline-block; background: {'#1a4a6a' if theme=='dark' else '#e3f2fd'};
                    color: {primary}; padding: 3px 8px; border-radius: 12px; font-size: 12px; margin: 2px;
                }}
            </style>
        </head>
        <body>
            {processed}
        </body>
        </html>
        """
        
        # 使用 components.html 正确渲染（移除key参数，某些版本不支持）
        components.html(
            html_content, 
            height=1800, 
            scrolling=True
        )
    
    # 决定显示顺序：仅展示文字报告
    last_analysis = st.session_state.get('last_analysis', None)

    # 注意：自动刷新逻辑已在任务完成检测处直接调用 st.rerun()，这里不再需要
    # 加载KPI数据用于显示核心指标概览
    def load_kpi_data():
        """优先从最新数据文件计算KPI，失败时再回退到analysis_summary.json"""
        data_file = os.path.join(base_dir, 'base_function', 'output', 'cleaned_chip_data_final.csv')
        if os.path.exists(data_file):
            try:
                import pandas as pd
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

                open_count = status_counts.get(-1, 0)
                severe_count = status_counts.get(2, 0)

                return {
                    'total': total,
                    'pass_rate': (pass_count / total * 100) if total > 0 else 0,
                    'pass_count': pass_count,
                    'fail_count': fail_count,
                    'open_count': open_count,
                    'severe_count': severe_count,
                    'open_rate': (open_count / total * 100) if total > 0 else 0,
                    'severe_rate': (severe_count / total * 100) if total > 0 else 0
                }
            except Exception as e:
                print(f"⚠️ 从数据文件计算KPI失败: {e}")
        
        # 回退：从analysis_summary.json读取
        summary_file = os.path.join(base_dir, 'base_function', 'output', 'analysis_summary.json')
        if os.path.exists(summary_file):
            try:
                with open(summary_file, 'r', encoding='utf-8') as f:
                    summary = json.load(f)
                    if 'eda_analysis' in summary and 'yield_stats' in summary['eda_analysis']:
                        yield_stats = summary['eda_analysis']['yield_stats']
                        total = yield_stats.get('total', 0)
                        open_count = yield_stats.get('open_count', 0)
                        severe_count = yield_stats.get('severe_count', 0)
                        return {
                            'total': total,
                            'pass_rate': yield_stats.get('pass_rate', 0) * 100,
                            'pass_count': yield_stats.get('pass_count', 0),
                            'fail_count': yield_stats.get('fail_count', 0),
                            'open_count': open_count,
                            'severe_count': severe_count,
                            'open_rate': (open_count / total * 100) if total > 0 else 0,
                            'severe_rate': (severe_count / total * 100) if total > 0 else 0
                        }
            except Exception as e:
                print(f"⚠️ 加载KPI数据失败: {e}")
        
        return None
    
    # 显示核心指标概览（如果有数据）
    kpi_data = load_kpi_data()
    if kpi_data:
        theme = st.session_state.get('theme', 'light')
        if theme == 'dark':
            bg_color, text_color, card_bg = "#1e1e1e", "#ecf0f1", "#2d2d2d"
            primary = "#5dade2"
        else:
            bg_color, text_color, card_bg = "#f5f7fa", "#2c3e50", "#ffffff"
            primary = "#3498db"
        
        kpi_html = f"""
        <div class="section-card" style="background: transparent; padding: 0; box-shadow: none; margin-bottom: 30px;">
          <h2 style="border-bottom: none; margin-bottom: 10px; padding-left: 10px; color: {primary};">1. 核心指标</h2>
          
          <div style="display: flex; flex-wrap: wrap; justify-content: space-between; gap: 20px; margin-bottom: 20px;">
            <div style="flex: 1 1 220px; min-width: 220px; background: {card_bg}; border-radius: 12px; padding: 24px 18px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
              <div style="font-size: 16px; color: {text_color}; font-weight: 600; margin-bottom: 15px;">整体良品率</div>
              <div style="font-size: 38px; font-weight: bold; color: {primary}; margin-bottom: 10px;">{kpi_data['pass_rate']:.1f}%</div>
              <div style="font-size: 13px; color: {text_color};">基准线，含轻微压连(1)与正常(0)</div>
            </div>
            
            <div style="flex: 1 1 220px; min-width: 220px; background: {card_bg}; border-radius: 12px; padding: 24px 18px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
              <div style="font-size: 16px; color: {text_color}; font-weight: 600; margin-bottom: 15px;">虚焊失效率</div>
              <div style="font-size: 38px; font-weight: bold; color: #e74c3c; margin-bottom: 10px;">{kpi_data['open_rate']:.1f}%</div>
              <div style="font-size: 13px; color: {text_color};">虚焊(-1) {kpi_data['open_count']}颗｜风险：断路</div>
            </div>
            
            <div style="flex: 1 1 220px; min-width: 220px; background: {card_bg}; border-radius: 12px; padding: 24px 18px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
              <div style="font-size: 16px; color: {text_color}; font-weight: 600; margin-bottom: 15px;">严重压连率</div>
              <div style="font-size: 38px; font-weight: bold; color: #f39c12; margin-bottom: 10px;">{kpi_data['severe_rate']:.1f}%</div>
              <div style="font-size: 13px; color: {text_color};">严重压连(2) {kpi_data['severe_count']}颗｜风险：短路</div>
            </div>
          </div>
        </div>
        """
        components.html(
            f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: {bg_color}; color: {text_color}; margin: 0; padding: 20px; overflow: visible; }}
                    .section-card {{ background: {card_bg}; border-radius: 8px; padding: 25px; margin-bottom: 20px; overflow: visible; }}
                    h2 {{ color: {primary}; font-size: 22px; border-bottom: 2px solid {primary}; padding-bottom: 10px; }}
                </style>
            </head>
            <body>{kpi_html}</body>
            </html>
            """,
            height=320,
            scrolling=False
        )
        st.markdown("---")
    
    # 显示报告（仅展示文字报告）
    if not text_report:
        st.info("ℹ️ 尚未生成描述性报告。请点击上方按钮开始分析。")
    else:
        render_report(text_report, "📝 文字识别分析报告（基于统计数据）", text_time_str, "text")
1