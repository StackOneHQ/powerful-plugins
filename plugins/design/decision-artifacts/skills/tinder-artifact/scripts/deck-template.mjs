import { open, readFile } from 'node:fs/promises';
import { constants, readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const template = await readFile(new URL('../assets/renderer.html',import.meta.url),'utf8');
const tag = '<script id="artifact-deck" type="application/json">';
const contract = template.match(/<script id="deck-contract">([\s\S]*?)<\/script>/)[1];
const exampleDir = new URL('../examples/after-hours/',import.meta.url);
const example = JSON.parse(await readFile(new URL('after-hours.tinder.json',exampleDir),'utf8'));
let presentation;

function examplePresentation() {
  if (!presentation) {
    const css=readFileSync(new URL('presentation.css',exampleDir),'utf8');
    const js=readFileSync(new URL('presentation.js',exampleDir),'utf8');
    const photo=readFileSync(new URL('concert.webp',exampleDir)).toString('base64');
    presentation='<style>'+css+'</style><script>'+js.replace('__CONCERT_PHOTO__','data:image/webp;base64,'+photo)+'</script>';
  }
  return presentation;
}

export function renderEnvelope(envelope) {
  if (!envelope || typeof envelope!=='object') throw Error('Expected a deck object with id, brief and payload.');
  const deck=runInNewContext(contract+'\nvalidateDeck(envelope.payload,envelope.brief,envelope.id)',{envelope});
  const data=JSON.stringify({id:envelope.id,brief:envelope.brief,payload:envelope.payload}).replaceAll('<','\\u003c');
  let html=template.replace(tag+'</script>',()=>tag+data+'</script>');
  if(envelope.id===example.id && envelope.brief===example.brief && JSON.stringify(envelope.payload)===JSON.stringify(example.payload)){
    html=html.replace('<!-- trusted-deck-presentation -->',examplePresentation);
  }
  return {deck,html};
}

export function openDeckFile(input) {
  const seed=input.match(/<script id="artifact-deck" type="application\/json">([\s\S]*?)<\/script>/);
  if (!seed) return renderEnvelope(JSON.parse(input));
  if (seed[1].trim()) return renderEnvelope(JSON.parse(seed[1]));
  // Only evaluate our packaged pilot definitions. Files supplied by the user contribute data only.
  const pilot=template.slice(template.indexOf('const pilotDefinitions='),template.indexOf('const DECK_PREFIX'));
  return {html:template,deck:runInNewContext(pilot+'\nPILOT')};
}

// The path comes only from a local CLI argument. Open once and validate the
// descriptor so pipes and devices cannot be consumed as decks.
export async function readDeckInput(path) {
  const file=await open(path,constants.O_RDONLY | (constants.O_NONBLOCK || 0));
  try {
    if(!(await file.stat()).isFile())throw Error('Choose a regular deck file.');
    return await file.readFile('utf8');
  } finally {
    await file.close();
  }
}
