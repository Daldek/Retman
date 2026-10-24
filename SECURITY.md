# Security policy

## Supported versions

Security fixes go into the latest release of Retman and into the development branch
`develop`. Older releases are not patched.

## Reporting a vulnerability

Please do not report vulnerabilities in public issues or pull requests.

Use GitHub's private vulnerability reporting: open the **Security** tab of
<https://github.com/Daldek/Retman>, choose **Report a vulnerability** and describe the
problem, the affected version and, if possible, how to reproduce it. You get an answer
as soon as the maintainer can read the report; a fix is released as a patch version and
credited in the CHANGELOG unless you prefer otherwise.

## Scope

Retman sends the text of a command to the model server that the user configures, and
calls Kartograf and IMGWTools only after the user has confirmed a plan. Reports about
the confirmation gate (a way to run a tool without a confirmed plan), the handling of
paths and geometry files, text of commands or answers reaching the technical log or the
collection file without consent, or the supply chain of the package are in scope. The
model server and the data tools have their own policies.
