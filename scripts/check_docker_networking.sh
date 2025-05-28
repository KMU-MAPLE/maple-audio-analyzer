#!/bin/bash
# Docker 컨테이너와 호스트 간 네트워크 연결 확인 스크립트

echo "===== Docker 네트워크 진단 도구 ====="
echo "실행 시간: $(date)"
echo "======================================"

# Docker가 설치되어 있는지 확인
if ! command -v docker &> /dev/null; then
    echo "❌ Docker가 설치되어 있지 않습니다."
    exit 1
fi

# 실행 중인 컨테이너 확인
echo -e "\n[실행 중인 컨테이너]"
docker ps

# 네트워크 확인
echo -e "\n[Docker 네트워크 목록]"
docker network ls

# 메인 네트워크 세부 정보
echo -e "\n[maple-network 세부 정보]"
docker network inspect maple-network 2>/dev/null || echo "maple-network가 존재하지 않습니다."

# Docker 브릿지 네트워크 세부 정보
echo -e "\n[bridge 네트워크 세부 정보]"
docker network inspect bridge

# 호스트 네트워크 인터페이스
echo -e "\n[호스트 네트워크 인터페이스]"
ip addr | grep -E "^[0-9]+:" -A 2

# Docker 호스트 IP 확인
echo -e "\n[Docker 호스트 IP 확인]"
echo "Docker 기본 게이트웨이 (일반적으로 172.17.0.1):"
ip route | grep docker0

# Docker 내부에서 호스트 IP 테스트
echo -e "\n[Docker 컨테이너에서 호스트 IP 연결 테스트]"
echo "다음 명령어를 Docker 컨테이너 내부에서 실행하여 호스트 IP 연결을 테스트할 수 있습니다:"
echo "docker exec -it maple-audio-analyzer_worker_1 curl -v http://172.17.0.1:8888/livez"

# 컨테이너에서 진단용 명령어
echo -e "\n[컨테이너 내부 진단 명령어]"
WORKER_CONTAINER=$(docker ps --filter name=maple-audio-analyzer_worker -q)
if [ -n "$WORKER_CONTAINER" ]; then
    echo "워커 컨테이너 내부에서 네트워크 확인:"
    docker exec $WORKER_CONTAINER ip route
    echo ""
    docker exec $WORKER_CONTAINER cat /etc/hosts
    echo ""
    echo "GPU 서비스 접근 테스트 (172.17.0.1:8888):"
    docker exec $WORKER_CONTAINER curl -s -m 2 http://172.17.0.1:8888/livez || echo "연결 실패"
fi

# 포트 상태 확인
echo -e "\n[포트 상태 확인]"
echo "포트 8888 (GPU 서비스):"
ss -tuln | grep ":8888" || echo "포트 8888이 사용 중이지 않습니다."

echo "포트 3000 (BentoML):"
ss -tuln | grep ":3000" || echo "포트 3000이 사용 중이지 않습니다."

echo "포트 6379 (Redis):"
ss -tuln | grep ":6379" || echo "포트 6379이 사용 중이지 않습니다."

echo "포트 27017 (MongoDB):"
ss -tuln | grep ":27017" || echo "포트 27017이 사용 중이지 않습니다."

# autossh 프로세스 확인
echo -e "\n[autossh 프로세스 확인]"
ps aux | grep autossh | grep -v grep || echo "실행 중인 autossh 프로세스가 없습니다."

# 기본 연결 테스트
echo -e "\n[기본 연결 테스트]"
echo "localhost:8888 :"
curl -m 2 -s -o /dev/null -w "%{http_code}" http://localhost:8888/livez || echo "연결 실패"

echo "172.17.0.1:8888 :"
curl -m 2 -s -o /dev/null -w "%{http_code}" http://172.17.0.1:8888/livez || echo "연결 실패"

echo "호스트 네임 확인:"
hostname

# SSH 포트 포워딩 상태 확인
echo -e "\n[SSH 포트 포워딩 확인]"
echo "포트 포워딩 재설정을 위해 다음 명령어를 실행하세요:"
echo "./scripts/stop_gpu_tunnel.sh 8888"
echo "./scripts/setup_gpu_tunnel.sh 8888 3000"

echo -e "\n====== 진단 완료 ======" 