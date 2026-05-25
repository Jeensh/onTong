"""Section 3 시뮬레이션 에이전트 — 신규 탭 (RFC: SIMULATION_AGENT_RFC.md).

multiturn (`backend/section3/agents/multiturn/`) 의 3-gate · 6 intent 위에
5 시나리오 (IT 운영자 페르소나) + intent 별 차별 UI 를 입힌다.

multiturn 의 함수·도구·schema 를 import 해서 thin wrap 하고, simulation
전용 신규 (1) tool 3종 (repo_grep / synthesize_virtual_term / compare_runs),
(2) Gate III 의 locate·explain·hypothesis 분기, (3) 별도 decision_log
테이블을 더한다.
"""
