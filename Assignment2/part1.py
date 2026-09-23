import argparse
import csv
import json
import math
import os
import platform
import random
import select
import socket
import statistics
import struct
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

PARAM_EXCHANGE=9; CREATE_STREAMS=10; TEST_START=1; TEST_RUNNING=2
TEST_END=4; EXCHANGE_RESULTS=13; DISPLAY_RESULTS=14; IPERF_DONE=16
ACCESS_DENIED=-1; SERVER_ERROR=-2; SERVER_TERMINATE=11
TCP_INFO=getattr(socket,'TCP_INFO',11)
# Linux include/uapi/linux/tcp.h: tcpi_bytes_acked is a native-endian u64 at offset 120.
BYTES_ACKED_OFFSET=120
FIELDS=['run_id','host','port','provider','country','algorithm','elapsed_s','interval_s',
        'bytes_acked','delta_bytes_acked','goodput_bps','goodput_mbps','bytes_sent',
        'snd_cwnd_segments','rtt_us','total_retrans','lost','snd_mss_bytes']

class ProtocolError(Exception): pass

@dataclass(frozen=True)
class Server:
    host: str
    port: int
    provider: str
    country: str


def load_servers(path, rng):
    with open(path,encoding='utf-8') as f: entries=json.load(f)
    if not isinstance(entries,list): raise ValueError('Server list must be a JSON array')
    candidates=[]; seen=set()
    for entry in entries:
        if not isinstance(entry,dict): continue
        host=str(entry.get('IP/HOST','')).strip()
        raw=str(entry.get('PORT','')).strip()
        if not host or not raw: continue
        try:
            if '-' in raw:
                a,b=map(int,raw.split('-',1))
                if not 1<=a<=b<=65535: continue
                ports=list(range(a,b+1)); rng.shuffle(ports)
            else:
                port=int(raw)
                if not 1<=port<=65535: continue
                ports=[port]
        except ValueError: continue
        # A range denotes alternative listener ports, not separate destinations.
        for port in ports:
            if (host,port) not in seen:
                candidates.append((Server(host,port,str(entry.get('PROVIDER','')),
                                          str(entry.get('COUNTRY',''))),host))
                seen.add((host,port))
    groups={}
    for server,host in candidates: groups.setdefault(host,[]).append(server)
    hosts=list(groups); rng.shuffle(hosts)
    return [groups[h] for h in hosts]


def recv_exact(sock,n):
    out=bytearray()
    while len(out)<n:
        chunk=sock.recv(n-len(out))
        if not chunk: raise ProtocolError(f'Unexpected EOF: needed {n}, got {len(out)}')
        out.extend(chunk)
    return bytes(out)


def send_json(sock,obj):
    payload=json.dumps(obj,separators=(',',':')).encode('utf-8')
    sock.sendall(struct.pack('!I',len(payload))+payload)


def recv_json(sock):
    size=struct.unpack('!I',recv_exact(sock,4))[0]
    if not 0<size<=16*1024*1024: raise ProtocolError(f'Invalid JSON length {size}')
    return json.loads(recv_exact(sock,size))


def read_state(sock):
    state=struct.unpack('b',recv_exact(sock,1))[0]
    if state==ACCESS_DENIED: raise ProtocolError('Server busy / access denied')
    if state==SERVER_TERMINATE: raise ProtocolError('Server terminated test')
    if state==SERVER_ERROR:
        err,unix=struct.unpack('!ii',recv_exact(sock,8))
        raise ProtocolError(f'iperf3 server error {err}, errno {unix}')
    return state


def expect(sock,expected):
    actual=read_state(sock)
    if actual!=expected: raise ProtocolError(f'Expected iperf3 state {expected}, got {actual}')


def tcp_stats(sock):
    raw=sock.getsockopt(socket.IPPROTO_TCP,TCP_INFO,256)
    if len(raw)<128: raise ProtocolError('Kernel TCP_INFO lacks tcpi_bytes_acked (requires >=128 bytes)')
    # First 8 bytes are u8 fields; subsequent values use native-endian layout.
    u32=lambda off:struct.unpack_from('=I',raw,off)[0]
    return dict(bytes_acked=struct.unpack_from('=Q',raw,BYTES_ACKED_OFFSET)[0],
                snd_mss_bytes=u32(16),lost=u32(32),total_retrans=u32(100),
                rtt_us=u32(68),snd_cwnd_segments=u32(80))


