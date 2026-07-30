1. Agente Orquestador
Objetivo
Coordinar el flujo completo del sistema, administrar los resultados parciales, manejar errores y registrar la traza de ejecución.
Prompt para Codex
Actúa como arquitecto senior de sistemas multiagente en Python.

Implementa un agente llamado FitAnalysisOrchestrator.

Objetivo:
Coordinar el análisis de compatibilidad entre un descriptivo de cargo y múltiples
CV almacenados en un directorio.

El orquestador debe coordinar los siguientes agentes y workers:

1. JobDescriptionAgent
2. CandidateRetrievalWorker
3. CandidateProfileAgent
4. FitAssessmentAgent
5. InterviewQuestionAgent
6. RankingAgent
7. SupervisorAgent

Flujo obligatorio:

1. Recibir:
   - texto o archivo del descriptivo del rol;
   - directorio de CV;
   - configuración de ponderaciones;
   - cantidad máxima de candidatos;
   - identificador opcional de ejecución.

2. Ejecutar JobDescriptionAgent.

3. Validar que el descriptivo tenga información suficiente para realizar
   el análisis.

4. Ejecutar CandidateRetrievalWorker para recuperar los CV más relevantes.

5. Para cada candidato recuperado:
   a. ejecutar CandidateProfileAgent;
   b. ejecutar FitAssessmentAgent;
   c. ejecutar InterviewQuestionAgent.

6. Acumular los resultados parciales en un payload estructurado.

7. Ejecutar RankingAgent.

8. Ejecutar SupervisorAgent.

9. Aplicar el resultado del supervisor:
   - approved: retornar resultado original;
   - modified_and_approved: aplicar las modificaciones documentadas;
   - rejected: retornar el rechazo con los motivos.

10. Registrar:
   - tiempo de inicio;
   - tiempo de término;
   - latencia por agente;
   - tokens utilizados;
   - estado;
   - errores;
   - resultado del fiscalizador.

Requisitos técnicos:

- Usar programación asíncrona.
- Usar asyncio.gather para procesar candidatos en paralelo.
- Configurar un límite de concurrencia mediante asyncio.Semaphore.
- Permitir que el sistema continúe si falla un CV individual.
- Registrar el error del candidato fallido.
- Evitar ciclos infinitos.
- Permitir solo un ciclo de corrección.
- No exponer stack traces al usuario.
- Retornar modelos Pydantic.
- Incorporar logging estructurado.
- Crear pruebas unitarias y de integración con mocks.

Output esperado:

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

Incluye un diagrama Mermaid del flujo en README.md.
No implementes lógica de negocio que corresponda a los agentes especializados.
Criterios de aceptación
•	Coordina todos los agentes en el orden correcto. 
•	Mantiene una traza completa. 
•	Continúa aunque falle un CV. 
•	Aplica una sola corrección. 
•	Entrega un resultado estructurado. 
________________________________________
2. Agente Analizador del Rol
Objetivo
Transformar el descriptivo de cargo en una estructura clara de requisitos, responsabilidades y ponderaciones.
Prompt para Codex
Implementa un agente llamado JobDescriptionAgent.

Objetivo:
Convertir un descriptivo de cargo no estructurado en un modelo JobDescription
estructurado y apto para evaluar candidatos.

Input:

{
  "role_id": "opcional",
  "role_description": "texto completo del descriptivo"
}

El agente debe extraer:

1. Título del rol.
2. Objetivo principal.
3. Responsabilidades.
4. Requisitos obligatorios.
5. Requisitos deseables.
6. Tecnologías.
7. Herramientas.
8. Años mínimos de experiencia.
9. Formación académica.
10. Certificaciones.
11. Idiomas.
12. Competencias técnicas.
13. Competencias conductuales.
14. Restricciones explícitas.
15. Requisitos ambiguos.
16. Requisitos excluyentes.

Para cada requisito debe crear:

{
  "requirement_id": "...",
  "name": "...",
  "category": "...",
  "mandatory": true,
  "exclusionary": false,
  "weight": 0,
  "minimum_level": "...",
  "minimum_years": null,
  "synonyms": [],
  "source_text": "...",
  "confidence": 0.0,
  "ambiguous": false
}

