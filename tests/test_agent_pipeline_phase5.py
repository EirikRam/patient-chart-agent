from pathlib import Path

import pytest

from packages.pipeline.agent_pipeline import run_agent_pipeline


def test_agent_pipeline_enable_agents() -> None:
    sample_path = Path(
        "data/raw/fhir_ehr_synthea/samples_100/"
        "Berna338_Moore224_f4159279-94bf-1bfc-701b-502b2a3131b4.json"
    )
    if not sample_path.exists():
        pytest.skip("sample data not available")

    result = run_agent_pipeline(sample_path, enable_agents=True, mode="mock")
    assert isinstance(result.timeline, list)
    assert isinstance(result.missing_info, list)
    assert isinstance(result.contradictions, list)

    result_disabled = run_agent_pipeline(sample_path, enable_agents=False, mode="mock")
    assert result_disabled.timeline is None
    assert result_disabled.missing_info is None
    assert result_disabled.contradictions is None
