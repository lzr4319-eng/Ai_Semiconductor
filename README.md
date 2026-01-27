# AI Semiconductor Production Assistant

这是一个基于 AI 的半导体生产数据分析平台，提供从数据清洗、EDA 分析到机器学习归因和 AI 智能问答的全流程解决方案。

## 🚀 快速开始

### 1. 环境准备

确保你的电脑上安装了 Python 3.8 或更高版本。

建议创建一个虚拟环境来隔离项目依赖：

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境 (Windows)
venv\Scripts\activate

# 激活虚拟环境 (macOS/Linux)
source venv/bin/activate
```

### 2. 安装依赖

在项目根目录下运行以下命令，一键安装所有必需的 Python 库：

```bash
pip install -r requirements.txt
```

### 3. 运行项目

安装完成后，使用 Streamlit 启动应用：

```bash
streamlit run Semiconductor_ai/main/app.py
```

启动后，浏览器会自动打开 `http://localhost:8501`，你就可以看到分析界面了。

## 📂 项目结构

- **Semiconductor_ai/main/**: 包含 Streamlit 前端应用的核心代码 (`app.py` 为入口)。
- **base_function/**: 包含底层的分析算法和自动化处理脚本。
- **data/**: (可选) 存放待分析的数据文件。

## 🛠️ 主要功能

1.  **数据清洗**: 自动处理缺失值及异常数据。
2.  **统计概览**: 生成描述性统计报告。
3.  **深度挖掘**: 利用决策树和随机森林分析影响良率的关键特征。
4.  **AI 智能看板**: 对话式数据分析助手。
# LZR_project
