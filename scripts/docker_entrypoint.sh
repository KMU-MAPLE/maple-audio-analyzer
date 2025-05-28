#!/bin/bash
# Docker 컨테이너 엔트리포인트 스크립트
# - GPU 서버로 SSH 터널 설정
# - 애플리케이션 실행

set -e  # 오류 발생 시 중단

# SSH 키 설정 (환경 변수에서 가져온 키)
if [ -n "$SSH_PRIVATE_KEY" ]; then
  echo "SSH 키 설정 중..."
  echo "$SSH_PRIVATE_KEY" > /root/.ssh/id_rsa
  chmod 600 /root/.ssh/id_rsa
  
  # 알려진 호스트 보안 경고 무시
  mkdir -p /root/.ssh
  echo "StrictHostKeyChecking no" > /root/.ssh/config
  echo "SSH 키 설정 완료"
else
  echo "경고: SSH_PRIVATE_KEY 환경변수가 설정되지 않았습니다."
  echo "SSH 터널링이 작동하지 않을 수 있습니다."
fi

# SSH 터널 설정
setup_ssh_tunnel() {
  # 환경 변수 또는 기본값 사용
  SSH_USER=${SSH_USER:-"elicer"}
  SSH_SERVER=${SSH_SERVER:-"central-02.tcp.tunnel.elice.io"}
  SSH_PORT=${SSH_PORT:-13220}
  LOCAL_PORT=${SSH_LOCAL_PORT:-3000}
  REMOTE_PORT=${SSH_REMOTE_PORT:-3000}
  
  echo "===== SSH 포트 포워딩 설정 ====="
  echo "서버: $SSH_USER@$SSH_SERVER:$SSH_PORT"
  echo "로컬 포트: $LOCAL_PORT"
  echo "원격 포트: $REMOTE_PORT"
  echo "==============================="
  
  # SSH 키 확인
  if [ ! -f "/root/.ssh/id_rsa" ]; then
    echo "오류: SSH 키 파일이 없습니다. SSH_PRIVATE_KEY 환경변수를 설정하세요."
    return 1
  fi
  
  # 기존 터널 종료
  pkill -f "autossh.*:$LOCAL_PORT:" >/dev/null 2>&1 || true
  
  # autossh 환경 변수 설정
  export AUTOSSH_PIDFILE="/tmp/autossh_gpu.pid"
  export AUTOSSH_POLL=60
  export AUTOSSH_GATETIME=30
  export AUTOSSH_DEBUG=1
  
  # 백그라운드로 autossh 실행
  autossh -M 0 -f -N -o "ServerAliveInterval 30" \
    -o "ServerAliveCountMax 3" \
    -o "StrictHostKeyChecking=no" \
    -o "PasswordAuthentication=no" \
    -p $SSH_PORT -i /root/.ssh/id_rsa \
    -L "$LOCAL_PORT:localhost:$REMOTE_PORT" \
    "$SSH_USER@$SSH_SERVER"
  
  # 성공 확인
  sleep 2
  if pgrep -f "autossh.*:$LOCAL_PORT:" > /dev/null; then
    echo "✅ SSH 포트 포워딩 성공: localhost:$LOCAL_PORT → $SSH_SERVER:$REMOTE_PORT"
    
    # GPU 서비스 URL 환경변수 설정
    export GPU_INFERENCE_SERVICE_URL="http://localhost:$LOCAL_PORT"
    echo "✅ GPU_INFERENCE_SERVICE_URL 설정: $GPU_INFERENCE_SERVICE_URL"
  else
    echo "❌ SSH 포트 포워딩 실패"
    return 1
  fi
}

# 메인 실행 코드
echo "==== 컨테이너 시작 ===="

# SSH_TUNNEL 환경변수가 true로 설정된 경우에만 SSH 터널 설정
if [ "$SSH_TUNNEL" = "true" ]; then
  setup_ssh_tunnel
  echo "SSH 터널 상태: $(pgrep -f autossh || echo '실행 중이지 않음')"
else
  echo "SSH 터널 비활성화 (SSH_TUNNEL=true로 설정하면 활성화됨)"
fi

# 원래 명령어 실행
echo "애플리케이션 실행: $@"
exec "$@" 