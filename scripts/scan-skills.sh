#!/usr/bin/env bash
#
# scan-skills.sh - Scan Claude skills with NVIDIA SkillSpector
# https://github.com/NVIDIA/skillspector
#
# A "skill" is any directory under $SKILL_ROOTS that directly contains a
# SKILL.md. SkillSpector treats each such directory as one skill bundle. Each
# plugin's agents/, commands/, hooks/ and scripts/ folders are scanned as well.
# In changed mode, changed plugin files outside all of them (a manifest, .mcp.json,
# source code) are copied into a staging folder and scanned as that plugin, so the
# changed content is read without rescanning everything else the plugin holds.
#
# Usage:
#   scripts/scan-skills.sh all                 # scan every skill
#   scripts/scan-skills.sh changed [BASE_REF]  # scan skills changed vs BASE_REF
#                                              # (BASE_REF defaults to origin/main)
#
# Environment:
#   SKILLSPECTOR_USE_LLM=1   Enable LLM semantic analysis (needs an API key,
#                            see SkillSpector docs). Default: static-only.
#   REPORT_ONLY=1            Scan and report findings but always exit 0 (do not
#                            fail on high-risk skills). Setup errors still fail.
#   SKILL_ROOTS="plugins codex-compat"  Root directories to search for skills.
#   SKILL_ROOT=plugins       Backward-compatible single-root override.
#   REPORT_DIR=...           Where SARIF reports are written.
#                            Default: skillspector-reports
#   SKILLSPECTOR_ALLOWLIST=... Exact reviewed skill/rule exceptions.
#                            Default: .skillspector-allowlist.json
#
# Exit status:
#   0  all scanned skills are within risk threshold (or REPORT_ONLY=1)
#   1  at least one skill is high risk (SkillSpector exit 1) or errored
#   2  usage / setup error (bad args, missing base ref)
#   127 skillspector is not installed
#
set -euo pipefail

MODE="${1:-all}"
BASE_REF="${2:-origin/main}"
SKILL_ROOTS="${SKILL_ROOTS:-${SKILL_ROOT:-plugins codex-compat}}"
REPORT_DIR="${REPORT_DIR:-skillspector-reports}"
SKILLSPECTOR_ALLOWLIST="${SKILLSPECTOR_ALLOWLIST:-.skillspector-allowlist.json}"
read -r -a SKILL_ROOT_ARRAY <<<"$SKILL_ROOTS"

# Holds copies of changed files that sit outside every scanned folder (changed mode only).
STAGE_ROOT=""
STAGED_PLUGINS=""
WHOLE_PLUGINS=""
# shellcheck disable=SC2329 # invoked by the EXIT trap
cleanup_stage() {
  if [ -n "$STAGE_ROOT" ]; then
    rm -rf "$STAGE_ROOT"
  fi
}
trap cleanup_stage EXIT

# True when the first argument is one of the newline-separated lines in the second.
in_list() {
  # A here-string, not a pipe: with pipefail, grep -q exiting early would fail the printf.
  grep -Fxq -- "$1" <<<"$2"
}

# Resolve relative skill and report paths from the repository root so invoking
# this script from a subdirectory does not change which files are classified.
if REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  if ! cd "$REPO_ROOT"; then
    echo "ERROR: cannot enter repository root '$REPO_ROOT'." >&2
    exit 2
  fi
fi

# Static analysis only by default so CI runs without any API credentials.
LLM_ARGS="--no-llm"
if [ "${SKILLSPECTOR_USE_LLM:-0}" = "1" ]; then
  LLM_ARGS=""
fi

if ! command -v skillspector >/dev/null 2>&1; then
  echo "ERROR: 'skillspector' not found on PATH." >&2
  echo "Install it (requires Python 3.12+) with the commit CI pins, so local" >&2
  echo "scans match CI (no PyPI release / tags upstream; bump deliberately):" >&2
  echo '  pip install "git+https://github.com/NVIDIA/skillspector.git@2eb844780ab163f01468ecf142c40a2ec0fcaec0"' >&2
  exit 127
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: 'jq' is required to prepare and review SARIF reports." >&2
  exit 127
fi

