import streamlit as st
import pandas as pd
import os
import json
import base64
import re
import io
try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle, PageBreak, KeepTogether, ListFlowable, ListItem
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch, mm
from reportlab.lib.fonts import addMapping
from bs4 import BeautifulSoup, NavigableString, Tag
import urllib.parse

def get_image_base64(image_path):
    if not os.path.exists(image_path):
        return ""
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')

def parse_html_to_flowables(html_content, styles, output_dir):
    """
    Parse HTML content and convert to ReportLab flowables.
    Handles headings, paragraphs, images, lists, and special div containers.
    """
    flowables = []
    # Pre-process HTML to remove newlines that might cause issues in text extraction
    soup = BeautifulSoup(html_content, 'html.parser')
    
    def extract_clean_text(tag):
        """Recursively extract text with basic formatting (b, i) from a tag."""
        text = ""
        for child in tag.children:
            if isinstance(child, NavigableString):
                text += str(child)
            elif isinstance(child, Tag):
                if child.name in ['strong', 'b']:
                    text += f"<b>{extract_clean_text(child)}</b>"
                elif child.name in ['em', 'i']:
                    text += f"<i>{extract_clean_text(child)}</i>"
                elif child.name == 'br':
                    text += "<br/>"
                else:
                    # For span, font, div, etc., just get text content
                    # This ensures we don't drop content from unsupported tags
                    text += extract_clean_text(child)
        return text

    def process_element(element):
        if isinstance(element, NavigableString):
            text = str(element).strip()
            if text:
                flowables.append(Paragraph(text, styles['CN_Normal']))
            return

        if element.name in ['h1', 'h2']:
            # Use CN_Heading2 for h2 to match the "2.1" hierarchy usually found in h2
            flowables.append(Paragraph(element.get_text().strip(), styles['CN_Heading2']))
        elif element.name == 'h3':
            flowables.append(Paragraph(element.get_text().strip(), styles['CN_Heading3']))
        elif element.name == 'p':
            # Check if p contains image
            img = element.find('img')
            if img:
                process_image(img)
                # Process remaining text in p if any
                # Remove img tags to get text
                element_copy = BeautifulSoup(str(element), 'html.parser').p
                if element_copy.find('img'):
                    element_copy.find('img').decompose()
                
                text_content = extract_clean_text(element_copy)
                if text_content.strip():
                    flowables.append(Paragraph(text_content, styles['CN_Normal']))
            else:
                # Regular paragraph
                text_content = extract_clean_text(element)
                if text_content.strip():
                    flowables.append(Paragraph(text_content, styles['CN_Normal']))
                
        elif element.name == 'ul':
            list_items = []
            for li in element.find_all('li', recursive=False):
                text_content = extract_clean_text(li)
                list_items.append(ListItem(Paragraph(text_content.strip(), styles['CN_Bullet'])))
            if list_items:
                flowables.append(ListFlowable(list_items, bulletType='bullet', start='•', leftIndent=20))
                flowables.append(Spacer(1, 5))
                
        elif element.name == 'div':
            if 'chart-wrapper' in element.get('class', []):
                img = element.find('img')
                if img:
                    process_image(img)
            elif 'analysis-box' in element.get('class', []):
                box_content = []
                for child in element.children:
                    if child.name == 'p':
                        text_content = extract_clean_text(child)
                        if text_content.strip():
                            box_content.append(Paragraph(text_content.strip(), styles['CN_Normal']))
                    elif child.name == 'ul':
                        for li in child.find_all('li'):
                            text_content = extract_clean_text(li)
                            if text_content.strip():
                                box_content.append(Paragraph(f"• {text_content.strip()}", styles['CN_Bullet']))
                
                if box_content:
                    t = Table([[box_content]], colWidths=[460])
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8f9fa')),
                        ('BOX', (0,0), (-1,-1), 0.5, colors.lightgrey),
                        ('LINEBEFORE', (0,0), (0,-1), 4, colors.HexColor('#3498db')),
                        ('PADDING', (0,0), (-1,-1), 10),
                    ]))
                    flowables.append(t)
                    flowables.append(Spacer(1, 10))
            elif 'section-card' in element.get('class', []):
                for child in element.children:
                    process_element(child)
            else:
                for child in element.children:
                    process_element(child)

        elif element.name == 'img':
             process_image(element)

    def process_image(img_tag):
                  src = img_tag.get('src')
                  if not src: return
                  
                  # Decode URL encoding (e.g. %20)
                  src = urllib.parse.unquote(src)
                  
                  # Resolve absolute path
                  abs_path = None
                  
                  # Strategy 1: Direct match in output subdirs
                  potential_paths = [
                      os.path.join(output_dir, 'analysis_report', os.path.basename(src)),
                      os.path.join(output_dir, 'ml_report', os.path.basename(src)),
                      os.path.join(output_dir, 'position_analysis_v2', os.path.basename(src))
                  ]
                  
                  for p in potential_paths:
                      if os.path.exists(p):
                          abs_path = p
                          break
                  
                  # Strategy 2: If src is already relative to project root or something else
                  if not abs_path:
                       # Try assuming src is relative to output_dir
                       # If src starts with output/, strip it
                       clean_src = src.replace('output/', '')
                       p = os.path.join(output_dir, clean_src)
                       if os.path.exists(p):
                           abs_path = p
                       else:
                           # Try relative to base_function
                           p2 = os.path.join(output_dir, '..', src)
                           if os.path.exists(p2):
                               abs_path = p2
                  
                  if abs_path and os.path.exists(abs_path):
                      try:
                          img = RLImage(abs_path)
                          img_width = 460
                          aspect = img.imageHeight / img.imageWidth
                          img.drawWidth = img_width
                          img.drawHeight = img_width * aspect
                          img.hAlign = 'CENTER'
                          flowables.append(Spacer(1, 5))
                          flowables.append(img)
                          flowables.append(Spacer(1, 10))
                      except Exception as e:
                          flowables.append(Paragraph(f"<font color='red'>图片加载失败: {os.path.basename(src)}</font>", styles['CN_Normal']))
                  else:
                      flowables.append(Paragraph(f"<font color='red'>图片未找到: {os.path.basename(src)}</font>", styles['CN_Normal']))

    # Start processing
    # Handle fragment vs full document
    if soup.body:
        for child in soup.body.children:
            process_element(child)
    else:
        for child in soup.children:
            process_element(child)
            
    return flowables