Reglas:

1. Analizar solamente el texto entregado.
2. No agregar tecnologías no mencionadas.
3. No inventar responsabilidades.
4. No convertir un requisito deseable en obligatorio.
5. Mantener el texto original como evidencia.
6. Detectar requisitos duplicados.
7. Consolidar requisitos equivalentes.
8. Marcar requisitos ambiguos.
9. Distinguir experiencia general y experiencia específica.
10. Distinguir competencias técnicas y conductuales.
11. Proponer pesos iniciales configurables.
12. Verificar que la suma de los pesos sea 100.
13. Si faltan datos importantes, incluir una lista de clarification_questions.
14. Retornar structured output mediante Pydantic.

Ponderación inicial sugerida:

- requisitos obligatorios: 50 %
- experiencia relevante: 20 %
- tecnologías y herramientas: 15 %
- formación y certificaciones: 10 %
- requisitos deseables: 5 %

La ponderación debe poder sobrescribirse desde configuración.

Output esperado:

{
  "role_id": "...",
  "role_title": "...",
  "role_summary": "...",
  "responsibilities": [],
  "requirements": [],
  "technologies": [],
  "education": [],
  "certifications": [],
  "languages": [],
  "weights": {},
  "ambiguities": [],
  "clarification_questions": [],
  "confidence": 0.0
}

Crea pruebas para:

- descriptivo completo;
- descriptivo ambiguo;
- requisitos duplicados;
- ausencia de años de experiencia;
- requisito obligatorio y deseable mezclados.
Criterios de aceptación
•	No inventa requisitos. 
•	Diferencia obligatorio y deseable. 
•	Conserva evidencia textual. 
•	Genera pesos coherentes. 
•	Detecta ambigüedades. 
________________________________________
3. Worker Vectorial
Objetivo
Buscar en la base vectorial los CV y fragmentos más relacionados con el descriptivo del rol.
Prompt para Codex
Implementa un worker llamado CandidateRetrievalWorker.

Objetivo:
Recuperar los candidatos y fragmentos de CV más relacionados con un
JobDescription estructurado.

El sistema utiliza Chroma como base vectorial y embeddings de OpenAI.

Input:

{
  "job_description": {},
  "top_k_candidates": 10,
  "chunks_per_query": 5
}

Flujo:

1. Recibir el JobDescription estructurado.

2. Crear consultas semánticas independientes para:
   - título del rol;
   - requisitos obligatorios;
   - tecnologías;
   - responsabilidades;
   - experiencia requerida;
   - certificaciones;
   - requisitos deseables.

3. Consultar Chroma con cada consulta.

4. Recuperar inicialmente k=5 fragmentos por consulta.

5. Agrupar resultados por candidate_id.

6. Eliminar fragmentos duplicados.

7. Evitar que un solo CV domine el resultado por tener más chunks.

8. Calcular un retrieval_score normalizado por candidato.

9. Identificar qué requisitos provocaron la recuperación de cada candidato.

10. Retornar los candidatos ordenados por relevancia semántica.

Output por candidato:

{
  "candidate_id": "...",
  "retrieval_score": 0.0,
  "matched_query_groups": [],
  "matched_requirements": [],
  "relevant_chunks": [
    {
      "content": "...",
      "source_file": "...",
      "page": 0,
      "section": "...",
      "chunk_id": "...",
      "similarity_score": 0.0
    }
  ]
}

Reglas críticas:

1. El retrieval_score no es el porcentaje de fit.
2. No convertir similitud vectorial directamente en fit.
3. Mantener metadata y fuente.
4. No utilizar atributos sensibles.
5. Si hay menos candidatos que top_k_candidates, retornar todos.
6. Si no hay resultados suficientes, registrar knowledge_gaps.
7. Permitir filtros por ubicación lógica del documento, fecha o versión.
8. Configurar k desde variables de entorno.
9. Permitir búsqueda híbrida como mejora futura.
10. Crear pruebas usando una base vectorial mock.

Incluye métricas:

