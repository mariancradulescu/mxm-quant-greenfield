using System;
using System.Collections.Generic;

namespace Mxm.Replay {
/// <summary>
/// Serializes bar decisions within ONE cTrader Robot instance. Never represents
/// an inter-process, inter-instance, broker or Cloud-distributed mutex.
/// A closed bar for a symbol is consumed at most once, even after a reload.
/// </summary>
public sealed class MxmPortfolioSequencer {
 readonly HashSet<string> allowed;
 readonly Dictionary<string, DateTime> latest = new(StringComparer.OrdinalIgnoreCase);
 bool processing;
 public int SymbolCount => allowed.Count;
 // Adjacent bars in a reloaded platform array do not establish that this
 // instance processed the intervening callbacks. Sample our own accepted
 // predecessor atomically with consuming the next callback.
 public bool TryEnter(string symbol,DateTime closedBarOpen,int barMinutes,
  out bool processedContiguous,out string reason) {
  processedContiguous=false;
  if(barMinutes<1 || closedBarOpen.Kind!=DateTimeKind.Utc) {
   reason="INVALID_PROCESSED_BAR_CLOCK";return false;
  }
  bool adjacent=latest.TryGetValue(symbol,out var prior) &&
   closedBarOpen.Ticks-prior.Ticks==checked(TimeSpan.TicksPerMinute*(long)barMinutes);
  if(!TryEnter(symbol,closedBarOpen,out reason))return false;
  processedContiguous=adjacent;return true;
 }
 public MxmPortfolioSequencer(IEnumerable<string> symbols) {
  allowed = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
  foreach(var name in symbols) {
   if(string.IsNullOrWhiteSpace(name) || !allowed.Add(name.Trim()))
    throw new ArgumentException("INVALID_OR_DUPLICATE_PORTFOLIO_SYMBOL");
  }
  if(allowed.Count==0)throw new ArgumentException("EMPTY_PORTFOLIO");
 }
 public bool TryEnter(string symbol, DateTime closedBarOpen, out string reason) {
  reason="NONE";
  if(processing){reason="REENTRANT_OR_CONCURRENT_DECISION";return false;}
  if(!allowed.Contains(symbol)){reason="SYMBOL_NOT_REGISTERED";return false;}
  if(closedBarOpen==default){reason="MISSING_BAR_TIME";return false;}
  if(latest.TryGetValue(symbol,out var old) && closedBarOpen<=old){
   reason="DUPLICATE_OR_OUT_OF_ORDER_BAR";return false;
  }
  processing=true;
  // Consume BEFORE orders; a failed broker operation cannot replay the signal.
  latest[symbol]=closedBarOpen;
  return true;
 }
 public void Exit() {
  if(!processing)throw new InvalidOperationException("UNBALANCED_PORTFOLIO_EXIT");
  processing=false;
 }
}
}
