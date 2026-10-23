FROM python:3.13-slim
WORKDIR /app
COPY . /app
ENV BS_HOST=0.0.0.0 PORT=8000 BS_DB=/data/brandsentinel.db
VOLUME /data
EXPOSE 8000
USER nobody
CMD ["python3", "run.py"]
