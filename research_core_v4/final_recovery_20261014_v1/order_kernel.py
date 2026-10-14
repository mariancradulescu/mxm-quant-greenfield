"""Closed-bar return/quadratic-variation ordering; no future inputs or fitting."""
import math
def sign(x):return int(x>0)-int(x<0)
def feature(values):
    if len(values)!=12 or any(not math.isfinite(r) for r in values):raise ValueError('FEATURE_SCHEMA')
    R=V=A=mass=0.
    for r in values:
        q=r*r;x=V*r-R*q;A+=x;mass+=abs(V*r)+abs(R*q);R+=r;V+=q
    tolerance=64*math.ulp(mass) if mass else 0.
    return {'side':0 if abs(A)<=tolerance else sign(A),'baseline':sign(R),'area':A,'rv':V,'return':R,'numeric_tolerance':tolerance}
