#!/usr/bin/env python3
"""
GPU 서버 연결 테스트 스크립트
"""
import os
import sys
import json
import argparse
import requests
import numpy as np
import time
from pathlib import Path

def check_gpu_service(service_url):
    """GPU 서비스 상태 확인"""
    try:
        # 헬스 체크
        response = requests.get(f"{service_url}/livez", timeout=5)
        if response.status_code == 200:
            print(f"✅ GPU 서비스 연결 성공: {service_url}/livez")
            return True
        else:
            print(f"❌ GPU 서비스 응답 오류: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ GPU 서비스 연결 실패: {e}")
        return False

def test_pitch_extraction(service_url):
    """음정 추출 테스트 (간단한 테스트 데이터 사용)"""
    # 간단한 사인파 생성 (테스트용)
    sr = 22050
    duration = 1  # 1초
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)

    # E4 음 (329.63Hz)의 사인파
    frequency = 329.63
    x = 0.5 * np.sin(2 * np.pi * frequency * t)
    
    # 세그먼트 생성 (1개)
    segments = [x.tolist()]
    
    # 요청 데이터 구성
    request_data = {
        "segments": segments,
        "sample_rate": sr
    }
    
    # pYIN API 호출
    try:
        start_time = time.time()
        response = requests.post(
            f"{service_url}/extract_pitch_with_pyin",
            json=request_data,
            timeout=30
        )
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ pYIN 음정 추출 성공 (처리 시간: {elapsed:.2f}초)")
            print(f"   추출된 음정: {result} Hz")
            return True
        else:
            print(f"❌ pYIN 음정 추출 실패: {response.status_code} - {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ pYIN 음정 추출 요청 오류: {e}")
        return False

def test_technique_prediction(service_url):
    """기법 예측 테스트 (간단한 테스트 데이터 사용)"""
    # 간단한 사인파 생성 (테스트용)
    sr = 22050
    duration = 1  # 1초
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)

    # 진폭 변조로 비브라토 효과가 있는 사인파
    frequency = 329.63
    vibrato_rate = 6  # Hz
    vibrato_depth = 0.15
    vibrato = 1.0 + vibrato_depth * np.sin(2 * np.pi * vibrato_rate * t)
    x = 0.5 * np.sin(2 * np.pi * frequency * t) * vibrato
    
    # 세그먼트 생성 (1개)
    segments = [x.tolist()]
    
    # 요청 데이터 구성
    request_data = {
        "segments": segments,
        "sample_rate": sr
    }
    
    # 기법 예측 API 호출
    try:
        start_time = time.time()
        response = requests.post(
            f"{service_url}/predict_techniques",
            json=request_data,
            timeout=60
        )
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 기법 예측 성공 (처리 시간: {elapsed:.2f}초)")
            print(f"   예측된 기법: {result}")
            return True
        else:
            print(f"❌ 기법 예측 실패: {response.status_code} - {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ 기법 예측 요청 오류: {e}")
        return False

def test_batch_processing(service_url):
    """대량의 세그먼트에 대한 배치 처리 테스트"""
    print("\n=== 배치 처리 테스트 ===")
    
    # 테스트 세그먼트 생성
    sr = 22050
    segment_count = 200  # 200개의 세그먼트로 테스트
    segments = []
    
    # 다양한 길이의 세그먼트 생성
    for i in range(segment_count):
        # 0.1초 ~ 0.5초 길이의 랜덤 세그먼트
        duration = 0.1 + 0.4 * np.random.random()
        samples = int(sr * duration)
        
        # 랜덤 주파수의 사인파 (노트 A2~A5, 110Hz~880Hz)
        freq = 110 * (2 ** (np.random.random() * 3))
        t = np.linspace(0, duration, samples, endpoint=False)
        segment = 0.5 * np.sin(2 * np.pi * freq * t)
        segments.append(segment.tolist())
    
    # 배치 요청 테스트 (predict_techniques)
    try:
        start_time = time.time()
        response = requests.post(
            f"{service_url}/predict_techniques",
            json={"segments": segments, "sample_rate": sr},
            timeout=180  # 3분 타임아웃
        )
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            if len(result) == segment_count:
                print(f"✅ 기법 예측 배치 처리 성공 ({segment_count}개 세그먼트, 처리 시간: {elapsed:.2f}초)")
                print(f"   처리 속도: {segment_count/elapsed:.1f} 세그먼트/초")
                return True
            else:
                print(f"⚠️ 기법 예측 배치 처리 불완전: 요청 {segment_count}개, 응답 {len(result)}개 ({elapsed:.2f}초)")
                return False
        else:
            print(f"❌ 기법 예측 배치 처리 실패: {response.status_code} - {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ 기법 예측 배치 처리 요청 오류: {e}")
        return False

