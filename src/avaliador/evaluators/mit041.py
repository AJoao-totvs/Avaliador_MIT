"""
MIT041 (Blueprint/Desenho da Solucao) evaluator.

Evaluates MIT041 documents against quality criteria.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from avaliador.config import settings
from avaliador.evaluators.base import BaseEvaluator
from avaliador.knowledge_base.loader import get_prompt, load_criteria
from avaliador.knowledge_base.references import get_reference_prompt
from avaliador.llm import DTAError, DTAProxyClient
from avaliador.models.schemas import (
    EvaluationMetadata,
    EvaluationResult,
    ExtractionResult,
    MITType,
    PillarScore,
)

logger = logging.getLogger(__name__)


class MIT041Evaluator(BaseEvaluator):
    """
    Evaluator for MIT041 (Desenho da Solucao / Blueprint) documents.

    Evaluates against three pillars:
    - P1: Completude Estrutural (30%)
    - P2: Qualidade das Regras e Fluxos (40%)
    - P3: Governanca e Aceite (30%)
    """

    mit_type = MITType.MIT041
    min_passing_score = 8.0

    def __init__(
        self,
        llm_client: Optional[DTAProxyClient] = None,
        use_references: bool = True,
    ):
        """
        Initialize MIT041 evaluator.

        Args:
            llm_client: DTA Proxy client. Created automatically if not provided.
            use_references: Whether to include good MIT samples as reference examples.
        """
        self._llm_client = llm_client
        self._criteria = None
        self.use_references = use_references
        self._reference_prompt: Optional[str] = None

    @property
    def llm_client(self) -> DTAProxyClient:
        """Get or create LLM client."""
        if self._llm_client is None:
            self._llm_client = DTAProxyClient()
        return self._llm_client

    @property
    def criteria(self) -> dict:
        """Load and cache evaluation criteria."""
        if self._criteria is None:
            try:
                self._criteria = load_criteria("MIT041")
            except FileNotFoundError:
                # Use default criteria if file not found
                self._criteria = self._get_default_criteria()
        return self._criteria

    def _get_default_criteria(self) -> dict:
        """Get default evaluation criteria."""
        return {
            "mit_type": "MIT041",
            "name": "Desenho da Solucao / Blueprint",
            "version": "1.0.0",
            "minimum_passing_score": 8.0,
            "pillars": [
                {
                    "id": "P1",
                    "name": "Completude Estrutural",
                    "weight": 0.30,
                },
                {
                    "id": "P2",
                    "name": "Qualidade das Regras e Fluxos",
                    "weight": 0.40,
                },
                {
                    "id": "P3",
                    "name": "Governanca e Aceite",
                    "weight": 0.30,
                },
            ],
        }

    def get_system_prompt(self) -> str:
        """Get system prompt for MIT041 evaluation."""
        try:
            return get_prompt("mit041_system")
        except FileNotFoundError:
            return self._get_default_system_prompt()

    def _get_default_system_prompt(self) -> str:
        """Get default system prompt if file not found."""
        return """Voce e um auditor senior especializado em documentacao de projetos de implantacao TOTVS Protheus.

## SUA TAREFA
Avaliar a qualidade de um documento MIT041 (Desenho da Solucao / Blueprint) e atribuir uma nota de 0 a 10.

## CRITERIOS DE AVALIACAO

### PILAR 1: COMPLETUDE ESTRUTURAL (30%)
- Metadados do projeto (cliente, codigo, nome do projeto)
- Historico de versoes com data, autor e descricao
- Lista de participantes com area de atuacao
- Descricao da situacao atual (AS IS)
- Cobertura de todos os processos do modulo

### PILAR 2: QUALIDADE DAS REGRAS E FLUXOS (40%)
- Cada processo deve ter: Objetivos, Origens, Fatores Criticos, Restricoes, Saidas
- Tabela de criterios de aceitacao com Processo/Descricao/Situacao Esperada
- Tabela de GAPs com ID, Descricao, Criticidade e Contorno
- Diagramas BPMN devem ter: eventos inicio/fim, gateways documentados, swimlanes com responsaveis

### PILAR 3: GOVERNANCA E ACEITE (30%)
- Tabela de aceite com aprovadores identificados (nome, cargo, empresa)
- Secao de premissas e restricoes do projeto
- Escopo claramente definido na estrategia de implementacao

## ESCALA DE NOTAS
- 10.0: Perfeito. Atende 100% dos criterios. Nenhuma recomendacao necessaria.
- 8.0-9.9: Excelente. Pequenas melhorias possiveis.
- 7.0-7.9: Bom. Atende requisitos minimos, mas ha gaps notaveis.
- 5.0-6.9: Insuficiente. Requer revisao antes de aprovacao.
- 0.0-4.9: Critico. Documento inadequado para uso.

## NOTA MINIMA ACEITAVEL: 8.0

## FORMATO DE RESPOSTA (JSON ESTRITO)
{
  "score": <numero de 0.0 a 10.0 com uma casa decimal>,
  "recommendations": [
    "<recomendacao especifica e acionavel 1>",
    "<recomendacao especifica e acionavel 2>"
  ]
}

