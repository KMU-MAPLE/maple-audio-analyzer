#!/bin/bash
# GPU 서버로의 SSH 포트 포워딩 설정 스크립트
# 사용법: ./setup_gpu_tunnel.sh [로컬포트] [원격포트]

set -e  # 오류 발생 시 스크립트 중단

# Elice 클라우드 기본 설정값
USER="elicer"  # Elice 클라우드 사용자 계정명
GPU_SERVER="central-02.tcp.tunnel.elice.io"  # Elice 클라우드 주소
SSH_PORT="13220"  # Elice 클라우드 SSH 포트
LOCAL_PORT=${1:-8888}  # 로컬 포트 (FastAPI 서버에서 접근할 포트)
REMOTE_PORT=${2:-3000}  # 원격 포트 (GPU 서버의 BentoML 서비스 포트)

# SSH 키 파일 경로 감지 (Windows WSL 및 Linux 환경 지원)
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    # Windows 환경
    SSH_KEY_PATH="$USERPROFILE/.ssh/elice-cloud-ondemand-4b44d9b0-ae6b-4f03-b289-899813d3af87.pem"
elif [[ -f "$HOME/.ssh/elice-cloud-ondemand-4b44d9b0-ae6b-4f03-b289-899813d3af87.pem" ]]; then
    # Linux/Mac 환경 - 키 파일이 있는 경우
    SSH_KEY_PATH="$HOME/.ssh/elice-cloud-ondemand-4b44d9b0-ae6b-4f03-b289-899813d3af87.pem"
else
    # 키 파일을 찾을 수 없는 경우
    echo "경고: Elice Cloud SSH 키 파일을 찾을 수 없습니다."
    read -p "SSH 키 파일 경로를 입력하세요: " SSH_KEY_PATH
fi

# 설정 정보 출력
echo "===== SSH 포트 포워딩 설정 ====="
echo "서버: $USER@$GPU_SERVER:$SSH_PORT"
echo "SSH 키: $SSH_KEY_PATH"
echo "로컬 포트: $LOCAL_PORT"
echo "원격 포트: $REMOTE_PORT"
echo "==============================="

# SSH 키 파일 확인
if [ ! -f "$SSH_KEY_PATH" ]; then
    echo "오류: SSH 키 파일이 존재하지 않습니다: $SSH_KEY_PATH"
    exit 1
fi

# autossh 설치 확인
if ! command -v autossh &> /dev/null; then
    echo "autossh가 설치되어 있지 않습니다. 설치를 시도합니다..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y autossh
    elif command -v yum &> /dev/null; then
        sudo yum install -y autossh
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --noconfirm autossh
    elif command -v brew &> /dev/null; then
        brew install autossh
    else
        echo "패키지 관리자를 찾을 수 없습니다. 수동으로 autossh를 설치해주세요."
        exit 1
    fi
fi

# 기존 autossh 프로세스 확인 및 종료
if pgrep -f "autossh.*:$LOCAL_PORT:localhost:$REMOTE_PORT" > /dev/null; then
    echo "이미 실행 중인 autossh 프로세스가 있습니다. 종료합니다..."
    pkill -f "autossh.*:$LOCAL_PORT:localhost:$REMOTE_PORT"
    sleep 1
fi

# 로컬 포트가 이미 사용 중인지 확인
if netstat -tln | grep -q ":$LOCAL_PORT "; then
    echo "경고: 포트 $LOCAL_PORT가 이미 사용 중입니다. 다른 포트를 사용하세요."
    exit 1
fi

# SSH 연결 테스트
echo "Elice 클라우드 연결을 테스트합니다..."
if ! ssh -o BatchMode=yes -o ConnectTimeout=10 -p $SSH_PORT -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no "$USER@$GPU_SERVER" exit &> /dev/null; then
    echo "Elice 클라우드에 연결할 수 없습니다. SSH 연결을 확인하세요."
    exit 1
fi
echo "Elice 클라우드 연결 성공!"

# autossh로 터널링 설정 및 데몬으로 실행
echo "포트 포워딩 설정 중: $LOCAL_PORT -> $GPU_SERVER:$REMOTE_PORT"
export AUTOSSH_PIDFILE="/tmp/autossh_gpu_$LOCAL_PORT.pid"
export AUTOSSH_LOGFILE="/tmp/autossh_gpu_$LOCAL_PORT.log"
export AUTOSSH_POLL=60
export AUTOSSH_GATETIME=30
export AUTOSSH_DEBUG=1

# 백그라운드로 autossh 실행 (Elice 클라우드 설정 적용) - 0.0.0.0으로 바인딩
autossh -M 0 -f -N -o "ServerAliveInterval 30" -o "ServerAliveCountMax 3" -o "StrictHostKeyChecking=no" -o "PasswordAuthentication=no" -p $SSH_PORT -i "$SSH_KEY_PATH" -L "0.0.0.0:$LOCAL_PORT:localhost:$REMOTE_PORT" "$USER@$GPU_SERVER"

# 연결 확인
sleep 2
if pgrep -f "autossh.*:$LOCAL_PORT:localhost:$REMOTE_PORT" > /dev/null; then
    echo "SSH 포트 포워딩이 성공적으로 설정되었습니다."
    echo "로컬 포트 $LOCAL_PORT에서 Elice 클라우드의 $REMOTE_PORT 포트로 연결됩니다."
    echo "로그 파일: $AUTOSSH_LOGFILE"
    
    # 환경 변수 설정 안내
    echo ""
    echo "다음 환경 변수를 설정하여 GPU 서비스를 활성화하세요:"
    echo "export GPU_INFERENCE_SERVICE_URL=\"http://localhost:$LOCAL_PORT\""
    echo ""
    echo "Docker 환경에서 사용하려면 docker-compose.yml 파일에 다음을 추가하세요:"
    echo "environment:"
    echo "  - GPU_INFERENCE_SERVICE_URL=http://host.docker.internal:$LOCAL_PORT"
    echo "extra_hosts:"
    echo "  - \"host.docker.internal:host-gateway\""
    echo ""
    echo "현재 쉘에서 설정하시겠습니까? (y/n)"
    read -r SET_ENV
    if [[ "$SET_ENV" == "y" || "$SET_ENV" == "Y" ]]; then
        export GPU_INFERENCE_SERVICE_URL="http://localhost:$LOCAL_PORT"
        echo "환경 변수가 설정되었습니다. (현재 쉘에서만 유효)"
    fi
else
    echo "SSH 포트 포워딩 설정에 실패했습니다. 로그 파일을 확인하세요: $AUTOSSH_LOGFILE"
    exit 1
fi 