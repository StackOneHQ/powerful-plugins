"""Local-only workbench, no external uploads or arbitrary file path reads."""
import base64
import json
import tempfile
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from .pipeline import analyze
from .calendar_recovery import analyze_calendar

ROOT=Path(__file__).resolve().parent.parent
ASSETS=Path(__file__).resolve().parent/'assets'


def agent_context(config,temp):
    """Accept public text/URLs, never browser-supplied local file paths."""
    context={}
    for key,limit in [('source',2048),('post_url',2048),('post_text',20000),('post_date',100),('evidence_profile_url',2048)]:
        if key in config and config[key] is not None:
            if not isinstance(config[key],str) or len(config[key])>limit:raise ValueError(f'Invalid {key.replace("_"," ")}')
            if config[key]:context[key]=config[key]
    for key in ('strict_only','discover_evidence'):
        if key in config and type(config[key]) is not bool:raise ValueError(f'{key.replace("_"," ")} must be true or false')
    if config.get('discover_evidence'):context['discover_evidence']=True
    if context.get('evidence_profile_url'):
        from .public_profile import profile_url
        profile_url(context['evidence_profile_url'])
        if context.get('discover_evidence'):raise ValueError('Choose a supplied profile URL or source discovery.')
    text=config.get('evidence_profile_text')
    if text is not None:
        if not isinstance(text,str) or len(text.encode('utf-8'))>500000:raise ValueError('Profile text must be below 500KB.')
        if text:
            if not context.get('evidence_profile_url'):raise ValueError('Pasted profile text requires its public profile URL.')
            snapshot=Path(temp)/'profile.md';snapshot.write_text(text, encoding="utf-8")
            context['evidence_profile_snapshot']=str(snapshot)
    return context


def agent_response(folder,agent):
    """Bundle every saved reader/proposal so selection never reruns inference."""
    workflow=json.loads((folder/'readers/workflow.json').read_text(encoding="utf-8"));views=[];reader_results={};seen=set()
    def add(relative,reader,scope):
        path=(folder/relative).resolve()
        if not path.is_relative_to(folder.resolve()):raise ValueError('Invalid reader result path.')
        if not path.is_file() or path in seen:return
        seen.add(path);r=json.loads(path.read_text(encoding="utf-8"));r['image']='local upload';r.setdefault('trace',[])
        r['geometry']['image']='local upload'
        if scope=='image_reader':reader_results[reader]=r
        views.append(dict(id=str(path.parent.relative_to(folder.resolve())),reader=reader,scope=scope,status=r['status'],result=r,
            overlay=base64.b64encode((path.parent/'overlay.png').read_bytes()).decode(),csv=(path.parent/'data.csv').read_text(encoding="utf-8")))
        if (path.parent/'daily.csv').is_file():views[-1]['daily_csv']=(path.parent/'daily.csv').read_text(encoding="utf-8")
    for a in workflow['attempts']:
        if a.get('result'):add('readers/'+a['result'],a['reader'],'image_reader')
    for a in agent['conditional_results']:add(a['result'],a.get('reader','calendar'),'inferred_correspondence')
    # Failed proposals are useful evidence and must remain inspectable too.
    for step in agent['steps']:
        if step.get('result'):
            reader={'test_first_customer_zero_history':'first_customer','test_comparison_totals':'comparison_totals'}.get(step['action'],'external_daily_revenue')
            add(step['result'],reader,'inferred_correspondence')
    if not views:raise ValueError('All automatic readers failed; inspect the image format or use manual mode.')
    successful=next((v for v in views if v['status']=='calibrated'),None)
    successful=successful or next((v for v in views if v['status']=='conditional_calibration'),None)
    selected=successful or max(views,key=lambda v:sum(len(s['points']) for s in v['result']['geometry']['series']))
    result=dict(selected['result'],overlay=selected['overlay'],csv=selected['csv'],selected_view=selected['id'],agent_views=views)
    if selected.get('daily_csv'):result['daily_csv']=selected['daily_csv']
    documents={}
    for step in agent['steps']:
        if step.get('evidence'):
            path=(folder/step['evidence']).resolve()
            if path.is_relative_to(folder.resolve()) and path.is_file():documents[step['evidence']]=json.loads(path.read_text(encoding="utf-8"))
    result['agent']=dict(agent,image='local upload');result['agent_evidence']=dict(workflow=workflow,reader_results=reader_results,documents=documents)
    result['trace']=list(result['trace'])+agent['steps']
    return result


