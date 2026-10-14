# Feishu Final Verification

Current status: `PENDING`

This document records the future final verification flow only. Do not configure real Feishu credentials in the repository.

## Steps

1. Configure `FEISHU_BOT_WEBHOOK_URL` locally.
2. Run the default smoke test.
3. Verify PENDING / 0 sends.
4. Run the smoke test with explicit confirmation send.
5. Verify confirmation is `CONFIRMED`.
6. Verify exactly one provider attempt.
7. Verify the Feishu client receives exactly one message.
8. Only after that evidence exists, replace the current PENDING entries in the status manifest and consider whether the overall portfolio can be described as fully verified. Until then, do not make either claim.
