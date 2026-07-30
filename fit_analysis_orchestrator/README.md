# FitAnalysisOrchestrator

Orquesta el análisis de compatibilidad entre un descriptivo de cargo y múltiples CV almacenados en un directorio.

## Flujo

```mermaid
flowchart TD
  A[Inicio] --> B[JobDescriptionAgent]
  B --> C{Validación de descriptivo}
  C -->|Válido| D[CandidateRetrievalWorker]
  C -->|Inválido| X[Rechazo]
  D --> E[Procesar candidatos en paralelo]
  E --> E1[CandidateProfileAgent]
  E --> E2[FitAssessmentAgent]
  E --> E3[InterviewQuestionAgent]
  E --> F[Acumular resultados]
  F --> G[RankingAgent]
  G --> H[SupervisorAgent]
  H --> I{Resultado del supervisor}
  I -->|approved| J[Retornar resultado original]
  I -->|modified_and_approved| K[Aplicar modificaciones y retornar]
  I -->|rejected| X
  J --> Z[Fin]
  K --> Z[Fin]
```

## Uso

```bash
python agent.py --role-text "Descriptivo de cargo..." --cv-dir ./cvs --max-candidates 5 --weights '{"technical": 0.7}'
```

## Salida esperada

```json
{
  "analysis_id": "...",
  "role": {},
  "candidates_analyzed": 0,
  "ranking": [],
  "supervisor_result": {},
  "traces": [],
  "total_latency_ms": 0,
  "total_tokens": 0,
  "status": "completed"
}
```
