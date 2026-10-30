"""Read-only local owner-archive audit. Never writes audio or biometric templates."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
import re
import zipfile
from collections import Counter
from pathlib import Path

AUDIO_RATE = 16000


def archive_inventory(path):
    """Return metadata only. Refuse unexpected structures and unsafe archive members."""
    path = Path(path)
    if not path.is_file():
        raise ValueError('Archive not found: ' + str(path))
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) > 1000 or any('/' in n or '\\' in n or n.startswith('.') for n in names):
            raise ValueError('Unsafe archive layout')
        if 'samples.json' not in names:
            raise ValueError('samples.json missing')
        metadata_info = z.getinfo('samples.json')
        if metadata_info.file_size > 100_000_000:
            raise ValueError('Oversized metadata file')
        raw_metadata=z.read('samples.json')
        # Long frequency-frame arrays inflate Python's JSON memory enormously.
        # For large known-shape exports, scan only three scalar metadata fields;
        # never instantiate millions of frequency values in RAM.
        if len(raw_metadata)>8_000_000:
            file_refs=[m.decode('utf-8') for m in re.findall(rb'"blobFilePath"\s*:\s*"([^"\\]+)"',raw_metadata)]
            starts=[float(x) for x in re.findall(rb'"startTime"\s*:\s*(-?[0-9.]+)',raw_metadata)]
            ends=[float(x) for x in re.findall(rb'"endTime"\s*:\s*(-?[0-9.]+)',raw_metadata)]
            if not file_refs or len(file_refs)>10000 or not (len(file_refs)==len(starts)==len(ends)):
                raise ValueError('Malformed large sample index')
            durations=[e-b for b,e in zip(starts,ends)]
        else:
            metadata = json.loads(raw_metadata)
            if not isinstance(metadata, list) or len(metadata)>10000 or any(not isinstance(x,dict) for x in metadata):
                raise ValueError('Unexpected sample index')
            file_refs=[x.get('blobFilePath') for x in metadata]
            durations=[float(x['endTime']) - float(x['startTime']) for x in metadata]
        if any(not math.isfinite(d) or d<0 or d>600 for d in durations):raise ValueError('Invalid duration metadata')
        audio_names = sorted(n for n in names if n.lower().endswith(('.webm','.wav','.flac','.mp3','.ogg')))
        groups = Counter(file_refs)
        if not audio_names or any(n not in audio_names for n in groups):
            raise ValueError('Archive audio references invalid')
        by_digest = {}
        for name in audio_names:
            info = z.getinfo(name)
            if info.file_size > 70_000_000:
                raise ValueError('Individual recording too large')
            digest = hashlib.sha256(z.read(name)).hexdigest()
            by_digest.setdefault(digest, []).append(name)
        return {
            'indexed_segments':len(file_refs),
            'segment_duration_seconds_range': [round(min(durations,default=0),3),round(max(durations,default=0),3)],
            'references_per_file':dict(groups),
            'audio_file_count':len(audio_names),
            'unique_recordings':len(by_digest),
            'duplicate_sets':[v for v in by_digest.values() if len(v)>1],
            'unique_audio_names':[v[0] for v in by_digest.values()],
        }


def decode_file(path, name):
    import numpy as np
    from faster_whisper.audio import decode_audio
    with zipfile.ZipFile(path) as z:
        info = z.getinfo(name)
        if info.file_size > 70_000_000: raise ValueError('Unexpected recording size')
        result = decode_audio(io.BytesIO(z.read(name)), sampling_rate=AUDIO_RATE)
    if result.ndim != 1 or len(result) > 12 * 60 * AUDIO_RATE:
        raise ValueError('Unexpected decoded duration')
    return np.asarray(result, dtype=np.float32)


def crop_windows(audio, seconds=6, max_windows=8):
    """Evenly distributed non-overlapping chunks; caller filters by speech content."""
    import numpy as np
    n = seconds * AUDIO_RATE
    count = len(audio)//n
    if count <= 0: return []
    indexes = sorted(set(int(i) for i in np.linspace(0,count-1,num=min(max_windows,count))))
    return [(i * seconds, np.asarray(audio[i*n:(i+1)*n], dtype=np.float32)) for i in indexes]


def speech_window(pcm):
    """Basic quality filter; NOT speaker authentication."""
    import numpy as np
    import webrtcvad
    x=np.asarray(pcm,dtype=np.float32)
    if len(x)<2*AUDIO_RATE: return False
    level=float(np.sqrt(np.mean(x*x)))
    if not (0.004 <= level <= 0.5):return False
    if float(np.mean(np.abs(x)>=0.995))>0.03:return False
    y=(np.clip(x,-0.999,0.999)*32767).astype('<i2').tobytes()
    frame=640
    vad=webrtcvad.Vad(2)
    voice_count=sum(bool(vad.is_speech(y[k:k+frame], AUDIO_RATE)) for k in range(0,len(y)-frame+1,frame))
    return voice_count>=60


def assess(path, *, score=False, max_windows=8):
    import numpy as np
    inv=archive_inventory(path)
    print('LOCAL ARCHIVE REVIEW (no uploads, no saved output audio)')
    print(json.dumps({k:v for k,v in inv.items() if k!='unique_audio_names'},indent=2))
    verifier = None
    owner = None
    candidate = None
    if score:
        from voice.identity import MODEL_ROOT, SpeakerVerifier
        verifier=SpeakerVerifier(MODEL_ROOT/'ecapa'/'embedding_model.ckpt')
        profile,binding=verifier._profile()
        calibration=verifier._calibration(binding)
        owner=(profile['centroid'],calibration['accept_floor'],calibration['reject_ceiling'])
        print(f"Current owner acceptance={owner[1]:.4f} non-owner ceiling={owner[2]:.4f}")
        try:
            from vorak_integrated.voice_core.multistyle import read_profile,candidate_path,prototypes,evaluate,similarity
            doc=read_profile(candidate_path())
            if doc is not None:
                result=evaluate(doc)
                candidate=(prototypes(doc['training']),similarity,result)
                print(f"Previous v10 candidate: ready={result['ready']} gap={result['gap']:.4f} (NOT ACTIVE)")
        except (ImportError,ValueError,KeyError,RuntimeError) as exc:
            print('Previous candidate unavailable:',type(exc).__name__)
        verifier.warmup()
    for name in inv['unique_audio_names']:
        audio=decode_file(path,name)
        windows=crop_windows(audio,seconds=6,max_windows=max_windows)
        evaluated=[]
        old_scores=[]
        candidate_scores=[]
        for at,w in windows:
            if not speech_window(w):continue
            evaluated.append(at)
            if verifier:
                from voice.audio import AudioClip,validate_audio
                from voice.identity import _cosine
                clip=validate_audio(AudioClip(w.astype(np.float32),sample_rate=AUDIO_RATE))
                emb=verifier.embed(clip)
                old_scores.append(_cosine(emb,owner[0]))
                if candidate:candidate_scores.append(candidate[1](emb,candidate[0]))
        print(f'{name}: decoded_seconds={len(audio)/AUDIO_RATE:.1f}, candidate_windows={len(windows)}, usable_speech_windows={len(evaluated)}')
        if old_scores:
            print('  Existing owner: min={:.4f}, median={:.4f}, max={:.4f}; passes={}/{}'.format(min(old_scores),float(np.median(old_scores)),max(old_scores),sum(v>=owner[1] for v in old_scores),len(old_scores)))
        if candidate_scores:
            print('  Multi-style candidate: min={:.4f}, median={:.4f}, max={:.4f}; these are NOT authorization results'.format(min(candidate_scores),float(np.median(candidate_scores)),max(candidate_scores)))
    if score:
        print('IMPORTANT: Archive segments are not independently authenticated. No profile was activated or modified.')


def main(argv=None):
    p=argparse.ArgumentParser(description='Review owner voice archive locally without changing enrollment')
    p.add_argument('--archive',required=True)
    p.add_argument('--scores',action='store_true',help='Run existing pinned ECAPA model and compare to calibrated owner profile')
    p.add_argument('--max-windows',type=int,default=6,choices=range(1,13),metavar='1..12')
    args=p.parse_args(argv)
    assess(args.archive,score=args.scores,max_windows=args.max_windows)

if __name__=='__main__':main()