def test_connection_speed(service_url):
    """연결 속도 테스트"""
    print("\n=== 연결 속도 테스트 ===")
    try:
        start_time = time.time()
        response = requests.get(f"{service_url}/livez", timeout=5)
        elapsed = time.time() - start_time
        print(f"연결 응답 시간: {elapsed:.4f}초")
        
        # 패킷 크기별 테스트 (작은 패킷부터 큰 패킷까지)
        for size_kb in [1, 10, 100, 1000]:
            size = size_kb * 1024  # KB -> 바이트
            data = {"data": "0" * size}
            
            start_time = time.time()
            response = requests.post(
                f"{service_url}/livez",
                json=data,
                timeout=30
            )
            elapsed = time.time() - start_time
            
            print(f"{size_kb}KB 패킷 전송 시간: {elapsed:.4f}초, 속도: {(size/1024/1024)/(elapsed):.2f} MB/s")
    except Exception as e:
        print(f"연결 속도 테스트 오류: {e}")

def check_docker_network():
    """Docker 네트워크 상태 확인"""
    print("\n=== Docker 네트워크 확인 ===")
    try:
        # Docker 네트워크를 호스트와 연결할 수 있는지 테스트
        response = requests.get("http://host.docker.internal:8888/livez", timeout=5)
        print(f"✅ host.docker.internal 연결 성공: 상태 코드 {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ host.docker.internal 연결 실패: {e}")
    
    # 로컬호스트 연결 테스트
    try:
        response = requests.get("http://localhost:8888/livez", timeout=5)
        print(f"✅ localhost:8888 연결 성공: 상태 코드 {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ localhost:8888 연결 실패: {e}")

def main():
    parser = argparse.ArgumentParser(description="GPU 서비스 테스트 도구")
    parser.add_argument("--url", type=str, default=os.environ.get("GPU_INFERENCE_SERVICE_URL", "http://localhost:8888"),
                        help="GPU 서비스 URL (기본값: 환경변수 GPU_INFERENCE_SERVICE_URL 또는 http://localhost:3000)")
    parser.add_argument("--full", action="store_true", help="모든 테스트 실행 (음정 추출 및 기법 예측)")
    parser.add_argument("--batch", action="store_true", help="대량 세그먼트 배치 처리 테스트 실행")
    args = parser.parse_args()
    
    service_url = args.url
    
    print(f"=== GPU 서비스 테스트 ===")
    print(f"대상 URL: {service_url}")
    print(f"시간: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=========================")
    
    # GPU 서비스 연결 확인
    if not check_gpu_service(service_url):
        print("\n⚠️  GPU 서비스에 연결할 수 없습니다. 네트워크 설정을 확인하세요.")
        print("다음 사항을 확인해보세요:")
        print("1. SSH 포트 포워딩이 활성화되었는지 확인 (setup_gpu_tunnel.sh)")
        print("2. GPU 서버가 실행 중인지 확인")
        print("3. Docker 네트워크 설정이 올바른지 확인 (host.docker.internal)")
        
        # Docker 환경에서 실행 중인지 확인
        if os.path.exists("/.dockerenv"):
            print("\n📋 Docker 환경에서 실행 중입니다.")
            check_docker_network()
        
        return 1
    
    # 기본 테스트 (음정 추출)
    success = test_pitch_extraction(service_url)
    
    # 전체 테스트 옵션이 지정된 경우 기법 예측도 테스트
    if args.full:
        success = test_technique_prediction(service_url) and success
        test_connection_speed(service_url)
    
    # 배치 처리 테스트 옵션이 지정된 경우
    if args.batch:
        success = test_batch_processing(service_url) and success
    
    if success:
        print("\n✅ 테스트 완료: GPU 서비스가 정상적으로 작동합니다.")
        return 0
    else:
        print("\n⚠️  테스트 실패: GPU 서비스 연결에 문제가 있습니다.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 