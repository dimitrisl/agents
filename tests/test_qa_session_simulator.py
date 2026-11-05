"""
Automated Pytest wrapper for the Tabletop & Online Multi-Client QA Session Simulator.

Ensures that realistic session simulation (In-Person Tabletop with Mobile Companion
and Online Desktop VTT) is continuously verified in CI without regressions.
"""

from scripts.qa.simulate_session import TabletopQASimulator


def test_qa_session_simulator_tabletop_and_online():
    simulator = TabletopQASimulator()
    passed = simulator.run_all(mode="both")
    assert passed is True, "QA Session Simulator reported one or more scenario failures."
