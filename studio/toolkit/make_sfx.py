"""Regenerate the synthetic SFX library into assets/sfx/. Replace any file with a real sample of the same name to upgrade it."""
import numpy as np, wave, os
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets/sfx")
SR=48000; rng=np.random.default_rng(7)
def save(name,x,st=None):
    x=x/ (np.max(np.abs(x))+1e-9)*0.89
    if st is None: st=np.stack([x,x],1)
    w=wave.open(f"{OUT}/{name}.wav","wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((st/ (np.max(np.abs(st))+1e-9)*0.89*32767).astype(np.int16).tobytes()); w.close()
def t(d): return np.arange(int(SR*d))/SR
def bandsweep(noise,f0,f1,q=2.0):
    # time-varying 2-pole resonant bandpass (state variable filter)
    n=len(noise); f=np.geomspace(f0,f1,n); out=np.zeros(n); lp=bp=0.0
    for i in range(n):
        F=2*np.sin(np.pi*f[i]/SR); hp=noise[i]-lp-bp/q; bp+=F*hp; lp+=F*bp; out[i]=bp
    return out
# whoosh: noise through rising-then-falling bandpass, bell envelope, slight stereo pan sweep
d=0.55; tt=t(d); n=rng.standard_normal(len(tt))
a=bandsweep(n[:len(tt)//2],300,3500); b=bandsweep(n[len(tt)//2:],3500,600)
x=np.concatenate([a,b]); env=np.sin(np.pi*tt/d)**2.2; x*=env
pan=np.linspace(-0.7,0.7,len(x)); save("whoosh",x,np.stack([x*(1-pan)/2+x*0.3,x*(1+pan)/2+x*0.3],1))
# swish (short, bright) for text/graphics in
d=0.28; tt=t(d); n=rng.standard_normal(len(tt)); x=bandsweep(n,1500,7000,1.5)*np.sin(np.pi*tt/d)**2; save("swish",x)
# pop: pitched blip with fast downward sweep
d=0.12; tt=t(d); f=900*np.exp(-tt*25)+350; ph=2*np.pi*np.cumsum(f)/SR; x=np.sin(ph)*np.exp(-tt*38); x[:48]*=np.linspace(0,1,48); save("pop",x)
# tick (counter)
d=0.04; tt=t(d); x=np.sin(2*np.pi*2400*tt)*np.exp(-tt*160)+0.3*rng.standard_normal(len(tt))*np.exp(-tt*400); save("tick",x)
# ding: bell with inharmonic partials
d=1.4; tt=t(d); x=sum(a*np.sin(2*np.pi*f*tt)*np.exp(-tt*k) for f,a,k in [(1318,1,3.2),(2637,0.5,4.5),(3520,0.25,6),(1975,0.3,5)]); x[:96]*=np.linspace(0,1,96); save("ding",x)
# impact: sub thump + click transient
d=0.7; tt=t(d); f=110*np.exp(-tt*9)+38; x=np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-tt*6)+0.4*rng.standard_normal(len(tt))*np.exp(-tt*90); save("impact",x)
# riser: rising tone + noise swell, cuts dead at end
d=1.6; tt=t(d); f=np.geomspace(180,1400,len(tt)); x=0.5*np.sin(2*np.pi*np.cumsum(f)/SR)+0.6*bandsweep(rng.standard_normal(len(tt)),400,6000,1.2); x*= (tt/d)**2.5; x[-240:]*=np.linspace(1,0,240); save("riser",x)
# error buzz for crossing out
d=0.35; tt=t(d); x=np.sign(np.sin(2*np.pi*110*tt))*0.6+np.sign(np.sin(2*np.pi*116*tt))*0.4; x*=np.exp(-tt*5); x[:96]*=np.linspace(0,1,96)
import numpy as _n; save("buzz",np.convolve(x,_n.ones(6)/6,'same'))
print("ok")
