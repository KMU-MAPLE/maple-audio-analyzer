FROM python:3.9-slim-bullseye

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# TensorFlow 최적화 환경 변수 추가
ENV TF_ENABLE_ONEDNN_OPTS=0

WORKDIR /srv

# 기본 시스템 패키지 및 SSH 관련 패키지 설치
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libsndfile1 \
    ffmpeg \
    git \
    ssh \
    autossh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# 멀티 아키텍처 지원을 위한 pip 설치 최적화
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# NumPy 오류 방지용 심볼릭 링크 (ARM 호환성 확보)
RUN ln -s /usr/lib/aarch64-linux-gnu/libf77blas.so.3 /usr/lib/aarch64-linux-gnu/libf77blas.so || true

COPY . .

# 모델 디렉토리 및 파일 설정
RUN mkdir -p /srv/models
RUN if [ -f "guitar_technique_classifier.keras" ]; then cp guitar_technique_classifier.keras /srv/models/; fi

# SSH 디렉토리 생성 및 권한 설정
RUN mkdir -p /root/.ssh && chmod 700 /root/.ssh

# 시작 스크립트 설정
COPY scripts/docker_entrypoint.sh /usr/local/bin/docker_entrypoint.sh
RUN chmod +x /usr/local/bin/docker_entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/docker_entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]