def generate_full_report_pdf():
    if WEASYPRINT_AVAILABLE:
        try:
            html_content = generate_full_report_html()
            simhei_candidates = [
                "/home/a/LZR_Project/Semiconductor_ai/main/assets/SimHei.ttf",
                "/home/a/LZR_Project/SimHei.ttf",
            ]
            simhei_path = None
            for p in simhei_candidates:
                if os.path.exists(p):
                    simhei_path = p
                    break
            if simhei_path:
                css_str = f"@font-face {{ font-family: 'SimHei'; src: url('file://{simhei_path}'); }} body {{ font-family: 'SimHei','Microsoft YaHei','Noto Sans CJK',sans-serif; }} h1, h2, h3 {{ font-family: 'SimHei','Microsoft YaHei','Noto Sans CJK',sans-serif; }}"
            else:
                css_str = "body { font-family: 'Noto Sans CJK','Microsoft YaHei',sans-serif; }"
            pdf_bytes = HTML(string=html_content, base_url=os.path.dirname(os.path.abspath(__file__))).write_pdf(stylesheets=[CSS(string=css_str)])
            return pdf_bytes
        except Exception:
            pass
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    
    # Register Font and FAKE BOLD mapping
    font_name = 'Helvetica' # Default fallback
    
    font_candidates = [
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "NotoSansCJK"),
        ("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf", "DroidSansFallback"),
        ("/usr/share/fonts/truetype/arphic/uming.ttc", "UMing"),
        ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", "MicroHei")
    ]
    
    for font_path, font_family in font_candidates:
        if os.path.exists(font_path):
            try:
                # Register the regular font
                pdfmetrics.registerFont(TTFont(font_family, font_path))
                # Register the SAME font as Bold, Italic, BoldItalic to prevent missing glyphs/tofu
                pdfmetrics.registerFont(TTFont(f'{font_family}-Bold', font_path))
                pdfmetrics.registerFont(TTFont(f'{font_family}-Italic', font_path))
                pdfmetrics.registerFont(TTFont(f'{font_family}-BoldItalic', font_path))
                
                # Add mapping: family, bold, italic, name
                addMapping(font_family, 0, 0, font_family)
                addMapping(font_family, 0, 1, f'{font_family}-Italic')
                addMapping(font_family, 1, 0, f'{font_family}-Bold')
                addMapping(font_family, 1, 1, f'{font_family}-BoldItalic')
                
                font_name = font_family
                break
            except Exception as e:
                print(f"Font registration failed for {font_path}: {e}")
            
    styles = getSampleStyleSheet()
    # Define Chinese Styles
    styles.add(ParagraphStyle(name='CN_Title', parent=styles['Title'], fontName=font_name, fontSize=22, leading=28, spaceAfter=30, alignment=1))
    styles.add(ParagraphStyle(name='CN_Heading1', parent=styles['Heading1'], fontName=font_name, fontSize=16, leading=22, spaceBefore=20, spaceAfter=12, textColor=colors.HexColor('#2c3e50')))
    styles.add(ParagraphStyle(name='CN_Heading2', parent=styles['Heading2'], fontName=font_name, fontSize=14, leading=20, spaceBefore=15, spaceAfter=8, textColor=colors.HexColor('#34495e')))
    styles.add(ParagraphStyle(name='CN_Heading3', parent=styles['Heading3'], fontName=font_name, fontSize=12, leading=16, spaceBefore=10, spaceAfter=5, textColor=colors.HexColor('#7f8c8d')))
    styles.add(ParagraphStyle(name='CN_Normal', parent=styles['Normal'], fontName=font_name, fontSize=10.5, leading=16, spaceAfter=6, alignment=0))
    styles.add(ParagraphStyle(name='CN_Bullet', parent=styles['Normal'], fontName=font_name, fontSize=10.5, leading=16, leftIndent=10))

    Story = []
    
    # --- 1. Cover / Header ---
    Story.append(Paragraph("半导体器件生产助手 - 工艺优化全景报告", styles['CN_Title']))
    Story.append(Paragraph(f"生成日期: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}", styles['CN_Normal']))
    Story.append(Spacer(1, 20))
    
    # --- 2. KPI Section (Part 1) ---
    Story.append(Paragraph("1. 核心指标概览", styles['CN_Heading1']))
    
    # Load KPI data
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(os.path.dirname(current_dir))
    output_dir = os.path.join(base_dir, 'base_function', 'output')
    text_results_file = os.path.join(output_dir, 'ai_text_analysis_results.json')
    
    kpi_data = {}
    if os.path.exists(text_results_file):
        try:
            with open(text_results_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                kpi_data = data.get('analysis_data', {}).get('kpi_stats', {})
                if not kpi_data:
                    summary = data.get('summary_stats', {})
                    if summary and 'eda_analysis' in summary:
                        yield_stats = summary['eda_analysis'].get('yield_stats', {})
                        if yield_stats:
                            total = yield_stats.get('total', 0)
                            kpi_data = {
                                'pass_rate': yield_stats.get('pass_rate', 0) * 100,
                                'open_rate': (yield_stats.get('open_count', 0) / total * 100) if total > 0 else 0,
                                'severe_rate': (yield_stats.get('severe_count', 0) / total * 100) if total > 0 else 0,
                                'open_count': yield_stats.get('open_count', 0),
                                'severe_count': yield_stats.get('severe_count', 0)
                            }
        except Exception as e:
            Story.append(Paragraph(f"数据加载失败: {e}", styles['CN_Normal']))
        if kpi_data:
            pass_rate = kpi_data.get('pass_rate', 0)
            open_rate = kpi_data.get('open_rate', 0)
            severe_rate = kpi_data.get('severe_rate', 0)
            open_count = kpi_data.get('open_count', 0)
            severe_count = kpi_data.get('severe_count', 0)
            kpi_table_data = [
                [
                    Paragraph(f"<b>整体良品率</b>", styles['CN_Normal']),
                    Paragraph(f"<b>虚焊失效率</b>", styles['CN_Normal']),
                    Paragraph(f"<b>严重压连率</b>", styles['CN_Normal'])
                ],
                [
                    Paragraph(f"<font color='#3498db' size=14><b>{pass_rate:.1f}%</b></font>", styles['CN_Normal']),
                    Paragraph(f"<font color='#e74c3c' size=14><b>{open_rate:.1f}%</b></font>", styles['CN_Normal']),
                    Paragraph(f"<font color='#f39c12' size=14><b>{severe_rate:.1f}%</b></font>", styles['CN_Normal'])
                ],
                [
                    Paragraph("基准线", styles['CN_Normal']),
                    Paragraph(f"数量: {open_count}", styles['CN_Normal']),
                    Paragraph(f"数量: {severe_count}", styles['CN_Normal'])
                ]
            ]
            t = Table(kpi_table_data, colWidths=[150, 150, 150])
            t.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#e8f6fd')),
                ('BACKGROUND', (1,0), (1,-1), colors.HexColor('#fdecec')),
                ('BACKGROUND', (2,0), (2,-1), colors.HexColor('#fef6e4')),
                ('BOX', (0,0), (-1,-1), 0.5, colors.grey),
                ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey),
                ('PADDING', (0,0), (-1,-1), 12),
            ]))
            Story.append(t)
            Story.append(Spacer(1, 20))
        else:
            Story.append(Paragraph(f"暂无核心指标数据 (Data not found at {text_results_file})", styles['CN_Normal']))
    
    Story.append(Paragraph("2. 描述性统计分析", styles['CN_Heading1']))
    if os.path.exists(text_results_file):
        try:
            with open(text_results_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                html_content = data.get('comprehensive_report', '')
                if html_content:
                    soup = BeautifulSoup(html_content, 'html.parser')
                    first_h2 = soup.find('h2')
                    if first_h2 and first_h2.get_text().strip().startswith('2.'):
                        first_h2.decompose()
                    flowables = parse_html_to_flowables(str(soup), styles, output_dir)
                    Story.extend(flowables)
        except Exception as e:
            Story.append(Paragraph(f"报告解析错误: {e}", styles['CN_Normal']))
    Story.append(PageBreak())
    Story.append(Paragraph("3. 深度挖掘与归因分析", styles['CN_Heading1']))
    if 'deep_mining_results' in st.session_state and st.session_state['deep_mining_results']:
        for res in st.session_state['deep_mining_results']:
            header_elements = []
            chart_name = res.get('chart_name', '未命名图表')
            header_elements.append(Paragraph(chart_name, styles['CN_Heading2']))
            image_path = res.get('image_path', '')
            if image_path and os.path.exists(image_path):
                try:
                    im = RLImage(image_path)
                    max_w = 460
                    if im.drawWidth > max_w:
                        ratio = max_w / im.drawWidth
                        im.drawWidth = max_w
                        im.drawHeight = im.drawHeight * ratio
                    header_elements.append(im)
                    header_elements.append(Spacer(1, 10))
                except:
                    header_elements.append(Paragraph(f"<font color='red'>图片加载失败: {image_path}</font>", styles['CN_Normal']))
            Story.append(KeepTogether(header_elements))
            analysis_text = res.get('analysis_text', '')
            analysis_content = []
            try:
                if isinstance(analysis_text, str):
                    clean_json = analysis_text.replace('```json', '').replace('```', '').strip()
                    if clean_json.startswith('{'):
                        analysis_data = json.loads(clean_json)
                        if 'key_findings' in analysis_data:
                            analysis_content.append(Paragraph("<b>📊 关键发现:</b>", styles['CN_Normal']))
                            for k in analysis_data['key_findings']:
                                analysis_content.append(Paragraph(f"• {k}", styles['CN_Bullet']))
                            analysis_content.append(Spacer(1, 6))
                        if 'process_suggestions' in analysis_data:
                            analysis_content.append(Paragraph(f"<b>💡 工艺建议:</b> {analysis_data['process_suggestions']}", styles['CN_Normal']))
                            analysis_content.append(Spacer(1, 6))
                        if 'detailed_analysis' in analysis_data:
                            analysis_content.append(Paragraph(f"<b>🔍 详细分析:</b> {analysis_data['detailed_analysis']}", styles['CN_Normal']))
                    else:
                        analysis_content.append(Paragraph(clean_json, styles['CN_Normal']))
                else:
                    analysis_content.append(Paragraph(str(analysis_text), styles['CN_Normal']))
            except:
                analysis_content.append(Paragraph(str(analysis_text), styles['CN_Normal']))
            if analysis_content:
                t = Table([[analysis_content]], colWidths=[460])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8f9fa')),
                    ('BOX', (0,0), (-1,-1), 0.5, colors.lightgrey),
                    ('LINEBEFORE', (0,0), (0,-1), 4, colors.HexColor('#3498db')),
                    ('PADDING', (0,0), (-1,-1), 10),
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ]))
                Story.append(t)
            Story.append(Spacer(1, 20))
            
    else:
        Story.append(Paragraph("暂无深度挖掘分析结果。", styles['CN_Normal']))
        
    # --- 5. Final Suggestions (Part 4) ---
    Story.append(PageBreak())
    Story.append(Paragraph("4. 总结与工艺优化建议", styles['CN_Heading1']))
    
    if 'final_suggestions' in st.session_state and st.session_state['final_suggestions']:
        sug_list = st.session_state['final_suggestions'].get('suggestions', [])
        for sug in sug_list:
            icon = sug.get('icon', '')
            title = sug.get('title', '优化建议')
            content = sug.get('content', '')
            
            # Card style
            title_para = Paragraph(f"{icon} <b>{title}</b>", styles['CN_Heading2'])
            content_para = Paragraph(content, styles['CN_Normal'])
            
            t = Table([[title_para], [content_para]], colWidths=[460])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f0f9eb')),
                ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#e1f3d8')),
                ('LINEBEFORE', (0,0), (0,-1), 5, colors.HexColor('#67c23a')),
                ('PADDING', (0,0), (-1,-1), 12),
                ('BOTTOMPADDING', (0,0), (0,0), 0),
                ('TOPPADDING', (0,1), (0,1), 5),
            ]))
            Story.append(t)
            Story.append(Spacer(1, 15))
    else:
        Story.append(Paragraph("暂无最终总结建议。", styles['CN_Normal']))

    doc.build(Story)
    buffer.seek(0)
    return buffer.getvalue()

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
        <title>半导体器件工艺优化全景报告</title>
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
        <h1>📊 半导体器件工艺优化全景报告</h1>
        <p style="text-align: center; color: #666;">生成日期: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}</p>
        
        <h2>第一部分：描述性统计分析</h2>
        {descriptive_html}
        
        <h2>第二部分：深度挖掘与归因</h2>
        {deep_mining_html}
        
        <h2>第三部分：总结与工艺优化建议</h2>
        {suggestions_html}
        
        <div style="text-align: center; margin-top: 50px; color: #999; font-size: 12px;">
            Generated by AI Semiconductor Device Production Assistant
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
        st.write("### 导出选项")
        sub_c1, sub_c2 = st.columns(2)
        
        with sub_c1:
            if st.button("🚀 生成 HTML 报告", type="primary"):
                with st.spinner("正在生成 HTML 报告..."):
                    try:
                        html_content = generate_full_report_html()
                        b64 = base64.b64encode(html_content.encode()).decode()
                        href = f'<a href="data:text/html;base64,{b64}" download="Semiconductor_Analysis_Report.html" style="text-decoration:none; color:white; background-color:#4CAF50; padding:10px 20px; border-radius:5px; font-weight:bold; display:block; text-align:center;">📥 下载 HTML</a>'
                        st.markdown(href, unsafe_allow_html=True)
                        st.success("HTML 报告就绪！")
                    except Exception as e:
                        st.error(f"HTML 生成失败: {str(e)}")
        
        with sub_c2:
            if st.button("📄 生成 PDF 报告"):
                with st.spinner("正在生成 PDF 报告..."):
                    try:
                        pdf_data = generate_full_report_pdf()
                        b64 = base64.b64encode(pdf_data).decode()
                        href = f'<a href="data:application/pdf;base64,{b64}" download="Semiconductor_Analysis_Report.pdf" style="text-decoration:none; color:white; background-color:#E74C3C; padding:10px 20px; border-radius:5px; font-weight:bold; display:block; text-align:center;">📥 下载 PDF</a>'
                        st.markdown(href, unsafe_allow_html=True)
                        st.success("PDF 报告就绪！")
                    except Exception as e:
                        st.error(f"PDF 生成失败: {str(e)}")
