# EmailMessage should block `bcc` in `extra_headers` and docs should not suggest `bcc` is a header

Following a security report deemed invalid, there are two related improvements to `EmailMessage` that we should pursue:

1. Add `bcc` to the `extra_headers` blocklist: `EmailMessage.message()` already blocks `from`, `to`, `cc`, and `reply-to` from being written into MIME headers via `extra_headers`, but `bcc` is missing.

2. Clarify docs to avoid saying that `bcc` is a "header": docs describe it as addresses used in the "Bcc header," which is inaccurate. Bcc addresses are passed to the SMTP server as RCPT TO recipients and never written into the MIME message -- there is no Bcc header in the outgoing message. The word "header" should be removed from that description.

Reported in django ticket #37152: https://code.djangoproject.com/ticket/37152
