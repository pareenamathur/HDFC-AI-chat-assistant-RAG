# Phase 4 — User Interface (Minimal Web App) Edge Cases

*Focus: UX, responsiveness, and user trust.*

---

## **EC 4.1: Rendering Long URLs**
- **Scenario**: The source citation URL is extremely long and breaks the chat layout on mobile.
- **Mitigation**: Use CSS `word-break: break-all;` and implement a "Copy Link" or "View Source" button instead of raw URLs.

---

## **EC 4.2: Markdown Parsing Errors**
- **Scenario**: LLM returns malformed markdown (e.g., unclosed bold tags).
- **Mitigation**: Use a robust markdown parser component (like `react-markdown`) that handles malformed input gracefully.

---

## **EC 4.3: Slow Response Feedback**
- **Scenario**: Retrieval takes 5 seconds, making the user think the app is frozen.
- **Mitigation**: Implement a "Thinking..." state with a skeleton screen and progress indicators for "Retrieving" vs "Generating".

---

## **EC 4.4: Mobile Responsiveness**
- **Scenario**: Chat interface breaks on small screens or different orientations.
- **Mitigation**: Implement responsive design with proper viewport meta tags and mobile-first CSS.

---

## **EC 4.5: Accessibility Issues**
- **Scenario**: Screen readers cannot properly parse the chat interface or citations.
- **Mitigation**: Add ARIA labels, semantic HTML, and keyboard navigation support.
