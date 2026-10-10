using System;
namespace Mxm.Native {
public static class NativeKernel {
    public static (int Direction,double Correlation,string Reason) Feature(double[] bids,double[] asks) {
        if(bids.Length!=13 || asks.Length!=13) return (0,0,"INVALID");
        var m=new double[13]; var s=new double[13];
        for(int i=0;i<13;i++) {
            if(!double.IsFinite(bids[i]) || !double.IsFinite(asks[i]) || !(0<bids[i] && bids[i]<asks[i])) return (0,0,"INVALID");
            m[i]=Math.Log((bids[i]+asks[i])/2); s[i]=Math.Log(asks[i]/bids[i]);
        }
        var x=new double[12]; var y=new double[12]; double mx=0,my=0;
        for(int i=0;i<12;i++) { x[i]=m[i+1]-m[i]; y[i]=s[i+1]-s[i]; mx+=x[i]; my+=y[i]; }
        mx/=12; my/=12; double xx=0,yy=0,xy=0;
        for(int i=0;i<12;i++) { double a=x[i]-mx,b=y[i]-my; xx+=a*a; yy+=b*b; xy+=a*b; }
        if(xx<=1e-24 || yy<=1e-24) return (0,0,"DEGENERATE_VARIANCE");
        double c=xy/Math.Sqrt(xx*yy); int d=Math.Abs(c)>=0.2 ? (c>0 ? 1:-1):0;
        return (d,c,d!=0 ? "SIGNAL":"WEAK_CONCORDANCE");
    }
}}
