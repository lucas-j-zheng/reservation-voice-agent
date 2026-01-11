"""
Audio Transcoding Utilities
Handles conversion between Twilio's μ-law 8kHz and Gemini's LPCM16 formats (16kHz/24kHz).
"""

import numpy as np

# μ-law constants
MULAW_BIAS = 0x84
MULAW_CLIP = 32635
MULAW_MAX = 0x1FFF


def _mulaw_decode_sample(mulaw_byte: int) -> int:
    """Decode a single μ-law byte to 16-bit linear PCM."""
    mulaw_byte = ~mulaw_byte
    sign = (mulaw_byte & 0x80)
    exponent = (mulaw_byte >> 4) & 0x07
    mantissa = mulaw_byte & 0x0F

    sample = ((mantissa << 3) + MULAW_BIAS) << exponent
    sample -= MULAW_BIAS

    if sign:
        sample = -sample

    return sample


def _mulaw_encode_sample(pcm_sample: int) -> int:
    """Encode a 16-bit linear PCM sample to μ-law."""
    sign = 0
    if pcm_sample < 0:
        sign = 0x80
        pcm_sample = -pcm_sample

    if pcm_sample > MULAW_CLIP:
        pcm_sample = MULAW_CLIP

    pcm_sample += MULAW_BIAS

    exponent = 7
    for exp in range(8):
        if pcm_sample < (1 << (exp + 8)):
            exponent = exp
            break

    mantissa = (pcm_sample >> (exponent + 3)) & 0x0F
    mulaw_byte = ~(sign | (exponent << 4) | mantissa)

    return mulaw_byte & 0xFF


def transcode_mulaw_to_pcm(mulaw_audio: bytes) -> bytes:
    """
    Convert μ-law 8kHz audio to 16-bit LPCM 16kHz.

    Args:
        mulaw_audio: Raw μ-law encoded audio bytes (8kHz)

    Returns:
        16-bit signed LPCM audio bytes (16kHz)
    """
    # Decode μ-law to 16-bit PCM
    pcm_samples = np.array(
        [_mulaw_decode_sample(b) for b in mulaw_audio],
        dtype=np.int16
    )

    # Resample 8kHz -> 16kHz (simple linear interpolation)
    resampled = resample_8k_to_16k(pcm_samples)

    return resampled.tobytes()


def transcode_pcm_to_mulaw(pcm_audio: bytes) -> bytes:
    """
    Convert 16-bit LPCM 16kHz audio to μ-law 8kHz.

    Args:
        pcm_audio: 16-bit signed LPCM audio bytes (16kHz)

    Returns:
        Raw μ-law encoded audio bytes (8kHz)
    """
    # Parse 16-bit PCM
    pcm_samples = np.frombuffer(pcm_audio, dtype=np.int16)

    # Resample 16kHz -> 8kHz (simple decimation)
    resampled = resample_16k_to_8k(pcm_samples)

    # Encode to μ-law
    mulaw_bytes = bytes([_mulaw_encode_sample(int(s)) for s in resampled])

    return mulaw_bytes


def resample_8k_to_16k(samples: np.ndarray) -> np.ndarray:
    """
    Resample from 8kHz to 16kHz using linear interpolation.

    Args:
        samples: Input samples at 8kHz

    Returns:
        Output samples at 16kHz
    """
    n = len(samples)
    if n == 0:
        return np.array([], dtype=np.int16)

    # Double the samples with linear interpolation
    output = np.zeros(n * 2, dtype=np.int16)
    output[::2] = samples

    # Interpolate odd indices
    output[1:-1:2] = (samples[:-1].astype(np.int32) + samples[1:].astype(np.int32)) // 2
    output[-1] = samples[-1]

    return output


def resample_16k_to_8k(samples: np.ndarray) -> np.ndarray:
    """
    Resample from 16kHz to 8kHz using decimation.

    Args:
        samples: Input samples at 16kHz

    Returns:
        Output samples at 8kHz
    """
    # Simple decimation: take every other sample
    return samples[::2].copy()


def resample_24k_to_8k(samples: np.ndarray) -> np.ndarray:
    """
    Resample from 24kHz to 8kHz using decimation.

    Args:
        samples: Input samples at 24kHz

    Returns:
        Output samples at 8kHz
    """
    # Take every 3rd sample (24kHz / 3 = 8kHz)
    return samples[::3].copy()


def transcode_pcm_24k_to_mulaw(pcm_audio: bytes) -> bytes:
    """
    Convert 16-bit LPCM 24kHz audio to μ-law 8kHz.

    Args:
        pcm_audio: 16-bit signed LPCM audio bytes (24kHz)

    Returns:
        Raw μ-law encoded audio bytes (8kHz)
    """
    # Parse 16-bit PCM
    pcm_samples = np.frombuffer(pcm_audio, dtype=np.int16)

    # Resample 24kHz -> 8kHz
    resampled = resample_24k_to_8k(pcm_samples)

    # Encode to μ-law
    mulaw_bytes = bytes([_mulaw_encode_sample(int(s)) for s in resampled])

    return mulaw_bytes
