#!/usr/bin/env python
"""
GPU 추론 서비스 상태 확인 스크립트

이 스크립트는 BentoML 기반 GPU 추론 서비스의 가용성을 확인하고 상태를 보고합니다.
SSH 포트 포워딩이 올바르게 설정되었는지, 서비스가 응답하는지 점검합니다.
"""

import os
import sys
import requests
import json
import argparse
import time
from datetime import datetime

# 스크립트 위치 기준으로 상위 디렉토리를 Python 경로에 추가 (workers 모듈 import 위해)
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
sys.path.insert(0, root_dir)

def check_service_status(url: str, timeout: int = 5) -> dict:
    """GPU 추론 서비스 상태 확인
    
    Args:
        url: 서비스 기본 URL
        timeout: 연결 타임아웃(초)
        
    Returns:
        상태 정보를 담은 딕셔너리
    """
    result = {
        "available": False,
        "endpoint": url,
        "livez": None,
        "error": None,
        "timestamp": datetime.now().isoformat(),
        "response_time_ms": None
    }
    
    # 라이브니스 체크
    try:
        start_time = time.time()
        response = requests.get(f"{url}/livez", timeout=timeout)
        end_time = time.time()
        result["response_time_ms"] = round((end_time - start_time) * 1000, 2)
        
        if response.status_code == 200:
            result["available"] = True
            result["livez"] = True
            return result
        else:
            result["error"] = f"상태 코드: {response.status_code}, 내용: {response.text[:100]}"
            return result
    except requests.exceptions.RequestException as e:
        result["error"] = f"요청 오류: {str(e)}"
        return result

def test_inference(url: str, timeout: int = 30) -> dict:
    """간단한 추론 요청 테스트
    
    Args:
        url: 서비스 기본 URL
        timeout: 연결 타임아웃(초)
        
    Returns:
        테스트 결과를 담은 딕셔너리
    """
    import numpy as np
    
    result = {
        "test_success": False,
        "predict_techniques": None,
        "extract_pitch_with_crepe": None,
        "extract_pitch_with_pyin": None,
        "error": None,
        "response_times_ms": {}
    }
    
    # 테스트용 더미 데이터 생성
    sr = 22050
    dummy_segment = np.random.rand(sr // 4).astype(np.float32).tolist()  # 0.25초 길이
    request_data = {
        "segments": [dummy_segment],
        "sample_rate": sr
    }
    
    # 테스트할 엔드포인트 목록
    endpoints = [
        "predict_techniques",
        "extract_pitch_with_crepe",
        "extract_pitch_with_pyin"
    ]
    
    all_successful = True
    
    for endpoint in endpoints:
        try:
            start_time = time.time()
            response = requests.post(
                f"{url}/{endpoint}",
                json=request_data,
                timeout=timeout
            )
            end_time = time.time()
            
            result["response_times_ms"][endpoint] = round((end_time - start_time) * 1000, 2)
            
            if response.status_code == 200:
                result[endpoint] = response.json()
            else:
                result[endpoint] = f"오류: HTTP {response.status_code}"
                all_successful = False
        except Exception as e:
            result[endpoint] = f"예외: {str(e)}"
            all_successful = False
    
    result["test_success"] = all_successful
    return result

def print_result(status_result: dict, inference_result: dict = None, verbose: bool = False):
    """결과 출력
    
    Args:
        status_result: 상태 확인 결과
        inference_result: 추론 테스트 결과 (선택 사항)
        verbose: 상세 정보 출력 여부
    """
    print(f"\n===== GPU 추론 서비스 상태 확인 ({'✅ 가능' if status_result['available'] else '❌ 불가'}) =====")
    print(f"엔드포인트: {status_result['endpoint']}")
    print(f"응답 시간: {status_result.get('response_time_ms', 'N/A')} ms")
    print(f"시간: {status_result['timestamp']}")
    
    if not status_result['available']:
        print(f"오류: {status_result['error']}")
        print("\nGPU 서비스를 이용할 수 없습니다. 다음을 확인하세요:")
        print("  1. SSH 포트 포워딩이 설정되어 있는지 (scripts/setup_gpu_tunnel.sh 실행)")
        print("  2. Elice 클라우드가 연결 가능한 상태인지")
        print("  3. Elice 클라우드에서 BentoML 서비스가 실행 중인지")
        print("\n도커 환경에서 실행 중인 경우:")
        print("  1. docker-compose.yml에 host.docker.internal 설정이 있는지 확인하세요:")
        print("     extra_hosts:")
        print("       - \"host.docker.internal:host-gateway\"")
        print("  2. 올바른 URL을 환경변수로 설정했는지 확인하세요:")
        print("     GPU_INFERENCE_SERVICE_URL=http://host.docker.internal:8888")
        return
    
    if inference_result:
        print(f"\n추론 테스트: {'✅ 성공' if inference_result['test_success'] else '❌ 실패'}")
        
        if verbose:
            print("\n== 엔드포인트 별 응답 시간 ==")
            for endpoint, response_time in inference_result.get('response_times_ms', {}).items():
                print(f"  {endpoint}: {response_time} ms")
            
            print("\n== 응답 데이터 샘플 ==")
            for endpoint in ["predict_techniques", "extract_pitch_with_crepe", "extract_pitch_with_pyin"]:
                result = inference_result.get(endpoint)
                print(f"  {endpoint}: {result}")
    
    print("\n✅ GPU 서비스가 정상 작동 중입니다.")

def main():
    parser = argparse.ArgumentParser(description='GPU 추론 서비스 상태 확인')
    parser.add_argument('--url', type=str, default=os.environ.get('GPU_INFERENCE_SERVICE_URL', 'http://localhost:8888'),
                        help='GPU 추론 서비스 URL (기본값: $GPU_INFERENCE_SERVICE_URL 또는 http://localhost:8888)')
    parser.add_argument('--test', action='store_true', help='간단한 추론 테스트 실행')
    parser.add_argument('--verbose', '-v', action='store_true', help='상세 정보 출력')
    parser.add_argument('--timeout', type=int, default=15, help='요청 타임아웃(초) (기본값: 15)')
    args = parser.parse_args()
    
    print("Elice 클라우드 GPU 서비스 연결 상태를 확인합니다...")
    
    # 서비스 상태 확인
    status_result = check_service_status(args.url, args.timeout)
    
    # 상태가 OK이고 테스트 요청을 받은 경우 추론 테스트 실행
    inference_result = None
    if status_result['available'] and args.test:
        print("기본 연결 확인됨. 추론 기능 테스트를 시작합니다...")
        inference_result = test_inference(args.url, args.timeout * 3)  # 추론에는 더 긴 타임아웃 적용
    
    # 결과 출력
    print_result(status_result, inference_result, args.verbose)
    
    # 종료 코드 설정 (성공: 0, 실패: 1)
    if not status_result['available'] or (inference_result and not inference_result['test_success']):
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main() 