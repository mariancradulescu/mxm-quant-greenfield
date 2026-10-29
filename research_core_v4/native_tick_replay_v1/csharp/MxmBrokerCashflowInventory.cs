using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Mxm.Replay {
/// <summary>
/// Original cTrader account transaction facts. This is a read-only, restart-
/// reconstructible view, NOT a durable command journal, original EUR200 anchor,
/// proof that the native Transactions collection is complete, or permission to trade.
/// A deposit/withdrawal changes capital, never strategy profit.
/// </summary>
public sealed record MxmBrokerCashflowFact(long Id, DateTime TimeUtc,
 string Kind, decimal RawAmountEur, decimal BalanceAfterEur);
public sealed class MxmBrokerCashflowInventory {
 readonly MxmBrokerCashflowFact[] facts;
 public MxmBrokerCashflowFact[] Facts=>facts.ToArray();
 public string ScopeFingerprint {get;}
 public string FactsSha256 {get;}
 public DateTime ObservedUtc {get;}
 public decimal ObservedDepositsEur {get;}
 public decimal ObservedWithdrawalsEur {get;}
 public decimal ObservedNetExternalFlowEur=>ObservedDepositsEur-ObservedWithdrawalsEur;
 // The native API describes transactions, not a complete original-capital
 // anchor, atomic history watermark or all account-originating cash movements.
 public bool FullHistoryCoverageProven=>false;
 public bool OriginalCapitalAnchorProven=>false;
 public bool CashflowNeutralStrategyNavProven=>false;
 public bool CanAuthorizeOrders=>false;
 static bool Utc(DateTime t)=>t.Kind==DateTimeKind.Utc && t!=default;
 static void Need(bool ok) {
  if(!ok)throw new ArgumentException("BROKER_CASHFLOW_FACTS_INVALID_OR_CONFLICTING");
 }
 static string Hash(string s)=>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(s))).ToLowerInvariant();
 public MxmBrokerCashflowInventory(string accountScope,string accountCurrency,
  DateTime observedUtc,IEnumerable<MxmBrokerCashflowFact> observations) {
  Need(!string.IsNullOrWhiteSpace(accountScope) && accountScope.Length<=1024 &&
   string.Equals(accountCurrency,"EUR",StringComparison.OrdinalIgnoreCase) &&
   Utc(observedUtc) && observations!=null);
  ScopeFingerprint=Hash(accountScope);ObservedUtc=observedUtc;
  var byId=new Dictionary<long,MxmBrokerCashflowFact>();
  foreach(var item in observations) {
   if(item is null)throw new ArgumentException("BROKER_CASHFLOW_NULL_FACT");
   Need(byId.Count<100000 && item.Id>0 &&
    Utc(item.TimeUtc) && item.TimeUtc<=observedUtc &&
    (item.Kind=="Deposit" || item.Kind=="Withdrawal") &&
    item.RawAmountEur!=0m);
   if(byId.TryGetValue(item.Id,out var earlier))Need(earlier==item);
   else byId.Add(item.Id,item);
  }
  facts=byId.Values.OrderBy(x=>x.TimeUtc).ThenBy(x=>x.Id).ToArray();
  decimal deposits=0m,withdrawals=0m;
  try {checked {
   foreach(var item in facts) {
    // The native API's Type is authoritative for direction. The magnitude
    // may have either sign in the API; never treat the sign as trade PnL.
    if(item.Kind=="Deposit")deposits+=Math.Abs(item.RawAmountEur);
    else withdrawals+=Math.Abs(item.RawAmountEur);
   }
   _=deposits-withdrawals;
  }} catch(OverflowException) {
   throw new ArgumentException("BROKER_CASHFLOW_TOTAL_OVERFLOW");
  }
  ObservedDepositsEur=deposits;ObservedWithdrawalsEur=withdrawals;
  // No account number or transaction notes leave this local calculation.
  FactsSha256=Hash(JsonSerializer.Serialize(new {
   scope=ScopeFingerprint,currency="EUR",facts
  }));
 }
}
}