- consultas ejecutadas;
- chunks recuperados;
- candidatos encontrados;
- tiempo de búsqueda;
- score promedio.
Criterios de aceptación
•	Recupera candidatos relevantes. 
•	Agrupa correctamente por candidato. 
•	Mantiene fuentes y páginas. 
•	Separa similitud de fit. 
•	No favorece CV más extensos. 
________________________________________
4. Agente Analizador de CV
Objetivo
Convertir el CV del candidato en un perfil profesional estructurado y respaldado por evidencias.
Prompt para Codex
Implementa un agente llamado CandidateProfileAgent.

Objetivo:
Extraer desde un CV un perfil profesional estructurado y trazable.

Input:

{
  "candidate_id": "...",
  "cv_chunks": [],
  "source_file": "..."
}

Debe extraer:

1. Nombre del candidato, solo para presentación.
2. Resumen profesional.
3. Cargos anteriores.
4. Empresas.
5. Fechas laborales.
6. Duración de cada experiencia.
7. Responsabilidades.
8. Logros.
9. Tecnologías.
10. Herramientas.
11. Metodologías.
12. Dominios de negocio.
13. Formación.
14. Certificaciones.
15. Idiomas.
16. Nivel de seniority evidenciado.
17. Años de experiencia total.
18. Años de experiencia por tecnología.
19. Evidencias relevantes para el rol.

Cada atributo debe contener evidencia:

{
  "value": "...",
  "evidence_text": "...",
  "source_file": "...",
  "page": 0,
  "section": "...",
  "evidence_type": "explicit | indirect | not_evidenced",
  "confidence": 0.0
}

Reglas:

1. No inventar experiencia.
2. No asumir conocimientos por el título del cargo.
3. No inferir seniority únicamente por años.
4. No sumar dos veces experiencias laborales superpuestas.
5. Distinguir evidencia explícita e indirecta.
6. Ausencia de evidencia no significa ausencia de competencia.
7. No usar edad, género, nacionalidad, fotografía, estado civil,
   dirección ni otros atributos sensibles.
8. No usar nombres de universidades como señal de calidad.
9. No evaluar prestigio de empresas.
10. Extraer solamente información relevante para el análisis profesional.
11. Mantener las fuentes.
12. Retornar CandidateProfile mediante Pydantic.

Output esperado:

{
  "candidate_id": "...",
  "candidate_name": "...",
  "professional_summary": "...",
  "experiences": [],
  "skills": [],
  "technologies": [],
  "education": [],
  "certifications": [],
  "languages": [],
  "total_years_experience": 0,
  "domain_experience": [],
  "evidence": [],
  "confidence": 0.0
}

Crea pruebas para:

- CV con fechas completas;
- CV sin fechas;
- experiencia superpuesta;
- tecnología mencionada sin contexto;
- CV sin certificaciones;
- información sensible.
Criterios de aceptación
•	Extrae perfiles estructurados. 
•	Conserva evidencia. 
•	No duplica años. 
•	Excluye atributos sensibles. 
•	Diferencia evidencia directa e indirecta. 
________________________________________
5. Agente Evaluador de Fit
Objetivo
Comparar el perfil del candidato con los requisitos del rol y calcular compatibilidad, fortalezas y brechas.
Prompt para Codex
Implementa un agente llamado FitAssessmentAgent.

Objetivo:
Evaluar la compatibilidad entre un JobDescription y un CandidateProfile.

Input:

{
  "job_description": {},
  "candidate_profile": {},
  "scoring_config": {}
}

Para cada requisito debe generar:

{
  "requirement_id": "...",
  "requirement_name": "...",
  "mandatory": true,
  "exclusionary": false,
  "status": "met | partially_met | not_evidenced | contradicted | not_applicable",
  "raw_score": 0.0,
  "max_score": 0.0,
  "weighted_score": 0.0,
  "evidence": [],
  "gap_description": "...",
  "confidence": 0.0
}

Flujo:

1. Comparar cada requisito con las evidencias del candidato.
2. Clasificar el estado.
3. Identificar fortalezas.
4. Identificar brechas.
5. Identificar requisitos excluyentes no cumplidos.
6. Entregar la información necesaria para calcular el fit.
7. Calcular el porcentaje final mediante código Python determinístico.
8. Generar confidence general.

