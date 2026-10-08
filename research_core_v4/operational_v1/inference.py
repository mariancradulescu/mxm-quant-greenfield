"""One-sided joint calendar-block wild bootstrap-t; no nominal t critical value."""
import numpy as np

def cluster(x,mask,block_days=7):
    ntrial,days,leaves=x.shape;assert days%block_days==0
    B=days//block_days
    v=x.reshape(ntrial,B,block_days,leaves);m=mask.reshape(v.shape)
    counts=m.sum(2);valid=counts>0
    means=(np.where(m,v,0)).sum(2)/np.maximum(counts,1)
    n=valid.sum(1);mu=(means*valid).sum(1)/np.maximum(n,1)
    u=(means-mu[:,None,:])*valid;s2=(u*u).sum(1)
    se=np.sqrt(s2/np.maximum(n-1,1)/np.maximum(n,1))
    support=(n>=12)&(se>1e-12);third=[]
    # Partition the scoring calendar (after structural warm-up), not raw acquisition calendar.
    # Whole weekly blocks stay in one third; unsupported calendar positions never reindexed.
    for idx in np.array_split(np.arange(B),3):
        vv=valid[:,idx];nn=vv.sum(1);support &= nn>=4
        third.append((means[:,idx]*vv).sum(1)/np.maximum(nn,1))
    return {'mu':mu,'u':u,'n':n,'s2':s2,'se':se,'valid':valid,'support':support,'third':np.stack(third,1)}

def bootstrap_max(g,bank):
    # Common bank R x B signs multiply the entire 261-leaf block vector.
    nt,B,L=g['u'].shape
    totals=(bank@g['u'].transpose(1,0,2).reshape(B,nt*L)).reshape(len(bank),nt,L).transpose(1,0,2)
    var=(g['n'][:,None,:]*g['s2'][:,None,:]-totals**2)/np.maximum(g['n'][:,None,:]-1,1)
    ts=totals/np.sqrt(np.maximum(var,1e-24));ts=np.where(g['support'][:,None,:],ts,-np.inf)
    return np.sort(ts.max(-1),axis=1)

def decisions(g,sorted_max,shift):
    t=(g['mu']+shift)/np.maximum(g['se'],1e-12)
    p=np.empty(t.shape)
    for i in range(len(t)):
        p[i]=(1+len(sorted_max[i])-np.searchsorted(sorted_max[i],t[i],side='left'))/(len(sorted_max[i])+1)
    significant=(p<=.025)&g['support']
    stable=((g['third']+shift[:,None,:])>0).sum(1)>=2
    return significant&stable,significant,p,t

def wilson(k,n,z):
    p=np.asarray(k)/n;den=1+z*z/n;mid=(p+z*z/(2*n))/den
    half=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return mid-half,mid+half
