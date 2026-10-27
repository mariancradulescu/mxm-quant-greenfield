"""Prospective sequence/state protocol; artificial source only, independent oracle."""
import json,os,random,shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PROJECT=ROOT/'research_core_v4/laboratory/csharp/sequenced_depth/MxmSequencedDepth.csproj'
def entry(i,side,price,size=10):return dict(Id=i,Side=side,Price=price,Size=size)
def new(i,side,price,size=10):return dict(Action=0,Id=i,Side=side,Price=price,Size=size)
def delete(i):return dict(Action=2,Id=i)
def begin(t=0,seq=0):return dict(op='begin',now=t,seq=seq)
def snapshot(seq,t,*entries,**kw):return dict(op='snapshot',seq=seq,now=t,symbol=kw.get('symbol',1),entries=list(entries))
def delta(seq,t,*updates,**kw):return dict(op='delta',seq=seq,now=t,symbol=kw.get('symbol',1),updates=list(updates))
def read(t):return dict(op='read',now=t)
def oracle(actions):
    levels={};epoch=seq=0;ready=fault=clock_fault=session=False;last=booktime=sent=None;out=[]
    def identity(i):return isinstance(i,str) and bool(i.strip()) and len(i)<=128
    for a in actions:
        t=a['now'];op=a['op']
        try:
            if clock_fault or t<0 or last is not None and t<last:
                clock_fault=True;raise ValueError()
            last=t
            if op=='begin':
                if not 0<=a['seq']<2**63-1:raise ValueError()
                levels={};booktime=sent=None;ready=False;epoch+=1;seq=a['seq'];fault=False;session=True
            elif op=='end':session=False;levels={};booktime=sent=None;ready=False
            elif op=='read':
                bids=[(e,t0) for e,t0 in levels.values() if e['Side']==1];asks=[(e,t0) for e,t0 in levels.values() if e['Side']==-1]
                bid=max((e['Price'] for e,_ in bids),default=None);ask=min((e['Price'] for e,_ in asks),default=None)
                def at(items,p):
                    found=[(e,t0) for e,t0 in items if e['Price']==p]
                    return (sum(e['Size'] for e,_ in found),min(t0 for _,t0 in found)) if found else (None,None)
                bs,bt=at(bids,bid);ass,atime=at(asks,ask)
                shape='Missing' if bid is None or ask is None else 'Crossed' if bid>ask else 'Locked' if bid==ask else 'Positive'
                out.append(dict(status='VIEW',view=dict(Epoch=epoch,Sequence=seq,Ready=ready and not fault,Faulted=fault,Bid=bid,Ask=ask,DisplayedBidSize=bs,DisplayedAskSize=ass,BidEntryObservedMs=bt,AskEntryObservedMs=atime,LastBookMessageMs=booktime,LastSendingUtcMs=sent,Shape=shape,Entries=len(levels),ExecutabilityProven=False,ContinuousObservationProven=False,SourceAuthenticationProven=False)))
            else:
                if not session or fault or a['seq']!=seq+1 or a.get('sent') is not None and a['sent']<0:raise ValueError()
                seq=a['seq']
                if op=='advance':continue
                if a['symbol']!=1:raise ValueError()
                if op=='snapshot':
                    candidate={}
                    for e in a['entries']:
                        if not identity(e['Id']) or e['Id'] in candidate or e['Side'] not in (1,-1) or e['Price']<=0 or e['Size']<=0:raise ValueError()
                        candidate[e['Id']]=(dict(e),t)
                elif op=='delta':
                    if not ready:raise ValueError()
                    candidate=dict(levels)
                    for u in a['updates']:
                        i=u['Id']
                        if not identity(i):raise ValueError()
                        if u['Action']==2:
                            if i not in candidate or u.get('Side') is not None and u['Side']!=candidate[i][0]['Side'] or u.get('Price') is not None or u.get('Size') is not None:raise ValueError()
                            del candidate[i]
                        elif u['Action']==0:
                            if i in candidate or u.get('Side') not in (1,-1) or u.get('Price') is None or u.get('Size') is None or u['Price']<=0 or u['Size']<=0:raise ValueError()
                            candidate[i]=({k:u[k] for k in ('Id','Side','Price','Size')},t)
                        else:raise ValueError()
                else:raise ValueError()
                if len(candidate)>10000:raise ValueError()
                levels=candidate;ready=True;booktime=t;sent=a.get('sent')
        except ValueError:
            fault=True;levels={};ready=False;booktime=sent=None;out.append(dict(status='HOLD'))
    return out
