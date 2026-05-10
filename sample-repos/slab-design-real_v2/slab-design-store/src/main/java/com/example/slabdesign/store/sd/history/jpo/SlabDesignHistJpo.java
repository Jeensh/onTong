package com.example.slabdesign.store.sd.history.jpo;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Lob;
import jakarta.persistence.Table;
import java.time.LocalDateTime;

/**
 * sd · history · SLAB_DESIGN_HIST — Slab 설계 과정 이력 JPO.
 * Composite PK: (CMP_CD, ORG_CD, HIST_ID).
 *
 * 매 step 실행 시 1 row 적재. 성공·실패 모두 적재.
 *   - 성공: ERROR_CODE = NULL, SLAB_NO 채워짐, SNAPSHOT 에 step 결과
 *   - 실패: ERROR_CODE 채워짐, SLAB_NO = NULL (SLAB_RESULT 미저장), SNAPSHOT 에 실패 시점 상태
 */
@Entity
@Table(name = "SLAB_DESIGN_HIST")
@IdClass(SlabDesignHistPK.class)
public class SlabDesignHistJpo {

    @Id @Column(name = "CMP_CD", length = 2)
    private String cmpCd;

    @Id @Column(name = "ORG_CD", length = 1)
    private String orgCd;

    @Id @Column(name = "HIST_ID", length = 30)
    private String histId;

    /** FK → ORDER_OS (회사·소코드는 PK 와 공유). */
    @Column(name = "ORDER_NO", length = 20)
    private String orderNo;

    /** 관련 SLAB_RESULT — FAIL 시 NULL. */
    @Column(name = "SLAB_NO", length = 20)
    private String slabNo;

    @Column(name = "STEP_NO")
    private Integer stepNo;

    @Column(name = "STEP_NAME", length = 50)
    private String stepName;

    /** FAIL 시 에러 코드, 성공 시 NULL. */
    @Column(name = "ERROR_CODE", length = 20)
    private String errorCode;

    /** 중간값 스냅샷 — JSON 형태로 직렬화된 step 결과. */
    @Lob
    @Column(name = "SNAPSHOT")
    private String snapshot;

    @Column(name = "EVENT_TIME")
    private LocalDateTime eventTime;

    public String getCmpCd() { return cmpCd; }
    public void setCmpCd(String v) { this.cmpCd = v; }
    public String getOrgCd() { return orgCd; }
    public void setOrgCd(String v) { this.orgCd = v; }
    public String getHistId() { return histId; }
    public void setHistId(String v) { this.histId = v; }
    public String getOrderNo() { return orderNo; }
    public void setOrderNo(String v) { this.orderNo = v; }
    public String getSlabNo() { return slabNo; }
    public void setSlabNo(String v) { this.slabNo = v; }
    public Integer getStepNo() { return stepNo; }
    public void setStepNo(Integer v) { this.stepNo = v; }
    public String getStepName() { return stepName; }
    public void setStepName(String v) { this.stepName = v; }
    public String getErrorCode() { return errorCode; }
    public void setErrorCode(String v) { this.errorCode = v; }
    public String getSnapshot() { return snapshot; }
    public void setSnapshot(String v) { this.snapshot = v; }
    public LocalDateTime getEventTime() { return eventTime; }
    public void setEventTime(LocalDateTime v) { this.eventTime = v; }
}
