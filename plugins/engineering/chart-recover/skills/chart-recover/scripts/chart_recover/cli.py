import argparse
import json
from pathlib import Path


def positive_int(value):
    number=int(value)
    if number<=0:raise argparse.ArgumentTypeError('must be a positive integer')
    return number


def main():
    p=argparse.ArgumentParser(description='Recover chart geometry and calibrate it with public evidence.')
    sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('analyze');a.add_argument('image');a.add_argument('--config');a.add_argument('--out',default='artifacts/analysis')
    au=sub.add_parser('auto',help='Detect one bar card and read nearby labels without manual ROI or numeric anchors')
    au.add_argument('image');au.add_argument('--scale',choices=['unknown','linear','log'],default='unknown');au.add_argument('--source');au.add_argument('--out',default='artifacts/auto')
    for command in ('recover','calendar','ticks'):
        rc=sub.add_parser(command,help={'recover':'Run all automatic image readers','calendar':'Read a daily calendar and calibrate a corresponding curve','ticks':'Read a numeric Y axis and its local curve'}[command])
        rc.add_argument('image');rc.add_argument('--source');rc.add_argument('--out',default=f'artifacts/{command}')
        rc.add_argument('--scale',choices=['unknown','linear','log'],default='unknown')
        rc.add_argument('--assume-shared-daily-revenue',action='store_true');rc.add_argument('--assume-full-month',action='store_true')
    rb=sub.add_parser('recover-batch',help='Run all automatic readers on every collected image')
    rb.add_argument('manifest');rb.add_argument('--out',default='artifacts/recovery-batch');rb.add_argument('--configs');rb.add_argument('--scale',choices=['unknown','linear','log'],default='unknown')
    ag=sub.add_parser('agent',help='Run automatic readers, then test explicitly conditional evidence associations')
    ag.add_argument('image');ag.add_argument('--out',default='artifacts/agent');ag.add_argument('--source');ag.add_argument('--strict-only',action='store_true')
    ag.add_argument('--profile-url',help='Linked public TrustMRR profile to test as external daily-revenue evidence')
    ag.add_argument('--profile-snapshot',help='Replay a saved public Markdown profile instead of fetching it; requires --profile-url')
    ag.add_argument('--discover-evidence',action='store_true',help='Find public profile hypotheses from source links or the bounded public startup catalog')
    ag.add_argument('--evidence-cache',help='Discover evidence offline from a cache containing discovery.json and profiles/<slug>.md')
    ab=sub.add_parser('agent-batch',help='Investigate every collected image, retaining strict and conditional candidates separately')
    ab.add_argument('manifest');ab.add_argument('--out',default='artifacts/agent-batch');ab.add_argument('--strict-only',action='store_true')
    ab.add_argument('--discover-evidence',action='store_true');ab.add_argument('--evidence-cache')
    b=sub.add_parser('benchmark');b.add_argument('--out',default='artifacts/heldout');b.add_argument('--per-kind',type=positive_int,default=20);b.add_argument('--seed',type=int,default=9000)
    g=sub.add_parser('generate');g.add_argument('--out',default='examples/generated');g.add_argument('--seed',type=int,default=42);g.add_argument('--kind',choices=['bar','barh','line','area','scatter','grouped_bar','stacked_bar','stacked_area'],default='bar');g.add_argument('--scale',choices=['linear','log'],default='linear')
    c=sub.add_parser('collect');c.add_argument('--query');c.add_argument('--url');c.add_argument('--public',action='store_true',help='Read public URL metadata without an API token');c.add_argument('--import-jsonl');c.add_argument('--pages',type=int,default=1);c.add_argument('--out',default='data/collected');c.add_argument('--no-download',action='store_true')
    i=sub.add_parser('investigate');i.add_argument('image');i.add_argument('--config',required=True);i.add_argument('--out',default='artifacts/investigation')
    ba=sub.add_parser('batch');ba.add_argument('manifest');ba.add_argument('--configs');ba.add_argument('--out',default='artifacts/batch')
    ba.add_argument('--auto',action='store_true',help='Try automatic bar-card layout and label reading on every image')
    ba.add_argument('--scale',choices=['unknown','linear','log'],default='unknown')
    s=sub.add_parser('serve');s.add_argument('--port',type=int,default=8765)
    d=sub.add_parser('discover');d.add_argument('--limit',type=int,default=10);d.add_argument('--out',default='data/discovered');d.add_argument('--no-download',action='store_true')
    d.add_argument('--recover',action='store_true',help='Run automatic recovery on collected images after discovery')
    d.add_argument('--agent',action='store_true',help='Run the full investigation agent on collected images')
    d.add_argument('--discover-evidence',action='store_true',help='Enable bounded external source discovery in --agent mode')
    d.add_argument('--evidence-cache',help='Use cached external evidence in --agent mode; post collection still uses the network')
    d.add_argument('--strict-only',action='store_true')
    d.add_argument('--scale',choices=['unknown','linear','log'],default='unknown')
    args=p.parse_args()
    if args.command=='agent':
        from .agent import investigate_image
        if args.profile_snapshot and not args.profile_url:p.error('--profile-snapshot requires --profile-url')
        if args.profile_url and (args.discover_evidence or args.evidence_cache):p.error('Choose a supplied profile URL or automatic evidence discovery')
        print(json.dumps(investigate_image(args.image,dict(source=args.source,evidence_profile_url=args.profile_url,
                         evidence_profile_snapshot=args.profile_snapshot,discover_evidence=args.discover_evidence,
                         evidence_cache=args.evidence_cache),args.out,args.strict_only),indent=2))
    elif args.command=='agent-batch':
        from .agent import investigate_batch
        print(json.dumps(investigate_batch(args.manifest,args.out,args.strict_only,args.discover_evidence,args.evidence_cache),indent=2))
    elif args.command in ('recover','calendar','ticks'):
        config=dict(source=args.source,scale=args.scale,assume_shared_daily_revenue=args.assume_shared_daily_revenue,assume_full_month=args.assume_full_month)
        if args.command=='recover':
            from .automatic import recover
            r=recover(args.image,config,args.out)
            print(json.dumps(r,indent=2))
        elif args.command=='ticks':
            from .tick_recovery import analyze_ticks
            r=analyze_ticks(args.image,config,args.out)
            print(json.dumps(dict(status=r['status'],axes=len(r['binding']['axes']),outcomes=[c['status'] for c in r['recovery']],correspondence=r['correspondence'],output=args.out),indent=2))
        else:
            from .calendar_recovery import analyze_calendar
            r=analyze_calendar(args.image,config,args.out)
            print(json.dumps(dict(status=r['status'],calendar_observations=len(r['calendar']['observations']),outcomes=[c['status'] for c in r['recovery']],correspondence=r['correspondence'],output=args.out),indent=2))
    elif args.command=='recover-batch':
        from .automatic import recover_batch
        configs=json.loads(Path(args.configs).read_text(encoding="utf-8")) if args.configs else {}
        print(json.dumps(recover_batch(args.manifest,args.out,configs,defaults=dict(scale=args.scale)),indent=2))
    elif args.command=='auto':
        from .pipeline import analyze
        r=analyze(args.image,dict(auto_layout=True,scale=args.scale,post_url=args.source),args.out)
        print(json.dumps({'status':r['status'],'series':[x['status'] for x in r['recovery']],
                          'automatic_anchors':len(r['visual_evidence']['binding']['anchors']),'output':args.out},indent=2))
    elif args.command=='analyze':
        from .pipeline import analyze
        config=json.loads(Path(args.config).read_text(encoding="utf-8")) if args.config else {}
        r=analyze(args.image,config,args.out);print(json.dumps({'status':r['status'],'series':[x['status'] for x in r['recovery']],'output':args.out},indent=2))
    elif args.command=='benchmark':
        from .benchmark import run_benchmark
        print(json.dumps(run_benchmark(args.out,args.per_kind,args.seed),indent=2))
    elif args.command=='generate':
        from .synthetic import generate_one
        generate_one(args.out,args.seed,args.kind,args.scale);print(args.out)
    elif args.command=='collect':
        from .collect import XCollector,PublicXCollector,save_posts
        if sum(bool(x) for x in (args.query,args.url,args.import_jsonl))!=1:p.error('Choose exactly one of --query, --url, --import-jsonl')
        if args.public and not args.url:p.error('--public requires --url')
        if args.import_jsonl:posts=[json.loads(l) for l in Path(args.import_jsonl).read_text(encoding="utf-8").splitlines() if l.strip()]
        elif args.query:posts=XCollector().search(args.query,args.pages)
        else:posts=(PublicXCollector() if args.public else XCollector()).lookup(args.url)
        print(json.dumps(save_posts(posts,args.out,not args.no_download),indent=2))
    elif args.command=='investigate':
        from .investigate import investigate
        print(json.dumps(investigate(args.image,json.loads(Path(args.config).read_text(encoding="utf-8")),args.out),indent=2))
    elif args.command=='batch':
        from .investigate import batch
        configs=json.loads(Path(args.configs).read_text(encoding="utf-8")) if args.configs else {}
        defaults=dict(auto_layout=True,scale=args.scale) if args.auto else dict(scale=args.scale)
        print(json.dumps(batch(args.manifest,args.out,configs,defaults=defaults),indent=2))
    elif args.command=='discover':
        from .discovery import discover
        if args.agent and args.recover:p.error('Choose --agent or --recover')
        if (args.agent or args.recover) and args.no_download:p.error('Investigation needs image downloads; remove --no-download')
        if (args.discover_evidence or args.evidence_cache or args.strict_only) and not args.agent:p.error('External evidence and strict policy require --agent')
        if args.agent and args.scale!='unknown':p.error('--agent infers scale; --scale is only available with --recover')
        result=discover(args.out,args.limit,download=not args.no_download)
        if args.recover:
            from .automatic import recover_batch
            manifest=Path(args.out)/'posts.jsonl'
            result['recovery']=recover_batch(manifest,Path(args.out)/'recovery',defaults=dict(scale=args.scale)) if manifest.exists() else dict(images=0,images_with_calibrated_candidates=0,results=[])
        if args.agent:
            from .agent import investigate_batch
            manifest=Path(args.out)/'posts.jsonl'
            result['investigation']=investigate_batch(manifest,Path(args.out)/'agent',args.strict_only,args.discover_evidence,args.evidence_cache) if manifest.exists() else dict(images=0,images_with_strict_candidates=0,images_with_conditional_candidates=0,results=[])
        if args.agent or args.recover:(Path(args.out)/'workflow.json').write_text(json.dumps(result,indent=2), encoding="utf-8")
        print(json.dumps(result,indent=2))
    else:
        from .server import serve
        serve(args.port)

if __name__=='__main__':main()
