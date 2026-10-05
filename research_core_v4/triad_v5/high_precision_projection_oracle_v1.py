"""Frozen arbitrary-precision reference. No numpy, no Y, no network."""
from decimal import Decimal as Dec, localcontext, ROUND_HALF_EVEN

PAIRS=((0,1),(0,2),(1,2))
def exact(v):
    return Dec.from_float(float(v))
def dot(a,b):
    return sum((x*y for x,y in zip(a,b)),Dec(0))
def matmul(a,b):
    return [[sum((a[i][k]*b[k][j] for k in range(len(b))),Dec(0)) for j in range(len(b[0]))] for i in range(len(a))]
def transpose(a):return [list(row) for row in zip(*a)]
def frob(a):return sum((v*v for row in a for v in row),Dec(0)).sqrt()
def oracle(X,D,digits):
    with localcontext() as ctx:
        ctx.prec=digits;ctx.rounding=ROUND_HALF_EVEN
        n=len(X);x=[[exact(v) for v in row] for row in X];d=[exact(v) for v in D]
        assert n>=5 and n<=23 and len(d)==n and all(len(row)==3 for row in x)
        assert all(v.is_finite() for row in x for v in row) and all(v.is_finite() for v in d)
        scale=[(sum((row[j]*row[j] for row in x),Dec(0))/Dec(n)).sqrt() for j in range(3)]
        if not all(s>Dec('1e-12') for s in scale):return {'status':'MATHEMATICAL_SCALE_REJECTED','accepted':False,'scale':[str(s) for s in scale]}
        z=[[row[j]/scale[j] for j in range(3)] for row in x]
        original=matmul(transpose(z),z);g=[row[:] for row in original];v=[[Dec(int(i==j)) for j in range(3)] for i in range(3)]
        gn=max(Dec(1),frob(original));tol=Dec(10)**(-digits+20)*gn;converged=False
        for sweep in range(128):
            for p,q in PAIRS:
                cross=g[p][q]
                if abs(cross)<=tol:continue
                tau=(g[q][q]-g[p][p])/(2*cross)
                sign=Dec(-1) if tau<0 else Dec(1)
                t=sign/(abs(tau)+(1+tau*tau).sqrt());c=1/(1+t*t).sqrt();s=c*t
                rot=[[Dec(int(i==j)) for j in range(3)] for i in range(3)]
                rot[p][p]=rot[q][q]=c;rot[p][q]=s;rot[q][p]=-s
                g=matmul(matmul(transpose(rot),g),rot);v=matmul(v,rot)
            off=max(abs(g[p][q]) for p,q in PAIRS)
            if off<=tol:converged=True;break
        if not converged:return {'status':'NUMERICAL_ORACLE_AMBIGUOUS_NONCONVERGENCE','accepted':False,'sweeps':128}
        reconstructed=matmul(matmul(v,[[g[i][i] if i==j else Dec(0) for j in range(3)] for i in range(3)]),transpose(v))
        eigen_backward=max(abs(reconstructed[i][j]-original[i][j]) for i in range(3) for j in range(3))
        if eigen_backward>Dec(10)**(-digits+15)*gn:return {'status':'NUMERICAL_ORACLE_AMBIGUOUS_EIGEN_RECONSTRUCTION','accepted':False,'eigen_backward_error':str(eigen_backward)}
        w=matmul(z,v);sv=[dot([row[j] for row in w],[row[j] for row in w]).sqrt() for j in range(3)]
        order=sorted(range(3),key=lambda j:(-sv[j],j));sing=[sv[j] for j in order]
        rank=sum(s>Dec('1e-12') for s in sing);keep=[j for j in order if sv[j]>Dec('1e-12')*sing[0]]
        beta=[Dec(0)]*3
        for j in keep:
            column=[row[j] for row in w];imax=max(range(n),key=lambda i:(abs(column[i]),-i));sign=Dec(-1) if column[imax]<0 else Dec(1)
            ud=dot([sign*a for a in column],d)/(sv[j]*sv[j])
            for l in range(3):beta[l]+=sign*v[l][j]*ud
        rd=[d[i]-dot(z[i],beta) for i in range(n)];rms=(dot(rd,rd)/Dec(n)).sqrt()
        accepted=rank==3 and rms>=Dec('1e-10')
        orth=max(abs(dot([row[j] for row in z],rd)) for j in range(3))
        return {'status':'MATHEMATICALLY_ELIGIBLE' if accepted else 'MATHEMATICAL_RANK_OR_RMS_REJECTED','accepted':accepted,'rank':rank,'retained':len(keep),'singular_values':[str(s) for s in sing],'scale':[str(s) for s in scale],'Z_Frobenius':str(frob(z)),'residual_RMS':str(rms),'residual':[str(a) for a in rd],'normalized':[str(a/rms) for a in rd] if rms else [],'orthogonality_error':str(orth),'eigen_backward_error':str(eigen_backward),'sweeps':sweep+1}
