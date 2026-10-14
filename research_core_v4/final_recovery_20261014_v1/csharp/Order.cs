using System;
using System.Text.Json;
public static class OrderKernel {
 public static object Feature(double[] values) {
  if(values.Length!=12)throw new Exception("FEATURE_SCHEMA");
  double R=0,V=0,A=0,mass=0;
  foreach(double r in values){if(!double.IsFinite(r))throw new Exception("FEATURE_SCHEMA");double q=r*r;A+=V*r-R*q;mass+=Math.Abs(V*r)+Math.Abs(R*q);R+=r;V+=q;}
  double tol=mass==0?0:64*(Math.BitIncrement(mass)-mass);
  return new{side=Math.Abs(A)<=tol?0:Math.Sign(A),baseline=Math.Sign(R),area=A,rv=V,@return=R,numeric_tolerance=tol};
 }
 public static int Side(double[] values){var z=JsonSerializer.SerializeToElement(Feature(values));return z.GetProperty("side").GetInt32();}
}
