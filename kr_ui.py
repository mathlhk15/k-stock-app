import json as _json

def _call_claude(prompt):
    try:
        body = _json.dumps({
            "model": "claude-opus-4-5",
            "max_tokens": 800,
            "messages": [{"role": "user", "content": prompt}]
        }, ensure_ascii=False).encode("utf-8")
        r = _req.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "x-api-key": st.secrets.get("ANTHROPIC_API_KEY", ""),
                "anthropic-version": "2023-06-01",
            },
            data=body,
            timeout=30,
        )
        d = r.json()
        if "error" in d:
            return f"오류: {d['error'].get('message', d['error'])}"
        return "".join(b["text"] for b in d.get("content", []) if b.get("type") == "text")
    except Exception as e:
        return f"오류: {e}"

def _call_gpt(prompt):
    try:
        body = _json.dumps({
            "model": "gpt-4o-mini",
            "max_tokens": 800,
            "messages": [{"role": "user", "content": prompt}]
        }, ensure_ascii=False).encode("utf-8")
        r = _req.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {st.secrets.get('OPENAI_API_KEY', '')}",
            },
            data=body,
            timeout=30,
        )
        d = r.json()
        if "error" in d:
            return f"오류: {d['error'].get('message', d['error'])}"
        choices = d.get("choices")
        if not choices:
            return f"오류: 응답 없음 ({d})"
        return choices[0]["message"]["content"]
    except Exception as e:
        return f"오류: {e}"

def _call_gemini(prompt):
    try:
        _key = st.secrets.get("GEMINI_API_KEY", "")
        body = _json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 800}
        }, ensure_ascii=False).encode("utf-8")
        r = _req.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={_key}",
            headers={"Content-Type": "application/json; charset=utf-8"},
            data=body,
            timeout=30,
        )
        d = r.json()
        if "error" in d:
            return f"오류: {d['error'].get('message', d['error'])}"
        candidates = d.get("candidates")
        if not candidates:
            return f"오류: 응답 없음 ({d})"
        return candidates[0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"오류: {e}"
