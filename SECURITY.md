# Security

## Reporting a problem

Please report it privately. On this repository's GitHub page, open the **Security** tab and click **Report a vulnerability**. Please do not open a public issue for a security problem.

Tell us what you found, how to reproduce it and what it affects. This is a two-person hackathon project, so we cannot promise a response time. We will reply as soon as we can.

## In scope

- The code in this repository.
- The deployed site, https://bhoomi.earth, including its `/api/` routes and the MCP endpoint at `/mcp/`.

The data providers' own services, the hosting provider and the AI model providers are out of scope. Please report problems with those to them.

## Keys

No key is stored in this repository. Keys load from environment variables only, and `.env.example` lists the names with no values. Every pull request is scanned for secrets. If you find a key or token in the code or in the git history, please report it the same way.

## Abuse

The Ask tab (`POST /api/ask`) calls a paid AI model for every question. It is rate limited, but reports of abuse, or of a way around the limit, are welcome.
