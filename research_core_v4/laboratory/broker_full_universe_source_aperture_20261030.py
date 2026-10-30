"""Reproduce 5,324-symbol 22-Sept Pepperstone Europe EUR200 access/margin
aggregates from the owner's existing authenticated PRIVATE broker ZIP.
No price/outcome data, forecast, execution, external sources or credentials.
A snapshot margin is never proof of historical or future order admission.
"""
import argparse,collections,hashlib,json,pathlib,zipfile,math
SHA="9553fd3b60f4f5dc8428c30d19cde7d7a13cad12de18a27a93785836e97f5f77"
def evaluate(path:pathlib.Path):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=SHA:raise ValueError("CAPTURE_SHA256_MISMATCH")
    with zipfile.ZipFile(path) as z:
        names=[x for x in z.namelist() if x.endswith("/BROKER_NATIVE_COMPETITION_UNIVERSE_CAPTURE_V2.json")]
        if len(names)!=1:raise ValueError("BROKER_NATIVE_MEMBER_NOT_UNIQUE")
        source=json.loads(z.read(names[0]))
    rows=source["symbols"]
    if (source["account_currency"]!="EUR" or source["starting_capital_eur"]!=200 or
        len(rows)!=5324 or source["current_new_entry_accessible_count"]!=1690):
        raise ValueError("WRONG_ACCOUNT_ROSTER")
    categories=collections.defaultdict(lambda:collections.Counter())
    identities=set();direction=collections.Counter()
    for row in rows:
        ident=int(row["symbol_id"])
        if ident in identities:raise ValueError("DUPLICATED_IDENTITY")
        identities.add(ident)
        if not(row["buy_eligible_current"] or row["sell_eligible_current"]):continue
        m=row["expected_margin_at_min_volume"]
        low=int(row["min_volume_cents"]);step=int(row["step_volume_cents"])
        high=int(row["max_volume_cents"])
        if (low<=0 or step<=0 or high<low or low%step!=0 or
            m["state"]!="CAPTURED_BROKER_NATIVE_READ_ONLY_CURRENT" or
            int(m["volume_cents"])!=low):raise ValueError("UNVERIFIED_NATIVE_MINIMUM_VOLUME")
        buy=float(m["buy_margin_eur"]);sell=float(m["sell_margin_eur"])
        if not math.isfinite(buy) or not math.isfinite(sell) or buy<0 or sell<0:
            raise ValueError("BAD_NATIVE_MARGIN")
        bok=bool(row["buy_eligible_current"]) and m["buy_feasibility"]=="EUR200_MIN_VOLUME_FEASIBLE"
        sok=bool(row["sell_eligible_current"]) and m["sell_feasibility"]=="EUR200_MIN_VOLUME_FEASIBLE"
        entry=categories[row["asset_class"]]
        entry["accessible"]+=1;entry["buy"]+=int(bok);entry["sell"]+=int(sok)
        entry["both"]+=int(bok and sok)
        entry["both_under_80eur_margin"]+=int(bok and sok and 0<buy<=80 and 0<sell<=80)
        entry["both_under_40eur_margin"]+=int(bok and sok and 0<buy<=40 and 0<sell<=40)
        direction["both" if bok and sok else "buy_only" if bok else "sell_only" if sok else "neither"]+=1
    if(len(identities)!=5324 or sum(v["accessible"] for v in categories.values())!=1690 or
       direction!={"both":1609,"buy_only":40,"neither":41} or len(categories)!=31 or
       sum(v["both_under_80eur_margin"] for v in categories.values())!=1563 or
       sum(v["both_under_40eur_margin"] for v in categories.values())!=1491):
        raise ValueError("FULL_UNIVERSE_RECONCILIATION_MISMATCH")
    return {
      "schema":"mxm.full-5324-broker-EUR200-native-min-volume-envelope.v1",
      "broker_zip_sha256":SHA,"captured_utc":source["captured_utc"],
      "source_total_symbol_identities":5324,"accessible_symbol_identities":1690,
      "accessible_asset_classes":len(categories),
      "buy_and_sell_necessary_margin_200eur":direction["both"],
      "buy_only_necessary_margin_200eur":direction["buy_only"],
      "neither_direction_necessary_margin_200eur":direction["neither"],
      "both_within_existing_director_80eur_ticket_cap":1563,
      "both_within_40eur_ticket_margin_illustrative":1491,
      "by_asset_class":{k:dict(v) for k,v in sorted(categories.items())},
      "interpretation":"Read-only current margin and broker minimum-volume feasibility; NOT historic costs, historical source joining, NET advantage, EUR200 funded execution or HARD21.",
      "separate_historical_corpora":"1576 M5 source and 145 annual PRIMARY145 are DISTINCT coverage populations; do not claim this report joins their return outcomes",
      "excluded_research_universe":False,
      "orders":0,"new_broker_requests":0,"cloud_activations":0
    }
def main():
    p=argparse.ArgumentParser();p.add_argument("action",choices=["selftest","evaluate"])
    p.add_argument("--broker-zip",type=pathlib.Path);p.add_argument("--output",type=pathlib.Path)
    a=p.parse_args();assert len(SHA)==64
    if a.action=="selftest":print("BROKER_5324_SOURCE_BLIND_SELFTEST_PASS");return
    if not a.broker_zip or not a.output:raise ValueError("EXPLICIT_PRIVATE_SOURCE_AND_OUTPUT_REQUIRED")
    result=evaluate(a.broker_zip);a.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in ("source_total_symbol_identities","accessible_symbol_identities","accessible_asset_classes","buy_and_sell_necessary_margin_200eur","both_within_existing_director_80eur_ticket_cap")},sort_keys=True))
if __name__=="__main__":main()
