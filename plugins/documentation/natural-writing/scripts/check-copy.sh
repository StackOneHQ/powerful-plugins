#!/usr/bin/env bash
# check-copy.sh: the mechanical half of the natural-writing skill as a gate.

usage() {
  cat <<'USAGE'
Usage: check-copy.sh [--channel prose|social] [--banned-terms FILE]
                     [--soft-terms FILE] [--allow-house-terms] <file>...

House terms (Rule 6) are optional and ship empty. Each terms file holds one
case-insensitive PCRE pattern per line; blank lines and lines starting with
# are ignored. The files can also be set with COPY_BANNED_TERMS and
COPY_SOFT_TERMS; a flag wins over the environment.

Exit codes:
  0  every hard check passed on every file
  1  at least one hard check failed (details printed)
  2  usage error, an input that is not a readable regular file, a host grep
     with no -P or no UTF-8 locale, or a grep error mid-run (never a silent pass)

Hard checks (fail): em/en dashes, curly quotes, emoji outside the channel
policy, house terms from --banned-terms (Rule 6), negation openers (S1),
the boundary-line metaphor (S17), reflective hand-holding phrases (Rule 3),
assistant tics (Rule 3).
Informational checks (print only): house terms from --soft-terms (Rule 6),
adjacent emoji pairs, banned words, arrival metaphors, filler,
copula-avoidance verbs, digestion metaphors, fake authority, transition
stacking, trailing participial clauses, label-colon bullets, false ranges,
stacked hedges, burstiness.

Channel policy for emoji:
  prose  (default)  any emoji fails
  social            emoji as a tone cue, end of line is the norm. Hard:
                    none on line 1, none at line start or after a bullet
                    marker, no emoji-only line, one per line (two separated
                    by text fails), at most four per file. Reported only:
                    an adjacent pair, and a mid-line emoji
USAGE
}

set -u
# grep -P needs a UTF-8 locale for the \x{...} code points. Prefer one the host
# actually has, under whichever spelling it lists: macOS prints C.UTF-8, glibc
# prints C.utf8. A self-test further down refuses to run if none of this worked.
utf8_locale=$(locale -a 2>/dev/null | grep -iE '^C\.(UTF-8|utf8)$' | head -1)
if [ -z "$utf8_locale" ]; then
  utf8_locale=$(locale -a 2>/dev/null | grep -iE '^en_US\.(UTF-8|utf8)$' | head -1)
fi
if [ -n "$utf8_locale" ]; then
  export LC_ALL="$utf8_locale"
fi

channel="prose"
allow_house_terms=0
banned_terms_file="${COPY_BANNED_TERMS:-}"
soft_terms_file="${COPY_SOFT_TERMS:-}"
files=()

while [ $# -gt 0 ]; do
  case "$1" in
    --channel)
      if [ $# -lt 2 ]; then
        echo "check-copy: --channel needs a value (prose or social)" >&2
        exit 2
      fi
      shift
      channel="$1"
      ;;
    --channel=*|--banned-terms=*|--soft-terms=*)
      set -- "${1%%=*}" "${1#*=}" "${@:2}"
      continue
      ;;
    --banned-terms|--soft-terms)
      if [ $# -lt 2 ]; then
        echo "check-copy: $1 needs a file path" >&2
        exit 2
      fi
      if [ "$1" = "--banned-terms" ]; then banned_terms_file="$2"; else soft_terms_file="$2"; fi
      shift
      ;;
    --allow-house-terms)
      allow_house_terms=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --*)
      echo "check-copy: unknown option $1" >&2
      exit 2
      ;;
    *)
      files+=("$1")
      ;;
  esac
  shift
done

if [ "${#files[@]}" -eq 0 ]; then
  echo "check-copy: no files given" >&2
  exit 2
fi
if [ "$channel" != "prose" ] && [ "$channel" != "social" ]; then
  echo "check-copy: --channel must be prose or social, got '$channel'" >&2
  exit 2
fi

# grep -P is required for the code-point classes. macOS system grep lacks it;
# prefer GNU grep from Homebrew when present.
GREP="grep"
if ! echo x | grep -qP 'x' 2>/dev/null; then
  if command -v ggrep >/dev/null 2>&1 && echo x | ggrep -qP 'x' 2>/dev/null; then
    GREP="ggrep"
  else
    echo "check-copy: this host's grep has no -P support (install GNU grep, e.g. brew install grep, or run in a container). Refusing to report a pass." >&2
    exit 2
  fi
