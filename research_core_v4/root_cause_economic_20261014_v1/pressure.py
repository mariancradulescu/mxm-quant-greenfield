"""Frozen endogenous level pressure: no parameter fitting, future input, or outcome access."""
def feature(bars):
    if len(bars)!=12:return {'side':0,'baseline':0,'reason':'BAR_COUNT'}
    u=max(b[1] for b in bars);l=min(b[2] for b in bars);r=u-l
    baseline=(bars[-1][3]>bars[0][0])-(bars[-1][3]<bars[0][0])
    if r<=0:return {'side':0,'baseline':baseline,'reason':'FLAT_RANGE'}
    signals=[]
    for side in (1,-1):
        contact=[b[1]>=u-.1*r if side==1 else b[2]<=l+.1*r for b in bars]
        clusters=[]
        for i,yes in enumerate(contact):
            if yes:
                if i and contact[i-1]:clusters[-1][1]=i
                else:clusters.append([i,i])
        if len(clusters)<3:continue
        aa,bb,cc=clusters[-3:]
        if cc[1]!=11:continue
        depths=[]
        for left,right in ((aa,bb),(bb,cc)):
            middle=bars[left[1]+1:right[0]]
            depths.append(u-min(b[2] for b in middle) if side==1 else max(b[1] for b in middle)-l)
        d1,d2=depths
        close=bars[-1][3];inside=(u-.25*r<=close<u-.02*r) if side==1 else (l+.02*r<close<=l+.25*r)
        if d1>=.2*r and d2>=.1*r and d2<=.75*d1 and inside:signals.append(side)
    side=signals[0] if len(signals)==1 else 0
    return {'side':side,'baseline':baseline,'reason':'THREE_REVISITS_SHRINKING_RETREATS' if side else 'NO_UNIQUE_PRESSURE','range':r,'upper':u,'lower':l}