Ponderación inicial:

- requisitos obligatorios: 50 %
- experiencia relevante: 20 %
- tecnologías y herramientas: 15 %
- formación y certificaciones: 10 %
- requisitos deseables: 5 %

Reglas de cálculo:

1. El LLM analiza evidencias y clasifica.
2. Python realiza la aritmética.
3. El fit debe estar entre 0 y 100.
4. Los pesos deben sumar 100.
5. Un requisito sin evidencia debe marcarse not_evidenced.
6. No afirmar que el candidato no tiene una habilidad cuando el CV no la menciona.
7. Las inferencias indirectas deben tener menor confianza.
8. Un requisito excluyente faltante debe generar un flag.
9. La penalización de requisitos excluyentes debe ser configurable.
10. Cada puntaje debe ser explicable.
11. Ningún atributo sensible puede afectar el score.
12. No utilizar el retrieval_score como fit_percentage.

Output esperado:

{
  "candidate_id": "...",
  "fit_percentage": 0.0,
  "fit_level": "high | medium | low",
  "mandatory_fit": 0.0,
  "desirable_fit": 0.0,
  "strengths": [],
  "gaps": [],
  "exclusionary_flags": [],
  "requirement_assessments": [],
  "confidence": 0.0
}

Crea pruebas para:

- candidato con fit alto;
- candidato con fit medio;
- candidato con baja evidencia;
- requisito excluyente faltante;
- empate de puntajes;
- pesos inválidos.
Criterios de aceptación
•	El cálculo se realiza en Python. 
•	Cada puntaje tiene evidencia. 
•	Separa falta de evidencia de falta real. 
•	Identifica brechas y excluyentes. 
•	El fit siempre está entre 0 y 100. 
________________________________________
6. Agente Generador de Preguntas
Objetivo
Crear cinco preguntas de entrevista orientadas a validar brechas, ambigüedades o competencias no demostradas.
Prompt para Codex
Implementa un agente llamado InterviewQuestionAgent.

Objetivo:
Generar exactamente cinco preguntas de entrevista personalizadas para cada candidato.

Input:

{
  "job_description": {},
  "candidate_profile": {},
  "fit_assessment": {}
}

Las preguntas deben priorizar:

1. Requisitos obligatorios parcialmente cumplidos.
2. Requisitos obligatorios sin evidencia.
3. Requisitos excluyentes ambiguos.
4. Tecnologías mencionadas sin contexto.
5. Experiencia relevante sin resultados comprobables.
6. Brechas que podrían cerrarse con evidencia adicional.

Cada pregunta debe incluir:

{
  "question": "...",
  "validates_requirement_id": "...",
  "validates_requirement": "...",
  "gap_type": "...",
  "rationale": "...",
  "expected_positive_evidence": "...",
  "expected_warning_signals": [],
  "potential_fit_increase": 0.0,
  "priority": 1
}

Reglas:

1. Generar exactamente cinco preguntas.
2. No crear preguntas genéricas.
3. No repetir preguntas.
4. Priorizar requisitos obligatorios.
5. Relacionar cada pregunta con un requisito.
6. Explicar qué evidencia positiva se espera.
7. No asumir que la respuesta será positiva.
8. No modificar todavía el fit.
9. potential_fit_increase representa el máximo ajuste posible.
10. La suma de aumentos potenciales no debe superar 100 menos el fit actual.
11. No formular preguntas sobre edad, familia, nacionalidad, salud,
    estado civil, religión u otros atributos sensibles.
12. Evitar preguntas capciosas o discriminatorias.
13. Preferir preguntas conductuales o basadas en experiencia real.
14. Crear pruebas con respuestas mock.

Ejemplo esperado:

