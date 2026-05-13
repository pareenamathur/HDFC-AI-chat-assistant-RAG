from typing import List, Dict, Any

class ContextBuilder:
    """Formats retrieved results into context for the LLM."""

    @staticmethod
    def build_context(results: List[Dict[str, Any]], intent: str = None) -> str:
        """
        Assembles chunks and metadata into a clean context string.
        Groups results by scheme so the LLM receives clearly labelled sections
        for every fund mentioned in the query.

        Args:
            results: List of result dicts from the retriever.
            intent: Detected intent to highlight specific metadata.
        """
        if not results:
            return "No relevant context found."

        # Group results by scheme_name to produce one section per fund
        from collections import defaultdict
        grouped: dict = defaultdict(list)
        order: list = []  # preserve insertion order
        for res in results:
            meta = res.get("metadata") or {}
            sn = meta.get("scheme_name", "Unknown Scheme")
            if sn not in grouped:
                order.append(sn)
            grouped[sn].append(res)

        context_blocks = []
        global_idx = 1  # continuous source counter across sections

        for scheme_name in order:
            context_blocks.append(f"=== FUND: {scheme_name} ===")
            for res in grouped[scheme_name]:
                meta = res.get("metadata") or {}
                text = (res.get("text") or "").strip()

                # Enrich with structured data if relevant to intent
                structured_info = []
                if intent:
                    sd_key = f"sd_{intent}"
                    if sd_key in meta:
                        structured_info.append(
                            f"Factual {intent.replace('_', ' ')}: {meta[sd_key]}"
                        )

                # Common fields to always include if present
                for field in ["expense_ratio", "exit_load", "nav", "risk_level"]:
                    if field in meta and meta[field]:
                        structured_info.append(
                            f"{field.replace('_', ' ').title()}: {meta[field]}"
                        )

                block = (
                    f"[Source {global_idx}]: {meta.get('source_url', 'Unknown Source')} "
                    f"(Updated: {meta.get('last_updated_date', 'Unknown')})\n"
                )
                if structured_info:
                    block += "Factual Highlights: " + " | ".join(set(structured_info)) + "\n"
                block += f"Content: {text.strip()}"

                context_blocks.append(block)
                global_idx += 1

        return "\n\n".join(context_blocks)

if __name__ == "__main__":
    # Test
    sample_results = [
        {
            "text": "The exit load for this fund is 1% if redeemed within 1 year.",
            "metadata": {
                "scheme_name": "HDFC Flexi Cap",
                "source_url": "hdfc_flexi.html",
                "sd_exit_load": "1% if < 1 year",
                "exit_load": "1%"
            }
        }
    ]
    builder = ContextBuilder()
    print(builder.build_context(sample_results, intent="exit_load"))
