"""VORAK multi-condition owner speaker calibration.

The same owner's speaking modes are modeled as several embeddings, NOT several
identities. Audio is never persisted; templates are protected via Windows DPAPI.
A candidate cannot authorize any VORAK command until independently validated
against held-out owner utterances AND explicitly consenting non-owner trials.
This is experimental voice recognition, not robust anti-spoofing.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import sys
import tempfile
from datetime import datetime, timezone

GROUPS = ('normal', 'casual', 'funny', 'investor', 'angry')
OWNER_PER_GROUP = 4
HOLDOUT_PER_GROUP = 2
GUEST_PER_PERSON = 4
GUESTS = ('guest1', 'guest2')
DIM = 192
MIN_GAP = 0.10
MAX_DURATION = 8
SECONDS = 5

class EnrollmentError(RuntimeError):
    pass


def root():
    from voice.identity import IDENTITY_ROOT
    return Path(IDENTITY_ROOT)


def model_id():
    from voice.identity import MODEL_ID
    return MODEL_ID


def protect(data: bytes) -> bytes:
    if os.name != 'nt':
        raise EnrollmentError('DPAPI storage requires Windows')
    try:
        import win32crypt
        return win32crypt.CryptProtectData(data, 'VORAK multi-style owner', None, None, None, 0)
    except (ImportError, OSError) as exc:
        raise EnrollmentError('Windows DPAPI unavailable. Install pywin32 in the existing venv.') from exc


def unprotect(data: bytes) -> bytes:
    if os.name != 'nt':
        raise EnrollmentError('DPAPI storage requires Windows')
    try:
        import win32crypt
        return win32crypt.CryptUnprotectData(data, None, None, None, 0)[1]
    except (ImportError, OSError) as exc:
        raise EnrollmentError('Unable to decrypt private owner profile for this Windows account.') from exc


def candidate_path():
    return root() / 'multistyle_candidate.dpapi'


def active_path():
    return root() / 'multistyle_active.dpapi'


def read_profile(path):
    try:
        if not path.exists(): return None
        doc = json.loads(unprotect(path.read_bytes()).decode('utf-8'))
        if not isinstance(doc, dict) or doc.get('version') != 1 or doc.get('model_id') != model_id():
            raise EnrollmentError('Profile version/model mismatch')
        return doc
    except EnrollmentError:
        raise
    except (ValueError, OSError, UnicodeError) as exc:
        raise EnrollmentError('Private profile data invalid; refusing authorization.') from exc


def save_profile(path, doc):
    """Atomic encrypted write; refuses non-local path tricks."""
    directory = root().resolve()
    if not directory.is_dir() or path.parent.resolve() != directory or path.is_symlink():
        raise EnrollmentError('Private identity directory is missing or redirected')
    data = protect(json.dumps(doc, separators=(',', ':'), allow_nan=False).encode('utf-8'))
    fd, tmp = tempfile.mkstemp(prefix='.vorak-multistyle-', dir=directory)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data); out.flush(); os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def initial():
    return {'version':1, 'model_id': model_id(), 'created_utc':datetime.now(timezone.utc).isoformat(),
            'training':{g:[] for g in GROUPS},'holdout':{g:[] for g in GROUPS},
            'nonowner':{g:[] for g in GUESTS}}


def normalize(v):
    if not isinstance(v, (list, tuple)) or len(v)!=DIM or not all(isinstance(x, (int,float)) and math.isfinite(x) for x in v):
        raise EnrollmentError('Invalid speaker embedding')
    magnitude=math.sqrt(sum(x*x for x in v))
    if magnitude < 1e-9:raise EnrollmentError('Zero speaker embedding')
    return [float(x)/magnitude for x in v]


def cosine(a,b):
    return sum(x*y for x,y in zip(a,b))


def centroid(vectors):
    vectors=[normalize(v) for v in vectors]
    return normalize([sum(v[i] for v in vectors)/len(vectors) for i in range(DIM)])


def prototypes(training):
    if set(training) != set(GROUPS) or any(len(training[g])!=OWNER_PER_GROUP for g in GROUPS):
        raise EnrollmentError('Need 20 owner enrollment samples across all five styles')
    return {g:centroid(training[g]) for g in GROUPS}


def similarity(vector, protos):
    v=normalize(vector)
    if set(protos)!=set(GROUPS):raise EnrollmentError('Invalid owner prototypes')
    all_center=centroid(list(protos.values()))
    # Same owner, five speaking conditions. All scores measured by same rule.
    return 0.25*cosine(v,all_center)+0.75*max(cosine(v,p) for p in protos.values())


def evaluate(doc):
    ps=prototypes(doc['training'])
    if set(doc['holdout'])!=set(GROUPS) or any(len(doc['holdout'][g])!=HOLDOUT_PER_GROUP for g in GROUPS):
        raise EnrollmentError('Need 10 independent owner check samples (two per style)')
    if set(doc['nonowner'])!=set(GUESTS) or any(len(doc['nonowner'][g])!=GUEST_PER_PERSON for g in GUESTS):
        raise EnrollmentError('Need four consenting non-owner samples from each of two different people')
    pos=[similarity(v,ps) for g in GROUPS for v in doc['holdout'][g]]
    neg=[similarity(v,ps) for g in GUESTS for v in doc['nonowner'][g]]
    floor=min(pos); ceiling=max(neg); gap=floor-ceiling
    # No threshold relaxation or implicit acceptance when owner and nonowner overlap.
    if gap < MIN_GAP:
        return {'ready':False,'gap':gap,'worst_owner':floor,'highest_nonowner':ceiling,
                'reason':'Insufficient owner/non-owner separation. Do not activate.', 'positive_scores':pos,'negative_scores':neg}
    threshold=(floor+ceiling)/2
    return {'ready':True,'gap':gap,'threshold':threshold,'reject_ceiling':ceiling,
            'worst_owner':floor,'highest_nonowner':ceiling,'positive_scores':pos,'negative_scores':neg,
            'prototypes':ps}


def validate_active(doc):
    if doc is None: return None
    if doc.get('state') != 'active' or doc.get('model_id')!=model_id() or doc.get('version')!=1:
        raise EnrollmentError('Active owner profile malformed')
    ps=doc.get('prototypes')
    if not isinstance(ps,dict) or set(ps)!=set(GROUPS):raise EnrollmentError('Active owner prototypes invalid')
    for g in GROUPS:normalize(ps[g])
    threshold=doc.get('threshold'); reject=doc.get('reject_ceiling')
    if not all(type(x) in (float,int) and math.isfinite(x) for x in (threshold,reject)):
        raise EnrollmentError('Active threshold invalid')
    if not (-1<=reject<threshold<=1):raise EnrollmentError('Unacceptable threshold relationship')
    if doc.get('gap',0) < MIN_GAP:raise EnrollmentError('Unacceptable calibration margin')
    return doc


def active():
    return validate_active(read_profile(active_path()))


def classify_embedding(v, config):
    config=validate_active(config)
    score=similarity(v,config['prototypes'])
    if score>=config['threshold']:
        return 'owner_verified',score
    if score<=config['reject_ceiling']:
        return 'speaker_mismatch',score
    return 'verification_uncertain',score


def capture_embedding(verifier, device, seconds):
    import numpy as np
    import sounddevice as sd
    from voice.audio import AudioClip, validate_audio
    from vorak_integrated.voice_core.identity import condition_pcm
    rec=sd.rec(int(seconds*16000), samplerate=16000, channels=1, dtype='float32', device=device)
    sd.wait()
    raw=np.asarray(rec[:,0], dtype=np.float32).copy()
    del rec
    pcm=np.rint(np.clip(raw,-1.,1.)*32767).astype('<i2').tobytes()
    # Enrollment must contain actual speech, not just stationary microphone noise.
    # VAD is a capture-quality check, NOT evidence of speaker identity.
    import webrtcvad
    vad=webrtcvad.Vad(2)
    frame_bytes=640  # 20 ms, 16 kHz, signed 16-bit PCM
    frames=(pcm[k:k+frame_bytes] for k in range(0,len(pcm)-frame_bytes+1,frame_bytes))
    if sum(bool(vad.is_speech(frame,16000)) for frame in frames)<60:
        raise EnrollmentError('Too little speech detected in recording; retry the same sample.')
    check=condition_pcm(pcm)
    if check.conditioned_pcm is None:
        raise EnrollmentError('Mic recording failed conditioning: '+check.status)
    samples=np.frombuffer(check.conditioned_pcm,dtype='<i2').astype(np.float32)/32768.
    try:
        clip=validate_audio(AudioClip(samples.astype(np.float32), sample_rate=16000))
        return normalize(verifier.embed(clip))
    finally:
        del raw,samples,pcm


def next_target(doc, phase):
    if phase=='train':
        section, groups, count='training',GROUPS,OWNER_PER_GROUP
    elif phase=='check':
        section, groups, count='holdout',GROUPS,HOLDOUT_PER_GROUP
    elif phase=='guests':
        section, groups, count='nonowner',GUESTS,GUEST_PER_PERSON
    else:raise EnrollmentError('Unknown phase')
    for g in groups:
        if len(doc[section][g])<count:return section,g,len(doc[section][g])+1,count
    return None


def status(doc):
    return {n:{k:len(v) for k,v in doc[n].items()} for n in ('training','holdout','nonowner')}


def enroll(phase, device, seconds):
    # These are local interactive operations executed under the signed-in Windows user.
    if active_path().exists():
        raise EnrollmentError('A multi-style profile is already active. Existing authentication unchanged.')
    doc=read_profile(candidate_path()) or initial()
    if phase=='check' and next_target(doc,'train'):
        raise EnrollmentError('Complete training before owner holdout tests')
    if phase=='guests' and (next_target(doc,'train') or next_target(doc,'check')):
        raise EnrollmentError('Complete owner phases before non-owner validation')
    from voice.identity import SpeakerVerifier,MODEL_ROOT
    verifier=SpeakerVerifier(MODEL_ROOT/'ecapa'/'embedding_model.ckpt')
    print('Warming local ECAPA model. No audio or embeddings uploaded.',flush=True)
    verifier.warmup()
    while True:
        target=next_target(doc,phase)
        if not target:break
        section,group,index,count=target
        if phase=='guests' and index==1:
            print('For',group,'use a DIFFERENT consenting person. No one should provide your voice as a guest.')
            if input('Guest explicitly agreed to local biometric comparison? Type CONSENT: ').strip()!='CONSENT':
                raise EnrollmentError('Consent is required for each non-owner.')
        print('\nPhase:',phase,'Mode:',group,'Sample:',f'{index}/{count}')
        if group=='angry':print('Use your natural frustrated/angry speaking style; avoid microphone clipping.')
        elif group=='investor':print('Speak as you would when discussing an investment or business decision.')
        elif group=='casual':print('Speak casually as you normally talk.')
        elif group=='funny':print('Use your own playful or humorous speaking style.')
        elif group=='normal':print('Speak in your normal everyday voice.')
        else:print('Ask consenting',group,'to speak a fresh sentence.')
        if input('Press Enter to record, or type STOP to preserve progress: ').strip().upper()=='STOP':break
        vector=capture_embedding(verifier,device,seconds)
        # No raw samples persisted, only DPAPI-encrypted embeddings.
        doc[section][group].append(vector)
        save_profile(candidate_path(),doc)
        print('Encrypted embedding saved. Progress:',json.dumps(status(doc),separators=(',',':')))
    print('Current progress:',json.dumps(status(doc),indent=2))


def activate():
    if active_path().exists():raise EnrollmentError('Multi-style profile already active; refusing replacement')
    doc=read_profile(candidate_path())
    if doc is None: raise EnrollmentError('Candidate not found. Collect owner samples first.')
    report=evaluate(doc)
    print('Owner worst score:',f"{report['worst_owner']:.4f}",'Non-owner highest:',f"{report['highest_nonowner']:.4f}",
          'Separation:',f"{report['gap']:.4f}")
    if not report['ready']:
        raise EnrollmentError(report['reason'])
    print('Experimental profile is eligible. It is NOT spoof-proof or tested against the public.')
    print('No other owners will be enrolled. Previous owner enrollment/calibration are preserved.')
    if input('Type ACTIVATE MULTISTYLE to use this profile for VORAK commands: ').strip()!='ACTIVATE MULTISTYLE':
        raise EnrollmentError('Activation cancelled.')
    policy={'version':1,'model_id':model_id(),'state':'active',
            'prototypes':report['prototypes'],'threshold':report['threshold'],
            'reject_ceiling':report['reject_ceiling'],'gap':report['gap'],
            'activated_utc':datetime.now(timezone.utc).isoformat()}
    save_profile(active_path(),policy)
    print('Multi-style owner profile activated; restart VORAK. Old enrollment remains unchanged.')


def main(argv=None):
    p=argparse.ArgumentParser(description='VORAK multi-style owner identity enrollment (local only)')
    p.add_argument('command', choices=('status','train','check','guests','evaluate','activate'))
    p.add_argument('--device',type=int,default=1)
    p.add_argument('--seconds',type=int,default=SECONDS,choices=range(4,9))
    args=p.parse_args(argv)
    try:
        doc=read_profile(candidate_path())
        if args.command=='status':
            print('Active:',active_path().exists(),'Candidate progress:',json.dumps(status(doc) if doc else {},indent=2))
        elif args.command in ('train','check','guests'):
            enroll(args.command,args.device,args.seconds)
        elif args.command=='evaluate':
            if not doc:raise EnrollmentError('No candidate found')
            r=evaluate(doc)
            print(json.dumps({k:v for k,v in r.items() if k not in ('positive_scores','negative_scores','prototypes')},indent=2))
        elif args.command=='activate':activate()
        return 0
    except EnrollmentError as ex:
        print('NOT ACTIVATED:',str(ex),file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('\nCancelled. Previously saved encrypted progress retained.')
        return 130

if __name__=='__main__':sys.exit(main())
