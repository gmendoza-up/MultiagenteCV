import asyncio
from fit_analysis_orchestrator.candidate_profile_agent import CandidateProfileAgent

payload = {
    "candidate_id": "c1",
    "cv_chunks": [
        {
            "content": "Nombre: Ana Pérez\nEmpresa: Acme Corp\nPuesto: Ingeniera de Datos\nDesde: enero 2019 hasta diciembre 2022\nResponsabilidades: Diseño de pipelines, análisis de datos.",
            "source_file": "c1.txt",
            "page": 1,
            "section": "Experiencia",
        }
    ],
    "source_file": "c1.txt",
}
agent = CandidateProfileAgent()
profile, tokens = asyncio.run(agent.execute(payload))
print("profile.total_years_experience:", profile.total_years_experience)
print("profile.confidence:", profile.confidence)
print("profile.candidate_name:", profile.candidate_name)
print("profile.evidence:", [e.model_dump() for e in profile.evidence])
print("profile.experiences:", [e.model_dump() for e in profile.experiences])
