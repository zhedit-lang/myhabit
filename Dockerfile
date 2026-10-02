FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data \
    DB_PATH=/data/myhabit.db \
    PORT=8000

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 数据库位于 /data。部署时请务必把持久化卷挂到这个路径，
# 否则容器重建（重新部署）时打卡数据会丢失。
EXPOSE 8000

CMD ["python", "main.py"]
