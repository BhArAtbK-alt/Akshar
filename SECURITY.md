# Security

Akshar runs as a keyboard input method, so it sees what you type. Principles:

- Transliteration is fully offline and never sends keystrokes anywhere.
- Translate mode (opt-in, `F10`) sends the typed phrase to an online service unless you use the offline backend.
- Your learning data stays in `~/.config/akshar/userdict.json`.

## Reporting a Vulnerability

Found a vulnerability? Please do **not** open a public issue or discussion thread, as this exposes the flaw before it can be fixed.

Instead, please use **GitHub Private Vulnerability Reporting**:

1. Navigate to the main page of this repository on GitHub.
2. Click on the **Security** tab (located under the repository name).
3. In the left sidebar, click **Advisories**.
4. Click **Report a vulnerability** to securely submit the details directly to the project maintainers.

We take security seriously and will review your private report as quickly as possible.