{
  "question": "Cuéntame sobre un proyecto en el que hayas utilizado SageMaker para entrenar o desplegar un modelo.",
  "validates_requirement": "Experiencia práctica en SageMaker",
  "rationale": "El CV menciona AWS y machine learning, pero no evidencia el uso de SageMaker.",
  "expected_positive_evidence": "Descripción del proyecto, responsabilidades, modelo, despliegue y resultado.",
  "expected_warning_signals": [
    "Solo conocimiento teórico",
    "Participación indirecta"
  ],
  "potential_fit_increase": 4,
  "priority": 1
}
Criterios de aceptación
•	Genera exactamente cinco preguntas. 
•	Cada una valida una brecha. 
•	No pregunta sobre atributos sensibles. 
•	Define evidencia esperada. 
•	Calcula el potencial de mejora sin alterar el fit. 
________________________________________
7. Agente de Ranking
Objetivo
Ordenar candidatos por fit y generar una comparación clara y transparente.
Prompt para Codex
Implementa un agente llamado RankingAgent.

Objetivo:
Ordenar los candidatos evaluados y construir una comparación estructurada.

Input:

{
  "job_description": {},
  "candidate_fit_results": [],
  "ranking_config": {}
}

Reglas de ordenamiento:

1. fit_percentage descendente.
2. En caso de empate:
   a. mandatory_fit descendente;
   b. menor cantidad de requisitos excluyentes faltantes;
   c. confidence descendente;
   d. cantidad de requisitos obligatorios cumplidos;
   e. retrieval_score descendente.

3. Nunca usar el nombre como criterio.
4. Nunca usar atributos sensibles.
5. No alterar los porcentajes calculados.
6. No inventar fortalezas ni brechas.

Para cada candidato entregar:

{
  "rank": 1,
  "candidate_id": "...",
  "candidate_name": "...",
  "fit_percentage": 0.0,
  "fit_level": "...",
  "mandatory_fit": 0.0,
  "confidence": 0.0,
  "main_strengths": [],
  "main_gaps": [],
  "missing_mandatory_requirements": [],
  "exclusionary_flags": [],
  "interview_questions": [],
  "recommendation": "advance | review | do_not_advance"
}

Además, generar:

1. Tabla comparativa de candidatos.
2. Diferencias principales entre los primeros candidatos.
3. Requisitos con menor cobertura en el grupo.
4. Requisitos con mayor cobertura.
5. Advertencias metodológicas.

Incluir siempre este mensaje:

"El ranking es una herramienta de apoyo a la decisión y no reemplaza la
evaluación profesional ni la entrevista."

Configuración:

- top_n;
- fit mínimo;
- incluir candidatos con requisitos excluyentes faltantes;
- cantidad de fortalezas y brechas visibles.

Output esperado:

{
  "role_id": "...",
  "role_title": "...",
  "total_candidates": 0,
  "ranking": [],
  "comparison_summary": {},
  "methodological_warning": "...",
  "generated_at": "..."
}

Crea pruebas para:

- ordenamiento normal;
- empate;
- requisitos excluyentes;
- top_n;
- filtro de fit mínimo;
- estabilidad del ranking.
Criterios de aceptación
•	Ordena de forma determinística. 
•	Respeta criterios de desempate. 
•	No cambia el fit. 
•	Presenta fortalezas y brechas. 
•	Incluye advertencia de apoyo a decisión. 
________________________________________
8. Agente Fiscalizador
Objetivo
Revisar que el análisis sea coherente, trazable, libre de sesgos indebidos y respaldado por evidencia.
Prompt para Codex
Implementa un agente llamado SupervisorAgent.

Objetivo:
Fiscalizar el resultado completo antes de entregarlo al usuario.

Input:

{
  "job_description": {},
  "candidate_profiles": [],
  "fit_results": [],
  "ranking_result": {},
  "traces": []
}

Debe evaluar cinco dimensiones:

1. Evidencia.
2. Coherencia.
3. Calidad.
4. Seguridad y sesgos.
5. Cumplimiento de la pregunta original.

Validaciones de evidencia:

- Cada fortaleza tiene evidencia.
- Cada brecha se relaciona con un requisito.
- Cada puntaje puede explicarse.
- Cada fuente identifica archivo y página o sección.
- Se distingue entre ausencia de evidencia y ausencia de experiencia.

Validaciones de coherencia:

- El fit coincide con los requirement_assessments.
- Los pesos suman 100.
- El ranking está ordenado correctamente.
- Los criterios de desempate están bien aplicados.
- Las preguntas corresponden a brechas reales.
- El aumento potencial es matemáticamente válido.

