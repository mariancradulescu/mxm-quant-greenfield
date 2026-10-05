// TRIAD V4: frozen standalone n-by-3 one-sided Jacobi SVD; no market reader.
#include <array>
#include <vector>
#include <cmath>
#include <limits>
#include <algorithm>
#include <iostream>
#include <iomanip>
#include <string>
using Row=std::array<double,3>;
struct Projection { bool accepted=false; std::string status="NUMERICAL_SUPPORT_FAILURE"; int rank=0,sweeps=0; std::array<double,3> singular{}; double rms=0,orth=0; std::vector<double> normalized; };
Projection current_projection(const std::vector<Row>& X,const std::vector<double>& D){
 Projection o; const size_t n=X.size(); if(n==0||D.size()!=n)return o;
 Row scale{}; double dnorm2=0;
 for(size_t i=0;i<n;++i){if(!std::isfinite(D[i]))return o;dnorm2+=D[i]*D[i];for(int j=0;j<3;++j){if(!std::isfinite(X[i][j]))return o;scale[j]+=X[i][j]*X[i][j];}}
 for(int j=0;j<3;++j){scale[j]=std::sqrt(scale[j]/n);if(!(scale[j]>1e-12)||!std::isfinite(scale[j]))return o;}
 std::vector<Row> Z(n),B(n);for(size_t i=0;i<n;++i)for(int j=0;j<3;++j)B[i][j]=Z[i][j]=X[i][j]/scale[j];
 std::array<Row,3> V{{Row{1,0,0},Row{0,1,0},Row{0,0,1}}};
 const double tol=8*std::numeric_limits<double>::epsilon();
 const std::array<std::array<int,2>,3> pairs{{{{0,1}},{{0,2}},{{1,2}}}};
 auto moments=[&](int p,int q){Row m{};for(size_t i=0;i<n;++i){m[0]+=B[i][p]*B[i][p];m[1]+=B[i][q]*B[i][q];m[2]+=B[i][p]*B[i][q];}return m;};
 bool converged=false;
 for(int sweep=0;sweep<100;++sweep){
  for(auto pair:pairs){int p=pair[0],q=pair[1];auto m=moments(p,q);double a=m[0],b=m[1],g=m[2];
   if(std::abs(g)<=tol*std::sqrt(a)*std::sqrt(b))continue;
   double tau=(b-a)/(2*g);double t=std::isfinite(tau)?std::copysign(1.0,tau)/(std::abs(tau)+std::hypot(1.0,tau)):g/(b-a);
   double c=1/std::hypot(1.0,t),s=c*t;
   for(size_t i=0;i<n;++i){double bp=B[i][p],bq=B[i][q];B[i][p]=c*bp-s*bq;B[i][q]=s*bp+c*bq;}
   for(int i=0;i<3;++i){double vp=V[i][p],vq=V[i][q];V[i][p]=c*vp-s*vq;V[i][q]=s*vp+c*vq;}
  }
  o.sweeps=sweep+1;converged=true;
  for(auto pair:pairs){auto m=moments(pair[0],pair[1]);if(!(std::abs(m[2])<=tol*std::sqrt(m[0])*std::sqrt(m[1])))converged=false;}
  if(converged)break;
 }
 if(!converged)return o;
 Row sv{};for(int j=0;j<3;++j){for(size_t i=0;i<n;++i)sv[j]+=B[i][j]*B[i][j];sv[j]=std::sqrt(sv[j]);}
 std::array<int,3> order{{0,1,2}};std::stable_sort(order.begin(),order.end(),[&](int a,int b){return sv[a]>sv[b];});
 Row beta{};
 for(int k=0;k<3;++k){int j=order[k];double sig=sv[j];o.singular[k]=sig;if(sig>1e-12)++o.rank;
  size_t imax=0;for(size_t i=1;i<n;++i)if(std::abs(B[i][j])>std::abs(B[imax][j]))imax=i;
  double sign=std::signbit(B[imax][j])?-1.:1.;
  if(sig>1e-12*sv[order[0]]){double ud=0;for(size_t i=0;i<n;++i)ud+=(sign*B[i][j]/sig)*D[i];for(int l=0;l<3;++l)beta[l]+=(sign*V[l][j])*(ud/sig);}
 }
 if(o.rank!=3||n<5){o.status="CANONICAL_RANK_OR_COUNT_REJECTED";return o;}
 std::vector<double> rd(n);Row orth{};double r2=0;
 for(size_t i=0;i<n;++i){double predicted=0;for(int j=0;j<3;++j)predicted+=Z[i][j]*beta[j];rd[i]=D[i]-predicted;r2+=rd[i]*rd[i];for(int j=0;j<3;++j)orth[j]+=Z[i][j]*rd[i];}
 o.orth=std::max({std::abs(orth[0]),std::abs(orth[1]),std::abs(orth[2])});o.rms=std::sqrt(r2/n);
 if(!std::isfinite(o.orth)||!(o.orth<1e-9*std::max(1.,std::sqrt(dnorm2)))){o.status="CANONICAL_ORTHOGONALITY_REJECTED";return o;}
 if(!std::isfinite(o.rms)||!(o.rms>=1e-10)){o.status="CANONICAL_RESIDUAL_RMS_REJECTED";return o;}
 o.normalized.resize(n);for(size_t i=0;i<n;++i)o.normalized[i]=rd[i]/o.rms;
 o.accepted=true;o.status="ACCEPTED";return o;
}
#ifndef TRIAD_V4_KERNEL_NO_MAIN
int main(){std::cout<<std::setprecision(17);size_t n;while(std::cin>>n){std::vector<Row>X(n);std::vector<double>D(n);for(size_t i=0;i<n;++i)std::cin>>X[i][0]>>X[i][1]>>X[i][2]>>D[i];auto o=current_projection(X,D);std::cout<<"{\"accepted\":"<<(o.accepted?"true":"false")<<",\"status\":\""<<o.status<<"\",\"rank\":"<<o.rank<<",\"sweeps\":"<<o.sweeps<<",\"singular_values\":[";for(int j=0;j<3;++j)std::cout<<(j?",":"")<<o.singular[j];std::cout<<"],\"rms\":"<<o.rms<<",\"orthogonality_error\":"<<o.orth<<",\"normalized\":[";for(size_t i=0;i<o.normalized.size();++i)std::cout<<(i?",":"")<<o.normalized[i];std::cout<<"]}\n";}}
#endif
