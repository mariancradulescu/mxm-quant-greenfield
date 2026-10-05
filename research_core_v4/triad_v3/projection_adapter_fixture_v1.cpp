// Deterministic projection kernel fixtures only: no Y, RNG or inference calls.
#define main historical_worker_main_not_called
#include "../triad_v2/exact_geometry_worker_v1.cpp"
#undef main
int main() {
    cout << setprecision(17);
    int n;
    while (cin >> n) {
        vector<array<double, 3>> X(n);
        vector<double> feature(n);
        for (int i = 0; i < n; ++i) {
            for (int j = 0; j < 3; ++j) cin >> X[i][j];
            cin >> feature[i];
        }
        // Real clockfit reproduction: n one-bridge canonical target relations.
        // Features fit within raw clipping limits; all scales are positive one.
        Geo geometry{};
        double returns[BARS][A] = {};
        for (int a = 0; a < A; ++a) geometry.scale[a] = 1;
        for (int r = 0; r < R; ++r) geometry.rc[r] = -1;
        for (int t = 0; t < T; ++t) geometry.tc[t] = -1;
        for (int i = 0; i < n; ++i) {
            geometry.tc[i] = 0; geometry.ta[i] = i;
            geometry.rc[i] = 0; geometry.target[i] = i; geometry.rs[i] = 1;
            geometry.causal[0][0][i] = true;
            geometry.leg[i][0] = i; geometry.leg[i][1] = n+i; geometry.leg[i][2] = 2*n+i;
            geometry.sgn[i][0] = 1; geometry.sgn[i][1] = -1; geometry.sgn[i][2] = -1;
            returns[12][i] = X[i][1];
            returns[11][i] = X[i][2]-X[i][1];
            returns[11][n+i] = X[i][2]-feature[i];
        }
        string actual_status;
        try {
            Clock actual = clockfit(geometry, 0, 0, 0, returns);
            actual_status = actual.ok ? "ACCEPTED" : "INELIGIBLE";
        } catch (const exception& error) {
            actual_status = string("THROWS_")+error.what();
        }
        double gram[3][3] = {}, rhs[3] = {}, inverse[3][3] = {};
        bool eligible = true;
        for (int j = 1; j < 3; ++j) {
            double s = 0;
            for (int i = 0; i < n; ++i) s += X[i][j]*X[i][j];
            s = sqrt(s/n);
            if (!(s > 1e-12)) eligible = false;
            for (int i = 0; i < n; ++i) X[i][j] /= s;
        }
        for (int i = 0; i < n; ++i) for (int j = 0; j < 3; ++j) {
            rhs[j] += X[i][j]*feature[i];
            for (int k = 0; k < 3; ++k) gram[j][k] += X[i][j]*X[i][k];
        }
        double det = gram[0][0]*(gram[1][1]*gram[2][2]-gram[1][2]*gram[2][1])
            -gram[0][1]*(gram[1][0]*gram[2][2]-gram[1][2]*gram[2][0])
            +gram[0][2]*(gram[1][0]*gram[2][1]-gram[1][1]*gram[2][0]);
        eligible = eligible && n >= 5 && inv3(gram, inverse);
        vector<double> rd(n);
        double rms = 0, orth[3] = {};
        if (eligible) {
            double beta[3];
            for (int j = 0; j < 3; ++j) beta[j] = dot3(inverse[j], rhs);
            for (int i = 0; i < n; ++i) {
                rd[i] = feature[i]-dot3(X[i].data(), beta);
                rms += rd[i]*rd[i];
                for (int j = 0; j < 3; ++j) orth[j] += X[i][j]*rd[i];
            }
            rms = sqrt(rms/n);
            eligible = rms >= 1e-10;
            for (int j = 0; j < 3; ++j) if (abs(orth[j]) > 1e-7) eligible = false;
        }
        cout << "{\"actual_clockfit_status\":\"" << actual_status << "\",\"accepted\":" << (eligible ? "true" : "false")
             << ",\"scaled_gram_determinant\":" << det
             << ",\"residual_rms\":" << rms << ",\"normalized\":[";
        for (int i = 0; i < n; ++i) {
            if (i) cout << ',';
            cout << (eligible ? rd[i]/rms : 0);
        }
        cout << "]}\n";
    }
}
