import bentoml
import numpy as np
import tensorflow as tf
import librosa
import os
import logging
from tensorflow.keras.models import load_model
from typing import List, Dict, Any
import crepe

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 모델 경로 설정
MODEL_DIR = os.environ.get("MODEL_DIR", "models")
MODEL_PATH = os.path.join(MODEL_DIR, "guitar_technique_classifier.keras")

# GPU 메모리 설정
gpus = tf.config.experimental.list_physical_devices('GPU')
if gpus:
    try:
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
        logger.info(f"GPU 메모리 동적 할당 설정 완료. 사용 가능한 GPU: {len(gpus)}개")
    except RuntimeError as e:
        logger.error(f"GPU 설정 오류: {e}")
else:
    logger.warning("사용 가능한 GPU가 없습니다. CPU 모드로 실행됩니다.")

# 유틸리티 함수
def wav_to_spectrogram(y, sr=22050, n_fft=512, hop_length=20, n_mels=128, target_time_frames=960):
    """오디오를 멜 스펙트로그램으로 변환"""
    S = librosa.feature.melspectrogram(y=y, sr=sr, n_fft=n_fft, hop_length=hop_length, n_mels=n_mels)
    S_db = librosa.power_to_db(S, ref=np.max)
    
    if S_db.shape[1] < target_time_frames:
        S_db = np.pad(S_db, ((0, 0), (0, target_time_frames - S_db.shape[1])), mode='constant')
    elif S_db.shape[1] > target_time_frames:
        S_db = S_db[:, :target_time_frames]
    
    return S_db


@bentoml.service(
    name="maple_audio_gpu_inference",
    traffic={"timeout": 300}
)
class MapleAudioGPUInferenceService:
    def __init__(self):
        logger.info("MapleAudioGPUInferenceService 초기화 시작")
        
        # 기법 분류 모델 로드
        self.techniques = ["bend", "hammer", "normal", "pull", "slide", "vibrato"]
        try:
            if os.path.exists(MODEL_PATH):
                self.technique_model = load_model(MODEL_PATH)
                logger.info(f"기법 분류 모델 로드 완료: {MODEL_PATH}")
            else:
                logger.error(f"모델 파일을 찾을 수 없음: {MODEL_PATH}")
                self.technique_model = None
        except Exception as e:
            logger.error(f"모델 로드 오류: {e}")
            self.technique_model = None
            
        logger.info("MapleAudioGPUInferenceService 초기화 완료")

    @bentoml.api
    def predict_techniques(self, segments: List[List[float]], sample_rate: int = 22050) -> List[List[str]]:
        """오디오 세그먼트에서 기타 연주 기법을 예측
        
        Args:
            segments: 오디오 세그먼트 리스트 (각 세그먼트는 float 리스트)
            sample_rate: 오디오 샘플링 레이트 (Hz)
            
        Returns:
            예측된 기법 리스트 (각 세그먼트별 문자열 리스트)
        """
        if self.technique_model is None:
            logger.error("기법 분류 모델이 로드되지 않았습니다.")
            return [["error"] for _ in segments]
        
        logger.info(f"기법 예측 요청: {len(segments)} 개 세그먼트")
        predictions = []
        
        for i, segment_data in enumerate(segments):
            try:
                segment = np.array(segment_data)
                
                if len(segment) < sample_rate * 0.01:
                    predictions.append(["unknown"])
                    continue
                
                spec = wav_to_spectrogram(segment, sr=sample_rate)
                spec = (spec - np.min(spec)) / (np.max(spec) - np.min(spec) + 1e-8)
                spec = spec[..., np.newaxis]
                spec = np.expand_dims(spec, axis=0)
                
                pred = self.technique_model.predict(spec, verbose=0)
                pred_binary = (pred > 0.5).astype(int)
                predicted_techniques = [self.techniques[i] for i in range(len(pred_binary[0])) if pred_binary[0][i] == 1]
                
                predictions.append(predicted_techniques if predicted_techniques else ["normal"])
            except Exception as e:
                logger.error(f"세그먼트 {i} 기법 예측 오류: {e}")
                predictions.append(["error"])
        
        logger.info(f"기법 예측 완료: {len(predictions)} 개 결과")
        return predictions

    @bentoml.api
    def extract_pitch_with_crepe(self, segments: List[List[float]], sample_rate: int = 22050) -> List[float]:
        """CREPE 모델을 사용하여 오디오 세그먼트의 음정 추출
        
        Args:
            segments: 오디오 세그먼트 리스트 (각 세그먼트는 float 리스트)
            sample_rate: 오디오 샘플링 레이트 (Hz)
            
        Returns:
            추출된 음정 주파수 리스트 (Hz)
        """
        logger.info(f"CREPE 음정 추출 요청: {len(segments)} 개 세그먼트")
        pitches = []
        
        for i, segment_data in enumerate(segments):
            try:
                segment = np.array(segment_data)
                
                if len(segment) < sample_rate * 0.01:
                    pitches.append(0.0)
                    continue
                
                time, frequency, confidence, activation = crepe.predict(
                    segment, sample_rate, viterbi=True, center=True, step_size=10
                )
                
                if np.any(confidence > 0.5):
                    avg_freq = np.mean(frequency[confidence > 0.5])
                    pitch = float(avg_freq) if not np.isnan(avg_freq) else 0.0
                else:
                    pitch = 0.0
                
                pitches.append(pitch)
            except Exception as e:
                logger.error(f"세그먼트 {i} CREPE 음정 추출 오류: {e}")
                pitches.append(-1.0)  # 오류 표시
        
        logger.info(f"CREPE 음정 추출 완료: {len(pitches)} 개 결과")
        return pitches

    @bentoml.api
    def extract_pitch_with_pyin(self, segments: List[List[float]], sample_rate: int = 22050) -> List[float]:
        """pYIN 알고리즘을 사용하여 오디오 세그먼트의 음정 추출
        
        Args:
            segments: 오디오 세그먼트 리스트 (각 세그먼트는 float 리스트)
            sample_rate: 오디오 샘플링 레이트 (Hz)
            
        Returns:
            추출된 음정 주파수 리스트 (Hz)
        """
        logger.info(f"pYIN 음정 추출 요청: {len(segments)} 개 세그먼트")
        pitches = []
        
        for i, segment_data in enumerate(segments):
            try:
                segment = np.array(segment_data)
                
                if len(segment) < sample_rate * 0.01:
                    pitches.append(0.0)
                    continue
                
                f0, voiced_flag, voiced_prob = librosa.pyin(
                    segment, 
                    fmin=librosa.note_to_hz('E2'),
                    fmax=librosa.note_to_hz('C6'),
                    sr=sample_rate
                )
                
                valid_f0 = f0[voiced_flag]
                avg_f0 = np.mean(valid_f0) if len(valid_f0) > 0 else 0.0
                pitch = float(avg_f0) if not np.isnan(avg_f0) else 0.0
                
                pitches.append(pitch)
            except Exception as e:
                logger.error(f"세그먼트 {i} pYIN 음정 추출 오류: {e}")
                pitches.append(-1.0)  # 오류 표시
        
        logger.info(f"pYIN 음정 추출 완료: {len(pitches)} 개 결과")
        return pitches 