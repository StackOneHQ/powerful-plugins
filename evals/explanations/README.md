# Explanation evaluations

These evaluations compare released skills with a candidate using the same model,
inputs, audience and tool budget. Keep benchmark samples, synthetic fixtures,
mechanical tests and user feedback separate in every report. None of the local
adaptations is an official benchmark score.

## Public benchmark basis

| Source | What it contributes | What it does not establish |
|---|---|---|
| [ASSET, ACL 2020](https://aclanthology.org/2020.acl-main.424/) and its [corpus](https://github.com/facebookresearch/asset) | Sentence simplification with multiple references; separate meaning, fluency and simplicity assessments | Software correctness, diagram quality or video comprehension |
| [IFEval](https://github.com/google-research/google-research/tree/master/instruction_following_eval) | Check objectively verifiable constraints independently of preference | Whether preserved words still express the same meaning |
| [AI2D](https://allenai.org/data/diagrams) | Diagram-grounded questions and relationships as a model for reader tasks | A direct benchmark score for generated diagrams |
| [ScienceQA](https://github.com/lupantech/ScienceQA) | Source-grounded explanations with comprehension questions | An established metric for educational video quality |

The committed fixtures are original synthetic material under this repository's
license. Public dataset files retain their own licenses. ASSET is CC BY-NC 4.0;
ScienceQA data is CC BY-NC-SA 4.0. Keep downloaded data and derivative outputs
outside the repository. Record dataset revision, split, item IDs, sampling method
and license when running a public sample. A benchmark-informed synthetic test must
never be reported as a run on the benchmark itself.

## Release sequence

1. `natural-writing`: technical explanation mode and its evaluation.
2. `animation-studio`: narrated educational explanations and artifact checks.
3. `diagram-explainer`: editable source-grounded diagrams and reader tasks.
4. `decision-artifacts`: guided interactive walkthroughs with static equivalents.

Each increment needs its own version bump, passing repository checks, tested
artifacts, and specific user feedback. A good result for one format does not
approve another format.

## Writing protocol

Freeze the cases before generating candidate outputs. Use `dev` cases to improve
the skill. Evaluate `holdout` cases only after that change is frozen; if their
results inform another edit, label them development data and create a fresh holdout.
Keep repetitions from the same case together when comparing results.

Run released and candidate skills in fresh sessions with the same model and
settings. Give generators only the source, request and their skill version, not
the expected facts, answer keys, human references or the other output. Record the
model, date, skill commit/content hash, prompt, output and tool limitations.
Use at least two runs per arm on the synthetic suite to expose variation. Report
case counts and failures, not just a pooled average.

```bash
python3 scripts/evaluate_explanations.py prepare \
  --cases evals/explanations/writing.jsonl --split dev --out /tmp/writing-prompts
python3 scripts/evaluate_explanations.py score \
  --cases evals/explanations/writing.jsonl --outputs /tmp/candidate.jsonl \
  --out /tmp/candidate-report.json
python3 scripts/evaluate_explanations.py blind \
  --cases evals/explanations/writing.jsonl --baseline /tmp/baseline.jsonl \
  --outputs /tmp/candidate.jsonl --out /tmp/writing-comparison
```

An output JSONL row is `{"id":"case-id","output":"the finished explanation"}`.
Use the same `--split` when preparing and scoring a partial suite. The CLI refuses
to overwrite evidence. It never calls a model or sends data over the network.

Literal checks catch omissions and changes to protected strings. Word count is
diagnostic only. A mechanically clean result is `awaiting_reviews`, not a pass
on meaning. Review outputs against the full source and expected facts, including
negation, threshold boundaries and uncertainty.

For blind comparison, give the reviewer `pairs.json`; keep `private-key.json`
away from the reviewer. Rate meaning, simplicity and fluency separately from
1 (poor) to 5 (excellent), with a reason tied to the output. Answer the case's
comprehension questions from the explanation. A case passes review only with
meaning 5, simplicity and fluency at least 4, no wrong comprehension answer and
no critical error. Record an unanswered or wrong required question as a critical
error. A model reviewer is a model reviewer, not human validation.

Review JSONL rows contain `id`, `output_sha256`, integer `meaning`, `simplicity`,
`fluency`, boolean `critical_error`, and `rationale`. The hash binds a review to
the exact output; revised outputs need a new review. `score --reviews FILE`
checks the review contract and reports status. It does not certify a release.

## User feedback

Show the user concrete A/B outputs before revealing their labels. Ask which is
easier to understand, which detail is missing or overexplained, and one question
that tests the mechanism. Preserve their actual response locally. Do not infer
approval from silence, a style preference, or an automated score.

Release only when critical facts and comprehension answers are preserved, the
candidate has no unexplained regression against the baseline, the repository
checks pass, and the user has reviewed the relevant artifact. Record shortcomings
and the sample size. Small samples support a release decision, not a claim of
general benchmark superiority.
