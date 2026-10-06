The completed diagnostic does not require any credentials. Machine-side authentication
has not been proven: Actions run 37455958290 found all four requested secret names empty.
No broker was contacted, no token was refreshed, and no market history was requested.

1. Use the existing approved application at https://openapi.ctrader.com/apps .
   If no valid accounts-only token remains, use its Playground, select **accounts**
   scope, and authorize the intended Pepperstone Europe LIVE account. Reject trading
   scope. Reauthorization is conditional on the absence/invalidity of an existing
   valid accounts-only token; empty repository secrets do not prove token invalidity.
2. At https://github.com/mariancradulescu/mxm-quant-greenfield/settings/secrets/actions ,
   enter repository Actions secrets directly:

   | Name | Value |
   | --- | --- |
   | CTRADER_CLIENT_ID | Approved application's Client ID |
   | CTRADER_CLIENT_SECRET | Same application's Client Secret |
   | CTRADER_REFRESH_TOKEN | Valid accounts-only refresh token |
   | CTRADER_EXPECTED_ACCOUNT_ID | Exact ctidTraderAccountId, not the trader login |
   | CTRADER_ACCESS_TOKEN | Access token from the same accounts-only authorization, for the tiny no-refresh proof |

   The first four names were checked and missing. The fifth is an additional temporary
   credential for a safe proof without consuming the refresh token; its presence was
   not checked this task. Do not paste any credential, OAuth code, or token into chat,
   files, commits, logs, or artifacts.
3. Say only that the secrets have been saved. The agent will create/push an exact
   hash-bound auth-only arm. Do not edit, start, or debug any workflow yourself.

The prepared preflight verifies ApplicationAuth, account list with explicit SCOPE_VIEW,
exact historical account fingerprint and LIVE status, AccountAuth, Pepperstone Europe,
HEDGED/MAX/non-swap-free state and EUR currency. It permits only five authentication
and account-metadata message types. It rejects trading scope before AccountAuth and
rejects every order, subscription, historical-data and refresh message path.

This task stops before that authenticated run because credentials are missing. No arm
has been created. The prepared workflow uses an access token only and cannot refresh
on an ephemeral hosted runner. Future unattended refresh remains locked until a durable
private checkpoint is provisioned and independently audited. The local checkpoint
adapter demonstrates 0700/0600 permissions, exclusive locking, fsync and atomic replace;
it does not claim distributed atomicity or solve a crash between server-side rotation
and private persistence. No extra private-storage infrastructure is required to perform
the tiny no-refresh proof using the access token above.

The final trading cBot will not depend on this research OAuth path or GitHub.