fi
# Without a UTF-8 locale grep -P rejects \x{2014} with exit 2, every code-point
# check comes back empty, and the file would pass. Prove it works first.
if ! printf '\xe2\x80\x94\n' | $GREP -qP '\x{2014}' 2>/dev/null; then
  echo "check-copy: $GREP -P cannot match a UTF-8 code point in this locale (install a C.UTF-8 or en_US.UTF-8 locale, or set LC_ALL to one). Refusing to report a pass." >&2
  exit 2
fi

EMOJI_CLASS='\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}'
EMOJI="[${EMOJI_CLASS}]"
# One emoji as a reader sees it: a base code point plus any skin-tone modifiers
# (U+1F3FB-1F3FF), variation selectors and zero-width-joined parts, so a
# joined sequence or a toned hand counts once. Used inside an atomic group so
# the regex engine cannot split a sequence back into its parts.
EMOJI_TAIL='[\x{1F3FB}-\x{1F3FF}\x{FE0F}]*'
EMOJI_UNIT="(?>${EMOJI}${EMOJI_TAIL}(?:\x{200D}${EMOJI}${EMOJI_TAIL})*)"
DASHES='[\x{2014}\x{2013}]'
CURLY='[\x{2018}\x{2019}\x{201C}\x{201D}]'

