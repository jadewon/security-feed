"""
Gemma LLM 분석기
Google AI의 Gemma 모델을 사용하여 보안 관련성 분석
"""

import json
import os
import re
from typing import List, Optional

from google import genai

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])
from models import FeedItem, AnalysisResult


class GemmaAnalyzer:
    """Gemma LLM 분석기"""

    PROMPT_TEMPLATE = """이 보안 취약점/뉴스에서 **영향받는 제품명**을 추출하세요.

## 기사 정보
제목: {title}
내용: {description}

## 추출 규칙
- 취약점이 발생한 정확한 제품/라이브러리/프레임워크 이름을 추출
- 일반적인 기술명이 아닌 구체적인 제품명 추출
- 예시:
  - "RedisGraph 2.x 취약점" → affected_product: "redisgraph"
  - "NestJS 인증 우회" → affected_product: "nestjs"
  - "Spring Boot Actuator 취약점" → affected_product: "spring boot"
  - "n8n 원격 코드 실행" → affected_product: "n8n"
  - "AWS EKS 권한 상승" → affected_product: "eks"
  - "FortiOS SSL VPN 취약점" → affected_product: "fortios"

## 추가 정보 추출
- 심각도 (critical/high/medium/low)
- 한줄 요약 (한글, 50자 이내)

JSON 형식으로만 응답:
{{"affected_product": "제품명", "severity": "심각도", "summary": "요약"}}"""

    def __init__(
        self,
        api_key: str = None,
        whitelist: List[str] = None,
        model: str = "gemma-3-12b-it",
    ):
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY가 설정되지 않았습니다")

        self.client = genai.Client(api_key=self.api_key)
        self.whitelist = [w.lower() for w in (whitelist or [])]
        self.model = model

    def analyze(self, item: FeedItem) -> Optional[AnalysisResult]:
        """항목 분석"""
        try:
            prompt = self._build_prompt(item)
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
            )

            return self._parse_response(response.text)

        except Exception as e:
            print(f"[ERROR] LLM 분석 실패: {e}")
            return None

    def _build_prompt(self, item: FeedItem) -> str:
        """프롬프트 생성"""
        return self.PROMPT_TEMPLATE.format(
            title=item.title,
            description=item.description[:1000],
        )

    def _parse_response(self, response_text: str) -> Optional[AnalysisResult]:
        """LLM 응답 파싱 및 화이트리스트 비교"""
        try:
            # JSON 블록 추출 (```json ... ``` 형식 처리)
            json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 중괄호로 둘러싸인 JSON 찾기
                json_match = re.search(r"\{[^{}]*\}", response_text)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    print(f"[WARN] JSON 파싱 실패: {response_text[:200]}")
                    return None

            data = json.loads(json_str)

            # 추출된 제품명
            affected_product = str(data.get("affected_product", "")).lower().strip()

            # 화이트리스트 비교
            is_relevant = self._check_whitelist(affected_product)

            return AnalysisResult(
                is_relevant=is_relevant,
                tech=affected_product,
                severity=str(data.get("severity", "low")).lower(),
                action_required=is_relevant and data.get("severity", "").lower() in ["critical", "high"],
                summary=str(data.get("summary", "")),
                raw_response=response_text,
            )

        except json.JSONDecodeError as e:
            print(f"[WARN] JSON 파싱 오류: {e}")
            return None

    def _check_whitelist(self, product: str) -> bool:
        """제품명이 화이트리스트에 있는지 확인 (단어 경계 기반)"""
        if not product or product == "none":
            return False

        product_lower = product.lower()

        # 제품명을 토큰으로 분리 (-, _, 공백 기준)
        product_tokens = set(re.split(r'[-_\s]', product_lower))

        for item in self.whitelist:
            # 정확히 일치
            if item == product_lower:
                return True

            # 화이트리스트 항목이 제품 토큰 중 하나와 일치
            # 예: "kubernetes" in ["kubernetes", "csi", "proxy"] → True
            if item in product_tokens:
                return True

            # 화이트리스트 항목의 토큰들이 제품 토큰에 모두 포함되어 있으면 매칭
            # 예: "spring boot" → ["spring", "boot"]
            #     "spring-boot-actuator" → ["spring", "boot", "actuator"]
            #     ["spring", "boot"].issubset(["spring", "boot", "actuator"]) → True
            item_tokens = set(re.split(r'[-_\s]', item))
            if len(item_tokens) > 1 and item_tokens.issubset(product_tokens):
                return True

            # 화이트리스트 항목의 토큰과 제품명 비교 (단일 토큰일 때)
            if product_lower in item_tokens:
                return True

        return False

    def analyze_batch(self, items: List[FeedItem]) -> List[tuple[FeedItem, Optional[AnalysisResult]]]:
        """여러 항목 분석 (순차 처리)"""
        results = []
        for item in items:
            result = self.analyze(item)
            results.append((item, result))
            print(f"[INFO] 분석 완료: {item.title[:50]}... → {result.severity if result else 'failed'}")
        return results
