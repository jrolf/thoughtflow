# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in ThoughtFlow, please report it responsibly:

1. **Do NOT** open a public GitHub issue for security vulnerabilities
2. Email security concerns to: james@think.dev
3. Include a detailed description of the vulnerability
4. If possible, include steps to reproduce

We will acknowledge receipt within 48 hours and aim to provide a fix within 7 days for critical issues.

## Security Considerations

ThoughtFlow handles interactions with LLM providers and potentially sensitive data. Users should:

- **Never commit API keys** to version control
- Use environment variables or secret management for credentials
- Be aware that trace logs may contain sensitive conversation data
- Review tool implementations for potential security implications
