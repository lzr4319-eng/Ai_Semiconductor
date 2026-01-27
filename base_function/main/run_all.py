import os
import subprocess
import sys

# 获取当前脚本所在目录的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(current_dir)  # base_function
base_dir = os.path.dirname(project_dir)  # LZR_Project

# 添加 Semiconductor_ai/main 到路径以导入数据清洗函数
semiconductor_ai_path = os.path.join(base_dir, 'Semiconductor_ai', 'main')
sys.path.insert(0, semiconductor_ai_path)

print("=" * 60)
print("🚀 开始执行完整分析流程")
print("=" * 60)

# 1. 执行数据清洗（直接调用统一的数据清洗函数）
print("\n[步骤 1/6] 数据清洗...")
try:
    from stat_analysis import clean_data_from_file
    
    # 输入文件：优先使用 base_function/data/梳理版.csv，否则使用项目根目录的梳理版.csv
    input_file = os.path.join(project_dir, 'data', '梳理版.csv')
    if not os.path.exists(input_file):
        input_file = os.path.join(base_dir, '梳理版.csv')
    
    # 输出目录和文件
    output_dir = os.path.join(project_dir, 'output')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    output_file = os.path.join(output_dir, 'cleaned_chip_data_final.csv')
    
    if os.path.exists(input_file):
        result = clean_data_from_file(input_file, output_file)
        if result is None:
            print("⚠️ 数据清洗失败，但继续执行后续步骤...")
    else:
        print(f"⚠️ 找不到输入文件 {input_file}，跳过数据清洗步骤...")
except Exception as e:
    print(f"⚠️ 数据清洗异常: {e}，但继续执行后续步骤...")

# 2. 执行EDA分析
print("\n[步骤 2/6] EDA探索性数据分析...")
subprocess.run(['python', os.path.join(current_dir, 'eda.py')])

# 3. 执行机器学习分析
print("\n[步骤 3/6] 机器学习分析...")
subprocess.run(['python', os.path.join(current_dir, 'ml.py')])

# 4. 执行位置分析
print("\n[步骤 4/6] 位置效应分析...")
subprocess.run(['python', os.path.join(current_dir, 'posion.py')])

# 5. AI分析（优先尝试视觉分析，失败则使用文本分析）
print("\n[步骤 5/6] AI分析...")
print("  尝试方式1: 视觉图表分析...")
vision_success = False
try:
    result = subprocess.run(
        ['python', os.path.join(current_dir, 'ai_chart_analyzer.py')], 
        check=False,
        capture_output=True,
        text=True,
        timeout=600  # 10分钟总超时
    )
    if result.returncode == 0 and "分析结果已保存" in result.stdout:
        print("✅ 视觉分析完成")
        vision_success = True
    else:
        print("⚠️ 视觉分析未完成，尝试文本分析...")
except subprocess.TimeoutExpired:
    print("⚠️ 视觉分析超时，切换到文本分析...")
except Exception as e:
    print(f"⚠️ 视觉分析异常: {e}，切换到文本分析...")

if not vision_success:
    print("  尝试方式2: 文本分析（基于统计数据）...")
    try:
        subprocess.run(['python', os.path.join(current_dir, 'ai_text_analyzer.py')], check=False)
        print("✅ 文本分析完成")
    except Exception as e:
        print(f"⚠️ 文本分析也失败: {e}")
        print("   将使用静态报告内容")

# 6. 生成HTML报告（统一使用html_generate.py，已支持AI分析和动态KPI）
print("\n[步骤 6/6] 生成HTML报告...")
subprocess.run(['python', os.path.join(current_dir, 'html_generate.py')], check=False)
print("✅ HTML报告已生成")

print("\n" + "=" * 60)
print("🎉 所有数据处理流程已完成！")
print("=" * 60)