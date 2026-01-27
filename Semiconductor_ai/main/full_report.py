import streamlit as st
import pandas as pd
import os
import json
import base64
import re

def get_image_base64(image_path):
    if not os.path.exists(image_path):
        return ""
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')

def generate_full_report_html():
    # 1. 获取项目路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(current_dir) # Semiconductor_ai
    base_dir = os.path.dirname(project_dir)    # LZR_Project
    output_dir = os.path.join(base_dir, 'base_function', 'output')

    # 2. 读取描述性统计内容 (HTML片段)
    text_results_file = os.path.join(output_dir, 'ai_text_analysis_results.json')
    descriptive_html = ""
    
    # 2.1 尝试读取核心指标 (KPI) 数据
    kpi_html = ""
    try:
        if os.path.exists(text_results_file):
            with open(text_results_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # 优先尝试从 analysis_data.kpi_stats 读取 (这是 ai_text_analysis_results.json 的主要结构)
                kpi_stats = data.get('analysis_data', {}).get('kpi_stats', {})
                
                # 如果没有，尝试从 summary_stats 读取 (旧结构或 analysis_summary.json 结构)
                if not kpi_stats:
                    summary = data.get('summary_stats', {})
                    if summary and 'eda_analysis' in summary:
                        yield_stats = summary['eda_analysis'].get('yield_stats', {})
                        if yield_stats:
                            # 转换旧结构数据
                            total = yield_stats.get('total', 0)
                            kpi_stats = {
                                'pass_rate': yield_stats.get('pass_rate', 0) * 100, # 旧结构通常是小数
                                'open_rate': (yield_stats.get('open_count', 0) / total * 100) if total > 0 else 0,
                                'severe_rate': (yield_stats.get('severe_count', 0) / total * 100) if total > 0 else 0,
                                'open_count': yield_stats.get('open_count', 0),
                                'severe_count': yield_stats.get('severe_count', 0)
                            }

                if kpi_stats:
                    pass_rate = kpi_stats.get('pass_rate', 0)
                    open_rate = kpi_stats.get('open_rate', 0)
                    severe_rate = kpi_stats.get('severe_rate', 0)
                    open_count = kpi_stats.get('open_count', 0)
                    severe_count = kpi_stats.get('severe_count', 0)
                    
                    kpi_html = f"""
                    <div class="section-card" style="background: transparent; padding: 0; box-shadow: none; margin-bottom: 30px;">
                      <h3 style="border-bottom: none; margin-bottom: 10px; padding-left: 10px;">1. 核心指标</h3>
                      
                      <div style="display: flex; flex-wrap: wrap; justify-content: space-between; gap: 20px; margin-bottom: 20px;">
                        <div style="flex: 1 1 220px; min-width: 220px; background: #fff; border-radius: 12px; padding: 24px 18px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
                          <div style="font-size: 16px; color: #2c3e50; font-weight: 600; margin-bottom: 15px;">整体良品率</div>
                          <div style="font-size: 38px; font-weight: bold; color: #3498db; margin-bottom: 10px;">{pass_rate:.1f}%</div>
                          <div style="font-size: 13px; color: #7f8c8d;">基准线，含轻微压连(1)与正常(0)</div>
                        </div>
                        
                        <div style="flex: 1 1 220px; min-width: 220px; background: #fff; border-radius: 12px; padding: 24px 18px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
                          <div style="font-size: 16px; color: #2c3e50; font-weight: 600; margin-bottom: 15px;">虚焊失效率</div>
                          <div style="font-size: 38px; font-weight: bold; color: #e74c3c; margin-bottom: 10px;">{open_rate:.1f}%</div>
                          <div style="font-size: 13px; color: #7f8c8d;">虚焊(-1) {open_count}颗｜风险：断路</div>
                        </div>
                        
                        <div style="flex: 1 1 220px; min-width: 220px; background: #fff; border-radius: 12px; padding: 24px 18px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
                          <div style="font-size: 16px; color: #2c3e50; font-weight: 600; margin-bottom: 15px;">严重压连率</div>
                          <div style="font-size: 38px; font-weight: bold; color: #f39c12; margin-bottom: 10px;">{severe_rate:.1f}%</div>
                          <div style="font-size: 13px; color: #7f8c8d;">严重压连(2) {severe_count}颗｜风险：短路</div>
                        </div>
                      </div>
                    </div>
                    """
    except Exception as e:
        print(f"KPI load error: {e}")

    if os.path.exists(text_results_file):
        try:
            with open(text_results_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                descriptive_html = data.get('comprehensive_report', '')
        except:
            descriptive_html = "<p>暂无描述性统计报告。</p>"
    
    # 将 KPI 插入到描述性报告的最前面
    if kpi_html:
        # 如果描述性报告已经包含了 <h2>...</h2> 这样的结构，我们尽量插在它后面或者前面
        # 这里简单粗暴地拼接在前面，作为 "1. 核心指标"
        descriptive_html = kpi_html + descriptive_html

    # 处理描述性报告中的图片路径
    def replace_img_src(match):
        src = match.group(1)
        # 尝试找到该文件的绝对路径
        if 'output/analysis_report' in src:
            filename = os.path.basename(src)
            abs_path = os.path.join(output_dir, 'analysis_report', filename)
            b64 = get_image_base64(abs_path)
            if b64:
                return f'src="data:image/png;base64,{b64}"'
        elif 'output/ml_report' in src:
            filename = os.path.basename(src)
            abs_path = os.path.join(output_dir, 'ml_report', filename)
            b64 = get_image_base64(abs_path)
            if b64:
                return f'src="data:image/png;base64,{b64}"'
        elif 'output/position_analysis_v2' in src:
            filename = os.path.basename(src)
            abs_path = os.path.join(output_dir, 'position_analysis_v2', filename)
            b64 = get_image_base64(abs_path)
            if b64:
                return f'src="data:image/png;base64,{b64}"'
        return match.group(0)

    descriptive_html = re.sub(r'src="([^"]+)"', replace_img_src, descriptive_html)

    # 3. 读取深度挖掘内容
    deep_mining_html = ""
    if 'deep_mining_results' in st.session_state and st.session_state['deep_mining_results']:
        for res in st.session_state['deep_mining_results']:
            chart_name = res.get('chart_name', '未命名图表')
            image_path = res.get('image_path', '')
            analysis_text = res.get('analysis_text', '')
            
            # 解析 JSON 格式的分析文本
            try:
                if isinstance(analysis_text, str):
                    clean_json = analysis_text.replace('```json', '').replace('```', '').strip()
                    analysis_data = json.loads(clean_json)
                    key_findings = analysis_data.get('key_findings', [])
                    process_suggestions = analysis_data.get('process_suggestions', '')
                    detailed_analysis = analysis_data.get('detailed_analysis', '')
                    
                    analysis_html = "<ul>"
                    for k in key_findings:
                        analysis_html += f"<li>{k}</li>"
                    analysis_html += "</ul>"
                    analysis_html += f"<p><strong>工艺建议:</strong> {process_suggestions}</p>"
                    analysis_html += f"<p><strong>详细分析:</strong> {detailed_analysis}</p>"
                else:
                    analysis_html = str(analysis_text)
            except:
                analysis_html = str(analysis_text)

            # 图片转 base64
            img_b64 = get_image_base64(image_path)
            img_tag = f'<img src="data:image/png;base64,{img_b64}" style="max-width:100%;">' if img_b64 else ''

            deep_mining_html += f"""
            <div class="section-card">
                <h3>{chart_name}</h3>
                <div class="chart-wrapper">{img_tag}</div>
                <div class="analysis-box">
                    {analysis_html}
                </div>
            </div>
            """
    else:
        deep_mining_html = "<p>暂无深度挖掘分析结果。</p>"

    # 4. 读取最终建议
    suggestions_html = ""
    if 'final_suggestions' in st.session_state and st.session_state['final_suggestions']:
        sug_list = st.session_state['final_suggestions'].get('suggestions', [])
        for sug in sug_list:
            suggestions_html += f"""
            <div class="suggestion-card">
                <div class="suggestion-header">
                    <span class="suggestion-icon">{sug.get('icon', '💡')}</span>
                    <span class="suggestion-title">{sug.get('title', '优化建议')}</span>
                </div>
                <div class="suggestion-content">
                    {sug.get('content', '')}
                </div>
            </div>
            """
    else:
        suggestions_html = "<p>暂无最终总结建议。</p>"
    
    # 5. 组装完整 HTML
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>半导体工艺优化全景报告</title>
        <style>
            body {{ font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f4f6f9; }}
            h1, h2, h3 {{ color: #2c3e50; }}
            h1 {{ text-align: center; border-bottom: 2px solid #3498db; padding-bottom: 10px; margin-bottom: 30px; }}
            .section-card {{ background: #fff; border-radius: 8px; padding: 25px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }}
            .chart-wrapper {{ text-align: center; margin: 20px 0; }}
            img {{ max-width: 100%; border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
            .analysis-box {{ background: #f8f9fa; border-left: 4px solid #3498db; padding: 15px; margin-top: 15px; }}
            .suggestion-card {{ background-color: #f0f9eb; border-radius: 8px; padding: 20px; margin-bottom: 15px; border-left: 5px solid #67c23a; box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05); }}
            .suggestion-header {{ display: flex; align-items: center; margin-bottom: 10px; }}
            .suggestion-icon {{ font-size: 24px; margin-right: 12px; }}
            .suggestion-title {{ font-size: 18px; font-weight: 600; color: #2c3e50; }}
            .suggestion-content {{ color: #5e6d82; font-size: 15px; margin-left: 36px; }}
            .tech-pill {{ background: #e8f4fd; color: #3498db; padding: 2px 8px; border-radius: 12px; font-size: 0.9em; font-weight: 500; }}
        </style>
    </head>
    <body>
        <h1>📊 半导体工艺优化全景报告</h1>
        <p style="text-align: center; color: #666;">生成日期: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}</p>
        
        <h2>第一部分：描述性统计分析</h2>
        {descriptive_html}
        
        <h2>第二部分：深度挖掘与归因</h2>
        {deep_mining_html}
        
        <h2>第三部分：总结与工艺优化建议</h2>
        {suggestions_html}
        
        <div style="text-align: center; margin-top: 50px; color: #999; font-size: 12px;">
            Generated by AI Semiconductor Production Assistant
        </div>
    </body>
    </html>
    """
    return full_html

def render_download_section(t):
    st.subheader("📥 完整报告导出")
    st.info("该模块将整合【描述性统计分析】、【深度挖掘】以及【工艺优化建议】，生成一份包含所有图表和智能分析的可离线阅读报告。")
    
    # 检查是否有数据
    has_stats = False
    has_mining = st.session_state.get('deep_mining_results') is not None
    has_suggestions = st.session_state.get('final_suggestions') is not None
    
    # 简单的检查：看文件是否存在
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(os.path.dirname(current_dir))
    text_results_file = os.path.join(base_dir, 'base_function', 'output', 'ai_text_analysis_results.json')
    if os.path.exists(text_results_file):
        has_stats = True
        
    if not (has_stats or has_mining):
        st.warning("⚠️ 暂无分析数据。请先运行【描述性统计分析】或【深度挖掘】模块。")
        # 即使没有数据也允许尝试生成，可能只是部分缺失
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("#### 包含内容：")
        st.markdown(f"- 📊 描述性统计报告: {'✅' if has_stats else '❌'}")
        st.markdown(f"- 🔍 深度挖掘分析: {'✅' if has_mining else '❌'}")
        st.markdown(f"- 💡 工艺优化建议: {'✅' if has_suggestions else '❌'}")

    with col2:
        if st.button("🚀 生成完整 HTML 报告", type="primary"):
            with st.spinner("正在打包所有图表和分析结果..."):
                try:
                    html_content = generate_full_report_html()
                    # 编码为 bytes
                    b64 = base64.b64encode(html_content.encode()).decode()
                    href = f'<a href="data:text/html;base64,{b64}" download="Semiconductor_Analysis_Report.html" style="text-decoration:none; color:white; background-color:#4CAF50; padding:10px 20px; border-radius:5px; font-weight:bold;">📥 点击下载完整报告 (HTML)</a>'
                    st.markdown(href, unsafe_allow_html=True)
                    st.success("报告生成成功！请点击上方按钮下载。")
                except Exception as e:
                    st.error(f"报告生成失败: {str(e)}")
