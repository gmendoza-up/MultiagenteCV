import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fit_analysis_orchestrator.agent import FitAnalysisOrchestrator

tmp = Path('tmp_cv_test')
tmp.mkdir(exist_ok=True)
(tmp / 'candidato_0.txt').write_text('Nombre: Candidato 0\nExperiencia: 5 años en Python y análisis de datos.')

orchestrator = FitAnalysisOrchestrator(
    role_text='Muy corto.',
    cv_directory=str(tmp),
    weights={'technical': 0.7},
    max_candidates=1,
)

async def run_it():
    print('calling run')
    result = await orchestrator.run()
    print('done', result.status)
    print('errors', result.errors)
    print('ranking', result.ranking)
    print('role', result.role)
    print('supervisor', result.supervisor_result)
    print('total_tokens', result.total_tokens)
    print('traces', [t.step for t in result.traces])
    print('candidates_analyzed', result.candidates_analyzed)

asyncio.run(run_it())
