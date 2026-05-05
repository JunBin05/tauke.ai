import os
import time
from fastapi import HTTPException
import requests
import json
from typing import Any, List, Optional


def get_zhipu_api_key() -> str:
    api_key =os.getenv("ZHIPUAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Missing ZHIPU_API_KEY or ZHIPUAI_API_KEY environment variable",
        )
    return api_key


def _extract_model_text(raw_content: Any) -> str:
    if raw_content is None:
        return ""

    if isinstance(raw_content, str):
        return raw_content.strip()

    if isinstance(raw_content, dict):
        text_value = raw_content.get("text")
        if isinstance(text_value, str):
            return text_value.strip()

        content_value = raw_content.get("content")
        if content_value is not None:
            return _extract_model_text(content_value)

        return ""

    if isinstance(raw_content, list):
        parts: List[str] = []
        for part in raw_content:
            extracted = _extract_model_text(part)
            if extracted:
                parts.append(extracted)
        return "\n".join(parts).strip()

    return str(raw_content).strip()


def _parse_model_json(raw_text: str, source_name: str, required_kind: Optional[str] = None) -> Any:
    """Parse JSON from an LLM response, tolerating preamble text and markdown fences."""
    if not isinstance(raw_text, str):
        raise HTTPException(status_code=502, detail=f"{source_name} returned non-text output before JSON parsing")

    if not raw_text.strip() or raw_text.strip().lower() in {"none", "null"}:
        raise HTTPException(status_code=502, detail=f"{source_name} returned empty output before JSON parsing")

    want_array = required_kind == "array"
    cleaned = _extract_json_from_text(raw_text, want_array=want_array)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        # Attempt to repair truncated JSON by closing unclosed braces/brackets
        repaired = _repair_truncated_json(cleaned)
        try:
            data = json.loads(repaired)
            print(f"[JSON Repair] Recovered truncated JSON for {source_name}")
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=502,
                detail=f"{source_name} returned invalid JSON: {exc}. Raw (first 300): {raw_text[:300]}"
            ) from exc

    if required_kind == "object" and not isinstance(data, dict):
        raise HTTPException(status_code=502, detail=f"{source_name} returned invalid JSON schema: expected object")
    if required_kind == "array" and not isinstance(data, list):
        raise HTTPException(status_code=502, detail=f"{source_name} returned invalid JSON schema: expected array")

    return data


def _extract_json_from_text(raw_text: str, want_array: bool = False) -> str:
    """Multi-strategy JSON extractor — handles preamble text, markdown fences, truncated fences."""
    # Strategy 1: plain strip of fences
    candidate = _strip_markdown_fences(raw_text)
    try:
        json.loads(candidate)
        return candidate
    except json.JSONDecodeError:
        pass

    # Strategy 2: find the first { or [ and last } or ]
    open_char, close_char = ("[", "]") if want_array else ("{", "}")
    start = raw_text.find(open_char)
    end = raw_text.rfind(close_char)
    if start != -1 and end != -1 and end > start:
        candidate = raw_text[start : end + 1]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # Strategy 3: try the stripped candidate anyway (e.g. trailing garbage after })
    for open_c, close_c in [("{" , "}"), ("[", "]")]:
        s = raw_text.find(open_c)
        e = raw_text.rfind(close_c)
        if s != -1 and e != -1 and e > s:
            try:
                json.loads(raw_text[s : e + 1])
                return raw_text[s : e + 1]
            except json.JSONDecodeError:
                pass

    # Strategy 4: return stripped as last resort (let caller raise a clear error)
    return candidate


def _repair_truncated_json(text: str) -> str:
    """
    Attempt to repair JSON that was cut off mid-stream (e.g. by max_tokens).
    Strategy: strip everything after the last cleanly-closed value, then
    close any unclosed braces/brackets in reverse order.
    """
    if not text:
        return text

    # Step 1: truncate at the last position that ends a clean value
    # Walk backwards from the end to find the last } or ] or " or digit
    t = text.rstrip()
    # Remove any trailing comma, colon, or partial key
    import re as _re
    # Strip trailing incomplete tokens: comma, colon, partial string, whitespace
    t = _re.sub(r'[,:\s]*$', '', t)
    # If we ended mid-string (odd number of unescaped quotes), strip the open string
    # Count quotes not preceded by backslash
    in_string = False
    escape_next = False
    for ch in t:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\':
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
    if in_string:
        # Remove back to the last unescaped opening quote
        last_quote = max(t.rfind('"'), 0)
        t = t[:last_quote].rstrip().rstrip(',').rstrip()

    # Step 2: close any open structures
    stack = []
    in_string = False
    escape_next = False
    for ch in t:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in '{[':
            stack.append('}' if ch == '{' else ']')
        elif ch in '}]':
            if stack:
                stack.pop()

    # Append the closing tokens in reverse
    closing = ''.join(reversed(stack))
    return t + closing


def _strip_markdown_fences(text: str) -> str:
    """Remove any surrounding markdown code fences from an LLM response."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        cleaned = cleaned[first_newline + 1:] if first_newline != -1 else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
    return cleaned


