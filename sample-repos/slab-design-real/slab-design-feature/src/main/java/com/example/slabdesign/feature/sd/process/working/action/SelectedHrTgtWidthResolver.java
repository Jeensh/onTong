package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;

/**
 * sd · working · 열연 목표 폭 선택 (5 → 1).
 *
 * 룰:
 *   1. ORDER_OS.CONFIRMED_PLANT_CD 의 **2번째 자리** 추출 (열연 위치, 0=제강 1=열연 ...)
 *   2. 그 자리 코드(`'1'~'5'`) → ORDER_QD 의 HR_TGT_WIDTH_1 ~ HR_TGT_WIDTH_5 중 매칭 컬럼 선택
 *   3. 비활성(' ') 또는 인식 불가 코드 → null (호출자가 처리 결정)
 *
 * 결과는 SDOrderEntity.selectedHrTgtWidth 작업용 필드에 set.
 */
@Component
public class SelectedHrTgtWidthResolver {

    /** 5 폭 중 1 선택. 매핑 안되면 null. */
    public BigDecimal resolve(SDOrderEntity order) {
        if (order == null) return null;
        String confirmed = order.getConfirmedPlantCd();
        if (confirmed == null || confirmed.length() < 2) return null;

        char hrChar = confirmed.charAt(1); // 0=제강, 1=열연 위치
        return switch (hrChar) {
            case '1' -> order.getHrTgtWidth1();
            case '2' -> order.getHrTgtWidth2();
            case '3' -> order.getHrTgtWidth3();
            case '4' -> order.getHrTgtWidth4();
            case '5' -> order.getHrTgtWidth5();
            default -> null; // ' '(비활성) 또는 인식 불가
        };
    }

    /** SDOrderEntity 의 selectedHrTgtWidth 필드를 직접 set. */
    public void resolveAndSet(SDOrderEntity order) {
        order.setSelectedHrTgtWidth(resolve(order));
    }
}
