# Repository Guidelines

## Project Structure

This is the individual Day 09 Evaluation and Failure Analysis lab. `src/lab9/` contains the evaluation pipeline, grader, statistics, regression gate, and mutation/trap exercises. `src/config/` contains metric specifications and failure-mode mappings; `src/data/eval/` contains public evaluation data; `src/tests/` contains pytest tests. Assignment references and submission requirements are in the root README, `CHECKPOINTS.md`, `RUBRIC.md`, `SUBMISSION.md`, and `docs/`.

## Relationship to Day 08

Day 09 continues Day 08 by evaluating its agent traces and guarding changes against regressions. As described in `README.md`, this starter repo is not standalone: copy the original Day 08 `src/` into this repo's `src/`, so both `src/lab8/` and `src/lab9/` are present. Use the instructor-provided Day 08 source as the fixed baseline. Do not edit files under `src/lab8/`; the assignment says those changes lose credit. Day 09's core comparisons use the `swarm` shape.

## Development and Commands

Use Python 3.11–3.13. Run commands from `src/` after installing both dependency files:

```bash
python -m pip install -r requirements.txt -r requirements-lab9.txt
python -m lab9.smoke
python -m lab9.evalset --build
python -m lab9.evalset --check
python -m pytest -q
```

Follow the milestone commands in the README for judge calibration, student tests, evaluation reports, and the CI gate. Some student tests are expected to fail until their corresponding TODOs are implemented; see `CHECKPOINTS.md`.

## Change Boundaries and Style

Keep changes focused on the Day 09 tasks. Follow existing Python style: four-space indentation, descriptive `snake_case`, and deterministic behavior for fixed inputs and seeds. Preserve evaluation provenance, separated labels, report integrity, and the specified metric/gate contracts. Do not hand-edit generated files under `src/reports/`; regenerate them with the documented `lab9` commands. Do not put labels inline in evaluation items. Avoid changing dependencies unless a task requires it.

Before changing grading or gate behavior, consult `docs/failure_taxonomy.md`, `docs/eval_card.md`, the metric spec, and the relevant assignment criteria. Keep public fixtures and report outputs free of secrets or private student data.

## Commits and Submission

Use concise imperative commit subjects. Follow `SUBMISSION.md` for the fork workflow, required reports, pull request, and final submission. Reports may be ignored by Git, so stage required generated reports explicitly as documented there.
