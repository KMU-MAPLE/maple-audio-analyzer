# Elice 클라우드 GPU 추론 서버 설정 가이드

이 가이드는 Elice 클라우드 환경에서 BentoML 기반 오디오 분석 서비스를 설정하고 실행하는 방법을 설명합니다.

## 1. 사전 요구사항

- Elice 클라우드 계정 및 접속 정보 (SSH 키 포함)
- Python 3.9 이상 (Python 3.10 또는 3.11 권장)
- pip 및 venv 패키지
- systemd 시스템 (자동 실행을 위한 선택사항)

## 2. 설치 단계

### 2.1. 클라우드 접속 및 코드 복사

```bash
# SSH 포트 포워딩 스크립트를 사용하여 Elice 클라우드에 연결
./scripts/setup_gpu_tunnel.sh

# 또는 직접 SSH 접속
ssh -i ~/.ssh/elice-cloud-ondemand-4b44d9b0-ae6b-4f03-b289-899813d3af87.pem -p 13220 elicer@central-02.tcp.tunnel.elice.io

# 클라우드 서버에서 프로젝트 폴더 생성
mkdir -p ~/maple-audio-analyzer/gpu_server
mkdir -p ~/maple-audio-analyzer/models

# 파일 복사 (로컬 개발 환경에서 실행)
# scp -P 13220 -i ~/.ssh/elice-cloud-ondemand-4b44d9b0-ae6b-4f03-b289-899813d3af87.pem -r gpu_server/* elicer@central-02.tcp.tunnel.elice.io:~/maple-audio-analyzer/gpu_server/
# scp -P 13220 -i ~/.ssh/elice-cloud-ondemand-4b44d9b0-ae6b-4f03-b289-899813d3af87.pem models/guitar_technique_classifier.keras elicer@central-02.tcp.tunnel.elice.io:~/maple-audio-analyzer/models/
```

### 2.2. Python 가상 환경 설정

```bash
# Elice 클라우드에서 실행
cd ~/maple-audio-analyzer
python -m venv .venv
source .venv/bin/activate

# 의존성 설치
cd gpu_server
pip install -r requirements.txt

# BentoML CLI 설치 (이미 requirements.txt에 포함되어 있음)
pip install bentoml>=1.2.0
```

### 2.3. BentoML 서비스 빌드 (선택사항)

```bash
# 가상 환경 활성화 상태에서
cd ~/maple-audio-analyzer/gpu_server
bentoml build -f bentofile.yaml
```

빌드 후 Bento를 확인할 수 있습니다:

```bash
bentoml list
```

## 3. 서비스 실행 방법

### 3.1. 직접 실행

```bash
# 가상 환경 활성화
source ~/maple-audio-analyzer/.venv/bin/activate

# 환경 변수 설정
export MODEL_DIR=~/maple-audio-analyzer/models

# 직접 소스 코드에서 실행
cd ~/maple-audio-analyzer/gpu_server
bentoml serve service:MapleAudioGPUInferenceService --production --port 3000 --host 0.0.0.0

# 또는 빌드된 Bento에서 실행
# bentoml serve maple_audio_gpu_inference:latest --production --port 3000 --host 0.0.0.0
```

### 3.2. systemd 서비스로 설정 (권장)

```bash
# 서비스 파일 편집 (사용자 및 경로 수정)
nano ~/maple-audio-analyzer/gpu_server/bentoml_maple_audio.service

# 서비스 파일 복사
sudo cp ~/maple-audio-analyzer/gpu_server/bentoml_maple_audio.service /etc/systemd/system/

# 서비스 파일 권한 변경
sudo chmod 644 /etc/systemd/system/bentoml_maple_audio.service

# systemd 데몬 리로드
sudo systemctl daemon-reload

# 서비스 활성화 (부팅 시 자동 시작)
sudo systemctl enable bentoml_maple_audio.service

# 서비스 시작
sudo systemctl start bentoml_maple_audio.service

# 서비스 상태 확인
sudo systemctl status bentoml_maple_audio.service
```

## 4. 로그 확인

```bash
# systemd 서비스 로그 확인
sudo journalctl -u bentoml_maple_audio.service -f

# 또는 로그 파일 직접 확인
sudo tail -f /var/log/bentoml_maple_audio.log
sudo tail -f /var/log/bentoml_maple_audio_error.log
```

## 5. 서비스 테스트

다음 명령으로 서비스 상태를 확인할 수 있습니다:

```bash
# 헬스 체크 (라이브니스 프로브)
curl http://localhost:3000/livez

# 포트 포워딩이 설정된 경우 메인 서버에서 테스트
# (메인 서버에서 실행)
python scripts/check_gpu_service.py --test

# 간단한 테스트 (Python 스크립트)
python3 -c '
import requests
import numpy as np
sr = 22050
dummy_segment = np.random.rand(sr // 4).astype(np.float32).tolist()
response = requests.post(
    "http://localhost:3000/predict_techniques",
    json={"segments": [dummy_segment], "sample_rate": sr}
)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
'
```

## 6. 문제 해결

### 6.1. SSH 연결 문제

SSH 연결이 되지 않는 경우 다음을 확인하세요:

```bash
# SSH 키 권한 확인
chmod 600 ~/.ssh/elice-cloud-ondemand-4b44d9b0-ae6b-4f03-b289-899813d3af87.pem

# 디버그 모드로 SSH 연결 시도
ssh -vvv -i ~/.ssh/elice-cloud-ondemand-4b44d9b0-ae6b-4f03-b289-899813d3af87.pem -p 13220 elicer@central-02.tcp.tunnel.elice.io
```

### 6.2. 로그 확인

서비스가 시작되지 않는 경우 로그를 확인하세요:

```bash
sudo journalctl -u bentoml_maple_audio.service -n 50
```

### 6.3. GPU 인식 확인

```bash
# NVIDIA GPU 상태 확인
nvidia-smi

# TensorFlow GPU 인식 확인
python3 -c "import tensorflow as tf; print('GPU 가능:', tf.config.list_physical_devices('GPU'))"
```

### 6.4. 수동 실행으로 오류 디버깅

```bash
# 가상 환경 활성화
source ~/maple-audio-analyzer/.venv/bin/activate

# 직접 실행하여 오류 메시지 확인
cd ~/maple-audio-analyzer/gpu_server
python -c "from service import MapleAudioGPUInferenceService; svc = MapleAudioGPUInferenceService()"
```

## 7. 보안 및 최적화 참고사항

### 7.1. Elice 클라우드 환경 특성

Elice 클라우드 환경에서는 일반적으로 보안 정책이 이미 설정되어 있으므로, 추가적인 방화벽 규칙이 필요하지 않을 수 있습니다. 기본적으로 3000번 포트는 로컬에서만 접근 가능하며, SSH 포트 포워딩을 통해 안전하게 접근할 수 있습니다.

### 7.2. 성능 최적화

TensorFlow의 성능을 최적화하려면 다음 환경 변수를 추가하세요:

```
export TF_FORCE_GPU_ALLOW_GROWTH=true
export TF_XLA_FLAGS="--tf_xla_auto_jit=2"
```

이 설정은 `bentoml_maple_audio.service` 파일에 추가할 수 있습니다. 