import { writeFile } from 'node:fs/promises';
import { readDeckInput, renderEnvelope } from './deck-template.mjs';

async function render(input, output) {
  const envelope=JSON.parse(await readDeckInput(input));
  const {html}=renderEnvelope(envelope);
  await writeFile(output,html,{flag:'wx',mode:0o600});
}

const [input, output, ...extra] = process.argv.slice(2);
if (!input || !output || extra.length) {
  console.error("Usage: node render-deck.mjs input.tinder.json new-output.html");
  process.exitCode = 2;
} else {
  try {
    await render(input, output);
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
