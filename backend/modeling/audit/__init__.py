"""Entity change audit — 'Coverage 그래프 recently_changed lens' 와 BR change history 의 단일 출처.

모든 ontology entity 의 create/update/confirm/reject 를 단일 테이블에 누적.
recommend persist 같은 자동 호출은 changed_by=None, 사용자 confirm/edit 는 changed_by="user".
"""
