"""20ms WebRTC VAD microphone endpointing; captured audio never written to disk."""
import collections
import queue
import array
import math
import sys
import threading
import time

RATE=16000
FRAME_MS=20
FRAME_BYTES=RATE * 2 * FRAME_MS // 1000


def rms(frame: bytes) -> float:
    if len(frame)!=FRAME_BYTES: return 0.
    samples=array.array('h');samples.frombytes(frame)
    if sys.byteorder!='little':samples.byteswap()
    return math.sqrt(sum(x*x for x in samples)/len(samples))/32768.

class Endpoint:
    """WebRTC VAD plus low-level energy gate; not a speaker authentication system."""
    def __init__(self, silence_ms=900, min_speech_ms=220, aggressiveness=2):
        import webrtcvad
        self.detector=webrtcvad.Vad(aggressiveness)
        self.silence_frames=max(1,silence_ms//FRAME_MS)
        self.min_speech_frames=max(1,min_speech_ms//FRAME_MS)
        self.noise=0.0005
        self.preroll=collections.deque(maxlen=15)
        self.reset()

    def reset(self):
        self.frames=[]; self.armed=False; self.voiced=0; self.quiet=0
        self.preroll.clear(); self.onset_sent=False

    def feed(self, frame, on_speech=None):
        if len(frame)!=FRAME_BYTES: return None
        energy=rms(frame)
        detected=bool(self.detector.is_speech(frame,RATE))
        # Smooth ambient baseline only while not within a voice utterance.
        if not self.armed and not detected:
            self.noise=0.98*self.noise+0.02*min(energy,0.035)
        speech=detected and energy > max(0.0010, self.noise*2.0)
        if not self.armed:
            self.preroll.append(frame)
            if speech:
                self.voiced+=1
                if self.voiced>=self.min_speech_frames:
                    self.armed=True
                    self.frames=list(self.preroll)
                    # Candidate speech started earlier than the last 300 ms.
                    if on_speech and not self.onset_sent:
                        self.onset_sent=True; on_speech()
            else:
                self.voiced=max(0,self.voiced-1)
            return None
        self.frames.append(frame)
        if speech: self.quiet=0
        else: self.quiet+=1
        if self.quiet >= self.silence_frames:
            result=b''.join(self.frames[:-self.silence_frames])
            self.reset()
            return result if len(result)>=FRAME_BYTES*self.min_speech_frames else b''
        return None

class Microphone:
    def __init__(self, device=None):
        self.device=device; self.queue=queue.Queue(maxsize=512); self.stream=None

    def __enter__(self):
        import sounddevice as sd
        def callback(data, frames, time_info, status):
            payload=bytes(data)
            for offset in range(0,len(payload),FRAME_BYTES):
                chunk=payload[offset:offset+FRAME_BYTES]
                if len(chunk)==FRAME_BYTES:
                    try:self.queue.put_nowait(chunk)
                    except queue.Full:
                        try:self.queue.get_nowait();self.queue.put_nowait(chunk)
                        except queue.Empty:pass
        self.stream=sd.RawInputStream(device=self.device, samplerate=RATE,channels=1,
                                      blocksize=RATE*FRAME_MS//1000,dtype='int16',callback=callback)
        self.stream.start()
        return self

    def __exit__(self,*exc):
        if self.stream:
            self.stream.stop();self.stream.close();self.stream=None

    def flush(self):
        while True:
            try:self.queue.get_nowait()
            except queue.Empty:return

    def collect(self, *, silence_ms=900,min_speech_ms=220,max_seconds=11.0,
                on_speech=None, stop=None):
        ep=Endpoint(silence_ms=silence_ms,min_speech_ms=min_speech_ms)
        start=time.monotonic()
        while time.monotonic()-start < max_seconds:
            if stop is not None and stop.is_set() and not ep.armed:return None
            try:chunk=self.queue.get(timeout=0.075)
            except queue.Empty:continue
            result=ep.feed(chunk,on_speech)
            if result is not None:return result or None
        return None   # Fail closed: don't invent a partial utterance.
