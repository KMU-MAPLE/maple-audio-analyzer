#!/bin/bash
# GPU 서버로의 SSH 포트 포워딩 종료 스크립트
# 사용법: ./stop_gpu_tunnel.sh [로컬포트]

# 기본값 설정
LOCAL_PORT=${1:-8888}  # 기본 로컬 포트

echo "===== SSH 포트 포워딩 종료 ====="
echo "로컬 포트: $LOCAL_PORT"
echo "=============================="

# autossh 프로세스 찾기 및 종료
if pgrep -f "autossh.*:$LOCAL_PORT:localhost:" > /dev/null; then
    echo "포트 $LOCAL_PORT에 연결된 autossh 프로세스를 종료합니다..."
    pkill -f "autossh.*:$LOCAL_PORT:localhost:"
    
    # 프로세스가 종료되었는지 확인
    sleep 2
    if ! pgrep -f "autossh.*:$LOCAL_PORT:localhost:" > /dev/null; then
        echo "SSH 포트 포워딩이 성공적으로 종료되었습니다."
        
        # PID 파일 및 로그 파일 삭제
        AUTOSSH_PIDFILE="/tmp/autossh_gpu_$LOCAL_PORT.pid"
        AUTOSSH_LOGFILE="/tmp/autossh_gpu_$LOCAL_PORT.log"
        
        if [ -f "$AUTOSSH_PIDFILE" ]; then
            rm -f "$AUTOSSH_PIDFILE"
        fi
        
        echo "환경 변수 제거 안내:"
        echo "다음 명령어로 환경 변수를 제거할 수 있습니다:"
        echo "unset GPU_INFERENCE_SERVICE_URL"
    else
        echo "경고: 프로세스 종료에 실패했습니다. 수동으로 종료해주세요:"
        echo "sudo kill \$(pgrep -f \"autossh.*:$LOCAL_PORT:localhost:\")"
    fi
else
    echo "포트 $LOCAL_PORT에 연결된 autossh 프로세스가 없습니다."
fi 