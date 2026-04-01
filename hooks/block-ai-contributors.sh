#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# block-ai-contributors.sh
#
# Prevents commits from non-human identities.  Called in two modes:
#
#   hooks/block-ai-contributors.sh identity
#       Checks GIT_AUTHOR_NAME, GIT_AUTHOR_EMAIL, GIT_COMMITTER_NAME,
#       GIT_COMMITTER_EMAIL against the blocklist.
#
#   hooks/block-ai-contributors.sh message <commit-msg-file>
#       Scans the commit message for Co-authored-by / Made-with trailers
#       whose value matches the blocklist.
#
# Blocklist is case-insensitive.  Add terms below to extend.
# ---------------------------------------------------------------------------

set -euo pipefail

BLOCKED_WORDS=(
    cursor
    clod
    claude
    copilot
    devin
    codex
    codeium
    coderabbit
    sourcegraph
    tabnine
    cursoragent
    github-actions
)

matches_blocklist() {
    local value
    value="$(echo "$1" | tr '[:upper:]' '[:lower:]')"
    for word in "${BLOCKED_WORDS[@]}"; do
        if [[ "$value" == *"$word"* ]]; then
            echo "$word"
            return 0
        fi
    done
    return 1
}

# ---- Mode: identity -------------------------------------------------------
check_identity() {
    local failed=0
    for var in GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL; do
        val="${!var:-}"
        if [ -n "$val" ]; then
            if matched=$(matches_blocklist "$val"); then
                echo "BLOCKED: $var='$val' matches blocklist word '$matched'"
                failed=1
            fi
        fi
    done

    if [ "$failed" -eq 1 ]; then
        echo ""
        echo "Commits must be attributed to a human contributor."
        echo "If this is wrong, update hooks/block-ai-contributors.sh."
        exit 1
    fi
}

# ---- Mode: message ---------------------------------------------------------
check_message() {
    local msgfile="$1"
    local failed=0

    while IFS= read -r line; do
        # Check Co-authored-by trailers
        if echo "$line" | grep -qi '^Co-authored-by:'; then
            if matched=$(matches_blocklist "$line"); then
                echo "BLOCKED: commit message contains non-human co-author trailer:"
                echo "  $line"
                echo "  (matched blocklist word '$matched')"
                failed=1
            fi
        fi
        # Check Made-with / Generated-by style trailers
        if echo "$line" | grep -qiE '^(Made-with|Generated-by|Assisted-by):'; then
            if matched=$(matches_blocklist "$line"); then
                echo "BLOCKED: commit message contains AI attribution trailer:"
                echo "  $line"
                echo "  (matched blocklist word '$matched')"
                failed=1
            fi
        fi
    done < "$msgfile"

    if [ "$failed" -eq 1 ]; then
        echo ""
        echo "Commit messages must not attribute AI tools as co-authors."
        echo "If this is wrong, update hooks/block-ai-contributors.sh."
        exit 1
    fi
}

# ---- Dispatch --------------------------------------------------------------
case "${1:-}" in
    identity) check_identity ;;
    message)  check_message "${2:?'Usage: block-ai-contributors.sh message <file>'}" ;;
    *)
        echo "Usage: block-ai-contributors.sh {identity|message <file>}"
        exit 1
        ;;
esac