def run_test(server,duration,interval,timeout,block_size,output,run_id,algorithm=None):
    cookie=(uuid.uuid4().hex+'-'+uuid.uuid4().hex[:4]).encode('ascii')
    assert len(cookie)==37
    control=None; data=None; samples=[]; bytes_sent=0; result=None
    try:
        control=socket.create_connection((server.host,server.port),timeout=timeout)
        control.settimeout(timeout)
        control.sendall(cookie)
        expect(control,PARAM_EXCHANGE)
        send_json(control,{'tcp':True,'omit':0,'time':math.ceil(duration),
                           'parallel':1,'len':block_size,'client_version':'3.0'})
        expect(control,CREATE_STREAMS)
        data=socket.socket(control.family,socket.SOCK_STREAM)
        if algorithm:
            data.setsockopt(socket.IPPROTO_TCP,socket.TCP_CONGESTION,algorithm.encode())
        data.settimeout(timeout)
        data.connect(control.getpeername())
        data.sendall(cookie)
        actual_algo=data.getsockopt(socket.IPPROTO_TCP,socket.TCP_CONGESTION,64).split(b'\0')[0].decode()
        expect(control,TEST_START)
        expect(control,TEST_RUNNING)
        data.setblocking(False)
        payload=os.urandom(block_size)
        start=time.monotonic(); last_t=start; last_ack=tcp_stats(data)['bytes_acked']
        next_sample=start+interval; end=start+duration
        pending=memoryview(payload)
        def sample(now):
            nonlocal last_t,last_ack,next_sample
            stats=tcp_stats(data)
            dt=now-last_t; delta=max(0,stats['bytes_acked']-last_ack)
            row=dict(run_id=run_id,host=server.host,port=server.port,
                     provider=server.provider,country=server.country,algorithm=actual_algo,
                     elapsed_s=now-start,interval_s=dt,bytes_acked=stats['bytes_acked'],
                     delta_bytes_acked=delta,goodput_bps=delta*8/dt if dt>0 else 0,
                     goodput_mbps=delta*8/dt/1e6 if dt>0 else 0,
                     bytes_sent=bytes_sent,**{k:v for k,v in stats.items() if k!='bytes_acked'})
            samples.append(row); last_t=now; last_ack=stats['bytes_acked']
            next_sample+=interval
        while True:
            now=time.monotonic()
            if now>=end: break
            if now>=next_sample:
                sample(now); continue
            readable,writable,_=select.select([control],[data],[],min(next_sample,end)-now)
            if readable:
                state=read_state(control)
                raise ProtocolError(f'Server ended test during transmission (state {state})')
            if writable:
                try:
                    count=data.send(pending)
                    if count==0: raise ProtocolError('Data connection closed during send')
                    bytes_sent+=count; pending=pending[count:]
                    if not pending: pending=memoryview(payload)
                except (BlockingIOError,InterruptedError): pass
        now=time.monotonic()
        if now>last_t: sample(now)
        # TEST_END is a control message; keep the data socket open until results exchange.
        control.sendall(struct.pack('b',TEST_END))
        expect(control,EXCHANGE_RESULTS)
        # Sender-side results structure expected by iperf3's JSON exchange.
        stream={'id':1,'bytes':bytes_sent,'retransmits':tcp_stats(data)['total_retrans'],
                'jitter':0,'errors':0,'packets':0}
        send_json(control,{'cpu_util_total':0.0,'cpu_util_user':0.0,'cpu_util_system':0.0,
                           'sender_has_retransmits':1,'congestion_used':actual_algo,
                           'streams':[stream]})
        result=recv_json(control)
        expect(control,DISPLAY_RESULTS)
        control.sendall(struct.pack('b',IPERF_DONE))
        return samples,bytes_sent,actual_algo,result
    finally:
        if data: data.close()
        if control: control.close()