Validaciones de seguridad:

- No se utilizaron atributos sensibles.
- No se hicieron inferencias sobre edad, género, nacionalidad,
  estado civil, salud, religión, fotografía o dirección.
- No se evaluó prestigio de universidades o empresas.
- No se expuso PII innecesaria.
- No existen expresiones discriminatorias.

Validaciones de calidad:

- Todos los candidatos tienen análisis.
- Cada candidato tiene exactamente cinco preguntas.
- Los resultados son comprensibles.
- Las advertencias están incluidas.
- La confianza es coherente con la evidencia disponible.

Output:

{
  "decision": "approved | modified_and_approved | rejected",
  "approved": true,
  "quality_score": 0.0,
  "dimension_scores": {
    "evidence": 0.0,
    "coherence": 0.0,
    "quality": 0.0,
    "safety": 0.0,
    "relevance": 0.0
  },
  "issues": [],
  "flags": [],
  "modifications": [],
  "final_result": {}
}

Árbol de decisión:

1. APPROVED:
   - quality_score >= 0.6;
   - sin flags críticos;
   - cálculos correctos;
   - ranking coherente.

2. MODIFIED_AND_APPROVED:
   - existen problemas menores corregibles;
   - no se requiere crear nueva evidencia;
   - las modificaciones quedan documentadas.

3. REJECTED:
   - quality_score < 0.6;
   - uso de atributos sensibles;
   - ausencia generalizada de evidencia;
   - cálculos incorrectos;
   - ranking inconsistente;
   - exposición grave de PII.

Reglas:

1. El supervisor puede corregir:
   - redacción;
   - etiquetas;
   - orden;
   - inconsistencias matemáticas determinísticas;
   - formatos.

2. El supervisor no puede:
   - inventar evidencia;
   - aumentar el fit sin evidencia;
   - agregar experiencia al candidato;
   - crear nuevos requisitos;
   - eliminar flags críticos.

3. Toda modificación debe indicar:
   - campo modificado;
   - valor anterior;
   - valor nuevo;
   - motivo.

4. Permitir solo una ronda de corrección.
5. Crear pruebas para:
   - aprobado;
   - modificado y aprobado;
   - rechazado por score;
   - rechazado por atributo sensible;
   - rechazado por falta de evidencia;
   - ranking inconsistente.
Criterios de aceptación
•	Evalúa calidad, seguridad y coherencia. 
•	Puede aprobar, modificar o rechazar. 
•	Documenta toda corrección. 
•	No inventa evidencia. 
•	Rechaza uso de atributos sensibles. 
Secuencia recomendada en Codex
Ejecuta los prompts en este orden:
1. Analizador del rol
2. Worker vectorial
3. Analizador de CV
4. Evaluador de fit
5. Generador de preguntas
6. Ranking
7. Fiscalizador
8. Orquestador
El orquestador se implementa al final porque necesita conocer las interfaces reales de todos los agentes. Es como contratar al director de una orquesta después de definir qué instrumentos habrá y qué partitura tocará cada uno.
Contrato común entre agentes
Conviene agregar esta instrucción al final de cada prompt:
Reglas comunes del sistema:

- Usar modelos Pydantic para inputs y outputs.
- No retornar diccionarios sin validación.
- Usar AsyncOpenAI cuando corresponda.
- Implementar reintentos con Tenacity.
- Mantener prompts fuera del código de negocio.
- Incorporar logging estructurado.
- Conservar evidencia y fuentes.
- Excluir atributos sensibles.
- No inventar información.
- Crear pruebas unitarias con mocks.
- Actualizar README.md.
- Ejecutar las pruebas antes de finalizar.
Resumen del diseño
El sistema quedaría dividido en tres tipos de responsabilidad:
Comprensión:
Analizador del rol + Analizador de CV

Decisión:
Evaluador de fit + Generador de preguntas + Ranking

Control:
Fiscalizador + Orquestador
La búsqueda vectorial funciona como puente entre el descriptivo y los CV, mientras el fiscalizador evita que el sistema entregue un ranking aparentemente preciso, pero construido sobre evidencia débil o criterios incorrectos.

