#!/bin/bash
# 3000번 포트를 사용하는 모든 프로세스 강제 종료

echo "===== 포트 3000 사용 프로세스 종료 ====="

# 포트 3000을 사용하는 프로세스 찾기
echo "포트 3000을 사용 중인 프로세스 확인:"
lsof -i :3000 || ss -tuln | grep :3000 || netstat -tuln | grep :3000

# 3000번 포트 관련 autossh 프로세스 강제 종료
echo "모든 autossh 프로세스 목록:"
ps aux | grep autossh | grep -v grep

echo "autossh 프로세스 종료 시도..."
pkill -9 -f "autossh"

# 3000번 포트를 사용하는 모든 프로세스 찾기
PID_LIST=$(lsof -t -i:3000 2>/dev/null)

if [ -n "$PID_LIST" ]; then
    echo "포트 3000을 사용 중인 프로세스: $PID_LIST"
    echo "프로세스 강제 종료 시도..."
    kill -9 $PID_LIST
    echo "포트 3000의 프로세스가 종료되었습니다."
else
    echo "lsof로 프로세스를 찾을 수 없습니다. 다른 방법으로 시도..."
    
    # fuser로 시도
    fuser -k -n tcp 3000
    
    echo "네트워크 포트 상태 확인:"
    ss -tuln | grep :3000 || netstat -tuln | grep :3000
fi

echo "===== 종료 완료 ====="
echo "SSH 터널 상태를 확인하려면 다음 명령어를 실행하세요:"
echo "netstat -tuln | grep :3000" 