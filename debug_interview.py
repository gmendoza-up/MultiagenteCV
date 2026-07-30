import asyncio
from fit_analysis_orchestrator.interview_question_agent import InterviewQuestionAgent
from fit_analysis_orchestrator.models import CandidateProfile, RoleDescriptor, EvidenceDetail

profile = CandidateProfile(
    candidate_id='c2',
    candidate_name='Candidato Falta',
    summary='Experiencia en análisis y resultados.',
    total_years_experience=2.0,
    technologies=[
        EvidenceDetail(value='Excel', evidence_text='Excel', source_file='cv.txt', page=1, section='Resumen', evidence_type='technology', confidence=0.7),
    ],
    skills=[
        EvidenceDetail(value='Análisis', evidence_text='Análisis', source_file='cv.txt', page=1, section='Resumen', evidence_type='skill', confidence=0.7),
    ],
)
role = RoleDescriptor(
    description_text='Se requiere experiencia en Python, SQL, trabajo con stakeholders y comunicación clara.',
    source='test',
)
agent = InterviewQuestionAgent()
requirements = agent._extract_requirements(role.description_text)
profile_terms = agent._collect_profile_terms(profile)
missing = agent._find_missing_terms(requirements, profile_terms)
questions, tokens = asyncio.run(agent.execute(profile, role))
print('requirements=', requirements)
print('profile_terms=', profile_terms)
print('missing=', missing)
print('tokens=', tokens)
print('question_texts=')
for q in questions:
    print('-', q.validates_requirement_id, q.validates_requirement, q.question)
print('unique questions=', len({q.question for q in questions}))
