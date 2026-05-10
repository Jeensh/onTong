package com.example.slabdesign.store.sd.working.domain.logic;

import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.jpo.SDOrderChemicalJpo;
import com.example.slabdesign.store.sd.working.jpo.SDOrderOmJpo;
import com.example.slabdesign.store.sd.working.jpo.SDOrderOsJpo;
import com.example.slabdesign.store.sd.working.jpo.SDOrderQdJpo;
import org.springframework.stereotype.Component;

/**
 * sd · working · 주문 도메인 변환 로직.
 *
 * 4개 JPO (OS/OM/QD/CHEMICAL) ↔ SDOrderEntity 변환을 담당하는 xxxStore 상위 모듈.
 * v2 변경: 기존 v1 의 리플렉션 기반 매핑을 명시적 setter 호출로 대체.
 *   - 정적 분석 도구가 호출 그래프를 직접 추적할 수 있다.
 *   - 필드별 의도가 코드 레벨에서 명시적으로 드러난다.
 *
 * 동명 필드 충돌 시 OS → OM → QD → CHEMICAL 순서로 first-non-null wins:
 *   - 복합 PK (cmpCd / orgCd / orderNo): 4 JPO 공유 — firstNonNull 로 OS 우선.
 *   - designPendQty: OS / OM 공유 — OS 우선.
 *   - 그 외 비-PK 필드는 단일 JPO 출처라 충돌 없음.
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
        SDOrderEntity e = new SDOrderEntity();

        // ============================================================
        // 복합 PK (4 JPO 공유) — firstNonNull, OS 우선.
        // ============================================================
        e.setCmpCd(firstNonNull(
            os  == null ? null : os.getCmpCd(),
            om  == null ? null : om.getCmpCd(),
            qd  == null ? null : qd.getCmpCd(),
            chm == null ? null : chm.getCmpCd()));
        e.setOrgCd(firstNonNull(
            os  == null ? null : os.getOrgCd(),
            om  == null ? null : om.getOrgCd(),
            qd  == null ? null : qd.getOrgCd(),
            chm == null ? null : chm.getOrgCd()));
        e.setOrderNo(firstNonNull(
            os  == null ? null : os.getOrderNo(),
            om  == null ? null : om.getOrderNo(),
            qd  == null ? null : qd.getOrderNo(),
            chm == null ? null : chm.getOrderNo()));

        // ============================================================
        // ORDER_OS — OS-전용 + designPendQty (OS / OM 공유, OS 우선).
        // ============================================================
        if (os != null) {
            e.setOsProgress(os.getOsProgress());
            e.setCloseFlag(os.getCloseFlag());
            e.setStockCode(os.getStockCode());
            e.setDesignPendQtyHigh(os.getDesignPendQtyHigh());
            e.setDesignPendQtyLow(os.getDesignPendQtyLow());
            e.setDesignPendQty(os.getDesignPendQty());
            e.setConfirmedPlantCd(os.getConfirmedPlantCd());
            e.setPossiblePlantCd(os.getPossiblePlantCd());
            e.setSmDue(os.getSmDue());
            e.setHrDue(os.getHrDue());
            e.setHrfDue(os.getHrfDue());
            e.setCrDue(os.getCrDue());
            e.setAnl1Due(os.getAnl1Due());
            e.setAnl2Due(os.getAnl2Due());
            e.setGalDue(os.getGalDue());
            e.setCrfDue(os.getCrfDue());
        }

        // ============================================================
        // ORDER_OM — OM-전용 + designPendQty fallback (OS 가 null 일 때).
        // ============================================================
        if (om != null) {
            e.setOrderWgtLow(om.getOrderWgtLow());
            e.setOrderWgtHigh(om.getOrderWgtHigh());
            e.setOrderWidth(om.getOrderWidth());
            e.setOrderLength(om.getOrderLength());
            // designPendQty: OS 가 이미 set 했으면 덮어쓰지 않음 (first-non-null wins).
            if (e.getDesignPendQty() == null) {
                e.setDesignPendQty(om.getDesignPendQty());
            }
            e.setWorkDue(om.getWorkDue());
            e.setPkgWgtLow(om.getPkgWgtLow());
            e.setPkgWgtHigh(om.getPkgWgtHigh());
            e.setProductCd(om.getProductCd());
            e.setCustomerCd(om.getCustomerCd());
            e.setProdDue(om.getProdDue());
            e.setDeliveryDue(om.getDeliveryDue());
        }

        // ============================================================
        // ORDER_QD — QD-전용 (강종 + 5 열연공장 목표 폭).
        // ============================================================
        if (qd != null) {
            e.setGradeCd(qd.getGradeCd());
            e.setHrTgtWidth1(qd.getHrTgtWidth1());
            e.setHrTgtWidth2(qd.getHrTgtWidth2());
            e.setHrTgtWidth3(qd.getHrTgtWidth3());
            e.setHrTgtWidth4(qd.getHrTgtWidth4());
            e.setHrTgtWidth5(qd.getHrTgtWidth5());
        }

        // ============================================================
        // ORDER_CHEMICAL — CHM-전용 (8 성분 × min/max/aim = 24).
        // ============================================================
        if (chm != null) {
            e.setCMin(chm.getCMin());   e.setCMax(chm.getCMax());   e.setCAim(chm.getCAim());
            e.setSiMin(chm.getSiMin()); e.setSiMax(chm.getSiMax()); e.setSiAim(chm.getSiAim());
            e.setMnMin(chm.getMnMin()); e.setMnMax(chm.getMnMax()); e.setMnAim(chm.getMnAim());
            e.setPMin(chm.getPMin());   e.setPMax(chm.getPMax());   e.setPAim(chm.getPAim());
            e.setSMin(chm.getSMin());   e.setSMax(chm.getSMax());   e.setSAim(chm.getSAim());
            e.setCrMin(chm.getCrMin()); e.setCrMax(chm.getCrMax()); e.setCrAim(chm.getCrAim());
            e.setNiMin(chm.getNiMin()); e.setNiMax(chm.getNiMax()); e.setNiAim(chm.getNiAim());
            e.setAlMin(chm.getAlMin()); e.setAlMax(chm.getAlMax()); e.setAlAim(chm.getAlAim());
        }

        return e;
    }

    /**
     * first-non-null wins helper. v1 리플렉션의 동명 필드 precedence 를 명시적으로 표현.
     */
    @SafeVarargs
    private static <T> T firstNonNull(T... vs) {
        for (T v : vs) {
            if (v != null) return v;
        }
        return null;
    }
}
