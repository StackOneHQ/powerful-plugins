import assert from 'node:assert/strict';
import { webcrypto } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import { runInNewContext } from 'node:vm';

// Exercise the same bundled functions used by standalone and paired browser decks.
const renderer=new URL('../plugins/design/decision-artifacts/skills/tinder-artifact/assets/renderer.html',import.meta.url);
const html=await readFile(renderer,'utf8');
const script=html.match(/<script id="review-records">([\s\S]*?)<\/script>/)[1];
const {draftStore,nextRevision,promptText}=runInNewContext(
  script+'\n;({draftStore,nextRevision,promptText})',{crypto:webcrypto,TextEncoder}
);

test('persist approvals only for the exact reviewed deck content',async ()=>{
  const deck={id:'draft',title:'Review',definitions:[{action:'Draft the copy'}]};
  assert.equal(await draftStore(deck),await draftStore(structuredClone(deck)));
  const changed={...deck,definitions:[{action:'Review the copy'}]};
  assert.notEqual(await draftStore(deck),await draftStore(changed));
});

test('restoring an earlier answer or clearing history cannot reuse a frozen revision',()=>{
  const item={id:'a',answerRevision:1,proposalVersion:1};
  const state={records:{a:item},history:[{decisions:[{...item,answerRevision:5,proposalVersion:3}]}]};
  assert.equal(nextRevision(state,'a','answerRevision'),6);
  assert.equal(nextRevision(state,'a','proposalVersion'),4);
  state.revisionFloor={a:{answerRevision:6,proposalVersion:3}};
  state.history=[];
  assert.equal(nextRevision(state,'a','answerRevision'),7);
  assert.equal(nextRevision(state,'a','proposalVersion'),4);
});

test('copied evidence and reviewer notes round-trip as fields of one decision',()=>{
  const decisions=[{id:'a',group:'Dismiss',context:'First line\nSecond line',notes:'Keep "draft"'}];
  const packet={taskId:'draft',decisions};
  const text=promptText({...packet,fingerprint:'internal',text:'previous representation'});
  const decoded=JSON.parse(text.slice(text.indexOf('\n\n')+2));
  assert.deepEqual(decoded,packet);
});
