import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, unlink, rmdir, rename } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import { get } from 'node:http';
import { once } from 'node:events';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';
import { openDeckFile } from '../plugins/design/decision-artifacts/skills/tinder-artifact/scripts/deck-template.mjs';

test('a paired receiver saves and queues a reviewed batch once, to the issuing chat',{skip:process.platform==='win32' && 'The recording CLI is a POSIX shell fixture.',timeout:20000},async t=>{
  const home=await mkdtemp(join(tmpdir(),'deck-receiver-'));
  const thread='12345678-1234-4123-9123-123456789012';
  const entry=fileURLToPath(new URL('../plugins/design/decision-artifacts/skills/tinder-artifact/scripts/connect-deck.mjs',import.meta.url));
  const fixture={id:'check-pair',brief:'Prepare an internal draft.',payload:{title:'Draft review',cards:[{
    job:'guide',kind:'proposal',required:true,question:'Use this draft?',context:'Internal pilot.',
    recommendation:'Use it.',reason:'Matches the brief.',action:'Prepare the draft.',source:'Pilot brief.',uncertainty:'Untested.'
  }]}};
  const hash=value=>createHash('sha256').update(value).digest('hex');
  const receiptFolder=join(home,'receipts',thread,hash(fixture.id).slice(0,24));
  const submissionPath=id=>join(receiptFolder,hash('submission/'+id));
  const removeIfPresent=async (operation,path)=>{
    try {await operation(path);} catch(error){if(error.code!=='ENOENT')throw error;}
  };
  t.after(async ()=>{
    // Clean only named files created by this fixture; unexpected files are retained.
    for(const file of ['codex','deck.json','calls.txt'])await removeIfPresent(unlink,join(home,file));
    for(const id of ['delivery-test-01','delivery-test-02']){
      for(const suffix of ['.json','.receipt.json','.receipt.json.tmp'])await removeIfPresent(unlink,submissionPath(id)+suffix);
    }
    await removeIfPresent(unlink,join(receiptFolder,'delivery-test-01.receipt.json'));
    await removeIfPresent(unlink,join(receiptFolder,'listener.port'));
    for(const directory of [receiptFolder,join(home,'receipts',thread),join(home,'receipts'),home])await removeIfPresent(rmdir,directory);
  });
  const file=join(home,'deck.json');
  await writeFile(file,JSON.stringify(fixture));
  // A recording CLI makes this test independent of a user account and live chats.
  const recorder=join(home,'codex');
  await writeFile(recorder,"#!/bin/sh\nif [ \"$2\" = '--help' ]; then echo '--thread --resume'; exit 0; fi\nprintf '%s\\n' \"$@\" >> \"$QUEUE_LOG\"\n",{mode:0o700});
  const log=join(home,'calls.txt');
  const site='https://review.example';
  function launchReceiver(){
    const child=spawn(process.execPath,[entry,file,join(home,'receipts'),'Draft chat',site],{
      env:{CODEX_THREAD_ID:thread,PATH:home,QUEUE_LOG:log},
      stdio:['ignore','pipe','inherit']
    });
    t.after(()=>child.kill());
    const lines=createInterface({input:child.stdout});
    return {child,ready:Promise.race([
      once(lines,'line').then(([line])=>JSON.parse(line)),
      once(child,'exit').then(()=>{throw Error('Receiver exited before readiness');})
    ])};
  }
  const first=launchReceiver();
  const launch=await first.ready;
  const origin=new URL(launch.local).origin;
  assert.equal((await fetch(launch.hosted,{redirect:'manual'})).status,403);
  const redirect=await new Promise((resolve,reject)=>{
    get(launch.hosted,{headers:{'Sec-Fetch-Mode':'navigate'}},res=>{res.resume();resolve(res);}).on('error',reject);
  });
  assert.equal(redirect.statusCode,302);
  const target=new URL(redirect.headers.location);
  assert.equal(target.origin,site);
  assert.equal((await fetch(origin+'/')).status,404);
  const shell=await fetch(origin+'/deck?deck=another-deck');
  assert.equal(shell.status,200);
  assert.ok(!(await shell.text()).includes(fixture.brief));
  const report=await fetch(origin+'/report.html',{redirect:'manual'});
  assert.equal(report.headers.get('location'),site+'/report.html');
  const key=new URLSearchParams(target.hash.slice(1)).get('tinderKey');
  const view=auth=>fetch(origin+'/open-view',{method:'POST',headers:{Origin:origin,Authorization:'Bearer '+auth}});
  assert.equal((await view('invalid')).status,403);
  const {path:viewPath}=await (await view(key)).json();
  assert.match(viewPath,/^\/deck\/[0-9a-f]{48}$/);
  assert.ok((await (await fetch(origin+viewPath)).text()).includes(fixture.brief));
  const deckHash=createHash('sha256').update(JSON.stringify(openDeckFile(JSON.stringify(fixture)).deck)).digest('hex');
  const post=(path,data,caller=site,auth=key)=>fetch(origin+path,{
    method:'POST',headers:{Origin:caller,Authorization:'Bearer '+auth,'Content-Type':'application/json'},
    body:JSON.stringify({taskId:fixture.id,deckHash,...data})
  });
  assert.equal((await post('/capability',{},'https://other.example')).status,403);
  assert.equal((await post('/capability',{},site,'wrong')).status,403);
  assert.equal((await post('/capability',{deckHash:'changed'})).status,403);
  const peer=await (await post('/capability',{})).json();
  assert.equal(peer.thread,thread);
  const snapshot={task:fixture.payload.title,submissionId:'delivery-test-01',createdAt:'2026-01-01T00:00:00Z',
    processingPolicy:'review-before-sending',decisions:[{id:'item-1',group:'Apply',intent:'approve',
      proposalVersion:1,answerRevision:1,notes:'Retain heading.',selected:[]}]};
  assert.equal((await post('/submit',{...snapshot,decisions:[{...snapshot.decisions[0],group:'Dismiss'}]})).status,400);
  assert.equal((await post('/submit',{...snapshot,createdAt:'invalid'})).status,400);
  // A local write collision occurs before queue invocation. Removing the
  // fixture obstruction allows the same reviewed submission to be sent once.
  const occupied=submissionPath(snapshot.submissionId)+'.json';
  await writeFile(occupied,'existing local fixture',{flag:'wx'});
  assert.equal((await post('/submit',snapshot)).status,409);
  assert.equal(await readFile(occupied,'utf8'),'existing local fixture');
  await unlink(occupied);
  const submitted=await (await post('/submit',snapshot)).json();
  assert.equal(submitted.state,'queued');
  const repeated=await (await post('/submit',snapshot)).json();
  assert.deepEqual(repeated,submitted);
  const changes={...snapshot,decisions:[{...snapshot.decisions[0],notes:'Different text.'}]};
  assert.equal((await post('/submit',changes)).status,409);
  await rename(submissionPath(snapshot.submissionId)+'.receipt.json',join(receiptFolder,snapshot.submissionId+'.receipt.json'));
  assert.deepEqual(await (await post('/submit',snapshot)).json(),submitted);
  const calls=await readFile(log,'utf8');
  assert.equal(calls.split('\n').filter(v=>v==='queue').length,1);
  assert.ok(calls.includes('--thread\n'+thread+'\n'));
  assert.ok(calls.includes('--resume'));
  assert.ok(!calls.includes('Retain heading.'));
  const filePath=JSON.parse(calls.match(/frozen decisions at ("[^"\n]+")\./)[1]);
  const expectedPath=submissionPath(snapshot.submissionId)+'.json';
  assert.equal(filePath,expectedPath);
  const frozen=JSON.parse(await readFile(expectedPath,'utf8'));
  assert.equal(frozen.decisions[0].requestedWork,'Prepare the draft.');
  assert.equal(frozen.decisions[0].notes,'Retain heading.');
  const feedback={...snapshot,submissionId:'delivery-test-02',decisions:[{
    ...snapshot.decisions[0],group:'Unresolved',intent:'dismiss',notes:'Already reviewed elsewhere.'
  }]};
  assert.equal((await (await post('/submit',feedback)).json()).state,'queued');
  const feedbackPacket=JSON.parse(await readFile(submissionPath(feedback.submissionId)+'.json','utf8'));
  assert.equal(feedbackPacket.decisions[0].requestedWork,null);
  assert.equal(feedbackPacket.decisions[0].notes,'Already reviewed elsewhere.');
  const stopped=once(first.child,'exit');
  first.child.kill();
  await stopped;
  const restarted=await launchReceiver().ready;
  assert.equal(new URL(restarted.local).origin,origin);
  assert.notEqual(restarted.local,launch.local);
});
