package com.example.slabdesign.store.sd.working.domain.logic;

import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.oracle.jpo.SDOrderChemicalJpo;
import com.example.slabdesign.store.sd.working.oracle.jpo.SDOrderOmJpo;
import com.example.slabdesign.store.sd.working.oracle.jpo.SDOrderOsJpo;
import com.example.slabdesign.store.sd.working.oracle.jpo.SDOrderQdJpo;
import org.springframework.stereotype.Component;

import java.lang.reflect.Field;

/**
 * sd · working · 주문 도메인 변환 로직.
 *
 * 4개 JPO (OS/OM/QD/CHEMICAL) ↔ SDOrderEntity 변환을 담당하는 xxxStore 상위 모듈.
 * dev notes 의 두 가지 변환 방식 모두 사용:
 *   1) 리플렉션 기반 필드명 매칭 (대부분의 단순 필드)
 *   2) 직접 계산·매핑 (선택된 열연 목표 폭, 작업기한 통합 등 — P2.1 추가)
 *
 * 동명 필드 충돌 시 OS → OM → QD → CHEMICAL 순서로 first-non-null wins
 * (예: designPendQty 는 OS 의 값 우선).
 *
 * NOTE: 리플렉션 매핑은 정적 분석 도구가 호출 그래프를 직접 추적하기 어렵습니다.
 *       이는 의도된 패턴이며 (도메인 의미 기반 매핑), 슬랩-디자인 툴이 분석할 때
 *       리플렉션 디스패치 경계를 인식할 수 있도록 별도 metadata 가 필요할 수 있습니다.
 */
@Component
public class SDOrderLogic {

    /**
     * 4 JPO → 1 Entity 통합.
     * null JPO 는 무시 (예: ORDER_CHEMICAL 미존재 주문).
     */
    public SDOrderEntity toEntity(SDOrderOsJpo os,
                                  SDOrderOmJpo om,
                                  SDOrderQdJpo qd,
                                  SDOrderChemicalJpo chm) {
        SDOrderEntity entity = new SDOrderEntity();
        copyByReflection(os, entity);   // OS 우선 — 충돌 시 winner
        copyByReflection(om, entity);
        copyByReflection(qd, entity);
        copyByReflection(chm, entity);
        // 직접 계산 영역 (P2.1 에서 채울 예정):
        //   - 선택된 열연 목표 폭 (confirmedPlantCd 의 열연 위치 → hrTgtWidth1~5 중 1개 선택)
        //   - 통합 작업기한 (8 due 중 confirmed 공정만의 max/min)
        return entity;
    }

    /**
     * source 의 필드를 target 의 동명 필드로 복사.
     * - source 가 null → no-op
     * - target 에 동명 필드 없음 → skip
     * - 타입 불일치 → skip
     * - target 필드가 이미 non-null → skip (first-non-null wins precedence)
     */
    private void copyByReflection(Object source, Object target) {
        if (source == null) return;
        Field[] sourceFields = source.getClass().getDeclaredFields();
        for (Field srcField : sourceFields) {
            try {
                srcField.setAccessible(true);
                Object value = srcField.get(source);
                if (value == null) continue;

                Field targetField = findField(target.getClass(), srcField.getName());
                if (targetField == null) continue;
                if (!targetField.getType().isAssignableFrom(srcField.getType())) continue;

                targetField.setAccessible(true);
                if (targetField.get(target) != null) continue; // precedence: first-non-null wins

                targetField.set(target, value);
            } catch (IllegalAccessException e) {
                throw new IllegalStateException(
                    "Field copy failed: " + srcField.getName() + " on " + source.getClass().getSimpleName(), e);
            }
        }
    }

    private Field findField(Class<?> cls, String name) {
        try {
            return cls.getDeclaredField(name);
        } catch (NoSuchFieldException e) {
            return null;
        }
    }
}
