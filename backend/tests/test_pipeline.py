import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import sys

# Mock heavy/audio dependencies before importing the pipeline
sys.modules['pygame'] = MagicMock()
sys.modules['pygame.mixer'] = MagicMock()
sys.modules['pyaudio'] = MagicMock()
sys.modules['webrtcvad'] = MagicMock()
sys.modules['openwakeword'] = MagicMock()
sys.modules['openwakeword.model'] = MagicMock()

from voice.pipeline import VoicePipeline, PipelineState

@pytest.fixture
def mock_pipeline():
    with patch('voice.pipeline.WakeWordDetector'), \
         patch('voice.pipeline.AudioCapture'):
        pipeline = VoicePipeline()
        yield pipeline

def test_pipeline_initial_state(mock_pipeline):
    assert mock_pipeline._state == PipelineState.IDLE
    assert mock_pipeline._running is False

def test_pipeline_set_state(mock_pipeline):
    # Mock the callback
    state_cb = MagicMock()
    mock_pipeline.on_state_change = state_cb
    
    mock_pipeline._set_state(PipelineState.LISTENING)
    
    assert mock_pipeline._state == PipelineState.LISTENING
    state_cb.assert_called_once_with(PipelineState.LISTENING)

@patch('voice.pipeline.start_local_mic')
def test_pipeline_start_stop(mock_local_mic, mock_pipeline):
    mock_pipeline._wake_word = MagicMock()
    
    # Needs to mock asyncio/threading to avoid actually spinning up threads in tests
    with patch('threading.Thread'):
        mock_pipeline.start()
        
    assert mock_pipeline._running is True
    mock_pipeline._wake_word.start.assert_called_once()
    mock_local_mic.assert_called_once()
    
    # Test stop
    mock_pipeline.stop()
    assert mock_pipeline._manually_stopped is True
    mock_pipeline._wake_word.stop.assert_called_once()
    assert mock_pipeline._state == PipelineState.IDLE

@pytest.mark.asyncio
async def test_pipeline_deactivate_resets_to_idle(mock_pipeline):
    # Set to some active state
    mock_pipeline._set_state(PipelineState.LISTENING)
    mock_pipeline._audio_capture = MagicMock()
    
    # Deactivate should abort capture and go back to wake word
    mock_pipeline.deactivate()
    
    assert mock_pipeline._state == PipelineState.IDLE
    mock_pipeline._wake_word.start.assert_called_once()
    mock_pipeline._audio_capture.stop.assert_called_once()
