FROM python:3.12-slim

# 系统依赖：wkhtmltopdf（HTML→PDF）、中文字体
RUN apt-get update && apt-get install -y --no-install-recommends \
    wkhtmltopdf \
    fonts-noto-cjk \
    fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 依赖（可分离缓存层）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码（开发模式可挂载）
COPY . .

# 默认运行方式（可被 docker run 参数覆盖）
ENTRYPOINT ["python3", "run_and_send_pipeline.py"]

# 可通过环境变量配置
#   TEMPLATE=weekend_recap
#   PROFILE=dad
#   PROVIDER=aliyun
