# 使用官方的 Python 基础镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 复制项目文件&创建必要的文件夹
COPY requirements.txt .
COPY biz /app/biz
COPY index.py /app/index.py
COPY chat.py /app/chat.py
COPY prompt_templates.yml /app/prompt_templates.yml
RUN mkdir -p /app/log /app/data/repos

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 暴露 Flask 的端口
EXPOSE 7860

# 启动命令
CMD ["python", "chat.py"]