if [ -f "$SKILLSPECTOR_ALLOWLIST" ] && ! jq -e '
  .version == 1
  and (.reviewed_high_risk | type == "array")
  and ([.reviewed_high_risk[].skill] | length == (unique | length))
  and all(.reviewed_high_risk[];
    (keys | sort) == ["rationale", "rules", "skill"]
    and (.skill | type == "string" and test("^(plugins|codex-compat)/") and (contains("..") | not))
    and (.rationale | type == "string" and length > 20)
    and (.rules | type == "array" and length > 0)
    and all(.rules[]; type == "string" and test("^[A-Z]+[0-9]+$"))
    and (.rules | length == (unique | length))
  )
' "$SKILLSPECTOR_ALLOWLIST" >/dev/null; then
  echo "ERROR: invalid SkillSpector allowlist '$SKILLSPECTOR_ALLOWLIST'." >&2
  exit 2
fi

is_reviewed_high_risk() {
  local skill_dir="$1"
  local sarif_report="$2"
  [ -f "$SKILLSPECTOR_ALLOWLIST" ] && [ -f "$sarif_report" ] || return 1
  jq -e --arg skill_dir "$skill_dir" --slurpfile report "$sarif_report" '
    ([.reviewed_high_risk[] | select(.skill == $skill_dir)]) as $entries
    | ([$report[0].runs[]?.results[]?.ruleId] | unique) as $actual_rules
    | ($entries | length) == 1
      and ($actual_rules | length) > 0
      and ($actual_rules == ($entries[0].rules | unique))
  ' "$SKILLSPECTOR_ALLOWLIST" >/dev/null 2>&1
}

# Scan every installed skill instruction, including deterministic Codex adapters. Generation
# drift proves only that output is current; security analysis must inspect the final prompt.
# Generated policy metadata is not model instruction content and does not trigger a rescan alone.
GENERATOR_MARKER="Generated by scripts/generate_codex_marketplace.py; do not edit."

is_generator_owned_policy_change() {
  local path="$1"
  case "$path" in
    */agents/openai.yaml) ;;
    *) return 1 ;;
  esac
  if [ -f "$path" ]; then
    grep -Fq "$GENERATOR_MARKER" "$path" 2>/dev/null
  else
    git show "$BASE_REF:$path" 2>/dev/null | \
      grep -Fq "$GENERATOR_MARKER" 2>/dev/null
  fi
}

is_plugin_root() {
  [ -f "$1/.claude-plugin/plugin.json" ] || [ -f "$1/.codex-plugin/plugin.json" ]
}

# The nearest directory at or above a changed path's folder that is a plugin root.
plugin_root_of() {
  local dir
  dir="$(dirname "$1")"
  while :; do
    if is_plugin_root "$dir"; then
      printf '%s\n' "$dir"
      return 0
    fi
    case "$dir" in
      . | /) return 1 ;;
    esac
    dir="$(dirname "$dir")"
  done
}

# All directories that directly contain an installable SKILL.md, plus each plugin's own
# agents, commands, hooks and scripts folders. Those are loaded or run alongside the skills
# but sit outside any skill directory, so a skill-only scan never reads them. Plugin roots
# are found by their manifest, so this works whether SKILL_ROOTS names the whole catalog or
# a single plugin.
ALL_DIRS="$(
  {
    for skill_root in "${SKILL_ROOT_ARRAY[@]}"; do
      if [ -d "$skill_root" ]; then
        find "$skill_root" -type f -name SKILL.md -print | while IFS= read -r skill_file; do
          dirname "$skill_file"
        done
        find "$skill_root" -type d \
          \( -name agents -o -name commands -o -name hooks -o -name scripts \) -print |
          while IFS= read -r component_dir; do
            if is_plugin_root "$(dirname "$component_dir")"; then
              printf '%s\n' "$component_dir"
            fi
          done
      fi
    done
  } | sort -u
)"