class CompiledDepth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('dotnet'):
            if os.environ.get('GITHUB_ACTIONS')=='true':raise RuntimeError('Required compiled sequenced depth unavailable')
            raise unittest.SkipTest('Production CSharp compilation required in CI')
    def check(self,actions):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'input').write_text(json.dumps(actions))
            subprocess.run(['dotnet','run','--no-build','-c','Release','--project',str(PROJECT),'--',str(p/'input'),str(p/'output')],check=True,capture_output=True,text=True)
            out=json.loads((p/'output').read_text());self.assertEqual(out,oracle(actions));return out
    def test_whole_message_bbo_and_delete_reveals_old_entry_without_new_observation(self):
        out=self.check([begin(),snapshot(1,1,entry('b',1,99),entry('a',-1,101),entry('old',1,98)),delta(2,2,delete('b'),new('ask2',-1,100)),read(2)])[-1]['view']
        self.assertEqual((out['Bid'],out['Ask'],out['BidEntryObservedMs'],out['AskEntryObservedMs']),(98,100,1,2))
    def test_heartbeat_and_silence_do_not_refresh_book_or_entry_observation(self):
        out=self.check([begin(),snapshot(1,1,entry('b',1,99),entry('a',-1,101)),dict(op='advance',seq=2,now=2),read(999999)])[-1]['view']
        self.assertEqual((out['LastBookMessageMs'],out['BidEntryObservedMs']),(1,1));self.assertFalse(out['ContinuousObservationProven'])
    def test_gap_duplicate_and_unknown_delete_erase_book_and_hold_until_new_verified_session(self):
        for bad in (delta(3,2,delete('b')),delta(1,2,delete('b')),delta(2,2,delete('unknown'))):
            out=self.check([begin(),snapshot(1,1,entry('b',1,99),entry('a',-1,101)),bad,read(3),snapshot(4,4,entry('b',1,99)),begin(5,7),snapshot(8,6,entry('b',1,99)),read(6)])
            self.assertTrue(out[1]['view']['Faulted']);self.assertEqual(out[1]['view']['Entries'],0);self.assertTrue(out[-1]['view']['Ready'])
    def test_invalid_suffix_never_publishes_a_valid_prefix(self):
        out=self.check([begin(),snapshot(1,1,entry('b',1,99)),delta(2,2,new('a',-1,101),delete('unknown')),read(3)])
        self.assertEqual(out[-1]['view']['Entries'],0)
    def test_snapshot_replaces_entire_book_and_empty_is_not_fill_or_liquidity_proof(self):
        out=self.check([begin(),snapshot(1,1,entry('b',1,99)),snapshot(2,2),read(2)])[-1]['view']
        self.assertTrue(out['Ready']);self.assertEqual(out['Shape'],'Missing');self.assertFalse(out['ExecutabilityProven'])
    def test_missing_snapshot_wrong_symbol_and_unsupported_amend_hold(self):
        for a in ([begin(),delta(1,1,new('b',1,99)),read(2)], [begin(),snapshot(1,1,entry('b',1,99),symbol=2),read(2)], [begin(),snapshot(1,1,entry('b',1,99)),delta(2,2,dict(Action=1,Id='b',Price=100)),read(2)]):
            self.assertTrue(self.check(a)[-1]['view']['Faulted'])
    def test_duplicate_ids_size_price_and_clock_failures(self):
        for entries in ((entry('b',1,99),entry('b',-1,101)),(entry('b',1,0),),(entry('b',1,99,0),)):
            self.check([begin(),snapshot(1,1,*entries),read(2)])
        self.check([begin(2),read(1),begin(3),read(3)])
    def test_multiple_entries_at_best_are_displayed_size_not_executable_size(self):
        out=self.check([begin(),snapshot(1,1,entry('a',1,100,10),entry('b',1,100,20),entry('c',-1,100,2)),read(1)])[-1]['view']
        self.assertEqual(out['DisplayedBidSize'],30);self.assertEqual(out['Shape'],'Locked');self.assertFalse(out['ExecutabilityProven'])
    def test_every_server_message_counts_and_source_time_is_separate(self):
        a=snapshot(5,100,entry('b',1,99),entry('a',-1,101));a['sent']=1000000
        out=self.check([begin(0,2),dict(op='advance',seq=3,now=1),dict(op='advance',seq=4,now=2),a,read(100)])[-1]['view']
        self.assertEqual((out['LastBookMessageMs'],out['LastSendingUtcMs']),(100,1000000))
    def test_deterministic_complete_message_paths_independent_reference(self):
        rng=random.Random(223);a=[begin()];seq=0;t=0
        for i in range(250):
            t+=rng.choice((0,1,10000));seq+=1
            if i%17==0:a.append(snapshot(seq,t,entry('b',1,99),entry('a',-1,101)))
            elif i%3==0:a.append(dict(op='advance',seq=seq,now=t))
            else:a.append(delta(seq,t,new(str(i),rng.choice((1,-1)),rng.randrange(95,105))))
            a.append(read(t))
        self.check(a)
class Boundaries(unittest.TestCase):
    def test_shared_product_compiles_receiver_component_but_does_not_subscribe_or_promote_it(self):
        b=ROOT/'research_core_v4/native_tick_replay_v1/csharp';p=(b/'MxmReferenceBot.csproj').read_text();bot=(b/'MxmReferenceProductBot.cs').read_text()
        self.assertIn('MxmSequencedDepthBook.cs',p);self.assertNotIn('new MxmSequencedDepthBook',bot)
        source=(b/'MxmSequencedDepthBook.cs').read_text()
        self.assertNotIn('ExecuteMarketOrder',source);self.assertNotIn('TcpClient',source)
if __name__=='__main__':unittest.main()