# Turn a terms file into one alternation: \b(?:(?:a)|(?:b))\b. Prints nothing
# for an unset path or a file with no patterns.
terms_regex() {
  [ -n "$1" ] || return 0
  if [ ! -r "$1" ]; then
    echo "check-copy: cannot read terms file $1" >&2
    return 2
  fi
  local joined re rc=0
  joined=$(grep -v '^[[:space:]]*#' "$1" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' | awk 'NF' | sed 's/.*/(?:&)/' | paste -sd'|' -)
  [ -n "$joined" ] || return 0
  re=$(printf '\\b(?:%s)\\b' "$joined")
  echo x | "$GREP" -qPi "$re" 2>/dev/null || rc=$?
  if [ "$rc" -eq 2 ]; then
    echo "check-copy: a pattern in a terms file is not valid PCRE: $re" >&2
    return 2
  fi
  printf '%s' "$re"
}

HOUSE=$(terms_regex "$banned_terms_file") || exit 2
HOUSE_SOFT=$(terms_regex "$soft_terms_file") || exit 2
NEGATION='\b(nobody|no one) (asked|invented|built|owns|talks|told)'
BOUNDARY="(is the line|that'?s the line|walks? the line|where the line (sits|is)|crossing the line)"
REFLECTIVE="(keep coming back to|the part that (gets|got|stuck with) me|what struck me|what stuck with me|the interesting thing is|what i find fascinating)"
TICS="(i hope this helps|great question|you.?re absolutely right|happy to help|of course!|certainly!|^perfect!|^found it!)"

failures=0

# grep exits 1 for no match and 2 for an error. Checks run inside command
# substitutions, where an exit cannot stop the script, so g() records any error
# and the loop below stops with exit 2 instead of counting a blank as a pass.
grep_errors=$(mktemp) || exit 2
trap 'rm -f "$grep_errors"' EXIT
g() {
  local rc=0
  "$GREP" "$@" || rc=$?
  if [ "$rc" -gt 1 ]; then
    echo "check-copy: grep failed with exit $rc (arguments: $*)" >> "$grep_errors"
  fi
  return "$rc"
}

# fail/info <label> <matches>: report on the file being checked. info prints
# nothing when there are no matches.
fail() {
  echo "FAIL [$f] $1"
  printf '%s\n' "$2" | sed 's/^/    /'
  failures=$((failures + 1))
}

info() {
  if [ -n "$2" ]; then
    echo "info [$f] $1"
    printf '%s\n' "$2" | sed 's/^/    /'
  fi
}

# hard/soft <label> <grep arguments>: grep the file being checked; any match
# fails it (hard) or is only printed (soft).
hard() {
  local m
  m=$(g "${@:2}" "$f")
  [ -z "$m" ] || fail "$1" "$m"
}

soft() {
  info "$1" "$(g "${@:2}" "$f")"
}

check_file() {
  f="$1"
  # Every check re-reads the file, so it has to be a regular file: a directory
  # makes grep error out, and a pipe is empty after the first check. Either
  # would otherwise leave every check blank and read as a pass.
  if [ ! -f "$f" ] || [ ! -r "$f" ]; then
    echo "check-copy: $f is not a readable regular file" >&2
    exit 2
  fi

  hard "em or en dash (Rule 1, must be 0)" -nP "$DASHES"
  hard "curly quote or apostrophe (Rule 5, must be 0)" -nP "$CURLY"

  if [ "$channel" = "prose" ]; then
    hard "emoji in a prose channel (Rule 5, must be 0)" -nP "$EMOJI"
  else
    # Drop CRs first: a CRLF file would otherwise turn every blank line into a
    # whitespace-only line. Removing only CR bytes keeps the line numbers.
    if ! social=$(tr -d '\r' < "$f"); then
      echo "check-copy: could not read $f for the social checks. Refusing to report a pass." >&2
      exit 2
    fi
    sgrep() { printf '%s\n' "$social" | g "$@"; }
    m=$(printf '%s\n' "$social" | head -1 | g -nP "$EMOJI"); [ -n "$m" ] && fail "emoji on the first line (Rule 5 social clause)" "$m"
    m=$(sgrep -nP "^\s*(#+\s*)?${EMOJI}|^\s*[-*\x{2022}]\s*${EMOJI}|^(?=.*${EMOJI})[\s\x{FE0F}\x{200D}${EMOJI_CLASS}]+$")
    [ -n "$m" ] && fail "emoji at line start, after a bullet, or on an emoji-only line (Rule 5 social clause)" "$m"
    m=$(sgrep -nP "${EMOJI_UNIT}\s*[^\s\x{FE0F}\x{200D}${EMOJI_CLASS}].*${EMOJI}"); [ -n "$m" ] && fail "two emoji separated by text on one line (Rule 5 social clause: one per line)" "$m"
    info "adjacent emoji pair (Rule 5 social clause: a deliberate sign-off at most once)" "$(sgrep -nP "${EMOJI_UNIT}\s*${EMOJI}")"
    info "mid-line emoji (Rule 5 social clause: end of line is the norm, eyeball)" "$(sgrep -nP "${EMOJI_UNIT}\s*[^\s\x{FE0F}\x{200D}${EMOJI_CLASS}\x29\x5D.!?,:;\"']")"
    total=$(sgrep -oP "$EMOJI_UNIT" | wc -l | tr -d ' ')
    if [ "$total" -gt 4 ]; then
      fail "more than four emoji in one post (Rule 5 social clause)" "count=$total"
    fi
  fi

  if [ "$allow_house_terms" -eq 0 ] && [ -n "$HOUSE" ]; then
    hard "house term (Rule 6, from --banned-terms; --allow-house-terms turns this check off for the whole run, so pass it only once every match is confirmed to sit in a quoted title)" -nPi "$HOUSE"
  fi
  if [ -n "$HOUSE_SOFT" ]; then
    soft "house terms that are only wrong as a description of your own product (Rule 6, eyeball)" -nPi "$HOUSE_SOFT"
  fi
  hard "negation opener (S1)" -nPi "$NEGATION"
  hard "boundary-line metaphor (S17)" -nEi "$BOUNDARY"
  hard "reflective hand-holding phrase (Rule 3)" -nEi "$REFLECTIVE"
  hard "assistant tic (Rule 3)" -nEi "$TICS"

  soft "arrival metaphors (Rule 2)" -nPi '\b(land(ed|s|ing)?|converg(e|es|ed|ing)|coalesc(e|es|ed|ing)|arriv(e|ed|es) at|settl(e|ed|es) on|gravitat(e|ed|es) toward)\b'
  soft "banned words (Rule 2, sample)" -nPi '\b(leverage|seamless|robust|comprehensive|cutting-edge|delve|harness|unlock|empower|game-chang|revolutioniz|underscore|showcase|holistic|paradigm|ecosystem|testament)\w*'
  soft "filler phrases (Rule 3)" -nEi "(it'?s (important to note|worth (noting|mentioning))|at the end of the day|here'?s the (thing|kicker|catch)|turns out|under the hood|out of the box|in conclusion|let'?s dive)"
  soft "correction pairs (S2)" -nPi "((it'?s|it is) not [^.]*,? (it'?s|it is))|(never [^.]*\. *(they|it|that)\b)|(says nothing about)|(did ?n[o']?t [^.]*\. *it (became|was|is)\b)"
  soft "colon-fragment labels (S9)" -nEi '^(The (result|problem|catch|answer|reason|upshot|fix)):'
  soft "copula-avoidance verbs (Rule 2)" -nPi '\b(serves? as|stands? as|functions? as|represents?|boasts?|exemplif(y|ies)|epitomiz(e|es))\b'
  soft "digestion or erasure metaphors (Rule 2)" -nPi '\b(swallow(s|ed|ing)?|consum(e|es|ed|ing)|eras(e|es|ed|ing)|drown(s|ed|ing)? out|dissolv(e|es|ed|ing)|evaporat(e|es|ed|ing)|drain(s|ed|ing)?|bur(y|ies|ied))\b'
  soft "fake-authority phrases (Rule 3)" -nPi '\b(studies (have )?shown|research (indicates|shows)|experts agree|data suggests)\b'
  info "transition-word paragraph openers (count)" "$(g -cPi '^(Moreover|Furthermore|Additionally|Notably|Ultimately|Subsequently|Conversely)\b' "$f" | sed 's/^0$//')"
  soft "trailing participial clauses (S18)" -nPi ',[[:space:]]+(highlighting|ensuring|reflecting|showcasing|fostering|underscoring|demonstrating|allowing|enabling|cementing|solidifying|paving|positioning|signalling|signaling|marking|making it (easier|possible)|further)\b'
  soft "label-colon bullets (S19)" -nE '^[[:space:]]*[-*]?[[:space:]]*\*\*[^*]+:\*\*'
  soft "despite-challenges arc (S20)" -nEi '(despite [^.]{0,40}(challenge|hurdle|obstacle|headwind)|while challenges remain|not without its|continues to (thrive|grow|evolve|lead|accelerate))'
  soft "false ranges (S21, eyeball)" -nPi '(everything |anything )?\bfrom [a-z]+ to [a-z]+\b'
  soft "knowledge-limit disclaimers (Rule 3)" -nEi '(specific details are limited|based on available information|as of my last (update|training)|unclear from the (sources|available))'
  soft "filler connectives (Rule 3)" -nPi '\b(in order to|due to the fact that|for the purpose of|in the process of|it should be noted that|prior to|subsequent to)\b'
  soft "inflated synonyms (Rule 2)" -nPi '\b(utiliz(e|es|ed|ing|ation)|facilitat(e|es|ed|ing)|numerous|commenc(e|es|ed|ing)|ascertain|garner(s|ed|ing)?|enhanc(e|es|ed|ing|ement))\b'
  soft "abstract metaphor nouns (Rule 2)" -nPi '\b(substrate|wedge|vector|locus|vantage|primitive|scaffolding|modality|gold-plat|ratchet|endgame|north star|flywheel|api surface)\b'
  soft "stacked hedges (C5)" -nPi '\b(could|may|might|can) (potentially|possibly|perhaps|arguably|conceivably)\b'
  soft "prescribed vocabulary, cap one per document (Rule 4)" -nPi '\b(boring|underrated|unsexy)\b'
  info "burstiness, want above 0.40 (Part 7)" "$(tr '!?' '..' < "$f" | tr '.' '\n' | awk 'NF>2 {n++; s+=NF; q+=NF*NF} END {if (n>1) {m=s/n; sd=sqrt(q/n-m*m); printf "sentences=%d mean=%.1f sd=%.1f burstiness=%.2f", n, m, sd, sd/m}}')"
}

for f in "${files[@]}"; do
  check_file "$f"
  if [ -s "$grep_errors" ]; then
    cat "$grep_errors" >&2
    echo "check-copy: a check could not run on $f. Refusing to report a pass." >&2
    exit 2
  fi
done

if [ "$failures" -gt 0 ]; then
  echo "check-copy: $failures hard failure(s), channel=$channel"
  exit 1
fi
echo "check-copy: pass, channel=$channel, files=${#files[@]}"
exit 0
