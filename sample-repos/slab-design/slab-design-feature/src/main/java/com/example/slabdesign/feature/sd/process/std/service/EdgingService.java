package com.example.slabdesign.feature.sd.process.std.service;

import com.example.slabdesign.store.sd.std.domain.entity.EdgingGroupEntity;
import com.example.slabdesign.store.sd.std.domain.entity.EdgingSpecEntity;
import com.example.slabdesign.store.sd.std.domain.logic.EdgingGroupLogic;
import com.example.slabdesign.store.sd.std.domain.logic.EdgingSpecLogic;
import com.example.slabdesign.store.sd.std.oracle.jpo.EdgingGroupJpo;
import com.example.slabdesign.store.sd.std.oracle.jpo.EdgingSpecJpo;
import com.example.slabdesign.store.sd.std.oracle.jpo.EdgingSpecPK;
import com.example.slabdesign.store.sd.std.oracle.repository.EdgingGroupRepository;
import com.example.slabdesign.store.sd.std.oracle.repository.EdgingSpecRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.List;
import java.util.Optional;

/**
 * sd · std · Edging 룩업 통합 서비스.
 *
 * 두 단계 룩업:
 *   1. findGroup: (강종/품종/고객/열연목표폭) 조건 매칭 + 우선순위 ASC, 첫 row 반환 (없으면 null)
 *   2. findSpec: (회사/소/그룹코드) 정확매칭 → 미존재 시 '*' fallback
 *      - 양쪽 모두 미존재 시 IllegalStateException (사용자 사양: DG 코드 미할당)
 *
 * @author 김XX (2017-08-21)
 * @author 최XX (2019-05-14 — '*' fallback 추가, 이전엔 group 매칭 필수)
 */
// 2018-02 운영이슈 P-2018-0237: '*' fallback 도입 전엔 매칭 누락 시 NullPointerException
//                                 → 일부 라인 작업 중단 사고. fallback 도입으로 해결.
// 2020-11 검토: 정확매칭 없이 '*' 만 있는 경우는 의도된 catchall 이지만, 양쪽 다 없으면
//                 데이터 정합성 이슈 → IllegalStateException 으로 시스템 알림
@Service
public class EdgingService {

    private final EdgingGroupRepository groupRepository;
    private final EdgingGroupLogic groupLogic;
    private final EdgingSpecRepository specRepository;
    private final EdgingSpecLogic specLogic;

    @Autowired
    public EdgingService(EdgingGroupRepository groupRepository, EdgingGroupLogic groupLogic,
                         EdgingSpecRepository specRepository, EdgingSpecLogic specLogic) {
        this.groupRepository = groupRepository;
        this.groupLogic = groupLogic;
        this.specRepository = specRepository;
        this.specLogic = specLogic;
    }

    /**
     * EDGING_GROUP 매칭 조회. 조건:
     *   GRADE_CD = ? AND PRODUCT_TYPE_CD = ? AND CUSTOMER_CD = ?
     *   AND HR_TGT_WIDTH_LOW ≤ hrTgtWidth AND HR_TGT_WIDTH_HIGH ≥ hrTgtWidth
     * ORDER BY PRIORITY ASC, 첫 row 반환.
     */
    public EdgingGroupEntity findGroup(String cmpCd, String orgCd,
                                       String gradeCd, String productTypeCd, String customerCd,
                                       BigDecimal hrTgtWidth) {
        List<EdgingGroupJpo> matches = groupRepository
            .findByCmpCdAndOrgCdAndGradeCdAndProductTypeCdAndCustomerCdAndHrTgtWidthLowLessThanEqualAndHrTgtWidthHighGreaterThanEqualOrderByPriorityAsc(
                cmpCd, orgCd, gradeCd, productTypeCd, customerCd, hrTgtWidth, hrTgtWidth);
        if (matches.isEmpty()) return null;
        return groupLogic.toEntity(matches.get(0));
    }

    /**
     * EDGING_SPEC 룩업.
     * 1. (cmpCd, orgCd, edgingGroupCd) 정확매칭
     * 2. 미존재 시 (cmpCd, orgCd, '*') fallback
     * 3. 양쪽 모두 미존재 시 IllegalStateException
     */
    public EdgingSpecEntity findSpec(String cmpCd, String orgCd, String edgingGroupCd) {
        // 1) 정확매칭
        Optional<EdgingSpecJpo> exact = specRepository.findById(
            new EdgingSpecPK(cmpCd, orgCd, edgingGroupCd));
        if (exact.isPresent()) return specLogic.toEntity(exact.get());

        // 2) '*' fallback
        Optional<EdgingSpecJpo> wildcard = specRepository.findById(
            new EdgingSpecPK(cmpCd, orgCd, "*"));
        if (wildcard.isPresent()) return specLogic.toEntity(wildcard.get());

        // 3) 양쪽 모두 미존재 — 데이터 정합성 운영 이슈
        throw new IllegalStateException(
            "EDGING_SPEC not found: groupCd=" + edgingGroupCd + " AND '*' fallback both missing");
    }
}