case "$MODE" in
  all)
    TARGETS="$ALL_DIRS"
    ;;
  changed)
    if ! git rev-parse --verify "$BASE_REF" >/dev/null 2>&1; then
      echo "ERROR: base ref '$BASE_REF' not found." >&2
      echo "Fetch it first, e.g.: git fetch origin main" >&2
      exit 2
    fi
    # Files changed on this branch relative to the merge-base with BASE_REF.
    CHANGED="$(git diff --name-only "$BASE_REF"...HEAD -- "${SKILL_ROOT_ARRAY[@]}")"
    CONTENT_CHANGED=""
    while IFS= read -r cf; do
      [ -z "$cf" ] && continue
      if is_generator_owned_policy_change "$cf"; then
        continue
      fi
      CONTENT_CHANGED="${CONTENT_CHANGED}${cf}
"
    done <<<"$CHANGED"

    TARGETS=""
    while IFS= read -r dir; do
      [ -z "$dir" ] && continue
      while IFS= read -r cf; do
        case "$cf" in
          "$dir"/*)
            TARGETS="${TARGETS}${dir}
"
            break
            ;;
        esac
      done <<<"$CONTENT_CHANGED"
    done <<<"$ALL_DIRS"

    # Changed plugin files outside every skill and component folder (source, .mcp.json,
    # plugin.json) still ship, so scan exactly those, staged under their repo paths: every
    # plugin change bumps plugin.json, which must not rescan untouched skills. A symlink
    # cannot be staged faithfully, so its plugin is scanned in place.
    while IFS= read -r cf; do
      [ -z "$cf" ] && continue
      covered=0
      while IFS= read -r dir; do
        [ -z "$dir" ] && continue
        case "$cf" in
          "$dir"/*) covered=1; break ;;
        esac
      done <<<"$ALL_DIRS"
      [ "$covered" -eq 1 ] && continue
      plugin_root="$(plugin_root_of "$cf")" || continue
      if [ -f "$cf" ] && [ ! -L "$cf" ]; then
        [ -n "$STAGE_ROOT" ] || STAGE_ROOT="$(mktemp -d)"
        mkdir -p "$(dirname "$STAGE_ROOT/$cf")"
        cp "$cf" "$STAGE_ROOT/$cf"
        STAGED_PLUGINS="${STAGED_PLUGINS}${plugin_root}
"
      elif [ -L "$cf" ] || [ -e "$cf" ]; then
        WHOLE_PLUGINS="${WHOLE_PLUGINS}${plugin_root}
"
      else
        continue
      fi
      TARGETS="${TARGETS}${plugin_root}
"
    done <<<"$CONTENT_CHANGED"
    TARGETS="$(printf '%s\n' "$TARGETS" | sed '/^$/d' | LC_ALL=C sort -u)"
    # A plugin scanned in place already covers the skill and component folders inside it.
    # A staged plugin holds only the changed files, so those folders are still scanned.
    if [ -n "$WHOLE_PLUGINS" ]; then
      KEPT=""
      while IFS= read -r target; do
        [ -z "$target" ] && continue
        inside=0
        while IFS= read -r plugin_root; do
          [ -z "$plugin_root" ] && continue
          case "$target" in
            "$plugin_root"/*) inside=1; break ;;
          esac
        done <<<"$WHOLE_PLUGINS"
        if [ "$inside" -eq 0 ]; then
          KEPT="${KEPT}${target}
"
        fi
      done <<<"$TARGETS"
      TARGETS="$KEPT"
    fi
    ;;
  *)
    echo "Usage: scan-skills.sh [all|changed] [base-ref]" >&2
    exit 2
    ;;
esac

# Drop blank lines from the target list.
TARGETS="$(printf '%s\n' "$TARGETS" | sed '/^$/d')"

if [ -z "$TARGETS" ]; then
  echo "No skills to scan${MODE:+ (mode: $MODE)}."
  exit 0
fi

mkdir -p "$REPORT_DIR"

FAIL=0
SCANNED=0
HIGH_RISK=""
REVIEWED_HIGH_RISK=""
ERRORED=""
SARIF_REPORTS=()

echo "SkillSpector scan (mode: $MODE${LLM_ARGS:+, static-only})"
echo "---------------------------------------------"

while IFS= read -r dir; do
  [ -z "$dir" ] && continue
  SCANNED=$((SCANNED + 1))
  slug="$(printf '%s' "$dir" | tr '/' '_')"
  sarif="$REPORT_DIR/$slug.sarif"

  scan_path="$dir"
  if in_list "$dir" "$STAGED_PLUGINS" && ! in_list "$dir" "$WHOLE_PLUGINS"; then
    scan_path="$STAGE_ROOT/$dir"
    echo ">> $dir (changed files outside skill and component folders)"
  else
    echo ">> $dir"
  fi
  set +e
  # shellcheck disable=SC2086
  skillspector scan "$scan_path" $LLM_ARGS --format sarif --output "$sarif"
  code=$?
  set -e

  case "$code" in
    0) echo "   PASS" ;;
    1)
      if is_reviewed_high_risk "$dir" "$sarif"; then
        echo "   REVIEWED HIGH RISK (exact skill/rule allowlist match)"
        REVIEWED_HIGH_RISK="${REVIEWED_HIGH_RISK}  $dir
"
      else
        echo "   HIGH RISK (score > 50)"
        HIGH_RISK="${HIGH_RISK}  $dir
"
        FAIL=1
      fi
      ;;
    *) echo "   SCAN ERROR (exit $code)"; ERRORED="${ERRORED}  $dir
"; FAIL=1 ;;
  esac

  # SkillSpector reports locations relative to each skill directory. Rewrite
  # them relative to the repository so GitHub code scanning can locate the
  # files after all reports are combined into one SARIF run.
  if [ -f "$sarif" ]; then
    normalized="$sarif.tmp"
    if jq --arg skill_dir "$dir" '
      (.runs[]?.results[]?.locations[]?.physicalLocation.artifactLocation.uri) |=
        if startswith("/")
          or test("^[A-Za-z][A-Za-z0-9+.-]*:")
          or startswith($skill_dir + "/")
        then .
        else $skill_dir + "/" + .
        end
    ' "$sarif" > "$normalized"; then
      mv "$normalized" "$sarif"
      SARIF_REPORTS+=("$sarif")
    else
      rm -f "$normalized"
      echo "   SARIF ERROR (invalid report)"
      ERRORED="${ERRORED}  $dir (invalid SARIF report)
"
      FAIL=1
    fi

    jq -r '.runs[]?.results[]? | "     [\(.level // "note")] \(.ruleId // "rule"): \(.message.text // "")"' \
      "$sarif" 2>/dev/null || true
  fi
done <<EOF_TARGETS
$TARGETS
EOF_TARGETS

# GitHub code scanning accepts one SARIF run per category. SkillSpector emits
# one run per skill, so consolidate their results into a single upload file.
if [ "${#SARIF_REPORTS[@]}" -gt 0 ]; then
  combined="$REPORT_DIR/skillspector.sarif"
  combined_tmp="$combined.tmp"
  if ! jq -s '
    . as $documents
    | [$documents[] | .runs[]?] as $runs
    | if ($runs | length) == 0 then
        error("SkillSpector reports contained no SARIF runs")
      else
        {
          version: ($documents[0].version // "2.1.0"),
          "$schema": ($documents[0]."$schema" // "https://schemastore.azurewebsites.net/schemas/json/sarif-2.1.0-rtm.4.json"),
          runs: [($runs[0] | .results = [$runs[] | .results[]?])]
        }
      end
  ' "${SARIF_REPORTS[@]}" > "$combined_tmp"; then
    rm -f "$combined_tmp"
    echo "ERROR: could not combine SkillSpector SARIF reports." >&2
    exit 2
  fi
  mv "$combined_tmp" "$combined"
fi

echo ""
echo "=== SkillSpector summary ==="
echo "Skills scanned: $SCANNED"
if [ -n "$HIGH_RISK" ]; then
  echo "High risk:"
  printf '%s' "$HIGH_RISK"
fi
if [ -n "$REVIEWED_HIGH_RISK" ]; then
  echo "Reviewed high risk (exact allowlist match):"
  printf '%s' "$REVIEWED_HIGH_RISK"
fi
if [ -n "$ERRORED" ]; then
  echo "Errored:"
  printf '%s' "$ERRORED"
fi
if [ "$FAIL" -eq 0 ]; then
  echo "Result: PASS"
else
  echo "Result: FAIL"
fi

if [ "${REPORT_ONLY:-0}" = "1" ] && [ "$FAIL" -ne 0 ]; then
  echo "(report-only mode: findings recorded, not failing the build)"
  exit 0
fi

exit "$FAIL"