## REGRAS IMPORTANTES
1. Se score = 10.0, recommendations DEVE ser array vazio []
2. Cada recomendacao deve ser ESPECIFICA e ACIONAVEL (ex: "Adicionar coluna 'Data' na tabela de Aceite")
3. NAO use recomendacoes vagas como "melhorar a qualidade"
4. Seja RIGOROSO - excelencia requer atencao a detalhes
5. Considere as descricoes de diagramas BPMN na avaliacao do Pilar 2
6. Responda APENAS com o JSON, sem texto adicional"""

    def _get_reference_section(self) -> str:
        """Get reference examples section for the prompt."""
        if not self.use_references:
            return ""

        if self._reference_prompt is None:
            try:
                self._reference_prompt = get_reference_prompt(
                    mit_type="mit41",
                    max_excerpts=6,
                    max_chars=8000,
                )
                if self._reference_prompt:
                    logger.info("Loaded reference examples from good MIT samples")
            except Exception as e:
                logger.warning(f"Failed to load reference examples: {e}")
                self._reference_prompt = ""

        return self._reference_prompt

    def get_user_prompt(self, extraction: ExtractionResult | dict) -> str:
        """Build user prompt with document content and reference examples."""
        if isinstance(extraction, dict):
            markdown = extraction.get("markdown", "")
            diagrams = extraction.get("diagrams", [])
        else:
            markdown = extraction.markdown
            diagrams = [d.model_dump() for d in extraction.diagrams]

        # Build diagrams section if available
        diagrams_section = ""
        if diagrams:
            diagrams_section = "\n\n## DESCRICAO DAS IMAGENS/DIAGRAMAS\n"
            for d in diagrams:
                diagrams_section += f"\n### Imagem {d.get('index', 0) + 1}"
                if d.get("diagram_type"):
                    diagrams_section += f" ({d['diagram_type']})"
                diagrams_section += f"\n{d.get('description', 'Sem descricao')}\n"

        # Get reference examples
        reference_section = self._get_reference_section()

        return f"""## DOCUMENTO MIT041 PARA AVALIACAO

{markdown}
{diagrams_section}
{reference_section}
## INSTRUCAO
Avalie este documento MIT041 comparando com os exemplos de referencia (quando disponiveis).
Retorne APENAS um JSON com score e recommendations."""

    def evaluate(
        self,
        extraction: ExtractionResult | dict,
        include_metadata: bool = False,
    ) -> EvaluationResult:
        """
        Evaluate a MIT041 document.

        Args:
            extraction: Extraction result from DoclingExtractor.
            include_metadata: Whether to include detailed metadata.

        Returns:
            EvaluationResult with score and recommendations.
        """
        if not self.validate_extraction(extraction):
            return EvaluationResult(
                score=0.0,
                recommendations=["Documento vazio ou invalido. Nao foi possivel extrair conteudo."],
            )

        # Get prompts
        system_prompt = self.get_system_prompt()
        user_prompt = self.get_user_prompt(extraction)

        # Call LLM with JSON mode for guaranteed valid JSON response
        logger.info("Sending document to LLM for evaluation...")
        try:
            llm_response = self.llm_client.chat_completion_with_metadata(
                system_prompt=system_prompt,
                user_content=user_prompt,
                temperature=0.3,
                max_tokens=settings.llm_max_tokens,
                json_mode=settings.llm_json_mode,
            )

            # Check if response was truncated
            if llm_response.finish_reason == "length":
                logger.warning(
                    f"LLM response was truncated (max_tokens={settings.llm_max_tokens}). "
                    "Consider increasing LLM_MAX_TOKENS in .env"
                )
                return EvaluationResult(
                    score=0.0,
                    recommendations=[
                        "Resposta da avaliacao foi truncada por limite de tokens. "
                        "Aumente LLM_MAX_TOKENS no arquivo .env (valor atual: "
                        f"{settings.llm_max_tokens})."
                    ],
                )

            response = llm_response.content
        except DTAError as e:
            logger.error(f"LLM call failed: {e}")
            return EvaluationResult(
                score=0.0,
                recommendations=[f"Erro ao avaliar documento: {str(e)}"],
            )
        except Exception as e:
            logger.error(f"Unexpected error during LLM call: {e}")
            return EvaluationResult(
                score=0.0,
                recommendations=[f"Erro inesperado ao avaliar documento: {str(e)}"],
            )

        # Parse response
        result = self._parse_response(response)

        # Add metadata if requested
        if include_metadata:
            if isinstance(extraction, dict):
                metadata_dict = extraction.get("metadata", {})
                word_count = metadata_dict.get("word_count", 0)
                image_count = metadata_dict.get("image_count", 0)
                relevant_images = metadata_dict.get("relevant_images", 0)
                vision_enabled = metadata_dict.get("vision_enabled", False)
                doc_name = "unknown"
            else:
                word_count = extraction.metadata.word_count
                image_count = extraction.metadata.image_count
                relevant_images = extraction.metadata.relevant_images
                vision_enabled = extraction.metadata.vision_enabled
                doc_name = "unknown"

            result.metadata = EvaluationMetadata(
                mit_type=self.mit_type,
                document_name=doc_name,
                word_count=word_count,
                image_count=image_count,
                relevant_images=relevant_images,
                vision_enabled=vision_enabled,
                evaluation_timestamp=datetime.now(),
            )

        return result

    def _parse_response(self, response: str) -> EvaluationResult:
        """
        Parse LLM response into EvaluationResult.

        Args:
            response: Raw LLM response string.

        Returns:
            Parsed EvaluationResult.
        """
        # Try to extract JSON from response
        try:
            # Remove markdown code blocks if present
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            data = json.loads(response)

            score = float(data.get("score", 0))
            score = max(0.0, min(10.0, score))  # Clamp to 0-10

            recommendations = data.get("recommendations", [])
            if not isinstance(recommendations, list):
                recommendations = [str(recommendations)]

            # Clean empty recommendations
            recommendations = [r for r in recommendations if r and r.strip()]

            return EvaluationResult(
                score=round(score, 1),
                recommendations=recommendations,
            )

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.debug(f"Raw response: {response}")
            return EvaluationResult(
                score=0.0,
                recommendations=[
                    "Erro ao processar resposta da avaliacao. "
                    "O formato da resposta do LLM nao foi reconhecido."
                ],
            )
