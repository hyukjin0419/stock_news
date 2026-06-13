"""
뉴스 본문 → Claude로 (관련성 판정 + 한국어 요약)을 한 번에.
relevant=false면 호출자가 해당 기사를 버린다.
"""
import json

from litellm import completion

MODEL = "anthropic/claude-haiku-4-5-20251001"
MAX_BODY_CHARS = 6000


def analyze(item, stock_name: str) -> bool:
    """
    item.summary 를 채우고, 이 기사가 stock_name 종목에 관한 것인지 bool 반환.
    실패 시 보수적으로 True + api_summary 폴백(놓치는 것보단 낫게).
    """
    body = item.body[:MAX_BODY_CHARS]
    prompt = (
        f"아래 뉴스가 '{stock_name}' 종목 보유자가 볼 만한 기사인지 판정하고, "
        f"맞다면 한국어로 3문장 이내로 요약해줘.\n"
        f"- keep(relevant=true): 그 종목이 주제이거나, **그 종목이 당사자로 얽힌** "
        f"거래·실적·제품·계약·규제 등 실질적 뉴스.\n"
        f"- drop(relevant=false): 단순 언급, 'Mag 7' 같은 섹터 묶음, "
        f"다른 종목 기사에서 비교 대상으로만 등장하는 경우.\n"
        f"- 요약은 본문 사실만. 추측·투자권유 금지.\n"
        f'다음 JSON만 출력: {{"relevant": true/false, "summary": "..."}}\n\n'
        f"제목: {item.title}\n\n본문:\n{body}"
    )
    try:
        res = completion(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=600,
        )
        parsed = _parse_json(res.choices[0].message.content)
        if parsed is None:
            item.summary = item.api_summary
            return True
        item.summary = parsed.get("summary", "") or item.api_summary
        return bool(parsed.get("relevant", True))
    except Exception as e:
        print(f"  ⚠️ 분석 실패 ({item.title[:30]}): {e}")
        item.summary = item.api_summary
        return True


def make_digest(items: list) -> dict | None:
    """
    회원의 오늘자 뉴스 전체를 종합해 호재/악재/액션으로 정리.
    {"호재":[...], "악재":[...], "액션":[...]} 또는 실패/빈입력 시 None.
    '액션'은 매매 지시가 아니라 주목·확인할 포인트.
    """
    if not items:
        return None
    lines = "\n".join(f"- [{i.title}] {i.summary}" for i in items)
    prompt = (
        "아래는 한 투자자의 관심종목 오늘자 뉴스 요약 모음이야. "
        "이를 종합해서 다음 셋으로 정리해줘.\n"
        "- 호재: 주가에 긍정적일 수 있는 사실들 (없으면 빈 배열)\n"
        "- 악재: 부정적일 수 있는 사실들 (없으면 빈 배열)\n"
        "- 액션: 투자자가 앞으로 주목하거나 확인하면 좋을 포인트. "
        "매수/매도 같은 지시는 절대 금지, '~를 지켜볼 것' 형태로만.\n"
        "각 항목은 짧은 한국어 문장. 사실 기반, 추측 금지.\n"
        '다음 JSON만 출력: {"호재":["..."],"악재":["..."],"액션":["..."]}\n\n'
        f"{lines}"
    )
    try:
        res = completion(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=800,
        )
        return _parse_json(res.choices[0].message.content)
    except Exception as e:
        print(f"  ⚠️ 다이제스트 실패: {e}")
        return None


def _parse_json(raw: str) -> dict | None:
    try:
        clean = raw.strip()
        if "```" in clean:
            clean = clean.split("```")[1].replace("json", "", 1).strip()
        start, end = clean.find("{"), clean.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        return json.loads(clean[start:end])
    except Exception:
        return None
