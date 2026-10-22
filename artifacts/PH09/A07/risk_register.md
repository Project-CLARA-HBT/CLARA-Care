# Risk Register — PH09 A07 (Mobile Pending Job Tracking)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH09-A07-01 | Dead-lettered jobs cluttering patient active notification list | Medium | Low | API query filters strictly on `status.in_(["pending", "processing"])`. | Mitigated |
| RISK-PH09-A07-02 | Slow polling query table scan across large historical outbox table | High | Low | Indexed `profile_id` and composite `status` index on `lifemap_outbox_events`. | Mitigated |
