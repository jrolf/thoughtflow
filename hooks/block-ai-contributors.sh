#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# block-ai-contributors.sh
#
# Prevents commits from non-human identities and invalid email addresses.
# Called in three modes:
#
#   hooks/block-ai-contributors.sh identity
#       Checks GIT_AUTHOR_NAME, GIT_AUTHOR_EMAIL, GIT_COMMITTER_NAME,
#       GIT_COMMITTER_EMAIL against the AI blocklist AND validates that
#       email addresses look like real, routable addresses.
#
#   hooks/block-ai-contributors.sh message <commit-msg-file>
#       Scans the commit message for Co-authored-by / Made-with trailers
#       whose value matches the blocklist.
#
#   hooks/block-ai-contributors.sh email <address>
#       Standalone email validation (for testing).
#
# Blocklist and email rules are case-insensitive.  Edit arrays below to
# customize.
# ---------------------------------------------------------------------------

set -euo pipefail

# ---- AI identity blocklist -------------------------------------------------
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

# ---- Email domain blocklist ------------------------------------------------
# Patterns that indicate a non-routable, machine-generated, or bot email.
# Matched case-insensitively against the full email address.
BLOCKED_EMAIL_PATTERNS=(
    '.local$'
    '.internal$'
    '.localhost$'
    '.home$'
    '.lan$'
    '@localhost'
    'MacBook'
    'iMac'
    'Mac-Pro'
    'Mac-mini'
    'Mac-Studio'
    '@example\.com$'
    '@test\.com$'
    '@invalid$'
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

validate_email() {
    local email="$1"
    local lower
    lower="$(echo "$email" | tr '[:upper:]' '[:lower:]')"

    # Must contain exactly one @
    local at_count
    at_count=$(echo "$email" | tr -cd '@' | wc -c | tr -d ' ')
    if [ "$at_count" -ne 1 ]; then
        echo "not a valid email (missing or multiple @ signs)"
        return 1
    fi

    local domain="${lower##*@}"

    # Must have at least one dot in domain
    if ! echo "$domain" | grep -q '\.'; then
        echo "domain '$domain' has no TLD (not a routable address)"
        return 1
    fi

    # Check against blocked patterns
    for pattern in "${BLOCKED_EMAIL_PATTERNS[@]}"; do
        if echo "$lower" | grep -qiE "$pattern"; then
            echo "matches blocked pattern '$pattern'"
            return 1
        fi
    done

    return 0
}

# ---- Mode: identity -------------------------------------------------------
check_identity() {
    local failed=0

    # AI name/email blocklist
    for var in GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL; do
        val="${!var:-}"
        if [ -n "$val" ]; then
            if matched=$(matches_blocklist "$val"); then
                echo "BLOCKED: $var='$val' matches AI blocklist word '$matched'"
                failed=1
            fi
        fi
    done

    # Email validation (author and committer)
    for var in GIT_AUTHOR_EMAIL GIT_COMMITTER_EMAIL; do
        val="${!var:-}"
        if [ -n "$val" ]; then
            if reason=$(validate_email "$val"); then
                : # valid
            else
                echo "BLOCKED: $var='$val' — $reason"
                failed=1
            fi
        fi
    done

    if [ "$failed" -eq 1 ]; then
        echo ""
        echo "Commits must be attributed to a human with a valid email."
        echo ""
        echo "Fix with:  git config user.email 'you@yourdomain.com'"
        echo "           git config user.name  'Your Name'"
        echo ""
        echo "To update the rules: hooks/block-ai-contributors.sh"
        exit 1
    fi
}

# ---- Mode: message ---------------------------------------------------------
check_message() {
    local msgfile="$1"
    local failed=0

    while IFS= read -r line; do
        if echo "$line" | grep -qi '^Co-authored-by:'; then
            if matched=$(matches_blocklist "$line"); then
                echo "BLOCKED: commit message contains non-human co-author trailer:"
                echo "  $line"
                echo "  (matched blocklist word '$matched')"
                failed=1
            fi
        fi
        if echo "$line" | grep -qiE '^(Made-with|Generated-by|Assisted-by|Created-with):'; then
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
        echo "To update the rules: hooks/block-ai-contributors.sh"
        exit 1
    fi
}

# ---- Mode: email (standalone test) -----------------------------------------
check_email_standalone() {
    local email="$1"
    if reason=$(validate_email "$email"); then
        echo "OK: '$email' is a valid commit email"
    else
        echo "BLOCKED: '$email' — $reason"
        exit 1
    fi
}

# ---- Dispatch --------------------------------------------------------------
case "${1:-}" in
    identity) check_identity ;;
    message)  check_message "${2:?'Usage: block-ai-contributors.sh message <file>'}" ;;
    email)    check_email_standalone "${2:?'Usage: block-ai-contributors.sh email <address>'}" ;;
    *)
        echo "Usage: block-ai-contributors.sh {identity|message <file>|email <address>}"
        exit 1
        ;;
esac
