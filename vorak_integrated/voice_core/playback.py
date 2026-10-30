"""Play Gemini TTS WAV in-memory; optional headset-only voice interruption."""
import io
import threading
import wave


def read_wav(blob):
    with wave.open(io.BytesIO(blob),'rb') as f:
        if f.getnchannels()!=1 or f.getsampwidth()!=2:raise ValueError('Unsupported Gemini WAV format')
        return f.getframerate(),f.readframes(f.getnframes())


def speak(blob, microphone, *, allow_barge_in=False, silence_ms=900, speaker_device=None):
    import sounddevice as sd
    sample_rate,pcm=read_wav(blob)
    stop_playing=threading.Event(); cancel_monitor=threading.Event()
    incoming={'pcm':None}
    monitor=None
    if allow_barge_in:
        microphone.flush()
        def listen():
            incoming['pcm']=microphone.collect(on_speech=stop_playing.set,stop=cancel_monitor,
                           silence_ms=silence_ms,max_seconds=16)
        monitor=threading.Thread(target=listen,daemon=True)
        monitor.start()
    try:
        with sd.RawOutputStream(samplerate=sample_rate,channels=1,dtype='int16',device=speaker_device) as stream:
            frame_bytes=max(2,(sample_rate//20)*2)
            for off in range(0,len(pcm),frame_bytes):
                if stop_playing.is_set():break
                stream.write(pcm[off:off+frame_bytes])
    finally:
        if monitor is not None:
            if not stop_playing.is_set():cancel_monitor.set()
            monitor.join(timeout=14 if stop_playing.is_set() else 0.4)
        if not stop_playing.is_set(): microphone.flush()
    return incoming['pcm'] if stop_playing.is_set() else None
