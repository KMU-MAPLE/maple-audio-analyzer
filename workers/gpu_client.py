import os
import requests
import json
from typing import List, Optional, Dict, Any
import logging
import numpy as np
import time

# 로깅 설정
logger = logging.getLogger(__name__)

# 환경 변수에서 GPU 추론 서비스 URL 가져오기
# SSH 포트 포워딩된 로컬 주소 (예: ssh -L 8888:localhost:3000 user@gpu-server-ip)
GPU_INFERENCE_SERVICE_URL = os.environ.get("GPU_INFERENCE_SERVICE_URL", "http://localhost:8888")
GPU_REQUEST_TIMEOUT = int(os.environ.get("GPU_REQUEST_TIMEOUT", 60))  # 초 단위
# 배치 사이즈 환경 변수 추가
GPU_BATCH_SIZE = int(os.environ.get("GPU_BATCH_SIZE", 100))  # 배치당 최대 세그먼트 수

def is_gpu_service_available() -> bool:
    """GPU 추론 서비스 가용성 확인 (간단한 헬스 체크)"""
    if not GPU_INFERENCE_SERVICE_URL:
        return False
    try:
        # BentoML은 기본적으로 /healthz 또는 /livez 엔드포인트를 제공
        response = requests.get(f"{GPU_INFERENCE_SERVICE_URL}/livez", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logger.warning(f"GPU 추론 서비스 ({GPU_INFERENCE_SERVICE_URL}) 연결 불가: {e}")
        return False

class GPUInferenceClient:
    def __init__(self, base_url: str = GPU_INFERENCE_SERVICE_URL, timeout: int = GPU_REQUEST_TIMEOUT, batch_size: int = GPU_BATCH_SIZE):
        self.base_url = base_url
        self.timeout = timeout
        self.batch_size = batch_size
        self.service_available = is_gpu_service_available()  # 초기 가용성 확인
        logger.info(f"GPU 추론 서비스 초기화: URL={base_url}, 가용성={self.service_available}, 배치 크기={batch_size}")

    def check_availability(self) -> bool:
        """서비스 가용성 재확인"""
        self.service_available = is_gpu_service_available()
        return self.service_available

    def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Optional[Any]:
        """GPU 서비스에 API 요청을 보내는 공통 메서드"""
        if not self.service_available:
            # 매 요청마다 서비스 가용성을 다시 확인
            if not self.check_availability():
                logger.warning(f"GPU 서비스 ({self.base_url}) 사용 불가. 요청을 보내지 않습니다: {endpoint}")
                return None
        
        url = f"{self.base_url}/{endpoint}"
        headers = {"Content-Type": "application/json"}
        try:
            # 세그먼트 데이터가 매우 클 수 있으므로 로깅 시 제한
            segments_count = len(data.get("segments", []))
            sample_rate = data.get("sample_rate", "N/A")
            logger.info(f"GPU 서비스 요청: {url}, 세그먼트 수: {segments_count}, 샘플링 레이트: {sample_rate}")
            
            start_time = time.time()
            response = requests.post(url, data=json.dumps(data), headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            elapsed_time = time.time() - start_time
            logger.info(f"GPU 서비스 응답 ({endpoint}): {response.status_code}, 데이터 크기: {len(response.content)} 바이트, 소요 시간: {elapsed_time:.2f}초")
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"GPU 서비스 HTTP 오류 ({url}): {e.response.status_code} - {e.response.text}")
        except requests.exceptions.Timeout:
            logger.error(f"GPU 서비스 타임아웃 ({url})")
        except requests.exceptions.ConnectionError:
            logger.error(f"GPU 서비스 연결 실패 ({url})")
            self.service_available = False  # 연결 실패 시 가용성 상태 업데이트
        except Exception as e:
            logger.error(f"GPU 서비스 요청 중 예기치 않은 오류 ({url}): {e}")
        return None

    def predict_techniques(self, segments: List[np.ndarray], sample_rate: int = 22050) -> Optional[List[List[str]]]:
        """GPU 서버에서 기타 연주 기법 예측
        
        Args:
            segments: 오디오 세그먼트 리스트 (NumPy 배열)
            sample_rate: 오디오 샘플링 레이트
            
        Returns:
            기법 예측 결과 리스트 또는 None (요청 실패 시)
        """
        if not segments:
            return []

        # 세그먼트 개수 로깅
        total_segments = len(segments)
        logger.info(f"총 처리할 세그먼트 수: {total_segments}")

        # 배치 처리를 위한 세그먼트 분할
        if total_segments > self.batch_size:
            logger.info(f"세그먼트 수({total_segments})가 배치 크기({self.batch_size})보다 큽니다. 배치 처리를 시작합니다.")
            
            # 배치로 나누어 처리
            all_results = []
            for i in range(0, total_segments, self.batch_size):
                batch = segments[i:i+self.batch_size]
                logger.info(f"배치 처리: {i+1}~{i+len(batch)}/{total_segments} 세그먼트")
                
                # NumPy 배열을 Python 리스트로 변환
                batch_list = [segment.tolist() for segment in batch]
                data = {"segments": batch_list, "sample_rate": sample_rate}
                
                # 배치 요청 및 결과 수집
                batch_result = self._make_request("predict_techniques", data)
                if batch_result is None:
                    logger.error(f"배치 처리 실패: {i+1}~{i+len(batch)}/{total_segments}")
                    return None
                
                all_results.extend(batch_result)
            
            logger.info(f"모든 배치 처리 완료. 총 결과 수: {len(all_results)}")
            return all_results
        else:
            # 하나의 배치로 처리 (기존 방식)
            segments_list = [segment.tolist() for segment in segments]
            data = {"segments": segments_list, "sample_rate": sample_rate}
            return self._make_request("predict_techniques", data)

    def extract_pitch_with_crepe(self, segments: List[np.ndarray], sample_rate: int = 22050) -> Optional[List[float]]:
        """GPU 서버에서 CREPE 모델을 사용한 음정 추출
        
        Args:
            segments: 오디오 세그먼트 리스트 (NumPy 배열)
            sample_rate: 오디오 샘플링 레이트
            
        Returns:
            음정 주파수 리스트 또는 None (요청 실패 시)
        """
        if not segments:
            return []

        # 세그먼트 개수 로깅
        total_segments = len(segments)
        logger.info(f"CREPE 처리할 총 세그먼트 수: {total_segments}")

        # 배치 처리를 위한 세그먼트 분할
        if total_segments > self.batch_size:
            logger.info(f"CREPE: 세그먼트 수({total_segments})가 배치 크기({self.batch_size})보다 큽니다. 배치 처리를 시작합니다.")
            
            # 배치로 나누어 처리
            all_results = []
            for i in range(0, total_segments, self.batch_size):
                batch = segments[i:i+self.batch_size]
                logger.info(f"CREPE 배치 처리: {i+1}~{i+len(batch)}/{total_segments} 세그먼트")
                
                # NumPy 배열을 Python 리스트로 변환
                batch_list = [segment.tolist() for segment in batch]
                data = {"segments": batch_list, "sample_rate": sample_rate}
                
                # 배치 요청 및 결과 수집
                batch_result = self._make_request("extract_pitch_with_crepe", data)
                if batch_result is None:
                    logger.error(f"CREPE 배치 처리 실패: {i+1}~{i+len(batch)}/{total_segments}")
                    return None
                
                all_results.extend(batch_result)
            
            logger.info(f"CREPE 모든 배치 처리 완료. 총 결과 수: {len(all_results)}")
            return all_results
        else:
            # 하나의 배치로 처리 (기존 방식)
            segments_list = [segment.tolist() for segment in segments]
            data = {"segments": segments_list, "sample_rate": sample_rate}
            return self._make_request("extract_pitch_with_crepe", data)

    def extract_pitch_with_pyin(self, segments: List[np.ndarray], sample_rate: int = 22050) -> Optional[List[float]]:
        """GPU 서버에서 pYIN 알고리즘을 사용한 음정 추출
        
        Args:
            segments: 오디오 세그먼트 리스트 (NumPy 배열)
            sample_rate: 오디오 샘플링 레이트
            
        Returns:
            음정 주파수 리스트 또는 None (요청 실패 시)
        """
        if not segments:
            return []

        # 세그먼트 개수 로깅
        total_segments = len(segments)
        logger.info(f"pYIN 처리할 총 세그먼트 수: {total_segments}")

        # 배치 처리를 위한 세그먼트 분할
        if total_segments > self.batch_size:
            logger.info(f"pYIN: 세그먼트 수({total_segments})가 배치 크기({self.batch_size})보다 큽니다. 배치 처리를 시작합니다.")
            
            # 배치로 나누어 처리
            all_results = []
            for i in range(0, total_segments, self.batch_size):
                batch = segments[i:i+self.batch_size]
                logger.info(f"pYIN 배치 처리: {i+1}~{i+len(batch)}/{total_segments} 세그먼트")
                
                # NumPy 배열을 Python 리스트로 변환
                batch_list = [segment.tolist() for segment in batch]
                data = {"segments": batch_list, "sample_rate": sample_rate}
                
                # 배치 요청 및 결과 수집
                batch_result = self._make_request("extract_pitch_with_pyin", data)
                if batch_result is None:
                    logger.error(f"pYIN 배치 처리 실패: {i+1}~{i+len(batch)}/{total_segments}")
                    return None
                
                all_results.extend(batch_result)
            
            logger.info(f"pYIN 모든 배치 처리 완료. 총 결과 수: {len(all_results)}")
            return all_results
        else:
            # 하나의 배치로 처리 (기존 방식)
            segments_list = [segment.tolist() for segment in segments]
            data = {"segments": segments_list, "sample_rate": sample_rate}
            return self._make_request("extract_pitch_with_pyin", data)

# 싱글톤으로 클라이언트 인스턴스 생성 (모듈 로드 시 초기화)
gpu_client = GPUInferenceClient() 