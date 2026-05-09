# Phase 0.3 — Guardrails Definition

## Content Policy

**Core Principle**: Facts-only, no investment advice, no recommendations

**Allowed**:
- Factual information about mutual fund schemes (expense ratios, exit loads, SIP amounts, etc.)
- Process information (how to download statements, how to invest, etc.)
- Documented scheme details from official sources
- Links to official documentation for detailed information

**Prohibited**:
- Investment advice or recommendations ("Should I invest in this fund?")
- Performance comparisons or return calculations
- Opinions on fund quality or suitability
- Predictions about future performance
- Personalized financial advice

## Response Constraints

**Maximum Length**: 3 sentences per answer

**Citation Requirement**: Exactly one official source link per response

**Mandatory Footer**: `Last updated from sources: <Date>`

**Rationale**:
- Short responses reduce risk of hallucination or misinterpretation
- Single citation ensures traceability and accountability
- Footer indicates data freshness and manages user expectations

## Privacy Policy

**No PII Collection**:
- PAN numbers (including obfuscated formats)
- Aadhaar numbers
- Phone numbers
- Email addresses
- Account numbers
- OTPs or verification codes

**Implementation**:
- PII filtering middleware in API layer
- No logging of user-identifiable information
- Sanitization of all input queries

**Rationale**:
- Regulatory compliance (SEBI guidelines)
- User trust and data protection
- Simpler compliance with data privacy laws

## Source Policy

**Allowed Sources**:
- AMC official websites (HDFC Mutual Fund)
- AMFI (Association of Mutual Funds in India)
- SEBI (Securities and Exchange Board of India)
- Official scheme documentation (Factsheets, KIM, SID)

**Prohibited Sources**:
- Third-party blogs or aggregator websites
- Social media posts or forums
- News articles or opinion pieces
- Unverified or unofficial sources

**Rationale**:
- Ensures accuracy and reliability
- Regulatory compliance
- Maintains trust in the assistant
- Reduces risk of misinformation

## Enforcement Mechanisms

1. **Intent Classification**: LLM-based classifier to detect advisory queries
2. **Guardrail LLM**: Separate model to scan for adversarial intent
3. **URL Validation**: Whitelist of approved domains
4. **Post-processing Validators**: Enforce length, citation, and footer constraints
5. **CI/CD Gates**: Automated compliance checks in deployment pipeline
