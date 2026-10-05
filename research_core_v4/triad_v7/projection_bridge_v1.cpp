// ABI only; the inherited production kernel is included byte-for-byte.
#define TRIAD_V4_KERNEL_NO_MAIN
#include "../triad_v4/canonical_projection_jacobi_v1.cpp"
extern "C" int triad_v7_projection(int n,const double* x,const double* d,double* out){
 if(n<0||n>23)return -1;
 std::vector<Row>X(n);std::vector<double>D(n);
 for(int i=0;i<n;i++){for(int j=0;j<3;j++)X[i][j]=x[3*i+j];D[i]=d[i];}
 auto p=current_projection(X,D);
 out[0]=p.accepted?1:0;out[1]=p.rank;out[2]=p.sweeps;
 for(int j=0;j<3;j++)out[3+j]=p.singular[j];out[6]=p.rms;out[7]=p.orth;
 for(int i=0;i<(int)p.normalized.size();i++)out[8+i]=p.normalized[i];
 return 0;
}
