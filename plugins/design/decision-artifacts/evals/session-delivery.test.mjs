import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import { get } from 'node:http';
import { once } from 'node:events';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';
import { openDeckFile } from '../skills/tinder-artifact/scripts/deck-template.mjs';

test('a paired receiver saves and queues a reviewed batch once, to the issuing chat',async t=>{
  const home=await mkdtemp(join(tmpdir(),'deck-receiver-'));
  t.after(()=>rm(home,{recursive:true,force:true}));
  const thread='12345678-1234-4123-9123-123456789012';
  const entry=fileURLToPath(new URL('../skills/tinder-artifact/scripts/connect-deck.mjs',import.meta.url));
  const fixture={id:'check-pair',brief:'Prepare an internal draft.',payload:{title:'Draft review',cards:[{
    job:'guide',kind:'proposal',required:true,question:'Use this draft?',context:'Internal pilot.',
    recommendation:'Use it.',reason:'Matches the brief.',action:'Prepare the draft.',source:'Pilot brief.',uncertainty:'Untested.'
  }]}};
  const file=join(home,'deck.json');
  await writeFile(file,JSON.stringify(fixture));
  // A recording CLI makes this test independent of a user account and live chats.
  const recorder=join(home,'codex');
  await writeFile(recorder,"#!/bin/sh\nif [ \"$2\" = '--help' ]; then echo '--thread --resume'; exit 0; fi\nprintf '%s\\n' \"$@\" >> \"$QUEUE_LOG\"\n",{mode:0o700});
  const log=join(home,'calls.txt');
  const site='https://review.example';
  const child=spawn(process.execPath,[entry,file,join(home,'receipts'),'Draft chat',site],{
    env:{...process.env,CODEX_THREAD_ID:thread,PATH:home+':'+process.env.PATH,QUEUE_LOG:log},
    stdio:['ignore','pipe','inherit']
  });
  t.after(()=>child.kill());
  const [line]=await once(createInterface({input:child.stdout}),'line');
  const launch=JSON.parse(line);
  const origin=new URL(launch.local).origin;
  assert.equal((await fetch(launch.hosted,{redirect:'manual'})).status,403);
  const redirect=await new Promise((resolve,reject)=>{
    get(launch.hosted,{headers:{'Sec-Fetch-Mode':'navigate'}},res=>{res.resume();resolve(res);}).on('error',reject);
  });
  assert.equal(redirect.statusCode,302);
  const target=new URL(redirect.headers.location);
  assert.equal(target.origin,site);
  assert.equal((await fetch(origin+'/')).status,404);
  assert.equal((await fetch(origin+'/deck?deck=another-deck')).status,200);
  const report=await fetch(origin+'/report.html',{redirect:'manual'});
  assert.equal(report.headers.get('location'),site+'/report.html');
  const key=new URLSearchParams(target.hash.slice(1)).get('tinderKey');
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
  const submitted=await (await post('/submit',snapshot)).json();
  assert.equal(submitted.state,'queued');
  const repeated=await (await post('/submit',snapshot)).json();
  assert.deepEqual(repeated,submitted);
  const changes={...snapshot,decisions:[{...snapshot.decisions[0],notes:'Different text.'}]};
  assert.equal((await post('/submit',changes)).status,409);
  const calls=await readFile(log,'utf8');
  assert.equal(calls.split('\n').filter(v=>v==='queue').length,1);
  assert.ok(calls.includes('--thread\n'+thread+'\n'));
  assert.ok(calls.includes('--resume'));
  assert.ok(!calls.includes('Retain heading.'));
  const filePath=JSON.parse(calls.match(/frozen decisions at ("[^"\n]+")\./)[1]);
  const frozen=JSON.parse(await readFile(filePath,'utf8'));
  assert.equal(frozen.decisions[0].requestedWork,'Prepare the draft.');
  assert.equal(frozen.decisions[0].notes,'Retain heading.');
  const feedback={...snapshot,submissionId:'delivery-test-02',decisions:[{
    ...snapshot.decisions[0],group:'Unresolved',intent:'dismiss',notes:'Already reviewed elsewhere.'
  }]};
  assert.equal((await (await post('/submit',feedback)).json()).state,'queued');
  const feedbackPacket=JSON.parse(await readFile(filePath.replace('delivery-test-01','delivery-test-02'),'utf8'));
  assert.equal(feedbackPacket.decisions[0].requestedWork,null);
  assert.equal(feedbackPacket.decisions[0].notes,'Already reviewed elsewhere.');
});