def write_csv(path,rows,fields):
    with open(path,'w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def plot_samples(runs,outdir):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(outdir/'goodput.pdf') as pdf:
        for run in runs:
            if not run['trace']: continue
            fig,ax=plt.subplots(figsize=(9,4))
            ax.plot([x['elapsed_s'] for x in run['trace']],
                    [x['goodput_mbps'] for x in run['trace']],marker='.',markersize=3)
            ax.set(title=f"{run['host']}:{run['port']} — {run['algorithm']} ({run['run_id']})",
                   xlabel='Elapsed time (s)',ylabel='Acknowledged goodput (Mbit/s)')
            ax.set_ylim(bottom=0);ax.grid(alpha=.3);fig.tight_layout();pdf.savefig(fig);plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--servers',type=Path,default=Path('data/listed_iperf3_servers.json'))
    p.add_argument('-n','--destinations',type=int,default=10)
    p.add_argument('-d','--duration',type=float,default=60)
    p.add_argument('-i','--interval',type=float,default=1)
    p.add_argument('--timeout',type=float,default=8)
    p.add_argument('--max-attempts',type=int,default=30)
    p.add_argument('--block-size',type=int,default=131072)
    p.add_argument('--algorithm',default=None,help='Optional TCP congestion control algorithm')
    p.add_argument('--seed',type=int,default=None)
    p.add_argument('--output',type=Path,default=Path('results/part1'))
    args=p.parse_args()
    if args.destinations<1 or args.duration<=0 or args.interval<=0 or args.timeout<=0 or args.max_attempts<1 or not 1<=args.block_size<=1024*1024:
        p.error('Invalid positive numeric argument or block size')
    if not hasattr(socket,'TCP_CONGESTION') or platform.system()!='Linux': p.error('Linux TCP_INFO/TCP_CONGESTION required')
    args.output.mkdir(parents=True,exist_ok=True)
    groups=load_servers(args.servers,random.Random(args.seed))
    if not groups: p.error('No valid server entries')
    successes=[]; failures=[]; summaries=[]; attempted=0
    for group in groups:
        if len(successes)>=args.destinations or attempted>=args.max_attempts: break
        for server in group:
            if attempted>=args.max_attempts: break
            attempted+=1; run_id=uuid.uuid4().hex[:12]
            print(f'[{attempted}/{args.max_attempts}] {server.host}:{server.port}',flush=True)
            try:
                rows,sent,algo,server_result=run_test(server,args.duration,args.interval,args.timeout,
                                                       args.block_size,args.output,run_id,args.algorithm)
                if not rows: raise ProtocolError('No samples obtained')
                speeds=[r['goodput_mbps'] for r in rows]
                summary=dict(run_id=run_id,host=server.host,port=server.port,provider=server.provider,
                             country=server.country,algorithm=algo,samples=len(rows),bytes_sent=sent,
                             min_mbps=min(speeds),median_mbps=statistics.median(speeds),
                             mean_mbps=statistics.mean(speeds),p95_mbps=sorted(speeds)[min(len(speeds)-1,math.ceil(.95*len(speeds))-1)])
                write_csv(args.output/f'{run_id}_samples.csv',rows,FIELDS)
                (args.output/f'{run_id}_server_results.json').write_text(json.dumps(server_result,indent=2))
                summaries.append(summary);successes.append(dict(**summary,trace=rows))
                print(f"  OK {summary['mean_mbps']:.2f} Mbit/s",flush=True)
                break
            except (OSError,ProtocolError,ValueError,UnicodeError,json.JSONDecodeError) as e:
                failure=dict(run_id=run_id,host=server.host,port=server.port,error=f'{type(e).__name__}: {e}')
                failures.append(failure);print(f"  FAILED {failure['error']}",flush=True)
    write_csv(args.output/'summary.csv',summaries,['run_id','host','port','provider','country','algorithm','samples','bytes_sent','min_mbps','median_mbps','mean_mbps','p95_mbps'])
    write_csv(args.output/'failures.csv',failures,['run_id','host','port','error'])
    (args.output/'manifest.json').write_text(json.dumps(dict(requested=args.destinations,completed=len(successes),
        shortfall=args.destinations-len(successes),attempts=attempted,seed=args.seed,
        duration_s=args.duration,interval_s=args.interval,kernel=platform.release(),
        selected=[{'host':x['host'],'port':x['port']} for x in successes]),indent=2))
    if successes: plot_samples(successes,args.output)
    print(f'Completed {len(successes)}/{args.destinations}; attempts={attempted}; output={args.output}')
    return 0 if len(successes)==args.destinations else 1

if __name__=='__main__': raise SystemExit(main())
