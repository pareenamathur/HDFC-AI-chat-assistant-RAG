# Phase 5 — Evaluation, Compliance & Observability Edge Cases

*Focus: System reliability, safety, and operational excellence.*

---

## **5a. Evaluation Harness**

### **EC 5a.1: Test Data Drift**
- **Scenario**: Evaluation test cases become outdated compared to current corpus.
- **Mitigation**: Periodic review and refresh of evaluation test suite.

### **EC 5a.2: RAGAS Metric Failure**
- **Scenario**: Faithfulness or relevance scores drop below acceptable threshold.
- **Mitigation**: Automated alerting and root cause analysis pipeline.

### **EC 5a.3: Performance Regression**
- **Scenario**: Latency increases beyond 2s target due to corpus growth.
- **Mitigation**: Implement caching, query optimization, or corpus pruning strategies.

---

## **5b. Compliance Checks (CI Gate)**

### **EC 5b.1: False Negatives in Advice Detection**
- **Scenario**: Advisory queries slip through the intent classifier.
- **Mitigation**: Regular adversarial testing and classifier retraining with new patterns.

### **EC 5b.2: CI Pipeline Failures**
- **Scenario**: Compliance checks fail intermittently due to flaky tests or API issues.
- **Mitigation**: Implement test retry logic and mock external dependencies in CI.

### **EC 5b.3: Constraint Enforcement Bypass**
- **Scenario**: Post-processing validator fails to catch constraint violations.
- **Mitigation**: Implement multiple validation layers with different approaches.

---

## **5c. Observability**

### **EC 5c.1: Log Volume Explosion**
- **Scenario**: High query volume generates excessive logs, increasing costs.
- **Mitigation**: Implement log sampling, aggregation, and retention policies.

### **EC 5c.2: Alert Fatigue**
- **Scenario**: Too many low-priority alerts cause important issues to be missed.
- **Mitigation**: Implement alert severity classification and suppression rules.

### **EC 5c.3: Metrics Dashboard Latency**
- **Scenario**: Observability dashboard becomes slow due to data volume.
- **Mitigation**: Implement data downsampling and pre-aggregation for dashboard queries.

---

## **5d. Operational Runbook**

### **EC 5d.1: Rollback Failure**
- **Scenario**: Corpus rollback fails due to backup corruption or incompatibility.
- **Mitigation**: Implement multiple backup versions and test rollback procedures regularly.

### **EC 5d.2: Onboarding Complexity**
- **Scenario**: New team members struggle to understand operational procedures.
- **Mitigation**: Maintain detailed, up-to-date documentation with runbooks and decision trees.

### **EC 5d.3: Incident Escalation Delays**
- **Scenario**: Critical incidents are not escalated promptly due to unclear ownership.
- **Mitigation**: Define clear on-call rotation and escalation matrices with contact information.