def import_public_post(url,temp):
    from .collect import POST_URL,PublicXCollector,save_posts
    if not isinstance(url,str) or not POST_URL.fullmatch(url):raise ValueError('Enter an original public X post URL.')
    posts=PublicXCollector().lookup(url)
    for post in posts:post['media']=post.get('media',[])[:4]
    save_posts(posts,temp,download=True)
    records=[json.loads(line) for line in (temp/'posts.jsonl').read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(records)!=1:raise ValueError('Expected one public post.')
    post=records[0];images=[];total=0
    for item in post.get('images',[]):
        path=(temp/item['path']).resolve()
        if not path.is_relative_to(temp.resolve()):raise ValueError('Invalid collected image path.')
        raw=path.read_bytes();total+=len(raw)
        if total>20_000_000:raise ValueError('Collected images exceed the 20MB workbench limit.')
        images.append(dict(image=base64.b64encode(raw).decode(),sha256=item['sha256'],source_url=item.get('source_url')))
    if not images:raise ValueError('This public page exposes no downloadable image. Upload an image you can access.')
    return dict(post={k:post.get(k) for k in ('id','url','text','created_at','collection_method','collection_limits')},
                images=images,errors=post.get('errors',[]))


class Handler(BaseHTTPRequestHandler):
    def _send(self,data,status=200,content_type='application/json'):
        if not isinstance(data,bytes):data=json.dumps(data,allow_nan=False).encode()
        self.send_response(status);self.send_header('Content-Type',content_type)
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)

    def do_GET(self):
        if self.path=='/':return self._send((Path(__file__).resolve().parent/'web/index.html').read_bytes(),content_type='text/html; charset=utf-8')
        if self.path=='/workbench.js':return self._send((Path(__file__).resolve().parent/'web/workbench.js').read_bytes(),content_type='text/javascript; charset=utf-8')
        examples={'/api/comparison-example':'comparison','/api/automatic-example':'bars','/api/example':'line'}
        if self.path in examples:
            folder=ASSETS/'examples'/examples[self.path]
            return self._send(dict(image=base64.b64encode((folder/'chart.png').read_bytes()).decode(),
                                   config=json.loads((folder/'config.json').read_text(encoding="utf-8"))))
        if self.path=='/api/benchmark':
            path=ROOT/'artifacts/heldout/summary.json'
            summary=json.loads(path.read_text(encoding="utf-8")) if path.exists() else json.loads((ASSETS/'benchmarks.json').read_text(encoding="utf-8"))
            automatic=ROOT/'artifacts/automatic-heldout-v2/summary.json'
            if automatic.exists():
                a=json.loads(automatic.read_text(encoding="utf-8"));summary['automatic']=dict(charts=a['cases'],passed=a['passed'])
            calendar=ROOT/'artifacts/calendar-heldout-v2/summary.json'
            if calendar.exists():
                c=json.loads(calendar.read_text(encoding="utf-8"));summary['calendar']=dict(charts=c['cases'],passed=c['passed'])
            previous=ROOT/'artifacts/hypothesis-heldout-v1/summary.json'
            hypotheses=ROOT/'artifacts/hypothesis-heldout-v2/summary.json'
            if not hypotheses.exists():hypotheses=previous
            if hypotheses.exists():
                h=json.loads(hypotheses.read_text(encoding="utf-8"));summary['hypotheses']=dict(charts=h['cases'],passed=h['passed'],incorrect_returned=h['incorrect_returned_candidates_under_criteria'],version=hypotheses.parent.name)
                if hypotheses!=previous and previous.exists():
                    summary['hypotheses']['earlier_returned_failures']=json.loads(previous.read_text(encoding="utf-8"))['incorrect_returned_candidates_under_criteria']
            caption=ROOT/'artifacts/caption-comparison/summary.json'
            if caption.exists():
                c=json.loads(caption.read_text(encoding="utf-8"))['synthetic']
                summary['caption']=dict(charts=c['cases'],passed=c['passed'],abstentions=c['abstentions'],returned_failures=c['returned_failures'])
            comparison_studies=[]
            for version in ('v1','v2','v3'):
                comparison=ROOT/f'artifacts/comparison-totals-heldout-{version}/summary.json'
                if comparison.exists():
                    c=json.loads(comparison.read_text(encoding="utf-8"))
                    stats={k:c[k] for k in ('charts','passed','abstained','returned_failures')}
                    stress=[r for r in c.get('controls',[]) if r.get('control') in ('log_axis','independent_axes')]
                    stats.update(version=version,assumption_stress_cases=len(stress),
                                 assumption_stress_failures=sum(r['status']=='conditional_calibration' and not r['passed'] for r in stress))
                    comparison_studies.append(stats)
            if comparison_studies:summary['comparison_studies']=comparison_studies
            if summary.get('comparison_studies'):summary['comparison_totals']=summary['comparison_studies'][-1]
            ticks=ROOT/'artifacts/tick-heldout-v2/summary.json'
            if ticks.exists():
                t=json.loads(ticks.read_text(encoding="utf-8"));summary['ticks']=dict(charts=t['cases'],passed=t['passed'])
            summary.setdefault('external_studies',[])
            for name,label in [('corner-sparse-corrected','Prior corner study: sparse lines'),('corner-mixed-corrected','Prior corner study: mixed lines'),('corner-curves-corrected','Prior corner study: smooth/step')]:
                path=ROOT/'artifacts'/name/'summary.json'
                if path.exists():
                    e=json.loads(path.read_text(encoding="utf-8"));summary['external_studies'].append(dict(label=label,charts=e['cases'],passed=e['passed'],abstentions=e['abstentions'],returned_failures=e['incorrect_returned_candidates_under_criteria']))
            step_study=ROOT/'artifacts/step-heldout-v1/summary.json'
            if step_study.exists():
                groups=json.loads(step_study.read_text(encoding="utf-8"))['readers']['revised']['groups']
                for key,label in [('step','Step conventions'),('other','Step-study linear/smooth checks')]:
                    g=groups[key];summary['external_studies'].append(dict(label=label,charts=g['cases'],passed=g['passed'],abstentions=g['abstentions'],returned_failures=g['returned_failures']))
            return self._send(summary)
        return self._send({'error':'Not found'},404)

    def do_POST(self):
        if self.path not in ('/api/analyze','/api/import-post'):return self._send({'error':'Not found'},404)
        origin=self.headers.get('Origin')
        if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'):
            return self._send({'error':'Local origin required'},403)
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<20_000_000:raise ValueError('Request must be below 20MB')
            data=json.loads(self.rfile.read(length))
            if self.path=='/api/import-post':
                with tempfile.TemporaryDirectory(prefix='chart-public-import-') as temp:
                    return self._send(import_public_post(data.get('url'),Path(temp)))
            raw=base64.b64decode(data['image'],validate=True)
            # Each request gets an isolated directory; user images never leave this computer.
            with tempfile.TemporaryDirectory(prefix='chart-recover-') as temp:
                path=Path(temp)/'input.image';path.write_bytes(raw)
                config=data.get('config',{})
                if not isinstance(config,dict):raise ValueError('Configuration must be an object.')
                reader=config.get('reader','bars' if config.get('auto_layout') else 'manual')
                if reader not in ('manual','bars','calendar','agent'):raise ValueError('Unknown chart reader')
                folder=Path(temp)/'result'
                if reader=='agent':
                    from .agent import investigate_image
                    context=agent_context(config,temp)
                    agent=investigate_image(path,context,folder,strict_only=bool(config.get('strict_only')))
                    result=agent_response(folder,agent)
                elif reader=='calendar':
                    config.setdefault('source',config.get('post_url'))
                    result=analyze_calendar(path,config,Path(temp)/'result')
                else:
                    config['auto_layout']=reader=='bars'
                    result=analyze(path,config,Path(temp)/'result')
                if reader!='agent':
                    result['overlay']=base64.b64encode((folder/'overlay.png').read_bytes()).decode()
                    result['csv']=(folder/'data.csv').read_text(encoding="utf-8")
                result['image']='local upload';result['geometry']['image']='local upload'
                self._send(result)
        except (ValueError,KeyError,OSError,IndexError,TypeError,RuntimeError) as e:self._send({'error':str(e)},400)
        except Exception:self._send({'error':'Analysis failed; check chart configuration.'},500)


def serve(port=8765):
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'Chart Recover: http://127.0.0.1:{port}',flush=True);server.serve_forever()
