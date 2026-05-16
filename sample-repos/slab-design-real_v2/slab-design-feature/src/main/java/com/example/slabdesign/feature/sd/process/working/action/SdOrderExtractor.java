package com.example.slabdesign.feature.sd.process.working.action;

import com.example.slabdesign.store.sd.working.domain.entity.SDOrderEntity;
import com.example.slabdesign.store.sd.working.domain.logic.SDOrderLogic;
import com.example.slabdesign.store.sd.working.jpo.SDOrderChemicalJpo;
import com.example.slabdesign.store.sd.working.jpo.SDOrderOmJpo;
import com.example.slabdesign.store.sd.working.jpo.SDOrderOsJpo;
import com.example.slabdesign.store.sd.working.jpo.SDOrderPK;
import com.example.slabdesign.store.sd.working.jpo.SDOrderQdJpo;
import com.example.slabdesign.store.sd.working.repository.SDOrderChemicalRepository;
import com.example.slabdesign.store.sd.working.repository.SDOrderOmRepository;
import com.example.slabdesign.store.sd.working.repository.SDOrderOsRepository;
import com.example.slabdesign.store.sd.working.repository.SDOrderQdRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;

/**
 * sd · working · 설계 대상 주문 추출.
 *
 * Phase 1 1단계: 4 ORDER 테이블 (OS / OM / QD / CHEMICAL) 을 Join 하여
 * SDOrderEntity 통합. ORDER_OS 의 진도(C/D) + 종결플래그(NULL/0 통과) 필터 적용.
 *
 * 구현: ORDER_OS 의 필터링된 row 들을 먼저 가져온 뒤, 각 row 의 (회사·소·주문번호) 복합키로
 * OM/QD/CHEMICAL 을 Repository.findById 로 조회. SDOrderLogic 의 리플렉션 매핑이 4 JPO 의
 * 동명 필드를 통합하여 단일 SDOrderEntity 로 변환.
 *
 * NOTE: N+1 쿼리 발생. 데모 데이터 규모에서는 무시. 실제 운영에서는 fetch-join 또는
 * MyBatis 단일 SQL 로 최적화 필요 (시나리오 확장 후보).
 */
@Component
public class SdOrderExtractor {

    private final SDOrderOsRepository osRepository;
    private final SDOrderOmRepository omRepository;
    private final SDOrderQdRepository qdRepository;
    private final SDOrderChemicalRepository chemicalRepository;
    private final SDOrderLogic orderLogic;

    @Autowired
    public SdOrderExtractor(SDOrderOsRepository osRepository,
                            SDOrderOmRepository omRepository,
                            SDOrderQdRepository qdRepository,
                            SDOrderChemicalRepository chemicalRepository,
                            SDOrderLogic orderLogic) {
        this.osRepository = osRepository;
        this.omRepository = omRepository;
        this.qdRepository = qdRepository;
        this.chemicalRepository = chemicalRepository;
        this.orderLogic = orderLogic;
    }

    /**
     * 설계 대상 주문 추출. 정합성 점검은 별도 단계 (SdOrderValidator) 에서.
     *
     * @param cmpCd 회사코드
     * @param orgCd 소코드 (K=광양, P=포항)
     * @return 진도/종결 필터 통과한 SDOrderEntity 리스트 (4 JPO 통합 완료, 작업용 필드는 미설정)
     */
    @Transactional(readOnly = true)
    public List<SDOrderEntity> extractDesignableOrders(String cmpCd, String orgCd) {
        List<SDOrderOsJpo> osList = osRepository.findDesignable(cmpCd, orgCd);
        List<SDOrderEntity> result = new ArrayList<>(osList.size());

        for (SDOrderOsJpo os : osList) {
            SDOrderPK pk = new SDOrderPK(os.getCmpCd(), os.getOrgCd(), os.getOrderNo());
            SDOrderOmJpo om = omRepository.findById(pk).orElse(null);
            SDOrderQdJpo qd = qdRepository.findById(pk).orElse(null);
            SDOrderChemicalJpo chemical = chemicalRepository.findById(pk).orElse(null);

            SDOrderEntity entity = orderLogic.toEntity(os, om, qd, chemical);
            result.add(entity);
        }
        return result;
    }

    /**
     * 단일 주문 hydration — 진도/종결 필터 미적용 (호출자 책임).
     * SdDriver.singleDesign 진입점에서 사용.
     *
     * @return OS 미존재 시 null. 그 외 OM/QD/CHEM 부분 누락은 reflection logic 이 NULL 처리.
     */
    @Transactional(readOnly = true)
    public SDOrderEntity findOne(String cmpCd, String orgCd, String orderNo) {
        SDOrderPK pk = new SDOrderPK(cmpCd, orgCd, orderNo);
        SDOrderOsJpo os = osRepository.findById(pk).orElse(null);
        if (os == null) {
            return null;
        }
        SDOrderOmJpo om = omRepository.findById(pk).orElse(null);
        SDOrderQdJpo qd = qdRepository.findById(pk).orElse(null);
        SDOrderChemicalJpo chemical = chemicalRepository.findById(pk).orElse(null);
        return orderLogic.toEntity(os, om, qd, chemical);
    }
}
