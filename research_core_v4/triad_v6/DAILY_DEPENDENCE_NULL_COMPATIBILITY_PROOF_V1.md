# V6 preexecution daily-dependence compatibility gate

This audit conditions on the certified actual support, fixed prefix scales,
original calendar, and complete declared target membership. It creates no
stochastic calibration outcomes and reads no market Y.

## Inherited definitions

The V2 identification proof fixes
E[Y | current X,D,past,retention] = X beta under the null. With
r = Q_X D and a = sqrt(mean(r^2)), the score is
psi = r' (Y - X b_hat)/(n a). Thus E[psi | current X,D,past,retention] = 0,
for every finite baseline estimate in the declared span. The daily score is
the equal mean of supported clock scores. Availability is fixed independently
of simulated outcomes. The same statement applies to every declared leaveout.

The historical dependence-envelope audit explicitly identifies the required
generic AR025/AR050 unit as the daily 12-leaf score vector, not a baseline
coefficient, variance state, feature, or intraday asset return. A relabeling
of an AR baseline or an intraday process cannot close that omission.

## Calendar and conditioning witness

The latest decision is 15:00 UTC; the longest horizon is 240 minutes.
The V2 training-support implementation admits that label, including its
additional 5-minute buffer and 240-minute purge, by 23:05 UTC, strictly before
the next day's 00:00 update. All preceding day's retained responses and their
predictors are therefore in the next day's past training information. The
earliest next-day predictor uses 07:50 UTC, after this update. There is no
across-day overlap of response windows. Missing clocks are unavailable and
not imputed; this argument concerns any two supported days and makes no
compression or synthetic filling of a missing day.

Let F_d denote information available at the day's start, including yesterday's
admissible training data. The prior supported daily score S_(d-1) is measurable
with respect to F_d. Applying iterated conditional expectation at each causal
clock gives E[S_d | F_d] = 0. For finite second moments,

Cov(S_d,S_(d-1)) = E[E[S_d | F_d] S_(d-1)'] = 0.

This is true componentwise across all twelve leaves. It does not assert
independence: shared volatility or other nonlinear dependence may remain.

## Required score-AR witness

A genuine daily score AR process is
U_d = rho U_(d-1) + sqrt(1-rho^2) Z_d,
with innovations independent of the preceding state and mean zero.
For any nondegenerate finite-variance stationary state,
E[U_d | U_(d-1)] = rho U_(d-1) and Gamma_1 = rho Gamma_0.
At rho=1/4 or rho=1/2 this conflicts with the inherited zero conditional
moment whenever Gamma_0 is nonzero. At Gamma_0=0 there is no nondegenerate
studentized size or power experiment.

Consequently a genuine daily SCORE AR025/AR050 is not a null DGP preserving
the frozen conditional null and past-training semantics. Centering its
unconditional mean does not restore its conditional null. MaxT resampling,
larger blocks, smaller nominal alpha, or studentization do not change this
logical compatibility gate.

## Separate marginal-law witness

Even ignoring the conditional-null conflict, the usual variance-normalized
linear AR recursion preserves a Gaussian marginal but not every inherited
innovation marginal. A variance-one t5 innovation has fourth moment 9 and
fourth cumulant 6. The stationary recursion has fourth moment
3 + 6*(1-rho^2)/(1+rho^2), hence 141/17 for rho=1/4 and 33/5 for rho=1/2,
not 9. This is a secondary exact witness; it is not an empirical simulation.
Other couplings can preserve selected marginals, but cannot overturn the
zero-lag-covariance consequence of the unchanged conditional null.

## Compositions examined, without selecting a replacement law

1. Filtering joint daily score innovations produces genuine score AR, but
   changes the conditional null and, generally, the marginal law. It also
   needs a separately governed treatment of masked days and stability/leaveout
   statistics; no such treatment is silently introduced here.
2. Carrying AR coefficients in X beta preserves the null. Their contribution
   cancels pathwise under Q_X and does not create the required score AR.
3. Multiplying independently centered daily scores by an AR multiplier can
   preserve conditional centering but gives zero adjacent-day score covariance
   when the daily innovations are independently centered. This is not score AR.
4. A marginal-preserving correlated-score copula may preserve marginals, but
   nonzero adjacent-day covariance still contradicts the conditional-null
   consequence above.

It is possible to define a separately labeled inference robustness perturbation
under a weaker unconditional score null. Such a sensitivity layer must not be
represented as certification under the inherited conditional null. Choosing
that distinction, or a different meaning of DAILY_AR, requires independent
governance. This task prohibits changing the frozen null or hiding ambiguity.

## Decision and limits

Fail the dual-layer compatibility gate before any stochastic worker, valid
trial manifest or execution authority can be certified. Preserve V6 numerical
support PASS. Classification:
PREOUTCOME_BLOCKED_DUAL_LAYER_DEPENDENCE_ARCHITECTURE_UNCERTIFIED_UNTESTED_NOT_NULL.
This is an architecture/contract blocker, not null, power, market or economic
evidence. No general impossibility of researching relational information is
claimed. The broader relational family and all untested universes remain open.
